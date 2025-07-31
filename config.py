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

    # .env に指定があればそれを優先（なければデフォルトに heic/heif/webp を含める）
    _raw_ext = os.getenv("ALLOWED_EXTENSIONS", "png,jpg,jpeg,pdf,heic,heif,webp")
    ALLOWED_EXTENSIONS = {
        x.strip().lower() for x in _raw_ext.split(",") if x.strip()
    }

    # リクエスト全体の上限（バイト）。環境変数が無ければ 50MB を既定にする
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))