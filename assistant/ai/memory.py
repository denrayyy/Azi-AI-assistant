"""SQLite-backed conversation memory."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple


from ai.ollama_client import ChatMessage


@dataclass(frozen=True)
class MemoryConfig:
    """Configuration for conversation persistence."""

    db_path: str
    max_history: int = 20
    system_prompt: str = (
        "You are a helpful desktop assistant. Keep responses concise and safe."
    )


class MemoryStore:
    """Persists conversation history in a local SQLite database."""

    def __init__(self, db_path: str, max_history: int = 20) -> None:
        self._config = MemoryConfig(db_path=db_path, max_history=max_history)
        self._ensure_db()

    def _ensure_db(self) -> None:
        db_file = Path(self._config.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self._config.db_path) as conn:
            conn.execute(
                ""
                "CREATE TABLE IF NOT EXISTS conversations ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  role TEXT NOT NULL,"
                "  content TEXT NOT NULL,"
                "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
            conn.commit()

    def save_message(self, role: str, content: str) -> None:
        if not content.strip():
            return

        with sqlite3.connect(self._config.db_path) as conn:
            conn.execute(
                "INSERT INTO conversations (role, content) VALUES (?, ?)",
                (role, content),
            )
            conn.commit()

    def load_recent(self) -> List[Tuple[str, str]]:
        with sqlite3.connect(self._config.db_path) as conn:
            rows = conn.execute(
                ""
                "SELECT role, content FROM conversations "
                "ORDER BY id DESC LIMIT ?"
                "",
                (self._config.max_history,),
            ).fetchall()

        return list(reversed(rows))

    def clear(self) -> None:
        with sqlite3.connect(self._config.db_path) as conn:
            conn.execute("DELETE FROM conversations")
            conn.commit()

    def build_context(self, user_text: str) -> Iterable[ChatMessage]:
        messages: List[ChatMessage] = [
            ChatMessage("system", self._config.system_prompt)
        ]
        for role, content in self.load_recent():
            messages.append(ChatMessage(role, content))
        messages.append(ChatMessage("user", user_text))
        return messages
