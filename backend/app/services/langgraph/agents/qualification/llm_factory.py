"""LLM Factory: Multi-provider LLM initialization for qualification."""
import os
from typing import Literal

from langchain_core.language_models import BaseChatModel
from app.services.langchain_cerebras_compat import ChatCerebras
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI  # For DeepSeek (OpenAI-compatible API)
from langchain_community.chat_models import ChatOllama


# Default models per provider
DEFAULT_MODELS = {
    "cerebras": "llama-3.3-70b",
    "claude": "claude-3-haiku-20240307",
    "deepseek": "deepseek-chat",
    "ollama": "llama3.1:8b"
}


def get_default_model(provider: str) -> str:
    """Get default model for a provider."""
    return DEFAULT_MODELS.get(provider, "llama-3.3-70b")


def initialize_llm(
    provider: Literal["cerebras", "claude", "deepseek", "ollama"],
    model: str,
    temperature: float = 0.2,
    max_tokens: int = 500
) -> BaseChatModel:
    """
    Initialize LLM based on provider.

    Args:
        provider: LLM provider (cerebras/claude/deepseek/ollama)
        model: Model ID
        temperature: Sampling temperature (0.2 for consistent scoring)
        max_tokens: Max completion tokens

    Returns:
        Configured BaseChatModel instance

    Raises:
        ValueError: If API key not set or provider unsupported
    """
    if provider == "cerebras":
        api_key = os.getenv("CEREBRAS_API_KEY")
        if not api_key:
            raise ValueError("CEREBRAS_API_KEY environment variable not set")

        return ChatCerebras(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key
        )

    elif provider == "claude":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        return ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key
        )

    elif provider == "deepseek":
        # DeepSeek V3 uses OpenAI-compatible API
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable not set")

        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )

    elif provider == "ollama":
        # Ollama runs locally, no API key needed
        return ChatOllama(
            model=model,
            temperature=temperature,
            num_predict=max_tokens
        )

    else:
        raise ValueError(f"Unsupported provider: {provider}")


__all__ = ["initialize_llm", "get_default_model", "DEFAULT_MODELS"]
