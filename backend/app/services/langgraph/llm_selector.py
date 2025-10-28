"""
LLM Provider Selector - Capability-Based Model Selection

Intelligently selects the best LLM provider based on task requirements:
- Speed → Cerebras (633ms, cheapest)
- Vision → Qwen via OpenRouter (multimodal)
- Reasoning → DeepSeek via OpenRouter (best logic)
- Voice/Real-time → Cerebras + Cartesia (ultra-low latency)
- Cost-optimized → DeepSeek via OpenRouter (90% cheaper than Claude)
- Premium → Claude via Anthropic (highest quality)

Usage:
    ```python
    from app.services.langgraph.llm_selector import get_llm_for_capability

    # Get fastest LLM for high-volume
    llm = get_llm_for_capability("speed")  # Returns Cerebras

    # Get best reasoning LLM
    llm = get_llm_for_capability("reasoning")  # Returns DeepSeek

    # Get vision-capable LLM
    llm = get_llm_for_capability("vision")  # Returns Qwen

    # Manual override
    llm = get_llm_for_capability("speed", provider="anthropic")  # Force Claude
    ```
"""

import os
from typing import Literal, Optional
from langchain_core.language_models import BaseChatModel

from app.core.logging import setup_logging

logger = setup_logging(__name__)


# ========== Provider Capabilities Matrix ==========

PROVIDER_CAPABILITIES = {
    "cerebras": {
        "speed": 10,  # 633ms - fastest
        "cost": 10,  # $0.10/M - cheapest
        "reasoning": 6,  # Good but not best
        "vision": 0,  # No vision support
        "voice": 10,  # Perfect for real-time with Cartesia
        "quality": 7,  # Good quality
    },
    "deepseek": {  # Via OpenRouter
        "speed": 7,  # Fast
        "cost": 9,  # $0.27/M - very cheap
        "reasoning": 10,  # Best reasoning (DeepSeek v3)
        "vision": 0,  # No vision (yet)
        "voice": 6,  # Decent for voice
        "quality": 8,  # High quality
    },
    "qwen": {  # Via OpenRouter
        "speed": 8,  # Fast
        "cost": 9,  # $0.18/M - very cheap
        "reasoning": 8,  # Great reasoning
        "vision": 10,  # Best vision (Qwen VL)
        "voice": 6,  # Decent for voice
        "quality": 8,  # High quality
    },
    "claude": {  # Via Anthropic or OpenRouter
        "speed": 4,  # 4026ms - slower
        "cost": 3,  # $0.25+$1.25/M - expensive
        "reasoning": 10,  # Excellent reasoning
        "vision": 9,  # Great vision (Claude 3.5 Sonnet)
        "voice": 5,  # OK for voice but slow
        "quality": 10,  # Highest quality
    },
    "yi": {  # Via OpenRouter
        "speed": 7,  # Fast
        "cost": 8,  # Cheap
        "reasoning": 7,  # Good reasoning
        "vision": 8,  # Good vision (Yi Vision)
        "voice": 6,  # Decent
        "quality": 7,  # Good quality
    },
    "glm": {  # Via OpenRouter (ChatGLM)
        "speed": 7,  # Fast
        "cost": 9,  # Very cheap
        "reasoning": 7,  # Good reasoning
        "vision": 7,  # Good vision (GLM-4V)
        "voice": 6,  # Decent
        "quality": 7,  # Good quality
    },
}


# ========== Default Models Per Provider ==========

DEFAULT_MODELS = {
    "cerebras": "llama3.1-8b",
    "deepseek": "deepseek/deepseek-chat",  # DeepSeek v3
    "qwen": "qwen/qwen-2.5-72b-instruct",  # Qwen 2.5
    "claude": "claude-3-5-haiku-20241022",  # Haiku for speed/cost balance
    "yi": "01-ai/yi-large",  # Yi Large
    "glm": "zhipuai/glm-4",  # GLM-4
}


# ========== Capability-Based Selection ==========

def get_best_provider_for_capability(
    capability: Literal["speed", "cost", "reasoning", "vision", "voice", "quality"],
    exclude_providers: Optional[list] = None
) -> str:
    """
    Get the best provider for a specific capability.

    Args:
        capability: Desired capability (speed, cost, reasoning, vision, voice, quality)
        exclude_providers: Providers to exclude from selection

    Returns:
        Provider name (cerebras, deepseek, qwen, claude, yi, glm)

    Example:
        >>> get_best_provider_for_capability("speed")
        "cerebras"
        >>> get_best_provider_for_capability("reasoning")
        "deepseek"
        >>> get_best_provider_for_capability("vision")
        "qwen"
    """
    exclude_providers = exclude_providers or []

    # Filter out excluded providers
    available = {
        provider: scores
        for provider, scores in PROVIDER_CAPABILITIES.items()
        if provider not in exclude_providers
    }

    if not available:
        raise ValueError("No providers available after exclusions")

    # Find provider with highest score for capability
    best_provider = max(
        available.items(),
        key=lambda x: x[1][capability]
    )[0]

    logger.info(
        f"Selected '{best_provider}' for capability '{capability}' "
        f"(score: {PROVIDER_CAPABILITIES[best_provider][capability]}/10)"
    )

    return best_provider


def get_llm_for_capability(
    capability: Literal["speed", "cost", "reasoning", "vision", "voice", "quality"],
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 500
) -> BaseChatModel:
    """
    Get LLM instance optimized for specific capability.

    If provider is specified, uses that provider regardless of capability.
    Otherwise, automatically selects best provider for capability.

    Args:
        capability: Task requirement (speed, cost, reasoning, vision, voice, quality)
        provider: Force specific provider (optional)
        model: Force specific model (optional, uses provider default if not set)
        temperature: Sampling temperature
        max_tokens: Max completion tokens

    Returns:
        Initialized LangChain ChatModel

    Example:
        >>> # Auto-select best for speed
        >>> llm = get_llm_for_capability("speed")  # Gets Cerebras
        >>>
        >>> # Auto-select best for reasoning
        >>> llm = get_llm_for_capability("reasoning")  # Gets DeepSeek
        >>>
        >>> # Force specific provider
        >>> llm = get_llm_for_capability("speed", provider="claude")  # Gets Claude despite being slower
    """
    # Auto-select provider if not specified
    if not provider:
        provider = get_best_provider_for_capability(capability)

    # Use default model if not specified
    if not model:
        model = DEFAULT_MODELS.get(provider, "llama3.1-8b")

    # Initialize LLM based on provider
    if provider == "cerebras":
        from langchain_cerebras import ChatCerebras

        api_key = os.getenv("CEREBRAS_API_KEY")
        if not api_key:
            raise ValueError("CEREBRAS_API_KEY not set")

        return ChatCerebras(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key
        )

    elif provider == "claude":
        from langchain_anthropic import ChatAnthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        return ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key
        )

    elif provider in ["deepseek", "qwen", "yi", "glm"]:
        # All use OpenRouter
        from langchain_openai import ChatOpenAI

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not set")

        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1"
        )

    else:
        raise ValueError(
            f"Unknown provider: {provider}. "
            f"Use: cerebras, claude, deepseek, qwen, yi, glm"
        )


# ========== Task-Specific Recommendations ==========

def get_recommended_providers(task_type: str) -> dict:
    """
    Get recommended providers for common task types.

    Args:
        task_type: Task category (qualification, enrichment, growth, marketing, bdr, conversation)

    Returns:
        Dict with primary, alternative, and budget recommendations

    Example:
        >>> recommendations = get_recommended_providers("qualification")
        >>> print(recommendations["primary"])  # "cerebras"
        >>> print(recommendations["premium"])  # "claude"
    """
    recommendations = {
        "qualification": {
            "primary": "cerebras",  # Speed is critical
            "alternative": "deepseek",  # Cost-effective
            "premium": "claude",  # Highest quality
            "reason": "Fast scoring matters most"
        },
        "enrichment": {
            "primary": "claude",  # Tool calling reliability
            "alternative": "deepseek",  # Good tool calling, cheaper
            "budget": "qwen",  # Cheapest with decent tools
            "reason": "Tool calling quality matters"
        },
        "growth": {
            "primary": "cerebras",  # Speed for scale
            "alternative": "deepseek",  # Reasoning for strategy
            "premium": "claude",  # Best strategy
            "reason": "High volume needs speed"
        },
        "marketing": {
            "primary": "deepseek",  # Great content generation
            "alternative": "qwen",  # Good creativity
            "vision": "qwen",  # If image generation needed
            "reason": "Creative reasoning important"
        },
        "bdr": {
            "primary": "claude",  # Best for personalization
            "alternative": "deepseek",  # Good reasoning
            "budget": "cerebras",  # Fast for high volume
            "reason": "Quality personalization critical"
        },
        "conversation": {
            "primary": "cerebras",  # Ultra-low latency
            "alternative": "deepseek",  # Good conversation
            "premium": "claude",  # Best understanding
            "reason": "Real-time needs speed"
        },
    }

    return recommendations.get(task_type, {
        "primary": "cerebras",
        "alternative": "deepseek",
        "premium": "claude",
        "reason": "Default: fast and cheap"
    })


# ========== Hybrid Multi-LLM Strategy ==========

def get_hybrid_llm_set(
    primary_capability: str,
    fallback_capability: str = "cost"
) -> dict:
    """
    Get a set of LLMs for hybrid architecture.

    Use primary for critical path, fallback for non-critical.

    Args:
        primary_capability: Main requirement (speed, reasoning, vision)
        fallback_capability: Fallback requirement (usually cost)

    Returns:
        Dict with primary and fallback LLM instances

    Example:
        >>> llms = get_hybrid_llm_set("speed", "cost")
        >>> # Use llms["primary"] for critical scoring
        >>> # Use llms["fallback"] for logging/analysis
    """
    return {
        "primary": get_llm_for_capability(primary_capability),
        "fallback": get_llm_for_capability(fallback_capability),
        "primary_provider": get_best_provider_for_capability(primary_capability),
        "fallback_provider": get_best_provider_for_capability(fallback_capability),
    }


# ========== Exports ==========

__all__ = [
    "get_best_provider_for_capability",
    "get_llm_for_capability",
    "get_recommended_providers",
    "get_hybrid_llm_set",
    "PROVIDER_CAPABILITIES",
    "DEFAULT_MODELS",
]
