<p align="center">
  <img src="docs/images/synteles_logo.png" alt="Synteles Logo" width="360"/>
</p>

# Synteles Agentlet

**Synteles Agentlet** is a lightweight harness for building composable AI workers with tools, customization and traceable execution.

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Apache 2.0 License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-red.svg)](CHANGELOG.md)
[![Build](https://github.com/Synteles/agentlet/actions/workflows/pr-checks.yml/badge.svg)](https://github.com/Synteles/agentlet/actions/workflows/pr-checks.yml)
[![Latest Release](https://img.shields.io/github/v/release/Synteles/agentlet?include_prereleases)](https://github.com/Synteles/agentlet/releases/latest)
[![Docker Hub](https://img.shields.io/docker/v/synteles/agentlet?label=docker&sort=semver)](https://hub.docker.com/r/synteles/agentlet/tags)

⚠️ **Early Development**: Synteles Agentlet is pre-v1.0. APIs and configurations may change. See [Known Limitations](#known-limitations).

**If you find this useful, please consider [starring this repository](https://github.com/Synteles/agentlet) to help other developers discover it!** ⭐

## Overview

Synteles Agentlet is an AI agent runtime that works standalone or as the execution layer within the Synteles platform:

- **Ephemeral execution** — spawn > execute > terminate lifecycle
- **Multi-provider LLM** — Anthropic, AWS Bedrock, OpenAI, Azure, Ollama and 100+ more via LiteLLM
- **MCP support** — integrate external tools via stdio, HTTP, and SSE transports
- **Tools** — shell, file editor, HTTP requests, Python REPL, web search, calculator, current time, and more — ready to use by name with no extra setup
- **Multiagency** — orchestrator/sub-agentlet pipelines and peer-to-peer swarm patterns
- **Declarative config** — YAML DSL/JSON with Pydantic validation and JSON Schema
- **Production observability** — 3-layer logging, OpenTelemetry traces/metrics, secret sanitization
- **Multimodal input** — pass images (local files, HTTP URLs, base64) to vision-capable models via `--image`
- **Timeouts and retries** — multi-level execution timeouts and declarative exponential backoff retry with per-error-class targeting, configurable backoff factor, initial interval, and interval cap

## Installation

### With uv (recommended for development)

```bash
git clone https://github.com/Synteles/agentlet.git
cd agentlet
uv sync
```

### With Docker

```bash
docker pull synteles/agentlet-core:latest

docker run -it --rm \
  -e ANTHROPIC_API_KEY="your-key" \
  synteles/agentlet-core:latest \
  agentlet-core --agentlet generic-assistant --prompt "Hello"
```

### From GitHub Release

Download the latest wheel from the [Releases page](https://github.com/Synteles/agentlet/releases) and install it:

```bash
pip install agentlet_core-<version>-py3-none-any.whl
```

### From source

```bash
git clone https://github.com/Synteles/agentlet.git
cd agentlet
pip install -e .
```

See [Installation Guide](docs/tutorials/installation.md) for more options and troubleshooting.

## Quick Start

Set your API key and run an example agentlet:

```bash
export ANTHROPIC_API_KEY="your-key"
agentlet-core --agentlet examples/simple-assistant.yaml --prompt "Say hello"
```

### Minimal config

```yaml
# my-assistant.yaml
agentlet:
  name: "my-assistant"

model:
  provider: "anthropic"
  model_id: "claude-sonnet-4-6"

system_prompt: "You are a helpful assistant."

tools:
  - "shell"
  - "editor"
```

```bash
agentlet-core --agentlet my-assistant.yaml --prompt "List Python files"

# With OpenTelemetry
agentlet-core --agentlet my-assistant.yaml --prompt "Task" \
  --otel-enabled --otlp-endpoint "http://localhost:4318"

# Debug mode
agentlet-core --agentlet my-assistant.yaml --prompt "Task" --debug
```

## Examples & Templates

### Example Agentlets

The `examples/` directory contains pre-built agentlets demonstrating various features:

- **simple-assistant.yaml** — minimal starter example
- **generic-assistant.yaml** — production-ready general-purpose assistant
- **generic-assistant.minified.yaml** — compact single-file version of generic-assistant
- **web-researcher.yaml** — web search and summarization
- **multi-agent-example.yaml** — orchestrator with specialist sub-agents
- **swarm-expert-panel.yaml** — peer-to-peer multi-agent collaboration
- **swarm-dynamic.yaml** — dynamic team provisioning via LLM
- **swarm-combined.yaml** — combined swarm patterns
- **mcp-stdio-example.yaml** — MCP tools via subprocess
- **mcp-http-example.yaml** — MCP tools via HTTP
- **mcp-sse-example.yaml** — MCP tools via Server-Sent Events
- **mcp-mixed-example.yaml** — MCP tools with mixed transports
- **otel-example.yaml** — OpenTelemetry observability setup

See [examples/](examples/) for all examples.

### Configuration Templates

The `templates/` directory contains starter templates:

- **agentlet-template.yaml** — basic YAML template
- **agentlet-template.json** — JSON configuration format
- **agentlet-schema.json** — JSON Schema for IDE validation and autocompletion

Copy a template and customize it for your use case. Use the schema in your IDE to enable autocomplete:

```json
{
  "$schema": "templates/agentlet-schema.json"
}
```

## Documentation

### Tutorials
- [Installation](docs/tutorials/installation.md)
- [Quick Start](docs/tutorials/quick-start.md)
- [Introduction](docs/tutorials/introduction.md)

### Reference
- [Configuration Reference](docs/reference/configuration.md)
- [Running Agentlets](docs/reference/running-agentlets.md)
- [MCP Tool Integration](docs/reference/mcp-integration.md)
- [Multi-Agent Systems](docs/reference/multi-agent.md)
- [Swarm Pattern](docs/reference/swarm.md)
- [Logging](docs/reference/logging.md)
- [OpenTelemetry & Tracing](docs/reference/telemetry.md)
- [Debugging](docs/reference/debugging.md)

### Architecture & Design
- [Architecture Overview](docs/architecture/overview.md)
- [Agent Lifecycle](docs/architecture/agent-lifecycle.md)
- [Configuration System](docs/architecture/configuration-system.md)
- [Tool Management](docs/architecture/tool-management.md)

## Development

```bash
git clone https://github.com/Synteles/agentlet.git
cd agentlet
uv sync --group dev
make check   # lint + typecheck + security + tests
```

Individual targets: `make lint`, `make typecheck`, `make security`, `make test`, `make format`.

For local development with Docker Compose:

```bash
docker compose up
```

## Contributing

Contributions are welcome. Good first contribution areas:

- Bug reports and reproducible issues
- Security hardening
- Documentation improvements
- Tests

Please read [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and [GOVERNANCE.md](GOVERNANCE.md) before contributing. Synteles uses the Developer Certificate of Origin — contributions must be signed off.

AI-assisted coding is allowed, but contributors remain responsible for the code they submit. By contributing, you confirm that you have reviewed, tested, and have the right to submit your contribution under the project license.

## Known Limitations

- Pre-v1.0 software: APIs and configurations may change
- Security support is best-effort until stable release

## Security

Please do not report security vulnerabilities through public GitHub issues. See [SECURITY.md](SECURITY.md) for responsible disclosure guidelines and reporting instructions.

## License

Synteles Agentlet is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).

The Synteles name, logo, visual identity, and related brand assets are not covered by the Apache License. See [TRADEMARKS.md](TRADEMARKS.md).

## Contact

- **Issues & Discussions**: [GitHub Issues](https://github.com/Synteles/agentlet/issues) · [GitHub Discussions](https://github.com/Synteles/agentlet/discussions)
- **Docker Hub**: [synteles/agentlet-core](https://hub.docker.com/r/synteles/agentlet-core)
- **General**: hello@synteles.io
- **Security**: security@synteles.io
- **Legal / trademark**: legal@synteles.io
- **Maintainer**: [Emin Askerov](https://github.com/emaskerov)

---

Built with ❤️ by the Synteles team
