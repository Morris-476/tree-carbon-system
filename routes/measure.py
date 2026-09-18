# 負責人：Jump0423
# 用途：/measure 頁面專用的 API 路由，串接前端表單與 services/measure/pipeline.py

import base64

import cv2
import numpy as np
from flask import Blueprint, request, jsonify

from services.core import db as db_service
from services.measure.pipeline import run_measure_pipeline

measure_bp = Blueprint('measure', __name__)


def _parse_tree_age(raw_tree_age):
    """把表單傳來的樹齡轉成 int，沒填或填了無效值一律回 None。

    前端「不填寫（使用預設值）」那個 <option> 的 value 是空字串，而且是用
    formData.append() 送出，所以欄位一定存在、只是內容為空，不能用
    'tree_age' in request.form 來判斷使用者有沒有填。樹齡只是選填的加值
    資訊，填了無效值也不該讓整張照片的分析失敗，因此一律降級成 None。
    """
    if not raw_tree_age:
        return None
    try:
        tree_age = int(raw_tree_age)
    except (TypeError, ValueError):
        return None
    return tree_age if tree_age > 0 else None


def _round_for_display(value):
    """畫面上的固碳量數字統一取到小數點第 2 位；None（沒填樹齡）維持 None。"""
    return None if value is None else round(value, 2)


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
    tree_age = _parse_tree_age(request.form.get('tree_age'))

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
        tree_age=tree_age,
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
        # co2_kg 與 annual_co2_kg 是結果卡片上直接顯示的兩個數字，一起取到
        # 小數點第 2 位；biomass_kg、carbon_kg 不顯示，維持原始精度
        'co2_kg': _round_for_display(result.co2_kg),
        'annual_co2_kg': _round_for_display(result.annual_co2_kg),
        'tree_age': result.tree_age,
        'warnings': result.warnings,
        'annotated_image': f'data:image/jpeg;base64,{annotated_base64}',
    }), 200
