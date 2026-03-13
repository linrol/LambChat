"""
DeepAgent Backend 工厂模块

为 DeepAgent 创建不同模式的 Backend 工厂函数。

Skills 路径现在使用 SkillsStoreBackend，支持 LLM 直接读写 skills 到 MongoDB。
OpenViking 路径使用 OpenVikingBackend，支持 LLM 读写 OpenViking 上下文数据库。
"""

import logging
from typing import Any, Callable, Optional

from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

from src.kernel.config import settings

logger = logging.getLogger(__name__)


def _build_openviking_routes(user_id: str, runtime: Any) -> dict:
    """当 ENABLE_OPENVIKING 开启时，构建 OpenViking 路由。"""
    if not settings.ENABLE_OPENVIKING:
        return {}

    try:
        from src.infra.backend.openviking_backend import create_openviking_backend

        memories_backend = create_openviking_backend(
            user_id=user_id, route_prefix="/memories/", runtime=runtime
        )
        resources_backend = create_openviking_backend(
            user_id=user_id, route_prefix="/resources/", runtime=runtime
        )
        logger.info("[OpenViking] Backend routes registered for user: %s", user_id)
        return {
            "/memories/": memories_backend,
            "/resources/": resources_backend,
        }
    except Exception as e:
        logger.warning("[OpenViking] Failed to create backend routes: %s", e)
        return {}


def create_memory_backend_factory(
    assistant_id: str,
    user_id: Optional[str] = None,
) -> Callable[[Any], CompositeBackend]:
    """
    创建基于内存的 Backend 工厂函数（非沙箱模式，不使用长期存储）

    Args:
        assistant_id: 助手 ID，用于命名空间隔离
        user_id: 用户 ID，用于 skills 读写

    Returns:
        Backend 工厂函数
    """

    def backend_factory(rt: Any) -> CompositeBackend:
        # Skills 使用 SkillsStoreBackend（读写 MongoDB）
        from src.infra.backend.skills_store import create_skills_backend

        skills_backend = create_skills_backend(user_id=user_id or "default", runtime=rt)

        routes = {
            "/skills/": skills_backend,
        }
        # OpenViking 路由（memories + resources）
        routes.update(_build_openviking_routes(user_id or "default", rt))

        return CompositeBackend(
            default=StateBackend(rt),  # 默认使用内存状态后端
            routes=routes,
        )

    return backend_factory


def create_postgres_backend_factory(
    assistant_id: str,
    user_id: Optional[str] = None,
) -> Callable[[Any], CompositeBackend]:
    """
    创建基于 PostgreSQL 的 Backend 工厂函数（非沙箱模式）

    Args:
        assistant_id: 助手 ID，用于命名空间隔离
        user_id: 用户 ID，用于 skills 读写

    Returns:
        Backend 工厂函数
    """

    def backend_factory(rt: Any) -> CompositeBackend:
        from deepagents.backends.store import BackendContext

        from src.infra.backend.skills_store import create_skills_backend

        def memory_namespace_factory(ctx: BackendContext) -> tuple[str, ...]:
            """Memory 使用 PostgresStore 持久化，按 assistant_id 隔离"""
            return (assistant_id, "memories")

        def default_namespace_factory(ctx: BackendContext) -> tuple[str, ...]:
            """默认文件系统按 assistant_id 隔离"""
            return (assistant_id, "filesystem")

        # Skills 使用 SkillsStoreBackend（读写 MongoDB）
        skills_backend = create_skills_backend(user_id=user_id or "default", runtime=rt)

        routes = {
            "/skills/": skills_backend,
        }

        # OpenViking 路由优先；否则用 PostgreSQL StoreBackend
        ov_routes = _build_openviking_routes(user_id or "default", rt)
        if ov_routes:
            routes.update(ov_routes)
        else:
            routes["/memories/"] = StoreBackend(rt, namespace=memory_namespace_factory)

        return CompositeBackend(
            default=StoreBackend(rt, namespace=default_namespace_factory),
            routes=routes,
        )

    return backend_factory


def create_sandbox_backend_factory(
    sandbox_backend: Any,
    assistant_id: str,
    user_id: Optional[str] = None,
) -> Callable[[Any], CompositeBackend]:
    """
    创建基于沙箱的 Backend 工厂函数

    Args:
        sandbox_backend: 沙箱后端实例（从 SessionSandboxManager 获取）
        assistant_id: 助手 ID，用于命名空间隔离
        user_id: 用户 ID，用于 skills 读写

    Returns:
        Backend 工厂函数
    """

    def backend_factory(rt: Any) -> CompositeBackend:
        from deepagents.backends.store import BackendContext

        from src.infra.backend.skills_store import create_skills_backend

        def memory_namespace_factory(ctx: BackendContext) -> tuple[str, ...]:
            """Memory 使用沙箱持久化，按 assistant_id 隔离"""
            return (assistant_id, "memories")

        # Skills 使用 SkillsStoreBackend（读写 MongoDB）
        skills_backend = create_skills_backend(user_id=user_id or "default", runtime=rt)

        routes = {
            "/skills/": skills_backend,
        }

        # OpenViking 路由优先；否则用 PostgreSQL StoreBackend
        ov_routes = _build_openviking_routes(user_id or "default", rt)
        if ov_routes:
            routes.update(ov_routes)
        else:
            routes["/memories/"] = StoreBackend(rt, namespace=memory_namespace_factory)

        return CompositeBackend(
            default=sandbox_backend,  # 沙箱模式使用沙箱 backend 作为默认
            routes=routes,
        )

    return backend_factory
