# scientia-vlm-core

Enterprise-grade Vision-Language Model (VLM) services for Python.

**PRIVATE PROPRIETARY IP** - Scientia Capital

## Features

- 🎯 **Abstract Provider Pattern** - Swappable VLM providers (OpenRouter, Replicate, etc.)
- 🔄 **Smart Retry Logic** - Exponential backoff with jitter for resilience
- 🛡️ **Circuit Breaker** - Prevent cascading failures with automatic recovery
- 📦 **Pydantic Models** - Type-safe configuration and responses
- 🚀 **Async/Await** - Full async support with httpx
- 🎨 **Image Processing** - ROI cropping and resizing with Pillow

## Installation

```bash
# Base installation
pip install -e .

# With OpenRouter provider
pip install -e ".[openrouter]"

# With all providers
pip install -e ".[all]"

# Development
pip install -e ".[dev]"
```

## Quick Start

### OpenRouter Provider

```python
from vlm_core import VLMConfig, Trade
from vlm_core.providers.openrouter import OpenRouterProvider

# Initialize provider
provider = OpenRouterProvider(
    api_key="your-openrouter-api-key",
    site_url="https://app.fieldvault.ai",
    app_name="FieldVault"
)

# Configure analysis
config = VLMConfig(
    model="qwen/qwen2.5-vl-72b-instruct",
    prompt="Extract HVAC equipment details from this image.",
    trade=Trade.HVAC,
    max_tokens=4096,
    temperature=0.0,
)

# Analyze image
result = await provider.analyze(image_base64, config)

print(f"Confidence: {result.confidence}")
print(f"Extraction: {result.extraction}")
```

### Circuit Breaker

```python
from vlm_core import CircuitBreaker, CircuitBreakerConfig

# Create circuit breaker
breaker = CircuitBreaker(
    CircuitBreakerConfig(
        service_name="openrouter",
        failure_threshold=5,
        reset_timeout=30000,  # 30 seconds
        success_threshold=2,
    )
)

# Execute with protection
try:
    result = await breaker.execute(
        lambda: provider.analyze(image_base64, config)
    )
except CircuitBreakerOpenError:
    # Service is down, use fallback
    print("VLM service unavailable")
```

### Retry Logic

```python
from vlm_core import retry, RetryConfig

# Execute with retry
result = await retry(
    lambda: provider.analyze(image_base64, config),
    RetryConfig(
        max_retries=3,
        base_delay=1000,
        max_delay=30000,
        backoff_multiplier=2.0,
        jitter=0.1,
    )
)
```

## Available Models

### Qwen VL (Primary)

- **qwen/qwen2.5-vl-72b-instruct** - $0.0015/image, 98.8% accuracy
- **qwen/qwen2.5-vl-30b-instruct** - $0.0008/image, fallback
- **qwen/qwen2.5-vl-8b-instruct** - $0.0003/image, fallback

## Architecture

```
vlm_core/
├── __init__.py           # Public API exports
├── exceptions.py         # Exception hierarchy
├── types/
│   ├── config.py        # Pydantic configuration models
│   └── responses.py     # Response models
├── providers/
│   ├── base.py          # Abstract VLMProvider class
│   └── openrouter.py    # OpenRouter implementation
└── middleware/
    ├── circuit_breaker.py  # Circuit breaker pattern
    └── retry.py           # Retry with exponential backoff
```

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=vlm_core --cov-report=term-missing

# Type checking
mypy vlm_core

# Linting
ruff check vlm_core
black --check vlm_core
```

## License

PROPRIETARY - Scientia Capital. All rights reserved.

This is private proprietary intellectual property. Unauthorized use, copying, or distribution is prohibited.
