"""
Google Drive へ領収書をアップロードし、
「誰でも閲覧可の直接表示 URL (uc?export=view…)」を返すユーティリティ
"""

from __future__ import annotations
import os, mimetypes
from pathlib import Path
from typing import Tuple, Union

from googleapiclient.discovery import build
from googleapiclient.http      import MediaFileUpload
from google.oauth2             import service_account

from PIL import Image, UnidentifiedImageError    # pillow
import pyheif                                    # HEIF/HEIC/HIF…

# Drive フォルダ ID（.env で上書き可）
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_ID", "xxxxxxxxxxxxxxxxxxxx")

# ─────────────────────────────
# Drive API service
# ─────────────────────────────
def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)

# ─────────────────────────────
# HEIF → JPEG 変換
# ─────────────────────────────
def _convert_heif_to_jpg(src_path: Union[str, Path]) -> Tuple[str, str]:
    src_path = Path(src_path)
    heif     = pyheif.read(src_path)
    img      = Image.frombytes(
        heif.mode, heif.size, heif.data,
        "raw", heif.mode, heif.stride,
    )
    dst_path = src_path.with_suffix(".jpg")
    img.save(dst_path, "JPEG", quality=90)
    return str(dst_path), dst_path.name

# ─────────────────────────────
# 任意画像を JPEG に統一
# ─────────────────────────────
def _ensure_jpeg(src_path: Union[str, Path]) -> Tuple[str, str]:
    """
    Pillow で開ける画像は必ず JPEG に再保存して
    (新パス, 新ファイル名) を返す。JPEG ならスルー。
    画像でなければそのまま返す。
    """
    src_path = Path(src_path)
    try:
        with Image.open(src_path) as im:
            if im.format != "JPEG":
                dst = src_path.with_suffix(".jpg")
                im.convert("RGB").save(dst, "JPEG", quality=90)
                return str(dst), dst.name
    except UnidentifiedImageError:
        pass
    return str(src_path), src_path.name

# ─────────────────────────────
# メイン関数
# ─────────────────────────────
def drive_upload(local_path: Union[str, Path], filename: str | None = None) -> str:
    """
    * HEIF/HEIC/HIF… なら JPEG へ変換
    * それ以外の画像も JPEG に統一
    * Drive へアップロード＋“誰でも閲覧可”権限を付与
    * uc?export=view&id=... 形式の URL を返す
    """
    local_path = Path(local_path)
    if filename is None:
        filename = local_path.name

    # 1) HEIF 判定：pyheif.read が成功するかで判断（拡張子依存なし）
    try:
        pyheif.read(local_path)
        local_path_str, filename = _convert_heif_to_jpg(local_path)
    except (pyheif.error.HeifError, FileNotFoundError):
        # HEIF でなければ通常の JPEG 統一
        local_path_str, filename = _ensure_jpeg(local_path)

    # 2) Google Drive へアップロード
    service = get_drive_service()
    meta  = {"name": filename, "parents": [DRIVE_FOLDER_ID]}
    mime  = mimetypes.guess_type(local_path_str)[0] or "application/octet-stream"
    media = MediaFileUpload(local_path_str, mimetype=mime, resumable=True)

    file = (
        service.files()
        .create(body=meta, media_body=media, fields="id")
        .execute()
    )
    file_id = file["id"]

    # 3) 公開権限を付与
    service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
    ).execute()

    # 4) 直接表示 URL を返す
    return f"https://drive.google.com/uc?export=view&id={file_id}"
