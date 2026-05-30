# Logging

Agentlet-core uses a production-ready **3-layer logging model** with automatic correlation tracking and security features.

## Overview

**Key Features:**
- **3-Layer Model** - Semantic (business), mechanical (SDK), and infrastructure logs
- **Automatic Correlation** - Context propagation via `log_context()`
- **Security-First** - Automatic secret sanitization
- **Rich Console Output** - Beautiful UX with icons, colors, and formatting
- **OTel-Ready** - JSON structured logging for observability

## 3-Layer Logging Model

The logging architecture separates concerns into three distinct layers:

```
Layer 1 (Semantic)       → synteles.*              → INFO (prod), DEBUG (dev)
Layer 2 (Mechanical)     → litellm.*, strands.*    → WARNING (prod), DEBUG (dev)
Layer 3 (Infrastructure) → botocore.*, urllib3.*   → WARNING (prod), INFO (dev)
```

**Key Principle**: Only Layer 1 defines business meaning. Layers 2 & 3 provide technical context.

### Layer 1: Semantic Logs (synteles.*)

Business-level events that define what the agentlet is doing:

```python
logger.info("Agentlet execution started", execution_id=exec_id)
logger.info("Tool call completed", tool="bash", duration_ms=123)
logger.error("Execution failed", error="timeout", timeout_sec=300)
```

**Production**: INFO level (only important business events)
**Debug**: DEBUG level (detailed execution flow)

### Layer 2: Mechanical Logs (litellm.*, strands.*)

SDK-level events from agent frameworks:

- Model initialization and API calls (litellm)
- Agent lifecycle and tool execution (strands)

**Production**: WARNING level (only SDK errors)
**Debug**: DEBUG level (full SDK context)

### Layer 3: Infrastructure Logs (botocore.*, urllib3.*, httpx.*)

Low-level HTTP, AWS, and network operations:

- HTTP request/response cycles
- AWS service calls and retries
- Connection pooling and timeouts

**Production**: WARNING level (only infrastructure errors)
**Debug**: INFO level (network-level visibility)

## Configuration

### Startup Configuration

Logging is configured **ONCE** at application startup in `cli/main.py`:

```python
from agentlet_core.logging import configure_logging
import logging
from pathlib import Path

# At CLI startup
configure_logging(
    level=logging.DEBUG if debug else logging.INFO,
    debug_mode=debug,
    log_dir=Path.cwd() if debug else None,
    json_format=False,  # Set True for OTel-ready structured logs
    enable_sanitization=True,  # Auto-redact secrets (recommended)
)
```

### Configuration Modes

**Production Mode** (default):
- **Level**: INFO
- **Output**: stdout via Rich console
- **Layer 1**: INFO to console
- **Layer 2/3**: WARNING (suppressed unless error)
- **File**: None
- **Format**: Human-readable with colors

**Debug Mode** (`--debug` flag):
- **Level**: DEBUG
- **Output**: stdout + file
- **Layer 1**: DEBUG to console + file
- **Layer 2**: DEBUG to console + file
- **Layer 3**: INFO to console + file
- **File**: `agentlet-core-{timestamp}.log`
- **Format**: Text or JSON (configurable)

### JSON Format for OTel

Enable structured JSON logging for OpenTelemetry ingestion:

```python
configure_logging(
    level=logging.INFO,
    debug_mode=False,
    json_format=True,  # Structured logs
    enable_sanitization=True,
)
```

**JSON Output**:
```json
{
  "timestamp": "2026-01-30T10:30:45.123456+00:00",
  "level": "INFO",
  "logger": "synteles.agentlet",
  "message": "Execution started",
  "process": 12345,
  "module": "base",
  "function": "execute",
  "line": 42,
  "context": {
    "execution_id": "abc-123",
    "agentlet": "assistant"
  }
}
```

## Correlation Context

### Automatic Context Propagation

The `log_context()` context manager eliminates manual `extra={}` repetition:

```python
from agentlet_core.logging import get_logger, log_context

logger = get_logger(__name__)

# All logs within this scope automatically include execution_id + agentlet
with log_context(execution_id=exec_id, agentlet="assistant"):
    logger.info("Starting execution")  # → includes execution_id + agentlet
    logger.info("Processing data")     # → includes execution_id + agentlet
    logger.info("Execution completed") # → includes execution_id + agentlet
```

### Benefits

- **No Manual Passing** - Context propagates automatically
- **Easy Tracing** - Filter logs by `execution_id` to see full execution
- **Thread-Safe** - Works correctly in async/concurrent scenarios
- **OTel-Ready** - `execution_id` becomes `trace_id` when OTel is enabled

### Nested Contexts

Contexts can be nested for hierarchical correlation:

```python
with log_context(execution_id=exec_id):
    logger.info("Execution started")

    with log_context(tool="bash"):
        logger.info("Running tool")  # Includes execution_id + tool

    with log_context(tool="file_editor"):
        logger.info("Running tool")  # Includes execution_id + tool
```

### OTel Integration

When OpenTelemetry is enabled, inject trace context automatically:

```python
from agentlet_core.logging import log_context
from agentlet_core.telemetry import inject_trace_context

# Correlate logs with traces
with log_context(**inject_trace_context(), execution_id=exec_id):
    logger.info("This log includes trace_id and span_id")
```

## Secret Sanitization

### Automatic Redaction

The `SecretSanitizationFilter` automatically redacts API keys, tokens, and passwords:

```python
logger.info("Using api_key=sk-1234567890")
# → Console: "Using api_key=***REDACTED***"

logger.info("Auth: Bearer abc123", extra={"token": "secret"})
# → Message and extra["token"] both redacted
```

### Supported Secret Patterns

- **AWS Keys**: `AKIA*`, `aws_access_key_id=*`
- **OpenAI Keys**: `sk-*`, `openai_api_key=*`
- **Anthropic Keys**: `anthropic_api_key=*`
- **GitHub Tokens**: `ghp_*`, `gho_*`, `ghs_*`
- **JWT Tokens**: `eyJ*`
- **Bearer Tokens**: `Bearer *`
- **Connection Strings**: `postgresql://*`, `mongodb://*`
- **Generic Patterns**: `password=*`, `secret=*`, `token=*`

### Configuration

Secret sanitization is **enabled by default** for security:

```python
configure_logging(
    enable_sanitization=True,  # Recommended (default)
)

# Disable only for local debugging (NOT recommended in production)
configure_logging(
    enable_sanitization=False,
)
```

## Usage Patterns

### Getting a Logger

```python
from agentlet_core.logging import get_logger

logger = get_logger(__name__)
```

The logger is automatically namespaced under `synteles.*`:
- `agentlet_core.agents.base` → `synteles.agentlet.agents.base`
- `__main__` → `synteles.__main__`

### Standard Logging

```python
from agentlet_core.logging import get_logger, log_context

logger = get_logger(__name__)

# Basic logging
logger.info("Processing request")
logger.warning("High memory usage", memory_mb=512)
logger.error("Failed to connect", error=str(e))

# With correlation context
with log_context(execution_id=exec_id, agentlet=agentlet_name):
    logger.info("Agentlet execution started")
    logger.info("Task completed", duration_ms=123)
```

### Rich Console Features

The `RichLoggerAdapter` provides enhanced UX features:

```python
from agentlet_core.logging import get_logger
from agentlet_core.logging.handlers import RichLoggerAdapter

logger = get_logger(__name__)
rich_logger = RichLoggerAdapter(logger)

# Success messages with ✓ icon
rich_logger.success("Operation completed")

# Tool call display as formatted table
rich_logger.tool_call({
    "tool": "bash",
    "args": {"command": "ls -la"},
    "result": "total 42\ndrwxr-xr-x ...",
})

# Execution summary table
rich_logger.execution_summary({
    "execution_id": "abc-123",
    "execution_time": "1.23s",
    "tool_calls": 5,
    "total_tokens": 1234,
    "total_cost": "$0.001234",
})

# Reasoning display
rich_logger.reasoning("I need to check the file system first")
```

## Best Practices

### DO ✅

**Use `log_context()` for correlation**:
```python
# Good - automatic context propagation
with log_context(execution_id=exec_id):
    logger.info("Processing")
```

**Log decisions and outcomes, not data dumps**:
```python
# Good - semantic business event
logger.info("Tool selected", tool="bash", reason="file_not_found")

# Bad - verbose data dump
logger.info(f"Tool selection result: {json.dumps(tool_data, indent=2)}")
```

**Trust the secret sanitization**:
```python
# Good - sanitization handles it
logger.debug("API request", headers=request.headers)

# Bad - manual redaction (fragile)
safe_headers = {k: "***" if "key" in k.lower() else v for k, v in headers.items()}
logger.debug("API request", headers=safe_headers)
```

**Treat Layer 1 logs as governance artifacts**:
```python
# Good - creates audit trail
logger.info("Model invoked", model="claude-sonnet-4-6", prompt_tokens=100)
logger.info("Tool executed", tool="bash", command_hash=hash(cmd))
```

### DON'T ❌

**Don't use `print()` for operational logging**:
```python
# Bad - bypasses logging infrastructure
print(f"Starting execution {exec_id}")

# Good - uses logging framework
logger.info("Starting execution", execution_id=exec_id)
```

**Don't re-log SDK errors**:
```python
# Bad - SDK already logs to litellm namespace
try:
    response = await model.complete(prompt)
except Exception as e:
    logger.error(f"LiteLLM error: {e}")  # Duplicate
    raise

# Good - let SDK log, add semantic context
try:
    response = await model.complete(prompt)
except Exception as e:
    logger.error("Model invocation failed", model=model_id)
    raise
```

**Don't log sensitive data directly**:
```python
# Bad - even with sanitization
logger.info(f"User password: {password}")

# Good - never log sensitive data
logger.info("User authenticated", user_id=user_id)
```

**Don't log excessively at INFO level**:
```python
# Bad - pollutes production logs
for item in items:
    logger.info(f"Processing item {item}")

# Good - use DEBUG for iteration details
logger.info("Processing batch", item_count=len(items))
for item in items:
    logger.debug("Processing item", item_id=item)
```

## File Structure

```
agentlet_core/logging/
├── __init__.py          # Public API exports
├── config.py            # Centralized configuration
├── context.py           # Correlation context manager
├── filters.py           # Secret sanitization, rate limiting
├── handlers.py          # Rich console output, structured logging
```

## Testing

### Run Logging Tests

```bash
# Run all logging tests (62 tests total)
uv run pytest tests/unit/test_logging*.py -v

# Test correlation context (11 tests)
uv run pytest tests/unit/test_logging_context.py -v

# Test secret sanitization (25 tests)
uv run pytest tests/unit/test_logging_filters.py -v
```

### Test with Debug Mode

```bash
# Enable debug mode
uv run agentlet-core --agentlet examples/simple-assistant.yaml \
  --prompt "Test" --debug

# Check log file created
ls -l agentlet-core-*.log

# View JSON logs
uv run agentlet-core --agentlet simple-assistant --prompt "Test" --debug
cat agentlet-core-*.log | jq .
```

## Integration with Telemetry

See [Telemetry](telemetry.md) for OpenTelemetry integration and log-trace correlation.

## Troubleshooting

### Logs Not Appearing

Check the effective log level:

```python
from agentlet_core.logging import get_effective_level
import logging

level = get_effective_level("synteles.agentlet")
if level <= logging.DEBUG:
    print("Debug logging is enabled")
```

### Third-Party SDK Logs Too Verbose

Adjust layer levels in `configure_logging()` or file an issue if defaults are wrong.

### Secrets Not Being Redacted

1. Check sanitization is enabled: `enable_sanitization=True`
2. Verify secret pattern is supported (see [Supported Secret Patterns](#supported-secret-patterns))
3. File an issue with example pattern if missing

### JSON Logs Missing Fields

Ensure context is set via `log_context()`:

```python
with log_context(execution_id=exec_id, custom_field="value"):
    logger.info("Message")  # JSON will include custom_field in context
```

## See Also

- [Telemetry](telemetry.md) - OpenTelemetry traces and metrics
- [Monitoring](monitoring.md) - Production monitoring best practices
- [Architecture: Configuration System](../architecture/configuration-system.md) - Log configuration in YAML
