"""
Google Drive に領収書をアップロードし
「誰でも閲覧可の直接表示 URL (uc?export=view…)」を返すユーティリティ
"""

from __future__ import annotations
import os, mimetypes, io
from pathlib import Path
from typing import Tuple, Union

from googleapiclient.discovery import build
from googleapiclient.http      import MediaFileUpload
from google.oauth2             import service_account

from PIL import Image, UnidentifiedImageError         # pillow
import pyheif                                          # HEIF

DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_ID", "xxxxxxxxxxxxxxxxxxxx")

# ----------------------------------------------------------------------
# Google Drive service
# ----------------------------------------------------------------------
def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)

# ----------------------------------------------------------------------
# 画像 → JPEG 統一
# ----------------------------------------------------------------------
def _to_jpeg(src_path: Union[str, Path]) -> Tuple[str, str]:
    """
    * Pillow で開ければ → JPEG 変換
    * 開けなければ pyheif で HEIF/HIEF → JPEG
    * それでも失敗したら元ファイルをそのまま返す
    戻り値: (新ファイルパス, 新ファイル名)
    """
    src_path = Path(src_path)
    # ---- 1) Pillow で開けるならそれだけで十分 -------------------------
    try:
        with Image.open(src_path) as img:
            if img.format != "JPEG":
                dst = src_path.with_suffix(".jpg")
                img.convert("RGB").save(dst, "JPEG", quality=90)
                return str(dst), dst.name
            return str(src_path), src_path.name
    except UnidentifiedImageError:
        pass                                             # → 次の pyheif へ

    # ---- 2) HEIF / HIEF / AVIF の可能性を試す -------------------------
    try:
        heif = pyheif.read(src_path)
        img  = Image.frombytes(
            heif.mode, heif.size, heif.data,
            "raw", heif.mode, heif.stride
        )
        dst = src_path.with_suffix(".jpg")
        img.save(dst, "JPEG", quality=90)
        return str(dst), dst.name
    except (ValueError, OSError):
        # HEIF でもなかった → そのまま返す
        return str(src_path), src_path.name

# ----------------------------------------------------------------------
# メイン関数
# ----------------------------------------------------------------------
def drive_upload(local_path: Union[str, Path], filename: str | None = None) -> str:
    local_path = Path(local_path)
    if filename is None:
        filename = local_path.name

    # 必要なら JPEG へ統一
    local_path_str, filename = _to_jpeg(local_path)

    service = get_drive_service()
    meta  = {"name": filename, "parents": [DRIVE_FOLDER_ID]}
    mime  = mimetypes.guess_type(local_path_str)[0] or "application/octet-stream"
    media = MediaFileUpload(local_path_str, mimetype=mime, resumable=True)

    file_id = (
        service.files()
        .create(body=meta, media_body=media, fields="id")
        .execute()
    )["id"]

    service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
    ).execute()

    return f"https://drive.google.com/uc?export=view&id={file_id}"

