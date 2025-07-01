<<<<<<< HEAD
=======
"""
Google Drive へ領収書をアップロードし、一覧ページ用に
「誰でも閲覧可の“直接表示 URL”」(uc?export=view…) を返すユーティリティ
"""

>>>>>>> 81b6db0 (feat: always convert images to JPEG before Drive upload)
from __future__ import annotations
import os, mimetypes
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http      import MediaFileUpload
from google.oauth2             import service_account
<<<<<<< HEAD
from PIL import Image
import pyheif

DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_ID", "xxxxxxxxxxxxxxxxxxxx")

=======
from PIL import Image, UnidentifiedImageError          # Pillow
import pyheif                                               # HEIC

# Drive フォルダ ID（.env で上書き可）
DRIVE_FOLDER_ID: str = os.getenv("GOOGLE_DRIVE_PARENT_ID", "xxxxxxxxxxxxxxxxxxxx")

# ─────────────────────────────
# Google Drive service
# ─────────────────────────────
>>>>>>> 81b6db0 (feat: always convert images to JPEG before Drive upload)
def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)

<<<<<<< HEAD
=======
# ─────────────────────────────
# HEIC → JPEG
# ─────────────────────────────
>>>>>>> 81b6db0 (feat: always convert images to JPEG before Drive upload)
def _convert_heic_to_jpg(src_path: str) -> tuple[str, str]:
    heif = pyheif.read(src_path)
    img  = Image.frombytes(heif.mode, heif.size, heif.data,
                           "raw", heif.mode, heif.stride)
    dst  = Path(src_path).with_suffix(".jpg")
    img.save(dst, "JPEG", quality=90)
    return str(dst), dst.name

<<<<<<< HEAD
def drive_upload(local_path: str, filename: str) -> str:
    if local_path.lower().endswith(".heic"):
        local_path, filename = _convert_heic_to_jpg(local_path)

=======
# ─────────────────────────────
# どんな画像でも JPEG に揃える
# ─────────────────────────────
def _ensure_jpeg(src_path: str) -> tuple[str, str]:
    """
    Pillow で開ける画像は必ず JPEG へ再保存して
    (新パス, 新ファイル名) を返す。
    JPEG だった／画像でなかった場合はそのまま。
    """
    try:
        with Image.open(src_path) as im:
            if im.format != "JPEG":
                dst = Path(src_path).with_suffix(".jpg")
                im.convert("RGB").save(dst, "JPEG", quality=90)
                return str(dst), dst.name
    except UnidentifiedImageError:
        pass
    return src_path, Path(src_path).name

# ─────────────────────────────
# メイン
# ─────────────────────────────
def drive_upload(local_path: str, filename: str) -> str:
    # 1) HEIC を先に変換
    if str(local_path).lower().endswith(".heic"):
        local_path, filename = _convert_heic_to_jpg(local_path)

    # 2) それ以外の画像も必ず JPEG 化
    local_path, filename = _ensure_jpeg(local_path)

>>>>>>> 81b6db0 (feat: always convert images to JPEG before Drive upload)
    service = get_drive_service()
    meta  = {"name": filename, "parents": [DRIVE_FOLDER_ID]}
    mime  = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    media = MediaFileUpload(local_path, mimetype=mime, resumable=True)

    res = service.files().create(body=meta, media_body=media, fields="id").execute()
    file_id = res["id"]

<<<<<<< HEAD
=======
    # “リンクを知る全員” 閲覧可
>>>>>>> 81b6db0 (feat: always convert images to JPEG before Drive upload)
    service.permissions().create(
        fileId=file_id, body={"role": "reader", "type": "anyone"}
    ).execute()

<<<<<<< HEAD
=======
    # 直接表示 URL
>>>>>>> 81b6db0 (feat: always convert images to JPEG before Drive upload)
    return f"https://drive.google.com/uc?export=view&id={file_id}"
