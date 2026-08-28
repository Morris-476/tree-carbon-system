"""
services/db.py
所有 SQL Server 查詢邏輯的唯一入口。
資料庫正規化為五張表：Sites、Species_Ref、Trees、Measurements、Admins。
連線憑證一律從環境變數讀取，不寫死任何帳號密碼。
"""
import base64
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


def _img_bin_to_data_uri(img_bin) -> "str | None":
    """把圖片二進位內容轉成前端可直接用的 data URI 字串。"""
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
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")


# 負責人：陳政雍 8/27 新增 record_id、dbh、site_name 三個欄位
# ── 地圖頁查詢（v_TreeCompleteData 檢視表）───────────────────────
def get_tree_map_data():
    """地圖頁用：回傳樹木清單與資料庫連線狀態。"""
    conn = get_db_connection()
    if conn is None:
        return [], "disconnected"
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                record_id,
                species_name,
                dbh,
                carbon_absorpation,
                latitude,
                longitude,
                site_name,
                image_data
            FROM v_TreeCompleteData
        """)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        tree_list = [dict(zip(columns, row)) for row in rows]
        for tree in tree_list:
            tree['img'] = _img_bin_to_data_uri(tree.pop('image_data', None))
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
    """回傳全站統計數字，供首頁使用。"""
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
    """回傳樹木清單，供資料展示頁使用。"""
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


# ── 時間對齊管線寫入（Arduino/RTK 對齊後的原始感測器資料）────────
# 負責人：蔡宗倫
# 開發日期：2026/08/22
def save_sensor_sync_records(records: list) -> dict:
    """寫入時間對齊後的原始感測器資料（Sensor_Sync_Records）。
    此表僅存放 merge_data.py 對齊完的中繼資料，供之後影像追蹤（tracker）與
    樹徑計算完成後，配合 track_id 寫入正式的 Trees / Measurements。
    records 為 list of dict，欄位需對應 sql/create_tables.sql 中 Sensor_Sync_Records 的定義。
    """
    if not records:
        return {'status': 'success', 'inserted': 0}

    conn = get_db_connection()
    if conn is None:
        return {'status': 'error', 'message': '資料庫連線失敗'}
    try:
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT INTO Sensor_Sync_Records (
                merge_batch_id, arduino_tree_id, recorded_at,
                latitude, longitude, rtk_height_m, rtk_speed_mps, rtk_heading_deg, rtk_tag,
                laser_status, led_status, tof_dist1_cm, tof_dist2_cm,
                rtk_gap_ms, video_offset_ms, video_filename
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r['merge_batch_id'], r['arduino_tree_id'], r['recorded_at'],
                    r['latitude'], r['longitude'], r['rtk_height_m'], r['rtk_speed_mps'],
                    r['rtk_heading_deg'], r['rtk_tag'],
                    r['laser_status'], r['led_status'], r['tof_dist1_cm'], r['tof_dist2_cm'],
                    r['rtk_gap_ms'], r['video_offset_ms'], r['video_filename'],
                )
                for r in records
            ]
        )
        conn.commit()
        return {'status': 'success', 'inserted': len(records)}
    except Exception as e:
        conn.rollback()
        return {'status': 'error', 'message': f'寫入 Sensor_Sync_Records 失敗：{str(e)}'}
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
# 直接查 Measurements/Trees/Sites/Species_Ref，不透過 v_AdminPendingQueue
# —— 該 view 內部用 INNER JOIN，Trees.site_id／species_id 為 NULL 時
# 會把整筆濾掉，用 LEFT JOIN 才不會受影響。
def get_all_trees_admin():
    """後台用：回傳待審核清單。"""
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                m.record_id           AS id,
                sp.species_name        AS species,
                m.dbh                   AS dbh,
                m.carbon_absorpation    AS carbon,
                s.site_name              AS site,
                m.[DATE]                 AS measure_date,
                m.[TIME]                  AS measure_time,
                t.[LATITUDE N/S]           AS lat_raw,
                t.[LONGITUDE E/W]           AS lng_raw,
                m.image_data                 AS image_bin
            FROM Measurements m
            LEFT JOIN Trees t       ON t.Tree_ID = m.Tree_ID
            LEFT JOIN Sites s       ON s.site_id = t.site_id
            LEFT JOIN Species_Ref sp ON sp.species_id = t.species_id
            WHERE LOWER(m.status) = 'pending'
        """)
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        trees = []
        for row in rows:
            recorded_at = ' '.join(
                part for part in (row['measure_date'], row['measure_time']) if part
            )
            trees.append({
                'id': row['id'],
                'species': row['species'],
                'dbh': float(row['dbh']) if row['dbh'] is not None else None,
                'carbon': float(row['carbon']) if row['carbon'] is not None else None,
                'lat': _parse_coord(row['lat_raw']),
                'lng': _parse_coord(row['lng_raw']),
                'site': row['site'],
                'status': 'pending',
                'recorded_at': recorded_at or None,
                'img': _img_bin_to_data_uri(row['image_bin']),
            })
        return trees
    except Exception as e:
        print(f"get_all_trees_admin 查詢失敗: {e}")
        return []
    finally:
        conn.close()


# 負責人：陳政雍 8/27 完成確認／刪除功能：實作 update_tree_status()、delete_tree()
# 張恆輔 8/28新增：dbh／carbon 可選（數據管理維護頁雙擊編輯後，按確認時一併存回），
# 只更新有帶值的欄位。
def update_tree_status(tree_id: int, new_status: str, dbh=None, carbon=None) -> bool:
    """後台：更新 Measurements 審核狀態，可一併更新 dbh／carbon_absorpation。
    回傳 True 表示更新成功（有找到該筆）。
    """
    fields = ['status = ?']
    params = [new_status]
    if dbh is not None:
        fields.append('dbh = ?')
        params.append(dbh)
    if carbon is not None:
        fields.append('carbon_absorpation = ?')
        params.append(carbon)
    params.append(tree_id)

    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE Measurements SET {', '.join(fields)} WHERE record_id = ?",
            params
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
    """CLI 桌面工具用：儲存含 GPS 座標的辨識紀錄。"""
    # TODO: 待實作 — 負責人：____
    raise NotImplementedError("此函式尚未實作")
