import os

os.environ["DEBUG"] = "false"

from pathlib import Path

def test_search_agent_subagents_enable_activity_logging():
    source = Path("src/agents/search_agent/nodes.py").read_text()

    assert "SubagentActivityMiddleware" in source


def test_search_agent_subagents_enable_tool_search_middleware():
    source = Path("src/agents/search_agent/nodes.py").read_text()

    assert "subagent_middleware.append(" in source
    assert "ToolSearchMiddleware(" in source


def test_fast_agent_subagents_enable_tool_search_middleware():
    source = Path("src/agents/fast_agent/nodes.py").read_text()

    assert "subagent_middleware.append(" in source
    assert "ToolSearchMiddleware(" in source


def test_subagent_activity_logging_externalizes_large_payloads_with_unique_paths():
    source = Path("src/infra/agent/middleware.py").read_text()

    assert "self._payload_dir" in source
    assert "self._payload_counter" in source
    assert "Full payload:" in source
    assert "payloads/{self._run_id}" in source


def test_subagent_activity_logging_appends_detail_hint_after_log_path():
    source = Path("src/infra/agent/middleware.py").read_text()

    assert "[Activity log saved to: {self._log_path}]" in source
    assert "For more details, check this file." in source
