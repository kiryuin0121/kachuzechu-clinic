"""
会員ユーザー限定画面
"""

from flask import Blueprint, render_template, session

from app.db import get_db
from app.utils import get_current_user, login_required

dashboard_bp = Blueprint("dashboard", __name__)

# 学習履歴閲覧画面
@dashboard_bp.route("/mypage")
@login_required
def mypage():
    # セッションからuserIdを取得
    user_id = session["user_id"]
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # userに紐づく学習履歴から 総練習回数(履歴データの総数)と練習したことがある早口言葉の数(履歴が少なくとも一つ存在してるお題の数)を取得
    try:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_practice_count,
                COUNT(DISTINCT tongue_twister_id) AS practiced_twister_count
            FROM logs
            WHERE user_id = %s
            """,
            (user_id,),
        )
        stats = cursor.fetchone()
    finally:
        cursor.close()

    return render_template(
        "mypage.html",
        total_practice_count=stats["total_practice_count"],
        practiced_twister_count=stats["practiced_twister_count"],
    )

# アカウント情報の閲覧、編集画面
@dashboard_bp.route("/settings")
@login_required
def settings():
    user = get_current_user()
    return render_template("settings.html", user=user)
