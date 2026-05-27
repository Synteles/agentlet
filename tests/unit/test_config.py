"""Unit tests for configuration management."""

import pytest
from pydantic import ValidationError

from agentlet_core.config.models import (
    AgentletConfig,
    AgentletMetadata,
    MCPToolConfig,
    ModelConfig,
    OutputConfig,
    ResourceLimits,
    SubAgentletConfig,
    SwarmParticipantConfig,
)


def test_model_config_basic():
    """Test basic model configuration."""
    config = ModelConfig(provider="bedrock", model_id="claude-sonnet-4-5")
    assert config.provider == "bedrock"
    assert config.model_id == "claude-sonnet-4-5"
    assert config.parameters == {}


def test_model_config_with_parameters():
    """Test model configuration with parameters."""
    config = ModelConfig(
        provider="bedrock",
        model_id="claude-sonnet-4-5",
        parameters={"temperature": 0.7, "max_tokens": 4096},
    )
    assert config.parameters["temperature"] == 0.7
    assert config.parameters["max_tokens"] == 4096


def test_mcp_tool_stdio_config():
    """Test stdio MCP tool configuration."""
    config = MCPToolConfig(
        name="file_reader",
        server="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem"],
    )
    assert config.name == "file_reader"
    assert config.server == "stdio"
    assert config.command == "npx"


def test_mcp_tool_stdio_requires_command():
    """Test that stdio tools require command."""
    with pytest.raises(ValidationError):
        MCPToolConfig(name="test", server="stdio")


def test_mcp_tool_sse_config():
    """Test SSE MCP tool configuration."""
    config = MCPToolConfig(
        name="web_search", server="sse", url="http://localhost:3000/mcp"
    )
    assert config.name == "web_search"
    assert config.server == "sse"
    assert config.url == "http://localhost:3000/mcp"


def test_mcp_tool_sse_requires_url():
    """Test that SSE tools require URL."""
    with pytest.raises(ValidationError):
        MCPToolConfig(name="test", server="sse")


def test_resource_limits_defaults():
    """Test resource limits default values."""
    limits = ResourceLimits()
    assert limits.max_execution_time == 300
    assert limits.max_tokens == 10000
    assert limits.max_tool_calls == 20


def test_output_config_defaults():
    """Test output configuration defaults."""
    output = OutputConfig()
    assert output.format == "markdown"
    assert output.show_messages is True
    assert output.show_reasoning is True
    assert output.show_tool_calls is True
    assert output.show_turn_boundaries is False


def test_agentlet_config_complete():
    """Test complete agentlet configuration."""
    config = AgentletConfig(
        agentlet=AgentletMetadata(name="test-agent", version="1.0.0"),
        system_prompt="You are a helpful assistant.",
        model=ModelConfig(provider="bedrock", model_id="claude-sonnet-4-5"),
    )
    assert config.agentlet.name == "test-agent"
    assert config.agentlet.version == "1.0.0"
    assert config.system_prompt == "You are a helpful assistant."
    assert config.model.provider == "bedrock"


def test_agentlet_config_with_defaults():
    """Test agentlet configuration uses defaults."""
    config = AgentletConfig(
        agentlet=AgentletMetadata(name="test"),
        system_prompt="Test prompt",
        model=ModelConfig(provider="test", model_id="test-model"),
    )
    assert config.tools == []
    assert config.mcp_tools == []
    assert config.resource_limits.max_execution_time == 300
    assert config.output.format == "markdown"


def test_agentlet_config_with_tools():
    """Test agentlet configuration with tools specified."""
    config = AgentletConfig(
        agentlet=AgentletMetadata(name="test"),
        system_prompt="Test prompt",
        model=ModelConfig(provider="test", model_id="test-model"),
        tools=["calculator", "file_read", "shell"],
    )
    assert config.tools == ["calculator", "file_read", "shell"]


def test_agentlet_config_empty_tools():
    """Test agentlet configuration with empty tools list."""
    config = AgentletConfig(
        agentlet=AgentletMetadata(name="test"),
        system_prompt="Test prompt",
        model=ModelConfig(provider="test", model_id="test-model"),
        tools=[],
    )
    assert config.tools == []


# ---------------------------------------------------------------------------
# SubAgentletConfig
# ---------------------------------------------------------------------------


def test_sub_agentlet_config_minimal():
    """SubAgentletConfig accepts minimal required fields."""
    cfg = SubAgentletConfig(
        name="helper",
        description="Helps with tasks.",
        system_prompt="You are a helper.",
    )
    assert cfg.name == "helper"
    assert cfg.description == "Helps with tasks."
    assert cfg.system_prompt == "You are a helper."
    assert cfg.model is None
    assert cfg.tools == []
    assert cfg.mcp_tools == []


def test_sub_agentlet_config_with_model_override():
    """SubAgentletConfig accepts an explicit model override."""
    cfg = SubAgentletConfig(
        name="cheap_agent",
        description="Uses a cheaper model.",
        system_prompt="Be concise.",
        model=ModelConfig(provider="bedrock", model_id="claude-haiku-4-5"),
    )
    assert cfg.model is not None
    assert cfg.model.provider == "bedrock"
    assert cfg.model.model_id == "claude-haiku-4-5"


def test_sub_agentlet_config_with_tools():
    """SubAgentletConfig accepts tools and mcp_tools."""
    cfg = SubAgentletConfig(
        name="coder",
        description="Writes code.",
        system_prompt="You are a software engineer.",
        tools=["file_editor", "shell"],
    )
    assert cfg.tools == ["file_editor", "shell"]


def test_agentlet_config_sub_agentlets_default_empty():
    """AgentletConfig.sub_agentlets defaults to [] — backwards compatible."""
    config = AgentletConfig(
        agentlet=AgentletMetadata(name="test"),
        system_prompt="Test prompt",
        model=ModelConfig(provider="test", model_id="test-model"),
    )
    assert config.sub_agentlets == []


def test_agentlet_config_with_sub_agentlets():
    """AgentletConfig accepts a list of sub-agentlets."""
    config = AgentletConfig(
        agentlet=AgentletMetadata(name="orchestrator"),
        system_prompt="You are an orchestrator.",
        model=ModelConfig(provider="bedrock", model_id="claude-sonnet-4-5"),
        sub_agentlets=[
            SubAgentletConfig(
                name="researcher",
                description="Researches topics.",
                system_prompt="You are a researcher.",
            ),
            SubAgentletConfig(
                name="writer",
                description="Writes content.",
                system_prompt="You are a writer.",
            ),
        ],
    )
    assert len(config.sub_agentlets) == 2
    assert config.sub_agentlets[0].name == "researcher"
    assert config.sub_agentlets[1].name == "writer"


# ---------------------------------------------------------------------------
# Python-identifier pattern validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["valid", "valid_name", "_private", "a", "A1_b"])
def test_sub_agentlet_name_valid(name):
    """SubAgentletConfig.name accepts valid Python identifiers."""
    cfg = SubAgentletConfig(name=name, description="d", system_prompt="sp")
    assert cfg.name == name


@pytest.mark.parametrize("name", ["1invalid", "my-agent", "has space", ""])
def test_sub_agentlet_name_invalid(name):
    """SubAgentletConfig.name rejects non-identifiers."""
    with pytest.raises(ValidationError):
        SubAgentletConfig(name=name, description="d", system_prompt="sp")


def test_sub_agentlet_name_too_long():
    """SubAgentletConfig.name rejects names longer than 128 chars."""
    with pytest.raises(ValidationError):
        SubAgentletConfig(name="a" * 129, description="d", system_prompt="sp")


@pytest.mark.parametrize("name", ["valid", "arch_v2", "_node", "a"])
def test_swarm_participant_name_valid(name):
    """SwarmParticipantConfig.name accepts valid Python identifiers."""
    cfg = SwarmParticipantConfig(name=name, description="d", system_prompt="sp")
    assert cfg.name == name


@pytest.mark.parametrize("name", ["1start", "my-node", "bad name", ""])
def test_swarm_participant_name_invalid(name):
    """SwarmParticipantConfig.name rejects non-identifiers."""
    with pytest.raises(ValidationError):
        SwarmParticipantConfig(name=name, description="d", system_prompt="sp")


@pytest.mark.parametrize("prefix", ["fs", "my_prefix", "_p", "a1"])
def test_mcp_tool_prefix_valid(prefix):
    """MCPToolConfig.prefix accepts valid Python identifiers."""
    cfg = MCPToolConfig(name="srv", server="stdio", command="npx", prefix=prefix)
    assert cfg.prefix == prefix


@pytest.mark.parametrize("prefix", ["1start", "my-prefix", "bad prefix"])
def test_mcp_tool_prefix_invalid(prefix):
    """MCPToolConfig.prefix rejects non-identifiers."""
    with pytest.raises(ValidationError):
        MCPToolConfig(name="srv", server="stdio", command="npx", prefix=prefix)


def test_mcp_tool_prefix_none_allowed():
    """MCPToolConfig.prefix=None is valid (optional field)."""
    cfg = MCPToolConfig(name="srv", server="stdio", command="npx")
    assert cfg.prefix is None


# ---------------------------------------------------------------------------
# Display-label pattern validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["my-agentlet", "agentlet_v2", "MyAgent", "0start", "a-b_c"]
)
def test_agentlet_metadata_name_valid(name):
    """AgentletMetadata.name accepts alphanumeric, hyphens, and underscores."""
    meta = AgentletMetadata(name=name)
    assert meta.name == name


@pytest.mark.parametrize("name", ["-start", "_start", "has space", ""])
def test_agentlet_metadata_name_invalid(name):
    """AgentletMetadata.name rejects names that don't start with a letter or digit."""
    with pytest.raises(ValidationError):
        AgentletMetadata(name=name)


def test_agentlet_metadata_name_too_long():
    """AgentletMetadata.name rejects names longer than 128 chars."""
    with pytest.raises(ValidationError):
        AgentletMetadata(name="a" * 129)


@pytest.mark.parametrize(
    "name", ["filesystem", "web-search", "my_server", "s1", "0mcp"]
)
def test_mcp_tool_name_valid(name):
    """MCPToolConfig.name accepts alphanumeric, hyphens, and underscores."""
    cfg = MCPToolConfig(name=name, server="stdio", command="npx")
    assert cfg.name == name


@pytest.mark.parametrize("name", ["-start", "_start", "has space", ""])
def test_mcp_tool_name_invalid(name):
    """MCPToolConfig.name rejects names that don't start with a letter or digit."""
    with pytest.raises(ValidationError):
        MCPToolConfig(name=name, server="stdio", command="npx")


def test_mcp_tool_name_too_long():
    """MCPToolConfig.name rejects names longer than 128 chars."""
    with pytest.raises(ValidationError):
        MCPToolConfig(name="a" * 129, server="stdio", command="npx")
