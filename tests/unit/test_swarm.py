"""Unit tests for swarm multi-agent pattern."""

from typing import Any
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from agentlet_core.agents.base import BaseAgentlet, _expand_participant_name
from agentlet_core.config.models import (
    AgentletConfig,
    AgentletMetadata,
    MCPToolConfig,
    ModelConfig,
    SubAgentletConfig,
    SwarmConfig,
    SwarmParticipantConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_participant(**overrides: Any) -> SwarmParticipantConfig:
    base: dict[str, Any] = dict(
        name="researcher",
        description="Researches topics",
        system_prompt="You are a researcher.",
    )
    base.update(overrides)
    return SwarmParticipantConfig(**base)


def _make_swarm_config(**overrides: Any) -> SwarmConfig:
    base: dict[str, Any] = dict(participants=[_make_participant()])
    base.update(overrides)
    return SwarmConfig(**base)


def _make_agentlet_config(**overrides: Any) -> AgentletConfig:
    base: dict[str, Any] = dict(
        agentlet=AgentletMetadata(name="test-agentlet"),
        system_prompt="You are a test agent.",
        model=ModelConfig(provider="bedrock", model_id="claude-sonnet-4-5"),
    )
    base.update(overrides)
    return AgentletConfig(**base)


# ---------------------------------------------------------------------------
# SwarmParticipantConfig
# ---------------------------------------------------------------------------


def test_participant_requires_name():
    with pytest.raises(ValidationError):
        SwarmParticipantConfig(description="d", system_prompt="sp")


def test_participant_requires_description():
    with pytest.raises(ValidationError):
        SwarmParticipantConfig(name="a", system_prompt="sp")


def test_participant_requires_system_prompt():
    with pytest.raises(ValidationError):
        SwarmParticipantConfig(name="a", description="d")


def test_participant_count_defaults_to_one():
    p = _make_participant()
    assert p.count == 1


def test_participant_count_minimum_one():
    with pytest.raises(ValidationError):
        _make_participant(count=0)


def test_participant_model_defaults_to_none():
    p = _make_participant()
    assert p.model is None


def test_participant_tools_default_empty():
    p = _make_participant()
    assert p.tools == []
    assert p.mcp_tools == []


def test_participant_model_override():
    p = _make_participant(
        model=ModelConfig(provider="bedrock", model_id="claude-haiku-4-5")
    )
    assert p.model is not None
    assert p.model.model_id == "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# SwarmConfig
# ---------------------------------------------------------------------------


def test_swarm_config_requires_participants():
    with pytest.raises(ValidationError):
        SwarmConfig()  # no participants


def test_swarm_config_rejects_empty_participants():
    with pytest.raises(ValidationError):
        SwarmConfig(participants=[])


def test_swarm_config_safety_defaults():
    cfg = _make_swarm_config()
    assert cfg.max_handoffs == 20
    assert cfg.max_iterations == 20
    assert cfg.execution_timeout == 900.0
    assert cfg.node_timeout == 300.0
    assert cfg.repetitive_handoff_detection_window == 0
    assert cfg.repetitive_handoff_min_unique_agents == 0


def test_swarm_config_entry_point_defaults_none():
    cfg = _make_swarm_config()
    assert cfg.entry_point is None


def test_swarm_config_entry_point_valid():
    cfg = _make_swarm_config(entry_point="researcher")
    assert cfg.entry_point == "researcher"


def test_swarm_config_entry_point_not_in_participants():
    with pytest.raises(ValidationError, match="entry_point"):
        SwarmConfig(
            participants=[_make_participant(name="researcher")],
            entry_point="nonexistent",
        )


def test_swarm_config_multiple_participants():
    cfg = SwarmConfig(
        participants=[
            _make_participant(name="researcher", count=2),
            _make_participant(name="writer", count=1),
        ]
    )
    assert len(cfg.participants) == 2
    assert cfg.participants[0].count == 2


# ---------------------------------------------------------------------------
# AgentletConfig.swarm field
# ---------------------------------------------------------------------------


def test_agentlet_config_swarm_defaults_to_none():
    cfg = _make_agentlet_config()
    assert cfg.swarm is None


def test_agentlet_config_swarm_parses_correctly():
    cfg = _make_agentlet_config(swarm=_make_swarm_config())
    assert cfg.swarm is not None
    assert len(cfg.swarm.participants) == 1


def test_agentlet_config_swarm_and_sub_agentlets_conflict():
    """Combining swarm with sub_agentlets must raise a ValidationError."""
    with pytest.raises(
        ValidationError, match="Cannot combine 'swarm' and 'sub_agentlets'"
    ):
        _make_agentlet_config(
            swarm=_make_swarm_config(),
            sub_agentlets=[
                SubAgentletConfig(
                    name="helper",
                    description="Helps out",
                    system_prompt="You help.",
                )
            ],
        )


def test_agentlet_config_sub_agentlets_alone_still_valid():
    """sub_agentlets without swarm must remain valid (backward compat)."""
    cfg = _make_agentlet_config(
        sub_agentlets=[
            SubAgentletConfig(
                name="helper",
                description="Helps out",
                system_prompt="You help.",
            )
        ]
    )
    assert cfg.swarm is None
    assert len(cfg.sub_agentlets) == 1


def test_agentlet_config_swarm_alone_valid():
    """swarm without sub_agentlets must be valid."""
    cfg = _make_agentlet_config(swarm=_make_swarm_config())
    assert cfg.swarm is not None
    assert cfg.sub_agentlets == []


# ---------------------------------------------------------------------------
# _expand_participant_name
# ---------------------------------------------------------------------------


def test_expand_name_count_one_no_suffix():
    assert _expand_participant_name("researcher", 1, 1) == "researcher"


def test_expand_name_count_many_adds_suffix():
    assert _expand_participant_name("researcher", 3, 1) == "researcher_1"
    assert _expand_participant_name("researcher", 3, 2) == "researcher_2"
    assert _expand_participant_name("researcher", 3, 3) == "researcher_3"


def test_expand_name_count_two():
    assert _expand_participant_name("devops_engineer", 2, 1) == "devops_engineer_1"
    assert _expand_participant_name("devops_engineer", 2, 2) == "devops_engineer_2"


# ---------------------------------------------------------------------------
# BaseAgentlet._build_swarm_nodes()
# ---------------------------------------------------------------------------


def _make_swarm_agentlet(swarm_cfg: SwarmConfig, mock_logger: Mock) -> BaseAgentlet:
    """Build a BaseAgentlet with swarm config, bypassing full spawn()."""
    config = _make_agentlet_config(swarm=swarm_cfg)
    with patch.object(BaseAgentlet, "__init__", lambda self, cfg, **kw: None):
        agentlet = BaseAgentlet.__new__(BaseAgentlet)
    agentlet.config = config
    agentlet.execution_id = "swarm-exec-id"
    agentlet.logger = mock_logger
    agentlet._sub_mcp_managers = []
    agentlet._swarm = None
    agentlet._swarm_node_times = {}
    agentlet._sub_agentlet_stats = {}
    agentlet.context = Mock()
    agentlet.context.working_dir = "/tmp/test"
    return agentlet


@pytest.fixture
def mock_logger() -> Mock:
    logger = Mock()
    logger.info = Mock()
    logger.success = Mock()
    logger.error = Mock()
    logger.metrics = Mock()
    logger.debug_log = Mock()
    logger.logger = Mock()
    return logger


def test_build_swarm_nodes_correct_count(mock_logger):
    """Total nodes created equals sum of participant counts."""
    cfg = SwarmConfig(
        participants=[
            _make_participant(name="architect", count=2),
            _make_participant(name="developer", count=3),
        ]
    )
    agentlet = _make_swarm_agentlet(cfg, mock_logger)
    default_model = Mock()

    with (
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
    ):
        mock_dtm.return_value.get_tools.return_value = []
        mock_agent_cls.side_effect = lambda **kw: Mock(name=kw["name"])

        nodes = agentlet._build_swarm_nodes(default_model, "bedrock/claude-sonnet-4-5")

    assert len(nodes) == 5  # 2 + 3


def test_build_swarm_nodes_expanded_names(mock_logger):
    """Nodes with count>1 get _N suffix; count=1 gets no suffix."""
    cfg = SwarmConfig(
        participants=[
            _make_participant(name="solo", count=1),
            _make_participant(name="twin", count=2),
        ]
    )
    agentlet = _make_swarm_agentlet(cfg, mock_logger)
    default_model = Mock()

    created_names = []

    with (
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
    ):
        mock_dtm.return_value.get_tools.return_value = []

        def capture_name(**kw):
            m = Mock()
            m.name = kw["name"]
            created_names.append(kw["name"])
            return m

        mock_agent_cls.side_effect = capture_name
        agentlet._build_swarm_nodes(default_model, "bedrock/claude-sonnet-4-5")

    assert "solo" in created_names
    assert "twin_1" in created_names
    assert "twin_2" in created_names
    assert "twin" not in created_names


def test_build_swarm_nodes_model_inheritance(mock_logger):
    """Participants without model override reuse the default_model."""
    cfg = SwarmConfig(participants=[_make_participant(name="agent")])
    agentlet = _make_swarm_agentlet(cfg, mock_logger)
    default_model = Mock()

    with (
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
    ):
        mock_dtm.return_value.get_tools.return_value = []
        mock_agent_cls.return_value = Mock(name="agent")

        agentlet._build_swarm_nodes(default_model, "bedrock/claude-sonnet-4-5")

        _, kwargs = mock_agent_cls.call_args
        assert kwargs["model"] is default_model


def test_build_swarm_nodes_model_override(mock_logger):
    """Participants with model override get a new LiteLLMModel."""
    cfg = SwarmConfig(
        participants=[
            _make_participant(
                name="specialist",
                model=ModelConfig(provider="bedrock", model_id="claude-haiku-4-5"),
            )
        ]
    )
    agentlet = _make_swarm_agentlet(cfg, mock_logger)
    default_model = Mock()

    with (
        patch("agentlet_core.agents.base.LiteLLMModel") as mock_litellm,
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
    ):
        mock_litellm.return_value = Mock()
        mock_dtm.return_value.get_tools.return_value = []
        mock_agent_cls.return_value = Mock(name="specialist")

        agentlet._build_swarm_nodes(default_model, "bedrock/claude-sonnet-4-5")

        mock_litellm.assert_called_once()
        assert mock_litellm.call_args[1]["model_id"] == "bedrock/claude-haiku-4-5"


def test_build_swarm_nodes_top_level_tools_go_to_entry_point(mock_logger):
    """Top-level config.tools are applied only to the entry_point agent."""
    cfg = SwarmConfig(
        participants=[
            _make_participant(name="entry"),
            _make_participant(name="other"),
        ],
        entry_point="entry",
    )
    config = _make_agentlet_config(swarm=cfg, tools=["swarm"])
    with patch.object(BaseAgentlet, "__init__", lambda self, c, **kw: None):
        agentlet = BaseAgentlet.__new__(BaseAgentlet)
    agentlet.config = config
    agentlet.execution_id = "exec-id"
    agentlet.logger = mock_logger
    agentlet._sub_mcp_managers = []
    agentlet.context = Mock()
    agentlet.context.working_dir = "/tmp"

    tools_per_agent: dict[str, list] = {}

    with (
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
    ):
        swarm_tool_mock = Mock()
        mock_dtm.return_value.get_tools.return_value = [swarm_tool_mock]

        def capture(**kw):
            m = Mock()
            m.name = kw["name"]
            tools_per_agent[kw["name"]] = kw["tools"]
            return m

        mock_agent_cls.side_effect = capture
        agentlet._build_swarm_nodes(Mock(), "bedrock/claude-sonnet-4-5")

    # entry gets swarm tool; other does not
    assert swarm_tool_mock in tools_per_agent["entry"]
    assert swarm_tool_mock not in tools_per_agent.get("other", [])


def test_build_swarm_nodes_trace_attributes(mock_logger):
    """Each node gets swarm_participant.name and swarm.parent_execution_id in trace attrs."""
    cfg = SwarmConfig(participants=[_make_participant(name="worker")])
    agentlet = _make_swarm_agentlet(cfg, mock_logger)
    agentlet.execution_id = "parent-123"

    with (
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
        patch.object(agentlet, "_build_trace_attributes", return_value={"base": "val"}),
    ):
        mock_dtm.return_value.get_tools.return_value = []
        mock_agent_cls.return_value = Mock(name="worker")

        agentlet._build_swarm_nodes(Mock(), "bedrock/model")

        _, kwargs = mock_agent_cls.call_args
        attrs = kwargs["trace_attributes"]
        assert attrs["swarm_participant.name"] == "worker"
        assert attrs["swarm.parent_execution_id"] == "parent-123"
        assert attrs["agentlet.name"] == "worker"


# ---------------------------------------------------------------------------
# BaseAgentlet.spawn() — swarm branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spawn_swarm_mode_sets_self_swarm(mock_logger):
    """spawn() sets self._swarm when config.swarm is configured."""
    cfg = _make_agentlet_config(
        swarm=SwarmConfig(participants=[_make_participant(name="agent", count=1)])
    )
    agentlet = BaseAgentlet(cfg, logger=mock_logger)

    with (
        patch("agentlet_core.agents.base.LiteLLMModel"),
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
        patch("agentlet_core.agents.base.Swarm") as mock_swarm_cls,
    ):
        mock_dtm.return_value.get_tools.return_value = []
        mock_agent_cls.return_value = Mock(name="agent")
        mock_swarm_cls.return_value = Mock()

        await agentlet.spawn()

    assert agentlet._swarm is not None
    assert agentlet._agent is None  # single-agent path not taken


@pytest.mark.asyncio
async def test_spawn_swarm_passes_safety_params(mock_logger):
    """spawn() passes all SwarmConfig safety params to Swarm constructor."""
    cfg = _make_agentlet_config(
        swarm=SwarmConfig(
            participants=[_make_participant()],
            max_handoffs=15,
            max_iterations=25,
            execution_timeout=600.0,
            node_timeout=120.0,
        )
    )
    agentlet = BaseAgentlet(cfg, logger=mock_logger)

    with (
        patch("agentlet_core.agents.base.LiteLLMModel"),
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
        patch("agentlet_core.agents.base.Swarm") as mock_swarm_cls,
    ):
        mock_dtm.return_value.get_tools.return_value = []
        mock_agent_cls.return_value = Mock(name="researcher")
        mock_swarm_cls.return_value = Mock()

        await agentlet.spawn()

    _, kwargs = mock_swarm_cls.call_args
    assert kwargs["max_handoffs"] == 15
    assert kwargs["max_iterations"] == 25
    assert kwargs["execution_timeout"] == 600.0
    assert kwargs["node_timeout"] == 120.0


# ---------------------------------------------------------------------------
# Swarm event handlers
# ---------------------------------------------------------------------------


def _make_agentlet_in_swarm_mode(mock_logger: Mock) -> BaseAgentlet:
    """Return a BaseAgentlet with self._swarm set (mocked)."""
    cfg = _make_agentlet_config(swarm=_make_swarm_config())
    with patch.object(BaseAgentlet, "__init__", lambda self, c, **kw: None):
        agentlet = BaseAgentlet.__new__(BaseAgentlet)
    agentlet.config = cfg
    agentlet.logger = mock_logger
    agentlet._swarm = Mock()  # non-None signals swarm mode
    agentlet._swarm_node_times = {}
    agentlet._swarm_node_tokens = {}
    agentlet._current_swarm_node = None
    return agentlet


def test_handle_swarm_node_event_logs_agent_name(mock_logger):
    agentlet = _make_agentlet_in_swarm_mode(mock_logger)
    node_timer: dict = {"current_node": None, "start_time": None, "node_times": {}}

    agentlet._handle_swarm_node_event(
        {"type": "multiagent_node_start", "node_id": "researcher_1"},
        node_timer,
    )

    mock_logger.info.assert_called_once()
    assert "researcher_1" in mock_logger.info.call_args[0][0]
    assert node_timer["current_node"] == "researcher_1"


def test_handle_swarm_node_event_records_previous_node_time(mock_logger):
    agentlet = _make_agentlet_in_swarm_mode(mock_logger)
    import time

    node_timer: dict = {
        "current_node": "prev_agent",
        "start_time": time.monotonic() - 2.0,  # 2 seconds ago
        "node_times": {},
    }

    agentlet._handle_swarm_node_event(
        {"type": "multiagent_node_start", "node_id": "next_agent"},
        node_timer,
    )

    assert "prev_agent" in node_timer["node_times"]
    assert node_timer["node_times"]["prev_agent"] >= 2.0
    assert node_timer["current_node"] == "next_agent"


def test_handle_swarm_node_event_ignores_non_swarm_events(mock_logger):
    agentlet = _make_agentlet_in_swarm_mode(mock_logger)
    node_timer: dict = {"current_node": None, "start_time": None, "node_times": {}}

    agentlet._handle_swarm_node_event({"data": "some text"}, node_timer)

    mock_logger.info.assert_not_called()
    assert node_timer["current_node"] is None


def test_handle_swarm_node_event_noop_when_not_swarm_mode(mock_logger):
    cfg = _make_agentlet_config()
    with patch.object(BaseAgentlet, "__init__", lambda self, c, **kw: None):
        agentlet = BaseAgentlet.__new__(BaseAgentlet)
    agentlet.config = cfg
    agentlet.logger = mock_logger
    agentlet._swarm = None  # not in swarm mode
    node_timer: dict = {"current_node": None, "start_time": None, "node_times": {}}

    agentlet._handle_swarm_node_event(
        {"type": "multiagent_node_start", "node_id": "agent"},
        node_timer,
    )

    mock_logger.info.assert_not_called()


def test_handle_swarm_handoff_event_logs_transition(mock_logger):
    agentlet = _make_agentlet_in_swarm_mode(mock_logger)

    agentlet._handle_swarm_handoff_event(
        {
            "type": "multiagent_handoff",
            "from_node_ids": ["researcher_1"],
            "to_node_ids": ["writer_1"],
        }
    )

    mock_logger.info.assert_called_once()
    call_arg = mock_logger.info.call_args[0][0]
    assert "researcher_1" in call_arg
    assert "writer_1" in call_arg


def test_handle_swarm_handoff_event_ignores_other_events(mock_logger):
    agentlet = _make_agentlet_in_swarm_mode(mock_logger)
    agentlet._handle_swarm_handoff_event({"data": "text"})
    mock_logger.info.assert_not_called()


# ---------------------------------------------------------------------------
# BaseAgentlet.execute() — swarm branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_swarm_streams_from_swarm(mock_logger):
    """execute() drives Swarm.stream_async when self._swarm is set."""
    cfg = _make_agentlet_config(swarm=_make_swarm_config())
    agentlet = BaseAgentlet(cfg, logger=mock_logger)
    agentlet._swarm = Mock()
    agentlet._agent = None
    agentlet._swarm_node_times = {}
    agentlet._sub_agentlet_stats = {}
    agentlet._tool_use_names = {}
    agentlet._recorded_tool_calls = set()

    from agentlet_core.runtime.context import ExecutionContext
    from datetime import datetime

    agentlet.context = ExecutionContext(
        execution_id="exec-id",
        agentlet_name="test",
        working_dir=None,
        start_time=datetime.now(),
    )

    async def fake_stream(prompt):
        yield {"data": "hello"}
        yield {"data": " world"}

    agentlet._swarm.stream_async = fake_stream

    chunks = []
    async for chunk in agentlet.execute("test prompt"):
        chunks.append(chunk)

    assert chunks == ["hello", " world"]


@pytest.mark.asyncio
async def test_execute_raises_when_neither_agent_nor_swarm(mock_logger):
    """execute() raises RuntimeError when spawn() was not called."""
    cfg = _make_agentlet_config()
    agentlet = BaseAgentlet(cfg, logger=mock_logger)
    agentlet._swarm = None
    agentlet._agent = None
    agentlet.context = None

    with pytest.raises(RuntimeError, match="not spawned"):
        async for _ in agentlet.execute("prompt"):
            pass


# ---------------------------------------------------------------------------
# BaseAgentlet._log_swarm_stats()
# ---------------------------------------------------------------------------


def test_log_swarm_stats_outputs_per_node_times(mock_logger):
    cfg = _make_agentlet_config(swarm=_make_swarm_config())
    with patch.object(BaseAgentlet, "__init__", lambda self, c, **kw: None):
        agentlet = BaseAgentlet.__new__(BaseAgentlet)
    agentlet.config = cfg
    agentlet.logger = mock_logger
    agentlet._swarm_node_times = {
        "researcher_1": 3.2,
        "writer_1": 1.8,
    }
    agentlet._swarm_node_tokens = {}

    agentlet._log_swarm_stats()

    calls = [str(c) for c in mock_logger.metrics.call_args_list]
    combined = " ".join(calls)
    assert "researcher_1" in combined
    assert "writer_1" in combined
    assert "3.2" in combined
    assert "1.8" in combined


def test_log_swarm_stats_noop_when_no_times(mock_logger):
    cfg = _make_agentlet_config(swarm=_make_swarm_config())
    with patch.object(BaseAgentlet, "__init__", lambda self, c, **kw: None):
        agentlet = BaseAgentlet.__new__(BaseAgentlet)
    agentlet.config = cfg
    agentlet.logger = mock_logger
    agentlet._swarm_node_times = {}
    agentlet._swarm_node_tokens = {}

    agentlet._log_swarm_stats()


# ---------------------------------------------------------------------------
# Entry-point resolution with count > 1
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spawn_entry_point_count_gt_one_resolves_first_instance(mock_logger):
    """When entry_point names a participant with count>1, spawn uses the _1 instance."""
    cfg = _make_agentlet_config(
        swarm=SwarmConfig(
            participants=[_make_participant(name="analyst", count=2)],
            entry_point="analyst",
        )
    )
    agentlet = BaseAgentlet(cfg, logger=mock_logger)

    with (
        patch("agentlet_core.agents.base.LiteLLMModel"),
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
        patch("agentlet_core.agents.base.Swarm") as mock_swarm_cls,
    ):
        mock_dtm.return_value.get_tools.return_value = []

        created: list[Mock] = []

        def make_agent(**kw):
            m = Mock()
            m.name = kw["name"]
            created.append(m)
            return m

        mock_agent_cls.side_effect = make_agent
        mock_swarm_cls.return_value = Mock()

        await agentlet.spawn()

    _, swarm_kwargs = mock_swarm_cls.call_args
    entry = swarm_kwargs["entry_point"]
    assert entry.name == "analyst_1"


# ---------------------------------------------------------------------------
# Swarm warning for top-level mcp_tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spawn_warns_top_level_mcp_tools_ignored_in_swarm_mode(mock_logger):
    """spawn() warns when top-level mcp_tools are declared in swarm mode."""
    cfg = _make_agentlet_config(
        swarm=_make_swarm_config(),
        mcp_tools=[
            MCPToolConfig(
                name="fs",
                server="stdio",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem"],
            )
        ],
    )
    agentlet = BaseAgentlet(cfg, logger=mock_logger)

    with (
        patch("agentlet_core.agents.base.LiteLLMModel"),
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
        patch("agentlet_core.agents.base.Swarm") as mock_swarm_cls,
    ):
        mock_dtm.return_value.get_tools.return_value = []
        mock_agent_cls.return_value = Mock(name="researcher")
        mock_swarm_cls.return_value = Mock()

        await agentlet.spawn()

    warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
    assert any("mcp_tools" in c for c in warning_calls)


# ---------------------------------------------------------------------------
# Participant MCP cleanup in terminate()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spawn_participant_mcp_tools_added_to_sub_mcp_managers(mock_logger):
    """Participants with mcp_tools get their MCPToolsManager stored for cleanup."""
    cfg = _make_agentlet_config(
        swarm=SwarmConfig(
            participants=[
                _make_participant(
                    name="worker",
                    mcp_tools=[
                        MCPToolConfig(
                            name="fs",
                            server="stdio",
                            command="npx",
                            args=["-y", "@modelcontextprotocol/server-filesystem"],
                        )
                    ],
                )
            ]
        )
    )
    agentlet = BaseAgentlet(cfg, logger=mock_logger)

    mock_mgr = Mock()
    mock_mgr.get_tools_sync.return_value = []

    with (
        patch("agentlet_core.agents.base.LiteLLMModel"),
        patch("agentlet_core.agents.base.DefaultToolsManager") as mock_dtm,
        patch("agentlet_core.agents.base.Agent") as mock_agent_cls,
        patch("agentlet_core.agents.base.Swarm") as mock_swarm_cls,
        patch("agentlet_core.agents.base.MCPToolsManager", return_value=mock_mgr),
    ):
        mock_dtm.return_value.get_tools.return_value = []
        mock_agent_cls.return_value = Mock(name="worker")
        mock_swarm_cls.return_value = Mock()

        await agentlet.spawn()

    assert mock_mgr in agentlet._sub_mcp_managers
    mock_mgr.initialize.assert_called_once()
    mock_mgr.enter_contexts.assert_called_once()


@pytest.mark.asyncio
async def test_terminate_cleans_up_participant_mcp_managers(mock_logger):
    """terminate() calls cleanup_sync() on all participant MCP managers."""
    cfg = _make_agentlet_config(swarm=_make_swarm_config())
    agentlet = BaseAgentlet(cfg, logger=mock_logger)
    agentlet._mcp_manager = None
    agentlet._swarm = None

    mgr1, mgr2 = Mock(), Mock()
    agentlet._sub_mcp_managers = [mgr1, mgr2]

    with (
        patch.object(agentlet, "_cleanup_aiohttp_sessions"),
    ):
        await agentlet.terminate()

    mgr1.cleanup_sync.assert_called_once()
    mgr2.cleanup_sync.assert_called_once()

    mock_logger.metrics.assert_not_called()
