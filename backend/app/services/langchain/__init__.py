"""
LangChain integration services for sales-agent

Provides LangChain-compatible wrappers for:
- Cerebras Cloud API (ultra-fast inference)
- Cartesia TTS (text-to-speech for voice agents)
- Custom tools for CRM, Apollo, LinkedIn integrations
"""

from .cerebras_llm import CerebrasLLM, get_cerebras_llm

__all__ = [
    "CerebrasLLM",
    "get_cerebras_llm",
]
