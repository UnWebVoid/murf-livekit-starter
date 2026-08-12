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
import re
import sqlite3
import uuid
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

CREATE TABLE IF NOT EXISTS escalations (
    reference_id     TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'open',
    urgency          TEXT NOT NULL DEFAULT 'high',
    language         TEXT NOT NULL DEFAULT 'hi',
    what_happened    TEXT NOT NULL,
    what_checked     TEXT NOT NULL,
    who_needs_help   TEXT NOT NULL,
    follow_up_pref   TEXT NOT NULL DEFAULT 'not specified',
    created_at       TEXT NOT NULL
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
    conn.executescript(_SCHEMA)
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


# ---------------------------------------------------------------------------
# Day 7 Escalation Storage & Sanitization API
# ---------------------------------------------------------------------------


def _sanitize_escalation_text(text: str | None) -> str:
    """Sanitize input text to strip passwords, OTPs, PINs, bank accounts, and card numbers.

    Rules:
    - 4-6 digit standalone numbers -> [REDACTED_CODE]
    - 10-16 digit standalone numbers -> [REDACTED_ACCOUNT_NUM]
    - Sensitive key-value pairs (e.g. pin=1234, password: xyz) -> [REDACTED_SENSITIVE_DATA]
    """
    if not text:
        return ""
    # Strip sensitive key-value pairs like pin=1234 or otp: 5678 or password: secret
    cleaned = re.sub(
        r"(?i)\b(pin|otp|cvv|password|passcode|secret)\b\s*[:=]?\s*\w+",
        r"\1: [REDACTED]",
        text,
    )
    # Strip standalone 4-6 digit numbers (OTPs / PINs)
    cleaned = re.sub(r"\b\d{4,6}\b", "[REDACTED_CODE]", cleaned)
    # Strip 10-16 digit numbers (Bank Account / Card / Aadhaar / PAN numbers)
    cleaned = re.sub(r"\b\d{10,16}\b", "[REDACTED_ACCOUNT_NUM]", cleaned)
    return cleaned.strip()


def db_create_escalation(
    user_id: str,
    what_happened: str,
    what_checked: str,
    who_needs_help: str | None = None,
    urgency: str = "high",
    language: str = "hi",
    follow_up_pref: str = "not specified",
) -> dict:
    """Create and persist a sanitized human help escalation record (Day 7).

    Returns structured dict with reference_id, status, created_at, urgency, language, etc.
    """
    valid_urgencies = {"low", "medium", "high", "emergency"}
    clean_urgency = (
        urgency.strip().lower()
        if urgency and urgency.strip().lower() in valid_urgencies
        else "high"
    )
    clean_lang = language.strip().lower() if language else "hi"

    # Generate unique Reference ID: ESC-YYYYMMDD-XXXX (e.g. ESC-20260812-7A9B)
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:6].upper()
    reference_id = f"ESC-{date_part}-{short_uuid}"

    clean_what_happened = _sanitize_escalation_text(what_happened)
    clean_what_checked = _sanitize_escalation_text(what_checked)
    clean_who = _sanitize_escalation_text(who_needs_help or "Anonymous Caller")
    clean_follow_up = _sanitize_escalation_text(follow_up_pref or "not specified")
    now = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO escalations (
                reference_id, user_id, status, urgency, language,
                what_happened, what_checked, who_needs_help, follow_up_pref, created_at
            )
            VALUES (?, ?, 'open', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reference_id,
                user_id,
                clean_urgency,
                clean_lang,
                clean_what_happened,
                clean_what_checked,
                clean_who,
                clean_follow_up,
                now,
            ),
        )
        conn.commit()

    logger.info(
        "Escalation created ref_id=%s urgency=%s user_id=%.8s...",
        reference_id,
        clean_urgency,
        user_id,
    )
    return {
        "reference_id": reference_id,
        "user_id": user_id,
        "status": "open",
        "urgency": clean_urgency,
        "language": clean_lang,
        "what_happened": clean_what_happened,
        "what_checked": clean_what_checked,
        "who_needs_help": clean_who,
        "follow_up_pref": clean_follow_up,
        "created_at": now,
    }


def db_list_escalations() -> list[dict]:
    """Retrieve all escalation records sorted by created_at DESC."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT reference_id, user_id, status, urgency, language, "
            "what_happened, what_checked, who_needs_help, follow_up_pref, created_at "
            "FROM escalations ORDER BY created_at DESC"
        ).fetchall()

    return [dict(row) for row in rows]


def db_update_escalation_status(reference_id: str, status: str) -> bool:
    """Update status of an escalation record (e.g. 'open' -> 'resolved')."""
    valid_statuses = {"open", "in_progress", "resolved"}
    if status not in valid_statuses:
        return False

    with _connect() as conn:
        cur = conn.execute(
            "UPDATE escalations SET status = ? WHERE reference_id = ?",
            (status, reference_id),
        )
        conn.commit()
        return cur.rowcount > 0

