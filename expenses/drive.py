"""
Google Drive へ領収書をアップロードし、一覧ページ用に
「誰でも閲覧可の“直接表示 URL”」を返すユーティリティ。

• HEIC/HEIF 画像はサーバー側で JPEG に変換してアップロード
• フォルダ ID と SA 鍵は .env の環境変数で管理
      GOOGLE_DRIVE_PARENT_ID
      GOOGLE_SERVICE_ACCOUNT_JSON
"""

from __future__ import annotations

import os
import mimetypes
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http      import MediaFileUpload
from google.oauth2             import service_account

# ──────────────────────────────
# 依存ライブラリ
#   pip install pillow pyheif
# Ubuntu で "libheif-dev" が無い場合は
#   apt install -y libheif-dev
# ──────────────────────────────
from PIL import Image
import pyheif


# Drive フォルダ ID（環境変数があれば優先）
DRIVE_FOLDER_ID: str = os.getenv("GOOGLE_DRIVE_PARENT_ID", "xxxxxxxxxxxxxxxxxxxx")


def get_drive_service():
    """サービスアカウント経由で Drive API v3 の service オブジェクトを返す"""
    cred_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    creds = service_account.Credentials.from_service_account_file(
        cred_path,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    # cache_discovery=False で不要な warning を抑制
    return build("drive", "v3", credentials=creds, cache_discovery=False)


# ──────────────────────────────
# HEIC → JPEG 変換ヘルパ
# ──────────────────────────────
def _convert_heic_to_jpg(src_path: str) -> tuple[str, str]:
    """
    HEIC 画像を JPEG に変換し、(変換後パス, 変換後ファイル名) を返す
    """
    heif = pyheif.read(src_path)
    img = Image.frombytes(
        heif.mode,
        heif.size,
        heif.data,
        "raw",
        heif.mode,
        heif.stride,
    )
    dst_path = Path(src_path).with_suffix(".jpg")
    img.save(dst_path, "JPEG", quality=90)
    return str(dst_path), dst_path.name


# ──────────────────────────────
# メイン関数
# ──────────────────────────────
def drive_upload(local_path: str, filename: str) -> str:
    """
    - 必要なら HEIC を JPEG に変換
    - Drive フォルダへアップロード
    - “リンクを知っている全員” 閲覧可に設定
    - 直接表示用 URL を返す
    """
    # HEIC → JPEG 変換（拡張子判定）
    if local_path.lower().endswith(".heic"):
        local_path, filename = _convert_heic_to_jpg(local_path)

    service = get_drive_service()

    # ① アップロード
    meta  = {"name": filename, "parents": [DRIVE_FOLDER_ID]}
    mime  = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    media = MediaFileUpload(local_path, mimetype=mime, resumable=True)

    file = (
        service.files()
        .create(body=meta, media_body=media, fields="id")
        .execute()
    )
    file_id: str = file["id"]

    # ② 誰でも閲覧可 (公開リンク) を付与
    service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
    ).execute()

    # ③ 直接表示 URL を返す
    return f"https://drive.google.com/uc?export=view&id={file_id}"
