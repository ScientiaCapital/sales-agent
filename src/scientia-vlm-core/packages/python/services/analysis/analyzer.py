"""
Blueprint analyzer pipeline.

Orchestrates VLM analysis with caching and confidence calculation.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

# Handle imports for both package and standalone execution
try:
    from .cache import AnalysisCache, hash_image
    from .prompts import get_analysis_prompt
except ImportError:
    from cache import AnalysisCache, hash_image
    from prompts import get_analysis_prompt

logger = logging.getLogger(__name__)


def calculate_confidence(extracted: dict[str, Any]) -> float:
    """Calculate confidence score from extraction completeness.

    Args:
        extracted: Dictionary of extracted fields

    Returns:
        Confidence score between 0.5 and 0.95
    """
    if not extracted:
        return 0.5

    non_null = sum(1 for v in extracted.values() if v is not None)
    total = len(extracted)

    if total == 0:
        return 0.5

    completeness = non_null / total
    # Scale from 0.5 (empty) to 0.95 (complete)
    return min(0.95, 0.5 + (completeness * 0.45))


@dataclass
class AnalysisResult:
    """Result of blueprint analysis."""

    extraction: dict[str, Any]
    confidence: float
    cache_hit: bool
    model_used: str
    image_hash: str
    cost_usd: float = 0.0


class VLMProviderProtocol(Protocol):
    """Protocol for VLM providers."""

    async def analyze_base64(
        self,
        image_base64: str,
        prompt: str,
        model: str,
        **kwargs,
    ) -> dict[str, Any]:
        """Analyze base64-encoded image."""
        ...


class BlueprintAnalyzer:
    """Orchestrates the blueprint analysis pipeline.

    Pipeline:
    1. Hash image for deduplication
    2. Check cache for existing analysis
    3. If cache miss: call VLM provider
    4. Calculate confidence from extraction
    5. Store result in cache
    6. Return structured result
    """

    DEFAULT_MODEL = "qwen/qwen2.5-vl-72b-instruct"

    def __init__(
        self,
        cache: AnalysisCache | None,
        provider: VLMProviderProtocol,
    ) -> None:
        """Initialize analyzer.

        Args:
            cache: Analysis cache (or None for cache-less mode)
            provider: VLM provider for analysis
        """
        self.cache = cache
        self.provider = provider

    async def analyze(
        self,
        image_base64: str,
        prompt: str | None = None,
        model: str | None = None,
    ) -> AnalysisResult:
        """Analyze a blueprint image.

        Args:
            image_base64: Base64-encoded image
            prompt: Analysis prompt (uses default if not provided)
            model: VLM model to use (uses default if not provided)

        Returns:
            AnalysisResult with extraction, confidence, and metadata
        """
        model = model or self.DEFAULT_MODEL
        prompt = prompt or get_analysis_prompt()

        # Step 1: Hash image
        image_hash = hash_image(image_base64)

        # Step 2: Check cache
        if self.cache:
            cached_result = await self.cache.get(image_hash)
            if cached_result:
                logger.info(f"Cache hit for hash {image_hash[:8]}...")
                return AnalysisResult(
                    extraction=cached_result,
                    confidence=calculate_confidence(cached_result),
                    cache_hit=True,
                    model_used=model,
                    image_hash=image_hash,
                )

        # Step 3: Call VLM provider
        logger.info(f"Cache miss for hash {image_hash[:8]}..., calling VLM")
        response = await self.provider.analyze_base64(
            image_base64=image_base64,
            prompt=prompt,
            model=model,
        )

        # Step 4: Parse response
        content = response.get("content", "")
        extraction = self._parse_json_response(content)

        # Step 5: Calculate confidence
        confidence = calculate_confidence(extraction)

        # Step 6: Calculate cost (approximate)
        usage = response.get("usage", {})
        cost_usd = self._calculate_cost(usage, model)

        # Step 7: Store in cache
        if self.cache:
            trade = extraction.get("trade")
            await self.cache.set(
                image_hash=image_hash,
                result=extraction,
                model=model,
                trade=trade,
                confidence=confidence,
                cost_usd=cost_usd,
            )

        return AnalysisResult(
            extraction=extraction,
            confidence=confidence,
            cache_hit=False,
            model_used=model,
            image_hash=image_hash,
            cost_usd=cost_usd,
        )

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        """Parse JSON from VLM response, handling markdown code blocks.

        Args:
            content: Raw response content

        Returns:
            Parsed JSON dict
        """
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if json_match:
            content = json_match.group(1).strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            return {"raw_content": content, "parse_error": str(e)}

    def _calculate_cost(self, usage: dict[str, int], model: str) -> float:
        """Calculate API cost from token usage.

        Args:
            usage: Token usage dict with prompt_tokens and completion_tokens
            model: Model identifier

        Returns:
            Estimated cost in USD
        """
        # Qwen VL pricing (per million tokens)
        pricing = {
            "qwen/qwen2.5-vl-72b-instruct": 0.40,
            "qwen/qwen2.5-vl-30b-instruct": 0.20,
            "qwen/qwen2.5-vl-8b-instruct": 0.10,
        }

        cost_per_million = pricing.get(model, 0.40)
        total_tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)

        return (total_tokens / 1_000_000) * cost_per_million
