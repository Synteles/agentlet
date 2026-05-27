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

"""
Logging module for Synteles Agentlet Core.

Contract-compliant logging with OpenTelemetry support.
"""

# Core logging functionality
from agentlet_core.logging.config import (
    configure_logging,
    get_logger,
    get_effective_level,
    JsonFormatter,
)
from agentlet_core.logging.handlers import (
    RichConsoleHandler,
    StructuredLogger,
    RichUI,
    RichLoggerAdapter,
)

# Context propagation
from agentlet_core.logging.context import (
    log_context,
    get_log_context,
    clear_log_context,
    ContextFilter,
)

# Logging filters
from agentlet_core.logging.filters import (
    SecretSanitizationFilter,
    RateLimitFilter,
)

# OpenTelemetry integration (optional, future)
# from agentlet_core.logging.otel import (
#     configure_otel,
#     TracedLogger,
#     create_span,
#     AgentletMetrics,
# )

__all__ = [
    # Core logging configuration
    "configure_logging",
    "get_logger",
    "get_effective_level",
    "JsonFormatter",
    # Handlers and loggers
    "RichConsoleHandler",
    "StructuredLogger",
    "RichUI",
    "RichLoggerAdapter",  # Backward compatibility
    # Context propagation
    "log_context",
    "get_log_context",
    "clear_log_context",
    "ContextFilter",
    # Filters
    "SecretSanitizationFilter",
    "RateLimitFilter",
    # OTel (future)
    # "configure_otel",
    # "TracedLogger",
    # "create_span",
    # "AgentletMetrics",
]
