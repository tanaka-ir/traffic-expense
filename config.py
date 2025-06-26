import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = (
        os.getenv("DATABASE_URL")
        or f"sqlite:///{BASE_DIR/'instance'/'traffic_expense.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Google Drive（後で使う）
    GDRIVE_SERVICE_JSON = os.getenv("GDRIVE_SERVICE_JSON")       # instance/service.json など
    GDRIVE_UPLOAD_FOLDER_ID = os.getenv("GDRIVE_UPLOAD_FOLDER_ID")

    # --- 画像アップロード設定 ---
    UPLOAD_FOLDER = Path(os.getenv("UPLOAD_FOLDER", "instance/receipts"))
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}  # 必要に応じて追加
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB/ファイル上限