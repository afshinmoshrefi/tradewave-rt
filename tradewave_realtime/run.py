"""Dev entrypoint: `python run.py` (or `flask --app run.py run`)."""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=app.config["PORT"], debug=True)
