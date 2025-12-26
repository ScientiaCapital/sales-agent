# VLM Analysis Service

**PRIVATE - Scientia Capital Proprietary IP**

Enterprise-grade FastAPI microservice for VLM image analysis with caching, RAG, and ROI re-analysis.

## Features

### Intelligent Analysis
- **Single & Batch Processing** - Analyze 1-10 images per request
- **Multi-Model Support** - Qwen 72B/30B/8B, DeepSeek v3.1
- **Trade-Specific** - HVAC, Roofing, Solar, Electrical, Plumbing
- **ROI Re-Analysis** - Confidence-guided region targeting

### Performance Optimization
- **Image Hashing** - SHA-256 duplicate detection
- **Database Caching** - Avoid redundant VLM calls
- **RAG Similarity** - Learn from similar extractions
- **Cost Tracking** - Per-request optimization

### Reliability
- **Rate Limiting** - 60 req/min default, configurable
- **Circuit Breaker** - Fail-fast pattern
- **Exponential Retry** - With jitter
- **Error Handling** - Comprehensive exception handling

### Observability
- **Request Logging** - Structured logs
- **Performance Metrics** - Latency, throughput
- **Cost Tracking** - Per-request cost
- **Confidence Scores** - Multi-signal breakdown

## Quick Start

### Local Development

1. **Install Dependencies**
   ```bash
   cd /Users/tmkipper/Desktop/tk_projects/vlm-ai-core/packages/python/services/analysis
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your OpenRouter API key
   ```

3. **Run Service**
   ```bash
   uvicorn services.analysis.main:app --reload --port 8002
   ```

4. **Open Documentation**
   ```
   http://localhost:8002/docs
   ```

### Docker Development

1. **Build and Run**
   ```bash
   docker-compose up --build
   ```

2. **With Local Database**
   ```bash
   docker-compose --profile local-db up --build
   ```

3. **With Redis Cache**
   ```bash
   docker-compose --profile local-cache up --build
   ```

### Production Deployment

1. **Build Image**
   ```bash
   docker build -t vlm-analysis:latest .
   ```

2. **Run Container**
   ```bash
   docker run -d \
     -p 8002:8002 \
     -e OPENROUTER_API_KEY=your_key \
     -e SUPABASE_URL=your_url \
     -e SUPABASE_SERVICE_KEY=your_key \
     --name vlm-analysis \
     vlm-analysis:latest
   ```

## API Usage

### Single Image Analysis

```bash
curl -X POST http://localhost:8002/api/v1/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "image": "base64_encoded_image...",
    "prompt": "Extract equipment model and serial number",
    "analysis_type": "equipment",
    "model": "qwen/qwen2.5-vl-72b-instruct",
    "use_cache": true,
    "use_rag": true
  }'
```

### Batch Analysis

```bash
curl -X POST http://localhost:8002/api/v1/analyze/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "images": ["base64_page1...", "base64_page2...", "base64_page3..."],
    "prompt": "Extract materials and quantities",
    "analysis_type": "blueprint",
    "model": "qwen/qwen2.5-vl-72b-instruct",
    "use_cache": true
  }'
```

### List Available Models

```bash
curl http://localhost:8002/api/v1/models
```

### Health Check

```bash
curl http://localhost:8002/health
```

## Python Client Example

```python
import httpx
import base64

# Initialize client
client = httpx.Client(base_url="http://localhost:8002")

# Read and encode image
with open("equipment.jpg", "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode()

# Analyze image
response = client.post(
    "/api/v1/analyze",
    json={
        "image": image_b64,
        "prompt": "Extract equipment model, serial number, and condition",
        "analysis_type": "equipment",
        "model": "qwen/qwen2.5-vl-72b-instruct",
        "trade": "hvac",
        "use_cache": True,
        "use_rag": True,
        "enable_roi": True,
        "roi_threshold": 0.75,
        "workflow": "field"
    },
    headers={"X-API-Key": "your-api-key"}
)

result = response.json()
print(f"Confidence: {result['confidence']}")
print(f"Cache hit: {result['cache_hit']}")
print(f"Cost saved: ${result['cost_saved']:.4f}")
print(f"Extraction: {result['extraction']}")
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/analyze` | POST | Single image analysis |
| `/api/v1/analyze/batch` | POST | Batch analysis (1-10 images) |
| `/api/v1/models` | GET | List available models |
| `/health` | GET | Health check |
| `/docs` | GET | OpenAPI documentation |
| `/redoc` | GET | ReDoc documentation |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | Yes | - | OpenRouter API key |
| `SUPABASE_URL` | No | - | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | No | - | Supabase service key |
| `RATE_LIMIT_PER_MINUTE` | No | 60 | Rate limit per API key |
| `ENABLE_CACHE` | No | true | Enable caching |
| `ENABLE_RAG` | No | true | Enable RAG |
| `ENABLE_ROI` | No | true | Enable ROI re-analysis |

## VLM Models

| Model | Use Case | Cost/1M tokens | Context |
|-------|----------|----------------|---------|
| `qwen/qwen2.5-vl-72b-instruct` | Blueprints, Field Photos | $0.40 | 32K |
| `qwen/qwen2.5-vl-30b-instruct` | Field Photos, Equipment | $0.20 | 32K |
| `qwen/qwen2.5-vl-8b-instruct` | Simple Extractions | $0.10 | 32K |
| `deepseek/deepseek-chat-v3.1` | Text Normalization | $0.00027 | 64K |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Application                  │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Routes     │  │ Dependencies │  │   Schemas    │  │
│  │              │  │              │  │              │  │
│  │ - /analyze   │  │ - VLMProvider│  │ - Pydantic   │  │
│  │ - /batch     │  │ - Middleware │  │   Models     │  │
│  │ - /models    │  │ - Auth       │  │ - Validation │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│                   Middleware Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Rate Limit   │  │ Cost Control │  │Observability │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│                    VLM Provider                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │Image Hashing │  │Cache Lookup  │  │ RAG Search   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  OpenRouter  │  │ROI Detection │  │  Confidence  │  │
│  │   API Call   │  │              │  │   Scoring    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=services.analysis --cov-report=html

# Run specific test
pytest tests/test_routes.py -v

# Run in watch mode
pytest-watch
```

## Development

### Code Quality

```bash
# Format code
black services/analysis

# Lint code
ruff check services/analysis

# Type checking
mypy services/analysis
```

### Project Structure

```
services/analysis/
├── __init__.py          # Package init
├── main.py              # FastAPI app with lifespan
├── routes.py            # API endpoints
├── dependencies.py      # Dependency injection
├── schemas.py           # Pydantic models
├── Dockerfile           # Multi-stage production build
├── docker-compose.yml   # Local development setup
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
└── README.md           # This file
```

## References

### Voice AI Core Pattern
Based on the FastAPI microservice pattern from:
- `/Users/tmkipper/Desktop/tk_projects/voice-ai-core/services/tts/`

### FieldVault.ai Integration
Uses VLM analysis patterns from:
- `/Users/tmkipper/Desktop/tk_projects/fieldvault-ai/web/lib/smart-vlm-client.ts`

## License

**UNLICENSED - Scientia Capital Proprietary IP**

This is private, proprietary software. Unauthorized copying, distribution, or use is strictly prohibited.

## Support

For internal support, contact Scientia Capital engineering team.
