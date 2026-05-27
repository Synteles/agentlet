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

"""Pydantic models for Agentlet configuration."""

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class RetryConfig(BaseModel):
    """Retry configuration for handling transient errors."""

    max_retries: int = Field(
        default=5, ge=0, description="Maximum number of retry attempts (default: 5)"
    )
    initial_retry_interval: float = Field(
        default=30.0,
        gt=0,
        description="Initial retry interval in seconds (default: 30.0)",
    )
    backoff_factor: float = Field(
        default=2.0, gt=1.0, description="Exponential backoff factor (default: 2.0)"
    )
    max_retry_interval: float = Field(
        default=300.0,
        gt=0,
        description="Maximum retry interval in seconds (default: 300.0)",
    )
    retry_on_errors: list[str] = Field(
        default_factory=lambda: [
            "RateLimitError",
            "EventLoopException",
            "APIConnectionError",
            "APITimeoutError",
            "litellm.RateLimitError",
        ],
        description="List of error types to retry on (default: ['RateLimitError', 'EventLoopException', 'APIConnectionError', 'APITimeoutError', 'litellm.RateLimitError'])",
    )


class ModelConfig(BaseModel):
    """LLM model configuration."""

    provider: str = Field(..., description="Model provider (e.g., 'bedrock', 'openai')")
    model_id: str = Field(..., description="Model identifier")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Model-specific parameters"
    )
    retry: RetryConfig = Field(
        default_factory=RetryConfig, description="Retry configuration"
    )

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v: Any) -> dict[str, Any]:
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        return {}


class MCPToolConfig(BaseModel):
    """MCP tool configuration."""

    name: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$",
        description=(
            "Identifier for this MCP server (used in logs and error messages). "
            "Must start with a letter or digit; may contain letters, digits, "
            "underscores, and hyphens; max 128 chars."
        ),
    )
    server: Literal["stdio", "http", "sse"] = Field(
        ..., description="Server transport type"
    )

    # stdio-specific fields
    command: Optional[str] = Field(None, description="Command for stdio servers")
    args: list[str] = Field(
        default_factory=list, description="Command arguments for stdio"
    )

    # http/sse-specific fields
    url: Optional[str] = Field(None, description="URL for HTTP/SSE servers")
    headers: dict[str, str] = Field(
        default_factory=dict, description="HTTP headers (for http/sse)"
    )
    api_key_env: Optional[str] = Field(
        None, description="Environment variable name for API key/token"
    )

    # Common fields
    env: dict[str, str] = Field(
        default_factory=dict, description="Environment variables for stdio servers"
    )

    # MCP tool filtering and prefixing
    prefix: Optional[str] = Field(
        None,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]{0,127}$",
        description=(
            "Prefix prepended to every tool name from this server "
            "(e.g. prefix='fs' turns 'read_file' into 'fs_read_file'). "
            "Must be a valid Python identifier — the combined name is registered "
            "as a callable in Strands."
        ),
    )
    tool_filters: Optional[dict[str, list[str]]] = Field(
        None, description="Tool filters with 'allowed' and/or 'rejected' lists"
    )

    @model_validator(mode="after")
    def validate_server_config(self) -> "MCPToolConfig":
        """Validate server-specific configuration."""
        if self.server == "stdio" and not self.command:
            raise ValueError("command is required for stdio servers")
        if self.server in ("http", "sse") and not self.url:
            raise ValueError(f"url is required for {self.server} servers")

        # Validate tool_filters structure
        if self.tool_filters:
            valid_keys = {"allowed", "rejected"}
            invalid_keys = set(self.tool_filters.keys()) - valid_keys
            if invalid_keys:
                raise ValueError(
                    f"Invalid tool_filters keys: {invalid_keys}. "
                    f"Only 'allowed' and 'rejected' are supported."
                )

        return self


class ResourceLimits(BaseModel):
    """Resource limits for agentlet execution."""

    max_execution_time: int = Field(
        default=300, description="Maximum execution time in seconds"
    )
    max_tokens: int = Field(default=10000, description="Maximum token limit")
    max_tool_calls: int = Field(default=20, description="Maximum tool calls")


class OutputConfig(BaseModel):
    """Output configuration."""

    format: Literal["markdown", "json", "text"] = Field(
        default="markdown", description="Output format"
    )
    show_messages: bool = Field(
        default=True, description="Show complete assistant messages per turn"
    )
    show_reasoning: bool = Field(
        default=True,
        description="Show reasoning blocks (extended thinking) if model supports it",
    )
    show_tool_calls: bool = Field(default=True, description="Show tool invocations")
    show_turn_boundaries: bool = Field(
        default=False, description="Show turn boundaries in multi-turn conversations"
    )


class AgentletMetadata(BaseModel):
    """Agentlet metadata."""

    name: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$",
        description=(
            "Agentlet name. Must start with a letter or digit; may contain "
            "letters, digits, underscores, and hyphens; max 128 chars."
        ),
    )
    version: str = Field(default="1.0.0", description="Agentlet version")


class OTELConfig(BaseModel):
    """OpenTelemetry configuration."""

    enabled: bool = Field(default=False, description="Enable OTEL trace export")
    otlp_endpoint: Optional[str] = Field(
        None,
        description="OTLP base endpoint URL (used as fallback if signal-specific endpoints not set)",
    )
    otlp_traces_endpoint: Optional[str] = Field(
        None,
        description="OTLP traces endpoint URL (overrides otlp_endpoint for traces)",
    )
    otlp_metrics_endpoint: Optional[str] = Field(
        None,
        description="OTLP metrics endpoint URL (overrides otlp_endpoint for metrics)",
    )
    otlp_headers: dict[str, str] = Field(
        default_factory=dict, description="OTLP headers"
    )
    console_exporter: bool = Field(
        default=False, description="Enable console export for debugging"
    )
    sampler: Optional[
        Literal["always_on", "always_off", "traceidratio", "parentbased_always_on"]
    ] = Field(None, description="Trace sampler type")
    sampler_arg: Optional[float] = Field(
        None, description="Sampler argument (e.g., 0.1 for 10% sampling)"
    )
    enable_metrics: bool = Field(default=False, description="Enable metrics export")
    trace_attributes: dict[str, Any] = Field(
        default_factory=dict, description="Custom trace attributes"
    )


class ObservabilityConfig(BaseModel):
    """Observability configuration."""

    otel: OTELConfig = Field(default_factory=OTELConfig)  # type: ignore[arg-type]


class SubAgentletConfig(BaseModel):
    """Configuration for a sub-agentlet used as a tool by an orchestrator agentlet.

    Sub-agentlets are specialized agents that an orchestrator can delegate tasks to.
    They run in-process as Strands tools, each with their own system prompt, tools,
    and optionally a different model from the orchestrator.

    Example YAML::

        sub_agentlets:
          - name: research_agent
            description: "Searches and summarizes factual information on any topic"
            system_prompt: "You are a research specialist..."
            tools: ["http_request"]

          - name: code_reviewer
            description: "Reviews code for bugs and quality issues"
            system_prompt: "You are an expert code reviewer..."
            model:
              provider: bedrock
              model_id: claude-haiku-4-5
            tools: ["file_editor"]
    """

    name: str = Field(
        ...,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]{0,127}$",
        description=(
            "Tool name exposed to the orchestrator. "
            "Must be unique across all sub-agentlets and other tools. "
            "Must be a valid Python identifier (letters/digits/underscores, "
            "no leading digit, no hyphens) — agentlet-core registers it as a callable."
        ),
    )
    description: str = Field(
        ...,
        description=(
            "Tool docstring shown to the orchestrator LLM when deciding which "
            "sub-agentlet to call. Be specific — vague descriptions lead to poor routing."
        ),
    )
    system_prompt: str = Field(
        ...,
        description="System prompt defining this sub-agentlet's specialization and behaviour.",
    )
    model: Optional[ModelConfig] = Field(
        None,
        description=(
            "Model configuration for this sub-agentlet. "
            "If not specified, inherits the orchestrator's model."
        ),
    )
    tools: list[str] = Field(
        default_factory=list,
        description="Strands default tools to load (e.g. 'http_request', 'file_editor').",
    )
    mcp_tools: list[MCPToolConfig] = Field(
        default_factory=list,
        description="MCP tool servers available to this sub-agentlet.",
    )
    output: OutputConfig = Field(
        default_factory=lambda: OutputConfig(
            show_messages=False,
            show_reasoning=False,
            show_tool_calls=False,
        ),
        description=(
            "Output display options for this sub-agentlet's execution. "
            "All options default to False (silent) — the orchestrator's own output "
            "is displayed instead. Set show_messages/show_reasoning/show_tool_calls "
            "to True to see the sub-agentlet's internal execution inline."
        ),
    )


class SwarmParticipantConfig(BaseModel):
    """Configuration for one agent type in a swarm panel.

    A single ``SwarmParticipantConfig`` describes a *type* of agent.  When
    ``count > 1`` the runtime creates multiple instances, each with a unique
    name suffix (``{name}_1``, ``{name}_2``, …).

    Example YAML::

        participants:
          - name: solutions_architect
            count: 2
            description: "Designs architecture and evaluates trade-offs"
            system_prompt: "You are a senior solutions architect..."
            tools: [http_request]
    """

    name: str = Field(
        ...,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]{0,127}$",
        description=(
            "Base name for this agent type. Instances get a ``_N`` suffix when "
            "``count > 1`` (e.g. ``solutions_architect_1``). "
            "Must be a valid Python identifier — expanded node names must also "
            "be valid identifiers."
        ),
    )
    count: int = Field(
        default=1,
        ge=1,
        description="Number of identical instances to create (default: 1).",
    )
    description: str = Field(
        ...,
        description=(
            "Shown to peer agents in the swarm's shared context so they know "
            "when to hand off to this agent type. Be specific."
        ),
    )
    system_prompt: str = Field(
        ...,
        description="Specialisation instructions for this agent type.",
    )
    model: Optional[ModelConfig] = Field(
        None,
        description=(
            "Model override for this participant. "
            "Inherits the top-level model when absent."
        ),
    )
    tools: list[str] = Field(
        default_factory=list,
        description="Strands default tools (e.g. 'http_request', 'shell').",
    )
    mcp_tools: list[MCPToolConfig] = Field(
        default_factory=list,
        description="MCP tool servers for this participant.",
    )


class SwarmConfig(BaseModel):
    """Declarative swarm configuration.

    When present on ``AgentletConfig``, the agentlet runs as a
    ``strands.multiagent.Swarm`` instead of a single agent.  Each
    ``SwarmParticipantConfig`` in ``participants`` is expanded into one or more
    ``Agent`` instances (determined by ``count``) and registered as swarm nodes.

    Safety parameters map 1:1 to ``strands.multiagent.Swarm.__init__``.

    Example YAML::

        swarm:
          entry_point: solutions_architect
          max_handoffs: 30
          participants:
            - name: solutions_architect
              count: 2
              description: "Architecture and design"
              system_prompt: "You are a solutions architect..."
    """

    participants: list[SwarmParticipantConfig] = Field(
        ...,
        min_length=1,
        description="Agent types in the panel. At least one required.",
    )
    entry_point: Optional[str] = Field(
        None,
        description=(
            "Base name of the participant that receives the initial prompt. "
            "Resolves to the first instance of that type "
            "(no suffix if count=1, ``_1`` suffix if count>1). "
            "Defaults to the first participant type."
        ),
    )
    max_handoffs: int = Field(
        default=20,
        ge=0,
        description="Maximum total handoffs before the swarm halts (default: 20).",
    )
    max_iterations: int = Field(
        default=20,
        ge=0,
        description="Maximum total agent iterations (default: 20).",
    )
    execution_timeout: float = Field(
        default=900.0,
        gt=0,
        description="Total swarm wall-clock time limit in seconds (default: 900).",
    )
    node_timeout: float = Field(
        default=300.0,
        gt=0,
        description="Per-agent turn time limit in seconds (default: 300).",
    )
    repetitive_handoff_detection_window: int = Field(
        default=0,
        ge=0,
        description="Window size for loop detection (default: 0 = disabled, matches Strands SDK).",
    )
    repetitive_handoff_min_unique_agents: int = Field(
        default=0,
        ge=0,
        description="Minimum unique agents required in the detection window (default: 0 = disabled, matches Strands SDK).",
    )

    @model_validator(mode="after")
    def validate_entry_point(self) -> "SwarmConfig":
        """Ensure entry_point names an actual participant."""
        if self.entry_point is not None:
            participant_names = {p.name for p in self.participants}
            if self.entry_point not in participant_names:
                raise ValueError(
                    f"entry_point '{self.entry_point}' not found in participants: "
                    f"{sorted(participant_names)}"
                )
        return self


class AgentletConfig(BaseModel):
    """Complete agentlet configuration."""

    agentlet: AgentletMetadata = Field(..., description="Agentlet metadata")
    prompt: Optional[str] = Field(None, description="Default user prompt")
    system_prompt: str = Field(..., description="System prompt / instructions")
    model: ModelConfig = Field(..., description="Model configuration")
    tools: list[str] = Field(default_factory=list, description="Tools to load")
    mcp_tools: list[MCPToolConfig] = Field(
        default_factory=list, description="MCP tools configuration"
    )
    sub_agentlets: list[SubAgentletConfig] = Field(
        default_factory=list,
        description=(
            "Sub-agentlets available as tools to this orchestrator. "
            "Each sub-agentlet is a specialized agent the orchestrator can delegate to."
        ),
    )
    swarm: Optional[SwarmConfig] = Field(
        None,
        description=(
            "Swarm configuration. When set, the agentlet runs as a peer-to-peer "
            "``strands.multiagent.Swarm`` instead of a single agent. "
            "Cannot be combined with ``sub_agentlets``."
        ),
    )
    resource_limits: ResourceLimits = Field(
        default_factory=ResourceLimits, description="Resource limits"
    )
    output: OutputConfig = Field(
        default_factory=OutputConfig, description="Output configuration"
    )
    observability: ObservabilityConfig = Field(
        default_factory=ObservabilityConfig, description="Observability configuration"
    )

    @model_validator(mode="after")
    def validate_swarm_not_combined_with_sub_agentlets(self) -> "AgentletConfig":
        """Swarm and sub_agentlets are mutually exclusive patterns."""
        if self.swarm is not None and self.sub_agentlets:
            raise ValueError(
                "Cannot combine 'swarm' and 'sub_agentlets' in the same config. "
                "Use the swarm pattern for peer-to-peer coordination, or "
                "sub_agentlets for orchestrator-as-tool pattern — not both."
            )
        return self
