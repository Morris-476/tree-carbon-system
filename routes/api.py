"""
routes/api.py
一般資料 API（樹木列表、地圖資料等）。

目前尚未實作任何 API 路由，僅先提供 blueprint 定義以讓 app.py 可以正常啟動。
"""
from flask import Blueprint

api_bp = Blueprint('api', __name__)
