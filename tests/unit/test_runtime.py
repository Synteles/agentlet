"""Unit tests for runtime context."""

import os
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from agentlet_core.agents.base import BaseAgentlet
from agentlet_core.runtime.context import ExecutionContext


def test_execution_context_initialization():
    """Test execution context initialization."""
    ctx = ExecutionContext(
        execution_id="test-123", agentlet_name="test-agent", working_dir="/tmp/test"
    )
    assert ctx.execution_id == "test-123"
    assert ctx.agentlet_name == "test-agent"
    assert ctx.working_dir == Path("/tmp/test").resolve()
    assert ctx.tool_calls == []
    assert ctx.errors == []
    assert ctx.input_tokens == 0
    assert ctx.output_tokens == 0
    assert ctx.total_cost == 0.0


def test_execution_context_temp_dir():
    """Test execution context creates temp directory."""
    ctx = ExecutionContext(execution_id="test-123", agentlet_name="test-agent")
    assert ctx.working_dir.exists()
    assert "agentlet_test-123" in str(ctx.working_dir)

    # Cleanup
    ctx.cleanup()
    assert not ctx.working_dir.exists()


def test_execution_time_tracking():
    """Test execution time tracking."""
    ctx = ExecutionContext(execution_id="test-123", agentlet_name="test-agent")
    ctx.start_execution()

    import time

    time.sleep(0.1)
    ctx.end_execution()

    assert ctx.execution_time >= 0.1


def test_tool_call_recording():
    """Test tool call recording."""
    ctx = ExecutionContext(execution_id="test-123", agentlet_name="test-agent")
    ctx.record_tool_call("test_tool", {"arg1": "value1"})

    assert len(ctx.tool_calls) == 1
    assert ctx.tool_calls[0]["tool"] == "test_tool"
    assert ctx.tool_calls[0]["args"]["arg1"] == "value1"


def test_error_recording():
    """Test error recording."""
    ctx = ExecutionContext(execution_id="test-123", agentlet_name="test-agent")
    ctx.record_error("Test error message")

    assert len(ctx.errors) == 1
    assert ctx.errors[0] == "Test error message"


def test_token_counting():
    """Test token counting."""
    ctx = ExecutionContext(execution_id="test-123", agentlet_name="test-agent")
    ctx.add_tokens(input_tokens=100, output_tokens=50, cost=0.001)
    ctx.add_tokens(input_tokens=200, output_tokens=100, cost=0.002)

    assert ctx.input_tokens == 300
    assert ctx.output_tokens == 150
    assert ctx.total_cost == 0.003


def test_execution_summary():
    """Test execution summary generation."""
    ctx = ExecutionContext(execution_id="test-123", agentlet_name="test-agent")
    ctx.start_execution()
    ctx.record_tool_call("tool1", {})
    ctx.record_error("error1")
    ctx.add_tokens(input_tokens=100, output_tokens=50, cost=0.001)
    ctx.end_execution()

    summary = ctx.get_summary()
    assert summary["execution_id"] == "test-123"
    assert summary["agentlet_name"] == "test-agent"
    assert summary["tool_calls"] == 1
    assert summary["errors"] == 1
    assert summary["input_tokens"] == 100
    assert summary["output_tokens"] == 50
    assert summary["total_tokens"] == 150
    assert summary["total_cost"] == "$0.001000"
    assert summary["start_time"] is not None
    assert summary["end_time"] is not None


# --- BaseAgentlet._resolve_execution_id tests ---


def test_resolve_execution_id_generates_uuid4_when_env_not_set():
    """Generates a fresh uuid4 when SYNTELES_EXEC_ID is not set."""
    with patch.dict("os.environ", {}, clear=False):
        # Ensure the var is absent
        os.environ.pop("SYNTELES_EXEC_ID", None)
        exec_id = BaseAgentlet._resolve_execution_id()
    parsed = uuid.UUID(exec_id)
    assert parsed.version == 4


def test_resolve_execution_id_uses_valid_uuid4_from_env():
    """Uses SYNTELES_EXEC_ID when it contains a valid UUID4."""
    valid_uuid4 = str(uuid.uuid4())
    with patch.dict("os.environ", {"SYNTELES_EXEC_ID": valid_uuid4}):
        exec_id = BaseAgentlet._resolve_execution_id()
    assert exec_id == valid_uuid4


def test_resolve_execution_id_falls_back_on_non_uuid4_version():
    """Falls back to generated uuid4 and warns when SYNTELES_EXEC_ID is a non-v4 UUID."""
    uuid1_value = str(uuid.uuid1())
    mock_logger = MagicMock()
    with patch("agentlet_core.agents.base.get_logger", return_value=mock_logger):
        with patch.dict("os.environ", {"SYNTELES_EXEC_ID": uuid1_value}):
            exec_id = BaseAgentlet._resolve_execution_id()
    assert exec_id != uuid1_value
    assert uuid.UUID(exec_id).version == 4
    mock_logger.warning.assert_called_once()
    assert "not a UUID4" in mock_logger.warning.call_args[0][0]


def test_resolve_execution_id_falls_back_on_invalid_string():
    """Falls back to generated uuid4 and warns when SYNTELES_EXEC_ID is not a UUID."""
    mock_logger = MagicMock()
    with patch("agentlet_core.agents.base.get_logger", return_value=mock_logger):
        with patch.dict("os.environ", {"SYNTELES_EXEC_ID": "not-a-uuid"}):
            exec_id = BaseAgentlet._resolve_execution_id()
    assert uuid.UUID(exec_id).version == 4
    mock_logger.warning.assert_called_once()
    assert "not a valid UUID" in mock_logger.warning.call_args[0][0]
