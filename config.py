import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent  # Исправлено: добавил __ перед file


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

    # Новая база данных для приложения
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://quizdbuser:5L7uW8YetOVBq6nTkxyGOX5LxLwW5FMc@dpg-d52l9bemcj7s73br0stg-a.virginia-postgres.render.com/quizdb_kbqg"
    )

    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "static" / "uploads" / "quizzes"))
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}