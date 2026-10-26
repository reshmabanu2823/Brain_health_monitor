"""
CORTIA — SQLite Database Layer
================================
Drop this file into your project root as  database.py
Then import from it in main.py and any route file.

Tables created automatically on first run:
  - mri_scans        → MRI audit log
  - eeg_sessions     → EEG session recordings
  - ai_conversations → CORTIA AI chat threads
  - ai_messages      → Individual messages inside each thread
"""

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── Path ──────────────────────────────────────────────────────────────────────
# Creates a  logs/  folder next to this file if it doesn't exist
DB_DIR  = Path(os.getenv("BHM_LOG_DIR", str(Path(__file__).parent / "logs")))
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv("BHM_CORTIA_DB", str(DB_DIR / "cortia_ai.db")))


# ── Connection helper ─────────────────────────────────────────────────────────
def get_connection() -> sqlite3.Connection:
    """
    Returns a sqlite3 connection with:
      - Row factory so rows behave like dicts  (row["column_name"])
      - Foreign key enforcement on
      - WAL mode for concurrent reads during inference
    """
    target_path = Path(os.getenv("BHM_CORTIA_DB", str(DB_PATH)))
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


# ── Schema ────────────────────────────────────────────────────────────────────
def init_db() -> None:
    """
    Call this ONCE at app startup (inside your FastAPI lifespan or @app.on_event).
    Creates all tables if they don't already exist — safe to call every restart.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 1. MRI Scan Audit Log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mri_scans (
            id                  TEXT PRIMARY KEY,
            timestamp           TEXT NOT NULL,
            file_identifier     TEXT NOT NULL,
            classification      TEXT NOT NULL,        -- Glioma | Meningioma | Pituitary | No Tumor
            confidence          REAL NOT NULL,        -- 0.0 – 1.0
            diagnostic_flag     TEXT NOT NULL,        -- POS | NEG
            saliency_peak       REAL,
            saliency_area       REAL,
            saliency_center_x   REAL,
            saliency_center_y   REAL,
            model_backbone      TEXT DEFAULT 'EfficientNetV2-S',
            mode                TEXT DEFAULT 'research'   -- everyday | research
        )
    """)

    # 2. EEG Session Recordings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eeg_sessions (
            id                  TEXT PRIMARY KEY,
            started_at          TEXT NOT NULL,
            ended_at            TEXT,
            source              TEXT NOT NULL,        -- SIMULATED | HARDWARE
            duration_seconds    REAL DEFAULT 0,
            total_samples       INTEGER DEFAULT 0,
            status              TEXT DEFAULT 'recording',  -- recording | completed | error
            signal_quality      TEXT,                 -- Acceptable | Needs review | Insufficient quality
            notes               TEXT,
            -- Band power features (stored as JSON string)
            features_json       TEXT
        )
    """)

    # 3. CORTIA AI — Conversation Threads
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_conversations (
            id          TEXT PRIMARY KEY,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            title       TEXT DEFAULT 'New conversation',
            provider    TEXT DEFAULT 'local'   -- local | gemini | openai
        )
    """)

    # 4. CORTIA AI — Individual Messages
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_messages (
            id              TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
            created_at      TEXT NOT NULL,
            role            TEXT NOT NULL,   -- user | assistant
            content         TEXT NOT NULL,
            citations_json  TEXT             -- JSON list of citation strings
        )
    """)

    conn.commit()
    conn.close()
    print(f"[CORTIA DB] Initialised at {DB_PATH}")


# ── Utility ───────────────────────────────────────────────────────────────────
def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()

def new_id() -> str:
    return str(uuid.uuid4())


# ═══════════════════════════════════════════════════════════════════════════════
# MRI SCANS
# ═══════════════════════════════════════════════════════════════════════════════

def insert_mri_scan(
    file_identifier: str,
    classification: str,
    confidence: float,
    diagnostic_flag: str,
    saliency_peak: float = None,
    saliency_area: float = None,
    saliency_center_x: float = None,
    saliency_center_y: float = None,
    model_backbone: str = "EfficientNetV2-S",
    mode: str = "research",
) -> str:
    """Insert one MRI scan result. Returns the new scan id."""
    scan_id = new_id()
    conn = get_connection()
    conn.execute("""
        INSERT INTO mri_scans
            (id, timestamp, file_identifier, classification, confidence,
             diagnostic_flag, saliency_peak, saliency_area,
             saliency_center_x, saliency_center_y, model_backbone, mode)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        scan_id, now_utc(), file_identifier, classification,
        confidence, diagnostic_flag,
        saliency_peak, saliency_area,
        saliency_center_x, saliency_center_y,
        model_backbone, mode,
    ))
    conn.commit()
    conn.close()
    return scan_id


def get_mri_scans(limit: int = 50) -> list[dict]:
    """Return recent MRI scans, newest first."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM mri_scans
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_mri_scan(scan_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM mri_scans WHERE id = ?", (scan_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ═══════════════════════════════════════════════════════════════════════════════
# EEG SESSIONS
# ═══════════════════════════════════════════════════════════════════════════════

def start_eeg_session(source: str = "SIMULATED", notes: str = "", session_id: str = None) -> str:
    """Call when a new EEG recording begins. Returns session id."""
    session_id = session_id or new_id()
    conn = get_connection()
    conn.execute("""
        INSERT INTO eeg_sessions
            (id, started_at, source, status, notes)
        VALUES (?,?,?,?,?)
    """, (session_id, now_utc(), source, "recording", notes))
    conn.commit()
    conn.close()
    return session_id


def end_eeg_session(
    session_id: str,
    duration_seconds: float,
    total_samples: int,
    signal_quality: str,
    features_json: str = None,   # pass json.dumps(your_feature_dict)
) -> None:
    """Call when a recording stops."""
    conn = get_connection()
    row = conn.execute("SELECT id FROM eeg_sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        conn.execute("""
            INSERT INTO eeg_sessions
                (id, started_at, ended_at, source, duration_seconds, total_samples, status, signal_quality, features_json)
            VALUES (?, ?, ?, 'HARDWARE', ?, ?, 'completed', ?, ?)
        """, (session_id, now_utc(), now_utc(), duration_seconds, total_samples, signal_quality, features_json))
    else:
        conn.execute("""
            UPDATE eeg_sessions
            SET ended_at         = ?,
                status           = 'completed',
                duration_seconds = ?,
                total_samples    = ?,
                signal_quality   = ?,
                features_json    = ?
            WHERE id = ?
        """, (
            now_utc(), duration_seconds, total_samples,
            signal_quality, features_json, session_id,
        ))
    conn.commit()
    conn.close()


def get_eeg_sessions(limit: int = 50) -> list[dict]:
    """Return recent EEG sessions, newest first."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM eeg_sessions
        ORDER BY started_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_eeg_session(session_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM eeg_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ═══════════════════════════════════════════════════════════════════════════════
# CORTIA AI — CONVERSATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def create_conversation(
    title: str = "New conversation",
    provider: str = "local",
) -> str:
    """Create a new AI chat thread. Returns conversation id."""
    conv_id = new_id()
    ts = now_utc()
    conn = get_connection()
    conn.execute("""
        INSERT INTO ai_conversations (id, created_at, updated_at, title, provider)
        VALUES (?,?,?,?,?)
    """, (conv_id, ts, ts, title, provider))
    conn.commit()
    conn.close()
    return conv_id


def get_conversations(limit: int = 30) -> list[dict]:
    """Return recent conversations, newest first."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM ai_conversations
        ORDER BY updated_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_conversation_title(conversation_id: str, title: str) -> None:
    conn = get_connection()
    conn.execute("""
        UPDATE ai_conversations SET title = ?, updated_at = ?
        WHERE id = ?
    """, (title, now_utc(), conversation_id))
    conn.commit()
    conn.close()


def delete_conversation(conversation_id: str) -> None:
    """Deletes thread + all its messages (CASCADE)."""
    conn = get_connection()
    conn.execute("DELETE FROM ai_conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# CORTIA AI — MESSAGES
# ═══════════════════════════════════════════════════════════════════════════════

def insert_message(
    conversation_id: str,
    role: str,           # "user" or "assistant"
    content: str,
    citations: list[str] = None,
) -> str:
    """Add a message to a conversation. Returns message id."""
    import json
    msg_id = new_id()
    conn = get_connection()
    conn.execute("""
        INSERT INTO ai_messages
            (id, conversation_id, created_at, role, content, citations_json)
        VALUES (?,?,?,?,?,?)
    """, (
        msg_id, conversation_id, now_utc(), role, content,
        json.dumps(citations) if citations else None,
    ))
    # Also bump conversation updated_at
    conn.execute("""
        UPDATE ai_conversations SET updated_at = ? WHERE id = ?
    """, (now_utc(), conversation_id))
    conn.commit()
    conn.close()
    return msg_id


def get_messages(conversation_id: str) -> list[dict]:
    """Return all messages in a conversation, oldest first."""
    import json
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM ai_messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC
    """, (conversation_id,)).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["citations"] = json.loads(d["citations_json"]) if d["citations_json"] else []
        result.append(d)
    return result


def delete_message(message_id: str) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM ai_messages WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()
