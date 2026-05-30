# Running Agentlets

Complete guide to executing agentlets using the CLI.

## Quick Start

```bash
# Run agentlet with config file and prompt
uv run agentlet-core --agentlet my-assistant.yaml --prompt "Say hello"

# Use agentlet name (searches in default locations)
uv run agentlet-core --agentlet simple-assistant --prompt "Analyze this code"

# Override model
uv run agentlet-core --agentlet my-assistant --model "openai/gpt-4" --prompt "Help me"
```

## CLI Reference

### Basic Usage

```bash
agentlet-core [OPTIONS]
```

### Core Options

#### --agentlet, -a

Path to agentlet configuration file or agentlet name.

```bash
# Explicit file path (YAML or JSON)
agentlet-core --agentlet /path/to/config.yaml --prompt "Task"

# Agentlet name — searches for {name}.yaml or {name}.yml in default locations
agentlet-core --agentlet simple-assistant --prompt "Task"
```

**Search paths** (for agentlet names):
1. Current working directory (`./`)
2. User Synteles directory (`~/.synteles/agentlets/`)
3. Local Synteles directory (`./.synteles/agentlets/`)

**Note:** Name resolution only matches `.yaml` and `.yml`. To use a JSON config, provide the explicit file path.

#### --prompt, -p

User prompt (task for the agentlet to perform).

```bash
agentlet-core --agentlet my-agent --prompt "Explain quantum computing"

# Multi-line prompts
agentlet-core --agentlet my-agent --prompt "Analyze the codebase:
1. Find all Python files
2. Check for security issues
3. Generate a report"
```

**Note**: Prompt is required unless defined in the configuration file.

#### --path

Path to working directory for agentlet execution.

```bash
# Run in specific directory
agentlet-core --agentlet my-agent --prompt "List files" --path /projects/myapp

# Use current directory (default)
agentlet-core --agentlet my-agent --prompt "List files"
```

**Behavior**:
- Default: Creates temporary directory
- With `--path`: Uses specified directory
- `${WORK_DIR}` in config expands to this path

### Model Options

#### --model, -m

Override LLM model to use.

```bash
# Full provider/model format
agentlet-core --agentlet my-agent --model "bedrock/claude-sonnet-4-6" --prompt "Task"

# Model only (uses provider from config)
agentlet-core --agentlet my-agent --model "claude-opus-4-5" --prompt "Task"

# OpenAI model
agentlet-core --agentlet my-agent --model "openai/gpt-4" --prompt "Task"
```

**Format**: `provider/model_id` or just `model_id`

**Supported providers**:
- `anthropic`: Anthropic API
- `bedrock`: AWS Bedrock
- `openai`: OpenAI API
- `azure`: Azure OpenAI
- `vertex_ai`: Google Vertex AI

See [LiteLLM providers](https://docs.litellm.ai/docs/providers) for full list.

### Resource Options

#### --timeout

Maximum execution time in seconds.

```bash
# 2 minute timeout
agentlet-core --agentlet my-agent --timeout 120 --prompt "Quick task"

# 10 minute timeout for long-running tasks
agentlet-core --agentlet my-agent --timeout 600 --prompt "Complex analysis"
```

**Default**: 300 seconds (5 minutes)

**Behavior**:
- Execution terminates if timeout exceeded
- Exit code 1 returned
- Partial results may be available

#### --max-tokens

LLM token limit (input + output).

```bash
# Limit to 8000 tokens
agentlet-core --agentlet my-agent --max-tokens 8000 --prompt "Task"

# High token limit for complex tasks
agentlet-core --agentlet my-agent --max-tokens 50000 --prompt "Analyze codebase"
```

**Default**: 10000 tokens

**Note**: This is a warning threshold, not enforced by the runtime.

### Retry Options

#### --max-retries

Maximum number of retry attempts for rate limit errors.

```bash
# More aggressive retries
agentlet-core --agentlet my-agent --max-retries 10 --prompt "Task"

# No retries
agentlet-core --agentlet my-agent --max-retries 0 --prompt "Task"
```

**Default**: 5 retries

#### --initial-retry-interval

Initial retry interval in seconds.

```bash
# Faster initial retry
agentlet-core --agentlet my-agent --initial-retry-interval 10.0 --prompt "Task"
```

**Default**: 30.0 seconds

#### --backoff-factor

Exponential backoff multiplier.

```bash
# Linear backoff (no exponential growth)
agentlet-core --agentlet my-agent --backoff-factor 1.0 --prompt "Task"

# Aggressive backoff
agentlet-core --agentlet my-agent --backoff-factor 3.0 --prompt "Task"
```

**Default**: 2.0 (doubles each retry)

**Example backoff sequence** (with defaults):
- Attempt 1: 30s
- Attempt 2: 60s
- Attempt 3: 120s
- Attempt 4: 240s
- Attempt 5: 300s (capped at max)

### Output Options

#### --output-format

Output format for agentlet responses.

```bash
# Markdown with rich formatting (default)
agentlet-core --agentlet my-agent --output-format markdown --prompt "Task"

# JSON output
agentlet-core --agentlet my-agent --output-format json --prompt "Task"

# Plain text
agentlet-core --agentlet my-agent --output-format text --prompt "Task"
```

**Options**:
- `markdown` (default): Rich console output with syntax highlighting
- `json`: JSON-formatted output
- `text`: Plain text output

### Observability Options

#### --otel-enabled

Enable OpenTelemetry trace export.

```bash
agentlet-core --agentlet my-agent --otel-enabled --prompt "Task"
```

#### --otlp-endpoint

OTLP base endpoint URL.

```bash
agentlet-core --agentlet my-agent --otel-enabled --otlp-endpoint "http://localhost:4318" --prompt "Task"
```

**Default**: `http://localhost:4318` or `OTEL_EXPORTER_OTLP_ENDPOINT`

#### --otlp-traces-endpoint

OTLP traces-specific endpoint (overrides base endpoint for traces).

```bash
agentlet-core --agentlet my-agent --otel-enabled \
  --otlp-traces-endpoint "http://localhost:4318/v1/traces" \
  --prompt "Task"
```

#### --otlp-metrics-endpoint

OTLP metrics-specific endpoint (overrides base endpoint for metrics).

```bash
agentlet-core --agentlet my-agent --otel-enabled \
  --otlp-metrics-endpoint "http://localhost:4318/v1/metrics" \
  --prompt "Task"
```

#### --otel-console

Enable console trace export for debugging.

```bash
agentlet-core --agentlet my-agent --otel-enabled --otel-console --prompt "Task"
```

**Output**: Traces printed to stderr in addition to OTLP export.

### Debug Options

#### --debug, -d

Enable detailed debug logging.

```bash
agentlet-core --agentlet my-agent --debug --prompt "Task"
```

**Effects**:
- Verbose logging to stdout
- Log file created: `agentlet-core-{timestamp}.log`
- Shows internal state and SDK operations
- Displays configuration values

**Use cases**:
- Troubleshooting configuration issues
- Understanding agent behavior
- Debugging MCP tool integration
- Performance analysis

#### --env-file

Path to `.env` file for environment variables.

```bash
# Explicit env file
agentlet-core --agentlet my-agent --env-file /path/to/.env --prompt "Task"

# Default behavior (searches in order):
# 1. ./.env (current working directory)
# 2. ~/synteles/.env (Synteles home directory)
agentlet-core --agentlet my-agent --prompt "Task"
```

**Format** (`.env` file):
```bash
# API keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# AWS credentials
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# MCP tool environment variables
CUSTOM_API_KEY=abc123
ALLOWED_DIRECTORIES=/home/user/projects
```

#### --image, -i

Pass one or more images to the model alongside the prompt. Can be repeated.

```bash
# Local file
agentlet-core --agentlet my-agent --prompt "Describe this diagram" \
  --image /path/to/diagram.png

# HTTP/HTTPS URL
agentlet-core --agentlet my-agent --prompt "What's in this screenshot?" \
  --image https://example.com/screenshot.png

# Multiple images
agentlet-core --agentlet my-agent --prompt "Compare these two designs" \
  --image design-a.png --image design-b.png
```

**Supported formats:** JPEG, PNG, GIF, WebP

**Supported sources:** Local file path, `http://` or `https://` URL, `data:image/...;base64,...` data URI

**Requires** a vision-capable model (e.g., `claude-sonnet-4-6`, `gpt-4o`).

### Version

```bash
agentlet-core --version
```

Displays version information and exits.

## Environment Variables

### Required Variables (Provider-Specific)

**Anthropic**:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Anthropic Foundry**:
```bash
export ANTHROPIC_FOUNDRY_API_KEY="..."
export ANTHROPIC_FOUNDRY_RESOURCE="..."
```

**AWS Bedrock**:
```bash
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-east-1"  # optional
```

**OpenAI**:
```bash
export OPENAI_API_KEY="sk-..."
```

**Azure OpenAI**:
```bash
export AZURE_API_KEY="..."
export AZURE_API_BASE="https://..."
export AZURE_API_VERSION="2024-02-01"
```

### Optional Variables

**Execution ID** (for trace correlation):
```bash
export SYNTELES_EXEC_ID="550e8400-e29b-41d4-a716-446655440000"  # Must be a valid UUID v4
```

Set this when running inside a CI/CD pipeline or orchestration system to tie the agentlet's traces back to a parent job ID. If absent or invalid, a new UUID v4 is generated automatically.

**LiteLLM Debug**:
```bash
export LITELLM_DEBUG="true"
```

**Tool Consent** (automatically set):
```bash
export BYPASS_TOOL_CONSENT="true"
```

**OpenTelemetry**:
```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_SERVICE_NAME="agentlet-core"
```

## Loading .env Files

Agentlet-core automatically loads environment variables from `.env` files.

**Search order**:
1. Explicit path via `--env-file`
2. `./.env` (current working directory)
3. `~/synteles/.env` (Synteles home directory)

**Example .env file**:
```bash
# API Keys
ANTHROPIC_API_KEY=sk-ant-api03-...

# AWS Credentials
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# MCP Tools
FILESYSTEM_ROOT=/projects
CUSTOM_API_KEY=abc123

# Debug
LITELLM_DEBUG=false
```

**Verification**:
```bash
# Check if env file loaded (with debug mode)
agentlet-core --agentlet my-agent --debug --prompt "Task"
# Output: ✓ Environment variables loaded from .env file
```

## Working with Prompts

### Single-Line Prompts

```bash
agentlet-core --agentlet my-agent --prompt "List all Python files"
```

### Multi-Line Prompts

**Shell heredoc**:
```bash
agentlet-core --agentlet my-agent --prompt "$(cat <<'EOF'
Analyze the codebase:
1. Find all Python files
2. Check for security issues
3. Generate a detailed report
EOF
)"
```

**File-based prompts**:
```bash
agentlet-core --agentlet my-agent --prompt "$(cat task.txt)"
```

### Prompts from Config

Define default prompts in configuration:

```yaml
prompt: "Your default task here"
```

```bash
# Uses prompt from config
agentlet-core --agentlet my-agent

# Override with CLI
agentlet-core --agentlet my-agent --prompt "Different task"
```

## Debug Mode and Logging

### Standard Logging (Production)

```bash
agentlet-core --agentlet my-agent --prompt "Task"
```

**Output**: INFO level logs to stdout via Rich console

**Example**:
```
ℹ Agentlet execution started
ℹ Loading configuration from simple-assistant.yaml
✓ Configuration loaded successfully
ℹ Agentlet spawned: simple-assistant v1.0.0
✓ MCP server 'filesystem' (stdio) initialized
ℹ Agent execution started
...
✓ Execution completed successfully
```

### Debug Mode

```bash
agentlet-core --agentlet my-agent --debug --prompt "Task"
```

**Output**:
- DEBUG level logs to stdout
- Log file created: `agentlet-core-YYYYMMDD-HHMMSS.log`
- Detailed SDK/framework logs
- Configuration values shown

**Example**:
```
✓ Environment variables loaded from .env file
ℹ Loading configuration from simple-assistant.yaml
DEBUG: Config data keys: ['agentlet', 'model', 'system_prompt', ...]
✓ Configuration loaded successfully
DEBUG: Model ID: bedrock/claude-sonnet-4-6
DEBUG: Retry config: max_retries=5, backoff_factor=2.0
ℹ Agentlet spawned: simple-assistant v1.0.0
DEBUG: Working directory: /tmp/agentlet-xyz
✓ OpenTelemetry configured
DEBUG: OTLP endpoint: http://localhost:4318
ℹ MCP server 'filesystem' initialized
DEBUG: Loaded 8 tools from MCP server
...
```

**Log file location**: `./agentlet-core-YYYYMMDD-HHMMSS.log`

### Log Levels

**INFO** (default):
- Agent lifecycle events (spawn, execute, terminate)
- Tool calls and results
- Execution summary
- Errors and warnings

**DEBUG** (with `--debug`):
- Configuration details
- Model parameters
- MCP tool initialization
- Token usage
- Retry attempts
- Internal state changes

## Exit Codes and Error Handling

### Exit Codes

| Code | Meaning | Cause |
|------|---------|-------|
| 0 | Success | Normal execution completed |
| 1 | Error | General error (config, API, tool failure) |
| 130 | Interrupted | User pressed Ctrl+C |

### Common Errors

#### Configuration Not Found

```bash
Error: No agentlet configuration found. Create a config file or specify --agentlet
```

**Solution**: Provide `--agentlet` or create config in search paths.

#### Missing Prompt

```bash
Error: No prompt provided. Use --prompt or define in config file.
```

**Solution**: Add `--prompt` or define `prompt` in config.

#### Invalid API Key

```bash
Error: Unauthorized: Invalid or missing API key.
```

**Solution**: Set appropriate environment variable (e.g., `ANTHROPIC_API_KEY`).

#### Timeout

```bash
Error: Execution timed out after 300s
```

**Solution**: Increase timeout with `--timeout`.

#### Rate Limit

```
⚠ Rate limit error (attempt 1/5): ...
ℹ Retrying in 30.0s...
```

**Solution**: Wait for automatic retry or adjust retry config.

### Error Handling Flow

1. **Configuration errors**: Fail fast with validation error
2. **API errors**: Retry with exponential backoff
3. **Tool errors**: Log and continue (unless fatal)
4. **Timeout**: Terminate and cleanup
5. **User interrupt**: Graceful cleanup and exit

## Common Use Cases

### Quick Task Execution

```bash
# Run simple task with default config
uv run agentlet-core --agentlet simple-assistant --prompt "Summarize quantum computing"
```

### Development Workflow

```bash
# Debug mode with custom model
uv run agentlet-core --agentlet my-agent \
  --model "bedrock/claude-sonnet-4-6" \
  --debug \
  --prompt "Analyze this codebase"
```

### Production Deployment

```bash
# With observability and resource limits
agentlet-core --agentlet production-agent \
  --timeout 600 \
  --max-tokens 50000 \
  --otel-enabled \
  --otlp-endpoint "http://collector:4318" \
  --prompt "Process customer request"
```

### Batch Processing

```bash
# Process multiple prompts
for task in task1.txt task2.txt task3.txt; do
  agentlet-core --agentlet batch-processor \
    --prompt "$(cat $task)" \
    --output-format json > "result-$task.json"
done
```

### CI/CD Integration

```bash
#!/bin/bash
set -e

# Load environment
source .env

# Run agentlet with timeout and JSON output
agentlet-core --agentlet ci-agent \
  --prompt "Run code quality checks" \
  --timeout 300 \
  --output-format json \
  --max-retries 3 > report.json

# Check exit code
if [ $? -eq 0 ]; then
  echo "✓ Agentlet execution succeeded"
else
  echo "✗ Agentlet execution failed"
  exit 1
fi
```

## Performance Tips

**Optimize token usage**:
- Use `--max-tokens` to limit context
- Filter MCP tools to only needed ones
- Keep system prompts concise

**Reduce latency**:
- Enable streaming mode
- Use lower temperature for faster responses
- Place OTLP collector close to runtime

**Handle rate limits**:
- Adjust retry configuration
- Use backoff factor 2.0 or higher
- Increase initial retry interval

**Debug efficiently**:
- Use `--debug` only when needed
- Check log files for historical issues
- Enable console exporter for trace debugging

## Next Steps

- **[Configuration](configuration.md)** - Complete configuration reference
- **[MCP Integration](mcp-integration.md)** - Advanced MCP tools usage

