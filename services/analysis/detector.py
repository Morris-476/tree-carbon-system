import cv2
import numpy as np
import os
from ultralytics import YOLO

class TreeDetector:
    def __init__(self, model_path="best.pt"):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"❌ 找不到模型檔: {model_path}")
        self.model = YOLO(model_path)

    def detect_and_measure(self, image_path):
        img = cv2.imread(image_path)
        if img is None: return None, []
        
        height, width, _ = img.shape
        # 執行辨識 [cite: 45]
        results = self.model.predict(source=image_path, save=False, verbose=False, conf=0.4)
        
        detected_trees = []
        for result in results:
            if result.masks is not None:
                # 遍歷這張照片中辨識到的所有目標
                for i in range(len(result.masks)):
                    class_id = int(result.boxes.cls[i])
                    species_name = result.names[class_id]
                    
                    mask_data = result.masks.data[i].cpu().numpy()
                    mask_resized = cv2.resize(mask_data, (width, height))
                    
                    y_indices, _ = np.where(mask_resized > 0.5)
                    if len(y_indices) > 0:
                        measure_y = int((np.min(y_indices) + np.max(y_indices)) / 2)
                        row_pixels = mask_resized[measure_y, :]
                        tree_indices = np.where(row_pixels > 0.5)[0]
                        
                        if len(tree_indices) > 0:
                            x_start, x_end = np.min(tree_indices), np.max(tree_indices)
                            detected_trees.append({
                                "species": species_name,
                                "mask": mask_resized,
                                "measure_y": measure_y,
                                "x_start": x_start,
                                "x_end": x_end,
                                "pixel_width": x_end - x_start # 取得像素寬度 [cite: 46]
                            })
        return img, detected_trees