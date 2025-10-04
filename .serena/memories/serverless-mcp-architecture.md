# Serverless MCP Architecture Patterns

## Load Balancing Endpoint Pattern

**Key Discovery**: RunPod serverless supports direct API access without webhooks.

### Endpoint Structure

```
https://ENDPOINT_ID.api.runpod.ai/PATH
```

**Example**:
```python
RUNPOD_ENDPOINT_ID = "abc123def456"
base_url = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/openai/v1"

client = AsyncOpenAI(
    api_key=os.getenv("RUNPOD_API_KEY"),
    base_url=base_url
)
```

### Health Check Pattern

**FastAPI `/ping` Endpoint**:
```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/ping")
async def health_check():
    return {
        "status": "healthy",
        "service": "context7-mcp",
        "timestamp": datetime.utcnow().isoformat()
    }
```

**RunPod Auto-Scaling**:
- Monitors `/ping` for worker health
- Scales workers based on request queue depth
- Automatic replacement of unhealthy workers

### Dual-Mode Development Workflow

**Local Development (Pod)**:
```bash
# Start RunPod Pod with exposed port 8000
curl https://<POD_ID>.runpod.io:8000/ping

# Direct development and testing
python mcp_server.py
```

**Production Deployment (Serverless)**:
```bash
# Deploy to serverless endpoint
runpod deploy --endpoint-id abc123 --handler handler.py

# Access via load balancer
curl https://api.runpod.ai/v2/abc123/openai/v1/chat/completions
```

### MCP Server Example

**File**: `mcp_servers/context7_load_balancer.py`

```python
from fastapi import FastAPI
from openai import AsyncOpenAI
import os

app = FastAPI()

# RunPod vLLM client
vllm_client = AsyncOpenAI(
    api_key=os.getenv("RUNPOD_API_KEY"),
    base_url=f"https://api.runpod.ai/v2/{os.getenv('RUNPOD_ENDPOINT_ID')}/openai/v1"
)

@app.get("/ping")
async def health():
    return {"status": "healthy", "service": "context7-mcp"}

@app.post("/v1/research")
async def research(query: str):
    """Context7 research endpoint with RunPod vLLM backend"""
    response = await vllm_client.chat.completions.create(
        model="meta-llama/Llama-3.1-8B",
        messages=[{"role": "user", "content": f"Research: {query}"}],
        max_tokens=2000
    )
    return {"result": response.choices[0].message.content}
```

### Serverless Handler Wrapper

```python
import runpod
from fastapi import Request
import uvicorn

def handler(event):
    """RunPod serverless handler wrapping FastAPI app"""
    request_data = event['input']
    
    # Simulate FastAPI request
    path = request_data.get('path', '/ping')
    method = request_data.get('method', 'GET')
    
    if path == '/ping' and method == 'GET':
        return {"status": "healthy"}
    
    # Route other requests to FastAPI app
    # ... implementation

runpod.serverless.start({"handler": handler})
```

## Architecture Benefits

1. **No Webhook Overhead**: Direct API access reduces latency
2. **Auto-Scaling**: RunPod handles worker scaling automatically
3. **Health Monitoring**: `/ping` enables intelligent load balancing
4. **Cost Efficiency**: Pay only for actual compute time
5. **Dual-Mode Development**: Easy local testing, seamless production deployment
