# ── 陳信睿 8/7修改 ────────────────────────────────────────
import os

DB_SERVER     = os.environ.get('DB_SERVER', '')
DB_NAME       = os.environ.get('DB_NAME', 'tree_db')
DB_USER       = os.environ.get('DB_USER', '')
DB_PASSWORD   = os.environ.get('DB_PASSWORD', '')
DB_ENCRYPT    = os.environ.get('DB_ENCRYPT', 'yes')
DB_TRUST_CERT = os.environ.get('DB_TRUST_CERT', 'no')

MODEL_PATH = os.environ.get('MODEL_PATH', 'Tree-Trunk-Segmentation/best.pt')

SECRET_KEY = os.environ.get('SECRET_KEY', '')

# ── 樹幹追蹤（services/analysis/tracker.py）──────────────────────
CONF_THRESHOLD = float(os.environ.get('CONF_THRESHOLD', '0.4'))
TRACKER_YAML   = os.environ.get('TRACKER_YAML', 'services/analysis/bytetrack_custom.yaml')
MIN_HITS       = int(os.environ.get('MIN_HITS', '3'))
IMGSZ          = int(os.environ.get('IMGSZ', '640'))
IOU            = float(os.environ.get('IOU', '0.7'))

UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
