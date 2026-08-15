"""
services/db.py
所有 SQL Server 查詢邏輯的唯一入口。
資料庫正規化為五張表：Sites、Species_Ref、Trees、Measurements、Admins。
連線憑證一律從環境變數讀取，不寫死任何帳號密碼。
"""
import os
import uuid
import pyodbc
import config


def get_db_connection():
    """建立 SQL Server 連線（憑證由 config.py 讀自環境變數）。
    DB_USER 留空時自動切換為 Windows 整合驗證（本機開發用）。
    """
    try:
        base = (
            f'DRIVER={{ODBC Driver 17 for SQL Server}};'
            f'SERVER={config.DB_SERVER};'
            f'DATABASE={config.DB_NAME};'
            f'Encrypt={config.DB_ENCRYPT};'
            f'TrustServerCertificate={config.DB_TRUST_CERT};'
            f'Timeout=10;'
        )
        if config.DB_USER:
            conn_str = base + f'UID={config.DB_USER};PWD={config.DB_PASSWORD};'
        else:
            conn_str = base + 'Trusted_Connection=yes;'
        return pyodbc.connect(conn_str)
    except Exception as e:
        print(f"資料庫連線失敗: {e}")
        return None


def _ensure_img_folder():
    """確保 static/img/ 資料夾存在，回傳資料夾路徑。"""
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


def _save_img_bin(img_bin) -> "str | None":
    """把二進位圖片存到 static/img/，回傳檔名（供 thumbnail_path 欄位儲存）。
    img_bin 為 None 時應回傳 None（不拋出例外）。
    """
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


def _get_or_create_species(cursor, species_name: str) -> int:
    """查詢 Species_Ref，若不存在則以預設係數新增。回傳 species_id。"""
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


# ── 地圖頁查詢（僅 confirmed）────────────────────────────────────
def get_tree_map_data():
    """回傳 (tree_list, db_status)，供 routes/pages.py 的地圖頁使用。
    tree_list 中每筆需含 id, species, dbh, carbon, lat, lng, time, img 欄位。
    db_status 為 "connected" 或 "disconnected"。
    """
    conn = get_db_connection()
    if conn is None:
        return [], "disconnected"
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                m.id,
                sr.name        AS species,
                m.dbh,
                m.carbon,
                t.latitude     AS lat,
                t.longitude    AS lng,
                m.recorded_at  AS time,
                m.thumbnail_path AS img
            FROM Measurements m
            INNER JOIN Trees       t  ON m.tree_id    = t.id
            INNER JOIN Species_Ref sr ON t.species_id = sr.id
            LEFT  JOIN Sites       si ON t.site_id    = si.id
            WHERE m.status = 'confirmed'
        """)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        tree_list = [dict(zip(columns, row)) for row in rows]
        return tree_list, "connected"
    except Exception as e:
        print(f"get_tree_map_data 查詢失敗: {e}")
        return [], "disconnected"
    finally:
        conn.close()


# ── 資料展示頁查詢（僅 confirmed）────────────────────────────────
def get_tree_list():
    """回傳樹木清單，供 routes/pages.py 的資料展示頁使用。
    每筆需含 id, species, dbh, carbon, recorded_at, img_url 欄位。
    """
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


# ── 網頁上傳寫入（status='confirmed'，直接公開）──────────────────
def save_tree_record(species, dbh, carbon, img_bin):
    """儲存網頁上傳的辨識結果（無 GPS 座標）。"""
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


# ── 資料處理管線寫入（status 固定 pending，等待管理員審核）──────
def save_pipeline_record(species, dbh, carbon, lat, lon,
                         fix_quality=None, distance_cm=None,
                         track_id=None, status='pending'):
    """管線上傳：含 GPS 座標，status 固定 pending，等待管理員審核後才公開。"""
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


# ── 後台管理：樹木清單（含所有 status）──────────────────────────
def get_all_trees_admin():
    """後台用：回傳含 status 的完整清單（pending + confirmed）。
    每筆需含 id, species, dbh, carbon, lat, lng, recorded_at, img_url, status 欄位。
    """
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


def update_tree_status(tree_id: int, new_status: str) -> bool:
    """後台：更新 Measurements 審核狀態。回傳 True 表示更新成功。"""
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


def delete_tree(tree_id: int) -> bool:
    """後台：刪除一筆 Measurements 記錄。回傳 True 表示刪除成功。"""
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


# ── 後台管理：使用者帳號 ─────────────────────────────────────────
# 陳政雍 8/1修改
def get_user_by_username(username: str):
    """登入驗證用：查詢帳號，回傳 dict（含 admin_id, username, password_hash）或 None。"""
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT admin_id, username, password_hash FROM Admins WHERE username = ?",
            username
        )
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))
    except Exception as e:
        print(f"get_user_by_username 查詢失敗: {e}")
        return None
    finally:
        conn.close()


# 陳政雍 8/1修改
def create_admin_user(username: str, password_hash: str) -> bool:
    """初始化工具用：新增管理員帳號（由 scripts/create_admin.py 呼叫）。"""
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Admins (username, password_hash) VALUES (?, ?)",
            username, password_hash
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"create_admin_user 寫入失敗: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# ── CLI 工具寫入（供 Tree-Trunk-Segmentation/main.py 的桌面版呼叫）
def insert_record_with_location(species, dbh, carbon, lat, lon, thumbnail_data=None):
    """CLI 桌面工具用：儲存含 GPS 座標的辨識紀錄（status='confirmed'）。"""
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")
