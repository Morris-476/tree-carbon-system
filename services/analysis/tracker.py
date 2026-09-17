# 負責人：Morris
# 開發日期：2026/08/02
# 用途：ByteTrack 多物件追蹤，透過 ultralytics 內建支援實作，免另裝套件

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
from ultralytics import YOLO

import config


class TreeTracker:
    """單一影片的樹幹追蹤器，整段影片只能建立一個實例，對每個影格依序呼叫
    track_frame()；每次呼叫都用 persist=True 讓 YOLO 跨影格維持同一組
    track_id，中途重新建立實例的話 track_id 會重置。新出現的 track_id 需
    連續確認 min_hits 幀才正式對外輸出，藉此濾掉 YOLO 一閃而過的誤判。

    已知限制：同一棵樹若被遮擋超過 track_buffer 幀數，重新出現時會被當成
    新樹、拿到新的 track_id，這是 ByteTrack 的正常特性，適合路樹間隔拍攝的
    情境，但人車經過造成的短暫遮擋可能被誤判成新樹，目前不處理。
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
        """初始化追蹤器並載入模型，所有參數未指定時一律從 config.py 讀取預設值。"""
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
        """對單一影格執行追蹤，須對同一段影片的連續影格依序呼叫。
        回傳 [{'frame', 'track_id', 'pixel_width', 'mask_width'}, ...]，
        尚未達到 min_hits 確認門檻的追蹤目標不會出現在結果中。
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
                        'frame': self._frame_idx,
                        'track_id': track_id,
                        'pixel_width': pixel_width,
                        # mask_width 是量出 pixel_width 當下那張遮罩的座標系寬度，
                        # 樹徑換算公式需要「像素寬度佔整張圖的比例」，兩者必須
                        # 用同一個座標系，所以要跟著 pixel_width 一起往下傳
                        'mask_width': mask_width,
                    }
                )

        self._frame_idx += 1
        return output

    # 量測線取偵測範圍底部往上一小段比例，而非垂直正中點：正中點常落在
    # 樹冠、量到枝葉寬度而非樹幹寬度。待相機校正完成後應改用
    # services/measure/geometry.py 以真實高度（1.3m）回推的方式
    TRUNK_MEASURE_HEIGHT_RATIO = 0.15

    @classmethod
    def _calc_pixel_width(cls, masks, index: int) -> tuple[Optional[int], Optional[int]]:
        """用分割遮罩計算樹幹在量測線上的像素寬度。量測線（measure_y）取偵測
        範圍底部往上 TRUNK_MEASURE_HEIGHT_RATIO 比例的位置，在該行找出遮罩為
        真的最左/最右 x 座標算出寬度。

        回傳 (pixel_width, mask_width)：mask_width 是這張遮罩本身的寬度
        （masks.data 是模型輸出解析度，不等於原始影格寬度），供樹徑換算公式
        計算「像素寬度佔整張圖的比例」，兩者須來自同一張遮罩。找不到有效
        遮罩、或該行沒有像素時回傳 (None, None)。
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

        # 只取「連續」的一段（像素間距=1 才算同一段），取像素數最多的一段當
        # 樹幹本體：低解析度遮罩常在主體以外冒出零星雜訊像素，直接取最左右 x
        # 會被雜訊點拉大，量出遠超實際樹幹的寬度
        row_xs = np.sort(row_xs)
        gaps = np.where(np.diff(row_xs) > 1)[0]
        main_run = max(np.split(row_xs, gaps + 1), key=len)

        x_start, x_end = int(main_run[0]), int(main_run[-1])
        return x_end - x_start, mask_width
