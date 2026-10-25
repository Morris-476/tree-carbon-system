# 陳信睿 10/25新增
# scripts/migrate_images_to_blob.py
import os
import sys
import io
import pyodbc
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient, ContentSettings

# 🎯 將專案根目錄加入搜尋路徑，確保能成功讀取根目錄的 config.py 與 .env
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import DB_CONNECTION_STRING
load_dotenv()

BLOB_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_BLOB_CONTAINER", "tree-images")

def migrate_database_images():
    print("🔌 連接 Azure Blob Storage...")
    blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)

    print("🔌 連接 Azure SQL Database...")
    conn = pyodbc.connect(DB_CONNECTION_STRING)
    cursor = conn.cursor()

    # 查詢具有二進位圖檔但尚未取得 URL 的紀錄
    cursor.execute("""
        SELECT record_id, tree_id, image_data 
        FROM Measurements 
        WHERE image_data IS NOT NULL AND (image_url IS NULL OR image_url = '')
    """)
    rows = cursor.fetchall()
    print(f"📊 找到 {len(rows)} 筆待遷移的圖片紀錄...")

    success_count = 0
    for row in rows:
        record_id = row[0]
        tree_id = row[1]
        image_bytes = row[2]

        blob_filename = f"tree_{tree_id}_record_{record_id}.jpg"
        blob_client = container_client.get_blob_client(blob_filename)

        print(f"  ⬆️ 正在上傳第 {record_id} 筆至 Blob: {blob_filename}...")
        
        # 上傳至 Blob 並設定 MIME 為 image/jpeg
        blob_client.upload_blob(
            io.BytesIO(image_bytes),
            overwrite=True,
            content_settings=ContentSettings(content_type='image/jpeg')
        )

        image_url = blob_client.url

        # 回寫 URL 至 Measurements 資料表
        cursor.execute("""
            UPDATE Measurements 
            SET image_url = ? 
            WHERE record_id = ?
        """, (image_url, record_id))

        success_count += 1

    conn.commit()
    print(f"🎉 成功遷移 {success_count} 筆照片至 Azure Blob Storage！")

    # 清除舊二進位內容以釋放 SQL 空間
    if success_count > 0:
        cursor.execute("UPDATE Measurements SET image_data = NULL WHERE image_url IS NOT NULL")
        conn.commit()
        print("🧹 已清除 Measurements 中的二進位暫存，釋放 Azure SQL 容量。")

    conn.close()

if __name__ == '__main__':
    migrate_database_images()