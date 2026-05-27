"""Tests for logging configuration and 3-layer model compliance."""

import logging
import tempfile
from pathlib import Path


from agentlet_core.logging.config import (
    configure_logging,
    get_logger,
    JsonFormatter,
)
from agentlet_core.logging.handlers import RichConsoleHandler


class TestConfigureLogging:
    """Test logging configuration."""

    def test_configure_logging_default_mode(self):
        """Test default logging configuration."""
        configure_logging()

        logger = logging.getLogger("synteles")
        assert logger.level == logging.DEBUG  # Root allows all, filter at handler
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], RichConsoleHandler)

    def test_configure_logging_debug_mode(self):
        """Test debug mode with file logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            configure_logging(debug_mode=True, log_dir=log_dir)

            logger = logging.getLogger("synteles")
            assert len(logger.handlers) == 2  # Console + File

            # Check file handler exists
            file_handlers = [
                h for h in logger.handlers if isinstance(h, logging.FileHandler)
            ]
            assert len(file_handlers) == 1

            # Check filename format
            log_file = Path(file_handlers[0].baseFilename)
            assert log_file.name.startswith("agentlet-core-")
            assert log_file.name.endswith(".log")
            assert log_file.parent == log_dir

    def test_configure_logging_idempotent(self):
        """Test that multiple calls to configure_logging don't duplicate handlers."""
        configure_logging()
        configure_logging()

        logger = logging.getLogger("synteles")
        # Should only have 1 handler after multiple calls
        assert len(logger.handlers) == 1

    def test_configure_logging_propagate_disabled(self):
        """Test that propagation to root logger is disabled."""
        configure_logging()

        logger = logging.getLogger("synteles")
        assert logger.propagate is False


class TestGetLogger:
    """Test get_logger namespace conversion."""

    def test_get_logger_agentlet_core_namespace(self):
        """Test agentlet_core namespace conversion."""
        logger = get_logger("agentlet_core.agents.base")
        assert logger.name == "synteles.agentlet.agents.base"

    def test_get_logger_synteles_namespace_passthrough(self):
        """Test synteles namespace passthrough."""
        logger = get_logger("synteles.custom")
        assert logger.name == "synteles.custom"

    def test_get_logger_other_namespaces(self):
        """Test other namespaces get synteles prefix."""
        logger = get_logger("other.module")
        assert logger.name == "synteles.other.module"

    def test_logger_hierarchy(self):
        """Test logger hierarchy and inheritance."""
        configure_logging(level=logging.INFO)

        parent = logging.getLogger("synteles.agentlet")
        child = logging.getLogger("synteles.agentlet.executor")

        # Child inherits from parent
        assert child.parent == parent


class TestThirdPartyLoggerConfiguration:
    """Test 3-layer logging model implementation."""

    def test_production_mode_verbosity(self):
        """Test production mode sets correct verbosity for SDKs."""
        configure_logging(debug_mode=False)

        # Layer 1: Synteles (INFO via handler, DEBUG via root)
        synteles = logging.getLogger("synteles")
        assert synteles.level == logging.DEBUG

        # Layer 2: Agent SDKs (WARNING in prod)
        litellm = logging.getLogger("litellm")
        strands = logging.getLogger("strands")
        assert litellm.level == logging.WARNING
        assert strands.level == logging.WARNING

        # Layer 3: Infrastructure SDKs (WARNING in prod)
        botocore = logging.getLogger("botocore")
        urllib3 = logging.getLogger("urllib3")
        httpx = logging.getLogger("httpx")
        assert botocore.level == logging.WARNING
        assert urllib3.level == logging.WARNING
        assert httpx.level == logging.WARNING

    def test_debug_mode_verbosity(self):
        """Test debug mode enables SDK verbosity."""
        configure_logging(debug_mode=True)

        # Layer 2: Agent SDKs (DEBUG in debug mode)
        litellm = logging.getLogger("litellm")
        strands = logging.getLogger("strands")
        assert litellm.level == logging.DEBUG
        assert strands.level == logging.DEBUG

        # Layer 3: Infrastructure SDKs (INFO in debug mode)
        botocore = logging.getLogger("botocore")
        urllib3 = logging.getLogger("urllib3")
        assert botocore.level == logging.INFO
        assert urllib3.level == logging.INFO

    def test_noisy_loggers_silenced(self):
        """Test very noisy loggers are silenced entirely."""
        configure_logging()

        # These should be ERROR only
        connection_pool = logging.getLogger("urllib3.connectionpool")
        httpx_client = logging.getLogger("httpx._client")
        assert connection_pool.level == logging.ERROR
        assert httpx_client.level == logging.ERROR


class TestJsonFormatter:
    """Test JSON formatter for structured logging."""

    def test_json_formatter_basic(self):
        """Test basic JSON formatting."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="synteles.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        # Should be valid JSON
        import json

        data = json.loads(output)

        # Check required fields
        assert "timestamp" in data
        assert "level" in data
        assert data["level"] == "INFO"
        assert "logger" in data
        assert data["logger"] == "synteles.test"
        assert "message" in data
        assert data["message"] == "Test message"
        assert "process" in data
        assert "module" in data
        assert "function" in data
        assert "line" in data

    def test_json_formatter_with_extra_context(self):
        """Test JSON formatter includes extra context."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="synteles.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add extra context
        record.execution_id = "exec-123"
        record.tool_name = "bash"

        output = formatter.format(record)
        import json

        data = json.loads(output)

        # Extra fields should be in context
        assert "context" in data
        assert data["context"]["execution_id"] == "exec-123"
        assert data["context"]["tool_name"] == "bash"

    def test_json_formatter_otel_fields_reserved(self):
        """Test JSON formatter includes OTel fields when present."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="synteles.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add OTel trace context
        record.trace_id = "abc123"
        record.span_id = "def456"
        record.trace_flags = 1

        output = formatter.format(record)
        import json

        data = json.loads(output)

        # OTel fields should be at root level
        assert data["trace_id"] == "abc123"
        assert data["span_id"] == "def456"
        assert data["trace_flags"] == 1

    def test_json_formatter_with_thread(self):
        """Test JSON formatter includes thread info when requested."""
        formatter = JsonFormatter(include_thread=True)
        record = logging.LogRecord(
            name="synteles.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        import json

        data = json.loads(output)

        assert "thread" in data
        assert "thread_name" in data


class TestNamespaceIsolation:
    """Test that SDK loggers remain isolated (DON'T wrap or rename)."""

    def test_sdk_loggers_not_renamed(self):
        """Test SDK loggers keep their original names."""
        configure_logging()

        # Layer 2 & 3 loggers should NOT be renamed to synteles.*
        litellm = logging.getLogger("litellm")
        strands = logging.getLogger("strands")
        botocore = logging.getLogger("botocore")

        assert litellm.name == "litellm"
        assert strands.name == "strands"
        assert botocore.name == "botocore"

    def test_synteles_namespace_exclusive(self):
        """Test synteles namespace is used exclusively for Layer 1."""
        configure_logging()

        # All synteles.* loggers should be our application code
        app_logger = get_logger("agentlet_core.agents.base")
        assert app_logger.name.startswith("synteles.")

        # SDK loggers should NOT start with synteles
        litellm = logging.getLogger("litellm")
        assert not litellm.name.startswith("synteles.")
