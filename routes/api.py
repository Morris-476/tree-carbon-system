"""
routes/api.py
一般資料 API（樹木列表、地圖資料等）。
"""
import os
import uuid

from flask import Blueprint, request, jsonify
from services import db as db_service
from routes.admin import login_required
from services import data_pipeline
import config

api_bp = Blueprint('api', __name__)


# 負責人：____
# 開發日期：2026/08/24
# 用意：接收管理員上傳的 RTK / Arduino / 影片檔案，執行時間對齊運算並回傳結果
#      （純運算邏輯，不寫入資料庫）
@api_bp.route('/api/upload', methods=['POST'])
@login_required
def api_upload():
    rtk_file = request.files.get('rtk_file')
    arduino_file = request.files.get('arduino_file')
    mp4_file = request.files.get('mp4_file')

    if not rtk_file or not rtk_file.filename:
        return jsonify({'error': '請上傳 RTK 檔案'}), 400
    if not arduino_file or not arduino_file.filename:
        return jsonify({'error': '請上傳 Arduino 檔案'}), 400

    upload_dir = os.path.join(config.UPLOAD_FOLDER, uuid.uuid4().hex)
    os.makedirs(upload_dir, exist_ok=True)

    rtk_path = os.path.join(upload_dir, rtk_file.filename)
    arduino_path = os.path.join(upload_dir, arduino_file.filename)
    rtk_file.save(rtk_path)
    arduino_file.save(arduino_path)

    video_path = None
    if mp4_file and mp4_file.filename:
        video_path = os.path.join(upload_dir, mp4_file.filename)
        mp4_file.save(video_path)

    result = data_pipeline.run_sensor_time_sync(
        rtk_file_path=rtk_path,
        csv_file_path=arduino_path,
        video_path=video_path,
    )

    if result['status'] != 'success':
        return jsonify({'error': result['message']}), 400

    records = [
        {**r, 'recorded_at': r['recorded_at'].strftime('%Y-%m-%d %H:%M:%S')}
        for r in result['records']
    ]
    video_start_at = result['video_start_at']

    return jsonify({
        'success': True,
        'total_count': result['total_count'],
        'matched_gps_count': result['matched_gps_count'],
        'video_start_at': video_start_at.strftime('%Y-%m-%d %H:%M:%S') if video_start_at else None,
        'video_filename': result['video_filename'],
        'records': records,
    }), 200


#陳政雍 8/18 新增Map功能
@api_bp.route('/api/trees', methods=['GET'])
def api_get_trees():
    """地圖頁用：回傳所有 confirmed 樹木資料（含座標），供 static/js/map.js 呼叫。"""
    tree_list, db_status = db_service.get_tree_map_data()
    if db_status == 'disconnected':
        return jsonify({'error': '資料庫連線失敗'}), 500
    return jsonify({'success': True, 'trees': tree_list})


# 陳信睿 8/18 首頁排版
@api_bp.route('/api/stats', methods=['GET'])
def api_get_stats():
    """首頁用：回傳全站統計數字，供 templates/index.html 呼叫。"""
    stats = db_service.get_stats()
    return jsonify({
        'success': True,
        'total_trees': stats['total_trees'],
        'total_carbon': stats['total_carbon']
    })
