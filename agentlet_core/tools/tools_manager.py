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

"""Default tools manager for Agentlet Core."""

import importlib
import os
from typing import Any, Optional

from agentlet_core.logging.config import get_logger
from agentlet_core.logging.handlers import RichLoggerAdapter


class DefaultToolsManager:
    """
    Manages default tools with lazy loading from strands_tools.
    """

    def __init__(self, *tool_names: str, logger: Optional[RichLoggerAdapter] = None):
        """
        Initialize tools manager.

        Args:
            *tool_names: Names of tools to manage
            logger: Logger instance
        """
        if "BYPASS_TOOL_CONSENT" not in os.environ:
            os.environ["BYPASS_TOOL_CONSENT"] = "true"

        # Create logger if not provided
        if logger is None:
            base_logger = get_logger(__name__)
            self.logger = RichLoggerAdapter(base_logger)
        else:
            self.logger = logger
        self._tools: dict[str, Any] = {}
        self._requested_tools = set(tool_names)

    def get_tool(self, tool_name: str) -> Any:
        """
        Get tool by name, loading it lazily if not already loaded.

        Loads tools from strands_tools package only.

        Args:
            tool_name: Name of the tool to load

        Returns:
            The loaded tool module

        Raises:
            ImportError: If tool cannot be imported from strands_tools
        """
        if tool_name not in self._tools:
            self.logger.info(f"Loading tool: {tool_name}")

            try:
                module = importlib.import_module(f"strands_tools.{tool_name}")
                self._tools[tool_name] = module
                self.logger.success(
                    f"Tool '{tool_name}' loaded successfully from strands_tools"
                )
            except ImportError as error:
                self.logger.error(
                    f"Failed to import tool '{tool_name}' from strands_tools: {error}"
                )
                raise ImportError(
                    f"Could not import tool '{tool_name}' from strands_tools"
                ) from error

        return self._tools[tool_name]

    def is_tool_loaded(self, tool_name: str) -> bool:
        """Check if a tool is already loaded."""
        return tool_name in self._tools

    def get_tools(self) -> list[Any]:
        """Get all requested tools, loading them if needed."""
        return [self.get_tool(name) for name in self._requested_tools]
