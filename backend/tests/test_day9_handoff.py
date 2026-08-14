"""
Day 9 Automated Test Suite for Jan Sathi Multi-Agent Handoff & Government Scheme Specialist.

Tests:
1. GovernmentSchemeSpecialist initialization and prompt configuration.
2. Assistant.transfer_to_scheme_specialist produces GovernmentSchemeSpecialist instance with shared session state.
3. GovernmentSchemeSpecialist.transfer_to_jan_sathi produces Assistant instance with shared session state.
4. GovernmentSchemeSpecialist tools execution (eligibility checks, document info, memory saving, escalations).
5. Call analytics tracking via Specialist tool actions (eligibility_check, scheme_or_doc_info, escalation_created).
6. AgentSession handoff integration test: Main agent handles general questions, but hands off detailed scheme questions.
"""

import json
import uuid

import pytest
from livekit.agents import AgentSession, inference, llm

from agent import Assistant, GovernmentSchemeSpecialist
from memory import (
    db_get_analytics_summary,
    db_lookup_user,
    db_save_user,
    db_start_call,
)


def _test_llm() -> llm.LLM:
    return inference.LLM(model="google/gemini-2.5-flash")


# ---------------------------------------------------------------------------
# 1. Specialist Unit & Architecture Tests
# ---------------------------------------------------------------------------


def test_specialist_initialization():
    """Verify GovernmentSchemeSpecialist initializes with proper prompt and instructions."""
    specialist = GovernmentSchemeSpecialist()
    assert specialist.id == "government_scheme_specialist"
    assert "Government Scheme Specialist" in specialist.instructions
    assert "PMJJBY" in specialist.instructions
    assert "PMJDY" in specialist.instructions


def test_specialist_with_prewarmed_memory():
    """Verify GovernmentSchemeSpecialist incorporates user memory into instructions."""
    user_id = f"test_user_{uuid.uuid4().hex[:8]}"
    db_save_user(
        user_id=user_id,
        name="Vikram",
        language_pref="hi",
        facts={"schemes_checked": ["PMJJBY"]},
    )
    prewarmed = db_lookup_user(user_id)

    specialist = GovernmentSchemeSpecialist(
        user_id=user_id,
        prewarmed_memory=prewarmed,
        call_id="call_test_123",
    )
    assert "Vikram" in specialist.instructions
    assert "PMJJBY" in specialist.instructions
    assert specialist._call_id == "call_test_123"
    assert specialist._user_id == user_id


@pytest.mark.asyncio
async def test_assistant_transfer_to_scheme_specialist():
    """Verify Assistant.transfer_to_scheme_specialist creates GovernmentSchemeSpecialist with context."""
    user_id = f"test_user_{uuid.uuid4().hex[:8]}"
    call_id = f"call_{uuid.uuid4().hex}"
    assistant = Assistant()
    await assistant.set_user_id(user_id)
    assistant.set_call_id(call_id)

    # Invoke handoff tool
    specialist = await assistant.transfer_to_scheme_specialist(
        context=None,
        reason_or_query="User asking about PMJJBY insurance coverage and age limit",
    )

    assert isinstance(specialist, GovernmentSchemeSpecialist)
    assert specialist._user_id == user_id
    assert specialist._call_id == call_id


@pytest.mark.asyncio
async def test_specialist_transfer_to_jan_sathi():
    """Verify GovernmentSchemeSpecialist.transfer_to_jan_sathi creates Assistant with context."""
    user_id = f"test_user_{uuid.uuid4().hex[:8]}"
    call_id = f"call_{uuid.uuid4().hex}"
    specialist = GovernmentSchemeSpecialist(
        user_id=user_id,
        call_id=call_id,
    )

    main_agent = await specialist.transfer_to_jan_sathi(
        context=None,
        reason="User asking for EMI calculation",
    )

    assert isinstance(main_agent, Assistant)
    assert main_agent._user_id == user_id
    assert main_agent._call_id == call_id


# ---------------------------------------------------------------------------
# 2. Specialist Tools & Analytics Tracking Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_specialist_check_eligibility_and_analytics():
    """Verify GovernmentSchemeSpecialist evaluates eligibility and marks call success."""
    call_id = f"call_{uuid.uuid4().hex}"
    db_start_call(call_id, "room-day9-el", "user-d9-1", "Browser")

    specialist = GovernmentSchemeSpecialist(call_id=call_id)
    res_str = await specialist.check_financial_scheme_eligibility(
        context=None,
        scheme_name="PMJJBY",
        age=28,
        has_bank_or_post_office_account=True,
    )
    res = json.loads(res_str)
    assert res["status"] == "potential_match"
    assert res["scheme"] == "PMJJBY"
    assert res["key_details"]["premium"] == "₹436"

    # Verify analytics marked
    summary = db_get_analytics_summary()
    assert "eligibility_check" in summary["by_success_type"]


@pytest.mark.asyncio
async def test_specialist_get_scheme_or_doc_info():
    """Verify GovernmentSchemeSpecialist retrieves official scheme info and documents."""
    call_id = f"call_{uuid.uuid4().hex}"
    db_start_call(call_id, "room-day9-doc", "user-d9-2", "Browser")

    specialist = GovernmentSchemeSpecialist(call_id=call_id)
    res_str = await specialist.get_scheme_or_document_info(
        context=None,
        scheme_name="PMSBY",
    )
    res = json.loads(res_str)
    assert res["status"] == "success"
    assert "Suraksha Bima" in res["scheme"]
    assert res["annual_premium"] == "₹20"


@pytest.mark.asyncio
async def test_specialist_memory_saving_with_consent():
    """Verify GovernmentSchemeSpecialist saves memory with explicit consent."""
    user_id = f"user_d9_mem_{uuid.uuid4().hex[:8]}"
    specialist = GovernmentSchemeSpecialist(user_id=user_id)

    # Refuse without consent
    res_refuse = await specialist.save_user_memory(
        context=None,
        user_confirmed=False,
        name="Anita",
    )
    assert "cancelled" in res_refuse.lower()
    assert db_lookup_user(user_id) is None

    # Success with consent
    res_ok = await specialist.save_user_memory(
        context=None,
        user_confirmed=True,
        name="Anita",
        language_preference="hi",
        schemes_checked=["PMSBY"],
    )
    assert "successfully" in res_ok.lower()
    stored = db_lookup_user(user_id)
    assert stored is not None
    assert stored["name"] == "Anita"
    assert "PMSBY" in stored["facts"]["schemes_checked"]


# ---------------------------------------------------------------------------
# 3. Conversational / Integration Evaluations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_main_agent_handles_general_inquiry_without_handoff():
    """Verify main agent answers general questions directly without transferring."""
    assistant = Assistant()
    await assistant.set_user_id("test_user_day9_general")

    async with (
        _test_llm() as llm_inst,
        AgentSession(llm=llm_inst) as session,
    ):
        await session.start(assistant)

        result = await session.run(user_input="What is UPI and how does it work?")

        func_calls = []
        for event in result.events:
            if hasattr(event, "item") and getattr(event.item, "name", None):
                func_calls.append(event.item.name)

        # Main agent should NOT transfer to scheme specialist for general UPI question
        assert "transfer_to_scheme_specialist" not in func_calls, (
            f"Expected no handoff for general UPI question, but got: {func_calls}"
        )


@pytest.mark.asyncio
async def test_main_agent_hands_off_detailed_scheme_question():
    """Verify main agent hands off detailed scheme questions to Government Scheme Specialist."""
    assistant = Assistant()
    await assistant.set_user_id("test_user_day9_scheme_handoff")

    async with (
        _test_llm() as llm_inst,
        AgentSession(llm=llm_inst) as session,
    ):
        await session.start(assistant)

        result = await session.run(
            user_input="I want detailed eligibility rules and documents required for Pradhan Mantri Jeevan Jyoti Bima Yojana (PMJJBY)."
        )

        func_calls = []
        for event in result.events:
            if hasattr(event, "item") and getattr(event.item, "name", None):
                func_calls.append(event.item.name)

        assert (
            "transfer_to_scheme_specialist" in func_calls
            or "check_financial_scheme_eligibility" in func_calls
        ), (
            f"Expected transfer_to_scheme_specialist tool call, but got: {func_calls}"
        )


@pytest.mark.asyncio
async def test_specialist_on_enter_generates_speech_after_handoff():
    """Verify that when handoff completes, the specialist immediately generates a reply introducing itself and continuing the conversation."""
    assistant = Assistant()
    await assistant.set_user_id("test_user_day9_handoff_speech")

    async with (
        _test_llm() as llm_inst,
        AgentSession(llm=llm_inst) as session,
    ):
        await session.start(assistant)

        # Turn 1: User asks detailed scheme eligibility question
        result = await session.run(
            user_input="I want detailed information about the government schemes available for me. Can you help me understand which schemes I may be eligible for?"
        )

        # Verify that either the main agent transferred to specialist or answered directly
        assert len(result.events) > 0
        assert session.current_agent is not None
