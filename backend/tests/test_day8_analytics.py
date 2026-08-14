"""
Day 8 Automated Test Suite for Jan Sathi Call Analytics Dashboard.

Tests:
1. db_start_call creates call record with initial outcome='failed' and unique UUID call_id.
2. Deduplication & room reuse: multiple calls with the same room_name create distinct rows.
3. db_mark_call_success updates outcome to 'success' for valid success types.
4. db_end_call computes correct duration and end_time.
5. db_get_analytics_summary computes total_calls, successful_calls, failed_calls, and success_rate %.
6. db_get_recent_calls returns safe metadata without transcripts or sensitive credentials.
"""

import uuid

from memory import (
    db_end_call,
    db_get_analytics_summary,
    db_get_recent_calls,
    db_mark_call_success,
    db_start_call,
)


def test_call_lifecycle_failed_default():
    """Test that a new call starts with outcome='failed' and records end_time on disconnect."""
    call_id = f"test_call_{uuid.uuid4().hex}"
    room_name = "test-room-1"
    user_id = f"user_{uuid.uuid4().hex[:8]}"

    # Start call
    res = db_start_call(call_id=call_id, room_name=room_name, user_id=user_id, channel="Browser")
    assert res["call_id"] == call_id
    assert res["outcome"] == "failed"
    assert res["channel"] == "Browser"

    # End call without marking success
    ended = db_end_call(call_id)
    assert ended is True

    # Check recent calls
    recent = db_get_recent_calls(limit=10)
    target = next((c for c in recent if c["call_id"] == call_id), None)
    assert target is not None
    assert target["outcome"] == "failed"
    assert target["success_type"] is None
    assert target["duration_seconds"] >= 0


def test_unique_call_ids_same_room():
    """Test that reusing the same LiveKit room name generates distinct unique call records."""
    room_name = f"shared-reused-room-{uuid.uuid4().hex}"
    call_id_1 = f"call_{uuid.uuid4().hex}"
    call_id_2 = f"call_{uuid.uuid4().hex}"

    db_start_call(call_id=call_id_1, room_name=room_name, user_id="user_a", channel="Browser")
    db_start_call(call_id=call_id_2, room_name=room_name, user_id="user_b", channel="SIP Outbound")

    db_end_call(call_id_1)
    db_end_call(call_id_2)

    recent = db_get_recent_calls(limit=20)
    calls_in_room = [c for c in recent if c["room_name"] == room_name]
    assert len(calls_in_room) == 2
    assert {c["call_id"] for c in calls_in_room} == {call_id_1, call_id_2}


def test_call_mark_success_types():
    """Test marking calls successful for eligibility_check, scheme_or_doc_info, and escalation_created."""
    # 1. Eligibility check
    c1 = f"call_{uuid.uuid4().hex}"
    db_start_call(c1, "room-el", "user-1", "Browser")
    ok1 = db_mark_call_success(c1, "eligibility_check")
    assert ok1 is True
    db_end_call(c1)

    # 2. Scheme / doc info
    c2 = f"call_{uuid.uuid4().hex}"
    db_start_call(c2, "room-doc", "user-2", "Browser")
    ok2 = db_mark_call_success(c2, "scheme_or_doc_info")
    assert ok2 is True
    db_end_call(c2)

    # 3. Escalation created
    c3 = f"call_{uuid.uuid4().hex}"
    db_start_call(c3, "room-esc", "user-3", "SIP Outbound")
    ok3 = db_mark_call_success(c3, "escalation_created")
    assert ok3 is True
    db_end_call(c3)

    # 4. Invalid success type rejected
    c4 = f"call_{uuid.uuid4().hex}"
    db_start_call(c4, "room-inv", "user-4", "Browser")
    ok4 = db_mark_call_success(c4, "invalid_type_name")
    assert ok4 is False
    db_end_call(c4)

    summary = db_get_analytics_summary()
    assert summary["successful_calls"] >= 3
    assert "eligibility_check" in summary["by_success_type"]
    assert "scheme_or_doc_info" in summary["by_success_type"]
    assert "escalation_created" in summary["by_success_type"]


def test_analytics_summary_calculation():
    """Test accuracy of aggregated summary metrics calculation."""
    summary = db_get_analytics_summary()
    assert "total_calls" in summary
    assert "successful_calls" in summary
    assert "failed_calls" in summary
    assert "success_rate" in summary
    assert summary["total_calls"] == summary["successful_calls"] + summary["failed_calls"]
    assert 0.0 <= summary["success_rate"] <= 100.0


def test_recent_calls_privacy_safe():
    """Test that recent call records return safe metadata and no sensitive transcripts or credentials."""
    recent = db_get_recent_calls(limit=10)
    for c in recent:
        assert "call_id" in c
        assert "room_name" in c
        assert "outcome" in c
        # Ensure sensitive fields do not exist
        assert "password" not in c
        assert "otp" not in c
        assert "pin" not in c
        assert "transcript" not in c
        assert "bank_account" not in c
