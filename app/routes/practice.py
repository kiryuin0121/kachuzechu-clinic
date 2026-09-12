""" お題の練習 """
import os

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from pydantic import ValidationError

from app import schemas
from app.db import get_db
from app.services import scoring, speech
from app.utils import get_audio_file_path, login_required

practice_bp = Blueprint("practice", __name__, url_prefix="/practice")

# 早口言葉idに紐づくお題を取得
def _get_tongue_twister(tongue_twister_id):
    """お題IDからレコードを1件取得する"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, phrase, furigana, difficulty, target_duration FROM tongue_twisters WHERE id = %s",
            (tongue_twister_id,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()

# ユーザーの録音音声ファイルを取得
@practice_bp.route("/audio/<int:tongue_twister_id>")
@login_required
def get_audio(tongue_twister_id: int):
    # 早口言葉idの妥当性の検証
    twister = _get_tongue_twister(tongue_twister_id)
    if twister is None:
            abort(404)

    # userのidを取得
    user_id = session["user_id"]

    # user_idとtwister_idで録音ファイルが存在するか調べる
    upload_folder, filename = get_audio_file_path(user_id, tongue_twister_id)
    if not os.path.exists(os.path.join(upload_folder, filename)):
        abort(404)

    # 録音ファイルをブラウザへ配信する
    return send_from_directory(upload_folder, filename, mimetype="audio/webm", conditional=True)

# 早口言葉１つの練習画面を表示
@practice_bp.route("/<int:tongue_twister_id>")
def practice(tongue_twister_id: int):
    # idでお題を取得
    twister = _get_tongue_twister(tongue_twister_id)
    if twister is None:
        # 不正なお題IDへのアクセスは拒否する。
        abort(404)

    # セッション情報を取得
    user_id = session.get("user_id")
    best_score = None
    last_log = None
    has_audio = False
    audio_url = None
    # ログイン時は、学習履歴の値を取得してくる
    if user_id is not None:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        try:
            # ログインしているユーザーの自己ベストを取得
            cursor.execute(
                """
                SELECT MAX(total_score) AS best_score
                FROM logs
                WHERE user_id = %s AND tongue_twister_id = %s
                """,
                (user_id, tongue_twister_id),
            )
            row = cursor.fetchone()
            best_score = row["best_score"] if row else None

            # 最新の練習記録を取得
            cursor.execute(
                """
                SELECT total_score FROM logs
                WHERE user_id = %s AND tongue_twister_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (user_id, tongue_twister_id),
            )
            last_log = cursor.fetchone()
        finally:
            cursor.close()

        # 録音ファイルが存在する場合は、実データのアドレスを生成
        upload_folder, filename = get_audio_file_path(user_id, tongue_twister_id)
        if os.path.exists(os.path.join(upload_folder, filename)):
            has_audio = True
            audio_url = url_for("practice.get_audio", tongue_twister_id=tongue_twister_id)

    return render_template(
        "practice.html",
        twister=twister,
        is_member=user_id is not None,
        best_score=best_score,
        last_log=last_log,
        has_audio=has_audio,
        audio_url=audio_url,
        repeat_count=scoring.PRACTICE_REPEAT_COUNT,
    )


@practice_bp.route("/score", methods=["POST"])
def score():
    """録音データを受け取り、音声認識・採点を行ってJSONで結果を返す"""

    audio_file = request.files.get("audio")
    if audio_file is None or audio_file.filename == "":
        return jsonify({"success": False, "message": "音声データが送信されていません。"}), 400

    audio_bytes = audio_file.read()

    # お題ID・録音時間・音声形式・サイズを検証する
    # （リクエスト全体のサイズ上限は MAX_CONTENT_LENGTH で Flask が先に413を返す）
    try:
        payload = schemas.ScoreRequestSchema.model_validate(
            {
                "tongue_twister_id": request.form.get("tongue_twister_id"),
                "duration_seconds": request.form.get("duration_seconds"),
                "audio_mimetype": audio_file.mimetype or "",
                "audio_size": len(audio_bytes),
            }
        )
    except ValidationError as exc:
        return jsonify({"success": False, "message": schemas.get_error_message(exc)}), 400

    tongue_twister_id = payload.tongue_twister_id
    duration_seconds = payload.duration_seconds

    twister = _get_tongue_twister(tongue_twister_id)
    if twister is None:
        return jsonify({"success": False, "message": "指定されたお題が見つかりません。"}), 404

    # 音声認識。送られてきた形式に合わせた拡張子で Whisper に渡す
    try:
        transcribed_text = speech.transcribe_uploaded_audio(
            audio_bytes, suffix=payload.audio_extension
        )
    except RuntimeError as exc:
        # APIキー未設定・認識結果が空など
        current_app.logger.error(f"音声認識に失敗しました: {exc}")
        return jsonify({"success": False, "message": "音声認識に失敗しました。もう一度お試しください。"}), 502
    except Exception as exc:
        # OpenAI SDK 側の例外（キー不正・通信エラーなど）。詳細はログにだけ残す
        current_app.logger.error(f"音声認識中に予期しないエラーが発生しました: {exc}")
        return jsonify({"success": False, "message": "音声認識サービスでエラーが発生しました。"}), 502

    # Whisper が漢字で書き起こした場合に備えて、お題本文も正解候補として渡す
    result = scoring.score_tongue_twister(
        expected_furigana=twister["furigana"],
        transcribed_text=transcribed_text,
        duration_seconds=duration_seconds,
        target_duration=twister["target_duration"],
        expected_phrase=twister["phrase"],
    )

    if not result.get("success"):
        return jsonify(result), 400

    # 会員は最新音声を上書き保存し、logs に1件追加する
    user_id = session.get("user_id")
    if user_id is not None:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        try:
            absolute_audio_path = speech.save_member_audio(user_id, tongue_twister_id, audio_bytes)

            # audio_path は static フォルダからの相対パスで保存する
            relative_audio_path = os.path.relpath(
                absolute_audio_path, current_app.static_folder
            ).replace(os.sep, "/")

            cursor.execute(
                """
                INSERT INTO logs (
                    user_id, tongue_twister_id, phrase_log, hiragana_log,
                    duration_log, accuracy_score, speed_score, total_score, audio_path
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    tongue_twister_id,
                    result["transcribed_text"],
                    result["transcribed_hiragana"],
                    result["duration_seconds"],
                    result["accuracy_score"],
                    result["speed_score"],
                    result["total_score"],
                    relative_audio_path,
                ),
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            current_app.logger.error(f"練習結果の保存に失敗しました: {exc}")
            # 採点は済んでいるので結果は返し、履歴保存に失敗したことだけ伝える
            result["log_saved"] = False
            result["log_save_error"] = "練習結果の保存に失敗しました。"
            cursor.close()
            return jsonify(result), 200
        else:
            result["log_saved"] = True
        finally:
            cursor.close()
    else:
        # ゲストは履歴を保存しない（一時音声は speech 側で削除済み）
        result["log_saved"] = False

    return jsonify(result), 200


