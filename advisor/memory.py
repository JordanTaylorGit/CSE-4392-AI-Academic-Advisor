"""Conversation state (spec req 6).

Short-term: the UI keeps the live message list for display and passes it back
into handle_message() each turn.
Long-term: every turn is appended to the chat_history table (spec req 7 —
advising/chat history is one of the required nonstructural stores; Person C
may also embed it into Chroma for "what did we discuss last week" recall).
"""

from . import db


def add_message(student_id: str, role: str, content: str) -> None:
    db.execute(
        "INSERT INTO chat_history (student_id, role, content) VALUES (:sid, :r, :c)",
        {"sid": student_id, "r": role, "c": content},
    )


def get_history(student_id: str, limit: int = 20) -> list[dict]:
    """Most recent `limit` messages, oldest first."""
    rows = db.query(
        "SELECT role, content, created_at FROM chat_history"
        " WHERE student_id = :sid ORDER BY id DESC LIMIT :lim",
        {"sid": student_id, "lim": limit},
    )
    return list(reversed(rows))
