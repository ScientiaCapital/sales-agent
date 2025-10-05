# Context7 MCP Load Balancer with RunPod vLLM Backend

## Overview

FastAPI-based MCP server providing Context7 research capabilities powered by RunPod's vLLM inference infrastructure. This architecture delivers cost-effective AI research operations with automatic scaling and load balancing.

### Architecture Diagram

```
┌─────────────┐      HTTP      ┌──────────────────────┐      OpenAI API      ┌────────────────┐
│   Client    │ ────────────► │  FastAPI MCP Server  │ ──────────────────► │  RunPod vLLM   │
│  (Claude)   │               │ context7_load_balancer│                      │  Load Balancer │
└─────────────┘               └──────────────────────┘                      └────────────────┘
                                        │                                            │
                                        │ /ping health checks                        │
                                        │                                            │
                                        ▼                                            ▼
                                  ┌──────────┐                               ┌──────────────┐
                                  │  RunPod  │                               │ Llama 3.1 8B │
                                  │  Autoscale│                              │   Workers    │
                                  └──────────┘                               └──────────────┘
```

### Key Features

- **Ultra-Fast Inference**: RunPod vLLM backend with automatic load balancing
- **Cost-Effective**: Pay-per-use serverless pricing, no idle costs
- **Auto-Scaling**: Health check monitoring for intelligent worker scaling
- **Dual-Mode**: Local development (Pod) and production deployment (Serverless)
- **OpenAI-Compatible**: Uses OpenAI SDK with custom base_url

---

## Quick Start

### Prerequisites

1. **RunPod Account**: Sign up at [runpod.io](https://runpod.io)
2. **RunPod vLLM Endpoint**: Deploy a vLLM endpoint with Llama 3.1 8B
3. **API Keys**: RunPod API key from account settings
4. **Python 3.11+**: Required for async/await support

### Installation

```bash
# Navigate to MCP servers directory
cd mcp_servers/

# Install dependencies
pip install -r requirements.txt
```

### Environment Configuration

Create or update `.env` file in project root:

```bash
# RunPod Configuration
RUNPOD_API_KEY=your_runpod_api_key_here
RUNPOD_VLLM_ENDPOINT_ID=your_vllm_endpoint_id_here
```

**Finding Your Endpoint ID**:
1. Go to RunPod Dashboard → Serverless
2. Click on your vLLM endpoint
3. Copy the Endpoint ID (format: `abc123def456`)

---

## Local Development

### Start the Server

```bash
# Option 1: Direct Python execution
python context7_load_balancer.py

# Option 2: Uvicorn with auto-reload
uvicorn context7_load_balancer:app --reload --port 8002
```

Server will start at: `http://localhost:8002`

### Test Endpoints

#### Health Check

```bash
curl http://localhost:8002/ping
```

**Expected Response**:
```json
{
  "status": "healthy",
  "service": "context7-mcp",
  "timestamp": "2025-01-04T10:30:00.123456",
  "vllm_configured": true
}
```

#### Research Endpoint

```bash
curl -X POST http://localhost:8002/v1/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain the benefits of vLLM for large language model inference",
    "max_tokens": 2000,
    "temperature": 0.7
  }'
```

**Expected Response**:
```json
{
  "result": "vLLM (Very Large Language Model) is a high-performance inference engine...",
  "model": "meta-llama/Llama-3.1-8B",
  "tokens_used": 245,
  "latency_ms": 850,
  "timestamp": "2025-01-04T10:31:00.456789"
}
```

### API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8002/docs
- **ReDoc**: http://localhost:8002/redoc

---

## Production Deployment (RunPod Serverless)

### Step 1: Prepare Deployment Files

Ensure you have:
- `context7_load_balancer.py` - FastAPI application
- `handler.py` - RunPod serverless wrapper
- `requirements.txt` - Dependencies

### Step 2: Deploy to RunPod

```bash
# Install RunPod CLI
pip install runpod

# Deploy to serverless endpoint
runpod deploy \
  --endpoint-id <your-endpoint-id> \
  --handler handler.py \
  --env RUNPOD_API_KEY=<your-key> \
  --env RUNPOD_VLLM_ENDPOINT_ID=<vllm-endpoint-id>
```

### Step 3: Test Deployment

```bash
# Health check
curl https://api.runpod.ai/v2/<endpoint-id>/ping

# Research query
curl -X POST https://api.runpod.ai/v2/<endpoint-id>/v1/research \
  -H "Content-Type: application/json" \
  -d '{"query": "What is FastAPI?"}'
```

---

## API Reference

### Endpoints

#### `GET /ping`

Health check endpoint for monitoring and auto-scaling.

**Response**: `200 OK`
```json
{
  "status": "healthy",
  "service": "context7-mcp",
  "timestamp": "2025-01-04T10:30:00.123456",
  "vllm_configured": true
}
```

---

#### `POST /v1/research`

Process research queries using RunPod vLLM backend.

**Request Body**:
```json
{
  "query": "string (required, 1-5000 chars)",
  "max_tokens": "integer (optional, 100-4000, default: 2000)",
  "temperature": "float (optional, 0.0-2.0, default: 0.7)"
}
```

**Response**: `200 OK`
```json
{
  "result": "string (research result)",
  "model": "string (model identifier)",
  "tokens_used": "integer (total tokens)",
  "latency_ms": "integer (request latency)",
  "timestamp": "string (ISO 8601)"
}
```

**Error Responses**:
- `400 Bad Request` - Invalid query format
- `500 Internal Server Error` - vLLM backend not configured
- `503 Service Unavailable` - vLLM backend unreachable
- `504 Gateway Timeout` - Request timeout

---

#### `GET /`

Root endpoint with service information.

**Response**: `200 OK`
```json
{
  "service": "Context7 MCP Load Balancer",
  "version": "1.0.0",
  "status": "running",
  "endpoints": {
    "health": "/ping",
    "research": "/v1/research",
    "docs": "/docs"
  }
}
```

---

## Configuration

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `RUNPOD_API_KEY` | Yes | RunPod API key | `csk-abc123...` |
| `RUNPOD_VLLM_ENDPOINT_ID` | Yes | RunPod vLLM endpoint ID | `abc123def456` |

### RunPod vLLM Backend

**Model**: `meta-llama/Llama-3.1-8B`

**Load Balancing Endpoint**:
```
https://api.runpod.ai/v2/{RUNPOD_VLLM_ENDPOINT_ID}/openai/v1
```

**Timeout Configuration**:
- Total timeout: 60 seconds
- Connect timeout: 10 seconds

---

## Testing

### Run Test Suite

```bash
# Run all tests
python test_mcp_server.py

# Run with verbose output
python test_mcp_server.py -v
```

### Manual Testing

#### Health Check Test

```bash
# Should return 200 OK with healthy status
curl -v http://localhost:8002/ping
```

#### Research Query Test

```bash
# Should return 200 OK with research result
curl -X POST http://localhost:8002/v1/research \
  -H "Content-Type: application/json" \
  -d '{"query": "What is vLLM?"}' | jq .
```

#### Error Handling Test

```bash
# Invalid request - should return 422 Validation Error
curl -X POST http://localhost:8002/v1/research \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## Troubleshooting

### Issue: "vLLM backend not configured"

**Cause**: Missing environment variables

**Solution**:
```bash
# Check environment variables are set
echo $RUNPOD_API_KEY
echo $RUNPOD_VLLM_ENDPOINT_ID

# Set in .env file
echo "RUNPOD_API_KEY=your_key" >> .env
echo "RUNPOD_VLLM_ENDPOINT_ID=your_endpoint_id" >> .env
```

---

### Issue: "503 Service Unavailable"

**Cause**: RunPod vLLM endpoint unreachable

**Solution**:
```bash
# Check endpoint status in RunPod dashboard
# Verify endpoint ID is correct
# Check RunPod API key has proper permissions
# Verify vLLM workers are running
```

---

### Issue: "504 Gateway Timeout"

**Cause**: Request timeout (60s exceeded)

**Solution**:
- Reduce query complexity
- Decrease max_tokens parameter
- Check RunPod worker performance
- Increase timeout in `context7_load_balancer.py`:

```python
vllm_client = AsyncOpenAI(
    api_key=RUNPOD_API_KEY,
    base_url=f"https://api.runpod.ai/v2/{RUNPOD_VLLM_ENDPOINT_ID}/openai/v1",
    timeout=httpx.Timeout(120.0, connect=10.0)  # Increase to 120s
)
```

---

### Issue: Import Errors

**Cause**: Missing dependencies

**Solution**:
```bash
# Reinstall dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep -E "fastapi|openai|uvicorn|pydantic|httpx|runpod"
```

---

## Cost Optimization

### Serverless Pricing

RunPod serverless charges only for active compute time:
- **Llama 3.1 8B**: ~$0.0001 per second of inference
- **No idle costs**: Pay only when processing requests
- **Auto-scaling**: Workers scale to zero when idle

### Best Practices

1. **Batch Requests**: Combine multiple queries when possible
2. **Optimize max_tokens**: Use minimum needed for task
3. **Implement Caching**: Cache frequent research queries
4. **Monitor Usage**: Track tokens_used in responses
5. **Use Temperature Wisely**: Lower temperature (0.3-0.5) for deterministic outputs

### Example Cost Calculation

```
Average query:
- Latency: 850ms
- Tokens: 245
- Cost: ~$0.000085

1000 queries/day:
- Daily: $0.085
- Monthly: $2.55
```

---

## Architecture Benefits

### vs Traditional Inference

| Feature | Context7 MCP + RunPod | Traditional GPU Server |
|---------|----------------------|----------------------|
| **Scaling** | Automatic, instant | Manual, slow |
| **Cost** | Pay-per-use | 24/7 idle costs |
| **Latency** | ~850ms | ~500ms |
| **Maintenance** | Zero | High |
| **Deployment** | Minutes | Hours/days |

### Key Advantages

1. **No Webhook Overhead**: Direct API access reduces latency
2. **Health Monitoring**: `/ping` enables intelligent load balancing
3. **Dual-Mode Development**: Easy local testing, seamless production
4. **OpenAI-Compatible**: Drop-in replacement for OpenAI API
5. **Cost-Effective**: No GPU idle time charges

---

## Development Workflow

### Local Development Loop

```bash
# 1. Start server with auto-reload
uvicorn context7_load_balancer:app --reload --port 8002

# 2. Test endpoint in separate terminal
curl -X POST http://localhost:8002/v1/research \
  -H "Content-Type: application/json" \
  -d '{"query": "Test query"}'

# 3. View logs in server terminal
# INFO:     127.0.0.1:54321 - "POST /v1/research HTTP/1.1" 200 OK

# 4. Make code changes - server auto-reloads
# 5. Repeat testing
```

### Deployment Checklist

- [ ] Environment variables set in RunPod dashboard
- [ ] vLLM endpoint deployed and running
- [ ] handler.py deployed to serverless endpoint
- [ ] Health check returns 200 OK
- [ ] Research endpoint tested with sample query
- [ ] Error handling verified (invalid inputs, timeouts)
- [ ] Monitoring configured (optional)

---

## Monitoring & Logging

### Server Logs

```bash
# Local development
tail -f logs/context7_mcp.log

# RunPod serverless
runpod logs --endpoint-id <your-endpoint-id>
```

### Key Metrics to Monitor

- **Health Check Response Time**: Should be <100ms
- **Research Latency**: Target <1000ms (850ms average)
- **Token Usage**: Track via `tokens_used` in responses
- **Error Rate**: Monitor 5xx errors
- **Auto-Scaling Events**: Worker count changes

### Logging Levels

```python
# Configure in context7_load_balancer.py
logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for verbose logs
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

---

## Support & Resources

### Documentation
- [RunPod Documentation](https://docs.runpod.io)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [vLLM Documentation](https://docs.vllm.ai)

### Community
- RunPod Discord: [discord.gg/runpod](https://discord.gg/runpod)
- FastAPI GitHub: [github.com/tiangolo/fastapi](https://github.com/tiangolo/fastapi)

### Issues
For bugs or feature requests, open an issue in the project repository.

---

## License

MIT License - See LICENSE file for details

---

**Built with**:
- FastAPI 0.115.0
- OpenAI SDK 1.52.0
- RunPod SDK 1.7.6
- Python 3.11+
