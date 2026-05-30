# Tool Management

Agentlet-core exposes two tool categories through a two-manager architecture that handles loading, connection lifecycle, and cleanup.

## Architecture

```
                     BaseAgentlet.spawn()
                              │
         ┌────────────────────┴───────────────────┐
         │                                         │
 DefaultToolsManager                       MCPToolsManager
         │                                         │
 Lazy-imports from                   Creates one MCPClient per entry
 strands_tools.*                               │
         │                        ┌─────────────┼─────────────┐
     default_tools             stdio           http           sse
                            (subprocess)    (remote)      (streaming)
         │                          │            │             │
         └──────────────────────────┴────────────┴─────────────┘
                               all_tools
                                  │
                        Strands Agent(tools=all_tools)
```

## Default Tools

`DefaultToolsManager` lazy-imports tools from the `strands-agents-tools` package. Each name in `tools:` maps to `strands_tools.{name}` — imported on first use and cached for the lifetime of the agentlet.

`BYPASS_TOOL_CONSENT=true` is set automatically; agentlet-core is designed for unattended execution.

**Available tools:**

| Name | Description |
|------|-------------|
| `bash` | Execute shell commands |
| `file_editor` | Read, write, and edit files with line-level precision |
| `computer` | Screen capture, mouse, and keyboard control |
| `web_browser` | Web browsing |
| `memory` | Persistent in-session memory |

**Configuration:**
```yaml
tools:
  - bash
  - file_editor
```

## MCP Tools

`MCPToolsManager` follows a **manual context management** pattern:

```
initialize()      → create MCPClient instances (no connections yet)
enter_contexts()  → open connections (spawn subprocess / HTTP session / SSE stream)
get_tools_sync()  → retrieve tool definitions from each server
[agent runs]
exit_contexts()   → close all connections; best-effort, logs errors and continues
```

Manual sequencing (vs. async context managers) gives precise rollback if a connection fails mid-init, and avoids asyncio recursion during cleanup.

### stdio — Local Subprocess

Spawns an MCP server as a child process communicating over stdin/stdout.

```yaml
mcp_tools:
  - name: filesystem
    server: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "${WORK_DIR}"]
    env:
      ALLOWED_DIRECTORIES: ${WORK_DIR}
    prefix: fs_
```

The subprocess is spawned on `enter_contexts()` and terminated with SIGTERM → SIGKILL (with timeout) on `exit_contexts()`.

### HTTP — Remote Server

Connects to a remote MCP server via streamable HTTP.

```yaml
mcp_tools:
  - name: web_search
    server: http
    url: https://api.example.com/mcp
    api_key_env: SEARCH_API_KEY
    headers:
      User-Agent: agentlet-core/1.0
    tool_filters:
      allowed: [search_web, fetch_url]
```

When `api_key_env` is set, the key is read from the environment and added as a `Bearer` token in the `Authorization` header. Custom `headers` are merged on top.

### SSE — Server-Sent Events

Long-lived connection for streaming event sources.

```yaml
mcp_tools:
  - name: events
    server: sse
    url: https://api.example.com/sse?token=${SSE_TOKEN}
```

> **Limitation:** The SSE transport does not support custom headers. Include auth in the URL or handle it server-side.

## Tool Filtering

Controls which tools from a server are visible to the agent:

```yaml
tool_filters:
  allowed:  [read_file, write_file]   # whitelist — only these tools exposed
  rejected: [delete_*, admin_*]       # blacklist — always excluded
```

`rejected` takes precedence over `allowed`. Glob patterns (`*`, `?`) are supported. Both keys can be specified simultaneously.

## Tool Prefixing

Prevents name collisions when multiple servers expose identically-named tools:

```yaml
mcp_tools:
  - name: local_fs
    server: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/local"]
    prefix: local_

  - name: remote_fs
    server: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/remote"]
    prefix: remote_
```

Result: `local_read_file`, `local_write_file`, `remote_read_file`, `remote_write_file`.

## `${WORK_DIR}` Expansion

`${WORK_DIR}` in MCP `env` values and `args` is substituted at spawn time with the agentlet's working directory (the `--path` value or the session temp dir). Use it to confine filesystem tools to the agent's workspace:

```yaml
mcp_tools:
  - name: filesystem
    server: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "${WORK_DIR}"]
    env:
      ALLOWED_DIRECTORIES: ${WORK_DIR}
```

## Security

- **Store API keys in environment variables** — use `api_key_env` or `${VAR}` expansion in `headers`. Never hardcode credentials in config files.
- **Reject dangerous tools** via `tool_filters.rejected` — especially `delete_*`, `drop_*`, `format_*`, `truncate_*`.
- **Confine filesystem access** with `ALLOWED_DIRECTORIES: ${WORK_DIR}`.
- The `stdio` subprocess inherits the parent process's environment. Use the tool's `env` field to scope or override what it sees.

## Error Handling

| Phase | Behaviour |
|-------|-----------|
| `initialize()` | Raises `RuntimeError` immediately on unknown server type or missing required fields |
| `enter_contexts()` | Rolls back already-entered contexts on failure, then raises `RuntimeError` |
| `get_tools_sync()` | Raises on protocol error, invalid response, or lost connection |
| `exit_contexts()` | Best-effort: logs each failure, continues to remaining clients |

## Swarm Mode

When `swarm:` is configured, the top-level `mcp_tools` list is **ignored** (a warning is logged). MCP tools for swarm participants are declared per-participant inside the `swarm` config block. The top-level `tools` list still applies to the entry-point agent.

## Related Documentation

- [Architecture Overview](./overview.md)
- [Agent Lifecycle](./agent-lifecycle.md)
- [Configuration System](./configuration-system.md)
- [Reference: MCP Integration](../reference/mcp-integration.md)
