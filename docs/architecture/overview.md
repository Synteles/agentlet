# Architecture Overview

This document provides a high-level view of agentlet-core's architecture, component relationships, and design principles.

## System Overview

Agentlet-core is a Python runtime for autonomous AI agents built on the Strands Agent Framework. It implements an ephemeral execution model where agents are spawned, execute tasks, and terminate cleanly with no persistent state.

## Key Characteristics:

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

## Layered Architecture

The system follows a clean layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI Layer (cli/)                          │
│  - Command-line interface (Click)                               │
│  - Argument parsing and validation                              │
│  - Configuration override mechanism                             │
│  - Lifecycle orchestration                                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                   Configuration Layer (config/)                  │
│  - YAML/JSON loading with search paths                          │
│  - Pydantic schema validation                                   │
│  - Environment variable expansion                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                     Agent Layer (agents/)                        │
│  - BaseAgentlet: Core lifecycle implementation                  │
│  - Strands Agent Framework integration                          │
│  - LiteLLM model orchestration                                  │
│  - Event stream processing                                      │
│  - Retry logic with exponential backoff                         │
└────────┬───────────────┬──────────────────┬─────────────────────┘
         │               │                  │
    ┌────▼────┐    ┌────▼─────┐     ┌─────▼──────┐
    │ Runtime │    │  Tools   │     │   Utils    │
    │         │    │          │     │            │
    │Context  │    │MCP Mgr   │     │Logger      │
    │Retry    │    │Default   │     │Env Loader  │
    │         │    │Mgr       │     │            │
    └─────────┘    └──────────┘     └────────────┘
```

## Component Responsibilities

### CLI Layer (`cli/main.py`)
**Purpose:** User interaction and application bootstrapping

- Parses command-line arguments using Click
- Loads and merges configuration from files and CLI flags
- Configures logging system (3-layer model)
- Configures OpenTelemetry telemetry
- Orchestrates agentlet lifecycle
- Handles top-level error scenarios

**Key Pattern:** Configuration precedence (CLI > config file > defaults)

### Configuration Layer (`config/`)
**Purpose:** Configuration loading, validation, and transformation

**Components:**
- `models.py`: Pydantic schemas defining configuration structure
  - `AgentletConfig`: Root configuration
  - `ModelConfig`: LLM provider/model settings
  - `MCPToolConfig`: MCP tool definitions
  - `SubAgentletConfig`: Inline sub-agentlet definition for multiagency
  - `ResourceLimits`: Execution constraints
  - `OutputConfig`: Display preferences
  - `OTELConfig`: OpenTelemetry settings
  - `RetryConfig`: Retry behavior configuration

- `loader.py`: Configuration discovery and loading
  - Multi-location search (CWD, ~/.synteles, ./.synteles)
  - Environment variable expansion (`${VAR}`, `$VAR`)
  - YAML/JSON format support

**Key Patterns:**
- Pydantic validation ensures type safety and constraint enforcement
- Environment variable substitution happens before parsing

### Agent Layer (`agents/base.py`)
**Purpose:** Core agentlet lifecycle and execution

**BaseAgentlet** implements the three-phase lifecycle:

1. **Spawn Phase:**
   - Create ExecutionContext
   - Initialize MCP tools (stdio/HTTP/SSE)
   - Enter MCP client contexts (Manual Context Management)
   - Create LiteLLM model with provider prefix
   - Initialize sub-agentlets (resolve models, start sub-MCP tools, wrap as `@tool`)
   - Initialize Strands Agent with all tools (sub-agentlets + default + MCP)
   - Build trace attributes for observability

2. **Execute Phase:**
   - Stream agent responses via `agent.stream_async()`
   - Buffer text chunks for message-based display
   - Handle reasoning blocks (extended thinking)
   - Display tool calls and results
   - Track token usage and costs
   - Apply retry logic with exponential backoff

3. **Terminate Phase:**
   - Exit MCP client contexts
   - Cleanup sub-agentlet MCP managers
   - Cleanup temporary working directory
   - Close aiohttp sessions
   - Display execution summary (including per-sub-agentlet stats)

**Key Patterns:**
- Async context manager (`__aenter__`/`__aexit__`) ensures cleanup
- Null callback handler prevents double output
- Retry logic wraps agent stream with configurable backoff
- Manual context management for MCP clients (production-ready pattern)

### Runtime Layer (`runtime/`)
**Purpose:** Execution context and error handling

**ExecutionContext** (`context.py`):
- Ephemeral state container (no persistence)
- Working directory management (temp or user-specified)
- Tool call tracking
- Error collection
- Token and cost accounting
- Automatic cleanup

**RetryHandler** (`retry.py`):
- Exponential backoff with configurable parameters
- API-suggested wait time extraction
- Progressive backoff for rolling window rate limits
- Retry decision based on error type patterns
- Context integration for tracking attempts

**Key Patterns:**
- Temporary directory cleanup in destructor
- Stateless execution model
- Correlation context via `log_context()`

### Tools Layer (`tools/`)
**Purpose:** Tool loading and lifecycle management

**MCPToolsManager** (`mcp_manager.py`):
- Multi-transport MCP client creation:
  - stdio: Subprocess with stdin/stdout/stderr
  - HTTP: Streamable HTTP client
  - SSE: Server-Sent Events client
- Environment variable substitution (`${WORK_DIR}`)
- Tool filtering and prefixing (namespace isolation)
- Manual context management pattern
- Graceful cleanup with context exit

**DefaultToolsManager** (`tools_manager.py`):
- Lazy loading from `strands_tools.*`
- Auto-sets `BYPASS_TOOL_CONSENT=true`
- Caches loaded tool modules
- Imports: bash, file_editor, computer, etc.

**Key Patterns:**
- Strands `MCPClient` for framework integration
- Context manager protocol for resource lifecycle
- Tool filtering via `allowed`/`rejected` lists
- Prefix support for namespace isolation

### Utils Layer (`utils/`, `logging/`)
**Purpose:** Cross-cutting concerns

**Logging System** (`logging/`):
- 3-layer logging model (semantic, mechanical, infrastructure)
- Correlation context manager (`log_context()`)
- Secret sanitization filter
- Rich console output with formatting
- JSON structured logging support
- OTel-ready design

**Environment Loader** (`utils/env.py`):
- Multi-location .env search
- Environment variable loading
- Path resolution and validation

## Integration Points

### LiteLLM Integration
**Purpose:** Multi-provider LLM access

- Model ID format: `provider/model_id` (e.g., `bedrock/claude-sonnet-4-6`)
- Provider-specific parameter passing
- Cost calculation via `litellm.cost_per_token()`
- Token usage tracking
- Retry disabled at LiteLLM level (handled by agentlet-core)

**Supported Providers:** anthropic, bedrock, openai, azure, vertex_ai, etc.

### Strands Agent Framework Integration
**Purpose:** Agent orchestration and tool integration

- `LiteLLMModel`: Model abstraction
- `Agent`: Core agent with streaming support
- `null_callback_handler`: Prevents duplicate output
- `MCPClient`: MCP tool integration
- `stream_async()`: Event-based streaming
- Trace attributes for observability

**Event Types:**
- `data`: Text chunks
- `message`: Complete message boundaries
- `reasoning`: Extended thinking blocks
- `current_tool_use`: Tool invocations
- `toolResult`: Tool execution results
- `start_event_loop`: Turn boundaries
- `metadata.usage`: Token usage

### MCP (Model Context Protocol) Integration
**Purpose:** External tool integration

**Transport Types:**
- **stdio:** Subprocess communication (e.g., npx MCP servers)
- **HTTP:** Streamable HTTP requests
- **SSE:** Server-Sent Events streaming

**Features:**
- Tool filtering: `allowed` and `rejected` lists
- Tool prefixing: Namespace isolation (e.g., `fs_read_file`)
- Manual context management for production reliability
- Environment variable expansion

**Pattern:**
```python
# Manual Context Management
manager.initialize()           # Create MCPClient instances
manager.enter_contexts()       # Establish connections
tools = manager.get_tools_sync()  # Get tools (requires active context)
# ... use tools ...
manager.exit_contexts()        # Clean up
```

### OpenTelemetry Integration
**Purpose:** Distributed tracing and metrics

**Configuration:**
- Signal-specific endpoints (traces, metrics)
- OTLP exporter with custom headers
- Trace sampler configuration
- Console exporter for debugging
- Custom trace attributes

**Trace Attributes (orchestrator):**
- `gen_ai.system`: "synteles-agentlet"
- `execution.id`: Unique execution identifier
- `agentlet.name`: Agentlet name
- `agentlet.version`: Agentlet version
- `model.provider`: LLM provider
- `model.id`: Model identifier
- Custom attributes from config

**Additional attributes on sub-agentlet spans:**
- `sub_agentlet.name`: Sub-agentlet name (for filtering in collectors)
- `sub_agentlet.parent_execution_id`: Links back to the orchestrator execution
- Sub-agent spans appear as children of the orchestrator's tool invocation span automatically (same process = same OTel context)

**Integration Point:**
- Strands Agent Framework accepts `trace_attributes` parameter
- All agent operations automatically traced
- Telemetry configured once at startup

## Design Principles

### 1. Ephemeral Execution Model
**No persistent state between runs**

- Each execution gets a fresh context
- Temporary working directories cleaned up
- No database or file-based state
- Stateless design enables horizontal scaling

### 2. Configuration as Code
**Declarative YAML/JSON configuration**

- Pydantic validation ensures correctness
- Environment variable expansion for secrets
- CLI override for runtime flexibility

### 3. Clean Resource Management
**Explicit lifecycle with guaranteed cleanup**

- Async context managers for automatic cleanup
- Manual context management for MCP tools
- Graceful shutdown with timeout/kill fallback
- No resource leaks

### 4. Observability First
**Built-in logging, tracing, and metrics**

- 3-layer logging model
- Correlation context propagation
- Secret sanitization
- OpenTelemetry integration
- Rich console output for UX

### 5. Separation of Concerns
**Clear component boundaries**

- Configuration separated from execution
- Tool management isolated from agent logic
- Logging independent of business logic
- Retry logic decoupled from streaming

### 6. Multi-Provider Support
**LLM provider agnostic via LiteLLM**

- Unified interface across providers
- Provider-specific parameter support
- Cost tracking across providers
- Easy provider switching

### 7. Extensibility
**Plugin-friendly architecture**

- MCP protocol for external tools
- Lazy tool loading
- Tool filtering and prefixing
- Custom trace attributes

## Data Flow

### Configuration Loading Flow
```
CLI Arguments
    │
    ├──> Load .env file (if specified)
    │
    ├──> Load config (file path or agentlet name)
    │    │
    │    └──> Search paths: CWD, ~/.synteles/agentlets, ./.synteles/agentlets
    │
    ├──> Expand environment variables in config
    │
    ├──> Validate with Pydantic schemas
    │
    └──> Override with CLI arguments (precedence)
         │
         └──> Final AgentletConfig
```

### Execution Flow
```
AgentletConfig
    │
    ├──> Configure Logging (3-layer model)
    │
    ├──> Configure Telemetry (OpenTelemetry)
    │
    ├──> Create BaseAgentlet
    │
    ├──> Spawn Phase
    │    │
    │    ├──> Create ExecutionContext
    │    ├──> Initialize MCP tools
    │    ├──> Enter MCP contexts
    │    ├──> Create LiteLLM model
    │    └──> Create Strands Agent
    │
    ├──> Execute Phase
    │    │
    │    ├──> Stream agent responses
    │    ├──> Buffer text chunks
    │    ├──> Handle reasoning blocks
    │    ├──> Display tool calls/results
    │    ├──> Track token usage
    │    └──> Apply retry logic
    │
    └──> Terminate Phase
         │
         ├──> Exit MCP contexts
         ├──> Cleanup working directory
         ├──> Close sessions
         └──> Display summary
```

### Event Processing Flow
```
agent.stream_async(prompt)
    │
    ├──> Event: start_event_loop
    │    └──> Handle turn boundary (if multi-turn)
    │
    ├──> Event: data (text chunks)
    │    └──> Buffer in text_buffer
    │
    ├──> Event: reasoning (extended thinking)
    │    └──> Buffer in reasoning_buffer
    │
    ├──> Event: current_tool_use
    │    ├──> Display tool call
    │    └──> Record in ExecutionContext
    │
    ├──> Event: message (role=user, toolResult)
    │    └──> Display tool result
    │
    ├──> Event: message (role=assistant)
    │    ├──> Display buffered text
    │    ├──> Display buffered reasoning
    │    └──> Clear buffers
    │
    └──> Event: metadata.usage
         ├──> Track token usage
         └──> Calculate cost
```

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                            CLI                                   │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Click Args  │───▶│ Load Config  │───▶│ Override     │       │
│  └─────────────┘    └──────────────┘    └──────┬───────┘       │
└────────────────────────────────────────────────┼────────────────┘
                                                  │
┌─────────────────────────────────────────────────▼────────────────┐
│                      Configuration                                │
│  ┌────────────┐    ┌──────────────┐    ┌──────────────┐         │
│  │ Loader     │───▶│ Pydantic     │───▶│ AgentletConf │         │
│  │ (YAML/JSON)│    │ Validation   │    │              │         │
│  └────────────┘    └──────────────┘    └──────┬───────┘         │
└────────────────────────────────────────────────┼─────────────────┘
                                                  │
┌─────────────────────────────────────────────────▼────────────────┐
│                      BaseAgentlet                                 │
│  ┌────────────────────────────────────────────────────┐          │
│  │ Lifecycle: spawn() → execute() → terminate()       │          │
│  └───┬──────────────────┬────────────────────┬────────┘          │
│      │                  │                    │                   │
│  ┌───▼────────┐    ┌───▼───────┐       ┌───▼────────┐          │
│  │ MCP Tools  │    │  Strands  │       │  Retry     │          │
│  │ Manager    │    │  Agent    │       │  Handler   │          │
│  └────────────┘    └───┬───────┘       └────────────┘          │
└────────────────────────┼─────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
┌───────▼────────┐ ┌────▼──────────┐ ┌──▼──────────────┐
│  LiteLLM       │ │  MCP Clients  │ │ Default Tools   │
│  Model         │ │  (stdio/http) │ │ (strands_tools) │
│                │ │               │ │                 │
│ - Provider     │ │ - stdio       │ │ - bash          │
│ - Model ID     │ │ - http        │ │ - file_editor   │
│ - Parameters   │ │ - sse         │ │ - computer      │
└────────────────┘ └───────────────┘ └─────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Supporting Systems                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Execution    │  │  Logging     │  │  Telemetry   │          │
│  │ Context      │  │  System      │  │  (OTel)      │          │
│  │              │  │              │  │              │          │
│  │ - State      │  │ - 3 Layers   │  │ - Traces     │          │
│  │ - Tracking   │  │ - Context    │  │ - Metrics    │          │
│  │ - Cleanup    │  │ - Filtering  │  │ - Attributes │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

## Error Handling Strategy

### Retry Logic
**Exponential backoff with API-suggested wait times**

- Configurable retry attempts (default: 5)
- Initial retry interval (default: 30s)
- Backoff factor (default: 2.0)
- Max retry interval (default: 300s)
- API wait time extraction from error messages
- Progressive backoff for rolling window rate limits

**Retryable Errors:**
- `RateLimitError`
- `EventLoopException`
- `APIConnectionError`
- `APITimeoutError`
- `litellm.RateLimitError`

**Non-retryable Errors:**
- Validation errors (fail fast)
- Configuration errors (fail fast)
- Authentication errors (fail fast)
- Other exceptions (fail immediately)

### Error Propagation
**Clear error boundaries with context**

- Configuration errors: CLI level (exit 1)
- Spawn errors: Agent level (cleanup + raise)
- Execution errors: Runtime level (record + raise)
- Cleanup errors: Best-effort (log + continue)

## Performance Considerations

### Lazy Loading
- Tools loaded on-demand from `strands_tools.*`
- MCP clients initialized only when configured

### Resource Management
- Temporary directories cleaned up automatically
- MCP subprocesses terminated with timeout/kill
- aiohttp sessions closed properly
- No memory leaks in long-running scenarios

### Streaming
- Message-based display (not character-by-character)
- Buffering reduces console flicker
- Async streaming for non-blocking I/O
- Generator-based retry preserves streaming

## Security Considerations

### Secret Management
- Environment variables for sensitive data
- Secret sanitization in logs (10+ pattern types)
- API keys passed via headers (not URLs)
- No secrets in configuration files

### Input Validation
- Pydantic schema validation
- File path validation
- Environment variable expansion

### Subprocess Safety
- stdio MCP servers isolated in subprocesses
- Environment variable scoping
- Timeout and kill fallback
- No shell injection vulnerabilities

## Future Enhancements

### Known TODOs
1. Full MCP protocol handshake implementation
2. Advanced telemetry and custom metrics
3. Plugin system for custom tool managers
4. Configuration schema versioning
5. Out-of-process sub-agentlet execution (containerised isolation)
6. Per-sub-agentlet execution timeout
7. Remote sub-agentlet references (by URL or name)
8. Nested orchestration (sub-agentlet with its own sub-agentlets)
9. Persistent tool state (optional)
10. Workflow composition primitives

## Related Documentation

- [Agent Lifecycle](./agent-lifecycle.md) - Detailed lifecycle phases
- [Configuration System](./configuration-system.md) - Configuration loading
- [Tool Management](./tool-management.md) - Tool integration patterns
- [CLAUDE.md](../../CLAUDE.md) - Developer guide
- [Logging](../observability/logging.md) - Logging system documentation
- [Telemetry](../observability/telemetry.md) - OpenTelemetry integration
- [Monitoring](../observability/monitoring.md) - Production monitoring best practices
