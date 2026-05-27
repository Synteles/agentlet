"""Integration tests for OTEL configuration and CLI override."""

from agentlet_core.config.loader import ConfigLoader
from agentlet_core.config.models import OTELConfig
from agentlet_core.cli.main import override_config


class TestOTELIntegration:
    """Test OTEL integration with configuration and CLI."""

    def test_config_loading_with_otel(self):
        """Test loading config with OTEL settings from YAML."""
        config = ConfigLoader.load("examples/otel-example.yaml")

        assert config.observability.otel.enabled is True
        assert config.observability.otel.otlp_endpoint == "http://localhost:4318"
        assert config.observability.otel.console_exporter is True
        assert config.observability.otel.sampler == "always_on"
        assert config.observability.otel.enable_metrics is True
        assert config.observability.otel.trace_attributes == {
            "environment": "development",
            "service.name": "agentlet-core",
        }

    def test_cli_override_otel_enabled(self):
        """Test CLI override for --otel-enabled flag."""
        # Load a config without OTEL (simple-assistant)
        config = ConfigLoader.load("examples/simple-assistant.yaml")

        # Verify OTEL is disabled by default
        assert config.observability.otel.enabled is False

        # Override with CLI flag
        config = override_config(
            config,
            prompt=None,
            model=None,
            timeout=None,
            max_tokens=None,
            output_format=None,
            max_retries=None,
            initial_retry_interval=None,
            backoff_factor=None,
            otel_enabled=True,
            otlp_endpoint=None,
            otlp_traces_endpoint=None,
            otlp_metrics_endpoint=None,
            otel_console=False,
        )

        # Verify OTEL is now enabled
        assert config.observability.otel.enabled is True

    def test_cli_override_otlp_endpoint(self):
        """Test CLI override for --otlp-endpoint."""
        config = ConfigLoader.load("examples/simple-assistant.yaml")

        # Override with CLI endpoint
        config = override_config(
            config,
            prompt=None,
            model=None,
            timeout=None,
            max_tokens=None,
            output_format=None,
            max_retries=None,
            initial_retry_interval=None,
            backoff_factor=None,
            otel_enabled=True,
            otlp_endpoint="http://collector:4318",
            otlp_traces_endpoint=None,
            otlp_metrics_endpoint=None,
            otel_console=False,
        )

        # Verify endpoint is set
        assert config.observability.otel.enabled is True
        assert config.observability.otel.otlp_endpoint == "http://collector:4318"

    def test_cli_override_console_exporter(self):
        """Test CLI override for --otel-console flag."""
        config = ConfigLoader.load("examples/simple-assistant.yaml")

        # Override with CLI flag
        config = override_config(
            config,
            prompt=None,
            model=None,
            timeout=None,
            max_tokens=None,
            output_format=None,
            max_retries=None,
            initial_retry_interval=None,
            backoff_factor=None,
            otel_enabled=True,
            otlp_endpoint=None,
            otlp_traces_endpoint=None,
            otlp_metrics_endpoint=None,
            otel_console=True,
        )

        # Verify console exporter is enabled
        assert config.observability.otel.enabled is True
        assert config.observability.otel.console_exporter is True

    def test_trace_attributes_building(self):
        """Test building trace attributes from config."""
        from agentlet_core.agents.base import BaseAgentlet

        config = ConfigLoader.load("examples/otel-example.yaml")
        agentlet = BaseAgentlet(config=config)

        # Build trace attributes
        trace_attrs = agentlet._build_trace_attributes()

        # Verify standard attributes
        assert trace_attrs["gen_ai.system"] == "synteles-agentlet"
        assert "execution.id" in trace_attrs
        assert trace_attrs["agentlet.name"] == "otel-assistant"
        assert trace_attrs["agentlet.version"] == "1.0.0"
        assert trace_attrs["model.provider"] == "anthropic"
        assert trace_attrs["model.id"] == "claude-sonnet-4-5"

        # Verify custom attributes from config
        assert trace_attrs["environment"] == "development"
        assert trace_attrs["service.name"] == "agentlet-core"

    def test_backward_compatibility_without_otel(self):
        """Test that configs without observability section work correctly."""
        config = ConfigLoader.load("examples/simple-assistant.yaml")

        # Should have default observability config
        assert hasattr(config, "observability")
        assert isinstance(config.observability.otel, OTELConfig)
        assert config.observability.otel.enabled is False

    def test_signal_specific_endpoints_config(self):
        """Test configuration with separate traces and metrics endpoints."""
        from agentlet_core.config.models import (
            AgentletConfig,
            AgentletMetadata,
            ModelConfig,
            OTELConfig,
            ObservabilityConfig,
        )

        otel_config = OTELConfig(
            enabled=True,
            otlp_endpoint="https://base.example.com/otlp",
            otlp_traces_endpoint="https://traces.example.com/otlp",
            otlp_metrics_endpoint="https://metrics.example.com/otlp",
        )

        observability_config = ObservabilityConfig(otel=otel_config)

        config = AgentletConfig(
            agentlet=AgentletMetadata(name="test", version="1.0.0"),
            system_prompt="Test",
            model=ModelConfig(provider="test", model_id="test"),
            observability=observability_config,
        )

        # Verify all endpoints are set correctly
        assert (
            config.observability.otel.otlp_endpoint == "https://base.example.com/otlp"
        )
        assert (
            config.observability.otel.otlp_traces_endpoint
            == "https://traces.example.com/otlp"
        )
        assert (
            config.observability.otel.otlp_metrics_endpoint
            == "https://metrics.example.com/otlp"
        )

    def test_cli_override_signal_specific_endpoints(self):
        """Test CLI override for signal-specific endpoints."""
        config = ConfigLoader.load("examples/simple-assistant.yaml")

        # Override with CLI flags
        config = override_config(
            config,
            prompt=None,
            model=None,
            timeout=None,
            max_tokens=None,
            output_format=None,
            max_retries=None,
            initial_retry_interval=None,
            backoff_factor=None,
            otel_enabled=True,
            otlp_endpoint="https://base.example.com/otlp",
            otlp_traces_endpoint="https://traces.example.com/otlp",
            otlp_metrics_endpoint="https://metrics.example.com/otlp",
            otel_console=False,
        )

        # Verify all endpoints are set
        assert config.observability.otel.enabled is True
        assert (
            config.observability.otel.otlp_endpoint == "https://base.example.com/otlp"
        )
        assert (
            config.observability.otel.otlp_traces_endpoint
            == "https://traces.example.com/otlp"
        )
        assert (
            config.observability.otel.otlp_metrics_endpoint
            == "https://metrics.example.com/otlp"
        )
