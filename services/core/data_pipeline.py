# 負責人：Morris
# 開發日期：2026/08/22
# 用途：資料上傳管線入口 run_upload_and_save()，時間對齊、追蹤後依序執行 IQR/座標/樹徑/樹種/固碳

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import cv2

from services.core import merge_data
from services.core import db as db_service
from services.blob_service import upload_tree_image
from services.analysis.tracker import TreeTracker
from services.analysis import tree_analysis
from services.analysis.tree_coordinate import recalculate_tree_coordinates
from services.analysis.tree_diameter import calculate_pending_diameters
from services.analysis.tree_species import classify_pending_trees
from services.analysis.tree_carbon import calculate_pending_carbon


def _extract_frame_jpeg(video_path: str, offset_ms: int):
    """抓影片 offset_ms 最接近的一幀，編碼成 JPEG bytes；抓不到回傳 None。"""
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            return None
        cap.set(cv2.CAP_PROP_POS_MSEC, max(offset_ms, 0))
        ok, frame = cap.read()
        if not ok or frame is None:
            return None
        ok, buf = cv2.imencode('.jpg', frame)
        return buf.tobytes() if ok else None
    finally:
        cap.release()


# 2026/10/29新增：截圖改直接轉存 Azure Blob Storage，不再把二進位塞進
# Measurements.image_data——這張表先前已經因為每筆都存一張近 1MB 的截圖，
# 把 Basic 層級 2GB 上限吃到快滿。回傳 (image_url, image_data)：
# 上傳成功 image_url 有值、image_data 為 None；Blob 上傳失敗（例如網路問題）
# 則退回存二進位到資料庫，確保這張截圖不會憑空消失。
def _extract_and_upload_frame(video_path: str, offset_ms: int, site_name: str):
    frame_bytes = _extract_frame_jpeg(video_path, offset_ms)
    if not frame_bytes:
        return None, None
    try:
        image_url = upload_tree_image(
            file_stream=frame_bytes,
            original_filename=f'{site_name}_{offset_ms}.jpg',
            content_type='image/jpeg',
        )
        return image_url, None
    except Exception as e:
        print(f'截圖上傳 Blob Storage 失敗，改存資料庫二進位: {e}')
        return None, frame_bytes


def run_tracking_only(video_path: str) -> dict:
    """對整支影片跑 TreeTracker，回傳每幀的 track_id／pixel_width，不寫入資料庫。
    成功：{'status': 'success', 'frame_count', 'fps', 'records': [{'frame', 'track_id', 'pixel_width'}, ...]}
    失敗：{'status': 'error', 'message'}
    """
    if not os.path.exists(video_path):
        return {'status': 'error', 'message': f'找不到影片檔案：{video_path}'}

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        return {'status': 'error', 'message': f'無法開啟影片：{video_path}'}

    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    if fps <= 0:
        cap.release()
        return {'status': 'error', 'message': f'無法讀取影片幀率：{video_path}'}

    tracker = TreeTracker()
    records = []
    frame_count = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            records.extend(tracker.track_frame(frame))
            frame_count += 1
    finally:
        cap.release()

    return {'status': 'success', 'frame_count': frame_count, 'fps': fps, 'records': records}


def run_sensor_time_sync(
    rtk_file_path: str,
    csv_file_path: str,
    video_path: Optional[str] = None,
    video_start_at: Optional[datetime] = None,
    max_rtk_gap_seconds: int = 3,
) -> dict:
    """對齊 Arduino(ToF) 與 RTK 時間戳記，純運算、不寫入資料庫。"""
    return merge_data.align_sensor_data(
        arduino_path=csv_file_path,
        rtk_path=rtk_file_path,
        video_filename=video_path,
        video_start_at=video_start_at,
        max_gap_seconds=max_rtk_gap_seconds,
    )


def run_upload_and_save(
    rtk_file_path: str,
    csv_file_path: str,
    video_path: Optional[str] = None,
    video_start_at: Optional[datetime] = None,
    max_rtk_gap_seconds: int = 3,
    focal_mm: Optional[float] = None,
    sensor_width_mm: Optional[float] = None,
) -> dict:
    """/api/upload 的完整流程：時間對齊 → 截圖 → 寫入 Measurements →
    距離 IQR → 座標 → 樹徑 → 樹種 → 固碳。site_name 取影片檔名（去副檔名）。
    focal_mm／sensor_width_mm 為拍攝設備參數，供樹徑換算使用，未提供則算不出樹徑。
    """
    result = merge_data.align_sensor_data(
        arduino_path=csv_file_path,
        rtk_path=rtk_file_path,
        video_filename=video_path,
        video_start_at=video_start_at,
        max_gap_seconds=max_rtk_gap_seconds,
    )
    if result['status'] != 'success':
        return result

    site_name = None
    if video_path:
        site_name = os.path.splitext(os.path.basename(video_path))[0]

        # 追蹤要在這次請求內完成：Measurements 沒存影片路徑，之後無法回頭補跑
        tracking = run_tracking_only(video_path)
        frame_lookup = {}
        fps = None
        if tracking['status'] == 'success':
            fps = tracking['fps']
            for det in tracking['records']:
                frame_lookup.setdefault(det['frame'], []).append(det)

        for record in result['records']:
            record['image_url'], record['image_data'] = _extract_and_upload_frame(
                video_path, record['video_offset_ms'], site_name
            )

            if fps:
                frame_idx = round(record['video_offset_ms'] / 1000 * fps)
                detections = frame_lookup.get(frame_idx, [])
            else:
                detections = []

            if detections:
                # 同一幀多棵樹時取 pixel_width 最大（離鏡頭最近、最可信）的一個
                best = max(detections, key=lambda d: d['pixel_width'] or 0)
                record['track_id'] = best['track_id']
                record['pixel_width'] = best['pixel_width']
                record['mask_width'] = best['mask_width']
            else:
                record['track_id'] = None
                record['pixel_width'] = None
                record['mask_width'] = None
            record['focal_mm'] = focal_mm
            record['sensor_width_mm'] = sensor_width_mm
    else:
        for record in result['records']:
            record['image_data'] = None
            record['image_url'] = None
            record['track_id'] = None
            record['pixel_width'] = None
            record['mask_width'] = None
            record['focal_mm'] = focal_mm
            record['sensor_width_mm'] = sensor_width_mm

    save_result = db_service.save_time_synced_measurements(result['records'], site_name)
    if save_result['status'] != 'success':
        return {'status': 'error', 'message': save_result['message']}

    # 順序不可調動：座標要先修正 Tree_ID，樹種辨識才會認對樹；固碳需要樹徑與樹種都完成
    tree_analysis.analyze_and_write_final_distances(verbose=False, save_csv=False)
    recalculate_tree_coordinates()
    calculate_pending_diameters()
    classify_pending_trees()
    calculate_pending_carbon()

    result['inserted'] = save_result['inserted']
    result['tree_id'] = save_result['tree_id']
    result['site_name'] = site_name
    return result


def process_upload(
    rtk_file_path: str,
    csv_file_path: str,
    video_path: str,
    video_start_timestamp_ms: Optional[int] = None,
    max_rtk_gap_ms: int = 200,
) -> list[dict]:
    """尚未實作，不是實際使用的入口（見 run_upload_and_save）。"""
    raise NotImplementedError('此函式尚未實作')
