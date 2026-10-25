# services/data_pipeline.py
"""
樹木巡檢與固碳量測量資料管線 (Data Pipeline)
負責：感測數據對齊、影片截圖抽取、Azure Blob Storage 上傳、樹徑運算與 Azure SQL 寫入。
"""
from __future__ import annotations  # 🎯 必須在所有 import 之前，避免 SyntaxError

import io
import os
import cv2
import pyodbc
from datetime import datetime
from typing import Optional, List, Dict, Any

import config
from services import merge_data
from services.blob_service import upload_tree_image


def _extract_frame_jpeg(video_path: str, offset_ms: float) -> Optional[bytes]:
    """從影片指定毫秒 (ms) 處擷取單格畫面並轉為 JPEG 二進位 bytes"""
    if not video_path or not os.path.exists(video_path):
        return None
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None

        # 跳至指定毫秒位置
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(offset_ms)))
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return None

        # 壓縮為 JPEG 格式（品質 85，節省空間與頻寬）
        success, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if success:
            return buffer.tobytes()
    except Exception as e:
        print(f"⚠️ 影片影格擷取失敗 (offset: {offset_ms} ms): {e}")
    return None


def calculate_tree_metrics(tof1: int, tof2: int) -> tuple[float, float, float]:
    """依據 ToF 測距計算樹徑 (dbh cm)、生物量 (biomass kg) 與固碳量 (carbon kg)"""
    dbh = round((tof1 + tof2) * 0.4, 2)
    biomass = round(0.09 * (dbh ** 2.4), 2)
    carbon_absorption = round(biomass * 0.5, 2)
    return dbh, biomass, carbon_absorption


def _get_or_create_tree(cursor, tracker_id: Optional[int], lat: Any, lng: Any) -> Optional[int]:
    """確保 Trees 表中有該棵樹，並回傳對應的 tree_id"""
    if tracker_id is None:
        return None
    try:
        cursor.execute("SELECT tree_id FROM Trees WHERE tracker_id = ?", (tracker_id,))
        row = cursor.fetchone()
        if row:
            return row[0]

        cursor.execute("""
            INSERT INTO Trees (tracker_id, [LATITUDE N/S], [LONGITUDE E/W], site_id, species_id)
            OUTPUT INSERTED.tree_id
            VALUES (?, ?, ?, NULL, NULL)
        """, (tracker_id, str(lat) if lat else None, str(lng) if lng else None))
        new_id = cursor.fetchone()[0]
        return new_id
    except Exception as e:
        print(f"⚠️ 自動建立樹木個體失敗 (tracker_id={tracker_id}): {e}")
        return None


def run_sensor_time_sync(
    rtk_file_path: str,
    csv_file_path: str,
    video_path: Optional[str] = None,
    video_start_at: Optional[datetime] = None,
    max_rtk_gap_seconds: int = 3,
) -> dict:
    """
    資料處理管線的第 1 步：解析 Arduino(ToF) 與 RTK 檔案、對齊時間戳記，回傳合併結果。
    純運算邏輯，不寫入資料庫。
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
    site_name: str = "未指定案場",
) -> list[dict]:
    """
    主處理函式：
    1. 解析感測器檔案並進行時間對齊
    2. 依時間軸從影片擷取樹木特寫影格
    3. 自動上傳照片至 Azure Blob Storage 取得 image_url
    4. 計算胸徑 (DBH) 與固碳量
    5. 寫入 Azure SQL Measurements 表 (status = 'Pending')
    """
    results: list[dict] = []

    # 1. 執行時間軸與感測數據對齊
    try:
        video_start_dt = None
        if video_start_timestamp_ms:
            video_start_dt = datetime.fromtimestamp(video_start_timestamp_ms / 1000.0)

        sync_result = run_sensor_time_sync(
            rtk_file_path=rtk_file_path,
            csv_file_path=csv_file_path,
            video_path=video_path,
            video_start_at=video_start_dt,
            max_rtk_gap_seconds=max(1, max_rtk_gap_ms // 1000),
        )
    except Exception as e:
        return [{
            "status": "error",
            "stage": "align_sensor_data",
            "message": f"感測器數據對齊失敗: {str(e)}"
        }]

    # 取得對齊後的資料清單
    records = sync_result.get("records", []) if isinstance(sync_result, dict) else sync_result
    if not records:
        return [{
            "status": "error",
            "stage": "align_sensor_data",
            "message": "未能對齊出任何有效感測數據，請確認時間格式與檔案完整性。"
        }]

    # 2. 連線至 Azure SQL 準備寫入
    try:
        conn = pyodbc.connect(config.DB_CONNECTION_STRING)
        cursor = conn.cursor()
    except Exception as e:
        return [{
            "status": "error",
            "stage": "db_connect",
            "message": f"資料庫連線失敗: {str(e)}"
        }]

    insert_measure_sql = """
        INSERT INTO Measurements (
            tree_id, dbh, biomass, carbon_absorpation,
            [DATE], [TIME], SPEED, HEADING, HEIGHT,
            Laser_Status, LED_Status, ToF_Dist1_cm, ToF_Dist2_cm,
            [INDEX], [TAG], status, site_name, image_url
        )
        OUTPUT INSERTED.record_id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?)
    """

    tree_cache: dict[int, int] = {}

    # 3. 逐筆處理感測紀錄、影片截圖與上傳
    for idx, r in enumerate(records):
        try:
            # 取得欄位（相容不同命名格式）
            track_id = r.get("Tree_ID") or r.get("track_id") or (idx + 1)
            try:
                track_id = int(track_id)
            except (ValueError, TypeError):
                track_id = None

            tof1 = int(r.get("ToF_Dist1_cm", 0))
            tof2 = int(r.get("ToF_Dist2_cm", 0))
            lat = r.get("latitude") or r.get("LATITUDE N/S")
            lng = r.get("longitude") or r.get("LONGITUDE E/W")
            date_val = str(r.get("DATE", datetime.now().strftime("%Y/%m/%d")))
            time_val = str(r.get("TIME", datetime.now().strftime("%H:%M:%S")))
            speed = float(r.get("SPEED", r.get("rtk_speed_mps", 0.0)))
            heading = int(r.get("HEADING", r.get("rtk_heading_deg", 0)))
            height = int(r.get("HEIGHT", r.get("rtk_height_m", 0)))
            laser_status = str(r.get("Laser_Status", "OFF"))
            led_status = str(r.get("LED_Status", "OFF"))
            rtk_index = int(r.get("INDEX", r.get("rtk_index", idx + 1)))
            rtk_tag = str(r.get("TAG", r.get("rtk_tag", "T"))).strip()

            # 計算胸徑與固碳量
            dbh, biomass, carbon_abs = calculate_tree_metrics(tof1, tof2)

            # 🎯 從影片中依 offset (毫秒) 擷取畫面並上傳 Azure Blob Storage
            image_url = None
            offset_ms = r.get("video_offset_ms")
            if offset_ms is not None and video_path:
                frame_bytes = _extract_frame_jpeg(video_path, float(offset_ms))
                if frame_bytes:
                    image_url = upload_tree_image(
                        file_stream=io.BytesIO(frame_bytes),
                        original_filename=f"tree_{track_id or 'snap'}_{idx}.jpg",
                        content_type="image/jpeg"
                    )

            # 確保樹木主檔存在
            current_tree_id = None
            if track_id is not None:
                if track_id not in tree_cache:
                    created_id = _get_or_create_tree(cursor, track_id, lat, lng)
                    if created_id:
                        tree_cache[track_id] = created_id
                current_tree_id = tree_cache.get(track_id)

            # 寫入 Measurements 資料表
            cursor.execute(insert_measure_sql, (
                current_tree_id, dbh, biomass, carbon_abs,
                date_val, time_val, speed, heading, height,
                laser_status, led_status, tof1, tof2,
                rtk_index, rtk_tag, site_name, image_url
            ))
            inserted_record_id = cursor.fetchone()[0]

            results.append({
                "status": "ok",
                "record_id": inserted_record_id,
                "track_id": track_id,
                "species": "未辨識樹種",
                "dbh": dbh,
                "biomass": biomass,
                "carbon": carbon_abs,
                "image_url": image_url,
                "lat": lat,
                "lng": lng
            })

        except Exception as err:
            results.append({
                "status": "error",
                "stage": f"process_row_{idx}",
                "message": f"第 {idx} 筆資料處理寫入失敗: {str(err)}"
            })

    try:
        conn.commit()
    except Exception as e:
        conn.rollback()
        return [{
            "status": "error",
            "stage": "db_commit",
            "message": f"資料庫 Transaction 提交失敗: {str(e)}"
        }]
    finally:
        conn.close()

    return results