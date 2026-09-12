from flask import Flask, abort, render_template, request
from dotenv import load_dotenv
import os

from app import db
from app.services import mail as mail_service

def create_app():
    """ Flaskインスタンスの初期設定を行い返却する関数"""
    # .env ファイルを読み込む。
    load_dotenv()

    app = Flask(__name__)

    # --- Flaskインスタンスのconfigに対して.envの環境変数を書き込む。---

    # セッション管理
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

    # DB接続情報
    app.config["DB_HOST"] = os.getenv("DB_HOST", "localhost")
    app.config["DB_PORT"] = int(os.getenv("DB_PORT", "3306"))
    app.config["DB_USER"] = os.getenv("DB_USER", "root")
    app.config["DB_PASSWORD"] = os.getenv("DB_PASSWORD", "")
    app.config["DB_NAME"] = os.getenv("DB_NAME", "OH_PY23DB_IH12A_38")

    # WhisperのapiKey
    app.config["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")

    # Flask-Mailの送信設定情報
    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "")
    app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "587"))
    app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    app.config["MAIL_USE_SSL"] = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "")
    app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER", "")

    # --- ファイルアップロード設定 ---
    
    # 早口言葉の録音音声ファイルを格納するフォルダのパス
    app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads", "audio")
    # アップロードを許可する最大サイズ（16MB）
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    # --- DB接続の後始末処理を登録 ---
    db.init_app(app)

    # --- Flask-Mailインスタンスを初期化 ---
    mail_service.init_app(app)

    # --- Blueprintを登録 ---
    from app.routes.auth import auth_bp
    from app.routes.home import home_bp
    from app.routes.practice import practice_bp
    from app.routes.dashboard import dashboard_bp

    app.register_blueprint(home_bp) #トップ
    app.register_blueprint(auth_bp) #認証関連
    app.register_blueprint(practice_bp) #早口言葉の練習
    app.register_blueprint(dashboard_bp) #管理画面

    # --- ミドルウェア制御 ---

    # 録音ファイルへのアクセスを遮断
    @app.before_request
    def forbid_audio_request():
        if request.path.startswith("/static/uploads/audio/"):
            abort(403)

    # --- エラー制御(表示) ---
    @app.errorhandler(404)
    def handle_not_found(error):
        return render_template("error.html", status_code=404, message="お探しのページまたはお題が見つかりませんでした。"), 404

    @app.errorhandler(403)
    def handle_forbidden(error):
        return render_template("error.html", status_code=403, message="このページ・データへのアクセス権限がありません。"), 403

    @app.errorhandler(413)
    def handle_payload_too_large(error):
        return render_template("error.html", status_code=413, message="送信されたファイルが大きすぎます。"), 413

    @app.errorhandler(500)
    def handle_internal_error(error):
        # 予期しないエラーの詳細はサーバーログにのみ残し、利用者には出さない。
        app.logger.error(f"予期しないエラーが発生しました: {error}")
        return render_template("error.html", status_code=500, message="サーバー側で予期せぬエラーが発生しました。"), 500

    return app
