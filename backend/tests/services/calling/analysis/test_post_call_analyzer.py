"""Tests for PostCallAnalyzer."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.calling.analysis.post_call_analyzer import (
    PostCallAnalyzer,
    CallAnalysis,
    SpeakerTurn,
    Sentiment,
    Speaker,
)


def test_post_call_analyzer_initialization():
    """Analyzer should initialize with API key."""
    analyzer = PostCallAnalyzer(api_key="test_aai_key")

    assert hasattr(analyzer, 'api_key')
    assert hasattr(analyzer, 'available')
    assert analyzer.api_key == "test_aai_key"


def test_post_call_analyzer_without_key():
    """Analyzer should handle missing API key gracefully."""
    with patch.dict('os.environ', {}, clear=True):
        analyzer = PostCallAnalyzer(api_key=None)
        assert analyzer.available is False


def test_call_analysis_dataclass():
    """CallAnalysis should initialize with proper defaults."""
    analysis = CallAnalysis(
        call_sid="CA123",
        lead_id="lead_456",
        duration_seconds=180,
    )

    assert analysis.call_sid == "CA123"
    assert analysis.lead_id == "lead_456"
    assert analysis.duration_seconds == 180
    assert analysis.turns == []
    assert analysis.overall_sentiment == Sentiment.NEUTRAL
    assert analysis.lead_sentiment_score == 0.0
    assert analysis.entities == {}
    assert analysis.topics == []
    assert analysis.objections_raised == []
    assert analysis.buying_signals == []
    assert analysis.talk_ratio == 0.0
    assert analysis.outcome == ""


def test_speaker_turn_dataclass():
    """SpeakerTurn should track conversation turns."""
    turn = SpeakerTurn(
        speaker=Speaker.LEAD,
        text="Yeah we do about 50 installs a month",
        start_ms=5000,
        end_ms=8000,
        sentiment=Sentiment.POSITIVE,
        confidence=0.95,
    )

    assert turn.speaker == Speaker.LEAD
    assert turn.text == "Yeah we do about 50 installs a month"
    assert turn.start_ms == 5000
    assert turn.end_ms == 8000
    assert turn.sentiment == Sentiment.POSITIVE
    assert turn.confidence == 0.95


def test_sentiment_enum():
    """Sentiment enum should have expected values."""
    assert Sentiment.POSITIVE.value == "positive"
    assert Sentiment.NEGATIVE.value == "negative"
    assert Sentiment.NEUTRAL.value == "neutral"


def test_speaker_enum():
    """Speaker enum should have expected values."""
    assert Speaker.AGENT.value == "agent"
    assert Speaker.LEAD.value == "lead"


@pytest.mark.asyncio
async def test_analyze_recording_returns_analysis():
    """analyze_recording should return CallAnalysis."""
    analyzer = PostCallAnalyzer(api_key="test_key")
    analyzer.available = False  # Simulate SDK not installed

    result = await analyzer.analyze_recording(
        audio_url="https://example.com/recording.mp3",
        call_sid="CA123",
        lead_id="lead_456",
    )

    assert isinstance(result, CallAnalysis)
    assert result.call_sid == "CA123"
    assert result.lead_id == "lead_456"


def test_determine_outcome_meeting_booked():
    """Should detect meeting booked from transcript."""
    analyzer = PostCallAnalyzer(api_key="test_key")

    turns = [
        SpeakerTurn(Speaker.AGENT, "How about Tuesday at 2pm?", 0, 1000),
        SpeakerTurn(Speaker.LEAD, "Tuesday works, I'll see you then", 1000, 2000),
    ]

    outcome = analyzer._determine_outcome(
        buying_signals=["sounds good"],
        objections=[],
        turns=turns,
    )

    assert outcome == "meeting_booked"


def test_determine_outcome_not_qualified():
    """Should detect not qualified lead."""
    analyzer = PostCallAnalyzer(api_key="test_key")

    turns = [
        SpeakerTurn(Speaker.LEAD, "Not interested, don't call again", 0, 1000),
    ]

    outcome = analyzer._determine_outcome(
        buying_signals=[],
        objections=["not interested"],
        turns=turns,
    )

    assert outcome == "not_qualified"


def test_determine_outcome_qualified():
    """Should detect qualified lead with buying signals."""
    analyzer = PostCallAnalyzer(api_key="test_key")

    turns = [
        SpeakerTurn(Speaker.LEAD, "Tell me more about pricing", 0, 1000),
        SpeakerTurn(Speaker.LEAD, "How does the process work?", 1000, 2000),
        SpeakerTurn(Speaker.LEAD, "Sounds interesting", 2000, 3000),
    ]

    outcome = analyzer._determine_outcome(
        buying_signals=["how much", "how does it work", "sounds good"],
        objections=[],
        turns=turns,
    )

    assert outcome == "qualified"


def test_determine_outcome_callback():
    """Should detect callback scheduled."""
    analyzer = PostCallAnalyzer(api_key="test_key")

    turns = [
        SpeakerTurn(Speaker.LEAD, "Can you call you back next week? I'll reach out later", 0, 1000),
    ]

    outcome = analyzer._determine_outcome(
        buying_signals=[],
        objections=[],
        turns=turns,
    )

    assert outcome == "callback_scheduled"


def test_extract_entities_competitors():
    """Should identify competitors from entities."""
    analyzer = PostCallAnalyzer(api_key="test_key")

    # Mock transcript with entities
    mock_transcript = MagicMock()
    mock_entity = MagicMock()
    mock_entity.entity_type = "organization"
    mock_entity.text = "SunRun"
    mock_transcript.entities = [mock_entity]

    entities = analyzer._extract_entities(mock_transcript)

    assert "SunRun" in entities["competitors"]


def test_extract_key_moments_objections():
    """Should extract objections from turns."""
    analyzer = PostCallAnalyzer(api_key="test_key")

    turns = [
        SpeakerTurn(Speaker.LEAD, "That's too expensive for us right now", 0, 1000, Sentiment.NEGATIVE),
        SpeakerTurn(Speaker.LEAD, "I need to talk to my partner first", 1000, 2000, Sentiment.NEUTRAL),
    ]

    mock_transcript = MagicMock()
    mock_transcript.auto_highlights_result = None

    objections, signals, actions = analyzer._extract_key_moments(mock_transcript, turns)

    assert len(objections) == 2
    assert "too expensive" in objections[0].lower()


def test_extract_key_moments_buying_signals():
    """Should extract buying signals from turns."""
    analyzer = PostCallAnalyzer(api_key="test_key")

    turns = [
        SpeakerTurn(Speaker.LEAD, "How much does it cost?", 0, 1000, Sentiment.NEUTRAL),
        SpeakerTurn(Speaker.LEAD, "That sounds good, tell me more", 1000, 2000, Sentiment.POSITIVE),
    ]

    mock_transcript = MagicMock()
    mock_transcript.auto_highlights_result = None

    objections, signals, actions = analyzer._extract_key_moments(mock_transcript, turns)

    assert len(signals) >= 1


def test_call_analysis_full_example():
    """Full CallAnalysis with realistic data."""
    analysis = CallAnalysis(
        call_sid="CA123abc",
        lead_id="lead_solar_456",
        duration_seconds=245,
        turns=[
            SpeakerTurn(Speaker.AGENT, "Hi, this is Tim from Solar Solutions", 0, 3000, Sentiment.POSITIVE, 0.9),
            SpeakerTurn(Speaker.LEAD, "Yeah, we're interested in solar", 3000, 5000, Sentiment.POSITIVE, 0.85),
            SpeakerTurn(Speaker.AGENT, "Great! How many installs do you do monthly?", 5000, 8000, Sentiment.POSITIVE, 0.8),
            SpeakerTurn(Speaker.LEAD, "About 50, but pricing is a concern", 8000, 12000, Sentiment.NEUTRAL, 0.7),
        ],
        overall_sentiment=Sentiment.POSITIVE,
        lead_sentiment_score=0.6,
        entities={
            "competitors": ["SunRun"],
            "products": ["solar panels", "battery storage"],
            "companies": ["Solar Solutions"],
        },
        topics=["RenewableEnergy", "HomeImprovement", "Sales"],
        objections_raised=["pricing is a concern"],
        buying_signals=["we're interested in solar"],
        action_items=["follow up on pricing"],
        talk_ratio=0.55,
        outcome="qualified",
        next_steps="Send pricing breakdown, schedule demo for next week",
    )

    assert analysis.duration_seconds == 245
    assert len(analysis.turns) == 4
    assert analysis.outcome == "qualified"
    assert analysis.lead_sentiment_score == 0.6
    assert "SunRun" in analysis.entities["competitors"]
