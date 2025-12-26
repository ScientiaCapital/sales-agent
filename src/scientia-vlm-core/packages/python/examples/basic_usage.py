"""
Basic usage examples for scientia-vlm-core.

PRIVATE PROPRIETARY IP - Scientia Capital
"""
import asyncio
import os
from pathlib import Path

from vlm_core import (
    VLMConfig,
    Trade,
    CircuitBreaker,
    CircuitBreakerConfig,
    retry,
    RetryConfig,
)
from vlm_core.providers.openrouter import OpenRouterProvider


async def example_basic_analysis():
    """Basic VLM analysis example."""
    # Initialize provider
    provider = OpenRouterProvider(
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
        site_url="https://app.fieldvault.ai",
        app_name="FieldVault"
    )

    # Configure analysis
    config = VLMConfig(
        model="qwen/qwen2.5-vl-72b-instruct",
        prompt="""Analyze this HVAC equipment image and extract:
        - equipment_type (furnace, AC unit, heat pump, etc.)
        - brand
        - model_number
        - estimated_age (in years)
        - condition (excellent, good, fair, poor)
        - issues (array of detected problems)

        Return as JSON.""",
        trade=Trade.HVAC,
        max_tokens=4096,
        temperature=0.0,
    )

    # Read test image (replace with your image)
    image_path = Path("test_hvac.jpg")
    if image_path.exists():
        import base64
        image_base64 = base64.b64encode(image_path.read_bytes()).decode('utf-8')

        # Analyze
        result = await provider.analyze(image_base64, config)

        print(f"Confidence: {result.confidence}")
        print(f"Model: {result.model}")
        print(f"Tokens used: {result.tokens_used}")
        print(f"Latency: {result.latency_ms}ms")
        print(f"Extraction: {result.extraction}")


async def example_with_circuit_breaker():
    """Example with circuit breaker protection."""
    provider = OpenRouterProvider(
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
    )

    # Create circuit breaker for OpenRouter service
    breaker = CircuitBreaker(
        CircuitBreakerConfig(
            service_name="openrouter",
            failure_threshold=5,
            reset_timeout=30000,  # 30 seconds
            success_threshold=2,
        )
    )

    config = VLMConfig(
        model="qwen/qwen2.5-vl-72b-instruct",
        prompt="Extract equipment details from this image.",
        trade=Trade.ELECTRICAL,
    )

    # Execute with circuit breaker protection
    try:
        result = await breaker.execute(
            lambda: provider.analyze("data:image/jpeg;base64,...", config)
        )
        print(f"Success: {result.extraction}")
    except Exception as e:
        print(f"Error: {e}")

    # Check circuit breaker metrics
    metrics = breaker.get_metrics()
    print(f"Circuit state: {metrics.state}")
    print(f"Total requests: {metrics.total_requests}")
    print(f"Total failures: {metrics.total_failures}")


async def example_with_retry():
    """Example with retry logic."""
    provider = OpenRouterProvider(
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
    )

    config = VLMConfig(
        model="qwen/qwen2.5-vl-72b-instruct",
        prompt="Extract roofing details from this image.",
        trade=Trade.ROOFING,
    )

    # Execute with retry
    result = await retry(
        lambda: provider.analyze("data:image/jpeg;base64,...", config),
        RetryConfig(
            max_retries=3,
            base_delay=1000,  # 1 second
            max_delay=30000,  # 30 seconds
            backoff_multiplier=2.0,
            jitter=0.1,
        )
    )

    print(f"Success after retries: {result.extraction}")


async def example_combined_resilience():
    """Example combining circuit breaker and retry."""
    provider = OpenRouterProvider(
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
    )

    breaker = CircuitBreaker(
        CircuitBreakerConfig(service_name="openrouter")
    )

    config = VLMConfig(
        model="qwen/qwen2.5-vl-72b-instruct",
        prompt="Extract solar panel details from this image.",
        trade=Trade.SOLAR,
    )

    # Combine both patterns
    async def resilient_call():
        return await breaker.execute(
            lambda: provider.analyze("data:image/jpeg;base64,...", config)
        )

    result = await retry(
        resilient_call,
        RetryConfig(max_retries=3)
    )

    print(f"Resilient call succeeded: {result.extraction}")


async def example_list_models():
    """List available VLM models."""
    provider = OpenRouterProvider(
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
    )

    models = provider.get_models()

    print("Available VLM Models:")
    print("-" * 80)
    for model in models:
        print(f"ID: {model.id}")
        print(f"Name: {model.name}")
        print(f"Context: {model.context_length:,} tokens")
        print(f"Cost: ${model.cost_per_image}/image")
        print(f"PDF Support: {model.supports_pdf}")
        print(f"Max Image Size: {model.max_image_size}px")
        print("-" * 80)


async def main():
    """Run all examples."""
    print("VLM Core Examples")
    print("=" * 80)

    # List available models
    await example_list_models()

    # Note: Other examples require actual image data
    # Uncomment when you have test images:

    # await example_basic_analysis()
    # await example_with_circuit_breaker()
    # await example_with_retry()
    # await example_combined_resilience()


if __name__ == "__main__":
    asyncio.run(main())
