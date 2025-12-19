from typing import Optional, Dict, Any, List
from services.db import get_db

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
                (f"%{q}%",)
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
    return [
        {"id": r[0], "title": r[1], "subtitle": r[2], "image_path": r[3]}
        for r in rows
    ]

def get_quiz(quiz_id: int) -> Optional[Dict[str, Any]]:
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id, title, subtitle, image_path FROM quizzes WHERE id=%s", (quiz_id,))
        row = cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "title": row[1], "subtitle": row[2], "image_path": row[3]}

def get_quiz_questions_with_options(quiz_id: int) -> List[Dict[str, Any]]:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT q.id, q.text, q.position
            FROM questions q
            WHERE q.quiz_id=%s
            ORDER BY q.position ASC, q.id ASC
            """,
            (quiz_id,)
        )
        qrows = cur.fetchall()

        questions = []
        for qid, qtext, pos in qrows:
            cur.execute(
                """
                SELECT id, text
                FROM options
                WHERE question_id=%s
                ORDER BY id ASC
                """,
                (qid,)
            )
            orows = cur.fetchall()
            questions.append({
                "id": qid,
                "text": qtext,
                "position": pos,
                "options": [{"id": oid, "text": otext} for oid, otext in orows]
            })
    return questions

def grade_quiz(quiz_id: int, answers: dict) -> tuple[int, int]:
    """
    answers: {question_id(str/int): option_id(str/int)}
    Возвращает (score, total_questions)
    """
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT id FROM questions WHERE quiz_id=%s",
            (quiz_id,)
        )
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
                (int(chosen), qid)
            )
            row = cur.fetchone()
            if row and row[0] is True:
                score += 1
    return score, total

def save_result(user_id: int, quiz_id: int, score: int, total: int) -> None:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO results (user_id, quiz_id, score, total)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, quiz_id, score, total)
        )
    db.commit()

def get_leaderboard(limit: int = 50):
    """
    Рейтинг по сумме очков по всем попыткам.
    """
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT u.id, u.username, COALESCE(SUM(r.points), 0) AS points
            FROM users u
            LEFT JOIN results r ON r.user_id = u.id
            GROUP BY u.id, u.username
            ORDER BY points DESC, u.username ASC
            LIMIT %s
            """,
            (limit,)
        )
        rows = cur.fetchall()

    return [{"user_id": r[0], "username": r[1], "points": int(r[2])} for r in rows]


def create_quiz(created_by: int, title: str, subtitle: str, image_path: str | None,
               questions_payload: list) -> int:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO quizzes (title, subtitle, image_path, created_by)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (title, subtitle, image_path, created_by)
        )
        quiz_id = cur.fetchone()[0]

        for idx, q in enumerate(questions_payload, start=1):
            cur.execute(
                """
                INSERT INTO questions (quiz_id, text, position, image_path, explanation)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (quiz_id, q["text"], idx, q.get("image_path"), q.get("explanation"))
            )
            qid = cur.fetchone()[0]

            correct = int(q["correct"])
            for i, opt_text in enumerate(q["options"], start=1):
                cur.execute(
                    """
                    INSERT INTO options (question_id, text, is_correct)
                    VALUES (%s, %s, %s)
                    """,
                    (qid, opt_text, (i == correct))
                )

    db.commit()
    return int(quiz_id)



def save_result(user_id: int, quiz_id: int, score: int, total: int,
                duration_seconds: int | None, points: int) -> int:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO results (user_id, quiz_id, score, total, duration_seconds, points)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, quiz_id, score, total, duration_seconds, points)
        )
        rid = cur.fetchone()[0]
    db.commit()
    return int(rid)

def get_result(result_id: int):
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
            (result_id,)
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
    Место попытки среди всех попыток ЭТОЙ викторины по points DESC, затем duration ASC (быстрее — лучше).
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
            ORDER BY points DESC NULLS LAST, duration_seconds ASC NULLS LAST, created_at ASC
            """,
            (quiz_id,)
        )
        ids = [x[0] for x in cur.fetchall()]

    return ids.index(result_id) + 1 if result_id in ids else 0


