import secrets
from datetime import datetime, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from pydantic import ValidationError
from werkzeug.security import check_password_hash, generate_password_hash

from app import schemas
from app.db import get_db
from app.services import mail as mail_service
from app.utils import login_required

auth_bp = Blueprint("auth", __name__)

# 確認メールのリンク（トークン）の有効期限
TOKEN_EXPIRY = timedelta(minutes=30)

# メールアドレスの確認に使用するワンタイムトークンを生成
def _generate_token(cursor, user_id: int) -> str:
    # ユーザーに対して既に紐づいているトークンデータがある場合は破棄
    cursor.execute(
        "DELETE FROM verifications WHERE user_id = %s AND type = 'registration'",
        (user_id,),
    )

    # 新しいトークン＆有効期限を発行
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + TOKEN_EXPIRY

    # Verificationsテーブルにトークンの情報を追加
    cursor.execute(
        """
        INSERT INTO verifications (user_id, token, type, expires_at)
        VALUES (%s, %s, 'registration', %s)
        """,
        (user_id, token, expires_at),
    )
    return token

# 新規登録
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    # 入力エラーで画面を出し直すとき、入力済みのメールアドレスを消さないよう先に控えておく。
    entered_email = (request.form.get("email") or "").strip()

    # SignUpSchemaのバリデーションルールに基づいて、新規登録フォームの内容を検証する
    try:
        form = schemas.SignUpSchema.model_validate(request.form.to_dict())
    except ValidationError as exc:
        # バリデーションエラー表示を行う
        flash(schemas.get_error_message(exc), "error")
        return render_template("register.html", email=entered_email), 400

    email = form.email
    password = form.password

    # DBコネクション、カーソルを取得
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        # ユニークなメールアドレスであるか検証する
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone() is not None:
            flash("このメールアドレスは既に登録されています。", "error")
            return render_template("register.html", email=email), 400

        # パスワードのハッシュ化を行う
        hashed_password = generate_password_hash(password)

        # Usersテーブルに新規ユーザー情報を追加する
        cursor.execute(
            "INSERT INTO users (email, hashed_password, is_verified) VALUES (%s, %s, FALSE)",
            (email, hashed_password),
        )

        # 連番情報からユーザーidを取得
        user_id = cursor.lastrowid

        # メール確認用のトークンを発行する
        token = _generate_token(cursor, user_id)
        db.commit()

        # 新規登録しようとしているメールアドレス宛に確認用メールを送信する
        try:
            mail_service.send_verification_email(email, token)
        except RuntimeError as exc:
            current_app.logger.error(f"登録確認メールの送信に失敗しました: {exc}")
            flash(
                "会員登録は受け付けましたが、確認メールの送信に失敗しました。"
                "時間をおいて再送してください。",
                "error",
            )
            return redirect(url_for("auth.registration_sent", email=email))

        # 「確認メールを送信しました」画面へ遷移させる
        return redirect(url_for("auth.registration_sent", email=email))

    except Exception as exc:
        # DBエラーが起きたときは、会員登録処理をなかったことにする
        db.rollback()
        current_app.logger.error(f"新規登録処理でエラーが発生しました: {exc}")
        flash("新規登録に失敗しました。時間をおいて再度お試しください。", "error")
        return render_template("register.html", email=email), 500
    finally:
        cursor.close()

# 「確認メールを送信しました」画面
@auth_bp.route("/register/sent")
def registration_sent():
    """会員登録後に「確認メールを送信しました」と案内する画面。再送フォームも持つ。"""
    # ?email=... が付いていればそれを再送フォームの初期値にする（無ければ空文字）
    return render_template("register_sent.html", email=request.args.get("email", ""))

# 確認メールの再送
@auth_bp.route("/register/resend", methods=["POST"])
def resend_verification():
    entered_email = (request.form.get("email") or "").strip()

    try:
        form = schemas.ResendVerificationSchema.model_validate(request.form.to_dict())
    except ValidationError as exc:
        flash(schemas.get_error_message(exc), "error")
        return render_template("register_sent.html", email=entered_email), 400

    email = form.email

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, is_verified FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        # そもそも登録されていない
        if user is None:
            flash("このメールアドレスは登録されていません。", "error")
            return render_template("register_sent.html", email=email), 404

        # 既に認証済みなら再送する意味がないので、ログイン画面へ案内する
        if user["is_verified"]:
            flash("このメールアドレスは既に確認済みです。ログインしてください。", "success")
            return redirect(url_for("auth.login"))

        # 古いトークンを捨てて新しいトークンを発行し、そのURLをメールで送る
        token = _generate_token(cursor, user["id"])
        db.commit()

        try:
            mail_service.send_verification_email(email, token)
        except RuntimeError as exc:
            current_app.logger.error(f"登録確認メールの再送に失敗しました: {exc}")
            flash("確認メールの送信に失敗しました。時間をおいて再度お試しください。", "error")
            return render_template("register_sent.html", email=email), 500

        flash("確認メールを再送しました。", "success")
        return redirect(url_for("auth.registration_sent", email=email))

    except Exception as exc:
        db.rollback()
        current_app.logger.error(f"確認メール再送処理でエラーが発生しました: {exc}")
        flash("確認メールの再送に失敗しました。時間をおいて再度お試しください。", "error")
        return render_template("register_sent.html", email=email), 500
    finally:
        cursor.close()


# URLの <token> の部分が、そのまま関数の引数 token に渡される
# （例: /verify/abc123 にアクセスすると token = "abc123"）
@auth_bp.route("/verify/<token>")
def verify_registration(token: str):
    """会員登録時に送った確認メールのリンク先。"""
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        # 1. トークンが存在するか確認 + 3. トークンの種類を確認
        #    （type も条件に入れることで、メール変更用のトークンを登録確認に流用できないようにする）
        cursor.execute(
            "SELECT id, user_id, expires_at FROM verifications WHERE token = %s AND type = 'registration'",
            (token,),
        )
        verification = cursor.fetchone()

        # 見つからない = 存在しないURL、または既に使われて削除済み
        if verification is None:
            return render_template(
                "verify.html", success=False, message="確認リンクが無効です。既に使用済みか、URLが正しくありません。"
            )

        # 2. トークンが期限切れでないか確認
        if verification["expires_at"] < datetime.now():
            # 期限切れトークンは以後使えないよう削除しておく。
            cursor.execute("DELETE FROM verifications WHERE id = %s", (verification["id"],))
            db.commit()
            return render_template(
                "verify.html", success=False, message="確認リンクの有効期限が切れています。お手数ですが再度登録してください。"
            )

        # 4. 対象ユーザーを取得
        cursor.execute("SELECT id FROM users WHERE id = %s", (verification["user_id"],))
        user = cursor.fetchone()

        # トークンはあるのにユーザーがいない（退会済みなど）。トークンだけ残しても意味がないので消す。
        if user is None:
            cursor.execute("DELETE FROM verifications WHERE id = %s", (verification["id"],))
            db.commit()
            return render_template("verify.html", success=False, message="対象のユーザーが見つかりませんでした。")

        # 5. users.is_verified = TRUE に更新
        cursor.execute("UPDATE users SET is_verified = TRUE WHERE id = %s", (user["id"],))
        # 6. 使用済みトークンを削除（同じURLを2回踏んでも無効になる）
        cursor.execute("DELETE FROM verifications WHERE id = %s", (verification["id"],))
        db.commit()

        # 確認リンクを踏んだ時点で本人確認は済んでいるので、
        # 改めてログイン画面を経由させずそのままログイン状態にする。
        session["user_id"] = user["id"]
        flash("メールアドレスの確認が完了しました。ようこそ！", "success")
        return redirect(url_for("home.index"))

    except Exception as exc:
        db.rollback()
        current_app.logger.error(f"メール確認処理でエラーが発生しました: {exc}")
        return render_template("verify.html", success=False, message="確認処理中にエラーが発生しました。"), 500
    finally:
        cursor.close()


# ログイン処理
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # GET … ログインフォームを表示するだけ
    if request.method == "GET":
        return render_template("login.html")

    # POST … フォーム送信時の処理
    entered_email = (request.form.get("email") or "").strip()

    # LoginSchemaのバリデーションルールに基づいて、ログインフォームの入力内容を検証する
    try:
        form = schemas.LoginSchema.model_validate(request.form.to_dict())
    except ValidationError as exc:
        flash(schemas.get_error_message(exc), "error")
        return render_template("login.html", email=entered_email), 400

    email = form.email
    password = form.password

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, hashed_password, is_verified FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        # check_password_hash は「入力されたパスワード」を同じ方法でハッシュ化し、
        # DBに保存されているハッシュと一致するかを見る（平文同士の比較はしない）。
        # ユーザーが存在しない場合もパスワード不一致の場合も、
        # 同じエラーメッセージにすることで「どちらが誤りか」を推測されにくくしている。
        if user is None or not check_password_hash(user["hashed_password"], password):
            flash("メールアドレスまたはパスワードが正しくありません。", "error")
            return render_template("login.html", email=email), 401

        # パスワードは合っているがメール認証がまだ。
        # show_resend=True を渡すと login.html 側で「確認メールを再送」リンクが表示される。
        if not user["is_verified"]:
            flash("メールアドレスがまだ確認されていません。届いたメールのリンクを確認してください。", "error")
            return render_template("login.html", email=email, show_resend=True), 403

        # ログイン成功。session に user_id を保存する（Flask標準のsession機能）。
        # 以降のリクエストでは session["user_id"] があるかどうかでログイン中か判定する。
        session["user_id"] = user["id"]
        flash("ログインしました。", "success")
        return redirect(url_for("home.index"))

    except Exception as exc:
        # SELECT しかしていないので rollback は不要
        current_app.logger.error(f"ログイン処理でエラーが発生しました: {exc}")
        flash("ログイン処理中にエラーが発生しました。", "error")
        return render_template("login.html", email=email), 500
    finally:
        cursor.close()


# ログアウト処理(セッションの内容を破棄)
@auth_bp.route("/logout")
def logout():
    # user_id を消せばログアウト。第2引数の None は「無くてもエラーにしない」ため。
    session.pop("user_id", None)
    flash("ログアウトしました。", "success")
    return redirect(url_for("home.index"))


# パスワード変更
# @login_required は app/utils.py で定義した自作デコレータで、
# 未ログイン（session に user_id が無い）ならログイン画面へ飛ばし、この関数を実行させない。
# フォームは設定画面（dashboard.settings）にあり、ここは送信先（POST）だけを受け持つ。
@auth_bp.route("/account/password", methods=["POST"])
@login_required
def change_password():
    # 文字数不足・確認用との不一致といった入力自体の不備は、
    # DBへ問い合わせる前にPydanticで弾く。
    try:
        form = schemas.ChangePasswordSchema.model_validate(request.form.to_dict())
    except ValidationError as exc:
        flash(schemas.get_error_message(exc), "error")
        return redirect(url_for("dashboard.settings"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        # session["user_id"] = 今ログインしているユーザーのID
        cursor.execute("SELECT id, hashed_password FROM users WHERE id = %s", (session["user_id"],))
        user = cursor.fetchone()

        # 現在のパスワードが正しくない場合は変更しない
        if user is None or not check_password_hash(user["hashed_password"], form.current_password):
            flash("現在のパスワードが正しくありません。", "error")
            return redirect(url_for("dashboard.settings"))

        # 新しいパスワードもハッシュ化してから保存する
        cursor.execute(
            "UPDATE users SET hashed_password = %s WHERE id = %s",
            (generate_password_hash(form.new_password), user["id"]),
        )
        db.commit()

        flash("パスワードを変更しました。", "success")
        return redirect(url_for("dashboard.settings"))

    except Exception as exc:
        db.rollback()
        current_app.logger.error(f"パスワード変更処理でエラーが発生しました: {exc}")
        flash("パスワードの変更に失敗しました。", "error")
        return redirect(url_for("dashboard.settings")), 500
    finally:
        cursor.close()


# メールアドレス変更（申請）
# この時点では users.email は書き換えない。新しいアドレス宛に確認メールを送り、
# リンクが踏まれた時点（verify_email_change）で初めて正式に変更する。
@auth_bp.route("/account/email", methods=["POST"])
@login_required
def request_email_change():
    # 2. 新しいメールアドレスの形式チェックはPydanticのEmailStrに任せる
    #    （パスワード照合より先に、入力そのものの妥当性を確認しておく）。
    try:
        form = schemas.ChangeEmailSchema.model_validate(request.form.to_dict())
    except ValidationError as exc:
        flash(schemas.get_error_message(exc), "error")
        return redirect(url_for("dashboard.settings"))

    new_email = form.new_email

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        # 1. 現在のパスワードを検証
        cursor.execute("SELECT id, email, hashed_password FROM users WHERE id = %s", (session["user_id"],))
        user = cursor.fetchone()

        if user is None or not check_password_hash(user["hashed_password"], form.current_password):
            flash("現在のパスワードが正しくありません。", "error")
            return redirect(url_for("dashboard.settings"))

        if new_email == user["email"]:
            flash("現在のメールアドレスと同じです。", "error")
            return redirect(url_for("dashboard.settings"))

        # 3. 新しいメールアドレスが既存ユーザーに使用されていないことを確認
        cursor.execute("SELECT id FROM users WHERE email = %s", (new_email,))
        if cursor.fetchone() is not None:
            flash("そのメールアドレスは既に他のアカウントで使用されています。", "error")
            return redirect(url_for("dashboard.settings"))

        # 4. 確認用トークンを生成
        #    登録時と違い new_email も一緒に保存しておき、確認時に「どのアドレスへ変えるか」を取り出す。
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + TOKEN_EXPIRY
        cursor.execute(
            """
            INSERT INTO verifications (user_id, token, new_email, type, expires_at)
            VALUES (%s, %s, %s, 'email_change', %s)
            """,
            (user["id"], token, new_email, expires_at),
        )
        db.commit()

        # 5. 新しいメールアドレスへ確認メールを送信
        #    （今のアドレスではなく新しいアドレスに送ることで、そのアドレスの持ち主であることを確認する）
        try:
            mail_service.send_email_change_verification_email(new_email, token)
        except RuntimeError as exc:
            current_app.logger.error(f"メールアドレス変更確認メールの送信に失敗しました: {exc}")
            flash("確認メールの送信に失敗しました。時間をおいて再度お試しください。", "error")
            return redirect(url_for("dashboard.settings")), 500

        flash("新しいメールアドレスへ確認メールを送信しました。メール内のリンクから変更を完了してください。", "success")
        return redirect(url_for("dashboard.settings"))

    except Exception as exc:
        db.rollback()
        current_app.logger.error(f"メールアドレス変更申請でエラーが発生しました: {exc}")
        flash("メールアドレス変更の申請に失敗しました。", "error")
        return redirect(url_for("dashboard.settings")), 500
    finally:
        cursor.close()


# メールアドレス変更（確定）
# ログイン必須にはしていない。トークンを知っている = 新しいアドレスのメールを受け取れた本人、とみなす。
@auth_bp.route("/account/email/verify/<token>")
def verify_email_change(token: str):
    """メールアドレス変更確認メールのリンク先。クリックされた時点で正式に変更する。"""
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        # 流れは verify_registration と同じ: トークン存在確認 → 期限確認 → 本処理 → トークン削除
        cursor.execute(
            "SELECT id, user_id, new_email, expires_at FROM verifications WHERE token = %s AND type = 'email_change'",
            (token,),
        )
        verification = cursor.fetchone()

        if verification is None:
            return render_template(
                "verify.html", success=False, message="確認リンクが無効です。既に使用済みか、URLが正しくありません。"
            )

        if verification["expires_at"] < datetime.now():
            cursor.execute("DELETE FROM verifications WHERE id = %s", (verification["id"],))
            db.commit()
            return render_template(
                "verify.html",
                success=False,
                message="確認リンクの有効期限が切れています。お手数ですが再度変更手続きを行ってください。",
            )

        # 申請時に保存しておいた「変更先アドレス」を取り出す
        new_email = verification["new_email"]

        # 確認完了時にも、新しいメールアドレスが他ユーザーによって
        # 使用されていないことを再確認する（申請後に他の人が同じアドレスで
        # 登録・変更してしまう競合を防ぐため）。
        cursor.execute(
            "SELECT id FROM users WHERE email = %s AND id != %s",
            (new_email, verification["user_id"]),
        )
        if cursor.fetchone() is not None:
            cursor.execute("DELETE FROM verifications WHERE id = %s", (verification["id"],))
            db.commit()
            return render_template(
                "verify.html",
                success=False,
                message="そのメールアドレスは既に他のアカウントで使用されているため、変更できませんでした。",
            )

        # ここで初めて users.email を書き換える
        cursor.execute(
            "UPDATE users SET email = %s WHERE id = %s",
            (new_email, verification["user_id"]),
        )
        # 使用済みの確認トークンは削除する
        cursor.execute("DELETE FROM verifications WHERE id = %s", (verification["id"],))
        db.commit()

        return render_template("verify.html", success=True, message="メールアドレスの変更が完了しました。")

    except Exception as exc:
        db.rollback()
        current_app.logger.error(f"メールアドレス変更確認処理でエラーが発生しました: {exc}")
        return render_template("verify.html", success=False, message="確認処理中にエラーが発生しました。"), 500
    finally:
        cursor.close()
