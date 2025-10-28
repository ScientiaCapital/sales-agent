"""
Cerebras Cloud API integration service for ultra-fast inference

Uses official cerebras-cloud-sdk 1.9.0 with automatic TCP connection optimization
for 21% faster TTFT compared to OpenAI SDK wrapper.
"""
import os
import time
from typing import Dict, Tuple
from cerebras.cloud.sdk import Cerebras
import cerebras.cloud.sdk
import json

from app.core.logging import setup_logging
from app.core.exceptions import CerebrasAPIError, CerebrasTimeoutError, MissingAPIKeyError

logger = setup_logging(__name__)


class CerebrasService:
    """
    Service for interacting with Cerebras Cloud API

    Uses official cerebras-cloud-sdk 1.9.0 for ultra-fast inference (<100ms target)
    with automatic TCP connection optimization for 21% TTFT improvement.
    """

    def __init__(self):
        self.api_key = os.getenv("CEREBRAS_API_KEY")

        if not self.api_key:
            raise MissingAPIKeyError(
                "CEREBRAS_API_KEY environment variable not set",
                context={"api_key": "CEREBRAS_API_KEY"}
            )

        # Initialize official Cerebras SDK client (replaces OpenAI wrapper)
        # TCP connection optimization is automatic in SDK
        self.client = Cerebras(
            api_key=self.api_key,
            max_retries=2,  # Default retry policy for resilience
            timeout=30.0  # 30 second timeout for inference calls
        )

        # Default model (llama3.1-8b is fastest for sub-100ms inference)
        self.default_model = os.getenv("CEREBRAS_DEFAULT_MODEL", "llama3.1-8b")

    def qualify_lead(
        self,
        company_name: str,
        company_website: str | None = None,
        company_size: str | None = None,
        industry: str | None = None,
        contact_name: str | None = None,
        contact_title: str | None = None,
        notes: str | None = None
    ) -> Tuple[float, str, int]:
        """
        Qualify a lead using Cerebras inference

        Args:
            company_name: Name of the company
            company_website: Company website URL
            company_size: Company size (e.g., "50-200 employees")
            industry: Industry sector
            contact_name: Contact person's name
            contact_title: Contact person's job title
            notes: Additional context or notes

        Returns:
            Tuple of (score, reasoning, latency_ms)
            - score: 0-100 qualification score
            - reasoning: Detailed explanation for the score
            - latency_ms: API response time in milliseconds
        """

        # Build context for the lead
        context_parts = [f"Company: {company_name}"]
        if company_website:
            context_parts.append(f"Website: {company_website}")
        if company_size:
            context_parts.append(f"Size: {company_size}")
        if industry:
            context_parts.append(f"Industry: {industry}")
        if contact_name:
            context_parts.append(f"Contact: {contact_name}")
        if contact_title:
            context_parts.append(f"Title: {contact_title}")
        if notes:
            context_parts.append(f"Notes: {notes}")

        lead_context = "\n".join(context_parts)

        # System prompt for lead qualification
        system_prompt = """You are an AI sales assistant specializing in B2B lead qualification.
Analyze the provided lead information and assign a qualification score from 0-100 based on:
- Company fit (size, industry alignment, market presence)
- Contact quality (decision-maker level, relevance)
- Sales potential (buying signals, readiness indicators)

Provide your response in this exact JSON format:
{
    "score": <number 0-100>,
    "reasoning": "<2-3 sentence explanation covering fit, quality, and potential>"
}"""

        user_prompt = f"Qualify this lead:\n\n{lead_context}"

        # Measure API latency
        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.default_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Low temperature for consistent scoring
                max_tokens=200  # Enough for score + reasoning
            )

            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            # Parse response
            content = response.choices[0].message.content
            result = json.loads(content)

            score = float(result["score"])
            reasoning = result["reasoning"]

            # Validate score range
            if not (0 <= score <= 100):
                raise ValueError(f"Score {score} outside valid range [0, 100]")

            return score, reasoning, latency_ms

        except json.JSONDecodeError as e:
            # Fallback if model doesn't return valid JSON
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            logger.warning(f"JSON parse error during lead qualification: {e}")
            # Use content as reasoning, assign medium score
            return 50.0, f"Unable to parse response: {str(e)}", latency_ms

        except (ValueError, KeyError) as e:
            # Handle data validation errors
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            logger.warning(f"Data validation error during lead qualification: {e}")
            return 50.0, f"Invalid response format: {str(e)}", latency_ms

        except cerebras.cloud.sdk.APIConnectionError as e:
            # Network connectivity issue - cannot reach Cerebras API
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            raise CerebrasAPIError(
                message="Cannot connect to Cerebras API - network error",
                details={
                    "company_name": company_name,
                    "latency_ms": latency_ms,
                    "error": str(e)
                }
            )

        except cerebras.cloud.sdk.RateLimitError as e:
            # Rate limit exceeded - too many requests
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            raise CerebrasAPIError(
                message="Cerebras API rate limit exceeded",
                details={
                    "company_name": company_name,
                    "latency_ms": latency_ms,
                    "error": str(e)
                }
            )

        except cerebras.cloud.sdk.APIStatusError as e:
            # Non-200 status code received
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            raise CerebrasAPIError(
                message=f"Cerebras API error (status {e.status_code})",
                details={
                    "company_name": company_name,
                    "latency_ms": latency_ms,
                    "status_code": e.status_code,
                    "error": str(e)
                }
            )

        except Exception as e:
            # Unexpected error - catch-all for unknown issues
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            raise CerebrasAPIError(
                message="Lead qualification service unavailable",
                details={
                    "company_name": company_name,
                    "latency_ms": latency_ms,
                    "error": str(e)
                }
            )

    def calculate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str = None
    ) -> Dict[str, float]:
        """
        Calculate API call cost based on token usage

        Cerebras pricing (as of Oct 2024):
        - llama3.1-8b: $0.10/M input tokens, $0.10/M output tokens

        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            model: Model name (defaults to default_model)

        Returns:
            Dict with input_cost, output_cost, and total_cost in USD
        """
        model = model or self.default_model

        # Pricing per million tokens (update as needed)
        pricing = {
            "llama3.1-8b": {"input": 0.10, "output": 0.10},
            "llama3.1-70b": {"input": 0.60, "output": 0.60}
        }

        prices = pricing.get(model, {"input": 0.10, "output": 0.10})

        input_cost = (prompt_tokens / 1_000_000) * prices["input"]
        output_cost = (completion_tokens / 1_000_000) * prices["output"]
        total_cost = input_cost + output_cost

        return {
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "total_cost_usd": round(total_cost, 6)
        }
