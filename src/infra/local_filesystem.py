"""Helpers for local filesystem preparation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.infra.logging import get_logger

logger = get_logger(__name__)


def ensure_local_filesystem_dirs(
    settings: Any,
    *,
    workspace_dir: str | Path = "./workspace",
    default_upload_dir: str | Path = "./uploads",
) -> None:
    """Create local directories that the app expects to exist at startup."""
    workspace_path = Path(workspace_dir)
    upload_path = Path(getattr(settings, "LOCAL_STORAGE_PATH", "") or default_upload_dir)

    required_paths = (
        workspace_path,
        workspace_path / "subagent_logs",
        workspace_path / "subagent_logs" / "payloads",
        upload_path,
        upload_path / "revealed_files",
        upload_path / "revealed_projects",
    )

    for path in required_paths:
        path.mkdir(parents=True, exist_ok=True)
        logger.info("Ensured local directory exists: %s", path.resolve())
