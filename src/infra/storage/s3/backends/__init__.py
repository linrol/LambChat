from src.infra.storage.s3.backends.local import LocalStorageBackend
from src.infra.storage.s3.backends.minio import MinioS3Backend

try:
    from src.infra.storage.s3.backends.aliyun import AliyunOssBackend
except ImportError:
    AliyunOssBackend = None  # type: ignore[assignment,misc]

__all__ = [
    "AliyunOssBackend",
    "LocalStorageBackend",
    "MinioS3Backend",
]
