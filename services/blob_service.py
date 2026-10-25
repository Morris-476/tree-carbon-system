# 陳信睿 10/25新增
# services/blob_service.py
import uuid
from azure.storage.blob import BlobServiceClient, ContentSettings
from config import AZURE_STORAGE_CONNECTION_STRING, AZURE_BLOB_CONTAINER

# 初始化 Blob 服務客戶端
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(AZURE_BLOB_CONTAINER)

def upload_tree_image(file_stream, original_filename="", content_type="image/jpeg"):
    """
    將圖片檔案流上傳至 Azure Blob Storage
    :param file_stream: 檔案二進位流 (BytesIO 或 Flask request.files['file'].stream)
    :param original_filename: 原始檔名 (用來保留副檔名)
    :param content_type: 圖片類型 (預設 image/jpeg)
    :return: 圖片的公開存取 URL
    """
    # 擷取副檔名，若無則預設 .jpg
    ext = ".jpg"
    if original_filename and "." in original_filename:
        ext = "." + original_filename.rsplit(".", 1)[1].lower()

    # 使用 UUID 產生不重複的唯一檔名，避免同名覆蓋
    blob_filename = f"tree_{uuid.uuid4().hex[:12]}{ext}"
    blob_client = container_client.get_blob_client(blob_filename)

    # 確保 stream 指標在開頭
    if hasattr(file_stream, 'seek'):
        file_stream.seek(0)

    # 上傳至 Blob 容器
    blob_client.upload_blob(
        file_stream,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type)
    )

    # 回傳圖片的公開 URL
    return blob_client.url