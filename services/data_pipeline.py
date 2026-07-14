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
"""
from __future__ import annotations

import os
import cv2
from typing import Optional

from services.rtk_parser import parse_rtk_file
from services.csv_parser import parse_tof_csv
from services.time_sync import align_measurements, TimeSyncError
from services.tracker import TreeTracker
from services.diameter_calc import TreeCalculator
from services import db as db_service
import config


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
