import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

    # Правильно: в getenv первым аргументом идёт ИМЯ переменной, вторым — значение по умолчанию
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://quizuser:quizpass@127.0.0.1:5432/quizdb"
    )

    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "static" / "uploads" / "quizzes"))
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
