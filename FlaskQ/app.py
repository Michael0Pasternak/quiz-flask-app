import json
import uuid
from pathlib import Path
from services.quiz import get_result, get_result_rank_in_quiz
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, abort
from dotenv import load_dotenv

from config import Config
from services.db import init_db, close_db, get_db
from services.auth import hash_password, verify_password, login_required, admin_required
from services.quiz import (
    search_quizzes, get_quiz, get_quiz_questions_with_options,
    grade_quiz, save_result, get_leaderboard, create_quiz
)

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    @app.before_request
    def _ensure_schema():
        # Инициализация схемы один раз при первом запросе
        if not app.config.get("_SCHEMA_READY"):
            init_db()
            app.config["_SCHEMA_READY"] = True

    app.teardown_appcontext(close_db)

    def allowed_image(filename: str) -> bool:
        if "." not in filename:
            return False
        ext = filename.rsplit(".", 1)[1].lower()
        return ext in app.config["ALLOWED_IMAGE_EXTENSIONS"]

    @app.context_processor
    def inject_user():
        return {
            "current_user": {
                "id": session.get("user_id"),
                "username": session.get("username"),
                "role": session.get("role"),
            }
        }

    @app.route("/")
    def index():
        return render_template("index.html")

    # ---------------- AUTH ----------------

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            password_confirm = request.form.get("password_confirm", "")

            if not email or not username or not password or not password_confirm:
                flash("Заполните все поля.")
                return redirect(url_for("register"))

            if password != password_confirm:
                flash("Пароли не совпадают.")
                return redirect(url_for("register"))

            db = get_db()
            with db.cursor() as cur:
                # проверка email
                cur.execute("SELECT id FROM users WHERE email=%s", (email,))
                if cur.fetchone():
                    flash("Этот email уже зарегистрирован.")
                    db.rollback()
                    return redirect(url_for("register"))

                # проверка username
                cur.execute("SELECT id FROM users WHERE username=%s", (username,))
                if cur.fetchone():
                    flash("Этот никнейм уже занят.")
                    db.rollback()
                    return redirect(url_for("register"))

                cur.execute(
                    """
                    INSERT INTO users (email, username, password_hash, role)
                    VALUES (%s, %s, %s, 'user') RETURNING id
                    """,
                    (email, username, hash_password(password))
                )
                user_id = cur.fetchone()[0]

            db.commit()

            session["user_id"] = int(user_id)
            session["username"] = username
            session["role"] = "user"

            flash("Регистрация успешна!")
            return redirect(url_for("index"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            db = get_db()
            with db.cursor() as cur:
                cur.execute(
                    "SELECT id, username, password_hash, role FROM users WHERE email=%s",
                    (email,)
                )
                row = cur.fetchone()

            if not row:
                flash("Неверная почта или пароль.")
                return redirect(url_for("login"))

            user_id, username, pwd_hash, role = row
            if not verify_password(password, pwd_hash):
                flash("Неверная почта или пароль.")
                return redirect(url_for("login"))

            session["user_id"] = int(user_id)
            session["username"] = username
            session["role"] = role

            flash("Вход выполнен.")
            return redirect(url_for("index"))

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Вы вышли.")
        return redirect(url_for("index"))

    # ---------------- QUIZZES ----------------

    @app.route("/quizzes")
    def quizzes():
        q = request.args.get("q", "")
        items = search_quizzes(q)
        return render_template("quizzes.html", quizzes=items, q=q)

    @app.route("/quiz/<int:quiz_id>")
    def quiz_detail(quiz_id: int):
        quiz = get_quiz(quiz_id)
        if not quiz:
            abort(404)
        return render_template("quiz_detail.html", quiz=quiz)

    @app.route("/quiz/<int:quiz_id>/pass", methods=["GET", "POST"])
    @login_required
    def quiz_pass(quiz_id: int):
        quiz = get_quiz(quiz_id)
        if not quiz:
            abort(404)

        questions = get_quiz_questions_with_options(quiz_id)
        if not questions:
            flash("У этой викторины пока нет вопросов.")
            return redirect(url_for("quiz_detail", quiz_id=quiz_id))

        if request.method == "POST":
            answers = dict(request.form)  # {question_id: option_id}
            score, total = grade_quiz(quiz_id, answers)
            duration_seconds = request.form.get("duration_seconds")
            try:
                duration_seconds = int(duration_seconds) if duration_seconds else None
            except:
                duration_seconds = None

            points = int(score) * 100  # 100 баллов за правильный ответ

            result_id = save_result(session["user_id"], quiz_id, score, total, duration_seconds, points)
            return redirect(url_for("quiz_result", result_id=result_id))

        return render_template("quiz_pass.html", quiz=quiz, questions=questions)

    @app.route("/result/<int:result_id>")
    @login_required
    def quiz_result(result_id: int):
        res = get_result(result_id)
        if not res or res["user_id"] != session.get("user_id"):
            abort(404)

        rank = get_result_rank_in_quiz(result_id)

        ratio = (res["score"] / res["total"]) if res["total"] else 0
        stars = 1
        if ratio >= 0.9:
            stars = 5
        elif ratio >= 0.75:
            stars = 4
        elif ratio >= 0.5:
            stars = 3
        elif ratio >= 0.25:
            stars = 2

        return render_template("result.html", res=res, rank=rank, stars=stars)

    @app.route("/leaderboard")
    def leaderboard():
        items = get_leaderboard(50)
        return render_template("leaderboard.html", items=items)

    # ---------------- ADMIN ----------------

    @app.route("/admin")
    @admin_required
    def admin_panel():
        items = search_quizzes("")
        return render_template("admin/admin_panel.html", quizzes=items)

    @app.route("/admin/quiz/create", methods=["GET", "POST"])
    @admin_required
    def admin_quiz_create():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            subtitle = request.form.get("subtitle", "").strip()
            questions_json = request.form.get("questions_json", "").strip()

            if not title:
                flash("Название обязательно.")
                return redirect(url_for("admin_quiz_create"))

            # Картинка викторины (общая)
            image_path = None
            file = request.files.get("image")
            if file and file.filename:
                if not allowed_image(file.filename):
                    flash("Неверный формат изображения (png/jpg/jpeg/webp).")
                    return redirect(url_for("admin_quiz_create"))
                ext = file.filename.rsplit(".", 1)[1].lower()
                new_name = f"{uuid.uuid4().hex}.{ext}"
                save_path = Path(app.config["UPLOAD_FOLDER"]) / new_name
                file.save(save_path)
                image_path = f"uploads/quizzes/{new_name}"

            # Парсим payload
            try:
                payload = json.loads(questions_json)
                if not isinstance(payload, list) or not payload:
                    raise ValueError("empty payload")

                for i, q in enumerate(payload):
                    if "text" not in q or "options" not in q or "correct" not in q:
                        raise ValueError("bad question format")
                    if not isinstance(q["options"], list) or len(q["options"]) != 4:
                        raise ValueError("options must be 4")
                    c = int(q["correct"])
                    if c < 1 or c > 4:
                        raise ValueError("correct must be 1..4")

                    # Картинка вопроса (опционально)
                    f = request.files.get(f"q_image_{i}")
                    if f and f.filename:
                        if not allowed_image(f.filename):
                            raise ValueError("bad question image format")
                        ext = f.filename.rsplit(".", 1)[1].lower()
                        new_name = f"{uuid.uuid4().hex}.{ext}"
                        q_save_path = Path(app.static_folder) / "uploads" / "questions" / new_name
                        f.save(q_save_path)
                        q["image_path"] = f"uploads/questions/{new_name}"

            except Exception:
                flash("Ошибка в данных вопросов. Проверь заполнение.")
                return redirect(url_for("admin_quiz_create"))

            quiz_id = create_quiz(
                created_by=session["user_id"],
                title=title,
                subtitle=subtitle,
                image_path=image_path,
                questions_payload=payload
            )
            flash("Викторина создана!")
            return redirect(url_for("quiz_detail", quiz_id=quiz_id))

        return render_template("admin/quiz_create.html")

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
