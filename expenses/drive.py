"""drive.py  – Google Drive 連携 + 画像変換ユーティリティ
------------------------------------------------------------
* iPhone の HEIC / HEIF を自動で PNG に変換してアップロード
* INFO ログで処理の流れを追跡できる
"""

from __future__ import annotations

import io
import logging
import mimetypes
import sys
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Tuple

import googleapiclient.discovery  # type: ignore
from googleapiclient.http import MediaIoBaseUpload  # type: ignore
from pillow_heif import register_heif_opener  # pip install pillow-heif
from PIL import Image, UnidentifiedImageError

# -------------------------- ロギング設定 -----------------------------------
logger = logging.getLogger(__name__)
if not logger.handlers:                          # 重複登録を防ぐ
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(h)
logger.setLevel(logging.INFO)
logger.info("drive.py is imported")

# ------------------------ 画像関連ユーティリティ ---------------------------
register_heif_opener()  # HEIF/HEIC を Pillow が読めるように

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".heif", ".heic"}


def _convert_to_png(src: BinaryIO, original_name: str) -> Tuple[io.BytesIO, str]:
    """HEIC などを PNG へ変換して (BytesIO, 新ファイル名) を返す"""
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            buf = io.BytesIO()
            im.save(buf, format="PNG", optimize=True)
            buf.seek(0)
            new_name = f"{Path(original_name).stem}.png"
            logger.info("Converted %s → %s (%d bytes)", original_name, new_name, buf.getbuffer().nbytes)
            return buf, new_name
    except UnidentifiedImageError:
        logger.exception("Could not open image %s", original_name)
        raise


# ------------------------ Google Drive 連携 ---------------------------------
_SERVICE_CACHE: dict[str, "googleapiclient.discovery.Resource"] = {}


def _get_service(credentials_path: str) -> "googleapiclient.discovery.Resource":
    if credentials_path not in _SERVICE_CACHE:
        from google.oauth2 import service_account  # type: ignore

        scopes = ["https://www.googleapis.com/auth/drive.file"]
        creds = service_account.Credentials.from_service_account_file(credentials_path, scopes=scopes)
        _SERVICE_CACHE[credentials_path] = googleapiclient.discovery.build("drive", "v3", credentials=creds)
    return _SERVICE_CACHE[credentials_path]


# ---------------------------------------------------------------------------
#  PUBLIC API
# ---------------------------------------------------------------------------

def drive_upload(
    local_path: Path,
    filename: str,
    *,
    folder_id: str,
    credentials_path: str,
) -> str:
    """
    `local_path` のファイルを Google Drive にアップロードし共有リンクを返す。
    HEIC/HEIF は自動で PNG へ変換してから送る。

    Parameters
    ----------
    local_path : Path          変換前後どちらでも良いローカルファイル
    filename   : str           Drive 上でのファイル名（変換される場合は上書き）
    folder_id  : str           アップロード先フォルダ ID
    credentials_path : str     サービスアカウント JSON のパス
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise ValueError(f"Unsupported extension: {ext}")

    # ---------- 変換が必要なら PNG に ----------
    fileobj: BinaryIO
    if ext in {".heif", ".heic"}:
        with local_path.open("rb") as raw:
            fileobj, filename = _convert_to_png(raw, filename)
    else:
        fileobj = local_path.open("rb")

    # ---------- MIME Type 推定 ----------
    mime_type, _ = mimetypes.guess_type(filename)
    mime_type = mime_type or "application/octet-stream"

    media = MediaIoBaseUpload(fileobj, mimetype=mime_type, resumable=False)

    # ---------- Drive へアップロード ----------
    service = _get_service(credentials_path)
    meta = {
        "name": filename,
        "parents": [folder_id],
        "description": f"uploaded {datetime.now():%Y-%m-%d %H:%M:%S}",
    }
    uploaded = (
        service.files()
        .create(body=meta, media_body=media, fields="id, webViewLink")
        .execute()
    )

    # anyone with the link → reader
    service.permissions().create(fileId=uploaded["id"], body={"type": "anyone", "role": "reader"}).execute()

    link: str = uploaded["webViewLink"]
    logger.info("Uploaded %s (id=%s) → %s", filename, uploaded["id"], link)
    return link
