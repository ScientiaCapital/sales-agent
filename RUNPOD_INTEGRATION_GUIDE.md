# RunPod Integration Guide for Sales Agent

## Executive Summary

RunPod provides a comprehensive cloud infrastructure platform for AI workloads, offering:
- **Storage**: S3-compatible object storage for documents, PDFs, audio files
- **Serverless**: Auto-scaling GPU/CPU workers for AI inference (Cerebras, Claude, custom models)
- **Network Volumes**: Persistent storage for database backups and shared data
- **GPU Compute**: Cost-effective GPU pods for ML inference

This guide provides a complete integration path for the sales-agent project, including code examples, cost comparisons, and migration strategies from Firebase.

---

## Table of Contents

1. [Python SDK Setup](#python-sdk-setup)
2. [Storage Solutions](#storage-solutions)
3. [Serverless Deployment](#serverless-deployment)
4. [Network Volumes](#network-volumes)
5. [GPU Compute](#gpu-compute)
6. [Cost Optimization](#cost-optimization)
7. [Migration from Firebase](#migration-from-firebase)
8. [Integration Examples](#integration-examples)

---

## 1. Python SDK Setup

### Installation

```bash
# Install the latest release
pip install runpod

# Or using uv (faster alternative)
uv add runpod

# Install development version
pip install git+https://github.com/runpod/runpod-python.git
```

Add to `backend/requirements.txt`:
```python
runpod==1.2.0
```

### Authentication

**Option 1: Credentials File (Recommended for Development)**
```toml
# ~/.runpod/credentials.toml
[profile]
api_key = "YOUR_RUNPOD_API_KEY"
```

**Option 2: Environment Variable (Recommended for Production)**
```bash
# Add to .env
RUNPOD_API_KEY=your_runpod_api_key
```

**Option 3: Python Code**
```python
import runpod
import os

# Set API key
runpod.api_key = os.getenv("RUNPOD_API_KEY")

# Optional: Use named profile
runpod.profile = "production"
```

### CLI Configuration

```bash
# Configure API key
runpod config

# Or provide directly
runpod config YOUR_API_KEY

# Configure with profile
runpod config --profile production
```

---

## 2. Storage Solutions

### S3-Compatible Object Storage

RunPod provides S3-compatible storage accessible via standard AWS SDKs (boto3, AWS CLI).

#### **Setup S3 Storage Service**

Create `backend/app/services/runpod_storage.py`:

```python
"""
RunPod S3-Compatible Storage Service
"""
import os
import boto3
from botocore.exceptions import ClientError
from typing import Optional, BinaryIO
import logging

logger = logging.getLogger(__name__)

# RunPod S3 Endpoints by Datacenter
RUNPOD_S3_ENDPOINTS = {
    "EUR-IS-1": "https://s3api-eur-is-1.runpod.io/",
    "EU-RO-1": "https://s3api-eu-ro-1.runpod.io/",
    "EU-CZ-1": "https://s3api-eu-cz-1.runpod.io/",
    "US-KS-2": "https://s3api-us-ks-2.runpod.io/",
    "US-CA-2": "https://s3api-us-ca-2.runpod.io/",
}

class RunPodStorageService:
    """
    S3-compatible storage service for RunPod.
    Handles file uploads, downloads, and URL generation.
    """

    def __init__(
        self,
        datacenter: str = "US-CA-2",
        bucket_name: Optional[str] = None
    ):
        """
        Initialize RunPod Storage Service.

        Args:
            datacenter: RunPod datacenter region
            bucket_name: S3 bucket name (defaults to env var)
        """
        self.datacenter = datacenter
        self.endpoint_url = RUNPOD_S3_ENDPOINTS.get(datacenter)

        if not self.endpoint_url:
            raise ValueError(f"Invalid datacenter: {datacenter}")

        # Initialize boto3 S3 client
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=os.getenv("RUNPOD_S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("RUNPOD_S3_SECRET_ACCESS_KEY"),
        )

        self.bucket_name = bucket_name or os.getenv("RUNPOD_S3_BUCKET_NAME")

        if not self.bucket_name:
            raise ValueError("Bucket name must be provided or set in RUNPOD_S3_BUCKET_NAME")

    def upload_file(
        self,
        file_path: str,
        object_name: str,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload a file to RunPod S3 storage.

        Args:
            file_path: Local file path
            object_name: S3 object key (path in bucket)
            content_type: MIME type (e.g., 'application/pdf')

        Returns:
            URL to the uploaded file

        Raises:
            ClientError: If upload fails
        """
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type

        try:
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                object_name,
                ExtraArgs=extra_args
            )

            # Generate URL
            url = f"{self.endpoint_url}{self.bucket_name}/{object_name}"
            logger.info(f"Uploaded {file_path} to {url}")
            return url

        except ClientError as e:
            logger.error(f"Failed to upload {file_path}: {e}")
            raise

    def upload_fileobj(
        self,
        file_obj: BinaryIO,
        object_name: str,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload a file-like object to RunPod S3 storage.

        Args:
            file_obj: File-like object (e.g., BytesIO)
            object_name: S3 object key
            content_type: MIME type

        Returns:
            URL to the uploaded file
        """
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type

        try:
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                object_name,
                ExtraArgs=extra_args
            )

            url = f"{self.endpoint_url}{self.bucket_name}/{object_name}"
            logger.info(f"Uploaded file object to {url}")
            return url

        except ClientError as e:
            logger.error(f"Failed to upload file object: {e}")
            raise

    def download_file(self, object_name: str, local_path: str) -> None:
        """
        Download a file from RunPod S3 storage.

        Args:
            object_name: S3 object key
            local_path: Local destination path
        """
        try:
            self.s3_client.download_file(
                self.bucket_name,
                object_name,
                local_path
            )
            logger.info(f"Downloaded {object_name} to {local_path}")

        except ClientError as e:
            logger.error(f"Failed to download {object_name}: {e}")
            raise

    def generate_presigned_url(
        self,
        object_name: str,
        expiration: int = 3600
    ) -> str:
        """
        Generate a presigned URL for temporary access.

        Args:
            object_name: S3 object key
            expiration: URL validity in seconds (default: 1 hour)

        Returns:
            Presigned URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': object_name
                },
                ExpiresIn=expiration
            )
            return url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    def delete_file(self, object_name: str) -> None:
        """
        Delete a file from RunPod S3 storage.

        Args:
            object_name: S3 object key
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=object_name
            )
            logger.info(f"Deleted {object_name}")

        except ClientError as e:
            logger.error(f"Failed to delete {object_name}: {e}")
            raise

    def list_files(self, prefix: str = "") -> list[str]:
        """
        List files in the bucket with optional prefix filter.

        Args:
            prefix: S3 object key prefix (e.g., 'documents/')

        Returns:
            List of object keys
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )

            if 'Contents' not in response:
                return []

            return [obj['Key'] for obj in response['Contents']]

        except ClientError as e:
            logger.error(f"Failed to list files: {e}")
            raise
```

#### **Environment Variables**

Add to `.env`:
```bash
# RunPod S3 Storage
RUNPOD_S3_ACCESS_KEY_ID=your_access_key_id
RUNPOD_S3_SECRET_ACCESS_KEY=your_secret_access_key
RUNPOD_S3_BUCKET_NAME=sales-agent-storage
RUNPOD_S3_DATACENTER=US-CA-2  # Choose closest to your users
```

#### **Usage Example**

```python
from app.services.runpod_storage import RunPodStorageService

# Initialize storage service
storage = RunPodStorageService(datacenter="US-CA-2")

# Upload PDF document
pdf_url = storage.upload_file(
    file_path="/tmp/lead_report.pdf",
    object_name="reports/lead_report_2024.pdf",
    content_type="application/pdf"
)

# Upload audio file from FastAPI UploadFile
from fastapi import UploadFile
async def upload_audio(file: UploadFile):
    audio_url = storage.upload_fileobj(
        file_obj=file.file,
        object_name=f"audio/{file.filename}",
        content_type=file.content_type
    )
    return audio_url

# Generate temporary access URL (1 hour)
temp_url = storage.generate_presigned_url(
    object_name="reports/lead_report_2024.pdf",
    expiration=3600
)

# List all documents
documents = storage.list_files(prefix="documents/")
```

### **RunPod SDK Upload Utilities**

For serverless workers, use RunPod's built-in upload utilities:

```python
from runpod.serverless.utils import upload_file_to_bucket, upload_in_memory_object

# Upload local file
bucket_creds = {
    'endpointUrl': 'https://s3api-us-ca-2.runpod.io/',
    'accessId': os.getenv('RUNPOD_S3_ACCESS_KEY_ID'),
    'accessSecret': os.getenv('RUNPOD_S3_SECRET_ACCESS_KEY'),
    'bucketName': 'sales-agent-storage'
}

presigned_url = upload_file_to_bucket(
    file_name='processed_audio.wav',
    file_location='/tmp/audio.wav',
    bucket_creds=bucket_creds,
    prefix='audio/'
)

# Upload in-memory data
data = b"Generated report content"
presigned_url = upload_in_memory_object(
    file_name='report.txt',
    file_data=data,
    bucket_creds=bucket_creds,
    prefix='reports/'
)
```

---

## 3. Serverless Deployment

### **Overview**

RunPod Serverless enables auto-scaling AI inference without managing infrastructure:
- **Auto-scaling**: 0 to 100+ workers based on demand
- **Cost-effective**: Pay only for compute time used
- **GPU/CPU support**: Choose optimal hardware
- **Fast cold starts**: <5s with FlashBoot

### **Create Serverless Worker**

Create `backend/runpod_workers/lead_qualification_worker.py`:

```python
"""
RunPod Serverless Worker for Lead Qualification
Uses Cerebras for ultra-fast inference
"""
import runpod
import os
from openai import OpenAI

# Initialize Cerebras client
cerebras_client = OpenAI(
    api_key=os.getenv("CEREBRAS_API_KEY"),
    base_url="https://api.cerebras.ai/v1"
)

def handler(job):
    """
    Handler for lead qualification jobs.

    Args:
        job: RunPod job object with 'input' containing lead data

    Returns:
        dict: Qualification results
    """
    try:
        # Extract input
        job_input = job.get("input", {})
        company_name = job_input.get("company_name")
        industry = job_input.get("industry")
        company_size = job_input.get("company_size")

        if not company_name:
            return {"error": "Missing required field: company_name"}

        # Build prompt
        prompt = f"""Analyze this lead and provide a qualification score (0-100):

Company: {company_name}
Industry: {industry or 'Unknown'}
Size: {company_size or 'Unknown'}

Provide:
1. Qualification Score (0-100)
2. Reasoning
3. Next Steps

Format as JSON."""

        # Call Cerebras (ultra-fast inference)
        response = cerebras_client.chat.completions.create(
            model="llama3.1-8b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7
        )

        result = response.choices[0].message.content

        return {
            "qualification_result": result,
            "model": "llama3.1-8b",
            "latency_ms": int(response.usage.total_tokens * 0.1)  # Estimated
        }

    except Exception as e:
        return {"error": str(e)}

# Start serverless worker
runpod.serverless.start({"handler": handler})
```

### **Create Docker Image**

Create `backend/runpod_workers/Dockerfile`:

```dockerfile
FROM runpod/base:0.6.2-cpu

# Install dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker code
COPY lead_qualification_worker.py .

# Set handler as entrypoint
CMD ["python", "lead_qualification_worker.py"]
```

Create `backend/runpod_workers/requirements.txt`:

```
runpod==1.2.0
openai>=1.0.0
```

### **Build and Push Image**

```bash
cd backend/runpod_workers

# Build Docker image
docker build -t your-dockerhub-username/lead-qualification-worker:latest .

# Push to Docker Hub
docker push your-dockerhub-username/lead-qualification-worker:latest
```

### **Deploy Serverless Endpoint**

**Option 1: RunPod Console**
1. Go to [RunPod Console](https://www.runpod.io/console/serverless)
2. Click "New Endpoint"
3. Configure:
   - **Name**: "Lead Qualification"
   - **Container Image**: `your-dockerhub-username/lead-qualification-worker:latest`
   - **GPU Type**: RTX 3090 (or CPU for cost savings)
   - **Workers Min**: 0
   - **Workers Max**: 10
   - **Scaler Type**: QUEUE_DELAY
   - **Scaler Value**: 30 seconds
   - **Idle Timeout**: 60 seconds
4. Click "Deploy"

**Option 2: Python SDK**

```python
import runpod
import os

runpod.api_key = os.getenv("RUNPOD_API_KEY")

# Create serverless endpoint
endpoint = runpod.create_endpoint(
    name="Lead Qualification",
    template_id="your_template_id",  # From Docker image
    gpu_type_ids=["NVIDIA GeForce RTX 3090"],
    workers_min=0,
    workers_max=10,
    scaler_type="QUEUE_DELAY",
    scaler_value=30,
    idle_timeout=60,
    flashboot=True  # Enable fast cold starts
)

print(f"Endpoint created: {endpoint['id']}")
```

### **Integrate into FastAPI Backend**

Update `backend/app/services/cerebras.py`:

```python
"""
Cerebras Service with RunPod Serverless Integration
"""
import runpod
import os
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class CerebrasService:
    """
    Handles lead qualification via RunPod Serverless + Cerebras.
    """

    def __init__(self):
        runpod.api_key = os.getenv("RUNPOD_API_KEY")
        self.endpoint = runpod.Endpoint(os.getenv("RUNPOD_ENDPOINT_ID"))

    async def qualify_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Qualify a lead using RunPod Serverless + Cerebras.

        Args:
            lead_data: Lead information

        Returns:
            Qualification results
        """
        try:
            # Submit job (async)
            run_request = self.endpoint.run(
                {
                    "company_name": lead_data.get("company_name"),
                    "industry": lead_data.get("industry"),
                    "company_size": lead_data.get("company_size")
                }
            )

            # Wait for completion (blocks until done)
            result = run_request.output()

            logger.info(f"Lead qualification completed: {result}")
            return result

        except Exception as e:
            logger.error(f"Lead qualification failed: {e}")
            raise
```

Add to `.env`:
```bash
RUNPOD_ENDPOINT_ID=your_endpoint_id_from_console
```

---

## 4. Network Volumes

### **Overview**

Network volumes provide persistent, shared storage:
- **Persistent**: Data survives pod/worker restarts
- **Shared**: Multiple workers access same data
- **S3-compatible**: Access via S3 API without running pods
- **Use cases**: Model weights, datasets, database backups

### **Create Network Volume**

**Console Method:**
1. Go to [Storage](https://www.runpod.io/console/user/storage)
2. Click "New Network Volume"
3. Configure:
   - **Datacenter**: US-CA-2 (choose closest to workers)
   - **Name**: "sales-agent-models"
   - **Size**: 100 GB
4. Click "Create"

**Python SDK Method:**

```python
import runpod

runpod.api_key = os.getenv("RUNPOD_API_KEY")

# Create network volume
volume = runpod.create_network_volume(
    name="sales-agent-models",
    size=100,  # GB
    datacenter="US-CA-2"
)

print(f"Volume created: {volume['id']}")
```

### **Access Network Volume in Serverless Workers**

Update worker to use network volume:

```python
import os

def handler(event, context):
    """Handler with network volume access."""
    volume_path = "/runpod-volume"

    # Read model from volume
    model_file = os.path.join(volume_path, "models/cerebras_model.pth")

    if os.path.exists(model_file):
        with open(model_file, "rb") as f:
            model_data = f.read()
            print(f"Loaded model from volume: {len(model_data)} bytes")

    # Write results to volume
    results_file = os.path.join(volume_path, "results/lead_scores.json")
    with open(results_file, "w") as f:
        f.write('{"scores": [95, 87, 72]}')

    return {"statusCode": 200}
```

### **Attach Volume to Endpoint**

When creating endpoint, specify `networkVolumeId`:

```python
endpoint = runpod.create_endpoint(
    name="Lead Qualification",
    network_volume_id="your_volume_id",  # Attach volume
    volume_mount_path="/runpod-volume",  # Mount point
    # ... other config
)
```

---

## 5. GPU Compute (On-Demand Pods)

### **Overview**

For long-running GPU tasks (model training, batch processing):
- **On-Demand Pods**: Reliable, persistent GPU instances
- **Spot Pods**: Up to 70% cheaper (can be interrupted)

### **Create GPU Pod**

```python
import runpod

runpod.api_key = os.getenv("RUNPOD_API_KEY")

# Create on-demand GPU pod
pod = runpod.create_pod(
    name="Lead Processing",
    image="runpod/pytorch:2.1.0-py3.10-cuda11.8.0",
    gpu_type_id="NVIDIA GeForce RTX 3090",
    cloud_type="SECURE",  # or "COMMUNITY" for lower cost
    volume_in_gb=50,
    container_disk_in_gb=20,
    ports="8888/http,22/tcp",
    env=[
        {"key": "JUPYTER_PASSWORD", "value": "secure_password"}
    ]
)

print(f"Pod created: {pod['id']}")

# Get pod details
pod_info = runpod.get_pod(pod['id'])
print(f"Pod IP: {pod_info['machine']['publicIp']}")

# Stop pod (saves costs when not in use)
runpod.stop_pod(pod['id'])

# Resume pod
runpod.resume_pod(pod['id'])

# Terminate pod
runpod.terminate_pod(pod['id'])
```

---

## 6. Cost Optimization

### **RunPod vs Firebase Storage Pricing Comparison**

| Feature | RunPod S3 Storage | Firebase Storage | Notes |
|---------|-------------------|------------------|-------|
| **Storage** | $0.023/GB/month | $0.026/GB/month | RunPod 12% cheaper |
| **Download** | $0.09/GB | $0.12/GB | RunPod 25% cheaper |
| **Upload** | Free | Free | Same |
| **Operations** | $0.005/10k requests | $0.05/10k writes | RunPod 90% cheaper for writes |

**Example: 100 GB storage + 500 GB downloads/month**
- Firebase: (100 × $0.026) + (500 × $0.12) = $62.60/month
- RunPod: (100 × $0.023) + (500 × $0.09) = $47.30/month
- **Savings: $15.30/month (24%)**

### **Serverless GPU Pricing**

| GPU Type | RunPod Price | On-Demand Price | Savings |
|----------|--------------|-----------------|---------|
| RTX 3090 | $0.34/hr | $1.50/hr | 77% |
| RTX 4090 | $0.69/hr | $2.00/hr | 65% |
| A100 80GB | $1.89/hr | $4.00/hr | 53% |

**Cost Optimization Strategies:**

1. **Auto-scaling**: Set `workersMin: 0` to scale to zero when idle
2. **FlashBoot**: Enable for <5s cold starts (reduce wasted idle time)
3. **CPU Workers**: Use for non-GPU tasks (95% cheaper)
4. **Spot Instances**: Use for non-critical batch jobs (70% cheaper)
5. **Network Volumes**: Share data between workers (avoid redundant downloads)

---

## 7. Migration from Firebase

### **Phase 1: Storage Migration**

**Step 1: Set up RunPod Storage Service**
```bash
# Add credentials to .env
RUNPOD_S3_ACCESS_KEY_ID=...
RUNPOD_S3_SECRET_ACCESS_KEY=...
RUNPOD_S3_BUCKET_NAME=sales-agent-storage
```

**Step 2: Create Migration Script**

Create `scripts/migrate_firebase_to_runpod.py`:

```python
"""
Migrate files from Firebase Storage to RunPod S3
"""
import firebase_admin
from firebase_admin import credentials, storage as firebase_storage
from app.services.runpod_storage import RunPodStorageService
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_firebase_to_runpod():
    """Migrate all files from Firebase to RunPod."""

    # Initialize Firebase
    cred = credentials.Certificate("firebase_credentials.json")
    firebase_admin.initialize_app(cred, {
        'storageBucket': 'your-firebase-bucket.appspot.com'
    })
    bucket = firebase_storage.bucket()

    # Initialize RunPod storage
    runpod_storage = RunPodStorageService(datacenter="US-CA-2")

    # List all Firebase files
    blobs = bucket.list_blobs()

    for blob in blobs:
        try:
            # Download from Firebase to temp
            temp_path = f"/tmp/{blob.name}"
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            blob.download_to_filename(temp_path)

            # Upload to RunPod
            runpod_storage.upload_file(
                file_path=temp_path,
                object_name=blob.name,
                content_type=blob.content_type
            )

            logger.info(f"Migrated: {blob.name}")

            # Clean up temp file
            os.remove(temp_path)

        except Exception as e:
            logger.error(f"Failed to migrate {blob.name}: {e}")

    logger.info("Migration complete!")

if __name__ == "__main__":
    migrate_firebase_to_runpod()
```

**Step 3: Run Migration**
```bash
python scripts/migrate_firebase_to_runpod.py
```

**Step 4: Update Code**

Replace Firebase imports:
```python
# OLD: Firebase
from firebase_admin import storage
bucket = storage.bucket()
blob = bucket.blob("documents/report.pdf")
blob.upload_from_filename("/tmp/report.pdf")

# NEW: RunPod
from app.services.runpod_storage import RunPodStorageService
storage = RunPodStorageService()
url = storage.upload_file(
    file_path="/tmp/report.pdf",
    object_name="documents/report.pdf"
)
```

### **Phase 2: Serverless Migration**

Migrate existing AI inference to RunPod Serverless:

1. **Create worker** (see Section 3)
2. **Deploy endpoint**
3. **Update FastAPI routes** to use RunPod endpoint
4. **Test thoroughly**
5. **Switch over** (update environment variables)

---

## 8. Integration Examples

### **Example 1: PDF Document Processing**

```python
from fastapi import UploadFile
from app.services.runpod_storage import RunPodStorageService
import runpod

storage = RunPodStorageService()
endpoint = runpod.Endpoint(os.getenv("RUNPOD_PDF_PROCESSOR_ENDPOINT"))

async def process_pdf(file: UploadFile):
    """Process uploaded PDF using RunPod Serverless."""

    # 1. Upload PDF to RunPod S3
    pdf_url = storage.upload_fileobj(
        file_obj=file.file,
        object_name=f"pdfs/{file.filename}",
        content_type="application/pdf"
    )

    # 2. Submit processing job
    job = endpoint.run({"pdf_url": pdf_url})

    # 3. Wait for results
    result = job.output()

    return result
```

### **Example 2: Audio Transcription with Cartesia**

```python
import runpod
from app.services.runpod_storage import RunPodStorageService

storage = RunPodStorageService()
endpoint = runpod.Endpoint(os.getenv("RUNPOD_AUDIO_TRANSCRIPTION_ENDPOINT"))

async def transcribe_audio(audio_file: UploadFile):
    """Transcribe audio using RunPod + Cartesia."""

    # Upload audio to RunPod S3
    audio_url = storage.upload_fileobj(
        file_obj=audio_file.file,
        object_name=f"audio/{audio_file.filename}",
        content_type=audio_file.content_type
    )

    # Submit transcription job
    job = endpoint.run({
        "audio_url": audio_url,
        "language": "en"
    })

    # Get transcription
    result = job.output()

    return {
        "transcription": result["text"],
        "audio_url": audio_url
    }
```

### **Example 3: Batch Lead Enrichment**

```python
import runpod
from typing import List, Dict

endpoint = runpod.Endpoint(os.getenv("RUNPOD_LEAD_ENRICHMENT_ENDPOINT"))

async def enrich_leads_batch(leads: List[Dict]):
    """Enrich multiple leads in parallel using RunPod."""

    # Submit all jobs asynchronously
    jobs = []
    for lead in leads:
        job = endpoint.run({
            "company_name": lead["company_name"],
            "website": lead.get("website")
        })
        jobs.append((lead["id"], job))

    # Collect results
    enriched_leads = []
    for lead_id, job in jobs:
        result = job.output()
        enriched_leads.append({
            "lead_id": lead_id,
            "enrichment": result
        })

    return enriched_leads
```

### **Example 4: Database Backup to Network Volume**

```python
import os
import subprocess
from datetime import datetime

def backup_database_to_runpod_volume():
    """Backup PostgreSQL database to RunPod Network Volume."""

    # Generate backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_{timestamp}.sql"

    # Dump database
    subprocess.run([
        "pg_dump",
        "-h", "localhost",
        "-U", "sales_agent",
        "-d", "sales_agent_db",
        "-f", backup_file
    ])

    # Copy to RunPod volume (assuming volume is mounted)
    volume_path = "/runpod-volume/backups"
    os.makedirs(volume_path, exist_ok=True)
    subprocess.run(["cp", backup_file, f"{volume_path}/{backup_file}"])

    print(f"Backup saved to RunPod volume: {backup_file}")
```

---

## Environment Variables Reference

Add to `.env`:

```bash
# RunPod API
RUNPOD_API_KEY=your_runpod_api_key

# RunPod S3 Storage
RUNPOD_S3_ACCESS_KEY_ID=your_s3_access_key
RUNPOD_S3_SECRET_ACCESS_KEY=your_s3_secret_key
RUNPOD_S3_BUCKET_NAME=sales-agent-storage
RUNPOD_S3_DATACENTER=US-CA-2  # Choose: EUR-IS-1, EU-RO-1, EU-CZ-1, US-KS-2, US-CA-2

# RunPod Serverless Endpoints
RUNPOD_LEAD_QUALIFICATION_ENDPOINT=your_endpoint_id
RUNPOD_PDF_PROCESSOR_ENDPOINT=your_endpoint_id
RUNPOD_AUDIO_TRANSCRIPTION_ENDPOINT=your_endpoint_id

# RunPod Network Volume
RUNPOD_NETWORK_VOLUME_ID=your_volume_id
```

---

## Next Steps

1. **Set up RunPod account** at [runpod.io](https://www.runpod.io)
2. **Generate API key** in account settings
3. **Create S3 bucket** credentials
4. **Implement RunPodStorageService** from Section 2
5. **Migrate critical files** from Firebase (Section 7)
6. **Deploy first serverless worker** (Section 3)
7. **Test integration** with existing FastAPI backend
8. **Monitor costs** and optimize worker scaling

---

## Resources

- **RunPod Documentation**: https://docs.runpod.io
- **RunPod Python SDK**: https://github.com/runpod/runpod-python
- **S3 API Reference**: https://docs.runpod.io/serverless/storage/s3-api
- **Community Support**: https://discord.gg/runpod
