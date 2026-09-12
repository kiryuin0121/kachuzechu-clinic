import math
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    EmailStr,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


# --- 共通処理 ---

# 先頭末尾に含まれるホワイトスペースを除去
def _strip_text_space(value):
    return value.strip() if isinstance(value, str) else value

# パスワードが最低文字数を見たいしているかの検証
def _validate_password_length(value: str) -> str:
    if len(value) < 8:
        raise ValueError("パスワードは8文字以上で入力してください。")
    return value


# --- 共通データ型 ---

# メールアドレス(先頭末尾の空白を除去したうえで、メールアドレスの形式を満たす)
Email = Annotated[EmailStr, BeforeValidator(_strip_text_space)]

# 現在のパスワード(入力必須)
CurrentPassword = Annotated[str, Field(min_length=1)]

# 新しく設定するパスワード(最低文字数を満たす文字列)
NewPassword = Annotated[str, AfterValidator(_validate_password_length)]



# --- 入力フォーム関連のスキーマを定義 ---

# 新規登録
class SignUpSchema(BaseModel):
    email: Email
    password: NewPassword
    confirm_password: str

    # パスワードと確認用パスワードが一致しているかを検証
    @model_validator(mode="after")
    def _validate_confirm_password(self):
        if self.password != self.confirm_password:
            raise ValueError("パスワードと確認用パスワードが一致しません。")
        return self

# ログイン
class LoginSchema(BaseModel):
    email: Email
    password: CurrentPassword

# 確認メール再送
class ResendVerificationSchema(BaseModel):
    email: Email

# メールアドレス変更
class ChangeEmailSchema(BaseModel):
    current_password: CurrentPassword
    new_email: Email

# パスワード変更
class ChangePasswordSchema(BaseModel):
    current_password: CurrentPassword
    new_password: NewPassword
    confirm_new_password: str

    # 新しいパスワードと確認用パスワードが一致しているかを検証
    @model_validator(mode="after")
    def _validate_confirm_new_password(self):
        if self.new_password != self.confirm_new_password:
            raise ValueError("新しいパスワードと確認用パスワードが一致しません。")
        return self


# MediaRecorderが生成しうる代表的なMIMEタイプと、それに対応する拡張子の対応表
AUDIO_FORMAT_LIST = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".mp4",
    "audio/x-m4a": ".m4a",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mpeg": ".mp3",
}

# --- 採点APIの入力値のデータ形式 ---

# 採点API（/practice/score）
# duration_seconds はフロントエンドで計測した値なので改ざんされうる。
# そのためお題ID・音声形式と合わせて、サーバー側でも必ず検証する。
# 音声のバイト列そのものは渡さず、MIMEタイプとサイズだけを見る。
class ScoreRequestSchema(BaseModel):
    # 上から順に検証されるので「お題ID → 録音時間 → 音声」の順でエラーが返る。
    tongue_twister_id: int = Field(ge=1)
    duration_seconds: float
    audio_mimetype: str
    audio_size: int

    # 録音時間が現実的な範囲か
    @field_validator("duration_seconds")
    @classmethod
    def _validate_duration(cls, value: float) -> float:
        # "nan" や "inf" は float() を通ってしまうため、大小比較の前に弾く。
        if not math.isfinite(value):
            raise ValueError("録音時間の値が不正です。")
        if value <= 0:
            raise ValueError("録音時間は0より大きい値である必要があります。")
        # 目標時間（3回連続分）は最長でも14秒前後だが、録音の始め忘れ・止め忘れ等を
        # 考慮し、余裕を持たせつつも「異常に大きな値」を弾けるラインとして120秒を上限にする。
        if value > 120:
            raise ValueError("録音時間が長すぎます。")
        return value

    # 許可している音声形式か
    @field_validator("audio_mimetype")
    @classmethod
    def _validate_mimetype(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.startswith(tuple(AUDIO_FORMAT_LIST)):
            raise ValueError(f"許可されていない音声形式です（{normalized or '不明'}）。")
        return normalized

    # 音声データが空でないか
    @field_validator("audio_size")
    @classmethod
    def _validate_audio_size(cls, value: int) -> int:
        # サイズの上限は app.config["MAX_CONTENT_LENGTH"] によって
        # Flaskがリクエスト受信時点で413として弾くため、ここでは下限のみ見る。
        # 100バイト未満は空ファイルなど明らかに不正なアップロードとみなす。
        if value < 100:
            raise ValueError("音声データが空、または短すぎます。")
        return value

    # MIMEタイプに対応する、Whisperへ渡す一時ファイルの拡張子
    @property
    def audio_extension(self) -> str:
        for mime_prefix, extension in AUDIO_FORMAT_LIST.items():
            if self.audio_mimetype.startswith(mime_prefix):
                return extension
        return ".webm"


# --- バリデーションエラーメッセージ ---

# エラーメッセージ表示時に使用するラベル
ERROR_LABELS = {
    "email": "メールアドレス",
    "password": "パスワード",
    "confirm_password": "確認用パスワード",
    "current_password": "現在のパスワード",
    "new_password": "新しいパスワード",
    "confirm_new_password": "確認用パスワード",
    "new_email": "新しいメールアドレス",
    "tongue_twister_id": "お題ID",
    "duration_seconds": "録音時間",
    "audio_mimetype": "音声形式",
    "audio_size": "音声データ",
}

# pydanticのValidationErrorの内容からUIに表示するエラーメッセージを構築する
def get_error_message(exc: ValidationError) -> str:
    """ バリデーションエラーの内容に応じたエラーメッセージを取得する関数 """

    error = exc.errors()[0]
    message = str(error["msg"])

    # モデル内で raise ValueError("...") した文は、Pydanticが "Value error, " を
    # 頭に付けて返してくるので、それを外して自分で書いた日本語メッセージをそのまま使う。
    prefix = "Value error, "
    if message.startswith(prefix):
        return message[len(prefix):]

    # 未入力・型違い・EmailStrの形式エラーなど、Pydantic標準の英語エラーの場合。
    field_name = error["loc"][0] if error["loc"] else None
    label = ERROR_LABELS.get(field_name, "入力内容")

    return f"{label}が正しくありません。"
