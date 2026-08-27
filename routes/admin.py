"""
routes/admin.py
後台管理路由：登入／登出、樹木審核（confirm/delete）。

"""
from functools import wraps
from flask import (Blueprint, session, request, jsonify,
                   redirect, url_for, render_template)
from werkzeug.security import check_password_hash
from services import db as db_service

admin_bp = Blueprint('admin', __name__)

# 負責人：陳政雍 8/27 修正允許值為 Pending／Approved
ALLOWED_STATUSES = frozenset({'Pending', 'Approved'})


# ── 登入保護裝飾器 ────────────────────────────────────────────────
# 陳政雍 8/1修改
def login_required(f):
    """
    套在需要登入的路由上。
    - API 路由（/api/ 開頭或 Accept: application/json）回傳 401 JSON
    - 頁面路由轉址到登入頁
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': '請先登入'}), 401
            return redirect(url_for('admin.login_page', next=request.path))
        return f(*args, **kwargs)
    return decorated


# 張恆輔 8/15新增：只允許站內相對路徑，避免 next 被用來跳轉到外部網址
def _safe_next_path(path):
    if path and path.startswith('/') and not path.startswith('//'):
        return path
    return ''


# ── 頁面路由 ──────────────────────────────────────────────────────
# 陳政雍 8/1修改
@admin_bp.route('/admin/login')
def login_page():
    next_path = _safe_next_path(request.args.get('next', ''))
    return render_template('admin/login.html', next=next_path)


# 陳政雍 8/1修改
# 張恆輔 8/15修改：檢視資料表改為公開頁面，不需登入
@admin_bp.route('/admin/dashboard')
def dashboard():
    return render_template('admin/dashboard.html')


# 張恆輔 8/15新增
@admin_bp.route('/admin/upload')
@login_required
def upload_page():
    return render_template('admin/upload.html')


# 陳政雍 8/16修改
@admin_bp.route('/admin/manage')
@login_required
def manage_page():
    return render_template('admin/manage.html')


# ── API：登入 ─────────────────────────────────────────────────────
# 陳政雍 8/1修改
@admin_bp.route('/api/admin/login', methods=['POST'])
def api_login():
    """
    接受 JSON 格式的 {username, password}，驗證成功後建立 session。
    帳號或密碼錯誤時統一回傳 401，不區分是帳號不存在還是密碼錯誤。
    """
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return jsonify({'error': '帳號或密碼錯誤'}), 401

    user = db_service.get_user_by_username(username)
    if user is None or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': '帳號或密碼錯誤'}), 401

    session.clear()
    session['admin_id'] = user['admin_id']
    session['username'] = user['username']
    return jsonify({'message': '登入成功'}), 200


# ── API：登出 ─────────────────────────────────────────────────────
# 陳政雍 8/1修改
@admin_bp.route('/api/admin/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'message': '已登出'}), 200


# ── API：樹木清單（含 pending）────────────────────────────────────
# 張恆輔 8/25新增
@admin_bp.route('/api/admin/trees', methods=['GET'])
@login_required
def api_get_trees():
    trees = db_service.get_all_trees_admin()
    return jsonify(trees), 200


# ── API：更新樹木狀態（唯一能把 pending → confirmed 的入口）────────
# 負責人：陳政雍 8/27 完成確認／刪除 API
@admin_bp.route('/api/admin/trees/<int:tree_id>', methods=['PUT'])
@login_required
def api_update_tree(tree_id: int):
    """status 只允許 ALLOWED_STATUSES 內的值，其餘回傳 400。"""
    data = request.get_json(silent=True) or {}
    new_status = data.get('status')
    if new_status not in ALLOWED_STATUSES:
        return jsonify({'error': 'status 格式錯誤'}), 400
    if not db_service.update_tree_status(tree_id, new_status):
        return jsonify({'error': '更新失敗，查無此筆資料'}), 400
    return jsonify({'success': True}), 200


# ── API：刪除樹木記錄 ─────────────────────────────────────────────
@admin_bp.route('/api/admin/trees/<int:tree_id>', methods=['DELETE'])
@login_required
def api_delete_tree(tree_id: int):
    if not db_service.delete_tree(tree_id):
        return jsonify({'error': '刪除失敗，查無此筆資料'}), 400
    return jsonify({'success': True}), 200
