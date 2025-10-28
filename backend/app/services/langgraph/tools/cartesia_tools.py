"""
Cartesia Voice Tools for LangGraph Agents

Provides LangChain-compatible tools for ultra-fast text-to-speech synthesis
using Cartesia AI. Integrates with existing CartesiaService and supports
both sonic-2 (quality) and sonic-turbo (speed) models.

Tool Categories:
- Text-to-Speech: Generate audio from text with emotion/speed control
- Voice Management: List available voices for synthesis

Performance:
- sonic-2: 90ms model latency, highest quality
- sonic-turbo: 40ms model latency, fastest for real-time conversations

Usage:
    ```python
    from app.services.langgraph.tools import get_cartesia_tools
    from langgraph.prebuilt import create_react_agent

    voice_tools = get_cartesia_tools()
    agent = create_react_agent(llm, voice_tools)

    # Agent can now synthesize speech and list voices
    result = await agent.ainvoke({
        "messages": [HumanMessage(
            content="Say 'Hello!' in a happy voice"
        )]
    })
    ```
"""

# Import existing tools from langchain module
from app.services.langchain.cartesia_tts_tool import (
    cartesia_text_to_speech,
    cartesia_list_voices,
    get_cartesia_tools as _get_cartesia_tools_impl
)


# Re-export tools for langgraph module
__all__ = [
    "cartesia_text_to_speech",
    "cartesia_list_voices",
]


def get_cartesia_tools():
    """
    Get all Cartesia voice tools for TTS synthesis.

    Returns:
        List of Cartesia tools: [cartesia_text_to_speech, cartesia_list_voices]

    Example:
        ```python
        from app.services.langgraph.tools import get_cartesia_tools
        from langgraph.prebuilt import create_react_agent

        voice_tools = get_cartesia_tools()
        agent = create_react_agent(llm, voice_tools)

        # Agent can synthesize speech with emotions
        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Generate audio: 'Thank you for your interest!' in a professional tone"
            )]
        })
        ```
    """
    return _get_cartesia_tools_impl()
