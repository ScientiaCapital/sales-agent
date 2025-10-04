# RunPod S3 Storage Implementation

## Service Implementation

**File**: `backend/app/services/runpod_storage.py` (276 lines)

### Key Patterns

**S3-Compatible Storage with boto3**:
```python
class RunPodStorageService:
    def __init__(self, datacenter: str = "US-CA-2", bucket_name: Optional[str] = None):
        self.endpoint_url = RUNPOD_S3_ENDPOINTS.get(datacenter)
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=os.getenv("RUNPOD_S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("RUNPOD_S3_SECRET_ACCESS_KEY"),
        )
```

### Available Datacenters

```python
RUNPOD_S3_ENDPOINTS = {
    "EUR-IS-1": "https://s3api-eur-is-1.runpod.io/",
    "EU-RO-1": "https://s3api-eu-ro-1.runpod.io/",
    "EU-CZ-1": "https://s3api-eu-cz-1.runpod.io/",
    "US-KS-2": "https://s3api-us-ks-2.runpod.io/",
    "US-CA-2": "https://s3api-us-ca-2.runpod.io/",
}
```

### Core Methods

1. **upload_file(file_path, object_name, content_type)** - Upload local file, returns public URL
2. **upload_fileobj(file_obj, object_name, content_type)** - Upload BytesIO/UploadFile
3. **download_file(object_name, local_path)** - Download to local path
4. **generate_presigned_url(object_name, expiration=3600)** - Temporary access URL
5. **delete_file(object_name)** - Delete from storage
6. **list_files(prefix="")** - List files with optional prefix filter

### Environment Configuration

```bash
RUNPOD_API_KEY=your_runpod_api_key_here
RUNPOD_S3_ACCESS_KEY_ID=your_runpod_s3_access_key_here
RUNPOD_S3_SECRET_ACCESS_KEY=your_runpod_s3_secret_key_here
RUNPOD_S3_BUCKET_NAME=sales-agent-storage
RUNPOD_S3_DATACENTER=US-CA-2
```

### Integration Points

**Added to** `backend/app/services/__init__.py`:
```python
from .cerebras import CerebrasService
from .runpod_storage import RunPodStorageService
# Firebase disabled - using RunPod instead
```

**Added to** `backend/requirements.txt`:
```python
runpod==1.7.6  # RunPod Python SDK for serverless and GPU compute
boto3==1.35.80  # AWS SDK for S3-compatible RunPod storage
```

### Usage Pattern

```python
from app.services.runpod_storage import RunPodStorageService

storage = RunPodStorageService(datacenter="US-CA-2")

# Upload FastAPI file
url = storage.upload_fileobj(
    upload_file.file, 
    f"documents/{upload_file.filename}",
    content_type=upload_file.content_type
)

# Generate presigned URL for secure sharing
presigned_url = storage.generate_presigned_url("documents/report.pdf", expiration=3600)
```

## Replaces Firebase

This implementation completely replaces Firebase Storage, providing:
- S3-compatible API via boto3
- 5 global datacenters for low latency
- Presigned URLs for secure temporary access
- Support for all file types (PDFs, audio, images, documents)
