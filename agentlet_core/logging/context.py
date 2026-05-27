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

"""Context propagation for structured logging.

Provides correlation context management for automatic propagation of
contextual information (like execution_id, tool names, etc.) to all logs
within a scope without manual repetition.

This module uses Python's contextvars for thread-safe and async-safe
context storage, making it suitable for concurrent agentlet executions.
"""

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

# Thread-safe, async-safe context storage
# Each execution context gets its own isolated context dictionary
_log_context: ContextVar[dict[str, Any]] = ContextVar("log_context", default={})


@contextmanager
def log_context(**context: Any) -> Iterator[None]:
    """
    Add context to all logs within this scope.

    This context manager automatically injects the provided key-value pairs
    into all log records created within its scope. Context is propagated
    to nested scopes and can be extended with additional fields.

    Context is thread-safe and async-safe using Python's contextvars module.

    Args:
        **context: Key-value pairs to add to log context (e.g., execution_id="exec-123")

    Yields:
        None

    Example:
        >>> from agentlet_core.logging import get_logger, log_context
        >>> logger = get_logger(__name__)
        >>>
        >>> # All logs in this scope get execution_id automatically
        >>> with log_context(execution_id="exec-123", agentlet="assistant"):
        ...     logger.info("Starting execution")
        ...     # → Logs with execution_id=exec-123, agentlet=assistant
        ...
        ...     # Nested context adds more fields
        ...     with log_context(tool="bash", tool_call_id="tool-456"):
        ...         logger.info("Calling tool")
        ...         # → Logs with execution_id, agentlet, tool, tool_call_id
        ...
        ...     logger.info("Execution completed")
        ...     # → Logs with execution_id=exec-123, agentlet=assistant

    Thread Safety:
        This function is safe to use in multi-threaded and async environments.
        Each thread/task maintains its own isolated context.
    """
    # Get current context (or empty dict if not set) and create a copy
    current = _log_context.get().copy()

    # Merge new context with existing context (new values override)
    current.update(context)

    # Set the new context and get a token for cleanup
    token = _log_context.set(current)

    try:
        yield
    finally:
        # Restore previous context when exiting the scope
        _log_context.reset(token)


def get_log_context() -> dict[str, Any]:
    """
    Get the current log context.

    Returns the context dictionary that will be automatically added to
    all log records. Useful for debugging or inspecting current context.

    Returns:
        Dictionary of current context key-value pairs. Returns empty dict
        if no context is set.

    Example:
        >>> with log_context(execution_id="exec-123"):
        ...     context = get_log_context()
        ...     print(context)
        {'execution_id': 'exec-123'}
    """
    return _log_context.get()


def clear_log_context() -> None:
    """
    Clear the current log context.

    Removes all context variables. This is rarely needed in normal operation
    as context managers handle cleanup automatically, but can be useful for
    testing or recovery from unexpected states.

    Example:
        >>> with log_context(execution_id="exec-123"):
        ...     clear_log_context()
        ...     context = get_log_context()
        ...     print(context)
        {}
    """
    _log_context.set({})


class ContextFilter(logging.Filter):
    """
    Logging filter that automatically injects context variables into log records.

    This filter reads the current context from the ContextVar and adds all
    context fields as attributes to the log record. These attributes are then
    available to formatters (especially JsonFormatter) for structured logging.

    The filter is registered globally during configure_logging() and doesn't
    need to be used directly.

    Example:
        When log_context(execution_id="exec-123") is active, every log record
        will have record.execution_id = "exec-123" automatically added.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Inject context variables into log record.

        Args:
            record: Log record to enhance with context

        Returns:
            Always True (never filters out logs)
        """
        # Get current context from ContextVar
        context = get_log_context()

        # Add all context fields as attributes on the log record
        # These become available to formatters (e.g., JsonFormatter will
        # include them in the "context" field)
        for key, value in context.items():
            setattr(record, key, value)

        return True  # Always allow the log through
