"""Unit tests for ConfigLoader."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agentlet_core.config.loader import ConfigLoader
from agentlet_core.config.models import AgentletConfig

MINIMAL_YAML = """\
agentlet:
  name: test-agent
model:
  provider: bedrock
  model_id: claude-sonnet-4-5
system_prompt: You are helpful.
"""

MINIMAL_DICT = {
    "agentlet": {"name": "test-agent"},
    "model": {"provider": "bedrock", "model_id": "claude-sonnet-4-5"},
    "system_prompt": "You are helpful.",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def _patch_search_paths(monkeypatch, paths: list[Path]) -> None:
    monkeypatch.setattr(ConfigLoader, "SEARCH_PATHS", paths)


# ---------------------------------------------------------------------------
# _load_from_file
# ---------------------------------------------------------------------------


class TestLoadFromFile:
    def test_yaml_extension(self, tmp_path):
        f = _write(tmp_path, "agent.yaml", MINIMAL_YAML)
        config = ConfigLoader._load_from_file(f)
        assert isinstance(config, AgentletConfig)
        assert config.agentlet.name == "test-agent"

    def test_yml_extension(self, tmp_path):
        f = _write(tmp_path, "agent.yml", MINIMAL_YAML)
        config = ConfigLoader._load_from_file(f)
        assert config.model.provider == "bedrock"

    def test_json_extension(self, tmp_path):
        f = _write(tmp_path, "agent.json", json.dumps(MINIMAL_DICT))
        config = ConfigLoader._load_from_file(f)
        assert config.agentlet.name == "test-agent"
        assert config.model.model_id == "claude-sonnet-4-5"

    def test_env_var_expansion(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TEST_PROVIDER", "openai")
        monkeypatch.setenv("TEST_MODEL", "gpt-4o")
        yaml_with_vars = """\
agentlet:
  name: test-agent
model:
  provider: $TEST_PROVIDER
  model_id: ${TEST_MODEL}
system_prompt: You are helpful.
"""
        f = _write(tmp_path, "agent.yaml", yaml_with_vars)
        config = ConfigLoader._load_from_file(f)
        assert config.model.provider == "openai"
        assert config.model.model_id == "gpt-4o"

    def test_unsupported_extension_raises(self, tmp_path):
        f = _write(tmp_path, "agent.toml", "")
        with pytest.raises(ValueError, match="Unsupported config format"):
            ConfigLoader._load_from_file(f)

    def test_invalid_config_raises_validation_error(self, tmp_path):
        f = _write(tmp_path, "agent.yaml", "agentlet:\n  name: test-agent\n")
        with pytest.raises(ValidationError):
            ConfigLoader._load_from_file(f)


# ---------------------------------------------------------------------------
# _find_agentlet_by_name
# ---------------------------------------------------------------------------


class TestFindAgentletByName:
    def test_finds_yaml(self, tmp_path, monkeypatch):
        _write(tmp_path, "my-agent.yaml", MINIMAL_YAML)
        _patch_search_paths(monkeypatch, [tmp_path])
        result = ConfigLoader._find_agentlet_by_name("my-agent")
        assert result == tmp_path / "my-agent.yaml"

    def test_finds_yml(self, tmp_path, monkeypatch):
        _write(tmp_path, "my-agent.yml", MINIMAL_YAML)
        _patch_search_paths(monkeypatch, [tmp_path])
        result = ConfigLoader._find_agentlet_by_name("my-agent")
        assert result == tmp_path / "my-agent.yml"

    def test_yaml_preferred_over_yml(self, tmp_path, monkeypatch):
        _write(tmp_path, "my-agent.yaml", MINIMAL_YAML)
        _write(tmp_path, "my-agent.yml", MINIMAL_YAML)
        _patch_search_paths(monkeypatch, [tmp_path])
        result = ConfigLoader._find_agentlet_by_name("my-agent")
        assert result.suffix == ".yaml"

    def test_not_found_raises(self, tmp_path, monkeypatch):
        _patch_search_paths(monkeypatch, [tmp_path])
        with pytest.raises(FileNotFoundError, match="missing-agent"):
            ConfigLoader._find_agentlet_by_name("missing-agent")

    def test_skips_nonexistent_search_path(self, tmp_path, monkeypatch):
        ghost = tmp_path / "nonexistent"
        _write(tmp_path, "real.yaml", MINIMAL_YAML)
        _patch_search_paths(monkeypatch, [ghost, tmp_path])
        result = ConfigLoader._find_agentlet_by_name("real")
        assert result == tmp_path / "real.yaml"


# ---------------------------------------------------------------------------
# _find_config_file
# ---------------------------------------------------------------------------


class TestFindConfigFile:
    def test_finds_yaml(self, tmp_path, monkeypatch):
        _write(tmp_path, "agent.yaml", MINIMAL_YAML)
        _patch_search_paths(monkeypatch, [tmp_path])
        result = ConfigLoader._find_config_file()
        assert result.suffix in (".yaml", ".yml", ".json")

    def test_finds_yml(self, tmp_path, monkeypatch):
        _write(tmp_path, "agent.yml", MINIMAL_YAML)
        _patch_search_paths(monkeypatch, [tmp_path])
        result = ConfigLoader._find_config_file()
        assert result == tmp_path / "agent.yml"

    def test_finds_json(self, tmp_path, monkeypatch):
        _write(tmp_path, "agent.json", json.dumps(MINIMAL_DICT))
        _patch_search_paths(monkeypatch, [tmp_path])
        result = ConfigLoader._find_config_file()
        assert result == tmp_path / "agent.json"

    def test_not_found_raises(self, tmp_path, monkeypatch):
        _patch_search_paths(monkeypatch, [tmp_path])
        with pytest.raises(FileNotFoundError, match="No agentlet config file found"):
            ConfigLoader._find_config_file()

    def test_skips_nonexistent_search_path(self, tmp_path, monkeypatch):
        ghost = tmp_path / "nonexistent"
        _write(tmp_path, "agent.yaml", MINIMAL_YAML)
        _patch_search_paths(monkeypatch, [ghost, tmp_path])
        result = ConfigLoader._find_config_file()
        assert result.parent == tmp_path


# ---------------------------------------------------------------------------
# load (integration)
# ---------------------------------------------------------------------------


class TestLoad:
    def test_explicit_file_path(self, tmp_path):
        f = _write(tmp_path, "agent.yaml", MINIMAL_YAML)
        config = ConfigLoader.load(str(f))
        assert isinstance(config, AgentletConfig)
        assert config.agentlet.name == "test-agent"

    def test_agentlet_name(self, tmp_path, monkeypatch):
        _write(tmp_path, "my-agent.yaml", MINIMAL_YAML)
        _patch_search_paths(monkeypatch, [tmp_path])
        config = ConfigLoader.load("my-agent")
        assert config.agentlet.name == "test-agent"

    def test_auto_discovery(self, tmp_path, monkeypatch):
        _write(tmp_path, "agent.yaml", MINIMAL_YAML)
        _patch_search_paths(monkeypatch, [tmp_path])
        config = ConfigLoader.load()
        assert isinstance(config, AgentletConfig)

    def test_nonexistent_path_raises(self):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            ConfigLoader.load("/nonexistent/path/agent.yaml")

    def test_nonexistent_name_raises(self, tmp_path, monkeypatch):
        _patch_search_paths(monkeypatch, [tmp_path])
        with pytest.raises(FileNotFoundError, match="ghost-agent"):
            ConfigLoader.load("ghost-agent")
