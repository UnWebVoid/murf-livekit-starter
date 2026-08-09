"""
Persistent SQLite memory for Jan Sathi (Day 4).

Design principles:
- Only APPROVED fields are stored — enforced by an allowlist, not just a blocklist.
- Approved facts: schemes_checked, eligibility_answers, topics_asked.
- No sensitive financial credentials are ever persisted.
- The database file is at backend/data/jan_sathi_memory.db (excluded from git).
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("memory")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DB_DIR = Path(__file__).parent.parent / "data"
_DB_PATH = _DB_DIR / "jan_sathi_memory.db"

# ---------------------------------------------------------------------------
# Schema — only approved fact keys are ever stored (allowlist enforced below)
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_memory (
    user_id          TEXT PRIMARY KEY,
    name             TEXT,
    language_pref    TEXT NOT NULL DEFAULT 'hi',
    facts            TEXT NOT NULL DEFAULT '{}',
    last_interaction TEXT NOT NULL
);
"""

# Approved keys inside the 'facts' JSON blob.
# ONLY these keys are written — all others are silently stripped (safeguard 2).
APPROVED_FACT_KEYS: frozenset[str] = frozenset(
    {"schemes_checked", "eligibility_answers", "topics_asked"}
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _connect() -> sqlite3.Connection:
    """Open (and initialise) the SQLite database, creating the directory if needed."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def _sanitize_facts(raw: dict) -> dict:
    """Return a copy of *raw* containing only approved fact keys."""
    sanitized: dict = {}
    for key in APPROVED_FACT_KEYS:
        if key in raw:
            sanitized[key] = raw[key]
    # Ensure required sub-structures exist with correct types
    if "schemes_checked" in sanitized and not isinstance(sanitized["schemes_checked"], list):
        sanitized["schemes_checked"] = []
    if "eligibility_answers" in sanitized and not isinstance(sanitized["eligibility_answers"], dict):
        sanitized["eligibility_answers"] = {}
    if "topics_asked" in sanitized and not isinstance(sanitized["topics_asked"], list):
        sanitized["topics_asked"] = []
    return sanitized


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def db_lookup_user(user_id: str) -> dict | None:
    """Return the user record as a plain dict, or *None* if not found.

    Returned dict shape:
        {
            "user_id": str,
            "name": str | None,
            "language_pref": str,
            "facts": {
                "schemes_checked": list[str],
                "eligibility_answers": dict[str, str],
                "topics_asked": list[str],
            },
            "last_interaction": str,  # ISO-8601 UTC
        }
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT user_id, name, language_pref, facts, last_interaction "
            "FROM user_memory WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    if row is None:
        return None

    try:
        raw_facts = json.loads(row["facts"])
    except (json.JSONDecodeError, TypeError):
        raw_facts = {}

    return {
        "user_id": row["user_id"],
        "name": row["name"],
        "language_pref": row["language_pref"],
        "facts": _sanitize_facts(raw_facts),
        "last_interaction": row["last_interaction"],
    }


def db_save_user(
    user_id: str,
    name: str | None,
    language_pref: str,
    facts: dict,
) -> None:
    """Upsert a user record.

    Only approved fact keys are written (all others are silently dropped —
    this is the allowlist-based safeguard 2, enforced at the storage layer).

    Args:
        user_id: Stable caller identity from LiveKit participant identity.
        name: Caller's first name (never an ID number or credential).
        language_pref: e.g. 'hi', 'en', 'hinglish'.
        facts: Dict containing any of APPROVED_FACT_KEYS.
    """
    sanitized = _sanitize_facts(facts)
    now = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO user_memory (user_id, name, language_pref, facts, last_interaction)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name             = COALESCE(excluded.name, name),
                language_pref    = excluded.language_pref,
                facts            = excluded.facts,
                last_interaction = excluded.last_interaction
            """,
            (user_id, name, language_pref, json.dumps(sanitized), now),
        )
        conn.commit()

    # Only log a truncated ID — never log the full UUID in production
    logger.info("Memory saved for user_id=%.8s...", user_id)


def db_delete_user(user_id: str) -> None:
    """Permanently delete all saved memory for a user.

    Called when the user explicitly asks Jan Sathi to forget them.
    """
    with _connect() as conn:
        conn.execute("DELETE FROM user_memory WHERE user_id = ?", (user_id,))
        conn.commit()

    logger.info("Memory deleted for user_id=%.8s...", user_id)
