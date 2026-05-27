"""Unit tests for RichConsoleHandler, StructuredLogger, RichUI, RichLoggerAdapter."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from agentlet_core.logging.handlers import (
    RichConsoleHandler,
    RichLoggerAdapter,
    RichUI,
    StructuredLogger,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_logger():
    return logging.getLogger("test.handlers.ui")


@pytest.fixture
def structured(base_logger):
    return StructuredLogger(base_logger)


@pytest.fixture
def ui(structured):
    obj = RichUI(structured)
    obj.console = MagicMock()
    return obj


@pytest.fixture
def adapter(base_logger):
    obj = RichLoggerAdapter(base_logger)
    obj._rich_ui.console = MagicMock()
    obj.console = obj._rich_ui.console
    return obj


def _make_record(msg="test", level=logging.INFO, **attrs):
    rec = logging.LogRecord(
        name="test",
        level=level,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for k, v in attrs.items():
        setattr(rec, k, v)
    return rec


# ---------------------------------------------------------------------------
# RichConsoleHandler
# ---------------------------------------------------------------------------


class TestRichConsoleHandler:
    @pytest.fixture
    def handler(self):
        h = RichConsoleHandler()
        h.console = MagicMock()
        return h

    def test_file_only_skipped(self, handler):
        handler.emit(_make_record(log_type="file_only"))
        handler.console.print.assert_not_called()

    def test_metric_log_type(self, handler):
        handler.emit(_make_record("cpu=50%", log_type="metric"))
        handler.console.print.assert_called_once()
        assert "cpu=50%" in str(handler.console.print.call_args)

    def test_rich_renderable(self, handler):
        renderable = MagicMock()
        rec = _make_record()
        rec.rich_renderable = renderable
        handler.emit(rec)
        handler.console.print.assert_called_once_with(renderable)

    def test_standard_message(self, handler):
        handler.emit(_make_record("hello world"))
        handler.console.print.assert_called_once()
        assert "hello world" in str(handler.console.print.call_args)

    def test_emit_fallback_on_error(self, handler):
        handler.console.print.side_effect = RuntimeError("boom")
        # Should not raise
        handler.emit(_make_record("test"))


# ---------------------------------------------------------------------------
# StructuredLogger
# ---------------------------------------------------------------------------


class TestStructuredLogger:
    def test_debug(self, structured, base_logger):
        with patch.object(base_logger, "debug") as m:
            structured.debug("msg")
            m.assert_called_once_with("msg", extra=None)

    def test_debug_with_context(self, structured, base_logger):
        with patch.object(base_logger, "debug") as m:
            structured.debug("msg", k="v")
            m.assert_called_once_with("msg", extra={"k": "v"})

    def test_warning(self, structured, base_logger):
        with patch.object(base_logger, "warning") as m:
            structured.warning("warn")
            m.assert_called_once()

    def test_error(self, structured, base_logger):
        with patch.object(base_logger, "error") as m:
            structured.error("err")
            m.assert_called_once()

    def test_critical(self, structured, base_logger):
        with patch.object(base_logger, "critical") as m:
            structured.critical("crit")
            m.assert_called_once()

    def test_log(self, structured, base_logger):
        with patch.object(base_logger, "log") as m:
            structured.log(logging.WARNING, "msg", x=1)
            m.assert_called_once_with(logging.WARNING, "msg", extra={"x": 1})


# ---------------------------------------------------------------------------
# RichUI
# ---------------------------------------------------------------------------


class TestRichUI:
    def test_create_title(self, ui):
        title = ui._create_title("🔥", "Title")
        assert "Title" in str(title)

    def test_get_value_dict(self, ui):
        assert ui._get_value({"k": "v"}, "k") == "v"
        assert ui._get_value({"k": "v"}, "x", "d") == "d"

    def test_get_value_object(self, ui):
        class Obj:
            name = "test"

        assert ui._get_value(Obj(), "name") == "test"
        assert ui._get_value(Obj(), "missing", "d") == "d"

    def test_format_bullet_simple(self, ui):
        lines = ui._format_value_as_bullet("k", "v")
        assert len(lines) == 1

    def test_format_bullet_complex_dict(self, ui):
        lines = ui._format_value_as_bullet("k", {"a": 1})
        assert len(lines) > 1

    def test_format_bullet_complex_list(self, ui):
        lines = ui._format_value_as_bullet("k", [1, 2])
        assert len(lines) > 1

    def test_format_bullet_is_error_true(self, ui):
        lines = ui._format_value_as_bullet("is_error", True)
        assert len(lines) == 1

    def test_format_bullet_is_error_false(self, ui):
        lines = ui._format_value_as_bullet("is_error", False)
        assert len(lines) == 1

    def test_success(self, ui):
        ui.success("done")
        ui.console.print.assert_called_once()

    def test_tool_call_with_dict_input(self, ui):
        ui.tool_call({"toolUseId": "1", "name": "bash", "input": {"cmd": "ls"}})
        ui.console.print.assert_called()

    def test_tool_call_with_json_string_input(self, ui):
        ui.tool_call({"toolUseId": "1", "name": "bash", "input": '{"cmd": "ls"}'})
        ui.console.print.assert_called()

    def test_tool_call_with_empty_input(self, ui):
        ui.tool_call({"toolUseId": "1", "name": "bash", "input": {}})
        ui.console.print.assert_not_called()

    def test_tool_result_success_dict(self, ui):
        ui.tool_result("bash", {"status": "ok"}, success=True)
        ui.console.print.assert_called()

    def test_tool_result_failure(self, ui):
        ui.tool_result("bash", {"status": "err"}, success=False)
        ui.console.print.assert_called()

    def test_tool_result_string(self, ui):
        ui.tool_result("bash", "plain output")
        ui.console.print.assert_called()

    def test_tool_result_non_string(self, ui):
        ui.tool_result("bash", 42)
        ui.console.print.assert_called()

    def test_tool_result_auto_detect_is_error(self, ui):
        ui.tool_result("bash", {"is_error": True})
        ui.console.print.assert_called()

    def test_assistant_message_normal(self, ui):
        ui.assistant_message("Hello!")
        ui.console.print.assert_called()

    def test_assistant_message_empty(self, ui):
        ui.assistant_message("   ")
        ui.console.print.assert_not_called()

    def test_reasoning_block_normal(self, ui):
        ui.reasoning_block("I think...")
        ui.console.print.assert_called()

    def test_reasoning_block_empty(self, ui):
        ui.reasoning_block("")
        ui.console.print.assert_not_called()

    def test_turn_boundary(self, ui):
        ui.turn_boundary(2)
        ui.console.print.assert_called()

    def test_reasoning(self, ui):
        ui.reasoning("step 1")
        ui.console.print.assert_called()

    def test_thinking(self, ui):
        ui.thinking("hmm")
        ui.console.print.assert_called_once()

    def test_code(self, ui):
        ui.code("print('hi')", "python")
        ui.console.print.assert_called()

    def test_json_output(self, ui):
        ui.json_output({"key": "value"})
        ui.console.print.assert_called()

    def test_markdown(self, ui):
        ui.markdown("# Title")
        ui.console.print.assert_called()

    def test_execution_summary_basic(self, ui):
        ui.execution_summary({"execution_time": "1.2s", "tool_calls": 3})
        ui.console.print.assert_called()

    def test_execution_summary_tokens(self, ui):
        ui.execution_summary(
            {
                "input_tokens": 1000,
                "output_tokens": 500,
                "total_tokens": 1500,
                "total_cost": "$0.001",
                "execution_time": "2.0s",
            }
        )
        ui.console.print.assert_called()

    def test_execution_summary_bool_values(self, ui):
        ui.execution_summary({"streaming": True, "failed": False})
        ui.console.print.assert_called()


# ---------------------------------------------------------------------------
# RichLoggerAdapter — delegate coverage
# ---------------------------------------------------------------------------


class TestRichLoggerAdapterDelegates:
    def test_info(self, adapter, base_logger):
        with patch.object(base_logger, "info"):
            adapter.info("msg")

    def test_warning(self, adapter, base_logger):
        with patch.object(base_logger, "warning"):
            adapter.warning("msg")

    def test_error(self, adapter, base_logger):
        with patch.object(base_logger, "error"):
            adapter.error("msg")

    def test_debug_log(self, adapter, base_logger):
        with patch.object(base_logger, "debug"):
            adapter.debug_log("msg")

    def test_metrics(self, adapter, base_logger):
        with patch.object(base_logger, "info"):
            adapter.metrics("cpu=50%")

    def test_success(self, adapter):
        adapter.success("done")
        adapter.console.print.assert_called()

    def test_tool_call(self, adapter):
        adapter.tool_call({"toolUseId": "1", "name": "bash", "input": {"cmd": "ls"}})

    def test_tool_result(self, adapter):
        adapter.tool_result("bash", "output")

    def test_assistant_message(self, adapter):
        adapter.assistant_message("hello")

    def test_reasoning_block(self, adapter):
        adapter.reasoning_block("thinking")

    def test_turn_boundary(self, adapter):
        adapter.turn_boundary(1)

    def test_reasoning(self, adapter):
        adapter.reasoning("step")

    def test_thinking(self, adapter):
        adapter.thinking()

    def test_code(self, adapter):
        adapter.code("x=1")

    def test_json_output(self, adapter):
        adapter.json_output({"k": "v"})

    def test_markdown(self, adapter):
        adapter.markdown("# h")

    def test_execution_summary(self, adapter):
        adapter.execution_summary({"total_cost": "$0"})
