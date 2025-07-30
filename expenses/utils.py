from __future__ import annotations

import uuid
from pathlib import Path
from functools import wraps
from typing import Final

from flask import abort, current_app
from flask_login import current_user
from werkzeug.datastructures import FileStorage

# ──────────────────────────────────────────────
# Pillow / HEIC 対応
# ──────────────────────────────────────────────
from PIL import Image, ImageOps, UnidentifiedImageError

# pillow-heif が無い環境でもアプリが落ちないように
try:
    from pillow_heif import register_heif_opener  # pip install pillow-heif
    register_heif_opener()  # HEIC/HEIF を Pillow で読めるように
    _heif_enabled = True
except Exception:
    _heif_enabled = False

# 送信許可拡張子（routesでもチェックしているが念のため）
ALLOWED_SEND_EXTS: Final = {".jpg", ".jpeg", ".png", ".heic", ".heif"}


# ──────────────────────────────────────────────
# アップロード画像を保存し、ファイル名を返す
#   - HEIC/HEIF は PNG へ変換
#   - それ以外は元の拡張子で保存
#   - EXIF回転を補正
# ──────────────────────────────────────────────
def save_upload(file: FileStorage) -> str:
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_SEND_EXTS:
        raise ValueError(f"拡張子 {ext} は許可されていません")

    # HEIC/HEIF → PNG へ統一（LINE表示の安定化目的）
    to_png = ext in {".heic", ".heif"} and _heif_enabled

    try:
        # FileStorage では file.stream を渡すのが安全
        with Image.open(file.stream) as im:
            # スマホの向き情報を反映してからRGB化
            im = ImageOps.exif_transpose(im).convert("RGB")

            if to_png:
                fname = f"{uuid.uuid4().hex}.png"
                im.save(upload_dir / fname, format="PNG", optimize=True)
            else:
                # 元拡張子のまま保存（JPEG/PNG）
                fname = f"{uuid.uuid4().hex}{ext}"
                im.save(upload_dir / fname)
    except UnidentifiedImageError:
        # 画像として開けない場合はそのまま保存（最後の手段）
        # ※ 表示できない可能性があるためログを残すことを推奨
        if to_png:
            fname = f"{uuid.uuid4().hex}.png"
        else:
            fname = f"{uuid.uuid4().hex}{ext}"
        # 先にストリームを先頭に戻してから保存
        try:
            file.stream.seek(0)
        except Exception:
            pass
        file.save(upload_dir / fname)

    return fname


# ──────────────────────────────────────────────
# 管理者チェック用デコレータ
# ──────────────────────────────────────────────
def admin_required(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or getattr(current_user, "role", None) != "admin":
            abort(403)
        return func(*args, **kwargs)
    return wrapped
