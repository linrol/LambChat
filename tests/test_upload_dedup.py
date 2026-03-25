import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pymongo.errors import DuplicateKeyError
from starlette.requests import Request

os.environ["DEBUG"] = "false"

from src.api.routes import upload as upload_routes
from src.kernel.schemas.user import TokenPayload


def _make_request(*, content_length: int | None = None) -> Request:
    headers = []
    if content_length is not None:
        headers.append((b"content-length", str(content_length).encode()))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/upload/file",
        "headers": headers,
        "scheme": "http",
        "server": ("testserver", 3001),
        "client": ("127.0.0.1", 12345),
        "root_path": "",
        "query_string": b"",
    }
    return Request(scope)


def _make_user() -> TokenPayload:
    return TokenPayload(
        sub="user-1",
        username="tester",
        roles=[],
        permissions=["file:upload"],
    )


class FakeUploadFile:
    def __init__(self, filename: str, content: bytes, content_type: str):
        self.filename = filename
        self._content = content
        self.content_type = content_type

    async def read(self) -> bytes:
        return self._content


@pytest.mark.asyncio
async def test_check_file_exists_cleans_stale_record(monkeypatch):
    file_record_storage = SimpleNamespace(
        find_by_hash=AsyncMock(
            return_value={
                "hash": "a" * 64,
                "key": "document/user-1/stale.txt",
                "name": "stale.txt",
                "category": "document",
                "mime_type": "text/plain",
                "size": 12,
            }
        ),
        delete_by_hash=AsyncMock(return_value=True),
    )
    storage = SimpleNamespace(file_exists=AsyncMock(return_value=False))

    monkeypatch.setattr(upload_routes, "_file_record_storage", file_record_storage)
    monkeypatch.setattr(upload_routes, "get_or_init_storage", AsyncMock(return_value=storage))

    result = await upload_routes.check_file_exists(
        upload_routes.FileCheckRequest(
            hash="a" * 64,
            size=12,
            name="stale.txt",
            mime_type="text/plain",
        ),
        _make_user(),
    )

    assert result == {"exists": False}
    file_record_storage.delete_by_hash.assert_awaited_once_with("a" * 64)


@pytest.mark.asyncio
async def test_upload_file_reuploads_when_hash_points_to_missing_object(monkeypatch):
    file_record_storage = SimpleNamespace(
        find_by_hash=AsyncMock(
            side_effect=[
                {
                    "hash": "unused",
                    "key": "document/user-1/missing.txt",
                    "name": "missing.txt",
                    "category": "document",
                    "mime_type": "text/plain",
                    "size": 11,
                }
            ]
        ),
        delete_by_hash=AsyncMock(return_value=True),
        create=AsyncMock(return_value={"id": "record-1"}),
    )
    storage = SimpleNamespace(
        file_exists=AsyncMock(return_value=False),
        upload_to_key=AsyncMock(
            return_value=SimpleNamespace(
                key="document/user-1/new.txt",
                url="/api/upload/file/document/user-1/new.txt",
            )
        ),
    )

    monkeypatch.setattr(upload_routes, "_file_record_storage", file_record_storage)
    monkeypatch.setattr(upload_routes, "get_or_init_storage", AsyncMock(return_value=storage))
    monkeypatch.setattr(
        upload_routes,
        "resolve_upload_limits",
        AsyncMock(
            return_value={
                "image": 10,
                "video": 10,
                "audio": 10,
                "document": 10,
                "maxFiles": 10,
            }
        ),
    )

    upload = FakeUploadFile("hello.txt", b"hello world", "text/plain")

    result = await upload_routes.upload_file(
        _make_request(content_length=11),
        upload,
        _make_user(),
    )

    assert result["key"].startswith("document/user-1/")
    assert result["name"] == "hello.txt"
    file_record_storage.delete_by_hash.assert_awaited_once()
    storage.upload_to_key.assert_awaited_once()
    file_record_storage.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_file_recovers_from_duplicate_key_race(monkeypatch):
    live_record = {
        "hash": "b" * 64,
        "key": "document/user-2/shared.txt",
        "name": "shared.txt",
        "category": "document",
        "mime_type": "text/plain",
        "size": 11,
    }
    file_record_storage = SimpleNamespace(
        find_by_hash=AsyncMock(side_effect=[None, live_record]),
        delete_by_hash=AsyncMock(return_value=False),
        create=AsyncMock(side_effect=DuplicateKeyError("duplicate key error")),
    )
    storage = SimpleNamespace(
        file_exists=AsyncMock(side_effect=[True]),
        upload_to_key=AsyncMock(
            return_value=SimpleNamespace(
                key="document/user-1/temp.txt",
                url="/api/upload/file/document/user-1/temp.txt",
            )
        ),
        delete_file=AsyncMock(return_value=True),
    )

    monkeypatch.setattr(upload_routes, "_file_record_storage", file_record_storage)
    monkeypatch.setattr(upload_routes, "get_or_init_storage", AsyncMock(return_value=storage))
    monkeypatch.setattr(
        upload_routes,
        "resolve_upload_limits",
        AsyncMock(
            return_value={
                "image": 10,
                "video": 10,
                "audio": 10,
                "document": 10,
                "maxFiles": 10,
            }
        ),
    )

    upload = FakeUploadFile("shared.txt", b"hello world", "text/plain")

    result = await upload_routes.upload_file(
        _make_request(content_length=11),
        upload,
        _make_user(),
    )

    assert result["exists"] is True
    assert result["key"] == live_record["key"]
    storage.delete_file.assert_awaited_once()
    deleted_key = storage.delete_file.await_args.args[0]
    assert deleted_key.startswith("document/user-1/")


@pytest.mark.asyncio
async def test_delete_file_preserves_tracked_deduplicated_file(monkeypatch):
    file_record_storage = SimpleNamespace(
        find_by_key=AsyncMock(
            return_value={
                "hash": "c" * 64,
                "key": "document/user-1/shared.txt",
                "reference_count": 2,
            }
        ),
        delete_by_key=AsyncMock(return_value=False),
    )
    storage = SimpleNamespace(delete_file=AsyncMock(return_value=True))

    monkeypatch.setattr(upload_routes, "_file_record_storage", file_record_storage)
    monkeypatch.setattr(upload_routes, "get_or_init_storage", AsyncMock(return_value=storage))

    result = await upload_routes.delete_file("document/user-1/shared.txt", _make_user())

    assert result == {
        "deleted": False,
        "key": "document/user-1/shared.txt",
        "status": "preserved",
    }
    storage.delete_file.assert_not_awaited()
    file_record_storage.delete_by_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_file_removes_unreferenced_upload(monkeypatch):
    file_record_storage = SimpleNamespace(
        find_by_key=AsyncMock(
            return_value={
                "hash": "d" * 64,
                "key": "document/user-1/temp.txt",
                "reference_count": 0,
            }
        ),
        delete_by_key=AsyncMock(return_value=True),
    )
    storage = SimpleNamespace(delete_file=AsyncMock(return_value=True))

    monkeypatch.setattr(upload_routes, "_file_record_storage", file_record_storage)
    monkeypatch.setattr(upload_routes, "get_or_init_storage", AsyncMock(return_value=storage))

    result = await upload_routes.delete_file("document/user-1/temp.txt", _make_user())

    assert result == {
        "deleted": True,
        "key": "document/user-1/temp.txt",
        "status": "deleted",
    }
    storage.delete_file.assert_awaited_once_with("document/user-1/temp.txt")
    file_record_storage.delete_by_key.assert_awaited_once_with("document/user-1/temp.txt")
