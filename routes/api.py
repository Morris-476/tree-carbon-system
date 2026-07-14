"""
routes/api.py
回傳 JSON 或執行操作的 API 路由。
搬移自根目錄 app.py 的 /upload 路由。
"""
import numpy as np
import cv2
from flask import Blueprint, request, redirect, url_for
from services import yolo as yolo_service
from services import db as db_service

api_bp = Blueprint('api', __name__)


@api_bp.route('/upload', methods=['POST'])
def upload_file():
    """
    接收前端表單上傳的圖片，執行 YOLO 推論，計算 DBH 與固碳量，寫入資料庫，
    最後轉址回資料展示頁。
    ⚠️ 固碳公式請與 services/diameter_calc.py 確認後統一實作。
    """
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")
