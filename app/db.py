import mysql.connector
from flask import current_app, g

# https://qiita.com/taiyang-ks/items/48b27fb230f3ee9c9d4c

# --- DB接続 ---
def connect_db() -> mysql.connector.connection.MySQLConnection:
    """ DBへのコネクションを作成して返す """
    # Flaskインスタンスのconfig変数からDB接続情報を読みだしてセットする
    return mysql.connector.connect(
        host=current_app.config.get("DB_HOST", "localhost"),
        port=int(current_app.config.get("DB_PORT", 3306)),
        user=current_app.config.get("DB_USER", "root"),
        password=current_app.config.get("DB_PASSWORD", ""),
        database=current_app.config.get("DB_NAME", "OH_PY23DB_IH12A_38"),
        autocommit=False,
        charset="utf8mb4",  # 日本語・絵文字対応
    )

# DBコネクションを取得
def get_db() -> mysql.connector.connection.MySQLConnection:
    """Flaskのgオブジェクトから現在のDBコネクションを取得(なければ作成して保持)"""
    if "db_connection" not in g:
        g.db_connection = connect_db()
    return g.db_connection

# DBコネクションを破棄
def close_db(exception: Exception | None = None) -> None:
    """リクエスト終了時にFlaskのgオブジェクトからDBコネクションを破棄"""
    db_connection = g.pop("db_connection", None)
    if db_connection is not None:
        db_connection.close()

def init_app(app) -> None:
    """Flaskアプリ終了に呼応してDBコネクションを閉じる処理を登録"""
    app.teardown_appcontext(close_db)
