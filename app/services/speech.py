"""音声ファイルの保存と Whisper による音声認識

会員の録音はユーザーID×お題IDごとに1ファイルだけ残し、再録音時は上書きする。
ゲストの録音は一時ファイルとして扱い、認識が終わったら削除する。
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, Optional

from flask import current_app
from openai import OpenAI


def _get_upload_directory() -> Path:
    """会員の録音の保存先ディレクトリを返す"""
    # Flask経由でない呼び出し（単体テストなど）でも動くようにデフォルトを持たせている
    if current_app:
        configured_path = current_app.config.get("UPLOAD_FOLDER")
        if configured_path:
            return Path(configured_path)
    return Path("app/static/uploads/audio")


def _get_openai_client() -> OpenAI:
    """Whisper API 呼び出し用のクライアントを返す"""
    api_key = current_app.config.get("OPENAI_API_KEY") if current_app else os.getenv("OPENAI_API_KEY")
    if not api_key:
        # キー未設定を Whisper 側のエラーと区別できるよう、ここで先に弾く
        raise RuntimeError("OpenAI APIキーが設定されていません。")
    return OpenAI(api_key=api_key)


def transcribe_audio_file(audio_file_path: str, language: str = "ja") -> str:
    """音声ファイルを Whisper API でテキスト化する"""
    client = _get_openai_client()

    with open(audio_file_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language,
        )

    text = getattr(response, "text", "")
    if not text:
        raise RuntimeError("音声認識の結果が空でした。")

    return text


def save_member_audio(user_id: int, tongue_twister_id: int, audio_bytes: bytes) -> str:
    """会員の録音をユーザーID×お題IDごとに1ファイルだけ保存する（既存ファイルは上書き）"""
    upload_directory = _get_upload_directory()
    upload_directory.mkdir(parents=True, exist_ok=True)

    # アップロード時のファイル名は使わず、IDから組み立てる（パス操作対策）
    filename = f"audio_user_{user_id}_twister_{tongue_twister_id}.webm"
    target_path = upload_directory / filename

    # 同名ファイルへの書き込みで上書きされるので、古い録音の削除は不要
    target_path.write_bytes(audio_bytes)

    return str(target_path)


def save_temporary_audio(audio_bytes: bytes, suffix: str = ".webm") -> str:
    """認識処理の間だけ使う一時ファイルを作り、そのパスを返す"""
    # Windows では開いたままのファイルを別の処理で読めないことがあるため、
    # delete=False で作って閉じ、削除は cleanup_file で行う
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.write(audio_bytes)
    temp_file.close()
    return temp_file.name


def cleanup_file(file_path: Optional[str]) -> None:
    """一時ファイルを削除する（存在しなければ何もしない）"""
    if file_path and os.path.exists(file_path):
        os.remove(file_path)


def transcribe_uploaded_audio(audio_bytes: bytes, suffix: str = ".webm", language: str = "ja") -> str:
    """アップロードされた音声データを Whisper で認識し、テキストを返す

    会員・ゲストどちらも一時ファイル経由で認識する。
    会員の録音を残すかどうかは呼び出し側で別途扱う。
    """
    temp_audio_path = None
    try:
        temp_audio_path = save_temporary_audio(audio_bytes, suffix=suffix)
        return transcribe_audio_file(temp_audio_path, language=language)
    finally:
        cleanup_file(temp_audio_path)


def process_guest_audio(audio_bytes: bytes, suffix: str = ".webm", language: str = "ja") -> Dict[str, str]:
    """ゲストの音声を一時保存→認識→削除の流れで処理する"""
    temp_audio_path = None

    try:
        temp_audio_path = save_temporary_audio(audio_bytes, suffix=suffix)
        transcribed_text = transcribe_audio_file(temp_audio_path, language=language)

        return {
            "success": True,
            "transcribed_text": transcribed_text,
            "temp_audio_path": temp_audio_path,
        }
    except Exception as exc:
        raise RuntimeError(f"ゲスト音声の処理中にエラーが発生しました。: {exc}") from exc
    finally:
        # 認識に失敗した場合も一時ファイルを残さない
        cleanup_file(temp_audio_path)


def process_member_audio(user_id: int, tongue_twister_id: int, audio_bytes: bytes) -> Dict[str, str]:
    """会員の音声を保存先へ書き込む"""
    audio_path = None

    try:
        audio_path = save_member_audio(user_id, tongue_twister_id, audio_bytes)
        return {
            "success": True,
            "audio_path": audio_path,
        }
    except Exception as exc:
        raise RuntimeError(f"会員音声の保存中にエラーが発生しました。: {exc}") from exc
