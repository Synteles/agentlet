"""Unit tests for CLI helper functions load_config and override_config."""

import pytest
from unittest.mock import patch

from agentlet_core.cli.main import load_config, override_config
from agentlet_core.config.models import AgentletConfig, AgentletMetadata, ModelConfig


def _make_config(**kwargs) -> AgentletConfig:
    return AgentletConfig(
        agentlet=AgentletMetadata(name="test"),
        model=ModelConfig(provider="bedrock", model_id="claude-sonnet-4-5"),
        system_prompt="You are helpful.",
        **kwargs,
    )


def _override(config: AgentletConfig, **kwargs) -> AgentletConfig:
    """Call override_config with all optional params defaulting to None/False."""
    defaults = dict(
        prompt=None,
        model=None,
        timeout=None,
        max_tokens=None,
        output_format=None,
        max_retries=None,
        initial_retry_interval=None,
        backoff_factor=None,
        otel_enabled=False,
        otlp_endpoint=None,
        otlp_traces_endpoint=None,
        otlp_metrics_endpoint=None,
        otel_console=False,
    )
    defaults.update(kwargs)
    return override_config(config, **defaults)


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_success(self, tmp_path):
        yaml = (
            "agentlet:\n  name: cli-test\n"
            "model:\n  provider: bedrock\n  model_id: claude-sonnet-4-5\n"
            "system_prompt: Hello.\n"
        )
        f = tmp_path / "agent.yaml"
        f.write_text(yaml)
        config = load_config(str(f))
        assert isinstance(config, AgentletConfig)
        assert config.agentlet.name == "cli-test"

    def test_file_not_found_wraps_message(self):
        with patch(
            "agentlet_core.cli.main.ConfigLoader.load",
            side_effect=FileNotFoundError("original"),
        ):
            with pytest.raises(
                FileNotFoundError, match="No agentlet configuration found"
            ):
                load_config("ghost")

    def test_none_path_triggers_auto_discovery(self, tmp_path, monkeypatch):
        yaml = (
            "agentlet:\n  name: auto\n"
            "model:\n  provider: bedrock\n  model_id: claude-sonnet-4-5\n"
            "system_prompt: Hi.\n"
        )
        (tmp_path / "agent.yaml").write_text(yaml)
        from agentlet_core.config.loader import ConfigLoader

        monkeypatch.setattr(ConfigLoader, "SEARCH_PATHS", [tmp_path])
        config = load_config(None)
        assert config.agentlet.name == "auto"


# ---------------------------------------------------------------------------
# override_config
# ---------------------------------------------------------------------------


class TestOverrideConfig:
    def test_prompt_set(self):
        config = _make_config()
        result = _override(config, prompt="hello")
        assert result.prompt == "hello"

    def test_prompt_none_preserves_existing(self):
        config = _make_config(prompt="original")
        result = _override(config, prompt=None)
        assert result.prompt == "original"

    def test_model_with_slash_updates_provider_and_id(self):
        config = _make_config()
        result = _override(config, model="openai/gpt-4o")
        assert result.model.provider == "openai"
        assert result.model.model_id == "gpt-4o"

    def test_model_without_slash_updates_id_only(self):
        config = _make_config()
        result = _override(config, model="gpt-4o")
        assert result.model.model_id == "gpt-4o"
        assert result.model.provider == "bedrock"  # unchanged

    def test_timeout_sets_max_execution_time(self):
        config = _make_config()
        result = _override(config, timeout=120)
        assert result.resource_limits.max_execution_time == 120

    def test_max_tokens_sets_limit(self):
        config = _make_config()
        result = _override(config, max_tokens=2000)
        assert result.resource_limits.max_tokens == 2000

    def test_output_format_markdown(self):
        config = _make_config()
        result = _override(config, output_format="markdown")
        assert result.output.format == "markdown"

    def test_output_format_json(self):
        config = _make_config()
        result = _override(config, output_format="json")
        assert result.output.format == "json"

    def test_output_format_text(self):
        config = _make_config()
        result = _override(config, output_format="text")
        assert result.output.format == "text"

    def test_output_format_invalid_ignored(self):
        config = _make_config()
        result = _override(config, output_format="xml")
        assert result.output.format == "markdown"  # default unchanged

    def test_max_retries(self):
        config = _make_config()
        result = _override(config, max_retries=10)
        assert result.model.retry.max_retries == 10

    def test_initial_retry_interval(self):
        config = _make_config()
        result = _override(config, initial_retry_interval=5.0)
        assert result.model.retry.initial_retry_interval == 5.0

    def test_backoff_factor(self):
        config = _make_config()
        result = _override(config, backoff_factor=3.0)
        assert result.model.retry.backoff_factor == 3.0

    def test_otel_enabled(self):
        config = _make_config()
        result = _override(config, otel_enabled=True)
        assert result.observability.otel.enabled is True

    def test_otlp_endpoint(self):
        config = _make_config()
        result = _override(config, otlp_endpoint="http://otel:4318")
        assert result.observability.otel.otlp_endpoint == "http://otel:4318"

    def test_otlp_traces_endpoint(self):
        config = _make_config()
        result = _override(config, otlp_traces_endpoint="http://traces:4318")
        assert result.observability.otel.otlp_traces_endpoint == "http://traces:4318"

    def test_otlp_metrics_endpoint(self):
        config = _make_config()
        result = _override(config, otlp_metrics_endpoint="http://metrics:4318")
        assert result.observability.otel.otlp_metrics_endpoint == "http://metrics:4318"

    def test_otel_console(self):
        config = _make_config()
        result = _override(config, otel_console=True)
        assert result.observability.otel.console_exporter is True

    def test_no_overrides_leaves_config_unchanged(self):
        config = _make_config()
        result = _override(config)
        assert result.model.provider == "bedrock"
        assert result.model.model_id == "claude-sonnet-4-5"
