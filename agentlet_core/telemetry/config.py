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

"""OpenTelemetry configuration and setup."""

import logging
import os
from typing import Optional

from agentlet_core.config.models import OTELConfig

logger = logging.getLogger(__name__)

# Global telemetry instance (singleton pattern)
_telemetry_instance: Optional[object] = None


def configure_telemetry(otel_config: OTELConfig) -> Optional[object]:
    """
    Configure OpenTelemetry telemetry for agentlet-core.

    This function should be called ONCE at application startup, after configure_logging().
    It creates a global StrandsTelemetry instance that will be used throughout the application.

    Args:
        otel_config: OTEL configuration from AgentletConfig

    Returns:
        StrandsTelemetry instance if OTEL is enabled and available, None otherwise

    Example:
        >>> from agentlet_core.config.models import OTELConfig
        >>> otel_config = OTELConfig(enabled=True, console_exporter=True)
        >>> telemetry = configure_telemetry(otel_config)
    """
    global _telemetry_instance

    # If OTEL is disabled, return None
    if not otel_config.enabled:
        logger.debug("OTEL is disabled, skipping telemetry configuration")
        return None

    # Try to import StrandsTelemetry (optional dependency)
    try:
        from strands.telemetry import StrandsTelemetry
    except ImportError:
        logger.warning(
            "OTEL enabled but strands-agents[otel] not installed. "
            "Install with: pip install 'strands-agents[otel]' or uv sync --group otel"
        )
        return None

    # Set environment variables from config before initializing telemetry
    # These will be picked up by OpenTelemetry SDK

    # Set base endpoint (used as fallback)
    if otel_config.otlp_endpoint:
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = otel_config.otlp_endpoint
        logger.debug(f"Set OTEL_EXPORTER_OTLP_ENDPOINT={otel_config.otlp_endpoint}")

    # Set signal-specific endpoints (override base endpoint)
    if otel_config.otlp_traces_endpoint:
        os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = (
            otel_config.otlp_traces_endpoint
        )
        logger.debug(
            f"Set OTEL_EXPORTER_OTLP_TRACES_ENDPOINT={otel_config.otlp_traces_endpoint}"
        )

    if otel_config.otlp_metrics_endpoint:
        os.environ["OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"] = (
            otel_config.otlp_metrics_endpoint
        )
        logger.debug(
            f"Set OTEL_EXPORTER_OTLP_METRICS_ENDPOINT={otel_config.otlp_metrics_endpoint}"
        )

    if otel_config.otlp_headers:
        # Format: key1=value1,key2=value2
        headers_str = ",".join(
            f"{key}={value}" for key, value in otel_config.otlp_headers.items()
        )
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = headers_str
        logger.debug(f"Set OTEL_EXPORTER_OTLP_HEADERS={headers_str}")

    if otel_config.sampler:
        os.environ["OTEL_TRACES_SAMPLER"] = otel_config.sampler
        logger.debug(f"Set OTEL_TRACES_SAMPLER={otel_config.sampler}")

    if otel_config.sampler_arg is not None:
        os.environ["OTEL_TRACES_SAMPLER_ARG"] = str(otel_config.sampler_arg)
        logger.debug(f"Set OTEL_TRACES_SAMPLER_ARG={otel_config.sampler_arg}")

    try:
        # Create StrandsTelemetry instance
        telemetry = StrandsTelemetry()

        # Setup OTLP exporter without explicit endpoint parameter
        # This allows OpenTelemetry SDK to read from environment variables
        # and automatically append signal-specific paths (/v1/traces, /v1/metrics)
        telemetry.setup_otlp_exporter()

        # Determine effective endpoints for logging
        traces_endpoint = (
            otel_config.otlp_traces_endpoint
            or otel_config.otlp_endpoint
            or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
            or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        )
        logger.info(f"OTLP traces endpoint: {traces_endpoint}")

        if otel_config.enable_metrics:
            metrics_endpoint = (
                otel_config.otlp_metrics_endpoint
                or otel_config.otlp_endpoint
                or os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")
                or os.environ.get(
                    "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"
                )
            )
            logger.info(f"OTLP metrics endpoint: {metrics_endpoint}")

        # Setup console exporter if enabled (prints traces to stdout for debugging)
        if otel_config.console_exporter:
            telemetry.setup_console_exporter()
            logger.info("Console exporter enabled (traces will be printed to stdout)")

        # Setup metrics if enabled
        if otel_config.enable_metrics:
            telemetry.setup_meter()
            logger.info("Metrics export enabled")

        # Store telemetry instance globally
        _telemetry_instance = telemetry
        logger.info("OpenTelemetry telemetry configured successfully")

        return telemetry

    except Exception as e:
        logger.error(f"Failed to configure OpenTelemetry: {e}")
        return None


def get_telemetry_instance() -> Optional[object]:
    """
    Get the global telemetry instance.

    Returns:
        StrandsTelemetry instance if configured, None otherwise
    """
    return _telemetry_instance
