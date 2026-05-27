"""Unit tests for sub-agentlet multiagency functionality.

Tests cover:
- SubAgentletConfig validation
- _build_sub_agentlet_tool() stats capture and error handling
- BaseAgentlet._build_sub_agentlet_tools() model resolution
- BaseAgentlet.terminate() sub-MCP manager cleanup
- OTel trace attributes on sub-agents
"""

from typing import Any
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from agentlet_core.agents.base import BaseAgentlet, _build_sub_agentlet_tool
from agentlet_core.config.models import (
    AgentletConfig,
    AgentletMetadata,
    ModelConfig,
    SubAgentletConfig,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(**overrides: Any) -> AgentletConfig:
    """Build a minimal valid AgentletConfig."""
    base: dict[str, Any] = dict(
        agentlet=AgentletMetadata(name="orchestrator"),
        system_prompt="You are an orchestrator.",
        model=ModelConfig(provider="bedrock", model_id="claude-sonnet-4-5"),
    )
    base.update(overrides)
    return AgentletConfig(**base)


def _make_sub_cfg(**overrides: Any) -> SubAgentletConfig:
    """Build a minimal valid SubAgentletConfig."""
    base: dict[str, Any] = dict(
        name="research_agent",
        description="Searches and summarises factual information.",
        system_prompt="You are a research specialist.",
    )
    base.update(overrides)
    return SubAgentletConfig(**base)


@pytest.fixture
def mock_logger():
    """Minimal logger mock matching BaseAgentlet usage."""
    logger = Mock()
    logger.info = Mock()
    logger.success = Mock()
    logger.error = Mock()
    logger.metrics = Mock()
    logger.logger = Mock()  # underlying Python logger used by RetryHandler
    return logger


# ---------------------------------------------------------------------------
# SubAgentletConfig validation
# ---------------------------------------------------------------------------


def test_sub_agentlet_config_requires_name():
    """name is mandatory."""
    with pytest.raises(ValidationError):
        SubAgentletConfig(
            description="desc",
            system_prompt="prompt",
        )


def test_sub_agentlet_config_requires_description():
    """description is mandatory."""
    with pytest.raises(ValidationError):
        SubAgentletConfig(
            name="agent",
            system_prompt="prompt",
        )


def test_sub_agentlet_config_requires_system_prompt():
    """system_prompt is mandatory."""
    with pytest.raises(ValidationError):
        SubAgentletConfig(
            name="agent",
            description="desc",
        )


def test_sub_agentlet_config_model_defaults_to_none():
    """model is optional and defaults to None (inherit orchestrator)."""
    cfg = _make_sub_cfg()
    assert cfg.model is None


def test_sub_agentlet_config_model_override():
    """model can be explicitly set to override the orchestrator's model."""
    cfg = _make_sub_cfg(
        model=ModelConfig(provider="bedrock", model_id="claude-haiku-4-5")
    )
    assert cfg.model is not None
    assert cfg.model.model_id == "claude-haiku-4-5"


def test_sub_agentlet_config_tools_default_empty():
    """tools and mcp_tools default to empty lists."""
    cfg = _make_sub_cfg()
    assert cfg.tools == []
    assert cfg.mcp_tools == []


def test_sub_agentlet_output_defaults_silent():
    """output defaults to all-False so sub-agentlets are silent by default."""
    cfg = _make_sub_cfg()
    assert cfg.output.show_messages is False
    assert cfg.output.show_reasoning is False
    assert cfg.output.show_tool_calls is False


def test_sub_agentlet_output_can_be_enabled():
    """output options can be individually enabled."""
    from agentlet_core.config.models import OutputConfig

    cfg = _make_sub_cfg(
        output=OutputConfig(
            show_messages=True, show_reasoning=False, show_tool_calls=True
        )
    )
    assert cfg.output.show_messages is True
    assert cfg.output.show_reasoning is False
    assert cfg.output.show_tool_calls is True


# ---------------------------------------------------------------------------
# AgentletConfig.sub_agentlets field
# ---------------------------------------------------------------------------


def test_agentlet_config_sub_agentlets_defaults_empty():
    """sub_agentlets defaults to [] — existing configs are unaffected."""
    config = _make_config()
    assert config.sub_agentlets == []


def test_agentlet_config_sub_agentlets_parses_correctly():
    """sub_agentlets list is parsed and validated correctly."""
    config = _make_config(
        sub_agentlets=[
            _make_sub_cfg(name="agent_a"),
            _make_sub_cfg(name="agent_b"),
        ]
    )
    assert len(config.sub_agentlets) == 2
    assert config.sub_agentlets[0].name == "agent_a"
    assert config.sub_agentlets[1].name == "agent_b"


# ---------------------------------------------------------------------------
# _build_sub_agentlet_tool() — stats capture
# ---------------------------------------------------------------------------


def _fake_metrics(input_tokens: int, output_tokens: int):
    """Build a fake EventLoopMetrics-like object."""
    m = Mock()
    m.accumulated_usage = {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": input_tokens + output_tokens,
    }
    return m


def test_build_sub_agentlet_tool_captures_stats():
    """Successful invocation populates stats_store with timing and token counts."""
    fake_result = Mock()
    fake_result.metrics = _fake_metrics(100, 50)
    fake_result.__str__ = lambda self: "result text"

    sub_agent = Mock(return_value=fake_result)
    sub_cfg = _make_sub_cfg(name="my_agent", description="Does something useful.")
    stats_store: dict = {}
    logger = Mock()

    with patch(
        "agentlet_core.agents.base.litellm.cost_per_token", return_value=(0.001, 0.002)
    ):
        wrapped = _build_sub_agentlet_tool(
            sub_agent, sub_cfg, "bedrock/claude-sonnet-4-5", stats_store, logger
        )
        response = wrapped(query="What is Python?")

    assert response == "result text"
    assert "my_agent" in stats_store
    stats = stats_store["my_agent"]
    assert stats["input_tokens"] == 100
    assert stats["output_tokens"] == 50
    assert stats["total_cost"] == pytest.approx(0.003)
    assert stats["execution_time"] > 0
    assert "error" not in stats


def test_build_sub_agentlet_tool_records_error_on_failure():
    """When the sub-agent raises, stats_store records the error and the tool returns an error string."""
    sub_agent = Mock(side_effect=RuntimeError("LLM timeout"))
    sub_cfg = _make_sub_cfg(name="failing_agent")
    stats_store: dict = {}
    logger = Mock()

    wrapped = _build_sub_agentlet_tool(
        sub_agent, sub_cfg, "bedrock/claude-sonnet-4-5", stats_store, logger
    )
    response = wrapped(query="Do something")

    assert "error" in response.lower()
    assert "failing_agent" in response
    assert "LLM timeout" in response
    assert stats_store["failing_agent"]["error"] == "LLM timeout"
    assert stats_store["failing_agent"]["execution_time"] > 0
    logger.error.assert_called_once()


def test_build_sub_agentlet_tool_logs_error():
    """Errors during sub-agent invocation are logged via the logger."""
    sub_agent = Mock(side_effect=ValueError("bad input"))
    sub_cfg = _make_sub_cfg(name="err_agent")
    stats_store: dict = {}
    logger = Mock()

    wrapped = _build_sub_agentlet_tool(
        sub_agent, sub_cfg, "bedrock/model", stats_store, logger
    )
    wrapped(query="test")

    logger.error.assert_called_once()
    call_args = logger.error.call_args[0][0]
    assert "err_agent" in call_args


# ---------------------------------------------------------------------------
# BaseAgentlet._build_sub_agentlet_tools() — model resolution
# ---------------------------------------------------------------------------


def _make_agentlet_with_sub(sub_cfgs, mock_logger):
    """Construct a BaseAgentlet with sub_agentlets, bypassing full spawn()."""
    config = _make_config(sub_agentlets=sub_cfgs)
    with patch.object(BaseAgentlet, "__init__", lambda self, cfg, **kw: None):
        agentlet = BaseAgentlet.__new__(BaseAgentlet)
    agentlet.config = config
    agentlet.execution_id = "test-exec-id"
    agentlet.logger = mock_logger
    agentlet._sub_mcp_managers = []
    agentlet._sub_agentlet_stats = {}
    agentlet.context = Mock()
    agentlet.context.working_dir = "/tmp/test"
    return agentlet


def test_model_inheritance_when_sub_cfg_model_is_none(mock_logger):
    """When sub_cfg.model is None, the orchestrator's LiteLLMModel is reused."""
    sub_cfg = _make_sub_cfg()
    agentlet = _make_agentlet_with_sub([sub_cfg], mock_logger)

    orchestrator_model = Mock()

    with (
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
        patch("agentlet_core.agents.base._build_sub_agentlet_tool") as mock_build,
    ):
        mock_dtm.return_value.get_tools.return_value = []
        mock_agent_cls.return_value = Mock()
        mock_build.return_value = Mock()

        agentlet._build_sub_agentlet_tools(orchestrator_model)

        # Agent should have been called with the same orchestrator model instance
        _, kwargs = mock_agent_cls.call_args
        assert kwargs["model"] is orchestrator_model


def test_model_override_builds_new_litellm_model(mock_logger):
    """When sub_cfg.model is set, a new LiteLLMModel is built with the correct model_id."""
    sub_cfg = _make_sub_cfg(
        model=ModelConfig(provider="bedrock", model_id="claude-haiku-4-5")
    )
    agentlet = _make_agentlet_with_sub([sub_cfg], mock_logger)

    orchestrator_model = Mock()

    with (
        patch("agentlet_core.agents.base.LiteLLMModel") as mock_litellm,
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
        patch("agentlet_core.agents.base._build_sub_agentlet_tool") as mock_build,
    ):
        new_model = Mock()
        mock_litellm.return_value = new_model
        mock_dtm.return_value.get_tools.return_value = []
        mock_agent_cls.return_value = Mock()
        mock_build.return_value = Mock()

        agentlet._build_sub_agentlet_tools(orchestrator_model)

        mock_litellm.assert_called_once()
        call_kwargs = mock_litellm.call_args[1]
        assert call_kwargs["model_id"] == "bedrock/claude-haiku-4-5"


# ---------------------------------------------------------------------------
# OTel trace attributes
# ---------------------------------------------------------------------------


def test_sub_agentlet_trace_attributes_include_name_and_parent(mock_logger):
    """Sub-agent receives sub_agentlet.name and sub_agentlet.parent_execution_id in trace attrs."""
    sub_cfg = _make_sub_cfg(name="specialist")
    agentlet = _make_agentlet_with_sub([sub_cfg], mock_logger)
    agentlet.execution_id = "parent-exec-123"

    with (
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
        patch("agentlet_core.agents.base._build_sub_agentlet_tool") as mock_build,
        patch.object(
            agentlet, "_build_trace_attributes", return_value={"base": "attr"}
        ),
    ):
        mock_dtm.return_value.get_tools.return_value = []
        mock_agent_cls.return_value = Mock()
        mock_build.return_value = Mock()

        agentlet._build_sub_agentlet_tools(Mock())

        _, kwargs = mock_agent_cls.call_args
        attrs = kwargs["trace_attributes"]
        assert attrs["sub_agentlet.name"] == "specialist"
        assert attrs["sub_agentlet.parent_execution_id"] == "parent-exec-123"
        assert attrs["agentlet.name"] == "specialist"


# ---------------------------------------------------------------------------
# Callback handler selection based on output config
# ---------------------------------------------------------------------------


def test_silent_output_uses_null_callback(mock_logger):
    """When output is all-False (default), null_callback_handler is used."""
    sub_cfg = _make_sub_cfg()  # defaults: show_messages=False etc.
    agentlet = _make_agentlet_with_sub([sub_cfg], mock_logger)

    with (
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
        patch("agentlet_core.agents.base._build_sub_agentlet_tool") as mock_build,
        patch("agentlet_core.agents.base.null_callback_handler") as mock_null,
    ):
        mock_dtm.return_value.get_tools.return_value = []
        mock_agent_cls.return_value = Mock()
        mock_build.return_value = Mock()

        agentlet._build_sub_agentlet_tools(Mock())

        _, kwargs = mock_agent_cls.call_args
        assert kwargs["callback_handler"] is mock_null


def test_show_messages_uses_default_callback(mock_logger):
    """When show_messages=True, callback_handler=None (Strands default) is used."""
    from agentlet_core.config.models import OutputConfig

    sub_cfg = _make_sub_cfg(output=OutputConfig(show_messages=True))
    agentlet = _make_agentlet_with_sub([sub_cfg], mock_logger)

    with (
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
        patch("agentlet_core.agents.base._build_sub_agentlet_tool") as mock_build,
    ):
        mock_dtm.return_value.get_tools.return_value = []
        mock_agent_cls.return_value = Mock()
        mock_build.return_value = Mock()

        agentlet._build_sub_agentlet_tools(Mock())

        _, kwargs = mock_agent_cls.call_args
        assert kwargs["callback_handler"] is None


def test_show_tool_calls_uses_default_callback(mock_logger):
    """When show_tool_calls=True, callback_handler=None (Strands default) is used."""
    from agentlet_core.config.models import OutputConfig

    sub_cfg = _make_sub_cfg(output=OutputConfig(show_tool_calls=True))
    agentlet = _make_agentlet_with_sub([sub_cfg], mock_logger)

    with (
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
        patch("agentlet_core.agents.base._build_sub_agentlet_tool") as mock_build,
    ):
        mock_dtm.return_value.get_tools.return_value = []
        mock_agent_cls.return_value = Mock()
        mock_build.return_value = Mock()

        agentlet._build_sub_agentlet_tools(Mock())

        _, kwargs = mock_agent_cls.call_args
        assert kwargs["callback_handler"] is None


# ---------------------------------------------------------------------------
# BaseAgentlet.terminate() — sub-MCP cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_terminate_cleans_up_sub_mcp_managers(mock_logger):
    """terminate() calls cleanup_sync() on all sub-agentlet MCP managers."""
    config = _make_config()

    with patch.object(BaseAgentlet, "__init__", lambda self, cfg, **kw: None):
        agentlet = BaseAgentlet.__new__(BaseAgentlet)

    agentlet.config = config
    agentlet.logger = mock_logger
    agentlet._mcp_manager = None
    agentlet.context = None

    sub_mgr_1 = Mock()
    sub_mgr_2 = Mock()
    agentlet._sub_mcp_managers = [sub_mgr_1, sub_mgr_2]

    with patch.object(agentlet, "_cleanup_aiohttp_sessions", return_value=None):
        await agentlet.terminate()

    sub_mgr_1.cleanup_sync.assert_called_once()
    sub_mgr_2.cleanup_sync.assert_called_once()
