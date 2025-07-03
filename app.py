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

db = SQLAlchemy()
migrate = Migrate()

login_manager = LoginManager()
login_manager.login_view = "auth.login"    # 未ログイン時は /login へ

def create_app():
    # ── .env を読み込み ─────────────────────
    load_dotenv()                 # ← ここだけに統一

    app = Flask(__name__, instance_relative_config=True)

    # 1) Config クラスを読み込む
    app.config.from_object(Config)

    # 2) .env の値で上書き（無ければ既存値を保持）
    app.config["MAX_CONTENT_LENGTH"] = int(
        os.getenv("MAX_CONTENT_LENGTH", app.config.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))
    )

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