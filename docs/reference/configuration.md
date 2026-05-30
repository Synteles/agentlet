# Configuration Reference

Complete reference for agentlet configuration files.

## Configuration File Format

Agentlet-core supports YAML and JSON configuration files.

**Supported extensions:**
- `.yaml`
- `.yml`
- `.json`

## Configuration Structure

```yaml
agentlet:              # Metadata (required)
prompt:                # Default prompt (optional)
system_prompt:         # Agent instructions (required)
model:                 # LLM configuration (required)
tools:                 # Default Strands tools (optional)
mcp_tools:             # MCP protocol tools (optional)
sub_agentlets:         # Inline sub-agentlets as tools (optional)
resource_limits:       # Execution constraints (optional)
output:                # Output configuration (optional)
observability:         # Telemetry configuration (optional)
```

## Agentlet Metadata

```yaml
agentlet:
  name: "my-assistant"     # Required: Identifier
  version: "1.0.0"         # Optional: Semantic version (default: "1.0.0")
```

**Fields:**
- `name` (string, required): Agentlet identifier
- `version` (string, optional): Semantic version (default: `"1.0.0"`)

## Prompt

```yaml
prompt: "Your default task here"
```

**Optional**: Default user prompt if not provided via CLI `--prompt`.

## System Prompt

```yaml
system_prompt: |
  You are a helpful assistant specialized in software development.
  You have access to bash, file editing, and filesystem tools.
  Always explain your reasoning before taking actions.
```

**Required**: Instructions for the agent's behavior and capabilities.

**Best practices:**
- Be specific about the agent's role
- Mention available tools
- Set expectations for response format
- Include any constraints or guidelines

## Model Configuration

```yaml
model:
  provider: "anthropic"              # Required
  model_id: "claude-sonnet-4-6"      # Required
  parameters:                        # Optional
    temperature: 0.7
    max_tokens: 4096
    top_p: 0.9
  retry:                             # Optional
    max_retries: 5
    initial_retry_interval: 30.0
    backoff_factor: 2.0
    max_retry_interval: 300.0
```

### Provider and Model

**Fields:**
- `provider` (string, required): LLM provider name
- `model_id` (string, required): Model identifier

**Supported providers:**
- `anthropic`: Anthropic API
- `bedrock`: AWS Bedrock
- `openai`: OpenAI API
- `azure`: Azure OpenAI
- `vertex_ai`: Google Vertex AI

**Model string format:** `provider/model_id`

**Examples:**
```yaml
# Anthropic
provider: "anthropic"
model_id: "claude-sonnet-4-6"

# AWS Bedrock
provider: "bedrock"
model_id: "claude-sonnet-4-6"

# OpenAI
provider: "openai"
model_id: "gpt-4"

# Azure
provider: "azure"
model_id: "gpt-4"
```

### Model Parameters

**Common parameters:**
```yaml
parameters:
  temperature: 0.7        # Sampling temperature (0.0 - 1.0)
  max_tokens: 4096        # Maximum output tokens
  top_p: 0.9              # Nucleus sampling
  top_k: 40               # Top-k sampling (provider-specific)
```

**Provider-specific parameters:**
- Passed directly to LiteLLM
- See [LiteLLM docs](https://docs.litellm.ai/docs/completion/input) for full list

### Retry Configuration

```yaml
retry:
  max_retries: 5                      # Maximum retry attempts
  initial_retry_interval: 30.0        # Initial wait time (seconds)
  backoff_factor: 2.0                 # Exponential backoff multiplier
  max_retry_interval: 300.0           # Maximum wait time (seconds)
  retry_on_errors:                    # Error types to retry
    - "RateLimitError"
    - "EventLoopException"
    - "APIConnectionError"
    - "APITimeoutError"
    - "litellm.RateLimitError"
```

**Default behavior:**
- Exponential backoff: 30s → 60s → 120s → 240s → 300s
- API-suggested wait times: Extracts `retry-after` from errors
- Progressive backoff: Increases wait for repeated rate limits

## Default Tools

```yaml
tools:
  - "bash"           # Execute shell commands
  - "file_editor"    # Read/write files with edits
  - "computer"       # Computer control (screenshot, mouse, keyboard)
```

**Available tools:**
- `bash`: Shell command execution
- `file_editor`: File operations with precise editing
- `computer`: Computer vision and control

**Tool consent:** Automatically bypassed via `BYPASS_TOOL_CONSENT=true`.

## MCP Tools

### stdio Transport

```yaml
mcp_tools:
  - name: "filesystem"              # Required: Tool identifier
    server: "stdio"                 # Required: Transport type
    command: "npx"                  # Required: Command to run
    args:                           # Optional: Command arguments
      - "-y"
      - "@modelcontextprotocol/server-filesystem"
    env:                            # Optional: Environment variables
      ALLOWED_DIRECTORIES: "${WORK_DIR}"
      LOG_LEVEL: "info"
    prefix: "fs"                    # Optional: Tool name prefix
    tool_filters:                   # Optional: Filter tools
      allowed:
        - "read_file"
        - "write_file"
```

**Fields:**
- `name` (string, required): Identifier for this MCP server
- `server` (literal "stdio", required): Transport type
- `command` (string, required): Executable command
- `args` (list[string], optional): Command arguments
- `env` (dict[string, string], optional): Environment variables
- `prefix` (string, optional): Prefix for tool names
- `tool_filters` (object, optional): Filter which tools to load

**Environment variable expansion:**
- `${WORK_DIR}`: Agentlet working directory
- `$VAR` or `${VAR}`: Any environment variable

### HTTP Transport

```yaml
mcp_tools:
  - name: "api-service"             # Required
    server: "http"                  # Required
    url: "https://api.example.com/mcp/"  # Required
    api_key_env: "API_KEY"          # Optional: Env var for API key
    headers:                        # Optional: Custom headers
      X-Custom-Header: "value"
      Authorization: "Bearer token"
    prefix: "api"                   # Optional
    tool_filters:                   # Optional
      rejected:
        - "dangerous_operation"
```

**Fields:**
- `name` (string, required): Identifier
- `server` (literal "http", required): Transport type
- `url` (string, required): HTTP endpoint URL
- `api_key_env` (string, optional): Environment variable name for API key
- `headers` (dict[string, string], optional): Custom HTTP headers
- `prefix` (string, optional): Tool name prefix
- `tool_filters` (object, optional): Filter tools

**Authentication:**
- `api_key_env`: Automatically adds `Authorization: Bearer {api_key}`
- Custom auth: Set `Authorization` header directly

### SSE Transport

```yaml
mcp_tools:
  - name: "realtime"                # Required
    server: "sse"                   # Required
    url: "http://localhost:8000/sse"  # Required
    prefix: "rt"                    # Optional
    tool_filters:                   # Optional
      allowed:
        - "get_updates"
```

**Fields:**
- `name` (string, required): Identifier
- `server` (literal "sse", required): Transport type
- `url` (string, required): SSE endpoint URL
- `prefix` (string, optional): Tool name prefix
- `tool_filters` (object, optional): Filter tools

**Note:** SSE client doesn't support custom headers. Use URL query params for auth: `?token=xxx`

### Tool Filters

**Allow specific tools:**
```yaml
tool_filters:
  allowed:
    - "read_file"
    - "write_file"
    - "list_directory"
```

**Reject specific tools:**
```yaml
tool_filters:
  rejected:
    - "delete_file"
    - "format_disk"
```

**Validation:**
- Only `allowed` and `rejected` are valid keys — any other key is a validation error
- Both `allowed` and `rejected` may be specified together (allow-list takes precedence; rejected acts as an additional exclusion within the allowed set)
- `tool_filters` can be omitted entirely (all tools are loaded)

### Tool Name Prefixing

Prevent naming conflicts between multiple MCP servers:

```yaml
mcp_tools:
  - name: "filesystem"
    prefix: "fs"      # Tools: fs_read_file, fs_write_file

  - name: "database"
    prefix: "db"      # Tools: db_query, db_insert
```

## Sub-Agentlets (Multiagency)

Declare specialised sub-agents inline. The orchestrator's LLM can call them as tools to delegate work.

```yaml
sub_agentlets:
  - name: research_agent           # Required: tool name the orchestrator calls
    description: >                 # Required: tool docstring shown to the LLM
      Searches and summarises factual information on any topic.
      Use for research, fact-checking, and information retrieval.
    system_prompt: |               # Required: sub-agent specialisation
      You are a research specialist. Find accurate, up-to-date information
      and return a structured summary with key findings.
    model:                         # Optional: override orchestrator's model
      provider: bedrock
      model_id: claude-haiku-4-5
      parameters:
        temperature: 0.3
    tools:                         # Optional: Strands default tools
      - "http_request"
    mcp_tools:                     # Optional: MCP tools (same schema as top-level)
      - name: "search"
        server: "http"
        url: "https://search.example.com/mcp/"
        api_key_env: "SEARCH_API_KEY"
```

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | ✅ | Tool name used by the orchestrator LLM to call this sub-agentlet. Must be unique. |
| `description` | string | ✅ | Tool docstring. The orchestrator LLM reads this when choosing which sub-agentlet to invoke. Be specific. |
| `system_prompt` | string | ✅ | Sub-agentlet's specialisation instructions. |
| `model` | ModelConfig | — | Model override. If absent, inherits the orchestrator's model. |
| `tools` | list[string] | — | Strands default tools (same values as top-level `tools`). |
| `mcp_tools` | list[MCPToolConfig] | — | MCP tools (same schema as top-level `mcp_tools`). |
| `output` | OutputConfig | — | Display options for the sub-agentlet's execution. All three fields default to `false` (silent). |

**Sub-agentlet `output` fields** (all default to `false`):
- `show_messages` — display the sub-agentlet's assistant messages inline
- `show_reasoning` — display the sub-agentlet's reasoning blocks inline
- `show_tool_calls` — display the sub-agentlet's tool calls inline

By default sub-agentlets run silently; the orchestrator's own output is displayed instead. Set any of the above to `true` to make a sub-agentlet's internal execution visible.

**How it works at runtime:**

1. `spawn()` initialises every sub-agentlet declared in `sub_agentlets` — resolves models, starts MCP servers, builds bare Strands agents, wraps each as a `@tool`.
2. Sub-agentlet tools are prepended to the orchestrator's tool list so the LLM sees them prominently.
3. When the orchestrator calls a sub-agentlet tool it passes a `query` string; the sub-agentlet processes it and returns a response string.
4. After execution, per-sub-agentlet statistics are logged:

```
[research_agent]   2.3s  |  1,240 in / 380 out  |  $0.000420
[writing_agent]    1.1s  |    890 in / 210 out  |  $0.000180
```

**OTel:** Sub-agent spans are automatically nested under the orchestrator's tool invocation span. Each span carries `sub_agentlet.name` and `sub_agentlet.parent_execution_id` attributes for filtering in your collector.

**Constraints:**
- `resource_limits`, `output`, and `observability` are orchestrator-level settings. Sub-agentlets do not have their own copies.
- Sub-agentlet MCP failures raise during `spawn()` — failing loudly rather than silently omitting a tool.
- Nested sub-agentlets (a sub-agentlet with its own `sub_agentlets`) are not supported.

**See:** [Multi-Agent Guide](multi-agent.md) for a full walkthrough with example.

## Swarm (Peer-to-Peer Multi-Agent)

Declare a declarative swarm of peer agents. **Cannot be combined with `sub_agentlets`** — they are mutually exclusive patterns.

```yaml
swarm:
  entry_point: solutions_architect   # Optional: first agent to receive the prompt
  max_handoffs: 20                   # Default: 20
  max_iterations: 20                 # Default: 20
  execution_timeout: 900.0           # Default: 900 s (total swarm wall-clock)
  node_timeout: 300.0                # Default: 300 s (per-agent turn)
  repetitive_handoff_detection_window: 0    # Default: 0 (disabled)
  repetitive_handoff_min_unique_agents: 0   # Default: 0 (disabled)
  participants:
    - name: solutions_architect       # Required: valid Python identifier
      count: 2                        # Default: 1
      description: "..."              # Required: shown to peer agents
      system_prompt: "..."            # Required
      model:                          # Optional: overrides top-level model
        provider: bedrock
        model_id: claude-haiku-4-5
      tools: [shell]                  # Optional
      mcp_tools: []                   # Optional
```

**Key fields:**
- `participants` (list, required): At least one participant type
- `entry_point` (string, optional): Base name of the participant that receives the initial prompt; defaults to the first participant
- `max_handoffs` / `max_iterations`: Safety limits; 0 = unlimited
- `repetitive_handoff_detection_window`: Set > 0 to enable loop detection (0 = disabled)
- `count`: Expand a participant type into `count` instances named `{name}_1`, `{name}_2`, etc.

**Swarm-specific runtime behaviour:**
- Top-level `mcp_tools` are **ignored** in swarm mode — declare MCP tools per participant under `swarm.participants[*].mcp_tools`
- Top-level `tools` are applied to the **entry-point agent only**; declare tools per participant for other agents

**See:** [Swarm Pattern Guide](swarm.md) for complete examples including dynamic and combined modes.

## Resource Limits

```yaml
resource_limits:
  max_execution_time: 300    # Seconds (default: 300)
  max_tokens: 10000          # Total tokens (default: 10000)
  max_tool_calls: 20         # Tool call limit (default: 20)
```

**Fields:**
- `max_execution_time` (int, optional): Maximum execution time in seconds
- `max_tokens` (int, optional): Maximum total tokens (input + output)
- `max_tool_calls` (int, optional): Maximum number of tool calls

**Behavior:**
- Timeout: Execution terminates if `max_execution_time` exceeded
- Token limit: Warning logged if exceeded (not enforced)
- Tool limit: Agent stops after `max_tool_calls` invocations

## Output Configuration

```yaml
output:
  format: "markdown"             # Output format (default: markdown)
  show_messages: true            # Show assistant messages (default: true)
  show_reasoning: true           # Show reasoning blocks (default: true)
  show_tool_calls: true          # Show tool calls (default: true)
  show_turn_boundaries: false    # Show turn indicators (default: false)
```

**Fields:**
- `format` (enum, optional): Output format
  - `"markdown"` (default): Rich markdown rendering
  - `"json"`: JSON output
  - `"text"`: Plain text
- `show_messages` (bool, optional): Display complete assistant messages per turn (default: `true`)
- `show_reasoning` (bool, optional): Display reasoning blocks for extended thinking (default: `true`)
- `show_tool_calls` (bool, optional): Display tool calls and results (default: `true`)
- `show_turn_boundaries` (bool, optional): Show turn boundary indicators for multi-turn conversations (default: `false`)

## Observability Configuration

```yaml
observability:
  otel:
    enabled: true                          # Enable OTEL (default: false)
    otlp_endpoint: "http://localhost:4318"  # Base OTLP endpoint
    otlp_traces_endpoint: "http://localhost:4318/v1/traces"  # Traces endpoint
    otlp_metrics_endpoint: "http://localhost:4318/v1/metrics"  # Metrics endpoint
    otlp_headers:                          # OTLP headers
      Authorization: "Bearer token"
    console_exporter: false                # Console export (default: false)
    sampler: "always_on"                   # Sampler type
    sampler_arg: 1.0                       # Sampler argument
    enable_metrics: false                  # Enable metrics (default: false)
    trace_attributes:                      # Custom trace attributes
      environment: "production"
      service.name: "agentlet-core"
```

**Fields:**
- `enabled` (bool, optional): Enable OpenTelemetry (default: false)
- `otlp_endpoint` (string, optional): Base OTLP endpoint (default: http://localhost:4318)
- `otlp_traces_endpoint` (string, optional): Traces-specific endpoint
- `otlp_metrics_endpoint` (string, optional): Metrics-specific endpoint
- `otlp_headers` (dict, optional): OTLP authentication headers
- `console_exporter` (bool, optional): Print traces to console (default: false)
- `sampler` (enum, optional): Trace sampler type
  - `"always_on"` (default): Export all traces
  - `"always_off"`: Export no traces
  - `"traceidratio"`: Export percentage of traces
  - `"parentbased_always_on"`: Follow parent trace decision
- `sampler_arg` (float, optional): Sampler argument (for traceidratio, 0.0-1.0)
- `enable_metrics` (bool, optional): Export metrics (default: false)
- `trace_attributes` (dict, optional): Custom attributes for all spans

**Endpoint precedence:**
1. Signal-specific endpoint (`otlp_traces_endpoint` or `otlp_metrics_endpoint`)
2. Base endpoint + signal path (`otlp_endpoint` + `/v1/traces`)
3. Environment variable (`OTEL_EXPORTER_OTLP_ENDPOINT`)
4. Default (`http://localhost:4318`)

## Environment Variable Expansion

Config files support environment variable expansion:

```yaml
mcp_tools:
  - name: "filesystem"
    env:
      API_KEY: "$MY_API_KEY"         # Expands to env var value
      WORK_DIR: "${WORK_DIR}"        # Special: agentlet working directory
      HOME: "${HOME}"                # User home directory
```

**Syntax:**
- `$VAR`: Simple expansion
- `${VAR}`: Braced expansion (recommended)

**Special variables:**
- `${WORK_DIR}`: Agentlet execution working directory

## Configuration Loading

### Search Paths

Agentlet-core searches for configs in this order:

1. **Explicit path**: `--agentlet /path/to/config.yaml` — loaded directly
2. **Name** (no `/` or `\` in the value): searched as `{name}.yaml` / `{name}.yml` in:
   - Current working directory (`CWD/`)
   - `~/.synteles/agentlets/`
   - `./.synteles/agentlets/`
3. **Auto-discovery** (no `--agentlet`): first `*.yaml`, `*.yml`, or `*.json` found in the same search paths

> **Note:** Name resolution (e.g. `--agentlet simple-assistant`) only matches `.yaml` and `.yml` files. JSON configs must be specified with an explicit path.

### Name Resolution

```bash
# Search for "simple-assistant.yaml" or "simple-assistant.yml" in search paths
agentlet-core --agentlet simple-assistant --prompt "Hello"

# Use explicit path (YAML or JSON)
agentlet-core --agentlet /path/to/config.yaml --prompt "Hello"
agentlet-core --agentlet /path/to/config.json --prompt "Hello"
```

### Environment Variables

**Required (provider-specific):**
```bash
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AZURE_API_KEY=...
```

**Optional:**
```bash
SYNTELES_EXEC_ID=<uuid4>    # Set execution ID for trace correlation (auto-generated if absent)
LITELLM_DEBUG=true          # Enable LiteLLM debug output
BYPASS_TOOL_CONSENT=true    # Auto-set by agentlet-core; skips interactive tool consent
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

`SYNTELES_EXEC_ID` is useful in CI/CD or orchestration systems where you want to correlate agentlet traces back to a parent pipeline run. Must be a valid UUID v4; if invalid, a new ID is generated and a warning is logged.


## CLI Override

CLI arguments override configuration file values:

```bash
# Override model
agentlet-core --agentlet my-agent.yaml --model "openai/gpt-4"

# Override timeout
agentlet-core --agentlet my-agent.yaml --timeout 120

# Override max tokens
agentlet-core --agentlet my-agent.yaml --max-tokens 8000

# Override output format
agentlet-core --agentlet my-agent.yaml --output-format json

# Override retry settings
agentlet-core --agentlet my-agent.yaml --max-retries 3 --backoff-factor 1.5
```

**Precedence:** CLI args > Config file > Defaults

## Complete Example

```yaml
# my-assistant.yaml
agentlet:
  name: "my-assistant"
  version: "1.0.0"

prompt: "Help me with software development tasks"

system_prompt: |
  You are an expert software development assistant.
  You have access to bash, file editing, and filesystem tools.
  Always explain your reasoning before making changes.

model:
  provider: "anthropic"
  model_id: "claude-sonnet-4-6"
  parameters:
    temperature: 0.7
    max_tokens: 4096
  retry:
    max_retries: 5
    initial_retry_interval: 30.0
    backoff_factor: 2.0

tools:
  - "bash"
  - "file_editor"

mcp_tools:
  - name: "filesystem"
    server: "stdio"
    command: "npx"
    args:
      - "-y"
      - "@modelcontextprotocol/server-filesystem"
    env:
      ALLOWED_DIRECTORIES: "${WORK_DIR}"
    prefix: "fs"
    tool_filters:
      allowed:
        - "read_file"
        - "write_file"
        - "list_directory"

resource_limits:
  max_execution_time: 300
  max_tokens: 10000
  max_tool_calls: 30

output:
  format: "markdown"
  show_messages: true
  show_reasoning: true
  show_tool_calls: true
  show_turn_boundaries: false

observability:
  otel:
    enabled: true
    otlp_endpoint: "http://localhost:4318"
    sampler: "traceidratio"
    sampler_arg: 0.1
    trace_attributes:
      environment: "production"
      team: "ai-platform"
```

## Validation

Configuration is validated using Pydantic schemas:

**Common validation errors:**
- Missing required fields (`agentlet.name`, `model.provider`)
- Invalid enum values (`output.format`, `observability.otel.sampler`)
- Invalid types (string instead of integer, etc.)
- Invalid tool filter keys (only `allowed` and `rejected` are accepted)
- Invalid model parameters

**Error messages include:**
- Field name
- Expected type
- Actual value
- Validation constraint

## Best Practices

1. **Use version control** - Track config changes in git
2. **Environment variables** - Store secrets in `.env`, not config files
3. **Tool filtering** - Only load needed tools to reduce token usage
4. **Resource limits** - Set appropriate limits for production
5. **Observability** - Enable OTEL in production with sampling
6. **Retry config** - Adjust for your API rate limits
7. **System prompt** - Be specific about agent capabilities and constraints

## Next Steps

- **[Running Agentlets](running-agentlets.md)** - CLI options and execution
- **[MCP Integration](mcp-integration.md)** - Advanced MCP usage
- **[Multi-Agent Systems](multi-agent.md)** - Orchestrate sub-agentlets

