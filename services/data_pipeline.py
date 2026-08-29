"""
services/data_pipeline.py
完整資料處理管線：從 RTK / ToF / 影片 輸入，到資料庫寫入。

處理步驟（依架構文件）：
  ① csv_parser    — 解析 ToF CSV
  ② rtk_parser    — 解析 RTK GNSS 文字檔
  ③ time_sync     — 對齊快門、ToF、RTK 時間戳記
  ④ tracker 初始化 — 建立 TreeTracker（整段影片只建立一次）
  ⑤ YOLO + 追蹤   — 逐幀執行 ByteTrack，蒐集各 track_id 的像素寬度
  ⑥ diameter_calc — 以中位數像素寬度計算 DBH（樹徑）
  ⑦ 固碳計算      — 以 TreeCalculator.calculate_carbon() 估算固碳量
  ⑧ DB 寫入       — status 固定為 "pending"，等待管理員審核後才公開

⚠️  k_value（cm/pixel）計算依賴相機焦距與感測器距離的對應關係，
    此常數需用真實硬體標定（用已知直徑物體在已知距離拍照量測）。
    取得真實硬體後，標定結果須替換此處的計算邏輯。

⚠️  2026/08/22 修改：原本模組頂層 import 的 services.rtk_parser / services.csv_parser /
    services.tracker / services.diameter_calc 這幾個檔案在專案中都還不存在（不是路徑打錯，
    是 CONTRIBUTING.md 架構文件裡規劃要有、但尚未有人實作），會讓整個模組一 import 就
    ImportError。時間對齊功能（run_sensor_time_sync）不需要這幾個模組，因此先把它們
    從頂層 import 移除；②③以外的步驟（④～⑦影像追蹤與樹徑計算）仍待負責人補上對應檔案，
    屆時請在 process_upload() 內補回對應 import。

⚠️  2026/08/24 修改：run_sensor_time_sync 改呼叫純運算版本 merge_data.align_sensor_data()，
    不再寫入資料庫，供 /api/upload 上傳流程直接呼叫並回傳對齊結果。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from services import merge_data
import config


def run_sensor_time_sync(
    rtk_file_path: str,
    csv_file_path: str,
    video_path: Optional[str] = None,
    video_start_at: Optional[datetime] = None,
    max_rtk_gap_seconds: int = 3,
) -> dict:
    """
    資料處理管線的第①～③步：解析 Arduino(ToF) 與 RTK 檔案、對齊時間戳記，回傳合併結果。
    純運算邏輯，不寫入資料庫。是 process_upload() 未來會呼叫的其中一段，
    目前先獨立提供，讓時間對齊功能不需等 tracker / diameter_calc 完成就能先運作。

    Args:
        rtk_file_path:        RTK CSV 路徑
        csv_file_path:        Arduino(ToF) CSV 路徑
        video_path:            影片路徑，僅用於記錄檔名（可為 None）
        video_start_at:        影片第 0 影格的真實時間；未提供時由 merge_data 自動
                               取 Arduino 最早時間戳記（詳見 services/merge_data.py 說明）
        max_rtk_gap_seconds:   RTK 與 Arduino 紀錄的最大容忍時間差（秒）

    Returns:
        dict，同 services.merge_data.align_sensor_data() 的回傳格式
    """
    return merge_data.align_sensor_data(
        arduino_path=csv_file_path,
        rtk_path=rtk_file_path,
        video_filename=video_path,
        video_start_at=video_start_at,
        max_gap_seconds=max_rtk_gap_seconds,
    )


def process_upload(
    rtk_file_path: str,
    csv_file_path: str,
    video_path: str,
    video_start_timestamp_ms: Optional[int] = None,
    max_rtk_gap_ms: int = 200,
) -> list[dict]:
    """
    主處理函式：解析感測器檔案、追蹤影片中的樹幹、計算樹徑與固碳量、寫入資料庫。

    Args:
        rtk_file_path:            RTK 文字檔路徑（假設格式見 rtk_parser.py）
        csv_file_path:            ToF CSV 路徑（假設格式見 csv_parser.py）
        video_path:               影片路徑（MP4 等 OpenCV 可開啟的格式）
        video_start_timestamp_ms: 影片第 0 影格的 Unix 毫秒時間戳記
                                  ⚠️ 若未提供，應以 os.path.getctime() 取得（假設待確認）
        max_rtk_gap_ms:           RTK 對齊最大容忍時間差（毫秒）

    Returns:
        list of dict，每筆含 "status": "ok"|"error"。
        錯誤項目額外含 "stage"（哪個環節失敗）和 "message"（原因）。
        成功項目含 track_id, species, dbh, carbon, lat, lng。

    DB 寫入政策：
        status 固定寫入 "pending"，不會在此處直接設為 "confirmed"。
        唯一能讓紀錄公開的入口是後台管理員透過 PUT /api/admin/trees/<id> 審核。
    """
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")
