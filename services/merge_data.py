# 負責人：蔡宗倫
# 開發日期：2026/08/16
# 2026/08/24 修改：改為純運算邏輯（不寫入資料庫、不輸出檔案），供 /api/upload 上傳流程呼叫
# 用意：對齊 Arduino(ToF) 與 RTK 的 CSV 數據，並推算影片起始時間，回傳合併後的資料

import os
from datetime import datetime

import pandas as pd


class MergeDataError(Exception):
    """合併過程發生錯誤時拋出，包含具體失敗原因。"""


def _read_tof_csv(arduino_path: str) -> pd.DataFrame:
    # TREE_0xx.CSV 前面有幾行空白/雜訊列，實際表頭是第一個以 Tree_ID 開頭的那一行
    with open(arduino_path, encoding='utf-8-sig') as f:
        lines = f.readlines()
    try:
        header_idx = next(i for i, line in enumerate(lines) if line.strip().startswith('Tree_ID'))
    except StopIteration:
        raise MergeDataError(f'Arduino 檔案中找不到表頭列（Tree_ID 開頭），請檢查檔案格式：{arduino_path}')

    df = pd.read_csv(arduino_path, skiprows=header_idx, encoding='utf-8-sig')
    df.columns = [c.strip() for c in df.columns]

    required = ['Tree_ID', 'DATE', 'TIME', 'Laser_Status', 'LED_Status', 'ToF_Dist1_cm', 'ToF_Dist2_cm']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise MergeDataError(f'Arduino 檔案缺少必要欄位 {missing}，請檢查檔案格式：{arduino_path}')

    df['recorded_at'] = pd.to_datetime(df['DATE'].astype(str) + ' ' + df['TIME'].astype(str))
    return df.drop(columns=['DATE', 'TIME'])


def _parse_rtk_datetime(date_val, time_val) -> datetime:
    # RTK DATE 為 YYMMDD、TIME 為 HHMMSS（皆可能省略前導 0，故 zfill 補齊）
    d = str(int(date_val)).zfill(6)
    t = str(int(time_val)).zfill(6)
    return datetime(2000 + int(d[0:2]), int(d[2:4]), int(d[4:6]), int(t[0:2]), int(t[2:4]), int(t[4:6]))


def _parse_coord(value: str) -> float:
    # 例如 "25.0883747N" -> 25.0883747，"121.4649937E" -> 121.4649937；S/W 為負值
    text = str(value).strip()
    sign = -1 if text[-1] in ('S', 'W') else 1
    return sign * float(text[:-1])


def _read_rtk_csv(rtk_path: str) -> pd.DataFrame:
    df = pd.read_csv(rtk_path, encoding='utf-8-sig')
    df.columns = [c.strip() for c in df.columns]

    required = ['INDEX', 'TAG', 'DATE', 'TIME', 'LATITUDE N/S', 'LONGITUDE E/W', 'HEIGHT', 'SPEED', 'HEADING']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise MergeDataError(f'RTK 檔案缺少必要欄位 {missing}，請檢查檔案格式：{rtk_path}')

    df['recorded_at'] = [_parse_rtk_datetime(d, t) for d, t in zip(df['DATE'], df['TIME'])]
    df['latitude'] = df['LATITUDE N/S'].apply(_parse_coord)
    df['longitude'] = df['LONGITUDE E/W'].apply(_parse_coord)

    # 依需求刪除 RTK 的 INDEX 欄位；DATE/TIME/原始經緯度欄位已轉換為 recorded_at/latitude/longitude，不再保留
    return df.drop(columns=['INDEX', 'DATE', 'TIME', 'LATITUDE N/S', 'LONGITUDE E/W'])


def align_sensor_data(
    arduino_path: str,
    rtk_path: str,
    video_filename: "str | None" = None,
    video_start_at: "datetime | None" = None,
    max_gap_seconds: int = 3,
) -> dict:
    """
    對齊 Arduino(ToF) 與 RTK 的時間戳記並合併，推算影片起始時間，回傳合併後的資料。
    純運算邏輯，不寫入資料庫、不輸出檔案。

    對齊邏輯：
      - 以 Arduino(ToF) 的紀錄為主軸（逐秒連續紀錄），用 merge_asof 抓最接近時間的 RTK 紀錄
        （容忍誤差 max_gap_seconds 內才算配對成功，超過就是沒有 GPS 座標的那幾秒）
      - 影片起始時間：Arduino 開機記錄與錄影幾乎同時開始，因此以 Arduino 最早一筆時間戳記
        作為影片第 0 影格的真實時間（若呼叫端已知更準確的時間，可用 video_start_at 覆蓋）
        ⚠️ 之所以不用 RTK 最早時間戳記，是因為 GPS 定位需要數秒到十幾秒才能拿到第一筆有效座標，
           RTK 檔案的第一筆紀錄時間會比實際開始晚，用它當基準會讓影片offset系統性偏移
      - 合併後重複欄位（兩份檔案都有的 DATE/TIME）只保留一份，統一為 recorded_at

    Args:
        arduino_path:     Arduino(ToF) CSV 路徑，例如 TREE_015.CSV
        rtk_path:          RTK CSV 路徑，例如 01182401.CSV
        video_filename:    對應的影片檔名，供辨識結果標記使用（可為 None）
        video_start_at:    影片第 0 影格的真實時間；未提供時自動取 Arduino 最早時間戳記
        max_gap_seconds:   RTK 與 Arduino 紀錄的最大容忍時間差（秒），預設 3 秒

    Returns:
        dict，成功時含：
          status='success', message, records（對齊後每筆資料的 list of dict），
          total_count, matched_gps_count（成功配對到 GPS 座標的筆數）,
          video_start_at, video_filename
        失敗時含：status='error', message
    """
    try:
        if not os.path.exists(arduino_path):
            raise MergeDataError(f'找不到 Arduino 檔案，請確認路徑：{arduino_path}')
        if not os.path.exists(rtk_path):
            raise MergeDataError(f'找不到 RTK 檔案，請確認路徑：{rtk_path}')

        df_arduino = _read_tof_csv(arduino_path).sort_values('recorded_at').reset_index(drop=True)
        df_rtk = _read_rtk_csv(rtk_path).rename(columns={'recorded_at': 'rtk_recorded_at'})
        df_rtk = df_rtk.sort_values('rtk_recorded_at').reset_index(drop=True)

        if video_start_at is None:
            video_start_at = df_arduino['recorded_at'].min().to_pydatetime()

        merged = pd.merge_asof(
            df_arduino,
            df_rtk,
            left_on='recorded_at',
            right_on='rtk_recorded_at',
            direction='nearest',
            tolerance=pd.Timedelta(seconds=max_gap_seconds),
        )
        merged['rtk_gap_ms'] = (merged['recorded_at'] - merged['rtk_recorded_at']).dt.total_seconds().abs() * 1000
        merged['video_offset_ms'] = (merged['recorded_at'] - video_start_at).dt.total_seconds() * 1000

        video_name = os.path.basename(video_filename) if video_filename else None

        records = []
        for _, row in merged.iterrows():
            records.append({
                'arduino_tree_id': int(row['Tree_ID']),
                'recorded_at': row['recorded_at'].to_pydatetime(),
                'laser_status': str(row['Laser_Status']),
                'led_status': str(row['LED_Status']),
                'tof_dist1_cm': float(row['ToF_Dist1_cm']),
                'tof_dist2_cm': float(row['ToF_Dist2_cm']),
                'rtk_tag': None if pd.isna(row['TAG']) else str(row['TAG']),
                'latitude': None if pd.isna(row['latitude']) else float(row['latitude']),
                'longitude': None if pd.isna(row['longitude']) else float(row['longitude']),
                'rtk_height_m': None if pd.isna(row['HEIGHT']) else float(row['HEIGHT']),
                'rtk_speed_mps': None if pd.isna(row['SPEED']) else float(row['SPEED']),
                'rtk_heading_deg': None if pd.isna(row['HEADING']) else float(row['HEADING']),
                'rtk_gap_ms': None if pd.isna(row['rtk_gap_ms']) else int(row['rtk_gap_ms']),
                'video_offset_ms': int(row['video_offset_ms']),
            })

        return {
            'status': 'success',
            'message': '時間對齊完成',
            'records': records,
            'total_count': len(records),
            'matched_gps_count': int(merged['latitude'].notna().sum()),
            'video_start_at': video_start_at,
            'video_filename': video_name,
        }

    except MergeDataError as e:
        return {'status': 'error', 'message': str(e)}
    except Exception as e:
        # 捕捉其他未知的系統錯誤
        return {'status': 'error', 'message': f'發生未知的系統錯誤：{str(e)}'}


# 本地端測試執行區塊（供單機驗證使用）
if __name__ == '__main__':
    test_arduino = 'data/raw/TREE_015.CSV'
    test_rtk = 'data/raw/01182401.CSV'

    result = align_sensor_data(test_arduino, test_rtk, video_filename='IMG_4631.MOV')
    if result['status'] == 'success':
        print(f"成功：{result['message']}，共 {result['total_count']} 筆（其中 {result['matched_gps_count']} 筆有 GPS 座標）")
    else:
        print(f"失敗：{result['message']}")
