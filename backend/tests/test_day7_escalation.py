"""
Day 7 Test Suite for Jan Sathi Human Help / Escalation System.

Tests:
1. Suspected fraud conversation with explicit user permission:
   - Agent recognizes fraud / escalation need.
   - Asks permission before creating escalation.
   - Escalation is created only after explicit permission.
   - Reference ID is generated (ESC-YYYYMMDD-XXXX).
2. Normal scheme conversation:
   - No escalation is created.
3. User refuses permission:
   - Agent asks permission.
   - User says no.
   - No escalation is created in database.
4. Storage Layer Sanitization:
   - Sensitive financial numbers (OTPs, PINs, card/account numbers) are redacted.
"""

import json
import pytest
from livekit.agents import AgentSession, inference, llm

from agent import Assistant
from memory import (
    db_create_escalation,
    db_list_escalations,
)


def _test_llm() -> llm.LLM:
    return inference.LLM(model="google/gemini-2.5-flash")


# ---------------------------------------------------------------------------
# 1. Direct Storage Layer & Sanitization Unit Tests
# ---------------------------------------------------------------------------


def test_db_create_escalation_sanitization():
    """Verify that passwords, PINs, OTPs, and bank account/card numbers are sanitized."""
    user_id = "test_user_day7_sanitization"
    what_happened = "I received a call asking for PIN 4920 and OTP 883920 for account 9876543210123."
    what_checked = "Checked UPI safety rules and warned about card 1122334455667788."

    record = db_create_escalation(
        user_id=user_id,
        what_happened=what_happened,
        what_checked=what_checked,
        who_needs_help="Test Caller",
        urgency="high",
        language="hi",
        follow_up_pref="phone call",
    )

    assert record["status"] == "open"
    assert record["reference_id"].startswith("ESC-")
    assert record["urgency"] == "high"

    # Verify sensitive data was redacted
    assert "4920" not in record["what_happened"]
    assert "883920" not in record["what_happened"]
    assert "9876543210123" not in record["what_happened"]
    assert "1122334455667788" not in record["what_checked"]
    assert "[REDACTED" in record["what_happened"]

    # Verify record appears in db_list_escalations()
    all_escalations = db_list_escalations()
    ref_ids = [e["reference_id"] for e in all_escalations]
    assert record["reference_id"] in ref_ids


@pytest.mark.asyncio
async def test_create_escalation_tool_refuses_without_permission():
    """Verify that create_escalation function tool refuses if user_confirmed=False."""
    assistant = Assistant()
    await assistant.set_user_id("test_user_day7_tool_refusal")

    res_str = await assistant.create_escalation(
        context=None,
        user_confirmed=False,
        what_happened="Suspected unauthorized withdrawal",
        what_checked="Explained helpline 1930",
    )
    res_data = json.loads(res_str)
    assert res_data["status"] == "refused"
    assert "permission was not granted" in res_data["reason"].lower()


@pytest.mark.asyncio
async def test_create_escalation_tool_success_with_permission():
    """Verify that create_escalation function tool succeeds when user_confirmed=True."""
    assistant = Assistant()
    await assistant.set_user_id("test_user_day7_tool_success")

    res_str = await assistant.create_escalation(
        context=None,
        user_confirmed=True,
        what_happened="Unauthorized UPI transaction of 5000 rupees",
        what_checked="Explained 1930 Cyber Crime Helpline and bank card block procedure",
        urgency="emergency",
        language="hi",
        preferred_follow_up="phone call",
    )
    res_data = json.loads(res_str)
    assert res_data["status"] == "open"
    assert res_data["reference_id"].startswith("ESC-")
    assert res_data["urgency"] == "emergency"


# ---------------------------------------------------------------------------
# 2. Agent Turn Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_fraud_escalation_with_user_permission():
    """Verify agent workflow when user reports fraud and agrees to escalation."""
    assistant = Assistant()
    await assistant.set_user_id("test_user_day7_fraud_perm")

    async with (
        _test_llm() as llm_inst,
        AgentSession(llm=llm_inst) as session,
    ):
        await session.start(assistant)

        # Turn 1: User reports fraud
        result1 = await session.run(
            user_input="Someone deducted 5000 rupees from my bank account via fraudulent UPI request! Can you create a help request for me?"
        )

        # Agent should explain and ask for permission, or call tool if user explicitly asked in input
        # Turn 2: User explicitly confirms permission
        result2 = await session.run(
            user_input="Yes, I give you permission to create the escalation request and share the summary with a human helper."
        )

        func_calls = []
        for event in result2.events:
            if hasattr(event, "item") and getattr(event.item, "name", None):
                func_calls.append(event.item.name)

        assert "create_escalation" in func_calls, (
            f"Expected create_escalation tool call after explicit user confirmation, got: {func_calls}"
        )


@pytest.mark.asyncio
async def test_agent_fraud_escalation_user_refuses_permission():
    """Verify that when user refuses permission, NO escalation is created."""
    assistant = Assistant()
    await assistant.set_user_id("test_user_day7_refusal")

    initial_count = len(db_list_escalations())

    async with (
        _test_llm() as llm_inst,
        AgentSession(llm=llm_inst) as session,
    ):
        await session.start(assistant)

        # User reports fraud but explicitly refuses saving/escalation
        result = await session.run(
            user_input="I think someone tried to scam me on UPI, but NO, do not create any escalation or help request and do not share my info with anyone."
        )

        func_calls = []
        for event in result.events:
            if hasattr(event, "item") and getattr(event.item, "name", None):
                func_calls.append(event.item.name)

        assert "create_escalation" not in func_calls, (
            f"create_escalation tool should NOT be called when user explicitly refuses, got: {func_calls}"
        )

    # Verify database count did not increase for this user
    final_count = len(db_list_escalations())
    assert final_count == initial_count


@pytest.mark.asyncio
async def test_agent_normal_scheme_inquiry_no_escalation():
    """Verify that a normal scheme query does NOT trigger escalation."""
    assistant = Assistant()
    await assistant.set_user_id("test_user_day7_scheme_no_escalation")

    async with (
        _test_llm() as llm_inst,
        AgentSession(llm=llm_inst) as session,
    ):
        await session.start(assistant)

        result = await session.run(
            user_input="What is the minimum age to enroll in Pradhan Mantri Jeevan Jyoti Bima Yojana (PMJJBY)?"
        )

        func_calls = []
        for event in result.events:
            if hasattr(event, "item") and getattr(event.item, "name", None):
                func_calls.append(event.item.name)

        assert "create_escalation" not in func_calls, (
            f"Normal scheme inquiry must NOT call create_escalation, got: {func_calls}"
        )
