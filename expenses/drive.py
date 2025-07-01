"""Google Drive へ領収書をアップロードし、
誰でも閲覧可の “直接表示 URL” (uc?export=view…) を返すユーティリティ"""

from __future__ import annotations
import os, mimetypes
from pathlib import Path, PurePath
from typing import Tuple, Union

from googleapiclient.discovery import build
from googleapiclient.http      import MediaFileUpload
from google.oauth2             import service_account

from PIL import Image, UnidentifiedImageError        # pillow
import pyheif                                         # HEIC

DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_ID", "xxxxxxxxxxxxxxxxxxxx")

# ───────────── Google Drive service ─────────────
def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)

# ───────────── HEIC → JPEG ─────────────
def _convert_heic_to_jpg(src: Union[str, Path]) -> Tuple[str, str]:
    src = Path(src)
    heif = pyheif.read(src)
    img  = Image.frombytes(heif.mode, heif.size, heif.data,
                           "raw", heif.mode, heif.stride)
    dst  = src.with_suffix(".jpg")
    img.save(dst, "JPEG", quality=90)
    return str(dst), dst.name

# ───────────── 任意画像を JPEG に統一 ─────────────
def _ensure_jpeg(src: Union[str, Path]) -> Tuple[str, str]:
    src = Path(src)
    try:
        with Image.open(src) as im:
            if im.format != "JPEG":
                dst = src.with_suffix(".jpg")
                im.convert("RGB").save(dst, "JPEG", quality=90)
                return str(dst), dst.name
    except UnidentifiedImageError:
        pass
    return str(src), src.name

# ───────────── メイン ─────────────
def drive_upload(local_path: Union[str, Path], filename: str | None = None) -> str:
    local_path = Path(local_path)
    if filename is None:
        filename = local_path.name

    # 1) HEIC / HEIF → JPEG   ← ★ここを修正
    if local_path.suffix.lower() in (".heic", ".heif"):
        local_path, filename = _convert_heic_to_jpg(local_path)
    else:
        # 2) そのほか画像も JPEG 化
        local_path, filename = _ensure_jpeg(local_path)

    service = get_drive_service()
    meta  = {"name": filename, "parents": [DRIVE_FOLDER_ID]}
    mime  = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    media = MediaFileUpload(local_path, mimetype=mime, resumable=True)

    file_id = (
        service.files()
               .create(body=meta, media_body=media, fields="id")
               .execute()
               ["id"]
    )

    # 公開権限
    service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
    ).execute()

    return f"https://drive.google.com/uc?export=view&id={file_id}"
