"""
scripts/create_admin.py
一次性命令列工具：建立第一個管理員帳號。

使用方式（從專案根目錄執行）：
    python scripts/create_admin.py

注意事項：
  - 這支腳本只在本機或伺服器終端機手動執行，不會被部署成任何網頁路由
  - 後台沒有公開的自助註冊功能，帳號只能透過這支腳本建立
  - 密碼以 werkzeug pbkdf2:sha256 雜湊後寫入資料庫，資料庫裡永遠不會存明文密碼
  - 執行前請確認 .env 已設定 DB_SERVER / DB_NAME / DB_USER / DB_PASSWORD
"""
import sys
import os
import getpass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from werkzeug.security import generate_password_hash
from services.db import get_user_by_username, create_admin_user


def main():
    # TODO: 待實作 — 負責人：____
    # 互動式 CLI：提示輸入帳號（英數字）、密碼（至少 6 字元，輸入兩次確認），
    # 以 generate_password_hash 雜湊後呼叫 create_admin_user 寫入資料庫。
    # 帳號已存在時應提示錯誤並結束，兩次密碼不一致時也應提示錯誤。
    raise NotImplementedError("此函式尚未實作")


if __name__ == '__main__':
    main()
