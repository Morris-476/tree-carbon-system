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

# ── 樹種辨識（services/species_classifier.py）─────────────────────
# 負責人：Morris
# 開發日期：2026/09/12
SPECIES_VECTORS_PATH = os.environ.get('SPECIES_VECTORS_PATH', 'Tree-Species-Vectors/tree_vectors.pkl')
CLIP_MODEL_NAME = os.environ.get('CLIP_MODEL_NAME', 'ViT-B/32')
# YOLO 去背時的信心度門檻，跟訓練樹種向量時使用的門檻一致（不可跟 CONF_THRESHOLD 混用，
# 那是追蹤流程專用的）
SPECIES_SEGMENT_CONF = float(os.environ.get('SPECIES_SEGMENT_CONF', '0.3'))
# 判定樹種的最低信心度（cosine similarity），低於此門檻視為無法判定，species_id 留空
SPECIES_CONFIDENCE_THRESHOLD = float(os.environ.get('SPECIES_CONFIDENCE_THRESHOLD', '0.6'))
