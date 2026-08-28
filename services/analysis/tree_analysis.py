import pandas as pd
import numpy as np

# ========== 設定 ==========
ARDUINO_FILE = 'arduino_final.csv'
RTK_FILE = 'rtk_final.csv'
VIDEO_START = pd.Timestamp('2026-08-01 18:24:01')
MIN_RECORDS = 2       # 少於此筆數標記為存疑
GAP_SECONDS = 1       # 間隔超過幾秒視為不同棵樹
MAX_VALID_DIST = 800  # ToF 有效距離上限（cm）

# ========== 讀取 Arduino 數據 ==========
df = pd.read_csv(ARDUINO_FILE)
df.columns = df.columns.str.strip()
df['DATETIME'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])

# 砍掉距離為 0（無效讀值）或超過上限（感測器飽和值）的讀值
valid = df[
    (df['Dist1_cm'] != 0) &
    (df['Dist1_cm'] <= MAX_VALID_DIST)
].copy().reset_index(drop=True)

# 用時間間隔分群
valid['gap'] = valid['DATETIME'].diff().dt.total_seconds().fillna(0) > GAP_SECONDS
valid['tree_group'] = valid['gap'].cumsum()

# 去除極端值函式（IQR法）
def remove_outliers_and_mean(series):
    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    filtered = series[(series >= Q1 - 1.5 * IQR) & (series <= Q3 + 1.5 * IQR)]
    return round(filtered.mean(), 1)

# 每群統計
result = valid.groupby('tree_group').agg(
    開始時間=('DATETIME', 'first'),
    結束時間=('DATETIME', 'last'),
    筆數=('Dist1_cm', 'count'),
    平均距離_cm=('Dist1_cm', remove_outliers_and_mean),
    最小距離_cm=('Dist1_cm', 'min'),
    最大距離_cm=('Dist1_cm', 'max'),
    原始距離列表=('Dist1_cm', lambda x: list(x)),
).reset_index(drop=True)

result['資料品質'] = result['筆數'].apply(
    lambda x: '✓ 有效' if x >= MIN_RECORDS else '⚠ 存疑（筆數不足）'
)
result.index = result.index + 1
result.index.name = '樹木編號'

# ========== 讀取 RTK 數據 ==========
rtk = pd.read_csv(RTK_FILE)
rtk.columns = rtk.columns.str.strip()

rtk['DATETIME'] = pd.to_datetime(
    '20' + rtk['DATE'].astype(str).str.zfill(6) + rtk['TIME'].astype(str).str.zfill(6),
    format='%Y%m%d%H%M%S'
)

def parse_coord(val):
    val = str(val).strip()
    direction = val[-1]
    num = float(val[:-1])
    return -num if direction in ['S', 'W'] else num

rtk['LAT'] = rtk['LATITUDE N/S'].apply(parse_coord)
rtk['LON'] = rtk['LONGITUDE E/W'].apply(parse_coord)

# ========== 時間對齊：找每棵樹對應的 RTK 座標 ==========
def get_rtk_for_tree(start, end):
    mask = (rtk['DATETIME'] >= start) & (rtk['DATETIME'] <= end)
    matched = rtk[mask]
    if len(matched) == 0:
        idx = (rtk['DATETIME'] - start).abs().idxmin()
        matched = rtk.iloc[[idx]]
    lat = round(matched['LAT'].mean(), 7)
    lon = round(matched['LON'].mean(), 7)
    return pd.Series({'緯度': lat, '經度': lon})

rtk_coords = result.apply(
    lambda row: get_rtk_for_tree(row['開始時間'], row['結束時間']), axis=1
)
result = pd.concat([result, rtk_coords], axis=1)

# ========== 影片時間對齊 ==========
result['影片開始秒數'] = (result['開始時間'] - VIDEO_START).dt.total_seconds().astype(int)
result['影片結束秒數'] = (result['結束時間'] - VIDEO_START).dt.total_seconds().astype(int)

# ========== 輸出結果 ==========
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
    print(f"  RTK 座標：{row['緯度']}, {row['經度']}")
    print(f"  對應影片：第 {row['影片開始秒數']} 秒 ~ 第 {row['影片結束秒數']} 秒")

print("\n" + "=" * 70)

# 儲存 CSV（不含原始距離列表欄位）
output = result.drop(columns=['原始距離列表'])
output.to_csv('tree_analysis_result_v2.csv', encoding='utf-8-sig')
print("✓ 結果已儲存至：tree_analysis_result_v2.csv")