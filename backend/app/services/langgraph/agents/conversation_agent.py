"""
ConversationAgent - Voice StateGraph for Real-Time Conversations

Uses LangGraph's StateGraph with Cerebras (ultra-fast LLM) and Cartesia (ultra-low
latency TTS) for real-time voice conversations. Optimized for sub-second response times.

Architecture:
    Voice StateGraph: process_input → generate_response → synthesize_speech → END
    - process_input: Add user message to conversation history
    - generate_response: Generate reply with Cerebras (633ms)
    - synthesize_speech: Convert to audio with Cartesia (<150ms)

Speed Optimization:
    - Cerebras LLM: 633ms average latency (6x faster than Claude)
    - Cartesia TTS: <150ms with sonic-turbo model
    - Total pipeline: <800ms end-to-end (real-time conversational)
    - WebSocket streaming for audio delivery

Cost Optimization:
    - Cerebras: $0.10/M tokens (10x cheaper than Claude)
    - Cartesia: ~$0.15/M characters
    - Cost per turn: ~$0.001 (extremely affordable for voice)

Performance:
    - LLM latency: ~633ms (Cerebras)
    - TTS latency: <150ms (Cartesia sonic-turbo)
    - Total: <800ms per turn
    - Supports multi-turn conversations with history

Usage:
    ```python
    from app.services.langgraph.agents import ConversationAgent
    from app.services.cartesia_service import VoiceConfig, VoiceSpeed, VoiceEmotion

    # Initialize agent
    agent = ConversationAgent()

    # Single-turn conversation
    result = await agent.send_message(
        text="Tell me about your product",
        voice_config=VoiceConfig(
            voice_id="a0e99841-438c-4a64-b679-ae501e7d6091",  # Professional voice
            speed=VoiceSpeed.NORMAL,
            emotion=VoiceEmotion.POSITIVITY
        )
    )

    # Play audio
    with open("response.mp3", "wb") as f:
        f.write(result.audio_output)

    # Multi-turn conversation with context
    config = {"configurable": {"thread_id": "conv_123"}}
    result1 = await agent.continue_conversation(
        text="What industries do you serve?",
        voice_config=voice_config,
        config=config
    )
    result2 = await agent.continue_conversation(
        text="Tell me more about SaaS",
        voice_config=voice_config,
        config=config  # Same thread maintains history
    )
    ```
"""

import os
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages

from app.services.langgraph.llm_selector import get_llm_for_capability
from app.services.cartesia_service import CartesiaService, VoiceConfig, VoiceSpeed, VoiceEmotion
from app.core.logging import setup_logging
from app.core.exceptions import ValidationError

logger = setup_logging(__name__)


# ========== State Schema ==========

class ConversationAgentState(TypedDict):
    """
    State for ConversationAgent with voice capabilities.

    Uses add_messages reducer for conversation history accumulation.
    """
    # Conversation history with automatic append
    messages: Annotated[List[BaseMessage], add_messages]

    # Current turn data
    user_input: str
    assistant_response: Optional[str]
    audio_output: Optional[bytes]

    # Voice configuration
    voice_config: Dict[str, Any]

    # Context
    conversation_context: Optional[Dict[str, Any]]
    turn_count: int

    # Performance metadata
    llm_latency_ms: Optional[int]
    tts_latency_ms: Optional[int]
    total_cost_usd: float


# ========== Output Schema ==========

@dataclass
class ConversationTurnResult:
    """
    Structured output from ConversationAgent turn.

    Contains text response, audio output, and performance metrics.
    """
    # Turn content
    user_input: str
    assistant_response: str
    audio_output: bytes  # MP3/PCM audio data
    turn_number: int

    # Conversation history
    conversation_history: List[Dict[str, str]]

    # Voice metadata
    audio_metadata: Dict[str, Any]  # duration, format, voice_id

    # Performance tracking
    latency_breakdown: Dict[str, int]  # llm_ms, tts_ms, total_ms
    total_cost_usd: float
    estimated_audio_duration_ms: int


# ========== ConversationAgent ==========

class ConversationAgent:
    """
    Real-time voice conversation agent with ultra-low latency.

    Combines Cerebras (fastest LLM) with Cartesia (fastest TTS) for
    sub-second conversational responses.
    """

    def __init__(
        self,
        # LLM provider override
        llm_provider: Optional[str] = None,
        # LLM parameters
        temperature: float = 0.7,
        max_tokens: int = 200  # Short responses for voice
    ):
        """
        Initialize ConversationAgent with ultra-fast voice stack.

        Args:
            llm_provider: Override LLM (default: auto-select for voice = Cerebras)
            temperature: Sampling temperature (0.7 for natural conversation)
            max_tokens: Max completion tokens (200 for concise voice responses)
        """
        self.temperature = temperature
        self.max_tokens = max_tokens

        logger.info("Initializing ConversationAgent with voice capabilities")

        # LLM: Auto-select for voice capability → Cerebras (633ms)
        self.llm_provider = llm_provider or "cerebras"
        self.llm = get_llm_for_capability(
            "voice",
            provider=llm_provider,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # TTS: Cartesia with WebSocket streaming
        self.tts = CartesiaService()

        logger.info(
            f"Voice stack initialized: LLM={self.llm_provider}, "
            f"TTS=Cartesia (sonic-turbo)"
        )

        # Initialize checkpointer for multi-turn conversations
        self.checkpointer = InMemorySaver()

        # Build StateGraph
        self.graph = self._build_graph()


    # ========== Node Functions ==========

    async def _process_input_node(self, state: ConversationAgentState) -> Dict[str, Any]:
        """
        Process user input and add to conversation history.
        """
        logger.info(f"Processing user input: '{state['user_input'][:50]}...'")

        # Add user message to history (add_messages reducer handles this automatically)
        return {
            "messages": [HumanMessage(content=state["user_input"])],
            "turn_count": state.get("turn_count", 0) + 1
        }


    async def _generate_response_node(self, state: ConversationAgentState) -> Dict[str, Any]:
        """
        Generate conversational response using Cerebras (ultra-fast).
        """
        logger.info(f"Generating response with {self.llm_provider} (turn #{state.get('turn_count', 1)})")
        start_time = time.time()

        # Build system prompt for voice conversations
        context = state.get("conversation_context", {})
        lead_id = context.get("lead_id")
        purpose = context.get("purpose", "general_conversation")

        system_prompt = f"""You are a helpful AI assistant in a voice conversation.

Conversation purpose: {purpose}
{f'Lead ID: {lead_id}' if lead_id else ''}

Guidelines for voice responses:
- Keep responses concise (2-3 sentences max)
- Use natural, conversational language
- Avoid listing or bullet points (hard to hear)
- Use verbal transitions ("so", "well", "actually")
- Ask clarifying questions when needed
- Be warm and engaging

Remember: This is a VOICE conversation - be concise and natural!"""

        # Invoke LLM with full conversation history
        messages = [
            {"role": "system", "content": system_prompt},
            *[
                {"role": "user" if isinstance(msg, HumanMessage) else "assistant", "content": msg.content}
                for msg in state.get("messages", [])
            ]
        ]

        response = await self.llm.ainvoke(messages)
        llm_latency_ms = int((time.time() - start_time) * 1000)

        # Estimate cost (Cerebras: $0.10/M tokens)
        estimated_tokens = sum(len(m["content"].split()) for m in messages) + len(response.content.split())
        llm_cost_usd = (estimated_tokens / 1_000_000) * 0.10

        logger.info(f"Response generated in {llm_latency_ms}ms, cost: ${llm_cost_usd:.6f}")

        return {
            "assistant_response": response.content,
            "messages": [AIMessage(content=response.content)],
            "llm_latency_ms": llm_latency_ms,
            "total_cost_usd": state.get("total_cost_usd", 0.0) + llm_cost_usd
        }


    async def _synthesize_speech_node(self, state: ConversationAgentState) -> Dict[str, Any]:
        """
        Convert response to speech using Cartesia (ultra-low latency).
        """
        response_text = state.get("assistant_response", "")
        logger.info(f"Synthesizing speech: '{response_text[:50]}...'")
        start_time = time.time()

        # Build VoiceConfig from state
        voice_config_dict = state.get("voice_config", {})
        voice_config = VoiceConfig(
            voice_id=voice_config_dict.get("voice_id", "a0e99841-438c-4a64-b679-ae501e7d6091"),  # Default professional voice
            speed=VoiceSpeed(voice_config_dict.get("speed", "normal")),
            emotion=VoiceEmotion(voice_config_dict.get("emotion", "positivity")),
            output_format=voice_config_dict.get("output_format", {"container": "mp3", "encoding": "mp3", "sample_rate": 44100})
        )

        # Generate speech (collect all chunks)
        audio_chunks = []
        async for chunk in self.tts.text_to_speech(
            text=response_text,
            voice_config=voice_config,
            stream=True
        ):
            audio_chunks.append(chunk)

        audio_output = b"".join(audio_chunks)
        tts_latency_ms = int((time.time() - start_time) * 1000)

        # Estimate cost (Cartesia: ~$0.15/M characters)
        char_count = len(response_text)
        tts_cost_usd = (char_count / 1_000_000) * 0.15

        # Estimate audio duration (rough: 150 words/minute = 2.5 words/second)
        word_count = len(response_text.split())
        estimated_duration_ms = int((word_count / 2.5) * 1000)

        logger.info(
            f"Speech synthesized in {tts_latency_ms}ms, "
            f"audio_duration≈{estimated_duration_ms}ms, cost: ${tts_cost_usd:.6f}"
        )

        return {
            "audio_output": audio_output,
            "tts_latency_ms": tts_latency_ms,
            "total_cost_usd": state.get("total_cost_usd", 0.0) + tts_cost_usd
        }


    # ========== Graph Construction ==========

    def _build_graph(self) -> StateGraph:
        """
        Build linear StateGraph for voice conversation pipeline.

        Architecture:
            START → process_input → generate_response → synthesize_speech → END

        Simple linear flow (no cycles, no conditionals) per turn.
        """
        logger.info("Building voice StateGraph for ConversationAgent")

        builder = StateGraph(ConversationAgentState)

        # Add nodes
        builder.add_node("process_input", self._process_input_node)
        builder.add_node("generate_response", self._generate_response_node)
        builder.add_node("synthesize_speech", self._synthesize_speech_node)

        # Linear edges: process → generate → synthesize
        builder.add_edge(START, "process_input")
        builder.add_edge("process_input", "generate_response")
        builder.add_edge("generate_response", "synthesize_speech")
        builder.add_edge("synthesize_speech", END)

        logger.info("Voice StateGraph compiled with checkpointer")
        return builder.compile(checkpointer=self.checkpointer)


    # ========== Public API ==========

    async def send_message(
        self,
        text: str,
        voice_config: Optional[VoiceConfig] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ConversationTurnResult:
        """
        Send a single message and get voice response (no conversation history).

        Args:
            text: User's message text
            voice_config: Voice configuration (optional, uses defaults)
            context: Optional context dict (lead_id, purpose, etc.)

        Returns:
            ConversationTurnResult with audio and metadata

        Example:
            >>> agent = ConversationAgent()
            >>> result = await agent.send_message(
            ...     text="What's your name?",
            ...     voice_config=VoiceConfig(voice_id="...", speed=VoiceSpeed.FAST)
            ... )
            >>> with open("response.mp3", "wb") as f:
            ...     f.write(result.audio_output)
        """
        if not text or not text.strip():
            raise ValidationError("text cannot be empty")

        # Use default voice config if not provided
        if not voice_config:
            voice_config = VoiceConfig(
                voice_id="a0e99841-438c-4a64-b679-ae501e7d6091",  # Professional voice
                speed=VoiceSpeed.NORMAL,
                emotion=VoiceEmotion.POSITIVITY
            )

        logger.info(f"Single-turn message: '{text[:50]}...'")

        start_time = time.time()

        # Run graph (no thread_id = fresh conversation each time)
        result = await self.graph.ainvoke({
            "messages": [],
            "user_input": text,
            "assistant_response": None,
            "audio_output": None,
            "voice_config": {
                "voice_id": voice_config.voice_id,
                "speed": voice_config.speed.value,
                "emotion": voice_config.emotion.value,
                "output_format": voice_config.output_format
            },
            "conversation_context": context or {},
            "turn_count": 0,
            "llm_latency_ms": None,
            "tts_latency_ms": None,
            "total_cost_usd": 0.0
        })

        total_latency_ms = int((time.time() - start_time) * 1000)

        # Build conversation history
        history = [
            {"role": "user" if isinstance(msg, HumanMessage) else "assistant", "content": msg.content}
            for msg in result.get("messages", [])
        ]

        # Estimate audio duration
        word_count = len(result["assistant_response"].split())
        estimated_duration_ms = int((word_count / 2.5) * 1000)

        logger.info(
            f"Single-turn complete in {total_latency_ms}ms, "
            f"cost: ${result['total_cost_usd']:.6f}"
        )

        return ConversationTurnResult(
            user_input=text,
            assistant_response=result["assistant_response"],
            audio_output=result["audio_output"],
            turn_number=1,
            conversation_history=history,
            audio_metadata={
                "voice_id": voice_config.voice_id,
                "speed": voice_config.speed.value,
                "emotion": voice_config.emotion.value,
                "format": voice_config.output_format["encoding"]
            },
            latency_breakdown={
                "llm_ms": result["llm_latency_ms"],
                "tts_ms": result["tts_latency_ms"],
                "total_ms": total_latency_ms
            },
            total_cost_usd=result["total_cost_usd"],
            estimated_audio_duration_ms=estimated_duration_ms
        )


    async def continue_conversation(
        self,
        text: str,
        voice_config: Optional[VoiceConfig] = None,
        context: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> ConversationTurnResult:
        """
        Continue multi-turn conversation with conversation history.

        Uses checkpointer to maintain state across turns via thread_id.

        Args:
            text: User's message text
            voice_config: Voice configuration (optional)
            context: Optional context dict (lead_id, purpose, etc.)
            config: LangGraph config with thread_id for conversation persistence

        Returns:
            ConversationTurnResult with audio and metadata

        Example:
            >>> agent = ConversationAgent()
            >>> config = {"configurable": {"thread_id": "conv_123"}}
            >>>
            >>> # Turn 1
            >>> result1 = await agent.continue_conversation(
            ...     text="Hi, I'm interested in your product",
            ...     config=config
            ... )
            >>>
            >>> # Turn 2 (remembers Turn 1 context)
            >>> result2 = await agent.continue_conversation(
            ...     text="What industries do you serve?",
            ...     config=config  # Same thread_id
            ... )
        """
        if not text or not text.strip():
            raise ValidationError("text cannot be empty")

        # Generate thread_id if not provided
        if not config:
            config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        elif "configurable" not in config or "thread_id" not in config["configurable"]:
            config = {"configurable": {"thread_id": str(uuid.uuid4())}}

        # Use default voice config if not provided
        if not voice_config:
            voice_config = VoiceConfig(
                voice_id="a0e99841-438c-4a64-b679-ae501e7d6091",
                speed=VoiceSpeed.NORMAL,
                emotion=VoiceEmotion.POSITIVITY
            )

        thread_id = config["configurable"]["thread_id"]
        logger.info(f"Multi-turn message: '{text[:50]}...', thread={thread_id}")

        start_time = time.time()

        # Get current state (if exists) to maintain turn count
        try:
            current_state = await self.graph.aget_state(config)
            existing_turn_count = current_state.values.get("turn_count", 0) if current_state.values else 0
        except:
            existing_turn_count = 0

        # Run graph with thread_id
        result = await self.graph.ainvoke({
            "messages": [],  # Checkpointer maintains history
            "user_input": text,
            "assistant_response": None,
            "audio_output": None,
            "voice_config": {
                "voice_id": voice_config.voice_id,
                "speed": voice_config.speed.value,
                "emotion": voice_config.emotion.value,
                "output_format": voice_config.output_format
            },
            "conversation_context": context or {},
            "turn_count": existing_turn_count,
            "llm_latency_ms": None,
            "tts_latency_ms": None,
            "total_cost_usd": 0.0
        }, config=config)

        total_latency_ms = int((time.time() - start_time) * 1000)

        # Build conversation history
        history = [
            {"role": "user" if isinstance(msg, HumanMessage) else "assistant", "content": msg.content}
            for msg in result.get("messages", [])
        ]

        # Estimate audio duration
        word_count = len(result["assistant_response"].split())
        estimated_duration_ms = int((word_count / 2.5) * 1000)

        logger.info(
            f"Multi-turn complete in {total_latency_ms}ms, "
            f"turn #{result['turn_count']}, cost: ${result['total_cost_usd']:.6f}"
        )

        return ConversationTurnResult(
            user_input=text,
            assistant_response=result["assistant_response"],
            audio_output=result["audio_output"],
            turn_number=result["turn_count"],
            conversation_history=history,
            audio_metadata={
                "voice_id": voice_config.voice_id,
                "speed": voice_config.speed.value,
                "emotion": voice_config.emotion.value,
                "format": voice_config.output_format["encoding"]
            },
            latency_breakdown={
                "llm_ms": result["llm_latency_ms"],
                "tts_ms": result["tts_latency_ms"],
                "total_ms": total_latency_ms
            },
            total_cost_usd=result["total_cost_usd"],
            estimated_audio_duration_ms=estimated_duration_ms
        )


# ========== Exports ==========

__all__ = [
    "ConversationAgent",
    "ConversationTurnResult",
]
