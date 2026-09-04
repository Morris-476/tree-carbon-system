# 負責人：張恆輔
# 開發日期：2026/09/04
# 用途：/measure 頁面用，把 YOLO 樹幹遮罩換算成真實樹徑（20 切片 + IQR 篩選異常值）

import cv2
import numpy as np

# 胸高量測高度（公尺），從 mask 最底部往上算，符合林業標準 1.3m
DBH_HEIGHT_M = 1.3
# 水平切片數量：胸高位置上下各取 10 條，共 20 條
DBH_SLICE_COUNT = 20
# 最少有效切片數，低於此值視為量測失敗
MIN_VALID_SLICES = 8


class GeometryEngine:
    """把「像素資訊」換算成「真實公分數」，與 YOLO 完全解耦，不做任何偵測。"""

    def compute_target_y(self, trunk_pts: np.ndarray, scale: float) -> float:
        """從 mask 最低點（可見範圍的地面基準）往上 1.3m，算出量測用的 target_y。
        影像座標系 y 軸向下為正，所以「往上」＝ y 值減小。
        scale 或 trunk_pts 無效時回傳 -1.0，供下游函式防呆判斷。
        """
        if scale <= 0:
            return -1.0
        if len(trunk_pts) == 0:
            return -1.0

        mask_bottom_y = float(trunk_pts[:, 1].max())
        height_cm = DBH_HEIGHT_M * 100.0
        offset_px = height_cm / scale
        target_y = mask_bottom_y - offset_px

        return target_y

    def get_diameter_at_height(self, trunk_pts: np.ndarray, target_y: float, scale: float) -> dict:
        """在 target_y 上下各取 10 條水平切片（共 20 條），用 IQR 過濾異常寬度
        （樹皮突起、遮擋等造成的離群值）後取平均，換算成公分直徑。
        回傳 {diameter_cm, std_cm, confidence}，confidence 為 high/medium/low。
        """
        if target_y < 0:
            return {'diameter_cm': 0.0, 'std_cm': 0.0, 'confidence': 'low'}

        half = DBH_SLICE_COUNT // 2

        # masks.xy 是稀疏輪廓點，直接搜尋切片附近的點會找不到足夠的點，
        # 所以先把多邊形填充成密集的二值 bitmap，再逐行掃描找 x 範圍
        x_max = int(trunk_pts[:, 0].max()) + 1
        y_max = int(trunk_pts[:, 1].max()) + 1
        raster = np.zeros((y_max + 1, x_max + 1), dtype=np.uint8)
        pts_int = trunk_pts.astype(np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(raster, [pts_int], 255)

        widths_px = []

        for offset in range(-half, half):
            y = int(target_y + offset)

            if y < 0 or y >= raster.shape[0]:
                continue

            xs = np.where(raster[y, :] > 0)[0]

            if len(xs) < 2:
                continue

            widths_px.append(float(xs[-1] - xs[0]))

        if len(widths_px) < MIN_VALID_SLICES:
            return {'diameter_cm': 0.0, 'std_cm': 0.0, 'confidence': 'low'}

        # IQR 過濾異常值：超出 [Q1-1.5*IQR, Q3+1.5*IQR] 的切片視為離群值捨棄
        arr = np.array(widths_px)
        q1 = np.percentile(arr, 25)
        q3 = np.percentile(arr, 75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        filtered = arr[(arr >= lower) & (arr <= upper)]

        if len(filtered) < MIN_VALID_SLICES:
            return {'diameter_cm': 0.0, 'std_cm': 0.0, 'confidence': 'low'}

        mean_px = float(np.mean(filtered))
        std_px = float(np.std(filtered))

        diameter_cm = round(mean_px * scale, 2)
        std_cm = round(std_px * scale, 3)

        n = len(filtered)

        if n >= 15 and std_cm < 0.5:
            confidence = 'high'
        elif n >= 10 and std_cm < 1.0:
            confidence = 'medium'
        else:
            confidence = 'low'

        return {
            'diameter_cm': diameter_cm,
            'std_cm': std_cm,
            'confidence': confidence
        }
