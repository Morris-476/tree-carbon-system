"""
routes/admin.py
後台管理路由：登入／登出、樹木審核（confirm/delete）。

安全設計：
  - 密碼以 werkzeug.security.check_password_hash 驗證（資料庫存雜湊值，不存明文）
  - 登入狀態由 Flask session 管理，secret_key 從環境變數讀取（見 config.py）
  - 所有需登入的路由都套 @login_required 裝飾器
  - 登入失敗統一回傳「帳號或密碼錯誤」，不區分帳號不存在/密碼錯誤
    （避免被用來枚舉帳號）
  - status 只能改成 'confirmed' 或 'pending'（已限縮合法值）

本輪未實作（超出範圍，日後可加）：
  - CSRF token 保護
  - 登入失敗次數限制（brute-force 防護）
  - 雙因素驗證
"""
from functools import wraps
from flask import (Blueprint, session, request, jsonify,
                   redirect, url_for, render_template)
from werkzeug.security import check_password_hash
from services import db as db_service

admin_bp = Blueprint('admin', __name__)

ALLOWED_STATUSES = frozenset({'confirmed', 'pending'})


# ── 登入保護裝飾器 ────────────────────────────────────────────────
def login_required(f):
    """
    套在需要登入的路由上。
    - API 路由（/api/ 開頭或 Accept: application/json）回傳 401 JSON
    - 頁面路由轉址到登入頁
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # TODO: 待實作 — 負責人：____
        raise NotImplementedError("此函式尚未實作")
    return decorated


# ── 頁面路由 ──────────────────────────────────────────────────────
@admin_bp.route('/admin/login')
def login_page():
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


@admin_bp.route('/admin/dashboard')
@login_required
def dashboard():
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


# ── API：登入 ─────────────────────────────────────────────────────
@admin_bp.route('/api/admin/login', methods=['POST'])
def api_login():
    """
    接受 JSON 格式的 {username, password}，驗證成功後建立 session。
    帳號或密碼錯誤時統一回傳 401，不區分是帳號不存在還是密碼錯誤。
    """
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


# ── API：登出 ─────────────────────────────────────────────────────
@admin_bp.route('/api/admin/logout', methods=['POST'])
def api_logout():
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


# ── API：樹木清單（含 pending）────────────────────────────────────
@admin_bp.route('/api/admin/trees', methods=['GET'])
@login_required
def api_get_trees():
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


# ── API：更新樹木狀態（唯一能把 pending → confirmed 的入口）────────
@admin_bp.route('/api/admin/trees/<int:tree_id>', methods=['PUT'])
@login_required
def api_update_tree(tree_id: int):
    """status 只允許 ALLOWED_STATUSES 內的值，其餘回傳 400。"""
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


# ── API：刪除樹木記錄 ─────────────────────────────────────────────
@admin_bp.route('/api/admin/trees/<int:tree_id>', methods=['DELETE'])
@login_required
def api_delete_tree(tree_id: int):
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")
