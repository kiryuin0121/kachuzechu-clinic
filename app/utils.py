from functools import wraps

from flask import current_app, redirect, session, url_for

from app.db import get_db

# ログイン必須な処理の前にはさみこんで実行するデコレーター関数
def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        # ろぐいんしてなかったらログインページにリダイレクトして次に進ませない。してたら次の処理にとおす処理
        if session.get("user_id") is None:
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)

    return wrapped_view


def get_current_user() -> dict | None:
    """現在ログイン中のユーザー情報をDBから取得する"""
    user_id = session.get("user_id")
    if user_id is None:
        return None

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, email FROM users WHERE id = %s", (user_id,))
        return cursor.fetchone()
    finally:
        cursor.close()

# userIdとtwisterIdから録音ファイルの物理的なファイルパスを組んで返す
def get_audio_file_path(user_id: int, tongue_twister_id: int):
    """ userIdとtwisterIdから録音ファイルの物理的なファイルパスを組んで返す """
    filename = f"audio_user_{user_id}_twister_{tongue_twister_id}.webm"
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    return upload_folder, filename
