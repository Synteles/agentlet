# Configuration System

This document details the configuration loading, validation, and override mechanisms in agentlet-core.

## Overview

The configuration system provides a flexible, validated approach to defining agentlet behavior through YAML/JSON files with CLI override support and remote loading capabilities.

**Key Features:**
- Declarative YAML/JSON configuration
- Pydantic schema validation
- Multi-location search paths
- Environment variable expansion
- CLI argument override
- Remote configuration from Synteles Platform API
- Type-safe configuration access

## Configuration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Configuration Flow                          │
└─────────────────────────────────────────────────────────────────┘

  CLI Arguments                Config File              Remote URL
       │                            │                        │
       │                            │                        │
       ▼                            ▼                        ▼
  ┌─────────┐                 ┌──────────┐          ┌──────────────┐
  │ Click   │                 │  Loader  │          │ HTTP Client  │
  │ Parser  │                 │  Search  │          │ + Auth       │
  └────┬────┘                 └────┬─────┘          └──────┬───────┘
       │                           │                        │
       │                           ▼                        │
       │                    ┌─────────────┐                 │
       │                    │ YAML/JSON   │                 │
       │                    │ Parser      │                 │
       │                    └─────┬───────┘                 │
       │                          │                         │
       │                          ▼                         │
       │                    ┌─────────────┐                 │
       │                    │ Environment │                 │
       │                    │ Expansion   │◀────────────────┘
       │                    └─────┬───────┘
       │                          │
       │                          ▼
       │                    ┌─────────────┐
       │                    │  Pydantic   │
       │                    │ Validation  │
       │                    └─────┬───────┘
       │                          │
       └─────────────────────────▶│
                                  ▼
                          ┌───────────────┐
                          │ AgentletConfig│
                          └───────────────┘
```

## Configuration Schema

The configuration is defined using Pydantic models in `config/models.py`.

### AgentletConfig (Root)

```python
class AgentletConfig(BaseModel):
    """Complete agentlet configuration."""

    agentlet: AgentletMetadata      # Name and version
    prompt: Optional[str]           # Default user prompt
    system_prompt: str              # System instructions (required)
    model: ModelConfig              # LLM configuration (required)
    tools: list[str]                # Default tools list
    mcp_tools: list[MCPToolConfig]  # MCP tools configuration
    resource_limits: ResourceLimits # Execution constraints
    output: OutputConfig            # Display preferences
    observability: ObservabilityConfig  # OTEL configuration
```

### AgentletMetadata

```python
class AgentletMetadata(BaseModel):
    """Agentlet metadata."""
    name: str                       # Agentlet name (required)
    version: str = "1.0.0"          # Version (default: "1.0.0")
```

### ModelConfig

```python
class ModelConfig(BaseModel):
    """LLM model configuration."""
    provider: str                   # Provider (e.g., "bedrock", "openai")
    model_id: str                   # Model identifier
    parameters: dict[str, Any]      # Model-specific parameters
    retry: RetryConfig              # Retry configuration
```

#### RetryConfig

```python
class RetryConfig(BaseModel):
    """Retry configuration for handling transient errors."""
    max_retries: int = 5                    # Maximum retry attempts
    initial_retry_interval: float = 30.0    # Initial wait (seconds)
    backoff_factor: float = 2.0             # Exponential factor
    max_retry_interval: float = 300.0       # Max wait (seconds)
    retry_on_errors: list[str] = [          # Retryable error types
        "RateLimitError",
        "EventLoopException",
        "APIConnectionError",
        "APITimeoutError",
        "litellm.RateLimitError",
    ]
```

### MCPToolConfig

```python
class MCPToolConfig(BaseModel):
    """MCP tool configuration."""
    name: str                               # Tool name/identifier
    server: Literal["stdio", "http", "sse"] # Transport type

    # stdio-specific
    command: Optional[str]                  # Command to execute
    args: list[str] = []                    # Command arguments

    # http/sse-specific
    url: Optional[str]                      # Server URL
    headers: dict[str, str] = {}            # HTTP headers
    api_key_env: Optional[str]              # API key env var name

    # Common
    env: dict[str, str] = {}                # Environment variables

    # Tool filtering and prefixing
    prefix: Optional[str]                   # Tool name prefix
    tool_filters: Optional[dict[str, list[str]]]  # allowed/rejected lists
```

**Validation:**
- `stdio` requires `command`
- `http`/`sse` require `url`
- `tool_filters` only accepts `allowed` and `rejected` keys

### ResourceLimits

```python
class ResourceLimits(BaseModel):
    """Resource limits for agentlet execution."""
    max_execution_time: int = 300   # Max time (seconds)
    max_tokens: int = 10000         # Token limit
    max_tool_calls: int = 20        # Max tool calls
```

### OutputConfig

```python
class OutputConfig(BaseModel):
    """Output configuration."""
    format: Literal["markdown", "json", "text"] = "markdown"
    show_messages: bool = True          # Show assistant messages
    show_reasoning: bool = True         # Show extended thinking
    show_tool_calls: bool = True        # Show tool invocations
    show_turn_boundaries: bool = False  # Show turn indicators
```

### ObservabilityConfig

```python
class ObservabilityConfig(BaseModel):
    """Observability configuration."""
    otel: OTELConfig  # OpenTelemetry settings

class OTELConfig(BaseModel):
    """OpenTelemetry configuration."""
    enabled: bool = False                           # Enable OTEL
    otlp_endpoint: Optional[str]                    # Base endpoint
    otlp_traces_endpoint: Optional[str]             # Traces endpoint
    otlp_metrics_endpoint: Optional[str]            # Metrics endpoint
    otlp_headers: dict[str, str] = {}               # OTLP headers
    console_exporter: bool = False                  # Console debug output
    sampler: Optional[Literal[...]]                 # Trace sampler
    sampler_arg: Optional[float]                    # Sampler parameter
    enable_metrics: bool = False                    # Enable metrics
    trace_attributes: dict[str, Any] = {}           # Custom attributes
```

## Configuration Loading

### ConfigLoader

The `ConfigLoader` class (`config/loader.py`) handles all configuration loading logic.

#### Load Methods

```python
class ConfigLoader:
    """Loads and validates agentlet configurations."""

    SEARCH_PATHS = [
        Path.cwd(),                         # Current working directory
        Path.home() / ".synteles" / "agentlets",  # User home
        Path.cwd() / ".synteles" / "agentlets",   # Local project
    ]

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> AgentletConfig:
        """
        Load agentlet configuration from file or remote URL.

        Args:
            config_path: Explicit path, agentlet name, or URL

        Returns:
            Validated AgentletConfig instance

        Raises:
            FileNotFoundError: Config not found
            ValidationError: Config validation fails
            ValueError: Invalid format or URL
            RuntimeError: Remote API request fails
        """
```

### Loading Decision Tree

```
config_path provided?
  │
  ├─ Yes ─▶ Is it a URL? (http:// or https://)
  │          │
  │          ├─ Yes ─▶ Load from remote API
  │          │
  │          └─ No ─▶ Is it a valid file path?
  │                   │
  │                   ├─ Yes ─▶ Load from file
  │                   │
  │                   └─ No ─▶ Is it a name (no / or \)?
  │                            │
  │                            ├─ Yes ─▶ Search for {name}.yaml
  │                            │
  │                            └─ No ─▶ FileNotFoundError
  │
  └─ No ─▶ Search default locations
           └─▶ Return first *.yaml, *.yml, or *.json found
```

### Local File Loading

#### Search Path Resolution

```python
@classmethod
def _find_config_file(cls) -> Path:
    """Search for config file in default locations."""
    for search_path in cls.SEARCH_PATHS:
        if not search_path.exists():
            continue

        # Look for .yaml or .json files
        for pattern in ["*.yaml", "*.yml", "*.json"]:
            matches = list(search_path.glob(pattern))
            if matches:
                return matches[0]  # Return first match

    raise FileNotFoundError(
        f"No agentlet config file found in search paths: {cls.SEARCH_PATHS}"
    )
```

**Search order:**
1. Current working directory
2. `~/.synteles/agentlets/`
3. `./.synteles/agentlets/`

**File patterns:** `*.yaml`, `*.yml`, `*.json`

#### Agentlet Name Resolution

```python
@classmethod
def _find_agentlet_by_name(cls, name: str) -> Path:
    """Search for agentlet by name in search paths."""
    for search_path in cls.SEARCH_PATHS:
        if not search_path.exists():
            continue

        # Look for {name}.yaml first, then {name}.yml
        for ext in [".yaml", ".yml"]:
            config_file = search_path / f"{name}{ext}"
            if config_file.exists():
                return config_file

    raise FileNotFoundError(
        f"Agentlet '{name}' not found in search paths: {cls.SEARCH_PATHS}"
    )
```

**Example:**
```bash
# Searches for simple-assistant.yaml in search paths
agentlet-core --agentlet simple-assistant
```

#### File Parsing

```python
@classmethod
def _load_from_file(cls, file_path: Path) -> AgentletConfig:
    """Load and parse config file."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Expand environment variables in content
    content = os.path.expandvars(content)

    # Parse based on file extension
    suffix = file_path.suffix.lower()
    if suffix in [".yaml", ".yml"]:
        data = yaml.safe_load(content)
    elif suffix == ".json":
        data = json.loads(content)
    else:
        raise ValueError(f"Unsupported config format: {suffix}")

    # Validate with Pydantic
    return AgentletConfig(**data)
```

**Key steps:**
1. Read file content
2. Expand environment variables (`$VAR`, `${VAR}`)
3. Parse YAML or JSON
4. Validate with Pydantic
5. Return AgentletConfig instance

## Environment Variable Expansion

Configuration files support environment variable substitution.

### Supported Formats

```yaml
# $VAR format
model:
  provider: $PROVIDER
  model_id: $MODEL_ID

# ${VAR} format
mcp_tools:
  - name: filesystem
    command: npx
    env:
      ALLOWED_DIRECTORIES: ${WORK_DIR}
      API_KEY: ${API_KEY}
```

### Expansion Timing

Environment variable expansion happens **before** YAML/JSON parsing:

```python
# Read file content
content = f.read()

# Expand environment variables
content = os.path.expandvars(content)

# Then parse YAML/JSON
data = yaml.safe_load(content)
```

**Benefits:**
- Variables work anywhere in the config
- Supports complex values
- No special handling needed

### Special Variables

#### ${WORK_DIR}

`${WORK_DIR}` is expanded at runtime by `MCPToolsManager`:

```python
# In MCPToolsManager._create_stdio_client()
for key, value in env.items():
    env[key] = value.replace("${WORK_DIR}", self.working_dir)

# In command arguments
expanded_args = [
    arg.replace("${WORK_DIR}", self.working_dir) for arg in config.args
]
```

**Usage:**
```yaml
mcp_tools:
  - name: filesystem
    server: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "${WORK_DIR}"]
    env:
      ALLOWED_DIRECTORIES: ${WORK_DIR}
```

## CLI Override Mechanism

Command-line arguments override configuration file values.

### Override Precedence

```
CLI Arguments > Config File > Defaults
```

### Override Implementation

```python
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
```

### Supported Overrides

#### Prompt Override

```python
if prompt:
    config.prompt = prompt
```

```bash
agentlet-core --agentlet my-agentlet --prompt "Say hello"
```

#### Model Override

```python
if model:
    # Parse model string (e.g., "bedrock/claude-sonnet-4-6")
    provider, _, model_id = model.partition("/")
    if model_id:
        config.model.provider = provider
        config.model.model_id = model_id
    else:
        config.model.model_id = model
```

**Examples:**
```bash
# Full format
agentlet-core --model bedrock/claude-sonnet-4-6

# Model ID only (keeps provider from config)
agentlet-core --model claude-sonnet-4-6
```

#### Resource Limits Override

```python
if timeout:
    config.resource_limits.max_execution_time = timeout

if max_tokens:
    config.resource_limits.max_tokens = max_tokens
```

```bash
agentlet-core --timeout 600 --max-tokens 20000
```

#### Output Format Override

```python
if output_format and output_format in ("markdown", "json", "text"):
    config.output.format = output_format
```

```bash
agentlet-core --output-format json
```

#### Retry Configuration Override

```python
if max_retries is not None:
    config.model.retry.max_retries = max_retries

if initial_retry_interval is not None:
    config.model.retry.initial_retry_interval = initial_retry_interval

if backoff_factor is not None:
    config.model.retry.backoff_factor = backoff_factor
```

```bash
agentlet-core --max-retries 10 --initial-retry-interval 60.0 --backoff-factor 1.5
```

#### OTEL Configuration Override

```python
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
```

```bash
agentlet-core --otel-enabled \
  --otlp-traces-endpoint http://localhost:4318/v1/traces \
  --otel-console
```

## Configuration Examples

### Minimal Configuration

```yaml
agentlet:
  name: simple-assistant
  version: 1.0.0

model:
  provider: anthropic
  model_id: claude-sonnet-4-6

system_prompt: "You are a helpful assistant."

resource_limits:
  max_execution_time: 300
  max_tokens: 10000

output:
  format: markdown
```

### Full Configuration

```yaml
agentlet:
  name: advanced-agent
  version: 2.0.0

prompt: "Analyze the codebase and provide insights"

system_prompt: |
  You are an expert code analyst with deep knowledge of software architecture.
  Provide detailed, actionable insights.

model:
  provider: bedrock
  model_id: claude-sonnet-4-6
  parameters:
    temperature: 0.7
    top_p: 0.9
  retry:
    max_retries: 5
    initial_retry_interval: 30.0
    backoff_factor: 2.0
    max_retry_interval: 300.0
    retry_on_errors:
      - RateLimitError
      - EventLoopException

tools:
  - bash
  - file_editor
  - computer

mcp_tools:
  - name: filesystem
    server: stdio
    command: npx
    args:
      - "-y"
      - "@modelcontextprotocol/server-filesystem"
      - "${WORK_DIR}"
    env:
      ALLOWED_DIRECTORIES: ${WORK_DIR}
    prefix: fs_

  - name: web_search
    server: http
    url: https://api.example.com/mcp
    api_key_env: SEARCH_API_KEY
    headers:
      User-Agent: agentlet-core/1.0
    tool_filters:
      allowed:
        - search_web
        - fetch_url
      rejected:
        - admin_*

resource_limits:
  max_execution_time: 600
  max_tokens: 20000
  max_tool_calls: 50

output:
  format: markdown
  show_messages: true
  show_reasoning: true
  show_tool_calls: true
  show_turn_boundaries: true

observability:
  otel:
    enabled: true
    otlp_traces_endpoint: http://localhost:4318/v1/traces
    otlp_metrics_endpoint: http://localhost:4318/v1/metrics
    otlp_headers:
      x-api-key: ${OTEL_API_KEY}
    console_exporter: false
    sampler: always_on
    enable_metrics: true
    trace_attributes:
      environment: production
      team: platform
```

### Environment Variable Usage

```yaml
# .env file
PROVIDER=bedrock
MODEL_ID=claude-sonnet-4-6
SEARCH_API_KEY=sk-1234567890
WORK_DIR=/path/to/project

# Config file with variables
model:
  provider: ${PROVIDER}
  model_id: ${MODEL_ID}

mcp_tools:
  - name: web_search
    server: http
    url: https://api.example.com/mcp
    api_key_env: SEARCH_API_KEY
    env:
      WORK_DIR: ${WORK_DIR}
```

## Validation and Error Handling

### Pydantic Validation

Configuration validation happens automatically via Pydantic:

```python
try:
    config = AgentletConfig(**data)
except ValidationError as e:
    # Detailed validation errors
    print(e)
    # Example:
    # 2 validation errors for AgentletConfig
    # agentlet.name
    #   field required (type=value_error.missing)
    # model.provider
    #   field required (type=value_error.missing)
```

### Field Validators

#### ModelConfig.parameters

```python
@field_validator("parameters", mode="before")
@classmethod
def validate_parameters(cls, v: Any) -> dict[str, Any]:
    if v is None:
        return {}
    if isinstance(v, dict):
        return v
    return {}
```

**Ensures:** `parameters` is always a dict (even if null/missing)

#### MCPToolConfig Validation

```python
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
```

**Validates:**
- stdio servers have `command`
- http/sse servers have `url`
- tool_filters only use valid keys

### Common Validation Errors

**Missing required field:**
```yaml
# Error: agentlet.name required
agentlet:
  version: 1.0.0

# Fix:
agentlet:
  name: my-agent
  version: 1.0.0
```

**Invalid server configuration:**
```yaml
# Error: command required for stdio
mcp_tools:
  - name: filesystem
    server: stdio

# Fix:
mcp_tools:
  - name: filesystem
    server: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem"]
```

**Invalid tool_filters:**
```yaml
# Error: invalid key 'blocked'
mcp_tools:
  - name: web_search
    server: http
    url: https://api.example.com
    tool_filters:
      blocked: ["admin_*"]

# Fix:
mcp_tools:
  - name: web_search
    server: http
    url: https://api.example.com
    tool_filters:
      rejected: ["admin_*"]
```

## Extension Patterns

### Adding New Configuration Fields

1. **Add to Pydantic model:**
```python
class AgentletConfig(BaseModel):
    # ... existing fields ...
    new_feature: NewFeatureConfig = Field(
        default_factory=NewFeatureConfig,
        description="New feature configuration"
    )
```

2. **Define nested model:**
```python
class NewFeatureConfig(BaseModel):
    """New feature configuration."""
    enabled: bool = False
    parameter: str = "default"
```

3. **Add CLI override (if needed):**
```python
@click.option(
    "--new-feature-enabled",
    is_flag=True,
    help="Enable new feature",
)
def cli(..., new_feature_enabled: bool) -> None:
    # ...
    config = override_config(..., new_feature_enabled=new_feature_enabled)

def override_config(..., new_feature_enabled: bool) -> AgentletConfig:
    if new_feature_enabled:
        config.new_feature.enabled = True
    return config
```

4. **Update example configs:**
```yaml
# examples/full-config.yaml
new_feature:
  enabled: true
  parameter: custom_value
```

5. **Add tests:**
```python
def test_new_feature_config():
    config = AgentletConfig(
        agentlet=AgentletMetadata(name="test"),
        system_prompt="test",
        model=ModelConfig(provider="test", model_id="test"),
        new_feature=NewFeatureConfig(enabled=True),
    )
    assert config.new_feature.enabled is True
```

### Custom Validators

Add custom validation logic:

```python
class CustomConfig(BaseModel):
    value: int

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: int) -> int:
        if v < 0:
            raise ValueError("value must be non-negative")
        return v
```

### Configuration Transformation

Transform configuration after loading:

```python
class ConfigLoader:
    @classmethod
    def load_with_transform(cls, config_path: str) -> AgentletConfig:
        config = cls.load(config_path)

        # Apply transformations
        if config.model.provider == "openai":
            # Apply OpenAI-specific defaults
            config.model.parameters.setdefault("temperature", 0.7)

        return config
```

## Best Practices

### 1. Use Environment Variables for Secrets

```yaml
# Good
mcp_tools:
  - name: web_search
    api_key_env: SEARCH_API_KEY

# Bad (hardcoded secret)
mcp_tools:
  - name: web_search
    headers:
      Authorization: "Bearer sk-1234567890"
```

### 2. Version Your Configurations

```yaml
agentlet:
  name: my-agent
  version: 2.0.0  # Increment when config changes
```

### 3. Provide Defaults

```yaml
# Minimal config with sensible defaults
agentlet:
  name: simple-agent

model:
  provider: anthropic
  model_id: claude-sonnet-4-6

system_prompt: "You are a helpful assistant."

# Other fields use defaults from Pydantic models
```

### 4. Document Complex Configurations

```yaml
# Advanced configuration for production use
agentlet:
  name: production-agent
  version: 1.0.0

# Use Claude Sonnet 4.5 for best reasoning
model:
  provider: bedrock
  model_id: claude-sonnet-4-6
  parameters:
    # Conservative temperature for consistent output
    temperature: 0.3
```

### 5. Validate Before Deployment

```bash
# Test configuration loading
python -c "from agentlet_core.config.loader import ConfigLoader; \
           ConfigLoader.load('my-config.yaml')"
```

### 6. Use Search Paths for Organization

```
~/.synteles/agentlets/
  ├── development.yaml
  ├── staging.yaml
  └── production.yaml
```

```bash
# Load by name
agentlet-core --agentlet production --prompt "Task"
```

## Related Documentation

- [Architecture Overview](./overview.md) - System architecture
- [Agent Lifecycle](./agent-lifecycle.md) - Lifecycle details
- [Tool Management](./tool-management.md) - Tool configuration
- [CLAUDE.md](../../CLAUDE.md) - Developer guide
