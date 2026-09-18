# 負責人：Jump0423
# 用途：/measure 頁面的主流程，串接樹幹偵測→樹徑量測→固碳計算→結果包裝→標註圖繪製

from __future__ import annotations

import datetime
from typing import Optional

import numpy as np

import config
from services.core.carbon import calculate_carbon
from services.core.diameter import calculate_scale_cm_per_px
from services.measure.geometry import GeometryEngine
from services.measure.models import MeasurementResult
from services.measure.trunk_detector import TrunkDetector
from services.measure.validator import Validator
from services.measure.visualizer import Visualizer

_detector = None
_geometry = GeometryEngine()
_validator = Validator()
_visualizer = Visualizer()


def _get_detector() -> TrunkDetector:
    global _detector
    if _detector is None:
        _detector = TrunkDetector(model_path=config.MODEL_PATH, conf=0.4)
    return _detector


def run_measure_pipeline(
    image: np.ndarray,
    focal_mm: float,
    sensor_width_mm: float,
    distance_m: float,
    species_data: dict,
    tree_age: Optional[int] = None,
    image_file: str = '',
) -> tuple[MeasurementResult, np.ndarray]:
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    detector = _get_detector()
    detection = detector.detect(image)

    if detection is None:
        result = MeasurementResult(
            status='no_trunk_detected',
            warnings=['未偵測到樹幹，請確認照片是否清楚拍到完整樹幹'],
            timestamp=now,
            image_file=image_file,
        )
        return result, _visualizer.draw(image, None, result)

    trunk_pts = detection['masks_xy']
    image_width_px = image.shape[1]
    distance_cm = distance_m * 100.0

    scale_result = calculate_scale_cm_per_px(
        image_width_px=image_width_px,
        distance_cm=distance_cm,
        focal_mm=focal_mm,
        sensor_width_mm=sensor_width_mm,
    )
    if scale_result.error is not None:
        result = MeasurementResult(status='invalid_camera_params', warnings=[scale_result.error],
                                    timestamp=now, image_file=image_file)
        return result, _visualizer.draw(image, detection, result)

    target_y = _geometry.compute_target_y(trunk_pts, scale_result.scale_cm_per_px)
    diameter_info = _geometry.get_diameter_at_height(trunk_pts, target_y, scale_result.scale_cm_per_px)

    result = _validator.validate(diameter_info['diameter_cm'])
    result.confidence = {'high': 0.9, 'medium': 0.6, 'low': 0.3}.get(diameter_info['confidence'], 0.0)
    result.diameter_std = diameter_info['std_cm']
    result.measurement_y = target_y
    result.image_file = image_file
    result.timestamp = now
    result.tree_age = tree_age

    carbon_result = calculate_carbon(
        dbh=result.diameter_cm,
        allo_param_a=species_data.get('allo_param_a'),
        allo_param_b=species_data.get('allo_param_b'),
        carbon_fraction=species_data.get('carbon_fraction'),
    )
    if carbon_result.error is None:
        result.species_name = species_data.get('species_name', '')
        result.biomass_kg = carbon_result.biomass_kg
        result.carbon_kg = carbon_result.carbon_kg
        result.co2_kg = carbon_result.co2_kg
        # 本年度固碳量 = 固碳量CO2當量 ÷ 樹齡（樹齡為選填，沒填就維持 None，
        # 前端會整塊不顯示）。固碳量本身算失敗時也不算，避免除到無意義的 0
        if tree_age is not None and tree_age > 0:
            result.annual_co2_kg = result.co2_kg / tree_age
    else:
        result.warnings.append(carbon_result.error)

    return result, _visualizer.draw(image, detection, result)