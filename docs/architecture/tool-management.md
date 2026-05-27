# Tool Management

This document details the tool loading, lifecycle, and integration patterns in agentlet-core.

## Overview

Agentlet-core supports two types of tools:
1. **Default Tools:** Pre-built tools from `strands-agents-tools` package
2. **MCP Tools:** External tools via Model Context Protocol (stdio/HTTP/SSE)

**Key Features:**
- Lazy loading of default tools
- Multi-transport MCP support (stdio, HTTP, SSE)
- Tool filtering and prefixing
- Manual context management pattern
- Clean resource lifecycle

## Tool Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Tool Management                           │
└─────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────┐
  │                      BaseAgentlet                             │
  │                                                               │
  │  ┌─────────────────────────────────────────────────────┐    │
  │  │                 spawn() Phase                       │    │
  │  │                                                     │    │
  │  │  ┌──────────────────┐      ┌───────────────────┐  │    │
  │  │  │ DefaultToolsManager     │ MCPToolsManager   │  │    │
  │  │  │                  │      │                   │  │    │
  │  │  │ - Lazy load      │      │ - Initialize      │  │    │
  │  │  │ - From strands   │      │ - Enter contexts  │  │    │
  │  │  │ - Cache modules  │      │ - Get tools       │  │    │
  │  │  └────────┬─────────┘      └─────────┬─────────┘  │    │
  │  │           │                           │            │    │
  │  │           ▼                           ▼            │    │
  │  │     default_tools              mcp_tools          │    │
  │  │           │                           │            │    │
  │  │           └──────────┬────────────────┘            │    │
  │  │                      ▼                             │    │
  │  │                 all_tools                          │    │
  │  │                      │                             │    │
  │  │                      ▼                             │    │
  │  │            Strands Agent(tools=all_tools)         │    │
  │  └─────────────────────────────────────────────────────┘    │
  └──────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────┐
  │                    Tool Transports                            │
  │                                                               │
  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
  │  │   stdio      │  │    HTTP      │  │     SSE      │       │
  │  │              │  │              │  │              │       │
  │  │ - Subprocess │  │ - Streamable │  │ - Server     │       │
  │  │ - Pipes      │  │ - REST API   │  │ - Events     │       │
  │  │ - Env vars   │  │ - Headers    │  │ - Streaming  │       │
  │  └──────────────┘  └──────────────┘  └──────────────┘       │
  └──────────────────────────────────────────────────────────────┘
```

## Default Tools Manager

The `DefaultToolsManager` (`tools/tools_manager.py`) handles loading of pre-built tools from the `strands-agents-tools` package.

### Architecture

```python
class DefaultToolsManager:
    """
    Manages default tools with lazy loading from strands_tools.
    """

    def __init__(self, *tool_names: str, logger: Optional[RichLoggerAdapter] = None):
        """
        Initialize tools manager.

        Args:
            *tool_names: Names of tools to manage
            logger: Logger instance
        """
        if "BYPASS_TOOL_CONSENT" not in os.environ:
            os.environ["BYPASS_TOOL_CONSENT"] = "true"

        self.logger = logger or RichLoggerAdapter(get_logger(__name__))
        self._tools: dict[str, Any] = {}
        self._requested_tools = set(tool_names)
```

**Key features:**
- Auto-sets `BYPASS_TOOL_CONSENT=true` (for non-interactive use)
- Lazy loading (tools loaded on first access)
- Module caching (loaded once, reused)
- Simple interface

### Lazy Loading Pattern

```python
def get_tool(self, tool_name: str) -> Any:
    """
    Get tool by name, loading it lazily if not already loaded.

    Args:
        tool_name: Name of the tool to load

    Returns:
        The loaded tool module

    Raises:
        ImportError: If tool cannot be imported from strands_tools
    """
    if tool_name not in self._tools:
        self.logger.info(f"Loading tool: {tool_name}")

        try:
            module = importlib.import_module(f"strands_tools.{tool_name}")
            self._tools[tool_name] = module
            self.logger.success(
                f"Tool '{tool_name}' loaded successfully from strands_tools"
            )
        except ImportError as error:
            self.logger.error(
                f"Failed to import tool '{tool_name}' from strands_tools: {error}"
            )
            raise ImportError(
                f"Could not import tool '{tool_name}' from strands_tools"
            ) from error

    return self._tools[tool_name]
```

**Loading flow:**
1. Check if tool already cached
2. If not, import from `strands_tools.{name}`
3. Cache the module
4. Return module reference

### Getting All Tools

```python
def get_tools(self) -> list[Any]:
    """Get all requested tools, loading them if needed."""
    return [self.get_tool(name) for name in self._requested_tools]
```

**Returns:** List of tool modules ready for Strands Agent

### Usage Example

```python
# Configuration
tools:
  - bash
  - file_editor
  - computer

# In BaseAgentlet.spawn()
default_tools = (
    DefaultToolsManager(*self.config.tools).get_tools()
    if self.config.tools
    else []
)

# Loads: strands_tools.bash, strands_tools.file_editor, strands_tools.computer
```

### Available Default Tools

From `strands-agents-tools` package:

- **bash:** Execute shell commands
- **file_editor:** Read/write/edit files
- **computer:** Screen capture and mouse/keyboard control
- **web_browser:** Web browsing capabilities
- **memory:** Persistent memory storage

**Installation:**
```bash
uv sync --group dev  # Includes strands-agents-tools
```

### Tool Consent Bypass

```python
if "BYPASS_TOOL_CONSENT" not in os.environ:
    os.environ["BYPASS_TOOL_CONSENT"] = "true"
```

**Why?**
- Strands tools require user consent for dangerous operations
- Agentlet-core is designed for non-interactive use
- Configuration implies consent
- Auto-setting ensures smooth execution

## MCP Tools Manager

The `MCPToolsManager` (`tools/mcp_manager.py`) manages external tools via the Model Context Protocol.

### Architecture

```python
class MCPToolsManager:
    """
    Manages MCP tools lifecycle and integration using Strands agents SDK.

    Supports stdio, HTTP (streamable), and SSE server types.
    Uses Strands' MCPClient for proper integration with Agent framework.
    """

    def __init__(
        self,
        tools_config: list[MCPToolConfig],
        working_dir: Optional[str] = None,
        logger: Optional[RichLoggerAdapter] = None,
    ):
        self.tools_config = tools_config
        self.working_dir = working_dir or os.getcwd()
        self.logger = logger or RichLoggerAdapter(get_logger(__name__))
        self._mcp_clients: list[MCPClient] = []
        self._stdio_processes: list[tuple[str, str]] = []  # Track for cleanup
```

### Manual Context Management Pattern

**Why Manual Context Management?**
- More control over context lifecycle
- Better error handling during initialization
- Explicit resource management
- Production-proven pattern
- Avoids async context manager complexity

**Pattern:**
```python
# 1. Initialize (create client instances)
manager.initialize()

# 2. Enter contexts (establish connections)
manager.enter_contexts()

# 3. Use tools (requires active context)
tools = manager.get_tools_sync()

# 4. Exit contexts (cleanup)
manager.exit_contexts()
```

### Lifecycle Methods

#### 1. Initialize

```python
def initialize(self) -> list[MCPClient]:
    """
    Initialize all configured MCP tools and return MCPClient instances.

    Returns:
        List of MCPClient instances ready to be passed to Agent

    Raises:
        RuntimeError: If tool initialization fails
    """
    self.logger.info(f"Initializing {len(self.tools_config)} MCP tool server(s)...")

    for tool_config in self.tools_config:
        try:
            if tool_config.server == "stdio":
                client = self._create_stdio_client(tool_config)
            elif tool_config.server == "http":
                client = self._create_http_client(tool_config)
            elif tool_config.server == "sse":
                client = self._create_sse_client(tool_config)
            else:
                raise ValueError(f"Unsupported server type: {tool_config.server}")

            self._mcp_clients.append(client)
            self.logger.success(
                f"MCP server '{tool_config.name}' ({tool_config.server}) initialized"
            )

        except Exception as e:
            self.logger.error(
                f"Failed to initialize MCP server '{tool_config.name}': {e}"
            )
            raise RuntimeError(
                f"Failed to initialize MCP server '{tool_config.name}'"
            ) from e

    return self._mcp_clients
```

**Creates MCPClient instances without establishing connections.**

#### 2. Enter Contexts

```python
def enter_contexts(self) -> None:
    """
    Enter all MCP client contexts.

    This must be called before using MCP tools. Each MCPClient's __enter__
    is called to establish connections.

    Raises:
        RuntimeError: If context entry fails
    """
    self.logger.info(
        f"Entering context for {len(self._mcp_clients)} MCP client(s)..."
    )

    for i, client in enumerate(self._mcp_clients):
        try:
            client.__enter__()
            self.logger.debug_log(f"MCP client {i + 1} context entered")
        except Exception as e:
            self.logger.error(
                f"Failed to enter context for MCP client {i + 1}: {e}"
            )
            # Rollback: exit already-entered contexts
            for j in range(i):
                try:
                    self._mcp_clients[j].__exit__(None, None, None)
                except Exception:
                    pass  # Ignore rollback errors
            raise RuntimeError(f"Failed to enter MCP client context {i + 1}") from e

    self.logger.success("All MCP client contexts entered successfully")
```

**Establishes connections (stdio pipes, HTTP sessions, SSE connections).**

**Error handling:**
- Best-effort rollback on failure
- Exit already-entered contexts
- Preserve original error

#### 3. Get Tools

```python
def get_tools_sync(self) -> list[Any]:
    """
    Get all tools from all MCP clients synchronously.

    This method collects tools from all initialized MCP clients by calling
    list_tools_sync() on each. Must be called within an active context
    (after enter_contexts()).

    Returns:
        List of tool objects from all MCP servers

    Raises:
        RuntimeError: If called outside of an active context
    """
    all_tools: list[Any] = []
    for client in self._mcp_clients:
        try:
            tools = client.list_tools_sync()
            all_tools.extend(tools)
            self.logger.info(f"Loaded {len(tools)} tool(s) from MCP server")
        except Exception as e:
            self.logger.error(f"Failed to list tools from MCP client: {e}")
            raise

    return all_tools
```

**Requires active context (after enter_contexts()).**

#### 4. Exit Contexts

```python
def exit_contexts(self) -> None:
    """
    Exit all MCP client contexts.

    This should be called during cleanup to properly close MCP connections.
    Attempts to exit all contexts even if some fail.
    """
    self.logger.info(
        f"Exiting context for {len(self._mcp_clients)} MCP client(s)..."
    )

    errors = []
    for i, client in enumerate(self._mcp_clients):
        try:
            client.__exit__(None, None, None)
            self.logger.debug_log(f"MCP client {i + 1} context exited")
        except Exception as e:
            error_msg = f"Failed to exit context for MCP client {i + 1}: {e}"
            self.logger.warning(error_msg)
            errors.append(error_msg)

    if errors:
        self.logger.warning(
            f"Encountered {len(errors)} error(s) during context exit"
        )
    else:
        self.logger.success("All MCP client contexts exited successfully")
```

**Best-effort cleanup (continues even if some fail).**

#### 5. Cleanup

```python
def cleanup_sync(self) -> None:
    """
    Synchronous cleanup of all MCP resources.

    This method exits all MCP client contexts and cleans up any resources.
    Safe to call multiple times.
    """
    if not self._mcp_clients:
        return

    self.logger.info("Cleaning up MCP resources...")
    self.exit_contexts()
    self.logger.success("MCP cleanup completed")
```

**Public cleanup method for external use.**

## MCP Transport Types

### stdio Transport

**Use case:** Local MCP servers run as subprocesses (e.g., npx MCP servers)

#### Creating stdio Client

```python
def _create_stdio_client(self, config: MCPToolConfig) -> MCPClient:
    """Create stdio-based MCP client."""
    if not config.command:
        raise ValueError(f"command is required for stdio server '{config.name}'")

    # Prepare environment variables
    env = os.environ.copy()
    env.update(config.env)

    # Expand ${WORK_DIR} in environment variables
    for key, value in env.items():
        env[key] = value.replace("${WORK_DIR}", self.working_dir)

    # Expand ${WORK_DIR} in command arguments
    expanded_args = [
        arg.replace("${WORK_DIR}", self.working_dir) for arg in config.args
    ]

    # Create stdio server parameters
    server_params = StdioServerParameters(
        command=config.command,
        args=expanded_args,
        env=env,
    )

    # Create MCPClient with stdio transport
    mcp_client = MCPClient(
        lambda: stdio_client(server_params),
        prefix=config.prefix,
        tool_filters=cast(ToolFilters, config.tool_filters)
        if config.tool_filters
        else None,
    )

    # Track process info for cleanup
    self._stdio_processes.append((config.name, config.command))

    return mcp_client
```

**Key features:**
- Subprocess with stdin/stdout/stderr pipes
- Environment variable expansion
- `${WORK_DIR}` substitution
- Process tracking for cleanup

#### Configuration Example

```yaml
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
      LOG_LEVEL: info
```

#### stdio Process Lifecycle

```
initialize()
    │
    └─▶ Create MCPClient with lambda: stdio_client(params)
        (No subprocess started yet)

enter_contexts()
    │
    └─▶ client.__enter__()
        │
        └─▶ Spawn subprocess
            ├─▶ Open stdin/stdout/stderr pipes
            └─▶ MCP handshake

get_tools_sync()
    │
    └─▶ client.list_tools_sync()
        │
        └─▶ Send MCP list_tools request
            └─▶ Receive tool definitions

[Agent uses tools via MCP protocol]

exit_contexts()
    │
    └─▶ client.__exit__(None, None, None)
        │
        ├─▶ Close stdin pipe
        ├─▶ Wait for process termination (timeout)
        ├─▶ SIGTERM if still running
        ├─▶ Wait again (timeout)
        └─▶ SIGKILL if still running (force terminate)
```

### HTTP Transport

**Use case:** Remote MCP servers with HTTP API (streamable)

#### Creating HTTP Client

```python
def _create_http_client(self, config: MCPToolConfig) -> MCPClient:
    """Create HTTP (streamable) MCP client."""
    if not config.url:
        raise ValueError(f"url is required for http server '{config.name}'")

    url: str = config.url

    # Prepare headers
    headers = config.headers.copy()

    # Add API key from environment if specified
    if config.api_key_env:
        api_key = os.getenv(config.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"API key not found in environment: {config.api_key_env}"
            )
        # Add Authorization header if not already present
        if "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {api_key}"

    # Create MCPClient with streamable HTTP transport
    mcp_client = MCPClient(
        lambda: streamablehttp_client(
            url=url,
            headers=headers if headers else None,
        ),
        prefix=config.prefix,
        tool_filters=cast(ToolFilters, config.tool_filters)
        if config.tool_filters
        else None,
    )

    return mcp_client
```

**Key features:**
- REST API communication
- Custom headers support
- API key from environment
- Bearer token authentication

#### Configuration Example

```yaml
mcp_tools:
  - name: web_search
    server: http
    url: https://api.example.com/mcp
    api_key_env: SEARCH_API_KEY
    headers:
      User-Agent: agentlet-core/1.0
      Accept: application/json
    tool_filters:
      allowed:
        - search_web
        - fetch_url
```

### SSE Transport

**Use case:** Server-Sent Events streaming (real-time updates)

#### Creating SSE Client

```python
def _create_sse_client(self, config: MCPToolConfig) -> MCPClient:
    """Create SSE (Server-Sent Events) MCP client."""
    if not config.url:
        raise ValueError(f"url is required for sse server '{config.name}'")

    url: str = config.url

    # Note: SSE client currently doesn't support custom headers
    if config.api_key_env:
        self.logger.warning(
            f"SSE server '{config.name}': api_key_env is set but SSE client "
            "doesn't support custom headers. Include auth in URL or server-side."
        )

    # Create MCPClient with SSE transport
    mcp_client = MCPClient(
        lambda: sse_client(url),
        prefix=config.prefix,
        tool_filters=cast(ToolFilters, config.tool_filters)
        if config.tool_filters
        else None,
    )

    return mcp_client
```

**Key features:**
- Real-time event streaming
- Server push notifications
- Long-lived connections

**Limitations:**
- No custom headers support (auth must be in URL or server-side)

#### Configuration Example

```yaml
mcp_tools:
  - name: notifications
    server: sse
    url: https://api.example.com/sse?token=YOUR_TOKEN
```

## Tool Filtering and Prefixing

### Tool Filtering

**Purpose:** Control which tools are exposed to the agent

**Configuration:**
```yaml
mcp_tools:
  - name: web_search
    server: http
    url: https://api.example.com/mcp
    tool_filters:
      allowed:
        - search_web
        - fetch_url
        - get_page_content
      rejected:
        - admin_*
        - delete_*
```

**Behavior:**
- `allowed`: Whitelist (only these tools exposed)
- `rejected`: Blacklist (exclude these tools)
- Patterns: Supports glob-like patterns (`*`, `?`)
- Precedence: `rejected` takes precedence over `allowed`

**Implementation:**
```python
mcp_client = MCPClient(
    transport_factory,
    tool_filters={"allowed": [...], "rejected": [...]}
)
```

### Tool Prefixing

**Purpose:** Avoid naming conflicts when multiple MCP servers provide tools with same names

**Configuration:**
```yaml
mcp_tools:
  - name: filesystem_local
    server: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/local"]
    prefix: local_

  - name: filesystem_remote
    server: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/remote"]
    prefix: remote_
```

**Result:**
- Local filesystem tools: `local_read_file`, `local_write_file`, `local_list_directory`
- Remote filesystem tools: `remote_read_file`, `remote_write_file`, `remote_list_directory`

**Implementation:**
```python
mcp_client = MCPClient(
    transport_factory,
    prefix="fs_"
)
```

### Combined Example

```yaml
mcp_tools:
  - name: database
    server: http
    url: https://api.example.com/db-mcp
    prefix: db_
    tool_filters:
      allowed:
        - query
        - insert
        - update
      rejected:
        - drop_*
        - truncate_*
```

**Exposed tools:**
- `db_query`
- `db_insert`
- `db_update`

**Hidden tools:**
- `db_drop_table` (rejected)
- `db_truncate_table` (rejected)
- Any other tools (not in allowed list)

## Usage in BaseAgentlet

### Integration in spawn() Phase

```python
async def spawn(self, working_dir: Optional[str] = None) -> None:
    """Initialize agentlet execution context."""
    # ... context creation ...

    # Initialize MCP tools using Manual Context Management
    mcp_tools = []
    if self.config.mcp_tools:
        self._mcp_manager = MCPToolsManager(
            tools_config=self.config.mcp_tools,
            working_dir=str(self.context.working_dir),
            logger=self.logger,
        )

        # Step 1: Initialize MCP clients
        self._mcp_manager.initialize()

        # Step 2: Enter MCP client contexts (Manual Context Management)
        self._mcp_manager.enter_contexts()

        # Step 3: Get actual tools from MCP clients (requires active context)
        mcp_tools = self._mcp_manager.get_tools_sync()

    # Get default tools (bash, file_editor, etc.)
    default_tools = (
        DefaultToolsManager(*self.config.tools).get_tools()
        if self.config.tools
        else []
    )

    # Combine default tools with MCP tools
    all_tools = default_tools + mcp_tools

    # Create agent with all tools
    self._agent = Agent(
        model=model,
        tools=all_tools,
        # ...
    )
```

### Cleanup in terminate() Phase

```python
async def terminate(self) -> None:
    """Clean up resources and terminate agentlet."""
    # Cleanup MCP tools
    if self._mcp_manager:
        self._mcp_manager.cleanup_sync()

    # ... other cleanup ...
```

## Error Handling

### Initialization Errors

```python
try:
    manager.initialize()
except RuntimeError as e:
    # MCP server not found (command doesn't exist)
    # Invalid URL
    # Configuration error
    logger.error(f"Failed to initialize MCP tools: {e}")
    raise
```

**Common errors:**
- Command not found (stdio)
- Invalid URL (http/sse)
- Missing required fields
- Network errors

### Context Entry Errors

```python
try:
    manager.enter_contexts()
except RuntimeError as e:
    # Connection timeout
    # MCP handshake failure
    # Subprocess spawn failure
    logger.error(f"Failed to enter MCP contexts: {e}")
    # Rollback happens automatically
    raise
```

**Recovery:**
- Automatic rollback of entered contexts
- Clear error messages
- No partial state

### Tool Listing Errors

```python
try:
    tools = manager.get_tools_sync()
except Exception as e:
    # MCP protocol error
    # Server returned invalid response
    # Connection lost
    logger.error(f"Failed to list tools: {e}")
    raise
```

**Common errors:**
- Protocol version mismatch
- Invalid tool definitions
- Connection interrupted

### Cleanup Errors

```python
# Best-effort cleanup
manager.cleanup_sync()
# Errors logged but not raised
```

**Cleanup strategy:**
- Continue even if some fail
- Log all errors
- No cascading failures

## Advanced Patterns

### Multiple MCP Servers of Same Type

```yaml
mcp_tools:
  - name: primary_db
    server: http
    url: https://primary.example.com/mcp
    prefix: primary_
    api_key_env: PRIMARY_DB_KEY

  - name: secondary_db
    server: http
    url: https://secondary.example.com/mcp
    prefix: secondary_
    api_key_env: SECONDARY_DB_KEY
```

**Agent sees:**
- `primary_query`, `primary_insert`, ...
- `secondary_query`, `secondary_insert`, ...

### Dynamic Tool Selection

```yaml
mcp_tools:
  - name: filesystem
    server: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem"]
    tool_filters:
      allowed:
        - read_*    # Only read operations
      rejected:
        - write_*   # No write operations
        - delete_*
```

**Use case:** Read-only agent for security

### Environment-Specific Configuration

```yaml
# development.yaml
mcp_tools:
  - name: database
    server: http
    url: http://localhost:8080/mcp
    prefix: db_

# production.yaml
mcp_tools:
  - name: database
    server: http
    url: https://prod-db.example.com/mcp
    prefix: db_
    api_key_env: PROD_DB_KEY
    headers:
      X-Environment: production
```

### Conditional Tool Loading

```python
# In configuration
if os.getenv("ENABLE_WEB_SEARCH") == "true":
    config.mcp_tools.append(
        MCPToolConfig(
            name="web_search",
            server="http",
            url="https://api.example.com/mcp",
            api_key_env="SEARCH_API_KEY",
        )
    )
```

## Performance Considerations

### Lazy Loading Benefits

**Default tools:**
- Loaded only when needed
- Cached after first load
- Fast subsequent access
- Reduced startup time

### MCP Context Management

**Manual pattern benefits:**
- Explicit control over lifecycle
- Better error handling
- Predictable resource usage
- No hidden async complexity

### Connection Pooling

**HTTP/SSE clients:**
- Reuse connections within context
- Proper cleanup on exit
- No connection leaks

### subprocess Management

**stdio clients:**
- Clean process termination
- Timeout and kill fallback
- No zombie processes
- Pipe cleanup

## Security Considerations

### API Key Management

```yaml
# Good: Environment variable
mcp_tools:
  - name: web_search
    server: http
    url: https://api.example.com/mcp
    api_key_env: SEARCH_API_KEY

# Bad: Hardcoded (DON'T DO THIS)
mcp_tools:
  - name: web_search
    server: http
    url: https://api.example.com/mcp
    headers:
      Authorization: "Bearer sk-1234567890"  # INSECURE!
```

### Tool Filtering for Safety

```yaml
# Restrict dangerous operations
mcp_tools:
  - name: filesystem
    server: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem"]
    tool_filters:
      rejected:
        - delete_*
        - remove_*
        - truncate_*
        - format_*
```

### Working Directory Isolation

```yaml
mcp_tools:
  - name: filesystem
    server: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem"]
    env:
      ALLOWED_DIRECTORIES: ${WORK_DIR}  # Restrict to working dir
```

### subprocess Security

**Environment variable scoping:**
```python
# Create isolated environment
env = os.environ.copy()
env.update(config.env)

# Remove sensitive variables
env.pop("AWS_SECRET_ACCESS_KEY", None)
env.pop("OPENAI_API_KEY", None)

# Create subprocess with isolated env
server_params = StdioServerParameters(
    command=config.command,
    args=config.args,
    env=env,
)
```

## Testing Tools

### Unit Testing Default Tools

```python
def test_default_tools_manager():
    manager = DefaultToolsManager("bash", "file_editor")

    # Test lazy loading
    assert not manager.is_tool_loaded("bash")

    # Load tool
    tool = manager.get_tool("bash")
    assert tool is not None
    assert manager.is_tool_loaded("bash")

    # Test caching
    tool2 = manager.get_tool("bash")
    assert tool is tool2  # Same instance

    # Test get_tools
    tools = manager.get_tools()
    assert len(tools) == 2
```

### Testing MCP Manager

```python
@pytest.mark.asyncio
async def test_mcp_manager_stdio():
    config = MCPToolConfig(
        name="test",
        server="stdio",
        command="python",
        args=["-m", "mcp_test_server"],
    )

    manager = MCPToolsManager([config])

    # Test initialization
    clients = manager.initialize()
    assert len(clients) == 1

    # Test context management
    manager.enter_contexts()
    tools = manager.get_tools_sync()
    assert len(tools) > 0

    # Test cleanup
    manager.exit_contexts()
```

### Mock MCP Server

```python
# tests/fixtures/mock_mcp_server.py
import asyncio
import json

async def mock_mcp_stdio_server():
    """Mock MCP server for testing."""
    while True:
        line = await asyncio.get_event_loop().run_in_executor(
            None, input
        )
        request = json.loads(line)

        if request["method"] == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": request["id"],
                "result": {
                    "tools": [
                        {
                            "name": "test_tool",
                            "description": "Test tool",
                            "inputSchema": {"type": "object"},
                        }
                    ]
                },
            }
            print(json.dumps(response))

if __name__ == "__main__":
    asyncio.run(mock_mcp_stdio_server())
```

## Debugging Tools

### Enable Debug Logging

```bash
# CLI debug mode
agentlet-core --debug --agentlet my-agentlet --prompt "Test"

# Environment variable
export LOG_LEVEL=DEBUG
agentlet-core --agentlet my-agentlet --prompt "Test"
```

### Test MCP Connection

```python
from agentlet_core.tools.mcp_manager import MCPToolsManager
from agentlet_core.config.models import MCPToolConfig

config = MCPToolConfig(
    name="test",
    server="stdio",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "."],
)

manager = MCPToolsManager([config])

try:
    manager.initialize()
    manager.enter_contexts()
    tools = manager.get_tools_sync()
    print(f"Found {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool}")
except Exception as e:
    print(f"Error: {e}")
finally:
    manager.exit_contexts()
```

### Inspect Tool Definitions

```python
tools = manager.get_tools_sync()
for tool in tools:
    print(f"Tool: {tool.name}")
    print(f"  Description: {tool.description}")
    print(f"  Input Schema: {tool.inputSchema}")
```

## Best Practices

### 1. Use Prefixes for Namespace Isolation

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

### 2. Filter Tools for Security

```yaml
mcp_tools:
  - name: filesystem
    server: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem"]
    tool_filters:
      rejected:
        - delete_*
        - remove_*
```

### 3. Use Environment Variables for Secrets

```yaml
mcp_tools:
  - name: database
    server: http
    url: https://db.example.com/mcp
    api_key_env: DATABASE_API_KEY  # Not hardcoded!
```

### 4. Isolate Working Directories

```yaml
mcp_tools:
  - name: filesystem
    server: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem"]
    env:
      ALLOWED_DIRECTORIES: ${WORK_DIR}
```

### 5. Handle Cleanup Errors Gracefully

```python
# In terminate()
try:
    if self._mcp_manager:
        self._mcp_manager.cleanup_sync()
except Exception as e:
    self.logger.warning(f"MCP cleanup error: {e}")
    # Continue with other cleanup
```

### 6. Test Tools Before Production

```bash
# Test tool loading
agentlet-core --agentlet test-config.yaml \
  --prompt "List available tools" \
  --debug
```

### 7. Document Custom MCP Servers

```yaml
# Custom MCP server for internal API
mcp_tools:
  - name: internal_api
    server: http
    url: https://internal.example.com/mcp
    api_key_env: INTERNAL_API_KEY
    tool_filters:
      allowed:
        - search_users
        - get_user_profile
      rejected:
        - admin_*
    # Purpose: Provide read-only access to user data
    # Maintainer: platform-team@example.com
    # Documentation: https://docs.internal.example.com/mcp
```

## Related Documentation

- [Architecture Overview](./overview.md) - System architecture
- [Agent Lifecycle](./agent-lifecycle.md) - Lifecycle details
- [Configuration System](./configuration-system.md) - Configuration patterns
- [CLAUDE.md](../../CLAUDE.md) - Developer guide
