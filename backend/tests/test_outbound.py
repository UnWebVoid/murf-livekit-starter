import pytest

from agent import Assistant


@pytest.mark.asyncio
async def test_assistant_outbound_mode_enable() -> None:
    assistant = Assistant()
    assert not assistant._is_outbound

    await assistant.enable_outbound_mode()
    assert assistant._is_outbound
    assert "OUTBOUND CALL INSTRUCTIONS" in assistant._instructions


@pytest.mark.asyncio
async def test_end_call_and_opt_out_tool() -> None:
    assistant = Assistant()
    res = await assistant.end_call_and_opt_out(context=None)
    assert "Understood. I won't continue this call. Thank you, and have a good day." in res
