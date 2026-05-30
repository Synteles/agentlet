# Installation

This guide covers installing agentlet-core using various methods.

## Prerequisites

- **Python 3.13+** required
- **uv** package manager (recommended) or **pip**
- **Node.js** (optional, for MCP stdio tools)

## Installation Methods

### Option 1: Install from GitHub Release (Recommended)

Download the latest wheel from the [Releases page](https://github.com/Synteles/agentlet/releases) and install it:

```bash
# Install the wheel with pip
pip install agentlet_core-<version>-py3-none-any.whl

# Or with uv
uv tool install agentlet_core-<version>-py3-none-any.whl
```

### Option 2: Install from Source

```bash
# Clone the repository
git clone https://github.com/Synteles/agentlet.git
cd agentlet

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### Option 3: Docker

```bash
# Pull the Docker image
docker pull synteles/agentlet-core:latest

# Run an agentlet
docker run -it --rm \
  -v $(pwd):/workspace \
  -e ANTHROPIC_API_KEY="your-api-key" \
  synteles/agentlet-core:latest \
  agentlet-core --agentlet /workspace/my-agentlet.yaml --prompt "Hello"
```

## Verify Installation

```bash
# Check version
python -c "import agentlet_core; print(agentlet_core.__version__)"

# Or run a simple test
agentlet-core --help
```

## Optional Dependencies

### OpenTelemetry (OTEL)

OpenTelemetry support is included in the standard installation. Enable it via configuration:

```yaml
observability:
  otel:
    enabled: true
    otlp_endpoint: "http://localhost:4318"
```

Or via CLI flags: `--otel-enabled --otlp-endpoint "http://localhost:4318"`

### Development Tools

For contributing or development:

```bash
# With uv
uv sync --group dev

# Installs: pytest, mypy, ruff, bandit, coverage
```

## MCP Tools (Optional)

For using MCP stdio tools, install Node.js and MCP servers:

```bash
# Example: Install filesystem MCP server
npm install -g @modelcontextprotocol/server-filesystem

# Or use npx (no installation needed)
npx -y @modelcontextprotocol/server-filesystem
```

## Environment Setup

### 1. LLM Provider API Keys

Set environment variables for your LLM provider:

**Anthropic:**
```bash
export ANTHROPIC_API_KEY="your-api-key"
```

**AWS Bedrock:**
```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"  # Optional
```

**OpenAI:**
```bash
export OPENAI_API_KEY="your-api-key"
```

### 2. Environment File

Create a `.env` file for persistent configuration:

```bash
# .env
ANTHROPIC_API_KEY=your-anthropic-key
OPENAI_API_KEY=your-openai-key
```

Agentlet-core automatically loads `.env` from:
- Current directory
- `~/synteles/.env`

## Troubleshooting

### Python Version Error

```
ERROR: This package requires Python 3.13+
```

**Solution**: Install Python 3.13 or later.

```bash
# Check Python version
python --version

# Install Python 3.13 (example with pyenv)
pyenv install 3.13.0
pyenv global 3.13.0
```

### uv Not Found

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH
export PATH="$HOME/.cargo/bin:$PATH"
```

### Import Error

```
ModuleNotFoundError: No module named 'agentlet_core'
```

**Solution**: Ensure agentlet-core is installed in the active Python environment.

```bash
# Check if installed (source install)
pip list | grep agentlet-core

# Reinstall from wheel or source
pip install agentlet_core-<version>-py3-none-any.whl
# Or from source:
pip install -e .
```

## Next Steps

- [Quick Start Guide](quick-start.md) - Run your first agentlet
- [Introduction](introduction.md) - Understand agentlet fundamentals
- [Configuration Guide](../reference/configuration.md) - Configure your agentlet
