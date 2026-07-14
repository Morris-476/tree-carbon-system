"""
services/csv_parser.py
ToF（Time-of-Flight）感測器 CSV 資料解析。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  假設的輸入格式（尚未取得真實硬體範例檔，待確認）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CSV 格式，第一行為表頭，欄位：
    timestamp_ms,distance_cm,flash_trigger

範例：
    timestamp_ms,distance_cm,flash_trigger
    1719300000050,118.3,0
    1719300000100,120.5,1
    1719300000150,120.2,0

欄位說明：
  timestamp_ms    Unix epoch 毫秒，整數，與 RTK 使用相同的時鐘基準（待確認）
  distance_cm     ToF 感測器讀值（公分），浮點數，代表感測器到樹幹的距離
  flash_trigger   整數 0 或 1：1 表示此時刻相機快門觸發（閃光燈同步訊號）
                  每次拍照只有一行的 flash_trigger 為 1（假設），
                  若出現多行為 1，time_sync.py 取第一個。

⚠️  以下假設特別不確定：
  - timestamp_ms 是否與 RTK 時鐘對齊（可能需要硬體同步機制）
  - flash_trigger 訊號精確到哪一行（可能有 ±1 行的抖動）
  - distance_cm 是否已補償感測器安裝偏移量
  取得真實 ToF 感測器輸出後必須重新驗證上述全部假設。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import csv
from dataclasses import dataclass
from typing import List


@dataclass
class TofRecord:
    timestamp_ms: int
    distance_cm: float
    flash_trigger: bool


def parse_tof_csv(file_path: str) -> List[TofRecord]:
    """
    解析假設格式的 ToF CSV 檔，回傳 TofRecord 列表。
    任何格式錯誤（缺欄位、型別）都應拋出 ValueError，不得靜默跳過或補猜測值。
    有效資料行為空時也應拋出 ValueError。
    """
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")
