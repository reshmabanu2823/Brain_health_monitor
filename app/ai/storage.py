"""SQLite persistence for CORTIA AI conversations with strict privacy boundaries."""
import json
import logging
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from .schemas import AnalysisReference, Citation

log = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ConversationStore:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cortia_conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cortia_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    citations_json TEXT,
                    references_json TEXT,
                    simulated_warning TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES cortia_conversations(id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_conv ON cortia_messages(conversation_id)")

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def create_conversation(self, title: str = "New Research Inquiry") -> str:
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO cortia_conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (conv_id, title[:100], now, now),
            )
        return conv_id

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        citations: Optional[List[Citation]] = None,
        references: Optional[List[AnalysisReference]] = None,
        simulated_warning: Optional[str] = None,
    ) -> str:
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        cit_json = json.dumps([c.model_dump() for c in citations]) if citations else None
        ref_json = json.dumps([r.model_dump() for r in references]) if references else None

        with self.connection() as conn:
            # Ensure conversation exists
            exists = conn.execute("SELECT id FROM cortia_conversations WHERE id = ?", (conversation_id,)).fetchone()
            if not exists:
                # Auto-generate title from first prompt
                title = content[:60] + "..." if len(content) > 60 else content
                conn.execute(
                    "INSERT INTO cortia_conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (conversation_id, title, now, now),
                )
            else:
                conn.execute(
                    "UPDATE cortia_conversations SET updated_at = ? WHERE id = ?",
                    (now, conversation_id),
                )

            conn.execute(
                """INSERT INTO cortia_messages (id, conversation_id, role, content, timestamp, citations_json, references_json, simulated_warning)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (msg_id, conversation_id, role, content, now, cit_json, ref_json, simulated_warning),
            )
        return msg_id

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            conv = conn.execute("SELECT * FROM cortia_conversations WHERE id = ?", (conversation_id,)).fetchone()
            if not conv:
                return None
            rows = conn.execute("SELECT * FROM cortia_messages WHERE conversation_id = ? ORDER BY rowid ASC", (conversation_id,)).fetchall()

        messages = []
        for r in rows:
            citations = [Citation(**c) for c in json.loads(r["citations_json"])] if r["citations_json"] else []
            references = [AnalysisReference(**a) for a in json.loads(r["references_json"])] if r["references_json"] else []
            messages.append({
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "timestamp": r["timestamp"],
                "citations": citations,
                "analysis_references": references,
                "simulated_warning": r["simulated_warning"],
            })

        return {
            "id": conv["id"],
            "title": conv["title"],
            "created_at": conv["created_at"],
            "updated_at": conv["updated_at"],
            "messages": messages,
        }

    def list_conversations(self, limit: int = 30) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute("""
                SELECT c.*, COUNT(m.id) as message_count
                FROM cortia_conversations c
                LEFT JOIN cortia_messages m ON m.conversation_id = c.id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def delete_conversation(self, conversation_id: str) -> bool:
        with self.connection() as conn:
            conn.execute("DELETE FROM cortia_messages WHERE conversation_id = ?", (conversation_id,))
            res = conn.execute("DELETE FROM cortia_conversations WHERE id = ?", (conversation_id,))
            return res.rowcount > 0

    def clear_all(self) -> bool:
        with self.connection() as conn:
            conn.execute("DELETE FROM cortia_messages")
            conn.execute("DELETE FROM cortia_conversations")
        return True
