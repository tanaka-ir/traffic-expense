"""drive.py
Google Drive 連携 + 画像変換ユーティリティ
-------------------------------------------
* iPhone の HEIC / HEIF を自動で PNG へ変換してアップロード
* 変換・アップロードの流れを INFO ログで追跡出来るようにした
"""

from __future__ import annotations

import io
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Tuple

import googleapiclient.discovery  # type: ignore
from googleapiclient.http import MediaIoBaseUpload  # type: ignore
from pillow_heif import register_heif_opener  # pip install pillow‑heif
from PIL import Image, UnidentifiedImageError

# ---------------------------------------------------------------------------
# ロギング設定 --------------------------------------------------------------
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

if not logger.handlers:
    # systemd-journal へ流れる stdout にハンドラを付ける
    handler = logging.StreamHandler(sys.stdout)
    fmt = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)

logger.setLevel(logging.INFO)
logger.info("drive.py is imported")

# ---------------------------------------------------------------------------
# 画像関連ユーティリティ ------------------------------------------------------
# ---------------------------------------------------------------------------
register_heif_opener()  # HEIF/HEIC を Pillow が開けるようにする

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".heif", ".heic"}


def _convert_to_png(src: BinaryIO, original_name: str) -> Tuple[io.BytesIO, str]:
    """画像を Pillow で読み取り PNG に再保存して返す

    Returns
    -------
    (png_buffer, new_filename)
    """
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")  # α不要なら"
            buf = io.BytesIO()
            im.save(buf, format="PNG", optimize=True)
            buf.seek(0)
            new_name = f"{Path(original_name).stem}.png"
            logger.info("Converted %s -> %s (size=%dB)", original_name, new_name, buf.getbuffer().nbytes)
            return buf, new_name
    except UnidentifiedImageError as e:
        logger.exception("Image convert failed: %s", e)
        raise


# ---------------------------------------------------------------------------
# Google Drive へのアップロード ---------------------------------------------
# ---------------------------------------------------------------------------

_SERVICE_CACHE: dict[str, "googleapiclient.discovery.Resource"] = {}


def _get_service(credentials_path: str) -> "googleapiclient.discovery.Resource":
    if credentials_path not in _SERVICE_CACHE:
        from google.oauth2 import service_account  # type: ignore

        scopes = ["https://www.googleapis.com/auth/drive.file"]
        creds = service_account.Credentials.from_service_account_file(credentials_path, scopes=scopes)
        _SERVICE_CACHE[credentials_path] = googleapiclient.discovery.build("drive", "v3", credentials=creds)
    return _SERVICE_CACHE[credentials_path]


def drive_upload(fp: BinaryIO, filename: str, *, folder_id: str, credentials_path: str) -> str:
    """ファイルストリームを Google Drive にアップロードし共有リンク URL を返す"""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise ValueError(f"Unsupported extension: {ext}")

    # HEIF/HEIC → PNG に変換 ------------------------------
    if ext in {".heif", ".heic"}:
        fp, filename = _convert_to_png(fp, filename)

    media = MediaIoBaseUpload(fp, mimetype="image/png", resumable=False)

    metadata = {
        "name": filename,
        "parents": [folder_id],
        "description": f"uploaded {datetime.now():%Y-%m-%d %H:%M:%S}"
    }

    service = _get_service(credentials_path)
    file = service.files().create(body=metadata, media_body=media, fields="id, webViewLink").execute()
    file_id = file["id"]

    # 共有リンクを Anyone with the link readable に変更
    service.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"}).execute()
    web_link: str = file["webViewLink"]

    logger.info("Uploaded %s to Drive id=%s", filename, file_id)
    return web_link
