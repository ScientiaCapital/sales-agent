"""
RunPod vLLM Service for cost-optimized LLM inference

Provides OpenAI-compatible API wrapper for RunPod vLLM endpoints,
offering 5x cost reduction compared to Cerebras for batch processing
and non-latency-critical operations.

Cost: $0.02/1M tokens (vs Cerebras $0.10/1M)
Latency: ~1200ms (vs Cerebras ~945ms)
"""

import os
import time
import asyncio
import logging
from typing import AsyncIterator, Dict, List, Any, Optional
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class RunPodVLLMService:
    """
    Service for interacting with RunPod vLLM endpoints

    Uses OpenAI-compatible SDK for seamless integration with existing code.
    Optimized for cost-effective batch processing and general inference tasks.
    """

    def __init__(self, endpoint_id: str = None):
        """
        Initialize RunPod vLLM service

        Args:
            endpoint_id: RunPod vLLM endpoint ID (defaults to env var)
        """
        self.endpoint_id = endpoint_id or os.getenv("RUNPOD_VLLM_ENDPOINT_ID")
        self.api_key = os.getenv("RUNPOD_API_KEY")

        if not self.endpoint_id:
            raise ValueError("RUNPOD_VLLM_ENDPOINT_ID environment variable not set")
        if not self.api_key:
            raise ValueError("RUNPOD_API_KEY environment variable not set")

        # Initialize AsyncOpenAI client with RunPod endpoint
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=f"https://api.runpod.ai/v2/{self.endpoint_id}/openai/v1"
        )

        # Default model (Llama 3.1 8B for cost efficiency)
        self.default_model = os.getenv("RUNPOD_DEFAULT_MODEL", "meta-llama/Llama-3.1-8B")

        # Pricing info for cost tracking
        self.cost_per_million = 0.02  # $0.02 per 1M tokens

    async def generate(
        self,
        prompt: str,
        model: str = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate completion with RunPod vLLM

        Args:
            prompt: Input prompt
            model: Model to use (defaults to self.default_model)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional OpenAI API parameters

        Returns:
            Dict containing result, usage stats, and cost info
        """
        model = model or self.default_model
        start_time = time.time()

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Calculate cost
            total_tokens = response.usage.total_tokens if response.usage else 0
            cost = (total_tokens / 1_000_000) * self.cost_per_million

            return {
                "result": response.choices[0].message.content,
                "provider": "runpod_vllm",
                "model": model,
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": total_tokens,
                "cost_per_million": self.cost_per_million,
                "total_cost": round(cost, 6),
                "latency_ms": latency_ms
            }

        except Exception as e:
            logger.error(f"RunPod vLLM generation error: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate_with_retry(
        self,
        prompt: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate with automatic retry on failure

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters for generate()

        Returns:
            Generation result with retry metadata
        """
        return await self.generate(prompt, **kwargs)

    async def stream(
        self,
        prompt: str,
        model: str = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream completion with RunPod vLLM

        Args:
            prompt: Input prompt
            model: Model to use (defaults to self.default_model)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional OpenAI API parameters

        Yields:
            Streamed text chunks
        """
        model = model or self.default_model

        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                **kwargs
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"RunPod vLLM streaming error: {e}")
            raise

    async def batch_generate(
        self,
        prompts: List[str],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Process multiple prompts in parallel for maximum efficiency

        Args:
            prompts: List of prompts to process
            **kwargs: Additional parameters for generate()

        Returns:
            List of generation results
        """
        tasks = [self.generate(prompt, **kwargs) for prompt in prompts]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def select_model_by_task(self, task_type: str) -> str:
        """
        Select optimal model based on task type

        Args:
            task_type: Type of task (code, chat, analysis, etc.)

        Returns:
            Model name
        """
        models = {
            "code": "codellama/CodeLlama-34b-Instruct-hf",
            "chat": "meta-llama/Llama-3.1-8B",
            "analysis": "meta-llama/Llama-3.1-70B",
            "general": "meta-llama/Llama-3.1-8B"
        }
        return models.get(task_type, self.default_model)

    async def qualify_lead(
        self,
        company_name: str,
        company_website: str = None,
        company_size: str = None,
        industry: str = None,
        contact_name: str = None,
        contact_title: str = None,
        notes: str = None
    ) -> Dict[str, Any]:
        """
        Qualify a lead using RunPod vLLM (Cerebras-compatible interface)

        Args:
            company_name: Name of the company
            company_website: Company website URL
            company_size: Company size (e.g., "50-200 employees")
            industry: Industry sector
            contact_name: Contact person's name
            contact_title: Contact person's job title
            notes: Additional context or notes

        Returns:
            Dict with score, reasoning, latency, and cost info
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

        # Construct full prompt
        full_prompt = f"{system_prompt}\n\nQualify this lead:\n\n{lead_context}"

        # Generate qualification
        result = await self.generate(
            prompt=full_prompt,
            temperature=0.3,  # Low temperature for consistent scoring
            max_tokens=200
        )

        import json

        try:
            # Parse JSON response
            response_text = result["result"]
            qualification = json.loads(response_text)

            # Add qualification data to result
            result["score"] = float(qualification["score"])
            result["reasoning"] = qualification["reasoning"]

            # Validate score range
            if not (0 <= result["score"] <= 100):
                raise ValueError(f"Score {result['score']} outside valid range [0, 100]")

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse qualification response: {e}")
            result["score"] = 50.0
            result["reasoning"] = f"Unable to parse response: {str(e)}"

        return result

    async def ensemble_generate(
        self,
        prompt: str,
        models: List[str] = None
    ) -> Dict[str, Any]:
        """
        Use multiple models and select best result

        Args:
            prompt: Input prompt
            models: List of models to use (defaults to preset ensemble)

        Returns:
            Best result from ensemble
        """
        if models is None:
            models = [
                "meta-llama/Llama-3.1-8B",
                "mistralai/Mistral-7B-Instruct-v0.2"
            ]

        # Generate with all models in parallel
        tasks = [self.generate(prompt, model=model) for model in models]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out errors
        valid_results = [r for r in results if not isinstance(r, Exception)]

        if not valid_results:
            raise Exception("All ensemble models failed")

        # Simple selection: return result with lowest perplexity (highest confidence)
        # In production, you'd want a more sophisticated scoring mechanism
        return valid_results[0]  # For now, just return first valid result

    def calculate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int
    ) -> Dict[str, float]:
        """
        Calculate API call cost based on token usage

        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens

        Returns:
            Dict with cost breakdown
        """
        total_tokens = prompt_tokens + completion_tokens
        total_cost = (total_tokens / 1_000_000) * self.cost_per_million

        return {
            "input_cost_usd": round((prompt_tokens / 1_000_000) * self.cost_per_million, 6),
            "output_cost_usd": round((completion_tokens / 1_000_000) * self.cost_per_million, 6),
            "total_cost_usd": round(total_cost, 6),
            "cost_per_million": self.cost_per_million
        }