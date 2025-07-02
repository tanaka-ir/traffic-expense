"""
Google Drive へ領収書をアップロードし、
誰でも閲覧可の “直接表示 URL” (uc?export=view…) を返すユーティリティ
"""

from __future__ import annotations
import os, mimetypes
from pathlib import Path
from typing import Tuple, Union

from googleapiclient.discovery import build
from googleapiclient.http      import MediaFileUpload
from google.oauth2             import service_account

from PIL import Image, UnidentifiedImageError        # Pillow
import pyheif                                         # HEIC/HEIF

import logging                         #後からこの下の4行は消す

logger = logging.getLogger(__name__)   # ← 自分専用のロガーを取得
logger.setLevel(logging.INFO)          # INFO 以上を出力

logger.info("drive.py is imported")    # ← モジュール読み込み時に 1 回だけ出る


DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_ID", "xxxxxxxxxxxxxxxxxxxx")

# ─────────────────────────────
# Google Drive service
# ─────────────────────────────
def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)

# ─────────────────────────────
# Pillow で開ける画像 → JPEG に統一
# ─────────────────────────────
def _ensure_jpeg(src: Union[str, Path]) -> Tuple[str, str]:
    p = Path(src)
    try:
        with Image.open(p) as im:
            if im.format != "JPEG":
                dst = p.with_suffix(".jpg")
                im.convert("RGB").save(dst, "JPEG", quality=90)
                return str(dst), dst.name
    except UnidentifiedImageError:
        # Pillow で開けない（= 画像じゃない or HEIF など）
        pass
    return str(p), p.name

# ─────────────────────────────
# 拡張子を無視して「中身が HEIF」なら JPEG へ
# ─────────────────────────────
def _maybe_convert_heif(src: Union[str, Path]) -> Tuple[str, str]:
    p = Path(src)
    try:
        heif = pyheif.read(p)
    except ValueError:
        # HEIF ではなかった
        return str(p), p.name

    img = Image.frombytes(
        heif.mode, heif.size, heif.data, "raw", heif.mode, heif.stride
    )
    dst = p.with_suffix(".jpg")
    img.save(dst, "JPEG", quality=90)
    return str(dst), dst.name

# ─────────────────────────────
# メイン
# ─────────────────────────────
def drive_upload(local_path: Union[str, Path], filename: str | None = None) -> str:
    """
    * まず Pillow で開けるなら JPEG へ
    * 開けなかった場合でも HEIF なら JPEG へ
    * Google Drive へアップロードして uc?export=view URL を返す
    """
    local_path_str, filename = _ensure_jpeg(local_path)
    local_path_str, filename = _maybe_convert_heif(local_path_str)

    service = get_drive_service()
    meta  = {"name": filename, "parents": [DRIVE_FOLDER_ID]}
    mime  = mimetypes.guess_type(local_path_str)[0] or "application/octet-stream"
    media = MediaFileUpload(local_path_str, mimetype="image/jpeg", resumable=True)

    file = (
        service.files()
        .create(body=meta, media_body=media, fields="id")
        .execute()
    )
    file_id = file["id"]

    service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
    ).execute()

    return f"https://drive.google.com/uc?export=view&id={file_id}"
