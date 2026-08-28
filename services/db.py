# 陳信睿 8/28 修改
"""
services/db.py
所有 SQL Server 查詢邏輯的唯一入口。
資料庫正規化為五張表：Sites、Species_Ref、Trees、Measurements、Admins。
連線憑證一律從環境變數讀取，不寫死任何帳號密碼。
"""
import base64
import datetime
import os
import uuid
import pyodbc
import config

# IPCC 預設含碳率（生質量中碳的比例），用於由 carbon_absorpation 反推 biomass。
# Measurements.biomass 為 NOT NULL，但目前專案內尚無正式的生質量計算公式，
# 待負責固碳計算的同學補上真正公式後，這裡應替換掉。
CARBON_FRACTION = 0.47


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


def _img_bin_to_data_uri(img_bin) -> "str | None":
    """把資料庫 image_data（VARBINARY）讀出的二進位內容轉成前端可直接用的
    data URI（data:image/...;base64,...），供 <img src> 直接顯示。
    img_bin 為 None 時回傳 None（不拋出例外）。

    圖片一律直接以二進位存入資料庫的 image_data 欄位，不寫檔到 static/img/。
    寫入時同理：INSERT/UPDATE 直接把 bytes 帶入 image_data 參數即可，
    pyodbc 會自動對應到 VARBINARY(MAX)，不需要額外轉換。
    """
    if img_bin is None:
        return None
    img_bytes = bytes(img_bin)
    if img_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        mime = 'image/png'
    elif img_bytes.startswith(b'\xff\xd8\xff'):
        mime = 'image/jpeg'
    elif img_bytes[:6] in (b'GIF87a', b'GIF89a'):
        mime = 'image/gif'
    else:
        mime = 'image/jpeg'
    b64 = base64.b64encode(img_bytes).decode('ascii')
    return f'data:{mime};base64,{b64}'


def _get_or_create_species(cursor, species_name: str) -> int:
    """查詢 Species_Ref，若不存在則以預設係數新增。回傳 species_id。"""
    cursor.execute(
        "SELECT species_id FROM Species_Ref WHERE species_name = ?", species_name
    )
    row = cursor.fetchone()
    if row is not None:
        return row[0]
    cursor.execute(
        "INSERT INTO Species_Ref (species_name) OUTPUT INSERTED.species_id VALUES (?)",
        species_name
    )
    return cursor.fetchone()[0]


# 這個 BUG 的核心修法：Trees.tracker_id 為 NOT NULL，代表每一棵「偵測到的樹」
# 都必須有自己專屬的 tracker_id（ByteTrack 給的追蹤編號），才能各自對應到
# 獨立的 Tree_ID。同一個 tracker_id 出現第二次，代表同一棵樹的另一次量測，
# 才共用既有 Tree_ID；tracker_id 是全新的，或呼叫端沒有追蹤器可用（例如桌面
# CLI 單張照片辨識），一律視為新樹、INSERT 一筆新的 Trees 記錄取得新 Tree_ID。
# 絕對不可以省略 tracker_id 或用固定值頂替，否則所有偵測到的樹都會被誤綁成
# 同一個 Tree_ID（這正是目前資料庫裡發生的問題）。
def _get_or_create_tree_id(cursor, track_id, species_id=None,
                            lat=None, lon=None, site_id=None) -> int:
    """依 tracker_id 找出（或新增）對應的 Tree_ID。
    track_id 為 None 時視為沒有追蹤資訊可比對，一律新增一筆 Trees 記錄。
    """
    if track_id is not None:
        cursor.execute("SELECT Tree_ID FROM Trees WHERE tracker_id = ?", track_id)
        row = cursor.fetchone()
        if row is not None:
            return row[0]
    else:
        cursor.execute("SELECT ISNULL(MAX(tracker_id), 0) + 1 FROM Trees")
        track_id = cursor.fetchone()[0]

    cursor.execute(
        "INSERT INTO Trees (site_id, tracker_id, species_id, [LATITUDE N/S], [LONGITUDE E/W]) "
        "OUTPUT INSERTED.Tree_ID VALUES (?, ?, ?, ?, ?)",
        site_id, track_id, species_id, lat, lon
    )
    return cursor.fetchone()[0]


# 負責人：陳政雍 8/27 新增 record_id、dbh、site_name 三個欄位
# ── 地圖頁查詢（v_TreeCompleteData 檢視表）───────────────────────
def get_tree_map_data():
    """回傳 (tree_list, db_status)，供 routes/pages.py 的地圖頁使用。
    tree_list 中每筆需含 record_id, species_name, dbh, carbon_absorpation,
    latitude, longitude, site_name, img 欄位。
    img 為 data URI 字串（由 image_data 二進位欄位轉換而來），無圖片時為 None。
    db_status 為 "connected" 或 "disconnected"。
    """
    conn = get_db_connection()
    if conn is None:
        return [], "disconnected"
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                紀錄編號           AS record_id,
                樹木種類           AS species_name,
                樹徑cm             AS dbh,
                固碳量             AS carbon_absorpation,
                緯度               AS latitude,
                經度               AS longitude,
                巡檢案場           AS site_name,
                樹木照片二進位     AS image_data
            FROM v_TreeCompleteData
        """)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        tree_list = [dict(zip(columns, row)) for row in rows]
        for tree in tree_list:
            tree['img'] = _img_bin_to_data_uri(tree.pop('image_data', None))
            # 資料庫存的是 '25.0883747N' 這種帶方向字母的字串，Leaflet 的
            # L.marker() 需要純數字，不轉換的話座標會變成 NaN、標記顯示不出來。
            tree['latitude'] = _parse_coord(tree['latitude'])
            tree['longitude'] = _parse_coord(tree['longitude'])
        return tree_list, "connected"
    except Exception as e:
        print(f"get_tree_map_data 查詢失敗: {e}")
        return [], "disconnected"
    finally:
        conn.close()

# 負責人：陳信睿 8/18 首頁排版
# ── 首頁統計查詢（僅 confirmed）──────────────────────────────────
# 負責人：陳政雍 8/27 修正 status 值改為 Approved、固碳量欄位改用 carbon_absorpation
def get_stats():
    """回傳全站統計數字，供首頁使用。
    回傳 dict：{'total_trees': ..., 'total_carbon': ...}。
    連線失敗或查詢例外時回傳 {'total_trees': 0, 'total_carbon': 0}。
    """
    conn = get_db_connection()
    if conn is None:
        return {'total_trees': 0, 'total_carbon': 0}
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) AS total_trees, SUM(carbon_absorpation) AS total_carbon
            FROM Measurements
            WHERE status = 'Approved'
        """)
        columns = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        result = dict(zip(columns, row))
        return {
            'total_trees': result.get('total_trees') or 0,
            'total_carbon': result.get('total_carbon') or 0
        }
    except Exception as e:
        print(f"get_stats 查詢失敗: {e}")
        return {'total_trees': 0, 'total_carbon': 0}
    finally:
        conn.close()


# ── 資料展示頁查詢（僅 confirmed）────────────────────────────────
def get_tree_list():
    """回傳樹木清單，供 routes/pages.py 的資料展示頁使用。
    每筆需含 id, species, dbh, carbon, recorded_at, img_url 欄位。
    img_url 請用 _img_bin_to_data_uri() 把 SELECT 出來的 image_data 轉成 data URI。
    """
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


# ── 網頁上傳寫入（status='confirmed'，直接公開）──────────────────
def save_tree_record(species, dbh, carbon, img_bin):
    """儲存網頁上傳的辨識結果（無 GPS 座標）。
    img_bin 為圖片二進位內容，INSERT 時直接帶入 Measurements.image_data
    （VARBINARY 欄位）參數即可，不需寫檔到 static/img/。
    """
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


# ── 資料處理管線寫入（status 固定 pending，等待管理員審核）──────
def save_pipeline_record(species, dbh, carbon, lat, lon,
                         fix_quality=None, distance_cm=None,
                         track_id=None, status='Pending'):
    """管線上傳：含 GPS 座標，status 固定 pending，等待管理員審核後才公開。
    track_id 應帶入 ByteTrack 給該棵樹的追蹤 ID：同一段影片裡同一棵樹的
    多次量測要傳同一個 track_id（才會共用同一個 Tree_ID），不同棵樹要傳
    不同的 track_id（見 _get_or_create_tree_id 說明）。
    """
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        species_id = _get_or_create_species(cursor, species) if species else None
        tree_id = _get_or_create_tree_id(cursor, track_id, species_id, lat, lon)

        biomass = float(carbon) / CARBON_FRACTION
        now = datetime.datetime.now()
        cursor.execute(
            "INSERT INTO Measurements "
            "(Tree_ID, dbh, biomass, carbon_absorpation, status, [DATE], [TIME]) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            tree_id, dbh, biomass, carbon, status,
            now.strftime('%Y/%m/%d'), now.strftime('%H:%M:%S')
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"save_pipeline_record 寫入失敗: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# 張恆輔 8/25新增：'25.0883747N' 這種字串轉成帶正負號的十進位度數，S/W 為負
def _parse_coord(raw):
    if not raw:
        return None
    raw = raw.strip()
    direction = raw[-1].upper()
    if direction not in ('N', 'S', 'E', 'W'):
        return None
    try:
        value = float(raw[:-1])
    except ValueError:
        return None
    return -value if direction in ('S', 'W') else value


# ── 後台管理：樹木清單（僅 pending）───────────────────────────────
# v_AdminPendingQueue 已改為 LEFT JOIN 並補上緯度／經度欄位，
# 直接查這張 view 即可（view 內部已經用 WHERE m.status = N'Pending' 篩選過）。
def get_all_trees_admin():
    """後台用：回傳待審核清單（v_AdminPendingQueue 內部已篩選 status = 'Pending'）。
    每筆含 id, tree_id, species, dbh, carbon, lat, lng, site, status, img 欄位。

    id：這筆量測記錄本身的編號（record_id），確認／刪除單筆資料要用這個。
    tree_id：這筆量測所屬的實體樹編號（Trees.Tree_ID）。同一棵樹被多次量測
    時，多筆資料的 tree_id 會相同、但 id 各自不同，兩者不能混用。
    """
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                紀錄編號     AS id,
                Tree_ID      AS tree_id,
                樹木種類     AS species,
                樹徑cm       AS dbh,
                固碳量       AS carbon,
                巡檢案場     AS site,
                緯度         AS lat_raw,
                經度         AS lng_raw,
                樹木照片二進位 AS image_bin
            FROM v_AdminPendingQueue
        """)
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        trees = []
        for row in rows:
            trees.append({
                'id': row['id'],
                'tree_id': row['tree_id'],
                'species': row['species'],
                'dbh': float(row['dbh']) if row['dbh'] is not None else None,
                'carbon': float(row['carbon']) if row['carbon'] is not None else None,
                'lat': _parse_coord(row['lat_raw']),
                'lng': _parse_coord(row['lng_raw']),
                'site': row['site'],
                'status': 'pending',
                'img': _img_bin_to_data_uri(row['image_bin']),
            })
        return trees
    except Exception as e:
        print(f"get_all_trees_admin 查詢失敗: {e}")
        return []
    finally:
        conn.close()


# 負責人：陳政雍 8/27 完成確認／刪除功能：實作 update_tree_status()、delete_tree()
def update_tree_status(tree_id: int, new_status: str) -> bool:
    """後台：更新 Measurements 審核狀態。回傳 True 表示更新成功（有找到該筆）。"""
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Measurements SET status = ? WHERE record_id = ?",
            new_status, tree_id
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"update_tree_status 更新失敗: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# 張恆輔 8/25新增
def delete_tree(tree_id: int) -> bool:
    """後台：刪除一筆 Measurements 記錄。回傳 True 表示刪除成功（有找到該筆）。"""
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Measurements WHERE record_id = ?", tree_id)
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"delete_tree 刪除失敗: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


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
    """CLI 桌面工具用：儲存含 GPS 座標的辨識紀錄（status='Approved'）。
    thumbnail_data 為圖片二進位內容，INSERT 時直接帶入 Measurements.image_data
    （VARBINARY 欄位）參數即可，不需寫檔到 static/img/。

    桌面版沒有影片追蹤器可判斷「是不是同一棵樹」，每次呼叫都視為偵測到一棵
    新樹，一律建立新的 Trees 記錄（傳入 track_id=None，見
    _get_or_create_tree_id），不會沿用舊的 Tree_ID。
    """
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        species_id = _get_or_create_species(cursor, species) if species else None
        tree_id = _get_or_create_tree_id(cursor, None, species_id, lat, lon)

        biomass = float(carbon) / CARBON_FRACTION
        now = datetime.datetime.now()
        cursor.execute(
            "INSERT INTO Measurements "
            "(Tree_ID, dbh, biomass, carbon_absorpation, status, [DATE], [TIME], image_data) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            tree_id, dbh, biomass, carbon, 'Approved',
            now.strftime('%Y/%m/%d'), now.strftime('%H:%M:%S'), thumbnail_data
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"insert_record_with_location 寫入失敗: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
