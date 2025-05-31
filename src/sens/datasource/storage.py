"""Cloud storage adapter for file uploads."""

import os
from pathlib import Path
from typing import Optional, BinaryIO
from abc import ABC, abstractmethod
import aiofiles
import boto3
from botocore.exceptions import NoCredentialsError
import structlog

logger = structlog.get_logger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    async def upload_file(self, file_path: str, file_content: bytes, content_type: str) -> str:
        """Upload a file and return its URL."""
        pass
    
    @abstractmethod
    async def download_file(self, file_path: str) -> bytes:
        """Download a file and return its content."""
        pass
    
    @abstractmethod
    async def delete_file(self, file_path: str) -> bool:
        """Delete a file."""
        pass
    
    @abstractmethod
    async def file_exists(self, file_path: str) -> bool:
        """Check if a file exists."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local file system storage backend."""
    
    def __init__(self, base_path: str = "/tmp/sens"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    async def upload_file(self, file_path: str, file_content: bytes, content_type: str) -> str:
        full_path = self.base_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(full_path, 'wb') as f:
            await f.write(file_content)
        
        return str(full_path)
    
    async def download_file(self, file_path: str) -> bytes:
        full_path = self.base_path / file_path
        
        async with aiofiles.open(full_path, 'rb') as f:
            return await f.read()
    
    async def delete_file(self, file_path: str) -> bool:
        full_path = self.base_path / file_path
        
        try:
            full_path.unlink()
            return True
        except FileNotFoundError:
            return False
    
    async def file_exists(self, file_path: str) -> bool:
        full_path = self.base_path / file_path
        return full_path.exists()


class S3StorageBackend(StorageBackend):
    """S3-compatible storage backend (works with AWS S3, Cloudflare R2, etc)."""
    
    def __init__(
        self,
        bucket_name: str,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        region_name: str = 'auto'
    ):
        self.bucket_name = bucket_name
        
        # Configure S3 client
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id or os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=secret_access_key or os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=region_name
        )
        
        # For Cloudflare R2, we need a different endpoint
        if endpoint_url and 'r2.cloudflarestorage.com' in endpoint_url:
            self.public_url_base = f"https://{bucket_name}.r2.dev"
        else:
            self.public_url_base = f"https://{bucket_name}.s3.amazonaws.com"
    
    async def upload_file(self, file_path: str, file_content: bytes, content_type: str) -> str:
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=file_content,
                ContentType=content_type
            )
            
            return f"{self.public_url_base}/{file_path}"
            
        except NoCredentialsError:
            logger.error("S3 credentials not found")
            raise
        except Exception as e:
            logger.error("S3 upload failed", error=str(e))
            raise
    
    async def download_file(self, file_path: str) -> bytes:
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=file_path
            )
            return response['Body'].read()
            
        except Exception as e:
            logger.error("S3 download failed", error=str(e))
            raise
    
    async def delete_file(self, file_path: str) -> bool:
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_path
            )
            return True
            
        except Exception as e:
            logger.error("S3 delete failed", error=str(e))
            return False
    
    async def file_exists(self, file_path: str) -> bool:
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=file_path
            )
            return True
        except:
            return False


class StorageManager:
    """Manages storage backend selection based on environment."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.backend = self._create_backend()
    
    def _create_backend(self) -> StorageBackend:
        """Create storage backend based on environment variables."""
        storage_type = os.getenv('SENS_STORAGE_TYPE', 'local')
        
        if storage_type == 's3' or storage_type == 'r2':
            bucket_name = os.getenv('SENS_STORAGE_BUCKET')
            if not bucket_name:
                logger.warning("S3 storage configured but no bucket name provided, falling back to local")
                return LocalStorageBackend()
            
            endpoint_url = os.getenv('SENS_STORAGE_ENDPOINT')
            
            return S3StorageBackend(
                bucket_name=bucket_name,
                endpoint_url=endpoint_url,
                access_key_id=os.getenv('SENS_STORAGE_ACCESS_KEY'),
                secret_access_key=os.getenv('SENS_STORAGE_SECRET_KEY'),
                region_name=os.getenv('SENS_STORAGE_REGION', 'auto')
            )
        else:
            return LocalStorageBackend(
                base_path=os.getenv('SENS_STORAGE_PATH', '/tmp/sens')
            )
    
    @property
    def storage(self) -> StorageBackend:
        return self.backend


# Singleton instance
storage_manager = StorageManager()