# Quick Start

Get started with agentlet-core in 5 minutes.

## Prerequisites

- Python 3.13+ installed
- An LLM API key (Anthropic, OpenAI, or AWS Bedrock)

## Step 1: Install

```bash
# Install from GitHub Release wheel (recommended)
pip install agentlet_core-<version>-py3-none-any.whl

# Or install from source
git clone https://github.com/Synteles/agentlet.git
cd agentlet
uv sync
```

## Step 2: Set API Key

```bash
# For Anthropic
export ANTHROPIC_API_KEY="your-api-key"

# For OpenAI
export OPENAI_API_KEY="your-api-key"

# For AWS Bedrock
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
```

## Step 3: Create Your First Agentlet

Create a file named `hello-assistant.yaml`:

```yaml
agentlet:
  name: "hello-assistant"
  version: "1.0.0"

model:
  provider: "anthropic"  # or "openai", "bedrock"
  model_id: "claude-sonnet-4-6"

system_prompt: "You are a friendly and helpful assistant."

tools:
  - "bash"

output:
  show_tool_calls: true
```

## Step 4: Run the Agentlet

```bash
agentlet-core --agentlet hello-assistant.yaml --prompt "Say hello and tell me what day it is"
```

You should see:

```
╭─────────────────────────────────────────────╮
│                                             │
│     ___                   _   _      _      │
│    /   \  __ _  ___ _ __ | |_| | ___| |_    │
│   / /\ / / _` |/ _ \ '_ \| __| |/ _ \ __|   │
│  / /_//| (_| |  __/ | | | |_| |  __/ |_    │
│ /___,'  \__, |\___|_| |_|\__|_|\___|\__|   │
│         |___/                               │
│                                             │
╰─────────────────────────────────────────────╯

ℹ Spawning agentlet 'hello-assistant'
ℹ Using model: anthropic/claude-sonnet-4-6

✓ Assistant response:
Hello! Let me check what day it is for you.

✓ Tool Call: bash
Command: date +"%A, %B %d, %Y"

✓ Tool Result:
Thursday, January 30, 2025

✓ Assistant response:
Today is Thursday, January 30, 2025. Have a great day!

✓ Execution completed
```

## Step 5: Try Different Prompts

```bash
# File operations
agentlet-core --agentlet hello-assistant.yaml \
  --prompt "Create a file called hello.txt with 'Hello World'"

# System information
agentlet-core --agentlet hello-assistant.yaml \
  --prompt "What operating system am I using?"

# Code generation
agentlet-core --agentlet hello-assistant.yaml \
  --prompt "Write a Python function to calculate fibonacci numbers"
```

## Step 6: Add MCP Tools (Optional)

Enhance your agentlet with MCP tools for filesystem access:

Create `filesystem-agent.yaml`:

```yaml
agentlet:
  name: "filesystem-agent"
  version: "1.0.0"

model:
  provider: "anthropic"
  model_id: "claude-sonnet-4-6"

system_prompt: "You are a helpful assistant with filesystem access."

tools:
  - "bash"

mcp_tools:
  - name: "filesystem"
    server: "stdio"
    command: "npx"
    args:
      - "-y"
      - "@modelcontextprotocol/server-filesystem"
    env:
      ALLOWED_DIRECTORIES: "${WORK_DIR}"
    prefix: "fs"
```

Run it:

```bash
agentlet-core --agentlet filesystem-agent.yaml \
  --prompt "List all Python files in the current directory"
```

## Step 7: Enable Debug Mode

See detailed execution logs:

```bash
agentlet-core --agentlet hello-assistant.yaml \
  --prompt "Hello" \
  --debug
```

Debug mode provides:
- Detailed execution logs
- File logging (`agentlet-core-{timestamp}.log`)
- SDK internal logs
- Verbose error messages

## Common CLI Options

```bash
# Override model
agentlet-core --agentlet my-agent.yaml \
  --model "openai/gpt-4" \
  --prompt "Hello"

# Set timeout
agentlet-core --agentlet my-agent.yaml \
  --timeout 120 \
  --prompt "Long running task"

# Change output format
agentlet-core --agentlet my-agent.yaml \
  --output-format json \
  --prompt "Get system info"

# Set working directory
agentlet-core --agentlet my-agent.yaml \
  --path /tmp/workspace \
  --prompt "Create files here"

# Enable retry logic
agentlet-core --agentlet my-agent.yaml \
  --max-retries 5 \
  --prompt "Task that might fail"
```

## Example Agentlets

The repository includes example agentlets in `examples/`:

- **simple-assistant.yaml** - Basic chat assistant
- **mcp-stdio-example.yaml** - MCP stdio tools
- **mcp-http-example.yaml** - MCP HTTP tools
- **otel-example.yaml** - OpenTelemetry integration

Clone and try them:

```bash
git clone https://github.com/Synteles/agentlet.git
cd agentlet

agentlet-core --agentlet examples/simple-assistant.yaml \
  --prompt "Hello, world!"
```

## Using Agentlet-core as a Library

You can also use agentlet-core programmatically:

```python
import asyncio
from agentlet_core.agents.base import BaseAgentlet
from agentlet_core.config.loader import load_config

async def main():
    # Load configuration
    config = load_config("hello-assistant.yaml")

    # Create and run agentlet
    agentlet = BaseAgentlet(config, prompt="Say hello!")

    async for event in agentlet.run():
        if "data" in event:
            print(event["data"], end="", flush=True)

asyncio.run(main())
```

## Next Steps

- **[Introduction](introduction.md)** - Learn about agentlet architecture
- **[Configuration Guide](../reference/configuration.md)** - Full config reference
- **[MCP Integration](../reference/mcp-integration.md)** - Advanced MCP usage
- **[Architecture Overview](../architecture/overview.md)** - System design deep dive

## Troubleshooting

### Command Not Found

```bash
# If agentlet-core not in PATH, use python -m
python -m agentlet_core.cli.main --agentlet my-agent.yaml --prompt "Hello"

# Or use uv run
uv run agentlet-core --agentlet my-agent.yaml --prompt "Hello"
```

### API Key Not Set

```
ERROR: ANTHROPIC_API_KEY not found in environment
```

**Solution**: Set the appropriate API key for your provider.

### Config File Not Found

```
ERROR: Configuration not found: my-agent
```

**Solution**: Provide full path or place config in one of these locations:
- Current directory
- `~/.synteles/agentlets/`
- `./.synteles/agentlets/`

## Get Help

```bash
# View all CLI options
agentlet-core --help

# Check version
python -c "import agentlet_core; print(agentlet_core.__version__)"
```
