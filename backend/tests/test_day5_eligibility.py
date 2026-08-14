"""
Day 5 Test Suite for Jan Sathi Scheme Eligibility Tool (check_financial_scheme_eligibility).

Tests:
1. Dataset evaluation: potential_match for PMJJBY, PMSBY, PMJDY.
2. Dataset evaluation: does_not_meet_criteria for out-of-range inputs.
3. Dataset evaluation: insufficient_information when required inputs missing.
4. Graceful failure path testing with simulate_failure=True.
5. Live agent tool invocation on eligibility intent vs generic intent.
6. Day 4 memory persistence regression checks.
"""

import json

import pytest
from livekit.agents import AgentSession, inference, llm

from agent import Assistant
from memory import (
    APPROVED_FACT_KEYS,
    db_delete_user,
    db_lookup_user,
    db_save_user,
)
from schemes_data import LAST_VERIFIED_DATE, evaluate_scheme_eligibility


def _test_llm() -> llm.LLM:
    return inference.LLM(model="google/gemini-2.5-flash")


# ---------------------------------------------------------------------------
# 1. Dataset Unit Tests
# ---------------------------------------------------------------------------

def test_evaluate_scheme_eligibility_potential_match():
    # PMJJBY match
    res_pmjjby = evaluate_scheme_eligibility(
        scheme_name="PMJJBY",
        age=25,
        has_bank_or_post_office_account=True,
    )
    assert res_pmjjby["status"] == "potential_match"
    assert res_pmjjby["scheme"] == "PMJJBY"
    assert res_pmjjby["key_details"]["premium"] == "₹436"
    assert "2 lakh" in res_pmjjby["key_details"]["cover"].lower()
    assert res_pmjjby["last_verified"] == LAST_VERIFIED_DATE
    assert "locally curated dataset" in res_pmjjby["disclaimer"].lower()

    # PMSBY match
    res_pmsby = evaluate_scheme_eligibility(
        scheme_name="PMSBY",
        age=60,
        has_bank_or_post_office_account=True,
    )
    assert res_pmsby["status"] == "potential_match"
    assert res_pmsby["scheme"] == "PMSBY"
    assert res_pmsby["key_details"]["premium"] == "₹20"
    assert res_pmsby["last_verified"] == LAST_VERIFIED_DATE

    # PMJDY match for unbanked individual
    res_pmjdy = evaluate_scheme_eligibility(
        scheme_name="PMJDY",
        is_unbanked=True,
    )
    assert res_pmjdy["status"] == "potential_match"
    assert res_pmjdy["scheme"] == "PMJDY"
    assert "RuPay" in res_pmjdy["key_details"]["card"] or "RuPay" in str(res_pmjdy["key_details"])
    assert res_pmjdy["last_verified"] == LAST_VERIFIED_DATE


def test_evaluate_scheme_eligibility_does_not_meet_criteria():
    # PMJJBY age 55 (limit 50)
    res_pmjjby_old = evaluate_scheme_eligibility(
        scheme_name="PMJJBY",
        age=55,
        has_bank_or_post_office_account=True,
    )
    assert res_pmjjby_old["status"] == "does_not_meet_criteria"
    assert "18 to 50" in res_pmjjby_old["reason"]

    # PMSBY age 75 (limit 70)
    res_pmsby_old = evaluate_scheme_eligibility(
        scheme_name="PMSBY",
        age=75,
        has_bank_or_post_office_account=True,
    )
    assert res_pmsby_old["status"] == "does_not_meet_criteria"
    assert "18 to 70" in res_pmsby_old["reason"]

    # PMJJBY without bank account
    res_no_bank = evaluate_scheme_eligibility(
        scheme_name="PMJJBY",
        age=30,
        has_bank_or_post_office_account=False,
    )
    assert res_no_bank["status"] == "does_not_meet_criteria"
    assert "requires an individual savings account" in res_no_bank["reason"]


def test_evaluate_scheme_eligibility_insufficient_info():
    # Missing age for PMJJBY
    res_no_age = evaluate_scheme_eligibility(scheme_name="PMJJBY")
    assert res_no_age["status"] == "insufficient_information"
    assert "missing_fields" in res_no_age
    assert "age" in res_no_age["missing_fields"]

    # Unknown scheme
    res_unknown = evaluate_scheme_eligibility(scheme_name="UnknownScheme")
    assert res_unknown["status"] == "insufficient_information"


# ---------------------------------------------------------------------------
# 2. Assistant Function Tool & Failure Path Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_financial_scheme_eligibility_tool_success():
    assistant = Assistant()
    result_str = await assistant.check_financial_scheme_eligibility(
        context=None,
        scheme_name="PMJJBY",
        age=30,
        has_bank_or_post_office_account=True,
    )
    data = json.loads(result_str)
    assert data["status"] == "potential_match"
    assert data["scheme"] == "PMJJBY"
    assert data["last_verified"] == LAST_VERIFIED_DATE


@pytest.mark.asyncio
async def test_check_financial_scheme_eligibility_tool_failure_path():
    assistant = Assistant()
    # Test graceful error handling with simulate_failure=True
    result_str = await assistant.check_financial_scheme_eligibility(
        context=None,
        scheme_name="PMJJBY",
        age=30,
        simulate_failure=True,
    )
    data = json.loads(result_str)
    assert data["status"] == "error"
    assert data["last_verified"] == LAST_VERIFIED_DATE
    assert "Unable to access scheme eligibility dataset" in data["reason"]
    assert "official_source" in data


# ---------------------------------------------------------------------------
# 3. Live Agent Integration Tests (Eligibility Intent vs Generic Intent)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_eligibility_intent_triggers_tool():
    """Verify that an explicit scheme eligibility question triggers check_financial_scheme_eligibility."""
    assistant = Assistant()
    await assistant.set_user_id("test_user_day5_eligibility")

    async with (
        _test_llm() as llm_inst,
        AgentSession(llm=llm_inst) as session,
    ):
        await session.start(assistant)

        # Run an agent turn following explicit eligibility request
        result = await session.run(
            user_input="I am 25 years old and I have a bank account. Could I be eligible for PMJJBY?"
        )

        # Confirm that check_financial_scheme_eligibility function tool was called
        func_calls = []
        for event in result.events:
            if hasattr(event, "item") and getattr(event.item, "name", None):
                func_calls.append(event.item.name)

        assert (
            "check_financial_scheme_eligibility" in func_calls
            or "transfer_to_scheme_specialist" in func_calls
        ), (
            f"Expected check_financial_scheme_eligibility or transfer_to_scheme_specialist tool call, but got: {func_calls}"
        )


@pytest.mark.asyncio
async def test_agent_generic_question_does_not_trigger_tool():
    """Verify that a generic question (e.g. 'What is insurance?') does NOT trigger the eligibility tool."""
    assistant = Assistant()
    await assistant.set_user_id("test_user_day5_generic")

    async with (
        _test_llm() as llm_inst,
        AgentSession(llm=llm_inst) as session,
    ):
        await session.start(assistant)

        result = await session.run(user_input="What is insurance?")

        func_calls = []
        for event in result.events:
            if hasattr(event, "item") and getattr(event.item, "name", None):
                func_calls.append(event.item.name)

        assert "check_financial_scheme_eligibility" not in func_calls, (
            "Generic question 'What is insurance?' should NOT call check_financial_scheme_eligibility tool!"
        )



# ---------------------------------------------------------------------------
# 4. Day 4 Memory System Regression Tests
# ---------------------------------------------------------------------------

def test_day4_memory_allowlist_and_persistence():
    user_id = "test_day4_regression_user_123"
    db_delete_user(user_id)

    # Save with allowed & disallowed keys
    facts = {
        "schemes_checked": ["PMJJBY", "PMSBY"],
        "eligibility_answers": {"age": "30"},
        "topics_asked": ["insurance"],
        "disallowed_key_aadhaar": "1234-5678-9012",
        "disallowed_key_pin": "9999",
    }
    db_save_user(user_id=user_id, name="Anita", language_pref="hi", facts=facts)

    record = db_lookup_user(user_id)
    assert record is not None
    assert record["name"] == "Anita"
    assert set(record["facts"].keys()).issubset(APPROVED_FACT_KEYS)
    assert "disallowed_key_aadhaar" not in record["facts"]
    assert "disallowed_key_pin" not in record["facts"]

    # Cleanup
    db_delete_user(user_id)
    assert db_lookup_user(user_id) is None
