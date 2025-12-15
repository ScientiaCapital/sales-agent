import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.calling.agents.objection_handler import ObjectionHandlerAgent, ObjectionResult


@pytest.mark.asyncio
async def test_handles_price_objection():
    """Should acknowledge price concern and pivot to value."""
    agent = ObjectionHandlerAgent(llm_provider=MagicMock())
    agent.llm = AsyncMock(return_value={
        "response": "I totally understand - budget is always a consideration. What if I told you most of our clients see ROI within 3 months?",
        "objection_type": "price",
        "objection_handled": True,
        "next_action": "continue_qualifying",
    })

    result = await agent.handle_objection(
        transcript="That sounds expensive, I don't think we can afford it",
        objection_context={"type": "price"},
    )

    assert result.objection_handled is True
    assert result.next_action == "continue_qualifying"


@pytest.mark.asyncio
async def test_handles_timing_objection():
    """Should acknowledge timing and offer future follow-up."""
    agent = ObjectionHandlerAgent(llm_provider=MagicMock())
    agent.llm = AsyncMock(return_value={
        "response": "Completely understand - when would be a better time to revisit this?",
        "objection_type": "timing",
        "objection_handled": True,
        "next_action": "schedule_callback",
    })

    result = await agent.handle_objection(
        transcript="Now's really not a good time, we're swamped",
        objection_context={"type": "timing"},
    )

    assert result.next_action == "schedule_callback"


@pytest.mark.asyncio
async def test_handles_authority_objection():
    """Should offer to include decision maker."""
    agent = ObjectionHandlerAgent(llm_provider=MagicMock())
    agent.llm = AsyncMock(return_value={
        "response": "No problem - would it help if we scheduled a call that includes them?",
        "objection_type": "authority",
        "objection_handled": True,
        "next_action": "schedule_with_dm",
    })

    result = await agent.handle_objection(
        transcript="I need to check with my business partner first",
        objection_context={"type": "authority"},
    )

    assert result.objection_type == "authority"
    assert result.objection_handled is True


@pytest.mark.asyncio
async def test_unhandled_objection_ends_gracefully():
    """Should end call gracefully when objection cannot be handled."""
    agent = ObjectionHandlerAgent(llm_provider=MagicMock())
    agent.llm = AsyncMock(return_value={
        "response": "I understand, thank you for your time.",
        "objection_type": "hard_no",
        "objection_handled": False,
        "next_action": "end_call",
    })

    result = await agent.handle_objection(
        transcript="Please remove us from your list",
        objection_context={"type": "hard_no"},
    )

    assert result.objection_handled is False
    assert result.next_action == "end_call"
