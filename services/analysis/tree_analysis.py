import pandas as pd
import numpy as np

from services.core import db as db_service

# ========== 設定 ==========
MIN_RECORDS = 2       # 少於此筆數標記為存疑
GAP_SECONDS = 2       # 同一站點的 track_id 時間序列，間隔超過幾秒視為換了一部影片
MAX_VALID_DIST = 800  # ToF 有效距離上限（cm）


def load_measurements() -> pd.DataFrame:
    """從 Measurements 資料表讀取原始感測器讀值
    （record_id/DATE/TIME/Laser_Status/ToF_Dist1_cm/site_name/track_id）。"""
    conn = db_service.get_db_connection()
    if conn is None:
        raise RuntimeError("資料庫連線失敗，無法讀取 Measurements 資料")
    try:
        return pd.read_sql("""
            SELECT [record_id], [DATE], [TIME], [Laser_Status], [ToF_Dist1_cm],
                   [site_name], [track_id]
            FROM Measurements
            ORDER BY [DATE], [TIME]
        """, conn)
    finally:
        conn.close()


def ensure_final_dist_column() -> None:
    """確保 Measurements.Final_Dist_cm 欄位存在（不存在才新增，可重複執行）。"""
    conn = db_service.get_db_connection()
    if conn is None:
        raise RuntimeError("資料庫連線失敗，無法檢查/新增 Final_Dist_cm 欄位")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'Measurements' AND COLUMN_NAME = 'Final_Dist_cm'
            )
            ALTER TABLE Measurements ADD Final_Dist_cm FLOAT NULL
        """)
        conn.commit()
    finally:
        conn.close()


def write_final_distances(result: pd.DataFrame) -> None:
    """把每群（每棵樹）去極端值後的平均距離寫回該群代表列的 Final_Dist_cm。
    寫入前先把全表 Final_Dist_cm 清成 NULL，避免分群邏輯改變後，
    不再是代表列的舊值殘留在資料庫裡變成過期的假資料。
    """
    conn = db_service.get_db_connection()
    if conn is None:
        raise RuntimeError("資料庫連線失敗，無法寫回 Final_Dist_cm")
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE Measurements SET Final_Dist_cm = NULL")
        for _, row in result.iterrows():
            cursor.execute(
                "UPDATE Measurements SET Final_Dist_cm = ? WHERE record_id = ?",
                float(row['平均距離_cm']), int(row['record_id'])
            )
        conn.commit()
    finally:
        conn.close()


# 分群邏輯：
#   - 以 track_id（影片追蹤編號）為主：沒有偵測到樹幹（track_id 為 NULL）的
#     影格直接排除，不算獨立的樹。
#   - 該站點完全沒有 track_id 資料（舊式純 ToF 資料）時，代表無法辨別是哪一棵樹，
#     直接整批排除、不納入任何計算，不再 fallback 用時間間隔分群。
#   - 同一站點常常分多部影片上傳，而每部影片的 track_id 都會從 1 重新編號，
#     若只用 (site_name, track_id) 當 key，不同影片的 1 號樹會被誤判成同一棵。
#     這裡先用時間間隔（超過 GAP_SECONDS 秒視為換了一部影片）切出「影片批次」，
#     同一批次內才用 track_id 分群，key 變成 (site_name, 影片批次序號, track_id)，
#     確保 tree id 不會跨影片重複。
def _assign_tree_key(site_df: pd.DataFrame) -> pd.DataFrame:
    site_df = site_df.sort_values('DATETIME').reset_index(drop=True)
    if not site_df['track_id'].notna().any():
        return site_df.iloc[0:0].assign(video_seq=[], tree_key=[], iqr_key=[])
    site_df = site_df[site_df['track_id'].notna()].copy()
    video_gap = site_df['DATETIME'].diff().dt.total_seconds().fillna(0) > GAP_SECONDS
    site_df['video_seq'] = video_gap.cumsum()
    site_df['tree_key'] = list(zip(site_df['site_name'], site_df['video_seq'], site_df['track_id']))
    # IQR 去極端值以同一影片批次內的多棵樹（多個 track_id）合併計算，
    # 而非單一 track_id 自己一群。
    site_df['iqr_key'] = list(zip(site_df['site_name'], site_df['video_seq']))
    return site_df


def compute_tree_groups(df: pd.DataFrame) -> pd.DataFrame:
    """把清洗過的 Measurements 依 tree_key 分群，對每群 ToF 距離做 IQR 去極端值後取平均。"""
    # 去除重複匯入的資料：
    #   曾發現同一批量測（同站點、同時間戳記、同距離、同 track_id）被完整重複寫入
    #   資料庫好幾次（例如同一秒的同一筆讀值出現在 4 個不同的 record_id）。
    #   時間間隔分群完全依賴時間戳記排序，遇到這種重複資料會把彼此不相干、
    #   record_id 差很遠的重複列誤判成同一群。這裡在分群前先去重，只保留
    #   record_id 最小（最早寫入）的那一筆。
    df = df.sort_values('record_id').drop_duplicates(
        subset=['site_name', 'DATE', 'TIME', 'ToF_Dist1_cm', 'track_id'],
        keep='first'
    ).reset_index(drop=True)

    valid = pd.concat(
        [_assign_tree_key(g) for _, g in df.groupby('site_name', dropna=False)],
        ignore_index=True
    )

    # 去除極端值（IQR法）：
    # Q1/Q3 門檻依 iqr_key 計算 —— 同一影片批次內所有物件（多個 track_id）合併算，
    # 再各自套用門檻過濾自己的讀值。
    grp = valid.groupby('iqr_key')['ToF_Dist1_cm']
    q1 = grp.transform('quantile', 0.25)
    q3 = grp.transform('quantile', 0.75)
    iqr = q3 - q1
    in_range = valid['ToF_Dist1_cm'].between(q1 - 1.5 * iqr, q3 + 1.5 * iqr)
    valid['ToF_filtered'] = valid['ToF_Dist1_cm'].where(in_range)

    # record_id 取該群「中間（偏後）」那一筆，讓寫回 Final_Dist_cm 的代表列
    # 盡量落在群內資料的中段，而不是永遠卡在最前面。
    result = valid.groupby('tree_key').agg(
        record_id=('record_id', lambda s: s.iloc[len(s) // 2]),
        站點=('site_name', 'first'),
        track_id=('track_id', 'first'),
        開始時間=('DATETIME', 'first'),
        結束時間=('DATETIME', 'last'),
        筆數=('ToF_Dist1_cm', 'count'),
        平均距離_cm=('ToF_filtered', lambda x: round(x.mean(), 1)),
        最小距離_cm=('ToF_Dist1_cm', 'min'),
        最大距離_cm=('ToF_Dist1_cm', 'max'),
        原始距離列表=('ToF_Dist1_cm', lambda x: list(x)),
    ).reset_index(drop=True)

    result['資料品質'] = result['筆數'].apply(
        lambda x: '✓ 有效' if x >= MIN_RECORDS else '⚠ 存疑（筆數不足）'
    )
    result.index = result.index + 1
    result.index.name = '樹木編號'
    return result


def analyze_and_write_final_distances(verbose: bool = True, save_csv: bool = True) -> dict:
    """完整流程：讀取 Measurements → 篩選有效 ToF 讀值 → 分群 → IQR 去極端值取平均
    → 寫回 Measurements.Final_Dist_cm。供 data_pipeline.py 在每次上傳資料後呼叫，
    也可直接執行本檔案（見下方 __main__）獨立跑一次。

    Returns:
        dict：{'group_count': 分群後的樹木數量}
    """
    df = load_measurements()
    df.columns = df.columns.str.strip()
    df['DATETIME'] = pd.to_datetime(df['DATE'].astype(str) + ' ' + df['TIME'].astype(str))

    # 只保留 ToF1（Laser）ON 且距離在有效範圍內
    valid = df[
        (df['Laser_Status'] == 'ON') &
        (df['ToF_Dist1_cm'] > 0) &
        (df['ToF_Dist1_cm'] <= MAX_VALID_DIST)
    ].copy().reset_index(drop=True)

    result = compute_tree_groups(valid)

    if verbose:
        print("=" * 70)
        print("樹木量測數據分析結果")
        print("=" * 70)
        for idx, row in result.iterrows():
            print(f"\n【樹木 {idx}】{row['資料品質']}")
            print(f"  量測時間：{row['開始時間'].strftime('%H:%M:%S')} ~ {row['結束時間'].strftime('%H:%M:%S')}")
            print(f"  有效筆數：{row['筆數']} 筆")
            print(f"  距離原始值：{row['原始距離列表']} cm")
            print(f"  平均距離（去極端值後）：{row['平均距離_cm']} cm")
            print(f"  最小距離：{row['最小距離_cm']} cm｜最大距離：{row['最大距離_cm']} cm")
        print("\n" + "=" * 70)

    if save_csv:
        output = result.drop(columns=['原始距離列表', 'record_id'])
        output.to_csv('tree_analysis_result_v2.csv', encoding='utf-8-sig')
        if verbose:
            print("✓ 結果已儲存至：tree_analysis_result_v2.csv")

    ensure_final_dist_column()
    write_final_distances(result)
    if verbose:
        print(f"✓ 已將 {len(result)} 群的平均距離寫回 Measurements.Final_Dist_cm")

    return {'group_count': len(result)}


if __name__ == '__main__':
    analyze_and_write_final_distances()
