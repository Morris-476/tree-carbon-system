"""
app.py
啟動點：建立 Flask app 並登記所有 Blueprint。
業務邏輯已全部移至 routes/ 與 services/，此檔案不含任何路由或查詢邏輯。
"""
from dotenv import load_dotenv
import os as _os
# 用 __file__ 絕對路徑，reloader 子進程也能正確找到 .env
load_dotenv(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '.env'))

from flask import Flask
from routes.pages import pages_bp
from routes.api import api_bp
from routes.admin import admin_bp
import config

app = Flask(__name__)
# secret_key 從環境變數讀取，不可留空（會導致 session 無法正常運作）
app.secret_key = config.SECRET_KEY
app.register_blueprint(pages_bp)
app.register_blueprint(api_bp)
app.register_blueprint(admin_bp)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
