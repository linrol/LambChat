"""
Aliyun OSS storage backend using official oss2 library.
"""

from __future__ import annotations

import asyncio
import io
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import BinaryIO, Optional

import oss2

from src.infra.logging import get_logger
from src.infra.storage.s3.base import S3StorageBackend
from src.infra.storage.s3.types import S3Config, UploadResult

logger = get_logger(__name__)


class AliyunOssBackend(S3StorageBackend):
    """Aliyun OSS storage backend using official oss2 library"""

    def __init__(self, config: S3Config):
        self.config = config
        self._bucket = None

    def _get_bucket(self):
        """Get or create Aliyun OSS bucket"""
        if self._bucket is None:
            endpoint = self.config.endpoint_url or f"oss-{self.config.region}.aliyuncs.com"
            endpoint = endpoint.replace("https://", "").replace("http://", "")

            auth = oss2.Auth(self.config.access_key, self.config.secret_key)

            logger.info(
                f"Aliyun OSS client config: endpoint={endpoint}, bucket={self.config.bucket_name}, "
                f"region={self.config.region}"
            )

            self._bucket = oss2.Bucket(
                auth,
                f"https://{endpoint}",
                self.config.bucket_name,
                connect_timeout=30,
            )

        return self._bucket

    async def upload(
        self,
        file: BinaryIO,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> UploadResult:
        content = file.read()
        file_size = len(content)
        file.seek(0)

        loop = asyncio.get_running_loop()
        bucket = self._get_bucket()

        def _put_object():
            headers = {}
            if content_type:
                headers["Content-Type"] = content_type
            if metadata:
                headers.update(metadata)
            return bucket.put_object(key, content, headers=headers)

        result = await loop.run_in_executor(None, _put_object)

        return UploadResult(
            key=key,
            url=self.config.get_public_url(key),
            size=file_size,
            content_type=content_type or "application/octet-stream",
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
        bucket = self._get_bucket()

        def _get_object():
            result = bucket.get_object(key)
            return result.read()

        return await loop.run_in_executor(None, _get_object)

    async def get_size(self, key: str) -> int:
        loop = asyncio.get_running_loop()
        bucket = self._get_bucket()

        def _head():
            head = bucket.head_object(key)
            return head.content_length

        return await loop.run_in_executor(None, _head)

    async def download_range(self, key: str, start: int, end: int) -> bytes:
        loop = asyncio.get_running_loop()
        bucket = self._get_bucket()

        def _get_range():
            result = bucket.get_object(key, byte_range=(start, end))
            return result.read()

        return await loop.run_in_executor(None, _get_range)

    async def download_stream(
        self, key: str, chunk_size: int = 1024 * 1024
    ) -> AsyncIterator[bytes]:
        """Stream download from OSS using chunked reads."""
        loop = asyncio.get_running_loop()
        bucket = self._get_bucket()
        oss_stream = await loop.run_in_executor(None, lambda: bucket.get_object(key))
        try:
            while True:
                chunk = await loop.run_in_executor(None, lambda: oss_stream.read(chunk_size))
                if not chunk:
                    break
                yield chunk
        finally:
            await loop.run_in_executor(None, oss_stream.close)

    async def download_range_stream(
        self, key: str, start: int, end: int, chunk_size: int = 256 * 1024
    ) -> AsyncIterator[bytes]:
        """Stream a byte range from OSS using chunked reads."""
        loop = asyncio.get_running_loop()
        bucket = self._get_bucket()
        oss_stream = await loop.run_in_executor(
            None, lambda: bucket.get_object(key, byte_range=(start, end))
        )
        try:
            while True:
                chunk = await loop.run_in_executor(None, lambda: oss_stream.read(chunk_size))
                if not chunk:
                    break
                yield chunk
        finally:
            await loop.run_in_executor(None, oss_stream.close)

    async def delete(self, key: str) -> bool:
        loop = asyncio.get_running_loop()
        bucket = self._get_bucket()

        def _delete_object():
            bucket.delete_object(key)
            return True

        return await loop.run_in_executor(None, _delete_object)

    async def exists(self, key: str) -> bool:
        loop = asyncio.get_running_loop()
        bucket = self._get_bucket()

        def _exists():
            return bucket.object_exists(key)

        return await loop.run_in_executor(None, _exists)

    async def get_url(self, key: str) -> str:
        return self.config.get_public_url(key)

    async def get_presigned_url(self, key: str, expires: int = 3600) -> str:
        loop = asyncio.get_running_loop()
        bucket = self._get_bucket()

        def _get_url():
            return bucket.sign_url(
                "GET",
                key,
                expires,
                params={"response-content-disposition": "inline"},
            )

        return await loop.run_in_executor(None, _get_url)

    async def list_objects(self, prefix: str = "") -> list[str]:
        loop = asyncio.get_running_loop()
        bucket = self._get_bucket()

        def _list_objects():
            objects = []
            for obj in oss2.ObjectIterator(bucket, prefix=prefix):
                objects.append(obj.key)
            return objects

        return await loop.run_in_executor(None, _list_objects)

    async def close(self) -> None:
        self._bucket = None
