"""
Post-Call Analysis using AssemblyAI.

Runs async after calls complete to extract:
- Sentiment per speaker turn
- Key entities (competitors, products, companies)
- Topic classification for lead scoring
- Action items and follow-ups
- Call quality metrics

This enriches CRM data without adding latency to real-time calls.
"""
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import os

logger = logging.getLogger(__name__)

try:
    import assemblyai as aai
    ASSEMBLYAI_AVAILABLE = True
except ImportError:
    aai = None
    ASSEMBLYAI_AVAILABLE = False


class Sentiment(str, Enum):
    """Sentiment classification."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class Speaker(str, Enum):
    """Speaker identification."""
    AGENT = "agent"  # AI or human sales rep
    LEAD = "lead"    # Prospect/customer


@dataclass
class SpeakerTurn:
    """A single turn in the conversation."""
    speaker: Speaker
    text: str
    start_ms: int
    end_ms: int
    sentiment: Sentiment = Sentiment.NEUTRAL
    confidence: float = 0.0
    entities: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class CallAnalysis:
    """Complete analysis of a call."""
    call_sid: str
    lead_id: str
    duration_seconds: int

    # Transcript with speaker diarization
    turns: List[SpeakerTurn] = field(default_factory=list)

    # Overall sentiment
    overall_sentiment: Sentiment = Sentiment.NEUTRAL
    lead_sentiment_score: float = 0.0  # -1 to 1

    # Entities detected
    entities: Dict[str, List[str]] = field(default_factory=dict)
    # e.g., {"competitors": ["SunRun", "Tesla"], "products": ["solar panels"]}

    # Topics discussed
    topics: List[str] = field(default_factory=list)

    # Key moments
    objections_raised: List[str] = field(default_factory=list)
    buying_signals: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)

    # Quality metrics
    talk_ratio: float = 0.0  # Lead talk time / total (higher = better)
    interruptions: int = 0
    dead_air_seconds: float = 0.0

    # Outcome
    outcome: str = ""  # qualified, not_qualified, meeting_booked, callback_scheduled
    next_steps: str = ""

    # Raw data
    raw_transcript: str = ""


class PostCallAnalyzer:
    """
    Analyzes completed calls using AssemblyAI.

    Features used:
    - Speaker diarization (who said what)
    - Sentiment analysis (per utterance)
    - Entity detection (competitors, products, people)
    - Topic classification
    - Auto highlights (key moments)

    Usage:
        analyzer = PostCallAnalyzer(api_key="aai_xxx")
        analysis = await analyzer.analyze_recording(
            audio_url="https://...",
            call_sid="CA123",
            lead_id="lead_456"
        )
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with AssemblyAI API key."""
        self.api_key = api_key or os.getenv("ASSEMBLYAI_API_KEY")

        if ASSEMBLYAI_AVAILABLE and self.api_key:
            aai.settings.api_key = self.api_key
            self.available = True
            logger.info("AssemblyAI PostCallAnalyzer initialized")
        else:
            self.available = False
            if not ASSEMBLYAI_AVAILABLE:
                logger.warning("AssemblyAI SDK not installed: pip install assemblyai")
            elif not self.api_key:
                logger.warning("ASSEMBLYAI_API_KEY not set")

    async def analyze_recording(
        self,
        audio_url: str,
        call_sid: str,
        lead_id: str,
        webhook_url: Optional[str] = None,
    ) -> CallAnalysis:
        """
        Analyze a call recording asynchronously.

        Args:
            audio_url: URL to the call recording (Twilio recording URL)
            call_sid: Twilio call SID
            lead_id: Lead ID from CRM
            webhook_url: Optional webhook for completion notification

        Returns:
            CallAnalysis with all extracted insights
        """
        if not self.available:
            logger.error("AssemblyAI not available for analysis")
            return CallAnalysis(
                call_sid=call_sid,
                lead_id=lead_id,
                duration_seconds=0,
            )

        logger.info(f"Starting post-call analysis for {call_sid}")

        try:
            # Configure transcription with all features
            config = aai.TranscriptionConfig(
                speaker_labels=True,           # Who said what
                sentiment_analysis=True,       # Sentiment per utterance
                entity_detection=True,         # People, orgs, products
                auto_highlights=True,          # Key moments
                iab_categories=True,           # Topic classification
                summarization=True,            # Call summary
                summary_type=aai.SummarizationType.bullets,
            )

            # Submit for transcription
            transcriber = aai.Transcriber()
            transcript = transcriber.transcribe(audio_url, config=config)

            if transcript.status == aai.TranscriptStatus.error:
                logger.error(f"Transcription failed: {transcript.error}")
                return CallAnalysis(
                    call_sid=call_sid,
                    lead_id=lead_id,
                    duration_seconds=0,
                )

            # Process results
            analysis = self._process_transcript(transcript, call_sid, lead_id)

            logger.info(f"Analysis complete for {call_sid}: {analysis.outcome}")
            return analysis

        except Exception as e:
            logger.error(f"Analysis failed for {call_sid}: {e}")
            return CallAnalysis(
                call_sid=call_sid,
                lead_id=lead_id,
                duration_seconds=0,
            )

    def _process_transcript(
        self,
        transcript: Any,
        call_sid: str,
        lead_id: str,
    ) -> CallAnalysis:
        """Process AssemblyAI transcript into CallAnalysis."""

        # Extract speaker turns with sentiment
        turns = []
        lead_sentiment_sum = 0.0
        lead_turn_count = 0
        agent_talk_time = 0
        lead_talk_time = 0

        if transcript.utterances:
            for utterance in transcript.utterances:
                # Map speaker (A = agent who initiated, B = lead who answered)
                speaker = Speaker.AGENT if utterance.speaker == "A" else Speaker.LEAD

                # Get sentiment for this utterance
                sentiment = Sentiment.NEUTRAL
                confidence = 0.0

                if transcript.sentiment_analysis_results:
                    for sa in transcript.sentiment_analysis_results:
                        if sa.start <= utterance.start <= sa.end:
                            sentiment = Sentiment(sa.sentiment.lower())
                            confidence = sa.confidence
                            break

                turn = SpeakerTurn(
                    speaker=speaker,
                    text=utterance.text,
                    start_ms=utterance.start,
                    end_ms=utterance.end,
                    sentiment=sentiment,
                    confidence=confidence,
                )
                turns.append(turn)

                # Track talk time
                duration_ms = utterance.end - utterance.start
                if speaker == Speaker.LEAD:
                    lead_talk_time += duration_ms
                    lead_sentiment_sum += (1.0 if sentiment == Sentiment.POSITIVE else
                                          -1.0 if sentiment == Sentiment.NEGATIVE else 0.0)
                    lead_turn_count += 1
                else:
                    agent_talk_time += duration_ms

        # Calculate metrics
        total_talk_time = agent_talk_time + lead_talk_time
        talk_ratio = lead_talk_time / total_talk_time if total_talk_time > 0 else 0.0
        lead_sentiment_score = lead_sentiment_sum / lead_turn_count if lead_turn_count > 0 else 0.0

        # Determine overall sentiment
        if lead_sentiment_score > 0.3:
            overall_sentiment = Sentiment.POSITIVE
        elif lead_sentiment_score < -0.3:
            overall_sentiment = Sentiment.NEGATIVE
        else:
            overall_sentiment = Sentiment.NEUTRAL

        # Extract entities
        entities = self._extract_entities(transcript)

        # Extract topics
        topics = self._extract_topics(transcript)

        # Extract key moments
        objections, buying_signals, action_items = self._extract_key_moments(transcript, turns)

        # Determine outcome based on signals
        outcome = self._determine_outcome(buying_signals, objections, turns)

        # Get summary as next steps
        next_steps = ""
        if transcript.summary:
            next_steps = transcript.summary

        return CallAnalysis(
            call_sid=call_sid,
            lead_id=lead_id,
            duration_seconds=int((transcript.audio_duration or 0) / 1000),
            turns=turns,
            overall_sentiment=overall_sentiment,
            lead_sentiment_score=lead_sentiment_score,
            entities=entities,
            topics=topics,
            objections_raised=objections,
            buying_signals=buying_signals,
            action_items=action_items,
            talk_ratio=talk_ratio,
            outcome=outcome,
            next_steps=next_steps,
            raw_transcript=transcript.text or "",
        )

    def _extract_entities(self, transcript: Any) -> Dict[str, List[str]]:
        """Extract and categorize entities."""
        entities = {
            "competitors": [],
            "products": [],
            "companies": [],
            "people": [],
            "locations": [],
            "money": [],
        }

        if not transcript.entities:
            return entities

        for entity in transcript.entities:
            entity_type = entity.entity_type.lower()
            text = entity.text

            if entity_type in ["organization", "org"]:
                # Check if competitor (common solar competitors)
                competitors = ["sunrun", "tesla", "vivint", "sunnova", "sunpower",
                              "enphase", "solaredge", "generac"]
                if any(comp in text.lower() for comp in competitors):
                    if text not in entities["competitors"]:
                        entities["competitors"].append(text)
                else:
                    if text not in entities["companies"]:
                        entities["companies"].append(text)
            elif entity_type == "person":
                if text not in entities["people"]:
                    entities["people"].append(text)
            elif entity_type in ["location", "gpe"]:
                if text not in entities["locations"]:
                    entities["locations"].append(text)
            elif entity_type in ["money", "quantity"]:
                if text not in entities["money"]:
                    entities["money"].append(text)
            elif entity_type in ["product", "work_of_art"]:
                if text not in entities["products"]:
                    entities["products"].append(text)

        return entities

    def _extract_topics(self, transcript: Any) -> List[str]:
        """Extract main topics discussed."""
        topics = []

        if transcript.iab_categories_result and transcript.iab_categories_result.summary:
            # Get top 5 topics by relevance
            sorted_topics = sorted(
                transcript.iab_categories_result.summary.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            topics = [topic for topic, _ in sorted_topics]

        return topics

    def _extract_key_moments(
        self,
        transcript: Any,
        turns: List[SpeakerTurn]
    ) -> tuple[List[str], List[str], List[str]]:
        """Extract objections, buying signals, and action items."""
        objections = []
        buying_signals = []
        action_items = []

        # Common objection patterns
        objection_patterns = [
            "too expensive", "can't afford", "not in budget",
            "need to think", "talk to my", "not interested",
            "already have", "using someone else", "bad timing",
            "call back later", "send information",
        ]

        # Buying signal patterns
        buying_patterns = [
            "how much", "when can", "what's the process",
            "sounds good", "interested", "tell me more",
            "how does it work", "what's included",
            "can you do", "is it possible",
        ]

        # Action item patterns
        action_patterns = [
            "send me", "email me", "call me back",
            "schedule", "set up", "follow up",
            "let me know", "get back to",
        ]

        for turn in turns:
            if turn.speaker == Speaker.LEAD:
                text_lower = turn.text.lower()

                for pattern in objection_patterns:
                    if pattern in text_lower and turn.text not in objections:
                        objections.append(turn.text)
                        break

                for pattern in buying_patterns:
                    if pattern in text_lower and turn.text not in buying_signals:
                        buying_signals.append(turn.text)
                        break

                for pattern in action_patterns:
                    if pattern in text_lower and turn.text not in action_items:
                        action_items.append(turn.text)
                        break

        # Also use auto_highlights if available
        if transcript.auto_highlights_result and transcript.auto_highlights_result.results:
            for highlight in transcript.auto_highlights_result.results[:10]:
                if highlight.text not in buying_signals and highlight.text not in objections:
                    buying_signals.append(f"[Highlight] {highlight.text}")

        return objections, buying_signals, action_items

    def _determine_outcome(
        self,
        buying_signals: List[str],
        objections: List[str],
        turns: List[SpeakerTurn],
    ) -> str:
        """Determine call outcome based on signals."""

        # Check for meeting-related keywords in transcript
        full_text = " ".join(t.text.lower() for t in turns)

        if any(kw in full_text for kw in ["scheduled", "calendar", "tuesday", "wednesday",
                                           "thursday", "monday", "friday", "appointment",
                                           "see you", "meet with"]):
            return "meeting_booked"

        if any(kw in full_text for kw in ["call back", "call you back", "reach out later"]):
            return "callback_scheduled"

        if len(buying_signals) >= 3 and len(objections) <= 1:
            return "qualified"

        if any(kw in full_text for kw in ["not interested", "don't call", "remove me"]):
            return "not_qualified"

        if len(objections) > len(buying_signals):
            return "needs_nurturing"

        return "follow_up_required"

    async def analyze_from_twilio(
        self,
        call_sid: str,
        lead_id: str,
        twilio_account_sid: str,
        twilio_auth_token: str,
    ) -> CallAnalysis:
        """
        Analyze a call using Twilio recording URL.

        Fetches recording from Twilio and submits to AssemblyAI.
        """
        # Construct Twilio recording URL
        # Format: https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Recordings/{RecordingSid}.mp3
        recording_url = (
            f"https://{twilio_account_sid}:{twilio_auth_token}@"
            f"api.twilio.com/2010-04-01/Accounts/{twilio_account_sid}/"
            f"Calls/{call_sid}/Recordings.json"
        )

        logger.info(f"Fetching recording for {call_sid} from Twilio")

        # In production, fetch recording URL from Twilio API
        # For now, return placeholder
        return await self.analyze_recording(
            audio_url=recording_url,
            call_sid=call_sid,
            lead_id=lead_id,
        )
