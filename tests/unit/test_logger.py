"""Tests for RichLoggerAdapter utility."""

import logging

import pytest

from agentlet_core.logging.config import get_logger
from agentlet_core.logging.handlers import RichLoggerAdapter


@pytest.fixture
def rich_logger():
    """Create a RichLoggerAdapter for testing."""
    base_logger = get_logger("test")
    return RichLoggerAdapter(base_logger)


def test_get_value_from_dict(rich_logger):
    """Test extracting values from dictionary."""
    data = {"key1": "value1", "key2": 42, "is_error": True}

    assert rich_logger._get_value(data, "key1") == "value1"
    assert rich_logger._get_value(data, "key2") == 42
    assert rich_logger._get_value(data, "is_error") is True
    assert rich_logger._get_value(data, "missing", "default") == "default"


def test_get_value_from_object(rich_logger):
    """Test extracting values from object attributes."""

    class TestObject:
        def __init__(self):
            self.key1 = "value1"
            self.key2 = 42
            self.is_error = False

    obj = TestObject()

    assert rich_logger._get_value(obj, "key1") == "value1"
    assert rich_logger._get_value(obj, "key2") == 42
    assert rich_logger._get_value(obj, "is_error") is False
    assert rich_logger._get_value(obj, "missing", "default") == "default"


def test_extract_tool_info_from_dict(rich_logger):
    """Test extracting tool info from dictionary."""
    tool_data = {
        "toolUseId": "tool_123",
        "name": "calculator",
        "input": {"expression": "2+2"},
    }

    tool_id, tool_name, tool_input = rich_logger._extract_tool_info(tool_data)

    assert tool_id == "tool_123"
    assert tool_name == "calculator"
    assert tool_input == {"expression": "2+2"}


def test_extract_tool_info_with_id_fallback(rich_logger):
    """Test extracting tool info with id fallback (no toolUseId)."""
    tool_data = {"id": "tool_456", "name": "bash", "input": {"command": "ls"}}

    tool_id, tool_name, tool_input = rich_logger._extract_tool_info(tool_data)

    assert tool_id == "tool_456"
    assert tool_name == "bash"
    assert tool_input == {"command": "ls"}


def test_format_value_as_bullet_simple(rich_logger):
    """Test formatting simple value as bullet point."""
    lines = rich_logger._format_value_as_bullet("status", "success")

    assert len(lines) == 1
    assert "status:" in str(lines[0])
    assert "success" in str(lines[0])


def test_format_value_as_bullet_complex(rich_logger):
    """Test formatting complex value (dict/list) as bullet points."""
    lines = rich_logger._format_value_as_bullet("config", {"key": "value"})

    # Should have multiple lines: one for key, then indented JSON
    assert len(lines) > 1
    assert "config:" in str(lines[0])


def test_format_value_as_bullet_is_error(rich_logger):
    """Test special formatting for is_error field."""
    # is_error=True should have bright_red style
    lines_error = rich_logger._format_value_as_bullet("is_error", True)
    assert len(lines_error) == 1

    # is_error=False should have dim white style
    lines_ok = rich_logger._format_value_as_bullet("is_error", False)
    assert len(lines_ok) == 1


def test_rich_logger_adapter_delegates_to_logger(rich_logger):
    """Test that RichLoggerAdapter delegates to underlying logger."""
    # Check that it has a logger attribute
    assert hasattr(rich_logger, "logger")
    assert isinstance(rich_logger.logger, logging.Logger)

    # Check that logger name is in synteles namespace
    assert rich_logger.logger.name.startswith("synteles.")


def test_rich_logger_adapter_debug_mode():
    """Test debug mode detection based on console handler level."""
    from agentlet_core.logging.config import configure_logging

    # Debug mode: configure with DEBUG level
    configure_logging(level=logging.DEBUG, debug_mode=True)
    debug_logger = get_logger("test")
    rich_debug = RichLoggerAdapter(debug_logger)
    assert rich_debug.debug is True

    # Production mode: configure with INFO level
    configure_logging(level=logging.INFO, debug_mode=False)
    info_logger = get_logger("test2")
    rich_info = RichLoggerAdapter(info_logger)
    assert rich_info.debug is False
