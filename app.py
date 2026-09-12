from app import create_app

# Flaskインスタンスを取得
app = create_app()

# Flaskアプリを起動
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
