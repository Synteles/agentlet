"""Tests for logging context propagation."""

import logging

import pytest

from agentlet_core.logging.config import configure_logging, get_logger
from agentlet_core.logging.context import (
    ContextFilter,
    clear_log_context,
    get_log_context,
    log_context,
)


class TestLogContext:
    """Test log_context context manager."""

    def test_log_context_basic(self):
        """Test basic context setting and retrieval."""
        # Initially empty
        assert get_log_context() == {}

        # Set context
        with log_context(execution_id="exec-123"):
            context = get_log_context()
            assert context == {"execution_id": "exec-123"}

        # Context cleared after exiting
        assert get_log_context() == {}

    def test_log_context_multiple_fields(self):
        """Test context with multiple fields."""
        with log_context(execution_id="exec-123", agentlet="assistant", user="alice"):
            context = get_log_context()
            assert context == {
                "execution_id": "exec-123",
                "agentlet": "assistant",
                "user": "alice",
            }

    def test_log_context_nested(self):
        """Test nested context managers."""
        with log_context(execution_id="exec-123"):
            assert get_log_context() == {"execution_id": "exec-123"}

            # Nested context adds more fields
            with log_context(tool="bash", tool_call_id="tool-456"):
                context = get_log_context()
                assert context == {
                    "execution_id": "exec-123",
                    "tool": "bash",
                    "tool_call_id": "tool-456",
                }

            # Back to outer context
            assert get_log_context() == {"execution_id": "exec-123"}

        # All context cleared
        assert get_log_context() == {}

    def test_log_context_override(self):
        """Test that nested context can override outer values."""
        with log_context(execution_id="exec-123", status="started"):
            assert get_log_context()["status"] == "started"

            # Override status in nested context
            with log_context(status="running"):
                context = get_log_context()
                assert context["execution_id"] == "exec-123"
                assert context["status"] == "running"

            # Outer context restored
            assert get_log_context()["status"] == "started"

    def test_clear_log_context(self):
        """Test clearing context."""
        with log_context(execution_id="exec-123"):
            assert get_log_context() != {}

            clear_log_context()
            assert get_log_context() == {}

    def test_log_context_isolation(self):
        """Test that context changes don't affect outer scope."""
        original_context = get_log_context().copy()

        with log_context(execution_id="exec-123"):
            pass

        # Context is restored after exiting
        assert get_log_context() == original_context


class TestContextFilter:
    """Test ContextFilter logging filter."""

    def test_context_filter_injects_fields(self):
        """Test that ContextFilter adds context to log records."""
        configure_logging()
        context_filter = ContextFilter()

        # Create a log record
        record = logging.LogRecord(
            name="synteles.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # No context initially
        assert not hasattr(record, "execution_id")

        # Set context and apply filter
        with log_context(execution_id="exec-123", tool="bash"):
            context_filter.filter(record)

        # Context fields should be added to record
        assert hasattr(record, "execution_id")
        assert record.execution_id == "exec-123"
        assert hasattr(record, "tool")
        assert record.tool == "bash"

    def test_context_filter_always_returns_true(self):
        """Test that ContextFilter never filters out logs."""
        context_filter = ContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        # Should always return True (allow log through)
        assert context_filter.filter(record) is True


class TestContextIntegration:
    """Test context integration with actual logging."""

    @pytest.fixture
    def capture_handler(self):
        """Create a handler that captures log records."""

        class CaptureHandler(logging.Handler):
            def __init__(self):
                super().__init__()
                self.records = []

            def emit(self, record):
                self.records.append(record)

        return CaptureHandler()

    def test_context_propagates_to_logs(self, capture_handler):
        """Test that context is automatically added to log records."""
        configure_logging()

        # Add capture handler to synteles logger
        logger = logging.getLogger("synteles")
        logger.addHandler(capture_handler)

        # Get a logger and log with context
        test_logger = get_logger("test")

        with log_context(execution_id="exec-123", agentlet="assistant"):
            test_logger.info("Test message")

        # Check that the log record has context fields
        assert len(capture_handler.records) > 0
        record = capture_handler.records[-1]
        assert hasattr(record, "execution_id")
        assert record.execution_id == "exec-123"
        assert hasattr(record, "agentlet")
        assert record.agentlet == "assistant"

    def test_nested_context_in_logs(self, capture_handler):
        """Test that nested context is reflected in logs."""
        configure_logging()
        logger = logging.getLogger("synteles")
        logger.addHandler(capture_handler)

        test_logger = get_logger("test")

        with log_context(execution_id="exec-123"):
            test_logger.info("Outer log")

            with log_context(tool="bash"):
                test_logger.info("Inner log")

        # First log should only have execution_id
        assert len(capture_handler.records) >= 2
        outer_record = capture_handler.records[-2]
        assert hasattr(outer_record, "execution_id")
        assert outer_record.execution_id == "exec-123"
        assert not hasattr(outer_record, "tool")

        # Second log should have both execution_id and tool
        inner_record = capture_handler.records[-1]
        assert hasattr(inner_record, "execution_id")
        assert inner_record.execution_id == "exec-123"
        assert hasattr(inner_record, "tool")
        assert inner_record.tool == "bash"

    def test_context_in_json_formatter(self, capture_handler):
        """Test that context appears in JSON formatted output."""
        import json

        from agentlet_core.logging.config import JsonFormatter

        configure_logging()

        # Create JSON formatter
        formatter = JsonFormatter()
        capture_handler.setFormatter(formatter)

        logger = logging.getLogger("synteles")
        logger.addHandler(capture_handler)

        test_logger = get_logger("test")

        with log_context(execution_id="exec-123", tool="bash"):
            test_logger.info("Test message")

        # Get the formatted output
        assert len(capture_handler.records) > 0
        record = capture_handler.records[-1]
        formatted = formatter.format(record)

        # Parse JSON and check context
        log_data = json.loads(formatted)
        assert "context" in log_data
        assert log_data["context"]["execution_id"] == "exec-123"
        assert log_data["context"]["tool"] == "bash"
