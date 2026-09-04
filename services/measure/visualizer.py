# 負責人：張恆輔
# 開發日期：2026/09/04
# 用途：/measure 頁面用，在原始照片上疊加樹幹遮罩、量測線與狀態標籤

import cv2
import numpy as np


class Visualizer:
    """在原始影像上繪製偵測結果，複製一份再畫，不修改原始影像。"""

    def draw(self, image: np.ndarray, detection: dict, result) -> np.ndarray:
        output = image.copy()

        if detection is None:
            self._draw_status_label(output, result)
            return output

        trunk_pts = detection['masks_xy']

        self._draw_mask(output, trunk_pts)
        self._draw_diameter_line(output, trunk_pts, int(result.measurement_y))
        self._draw_status_label(output, result)

        return output

    def _draw_mask(self, image: np.ndarray, trunk_pts: np.ndarray) -> None:
        """半透明綠色遮罩＋亮綠色輪廓線，讓使用者確認 YOLO 偵測範圍是否正確。"""
        img_h, img_w = image.shape[:2]

        mask = np.zeros((img_h, img_w), dtype=np.uint8)
        pts = trunk_pts.astype(np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(mask, [pts], color=255)

        overlay = np.zeros_like(image)
        overlay[mask == 255] = (0, 180, 0)

        cv2.addWeighted(overlay, 0.4, image, 1.0, 0, image)
        cv2.polylines(image, [pts], isClosed=True, color=(0, 255, 0), thickness=2)

    def _draw_diameter_line(self, image: np.ndarray, trunk_pts: np.ndarray, measure_y: int) -> None:
        """胸高位置的紅色水平量測線；用光柵化找 x 範圍，避免稀疏輪廓點找不到足夠的點。"""
        img_h = image.shape[0]
        measure_y = max(0, min(measure_y, img_h - 1))

        x_max_pt = int(trunk_pts[:, 0].max()) + 1
        y_max_pt = int(trunk_pts[:, 1].max()) + 1
        raster = np.zeros((y_max_pt + 1, x_max_pt + 1), dtype=np.uint8)
        pts_int = trunk_pts.astype(np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(raster, [pts_int], 255)

        if measure_y < raster.shape[0]:
            xs = np.where(raster[measure_y, :] > 0)[0]
        else:
            xs = np.array([])

        if len(xs) >= 2:
            x_left = int(xs[0])
            x_right = int(xs[-1])
        else:
            x_left = int(trunk_pts[:, 0].min())
            x_right = int(trunk_pts[:, 0].max())

        cv2.line(image, (x_left, measure_y), (x_right, measure_y), color=(0, 0, 255), thickness=10)
        cv2.circle(image, (x_left, measure_y), radius=5, color=(0, 0, 255), thickness=-1)
        cv2.circle(image, (x_right, measure_y), radius=5, color=(0, 0, 255), thickness=-1)

    def _draw_status_label(self, image: np.ndarray, result) -> None:
        """右上角狀態標籤：DBH、方法、狀態、信心度，顏色依 status 區分。"""
        img_h, img_w = image.shape[:2]

        if result.status == 'verified':
            color = (0, 200, 0)
        elif result.status == 'mismatch':
            color = (0, 165, 255)
        else:
            color = (0, 0, 220)

        lines = [
            f'DBH: {result.diameter_cm:.1f} cm',
            f'Method: {result.method}',
            f'Status: {result.status}',
            f'Conf:   {result.confidence:.2f}',
        ]

        if result.species_name:
            lines.append(f'Species: {result.species_name}')
        if result.carbon_kg > 0:
            lines.append(f'Carbon:  {result.carbon_kg:.2f} kg')
            lines.append(f'CO2 eq:  {result.co2_kg:.2f} kg')

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        line_gap = 30
        margin = 10

        max_text_w = 0
        for line in lines:
            (text_w, _), _ = cv2.getTextSize(line, font, font_scale, thickness)
            if text_w > max_text_w:
                max_text_w = text_w

        box_x1 = img_w - max_text_w - margin * 3
        box_y1 = margin
        box_x2 = img_w - margin
        box_y2 = margin + len(lines) * line_gap + margin

        overlay = image.copy()
        cv2.rectangle(overlay, (box_x1, box_y1), (box_x2, box_y2), color=(0, 0, 0), thickness=-1)
        cv2.addWeighted(overlay, 0.5, image, 0.5, 0, image)

        for i, line in enumerate(lines):
            text_x = box_x1 + margin
            text_y = box_y1 + margin + (i + 1) * line_gap - 5
            cv2.putText(image, line, (text_x, text_y), font, font_scale, color, thickness, lineType=cv2.LINE_AA)
