"""
services/analysis/tracker.py
# 負責人：Morris
# 開發日期：2026/08/02
# 用途：ByteTrack 多物件追蹤，透過 ultralytics 內建支援實作。
不需要額外安裝獨立的 ByteTrack 套件，ultralytics 套件已內建。

設計原則：
  - TreeTracker 實例必須在整段影片期間只建立一次，並重複呼叫 track_frame()
  - 每次呼叫都使用 persist=True，確保 ultralytics 在 YOLO 實例內部
    保持追蹤狀態，跨影格維持一致的 track_id
  - 不要在每個影格重新建立 TreeTracker 實例，否則 track_id 會重置
  - 新出現的 track_id 需連續確認 min_hits 幀才正式對外輸出，
    藉此濾掉 YOLO 一閃而過的誤判（例如反光被誤認成樹幹）

輸出格式（依 data_flow.docx 正式規格為準）：
  [{"frame": int, "track_id": int, "pixel_width": int | None}, ...]

已知限制（不在這次實作範圍內解決）：
  同一棵樹如果被遮擋超過 track_buffer 設定的幀數，重新出現時會被
  當成新的樹、拿到新的 track_id。這是 ByteTrack 的正常特性，適合
  「路樹間隔開、一次一兩棵」的拍攝情境，但如果同一棵樹在鏡頭前
  暫時被遮擋（人/車經過）超過緩衝幀數，會誤判成新樹，先記錄不處理。
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
from ultralytics import YOLO

import config


class TreeTracker:
    """
    單一影片的樹幹追蹤器。
    整段影片只建立一個實例，對每個影格依序呼叫 track_frame()。
    track_id 在影片全程不重置，以利後續去重複統計。
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf: Optional[float] = None,
        tracker_yaml: Optional[str] = None,
        min_hits: Optional[int] = None,
        imgsz: Optional[int] = None,
        iou: Optional[float] = None,
    ):
        """
        初始化追蹤器並載入模型。
        所有參數未指定時，一律從 config.py 讀取預設值。
        """
        self.model = YOLO(model_path or config.MODEL_PATH)
        self.conf = conf if conf is not None else config.CONF_THRESHOLD
        self.tracker_yaml = tracker_yaml or config.TRACKER_YAML
        self.min_hits = min_hits if min_hits is not None else config.MIN_HITS
        self.imgsz = imgsz or config.IMGSZ
        self.iou = iou if iou is not None else config.IOU

        # 記錄每個 track_id 已經連續出現的幀數，未達 min_hits 前不對外輸出
        self._hit_counts: Dict[int, int] = {}
        self._frame_idx = 0

    def track_frame(self, frame_array: np.ndarray) -> List[dict]:
        """
        對單一影格執行追蹤，必須對同一段影片的連續影格依序呼叫。

        Args:
            frame_array: OpenCV BGR numpy array（單一影格）

        Returns:
            list of dict：[{"frame": int, "track_id": int, "pixel_width": int | None}, ...]
            尚未達到 min_hits 確認門檻的追蹤目標，不會出現在回傳結果中。
        """
        results = self.model.track(
            source=frame_array,
            persist=True,
            conf=self.conf,
            tracker=self.tracker_yaml,
            imgsz=self.imgsz,
            iou=self.iou,
            verbose=False,
        )

        output: List[dict] = []
        result = results[0]
        boxes = result.boxes
        masks = result.masks

        # boxes.id 有可能是 None（框還沒被穩定追蹤到），必須先檢查
        if boxes is not None and boxes.id is not None:
            ids = boxes.id.cpu().numpy().astype(int)

            for i, raw_track_id in enumerate(ids):
                track_id = int(raw_track_id)

                # 連續確認機制：track_id 要連續出現滿 min_hits 幀才正式輸出
                self._hit_counts[track_id] = self._hit_counts.get(track_id, 0) + 1
                if self._hit_counts[track_id] < self.min_hits:
                    continue

                pixel_width, mask_width = (
                    self._calc_pixel_width(masks, i) if masks is not None else (None, None)
                )

                output.append(
                    {
                        "frame": self._frame_idx,
                        "track_id": track_id,
                        "pixel_width": pixel_width,
                        # mask_width：量出 pixel_width 當下那張遮罩的座標系寬度，
                        # 樹徑換算公式需要「像素寬度佔整張圖的比例」，兩者必須
                        # 用同一個座標系，所以要跟著 pixel_width 一起往下傳。
                        "mask_width": mask_width,
                    }
                )

        self._frame_idx += 1
        return output

    # 2026/09/12修正：量測線原本取整個偵測範圍（含樹冠）垂直方向的正中點，
    # 但拍攝到的多半是全株入鏡（樹冠佔畫面比例遠大於樹幹），正中點常常落在
    # 樹冠中段，量到的是枝葉寬度、不是樹幹寬度，導致同一棵樹在不同影格量出
    # 的寬度大幅跳動。改成偵測範圍底部往上一小段比例，比較接近實際樹幹位置。
    # 這仍然是沒有標定過真實高度的權宜做法，等相機校正常數（k值）確定後，
    # 應該改用 services/measure/geometry.py 那種以真實高度（1.3m）回推的方式。
    TRUNK_MEASURE_HEIGHT_RATIO = 0.15

    @classmethod
    def _calc_pixel_width(cls, masks, index: int) -> tuple[Optional[int], Optional[int]]:
        """
        用分割遮罩計算樹幹在量測線上的像素寬度。
        量測線（measure_y）取偵測範圍底部往上 TRUNK_MEASURE_HEIGHT_RATIO
        比例的位置（比正中點更接近地面/樹幹基部），在該行找出遮罩為真的
        最左/最右 x 座標，回傳寬度（像素）。

        回傳 (pixel_width, mask_width)：mask_width 是這張遮罩本身的寬度
        （masks.data 是模型輸出解析度，不等於原始影格寬度），供樹徑換算
        公式計算「像素寬度佔整張圖的比例」時使用，兩者必須來自同一張遮罩。

        找不到有效遮罩、或該行沒有像素時，回傳 (None, None)（呼叫端需自行處理）。
        """
        try:
            mask_array = masks.data[index].cpu().numpy()  # shape: (H, W)
        except (IndexError, AttributeError):
            return None, None

        mask_width = mask_array.shape[1]

        ys, xs = np.where(mask_array > 0.5)
        if len(ys) == 0:
            return None, mask_width

        y_min, y_max = int(ys.min()), int(ys.max())
        measure_y = int(y_max - (y_max - y_min) * cls.TRUNK_MEASURE_HEIGHT_RATIO)
        row_xs = xs[ys == measure_y]
        if len(row_xs) == 0:
            return None, mask_width

        x_start, x_end = int(row_xs.min()), int(row_xs.max())
        return x_end - x_start, mask_width
