"""Tests for DefaultToolsManager."""

import os
import pytest
from unittest.mock import Mock, patch

from agentlet_core.tools.tools_manager import DefaultToolsManager


class TestDefaultToolsManager:
    """Test DefaultToolsManager functionality."""

    def test_init_sets_bypass_tool_consent(self):
        """Test that BYPASS_TOOL_CONSENT is set to true by default."""
        # Clear the env var if it exists
        if "BYPASS_TOOL_CONSENT" in os.environ:
            del os.environ["BYPASS_TOOL_CONSENT"]

        DefaultToolsManager()
        assert os.environ["BYPASS_TOOL_CONSENT"] == "true"

    def test_init_preserves_existing_bypass_tool_consent(self):
        """Test that existing BYPASS_TOOL_CONSENT value is preserved."""
        os.environ["BYPASS_TOOL_CONSENT"] = "false"
        DefaultToolsManager()
        assert os.environ["BYPASS_TOOL_CONSENT"] == "false"

    def test_init_with_tool_names(self):
        """Test initialization with specific tool names."""
        manager = DefaultToolsManager("calculator", "file_read")
        assert manager._requested_tools == {"calculator", "file_read"}

    def test_init_without_tool_names(self):
        """Test initialization without tool names results in empty set."""
        manager = DefaultToolsManager()
        assert manager._requested_tools == set()

    @patch("agentlet_core.tools.tools_manager.importlib.import_module")
    def test_get_tool_loads_module(self, mock_import):
        """Test that get_tool loads module via importlib."""
        mock_module = Mock()
        mock_import.return_value = mock_module

        manager = DefaultToolsManager()
        result = manager.get_tool("calculator")

        mock_import.assert_called_once_with("strands_tools.calculator")
        assert result == mock_module
        assert manager._tools["calculator"] == mock_module

    @patch("agentlet_core.tools.tools_manager.importlib.import_module")
    def test_get_tool_caches_module(self, mock_import):
        """Test that get_tool caches loaded modules."""
        mock_module = Mock()
        mock_import.return_value = mock_module

        manager = DefaultToolsManager()
        result1 = manager.get_tool("calculator")
        result2 = manager.get_tool("calculator")

        mock_import.assert_called_once()
        assert result1 == result2 == mock_module

    @patch("agentlet_core.tools.tools_manager.importlib.import_module")
    def test_get_tool_import_error(self, mock_import):
        """Test that get_tool raises ImportError when module cannot be imported."""
        mock_import.side_effect = ImportError("Module not found")

        manager = DefaultToolsManager()
        with pytest.raises(
            ImportError,
            match="Could not import tool .* from strands_tools",
        ):
            manager.get_tool("nonexistent")

    def test_is_tool_loaded(self):
        """Test is_tool_loaded method."""
        manager = DefaultToolsManager()
        assert not manager.is_tool_loaded("calculator")

        manager._tools["calculator"] = Mock()
        assert manager.is_tool_loaded("calculator")

    @patch("agentlet_core.tools.tools_manager.importlib.import_module")
    def test_get_tools_loads_all_requested(self, mock_import):
        """Test that get_tools loads all requested tools."""
        mock_calc = Mock()
        mock_file = Mock()
        mock_import.side_effect = [mock_calc, mock_file]

        manager = DefaultToolsManager("calculator", "file_read")
        tools = manager.get_tools()

        assert len(tools) == 2
        assert mock_calc in tools
        assert mock_file in tools

    def test_get_tools_empty_when_no_tools_requested(self):
        """Test that get_tools returns empty list when no tools requested."""
        manager = DefaultToolsManager()
        tools = manager.get_tools()
        assert tools == []
