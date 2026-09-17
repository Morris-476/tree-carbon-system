# 負責人：Morris
# 開發日期：2026/09/12
# 用途：樹種辨識共用模組（YOLO 去背＋CLIP 向量＋比對 tree_vectors.pkl）。
#      ⚠️ 前處理不可與 tracker.py／trunk_detector.py 共用，混用會讓向量偏離訓練基準
from __future__ import annotations

import os
import pickle
import tempfile
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np
from PIL import Image

import config

_tree_vectors = None
_clip_model = None
_clip_preprocess = None
_clip_device = None


@dataclass
class SpeciesResult:
    """樹種辨識結果，欄位命名對齊 services/geo.py 的 TreeCoordinate、
    services/carbon.py 的 CarbonResult：error 為 None 代表判定成功；
    不為 None 時代表偵測失敗或信心度不足，species 維持 None，
    呼叫端不應把 species 寫進資料庫。
    """
    species: Optional[str] = None
    confidence: float = 0.0
    scores: dict = field(default_factory=dict)
    error: Optional[str] = None


def _load_tree_vectors() -> dict:
    global _tree_vectors
    if _tree_vectors is None:
        with open(config.SPECIES_VECTORS_PATH, 'rb') as f:
            _tree_vectors = pickle.load(f)
    return _tree_vectors


def _load_clip():
    global _clip_model, _clip_preprocess, _clip_device
    if _clip_model is None:
        import clip
        import torch
        _clip_device = 'cuda' if torch.cuda.is_available() else 'cpu'
        _clip_model, _clip_preprocess = clip.load(config.CLIP_MODEL_NAME, device=_clip_device)
    return _clip_model, _clip_preprocess, _clip_device


def segment_trunk(image: np.ndarray, yolo_model) -> Optional[np.ndarray]:
    """對照片做樹幹去背，取面積最大的遮罩（不是信心度最高的，跟訓練時一致）。
    偵測不到樹幹時回傳 None。
    """
    results = yolo_model(image, conf=config.SPECIES_SEGMENT_CONF)

    if results[0].masks is None:
        return None

    masks = results[0].masks.data.cpu().numpy()
    areas = [m.sum() for m in masks]
    best_mask = masks[np.argmax(areas)]

    mask = cv2.resize(best_mask, (image.shape[1], image.shape[0]))
    mask = (mask > 0.5).astype(np.uint8) * 255

    return cv2.bitwise_and(image, image, mask=mask)


def extract_clip_vector(masked_image: np.ndarray) -> np.ndarray:
    """把去背後的圖片轉成正規化過的 CLIP 向量。
    刻意比照訓練時的做法先存成暫存 JPEG 再讀回來，跟產生 tree_vectors.pkl
    當下的前處理完全一致，不直接在記憶體轉換，避免向量跟訓練時有落差。
    """
    import torch

    clip_model, preprocess, device = _load_clip()

    fd, temp_path = tempfile.mkstemp(suffix='.jpg')
    os.close(fd)
    try:
        cv2.imwrite(temp_path, masked_image)
        img = Image.open(temp_path).convert('RGB')
        img_input = preprocess(img).unsqueeze(0).to(device)

        with torch.no_grad():
            vector = clip_model.encode_image(img_input)
            vector = vector / vector.norm(dim=-1, keepdim=True)

        return vector.cpu().numpy()[0]
    finally:
        os.remove(temp_path)


def identify_species(image: np.ndarray, yolo_model) -> SpeciesResult:
    """辨識一張照片裡的樹種。信心度低於 config.SPECIES_CONFIDENCE_THRESHOLD
    時視為無法判定，species 回傳 None，不會硬選一個分數最高的樹種頂替。
    """
    masked = segment_trunk(image, yolo_model)
    if masked is None:
        return SpeciesResult(error='未偵測到樹幹')

    query_vector = extract_clip_vector(masked)
    tree_db = _load_tree_vectors()

    scores = {name: float(np.dot(query_vector, vec)) for name, vec in tree_db.items()}
    best_species = max(scores, key=scores.get)
    best_confidence = scores[best_species]

    if best_confidence < config.SPECIES_CONFIDENCE_THRESHOLD:
        return SpeciesResult(
            confidence=best_confidence,
            scores=scores,
            error=f'信心度不足（最高 {best_confidence:.2f} < 門檻 {config.SPECIES_CONFIDENCE_THRESHOLD}）'
        )

    return SpeciesResult(species=best_species, confidence=best_confidence, scores=scores)
