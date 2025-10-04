# RunPod vLLM Integration Patterns

## Service Architecture

**File**: `backend/app/services/runpod_vllm.py`

### OpenAI SDK Compatibility

RunPod vLLM uses OpenAI-compatible API via custom base_url:

```python
from openai import AsyncOpenAI
import os

class RunPodVLLMService:
    def __init__(self, endpoint_id: str = None):
        self.endpoint_id = endpoint_id or os.getenv("RUNPOD_VLLM_ENDPOINT_ID")
        
        self.client = AsyncOpenAI(
            api_key=os.getenv("RUNPOD_API_KEY"),
            base_url=f"https://api.runpod.ai/v2/{self.endpoint_id}/openai/v1"
        )
        
        self.default_model = os.getenv("RUNPOD_DEFAULT_MODEL", "meta-llama/Llama-3.1-8B")
```

### Core Methods

**1. Simple Generation**:
```python
async def generate(self, prompt: str, **kwargs) -> str:
    """Generate completion with RunPod vLLM"""
    response = await self.client.chat.completions.create(
        model=kwargs.get("model", self.default_model),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=kwargs.get("max_tokens", 500),
        temperature=kwargs.get("temperature", 0.7)
    )
    return response.choices[0].message.content
```

**2. Streaming Generation**:
```python
async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
    """Stream completion with RunPod vLLM"""
    stream = await self.client.chat.completions.create(
        model=kwargs.get("model", self.default_model),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=kwargs.get("max_tokens", 500),
        temperature=kwargs.get("temperature", 0.7),
        stream=True
    )
    
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

**3. Batch Processing**:
```python
async def batch_generate(self, prompts: List[str], **kwargs) -> List[str]:
    """Process multiple prompts in parallel"""
    tasks = [self.generate(prompt, **kwargs) for prompt in prompts]
    return await asyncio.gather(*tasks)
```

### Environment Configuration

```bash
# RunPod vLLM Configuration
RUNPOD_API_KEY=your_runpod_api_key_here
RUNPOD_VLLM_ENDPOINT_ID=your_vllm_endpoint_id_here
RUNPOD_DEFAULT_MODEL=meta-llama/Llama-3.1-8B

# Supported Models (vLLM compatible)
# - meta-llama/Llama-3.1-8B
# - meta-llama/Llama-3.1-70B
# - mistralai/Mistral-7B-Instruct-v0.2
# - codellama/CodeLlama-34b-Instruct-hf
```

### Integration with FastAPI

```python
from fastapi import APIRouter, HTTPException
from app.services.runpod_vllm import RunPodVLLMService

router = APIRouter()
vllm_service = RunPodVLLMService()

@router.post("/generate")
async def generate_completion(prompt: str, max_tokens: int = 500):
    try:
        result = await vllm_service.generate(
            prompt=prompt,
            max_tokens=max_tokens
        )
        return {"result": result, "provider": "runpod_vllm"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream")
async def stream_completion(prompt: str):
    """Streaming endpoint with Server-Sent Events"""
    async def event_generator():
        async for chunk in vllm_service.stream(prompt):
            yield f"data: {chunk}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

### Cost Comparison

**RunPod vLLM vs Cerebras**:

| Provider | Model | Cost/1M | Latency | Use Case |
|----------|-------|---------|---------|----------|
| RunPod vLLM | Llama-3.1-8B | $0.02 | ~1200ms | General tasks, batch processing |
| Cerebras | llama3.1-8b | $0.10 | ~945ms | Real-time, low-latency needs |

**Cost Savings Example**:
- 10M tokens/month on RunPod: $200
- 10M tokens/month on Cerebras: $1,000
- **Savings: $800/month (80%)**

### Streaming Pattern with FastAPI

```python
from fastapi.responses import StreamingResponse

@router.post("/chat/stream")
async def chat_stream(messages: List[Dict[str, str]]):
    async def generate():
        async for chunk in vllm_service.stream_chat(messages):
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
```

### Error Handling & Retry Pattern

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

class RunPodVLLMService:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate_with_retry(self, prompt: str, **kwargs) -> str:
        """Generate with automatic retry on failure"""
        try:
            return await self.generate(prompt, **kwargs)
        except Exception as e:
            logger.error(f"RunPod vLLM error: {e}")
            raise
```

### Usage in LLM Router

```python
from app.services.runpod_vllm import RunPodVLLMService
from app.services.llm_router import LLMRouter, RoutingStrategy

# Initialize services
runpod = RunPodVLLMService()
router = LLMRouter(strategy=RoutingStrategy.BALANCED)

# Router automatically uses RunPod for 80% of traffic
result = await router.generate("Analyze this lead...")

# Direct RunPod usage for cost-sensitive tasks
result = await runpod.generate(
    prompt="Batch process 1000 documents",
    max_tokens=2000
)
```

## Advanced Patterns

### 1. Model Selection by Task Type

```python
def select_model_by_task(task_type: str) -> str:
    models = {
        "code": "codellama/CodeLlama-34b-Instruct-hf",
        "chat": "meta-llama/Llama-3.1-8B",
        "analysis": "meta-llama/Llama-3.1-70B"
    }
    return models.get(task_type, "meta-llama/Llama-3.1-8B")

result = await vllm_service.generate(
    prompt=user_input,
    model=select_model_by_task("code")
)
```

### 2. Network Volumes for Model Caching

```python
# RunPod serverless with network volume
VOLUME_PATH = "/runpod-volume"
MODEL_CACHE = f"{VOLUME_PATH}/models"

def load_model_from_volume():
    # Models persist across serverless invocations
    model_path = f"{MODEL_CACHE}/Llama-3.1-8B"
    # ... load model
```

### 3. Multi-Model Ensemble

```python
async def ensemble_generate(prompt: str) -> str:
    """Use multiple models and pick best result"""
    tasks = [
        vllm_service.generate(prompt, model="meta-llama/Llama-3.1-8B"),
        vllm_service.generate(prompt, model="mistralai/Mistral-7B-Instruct-v0.2")
    ]
    results = await asyncio.gather(*tasks)
    # Score and select best result
    return select_best_result(results)
```
