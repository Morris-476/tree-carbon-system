# 負責人：Jump0423
# 用途：/measure 頁面專用的 API 路由，串接前端表單與 services/measure/pipeline.py

import base64

import cv2
import numpy as np
from flask import Blueprint, request, jsonify

from services.core import db as db_service
from services.measure.pipeline import run_measure_pipeline

measure_bp = Blueprint('measure', __name__)


@measure_bp.route('/api/species', methods=['GET'])
def api_species():
    """給 /measure 頁面的樹種下拉選單用，直接複用既有的 db.get_species_list()。"""
    species_list = db_service.get_species_list()
    return jsonify(species_list), 200


@measure_bp.route('/api/measure', methods=['POST'])
def api_measure():
    """接收照片與拍攝參數，呼叫 run_measure_pipeline() 算出樹徑與固碳量。"""
    image_file = request.files.get('image')
    if image_file is None:
        return jsonify({'error': '缺少照片'}), 400

    try:
        focal_mm = float(request.form.get('focal_mm'))
        sensor_width_mm = float(request.form.get('sensor_width'))
        distance_m = float(request.form.get('distance_m'))
    except (TypeError, ValueError):
        return jsonify({'error': '拍攝參數格式錯誤'}), 400

    species_id = request.form.get('species_id')

    file_bytes = np.frombuffer(image_file.read(), dtype=np.uint8)
    image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if image is None:
        return jsonify({'error': '照片格式無法解析'}), 400

    species_data = {}
    if species_id:
        species_list = db_service.get_species_list()
        matched = next((s for s in species_list if str(s.get('species_id')) == str(species_id)), None)
        if matched:
            species_data = matched

    result, annotated = run_measure_pipeline(
        image=image,
        focal_mm=focal_mm,
        sensor_width_mm=sensor_width_mm,
        distance_m=distance_m,
        species_data=species_data,
        image_file=image_file.filename or '',
    )

    _, buffer = cv2.imencode('.jpg', annotated)
    annotated_base64 = base64.b64encode(buffer).decode('utf-8')

    return jsonify({
        'diameter_cm': result.diameter_cm,
        'status': result.status,
        'confidence': result.confidence,
        'species_name': result.species_name,
        'biomass_kg': result.biomass_kg,
        'carbon_kg': result.carbon_kg,
        'co2_kg': result.co2_kg,
        'warnings': result.warnings,
        'annotated_image': f'data:image/jpeg;base64,{annotated_base64}',
    }), 200
