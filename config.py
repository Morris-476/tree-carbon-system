# 陳信睿 10/25修改
# config.py
import os
import pyodbc
from dotenv import load_dotenv

# 🎯 載入 .env 環境變數
load_dotenv()

# =====================================================================
# 1. 自動偵測本機已安裝的 SQL Server ODBC 驅動程式
# =====================================================================
available_drivers = pyodbc.drivers()
preferred_drivers = [
    'ODBC Driver 18 for SQL Server',
    'ODBC Driver 17 for SQL Server',
    'ODBC Driver 13 for SQL Server',
    'SQL Server'
]
# 自動挑選電腦裡最新的可用驅動程式
chosen_driver = next((d for d in preferred_drivers if d in available_drivers), 'SQL Server')

# =====================================================================
# 2. Azure SQL 資料庫設定
# =====================================================================
DB_SERVER     = os.environ.get('DB_SERVER', 'tree-server-tku.database.windows.net')
DB_NAME       = os.environ.get('DB_NAME', 'tree_db')
DB_USER       = os.environ.get('DB_USER', 'sa_admin')
DB_PASSWORD   = os.environ.get('DB_PASSWORD', '')
DB_ENCRYPT    = os.environ.get('DB_ENCRYPT', 'yes')
DB_TRUST_CERT = os.environ.get('DB_TRUST_CERT', 'yes')

# 🎯 動態帶入抓到的 driver，解決 IM002 找不到驅動程式的問題
DB_CONNECTION_STRING = os.environ.get(
    'DB_CONNECTION_STRING',
    f"Driver={{{chosen_driver}}};Server=tcp:{DB_SERVER},1433;Database={DB_NAME};Uid={DB_USER};Pwd={DB_PASSWORD};Encrypt={DB_ENCRYPT};TrustServerCertificate={DB_TRUST_CERT};Connection Timeout=30;"
)

# =====================================================================
# 3. Azure Blob Storage 設定
# =====================================================================
AZURE_STORAGE_CONNECTION_STRING = os.environ.get('AZURE_STORAGE_CONNECTION_STRING', '')
AZURE_BLOB_CONTAINER            = os.environ.get('AZURE_BLOB_CONTAINER', 'tree-images')

# =====================================================================
# 4. 其他專案設定
# =====================================================================
MODEL_PATH    = os.environ.get('MODEL_PATH', 'Tree-Trunk-Segmentation/best.pt')
SECRET_KEY    = os.environ.get('SECRET_KEY', 'tree-carbon-secret-key')
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')

# =====================================================================
# 5. 樹幹追蹤（services/analysis/tracker.py）
# 2026/10/29修正：Blob Storage 合併衝突時被整份蓋掉，從合併前的 main
# （commit 61b641b）復原回來，數值沒有變動
# =====================================================================
CONF_THRESHOLD = float(os.environ.get('CONF_THRESHOLD', '0.4'))
TRACKER_YAML   = os.environ.get('TRACKER_YAML', 'services/analysis/bytetrack_custom.yaml')
MIN_HITS       = int(os.environ.get('MIN_HITS', '3'))
IMGSZ          = int(os.environ.get('IMGSZ', '640'))
IOU            = float(os.environ.get('IOU', '0.7'))

# =====================================================================
# 6. 樹種辨識（services/core/species_classifier.py）
# 負責人：Morris，開發日期：2026/09/12（同上，合併時遺失，這裡復原）
# =====================================================================
SPECIES_VECTORS_PATH = os.environ.get('SPECIES_VECTORS_PATH', 'Tree-Species-Vectors/tree_vectors.pkl')
CLIP_MODEL_NAME = os.environ.get('CLIP_MODEL_NAME', 'ViT-B/32')
# YOLO 去背時的信心度門檻，跟訓練樹種向量時使用的門檻一致（不可跟 CONF_THRESHOLD 混用，
# 那是追蹤流程專用的）
SPECIES_SEGMENT_CONF = float(os.environ.get('SPECIES_SEGMENT_CONF', '0.3'))
# 判定樹種的最低信心度（cosine similarity），低於此門檻視為無法辨識，species_id 留空
SPECIES_CONFIDENCE_THRESHOLD = float(os.environ.get('SPECIES_CONFIDENCE_THRESHOLD', '0.6'))
