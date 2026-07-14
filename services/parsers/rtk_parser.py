"""
services/rtk_parser.py
RTK GNSS 原始資料解析。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  假設的輸入格式（尚未取得真實硬體範例檔，待確認）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
純文字檔，每行一筆紀錄，逗號分隔，欄位順序固定：
    timestamp_ms,latitude,longitude,fix_quality
範例：
    1719300000123,25.174532,121.450214,4
    1719300000623,25.174535,121.450219,4

欄位說明：
  timestamp_ms  Unix epoch 毫秒，整數
  latitude      十進位度（WGS-84），浮點數，正值為北緯
  longitude     十進位度（WGS-84），浮點數，正值為東經
  fix_quality   整數，依 NMEA GGA 慣例：
                  0 = 無效定位，4 = RTK fixed，5 = RTK float
                  （其他值可能存在，此 parser 不過濾，由呼叫端決定是否排除）

允許以 # 開頭的行作為註解，允許空行，不允許表頭行。

⚠️  此格式為推測，取得真實 RTK 接收器輸出後必須重新驗證。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from dataclasses import dataclass
from typing import List


@dataclass
class RtkRecord:
    timestamp_ms: int
    latitude: float
    longitude: float
    fix_quality: int


def parse_rtk_file(file_path: str) -> List[RtkRecord]:
    """
    解析假設格式的 RTK 文字檔，回傳 RtkRecord 列表。
    任何格式錯誤（欄位數、型別）都應拋出 ValueError，不得靜默跳過。
    有效紀錄為空時也應拋出 ValueError。
    """
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")
