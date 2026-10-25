"""
routes/pages.py
一般頁面路由（首頁、關於、地圖等）。

目前僅實作首頁路由，其餘頁面路由待後續補上。
"""
from flask import Blueprint, render_template

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def index():
    return render_template('index.html')


#陳政雍 8/18新增Map功能
@pages_bp.route('/map')
def map_page():
    return render_template('map.html')


# 張恆輔 9/4新增：簡易固碳繪測頁（前端複製自 Tree-Trunk-Measurement，功能未變）
@pages_bp.route('/measure')
def measure():
    return render_template('measure.html')
