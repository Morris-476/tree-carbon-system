"""
services/time_sync.py
影像快門、ToF 感測器、RTK GNSS 三者的時間對齊。

對齊策略：
  1. 以 ToF CSV 裡 flash_trigger=1 的行為「快門按下時刻」
  2. 在 RTK 紀錄裡找時間戳記最接近快門時刻的那一筆（在容忍誤差內）
  3. 影片影格對齊：使用影片檔案建立時間作為第 0 影格時刻（見假設說明）

⚠️  影格對齊假設特別不確定：
  目前假設「影片第一影格時間 = 檔案系統建立時間（os.path.getctime）」。
  此假設在以下情況下會失效：
    - 檔案複製或轉檔後 ctime 被更新
    - 相機內部時鐘與 RTK/ToF 時鐘未同步
    - 影片以緩衝形式錄製，第一影格實際時刻早於檔案寫入時刻
  需要拿到真實拍攝工作流程後，依實際相機輸出的 metadata 重新實作此部分。
"""
from dataclasses import dataclass
from typing import List, Optional

from services.rtk_parser import RtkRecord
from services.csv_parser import TofRecord


DEFAULT_MAX_GAP_MS = 200  # 預設最大容忍時間差（毫秒）


class TimeSyncError(Exception):
    """時間對齊失敗時拋出，包含具體失敗原因。"""


@dataclass
class SyncResult:
    """對齊後的結果，包含快門時刻對應的 GPS 座標與感測器讀值。"""
    shutter_timestamp_ms: int
    latitude: float
    longitude: float
    fix_quality: int
    distance_cm: float
    # 影片影格偏移：相對於影片第 0 影格的毫秒數，None 表示未提供影片起始時間
    frame_offset_ms: Optional[int]
    # 實際採用的 RTK 紀錄與快門時刻的時間差（毫秒），供偵錯用
    rtk_gap_ms: int


def align_measurements(
    tof_records: List[TofRecord],
    rtk_records: List[RtkRecord],
    video_start_timestamp_ms: Optional[int] = None,
    max_gap_ms: int = DEFAULT_MAX_GAP_MS,
) -> SyncResult:
    """
    對齊 ToF、RTK、影片三者的時間戳記。

    Args:
        tof_records:              從 csv_parser 取得的 ToF 資料
        rtk_records:              從 rtk_parser 取得的 RTK 資料
        video_start_timestamp_ms: 影片第 0 影格的 Unix 毫秒時間戳記
                                  ⚠️ 假設由呼叫端以 os.path.getctime() 換算，
                                     此假設待真實硬體驗證
        max_gap_ms:               RTK 紀錄與快門時刻的最大容忍時間差（預設 200ms）

    Returns:
        SyncResult 對齊結果

    Raises:
        TimeSyncError: 對齊失敗（沒有 flash_trigger、RTK 時間差過大等）
    """
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")
