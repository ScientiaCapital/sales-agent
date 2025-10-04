"""
RunPod S3-Compatible Storage Service

Provides S3-compatible storage for documents, PDFs, audio files, and other assets.
Replaces Firebase Storage with RunPod's cost-effective infrastructure.
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

    Usage:
        storage = RunPodStorageService(datacenter="US-CA-2")
        url = storage.upload_file("document.pdf", "documents/document.pdf")
    """

    def __init__(
        self,
        datacenter: str = "US-CA-2",
        bucket_name: Optional[str] = None
    ):
        """
        Initialize RunPod Storage Service.

        Args:
            datacenter: RunPod datacenter region (default: US-CA-2)
            bucket_name: S3 bucket name (defaults to env var RUNPOD_S3_BUCKET_NAME)

        Raises:
            ValueError: If datacenter is invalid or bucket name not provided
        """
        self.datacenter = datacenter
        self.endpoint_url = RUNPOD_S3_ENDPOINTS.get(datacenter)

        if not self.endpoint_url:
            raise ValueError(
                f"Invalid datacenter: {datacenter}. "
                f"Valid options: {list(RUNPOD_S3_ENDPOINTS.keys())}"
            )

        # Initialize boto3 S3 client with RunPod credentials
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=os.getenv("RUNPOD_S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("RUNPOD_S3_SECRET_ACCESS_KEY"),
        )

        self.bucket_name = bucket_name or os.getenv("RUNPOD_S3_BUCKET_NAME")

        if not self.bucket_name:
            raise ValueError(
                "Bucket name must be provided or set in RUNPOD_S3_BUCKET_NAME env var"
            )

    def upload_file(
        self,
        file_path: str,
        object_name: str,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload a file to RunPod S3 storage.

        Args:
            file_path: Local file path to upload
            object_name: S3 object key (path in bucket)
            content_type: MIME type (e.g., 'application/pdf', 'audio/wav')

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

            # Generate public URL
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

        Useful for FastAPI UploadFile or BytesIO objects.

        Args:
            file_obj: File-like object (e.g., BytesIO, UploadFile.file)
            object_name: S3 object key
            content_type: MIME type

        Returns:
            URL to the uploaded file

        Raises:
            ClientError: If upload fails
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

        Raises:
            ClientError: If download fails
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

        Useful for secure sharing or time-limited downloads.

        Args:
            object_name: S3 object key
            expiration: URL validity in seconds (default: 1 hour)

        Returns:
            Presigned URL with expiration

        Raises:
            ClientError: If URL generation fails
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
            object_name: S3 object key to delete

        Raises:
            ClientError: If deletion fails
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
            prefix: S3 object key prefix (e.g., 'documents/', 'audio/')

        Returns:
            List of object keys matching the prefix

        Raises:
            ClientError: If listing fails
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
