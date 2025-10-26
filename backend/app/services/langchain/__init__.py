"""
LangChain integration services for sales-agent

Provides LangChain-compatible wrappers for:
- Cerebras Cloud API (ultra-fast inference)
- Cartesia TTS (text-to-speech for voice agents)
- Custom tools for CRM, Apollo, LinkedIn integrations
"""

from .cerebras_llm import CerebrasLLM, get_cerebras_llm
from .cartesia_tts_tool import (
    cartesia_text_to_speech,
    cartesia_list_voices,
    get_cartesia_tools,
)

__all__ = [
    # LLMs
    "CerebrasLLM",
    "get_cerebras_llm",
    # Tools
    "cartesia_text_to_speech",
    "cartesia_list_voices",
    "get_cartesia_tools",
]
