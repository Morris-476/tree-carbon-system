"""
services/tracker.py
ByteTrack 多物件追蹤，透過 ultralytics 內建支援實作。
不需要額外安裝套件，沿用 services/yolo.py 已有的 ultralytics 依賴。

設計原則：
  - TreeTracker 實例必須在整段影片期間只建立一次，並重複呼叫 track_frame()
  - 每次呼叫都使用 persist=True，確保 ultralytics 在 YOLO 實例內部
    保持追蹤狀態，跨影格維持一致的 track_id
  - 不要在每個影格重新建立 TreeTracker 實例，否則 track_id 會重置
"""
from __future__ import annotations

import cv2
import numpy as np
from typing import List, Optional
from ultralytics import YOLO
import config


class TreeTracker:
    """
    單一影片的樹幹追蹤器。
    整段影片只建立一個實例，對每個影格依序呼叫 track_frame()。
    track_id 在影片全程不重置，以利後續去重複統計。
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        初始化追蹤器並載入模型。
        model_path 未指定時使用 config.MODEL_PATH。
        """
        # TODO: 待實作 — 負責人：____
        raise NotImplementedError("此函式尚未實作")

    def track_frame(self, frame_array: np.ndarray) -> List[dict]:
        """
        對單一影格執行追蹤，必須對同一段影片的連續影格依序呼叫。

        Args:
            frame_array: OpenCV BGR numpy array（單一影格）

        Returns:
            list of dict，格式與 services/yolo.py detect_and_measure() 相容：
            {
                "track_id":    int | None,
                "species":     str,
                "mask":        np.ndarray | None,
                "measure_y":   int | None,
                "x_start":     int | None,
                "x_end":       int | None,
                "pixel_width": int | None,
                "confidence":  float,
            }
        """
        # TODO: 待實作 — 負責人：____
        raise NotImplementedError("此函式尚未實作")
