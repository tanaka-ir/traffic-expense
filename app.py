from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from dotenv import load_dotenv
from config import Config
import os

from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception as e:
    print("pillow-heif registration failed:", e)

db = SQLAlchemy()
migrate = Migrate()

login_manager = LoginManager()
login_manager.login_view = "auth.login"    # 未ログイン時は /login へ

def create_app():
    # ── .env を読み込み ─────────────────────
    load_dotenv()                 # ← ここだけに統一

    app = Flask(__name__, instance_relative_config=True)

    import sys, logging
    h = logging.StreamHandler(sys.stderr)  # Gunicornが拾う出力先
    h.setLevel(logging.INFO)
    app.logger.addHandler(h)
    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False  # 重複出力を防止

    # 1) Config クラスを読み込む
    app.config.from_object(Config)


    # 2) .env の値で上書き（無ければ既存値を保持）
    app.config["MAX_CONTENT_LENGTH"] = int(
        os.getenv("MAX_CONTENT_LENGTH", app.config.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))
    )
    app.logger.info("MAX_CONTENT_LENGTH = %d bytes", app.config["MAX_CONTENT_LENGTH"])

    # ── 拡張を初期化 ────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)      # ← 1 回で OK
    login_manager.init_app(app)

    # instance/ ディレクトリを保証
    os.makedirs(app.instance_path, exist_ok=True)

    # ── Blueprint 登録 ─────────────────────
    from expenses import bp as expenses_bp
    app.register_blueprint(expenses_bp)

    from auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    # ルート
    @app.route("/")
    def index():
        return redirect(url_for("expenses.submit"))

    return app

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, conn_record):
    if isinstance(dbapi_conn, sqlite3.Connection):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()