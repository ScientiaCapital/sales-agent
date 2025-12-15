"""
End-to-end integration test for voice pipeline.

Tests the full flow:
1. Pre-call gate approval
2. Call initiation
3. Agent conversation (mocked audio)
4. Meeting booking
5. Post-call confirmation
"""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_call_flow():
    """Test complete call flow from queue to meeting booked."""
    from app.services.calling.agents.qualifier import QualifierAgent
    from app.services.calling.agents.closer import CloserAgent

    # Setup mocks
    mock_llm = AsyncMock()
    mock_llm.side_effect = [
        # Qualifier turn 1
        {
            "response": "Hi John, this is Alex from Solar Solutions...",
            "qualification_status": "gathering_info",
            "signals": [],
        },
        # Qualifier turn 2 (qualified)
        {
            "response": "Great, sounds like we can help!",
            "qualification_status": "qualified",
            "signals": ["interested"],
        },
        # Closer turn 1
        {
            "response": "I have Tuesday at 2pm available",
            "action": "propose_times",
            "proposed_times": ["2024-12-17T14:00"],
        },
        # Closer turn 2 (confirmed)
        {
            "response": "Perfect, see you Tuesday!",
            "action": "meeting_confirmed",
            "meeting_time": "2024-12-17T14:00",
        },
    ]

    # Initialize components
    qualifier = QualifierAgent(llm_provider=mock_llm)
    closer = CloserAgent(llm_provider=mock_llm)

    # Simulate conversation
    lead_context = {"company_name": "Solar Pros", "contact_name": "John"}

    # Turn 1: Greeting
    result1 = await qualifier.process_turn("Hello?", lead_context)
    assert result1.status == "gathering_info"

    # Turn 2: Interest expressed → qualified
    result2 = await qualifier.process_turn(
        "Yeah we do about 50 installs a month", lead_context
    )
    assert result2.transfer_to == "closer"

    # Turn 3: Closer proposes times
    result3 = await closer.close("I'd like to learn more", lead_context)
    assert result3.action == "propose_times"

    # Turn 4: Meeting confirmed
    result4 = await closer.close("Tuesday at 2 works", lead_context)
    assert result4.action == "meeting_confirmed"
    assert result4.meeting_time is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_objection_flow():
    """Test flow when lead raises objection."""
    from app.services.calling.agents.qualifier import QualifierAgent
    from app.services.calling.agents.objection_handler import ObjectionHandlerAgent

    mock_llm = AsyncMock()
    mock_llm.side_effect = [
        # Qualifier detects objection
        {
            "response": "I understand...",
            "qualification_status": "objection",
            "signals": ["price_objection"],
        },
        # ObjectionHandler handles it
        {
            "response": "I hear you on budget...",
            "objection_type": "price",
            "objection_handled": True,
            "next_action": "continue_qualifying",
        },
        # Qualifier continues
        {
            "response": "What if...",
            "qualification_status": "gathering_info",
            "signals": [],
        },
    ]

    qualifier = QualifierAgent(llm_provider=mock_llm)
    objection_handler = ObjectionHandlerAgent(llm_provider=mock_llm)

    # Lead raises price concern
    result1 = await qualifier.process_turn("That sounds expensive", {})
    assert result1.transfer_to == "objection_handler"

    # Handle objection
    result2 = await objection_handler.handle_objection(
        "That sounds expensive", {"type": "price"}
    )
    assert result2.objection_handled is True
    assert result2.next_action == "continue_qualifying"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_not_interested_flow():
    """Test flow when lead is not interested."""
    from app.services.calling.agents.qualifier import QualifierAgent

    mock_llm = AsyncMock()
    mock_llm.return_value = {
        "response": "I understand, thank you for your time. Have a great day!",
        "qualification_status": "not_qualified",
        "signals": ["not_interested"],
    }

    qualifier = QualifierAgent(llm_provider=mock_llm)

    result = await qualifier.process_turn(
        "No thanks, we're not interested", {"company_name": "ABC Corp"}
    )

    assert result.status == "not_qualified"
    assert result.should_end_call is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_human_transfer_flow():
    """Test flow when lead requests human."""
    from app.services.calling.agents.qualifier import QualifierAgent

    mock_llm = AsyncMock()
    mock_llm.return_value = {
        "response": "Of course, let me connect you with a team member.",
        "qualification_status": "transfer",
        "signals": ["human_requested"],
    }

    qualifier = QualifierAgent(llm_provider=mock_llm)

    result = await qualifier.process_turn(
        "Can I speak to a real person?", {"company_name": "Test Corp"}
    )

    assert result.transfer_to == "human"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_gate_approval_flow():
    """Test pre-call gate approval flow."""
    from app.services.calling.gates.pre_call import PreCallGate

    gate = PreCallGate(
        slack_webhook_url="https://hooks.slack.com/test",
        timeout_seconds=1,
    )

    # Simulate approval callback
    gate.handle_slack_callback("call_123", "approve", "tim")

    # Check approval was recorded
    result = gate._pending_approvals.get("call_123")
    assert result is not None
    assert result.approved is True
    assert result.approver == "tim"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_meeting_confirmation_flow():
    """Test post-call meeting confirmation flow."""
    from app.services.calling.gates.post_call import PostCallGate

    gate = PostCallGate(slack_webhook_url="https://hooks.slack.com/test")

    # Simulate confirmation callback
    gate.handle_slack_callback("meeting_456", "confirm", "tim")

    # Check confirmation was recorded
    result = gate._pending_confirmations.get("meeting_456")
    assert result is not None
    assert result.confirmed is True
    assert result.reviewer == "tim"
