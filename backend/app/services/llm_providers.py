"""
LLM Provider Service - Hybrid Model Stack

Supports multiple providers with intelligent routing:
- Cerebras: Ultra-fast pre-filtering (500ms, $0.000006/req)
- DeepSeek V3: Deep qualification scoring (671B MoE, $0.28/1M tokens)
- OpenRouter: Access to 400+ models including Qwen VL for vision
- Anthropic Claude: High-quality reasoning (fallback)

Architecture:
    ┌─────────────────────────────────────────────────────────┐
    │           HYBRID MODEL ROUTING                          │
    ├─────────────────────────────────────────────────────────┤
    │  TIER 1: Cerebras (pre-filter)                         │
    │  └─ Fast reject obvious non-fits: <500ms, $0.000006    │
    │                                                         │
    │  TIER 2: DeepSeek V3 (deep scoring)                    │
    │  └─ Nuanced ICP analysis: 1-2s, $0.00035/req          │
    │                                                         │
    │  TIER 3: Qwen VL (website vision)                      │
    │  └─ Screenshot analysis: 2-3s, $0.001/image           │
    └─────────────────────────────────────────────────────────┘

Usage:
    from app.services.llm_providers import get_llm_provider, ModelTier

    # Get provider for specific tier
    llm = get_llm_provider(ModelTier.FAST_FILTER)
    llm = get_llm_provider(ModelTier.DEEP_SCORING)
    llm = get_llm_provider(ModelTier.VISION)

    # Or direct provider access
    llm = get_deepseek_chat()
    llm = get_openrouter_model("qwen/qwen-2.5-vl-72b-instruct")

Author: Tim Kipper (GTM Engineering)
Date: November 26, 2025
"""

import os
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_cerebras import ChatCerebras
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from app.core.logging import setup_logging

logger = setup_logging(__name__)


class ModelTier(Enum):
    """Model tiers for hybrid routing."""
    FAST_FILTER = "fast_filter"      # Cerebras - obvious rejects
    DEEP_SCORING = "deep_scoring"    # DeepSeek V3 - nuanced analysis
    VISION = "vision"                # Qwen VL - website screenshots
    PREMIUM = "premium"              # Claude - complex reasoning


@dataclass
class ModelConfig:
    """Configuration for a model provider."""
    provider: str
    model: str
    api_key_env: str
    base_url: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 500
    cost_per_1m_input: float = 0.0
    cost_per_1m_output: float = 0.0
    description: str = ""


# Model configurations for each tier
MODEL_CONFIGS: Dict[ModelTier, ModelConfig] = {
    ModelTier.FAST_FILTER: ModelConfig(
        provider="cerebras",
        model="llama3.1-8b",
        api_key_env="CEREBRAS_API_KEY",
        temperature=0.2,
        max_tokens=500,
        cost_per_1m_input=0.01,  # ~$0.000006 per request
        cost_per_1m_output=0.01,
        description="Ultra-fast pre-filter for obvious non-fits (500ms)"
    ),
    ModelTier.DEEP_SCORING: ModelConfig(
        provider="deepseek",
        model="deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com",
        temperature=0.3,
        max_tokens=800,
        cost_per_1m_input=0.28,
        cost_per_1m_output=0.42,
        description="DeepSeek V3 MoE for nuanced ICP scoring (671B params)"
    ),
    ModelTier.VISION: ModelConfig(
        provider="openrouter",
        model="qwen/qwen-2.5-vl-7b-instruct",  # 7B is cheaper, 72B for complex
        api_key_env="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        temperature=0.2,
        max_tokens=1000,
        cost_per_1m_input=0.064,
        cost_per_1m_output=0.40,
        description="Qwen VL for website screenshot analysis"
    ),
    ModelTier.PREMIUM: ModelConfig(
        provider="anthropic",
        model="claude-sonnet-4-5-20250929",
        api_key_env="ANTHROPIC_API_KEY",
        temperature=0.3,
        max_tokens=800,
        cost_per_1m_input=3.00,
        cost_per_1m_output=15.00,
        description="Claude Sonnet 4.5 for complex reasoning (best-in-class)"
    ),
}


def get_llm_provider(
    tier: ModelTier,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None
) -> BaseChatModel:
    """
    Get LLM provider for a specific tier.

    Args:
        tier: ModelTier enum specifying which tier to use
        temperature: Optional override for temperature
        max_tokens: Optional override for max_tokens

    Returns:
        Configured LangChain chat model

    Raises:
        ValueError: If API key not configured
    """
    config = MODEL_CONFIGS[tier]

    api_key = os.getenv(config.api_key_env)
    if not api_key:
        raise ValueError(f"{config.api_key_env} environment variable not set")

    temp = temperature if temperature is not None else config.temperature
    tokens = max_tokens if max_tokens is not None else config.max_tokens

    logger.info(f"Initializing {tier.value} provider: {config.provider}/{config.model}")

    if config.provider == "cerebras":
        return ChatCerebras(
            model=config.model,
            temperature=temp,
            max_tokens=tokens,
            api_key=api_key
        )

    elif config.provider == "deepseek":
        # DeepSeek uses OpenAI-compatible API
        return ChatOpenAI(
            model=config.model,
            temperature=temp,
            max_tokens=tokens,
            api_key=api_key,
            base_url=config.base_url
        )

    elif config.provider == "openrouter":
        # OpenRouter uses OpenAI-compatible API
        return ChatOpenAI(
            model=config.model,
            temperature=temp,
            max_tokens=tokens,
            api_key=api_key,
            base_url=config.base_url,
            default_headers={
                "HTTP-Referer": "https://sales-agent.local",
                "X-Title": "Sales Agent Qualification"
            }
        )

    elif config.provider == "anthropic":
        return ChatAnthropic(
            model=config.model,
            temperature=temp,
            max_tokens=tokens,
            api_key=api_key
        )

    else:
        raise ValueError(f"Unknown provider: {config.provider}")


def get_deepseek_chat(
    model: str = "deepseek-chat",
    temperature: float = 0.3,
    max_tokens: int = 800
) -> ChatOpenAI:
    """
    Get DeepSeek V3 chat model directly.

    DeepSeek V3 is a 671B MoE model with excellent reasoning
    at a fraction of the cost of other large models.

    Pricing (Nov 2025):
        - Input: $0.28/1M tokens ($0.028 cache hit)
        - Output: $0.42/1M tokens
        - Context: 128K tokens

    Args:
        model: Model name (deepseek-chat for V3)
        temperature: Sampling temperature
        max_tokens: Maximum output tokens

    Returns:
        Configured ChatOpenAI instance pointing to DeepSeek
    """
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


def get_openrouter_model(
    model: str,
    temperature: float = 0.2,
    max_tokens: int = 1000
) -> ChatOpenAI:
    """
    Get any model from OpenRouter.

    OpenRouter provides access to 400+ models including:
    - qwen/qwen-2.5-vl-7b-instruct (vision, cheap)
    - qwen/qwen-2.5-vl-72b-instruct (vision, powerful)
    - mistralai/pixtral-12b (vision)
    - meta-llama/llama-3.1-405b-instruct (reasoning)

    Args:
        model: OpenRouter model ID (e.g., "qwen/qwen-2.5-vl-72b-instruct")
        temperature: Sampling temperature
        max_tokens: Maximum output tokens

    Returns:
        Configured ChatOpenAI instance pointing to OpenRouter
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable not set")

    return ChatOpenAI(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://sales-agent.local",
            "X-Title": "Sales Agent"
        }
    )


def estimate_cost(tier: ModelTier, input_tokens: int, output_tokens: int) -> float:
    """
    Estimate cost for a request.

    Args:
        tier: Model tier used
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Estimated cost in USD
    """
    config = MODEL_CONFIGS[tier]
    input_cost = (input_tokens / 1_000_000) * config.cost_per_1m_input
    output_cost = (output_tokens / 1_000_000) * config.cost_per_1m_output
    return input_cost + output_cost


# Convenience exports
__all__ = [
    "ModelTier",
    "ModelConfig",
    "MODEL_CONFIGS",
    "get_llm_provider",
    "get_deepseek_chat",
    "get_openrouter_model",
    "estimate_cost"
]
