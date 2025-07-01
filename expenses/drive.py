"""
Google Drive へ領収書をアップロードし、
『誰でも閲覧可の直接表示 URL』(uc?export=view…) を返すユーティリティ
    * HEIC / HEIF / HIF / AVIF は必ず JPEG へ変換
    * 他の画像も JPEG に統一
"""
from __future__ import annotations

import io, os, mimetypes
from pathlib import Path
from typing import Tuple, Union

from googleapiclient.discovery import build
from googleapiclient.http      import MediaFileUpload
from google.oauth2             import service_account

from PIL import Image, UnidentifiedImageError
import pyheif


DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_ID", "xxxxxxxxxxxxxxxxxxxx")


# ──────────────────────────────────────────
def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


# ──────────────────────────────────────────
# HEIF 判定 & 変換（拡張子無視で “中身” を読む）
# ──────────────────────────────────────────
def _heif_to_jpg(src: Union[str, Path]) -> Tuple[str, str] | None:
    src = Path(src)
    try:
        data = pyheif.read(src)               # ← HEIF でなければ ValueError
    except Exception:
        return None                           # HEIF ではない
    img = Image.frombytes(
        data.mode, data.size, data.data, "raw", data.mode, data.stride
    )
    dst = src.with_suffix(".jpg")
    img.save(dst, "JPEG", quality=90)
    return str(dst), dst.name


# ──────────────────────────────────────────
# Pillow で開ける画像は必ず JPEG にそろえる
# ──────────────────────────────────────────
def _ensure_jpeg(src: Union[str, Path]) -> Tuple[str, str]:
    src = Path(src)
    try:
        with Image.open(src) as im:
            if im.format != "JPEG":
                dst = src.with_suffix(".jpg")
                im.convert("RGB").save(dst, "JPEG", quality=90)
                return str(dst), dst.name
    except UnidentifiedImageError:
        pass   # 画像でなければそのまま
    return str(src), src.name


# ──────────────────────────────────────────
# メイン
# ──────────────────────────────────────────
def drive_upload(local_path: Union[str, Path], filename: str | None = None) -> str:
    local_path = Path(local_path)
    if filename is None:
        filename = local_path.name

    # ① まず **中身が HEIF なら必ず変換**（拡張子は無視）
    heif_conv = _heif_to_jpg(local_path)
    if heif_conv:
        local_path_str, filename = heif_conv
    else:
        # ② それ以外も JPEG にそろえる
        local_path_str, filename = _ensure_jpeg(local_path)

    # ③ Drive へアップロード
    service = get_drive_service()
    meta  = {"name": filename, "parents": [DRIVE_FOLDER_ID]}
    mime  = mimetypes.guess_type(local_path_str)[0] or "application/octet-stream"
    media = MediaFileUpload(local_path_str, mimetype=mime, resumable=True)

    file_id = (
        service.files()
        .create(body=meta, media_body=media, fields="id")
        .execute()
    )["id"]

    # ④ 公開リンク付与
    service.permissions().create(
        fileId=file_id, body={"role": "reader", "type": "anyone"}
    ).execute()

    return f"https://drive.google.com/uc?export=view&id={file_id}"
