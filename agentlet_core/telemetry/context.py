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

"""Trace context injection for logging correlation."""

from typing import Any


def inject_trace_context() -> dict[str, Any]:
    """
    Extract current OTEL trace context for logging correlation.

    This function gets the current OTEL span and extracts trace_id, span_id, and trace_flags
    for use with log_context() to enable automatic correlation of logs with traces.

    Returns:
        Dictionary with trace context fields (trace_id, span_id, trace_flags).
        Returns empty dict if OTEL is not available or no active span.

    Example:
        >>> from agentlet_core.logging import log_context
        >>> from agentlet_core.telemetry.context import inject_trace_context
        >>>
        >>> # Correlate logs with traces automatically
        >>> with log_context(**inject_trace_context(), execution_id=exec_id):
        >>>     logger.info("This log will include trace_id and span_id")
    """
    try:
        from opentelemetry import trace
    except ImportError:
        # OTEL not installed, return empty dict
        return {}

    try:
        # Get current span
        span = trace.get_current_span()
        if not span:
            return {}

        # Get span context
        span_context = span.get_span_context()
        if not span_context or not span_context.is_valid:
            return {}

        # Extract trace context fields
        trace_id = format(span_context.trace_id, "032x")  # 32-char hex string
        span_id = format(span_context.span_id, "016x")  # 16-char hex string
        trace_flags = span_context.trace_flags

        return {
            "trace_id": trace_id,
            "span_id": span_id,
            "trace_flags": trace_flags,
        }

    except Exception:
        # If anything goes wrong, return empty dict (fail gracefully)
        return {}
