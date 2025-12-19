# services/quiz.py
from __future__ import annotations

from typing import Optional, Dict, Any, List, Tuple

from services.db import get_db


# =========================
# Public (user) functions
# =========================

def search_quizzes(q: str = "") -> List[Dict[str, Any]]:
    db = get_db()
    q = (q or "").strip()

    with db.cursor() as cur:
        if q:
            cur.execute(
                """
                SELECT id, title, subtitle, image_path
                FROM quizzes
                WHERE title ILIKE %s
                ORDER BY created_at DESC
                """,
                (f"%{q}%",),
            )
        else:
            cur.execute(
                """
                SELECT id, title, subtitle, image_path
                FROM quizzes
                ORDER BY created_at DESC
                """
            )
        rows = cur.fetchall()

    return [{"id": r[0], "title": r[1], "subtitle": r[2], "image_path": r[3]} for r in rows]


def get_quiz(quiz_id: int) -> Optional[Dict[str, Any]]:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, title, subtitle, image_path FROM quizzes WHERE id=%s",
            (quiz_id,),
        )
        row = cur.fetchone()

    if not row:
        return None

    return {"id": row[0], "title": row[1], "subtitle": row[2], "image_path": row[3]}


def get_quiz_questions_with_options(quiz_id: int) -> List[Dict[str, Any]]:
    db = get_db()

    with db.cursor() as cur:
        cur.execute(
            """
            SELECT q.id, q.text, q.position, q.image_path, q.explanation
            FROM questions q
            WHERE q.quiz_id=%s
            ORDER BY q.position ASC, q.id ASC
            """,
            (quiz_id,),
        )
        qrows = cur.fetchall()

        questions: List[Dict[str, Any]] = []
        for qid, qtext, pos, qimg, qexp in qrows:
            cur.execute(
                """
                SELECT id, text
                FROM options
                WHERE question_id=%s
                ORDER BY id ASC
                """,
                (qid,),
            )
            orows = cur.fetchall()

            questions.append(
                {
                    "id": qid,
                    "text": qtext,
                    "position": pos,
                    "image_path": qimg,
                    "explanation": qexp,
                    "options": [{"id": oid, "text": otext} for oid, otext in orows],
                }
            )

    return questions


def grade_quiz(quiz_id: int, answers: dict) -> Tuple[int, int]:
    """
    answers: {question_id(str/int): option_id(str/int)}
    Возвращает (score, total_questions)
    """
    db = get_db()

    with db.cursor() as cur:
        cur.execute("SELECT id FROM questions WHERE quiz_id=%s", (quiz_id,))
        qids = [r[0] for r in cur.fetchall()]

        total = len(qids)
        score = 0

        for qid in qids:
            chosen = answers.get(str(qid)) or answers.get(qid)
            if not chosen:
                continue

            cur.execute(
                """
                SELECT is_correct
                FROM options
                WHERE id=%s AND question_id=%s
                """,
                (int(chosen), qid),
            )
            row = cur.fetchone()
            if row and row[0] is True:
                score += 1

    return score, total


# =========================
# Results / leaderboard
# =========================

def save_result(
    user_id: int,
    quiz_id: int,
    score: int,
    total: int,
    duration_seconds: int | None,
    points: int,
) -> int:
    """
    Сохраняет попытку и возвращает result_id
    """
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO results (user_id, quiz_id, score, total, duration_seconds, points)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, quiz_id, score, total, duration_seconds, points),
        )
        rid = cur.fetchone()[0]
    db.commit()
    return int(rid)


def get_result(result_id: int) -> Optional[Dict[str, Any]]:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT r.id, r.user_id, u.username, r.quiz_id, r.score, r.total,
                   r.duration_seconds, r.points, q.title
            FROM results r
            JOIN users u ON u.id = r.user_id
            JOIN quizzes q ON q.id = r.quiz_id
            WHERE r.id = %s
            """,
            (result_id,),
        )
        row = cur.fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "user_id": row[1],
        "username": row[2],
        "quiz_id": row[3],
        "score": row[4],
        "total": row[5],
        "duration_seconds": row[6],
        "points": row[7],
        "quiz_title": row[8],
    }


def get_result_rank_in_quiz(result_id: int) -> int:
    """
    Место попытки среди всех попыток ЭТОЙ викторины по points DESC,
    затем duration ASC (быстрее — лучше).
    """
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT quiz_id FROM results WHERE id=%s", (result_id,))
        r = cur.fetchone()
        if not r:
            return 0
        quiz_id = r[0]

        cur.execute(
            """
            SELECT id
            FROM results
            WHERE quiz_id=%s
            ORDER BY points DESC NULLS LAST,
                     duration_seconds ASC NULLS LAST,
                     created_at ASC
            """,
            (quiz_id,),
        )
        ids = [x[0] for x in cur.fetchall()]

    return ids.index(result_id) + 1 if result_id in ids else 0


def get_leaderboard(limit=50):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT
              u.id AS user_id,
              u.username,
              COALESCE(SUM(r.score), 0) AS points
            FROM results r
            JOIN users u ON u.id = r.user_id
            GROUP BY u.id, u.username
            ORDER BY points DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    # rows: [(user_id, username, points), ...]
    return [{"user_id": r[0], "username": r[1], "points": r[2]} for r in rows]




# =========================
# Admin: create / list / delete
# =========================

def create_quiz(
    created_by: int,
    title: str,
    subtitle: str,
    image_path: str | None,
    questions_payload: list,
) -> int:
    """
    questions_payload = [
      {
        "text": "...",
        "options": ["a","b","c","d"],
        "correct": 2,              # 1..4
        "explanation": "....",     # optional
        "image_path": "uploads/questions/xxx.jpg"  # optional
      }, ...
    ]
    """
    db = get_db()

    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO quizzes (title, subtitle, image_path, created_by)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (title, subtitle, image_path, created_by),
        )
        quiz_id = cur.fetchone()[0]

        for idx, q in enumerate(questions_payload, start=1):
            cur.execute(
                """
                INSERT INTO questions (quiz_id, text, position, image_path, explanation)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (quiz_id, q["text"], idx, q.get("image_path"), q.get("explanation")),
            )
            qid = cur.fetchone()[0]

            correct = int(q["correct"])
            opts = q["options"]
            if len(opts) != 4:
                raise ValueError("Each question must have exactly 4 options")

            for i, opt_text in enumerate(opts, start=1):
                cur.execute(
                    """
                    INSERT INTO options (question_id, text, is_correct)
                    VALUES (%s, %s, %s)
                    """,
                    (qid, opt_text, (i == correct)),
                )

    db.commit()
    return int(quiz_id)


def admin_list_quizzes() -> List[Dict[str, Any]]:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT id, title, subtitle, created_at
            FROM quizzes
            ORDER BY created_at DESC
            """
        )
        rows = cur.fetchall()

    return [{"id": r[0], "title": r[1], "subtitle": r[2], "created_at": r[3]} for r in rows]


def delete_quiz(quiz_id: int) -> None:
    """
    Удаляем викторину полностью:
    options -> questions -> results -> quizzes
    """
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            DELETE FROM options
            WHERE question_id IN (SELECT id FROM questions WHERE quiz_id=%s)
            """,
            (quiz_id,),
        )
        cur.execute("DELETE FROM questions WHERE quiz_id=%s", (quiz_id,))
        cur.execute("DELETE FROM results WHERE quiz_id=%s", (quiz_id,))
        cur.execute("DELETE FROM quizzes WHERE id=%s", (quiz_id,))
    db.commit()

def admin_get_quiz(quiz_id: int) -> Optional[Dict[str, Any]]:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, title, subtitle, image_path FROM quizzes WHERE id=%s",
            (quiz_id,)
        )
        row = cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "title": row[1], "subtitle": row[2], "image_path": row[3]}


def admin_update_quiz(quiz_id: int, title: str, subtitle: str, image_path: str | None) -> None:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            UPDATE quizzes
            SET title=%s, subtitle=%s, image_path=%s
            WHERE id=%s
            """,
            (title, subtitle, image_path, quiz_id)
        )
    db.commit()