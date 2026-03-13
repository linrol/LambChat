"""
OpenViking 客户端管理

单例管理 AsyncHTTPClient 生命周期，在 FastAPI app startup/shutdown 中注册。
"""

import logging
from typing import Any, Optional

from src.kernel.config import settings

logger = logging.getLogger(__name__)

_client: Optional[Any] = None


async def get_openviking_client():
    """
    获取 OpenViking AsyncHTTPClient 单例。

    首次调用时创建并初始化客户端。
    """
    global _client

    if _client is not None:
        return _client

    if not settings.ENABLE_OPENVIKING:
        return None

    try:
        from openviking import AsyncHTTPClient

        _client = AsyncHTTPClient(
            url=settings.OPENVIKING_URL,
            api_key=settings.OPENVIKING_API_KEY or None,
            agent_id=settings.OPENVIKING_AGENT_ID or None,
        )
        await _client.initialize()
        logger.info(
            "[OpenViking] Client initialized, url=%s", settings.OPENVIKING_URL
        )
        return _client
    except ImportError:
        logger.error(
            "[OpenViking] openviking package not installed. Run: pip install openviking"
        )
        return None
    except Exception as e:
        logger.error("[OpenViking] Failed to initialize client: %s", e)
        _client = None
        return None


async def close_openviking_client():
    """关闭 OpenViking 客户端连接。"""
    global _client

    if _client is not None:
        try:
            await _client.close()
            logger.info("[OpenViking] Client closed")
        except Exception as e:
            logger.warning("[OpenViking] Error closing client: %s", e)
        finally:
            _client = None
