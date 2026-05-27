# MCP Integration

Comprehensive guide to integrating Model Context Protocol (MCP) tools with agentlet-core.

## Overview

MCP (Model Context Protocol) enables agentlets to access external tools and services through a standardized protocol. Agentlet-core supports three transport types:

- **stdio**: Local command-line tools (subprocess-based)
- **HTTP**: Remote HTTP/HTTPS services (streamable HTTP)
- **SSE**: Server-Sent Events streaming services

All MCP integrations use the Strands agents SDK's `MCPClient` for proper integration with the Agent framework.

## Quick Start

### Basic stdio Example

```yaml
mcp_tools:
  - name: "filesystem"
    server: "stdio"
    command: "npx"
    args:
      - "-y"
      - "@modelcontextprotocol/server-filesystem"
    env:
      ALLOWED_DIRECTORIES: "${WORK_DIR}"
```

```bash
agentlet-core --agentlet my-agent --prompt "List files in current directory"
```

### Basic HTTP Example

```yaml
mcp_tools:
  - name: "api-service"
    server: "http"
    url: "https://api.example.com/mcp/"
    api_key_env: "API_KEY"
```

```bash
export API_KEY="your-api-key"
agentlet-core --agentlet my-agent --prompt "Query the API"
```

## stdio Transport

Stdio transport launches local command-line MCP servers as subprocesses.

### Configuration

```yaml
mcp_tools:
  - name: "tool-name"           # Required: Identifier
    server: "stdio"              # Required: Transport type
    command: "command"           # Required: Executable
    args: []                     # Optional: Arguments
    env: {}                      # Optional: Environment variables
    prefix: "prefix"             # Optional: Tool name prefix
    tool_filters: {}             # Optional: Filter tools
```

### Complete Example

```yaml
mcp_tools:
  # Filesystem MCP server
  - name: "filesystem"
    server: "stdio"
    command: "npx"
    args:
      - "-y"
      - "@modelcontextprotocol/server-filesystem"
    env:
      ALLOWED_DIRECTORIES: "${WORK_DIR}"
      LOG_LEVEL: "info"
    prefix: "fs"
    tool_filters:
      allowed:
        - "read_file"
        - "write_file"
        - "list_directory"

  # AWS Documentation MCP server
  - name: "aws-docs"
    server: "stdio"
    command: "uvx"
    args:
      - "awslabs.aws-documentation-mcp-server@latest"
    prefix: "aws"
    tool_filters:
      allowed:
        - "search_documentation"
        - "read_documentation"
```

### Popular stdio MCP Servers

**Filesystem**:
```yaml
- name: "filesystem"
  server: "stdio"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem"]
  env:
    ALLOWED_DIRECTORIES: "${WORK_DIR}"
```

**GitHub**:
```yaml
- name: "github"
  server: "stdio"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-github"]
  env:
    GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
```

**PostgreSQL**:
```yaml
- name: "postgres"
  server: "stdio"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-postgres"]
  env:
    POSTGRES_CONNECTION_STRING: "${DATABASE_URL}"
```

**Puppeteer** (web scraping):
```yaml
- name: "puppeteer"
  server: "stdio"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-puppeteer"]
```

**Brave Search**:
```yaml
- name: "brave-search"
  server: "stdio"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-brave-search"]
  env:
    BRAVE_API_KEY: "${BRAVE_API_KEY}"
```

**Slack**:
```yaml
- name: "slack"
  server: "stdio"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-slack"]
  env:
    SLACK_BOT_TOKEN: "${SLACK_BOT_TOKEN}"
    SLACK_TEAM_ID: "${SLACK_TEAM_ID}"
```

### Environment Variable Expansion

**Special variables**:
- `${WORK_DIR}`: Agentlet working directory
- `$VAR` or `${VAR}`: Any environment variable

**Example**:
```yaml
mcp_tools:
  - name: "filesystem"
    server: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem"]
    env:
      ALLOWED_DIRECTORIES: "${WORK_DIR}"        # Agentlet working dir
      HOME: "${HOME}"                           # User home directory
      CUSTOM_PATH: "$CUSTOM_ENV_VAR"            # Custom variable
      LOG_FILE: "${WORK_DIR}/logs/mcp.log"      # Combined
```

### Process Management

**Lifecycle**:
1. **Spawn**: Process started when agentlet initializes
2. **Connect**: stdin/stdout pipes established
3. **Execute**: Tools invoked via MCP protocol
4. **Cleanup**: Process terminated on agentlet termination

**Cleanup**:
- Graceful termination attempted first
- Force-kill after timeout if needed
- All stdio processes tracked for cleanup

## HTTP Transport

HTTP transport connects to remote MCP servers via streamable HTTP.

### Configuration

```yaml
mcp_tools:
  - name: "tool-name"           # Required: Identifier
    server: "http"               # Required: Transport type
    url: "https://..."           # Required: Endpoint URL
    api_key_env: "VAR_NAME"      # Optional: API key env var
    headers: {}                  # Optional: Custom headers
    prefix: "prefix"             # Optional: Tool name prefix
    tool_filters: {}             # Optional: Filter tools
```

### Complete Example

```yaml
mcp_tools:
  # Custom API with authentication
  - name: "custom-api"
    server: "http"
    url: "https://api.example.com/mcp/"
    api_key_env: "CUSTOM_API_KEY"
    headers:
      X-Custom-Header: "custom-value"
      Content-Type: "application/json"
    prefix: "api"
    tool_filters:
      rejected:
        - "dangerous_tool"
        - "deprecated_tool"

  # Public service (no auth)
  - name: "public-service"
    server: "http"
    url: "http://localhost:8080/mcp/"
    headers:
      Accept: "application/json"
    prefix: "pub"
```

### Authentication

**API key via environment variable** (automatic Bearer token):
```yaml
mcp_tools:
  - name: "api-service"
    server: "http"
    url: "https://api.example.com/mcp/"
    api_key_env: "API_KEY"  # Adds: Authorization: Bearer {api_key}
```

**Custom Authorization header**:
```yaml
mcp_tools:
  - name: "api-service"
    server: "http"
    url: "https://api.example.com/mcp/"
    headers:
      Authorization: "Bearer your-token-here"
```

**Custom auth scheme**:
```yaml
mcp_tools:
  - name: "api-service"
    server: "http"
    url: "https://api.example.com/mcp/"
    headers:
      X-API-Key: "${CUSTOM_API_KEY}"
      X-Client-ID: "client-123"
```

**No authentication**:
```yaml
mcp_tools:
  - name: "public-api"
    server: "http"
    url: "http://localhost:8080/mcp/"
```

### HTTPS and TLS

Standard HTTPS works without additional configuration:

```yaml
mcp_tools:
  - name: "secure-api"
    server: "http"
    url: "https://secure.example.com/mcp/"
    api_key_env: "API_KEY"
```

**Note**: The transport is called "http" but supports both HTTP and HTTPS.

## SSE Transport

SSE (Server-Sent Events) transport enables real-time streaming connections.

### Configuration

```yaml
mcp_tools:
  - name: "tool-name"           # Required: Identifier
    server: "sse"                # Required: Transport type
    url: "http://..."            # Required: SSE endpoint URL
    prefix: "prefix"             # Optional: Tool name prefix
    tool_filters: {}             # Optional: Filter tools
```

### Complete Example

```yaml
mcp_tools:
  - name: "realtime-service"
    server: "sse"
    url: "http://localhost:8000/sse"
    prefix: "rt"
    tool_filters:
      allowed:
        - "stream_data"
        - "get_updates"
        - "subscribe"
```

### Authentication

**SSE clients don't support custom headers**. Include auth in URL:

```yaml
mcp_tools:
  - name: "sse-service"
    server: "sse"
    url: "http://localhost:8000/sse?token=your-token-here"
```

**Alternative**: Server-side authentication via session cookies or IP allowlist.

### Use Cases

- Real-time data streaming
- Event monitoring
- Live updates
- WebSocket alternatives

## Tool Filtering

Control which tools are loaded from MCP servers.

### Allow Specific Tools

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
        - "list_directory"
    # Only these 3 tools will be loaded
```

### Reject Specific Tools

```yaml
mcp_tools:
  - name: "database"
    server: "http"
    url: "https://db.example.com/mcp/"
    tool_filters:
      rejected:
        - "delete_database"
        - "drop_table"
        - "truncate_table"
    # All tools except these 3 will be loaded
```

### Validation Rules

- Cannot specify both `allowed` and `rejected`
- Must specify at least one if `tool_filters` is present
- Tool names are case-sensitive
- Unknown tool names are silently ignored

### Use Cases

**Security**: Prevent dangerous operations
```yaml
tool_filters:
  rejected:
    - "delete_file"
    - "format_disk"
    - "shutdown_system"
```

**Token optimization**: Load only needed tools
```yaml
tool_filters:
  allowed:
    - "search_documentation"
    - "read_documentation"
```

**Access control**: Limit capabilities per deployment
```yaml
# Production: read-only
tool_filters:
  allowed:
    - "read_file"
    - "list_directory"

# Development: full access
tool_filters:
  rejected: []
```

## Tool Name Prefixing

Prevent naming conflicts between multiple MCP servers.

### Without Prefix (Risk of Conflicts)

```yaml
mcp_tools:
  - name: "filesystem"
    server: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem"]
    # Tools: read_file, write_file, ...

  - name: "database"
    server: "http"
    url: "https://db.example.com/mcp/"
    # Tools: read_file, write_file, ...
    # ⚠ Naming conflict!
```

### With Prefix (No Conflicts)

```yaml
mcp_tools:
  - name: "filesystem"
    server: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem"]
    prefix: "fs"
    # Tools: fs_read_file, fs_write_file, fs_list_directory

  - name: "database"
    server: "http"
    url: "https://db.example.com/mcp/"
    prefix: "db"
    # Tools: db_read_file, db_write_file, db_query
    # ✓ No conflict
```

**Tool invocation**:
```
Agent uses: fs_read_file("config.yaml")
Agent uses: db_read_file("users", "id=123")
```

### Best Practices

**Use short, descriptive prefixes**:
```yaml
prefix: "fs"    # filesystem
prefix: "db"    # database
prefix: "gh"    # github
prefix: "aws"   # aws-docs
prefix: "api"   # custom-api
```

**Always use prefixes when**:
- Multiple MCP servers might have overlapping tool names
- Combining different types of services
- Building reusable agentlet configs

## Combining Multiple MCP Servers

### Mixed Transport Example

```yaml
mcp_tools:
  # Local filesystem access
  - name: "filesystem"
    server: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem"]
    env:
      ALLOWED_DIRECTORIES: "${WORK_DIR}"
    prefix: "fs"

  # Remote API service
  - name: "api-service"
    server: "http"
    url: "https://api.example.com/mcp/"
    api_key_env: "API_KEY"
    prefix: "api"

  # Real-time updates
  - name: "notifications"
    server: "sse"
    url: "http://localhost:8000/sse"
    prefix: "notify"

# Default Strands tools (optional)
tools:
  - "bash"
  - "file_editor"
```

### Practical Multi-Server Setup

**Development assistant**:
```yaml
mcp_tools:
  # Code repository access
  - name: "github"
    server: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
    prefix: "gh"

  # Local filesystem
  - name: "filesystem"
    server: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem"]
    env:
      ALLOWED_DIRECTORIES: "${WORK_DIR}"
    prefix: "fs"

  # Documentation search
  - name: "aws-docs"
    server: "stdio"
    command: "uvx"
    args: ["awslabs.aws-documentation-mcp-server@latest"]
    prefix: "aws"
```

**Data processing**:
```yaml
mcp_tools:
  # Database access
  - name: "postgres"
    server: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-postgres"]
    env:
      POSTGRES_CONNECTION_STRING: "${DATABASE_URL}"
    prefix: "db"

  # External API
  - name: "data-api"
    server: "http"
    url: "https://data.example.com/mcp/"
    api_key_env: "DATA_API_KEY"
    prefix: "api"

  # Filesystem for reports
  - name: "filesystem"
    server: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem"]
    env:
      ALLOWED_DIRECTORIES: "${WORK_DIR}"
    prefix: "fs"
    tool_filters:
      allowed:
        - "write_file"  # Only allow writing reports
```

## Troubleshooting

### Common Issues

#### stdio Process Fails to Start

**Symptoms**:
```
✗ Failed to initialize MCP server 'filesystem'
```

**Causes**:
- Command not found in PATH
- Missing npm packages
- Incorrect arguments

**Solutions**:
```bash
# Test command manually
npx -y @modelcontextprotocol/server-filesystem

# Check PATH
which npx

# Install globally
npm install -g @modelcontextprotocol/server-filesystem
```

#### Environment Variable Not Expanded

**Symptoms**:
```
env:
  ALLOWED_DIRECTORIES: "${WORK_DIR}"
# Shows literal "${WORK_DIR}" instead of path
```

**Cause**: Using single quotes in YAML

**Solution**: Use double quotes or no quotes
```yaml
env:
  ALLOWED_DIRECTORIES: "${WORK_DIR}"  # ✓ Correct
  # OR
  ALLOWED_DIRECTORIES: ${WORK_DIR}    # ✓ Also correct
```

#### HTTP Connection Refused

**Symptoms**:
```
✗ Failed to initialize MCP server 'api-service'
Error: Connection refused
```

**Solutions**:
```bash
# Check if service is running
curl http://localhost:8080/mcp/

# Check firewall
sudo ufw status

# Verify URL in config
url: "http://localhost:8080/mcp/"  # Include trailing slash if needed
```

#### API Authentication Failed

**Symptoms**:
```
Error: 401 Unauthorized
```

**Solutions**:
```bash
# Check environment variable is set
echo $API_KEY

# Load .env file
agentlet-core --agentlet my-agent --env-file .env --prompt "Task"

# Test API key manually
curl -H "Authorization: Bearer $API_KEY" https://api.example.com/mcp/
```

#### SSE Connection Timeout

**Symptoms**:
```
✗ Failed to initialize MCP server 'sse-service'
Error: Connection timeout
```

**Solutions**:
```bash
# Check SSE endpoint
curl -H "Accept: text/event-stream" http://localhost:8000/sse

# Verify URL format
url: "http://localhost:8000/sse"  # No trailing slash for SSE

# Check server logs
```

#### Tool Filtering Not Working

**Symptoms**: Rejected tools still appear or allowed tools not loaded

**Solutions**:
```yaml
# Check spelling (case-sensitive)
tool_filters:
  allowed:
    - "read_file"      # ✓ Correct
    # NOT "Read_File" or "readFile"

# Cannot mix allowed and rejected
tool_filters:
  allowed:
    - "read_file"
  rejected:           # ✗ Error: cannot specify both
    - "delete_file"

# Fix: Use one or the other
tool_filters:
  allowed:
    - "read_file"
```

#### Prefix Not Applied

**Symptoms**: Tools appear without prefix

**Cause**: Strands MCPClient applies prefix automatically

**Verification**:
```yaml
prefix: "fs"
# Tools appear as: fs_read_file, fs_write_file (correct)
```

### Debug Mode

Enable debug logging to troubleshoot MCP issues:

```bash
agentlet-core --agentlet my-agent --debug --prompt "Task"
```

**Debug output includes**:
```
DEBUG: MCP server 'filesystem' initialized
DEBUG: Loaded 8 tools from MCP server
DEBUG: Tool names: ['fs_read_file', 'fs_write_file', ...]
DEBUG: MCP client context entered
```

### Testing MCP Servers

**Test stdio command manually**:
```bash
# Should start without errors
npx -y @modelcontextprotocol/server-filesystem
```

**Test HTTP endpoint**:
```bash
# Should return MCP protocol response
curl https://api.example.com/mcp/
```

**Test SSE endpoint**:
```bash
# Should stream events
curl -H "Accept: text/event-stream" http://localhost:8000/sse
```

## Best Practices

### Security

**Use environment variables for secrets**:
```yaml
# ✓ Good: Secret in environment
env:
  API_KEY: "${MY_API_KEY}"

# ✗ Bad: Secret in config
env:
  API_KEY: "sk-1234567890"
```

**Filter dangerous tools in production**:
```yaml
tool_filters:
  rejected:
    - "delete_file"
    - "drop_table"
    - "format_disk"
    - "shutdown"
```

**Restrict filesystem access**:
```yaml
env:
  ALLOWED_DIRECTORIES: "${WORK_DIR}"  # Not root or home
```

### Performance

**Filter tools to reduce token usage**:
```yaml
# Load only what you need
tool_filters:
  allowed:
    - "read_file"
    - "write_file"
# Instead of loading all 20+ tools
```

**Use local stdio when possible**:
- Lower latency than HTTP
- No network overhead
- Better for file operations

**Use HTTP for remote services**:
- When data is remote anyway
- For centralized services
- When sharing between agentlets

### Reliability

**Always use prefixes**:
```yaml
prefix: "fs"  # Prevents naming conflicts
```

**Set appropriate timeouts**:
```yaml
resource_limits:
  max_execution_time: 300  # 5 minutes
```

**Test MCP servers independently**:
```bash
# Test before adding to config
npx -y @modelcontextprotocol/server-filesystem
```

### Maintainability

**Use descriptive names**:
```yaml
- name: "filesystem"      # ✓ Clear purpose
- name: "tool1"           # ✗ Unclear
```

**Document custom MCP servers**:
```yaml
# Custom internal API for customer data
- name: "customer-api"
  server: "http"
  url: "https://internal.example.com/mcp/"
  api_key_env: "CUSTOMER_API_KEY"
```

**Version control configurations**:
```bash
git add my-agent.yaml
git commit -m "Add GitHub MCP integration"
```

## MCP Server Development

See [MCP documentation](https://modelcontextprotocol.io/) for creating custom MCP servers.

**Quick server types**:
- **stdio**: Python, Node.js, Go (any language with stdin/stdout)
- **HTTP**: REST API with MCP protocol
- **SSE**: Real-time streaming server

## Next Steps

- **[Configuration](configuration.md)** - Complete MCP configuration reference
- **[Running Agentlets](running-agentlets.md)** - CLI options and execution

