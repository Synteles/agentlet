"""Unit tests for BaseAgentlet helper methods (no live LLM calls)."""

import logging
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from agentlet_core.agents.base import BaseAgentlet, _expand_participant_name
from agentlet_core.config.models import AgentletConfig, AgentletMetadata, ModelConfig
from agentlet_core.runtime.context import ExecutionContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    show_tool_calls: bool = True,
    show_messages: bool = True,
    show_reasoning: bool = True,
    show_turn_boundaries: bool = True,
) -> AgentletConfig:
    cfg = AgentletConfig(
        agentlet=AgentletMetadata(name="test-agent"),
        model=ModelConfig(provider="bedrock", model_id="claude-sonnet-4-5"),
        system_prompt="You are helpful.",
    )
    cfg.output.show_tool_calls = show_tool_calls
    cfg.output.show_messages = show_messages
    cfg.output.show_reasoning = show_reasoning
    cfg.output.show_turn_boundaries = show_turn_boundaries
    return cfg


def _make_agent(**cfg_kwargs) -> BaseAgentlet:
    config = _make_config(**cfg_kwargs)
    mock_logger = MagicMock()
    mock_logger.logger = logging.getLogger("test.base_agent")
    return BaseAgentlet(config=config, logger=mock_logger)


def _with_context(agent: BaseAgentlet) -> ExecutionContext:
    ctx = ExecutionContext(execution_id="test-exec", agentlet_name="test-agent")
    ctx.start_execution()
    agent.context = ctx
    return ctx


# ---------------------------------------------------------------------------
# _expand_participant_name
# ---------------------------------------------------------------------------


class TestExpandParticipantName:
    def test_single_instance_no_suffix(self):
        assert _expand_participant_name("researcher", 1, 1) == "researcher"

    def test_multiple_instances_adds_suffix(self):
        assert _expand_participant_name("researcher", 3, 1) == "researcher_1"
        assert _expand_participant_name("researcher", 3, 2) == "researcher_2"
        assert _expand_participant_name("researcher", 3, 3) == "researcher_3"


# ---------------------------------------------------------------------------
# _resolve_execution_id
# ---------------------------------------------------------------------------


class TestResolveExecutionId:
    def test_generates_uuid_when_env_not_set(self, monkeypatch):
        monkeypatch.delenv("SYNTELES_EXEC_ID", raising=False)
        eid = BaseAgentlet._resolve_execution_id()
        # Should be a valid UUID4 string
        from uuid import UUID

        parsed = UUID(eid)
        assert parsed.version == 4

    def test_uses_valid_uuid4_from_env(self, monkeypatch):
        valid_uuid = str(uuid4())
        monkeypatch.setenv("SYNTELES_EXEC_ID", valid_uuid)
        result = BaseAgentlet._resolve_execution_id()
        assert result == valid_uuid

    def test_ignores_non_uuid4_and_generates_new(self, monkeypatch):
        monkeypatch.setenv("SYNTELES_EXEC_ID", "not-a-uuid")
        result = BaseAgentlet._resolve_execution_id()
        # Should fall back to a new UUID
        from uuid import UUID

        parsed = UUID(result)
        assert parsed.version == 4

    def test_ignores_uuid_non_v4_and_generates_new(self, monkeypatch):
        # UUID v1 example
        monkeypatch.setenv("SYNTELES_EXEC_ID", "550e8400-e29b-11d4-a716-446655440000")
        result = BaseAgentlet._resolve_execution_id()
        from uuid import UUID

        parsed = UUID(result)
        assert parsed.version == 4


# ---------------------------------------------------------------------------
# _get_litellm_model_id
# ---------------------------------------------------------------------------


class TestGetLitellmModelId:
    def test_adds_provider_prefix(self):
        agent = _make_agent()
        assert agent._get_litellm_model_id() == "bedrock/claude-sonnet-4-5"

    def test_no_double_prefix(self):
        config = AgentletConfig(
            agentlet=AgentletMetadata(name="t"),
            model=ModelConfig(provider="bedrock", model_id="bedrock/claude-sonnet-4-5"),
            system_prompt="Hi.",
        )
        mock_logger = MagicMock()
        mock_logger.logger = logging.getLogger("test")
        agent = BaseAgentlet(config=config, logger=mock_logger)
        assert agent._get_litellm_model_id() == "bedrock/claude-sonnet-4-5"


# ---------------------------------------------------------------------------
# _build_trace_attributes
# ---------------------------------------------------------------------------


class TestBuildTraceAttributes:
    def test_contains_required_keys(self):
        agent = _make_agent()
        attrs = agent._build_trace_attributes()
        assert attrs["gen_ai.system"] == "synteles-agentlet"
        assert attrs["agentlet.name"] == "test-agent"
        assert attrs["model.provider"] == "bedrock"
        assert attrs["model.id"] == "claude-sonnet-4-5"

    def test_merges_custom_trace_attributes(self):
        config = _make_config()
        config.observability.otel.trace_attributes = {"custom": "value"}
        mock_logger = MagicMock()
        mock_logger.logger = logging.getLogger("test")
        agent = BaseAgentlet(config=config, logger=mock_logger)
        attrs = agent._build_trace_attributes()
        assert attrs["custom"] == "value"


# ---------------------------------------------------------------------------
# _extract_result_text
# ---------------------------------------------------------------------------


class TestExtractResultText:
    def test_list_with_dict_text(self):
        agent = _make_agent()
        assert agent._extract_result_text([{"text": "hello"}]) == "hello"

    def test_list_with_non_dict_first(self):
        agent = _make_agent()
        assert agent._extract_result_text(["plain"]) == "plain"

    def test_empty_list_falls_through(self):
        agent = _make_agent()
        result = agent._extract_result_text([])
        assert result == "[]"

    def test_non_list_content(self):
        agent = _make_agent()
        assert agent._extract_result_text("raw") == "raw"

    def test_dict_without_text_key(self):
        agent = _make_agent()
        result = agent._extract_result_text([{"other": "data"}])
        assert "other" in result


# ---------------------------------------------------------------------------
# _handle_text_event
# ---------------------------------------------------------------------------


class TestHandleTextEvent:
    def test_returns_chunk_when_data_present(self):
        agent = _make_agent()
        buf: list[str] = []
        chunk = agent._handle_text_event({"data": "hello"}, buf)
        assert chunk == "hello"
        assert buf == ["hello"]

    def test_returns_none_when_no_data(self):
        agent = _make_agent()
        buf: list[str] = []
        chunk = agent._handle_text_event({}, buf)
        assert chunk is None
        assert buf == []

    def test_returns_none_when_data_empty(self):
        agent = _make_agent()
        buf: list[str] = []
        chunk = agent._handle_text_event({"data": ""}, buf)
        assert chunk is None


# ---------------------------------------------------------------------------
# _handle_tool_call_event
# ---------------------------------------------------------------------------


class TestHandleToolCallEvent:
    def test_skips_when_show_tool_calls_false(self):
        agent = _make_agent(show_tool_calls=False)
        event = {"current_tool_use": {"toolUseId": "1", "name": "bash", "input": {}}}
        agent._handle_tool_call_event(event)
        agent.logger.tool_call.assert_not_called()

    def test_skips_when_no_current_tool_use(self):
        agent = _make_agent(show_tool_calls=True)
        agent._handle_tool_call_event({"data": "something"})
        agent.logger.tool_call.assert_not_called()

    def test_displays_tool_call_and_stores_name(self):
        agent = _make_agent(show_tool_calls=True)
        event = {
            "current_tool_use": {
                "toolUseId": "abc",
                "name": "bash",
                "input": {"cmd": "ls"},
            }
        }
        agent._handle_tool_call_event(event)
        agent.logger.tool_call.assert_called_once()
        assert agent._tool_use_names["abc"] == "bash"

    def test_records_in_context_once(self):
        agent = _make_agent(show_tool_calls=True)
        ctx = _with_context(agent)
        event = {
            "current_tool_use": {
                "toolUseId": "id1",
                "name": "bash",
                "input": {"cmd": "ls"},
            }
        }
        agent._handle_tool_call_event(event)
        agent._handle_tool_call_event(event)  # duplicate — should not double-record
        assert len(ctx.tool_calls) == 1


# ---------------------------------------------------------------------------
# _handle_tool_result_event
# ---------------------------------------------------------------------------


class TestHandleToolResultEvent:
    def test_skips_when_show_tool_calls_false(self):
        agent = _make_agent(show_tool_calls=False)
        event = {
            "message": {
                "role": "user",
                "content": [
                    {
                        "toolResult": {
                            "toolUseId": "1",
                            "status": "success",
                            "content": [],
                        }
                    }
                ],
            }
        }
        agent._handle_tool_result_event(event)
        agent.logger.tool_result.assert_not_called()

    def test_skips_when_no_message(self):
        agent = _make_agent(show_tool_calls=True)
        agent._handle_tool_result_event({"data": "x"})
        agent.logger.tool_result.assert_not_called()

    def test_skips_when_message_not_user_role(self):
        agent = _make_agent(show_tool_calls=True)
        event = {"message": {"role": "assistant", "content": []}}
        agent._handle_tool_result_event(event)
        agent.logger.tool_result.assert_not_called()

    def test_displays_tool_result(self):
        agent = _make_agent(show_tool_calls=True)
        agent._tool_use_names["id1"] = "bash"
        event = {
            "message": {
                "role": "user",
                "content": [
                    {
                        "toolResult": {
                            "toolUseId": "id1",
                            "status": "success",
                            "content": [{"text": "ok"}],
                        }
                    }
                ],
            }
        }
        agent._handle_tool_result_event(event)
        agent.logger.tool_result.assert_called_once()

    def test_records_error_in_context(self):
        agent = _make_agent(show_tool_calls=True)
        ctx = _with_context(agent)
        event = {
            "message": {
                "role": "user",
                "content": [
                    {
                        "toolResult": {
                            "toolUseId": "id1",
                            "status": "error",
                            "content": [{"text": "fail"}],
                        }
                    }
                ],
            }
        }
        agent._handle_tool_result_event(event)
        assert len(ctx.errors) > 0


# ---------------------------------------------------------------------------
# _handle_message_event
# ---------------------------------------------------------------------------


class TestHandleMessageEvent:
    def test_skips_when_no_message(self):
        agent = _make_agent()
        buf = ["chunk"]
        agent._handle_message_event({"data": "x"}, buf)
        assert buf == ["chunk"]  # unchanged

    def test_skips_non_dict_message(self):
        agent = _make_agent()
        buf = ["chunk"]
        agent._handle_message_event({"message": "plain"}, buf)

    def test_displays_assistant_message_and_clears_buffer(self):
        agent = _make_agent(show_messages=True)
        buf = ["hello ", "world"]
        agent._handle_message_event({"message": {"role": "assistant"}}, buf)
        agent.logger.assistant_message.assert_called_once_with("hello world")
        assert buf == []

    def test_skips_user_message(self):
        agent = _make_agent(show_messages=True)
        buf = ["data"]
        agent._handle_message_event({"message": {"role": "user"}}, buf)
        agent.logger.assistant_message.assert_not_called()

    def test_skips_empty_buffer(self):
        agent = _make_agent(show_messages=True)
        buf: list[str] = []
        agent._handle_message_event({"message": {"role": "assistant"}}, buf)
        agent.logger.assistant_message.assert_not_called()


# ---------------------------------------------------------------------------
# _handle_reasoning_event
# ---------------------------------------------------------------------------


class TestHandleReasoningEvent:
    def test_skips_when_show_reasoning_false(self):
        agent = _make_agent(show_reasoning=False)
        buf: list[str] = []
        agent._handle_reasoning_event(
            {"reasoning": True, "reasoningText": "think"}, buf
        )
        assert buf == []

    def test_buffers_reasoning_text(self):
        agent = _make_agent(show_reasoning=True)
        buf: list[str] = []
        agent._handle_reasoning_event(
            {"reasoning": True, "reasoningText": "think"}, buf
        )
        assert "think" in buf

    def test_displays_on_message_event(self):
        agent = _make_agent(show_reasoning=True)
        buf = ["step 1"]
        agent._handle_reasoning_event({"message": True}, buf)
        agent.logger.reasoning_block.assert_called_once_with("step 1")
        assert buf == []

    def test_skips_empty_reasoning_buffer(self):
        agent = _make_agent(show_reasoning=True)
        buf: list[str] = []
        agent._handle_reasoning_event({"message": True}, buf)
        agent.logger.reasoning_block.assert_not_called()


# ---------------------------------------------------------------------------
# _handle_turn_boundary
# ---------------------------------------------------------------------------


class TestHandleTurnBoundary:
    def test_skips_when_show_turn_boundaries_false(self):
        agent = _make_agent(show_turn_boundaries=False)
        counter = {"count": 0}
        agent._handle_turn_boundary({"start_event_loop": True}, counter)
        assert counter["count"] == 0

    def test_increments_counter_on_start_event(self):
        agent = _make_agent(show_turn_boundaries=True)
        counter = {"count": 0}
        agent._handle_turn_boundary({"start_event_loop": True}, counter)
        assert counter["count"] == 1

    def test_first_turn_no_boundary_displayed(self):
        agent = _make_agent(show_turn_boundaries=True)
        counter = {"count": 0}
        agent._handle_turn_boundary({"start_event_loop": True}, counter)
        agent.logger.turn_boundary.assert_not_called()

    def test_second_turn_boundary_displayed(self):
        agent = _make_agent(show_turn_boundaries=True)
        counter = {"count": 1}
        agent._handle_turn_boundary({"start_event_loop": True}, counter)
        agent.logger.turn_boundary.assert_called_once_with(2)

    def test_non_start_event_ignored(self):
        agent = _make_agent(show_turn_boundaries=True)
        counter = {"count": 0}
        agent._handle_turn_boundary({"data": "x"}, counter)
        assert counter["count"] == 0


# ---------------------------------------------------------------------------
# _handle_token_usage
# ---------------------------------------------------------------------------


class TestHandleTokenUsage:
    def test_skips_when_no_event_key(self):
        agent = _make_agent()
        ctx = _with_context(agent)
        agent._handle_token_usage({"data": "x"})
        assert ctx.input_tokens == 0

    def test_skips_when_no_metadata(self):
        agent = _make_agent()
        ctx = _with_context(agent)
        agent._handle_token_usage({"event": {}})
        assert ctx.input_tokens == 0

    def test_skips_when_no_usage(self):
        agent = _make_agent()
        ctx = _with_context(agent)
        agent._handle_token_usage({"event": {"metadata": {}}})
        assert ctx.input_tokens == 0

    def test_updates_context_on_valid_usage(self):
        agent = _make_agent()
        ctx = _with_context(agent)
        with patch("litellm.cost_per_token", return_value=(0.001, 0.002)):
            agent._handle_token_usage(
                {
                    "event": {
                        "metadata": {
                            "usage": {
                                "inputTokens": 100,
                                "outputTokens": 50,
                                "cacheReadInputTokens": 0,
                            }
                        }
                    }
                }
            )
        assert ctx.input_tokens == 100
        assert ctx.output_tokens == 50


# ---------------------------------------------------------------------------
# _log_main_agentlet_stats
# ---------------------------------------------------------------------------


class TestLogMainAgentletStats:
    def test_no_op_without_context(self):
        agent = _make_agent()
        agent.context = None
        agent._log_main_agentlet_stats()
        agent.logger.metrics.assert_not_called()

    def test_logs_with_context(self):
        agent = _make_agent()
        _with_context(agent)
        agent._log_main_agentlet_stats()
        assert agent.logger.metrics.call_count >= 1


# ---------------------------------------------------------------------------
# _log_sub_agentlet_stats
# ---------------------------------------------------------------------------


class TestLogSubAgentletStats:
    def test_no_op_when_no_stats(self):
        agent = _make_agent()
        agent._log_sub_agentlet_stats()
        agent.logger.metrics.assert_not_called()

    def test_logs_error_stats(self):
        agent = _make_agent()
        _with_context(agent)
        agent._sub_agentlet_stats = {"sub1": {"execution_time": 1.0, "error": "boom"}}
        agent._log_sub_agentlet_stats()
        agent.logger.metrics.assert_called()

    def test_logs_success_stats_and_adds_tokens(self):
        agent = _make_agent()
        ctx = _with_context(agent)
        agent._sub_agentlet_stats = {
            "sub1": {
                "execution_time": 2.5,
                "input_tokens": 100,
                "output_tokens": 50,
                "total_cost": 0.001,
            }
        }
        agent._log_sub_agentlet_stats()
        # Tokens should be added to context
        assert ctx.input_tokens == 100
        assert ctx.output_tokens == 50


# ---------------------------------------------------------------------------
# _log_swarm_stats
# ---------------------------------------------------------------------------


class TestLogSwarmStats:
    def test_no_op_when_empty(self):
        agent = _make_agent()
        agent._log_swarm_stats()
        agent.logger.metrics.assert_not_called()

    def test_logs_node_times(self):
        agent = _make_agent()
        agent._swarm_node_times = {"node1": 3.2, "node2": 1.8}
        agent._log_swarm_stats()
        assert agent.logger.metrics.call_count >= 2


# ---------------------------------------------------------------------------
# _calculate_cost
# ---------------------------------------------------------------------------


class TestCalculateCost:
    def test_returns_sum_of_costs(self):
        agent = _make_agent()
        with patch("litellm.cost_per_token", return_value=(0.01, 0.02)):
            cost = agent._calculate_cost(100, 50, 0)
        assert cost == pytest.approx(0.03)

    def test_returns_zero_on_litellm_error(self):
        agent = _make_agent()
        with patch("litellm.cost_per_token", side_effect=Exception("unknown model")):
            cost = agent._calculate_cost(100, 50, 0)
        assert cost == 0.0
