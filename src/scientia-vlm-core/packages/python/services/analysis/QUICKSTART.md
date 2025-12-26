# VLM Analysis Service - Quick Start

**PRIVATE - Scientia Capital Proprietary IP**

## 🚀 Get Started in 3 Minutes

### 1. Install Dependencies

```bash
cd /Users/tmkipper/Desktop/tk_projects/vlm-ai-core/packages/python/services/analysis
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and add your OpenRouter API key:
```bash
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx
```

### 3. Run Service

```bash
uvicorn services.analysis.main:app --reload --port 8002
```

### 4. Test API

Open browser: http://localhost:8002/docs

Or use curl:
```bash
# Health check
curl http://localhost:8002/health

# List models
curl http://localhost:8002/api/v1/models
```

## 🐳 Docker Quick Start

```bash
# Build and run
docker-compose up --build

# Access API
open http://localhost:8002/docs
```

## 📚 Documentation

- **OpenAPI Docs**: http://localhost:8002/docs
- **ReDoc**: http://localhost:8002/redoc
- **Full README**: [README.md](README.md)
- **Implementation Summary**: `/Users/tmkipper/Desktop/tk_projects/vlm-ai-core/docs/VLM-ANALYSIS-SERVICE.md`

## 🔑 API Example

```python
import httpx
import base64

# Read image
with open("equipment.jpg", "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode()

# Analyze
response = httpx.post(
    "http://localhost:8002/api/v1/analyze",
    json={
        "image": image_b64,
        "prompt": "Extract equipment model and serial number",
        "analysis_type": "equipment",
        "model": "qwen/qwen2.5-vl-72b-instruct"
    }
)

print(response.json())
```

## 🛠️ Development

```bash
# Format code
black services/analysis

# Lint code
ruff check services/analysis

# Type check
mypy services/analysis

# Run tests
pytest
```

## 📂 File Structure

```
services/analysis/
├── main.py              # FastAPI app
├── routes.py            # API endpoints
├── dependencies.py      # DI with @lru_cache
├── schemas.py           # Pydantic models
├── Dockerfile           # Production build
├── docker-compose.yml   # Dev environment
└── requirements.txt     # Dependencies
```

## 🎯 Pattern Reference

Based on: `/Users/tmkipper/Desktop/tk_projects/voice-ai-core/services/tts/`

## ⚠️ TODO

- [ ] Implement VLMProvider (OpenRouter API client)
- [ ] Add caching (Supabase)
- [ ] Implement RAG (similarity search)
- [ ] Add ROI detection
- [ ] Write tests (pytest)
- [ ] Add middleware (rate limiting, cost control)

## 🔒 Security

**PRIVATE** - This is proprietary Scientia Capital IP. Do not distribute.
