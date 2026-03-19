"""
S3-compatible storage service

Supports multiple S3-compatible providers:
- AWS S3
- Alibaba Cloud OSS
- Tencent Cloud COS
- MinIO
- Any S3-compatible storage
- Local filesystem storage
"""

from src.infra.storage.s3.backends import (
    AliyunOssBackend,
    LocalStorageBackend,
    MinioS3Backend,
)
from src.infra.storage.s3.base import S3StorageBackend
from src.infra.storage.s3.service import (
    S3StorageService,
    close_storage,
    get_storage_service,
    init_storage,
)
from src.infra.storage.s3.types import S3Config, S3Provider, UploadResult

__all__ = [
    # Types
    "S3Config",
    "S3Provider",
    "UploadResult",
    # Base
    "S3StorageBackend",
    # Backends
    "AliyunOssBackend",
    "LocalStorageBackend",
    "MinioS3Backend",
    # Service
    "S3StorageService",
    "get_storage_service",
    "init_storage",
    "close_storage",
]
