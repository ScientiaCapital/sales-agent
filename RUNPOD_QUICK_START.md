# RunPod Quick Start Guide

## 5-Minute Setup

### 1. Install RunPod SDK

```bash
pip install runpod boto3
```

### 2. Configure Environment

Add to `.env`:
```bash
RUNPOD_API_KEY=your_api_key_here
RUNPOD_S3_ACCESS_KEY_ID=your_s3_key
RUNPOD_S3_SECRET_ACCESS_KEY=your_s3_secret
RUNPOD_S3_BUCKET_NAME=sales-agent-storage
```

### 3. Create Storage Service

Copy `RunPodStorageService` from main guide to:
```
backend/app/services/runpod_storage.py
```

### 4. Upload Your First File

```python
from app.services.runpod_storage import RunPodStorageService

storage = RunPodStorageService(datacenter="US-CA-2")
url = storage.upload_file(
    file_path="document.pdf",
    object_name="documents/document.pdf"
)
print(f"Uploaded: {url}")
```

---

## Common Use Cases

### File Upload (FastAPI)

```python
from fastapi import UploadFile
from app.services.runpod_storage import RunPodStorageService

storage = RunPodStorageService()

@app.post("/upload")
async def upload_file(file: UploadFile):
    url = storage.upload_fileobj(
        file_obj=file.file,
        object_name=f"uploads/{file.filename}",
        content_type=file.content_type
    )
    return {"url": url}
```

### Serverless AI Inference

```python
import runpod

runpod.api_key = os.getenv("RUNPOD_API_KEY")
endpoint = runpod.Endpoint("your_endpoint_id")

# Submit job
job = endpoint.run({"prompt": "Analyze this lead..."})

# Get result
result = job.output()
```

### Database Backup to Network Volume

```python
# Assuming volume mounted at /runpod-volume
import subprocess
from datetime import datetime

backup_file = f"backup_{datetime.now().strftime('%Y%m%d')}.sql"
subprocess.run([
    "pg_dump", "-U", "sales_agent", "-d", "sales_agent_db",
    "-f", f"/runpod-volume/backups/{backup_file}"
])
```

---

## Pricing Cheat Sheet

### Storage (S3-Compatible)
- Storage: **$0.023/GB/month**
- Download: **$0.09/GB**
- Uploads: **Free**

### Serverless GPU (per hour)
- RTX 3090: **$0.34/hr** (auto-scale from 0)
- RTX 4090: **$0.69/hr**
- A100 80GB: **$1.89/hr**

### Network Volumes
- **$0.10/GB/month** (persistent storage)

---

## Cost Comparison: RunPod vs Firebase

**Scenario**: 100 GB storage + 500 GB downloads/month

| Provider | Monthly Cost | Savings |
|----------|--------------|---------|
| Firebase Storage | $62.60 | - |
| RunPod S3 Storage | $47.30 | **24%** |

---

## S3 Datacenter Endpoints

Choose closest to your users:

| Region | Endpoint |
|--------|----------|
| Europe (Iceland) | `https://s3api-eur-is-1.runpod.io/` |
| Europe (Romania) | `https://s3api-eu-ro-1.runpod.io/` |
| Europe (Czech) | `https://s3api-eu-cz-1.runpod.io/` |
| US (Kansas) | `https://s3api-us-ks-2.runpod.io/` |
| US (California) | `https://s3api-us-ca-2.runpod.io/` |

---

## Deployment Checklist

- [ ] Create RunPod account
- [ ] Generate API key
- [ ] Create S3 credentials
- [ ] Add environment variables to `.env`
- [ ] Install `runpod` and `boto3`
- [ ] Copy `RunPodStorageService` to project
- [ ] Test file upload
- [ ] Create Docker image for serverless worker
- [ ] Deploy first serverless endpoint
- [ ] Update FastAPI routes to use RunPod
- [ ] Monitor costs in RunPod console

---

## Support

- **Docs**: https://docs.runpod.io
- **GitHub**: https://github.com/runpod/runpod-python
- **Discord**: https://discord.gg/runpod

---

## Next Steps

1. Read full guide: `RUNPOD_INTEGRATION_GUIDE.md`
2. Implement storage service
3. Deploy serverless worker
4. Monitor and optimize costs
