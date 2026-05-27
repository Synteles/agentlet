# Agent Lifecycle

This document provides a detailed exploration of the agentlet lifecycle: Spawn → Execute → Terminate.

## Overview

The agentlet lifecycle is the core pattern of agentlet-core's execution model. Each execution follows a strict three-phase lifecycle with guaranteed cleanup:

```
┌──────────┐      ┌───────────┐      ┌────────────┐
│  SPAWN   │─────▶│  EXECUTE  │─────▶│ TERMINATE  │
└──────────┘      └───────────┘      └────────────┘
     │                  │                    │
Initialize          Run Task            Clean Up
```

**Key Characteristics:**
- **Ephemeral:** No persistent state between runs
- **Isolated:** Each execution gets a fresh context
- **Safe:** Guaranteed cleanup via async context manager
- **Observable:** Rich logging and tracing throughout
- **Resilient:** Retry logic with exponential backoff

## Implementation Pattern

The lifecycle is implemented in `BaseAgentlet` using the async context manager pattern:

```python
async with BaseAgentlet(config) as agentlet:
    await agentlet.spawn(working_dir)
    async for chunk in agentlet.execute(prompt):
        # Process streaming response
        pass
    # Automatic cleanup via __aexit__
```

**Or using the convenience method:**

```python
agentlet = BaseAgentlet(config)
response = await agentlet.run(prompt, working_dir)
# run() handles spawn → execute → terminate
```

## Phase 1: Spawn

**Purpose:** Initialize all resources required for execution.

### Responsibilities

1. Create ExecutionContext
2. Initialize MCP tools
3. Enter MCP client contexts
4. Create LiteLLM model
5. Initialize Strands Agent
6. Build trace attributes

### Detailed Flow

```python
async def spawn(self, working_dir: Optional[str] = None) -> None:
    """Initialize agentlet execution context."""
```

#### Step 1: Create ExecutionContext

```python
self.context = ExecutionContext(
    execution_id=self.execution_id,
    agentlet_name=self.config.agentlet.name,
    working_dir=working_dir,
    start_time=datetime.now(),
)
```

**ExecutionContext tracks:**
- Unique execution ID (UUID)
- Agentlet name and version
- Working directory (temp or user-specified)
- Tool call history
- Error collection
- Token usage and costs
- Retry attempts
- Execution timestamps

**Working Directory Logic:**
```python
if working_dir:
    self.working_dir = Path(working_dir).resolve()
    self._temp_dir = None
else:
    self._temp_dir = tempfile.mkdtemp(prefix=f"agentlet_{execution_id}_")
    self.working_dir = Path(self._temp_dir)
```

#### Step 2: Initialize MCP Tools

**Manual Context Management Pattern (Production-Ready):**

```python
if self.config.mcp_tools:
    self._mcp_manager = MCPToolsManager(
        tools_config=self.config.mcp_tools,
        working_dir=str(self.context.working_dir),
        logger=self.logger,
    )

    # Initialize MCP clients (create instances)
    self._mcp_manager.initialize()

    # Enter MCP client contexts (establish connections)
    self._mcp_manager.enter_contexts()

    # Get actual tools from MCP clients (requires active context)
    mcp_tools = self._mcp_manager.get_tools_sync()
```

**Why Manual Context Management?**
- More control over context lifecycle
- Better error handling during initialization
- Explicit resource management
- Production-proven pattern

**MCP Client Creation Process:**

```python
# For stdio transport
mcp_client = MCPClient(
    lambda: stdio_client(server_params),
    prefix=config.prefix,
    tool_filters=config.tool_filters,
)

# For HTTP transport
mcp_client = MCPClient(
    lambda: streamablehttp_client(url=url, headers=headers),
    prefix=config.prefix,
    tool_filters=config.tool_filters,
)

# For SSE transport
mcp_client = MCPClient(
    lambda: sse_client(url),
    prefix=config.prefix,
    tool_filters=config.tool_filters,
)
```

**Tool Filtering and Prefixing:**
- `tool_filters`: `{"allowed": [...], "rejected": [...]}`
- `prefix`: Namespace isolation (e.g., `fs_` → `fs_read_file`)

#### Step 3: Create LiteLLM Model

```python
# Build model parameters from config
model_params = {
    "max_tokens": self.config.resource_limits.max_tokens,
    **self.config.model.parameters,
}

# Disable LiteLLM internal retries (we handle retries)
model_params["num_retries"] = 0

# Create model with provider prefix
model = LiteLLMModel(
    model_id=self._get_litellm_model_id(),  # e.g., "bedrock/claude-sonnet-4-6"
    params=model_params,
)
```

**Model ID Construction:**
```python
def _get_litellm_model_id(self) -> str:
    """Construct LiteLLM model ID with provider prefix."""
    provider = self.config.model.provider.lower()
    model_id = self.config.model.model_id

    if not model_id.startswith(f"{provider}/"):
        return f"{provider}/{model_id}"
    return model_id
```

#### Step 4: Load Default Tools

```python
# Get default tools (bash, file_editor, etc.)
default_tools = (
    DefaultToolsManager(*self.config.tools).get_tools()
    if self.config.tools
    else []
)
```

**DefaultToolsManager:**
- Lazy loads from `strands_tools.*`
- Auto-sets `BYPASS_TOOL_CONSENT=true`
- Caches loaded modules
- Returns tool module list

#### Step 5: Create Strands Agent

```python
# Combine default tools with MCP tools
all_tools = default_tools + mcp_tools

# Build trace attributes for OTEL integration
trace_attributes = self._build_trace_attributes()

# Create agent with null callback handler
self._agent = Agent(
    model=model,
    name=self.config.agentlet.name,
    system_prompt=self.config.system_prompt,
    callback_handler=null_callback_handler,  # Prevents duplicate output
    tools=all_tools,
    trace_attributes=trace_attributes,
)
```

**Why null_callback_handler?**
- Agent framework has built-in callbacks for printing
- We handle all display through RichLogger
- Prevents duplicate output
- Consistent formatting across all output

**Trace Attributes:**
```python
{
    "gen_ai.system": "synteles-agentlet",
    "execution.id": self.execution_id,
    "agentlet.name": self.config.agentlet.name,
    "agentlet.version": self.config.agentlet.version,
    "model.provider": self.config.model.provider,
    "model.id": self.config.model.model_id,
    # ... custom attributes from config
}
```

### Spawn Phase Diagram

```
spawn()
  │
  ├─▶ Create ExecutionContext
  │     ├─▶ Generate execution_id (UUID)
  │     ├─▶ Setup working_dir (temp or user-specified)
  │     └─▶ Initialize tracking (tokens, errors, tool calls)
  │
  ├─▶ Initialize MCP Tools (if configured)
  │     ├─▶ Create MCPToolsManager
  │     ├─▶ initialize() - Create MCPClient instances
  │     │     ├─▶ stdio: StdioServerParameters + stdio_client
  │     │     ├─▶ http: streamablehttp_client
  │     │     └─▶ sse: sse_client
  │     ├─▶ enter_contexts() - Establish connections
  │     └─▶ get_tools_sync() - Get tool list
  │
  ├─▶ Create LiteLLM Model
  │     ├─▶ Construct model_id with provider prefix
  │     ├─▶ Merge config parameters + max_tokens
  │     └─▶ Disable LiteLLM retries (num_retries=0)
  │
  ├─▶ Load Default Tools
  │     ├─▶ Create DefaultToolsManager
  │     ├─▶ Lazy import from strands_tools.*
  │     └─▶ Return tool modules
  │
  ├─▶ Create Strands Agent
  │     ├─▶ Combine default_tools + mcp_tools
  │     ├─▶ Build trace_attributes for OTEL
  │     └─▶ Use null_callback_handler
  │
  └─▶ Log success and ready state
```

## Phase 2: Execute

**Purpose:** Stream agent responses, handle tool calls, track usage, apply retry logic.

### Responsibilities

1. Stream agent responses via `stream_async()`
2. Buffer text chunks for message-based display
3. Handle reasoning blocks (extended thinking)
4. Display and track tool calls/results
5. Track token usage and costs
6. Apply retry logic with exponential backoff
7. Handle turn boundaries (multi-turn conversations)

### Detailed Flow

```python
async def execute(self, prompt: str) -> AsyncIterator[str]:
    """Execute the agentlet with given prompt."""
```

#### Message-Based Display Pattern

**Why not character-by-character streaming?**
- Reduces console flicker
- Better formatting control
- Cleaner separation of content types
- Easier to handle structured content (reasoning, tool calls)

**Implementation:**
```python
# Buffers for accumulating content
text_buffer: list[str] = []        # Accumulate text chunks per message
reasoning_buffer: list[str] = []   # Accumulate reasoning text
turn_counter = {"count": 0}        # Track current turn number

async for event in self._retry_handler.retry_async_generator(
    self._agent.stream_async, prompt
):
    # Buffer chunks, display on message boundaries
    pass
```

#### Event Processing

The agent emits various event types during streaming. Each is handled differently:

##### 1. Turn Boundary Events

```python
def _handle_turn_boundary(self, event: dict, turn_counter: dict) -> None:
    """Handle turn boundary events in multi-turn conversations."""
    if event.get("start_event_loop"):
        turn_counter["count"] += 1
        # Only show turn boundary after turn 1
        if turn_counter["count"] > 1:
            self.logger.turn_boundary(turn_counter["count"])
```

**Turn boundaries indicate:**
- Multi-turn conversation flow
- Agent making another tool use → response cycle
- Progress indicator for long-running tasks

##### 2. Text Data Events

```python
def _handle_text_event(self, event: dict, text_buffer: list[str]) -> Optional[str]:
    """Handle text data events by buffering them."""
    if "data" not in event or not event["data"]:
        return None

    chunk = str(event["data"])
    text_buffer.append(chunk)  # Buffer instead of printing immediately
    return chunk  # Still yield for programmatic access
```

**Key points:**
- Text chunks buffered in memory
- Not displayed until message boundary
- Still yielded for programmatic consumers
- Reduces console flicker

##### 3. Reasoning Events (Extended Thinking)

```python
def _handle_reasoning_event(self, event: dict, reasoning_buffer: list[str]) -> None:
    """Handle reasoning events from models that support extended thinking."""
    if not self.config.output.show_reasoning:
        return

    # Accumulate reasoning text
    if event.get("reasoning") and "reasoningText" in event:
        reasoning_text = event["reasoningText"]
        if reasoning_text:
            reasoning_buffer.append(reasoning_text)

    # Display complete reasoning block
    if reasoning_buffer and (event.get("reasoning_complete") or event.get("message")):
        complete_reasoning = "".join(reasoning_buffer)
        if complete_reasoning.strip():
            self.logger.reasoning_block(complete_reasoning)
        reasoning_buffer.clear()
```

**Reasoning blocks:**
- Extended thinking from models like Claude 3.5 Sonnet v2
- Shows agent's internal reasoning process
- Buffered and displayed as complete blocks
- Configurable via `output.show_reasoning`

##### 4. Message Events (Display Boundary)

```python
def _handle_message_event(self, event: dict, text_buffer: list[str]) -> None:
    """Handle complete message events - displays buffered text."""
    if "message" not in event:
        return

    msg = event["message"]
    if not isinstance(msg, dict):
        return

    # Only display assistant messages
    if msg.get("role") == "assistant" and text_buffer:
        complete_text = "".join(text_buffer)
        if complete_text.strip() and self.config.output.show_messages:
            self.logger.assistant_message(complete_text)
        text_buffer.clear()
```

**Message boundaries:**
- Signal end of streaming for current message
- Trigger display of buffered text
- Clear buffers for next message
- Role-based filtering (only assistant messages)

##### 5. Tool Call Events

```python
def _handle_tool_call_event(self, event: dict) -> None:
    """Handle tool call events from agent stream."""
    if not self.config.output.show_tool_calls or "current_tool_use" not in event:
        return

    tool_use = event["current_tool_use"]
    self.logger.tool_call(tool_use)

    # Store tool name for later use in tool result display
    tool_use_id = tool_use.get("toolUseId") or tool_use.get("id")
    tool_name = tool_use.get("name")
    if tool_use_id and tool_name:
        self._tool_use_names[str(tool_use_id)] = str(tool_name)

    # Record tool call in execution context (avoid duplicates)
    if self.context and tool_use_id and tool_use_id not in self._recorded_tool_calls:
        tool_args = tool_use.get("input", {})
        self.context.record_tool_call(tool_name, tool_args)
        self._recorded_tool_calls.add(tool_use_id)
```

**Tool tracking:**
- Display tool invocation immediately
- Store tool_use_id → tool_name mapping
- Record in ExecutionContext for summary
- Deduplicate using recorded set

##### 6. Tool Result Events

```python
def _handle_tool_result_event(self, event: dict) -> None:
    """Handle tool result events from agent stream."""
    if not self.config.output.show_tool_calls or "message" not in event:
        return

    msg = event["message"]
    if not isinstance(msg, dict) or msg.get("role") != "user":
        return

    content = msg.get("content")
    if not isinstance(content, list):
        return

    for item in content:
        if not isinstance(item, dict) or "toolResult" not in item:
            continue

        # Display the tool result
        self._display_tool_result(item["toolResult"])

def _display_tool_result(self, tool_result: dict) -> None:
    """Display tool result with status and content."""
    tool_use_id = tool_result.get("toolUseId", "unknown")
    status = tool_result.get("status", "success")
    content = tool_result.get("content", [])
    is_error = status == "error"

    # Look up tool name from stored mapping
    tool_name = self._tool_use_names.get(str(tool_use_id), "Tool")
    result_text = self._extract_result_text(content)

    # Display result
    self.logger.tool_result(tool_name, {"status": status, "content": result_text},
                           success=not is_error)

    # Record tool errors in context
    if is_error and self.context:
        self.context.record_error(f"Tool '{tool_name}' failed: {result_text}")
```

**Tool result handling:**
- Match result to tool call via tool_use_id
- Display with success/error formatting
- Record errors in ExecutionContext
- Extract text from various content formats

##### 7. Token Usage Events

```python
def _handle_token_usage(self, event: dict) -> None:
    """Extract and track token usage from agent events."""
    if "event" not in event or not isinstance(event["event"], dict):
        return

    evt = event["event"]
    if "metadata" not in evt or not evt["metadata"]:
        return

    metadata = evt["metadata"]
    if "usage" not in metadata:
        return

    usage = metadata["usage"]
    input_tokens = usage.get("inputTokens", 0)
    output_tokens = usage.get("outputTokens", 0)
    cache_read_tokens = usage.get("cacheReadInputTokens", 0)

    # Calculate cost using LiteLLM
    cost = self._calculate_cost(input_tokens, output_tokens, cache_read_tokens)

    # Update context
    if self.context:
        self.context.add_tokens(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )
```

**Token tracking:**
- Extract from metadata.usage
- Calculate cost via `litellm.cost_per_token()`
- Accumulate in ExecutionContext
- Log metrics for observability

#### Retry Logic Integration

**Retry wraps the entire streaming operation:**

```python
async for event in self._retry_handler.retry_async_generator(
    self._agent.stream_async, prompt
):
    # Event processing
    pass
```

**RetryHandler behavior:**
- Restarts entire stream on retryable errors
- Exponential backoff: `initial * (factor ^ attempt)`
- API-suggested wait time extraction
- Progressive backoff for rolling window rate limits
- Configurable error types for retry

**Retryable errors:**
- `RateLimitError`
- `EventLoopException`
- `APIConnectionError`
- `APITimeoutError`
- `litellm.RateLimitError`

**Retry flow:**
```python
for attempt in range(max_retries + 1):
    try:
        async for item in agent.stream_async(prompt):
            yield item
        return  # Success
    except Exception as e:
        if should_retry(e) and attempt < max_retries:
            wait_time = calculate_wait_time(attempt)
            await asyncio.sleep(wait_time)
            continue
        raise e
```

### Execute Phase Diagram

```
execute(prompt)
  │
  ├─▶ Initialize buffers and counters
  │     ├─▶ text_buffer: []
  │     ├─▶ reasoning_buffer: []
  │     └─▶ turn_counter: {count: 0}
  │
  ├─▶ Retry wrapper around agent.stream_async()
  │     │
  │     └─▶ For each retry attempt:
  │           ├─▶ Wait with exponential backoff
  │           ├─▶ Extract API-suggested wait time
  │           ├─▶ Record retry in context
  │           └─▶ Restart stream
  │
  ├─▶ Process streaming events:
  │     │
  │     ├─▶ start_event_loop
  │     │     └─▶ Display turn boundary (if multi-turn)
  │     │
  │     ├─▶ data (text chunks)
  │     │     ├─▶ Append to text_buffer
  │     │     └─▶ Yield for programmatic access
  │     │
  │     ├─▶ reasoning (extended thinking)
  │     │     └─▶ Append to reasoning_buffer
  │     │
  │     ├─▶ current_tool_use
  │     │     ├─▶ Display tool call
  │     │     ├─▶ Store tool_use_id → name mapping
  │     │     └─▶ Record in ExecutionContext
  │     │
  │     ├─▶ message (role=user, toolResult)
  │     │     └─▶ Display tool result
  │     │
  │     ├─▶ message (role=assistant)
  │     │     ├─▶ Display buffered text
  │     │     ├─▶ Display buffered reasoning
  │     │     └─▶ Clear buffers
  │     │
  │     └─▶ metadata.usage
  │           ├─▶ Extract token counts
  │           ├─▶ Calculate cost via LiteLLM
  │           └─▶ Update ExecutionContext
  │
  ├─▶ end_execution()
  │     └─▶ Record end timestamp
  │
  └─▶ Log completion with execution time
```

## Phase 3: Terminate

**Purpose:** Clean up all resources and display summary.

### Responsibilities

1. Exit MCP client contexts
2. Cleanup temporary working directory
3. Close aiohttp sessions
4. Display execution summary
5. Handle cleanup errors gracefully

### Detailed Flow

```python
async def terminate(self) -> None:
    """Clean up resources and terminate agentlet."""
```

#### Step 1: Cleanup MCP Tools

```python
if self._mcp_manager:
    self._mcp_manager.cleanup_sync()
```

**cleanup_sync() implementation:**
```python
def cleanup_sync(self) -> None:
    """Synchronous cleanup of all MCP resources."""
    if not self._mcp_clients:
        return

    self.exit_contexts()

def exit_contexts(self) -> None:
    """Exit all MCP client contexts."""
    errors = []
    for i, client in enumerate(self._mcp_clients):
        try:
            client.__exit__(None, None, None)
        except Exception as e:
            error_msg = f"Failed to exit context for MCP client {i + 1}: {e}"
            self.logger.warning(error_msg)
            errors.append(error_msg)

    if errors:
        self.logger.warning(f"Encountered {len(errors)} error(s) during context exit")
```

**Why synchronous cleanup?**
- Avoids asyncio recursion issues
- Simpler error handling
- More predictable behavior
- Works in both async and sync contexts

**stdio process cleanup:**
- `__exit__` closes stdin/stdout/stderr pipes
- Waits for process termination
- Timeout and SIGKILL fallback
- Prevents zombie processes

#### Step 2: Cleanup Working Directory

```python
if self.context:
    self.context.cleanup()
```

**ExecutionContext cleanup:**
```python
def cleanup(self) -> None:
    """Clean up temporary resources."""
    if self._temp_dir and Path(self._temp_dir).exists():
        shutil.rmtree(self._temp_dir, ignore_errors=True)
```

**Cleanup behavior:**
- Only removes temporary directories (not user-specified)
- `ignore_errors=True` for best-effort cleanup
- No cleanup if user provided working_dir
- Prevents accumulation of temp directories

#### Step 3: Cleanup aiohttp Sessions

```python
await self._cleanup_aiohttp_sessions()
```

**Session cleanup:**
```python
async def _cleanup_aiohttp_sessions(self) -> None:
    """Clean up any unclosed aiohttp client sessions."""
    try:
        # Cleanup litellm client if available
        if hasattr(litellm, "close"):
            await litellm.close()

        # Brief delay for cleanup to complete
        await asyncio.sleep(0.1)

    except Exception as e:
        self.logger.debug_log(f"Cleanup error: {e}")
```

**Why this matters:**
- LiteLLM uses aiohttp for HTTP requests
- Prevents "Unclosed client session" warnings
- Ensures clean shutdown
- Small delay allows pending requests to complete

#### Step 4: Display Summary (CLI Layer)

```python
# In cli/main.py after run() completes
if agentlet.context:
    logger.execution_summary(agentlet.context.get_summary())
```

**Summary includes:**
```python
{
    "execution_id": str,
    "agentlet_name": str,
    "execution_time": "X.XXs",
    "tool_calls": int,
    "errors": int,
    "retry_attempts": int,
    "input_tokens": int,
    "output_tokens": int,
    "total_tokens": int,
    "total_cost": "$X.XXXXXX",
    "start_time": ISO8601,
    "end_time": ISO8601,
}
```

### Terminate Phase Diagram

```
terminate()
  │
  ├─▶ Cleanup MCP Tools
  │     ├─▶ exit_contexts()
  │     │     └─▶ For each MCPClient:
  │     │           ├─▶ client.__exit__(None, None, None)
  │     │           ├─▶ Close stdio pipes (if stdio)
  │     │           ├─▶ Wait for process termination
  │     │           └─▶ SIGKILL fallback if timeout
  │     │
  │     └─▶ Log cleanup status
  │
  ├─▶ Cleanup Working Directory
  │     └─▶ context.cleanup()
  │           └─▶ shutil.rmtree(_temp_dir, ignore_errors=True)
  │
  ├─▶ Cleanup aiohttp Sessions
  │     ├─▶ litellm.close() (if available)
  │     └─▶ asyncio.sleep(0.1) for pending requests
  │
  ├─▶ Display Execution Summary (CLI layer)
  │     ├─▶ Execution time
  │     ├─▶ Tool calls count
  │     ├─▶ Errors count
  │     ├─▶ Retry attempts
  │     ├─▶ Token usage
  │     └─▶ Total cost
  │
  └─▶ Log termination success
```

## Async Context Manager Pattern

The lifecycle is enforced via the async context manager protocol:

```python
async def __aenter__(self):
    """Async context manager entry."""
    return self

async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
    """Async context manager exit with guaranteed cleanup."""
    await self.terminate()
    return False  # Don't suppress exceptions
```

**Benefits:**
- Guaranteed cleanup even on exceptions
- Pythonic resource management
- Works with async with statement
- No resource leaks

**Usage:**
```python
async with BaseAgentlet(config) as agentlet:
    await agentlet.spawn()
    await agentlet.execute(prompt)
    # terminate() called automatically
```

## Error Handling Throughout Lifecycle

### Spawn Phase Errors

```python
try:
    await agentlet.spawn(working_dir)
except RuntimeError as e:
    # MCP tool initialization failed
    # Context not fully initialized
    # No cleanup needed beyond what was already done
    raise
```

**Error scenarios:**
- MCP server not found (command doesn't exist)
- MCP connection timeout
- Tool validation errors
- Model configuration errors

**Recovery:**
- No automatic recovery (fail fast)
- Partial cleanup in MCPToolsManager
- Clear error messages with context

### Execute Phase Errors

```python
try:
    async for chunk in agentlet.execute(prompt):
        pass
except asyncio.TimeoutError:
    # Execution timeout
    # Context partially populated
    # Cleanup will happen in terminate()
    raise
except Exception as e:
    # Agent execution error
    # Error recorded in context
    # Cleanup will happen in terminate()
    raise
```

**Error scenarios:**
- Rate limit errors (retryable)
- API connection errors (retryable)
- Model errors (non-retryable)
- Tool execution errors (recorded, execution continues)
- Timeout errors (non-retryable)

**Recovery:**
- Retry logic for transient errors
- Error tracking in ExecutionContext
- Tool errors don't stop execution
- Non-retryable errors propagate immediately

### Terminate Phase Errors

```python
async def terminate(self) -> None:
    try:
        # Cleanup MCP tools
        if self._mcp_manager:
            self._mcp_manager.cleanup_sync()
    except Exception as e:
        # Log but continue with other cleanup
        self.logger.warning(f"MCP cleanup error: {e}")

    try:
        # Cleanup working directory
        if self.context:
            self.context.cleanup()
    except Exception as e:
        # Log but continue
        self.logger.warning(f"Context cleanup error: {e}")

    # Continue with other cleanup...
```

**Error handling strategy:**
- Best-effort cleanup
- Log errors but don't raise
- Continue with remaining cleanup steps
- No cascading cleanup failures

## Lifecycle Observability

### Logging Integration

Each phase emits structured logs with correlation context:

```python
# Spawn phase
with log_context(execution_id=exec_id, agentlet=name):
    logger.info("Spawning agentlet")
    # ... spawn operations ...
    logger.success("Agentlet spawned successfully")

# Execute phase
with log_context(execution_id=exec_id, agentlet=name):
    logger.info("Executing task")
    # ... execution ...
    logger.success("Task completed")

# Terminate phase
with log_context(execution_id=exec_id, agentlet=name):
    logger.info("Terminating agentlet")
    # ... cleanup ...
    logger.success("Agentlet terminated")
```

**Correlation context includes:**
- `execution_id`: UUID for tracing
- `agentlet`: Agentlet name
- `retry_attempt`: Retry count (if retrying)

### Tracing Integration

OpenTelemetry traces span the entire lifecycle:

```python
# Trace attributes attached to agent
trace_attributes = {
    "gen_ai.system": "synteles-agentlet",
    "execution.id": execution_id,
    "agentlet.name": agentlet_name,
    "agentlet.version": version,
    "model.provider": provider,
    "model.id": model_id,
}

# Strands Agent automatically creates spans
agent = Agent(
    model=model,
    trace_attributes=trace_attributes,
    # ...
)
```

**Trace hierarchy:**
```
agentlet-execution [span]
  ├─ spawn [span]
  │   ├─ mcp-init [span]
  │   └─ agent-create [span]
  ├─ execute [span]
  │   ├─ agent-stream [span]
  │   ├─ tool-call-1 [span]
  │   ├─ tool-call-2 [span]
  │   └─ token-usage [event]
  └─ terminate [span]
      └─ cleanup [span]
```

### Metrics Tracking

ExecutionContext tracks key metrics:

```python
summary = {
    "execution_time": "45.23s",
    "tool_calls": 3,
    "errors": 0,
    "retry_attempts": 1,
    "input_tokens": 1234,
    "output_tokens": 567,
    "total_tokens": 1801,
    "total_cost": "$0.012345",
}
```

**Metric categories:**
- **Performance:** execution_time, retry_attempts
- **Usage:** token counts, cost
- **Behavior:** tool_calls, errors
- **Timestamps:** start_time, end_time

## Best Practices

### 1. Always Use Context Manager

```python
# Good
async with BaseAgentlet(config) as agentlet:
    await agentlet.spawn()
    await agentlet.execute(prompt)

# Bad (manual cleanup)
agentlet = BaseAgentlet(config)
await agentlet.spawn()
await agentlet.execute(prompt)
await agentlet.terminate()  # Easy to forget!
```

### 2. Provide Working Directory When Needed

```python
# For file operations, provide explicit working dir
await agentlet.spawn(working_dir="/path/to/project")

# For ephemeral tasks, use temp dir (default)
await agentlet.spawn()  # Creates temp dir
```

### 3. Handle Timeouts Gracefully

```python
timeout = config.resource_limits.max_execution_time

try:
    await asyncio.wait_for(agentlet.run(prompt), timeout=timeout)
except asyncio.TimeoutError:
    logger.error(f"Execution timed out after {timeout}s")
    # terminate() will still be called via context manager
```

### 4. Monitor Retry Attempts

```python
# In execute():
if agentlet.context:
    retry_count = agentlet.context.retry_attempts
    if retry_count > 3:
        logger.warning(f"High retry count: {retry_count}")
```

### 5. Check Summary After Execution

```python
summary = agentlet.context.get_summary()

if summary["errors"] > 0:
    logger.warning(f"Execution completed with {summary['errors']} errors")

if summary["total_cost"] > 1.0:
    logger.warning(f"High cost: {summary['total_cost']}")
```

## Related Documentation

- [Architecture Overview](./overview.md) - System architecture
- [Configuration System](./configuration-system.md) - Configuration details
- [Tool Management](./tool-management.md) - Tool integration patterns
- [CLAUDE.md](../../CLAUDE.md) - Developer guide
