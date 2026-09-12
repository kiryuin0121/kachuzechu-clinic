""" お題の表示 """
from flask import Blueprint, abort, current_app, render_template, session

from app.db import get_db
from app.services import scoring

home_bp = Blueprint("home", __name__)

# 早口言葉の難易度は5段階
DIFFICULTIES = (1, 2, 3, 4, 5)

# トップ画面(難易度選択画面)
@home_bp.route("/")
def index():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        # 各難易度に何件のお題があるかを取得
        cursor.execute(
            "SELECT difficulty, COUNT(*) AS count FROM tongue_twisters GROUP BY difficulty"
        )
        rows = cursor.fetchall()
        counts_by_difficulty = {row["difficulty"]: row["count"] for row in rows}
    except Exception as exc:
        current_app.logger.error(f"ホーム画面のお題件数取得に失敗しました: {exc}")
        counts_by_difficulty = {}
    finally:
        cursor.close()

    return render_template(
        "index.html",
        difficulties=DIFFICULTIES,
        counts_by_difficulty=counts_by_difficulty,
    )


# レベル別のお題一覧表示画面
@home_bp.route("/difficulty/<int:level>")
def difficulty(level: int):
    # 不正な難易度（1〜5の範囲外）へのアクセスは拒否する。
    if level not in DIFFICULTIES:
        abort(404)

    # DBコネクション、カーソルを取得
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # 難易度別にお題一覧を取得する
    try:
        cursor.execute(
            """
            SELECT id, phrase, difficulty, target_duration
            FROM tongue_twisters
            WHERE difficulty = %s
            ORDER BY id
            """,
            (level,),
        )
        tongue_twisters = cursor.fetchall()

        # セッション情報を取得
        user_id = session.get("user_id")

        # お題idに自己ベストが紐づけられたリスト
        best_scores = {}

        # ログインしているときは、best_scoresを埋める
        if user_id is not None:
            cursor.execute(
                """
                SELECT tongue_twister_id, MAX(total_score) AS best_score
                FROM logs
                WHERE user_id = %s AND tongue_twister_id IN (
                    SELECT id FROM tongue_twisters WHERE difficulty = %s
                )
                GROUP BY tongue_twister_id
                """,
                (user_id, level),
            )
            best_scores = {row["tongue_twister_id"]: row["best_score"] for row in cursor.fetchall()}
    finally:
        cursor.close()

    return render_template(
        "difficulty.html",
        level=level,
        tongue_twisters=tongue_twisters,
        best_scores=best_scores,
        repeat_count=scoring.PRACTICE_REPEAT_COUNT,
    )
