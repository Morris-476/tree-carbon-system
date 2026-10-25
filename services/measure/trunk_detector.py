# 負責人：張恆輔
# 開發日期：2026/09/04
# 用途：/measure 頁面用的單張照片版 YOLO 樹幹偵測（tracker.py 是影片追蹤版，兩者分開）

import os
import numpy as np
from ultralytics import YOLO


class TrunkDetector:
    """YOLO 樹幹偵測器：載入模型，對單張影像推論，回傳信心度最高的樹幹輪廓。"""

    def __init__(self, model_path: str, conf: float):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f'找不到模型檔：{model_path}')
        print('正在載入 YOLO 模型...')
        self.model = YOLO(model_path)
        self.conf = conf

    def detect(self, image: np.ndarray):
        """對輸入影像執行 YOLO 推論，回傳信心度最高的樹幹遮罩與信心度。
        偵測不到時回傳 None，不拋出例外，由呼叫端決定如何處理。
        """
        results = self.model.predict(
            source=image,
            save=False,
            verbose=False,
            conf=self.conf
        )

        for result in results:
            if result.masks is None or len(result.boxes) == 0:
                continue

            conf_scores = result.boxes.conf.cpu().numpy()
            best_idx = int(np.argmax(conf_scores))

            trunk_pts = result.masks.xy[best_idx]
            if len(trunk_pts) == 0:
                continue

            box = result.boxes.xyxy[best_idx].cpu().numpy().tolist()

            return {
                'masks_xy': trunk_pts,
                'confidence': float(conf_scores[best_idx]),
                'box': box
            }

        return None

    def get_trunk_pixel_width(self, mask: np.ndarray) -> float:
        """樹幹輪廓最寬處的像素距離（最右 x 減最左 x）。"""
        return float(mask[:, 0].max() - mask[:, 0].min())

    def is_trunk_complete(self, box: list, img_shape: tuple) -> bool:
        """檢查偵測框是否碰到影像左右邊緣（樹幹是否完整入鏡），容差 5px。"""
        img_w = img_shape[1]
        margin = 5

        x1 = box[0]
        x2 = box[2]

        if x1 < margin:
            return False
        if x2 > img_w - margin:
            return False

        return True
