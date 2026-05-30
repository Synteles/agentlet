# Configuration System

Configuration flows from YAML/JSON files through Pydantic validation, with environment variable expansion and CLI override at the edges.

## Flow

```
CLI Arguments                Config File
     │                            │
     │                            ▼
     │                     Loader (search paths)
     │                            │
     │                            ▼
     │                     YAML / JSON parser
     │                            │
     │                            ▼
     │                     Environment expansion ($VAR / ${VAR})
     │                            │
     │                            ▼
     │                     Pydantic validation
     │                            │
     └────────────────────────────▶
                                  ▼
                          AgentletConfig
```

**Precedence:** CLI arguments override config file values, which override Pydantic defaults.

## Schema

All models live in `config/models.py`. Fields marked ✱ are required; all others have defaults.

### Root: `AgentletConfig`

| Field | Type | Description |
|-------|------|-------------|
| `agentlet` ✱ | `AgentletMetadata` | Name and version |
| `system_prompt` ✱ | `str` | Agent instructions |
| `model` ✱ | `ModelConfig` | LLM provider settings |
| `prompt` | `str` | Default prompt (overridden by `--prompt`) |
| `tools` | `list[str]` | Strands built-in tools |
| `mcp_tools` | `list[MCPToolConfig]` | MCP protocol tools |
| `sub_agentlets` | `list[SubAgentletConfig]` | Inline sub-agents (mutually exclusive with `swarm`) |
| `swarm` | `SwarmConfig` | Swarm mode (mutually exclusive with `sub_agentlets`) |
| `resource_limits` | `ResourceLimits` | Execution constraints |
| `output` | `OutputConfig` | Display preferences |
| `observability` | `ObservabilityConfig` | OTel settings |

### `AgentletMetadata`

| Field | Default | Description |
|-------|---------|-------------|
| `name` ✱ | — | Agentlet identifier |
| `version` | `"1.0.0"` | Semantic version |

### `ModelConfig`

| Field | Default | Description |
|-------|---------|-------------|
| `provider` ✱ | — | LiteLLM provider (`anthropic`, `bedrock`, `openai`, `azure`, …) |
| `model_id` ✱ | — | Model identifier |
| `parameters` | `{}` | Passed through to LiteLLM |
| `retry` | See below | Retry behaviour |

### `RetryConfig` (nested under `model.retry`)

| Field | Default | Description |
|-------|---------|-------------|
| `max_retries` | `5` | Maximum retry attempts |
| `initial_retry_interval` | `30.0` s | First wait before retry |
| `backoff_factor` | `2.0` | Exponential multiplier |
| `max_retry_interval` | `300.0` s | Wait cap |
| `retry_on_errors` | `["RateLimitError", "EventLoopException", "APIConnectionError", "APITimeoutError", "litellm.RateLimitError"]` | Error names that trigger a retry |

### `MCPToolConfig`

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Identifier |
| `server` | Yes | `"stdio"`, `"http"`, or `"sse"` |
| `command` | stdio only | Subprocess command |
| `args` | stdio | Command arguments |
| `url` | http / sse | Server URL |
| `headers` | http | Custom HTTP headers |
| `api_key_env` | — | Env var holding the API key (added as `Bearer` auth) |
| `env` | — | Env vars forwarded to the subprocess |
| `prefix` | — | Tool name prefix (`fs_` → `fs_read_file`) |
| `tool_filters` | — | `{"allowed": [...], "rejected": [...]}` |

### `ResourceLimits`

| Field | Default | Description |
|-------|---------|-------------|
| `max_execution_time` | `300` s | Hard wall-clock timeout |
| `max_tokens` | `10000` | Passed as `max_tokens` to the model |
| `max_tool_calls` | `20` | Maximum tool invocations per execution |

### `OutputConfig`

| Field | Default | Description |
|-------|---------|-------------|
| `format` | `"markdown"` | `"markdown"`, `"json"`, or `"text"` |
| `show_messages` | `true` | Show assistant messages |
| `show_reasoning` | `true` | Show extended thinking blocks |
| `show_tool_calls` | `true` | Show tool invocations and results |
| `show_turn_boundaries` | `false` | Show turn-boundary dividers |

### `OTELConfig` (nested under `observability.otel`)

| Field | Default | Description |
|-------|---------|-------------|
| `enabled` | `false` | Enable OTel export |
| `otlp_endpoint` | — | Base OTLP endpoint |
| `otlp_traces_endpoint` | — | Traces-specific endpoint (overrides base) |
| `otlp_metrics_endpoint` | — | Metrics-specific endpoint (overrides base) |
| `otlp_headers` | `{}` | Headers sent with every OTLP request |
| `console_exporter` | `false` | Print traces to console (debug) |
| `sampler` | — | `always_on`, `always_off`, `traceidratio`, `parentbased_*` |
| `sampler_arg` | — | Sampling ratio for `traceidratio` (e.g., `0.1` = 10%) |
| `enable_metrics` | `false` | Enable metrics export |
| `trace_attributes` | `{}` | Custom key-value attributes added to every span |

## Config Loading

### Search Paths

`ConfigLoader` in `config/loader.py` resolves configurations in this order:

```
config_path provided?
  │
  ├─ Yes — valid file path?   → load directly
  │
  ├─ Yes — name only?         → search for {name}.yaml / {name}.yml
  │                               CWD → ~/.synteles/agentlets → ./.synteles/agentlets
  │
  └─ No                       → auto-discover first *.yaml / *.yml / *.json
                                  CWD → ~/.synteles/agentlets → ./.synteles/agentlets
```

Name-based lookup only matches `.yaml` and `.yml`. Auto-discovery also matches `.json`.

### Environment Variable Expansion

`$VAR` and `${VAR}` are expanded by `os.path.expandvars()` **before** YAML/JSON parsing, so substitution works anywhere in the file — values, multi-line strings, even YAML keys.

`${WORK_DIR}` is a special runtime variable expanded by `MCPToolsManager` at spawn time; it resolves to the agentlet's working directory (the `--path` value or the temp dir).

### CLI Overrides

| CLI flag | Config field |
|----------|-------------|
| `--model provider/model_id` | `model.provider`, `model.model_id` |
| `--timeout N` | `resource_limits.max_execution_time` |
| `--max-tokens N` | `resource_limits.max_tokens` |
| `--output-format fmt` | `output.format` |
| `--max-retries N` | `model.retry.max_retries` |
| `--initial-retry-interval F` | `model.retry.initial_retry_interval` |
| `--backoff-factor F` | `model.retry.backoff_factor` |
| `--otel-enabled` | `observability.otel.enabled` |
| `--otlp-endpoint URL` | `observability.otel.otlp_endpoint` |
| `--otlp-traces-endpoint URL` | `observability.otel.otlp_traces_endpoint` |
| `--otlp-metrics-endpoint URL` | `observability.otel.otlp_metrics_endpoint` |
| `--otel-console` | `observability.otel.console_exporter` |

## Validation

Pydantic validates the config after parsing. Cross-field rules enforced by validators:

- `stdio` requires `command`; `http`/`sse` require `url`
- `tool_filters` only accepts `allowed` and `rejected` keys
- `sub_agentlets` and `swarm` are mutually exclusive

Common errors and fixes:

| Error | Fix |
|-------|-----|
| `agentlet.name` missing | Add `agentlet:\n  name: my-agent` |
| `command` required for stdio | Add `command: npx` to the MCP tool |
| `url` required for http/sse | Add `url: https://…` |
| Invalid `tool_filters` key | Use `allowed` or `rejected` (not `blocked`, `whitelist`, etc.) |
| `sub_agentlets` + `swarm` both set | Remove one — they are mutually exclusive |

## Configuration Examples

### Minimal

```yaml
agentlet:
  name: simple-assistant

model:
  provider: anthropic
  model_id: claude-sonnet-4-6

system_prompt: "You are a helpful assistant."
```

### Full

```yaml
agentlet:
  name: advanced-agent
  version: 2.0.0

prompt: "Analyze the codebase and provide insights"

system_prompt: |
  You are an expert code analyst. Provide detailed, actionable insights.

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

mcp_tools:
  - name: filesystem
    server: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "${WORK_DIR}"]
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

resource_limits:
  max_execution_time: 600
  max_tokens: 20000
  max_tool_calls: 50

output:
  format: markdown
  show_messages: true
  show_reasoning: true
  show_tool_calls: true
  show_turn_boundaries: false

observability:
  otel:
    enabled: true
    otlp_traces_endpoint: http://localhost:4318/v1/traces
    otlp_metrics_endpoint: http://localhost:4318/v1/metrics
    otlp_headers:
      x-api-key: ${OTEL_API_KEY}
    sampler: always_on
    enable_metrics: true
    trace_attributes:
      environment: production
      team: platform
```

## Best Practices

- **Store secrets in environment variables** — use `$VAR` expansion or `api_key_env`, never hardcode.
- **Version your configs** — bump `agentlet.version` when the config changes; it surfaces in traces.
- **Use search paths for multi-environment setups** — place configs in `~/.synteles/agentlets/` and reference by name (`--agentlet production`).
- **Validate before deploying** — run `agentlet-core --agentlet my-config.yaml --prompt "ping"` or dry-run the loader to catch schema errors early.

## Related Documentation

- [Architecture Overview](./overview.md)
- [Agent Lifecycle](./agent-lifecycle.md)
- [Tool Management](./tool-management.md)
- [Reference: Configuration](../reference/configuration.md)
