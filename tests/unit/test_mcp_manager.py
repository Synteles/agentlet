"""Unit tests for MCPToolsManager."""

import os
import pytest
from unittest.mock import Mock, patch
from pydantic import ValidationError

from agentlet_core.config.models import MCPToolConfig
from agentlet_core.tools.mcp_manager import MCPToolsManager


@pytest.fixture
def working_dir(tmp_path):
    """Create a temporary working directory."""
    return str(tmp_path)


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    logger = Mock()
    logger.info = Mock()
    logger.success = Mock()
    logger.error = Mock()
    logger.warning = Mock()
    logger.debug_log = Mock()
    return logger


@pytest.fixture
def stdio_config():
    """Create a stdio MCP tool configuration."""
    return MCPToolConfig(
        name="filesystem",
        server="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "${WORK_DIR}"],
        env={"ALLOWED_DIRS": "${WORK_DIR}"},
        prefix="fs",
    )


@pytest.fixture
def http_config():
    """Create an HTTP MCP tool configuration."""
    return MCPToolConfig(
        name="web_api",
        server="http",
        url="https://api.example.com/mcp",
        headers={"X-Custom": "value"},
        api_key_env="TEST_API_KEY",
        prefix="web",
    )


@pytest.fixture
def sse_config():
    """Create an SSE MCP tool configuration."""
    return MCPToolConfig(
        name="events",
        server="sse",
        url="https://events.example.com/mcp",
        prefix="evt",
    )


class TestMCPToolsManagerInit:
    """Test MCPToolsManager initialization."""

    def test_init_basic(self, stdio_config, working_dir):
        """Test basic initialization."""
        manager = MCPToolsManager([stdio_config], working_dir=working_dir)

        assert manager.tools_config == [stdio_config]
        assert manager.working_dir == working_dir
        assert manager._mcp_clients == []
        assert manager._stdio_processes == []

    def test_init_without_working_dir(self, stdio_config):
        """Test initialization without explicit working_dir uses cwd."""
        manager = MCPToolsManager([stdio_config])

        assert manager.working_dir == os.getcwd()

    def test_init_creates_logger_if_not_provided(self, stdio_config, working_dir):
        """Test that logger is created if not provided."""
        manager = MCPToolsManager([stdio_config], working_dir=working_dir)

        assert manager.logger is not None
        # Logger should be a RichLoggerAdapter
        assert hasattr(manager.logger, "logger")

    def test_init_uses_provided_logger(self, stdio_config, working_dir, mock_logger):
        """Test that provided logger is used."""
        manager = MCPToolsManager(
            [stdio_config], working_dir=working_dir, logger=mock_logger
        )

        assert manager.logger == mock_logger


class TestStdioClientCreation:
    """Test stdio MCP client creation."""

    @patch("agentlet_core.tools.mcp_manager.MCPClient")
    @patch("agentlet_core.tools.mcp_manager.StdioServerParameters")
    def test_create_stdio_client_basic(
        self, mock_params, mock_client_class, stdio_config, working_dir, mock_logger
    ):
        """Test creating basic stdio client."""
        manager = MCPToolsManager([stdio_config], working_dir, logger=mock_logger)

        manager._create_stdio_client(stdio_config)

        # Verify StdioServerParameters was created with correct args
        mock_params.assert_called_once()
        call_kwargs = mock_params.call_args[1]
        assert call_kwargs["command"] == "npx"
        # Args should have ${WORK_DIR} expanded
        assert working_dir in call_kwargs["args"]

        # Verify MCPClient was created
        mock_client_class.assert_called_once()

        # Verify process tracking
        assert len(manager._stdio_processes) == 1
        assert manager._stdio_processes[0] == ("filesystem", "npx")

    @patch("agentlet_core.tools.mcp_manager.MCPClient")
    @patch("agentlet_core.tools.mcp_manager.StdioServerParameters")
    def test_create_stdio_client_expands_work_dir_in_args(
        self, mock_params, mock_client_class, stdio_config, working_dir, mock_logger
    ):
        """Test that ${WORK_DIR} is expanded in args."""
        manager = MCPToolsManager([stdio_config], working_dir, logger=mock_logger)

        manager._create_stdio_client(stdio_config)

        # Check that args were expanded
        call_kwargs = mock_params.call_args[1]
        expanded_args = call_kwargs["args"]
        assert "${WORK_DIR}" not in " ".join(expanded_args)
        assert working_dir in " ".join(expanded_args)

    @patch("agentlet_core.tools.mcp_manager.MCPClient")
    @patch("agentlet_core.tools.mcp_manager.StdioServerParameters")
    def test_create_stdio_client_expands_work_dir_in_env(
        self, mock_params, mock_client_class, stdio_config, working_dir, mock_logger
    ):
        """Test that ${WORK_DIR} is expanded in environment variables."""
        manager = MCPToolsManager([stdio_config], working_dir, logger=mock_logger)

        manager._create_stdio_client(stdio_config)

        # Check that env vars were expanded
        call_kwargs = mock_params.call_args[1]
        env = call_kwargs["env"]
        assert env["ALLOWED_DIRS"] == working_dir
        assert "${WORK_DIR}" not in env.get("ALLOWED_DIRS", "")

    def test_create_stdio_client_requires_command(self, working_dir, mock_logger):
        """Test that stdio config validation requires command."""
        # Pydantic validates at config creation time
        with pytest.raises(ValidationError, match="command is required"):
            MCPToolConfig(name="test", server="stdio")

    @patch("agentlet_core.tools.mcp_manager.MCPClient")
    @patch("agentlet_core.tools.mcp_manager.StdioServerParameters")
    def test_create_stdio_client_with_prefix(
        self, mock_params, mock_client_class, stdio_config, working_dir, mock_logger
    ):
        """Test stdio client creation with prefix."""
        manager = MCPToolsManager([stdio_config], working_dir, logger=mock_logger)

        manager._create_stdio_client(stdio_config)

        # Verify prefix was passed to MCPClient
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["prefix"] == "fs"

    @patch("agentlet_core.tools.mcp_manager.MCPClient")
    @patch("agentlet_core.tools.mcp_manager.StdioServerParameters")
    def test_create_stdio_client_with_tool_filters(
        self, mock_params, mock_client_class, working_dir, mock_logger
    ):
        """Test stdio client creation with tool filters."""
        config = MCPToolConfig(
            name="test",
            server="stdio",
            command="npx",
            args=["-y", "test"],
            tool_filters={"allowed": ["read", "write"]},
        )
        manager = MCPToolsManager([config], working_dir, logger=mock_logger)

        manager._create_stdio_client(config)

        # Verify tool_filters was passed to MCPClient
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["tool_filters"] == {"allowed": ["read", "write"]}


class TestHttpClientCreation:
    """Test HTTP MCP client creation."""

    @patch("agentlet_core.tools.mcp_manager.MCPClient")
    def test_create_http_client_basic(
        self, mock_client_class, http_config, working_dir, mock_logger, monkeypatch
    ):
        """Test creating basic HTTP client."""
        monkeypatch.setenv("TEST_API_KEY", "test-key-123")

        manager = MCPToolsManager([http_config], working_dir, logger=mock_logger)
        manager._create_http_client(http_config)

        # Verify MCPClient was created
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["prefix"] == "web"

    def test_create_http_client_requires_url(self, working_dir, mock_logger):
        """Test that HTTP config validation requires URL."""
        # Pydantic validates at config creation time
        with pytest.raises(ValidationError, match="url is required"):
            MCPToolConfig(name="test", server="http")

    @patch("agentlet_core.tools.mcp_manager.MCPClient")
    def test_create_http_client_with_api_key_env(
        self, mock_client_class, http_config, working_dir, mock_logger, monkeypatch
    ):
        """Test HTTP client with API key from environment."""
        monkeypatch.setenv("TEST_API_KEY", "test-key-123")

        manager = MCPToolsManager([http_config], working_dir, logger=mock_logger)
        manager._create_http_client(http_config)

        # Verify the factory function was created (we can't easily test the lambda)
        mock_client_class.assert_called_once()

    def test_create_http_client_missing_api_key(
        self, http_config, working_dir, mock_logger, monkeypatch
    ):
        """Test HTTP client fails when API key not in environment."""
        monkeypatch.delenv("TEST_API_KEY", raising=False)

        manager = MCPToolsManager([http_config], working_dir, logger=mock_logger)

        with pytest.raises(
            RuntimeError, match="API key not found in environment: TEST_API_KEY"
        ):
            manager._create_http_client(http_config)

    @patch("agentlet_core.tools.mcp_manager.MCPClient")
    def test_create_http_client_without_api_key_env(
        self, mock_client_class, working_dir, mock_logger
    ):
        """Test HTTP client without api_key_env."""
        config = MCPToolConfig(
            name="test",
            server="http",
            url="https://api.example.com",
            headers={"X-Custom": "value"},
        )
        manager = MCPToolsManager([config], working_dir, logger=mock_logger)

        manager._create_http_client(config)

        # Should succeed without api_key_env
        mock_client_class.assert_called_once()


class TestSseClientCreation:
    """Test SSE MCP client creation."""

    @patch("agentlet_core.tools.mcp_manager.MCPClient")
    def test_create_sse_client_basic(
        self, mock_client_class, sse_config, working_dir, mock_logger
    ):
        """Test creating basic SSE client."""
        manager = MCPToolsManager([sse_config], working_dir, logger=mock_logger)
        manager._create_sse_client(sse_config)

        # Verify MCPClient was created
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["prefix"] == "evt"

    def test_create_sse_client_requires_url(self, working_dir, mock_logger):
        """Test that SSE config validation requires URL."""
        # Pydantic validates at config creation time
        with pytest.raises(ValidationError, match="url is required"):
            MCPToolConfig(name="test", server="sse")

    @patch("agentlet_core.tools.mcp_manager.MCPClient")
    def test_create_sse_client_warns_about_api_key(
        self, mock_client_class, working_dir, mock_logger
    ):
        """Test that SSE client warns when api_key_env is set."""
        config = MCPToolConfig(
            name="test",
            server="sse",
            url="https://events.example.com",
            api_key_env="TEST_KEY",
        )
        manager = MCPToolsManager([config], working_dir, logger=mock_logger)

        manager._create_sse_client(config)

        # Should log a warning about api_key_env not being supported
        mock_logger.warning.assert_called_once()
        assert "api_key_env" in str(mock_logger.warning.call_args)


class TestInitialize:
    """Test MCPToolsManager initialize method."""

    @patch("agentlet_core.tools.mcp_manager.MCPClient")
    @patch("agentlet_core.tools.mcp_manager.StdioServerParameters")
    def test_initialize_single_stdio_tool(
        self, mock_params, mock_client_class, stdio_config, working_dir, mock_logger
    ):
        """Test initializing single stdio tool."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        manager = MCPToolsManager([stdio_config], working_dir, logger=mock_logger)
        clients = manager.initialize()

        assert len(clients) == 1
        assert clients[0] == mock_client
        assert manager._mcp_clients == [mock_client]
        mock_logger.info.assert_called()
        mock_logger.success.assert_called()

    @patch("agentlet_core.tools.mcp_manager.MCPClient")
    def test_initialize_multiple_tools(
        self,
        mock_client_class,
        stdio_config,
        http_config,
        working_dir,
        mock_logger,
        monkeypatch,
    ):
        """Test initializing multiple tools."""
        monkeypatch.setenv("TEST_API_KEY", "test-key")
        mock_client1 = Mock()
        mock_client2 = Mock()
        mock_client_class.side_effect = [mock_client1, mock_client2]

        manager = MCPToolsManager(
            [stdio_config, http_config], working_dir, logger=mock_logger
        )

        with patch("agentlet_core.tools.mcp_manager.StdioServerParameters"):
            clients = manager.initialize()

        assert len(clients) == 2
        assert clients == [mock_client1, mock_client2]

    def test_initialize_unsupported_server_type(self, working_dir, mock_logger):
        """Test that unsupported server type raises validation error."""
        # Pydantic validates server type at config creation time
        with pytest.raises(ValidationError, match="Input should be"):
            MCPToolConfig(name="test", server="invalid")  # type: ignore

    @patch("agentlet_core.tools.mcp_manager.MCPClient")
    @patch("agentlet_core.tools.mcp_manager.StdioServerParameters")
    def test_initialize_logs_errors(
        self, mock_params, mock_client_class, stdio_config, working_dir, mock_logger
    ):
        """Test that initialization errors are logged."""
        mock_client_class.side_effect = Exception("Test error")

        manager = MCPToolsManager([stdio_config], working_dir, logger=mock_logger)

        with pytest.raises(RuntimeError, match="Failed to initialize"):
            manager.initialize()

        mock_logger.error.assert_called()


class TestContextManagement:
    """Test MCP context management (enter/exit)."""

    @pytest.fixture
    def mock_clients(self):
        """Create mock MCP clients."""
        client1 = Mock()
        client1.__enter__ = Mock(return_value=client1)
        client1.__exit__ = Mock(return_value=None)

        client2 = Mock()
        client2.__enter__ = Mock(return_value=client2)
        client2.__exit__ = Mock(return_value=None)

        return [client1, client2]

    def test_enter_contexts_success(self, working_dir, mock_logger, mock_clients):
        """Test successful context entry."""
        manager = MCPToolsManager([], working_dir, logger=mock_logger)
        manager._mcp_clients = mock_clients

        manager.enter_contexts()

        # Verify all clients had __enter__ called
        for client in mock_clients:
            client.__enter__.assert_called_once()

        mock_logger.success.assert_called_once()

    def test_enter_contexts_with_failure_triggers_rollback(
        self, working_dir, mock_logger
    ):
        """Test that context entry failure triggers rollback."""
        client1 = Mock()
        client1.__enter__ = Mock(return_value=client1)
        client1.__exit__ = Mock(return_value=None)

        client2 = Mock()
        client2.__enter__ = Mock(side_effect=Exception("Connection failed"))
        client2.__exit__ = Mock(return_value=None)

        manager = MCPToolsManager([], working_dir, logger=mock_logger)
        manager._mcp_clients = [client1, client2]

        with pytest.raises(RuntimeError, match="Failed to enter MCP client context"):
            manager.enter_contexts()

        # First client should have been entered and then exited (rollback)
        client1.__enter__.assert_called_once()
        client1.__exit__.assert_called_once()

        # Second client should have attempted enter but no exit
        client2.__enter__.assert_called_once()
        client2.__exit__.assert_not_called()

    def test_exit_contexts_success(self, working_dir, mock_logger, mock_clients):
        """Test successful context exit."""
        manager = MCPToolsManager([], working_dir, logger=mock_logger)
        manager._mcp_clients = mock_clients

        manager.exit_contexts()

        # Verify all clients had __exit__ called
        for client in mock_clients:
            client.__exit__.assert_called_once_with(None, None, None)

        mock_logger.success.assert_called_once()

    def test_exit_contexts_continues_on_error(self, working_dir, mock_logger):
        """Test that context exit continues even if some fail."""
        client1 = Mock()
        client1.__exit__ = Mock(return_value=None)

        client2 = Mock()
        client2.__exit__ = Mock(side_effect=Exception("Cleanup failed"))

        client3 = Mock()
        client3.__exit__ = Mock(return_value=None)

        manager = MCPToolsManager([], working_dir, logger=mock_logger)
        manager._mcp_clients = [client1, client2, client3]

        manager.exit_contexts()

        # All clients should have had exit called
        client1.__exit__.assert_called_once()
        client2.__exit__.assert_called_once()
        client3.__exit__.assert_called_once()

        # Should log warnings for the failure
        assert mock_logger.warning.call_count >= 1


class TestToolRetrieval:
    """Test tool retrieval from MCP clients."""

    def test_get_clients_returns_initialized_clients(self, working_dir, mock_logger):
        """Test that get_clients returns initialized clients."""
        mock_client1 = Mock()
        mock_client2 = Mock()

        manager = MCPToolsManager([], working_dir, logger=mock_logger)
        manager._mcp_clients = [mock_client1, mock_client2]

        clients = manager.get_clients()

        assert clients == [mock_client1, mock_client2]

    def test_get_tools_sync_success(self, working_dir, mock_logger):
        """Test successful tool retrieval."""
        mock_tool1 = Mock(name="tool1")
        mock_tool2 = Mock(name="tool2")
        mock_tool3 = Mock(name="tool3")

        client1 = Mock()
        client1.list_tools_sync = Mock(return_value=[mock_tool1, mock_tool2])

        client2 = Mock()
        client2.list_tools_sync = Mock(return_value=[mock_tool3])

        manager = MCPToolsManager([], working_dir, logger=mock_logger)
        manager._mcp_clients = [client1, client2]

        tools = manager.get_tools_sync()

        assert len(tools) == 3
        assert tools == [mock_tool1, mock_tool2, mock_tool3]

        client1.list_tools_sync.assert_called_once()
        client2.list_tools_sync.assert_called_once()

    def test_get_tools_sync_with_error(self, working_dir, mock_logger):
        """Test tool retrieval with error."""
        client1 = Mock()
        client1.list_tools_sync = Mock(side_effect=Exception("Failed to list tools"))

        manager = MCPToolsManager([], working_dir, logger=mock_logger)
        manager._mcp_clients = [client1]

        with pytest.raises(Exception, match="Failed to list tools"):
            manager.get_tools_sync()

        mock_logger.error.assert_called()


class TestCleanup:
    """Test cleanup methods."""

    def test_cleanup_sync_calls_exit_contexts(self, working_dir, mock_logger):
        """Test that cleanup_sync calls exit_contexts."""
        mock_client = Mock()
        mock_client.__exit__ = Mock(return_value=None)

        manager = MCPToolsManager([], working_dir, logger=mock_logger)
        manager._mcp_clients = [mock_client]

        manager.cleanup_sync()

        mock_client.__exit__.assert_called_once()
        assert mock_logger.info.call_count >= 1
        mock_logger.success.assert_called()

    def test_cleanup_sync_with_no_clients(self, working_dir, mock_logger):
        """Test cleanup with no initialized clients."""
        manager = MCPToolsManager([], working_dir, logger=mock_logger)

        # Should not raise error
        manager.cleanup_sync()

    def test_cleanup_sync_idempotent(self, working_dir, mock_logger):
        """Test that cleanup_sync can be called multiple times."""
        mock_client = Mock()
        mock_client.__exit__ = Mock(return_value=None)

        manager = MCPToolsManager([], working_dir, logger=mock_logger)
        manager._mcp_clients = [mock_client]

        manager.cleanup_sync()
        manager.cleanup_sync()

        # Should not raise error on second call
        assert mock_client.__exit__.call_count == 2


class TestListTools:
    """Test list_tools method."""

    def test_list_tools_returns_empty_list(self, working_dir, mock_logger):
        """Test that list_tools returns empty list (method is a placeholder)."""
        manager = MCPToolsManager([], working_dir, logger=mock_logger)

        tool_names = manager.list_tools()

        assert tool_names == []
