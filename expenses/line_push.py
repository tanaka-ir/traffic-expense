from __future__ import annotations

import os
import logging
from typing import Optional

from flask import current_app
from linebot import LineBotApi
from linebot.models import ImageSendMessage, TextSendMessage

# ─────────────────────────────────────────────
# 環境変数
# ─────────────────────────────────────────────
LINE_TOKEN: Optional[str] = os.getenv("LINE_TOKEN")
DEFAULT_TO: Optional[str] = os.getenv("LINE_TO")  # 送信先（ユーザーID or グループID）

if not LINE_TOKEN:
    raise RuntimeError("環境変数 LINE_TOKEN が未設定です")

bot = LineBotApi(LINE_TOKEN)

# ロガー
logger = logging.getLogger(__name__)
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(h)
logger.setLevel(logging.INFO)


# ─────────────────────────────────────────────
# 内部ユーティリティ
# ─────────────────────────────────────────────
def _resolve_to(to: Optional[str]) -> str:
    """送信先IDを決定（明示指定 > 環境変数）"""
    target = to or DEFAULT_TO
    if not target:
        raise RuntimeError("送信先IDが未指定です。環境変数 LINE_TO か引数 to を設定してください。")
    return target

def _assert_https(url: str) -> None:
    if not url.startswith("https://"):
        # 画像メッセージは HTTPS 必須（HTTP だと失敗/白画像の原因）
        raise ValueError(f"Image URL must be HTTPS: {url}")


# ─────────────────────────────────────────────
# 外部公開API
# ─────────────────────────────────────────────
def push_text(msg: str, *, to: Optional[str] = None) -> None:
    """テキストのみを送信"""
    target = _resolve_to(to)
    bot.push_message(target, TextSendMessage(text=msg))
    logger.info("LINE TEXT -> %s | %s", target, (msg[:60] + "…") if len(msg) > 60 else msg)


def push_image(image_url: str, *, to: Optional[str] = None) -> None:
    """
    画像のみを送信（プレビューも同URL）
    """
    _assert_https(image_url)
    target = _resolve_to(to)
    try:
        bot.push_message(
            target,
            ImageSendMessage(
                original_content_url=image_url,
                preview_image_url=image_url,
            ),
        )
        logger.info("LINE IMAGE -> %s | %s", target, image_url)
    except Exception as e:
        logger.exception("LINE 画像送信失敗: %s", e)
        raise


def push_image_with_note(
    image_url: str,
    user_name: str,
    role: str = "user",         # "admin" / "user"
    note: Optional[str] = None, # 追記事項（区間・金額など）
    *,
    to: Optional[str] = None,
) -> None:
    """
    画像と「誰からか」のテキストを1回の push で送る。
    送信順序は [画像, テキスト]。必要なら並び替えてOK。
    """
    _assert_https(image_url)
    target = _resolve_to(to)

    role_jp = "管理者" if role == "admin" else "ユーザー"
    text = f"{user_name}（{role_jp}）からの申請です。"
    if note:
        text += f"\n{note}"

    messages = [
        ImageSendMessage(
            original_content_url=image_url,
            preview_image_url=image_url,
        ),
        TextSendMessage(text=text),
    ]

    try:
        bot.push_message(target, messages)
        # Flask アプリ側のログにも出す
        logger.info("LINE IMAGE+TEXT -> %s | %s | %s(%s)", target, image_url, user_name, role)
        try:
            current_app.logger.info("LINE PUSH OK -> %s | %s(%s)", image_url, user_name, role)
        except Exception:
            pass
    except Exception as e:
        logger.exception("LINE 画像+テキスト送信失敗: %s", e)
        try:
            current_app.logger.exception("LINE PUSH 失敗: %s", e)
        except Exception:
            pass
        raise
