import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.calling.agents.closer import CloserAgent, CloseResult


@pytest.mark.asyncio
async def test_closer_proposes_meeting_times():
    """Closer should propose meeting times."""
    agent = CloserAgent(llm_provider=MagicMock())
    agent.llm = AsyncMock(return_value={
        "response": "Perfect! I have Tuesday at 2pm or Wednesday at 10am available. Which works better?",
        "action": "propose_times",
        "proposed_times": ["2024-12-17T14:00", "2024-12-18T10:00"],
    })

    result = await agent.close(
        transcript="Yeah I'd be interested in learning more",
        lead_context={"company_name": "Solar Pros"},
    )

    assert result.action == "propose_times"
    assert len(result.proposed_times) > 0


@pytest.mark.asyncio
async def test_closer_confirms_meeting():
    """Closer should confirm meeting details."""
    agent = CloserAgent(llm_provider=MagicMock())
    agent.llm = AsyncMock(return_value={
        "response": "Great! I've got you down for Tuesday at 2pm. You'll get a calendar invite shortly!",
        "action": "meeting_confirmed",
        "meeting_time": "2024-12-17T14:00",
    })

    result = await agent.close(
        transcript="Tuesday at 2 works",
        lead_context={"company_name": "Solar Pros"},
    )

    assert result.action == "meeting_confirmed"
    assert result.meeting_time is not None


@pytest.mark.asyncio
async def test_closer_handles_reschedule():
    """Closer should handle reschedule request."""
    agent = CloserAgent(llm_provider=MagicMock())
    agent.llm = AsyncMock(return_value={
        "response": "No problem - what day works better for you?",
        "action": "reschedule",
        "proposed_times": [],
    })

    result = await agent.close(
        transcript="Actually neither of those work for me",
        lead_context={"company_name": "Solar Pros"},
    )

    assert result.action == "reschedule"


@pytest.mark.asyncio
async def test_closer_handles_declined():
    """Closer should handle declined meeting gracefully."""
    agent = CloserAgent(llm_provider=MagicMock())
    agent.llm = AsyncMock(return_value={
        "response": "I understand. Would it be okay if I followed up next month?",
        "action": "declined",
        "proposed_times": [],
    })

    result = await agent.close(
        transcript="I don't think I'm ready for a meeting yet",
        lead_context={"company_name": "Solar Pros"},
    )

    assert result.action == "declined"
