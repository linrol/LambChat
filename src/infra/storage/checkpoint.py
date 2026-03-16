"""
Checkpoint 存储实现

提供 LangGraph checkpointer 的工厂函数，支持 MongoDB 持久化。

注意：langgraph 的 MongoDBSaver 使用同步 pymongo 客户端，
在 asyncio 事件循环中会阻塞。我们使用 AsyncMongoDBSaver（如果可用），
否则回退到同步版本（仅在 startup 时创建，运行时 I/O 较短可接受）。
"""

import asyncio
import logging
from functools import partial
from typing import Optional

from src.kernel.config import settings

logger = logging.getLogger(__name__)

# MongoDB Checkpointer 单例
_mongo_checkpointer: Optional[object] = None


def _build_connection_string() -> str:
    """构建 MongoDB 连接字符串"""
    from urllib.parse import quote_plus

    base_url = settings.MONGODB_URL
    username = settings.MONGODB_USERNAME
    password = settings.MONGODB_PASSWORD
    auth_source = settings.MONGODB_AUTH_SOURCE

    if username and password:
        if base_url.startswith("mongodb://"):
            rest = base_url[len("mongodb://") :]
            encoded_user = quote_plus(username)
            encoded_pass = quote_plus(password)
            return f"mongodb://{encoded_user}:{encoded_pass}@{rest}?authSource={auth_source}"
        elif base_url.startswith("mongodb+srv://"):
            rest = base_url[len("mongodb+srv://") :]
            encoded_user = quote_plus(username)
            encoded_pass = quote_plus(password)
            return f"mongodb+srv://{encoded_user}:{encoded_pass}@{rest}?authSource={auth_source}"

    return base_url


def get_mongo_checkpointer(collection_name: str = "checkpoints"):
    """
    获取 MongoDB checkpointer 单例

    Args:
        collection_name: MongoDB collection 名称，默认为 "checkpoints"

    Returns:
        MongoDBSaver 实例，如果创建失败则返回 None
    """
    global _mongo_checkpointer
    if _mongo_checkpointer is not None:
        return _mongo_checkpointer

    try:
        # 优先尝试异步版本
        try:
            from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver

            connection_string = _build_connection_string()
            _mongo_checkpointer = AsyncMongoDBSaver.from_conn_string(
                connection_string,
                db_name=settings.MONGODB_DB,
                checkpoint_collection_name=collection_name,
            )
            logger.info(
                f"Async MongoDB checkpointer created: {settings.MONGODB_DB}.{collection_name}"
            )
            return _mongo_checkpointer
        except ImportError:
            logger.debug("AsyncMongoDBSaver not available, falling back to sync MongoDBSaver")

        # 回退到同步版本（仅在 startup 时创建连接，短 I/O 可接受）
        from langgraph.checkpoint.mongodb import MongoDBSaver
        from pymongo import MongoClient

        connection_string = _build_connection_string()
        client: MongoClient = MongoClient(connection_string)

        _mongo_checkpointer = MongoDBSaver(
            client,
            db_name=settings.MONGODB_DB,
            checkpoint_collection_name=collection_name,
        )

        logger.info(f"Sync MongoDB checkpointer created: {settings.MONGODB_DB}.{collection_name}")
        return _mongo_checkpointer

    except ImportError as e:
        logger.warning(f"MongoDB checkpointer not available: {e}")
        return None
    except Exception as e:
        logger.warning(f"Failed to create MongoDB checkpointer: {e}")
        return None


async def get_async_checkpointer():
    """
    获取 checkpointer 实例（兼容异步调用）

    优先使用 MongoDB（持久化），如果不可用则返回 MemorySaver。

    Returns:
        Checkpointer 实例
    """
    checkpointer = get_mongo_checkpointer()
    if checkpointer is not None:
        return checkpointer

    from langgraph.checkpoint.memory import MemorySaver

    logger.warning("Using MemorySaver (data will be lost on restart)")
    return MemorySaver()


def get_checkpointer():
    """
    获取 checkpointer 实例（同步版本，向后兼容）
    """
    return get_mongo_checkpointer() or __import__("langgraph.checkpoint.memory").MemorySaver()
