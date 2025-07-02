"""
Google Drive へ領収書画像をアップロードし、
「誰でも閲覧可」の “直接表示 URL” (uc?export=view…) を返すユーティリティ
"""

from __future__ import annotations

import os
import mimetypes
from pathlib import Path
from typing import Tuple, Union

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

from PIL import Image, UnidentifiedImageError      # Pillow
import pyheif                                      # HEIC / HEIF

# ─────────────────────────────
# 設定
# ─────────────────────────────
DRIVE_FOLDER_ID: str = os.getenv("GOOGLE_DRIVE_PARENT_ID", "xxxxxxxxxxxxxxxxxxxx")


def get_drive_service():
    """Service Account で Drive API v3 service を取得"""
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    # cache_discovery=False で警告抑制
    return build("drive", "v3", credentials=creds, cache_discovery=False)


# ─────────────────────────────
# 0) 拡張子を無視して「実データが HEIF なら JPEG へ」
# ─────────────────────────────
def _maybe_convert_heif(src_path: Union[str, Path]) -> Tuple[str, str]:
    """
    * src_path が HEIF/HEIC/AVIF 形式なら JPEG へ変換して
      (新パス, 新ファイル名) を返す
    * そうでなければ (元パス, 元ファイル名) のまま返す
    """
    src_path = Path(src_path)
    try:
        heif = pyheif.read(src_path)
    except ValueError:
        # HEIF ではなかった（そのまま）
        return str(src_path), src_path.name

    # ここに来る = HEIF と判定できた
    img = Image.frombytes(
        heif.mode, heif.size, heif.data, "raw", heif.mode, heif.stride
    )
    dst = src_path.with_suffix(".jpg")
    img.save(dst, "JPEG", quality=90)
    return str(dst), dst.name


# ─────────────────────────────
# 1) 通常画像（PNG など）も強制的に JPEG に揃える
# ─────────────────────────────
def _ensure_jpeg(src_path: Union[str, Path]) -> Tuple[str, str]:
    """
    Pillow で開ける画像なら必ず JPEG へ再保存して統一する。
    既に JPEG だった場合や画像でない場合はそのまま。
    """
    src_path = Path(src_path)
    try:
        with Image.open(src_path) as im:
            if im.format != "JPEG":
                dst = src_path.with_suffix(".jpg")
                im.convert("RGB").save(dst, "JPEG", quality=90)
                return str(dst), dst.name
    except UnidentifiedImageError:
        # Pillow が開けない → 画像でない（そのまま）
        pass
    return str(src_path), src_path.name


# ─────────────────────────────
# メイン関数
# ─────────────────────────────
def drive_upload(local_path: Union[str, Path], filename: str | None = None) -> str:
    """
    1. 実データが HEIF なら JPEG へ変換
    2. それ以外でも画像なら JPEG へ統一
    3. Google Drive フォルダへアップロード
    4. “リンクを知る全員” 閲覧可に設定
    5. uc?export=view&id=… 形式の URL を返す
    """
    local_path = Path(local_path)
    if filename is None:
        filename = local_path.name

    # 0) HEIF → JPEG
    local_path_str, filename = _maybe_convert_heif(local_path)

    # 1) PNG など通常画像も JPEG 化
    local_path_str, filename = _ensure_jpeg(local_path_str)

    # 2) Drive へアップロード
    service = get_drive_service()
    meta = {"name": filename, "parents": [DRIVE_FOLDER_ID]}
    mime = mimetypes.guess_type(local_path_str)[0] or "application/octet-stream"
    media = MediaFileUpload(local_path_str, mimetype=mime, resumable=True)

    res = (
        service.files()
        .create(body=meta, media_body=media, fields="id")
        .execute()
    )
    file_id = res["id"]

    # 3) 公開権限を付与
    service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
    ).execute()

    # 4) 直接表示 URL を返す
    return f"https://drive.google.com/uc?export=view&id={file_id}"
