"""Unit tests for inject_trace_context."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from agentlet_core.telemetry.context import inject_trace_context


class TestInjectTraceContext:
    def test_otel_not_installed_returns_empty(self):
        with patch.dict(
            sys.modules, {"opentelemetry": None, "opentelemetry.trace": None}
        ):
            result = inject_trace_context()
        assert result == {}

    def test_no_active_span_returns_empty(self):
        mock_trace = MagicMock()
        mock_trace.get_current_span.return_value = None
        with patch.dict(
            sys.modules,
            {"opentelemetry": MagicMock(), "opentelemetry.trace": mock_trace},
        ):
            result = inject_trace_context()
        assert result == {}

    def test_invalid_span_context_returns_empty(self):
        mock_ctx = MagicMock()
        mock_ctx.is_valid = False
        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_ctx

        mock_trace = MagicMock()
        mock_trace.get_current_span.return_value = mock_span
        with patch.dict(
            sys.modules,
            {"opentelemetry": MagicMock(), "opentelemetry.trace": mock_trace},
        ):
            result = inject_trace_context()
        assert result == {}

    def test_span_with_no_context_returns_empty(self):
        mock_span = MagicMock()
        mock_span.get_span_context.return_value = None

        mock_trace = MagicMock()
        mock_trace.get_current_span.return_value = mock_span
        with patch.dict(
            sys.modules,
            {"opentelemetry": MagicMock(), "opentelemetry.trace": mock_trace},
        ):
            result = inject_trace_context()
        assert result == {}

    def test_valid_span_returns_trace_context(self):
        otel_trace = pytest.importorskip("opentelemetry.trace")

        trace_id_int = 0x4BF92F3577B34DA6A3CE929D0E0E4736
        span_id_int = 0x00F067AA0BA902B7
        trace_flags_val = 1

        mock_ctx = MagicMock()
        mock_ctx.is_valid = True
        mock_ctx.trace_id = trace_id_int
        mock_ctx.span_id = span_id_int
        mock_ctx.trace_flags = trace_flags_val

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_ctx

        with patch.object(otel_trace, "get_current_span", return_value=mock_span):
            result = inject_trace_context()

        assert "trace_id" in result
        assert "span_id" in result
        assert "trace_flags" in result
        assert result["trace_id"] == format(trace_id_int, "032x")
        assert result["span_id"] == format(span_id_int, "016x")
        assert result["trace_flags"] == trace_flags_val

    def test_exception_in_span_handling_returns_empty(self):
        mock_span = MagicMock()
        mock_span.get_span_context.side_effect = RuntimeError("broken span")

        mock_trace = MagicMock()
        mock_trace.get_current_span.return_value = mock_span

        with patch.dict(
            sys.modules,
            {"opentelemetry": MagicMock(), "opentelemetry.trace": mock_trace},
        ):
            result = inject_trace_context()
        assert result == {}
