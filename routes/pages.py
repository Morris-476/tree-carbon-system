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
