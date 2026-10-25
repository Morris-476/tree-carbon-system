# 負責人：陳信睿、張恆輔、陳政雍、蔡宗倫、Morris
# 用途：所有 SQL 查詢邏輯的唯一入口，routes/ 一律不可直接查資料庫

import base64
import datetime
import pyodbc
import config

# IPCC 預設含碳率（生質量中碳的比例）
CARBON_FRACTION = 0.47

def calculate_carbon(dbh: float, allo_param_a: float = 0.09, allo_param_b: float = 2.4, carbon_fraction: float = 0.5):
    """內建簡易固碳計算（避免依賴找不到的模組）"""
    class Result:
        def __init__(self, biomass_kg, carbon_kg, error=None):
            self.biomass_kg = biomass_kg
            self.carbon_kg = carbon_kg
            self.error = error

    try:
        if dbh is None or dbh <= 0:
            return Result(0.0, 0.0, error="DBH無效")
        biomass = allo_param_a * (dbh ** allo_param_b)
        carbon = biomass * carbon_fraction
        return Result(round(biomass, 2), round(carbon, 2))
    except Exception as e:
        return Result(0.0, 0.0, error=str(e))

def get_db_connection():
    """建立 SQL Server 連線（採用 config.py 自動匹配的驅動與環境變數）"""
    try:
        if hasattr(config, 'DB_CONNECTION_STRING') and config.DB_CONNECTION_STRING:
            return pyodbc.connect(config.DB_CONNECTION_STRING)
            
        base = (
            f"DRIVER={{{getattr(config, 'chosen_driver', 'ODBC Driver 17 for SQL Server')}}};"
            f'SERVER={config.DB_SERVER};'
            f'DATABASE={config.DB_NAME};'
            f'Encrypt={config.DB_ENCRYPT};'
            f'TrustServerCertificate={config.DB_TRUST_CERT};'
            f'Timeout=15;'
        )
        if config.DB_USER:
            conn_str = base + f'UID={config.DB_USER};PWD={config.DB_PASSWORD};'
        else:
            conn_str = base + 'Trusted_Connection=yes;'
        return pyodbc.connect(conn_str)
    except Exception as e:
        print(f'資料庫連線失敗: {e}')
        return None


def _img_bin_to_data_uri(img_bin) -> 'str | None':
    """相容舊版：把圖片二進位內容轉成前端 data URI 字串"""
    if img_bin is None:
        return None
    img_bytes = bytes(img_bin)
    if img_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        mime = 'image/png'
    elif img_bytes.startswith(b'\xff\xd8\xff'):
        mime = 'image/jpeg'
    else:
        mime = 'image/jpeg'
    b64 = base64.b64encode(img_bytes).decode('ascii')
    return f'data:{mime};base64,{b64}'


def _get_or_create_species(cursor, species_name: str) -> int:
    """查詢 Species_Ref，若不存在則以預設係數新增。回傳 species_id。"""
    cursor.execute(
        'SELECT species_id FROM Species_Ref WHERE species_name = ?', species_name
    )
    row = cursor.fetchone()
    if row is not None:
        return row[0]
    cursor.execute(
        'INSERT INTO Species_Ref (species_name) OUTPUT INSERTED.species_id VALUES (?)',
        species_name
    )
    return cursor.fetchone()[0]


def get_or_create_species_id(species_name: str) -> int:
    """查詢／新增 Species_Ref，回傳 species_id。"""
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError('資料庫連線失敗，無法查詢/新增樹種')
    try:
        cursor = conn.cursor()
        species_id = _get_or_create_species(cursor, species_name)
        conn.commit()
        return species_id
    finally:
        conn.close()


def _get_or_create_tree_id(cursor, track_id, species_id=None,
                            lat=None, lon=None, site_id=None) -> int:
    """依 tracker_id 找出（或新增）對應的 Tree_ID"""
    if track_id is not None:
        cursor.execute('SELECT Tree_ID FROM Trees WHERE tracker_id = ?', track_id)
        row = cursor.fetchone()
        if row is not None:
            return row[0]
    else:
        cursor.execute('SELECT ISNULL(MAX(tracker_id), 0) + 1 FROM Trees')
        track_id = cursor.fetchone()[0]

    cursor.execute(
        'INSERT INTO Trees (site_id, tracker_id, species_id, [LATITUDE N/S], [LONGITUDE E/W]) '
        'OUTPUT INSERTED.Tree_ID VALUES (?, ?, ?, ?, ?)',
        site_id, track_id, species_id, lat, lon
    )
    return cursor.fetchone()[0]


# ── 地圖頁查詢（v_TreeCompleteData 檢視表，優先讀取 Azure Blob URL）──
def get_tree_map_data():
    """地圖頁用：回傳樹木清單與資料庫連線狀態。"""
    conn = get_db_connection()
    if conn is None:
        return [], 'disconnected'
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                record_id,
                tracker_id         AS tree_id,
                species_name,
                dbh,
                carbon_absorpation,
                latitude,
                longitude,
                site_name,
                image_url
            FROM v_TreeCompleteData
        ''')
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        tree_list = [dict(zip(columns, row)) for row in rows]
        for tree in tree_list:
            tree['img'] = tree.get('image_url') or '/static/img/no-image.png'
            tree['latitude'] = _parse_coord(tree['latitude'])
            tree['longitude'] = _parse_coord(tree['longitude'])
        return tree_list, 'connected'
    except Exception as e:
        print(f'get_tree_map_data 查詢失敗: {e}')
        return [], 'disconnected'
    finally:
        conn.close()


# ── 首頁統計查詢 ──
def get_stats():
    """回傳全站統計數字，供首頁使用。"""
    conn = get_db_connection()
    if conn is None:
        return {'total_trees': 0, 'total_carbon': 0}
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) AS total_trees, ISNULL(SUM(carbon_absorpation), 0) AS total_carbon
            FROM Measurements
            WHERE status = 'Approved'
        ''')
        row = cursor.fetchone()
        return {
            'total_trees': row[0] if row else 0,
            'total_carbon': float(round(row[1], 2)) if row and row[1] else 0.0
        }
    except Exception as e:
        print(f'get_stats 查詢失敗: {e}')
        return {'total_trees': 0, 'total_carbon': 0}
    finally:
        conn.close()


def get_species_list():
    """回傳所有樹種資料"""
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT species_id, species_name, allo_param_a, allo_param_b, carbon_fraction '
            'FROM Species_Ref ORDER BY species_name'
        )
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception as e:
        print(f'get_species_list 查詢失敗: {e}')
        return []
    finally:
        conn.close()


_FALLBACK_CAMERA_PROFILES = [
    {'name': 'iPhone 13', 'focal_mm': 5.7, 'sensor_width': 7.5},
    {'name': 'iPhone 13 Pro', 'focal_mm': 5.8, 'sensor_width': 7.8},
    {'name': 'iPhone 14', 'focal_mm': 5.7, 'sensor_width': 7.5},
    {'name': 'iPhone 14 Pro', 'focal_mm': 6.9, 'sensor_width': 10.0},
    {'name': 'iPhone 15', 'focal_mm': 6.2, 'sensor_width': 8.2},
    {'name': 'iPhone 15 Pro', 'focal_mm': 6.9, 'sensor_width': 10.0},
    {'name': 'iPhone 16', 'focal_mm': 6.2, 'sensor_width': 8.2},
    {'name': 'iPhone 16 Pro', 'focal_mm': 6.9, 'sensor_width': 10.0},
    {'name': 'Samsung Galaxy S24 Ultra', 'focal_mm': 6.5, 'sensor_width': 9.9},
]


def get_camera_profiles():
    """回傳可選的拍攝設備清單"""
    conn = get_db_connection()
    if conn is None:
        return _FALLBACK_CAMERA_PROFILES
    try:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT profile_id, name, focal_mm, sensor_width '
            'FROM Camera_Profiles ORDER BY name'
        )
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return rows if rows else _FALLBACK_CAMERA_PROFILES
    except Exception as e:
        return _FALLBACK_CAMERA_PROFILES
    finally:
        conn.close()


def _ensure_measurement_columns(cursor):
    columns = {
        'latitude': 'FLOAT NULL',
        'longitude': 'FLOAT NULL',
        'SPEED': 'DECIMAL(4,2) NULL',
        'HEADING': 'INT NULL',
        'TAG': 'CHAR(1) NULL',
        'HEIGHT': 'INT NULL',
        'Laser_Status': 'VARCHAR(10) NULL',
        'LED_Status': 'VARCHAR(10) NULL',
        'ToF_Dist1_cm': 'INT NULL',
        'ToF_Dist2_cm': 'INT NULL',
        'gnss_gap_ms': 'INT NULL',
        'video_offset_ms': 'INT NULL',
        'site_name': 'VARCHAR(255) NULL',
        'image_data': 'VARBINARY(MAX) NULL',
        'image_url': 'NVARCHAR(500) NULL',  # 🎯 支援 Azure Blob URL
        'track_id': 'INT NULL',
        'pixel_width': 'INT NULL',
        'mask_width': 'INT NULL',
        'focal_mm': 'DECIMAL(6,2) NULL',
        'sensor_width_mm': 'DECIMAL(6,2) NULL',
    }
    for name, ddl in columns.items():
        cursor.execute(
            f"IF COL_LENGTH('dbo.Measurements', '{name}') IS NULL "
            f"ALTER TABLE dbo.Measurements ADD [{name}] {ddl}"
        )


def _rename_rtk_gap_column(cursor):
    cursor.execute(
        "IF COL_LENGTH('dbo.Measurements', 'rtk_gap_ms') IS NOT NULL "
        "AND COL_LENGTH('dbo.Measurements', 'gnss_gap_ms') IS NULL "
        "EXEC sp_rename 'dbo.Measurements.rtk_gap_ms', 'gnss_gap_ms', 'COLUMN'"
    )


def _ensure_tree_columns(cursor):
    cursor.execute(
        "IF COL_LENGTH('dbo.Trees', 'site_id') IS NULL "
        "ALTER TABLE dbo.Trees ADD site_id INT NULL"
    )


def _drop_unused_measurement_columns(cursor):
    cursor.execute(
        "IF COL_LENGTH('dbo.Measurements', 'video_fps') IS NOT NULL "
        "ALTER TABLE dbo.Measurements DROP COLUMN video_fps"
    )


_schema_ready = False


def _ensure_schema_ready(cursor):
    global _schema_ready
    if _schema_ready:
        return
    _rename_rtk_gap_column(cursor)
    _ensure_measurement_columns(cursor)
    _ensure_tree_columns(cursor)
    _drop_unused_measurement_columns(cursor)
    _schema_ready = True


def _coord_to_str(value, positive_letter, negative_letter):
    if value is None:
        return None
    letter = positive_letter if value >= 0 else negative_letter
    return f'{abs(value):.7f}{letter}'


def update_tree_coordinate(tree_id, latitude, longitude) -> None:
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError('資料庫連線失敗，無法寫回 Trees 座標')
    try:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE Trees SET [LATITUDE N/S] = ?, [LONGITUDE E/W] = ? WHERE Tree_ID = ?',
            _coord_to_str(latitude, 'N', 'S'), _coord_to_str(longitude, 'E', 'W'), tree_id
        )
        conn.commit()
    finally:
        conn.close()


def insert_tree_coordinate(latitude, longitude, tracker_id=None) -> int:
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError('資料庫連線失敗，無法寫回 Trees 座標')
    try:
        cursor = conn.cursor()
        if tracker_id is None:
            cursor.execute('SELECT ISNULL(MAX(tracker_id), 0) + 1 FROM Trees')
            tracker_id = cursor.fetchone()[0]
        cursor.execute(
            'INSERT INTO Trees (tracker_id, [LATITUDE N/S], [LONGITUDE E/W]) '
            'OUTPUT INSERTED.Tree_ID VALUES (?, ?, ?)',
            tracker_id, _coord_to_str(latitude, 'N', 'S'), _coord_to_str(longitude, 'E', 'W')
        )
        tree_id = cursor.fetchone()[0]
        conn.commit()
        return tree_id
    finally:
        conn.close()


def find_linked_tree_id(site_name, track_id, video_seq):
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError('資料庫連線失敗，無法查詢既有 Tree_ID')
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT TOP 1 m.Tree_ID
            FROM Measurements m
            JOIN Trees t ON t.Tree_ID = m.Tree_ID
            WHERE m.site_name = ? AND m.track_id = ? AND m.video_seq = ?
              AND t.tracker_id = m.track_id
        ''', site_name, track_id, video_seq)
        row = cursor.fetchone()
        return row[0] if row is not None else None
    finally:
        conn.close()


def link_measurement_to_tree(site_name, video_seq, track_id, tree_id) -> None:
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError('資料庫連線失敗，無法更新 Measurements.Tree_ID')
    try:
        cursor = conn.cursor()
        if track_id is None:
            cursor.execute(
                'UPDATE Measurements SET Tree_ID = ? '
                'WHERE site_name = ? AND video_seq = ? AND track_id IS NULL',
                tree_id, site_name, video_seq
            )
        else:
            cursor.execute(
                'UPDATE Measurements SET Tree_ID = ? '
                'WHERE site_name = ? AND video_seq = ? AND track_id = ?',
                tree_id, site_name, video_seq, track_id
            )
        conn.commit()
    finally:
        conn.close()


def get_trees_needing_species() -> list:
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError('資料庫連線失敗，無法查詢待判定樹種的樹')
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT Tree_ID, image_data FROM (
                SELECT
                    t.Tree_ID,
                    m.image_data,
                    ROW_NUMBER() OVER (
                        PARTITION BY t.Tree_ID
                        ORDER BY CASE WHEN m.Final_Dist_cm IS NOT NULL THEN 0 ELSE 1 END, m.record_id
                    ) AS rn
                FROM Trees t
                JOIN Measurements m ON m.Tree_ID = t.Tree_ID
                WHERE t.species_id IS NULL AND m.image_data IS NOT NULL
            ) ranked
            WHERE rn = 1
        ''')
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def update_tree_species(tree_id, species_id) -> None:
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError('資料庫連線失敗，無法寫回 Trees 樹種')
    try:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE Trees SET species_id = ? WHERE Tree_ID = ?',
            species_id, tree_id
        )
        conn.commit()
    finally:
        conn.close()


def get_measurements_needing_diameter() -> list:
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError('資料庫連線失敗，無法查詢待換算樹徑的紀錄')
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                record_id,
                Final_Pixel_Width AS pixel_width,
                mask_width,
                Final_Dist_cm AS distance_cm,
                focal_mm,
                sensor_width_mm
            FROM Measurements
            WHERE dbh = 0
              AND Final_Dist_cm IS NOT NULL
              AND Final_Pixel_Width IS NOT NULL
              AND mask_width IS NOT NULL
              AND focal_mm IS NOT NULL
              AND sensor_width_mm IS NOT NULL
        ''')
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def update_measurement_dbh(record_id, dbh) -> None:
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError('資料庫連線失敗，無法寫回 Measurements.dbh')
    try:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE Measurements SET dbh = ? WHERE record_id = ?',
            dbh, record_id
        )
        conn.commit()
    finally:
        conn.close()


def get_measurements_needing_carbon() -> list:
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError('資料庫連線失敗，無法查詢待計算固碳量的紀錄')
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                m.record_id,
                m.dbh,
                s.allo_param_a,
                s.allo_param_b,
                s.carbon_fraction
            FROM Measurements m
            JOIN Trees t ON t.Tree_ID = m.Tree_ID
            JOIN Species_Ref s ON s.species_id = t.species_id
            WHERE m.carbon_absorpation = 0
              AND m.dbh > 0
              AND s.allo_param_a IS NOT NULL
              AND s.allo_param_b IS NOT NULL
              AND s.carbon_fraction IS NOT NULL
        ''')
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def update_measurement_carbon(record_id, biomass, carbon_absorpation) -> None:
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError('資料庫連線失敗，無法寫回 Measurements 固碳量')
    try:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE Measurements SET biomass = ?, carbon_absorpation = ? WHERE record_id = ?',
            biomass, carbon_absorpation, record_id
        )
        conn.commit()
    finally:
        conn.close()


def save_time_synced_measurements(records: list, site_name) -> dict:
    """寫入時間對齊後的資料（支援 image_url）到 dbo.Measurements"""
    if not records:
        return {'status': 'success', 'inserted': 0, 'tree_id': None}

    conn = get_db_connection()
    if conn is None:
        return {'status': 'error', 'message': '資料庫連線失敗'}
    try:
        cursor = conn.cursor()
        _ensure_schema_ready(cursor)

        for r in records:
            recorded_at = r['recorded_at']
            cursor.execute(
                'INSERT INTO Measurements ('
                'Tree_ID, dbh, biomass, carbon_absorpation, status, [DATE], [TIME], '
                'latitude, longitude, SPEED, HEADING, TAG, HEIGHT, '
                'Laser_Status, LED_Status, ToF_Dist1_cm, ToF_Dist2_cm, '
                'gnss_gap_ms, video_offset_ms, site_name, image_url, '
                'track_id, pixel_width, mask_width, focal_mm, sensor_width_mm'
                ') VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                None, 0, 0, 0, 'Pending',
                recorded_at.strftime('%Y/%m/%d'), recorded_at.strftime('%H:%M:%S'),
                r.get('latitude'), r.get('longitude'), r.get('rtk_speed_mps'), r.get('rtk_heading_deg'),
                r.get('rtk_tag'), r.get('rtk_height_m'),
                r.get('laser_status'), r.get('led_status'),
                int(r.get('tof_dist1_cm', 0)), int(r.get('tof_dist2_cm', 0)),
                r.get('gnss_gap_ms'), r.get('video_offset_ms'), site_name,
                r.get('image_url'),  # 🎯 存入 Blob URL
                r.get('track_id'), r.get('pixel_width'), r.get('mask_width'),
                r.get('focal_mm'), r.get('sensor_width_mm'),
            )
        conn.commit()
        return {'status': 'success', 'inserted': len(records), 'tree_id': None}
    except Exception as e:
        conn.rollback()
        return {'status': 'error', 'message': f'寫入 Measurements 失敗：{str(e)}'}
    finally:
        conn.close()


def _parse_coord(raw):
    if not raw:
        return None
    raw = str(raw).strip()
    direction = raw[-1].upper()
    if direction not in ('N', 'S', 'E', 'W'):
        try:
            return float(raw)
        except ValueError:
            return None
    try:
        value = float(raw[:-1])
    except ValueError:
        return None
    return -value if direction in ('S', 'W') else value


# ── 後台管理：樹木清單（支援 image_url）──
def get_all_trees_admin():
    """後台待審核用：優先讀取 image_url，若無則讀取舊 image_data"""
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                m.record_id       AS id,
                m.Tree_ID         AS tree_id,
                sp.species_name   AS species,
                m.dbh             AS dbh,
                m.carbon_absorpation AS carbon,
                m.site_name       AS site,
                t.[LATITUDE N/S]  AS lat_raw,
                t.[LONGITUDE E/W] AS lng_raw,
                m.image_url       AS image_url,
                m.image_data      AS image_bin,
                m.[DATE]          AS measure_date,
                m.[TIME]          AS measure_time
            FROM Measurements m
            LEFT JOIN Trees t ON t.Tree_ID = m.Tree_ID
            LEFT JOIN Species_Ref sp ON sp.species_id = t.species_id
            WHERE m.status = 'Pending'
        ''')
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        trees = []
        for row in rows:
            recorded_at = ' '.join(
                part for part in (str(row['measure_date']), str(row['measure_time'])) if part
            )
            img_src = row.get('image_url') or _img_bin_to_data_uri(row.get('image_bin')) or '/static/img/no-image.png'

            trees.append({
                'id': row['id'],
                'tree_id': row['tree_id'],
                'species': row['species'] or '未辨識樹種',
                'dbh': float(row['dbh']) if row['dbh'] is not None else None,
                'carbon': float(row['carbon']) if row['carbon'] is not None else None,
                'lat': _parse_coord(row['lat_raw']),
                'lng': _parse_coord(row['lng_raw']),
                'site': row['site'] or '未指定案場',
                'status': 'pending',
                'recorded_at': recorded_at or None,
                'img': img_src,
            })
        return trees
    except Exception as e:
        print(f'get_all_trees_admin 查詢失敗: {e}')
        return []
    finally:
        conn.close()


def admin_update_measurement(record_id: int, new_status: str, dbh=None, species=None):
    """後台更新狀態：放寬圖片檢查為 image_url 或 image_data 任一有值即可"""
    conn = get_db_connection()
    if conn is None:
        return False, '資料庫連線失敗'
    try:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT m.Tree_ID, m.dbh, m.image_url, m.image_data, m.track_id,
                   t.tracker_id, t.[LATITUDE N/S], t.[LONGITUDE E/W]
            FROM Measurements m
            LEFT JOIN Trees t ON t.Tree_ID = m.Tree_ID
            WHERE m.record_id = ?
        ''', record_id)
        row = cursor.fetchone()
        if row is None:
            return False, '查無此筆資料'
        (current_tree_id, current_dbh, image_url, image_data, m_track_id,
         t_tracker_id, lat_raw, lng_raw) = row

        if dbh is not None:
            cursor.execute('UPDATE Measurements SET dbh = ? WHERE record_id = ?', dbh, record_id)
            current_dbh = dbh

        if species is not None and current_tree_id is not None:
            species_id = _get_or_create_species(cursor, species)
            cursor.execute(
                'UPDATE Trees SET species_id = ? WHERE Tree_ID = ?',
                species_id, current_tree_id
            )

        if new_status == 'Approved':
            missing = []
            if not image_url and not image_data:
                missing.append('照片')
            if current_dbh is None or current_dbh <= 0:
                missing.append('樹徑')
            if lat_raw is None or lng_raw is None:
                missing.append('座標')
            if missing:
                conn.commit()
                return False, f"資料不完整（缺少：{'、'.join(missing)}），無法核准"

        cursor.execute(
            'UPDATE Measurements SET status = ? WHERE record_id = ?',
            new_status, record_id
        )
        found = cursor.rowcount > 0

        if current_tree_id is not None and current_dbh is not None and current_dbh > 0:
            cursor.execute('''
                SELECT s.allo_param_a, s.allo_param_b, s.carbon_fraction
                FROM Trees t
                JOIN Species_Ref s ON s.species_id = t.species_id
                WHERE t.Tree_ID = ?
            ''', current_tree_id)
            species_row = cursor.fetchone()
            if species_row is not None:
                allo_a, allo_b, carbon_fraction = species_row
                result = calculate_carbon(
                    dbh=float(current_dbh),
                    allo_param_a=float(allo_a) if allo_a is not None else None,
                    allo_param_b=float(allo_b) if allo_b is not None else None,
                    carbon_fraction=float(carbon_fraction) if carbon_fraction is not None else None,
                )
                if result.error is None:
                    cursor.execute(
                        'UPDATE Measurements SET biomass = ?, carbon_absorpation = ? WHERE record_id = ?',
                        result.biomass_kg, result.carbon_kg, record_id
                    )

        conn.commit()
        return found, (None if found else '查無此筆資料')
    except Exception as e:
        print(f'admin_update_measurement 更新失敗: {e}')
        conn.rollback()
        return False, '更新失敗，發生系統錯誤'
    finally:
        conn.close()


def delete_tree(record_id: int) -> bool:
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT Tree_ID FROM Measurements WHERE record_id = ?', record_id)
        row = cursor.fetchone()
        if row is None:
            return False
        tree_id = row[0]

        if tree_id is None:
            cursor.execute('DELETE FROM Measurements WHERE record_id = ?', record_id)
        else:
            cursor.execute('DELETE FROM Measurements WHERE Tree_ID = ?', tree_id)
            cursor.execute('DELETE FROM Trees WHERE Tree_ID = ?', tree_id)
        conn.commit()
        return True
    except Exception as e:
        print(f'delete_tree 刪除失敗: {e}')
        conn.rollback()
        return False
    finally:
        conn.close()


def get_user_by_username(username: str):
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT admin_id, username, password_hash FROM Admins WHERE username = ?',
            username
        )
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))
    except Exception as e:
        print(f'get_user_by_username 查詢失敗: {e}')
        return None
    finally:
        conn.close()


def create_admin_user(username: str, password_hash: str) -> bool:
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO Admins (username, password_hash) VALUES (?, ?)',
            username, password_hash
        )
        conn.commit()
        return True
    except Exception as e:
        print(f'create_admin_user 寫入失敗: {e}')
        conn.rollback()
        return False
    finally:
        conn.close()