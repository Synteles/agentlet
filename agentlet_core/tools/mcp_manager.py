# Copyright 2026 Emin Askerov
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""MCP tools manager for Agentlet Core using Strands agents SDK."""

import os
from typing import Any, Optional, cast

from mcp import StdioServerParameters, stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient
from strands.tools.mcp.mcp_client import ToolFilters

from agentlet_core.config.models import MCPToolConfig
from agentlet_core.logging.config import get_logger
from agentlet_core.logging.handlers import RichLoggerAdapter


class MCPToolsManager:
    """
    Manages MCP tools lifecycle and integration using Strands agents SDK.

    Supports stdio, HTTP (streamable), and SSE server types.
    Uses Strands' MCPClient for proper integration with Agent framework.
    """

    def __init__(
        self,
        tools_config: list[MCPToolConfig],
        working_dir: Optional[str] = None,
        logger: Optional[RichLoggerAdapter] = None,
    ):
        """
        Initialize MCP tools manager.

        Args:
            tools_config: List of MCP tool configurations
            working_dir: Working directory for tools (used for ${WORK_DIR} expansion)
            logger: Logger instance
        """
        self.tools_config = tools_config
        self.working_dir = working_dir or os.getcwd()
        # Create logger if not provided
        if logger is None:
            base_logger = get_logger(__name__)
            self.logger = RichLoggerAdapter(base_logger)
        else:
            self.logger = logger
        self._mcp_clients: list[MCPClient] = []
        # Track stdio process info for cleanup (name, command)
        self._stdio_processes: list[tuple[str, str]] = []

    def initialize(self) -> list[MCPClient]:
        """
        Initialize all configured MCP tools and return MCPClient instances.

        Returns:
            List of MCPClient instances ready to be passed to Agent

        Raises:
            RuntimeError: If tool initialization fails
        """
        self.logger.info(f"Initializing {len(self.tools_config)} MCP tool server(s)...")

        for tool_config in self.tools_config:
            try:
                if tool_config.server == "stdio":
                    client = self._create_stdio_client(tool_config)
                elif tool_config.server == "http":
                    client = self._create_http_client(tool_config)
                elif tool_config.server == "sse":
                    client = self._create_sse_client(tool_config)
                else:
                    raise ValueError(f"Unsupported server type: {tool_config.server}")

                self._mcp_clients.append(client)
                self.logger.success(
                    f"MCP server '{tool_config.name}' ({tool_config.server}) initialized"
                )

            except Exception as e:
                self.logger.error(
                    f"Failed to initialize MCP server '{tool_config.name}': {e}"
                )
                raise RuntimeError(
                    f"Failed to initialize MCP server '{tool_config.name}'"
                ) from e

        return self._mcp_clients

    def _create_stdio_client(self, config: MCPToolConfig) -> MCPClient:
        """
        Create stdio-based MCP client.

        Args:
            config: Tool configuration

        Returns:
            MCPClient instance configured for stdio transport
        """
        if not config.command:
            raise ValueError(f"command is required for stdio server '{config.name}'")

        # Prepare environment variables
        env = os.environ.copy()
        env.update(config.env)

        # Expand ${WORK_DIR} in environment variables
        for key, value in env.items():
            env[key] = value.replace("${WORK_DIR}", self.working_dir)

        # Expand ${WORK_DIR} in command arguments
        expanded_args = [
            arg.replace("${WORK_DIR}", self.working_dir) for arg in config.args
        ]

        # Create stdio server parameters
        server_params = StdioServerParameters(
            command=config.command,
            args=expanded_args,
            env=env,
        )

        # Create MCPClient with stdio transport
        mcp_client = MCPClient(
            lambda: stdio_client(server_params),
            prefix=config.prefix,
            tool_filters=cast(ToolFilters, config.tool_filters)
            if config.tool_filters
            else None,
        )

        # Track process info for cleanup (name and command pattern)
        self._stdio_processes.append((config.name, config.command))

        return mcp_client

    def _create_http_client(self, config: MCPToolConfig) -> MCPClient:
        """
        Create HTTP (streamable) MCP client.

        Args:
            config: Tool configuration

        Returns:
            MCPClient instance configured for HTTP transport
        """
        if not config.url:
            raise ValueError(f"url is required for http server '{config.name}'")

        # Type assertion after validation
        url: str = config.url

        # Prepare headers
        headers = config.headers.copy()

        # Add API key from environment if specified
        if config.api_key_env:
            api_key = os.getenv(config.api_key_env)
            if not api_key:
                raise RuntimeError(
                    f"API key not found in environment: {config.api_key_env}"
                )
            # Add Authorization header if not already present
            if "Authorization" not in headers:
                headers["Authorization"] = f"Bearer {api_key}"

        # Create MCPClient with streamable HTTP transport
        mcp_client = MCPClient(
            lambda: streamablehttp_client(
                url=url,
                headers=headers if headers else None,
            ),
            prefix=config.prefix,
            tool_filters=cast(ToolFilters, config.tool_filters)
            if config.tool_filters
            else None,
        )

        return mcp_client

    def _create_sse_client(self, config: MCPToolConfig) -> MCPClient:
        """
        Create SSE (Server-Sent Events) MCP client.

        Args:
            config: Tool configuration

        Returns:
            MCPClient instance configured for SSE transport
        """
        if not config.url:
            raise ValueError(f"url is required for sse server '{config.name}'")

        # Type assertion after validation
        url: str = config.url

        # Note: SSE client in MCP SDK currently doesn't support custom headers
        # API key should be included in the URL or handled by the server
        if config.api_key_env:
            self.logger.warning(
                f"SSE server '{config.name}': api_key_env is set but SSE client "
                "doesn't support custom headers. Include auth in URL or server-side."
            )

        # Create MCPClient with SSE transport
        mcp_client = MCPClient(
            lambda: sse_client(url),
            prefix=config.prefix,
            tool_filters=cast(ToolFilters, config.tool_filters)
            if config.tool_filters
            else None,
        )

        return mcp_client

    def get_clients(self) -> list[MCPClient]:
        """
        Get all initialized MCPClient instances.

        Returns:
            List of MCPClient instances
        """
        return self._mcp_clients

    def list_tools(self) -> list[str]:
        """
        List all tool names from all MCP servers.

        Note: This requires the clients to be used within a context manager.

        Returns:
            List of tool names
        """
        tool_names: list[str] = []
        for client in self._mcp_clients:
            # This would require the client to be in an active context
            # For now, just return the configured server names
            pass
        return tool_names

    def get_tools_sync(self) -> list[Any]:
        """
        Get all tools from all MCP clients synchronously.

        This method collects tools from all initialized MCP clients by calling
        list_tools_sync() on each. Must be called within an active context
        (after enter_contexts()).

        Returns:
            List of tool objects from all MCP servers

        Raises:
            RuntimeError: If called outside of an active context
        """
        all_tools: list[Any] = []
        for client in self._mcp_clients:
            try:
                tools = client.list_tools_sync()
                all_tools.extend(tools)
                self.logger.info(f"Loaded {len(tools)} tool(s) from MCP server")
            except Exception as e:
                self.logger.error(f"Failed to list tools from MCP client: {e}")
                raise

        return all_tools

    def enter_contexts(self) -> None:
        """
        Enter all MCP client contexts.

        This must be called before using MCP tools. Each MCPClient's __enter__
        is called to establish connections.

        Raises:
            RuntimeError: If context entry fails
        """
        self.logger.info(
            f"Entering context for {len(self._mcp_clients)} MCP client(s)..."
        )

        for i, client in enumerate(self._mcp_clients):
            try:
                client.__enter__()
                self.logger.debug_log(f"MCP client {i + 1} context entered")
            except Exception as e:
                self.logger.error(
                    f"Failed to enter context for MCP client {i + 1}: {e}"
                )
                # Cleanup any already-entered contexts (best-effort rollback)
                for j in range(i):
                    try:
                        # Type ignore: __exit__ signature accepts Optional but type checker is strict
                        self._mcp_clients[j].__exit__(None, None, None)  # type: ignore
                    except Exception:
                        # Ignore cleanup errors during rollback to preserve original error
                        pass  # nosec B110
                raise RuntimeError(f"Failed to enter MCP client context {i + 1}") from e

        self.logger.success("All MCP client contexts entered successfully")

    def exit_contexts(self) -> None:
        """
        Exit all MCP client contexts.

        This should be called during cleanup to properly close MCP connections.
        Attempts to exit all contexts even if some fail.
        """
        self.logger.info(
            f"Exiting context for {len(self._mcp_clients)} MCP client(s)..."
        )

        errors = []
        for i, client in enumerate(self._mcp_clients):
            try:
                # Type ignore: __exit__ signature accepts Optional but type checker is strict
                client.__exit__(None, None, None)  # type: ignore
                self.logger.debug_log(f"MCP client {i + 1} context exited")
            except Exception as e:
                error_msg = f"Failed to exit context for MCP client {i + 1}: {e}"
                self.logger.warning(error_msg)
                errors.append(error_msg)

        if errors:
            self.logger.warning(
                f"Encountered {len(errors)} error(s) during context exit"
            )
        else:
            self.logger.success("All MCP client contexts exited successfully")

    def cleanup_sync(self) -> None:
        """
        Synchronous cleanup of all MCP resources.

        This method exits all MCP client contexts and cleans up any resources.
        Safe to call multiple times.
        """
        if not self._mcp_clients:
            return

        self.logger.info("Cleaning up MCP resources...")
        self.exit_contexts()
        self.logger.success("MCP cleanup completed")
