import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.calling.agents.qualifier import QualifierAgent, QualificationResult


@pytest.mark.asyncio
async def test_qualifier_agent_qualifies_interested_lead():
    """Qualifier should return QUALIFIED when lead shows interest."""
    agent = QualifierAgent(llm_provider=MagicMock())
    agent.llm = AsyncMock(return_value={
        "response": "Great! So you're currently handling about 50 installations per month?",
        "qualification_status": "gathering_info",
        "signals": ["expressed_interest", "solar_installer"],
    })

    result = await agent.process_turn(
        transcript="Yeah we do a lot of solar work, probably 50 installs a month",
        lead_context={"company_name": "SunPower Pros", "industry": "solar"},
    )

    assert result.next_response is not None
    assert "qualified" in result.status.lower() or "gathering" in result.status.lower()


@pytest.mark.asyncio
async def test_qualifier_agent_detects_not_interested():
    """Qualifier should return NOT_QUALIFIED when lead declines."""
    agent = QualifierAgent(llm_provider=MagicMock())
    agent.llm = AsyncMock(return_value={
        "response": "I understand, thank you for your time. Have a great day!",
        "qualification_status": "not_qualified",
        "signals": ["not_interested", "hang_up_signal"],
    })

    result = await agent.process_turn(
        transcript="No thanks, we're not interested. Please don't call again.",
        lead_context={"company_name": "ABC Corp"},
    )

    assert result.status == "not_qualified"
    assert result.should_end_call is True


@pytest.mark.asyncio
async def test_qualifier_agent_detects_objection():
    """Qualifier should route to objection handler when objection detected."""
    agent = QualifierAgent(llm_provider=MagicMock())
    agent.llm = AsyncMock(return_value={
        "response": "I understand budget is a concern...",
        "qualification_status": "objection",
        "signals": ["price_objection"],
    })

    result = await agent.process_turn(
        transcript="That sounds too expensive for us",
        lead_context={"company_name": "Budget Solar"},
    )

    assert result.transfer_to == "objection_handler"


@pytest.mark.asyncio
async def test_qualifier_agent_routes_qualified_to_closer():
    """Qualifier should transfer to closer when lead is qualified."""
    agent = QualifierAgent(llm_provider=MagicMock())
    agent.llm = AsyncMock(return_value={
        "response": "That's great! Let me tell you how we can help...",
        "qualification_status": "qualified",
        "signals": ["budget_confirmed", "decision_maker"],
    })

    result = await agent.process_turn(
        transcript="Yes I'm the owner and we have budget for this quarter",
        lead_context={"company_name": "Ready Solar"},
    )

    assert result.transfer_to == "closer"


@pytest.mark.asyncio
async def test_qualifier_agent_routes_to_human():
    """Qualifier should transfer to human when requested."""
    agent = QualifierAgent(llm_provider=MagicMock())
    agent.llm = AsyncMock(return_value={
        "response": "Absolutely, let me connect you with someone...",
        "qualification_status": "transfer",
        "signals": ["human_requested"],
    })

    result = await agent.process_turn(
        transcript="Can I speak to a real person please?",
        lead_context={"company_name": "Any Corp"},
    )

    assert result.transfer_to == "human"
