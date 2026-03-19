"""
S3 storage backend using minio library.

Compatible with AWS S3, MinIO, Tencent COS, and any S3-compatible provider.
"""

from __future__ import annotations

import asyncio
import io
from datetime import datetime, timezone
from typing import TYPE_CHECKING, BinaryIO, Optional

from src.infra.logging import get_logger
from src.infra.storage.s3.base import S3StorageBackend
from src.infra.storage.s3.types import S3Config, S3Provider, UploadResult

if TYPE_CHECKING:
    import minio

logger = get_logger(__name__)


class MinioS3Backend(S3StorageBackend):
    """S3 storage backend using minio library"""

    def __init__(self, config: S3Config):
        self.config = config
        self._client: minio.Minio | None = None

    def _get_client(self):
        """Get or create minio S3 client"""
        if self._client is None:
            import minio

            endpoint: str | None = self.config.endpoint_url or self.config.get_endpoint_url()
            if endpoint:
                endpoint = endpoint.replace("https://", "").replace("http://", "")
            else:
                endpoint = "localhost:9000"

            logger.info(
                f"Minio client config: endpoint={endpoint}, bucket={self.config.bucket_name}, "
                f"region={self.config.region}, access_key length={len(self.config.access_key)}"
            )

            self._client = minio.Minio(
                endpoint=endpoint,
                access_key=self.config.access_key,
                secret_key=self.config.secret_key,
                secure=True,
                region=(self.config.region if self.config.provider != S3Provider.AWS else None),
            )

        return self._client

    async def upload(
        self,
        file: BinaryIO,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> UploadResult:
        import mimetypes

        if not content_type:
            content_type, _ = mimetypes.guess_type(key)
            if not content_type:
                content_type = "application/octet-stream"

        content = file.read()
        file_size = len(content)
        file.seek(0)

        loop = asyncio.get_running_loop()
        client = self._get_client()

        def _put_object():
            data = io.BytesIO(content)
            return client.put_object(
                bucket_name=self.config.bucket_name,
                object_name=key,
                data=data,
                length=file_size,
                content_type=content_type,
                metadata=metadata or {},
            )

        result = await loop.run_in_executor(None, _put_object)

        return UploadResult(
            key=key,
            url=self.config.get_public_url(key),
            size=file_size,
            content_type=content_type,
            etag=result.etag,
            last_modified=datetime.now(timezone.utc),
        )

    async def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> UploadResult:
        return await self.upload(io.BytesIO(data), key, content_type, metadata)

    async def download(self, key: str) -> bytes:
        loop = asyncio.get_running_loop()
        client = self._get_client()

        def _get_object():
            response = client.get_object(
                bucket_name=self.config.bucket_name,
                object_name=key,
            )
            return response.read()

        return await loop.run_in_executor(None, _get_object)

    async def get_size(self, key: str) -> int:
        loop = asyncio.get_running_loop()
        client = self._get_client()

        def _stat():
            stat = client.stat_object(
                bucket_name=self.config.bucket_name,
                object_name=key,
            )
            return stat.size

        return await loop.run_in_executor(None, _stat)

    async def download_range(self, key: str, start: int, end: int) -> bytes:
        loop = asyncio.get_running_loop()
        client = self._get_client()
        length = end - start + 1

        def _get_range():
            response = client.get_object(
                bucket_name=self.config.bucket_name,
                object_name=key,
                offset=start,
                length=length,
            )
            return response.read()

        return await loop.run_in_executor(None, _get_range)

    async def delete(self, key: str) -> bool:
        loop = asyncio.get_running_loop()
        client = self._get_client()

        def _delete_object():
            client.remove_object(
                bucket_name=self.config.bucket_name,
                object_name=key,
            )
            return True

        return await loop.run_in_executor(None, _delete_object)

    async def exists(self, key: str) -> bool:
        loop = asyncio.get_running_loop()
        client = self._get_client()

        def _stat_object():
            try:
                client.stat_object(
                    bucket_name=self.config.bucket_name,
                    object_name=key,
                )
                return True
            except Exception:
                return False

        return await loop.run_in_executor(None, _stat_object)

    async def get_url(self, key: str) -> str:
        return self.config.get_public_url(key)

    async def get_presigned_url(self, key: str, expires: int = 3600) -> str:
        loop = asyncio.get_running_loop()
        client = self._get_client()

        def _presigned_url():
            from datetime import timedelta

            return client.presigned_get_object(
                bucket_name=self.config.bucket_name,
                object_name=key,
                expires=timedelta(seconds=expires),
            )

        return await loop.run_in_executor(None, _presigned_url)

    async def list_objects(self, prefix: str = "") -> list[str]:
        loop = asyncio.get_running_loop()
        client = self._get_client()

        def _list_objects():
            objects = []
            for obj in client.list_objects(
                bucket_name=self.config.bucket_name,
                prefix=prefix,
                recursive=True,
            ):
                objects.append(obj.object_name)
            return objects

        return await loop.run_in_executor(None, _list_objects)

    async def close(self) -> None:
        self._client = None
