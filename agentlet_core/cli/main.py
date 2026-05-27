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

"""Main CLI interface using Click."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import click

from agentlet_core.agents.base import BaseAgentlet
from agentlet_core.config.loader import ConfigLoader
from agentlet_core.config.models import AgentletConfig
from agentlet_core.utils.env import load_env_file
from agentlet_core.logging.config import configure_logging, get_logger
from agentlet_core.logging.handlers import RichLoggerAdapter

from importlib.metadata import version


@click.command()
@click.option(
    "--prompt",
    "-p",
    help="User prompt (task for the agentlet to perform)",
    type=str,
)
@click.option(
    "--model",
    "-m",
    help="LLM model to use (e.g., 'bedrock/claude-sonnet-4-5')",
    type=str,
)
@click.option(
    "--path",
    help="Path to working directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=None,
)
@click.option(
    "--timeout",
    help="Maximum execution time in seconds",
    type=int,
    default=None,
)
@click.option(
    "--max-tokens",
    help="LLM token limit",
    type=int,
    default=None,
)
@click.option(
    "--agentlet",
    "-a",
    help="Path to agentlet configuration file or agentlet name",
    type=str,
    default=None,
)
@click.option(
    "--output-format",
    help="Output format",
    type=click.Choice(["json", "markdown", "text"], case_sensitive=False),
    default=None,
)
@click.option(
    "--debug",
    "-d",
    is_flag=True,
    help="Enable detailed debug logging",
)
@click.option(
    "--env-file",
    help="Path to .env file (default: searches .env in current dir, project root, and home)",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    default=None,
)
@click.option(
    "--max-retries",
    help="Maximum number of retry attempts for rate limit errors (default: 5)",
    type=int,
    default=None,
)
@click.option(
    "--initial-retry-interval",
    help="Initial retry interval in seconds (default: 30.0)",
    type=float,
    default=None,
)
@click.option(
    "--backoff-factor",
    help="Exponential backoff factor (default: 2.0)",
    type=float,
    default=None,
)
@click.option(
    "--otel-enabled",
    is_flag=True,
    help="Enable OpenTelemetry trace export",
)
@click.option(
    "--otlp-endpoint",
    type=str,
    help="OTLP base endpoint URL (default: http://localhost:4318 or OTEL_EXPORTER_OTLP_ENDPOINT)",
)
@click.option(
    "--otlp-traces-endpoint",
    type=str,
    help="OTLP traces endpoint URL (overrides --otlp-endpoint for traces)",
)
@click.option(
    "--otlp-metrics-endpoint",
    type=str,
    help="OTLP metrics endpoint URL (overrides --otlp-endpoint for metrics)",
)
@click.option(
    "--otel-console",
    is_flag=True,
    help="Enable console trace export for debugging",
)
@click.option(
    "--image",
    "-i",
    "images",
    multiple=True,
    help=(
        "Image to pass to the model (can be specified multiple times). "
        "Accepts a local file path, an HTTP/HTTPS URL, or a base64 data URL. "
        "Supported formats: JPEG, PNG, GIF, WebP. "
        "Requires a vision-capable model (e.g. claude-3-5-sonnet, gpt-4o)."
    ),
    type=str,
)
@click.version_option(version=version("agentlet-core"), prog_name="agentlet-core")
def cli(
    prompt: Optional[str],
    model: Optional[str],
    path: Optional[str],
    timeout: Optional[int],
    max_tokens: Optional[int],
    agentlet: Optional[str],
    output_format: Optional[str],
    debug: bool,
    env_file: Optional[str],
    max_retries: Optional[int],
    initial_retry_interval: Optional[float],
    backoff_factor: Optional[float],
    otel_enabled: bool,
    otlp_endpoint: Optional[str],
    otlp_traces_endpoint: Optional[str],
    otlp_metrics_endpoint: Optional[str],
    otel_console: bool,
    images: tuple[str, ...],
) -> None:
    """
    Agentlet Core - Autonomous AI agent runtime.

    Execute tasks using configurable AI agents with MCP tools support.
    """
    # Load .env file early (before any operations that might need env vars)
    env_loaded = load_env_file(env_file)
    if debug and env_loaded:
        click.echo("✓ Environment variables loaded from .env file", err=True)

    # Configure logging ONCE at startup (Synteles Logging Contract requirement)
    configure_logging(
        level=logging.DEBUG if debug else logging.INFO,
        debug_mode=debug,
        log_dir=Path.cwd() if debug else None,
        json_format=False,  # Use text format for now (JSON can be enabled later)
    )

    try:
        # Load configuration
        config = load_config(agentlet)

        # Override config with CLI arguments
        config = override_config(
            config,
            prompt=prompt,
            model=model,
            timeout=timeout,
            max_tokens=max_tokens,
            output_format=output_format,
            max_retries=max_retries,
            initial_retry_interval=initial_retry_interval,
            backoff_factor=backoff_factor,
            otel_enabled=otel_enabled,
            otlp_endpoint=otlp_endpoint,
            otlp_traces_endpoint=otlp_traces_endpoint,
            otlp_metrics_endpoint=otlp_metrics_endpoint,
            otel_console=otel_console,
        )

        # Configure telemetry (after logging, before agent execution)
        from agentlet_core.telemetry.config import configure_telemetry

        telemetry_instance = configure_telemetry(config.observability.otel)
        if debug and telemetry_instance:
            click.echo("✓ OpenTelemetry configured", err=True)

        # Validate prompt
        if not config.prompt:
            click.echo(
                "Error: No prompt provided. Use --prompt or define in config file.",
                err=True,
            )
            sys.exit(1)

        # Run agentlet
        asyncio.run(run_agentlet(config, path, debug, list(images)))

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def load_config(config_path: Optional[str]) -> AgentletConfig:
    """Load agentlet configuration."""
    try:
        return ConfigLoader.load(config_path)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            "No agentlet configuration found. Create a config file or specify --agentlet"
        ) from e


def override_config(
    config: AgentletConfig,
    prompt: Optional[str],
    model: Optional[str],
    timeout: Optional[int],
    max_tokens: Optional[int],
    output_format: Optional[str],
    max_retries: Optional[int],
    initial_retry_interval: Optional[float],
    backoff_factor: Optional[float],
    otel_enabled: bool,
    otlp_endpoint: Optional[str],
    otlp_traces_endpoint: Optional[str],
    otlp_metrics_endpoint: Optional[str],
    otel_console: bool,
) -> AgentletConfig:
    """Override configuration with CLI arguments."""
    if prompt:
        config.prompt = prompt

    if model:
        # Parse model string (e.g., "bedrock/claude-sonnet-4-5")
        provider, _, model_id = model.partition("/")
        if model_id:
            config.model.provider = provider
            config.model.model_id = model_id
        else:
            config.model.model_id = model

    if timeout:
        config.resource_limits.max_execution_time = timeout

    if max_tokens:
        config.resource_limits.max_tokens = max_tokens

    if output_format and output_format in ("markdown", "json", "text"):
        config.output.format = output_format  # type: ignore[assignment]

    # Override retry configuration if provided
    if max_retries is not None:
        config.model.retry.max_retries = max_retries

    if initial_retry_interval is not None:
        config.model.retry.initial_retry_interval = initial_retry_interval

    if backoff_factor is not None:
        config.model.retry.backoff_factor = backoff_factor

    # Override OTEL configuration if provided
    if otel_enabled:
        config.observability.otel.enabled = True

    if otlp_endpoint:
        config.observability.otel.otlp_endpoint = otlp_endpoint

    if otlp_traces_endpoint:
        config.observability.otel.otlp_traces_endpoint = otlp_traces_endpoint

    if otlp_metrics_endpoint:
        config.observability.otel.otlp_metrics_endpoint = otlp_metrics_endpoint

    if otel_console:
        config.observability.otel.console_exporter = True

    return config


async def run_agentlet(
    config: AgentletConfig,
    working_dir: Optional[str],
    debug: bool,
    images: Optional[list[str]] = None,
) -> None:
    """Execute the agentlet."""
    # Create logger (logging already configured in cli())
    base_logger = get_logger(__name__)
    logger = RichLoggerAdapter(base_logger)

    # Display splash screen
    logger.splash()

    # Create and run agentlet with proper cleanup
    agentlet = BaseAgentlet(config=config, logger=logger)

    # Ensure prompt is not None (should be validated in cli() function)
    if not config.prompt:
        raise ValueError("Prompt cannot be None")

    timeout = config.resource_limits.max_execution_time

    try:
        _response = await asyncio.wait_for(
            agentlet.run(
                prompt=config.prompt,
                working_dir=working_dir,
                images=images or [],
            ),
            timeout=timeout,
        )

        # Display execution summary if context exists
        if agentlet.context:
            logger.execution_summary(agentlet.context.get_summary())

    except asyncio.TimeoutError:
        logger.error(f"Execution timed out after {timeout}s")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("Execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        raise
    finally:
        # Cleanup is handled by agentlet.terminate()
        # No additional cleanup needed here
        pass


if __name__ == "__main__":
    cli()
