import os
from types import SimpleNamespace

os.environ["DEBUG"] = "false"

import pytest
from langchain.agents.middleware.types import ModelRequest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool

from src.infra.agent.middleware import ToolSearchMiddleware
from src.infra.tool.tool_search import search_tools_with_keywords
from src.infra.tool.tool_search_tool import ToolSearchTool


def _tool(name: str, description: str):
    return SimpleNamespace(name=name, description=description, server="")


class _StubManager:
    def __init__(self, *, discovered=None, undiscovered=None):
        self._discovered = list(discovered or [])
        self._undiscovered = list(undiscovered or [])

    def get_discovered_tools(self):
        return list(self._discovered)

    def get_undiscovered_tools(self):
        return list(self._undiscovered)

    def discover_tools(self, names):
        newly_discovered = []
        remaining = []
        name_set = set(names)
        for tool in self._undiscovered:
            if tool.name in name_set:
                self._discovered.append(tool)
                newly_discovered.append(tool)
            else:
                remaining.append(tool)
        self._undiscovered = remaining
        return newly_discovered

    def get_deferred_stubs_string(self):
        return "## MCP Tools (Deferred)\n- web_search_prime: Search web information."


def test_search_tools_plus_term_matches_underscored_tool_names():
    tools = [
        _tool(
            "web_search_prime",
            "Search web information, returns results including web page title and URL.",
        ),
        _tool("search_doc", "Search documentation, issues, and commits of a GitHub repository."),
    ]

    results = search_tools_with_keywords("+web_search", tools)

    assert [result.name for result in results] == ["web_search_prime"]


def test_search_tools_select_returns_exact_tool_name():
    tools = [
        _tool("web_search_prime", "Search web information."),
        _tool("search_doc", "Search documentation."),
    ]

    results = search_tools_with_keywords("select:search_doc", tools)

    assert [result.name for result in results] == ["search_doc"]


def test_search_tools_respects_higher_max_results():
    tools = [_tool(f"web_search_{index}", f"Search the web for result {index}.") for index in range(12)]

    results = search_tools_with_keywords("web search", tools, max_results=12)

    assert len(results) == 12


@pytest.mark.asyncio
async def test_tool_search_returns_already_loaded_matches():
    loaded_tool = _tool("search_doc", "Search documentation.")
    manager = _StubManager(discovered=[loaded_tool], undiscovered=[])
    search_tool = ToolSearchTool(manager=manager, search_limit=10)

    result = await search_tool._arun("select:search_doc")

    assert "Found 1 tool(s)" in result
    assert "already available" in result
    assert "search_doc" in result


@pytest.mark.asyncio
async def test_tool_search_returns_loaded_and_newly_loaded_matches_together():
    loaded_tool = _tool("search_doc", "Search documentation.")
    deferred_tool = _tool("web_search_prime", "Search web information.")
    manager = _StubManager(discovered=[loaded_tool], undiscovered=[deferred_tool])
    search_tool = ToolSearchTool(manager=manager, search_limit=10)

    result = await search_tool._arun("search")

    assert "Found 2 tool(s)" in result
    assert "1 newly loaded, 1 already available" in result
    assert "search_doc" in result
    assert "web_search_prime" in result


@pytest.mark.asyncio
async def test_tool_search_prioritizes_newly_loaded_matches_when_limit_is_small():
    loaded_tool = _tool("search_doc", "Search documentation.")
    deferred_tool = _tool("web_search_prime", "Search web information.")
    manager = _StubManager(discovered=[loaded_tool], undiscovered=[deferred_tool])
    search_tool = ToolSearchTool(manager=manager, search_limit=1)

    result = await search_tool._arun("search")

    assert "Found 1 tool(s) (1 tools loaded)" in result
    assert "web_search_prime" in result
    assert "search_doc" not in result


@tool
def search_doc(query: str) -> str:
    """Search documentation."""
    return query


def test_fast_agent_context_supports_deferred_tool_loading():
    source = open("src/agents/fast_agent/context.py", encoding="utf-8").read()

    assert "self.deferred_manager" in source
    assert "DeferredToolManager(" in source
    assert "restore_discovered_tools" in source


@pytest.mark.asyncio
async def test_tool_search_middleware_injects_search_tool_and_discovered_tools():
    manager = _StubManager(discovered=[search_doc], undiscovered=[])
    middleware = ToolSearchMiddleware(deferred_manager=manager, search_limit=10)
    request = ModelRequest(
        model=FakeListChatModel(responses=["ok"]),
        messages=[],
        system_message=SystemMessage(content="system"),
        tools=[],
    )
    captured = {}

    async def handler(req):
        captured["request"] = req
        return req

    await middleware.awrap_model_call(request, handler)

    tool_names = [tool.name for tool in captured["request"].tools]
    assert "search_tools" in tool_names
    assert "search_doc" in tool_names


def test_fast_agent_nodes_enable_tool_search_middleware_and_persist_discoveries():
    source = open("src/agents/fast_agent/nodes.py", encoding="utf-8").read()

    assert "ToolSearchMiddleware(" in source
    assert "persist_discovered_tools" in source
    assert "ToolSearchTool(" in source
