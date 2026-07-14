"""
routes/pages.py
回傳 HTML 頁面的路由（首頁、地圖、資料展示、資訊頁）。
搬移自根目錄 app.py 中所有以 render_template() 回傳的路由。
"""
import json
from flask import Blueprint, render_template
from services import db as db_service

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def index():
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


@pages_bp.route('/interactive-map')
def interactive_map():
    tree_list, db_status = db_service.get_tree_map_data()
    return render_template(
        'map.html',
        trees_json=json.dumps(tree_list, ensure_ascii=False, default=str),
        db_status=db_status
    )


@pages_bp.route('/data-display')
def data_display():
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


@pages_bp.route('/<page_name>')
def info_pages(page_name):
    """有效的 page_name 清單：carbon-intro, project-intro, operation-guide, about, data-edit, login。"""
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")
