"""
routes/api.py
一般資料 API（樹木列表、地圖資料等）。

目前尚未實作任何 API 路由，僅先提供 blueprint 定義以讓 app.py 可以正常啟動。
"""
from flask import Blueprint, jsonify
from services import db as db_service

api_bp = Blueprint('api', __name__)


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
