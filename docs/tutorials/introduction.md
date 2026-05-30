# Core Concepts

Understanding the fundamental concepts behind agentlet-core.

## What is an Agentlet?

An **agentlet** is a minimal viable unit of autonomous AI agency - a standardized, containerized building block that occupies the sweet spot between passive tools and complex agents.

### Key Characteristics

**1. Ephemeral Execution**
- No persistent state between runs
- Clean spawn → execute → terminate lifecycle
- Fresh context for each execution

**2. Declarative Configuration**
- YAML/JSON configuration files
- Pydantic validation
- Environment variable expansion

**3. Multi-Provider LLM Support**
- Works with any LiteLLM-compatible provider
- Unified model string format: `provider/model_id`
- Cost tracking and token usage

**4. Rich Tooling**
- Default Strands tools (bash, file_editor, computer)
- MCP protocol tools (stdio, HTTP, SSE)
- Tool filtering and prefixing

**5. Multiagency**
- Inline sub-agentlets defined in YAML, each callable as a tool
- Orchestrator delegates specialised tasks; sub-agents return results as strings
- Per-sub-agentlet statistics: execution time, token usage, cost
- Sub-agent OTel spans auto-nested under the orchestrator's trace

**6. Production-Ready Observability**
- 3-layer logging system
- OpenTelemetry traces and metrics
- Automatic secret sanitization

## Agentlet Lifecycle

Every agentlet follows a three-phase lifecycle:

```
┌─────────┐     ┌───────────┐     ┌───────────┐
│ SPAWN   │ ──> │  EXECUTE  │ ──> │ TERMINATE │
└─────────┘     └───────────┘     └───────────┘
```

### Phase 1: Spawn

**What happens:**
1. Load and validate configuration
2. Create execution context (unique ID, working directory)
3. Configure logging system
4. Initialize MCP tools
5. Create Strands Agent with LiteLLM model

**Key artifacts created:**
- Execution ID: `550e8400-e29b-41d4-a716-446655440000`
- Working directory: Temp directory or user-specified path
- Logger: Configured with correlation context
- Agent: Ready to process prompts

### Phase 2: Execute

**What happens:**
1. Stream agent responses in real-time
2. Track tool calls and results
3. Handle errors with retry logic
4. Accumulate token usage and cost
5. Display reasoning blocks (if extended thinking)
6. Show turn boundaries for multi-turn conversations

**Execution modes:**
- **Streaming**: Messages displayed as they arrive
- **Non-streaming**: Spinner shows progress, then complete output

### Phase 3: Terminate

**What happens:**
1. Clean up MCP tool connections
2. Terminate stdio subprocesses
3. Remove temporary directories
4. Close aiohttp sessions
5. Display execution summary

**Summary includes:**
- Total execution time
- Token usage (input/output/cache)
- Total cost
- Tool calls made
- Errors encountered

## Configuration Anatomy

A typical agentlet configuration has these sections:

```yaml
# Metadata
agentlet:
  name: "my-assistant"
  version: "1.0.0"

# Optional default prompt
prompt: "Your default task"

# Agent instructions
system_prompt: "You are a helpful assistant."

# LLM configuration
model:
  provider: "anthropic"
  model_id: "claude-sonnet-4-6"
  parameters:
    temperature: 0.7
    max_tokens: 4096

# Default Strands tools
tools:
  - "bash"
  - "file_editor"

# MCP protocol tools
mcp_tools:
  - name: "filesystem"
    server: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem"]

# Execution constraints
resource_limits:
  max_execution_time: 300  # seconds
  max_tokens: 10000
  max_tool_calls: 20

# Output configuration
output:
  format: "markdown"  # or "json", "text"
  show_messages: true
  show_reasoning: true
  show_tool_calls: true
  show_turn_boundaries: false

# Observability
observability:
  otel:
    enabled: true
    otlp_endpoint: "http://localhost:4318"
```

## Multi-Provider LLM Support

Agentlet-core uses LiteLLM for unified multi-provider access.

### Model String Format

```
provider/model_id
```

**Examples:**
- `anthropic/claude-sonnet-4-6`
- `openai/gpt-4`
- `bedrock/claude-sonnet-4-6`
- `azure/gpt-4`
- `vertex_ai/gemini-pro`

### Provider Configuration

**Anthropic:**
```yaml
model:
  provider: "anthropic"
  model_id: "claude-sonnet-4-6"
```

Environment: `ANTHROPIC_API_KEY`

**AWS Bedrock:**
```yaml
model:
  provider: "bedrock"
  model_id: "claude-sonnet-4-6"
```

Environment: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

**OpenAI:**
```yaml
model:
  provider: "openai"
  model_id: "gpt-4"
```

Environment: `OPENAI_API_KEY`

### Cost Tracking

LiteLLM automatically tracks token usage and costs:

```
✓ Execution Summary:
┌────────────────────┬──────────┐
│ Metric             │ Value    │
├────────────────────┼──────────┤
│ Input Tokens       │ 1,234    │
│ Output Tokens      │ 567      │
│ Cache Read Tokens  │ 89       │
│ Total Cost         │ $0.0145  │
└────────────────────┴──────────┘
```

## Tool Management

Agentlets have access to two types of tools:

### 1. Default Strands Tools

Built-in tools from `strands-agents-tools`:

- **bash**: Execute shell commands
- **file_editor**: Read/write files with precise edits
- **computer**: Computer control (screenshot, mouse, keyboard)

**Configuration:**
```yaml
tools:
  - "bash"
  - "file_editor"
  - "computer"
```

### 2. MCP Protocol Tools

External tools via Model Context Protocol:

**stdio** (Local subprocess):
```yaml
mcp_tools:
  - name: "filesystem"
    server: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem"]
```

**HTTP** (Remote API):
```yaml
mcp_tools:
  - name: "api-service"
    server: "http"
    url: "https://api.example.com/mcp/"
    api_key_env: "API_KEY"
```

**SSE** (Server-Sent Events):
```yaml
mcp_tools:
  - name: "realtime"
    server: "sse"
    url: "http://localhost:8000/sse"
```

### Tool Filtering

Only load specific tools:

```yaml
mcp_tools:
  - name: "filesystem"
    server: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem"]
    tool_filters:
      allowed:
        - "read_file"
        - "write_file"
```

Or reject dangerous tools:

```yaml
tool_filters:
  rejected:
    - "delete_file"
    - "format_disk"
```

### Tool Name Prefixing

Prevent naming conflicts:

```yaml
mcp_tools:
  - name: "filesystem"
    prefix: "fs"  # Tools: fs_read_file, fs_write_file

  - name: "database"
    prefix: "db"  # Tools: db_query, db_insert
```

## Execution Context

Each agentlet execution creates an ephemeral context:

```python
ExecutionContext(
    execution_id="550e8400-e29b-41d4-a716-446655440000",
    agentlet_name="my-assistant",
    start_time=datetime.now(),
    work_dir="/tmp/agentlet-abc123",
    tool_calls=[],
    errors=[],
    token_usage={
        "input_tokens": 1234,
        "output_tokens": 567,
        "total_cost": 0.0145
    }
)
```

**Properties:**
- **Unique per execution**: Fresh context every run
- **Ephemeral**: Cleaned up on termination
- **Tracked**: All tool calls and errors recorded
- **Correlated**: Execution ID links all logs and traces

## Retry Logic

Adaptive exponential backoff for LLM API errors:

```yaml
model:
  retry:
    max_retries: 5
    initial_retry_interval: 30.0  # seconds
    backoff_factor: 2.0
    max_retry_interval: 300.0
    retry_on_errors:
      - "RateLimitError"
      - "APIConnectionError"
      - "APITimeoutError"
```

**Features:**
- Exponential backoff: 30s → 60s → 120s → 240s → 300s
- API-suggested wait times: Extracts `retry-after` from error messages
- Progressive backoff: Increases wait time for repeated rate limits
- Nested exception handling: Detects wrapped errors

## Message-Based Display

Agentlet-core uses message-based display (not character streaming):

**Benefits:**
- Complete messages per turn (better UX)
- Reasoning blocks for extended thinking
- Turn boundary indicators
- No duplicate output from SDK callbacks

**Output modes:**
- **Streaming**: Messages displayed as they arrive
- **Non-streaming**: Progress spinner, then complete output

## Environment Variables

### Configuration Expansion

Use `$VAR` or `${VAR}` in configs:

```yaml
mcp_tools:
  - name: "filesystem"
    env:
      ALLOWED_DIRS: "${WORK_DIR}"  # Expands to working directory
      API_KEY: "$MY_API_KEY"       # Expands from environment
```

### Special Variables

- `${WORK_DIR}`: Agentlet working directory
- Standard env vars: `$HOME`, `$USER`, etc.

### Search Paths

`.env` files loaded from:
1. Explicit `--env-file` path
2. Current directory (`.env`)
3. Synteles home (`~/synteles/.env`)

## Observability

### 3-Layer Logging Model

**Layer 1 (Semantic)**: `synteles.*`
- Business decisions and outcomes
- INFO in production, DEBUG in dev
- Defines meaning

**Layer 2 (Mechanical)**: `litellm.*`, `strands.*`
- SDK operations
- WARNING in production, DEBUG in dev
- Technical context

**Layer 3 (Infrastructure)**: `botocore.*`, `urllib3.*`
- Low-level transport logs
- WARNING in production, INFO in dev
- Minimal visibility

### Correlation Context

Automatic context propagation:

```python
with log_context(execution_id=exec_id, agentlet="my-assistant"):
    logger.info("Starting execution")  # Includes execution_id
    logger.info("Processing data")     # Includes execution_id
    logger.info("Execution completed") # Includes execution_id
```

### OpenTelemetry Traces

Built-in OTLP export:

```yaml
observability:
  otel:
    enabled: true
    otlp_endpoint: "http://localhost:4318"
    sampler: "traceidratio"
    sampler_arg: 0.1  # 10% sampling
```

**Automatic spans:**
- Agent execution (root span)
- Reasoning cycles
- Model invocations
- Tool executions

## Multiagency

An agentlet can act as an **orchestrator** by declaring `sub_agentlets` inline. Each sub-agentlet is a specialised Strands agent wrapped as a tool — the orchestrator's LLM decides when to call it.

```yaml
sub_agentlets:
  - name: research_agent
    description: "Searches and summarises factual information on any topic"
    system_prompt: "You are a research specialist..."
    tools: ["http_request"]

  - name: writing_agent
    description: "Transforms research notes into well-structured written content"
    system_prompt: "You are a professional writer..."
    model:
      provider: bedrock
      model_id: claude-haiku-4-5  # cheaper model for this sub-task
```

**Key properties:**
- Sub-agentlets run **in-process** — no subprocess overhead, no IPC
- **Model inheritance** — omit `model` to reuse the orchestrator's model
- **Full tool support** — each sub-agentlet can declare its own `tools` and `mcp_tools`
- **Statistics** — execution time, tokens, and cost logged per sub-agentlet after each run
- **Isolated** — sub-agentlets have no `ExecutionContext`; the orchestrator owns lifecycle tracking

See [Multi-Agent Guide](../reference/multi-agent.md) for a complete walkthrough.

## Next Steps

- **[Configuration Guide](../reference/configuration.md)** - Full config reference
- **[Multi-Agent Systems](../reference/multi-agent.md)** - Orchestrating sub-agentlets
- **[Architecture Overview](../architecture/overview.md)** - System design
- **[Agent Lifecycle](../architecture/agent-lifecycle.md)** - Lifecycle deep dive
