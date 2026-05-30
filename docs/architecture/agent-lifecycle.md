# Agent Lifecycle

The agentlet lifecycle is the core execution pattern: each invocation spawns a fresh agent, runs to completion, then terminates — no persistent state survives between runs.

## Overview

```
┌──────────┐      ┌───────────┐      ┌────────────┐
│  SPAWN   │─────▶│  EXECUTE  │─────▶│ TERMINATE  │
└──────────┘      └───────────┘      └────────────┘
     │                  │                    │
Initialize          Run Task            Clean Up
```

**Characteristics:**
- **Ephemeral** — fresh context every run, no carry-over state
- **Safe** — `__aexit__` guarantees cleanup even on exception
- **Observable** — structured logs and OTel spans throughout
- **Resilient** — retry handler wraps the entire execute phase

## Phase 1: Spawn

Sets up every resource the agent needs before processing begins.

```
spawn()
  │
  ├─▶ Create ExecutionContext
  │     ├─▶ Generate unique execution ID (UUID v4)
  │     ├─▶ Set working directory (temp dir or --path)
  │     └─▶ Initialize tracking (tokens, errors, tool calls)
  │
  ├─▶ Initialize MCP tools (if configured)
  │     ├─▶ Create MCPClient instances per transport (stdio / http / sse)
  │     ├─▶ enter_contexts() — open connections / spawn subprocesses
  │     └─▶ get_tools_sync() — retrieve tool definitions
  │
  ├─▶ Create LiteLLMModel
  │     ├─▶ Build model ID: provider/model_id
  │     ├─▶ Merge config.parameters + resource_limits.max_tokens
  │     └─▶ Disable LiteLLM retries (agentlet-core manages all retries)
  │
  ├─▶ Load default Strands tools (lazy import from strands_tools.*)
  │
  └─▶ Create Strands Agent
        ├─▶ system_prompt + all tools (default + MCP + sub-agentlets)
        ├─▶ null_callback_handler (agentlet-core owns display)
        └─▶ trace_attributes for OTel
```

**Key decisions:**

- **Manual context management for MCP** — explicit `initialize()` → `enter_contexts()` → `exit_contexts()` instead of async context managers. This gives precise rollback on partial-init failures and avoids asyncio recursion in cleanup.
- **`null_callback_handler`** — the Strands framework has its own console output callbacks; disabling them gives agentlet-core full ownership of display formatting via RichLogger.
- **LiteLLM retries disabled** (`num_retries=0`) — `RetryHandler` manages all retry behaviour; LiteLLM's internal retries would interfere with backoff timing.

## Phase 2: Execute

Streams agent responses, dispatches events, tracks usage, and retries on transient errors.

### Message-Based Display

Text chunks are **buffered** and flushed only at message boundaries — not streamed character by character. This eliminates console flicker, enables clean reasoning-block panels, and gives consistent tool-call display regardless of how the model chunks its output.

### Event Dispatch

The Strands framework emits a stream of typed events during `stream_async()`. Agentlet-core handles each category:

| Event | When emitted | Action |
|-------|-------------|--------|
| `start_event_loop` | Agent begins a new reasoning turn | Show turn-boundary divider (if `show_turn_boundaries`, turns > 1) |
| `data` | Text chunk arrives | Append to text buffer |
| `reasoning` | Extended thinking text | Append to reasoning buffer |
| `current_tool_use` | Agent invokes a tool | Display tool-call panel; record in `ExecutionContext` |
| `message` (role=user) | Tool result returned | Display tool result |
| `message` (role=assistant) | Full message complete | Flush text buffer and reasoning buffer to console |
| `metadata.usage` | Token counts from model | Accumulate tokens; calculate cost via `litellm.cost_per_token()` |

### Execute Phase Flow

```
execute(prompt)
  │
  ├─▶ Retry wrapper — restarts the full stream on transient errors
  │
  └─▶ Event loop over agent.stream_async(prompt)
        │
        ├─▶ start_event_loop   → turn-boundary display
        ├─▶ data               → buffer text
        ├─▶ reasoning          → buffer reasoning
        ├─▶ current_tool_use   → display + track tool call
        ├─▶ message (user)     → display tool result
        ├─▶ message (asst)     → flush buffers to console
        └─▶ metadata.usage     → update token + cost counters
```

### Retry Logic

`RetryHandler` wraps `stream_async()` and restarts it from scratch on retryable errors:

- **Exponential backoff:** `initial_interval × factor^attempt` (default: 30 s, ×2, cap 300 s)
- **API-suggested wait:** extracts `retry-after` hints from rate-limit error messages
- **Configurable error list:** via `model.retry.retry_on_errors` (defaults: `RateLimitError`, `APIConnectionError`, `APITimeoutError`, `EventLoopException`, `litellm.RateLimitError`)

## Phase 3: Terminate

Releases all resources acquired during spawn.

```
terminate()
  │
  ├─▶ Exit MCP client contexts
  │     └─▶ Best-effort: logs each failure, continues to next client
  │
  ├─▶ Cleanup sub-agentlet MCP managers (if orchestrator)
  │
  ├─▶ Remove temporary working directory (shutil.rmtree, ignore_errors)
  │     └─▶ Skipped if user supplied an explicit --path
  │
  ├─▶ Close aiohttp sessions (litellm.close())
  │
  └─▶ Display execution summary (CLI layer)
```

**Execution summary** includes: execution time, tool calls, errors, retry attempts, token usage (input / output / cache read), and total cost.

## Lifecycle Observability

### Logging

Every phase emits structured logs under the `synteles.*` namespace. `log_context()` injects `execution_id` and `agentlet` name into every log record, enabling log-trace correlation without manual field threading.

### OTel Trace Hierarchy

The Strands Agent Framework auto-creates spans for model invocations and tool calls. Agentlet-core attaches attributes at the root span:

```
agentlet-execution
  ├─ model-invocation
  │   ├─ tool-call: bash
  │   └─ tool-call: read_file
  └─ sub-agentlet: research_agent   (orchestrator only)
      └─ model-invocation
          └─ tool-call: http_request
```

Root span attributes: `gen_ai.system`, `execution.id`, `agentlet.name`, `agentlet.version`, `model.provider`, `model.id`, plus any custom `trace_attributes` from config.

Sub-agentlet spans are automatically children of the orchestrator's tool-call span (same process → same OTel context). Additional attributes: `sub_agentlet.name`, `sub_agentlet.parent_execution_id`.

## Error Handling

| Phase | Strategy | Effect |
|-------|----------|--------|
| Spawn | Fail fast | Partially-entered MCP contexts are rolled back; clear error surfaced to CLI |
| Execute — transient | Retry with backoff | Full stream restarted up to `max_retries` |
| Execute — fatal | Propagate immediately | Cleanup still runs via `__aexit__` |
| Terminate | Best-effort | Each cleanup step logged; failures do not cascade |

Tool errors returned by MCP servers are recorded in `ExecutionContext` but do not halt execution — the agent LLM decides how to proceed.

## Related Documentation

- [Architecture Overview](./overview.md)
- [Configuration System](./configuration-system.md)
- [Tool Management](./tool-management.md)
- [Logging](../observability/logging.md)
- [Telemetry](../observability/telemetry.md)
