"""
Local filesystem storage backend.

Stores files on disk when S3 is not configured.
"""

from __future__ import annotations

import asyncio
import io
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Optional

from src.infra.logging import get_logger
from src.infra.storage.s3.base import S3StorageBackend
from src.infra.storage.s3.types import S3Config, UploadResult

logger = get_logger(__name__)


class LocalStorageBackend(S3StorageBackend):
    """Local filesystem storage backend"""

    def __init__(self, config: S3Config):
        self.config = config
        self._base_path = Path(config.storage_path).resolve()
        self._base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorageBackend initialized at: {self._base_path}")

    def _get_file_path(self, key: str) -> Path:
        """Get the local file path for a given key, preventing path traversal."""
        target = (self._base_path / key).resolve()
        if not str(target).startswith(str(self._base_path)):
            raise ValueError(f"Invalid key: path traversal detected: {key}")
        return target

    async def upload(
        self,
        file: BinaryIO,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> UploadResult:
        file_path = self._get_file_path(key)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        content = file.read()
        file_size = len(content)

        loop = asyncio.get_running_loop()

        def _write():
            with open(file_path, "wb") as f:
                f.write(content)

        await loop.run_in_executor(None, _write)

        return UploadResult(
            key=key,
            url=f"/api/upload/file/{key}",
            size=file_size,
            content_type=content_type or "application/octet-stream",
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
        file_path = self._get_file_path(key)
        loop = asyncio.get_running_loop()

        def _read():
            with open(file_path, "rb") as f:
                return f.read()

        try:
            return await loop.run_in_executor(None, _read)
        except FileNotFoundError:
            raise FileNotFoundError(f"Object {key} not found")

    async def get_size(self, key: str) -> int:
        file_path = self._get_file_path(key)
        return file_path.stat().st_size

    async def delete(self, key: str) -> bool:
        file_path = self._get_file_path(key)
        loop = asyncio.get_running_loop()

        def _delete():
            if file_path.exists():
                file_path.unlink()
                parent = file_path.parent
                while parent != self._base_path and parent.exists():
                    try:
                        parent.rmdir()
                        parent = parent.parent
                    except OSError:
                        break
                return True
            return False

        return await loop.run_in_executor(None, _delete)

    async def exists(self, key: str) -> bool:
        return self._get_file_path(key).exists()

    async def get_url(self, key: str) -> str:
        return f"/api/upload/file/{key}"

    async def get_presigned_url(self, key: str, expires: int = 3600) -> str:
        _ = expires
        return f"/api/upload/file/{key}"

    async def list_objects(self, prefix: str = "") -> list[str]:
        prefix_path = self._base_path / prefix
        if not prefix_path.exists():
            return []

        loop = asyncio.get_running_loop()

        def _list():
            objects = []
            for root, _dirs, files in os.walk(prefix_path):
                for fname in files:
                    full_path = Path(root) / fname
                    rel = full_path.relative_to(self._base_path)
                    objects.append(str(rel))
            return objects

        return await loop.run_in_executor(None, _list)

    async def close(self) -> None:
        pass
