from flask import current_app, url_for
from flask_mail import Mail, Message

# Flask-Mailインスタンスを生成
mail = Mail()

def init_app(app) -> None:
    """Flask-Mailインスタンスを初期化する関数"""
    mail.init_app(app)

# メール送信
def _send_mail(subject: str, recipient: str, body: str) -> None:
    """メールを構築し、送信する関数"""
    try:
        message = Message(
            subject=subject,
            recipients=[recipient],
            body=body,
            sender=current_app.config.get("MAIL_DEFAULT_SENDER"),
        )
        mail.send(message)
    except Exception as exc:
        current_app.logger.error(f"メール送信に失敗しました（宛先: {recipient}): {exc}")
        raise RuntimeError("メールの送信に失敗しました。") from exc

# 初回登録時のメールアドレス検証
def send_verification_email(recipient_email: str, token: str) -> None:
    """会員登録時の、メールアドレス確認メールを送信する。"""

    # 検証用のリンクを取得
    verify_url = url_for("auth.verify_registration", token=token, _external=True)

    # メール本文
    body = (
        "滑舌クリニックへのご登録ありがとうございます。\n\n"
        "以下のリンクをクリックして、メールアドレスの確認を完了してください。\n"
        f"{verify_url}\n\n"
        "このリンクには有効期限があります。期限が切れた場合は再度登録を行ってください。\n"
        "このメールに心当たりがない場合は、破棄してください。"
    )

    # 新規登録する予定のメールアドレスに対して検証用のメールを送信する
    _send_mail("【滑舌クリニック】メールアドレスの確認のご案内", recipient_email, body)

# メールアドレス変更時の新規アドレスの検証
def send_email_change_verification_email(recipient_email: str, token: str) -> None:
    """メールアドレス変更時の、新アドレス確認メールを送信する。"""

    # 検証用のリンクを取得
    verify_url = url_for("auth.verify_email_change", token=token, _external=True)

    # メール本文
    body = (
        "メールアドレス変更のお手続きを受け付けました。\n\n"
        "以下のリンクをクリックすると、このアドレスへの変更が完了します。\n"
        f"{verify_url}\n\n"
        "このリンクには有効期限があります。期限が切れた場合は変更手続きをやり直してください。\n"
        "このメールに心当たりがない場合は、破棄してください。"
    )

    # 変更後のメールアドレスに,,
    _send_mail("【滑舌クリニック】メールアドレス変更の確認のご案内", recipient_email, body)
