"""
Google Drive へ領収書イメージをアップロードし、
「誰でも閲覧可の“直接表示 URL” (uc?export=view…)」を返すユーティリティ。

・HEIC/HEIF 画像はサーバー側で JPEG に変換
・拡張子が .jpeg でも中身が HEIF のケースを自動判定
・その他の画像もすべて JPEG に統一
・Drive フォルダ ID と SA 鍵パスは .env で管理
      GOOGLE_DRIVE_PARENT_ID
      GOOGLE_SERVICE_ACCOUNT_JSON
"""

from __future__ import annotations

import os, mimetypes
from pathlib import Path
from typing import Tuple, Union

from googleapiclient.discovery import build
from googleapiclient.http      import MediaFileUpload
from google.oauth2             import service_account

from PIL import Image, UnidentifiedImageError      # Pillow
import pyheif                                       # HEIC / HEIF 判定用

# Drive フォルダ ID（.env で上書き可）
DRIVE_FOLDER_ID: str = os.getenv("GOOGLE_DRIVE_PARENT_ID", "xxxxxxxxxxxxxxxxxxxx")

# ─────────────────────────────
# Drive API service
# ─────────────────────────────
def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    # cache_discovery=False で余計な Warning を抑制
    return build("drive", "v3", credentials=creds, cache_discovery=False)

# ─────────────────────────────
# HEIC → JPEG
# ─────────────────────────────
def _convert_heic_to_jpg(src_path: Union[str, Path]) -> Tuple[str, str]:
    src_path = Path(src_path)
    heif = pyheif.read(src_path)
    img  = Image.frombytes(
        heif.mode, heif.size, heif.data,
        "raw", heif.mode, heif.stride
    )
    dst_path = src_path.with_suffix(".jpg")
    img.save(dst_path, "JPEG", quality=90)
    return str(dst_path), dst_path.name

# ─────────────────────────────
# 任意画像を JPEG に統一
# ─────────────────────────────
def _ensure_jpeg(src_path: Union[str, Path]) -> Tuple[str, str]:
    src_path = Path(src_path)
    try:
        with Image.open(src_path) as im:
            if im.format != "JPEG":
                dst = src_path.with_suffix(".jpg")
                im.convert("RGB").save(dst, "JPEG", quality=90)
                return str(dst), dst.name
    except UnidentifiedImageError:
        # 画像でない or Pillow が開けない場合はそのまま返す
        pass
    return str(src_path), src_path.name

# ─────────────────────────────
# メイン関数
# ─────────────────────────────
def drive_upload(local_path: Union[str, Path], filename: str | None = None) -> str:
    """
    * HEIF/HEIC は先に JPEG へ変換  
    * それ以外の画像も JPEG に統一  
    * Google Drive へアップロード → “リンクを知る全員” 閲覧可  
    * uc?export=view&id=... 形式の直接表示 URL を返す
    """
    local_path = Path(local_path)
    if filename is None:
        filename = local_path.name

    # ――― 1) 拡張子無視で HEIF かどうか試す ―――
    is_heif = False
    try:
        pyheif.read(local_path)      # 読めれば HEIF/HIEF
        is_heif = True
    except Exception:
        pass

    if is_heif:
        local_path_str, filename = _convert_heic_to_jpg(local_path)
    else:
        # ――― 2) 画像はすべて JPEG 化 ―――
        local_path_str, filename = _ensure_jpeg(local_path)

    # ――― 3) Drive へアップロード ―――
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

    # ――― 4) 公開リンク付与 ―――
    service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
    ).execute()

    # ――― 5) 直接表示 URL を返す ―――
    return f"https://drive.google.com/uc?export=view&id={file_id}"
