from __future__ import annotations

import uuid
from pathlib import Path
from functools import wraps
from typing import Final

from flask import abort
from flask_login import current_user
from werkzeug.datastructures import FileStorage

# ──────────────────────────────────────────────
# Pillow / HEIC 対応
# ──────────────────────────────────────────────
from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener   # pip install pillow pillow-heif

register_heif_opener()                         # HEIC/HEIF を Pillow で読めるように

# ──────────────────────────────────────────────
# 保存先フォルダ
# ──────────────────────────────────────────────
UPLOAD_DIR: Final[Path] = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# ──────────────────────────────────────────────
# アップロード画像を保存し、ファイル名を返す
#   - HEIC/HEIF は PNG へ変換
#   - そのほかは元の拡張子で保存
# ──────────────────────────────────────────────
def save_upload(file: FileStorage) -> str:
    ext = Path(file.filename).suffix.lower()
    if ext in {".heic", ".heif"}:
        # 変換して PNG で保存
        try:
            with Image.open(file) as im:
                im = im.convert("RGB")
                fname = f"{uuid.uuid4().hex}.png"
                im.save(UPLOAD_DIR / fname, format="PNG", optimize=True)
                return fname
        except UnidentifiedImageError:
            raise ValueError("画像を読み込めませんでした")
    else:
        # そのまま保存
        fname = f"{uuid.uuid4().hex}{ext}"
        file.save(UPLOAD_DIR / fname)
        return fname


# ──────────────────────────────────────────────
# 管理者チェック用デコレータ
# ──────────────────────────────────────────────
def admin_required(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)
        return func(*args, **kwargs)

    return wrapped
