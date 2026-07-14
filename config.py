import os

# ── 資料庫（Azure SQL） ────────────────────────────────────────
DB_SERVER     = os.environ.get('DB_SERVER', '')
DB_NAME       = os.environ.get('DB_NAME', 'tree_db')
DB_USER       = os.environ.get('DB_USER', '')
DB_PASSWORD   = os.environ.get('DB_PASSWORD', '')
DB_ENCRYPT    = os.environ.get('DB_ENCRYPT', 'yes')
DB_TRUST_CERT = os.environ.get('DB_TRUST_CERT', 'no')

# ── YOLO 模型路徑 ───────────────────────────────────────────────
MODEL_PATH = os.environ.get('MODEL_PATH', 'Tree-Trunk-Segmentation/best.pt')

# ── Flask session 密鑰 ──────────────────────────────────────────
# 使用 secrets.token_hex(32) 產生隨機值填入 .env
SECRET_KEY = os.environ.get('SECRET_KEY', '')
