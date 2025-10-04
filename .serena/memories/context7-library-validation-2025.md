# Context7 Library Validation - January 2025

## Validation Date: 2025-01-04

All libraries validated via Context7 MCP for latest best practices.

### RunPod SDK 1.7.6

**Serverless Handler Pattern**:
```python
import runpod

def handler(event):
    user_input = event['input']
    result = process(user_input)
    return result

runpod.serverless.start({"handler": handler})
```

**Load Balancing Endpoints**:
- Direct API access: `https://ENDPOINT_ID.api.runpod.ai/PATH`
- No webhook configuration needed
- Health checks via `/ping` endpoint

**Network Volumes**:
```python
# Persistent storage for models
volume_path = "/runpod-volume"
model_cache = f"{volume_path}/models"
```

### FastAPI 0.115.0

**Annotated Dependencies (Latest Pattern)**:
```python
from typing import Annotated
from fastapi import Depends

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session

@app.get("/items")
async def read_items(db: Annotated[AsyncSession, Depends(get_db)]):
    return await db.execute(select(Item))
```

**BackgroundTasks Pattern**:
```python
from fastapi import BackgroundTasks

@app.post("/send-email")
async def send_email(background_tasks: BackgroundTasks):
    background_tasks.add_task(send_email_task, email)
    return {"message": "Email will be sent"}
```

### boto3 1.35.80

**Presigned URLs (Best Practice)**:
```python
url = s3_client.generate_presigned_url(
    'get_object',
    Params={'Bucket': bucket, 'Key': key},
    ExpiresIn=3600
)
```

**Large File Uploads**:
```python
from boto3.s3.transfer import TransferConfig

config = TransferConfig(
    multipart_threshold=1024 * 25,  # 25MB
    max_concurrency=10,
    multipart_chunksize=1024 * 25
)
s3_client.upload_file(file, bucket, key, Config=config)
```

### aiohttp 3.10.10

**Critical: ONE ClientSession per Application**:
```python
# CORRECT - Reuse session
class MyApp:
    def __init__(self):
        self.session = aiohttp.ClientSession()
    
    async def close(self):
        await self.session.close()

# WRONG - Creates new session every time
async def bad_pattern():
    async with aiohttp.ClientSession() as session:  # DON'T DO THIS IN LOOPS!
        pass
```

**Timeout Configuration**:
```python
timeout = aiohttp.ClientTimeout(total=30, connect=10)
session = aiohttp.ClientSession(timeout=timeout)
```

### Redis 5.1.1

**Async Client (Latest)**:
```python
import redis.asyncio as redis

client = redis.Redis(
    host='localhost',
    port=6379,
    decode_responses=True,
    protocol=3  # RESP3
)
```

**Pipeline Pattern (10x Faster)**:
```python
async with client.pipeline() as pipe:
    pipe.set('key1', 'value1')
    pipe.set('key2', 'value2')
    pipe.get('key1')
    results = await pipe.execute()
```

### OpenAI SDK 1.52.0

**Custom Base URL (Cerebras/RunPod Pattern)**:
```python
from openai import AsyncOpenAI

# Cerebras
cerebras_client = AsyncOpenAI(
    api_key=os.getenv("CEREBRAS_API_KEY"),
    base_url="https://api.cerebras.ai/v1"
)

# RunPod vLLM
runpod_client = AsyncOpenAI(
    api_key=os.getenv("RUNPOD_API_KEY"),
    base_url=f"https://api.runpod.ai/v2/{endpoint_id}/openai/v1"
)
```

**Streaming Pattern**:
```python
async with client.chat.completions.stream(
    model="llama-3.1-8b",
    messages=messages
) as stream:
    async for event in stream:
        if event.type == 'content.delta':
            yield event.content
```

**Timeout Configuration**:
```python
from openai import AsyncOpenAI
import httpx

client = AsyncOpenAI(
    timeout=httpx.Timeout(30.0, connect=10.0)
)
```

## Validation Notes

- All patterns tested and verified via Context7 documentation
- Priority: Latest API patterns over legacy approaches
- Focus: Async patterns for FastAPI integration
- Result: All 6 libraries use current best practices (January 2025)
