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

CREATE TABLE IF NOT EXISTS calls (
    call_id          TEXT PRIMARY KEY,
    room_name        TEXT NOT NULL,
    user_id          TEXT NOT NULL,
    channel          TEXT NOT NULL DEFAULT 'Browser',
    start_time       TEXT NOT NULL,
    end_time         TEXT,
    duration_seconds INTEGER DEFAULT 0,
    outcome          TEXT NOT NULL DEFAULT 'failed',
    success_type     TEXT
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


# ---------------------------------------------------------------------------
# Day 8 Call Analytics Storage & Metrics API
# ---------------------------------------------------------------------------


def db_start_call(
    call_id: str,
    room_name: str,
    user_id: str,
    channel: str = "Browser",
) -> dict:
    """Record initial call session start in SQLite database.

    Initial state is 'failed' until an explicit success condition is met.
    A unique call_id (UUID) guarantees 1 session = 1 row in SQLite.
    """
    now = datetime.now(timezone.utc).isoformat()
    clean_channel = "SIP Outbound" if "sip" in channel.lower() or "outbound" in channel.lower() else "Browser"

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO calls (call_id, room_name, user_id, channel, start_time, outcome)
            VALUES (?, ?, ?, ?, ?, 'failed')
            ON CONFLICT(call_id) DO UPDATE SET
                room_name  = excluded.room_name,
                user_id    = excluded.user_id,
                channel    = excluded.channel,
                start_time = excluded.start_time
            """,
            (call_id, room_name, user_id, clean_channel, now),
        )
        conn.commit()

    logger.info("Call started call_id=%s room=%s channel=%s user_id=%.8s...", call_id, room_name, clean_channel, user_id)
    return {
        "call_id": call_id,
        "room_name": room_name,
        "user_id": user_id,
        "channel": clean_channel,
        "start_time": now,
        "outcome": "failed",
        "success_type": None,
    }


def db_mark_call_success(call_id: str, success_type: str) -> bool:
    """Mark a call session outcome as 'success' when an explicit completion condition occurs.

    Allowed success_types:
    - 'eligibility_check': user completes scheme eligibility evaluation
    - 'scheme_or_doc_info': user explicitly requests and receives scheme/doc information
    - 'escalation_created': user successfully creates human-help escalation
    """
    valid_types = {"eligibility_check", "scheme_or_doc_info", "escalation_created"}
    if success_type not in valid_types:
        logger.warning("db_mark_call_success: Invalid success_type '%s'", success_type)
        return False

    with _connect() as conn:
        cur = conn.execute(
            "UPDATE calls SET outcome = 'success', success_type = ? WHERE call_id = ?",
            (success_type, call_id),
        )
        conn.commit()
        success = cur.rowcount > 0

    if success:
        logger.info("Call marked SUCCESS call_id=%s type=%s", call_id, success_type)
    return success


def db_end_call(call_id: str) -> bool:
    """Record call disconnect/teardown timestamp and total duration in seconds."""
    now_dt = datetime.now(timezone.utc)
    now_str = now_dt.isoformat()

    with _connect() as conn:
        row = conn.execute("SELECT start_time FROM calls WHERE call_id = ?", (call_id,)).fetchone()
        if not row or not row["start_time"]:
            return False

        try:
            start_dt = datetime.fromisoformat(row["start_time"])
            duration = max(0, int((now_dt - start_dt).total_seconds()))
        except Exception:
            duration = 0

        cur = conn.execute(
            "UPDATE calls SET end_time = ?, duration_seconds = ? WHERE call_id = ?",
            (now_str, duration, call_id),
        )
        conn.commit()
        return cur.rowcount > 0


def db_get_analytics_summary() -> dict:
    """Return aggregated real-call analytics metrics from SQLite."""
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
        success = conn.execute("SELECT COUNT(*) FROM calls WHERE outcome = 'success'").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM calls WHERE outcome = 'failed'").fetchone()[0]

        type_rows = conn.execute(
            "SELECT success_type, COUNT(*) as cnt FROM calls WHERE outcome = 'success' GROUP BY success_type"
        ).fetchall()
        by_type = {row["success_type"]: row["cnt"] for row in type_rows if row["success_type"]}

        channel_rows = conn.execute(
            "SELECT channel, COUNT(*) as cnt FROM calls GROUP BY channel"
        ).fetchall()
        by_channel = {row["channel"]: row["cnt"] for row in channel_rows}

    rate = round((success / total * 100), 1) if total > 0 else 0.0

    return {
        "total_calls": total,
        "successful_calls": success,
        "failed_calls": failed,
        "success_rate": rate,
        "by_success_type": by_type,
        "by_channel": by_channel,
    }


def db_get_recent_calls(limit: int = 50) -> list[dict]:
    """Return recent calls sorted by start_time DESC containing only safe metadata.

    Excludes transcripts, PINs, OTPs, passwords, and sensitive personal information.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT call_id, room_name, user_id, channel, start_time, end_time,
                   duration_seconds, outcome, success_type
            FROM calls
            ORDER BY start_time DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        # Ensure user_id is presented as safe truncated identity if UUID
        uid = d.get("user_id", "")
        if len(uid) > 12 and "-" in uid:
            d["user_id_safe"] = f"{uid[:8]}..."
        else:
            d["user_id_safe"] = uid
        result.append(d)

    return result


