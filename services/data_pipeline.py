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

⚠️  2026/08/29 修改：新增 run_upload_and_save()，把對齊結果連同影片截圖寫入 dbo.Measurements。
    對齊運算本身（merge_data.align_sensor_data）完全沒有更動。

⚠️  2026/09/11 修改：run_upload_and_save() 寫入 Measurements 後，接著呼叫
    tree_analysis.analyze_and_write_final_distances()（IQR 去極端值，寫回
    Measurements.Final_Dist_cm）與 tree_coordinate.recalculate_tree_coordinates()
    （依推車座標＋方位角＋Final_Dist_cm 推算樹木座標，寫入 Trees）。
    之前這兩支函式都各自獨立、沒有被 pipeline 呼叫，上傳資料後不會生效。
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import cv2

from services import merge_data
from services import db as db_service
from services.analysis.tracker import TreeTracker
from services.analysis import tree_analysis
from services.analysis.tree_coordinate import recalculate_tree_coordinates
from services.analysis.tree_diameter import calculate_pending_diameters
from services.analysis.tree_species import classify_pending_trees
from services.analysis.tree_carbon import calculate_pending_carbon
import config


def _extract_frame_jpeg(video_path: str, offset_ms: int):
    """從影片抓 offset_ms 那個時間點最接近的一格，編碼成 JPEG bytes。
    抓不到（超出影片長度、影片壞掉等）時回傳 None，不拋例外中斷整批處理。
    """
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


# 張恆輔 8/30新增：只跑追蹤，先單獨驗證 track_id／pixel_width
# 拿不拿得到，不做樹徑換算、固碳計算、也不寫資料庫。
def run_tracking_only(video_path: str) -> dict:
    """
    對整支影片跑 TreeTracker，回傳每幀的 track_id／pixel_width。
    TreeTracker 只建立一次、對每一幀依序呼叫 track_frame()，
    符合 tracker.py 要求的 persist 語意（見該檔案開頭說明）。

    Args:
        video_path: 影片路徑（MP4 等 OpenCV 可開啟的格式）

    Returns:
        dict：
          成功時 {'status': 'success', 'frame_count': int, 'fps': float, 'records': [...]}，
          fps 是這支影片的幀率，用來把 records 裡的 frame 編號換算回毫秒
          （offset_ms = frame / fps * 1000），供跟時間對齊後的資料配對。
          records 為所有幀合併後的結果，格式：
          [{"frame": int, "track_id": int, "pixel_width": int | None}, ...]
          失敗時 {'status': 'error', 'message': str}
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


def run_upload_and_save(
    rtk_file_path: str,
    csv_file_path: str,
    video_path: Optional[str] = None,
    video_start_at: Optional[datetime] = None,
    max_rtk_gap_seconds: int = 3,
    focal_mm: Optional[float] = None,
    sensor_width_mm: Optional[float] = None,
) -> dict:
    """
    資料上傳頁的完整流程：時間對齊 → 每筆抓對應時間點的影片截圖 → 寫入 dbo.Measurements
    → 距離 IQR → 座標 → 樹徑 → 樹種 → 固碳（後五步依序自動執行，見函式尾端）。
    對齊邏輯直接呼叫 align_sensor_data()，完全沒有更動；這裡只負責截圖與寫入資料庫。

    site_name 自動取影片檔名（去掉副檔名），例如 IMG_4631.MOV -> "IMG_4631"。
    沒有上傳影片時，site_name 為 None、每筆的 image_data 也是 None（不影響對齊與寫入）。

    Args:
        rtk_file_path:        RTK CSV 路徑
        csv_file_path:        Arduino(ToF) CSV 路徑
        video_path:            影片路徑；有給的話才會截圖
        video_start_at:        影片第 0 影格的真實時間，未提供時由 merge_data 自動推算
        max_rtk_gap_seconds:   RTK 與 Arduino 紀錄的最大容忍時間差（秒）
        focal_mm:              拍攝設備焦距（mm），來自資料上傳頁選的機型／手動輸入；
                               沒提供時樹徑算不出來，dbh 維持 0
        sensor_width_mm:       拍攝設備感光元件寬度（mm），同上

    Returns:
        dict：對齊失敗時同 align_sensor_data() 的錯誤格式；
        成功時額外含 inserted（實際寫入 Measurements 筆數）、tree_id、site_name。
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

        # 張恆輔 8/30新增：追蹤要在這裡（跟時間對齊同一次請求）跑完，
        # 因為 Measurements 沒有存影片路徑，等這次請求結束、之後沒辦法
        # 再回頭找到這支影片來補跑追蹤。track_id／pixel_width 先存起來，
        # 樹徑換算（IQR 篩選 + k值）留給後面的步驟處理，這裡不做。
        tracking = run_tracking_only(video_path)
        frame_lookup = {}
        fps = None
        if tracking['status'] == 'success':
            fps = tracking['fps']
            for det in tracking['records']:
                frame_lookup.setdefault(det['frame'], []).append(det)

        for record in result['records']:
            record['image_data'] = _extract_frame_jpeg(video_path, record['video_offset_ms'])

            if fps:
                frame_idx = round(record['video_offset_ms'] / 1000 * fps)
                detections = frame_lookup.get(frame_idx, [])
            else:
                detections = []

            if detections:
                # 同一幀出現多棵樹時，先取 pixel_width 最大（離鏡頭最近、最可信）的那個
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
            record['track_id'] = None
            record['pixel_width'] = None
            record['mask_width'] = None
            record['focal_mm'] = focal_mm
            record['sensor_width_mm'] = sensor_width_mm

    save_result = db_service.save_time_synced_measurements(result['records'], site_name)
    if save_result['status'] != 'success':
        return {'status': 'error', 'message': save_result['message']}

    # 2026/09/12新增：完整補上距離 → 座標 → 樹徑 → 樹種 → 固碳的自動流程，
    # 順序不可任意調動：
    #   ① 距離 IQR（tree_analysis）：篩出每棵樹的代表紀錄與代表距離
    #   ② 座標（tree_coordinate）：算出真實座標，同時把代表紀錄的
    #      Measurements.Tree_ID 從上傳當下的佔位值改成正確的真實 Tree_ID
    #   ③ 樹徑（tree_diameter）：用代表紀錄的像素寬度＋代表距離換算 dbh，
    #      只需要①的結果，不依賴②
    #   ④ 樹種（tree_species）：必須排在②之後——判斷「這棵樹辨識過了嗎」
    #      是透過 Measurements.Tree_ID 對應到 Trees，佔位 Tree_ID 還沒被
    #      ②修正的話，樹種會被誤寫到錯的樹上
    #   ⑤ 固碳（tree_carbon）：需要③的 dbh 與④辨識出的樹種固碳係數，
    #      兩者都好了才能算，必須排最後
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
