# 負責人：Morris、justin99lin
# 開發日期：2026/08/27
# 用途：對 Measurements 分群並用 IQR 去極端值，取代表距離／像素寬度／GPS 寫回

import pandas as pd
import numpy as np

from services.core import db as db_service

# ========== 設定 ==========
MIN_RECORDS = 2       # 少於此筆數標記為存疑
GAP_SECONDS = 2       # 同一站點的 track_id 時間序列，間隔超過幾秒視為換了一部影片
MAX_VALID_DIST = 800  # ToF 有效距離上限（cm）

# 同一棵樹相鄰兩筆距離讀值超過此值視為跳掉（樣本數少時 IQR 無法有效篩掉離群值）
MAX_CONSECUTIVE_JUMP_CM = 200


def load_measurements() -> pd.DataFrame:
    """從 Measurements 讀取原始感測器讀值，含分群/代表列挑選需要的欄位。
    has_image 只取有無旗標、不拉 image_data 本體，避免整表 blob 一次讀進記憶體。
    """
    conn = db_service.get_db_connection()
    if conn is None:
        raise RuntimeError('資料庫連線失敗，無法讀取 Measurements 資料')
    try:
        return pd.read_sql('''
            SELECT [record_id], [DATE], [TIME], [Laser_Status], [ToF_Dist1_cm],
                   [site_name], [track_id], [pixel_width], [latitude], [longitude],
                   [HEADING], CASE WHEN [image_data] IS NOT NULL THEN 1 ELSE 0 END AS has_image
            FROM Measurements
            ORDER BY [DATE], [TIME]
        ''', conn)
    finally:
        conn.close()


def ensure_final_dist_column() -> None:
    """確保 Final_Dist_cm（代表距離）／video_seq（分群用的影片批次序號）／
    Final_Pixel_Width（整群平均後的樹幹像素寬度）欄位存在，可重複執行。
    """
    conn = db_service.get_db_connection()
    if conn is None:
        raise RuntimeError('資料庫連線失敗，無法檢查/新增分析欄位')
    try:
        cursor = conn.cursor()
        for col, ddl in (
            ('Final_Dist_cm', 'FLOAT NULL'),
            ('video_seq', 'INT NULL'),
            ('Final_Pixel_Width', 'FLOAT NULL'),
        ):
            cursor.execute(f'''
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'Measurements' AND COLUMN_NAME = '{col}'
                )
                ALTER TABLE Measurements ADD [{col}] {ddl}
            ''')
        conn.commit()
    finally:
        conn.close()


def write_final_distances(result: pd.DataFrame) -> None:
    """把每群（每棵樹）算好的代表值（距離、影片批次、平均樹幹寬度、
    GPS／方位角）寫回該群代表列。寫入前先清空全表這幾欄，避免分群邏輯
    改變後，舊代表列殘留過期資料。"""
    conn = db_service.get_db_connection()
    if conn is None:
        raise RuntimeError('資料庫連線失敗，無法寫回代表列資料')
    try:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE Measurements SET Final_Dist_cm = NULL, video_seq = NULL, '
            'Final_Pixel_Width = NULL'
        )
        for _, row in result.iterrows():
            cursor.execute(
                'UPDATE Measurements SET Final_Dist_cm = ?, video_seq = ?, '
                'Final_Pixel_Width = ?, latitude = ?, longitude = ?, HEADING = ? '
                'WHERE record_id = ?',
                float(row['平均距離_cm']), int(row['影片批次']),
                None if pd.isna(row['平均像素寬度']) else float(row['平均像素寬度']),
                None if pd.isna(row['平均緯度']) else float(row['平均緯度']),
                None if pd.isna(row['平均經度']) else float(row['平均經度']),
                None if pd.isna(row['平均方位角']) else float(row['平均方位角']),
                int(row['record_id'])
            )
        conn.commit()
    finally:
        conn.close()


# 分群邏輯：先用時間間隔切出 video_seq（避免同站點多次上傳被誤判成同批）；
# 批次內有 track_id 時以 track_id 分棵樹，沒偵測到樹幹（track_id 為 NULL）
# 的影格排除；完全沒有 track_id（舊式純 ToF 資料）時整批視為一棵樹
def _assign_tree_key(site_df: pd.DataFrame) -> pd.DataFrame:
    site_df = site_df.sort_values('DATETIME').reset_index(drop=True)
    gap = site_df['DATETIME'].diff().dt.total_seconds().fillna(0) > GAP_SECONDS
    site_df['video_seq'] = gap.cumsum()
    if site_df['track_id'].notna().any():
        site_df = site_df[site_df['track_id'].notna()].copy()
        site_df['tree_key'] = list(zip(site_df['site_name'], site_df['video_seq'], site_df['track_id']))
    else:
        site_df['tree_key'] = list(zip(site_df['site_name'], site_df['video_seq']))
    return site_df


# 去除極端值函式（IQR法）
def remove_outliers_and_mean(series):
    series = series.dropna()
    if series.empty:
        return float('nan')
    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    filtered = series[(series >= Q1 - 1.5 * IQR) & (series <= Q3 + 1.5 * IQR)]
    return round(filtered.mean(), 1)


def _longest_continuous_run(series: pd.Series) -> pd.Series:
    """series 須已依時間排序。相鄰讀值差距超過 MAX_CONSECUTIVE_JUMP_CM 視為
    斷點，回傳斷點切出來最長的一段（先篩掉跳掉的讀值，IQR 才不會在樣本數
    很少時失效）；少於 2 筆讀值時無從判斷連續性，原樣回傳。"""
    values = series.to_numpy()
    if len(values) < 2:
        return series

    diffs = np.abs(np.diff(values))
    breaks = np.where(diffs > MAX_CONSECUTIVE_JUMP_CM)[0] + 1
    starts = np.concatenate(([0], breaks))
    ends = np.concatenate((breaks, [len(values)]))
    best = np.argmax(ends - starts)
    return series.iloc[starts[best]:ends[best]]


# 代表列取「群內有截圖、且量到樹幹寬度最大」的那一秒（拍得最清楚），群內
# 沒有符合的才退回時間中位數；距離、樹幹寬度用整群 IQR 平均，GPS/方位角
# 用群內所有有效秒數平均，不再只看代表列自己那一秒有沒有資料
def _summarize_group(g: pd.DataFrame) -> pd.Series:
    photo_candidates = g[(g['has_image'] == 1) & g['pixel_width'].notna()]
    if len(photo_candidates) > 0:
        record_id = photo_candidates.loc[photo_candidates['pixel_width'].idxmax(), 'record_id']
    else:
        record_id = g.iloc[len(g) // 2]['record_id']

    gps = g[['latitude', 'longitude', 'HEADING']].dropna()

    # 距離平均優先取「同時有量到寬度」的幀，跟像素寬度用同一批樣本，否則
    # 取樣範圍不一致時（例如遠距離沒偵測到寬度的幀仍算進距離平均），樹徑
    # 換算會拿到對不到同一拍攝時刻的距離與寬度
    g_with_width = g[g['pixel_width'].notna()]
    dist_source = g_with_width['ToF_Dist1_cm'] if len(g_with_width) > 0 else g['ToF_Dist1_cm']
    dist_source = _longest_continuous_run(dist_source)

    return pd.Series({
        'record_id': record_id,
        '站點': g['site_name'].iloc[0],
        'track_id': g['track_id'].iloc[0],
        '影片批次': g['video_seq'].iloc[0],
        '開始時間': g['DATETIME'].iloc[0],
        '結束時間': g['DATETIME'].iloc[-1],
        '筆數': g['ToF_Dist1_cm'].count(),
        '平均距離_cm': remove_outliers_and_mean(dist_source),
        '最小距離_cm': g['ToF_Dist1_cm'].min(),
        '最大距離_cm': g['ToF_Dist1_cm'].max(),
        '原始距離列表': list(g['ToF_Dist1_cm']),
        '平均像素寬度': remove_outliers_and_mean(g['pixel_width']),
        '平均緯度': gps['latitude'].mean() if len(gps) else float('nan'),
        '平均經度': gps['longitude'].mean() if len(gps) else float('nan'),
        '平均方位角': gps['HEADING'].mean() if len(gps) else float('nan'),
    })


def compute_tree_groups(df: pd.DataFrame) -> pd.DataFrame:
    """把清洗過的 Measurements 依 tree_key 分群，算出每群的代表值。"""
    # 同一批量測曾被完整重複寫入資料庫好幾次，時間間隔分群會把這些重複列
    # 誤判成同一群，故分群前先去重，只保留 record_id 最小（最早寫入）的那一筆
    df = df.sort_values('record_id').drop_duplicates(
        subset=['site_name', 'DATE', 'TIME', 'ToF_Dist1_cm', 'track_id'],
        keep='first'
    ).reset_index(drop=True)

    valid = pd.concat(
        [_assign_tree_key(g) for _, g in df.groupby('site_name', dropna=False)],
        ignore_index=True
    )

    result = valid.groupby('tree_key').apply(_summarize_group).reset_index(drop=True)

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

    回傳 {'group_count': 分群後的樹木數量}。
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
        print('=' * 70)
        print('樹木量測數據分析結果')
        print('=' * 70)
        for idx, row in result.iterrows():
            print(f"\n【樹木 {idx}】{row['資料品質']}")
            print(f"  量測時間：{row['開始時間'].strftime('%H:%M:%S')} ~ {row['結束時間'].strftime('%H:%M:%S')}")
            print(f"  有效筆數：{row['筆數']} 筆")
            print(f"  距離原始值：{row['原始距離列表']} cm")
            print(f"  平均距離（去極端值後）：{row['平均距離_cm']} cm")
            print(f"  最小距離：{row['最小距離_cm']} cm｜最大距離：{row['最大距離_cm']} cm")
        print('\n' + '=' * 70)

    if save_csv:
        output = result.drop(columns=['原始距離列表', 'record_id'])
        output.to_csv('tree_analysis_result_v2.csv', encoding='utf-8-sig')
        if verbose:
            print('✓ 結果已儲存至：tree_analysis_result_v2.csv')

    ensure_final_dist_column()
    write_final_distances(result)
    if verbose:
        print(f'✓ 已將 {len(result)} 群的平均距離寫回 Measurements.Final_Dist_cm')

    return {'group_count': len(result)}


if __name__ == '__main__':
    analyze_and_write_final_distances()
