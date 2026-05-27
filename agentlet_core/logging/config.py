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

"""Centralized logging configuration for Synteles Agentlet Core."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def configure_logging(
    level: int = logging.INFO,
    debug_mode: bool = False,
    log_dir: Optional[Path] = None,
    json_format: bool = False,
    enable_sanitization: bool = True,
) -> None:
    """
    Configure logging for agentlet-core according to Synteles contract.

    This function MUST be called once at application startup.

    Args:
        level: Root logger level (default: INFO)
        debug_mode: Enable file logging and DEBUG level (default: False)
        log_dir: Directory for log files (default: current directory)
        json_format: Use JSON formatter for structured logging (OTel-ready)
        enable_sanitization: Enable secret sanitization filter (default: True)

    Policy:
        - Default mode: INFO level, stdout via RichConsoleHandler
        - Debug mode: DEBUG level, stdout + file via RichConsoleHandler + FileHandler
        - File naming: agentlet-core-{timestamp}.log
        - Hierarchy: synteles.* namespace
        - JSON format: Structured logs ready for OTel ingestion
        - Filters: ContextFilter (always), SecretSanitizationFilter (optional)
    """
    # Import here to avoid circular dependency
    from agentlet_core.logging.handlers import RichConsoleHandler
    from agentlet_core.logging.context import ContextFilter
    from agentlet_core.logging.filters import SecretSanitizationFilter

    # Get root synteles logger
    root_logger = logging.getLogger("synteles")
    root_logger.setLevel(logging.DEBUG)  # Allow all levels, filter at handler

    # Clear any existing handlers (idempotent configuration)
    root_logger.handlers.clear()

    # Create logging filters
    context_filter = ContextFilter()
    sanitization_filter = SecretSanitizationFilter() if enable_sanitization else None

    # Create Rich console handler (always enabled, never JSON)
    console_handler = RichConsoleHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(_create_formatter(json_format=False))
    # Add filters to console handler
    console_handler.addFilter(context_filter)
    if sanitization_filter:
        console_handler.addFilter(sanitization_filter)
    root_logger.addHandler(console_handler)

    # Add file handler in debug mode
    file_handler = None
    if debug_mode:
        file_handler = _create_file_handler(log_dir)
        file_handler.setLevel(logging.DEBUG)  # File gets all DEBUG messages
        # File can use JSON format for machine parsing
        file_handler.setFormatter(
            _create_formatter(include_thread=True, json_format=json_format)
        )
        # Add filters to file handler
        file_handler.addFilter(context_filter)
        if sanitization_filter:
            file_handler.addFilter(sanitization_filter)
        root_logger.addHandler(file_handler)

    # Prevent propagation to root logger (avoid duplicate output)
    root_logger.propagate = False

    # Configure third-party loggers (attach handlers based on debug mode)
    _configure_third_party_loggers(
        debug_mode, console_handler=console_handler, file_handler=file_handler
    )


def _create_formatter(
    include_thread: bool = False, json_format: bool = False
) -> logging.Formatter:
    """
    Create standard log formatter with required fields.

    Contract-required fields:
        - asctime: Timestamp
        - levelname: Log level
        - name: Logger name (hierarchical)
        - message: Log message
        - process: Process ID
        - thread: Thread ID (optional)

    Args:
        include_thread: Include thread ID in output
        json_format: Use JSON formatter for structured logging (OTel-ready)

    Returns:
        Formatter instance (JsonFormatter or standard Formatter)
    """
    if json_format:
        return JsonFormatter(include_thread=include_thread)

    # Standard text formatter
    if include_thread:
        fmt = (
            "%(asctime)s [%(levelname)-8s] "
            "[%(process)d:%(thread)d] "
            "%(name)s - %(message)s"
        )
    else:
        fmt = "%(asctime)s [%(levelname)-8s] [%(process)d] %(name)s - %(message)s"

    return logging.Formatter(
        fmt=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
    )


class JsonFormatter(logging.Formatter):
    """
    JSON formatter for structured logging (OTel-ready).

    Outputs each log record as a single JSON line with:
    - All contract-required fields
    - Extra context data
    - Reserved fields for future OTel integration
    """

    def __init__(self, include_thread: bool = False):
        """
        Initialize JSON formatter.

        Args:
            include_thread: Include thread ID in output
        """
        super().__init__()
        self.include_thread = include_thread

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON string (single line)
        """
        # Build base log record
        log_data: dict[str, Any] = {
            # Contract-required fields
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "process": record.process,
            # Additional useful fields
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add thread if requested
        if self.include_thread:
            log_data["thread"] = record.thread
            log_data["thread_name"] = record.threadName

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add all extra fields (context data)
        # This is where execution_id, tool_name, etc. will go
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "taskName",
            ]:
                # Only include JSON-serializable values
                try:
                    json.dumps(value)
                    extra_fields[key] = value
                except (TypeError, ValueError):
                    extra_fields[key] = str(value)

        if extra_fields:
            log_data["context"] = extra_fields

        # Reserved for future OTel integration
        # These will be populated when OTel is enabled
        if hasattr(record, "trace_id"):
            log_data["trace_id"] = record.trace_id
        if hasattr(record, "span_id"):
            log_data["span_id"] = record.span_id
        if hasattr(record, "trace_flags"):
            log_data["trace_flags"] = record.trace_flags

        return json.dumps(log_data, default=str)


def _create_file_handler(log_dir: Optional[Path]) -> logging.FileHandler:
    """
    Create file handler with contract-compliant naming.

    Filename format: agentlet-core-{timestamp}.log

    Args:
        log_dir: Directory for log files (default: current directory)

    Returns:
        FileHandler instance
    """
    if log_dir is None:
        log_dir = Path.cwd()

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = log_dir / f"agentlet-core-{timestamp}.log"

    return logging.FileHandler(log_file, encoding="utf-8")


def _configure_third_party_loggers(
    debug_mode: bool,
    console_handler: Optional[logging.Handler] = None,
    file_handler: Optional[logging.FileHandler] = None,
) -> None:
    """
    Configure logging levels for third-party SDKs.

    Implements the 3-layer logging model:
    - Layer 1: synteles.* (handled by root logger)
    - Layer 2: SDK mechanical logs (litellm, strands)
    - Layer 3: Infrastructure logs (botocore, httpx, etc.)

    Policy:
        Production (debug_mode=False):
            - synteles.*: INFO (console only)
            - litellm.*:  WARNING (no output in prod)
            - strands.*:  WARNING (no output in prod)
            - Layer 3:    WARNING (no output in prod)

        Debug (debug_mode=True):
            - synteles.*: DEBUG (console + file)
            - litellm.*:  DEBUG (console + file)
            - strands.*:  DEBUG (console + file)
            - Layer 3:    INFO (console + file)

    This separation ensures:
    - Semantic logs (Layer 1) remain readable
    - Technical logs (Layer 2/3) don't overwhelm signal in production
    - Debug mode shows full SDK context for troubleshooting
    - CloudWatch costs stay manageable in production

    Args:
        debug_mode: Whether debug mode is enabled
        console_handler: Console handler to attach to third-party loggers (debug mode only)
        file_handler: File handler to attach to third-party loggers (debug mode only)
    """
    # List of all third-party loggers we manage
    # Note: LiteLLM uses both lowercase and uppercase logger names
    layer2_loggers = [
        "litellm",
        "LiteLLM",  # LiteLLM's main logger (uppercase)
        "LiteLLM Proxy",  # LiteLLM proxy logger
        "LiteLLM Router",  # LiteLLM router logger
        "strands",
    ]
    layer3_loggers = [
        "botocore",
        "boto3",
        "urllib3",
        "httpx",
        "httpcore",
        "aiohttp",
    ]
    noisy_loggers = ["urllib3.connectionpool", "httpx._client"]
    critical_loggers = [
        "botocore.auth",
        "botocore.parsers",
        "botocore.retryhandler",
    ]

    if debug_mode:
        # Debug mode: show SDK details for troubleshooting
        # Attach both console and file handlers for full visibility
        # Layer 2: Agent SDKs (DEBUG level)
        for logger_name in layer2_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.DEBUG)
            logger.handlers.clear()  # Remove any default handlers
            logger.propagate = False  # Don't propagate to root
            # Add console handler for real-time visibility
            if console_handler:
                logger.addHandler(console_handler)
            # Add file handler for persistent logs
            if file_handler:
                logger.addHandler(file_handler)

        # Layer 3: Infrastructure SDKs (INFO level)
        for logger_name in layer3_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.INFO)
            logger.handlers.clear()
            logger.propagate = False
            # Add console handler for real-time visibility
            if console_handler:
                logger.addHandler(console_handler)
            # Add file handler for persistent logs
            if file_handler:
                logger.addHandler(file_handler)
    else:
        # Production mode: suppress SDK noise, show only warnings/errors
        # Layer 2: Agent SDKs (WARNING level)
        for logger_name in layer2_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.WARNING)
            logger.handlers.clear()  # Remove any default handlers
            logger.propagate = False  # Don't propagate to root

        # Layer 3: Infrastructure SDKs (WARNING level)
        for logger_name in layer3_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.WARNING)
            logger.handlers.clear()
            logger.propagate = False

    # CRITICAL: Never enable these in production (too verbose)
    for logger_name in critical_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
        logger.handlers.clear()
        logger.propagate = False

    # Silence very noisy loggers entirely
    for logger_name in noisy_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.ERROR)
        logger.handlers.clear()
        logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with synteles namespace.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance in synteles hierarchy

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Starting agentlet")
    """
    # Ensure name is in synteles namespace
    if not name.startswith("synteles."):
        # Handle package name conversion
        if name.startswith("agentlet_core"):
            name = name.replace("agentlet_core", "synteles.agentlet", 1)
        else:
            name = f"synteles.{name}"

    return logging.getLogger(name)


def get_effective_level(logger_name: str) -> int:
    """
    Get the effective log level for a logger considering handler-level filtering.

    In agentlet-core's architecture, filtering happens at the handler level
    rather than the logger level. This helper makes it easy to determine
    what messages will actually be displayed.

    Args:
        logger_name: Name of the logger (e.g., "synteles.agentlet")

    Returns:
        The minimum (most permissive) handler level, or NOTSET if no handlers.
        Lower numbers = more verbose (DEBUG=10, INFO=20, WARNING=30, etc.)

    Example:
        >>> level = get_effective_level("synteles.agentlet")
        >>> if level <= logging.DEBUG:
        ...     print("Debug logging is enabled")
    """
    logger = logging.getLogger(logger_name)

    # If logger has no handlers, check parent loggers
    if not logger.handlers:
        # Walk up the hierarchy to find handlers
        current = logger
        while current.parent and not current.handlers:
            current = current.parent
        logger = current

    # If still no handlers, return NOTSET
    if not logger.handlers:
        return logging.NOTSET

    # Return the minimum handler level (most permissive)
    return min(h.level for h in logger.handlers)
