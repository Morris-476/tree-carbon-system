import pandas as pd
import numpy as np

# ========== 設定 ==========
ARDUINO_FILE = 'arduino_final.csv'
MIN_RECORDS = 2       # 少於此筆數標記為存疑
GAP_SECONDS = 2       # 間隔超過幾秒視為不同棵樹
MAX_VALID_DIST = 800  # ToF 有效距離上限（cm）

# ========== 讀取 Arduino 數據 ==========
df = pd.read_csv(ARDUINO_FILE)
df.columns = df.columns.str.strip()
df['DATETIME'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])

# 只保留 ToF1 NORMAL 且距離在有效範圍內
valid = df[
    (df['ToF1_Status'] == 'NORMAL') &
    (df['Dist1_cm'] > 0) &
    (df['Dist1_cm'] <= MAX_VALID_DIST)
].copy().reset_index(drop=True)

# 用時間間隔分群（同一棵樹的連續讀值）
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

print("\n" + "=" * 70)

# 儲存 CSV（不含原始距離列表欄位）
output = result.drop(columns=['原始距離列表'])
output.to_csv('tree_analysis_result_v2.csv', encoding='utf-8-sig')
print("✓ 結果已儲存至：tree_analysis_result_v2.csv")
