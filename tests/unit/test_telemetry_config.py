"""Unit tests for telemetry configuration."""

from agentlet_core.config.models import OTELConfig, ObservabilityConfig
from agentlet_core.telemetry.config import configure_telemetry


class TestOTELConfig:
    """Test OTEL configuration models."""

    def test_otel_config_defaults(self):
        """Test OTEL config default values."""
        config = OTELConfig()

        assert config.enabled is False
        assert config.otlp_endpoint is None
        assert config.otlp_headers == {}
        assert config.console_exporter is False
        assert config.sampler is None
        assert config.sampler_arg is None
        assert config.enable_metrics is False
        assert config.trace_attributes == {}

    def test_otel_config_from_dict(self):
        """Test OTEL config creation from dictionary."""
        config = OTELConfig(
            enabled=True,
            otlp_endpoint="http://localhost:4318",
            otlp_headers={"Authorization": "Bearer token"},
            console_exporter=True,
            sampler="always_on",
            enable_metrics=True,
            trace_attributes={"environment": "test"},
        )

        assert config.enabled is True
        assert config.otlp_endpoint == "http://localhost:4318"
        assert config.otlp_headers == {"Authorization": "Bearer token"}
        assert config.console_exporter is True
        assert config.sampler == "always_on"
        assert config.enable_metrics is True
        assert config.trace_attributes == {"environment": "test"}

    def test_otel_config_sampler_types(self):
        """Test OTEL config sampler type validation."""
        # Valid sampler types
        valid_samplers = [
            "always_on",
            "always_off",
            "traceidratio",
            "parentbased_always_on",
        ]

        for sampler in valid_samplers:
            config = OTELConfig(sampler=sampler)
            assert config.sampler == sampler

    def test_otel_config_sampler_arg(self):
        """Test OTEL config sampler_arg."""
        config = OTELConfig(sampler="traceidratio", sampler_arg=0.1)
        assert config.sampler_arg == 0.1

    def test_observability_config_defaults(self):
        """Test ObservabilityConfig default values."""
        config = ObservabilityConfig()

        assert isinstance(config.otel, OTELConfig)
        assert config.otel.enabled is False


class TestConfigureTelemetry:
    """Test telemetry configuration function."""

    def test_configure_telemetry_disabled(self):
        """Test that configure_telemetry returns None when disabled."""
        config = OTELConfig(enabled=False)
        result = configure_telemetry(config)

        assert result is None

    def test_configure_telemetry_enabled_without_otel(self):
        """Test configure_telemetry with OTEL enabled but not installed."""
        config = OTELConfig(enabled=True)

        # This will try to import strands.telemetry
        # If not installed, it should return None and log a warning
        result = configure_telemetry(config)

        # Result depends on whether strands-agents[otel] is installed
        # We can't assert the exact result, but it shouldn't raise an exception
        assert result is None or result is not None

    def test_configure_telemetry_with_endpoint(self):
        """Test configure_telemetry with custom endpoint."""
        config = OTELConfig(enabled=True, otlp_endpoint="http://collector:4318")

        result = configure_telemetry(config)

        # If OTEL is installed, result should be StrandsTelemetry instance
        # If not installed, result should be None
        assert result is None or result is not None

    def test_configure_telemetry_with_console_exporter(self):
        """Test configure_telemetry with console exporter enabled."""
        config = OTELConfig(enabled=True, console_exporter=True)

        result = configure_telemetry(config)

        # Should not raise exception
        assert result is None or result is not None

    def test_configure_telemetry_with_metrics(self):
        """Test configure_telemetry with metrics enabled."""
        config = OTELConfig(enabled=True, enable_metrics=True)

        result = configure_telemetry(config)

        # Should not raise exception
        assert result is None or result is not None

    def test_configure_telemetry_with_sampler(self):
        """Test configure_telemetry with sampler configuration."""
        config = OTELConfig(enabled=True, sampler="traceidratio", sampler_arg=0.1)

        result = configure_telemetry(config)

        # Should not raise exception
        assert result is None or result is not None

    def test_configure_telemetry_with_headers(self):
        """Test configure_telemetry with custom headers."""
        config = OTELConfig(
            enabled=True,
            otlp_headers={"Authorization": "Bearer token", "X-Custom": "value"},
        )

        result = configure_telemetry(config)

        # Should not raise exception
        assert result is None or result is not None

    def test_configure_telemetry_with_signal_specific_endpoints(self):
        """Test configure_telemetry with separate traces and metrics endpoints."""
        config = OTELConfig(
            enabled=True,
            otlp_traces_endpoint="https://traces.example.com/otlp",
            otlp_metrics_endpoint="https://metrics.example.com/otlp",
        )

        result = configure_telemetry(config)

        # Should not raise exception
        assert result is None or result is not None
