# 負責人：陳信睿、張恆輔、陳政雍、蔡宗倫、Morris
# 開發日期：2026/08/01
# 用途：所有 SQL 查詢邏輯的唯一入口，routes/ 一律不可直接查資料庫

import base64
import datetime
import pyodbc
import config
from services.core.carbon import calculate_carbon

# IPCC 預設含碳率（生質量中碳的比例），用於由 carbon_absorpation 反推 biomass。
# Measurements.biomass 為 NOT NULL，但目前尚無正式的生質量計算公式，
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
        print(f'資料庫連線失敗: {e}')
        return None


def _img_bin_to_data_uri(img_bin) -> 'str | None':
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
    """查詢／新增 Species_Ref，回傳 species_id；供批次腳本使用，不需自行管理 cursor。"""
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


# tracker_id 不可省略或用固定值頂替：Trees.tracker_id 為 NOT NULL，同一個
# tracker_id 代表同一棵樹才共用既有 Tree_ID，否則所有偵測到的樹都會被誤綁成同一筆
def _get_or_create_tree_id(cursor, track_id, species_id=None,
                            lat=None, lon=None, site_id=None) -> int:
    """依 tracker_id 找出（或新增）對應的 Tree_ID，track_id 為 None 時一律新增一筆。"""
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


# ── 地圖頁查詢（v_TreeCompleteData 檢視表）──
def get_tree_map_data():
    """地圖頁用：回傳樹木清單與資料庫連線狀態。"""
    conn = get_db_connection()
    if conn is None:
        return [], 'disconnected'
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                紀錄編號           AS record_id,
                Tree_ID            AS tree_id,
                樹木種類           AS species_name,
                樹徑cm             AS dbh,
                固碳量             AS carbon_absorpation,
                緯度               AS latitude,
                經度               AS longitude,
                巡檢案場           AS site_name,
                樹木照片二進位     AS image_data
            FROM v_TreeCompleteData
        ''')
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        tree_list = [dict(zip(columns, row)) for row in rows]
        for tree in tree_list:
            tree['img'] = _img_bin_to_data_uri(tree.pop('image_data', None))
            # 資料庫存的是帶方向字母的字串（如 '25.0883747N'），Leaflet 需要
            # 純數字，不轉換的話座標會變成 NaN，地圖標記顯示不出來
            tree['latitude'] = _parse_coord(tree['latitude'])
            tree['longitude'] = _parse_coord(tree['longitude'])
        return tree_list, 'connected'
    except Exception as e:
        print(f'get_tree_map_data 查詢失敗: {e}')
        return [], 'disconnected'
    finally:
        conn.close()


# ── 首頁統計查詢（僅 Approved）──
def get_stats():
    """回傳全站統計數字，供首頁使用。"""
    conn = get_db_connection()
    if conn is None:
        return {'total_trees': 0, 'total_carbon': 0}
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) AS total_trees, SUM(carbon_absorpation) AS total_carbon
            FROM Measurements
            WHERE status = 'Approved'
        ''')
        columns = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        result = dict(zip(columns, row))
        return {
            'total_trees': result.get('total_trees') or 0,
            'total_carbon': result.get('total_carbon') or 0
        }
    except Exception as e:
        print(f'get_stats 查詢失敗: {e}')
        return {'total_trees': 0, 'total_carbon': 0}
    finally:
        conn.close()


# ── /measure 頁面查詢 ──
# ⚠️ carbon_fraction 欄位尚未加進 Species_Ref，此函式在補上前會查詢失敗
def get_species_list():
    """回傳所有樹種資料，供 /measure 頁面下拉選單與固碳計算使用。"""
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


# 資料上傳頁用，供選擇拍攝手機型號的下拉選單。Camera_Profiles 資料表若尚未
# 建立或查詢失敗，改用這份跟 static/measure/app.js 的 CAMERA_PRESETS 相同的
# 內建清單頂替；資料表就緒後會自動改吃資料庫資料，不用再改這支函式
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
    """回傳可選的拍攝設備清單（型號、焦距、感光元件寬度），供資料上傳頁下拉選單使用。"""
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
        print(f'get_camera_profiles 查詢失敗，改用內建清單: {e}')
        return _FALLBACK_CAMERA_PROFILES
    finally:
        conn.close()


# ── 資料展示頁查詢（僅 Approved）──
def get_tree_list():
    """回傳樹木清單，供資料展示頁使用。尚未實作。"""
    raise NotImplementedError('此函式尚未實作')


# ── 網頁上傳寫入（status='Approved'，直接公開）──
def save_tree_record(species, dbh, carbon, img_bin):
    """儲存網頁上傳的辨識結果（無 GPS 座標）。尚未實作。"""
    raise NotImplementedError('此函式尚未實作')


# ── 資料處理管線寫入（status 固定 Pending，等待管理員審核）──
def save_pipeline_record(species, dbh, carbon, lat, lon,
                         fix_quality=None, distance_cm=None,
                         track_id=None, status='Pending'):
    """管線上傳：含 GPS 座標，status 固定 Pending，等待管理員審核後才公開。
    track_id 為 ByteTrack 給該棵樹的追蹤 ID，同一棵樹的多次量測需傳同一個
    track_id 才會共用同一個 Tree_ID（見 _get_or_create_tree_id）。
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
            'INSERT INTO Measurements '
            '(Tree_ID, dbh, biomass, carbon_absorpation, status, [DATE], [TIME]) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            tree_id, dbh, biomass, carbon, status,
            now.strftime('%Y/%m/%d'), now.strftime('%H:%M:%S')
        )
        conn.commit()
        return True
    except Exception as e:
        print(f'save_pipeline_record 寫入失敗: {e}')
        conn.rollback()
        return False
    finally:
        conn.close()


# ── 時間對齊 + 影片截圖寫入 dbo.Measurements ──
# 補齊 Measurements 目前沒有、但這次寫入需要的欄位（已存在就不動）
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
        # 同一支影片內的追蹤結果，供之後 IQR 篩選＋樹徑換算使用
        'track_id': 'INT NULL',
        'pixel_width': 'INT NULL',
        # mask_width 是量出 pixel_width 當下那張遮罩的寬度；focal_mm／
        # sensor_width_mm 是這次上傳選擇的拍攝設備規格，整批共用同一組值
        'mask_width': 'INT NULL',
        'focal_mm': 'DECIMAL(6,2) NULL',
        'sensor_width_mm': 'DECIMAL(6,2) NULL',
    }
    for name, ddl in columns.items():
        cursor.execute(
            f"IF COL_LENGTH('dbo.Measurements', '{name}') IS NULL "
            f"ALTER TABLE dbo.Measurements ADD [{name}] {ddl}"
        )


# 欄位改名：rtk_gap_ms -> gnss_gap_ms（GPS 定位資料其實是 GNSS，不只 RTK，
# 名稱改得更準確）。用 sp_rename 保留既有資料；已經改過名字的資料庫會直接跳過
def _rename_rtk_gap_column(cursor):
    cursor.execute(
        "IF COL_LENGTH('dbo.Measurements', 'rtk_gap_ms') IS NOT NULL "
        "AND COL_LENGTH('dbo.Measurements', 'gnss_gap_ms') IS NULL "
        "EXEC sp_rename 'dbo.Measurements.rtk_gap_ms', 'gnss_gap_ms', 'COLUMN'"
    )


# 補 Trees 缺的 site_id 欄位：_get_or_create_tree_id() 的 INSERT 語法會用到
# site_id，資料庫沒有這欄的話會噴 Invalid column name 'site_id'
def _ensure_tree_columns(cursor):
    cursor.execute(
        "IF COL_LENGTH('dbo.Trees', 'site_id') IS NULL "
        "ALTER TABLE dbo.Trees ADD site_id INT NULL"
    )


# 清掉不再使用的舊欄位：video_fps 原本規劃用來把 video_offset_ms 換算成
# 實際影格編號，但全專案沒有程式碼讀寫它、一直是 NULL，故移除
def _drop_unused_measurement_columns(cursor):
    cursor.execute(
        "IF COL_LENGTH('dbo.Measurements', 'video_fps') IS NOT NULL "
        "ALTER TABLE dbo.Measurements DROP COLUMN video_fps"
    )


# 上述幾個 schema 檢查都有 IF COL_LENGTH 防呆、可安全重複執行，但放在每次
# /api/upload 請求的熱路徑上不是好做法，改成整個 process 啟動後只真正執行一次
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


# 把帶正負號的十進位度數轉回 Trees.[LATITUDE N/S] / [LONGITUDE E/W] 需要的字串格式
def _coord_to_str(value, positive_letter, negative_letter):
    if value is None:
        return None
    letter = positive_letter if value >= 0 else negative_letter
    return f'{abs(value):.7f}{letter}'


# 供 services/analysis/tree_coordinate.py 寫回大圓公式推算出的樹木座標，
# 覆蓋 Trees 原本存的（建樹時暫用的推車座標）經緯度
def update_tree_coordinate(tree_id, latitude, longitude) -> None:
    """把推算出的樹木座標（十進位度）覆蓋寫回 Trees.[LATITUDE N/S] / [LONGITUDE E/W]。"""
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


# 座標計算目前不比對既有 Trees 記錄，每筆符合條件的量測都直接新增一筆
# （Tree_ID 為 IDENTITY，接續現有最大值遞增）
def insert_tree_coordinate(latitude, longitude, tracker_id=None) -> int:
    """新增一筆 Trees 記錄，座標為算出的樹木座標。tracker_id 為 None 時
    （量測列沒有追蹤編號可用）自動接續 Trees 現有最大 tracker_id 遞增一號，
    因為 Trees.tracker_id 為 NOT NULL。回傳新增的 Tree_ID。"""
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


# 分群 key 為 (site_name, video_seq, track_id)：只比對 (site_name, track_id)
# 會在不同批次上傳撞號時誤判成同一棵樹，需一併比對 video_seq；用
# tracker_id 是否等於 track_id 判斷是否為已算過座標的真實 Tree
def find_linked_tree_id(site_name, track_id, video_seq):
    """回傳已經算過真實座標、且 (site_name, video_seq, track_id) 對得上的
    Tree_ID；找不到回傳 None。"""
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
    """把同一棵樹（同一 site_name+video_seq+track_id）底下所有 Measurements
    紀錄的 Tree_ID，一次填成算出真實座標後對應的 Tree_ID。"""
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError('資料庫連線失敗，無法更新 Measurements.Tree_ID')
    try:
        cursor = conn.cursor()
        # track_id 可能是 None（舊式無追蹤資料），SQL 的 = 比對 NULL 一律
        # 不成立，要改用 IS NULL，否則這種資料完全更新不到任何一筆
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
    """回傳 [{'tree_id': int, 'image_data': bytes}, ...]：species_id 還是
    NULL、且找得到截圖的樹，一棵樹只回傳一筆代表截圖（優先取有 Final_Dist_cm
    的代表紀錄，跟 tree_coordinate.py 用同一筆，沒有才退回任一筆有截圖的紀錄）。
    """
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
    """把辨識出的樹種寫回 Trees.species_id。"""
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
    """回傳 [{'record_id', 'pixel_width', 'mask_width', 'distance_cm',
    'focal_mm', 'sensor_width_mm'}, ...]：dbh 還是 0、且換算欄位齊全的
    代表紀錄；pixel_width 讀整群 IQR 平均後的 Final_Pixel_Width，非單一秒讀值。"""
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
    """把換算出的樹徑寫回 Measurements.dbh。"""
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
    """回傳 [{'record_id', 'dbh', 'allo_param_a', 'allo_param_b',
    'carbon_fraction'}, ...]：carbon_absorpation 還是 0、且已經有 dbh 與
    樹種固碳係數可用的代表紀錄。"""
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
    """把算出的生質量、固碳量寫回 Measurements。"""
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
    """寫入時間對齊後的資料（含影片截圖）到 dbo.Measurements。Tree_ID 先留
    NULL（避免整批共用同一個假 ID），dbh／biomass／carbon_absorpation 先
    寫 0，皆等後續座標／樹徑／固碳步驟依 record_id 回填；status 固定 'Pending'。
    """
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
                'gnss_gap_ms, video_offset_ms, site_name, image_data, '
                'track_id, pixel_width, mask_width, focal_mm, sensor_width_mm'
                ') VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                None, 0, 0, 0, 'Pending',
                recorded_at.strftime('%Y/%m/%d'), recorded_at.strftime('%H:%M:%S'),
                r['latitude'], r['longitude'], r['rtk_speed_mps'], r['rtk_heading_deg'],
                r['rtk_tag'], r['rtk_height_m'],
                r['laser_status'], r['led_status'],
                int(r['tof_dist1_cm']), int(r['tof_dist2_cm']),
                r['gnss_gap_ms'], r['video_offset_ms'], site_name, r.get('image_data'),
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


# ── 時間對齊管線寫入（Arduino/RTK 對齊後的原始感測器資料，舊版暫存表，目前未使用）──
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
            '''
            INSERT INTO Sensor_Sync_Records (
                merge_batch_id, arduino_tree_id, recorded_at,
                latitude, longitude, rtk_height_m, rtk_speed_mps, rtk_heading_deg, rtk_tag,
                laser_status, led_status, tof_dist1_cm, tof_dist2_cm,
                gnss_gap_ms, video_offset_ms, video_filename
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                (
                    r['merge_batch_id'], r['arduino_tree_id'], r['recorded_at'],
                    r['latitude'], r['longitude'], r['rtk_height_m'], r['rtk_speed_mps'],
                    r['rtk_heading_deg'], r['rtk_tag'],
                    r['laser_status'], r['led_status'], r['tof_dist1_cm'], r['tof_dist2_cm'],
                    r['gnss_gap_ms'], r['video_offset_ms'], r['video_filename'],
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


# 把 '25.0883747N' 這種字串轉成帶正負號的十進位度數，S/W 為負
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


# ── 後台管理：樹木清單（僅 Pending）──
# 加上 t.tracker_id = m.track_id，排除座標推算失敗、仍卡在上傳當下佔位
# Tree_ID 的孤兒紀錄，避免管理員誤核准到不相干的座標
def get_all_trees_admin():
    """後台用：回傳待審核清單。"""
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                v.紀錄編號     AS id,
                v.Tree_ID      AS tree_id,
                v.樹木種類     AS species,
                v.樹徑cm       AS dbh,
                v.固碳量       AS carbon,
                v.巡檢案場     AS site,
                v.緯度         AS lat_raw,
                v.經度         AS lng_raw,
                v.樹木照片二進位 AS image_bin,
                m.[DATE]       AS measure_date,
                m.[TIME]       AS measure_time
            FROM v_AdminPendingQueue v
            JOIN Measurements m ON m.record_id = v.紀錄編號
            JOIN Trees t ON t.Tree_ID = m.Tree_ID
            WHERE m.Final_Dist_cm IS NOT NULL
              AND m.track_id IS NOT NULL
              AND t.tracker_id = m.track_id
        ''')
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        trees = []
        for row in rows:
            recorded_at = ' '.join(
                part for part in (row['measure_date'], row['measure_time']) if part
            )
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
                'recorded_at': recorded_at or None,
                'img': _img_bin_to_data_uri(row['image_bin']),
            })
        return trees
    except Exception as e:
        print(f'get_all_trees_admin 查詢失敗: {e}')
        return []
    finally:
        conn.close()


# 固碳量一定要用「樹徑 × 樹種係數」重新算出，不接受前端直接傳入；species
# 影響 Trees（同 Tree_ID 全部生效），dbh 只影響 Measurements 這一筆
def admin_update_measurement(record_id: int, new_status: str, dbh=None, species=None):
    """後台：更新 Measurements 審核狀態，可一併更新樹徑／樹種，並重新計算
    固碳量。回傳 (success, error_message)；success 為 False 時 error_message
    說明找不到紀錄或缺哪些資料無法核准。"""
    conn = get_db_connection()
    if conn is None:
        return False, '資料庫連線失敗'
    try:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT m.Tree_ID, m.dbh, m.image_data, m.track_id,
                   t.tracker_id, t.[LATITUDE N/S], t.[LONGITUDE E/W]
            FROM Measurements m
            LEFT JOIN Trees t ON t.Tree_ID = m.Tree_ID
            WHERE m.record_id = ?
        ''', record_id)
        row = cursor.fetchone()
        if row is None:
            return False, '查無此筆資料'
        (current_tree_id, current_dbh, image_data, m_track_id,
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
            # 核准前檢查照片／樹徑／座標／Tree_ID 對應關係是否齊全，缺件就
            # 擋下、回傳原因，不寫入 status（已送出的 dbh／species 仍保留）
            missing = []
            if not image_data:
                missing.append('照片')
            if current_dbh is None or current_dbh <= 0:
                missing.append('樹徑')
            if lat_raw is None or lng_raw is None:
                missing.append('座標')
            if m_track_id is None or t_tracker_id != m_track_id:
                missing.append('Tree_ID 對應關係尚未確認')
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


# 刪除時連同這個 Tree_ID 底下所有 Measurements 紀錄、以及 Trees 那一筆本身
# 一起刪（同一棵樹每一秒的原始紀錄都指到同一個 Tree_ID，只刪代表列會留下
# 刪不掉的孤兒資料）。Tree_ID 還是 NULL（尚未分析出正式 Tree_ID）時，退回只刪這一筆
def delete_tree(record_id: int) -> bool:
    """後台：刪除指定紀錄所屬 Tree_ID 底下所有資料。回傳 True 表示刪除
    成功（有找到該筆）。"""
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


# ── 後台管理：使用者帳號 ──
def get_user_by_username(username: str):
    """登入驗證用：查詢帳號，回傳 dict（含 admin_id, username, password_hash）或 None。"""
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
    """初始化工具用：新增管理員帳號（由 scripts/create_admin.py 呼叫）。"""
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


# ── CLI 工具寫入（供 Tree-Trunk-Segmentation/main.py 的桌面版呼叫）──
def insert_record_with_location(species, dbh, carbon, lat, lon, thumbnail_data=None):
    """CLI 桌面工具用：儲存含 GPS 座標的辨識紀錄。尚未實作。"""
    raise NotImplementedError('此函式尚未實作')
