import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

os.environ["DEBUG"] = "false"

from src.api.routes import session as session_routes
from src.infra.session.manager import SessionManager
from src.kernel.schemas.session import Session
from src.kernel.schemas.user import TokenPayload


def _make_user() -> TokenPayload:
    return TokenPayload(sub="user-1", username="tester", roles=[], permissions=[])


def _make_session() -> Session:
    return Session(
        id="session-1",
        name="Test Session",
        metadata={},
        user_id="user-1",
        agent_id="search",
    )


@pytest.mark.asyncio
async def test_clear_session_messages_releases_attachment_references(monkeypatch):
    manager = AsyncMock(spec=SessionManager)
    manager.get_session.return_value = _make_session()
    manager.clear_session_messages.return_value = 2

    monkeypatch.setattr(session_routes, "SessionManager", lambda: manager)

    result = await session_routes.clear_session_messages("session-1", _make_user())

    assert result == {"status": "cleared", "released_attachments": 2}
    manager.clear_session_messages.assert_awaited_once_with("session-1")


@pytest.mark.asyncio
async def test_delete_session_releases_attachment_references_before_deleting(monkeypatch):
    manager = AsyncMock(spec=SessionManager)
    manager.get_session.return_value = _make_session()
    manager.delete_session.return_value = True

    monkeypatch.setattr(session_routes, "SessionManager", lambda: manager)

    result = await session_routes.delete_session("session-1", _make_user())

    assert result == {"status": "deleted"}
    manager.delete_session.assert_awaited_once_with("session-1")


@pytest.mark.asyncio
async def test_session_manager_clear_session_messages_releases_unique_attachment_keys(monkeypatch):
    trace_storage = AsyncMock()
    trace_storage.get_session_events.return_value = [
        {
            "event_type": "user:message",
            "data": {
                "attachments": [
                    {"key": "document/user-1/a.txt"},
                    {"key": "document/user-1/a.txt"},
                    {"key": "document/user-1/b.txt"},
                ]
            },
        },
        {
            "event_type": "assistant:message",
            "data": {"attachments": [{"key": "document/user-1/c.txt"}]},
        },
    ]
    trace_storage.delete_session_traces = AsyncMock(return_value=1)

    storage = AsyncMock()
    storage.release_references.return_value = 2
    storage.find_by_key.side_effect = [
        {"key": "document/user-1/a.txt", "reference_count": 0},
        {"key": "document/user-1/b.txt", "reference_count": 1},
    ]

    manager = SessionManager()
    manager._trace_storage = trace_storage

    monkeypatch.setattr("src.infra.session.manager.FileRecordStorage", lambda: storage)
    delete_storage = AsyncMock()
    monkeypatch.setattr("src.infra.session.manager.get_storage_service", lambda: delete_storage)

    manager._file_record_storage = storage

    released = await manager.clear_session_messages("session-1")

    assert released == 2
    storage.release_references.assert_awaited_once_with(
        ["document/user-1/a.txt", "document/user-1/b.txt"]
    )
    delete_storage.delete_file.assert_awaited_once_with("document/user-1/a.txt")
    storage.delete_by_key.assert_awaited_once_with("document/user-1/a.txt")
    trace_storage.delete_session_traces.assert_awaited_once_with("session-1")


@pytest.mark.asyncio
async def test_emit_user_message_tracks_attachment_references(monkeypatch):
    from src.infra.writer.present import Presenter, PresenterConfig

    presenter = Presenter(
        PresenterConfig(
            session_id="session-1",
            agent_id="search",
            user_id="user-1",
            run_id="run-1",
            enable_storage=False,
        )
    )

    save_event = AsyncMock()
    file_record_storage = SimpleNamespace(add_references=AsyncMock(return_value=2))

    monkeypatch.setattr(presenter, "save_event", save_event)
    monkeypatch.setattr("src.infra.writer.present.FileRecordStorage", lambda: file_record_storage)

    await presenter.emit_user_message(
        "hello",
        attachments=[
            {"key": "document/user-1/a.txt"},
            {"key": "document/user-1/a.txt"},
            {"key": "document/user-1/b.txt"},
        ],
    )

    file_record_storage.add_references.assert_awaited_once_with(
        ["document/user-1/a.txt", "document/user-1/b.txt"]
    )
    save_event.assert_awaited_once()
