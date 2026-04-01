from types import SimpleNamespace

import pytest

from src.infra.local_filesystem import ensure_local_filesystem_dirs


def test_ensure_local_filesystem_dirs_creates_workspace_and_uploads(tmp_path):
    workspace_dir = tmp_path / "workspace"
    uploads_dir = tmp_path / "uploads"
    settings = SimpleNamespace(LOCAL_STORAGE_PATH=str(uploads_dir))

    ensure_local_filesystem_dirs(settings, workspace_dir=workspace_dir)

    assert workspace_dir.is_dir()
    assert uploads_dir.is_dir()
    assert (workspace_dir / "subagent_logs").is_dir()
    assert (workspace_dir / "subagent_logs" / "payloads").is_dir()
    assert (uploads_dir / "revealed_files").is_dir()
    assert (uploads_dir / "revealed_projects").is_dir()


def test_ensure_local_filesystem_dirs_uses_default_upload_path_when_blank(tmp_path):
    workspace_dir = tmp_path / "workspace"
    default_uploads_dir = tmp_path / "uploads"
    settings = SimpleNamespace(LOCAL_STORAGE_PATH="")

    ensure_local_filesystem_dirs(
        settings,
        workspace_dir=workspace_dir,
        default_upload_dir=default_uploads_dir,
    )

    assert workspace_dir.is_dir()
    assert default_uploads_dir.is_dir()
    assert (default_uploads_dir / "revealed_files").is_dir()
    assert (default_uploads_dir / "revealed_projects").is_dir()


@pytest.mark.asyncio
async def test_lifespan_creates_local_dirs_after_settings_initialize(monkeypatch):
    import src.api.main as main_module

    call_order: list[str] = []
    app = object()

    async def fake_initialize_settings():
        call_order.append("initialize")
        main_module.settings.LOCAL_STORAGE_PATH = "/tmp/db-uploads"

    def fake_ensure_local_filesystem_dirs(settings_obj):
        call_order.append(f"ensure:{settings_obj.LOCAL_STORAGE_PATH}")
        raise RuntimeError("stop after directory setup")

    monkeypatch.setattr(main_module, "initialize_settings", fake_initialize_settings)
    monkeypatch.setattr(
        main_module, "ensure_local_filesystem_dirs", fake_ensure_local_filesystem_dirs
    )

    with pytest.raises(RuntimeError, match="stop after directory setup"):
        async with main_module.lifespan(app):
            pass

    assert call_order == ["initialize", "ensure:/tmp/db-uploads"]
