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


# 陳政雍 8/1修改
def main():
    username = input("請輸入管理員帳號（英數字）：").strip()
    if not username or not username.isalnum():
        print("帳號不可為空，且只能包含英數字")
        return

    if get_user_by_username(username) is not None:
        print(f"帳號「{username}」已存在，請改用其他帳號")
        return

    password = getpass.getpass("請輸入密碼（至少 6 字元）：")
    if len(password) < 6:
        print("密碼長度不可少於 6 字元")
        return

    password_confirm = getpass.getpass("請再輸入一次密碼：")
    if password != password_confirm:
        print("兩次輸入的密碼不一致")
        return

    password_hash = generate_password_hash(password)

    if create_admin_user(username, password_hash):
        print(f"管理員帳號「{username}」建立成功")
    else:
        print("管理員帳號建立失敗，請檢查資料庫連線或錯誤訊息")


if __name__ == '__main__':
    main()
