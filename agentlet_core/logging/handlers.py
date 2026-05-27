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

"""Custom logging handlers for Rich console output."""

import json
import logging
from importlib.metadata import version
from typing import Any

from rich.console import Console, Group, RenderableType
from rich.json import JSON
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text


class RichConsoleHandler(logging.Handler):
    """
    Custom logging handler that outputs to Rich console.

    Preserves the beautiful UX of AgentletLogger while using
    standard Python logging infrastructure.
    """

    # Icon mapping for log levels
    LEVEL_ICONS = {
        logging.DEBUG: "🐛",
        logging.INFO: "ℹ",
        logging.WARNING: "⚠",
        logging.ERROR: "✗",
        logging.CRITICAL: "🔥",
    }

    LEVEL_STYLES = {
        logging.DEBUG: "dim",
        logging.INFO: "bold bright_blue",
        logging.WARNING: "bold bright_yellow",
        logging.ERROR: "bold bright_red",
        logging.CRITICAL: "bold red on white",
    }

    def __init__(self):
        """Initialize Rich console handler."""
        super().__init__()
        self.console = Console()

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record to Rich console.

        Falls back to stderr if Rich console fails to ensure logs are never lost.

        Args:
            record: Log record to emit
        """
        try:
            # Check for special log types
            log_type = getattr(record, "log_type", None)

            # Skip file-only messages (debug mode text tables, etc.)
            if log_type == "file_only":
                return

            # Special handling for metrics
            if log_type == "metric":
                msg = record.getMessage()
                self.console.print(f"📊 {msg}")
                return

            # Get level-specific styling
            icon = self.LEVEL_ICONS.get(record.levelno, "•")
            style = self.LEVEL_STYLES.get(record.levelno, "white")

            # Special handling for custom Rich renderables
            if hasattr(record, "rich_renderable"):
                # Custom Rich renderables (for tool calls, panels, etc.)
                self.console.print(record.rich_renderable)
            else:
                # Standard text output with message only (no timestamp/logger name)
                # The formatter adds those, but we only want the message for UX
                msg = record.getMessage()
                self.console.print(f"[{style}]{icon}[/{style}]  {msg}")

        except Exception as e:
            # Fallback to stderr to ensure log is not lost
            try:
                import sys

                # Format a plain text message for stderr
                msg = self.format(record)
                sys.stderr.write(f"[LOGGING ERROR] Rich console failed: {e}\n")
                sys.stderr.write(f"{msg}\n")
                sys.stderr.flush()
            except Exception:
                # Last resort: use base handler's error handling
                self.handleError(record)


class StructuredLogger:
    """
    Clean interface for structured logging with context support.

    Wraps a standard Python logger and provides convenience methods
    for logging with structured context data via the 'extra' parameter.

    This class focuses solely on standard logging operations without
    Rich UX features, providing a clean separation of concerns.

    Usage:
        >>> from agentlet_core.logging import get_logger
        >>> base_logger = get_logger(__name__)
        >>> logger = StructuredLogger(base_logger)
        >>> logger.info("Task started", task_id="123", user="alice")
        >>> logger.error("Task failed", task_id="123", error_code="TIMEOUT")
    """

    def __init__(self, logger: logging.Logger):
        """
        Initialize structured logger.

        Args:
            logger: Standard Python logger to wrap
        """
        self.logger = logger
        self.name = logger.name

    def debug(self, msg: str, **context) -> None:
        """
        Log debug message with optional context.

        Args:
            msg: Message to log
            **context: Additional context fields (added to 'extra')
        """
        self.logger.debug(msg, extra=context if context else None)

    def info(self, msg: str, **context) -> None:
        """
        Log info message with optional context.

        Args:
            msg: Message to log
            **context: Additional context fields (added to 'extra')
        """
        self.logger.info(msg, extra=context if context else None)

    def warning(self, msg: str, **context) -> None:
        """
        Log warning message with optional context.

        Args:
            msg: Message to log
            **context: Additional context fields (added to 'extra')
        """
        self.logger.warning(msg, extra=context if context else None)

    def error(self, msg: str, **context) -> None:
        """
        Log error message with optional context.

        Args:
            msg: Message to log
            **context: Additional context fields (added to 'extra')
        """
        self.logger.error(msg, extra=context if context else None)

    def critical(self, msg: str, **context) -> None:
        """
        Log critical message with optional context.

        Args:
            msg: Message to log
            **context: Additional context fields (added to 'extra')
        """
        self.logger.critical(msg, extra=context if context else None)

    def log(self, level: int, msg: str, **context) -> None:
        """
        Log message at specified level with optional context.

        Args:
            level: Log level (e.g., logging.INFO)
            msg: Message to log
            **context: Additional context fields (added to 'extra')
        """
        self.logger.log(level, msg, extra=context if context else None)


class RichUI:
    """
    Rich console UI features for beautiful terminal output.

    Handles visual presentation using Rich library (splash screens, panels,
    syntax highlighting, etc.) while delegating logging to a StructuredLogger.

    This class is purely concerned with UX/presentation and uses composition
    to integrate with the logging system.

    Usage:
        >>> from agentlet_core.logging import get_logger
        >>> base_logger = get_logger(__name__)
        >>> structured_logger = StructuredLogger(base_logger)
        >>> ui = RichUI(structured_logger)
        >>> ui.success("Build completed!")
        >>> ui.tool_call(tool_data)
    """

    # Constants
    PANEL_WIDTH = 80
    BULLET = "  • "

    def __init__(self, logger: StructuredLogger):
        """
        Initialize Rich UI.

        Args:
            logger: StructuredLogger for logging operations
        """
        self.logger = logger
        self.console = Console()

    def _create_title(
        self,
        icon: str,
        text: str,
        icon_style: str = "bold",
        text_style: str = "bold bright_cyan",
    ) -> Text:
        """Create styled title for panels."""
        title = Text()
        title.append(f"{icon} ", style=icon_style)
        title.append(text, style=text_style)
        return title

    def _get_value(self, data: Any, key: str, default: Any = "unknown") -> Any:
        """Extract value from dict or object attribute."""
        if isinstance(data, dict):
            return data.get(key, default)
        return getattr(data, key, default)

    def _format_value_as_bullet(
        self, key: str, value: Any, key_style: str = "bright_green"
    ) -> list[Text]:
        """Format a key-value pair as bullet point(s)."""
        lines = []

        if isinstance(value, (dict, list)):
            # Complex value: show key, then indented JSON
            lines.append(
                Text.assemble(
                    (self.BULLET, "bright_blue"),
                    (f"{key}: ", key_style),
                )
            )
            value_str = json.dumps(value, indent=2)
            for line in value_str.split("\n"):
                lines.append(Text(f"    {line}", style="white"))
        else:
            # Simple value: key and value on same line
            value_str = str(value)

            # Special styling for is_error field
            if key == "is_error":
                value_style = "bright_red" if value else "dim white"
            else:
                value_style = "bright_white"

            lines.append(
                Text.assemble(
                    (self.BULLET, "bright_blue"),
                    (f"{key}: ", key_style),
                    (value_str, value_style),
                )
            )

        return lines

    def _extract_tool_info(self, tool_data: Any) -> tuple[str, str, Any]:
        """Extract tool ID, name, and input from tool data."""
        # Try multiple keys for ID (toolUseId or id)
        tool_id = self._get_value(tool_data, "toolUseId")
        if tool_id == "unknown":
            tool_id = self._get_value(tool_data, "id")

        tool_name = self._get_value(tool_data, "name")
        tool_input = self._get_value(tool_data, "input", {})

        return str(tool_id), str(tool_name), tool_input

    def success(self, message: str) -> None:
        """Display success message with special formatting."""
        self.console.print(
            f"[bold bright_green]✓[/bold bright_green]  [bright_white]{message}[/bright_white]"
        )
        # Also log to standard logger for file output
        self.logger.info(f"SUCCESS: {message}")

    def splash(self) -> None:
        """Display splash screen with ASCII art logo."""
        splash_art = """[deep_sky_blue4]
    ███████╗██╗   ██╗███╗   ██╗████████╗███████╗██╗     ███████╗███████╗
    ██╔════╝╚██╗ ██╔╝████╗  ██║╚══██╔══╝██╔════╝██║     ██╔════╝██╔════╝
    ███████╗ ╚████╔╝ ██╔██╗ ██║   ██║   █████╗  ██║     █████╗  ███████╗
    ╚════██║  ╚██╔╝  ██║╚██╗██║   ██║   ██╔══╝  ██║     ██╔══╝  ╚════██║
    ███████║   ██║   ██║ ╚████║   ██║   ███████╗███████╗███████╗███████║
    ╚══════╝   ╚═╝   ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚══════╝╚══════╝╚══════╝

     █████╗  ██████╗ ███████╗███╗   ██╗████████╗██╗     ███████╗████████╗
    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██║     ██╔════╝╚══██╔══╝
    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║     █████╗     ██║
    ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║     ██╔══╝     ██║
    ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ███████╗███████╗   ██║
    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚══════╝   ╚═╝
[/deep_sky_blue4]"""
        self.console.print(splash_art)
        self.console.print(
            f"    [dim]agentlet-core v{version('agentlet-core')}[/dim]\n"
        )

    def tool_call(self, tool_data: Any) -> None:
        """Display tool invocation with Rich panel."""
        # Extract tool information
        tool_id, tool_name, tool_input = self._extract_tool_info(tool_data)

        # Parse input if it's a JSON string
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except (json.JSONDecodeError, TypeError):
                pass

        # Only show complete tool calls (not partial streaming updates)
        if isinstance(tool_input, dict) and tool_input:
            # Create title
            title = self._create_title(
                "⚡", "Tool Call: ", "bold yellow", "bold bright_cyan"
            )
            title.append(tool_name, style="bold bright_magenta")

            # Build content
            content_lines = []

            # Add tool ID (full ID, no truncation)
            content_lines.append(
                Text.assemble(("ID: ", "dim cyan"), (str(tool_id), "dim white"))
            )
            content_lines.append(Text())  # Empty line

            # Add parameters
            if tool_input:
                content_lines.append(Text("Parameters:", style="bold bright_yellow"))
                for key, value in tool_input.items():
                    content_lines.extend(self._format_value_as_bullet(key, value))
            else:
                content_lines.append(Text("No parameters", style="dim italic"))

            # Create and print panel
            content = Text("\n").join(content_lines)
            panel = Panel(
                content,
                title=title,
                border_style="bright_blue",
                padding=(1, 2),
                width=self.PANEL_WIDTH,
            )
            self.console.print(panel)

            # Also log structured data
            self.logger.info(
                f"Tool call: {tool_name}",
                tool_id=tool_id,
                tool_name=tool_name,
                tool_input=tool_input,
            )

    def tool_result(
        self, tool_name: str, result: Any, success: bool | None = None
    ) -> None:
        """Display tool execution result."""
        # Auto-detect success from result if not explicitly provided
        if success is None:
            is_error = self._get_value(result, "is_error", False)
            success = not is_error

        # Determine styling based on success
        if success:
            icon = "✅"
            text = "Tool Result: "
            icon_style = "bold green"
            text_style = "bold bright_green"
            border_color = "green"
        else:
            icon = "❌"
            text = "Tool Error: "
            icon_style = "bold red"
            text_style = "bold bright_red"
            border_color = "red"

        # Create title
        title = self._create_title(icon, text, icon_style, text_style)
        title.append(tool_name, style="bold bright_magenta")

        # Build content
        content_parts: list[RenderableType] = []

        if isinstance(result, dict):
            # Display dict fields as bullet points
            for key, value in result.items():
                content_parts.extend(self._format_value_as_bullet(key, value))
        elif isinstance(result, str):
            content_parts.append(Text(result, style="white"))
        else:
            content_parts.append(Text(str(result), style="white"))

        # Create and print panel
        final_content = Group(*content_parts)
        panel = Panel(
            final_content,
            title=title,
            border_style=border_color,
            padding=(1, 2),
            width=self.PANEL_WIDTH,
        )
        self.console.print(panel)

        # Log to standard logger
        level = logging.INFO if success else logging.ERROR
        self.logger.log(
            level,
            f"Tool result: {tool_name} - {'success' if success else 'error'}",
            tool_name=tool_name,
            result=result,
            success=success,
        )

    def assistant_message(self, text: str) -> None:
        """Display complete assistant message."""
        if not text or not text.strip():
            return

        title = self._create_title("🤖", "Assistant", "bold", "bold bright_cyan")

        panel = Panel(
            Text(text.strip(), style="bright_white"),
            title=title,
            border_style="bright_cyan",
            padding=(1, 2),
            width=self.PANEL_WIDTH,
        )
        self.console.print(panel)

        # Log to standard logger
        self.logger.info("Assistant message", assistant_text=text)

    def reasoning_block(self, text: str) -> None:
        """Display extended thinking/reasoning block."""
        if not text or not text.strip():
            return

        title = self._create_title(
            "💭", "Reasoning", "bold magenta", "bold bright_magenta"
        )

        panel = Panel(
            Text(text.strip(), style="italic bright_white"),
            title=title,
            border_style="magenta",
            padding=(1, 2),
            width=self.PANEL_WIDTH,
        )
        self.console.print(panel)

        # Log to standard logger
        self.logger.info("Reasoning block", reasoning_text=text)

    def turn_boundary(self, turn_number: int) -> None:
        """Display turn boundary indicator in multi-turn conversations."""
        # Simple, clean turn indicator
        self.console.print()  # Blank line before
        self.console.print(
            f"[dim bright_blue]{'─' * 10}[/dim bright_blue] "
            f"[bold bright_yellow]🔄 Turn {turn_number}[/bold bright_yellow] "
            f"[dim bright_blue]{'─' * 10}[/dim bright_blue]"
        )
        self.console.print()  # Blank line after

        # Log to standard logger
        self.logger.info(f"Turn {turn_number} started", turn=turn_number)

    def reasoning(self, text: str) -> None:
        """Display reasoning step with enhanced formatting."""
        title = self._create_title("🧠", "Reasoning")

        panel = Panel(
            text,
            title=title,
            border_style="cyan",
            padding=(1, 2),
            expand=False,
        )
        self.console.print(panel)

        # Also log to standard logger
        self.logger.info("Reasoning", reasoning=text)

    def thinking(self, message: str = "Thinking...") -> None:
        """Display a thinking message with style."""
        self.console.print(f"[bold bright_magenta]💭 {message}[/bold bright_magenta]")

    def code(self, code: str, language: str = "python") -> None:
        """Display code with syntax highlighting in a panel."""
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)

        title = self._create_title("📝", "Code", "bold", "bold bright_green")
        if language:
            title.append(f" ({language})", style="dim bright_green")

        panel = Panel(
            syntax,
            title=title,
            border_style="green",
            padding=(1, 2),
            expand=False,
        )
        self.console.print(panel)

    def json_output(self, data: dict) -> None:
        """Display JSON output with enhanced formatting."""
        title = self._create_title("📋", "JSON Output", "bold", "bold bright_yellow")

        panel = Panel(
            JSON.from_data(data),
            title=title,
            border_style="yellow",
            padding=(1, 2),
            expand=False,
        )
        self.console.print(panel)

    def markdown(self, text: str) -> None:
        """Display markdown-formatted text."""
        md = Markdown(text)
        self.console.print(md)

    def execution_summary(self, summary: dict) -> None:
        """Display execution summary with colorful formatting."""
        title = self._create_title("📊", "Execution Summary")

        table = Table(
            title=title,
            show_header=True,
            header_style="bold bright_magenta",
            border_style="bright_blue",
            padding=(0, 1),
        )
        table.add_column("Metric", style="bright_cyan", no_wrap=True)
        table.add_column("Value", style="bright_white")

        # Build rows for both Rich table and text log
        rows = []
        for key, value in summary.items():
            # Format the key
            formatted_key = key.replace("_", " ").title()

            # Format the value with appropriate styling
            if isinstance(value, bool):
                value_str = "✓" if value else "✗"
                value_style = "green" if value else "red"
            elif key in ("input_tokens", "output_tokens", "total_tokens"):
                # Format token counts with commas for readability
                value_str = f"{value:,}"
                value_style = "bright_green"
            elif key == "total_cost":
                # Cost already formatted as string (e.g., "$0.000123")
                value_str = str(value)
                value_style = "bright_yellow"
            elif key == "execution_time":
                # Execution time already formatted as string (e.g., "1.23s")
                value_str = str(value)
                value_style = "bright_green"
            elif isinstance(value, (int, float)):
                value_str = str(value)
                value_style = "bright_green"
            else:
                value_str = str(value)
                value_style = "bright_white"

            # Add to Rich table with styling
            table.add_row(formatted_key, Text(value_str, style=value_style))

            # Store for text log
            rows.append((formatted_key, value_str))

        # Display Rich table to console
        self.console.print(table)

        # Check if debug mode is enabled (file handlers present)
        # Walk up the logger hierarchy to find handlers
        base_logger = self.logger.logger
        has_file_handler = False
        current = base_logger

        while current:
            has_file_handler = any(
                isinstance(h, logging.FileHandler) for h in current.handlers
            )
            if has_file_handler or not current.parent:
                break
            current = current.parent

        # Only log text table to file in debug mode
        if has_file_handler:
            # Build text table for log file
            # Calculate column widths
            max_key_len = max(len(row[0]) for row in rows) if rows else 10
            max_val_len = max(len(row[1]) for row in rows) if rows else 10

            # Create text table
            separator = (
                "+" + "-" * (max_key_len + 2) + "+" + "-" * (max_val_len + 2) + "+"
            )
            header = f"| {'Metric':<{max_key_len}} | {'Value':<{max_val_len}} |"

            text_table_lines = [
                "",
                "Execution Summary:",
                separator,
                header,
                separator,
            ]

            for key, value in rows:
                text_table_lines.append(
                    f"| {key:<{max_key_len}} | {value:<{max_val_len}} |"
                )

            text_table_lines.append(separator)
            text_table = "\n".join(text_table_lines)

            # Log with structured data and formatted table (file only)
            self.logger.logger.info(
                text_table, extra={"summary": summary, "log_type": "file_only"}
            )


class RichLoggerAdapter:
    """
    Backward-compatible adapter combining StructuredLogger and RichUI.

    This class maintains the existing API while using composition internally
    to separate standard logging (StructuredLogger) from Rich UX features (RichUI).

    New code should prefer using StructuredLogger and RichUI directly for
    clearer separation of concerns, but this adapter remains for backward
    compatibility with existing code.

    Usage:
        >>> logger = logging.getLogger(__name__)
        >>> rich_logger = RichLoggerAdapter(logger)
        >>> rich_logger.info("Task started", task_id="123")  # Structured logging
        >>> rich_logger.success("Operation completed")  # Rich UX
        >>> rich_logger.tool_call(tool_data)  # Rich UX
    """

    # Constants (for backward compatibility)
    PANEL_WIDTH = 80
    BULLET = "  • "

    def __init__(self, logger: logging.Logger):
        """
        Initialize adapter using composition.

        Args:
            logger: Standard Python logger to wrap
        """
        # Create composed components
        self._structured_logger = StructuredLogger(logger)
        self._rich_ui = RichUI(self._structured_logger)

        # Keep direct references for backward compatibility
        self.logger = logger
        self.console = self._rich_ui.console

        # Track debug mode by checking console handler level
        # (our architecture filters at handler level, not logger level)
        self.debug_enabled = any(
            h.level <= logging.DEBUG
            for h in logging.getLogger("synteles").handlers
            if isinstance(h, RichConsoleHandler)
        )

    @property
    def debug(self) -> bool:  # type: ignore[override]
        """Check if debug mode is enabled (backward compatibility property)."""
        return self.debug_enabled

    # Helper methods (delegate to RichUI for backward compatibility)
    def _create_title(self, *args, **kwargs) -> Text:
        """Create styled title for panels (delegates to RichUI)."""
        return self._rich_ui._create_title(*args, **kwargs)

    def _get_value(self, *args, **kwargs) -> Any:
        """Extract value from dict or object attribute (delegates to RichUI)."""
        return self._rich_ui._get_value(*args, **kwargs)

    def _format_value_as_bullet(self, *args, **kwargs) -> list[Text]:
        """Format a key-value pair as bullet point(s) (delegates to RichUI)."""
        return self._rich_ui._format_value_as_bullet(*args, **kwargs)

    def _extract_tool_info(self, *args, **kwargs) -> tuple[str, str, Any]:
        """Extract tool ID, name, and input from tool data (delegates to RichUI)."""
        return self._rich_ui._extract_tool_info(*args, **kwargs)

    # Standard logging methods (delegate to StructuredLogger)
    # Note: debug() method not included due to conflict with debug property
    # Use debug_log() or logger.debug() instead

    def info(self, msg: str, **context) -> None:
        """Log info message with optional context."""
        self._structured_logger.info(msg, **context)

    def warning(self, msg: str, **context) -> None:
        """Log warning message with optional context."""
        self._structured_logger.warning(msg, **context)

    def error(self, msg: str, **context) -> None:
        """Log error message with optional context."""
        self._structured_logger.error(msg, **context)

    def debug_log(self, message: str) -> None:
        """
        Log debug message (only shown when debug mode is enabled).

        Uses standard logging system at DEBUG level, ensuring logs appear
        in both console (when debug mode is active) and log files.
        """
        self._structured_logger.debug(message)

    def metrics(self, message: str, **extra) -> None:
        """
        Log operational metrics (token usage, cost, etc).

        Always visible in console at INFO level, and logged to files
        for audit trail. Uses standard logging system with 'metric' marker.

        Args:
            message: Metric message to log
            **extra: Additional context fields (token counts, costs, etc.)
        """
        # Add metric marker to extra context for filtering/analysis
        extra["log_type"] = "metric"
        self._structured_logger.logger.info(message, extra=extra)

    # Rich UX methods (delegate to RichUI)
    def success(self, message: str) -> None:
        """Display success message with special formatting (delegates to RichUI)."""
        self._rich_ui.success(message)

    def splash(self) -> None:
        """Display splash screen with ASCII art logo (delegates to RichUI)."""
        self._rich_ui.splash()

    def tool_call(self, tool_data: Any) -> None:
        """Display tool invocation with Rich panel (delegates to RichUI)."""
        self._rich_ui.tool_call(tool_data)

    def tool_result(
        self, tool_name: str, result: Any, success: bool | None = None
    ) -> None:
        """Display tool execution result (delegates to RichUI)."""
        self._rich_ui.tool_result(tool_name, result, success)

    def assistant_message(self, text: str) -> None:
        """Display complete assistant message (delegates to RichUI)."""
        self._rich_ui.assistant_message(text)

    def reasoning_block(self, text: str) -> None:
        """Display extended thinking/reasoning block (delegates to RichUI)."""
        self._rich_ui.reasoning_block(text)

    def turn_boundary(self, turn_number: int) -> None:
        """Display turn boundary indicator (delegates to RichUI)."""
        self._rich_ui.turn_boundary(turn_number)

    def reasoning(self, text: str) -> None:
        """Display reasoning step with enhanced formatting (delegates to RichUI)."""
        self._rich_ui.reasoning(text)

    def thinking(self, message: str = "Thinking...") -> None:
        """Display a thinking message with style (delegates to RichUI)."""
        self._rich_ui.thinking(message)

    def code(self, code: str, language: str = "python") -> None:
        """Display code with syntax highlighting (delegates to RichUI)."""
        self._rich_ui.code(code, language)

    def json_output(self, data: dict) -> None:
        """Display JSON output with enhanced formatting (delegates to RichUI)."""
        self._rich_ui.json_output(data)

    def markdown(self, text: str) -> None:
        """Display markdown-formatted text (delegates to RichUI)."""
        self._rich_ui.markdown(text)

    def execution_summary(self, summary: dict) -> None:
        """Display execution summary with colorful formatting (delegates to RichUI)."""
        self._rich_ui.execution_summary(summary)
