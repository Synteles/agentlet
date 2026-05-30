# Synteles Agentlet

**Agentlet** is a lightweight harness for building composable AI workers with tools, customization and traceable execution.

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Apache 2.0 License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-red.svg)](CHANGELOG.md)

⚠️ **Early Development**: Synteles Agentlet is pre-v1.0. APIs and configurations may change. See [Known Limitations](#known-limitations).

**If you find this useful, please consider [starring this repository](https://github.com/Synteles/agentlet) to help other developers discover it!** ⭐

## Overview

Synteles Agentlet is a Python runtime for autonomous AI agents built on the Strands Agent Framework.

- **Ephemeral execution** — clean spawn → execute → terminate lifecycle
- **Multi-provider LLM** — Anthropic, AWS Bedrock, OpenAI, Azure, and more via LiteLLM
- **MCP tools** — integrate external tools via stdio, HTTP, and SSE transports
- **Multiagency** — orchestrator/sub-agentlet pipelines and peer-to-peer swarm patterns
- **Declarative config** — YAML/JSON with Pydantic validation and JSON Schema
- **Production observability** — 3-layer logging, OpenTelemetry traces/metrics, secret sanitization
- **Multimodal input** — pass images (local files, HTTP URLs, base64) to vision-capable models via `--image`

## Installation

### From GitHub Release

Download the latest wheel from the [Releases page](https://github.com/Synteles/agentlet/releases) and install it:

```bash
pip install agentlet_core-<version>-py3-none-any.whl
```

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
```

```bash
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
- **data-processor.yaml** — batch data processing
- **web-researcher.yaml** — web search and summarization
- **telegram-assistant.yaml** — Telegram bot integration
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

**[Complete Documentation](docs/README.md)**

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
- [Deployment Guide](docs/reference/deployment.md)
- [Versioning](docs/reference/versioning.md)
- [CI/CD Automation](docs/reference/ci-cd.md)

### Architecture & Design
- [Architecture Overview](docs/architecture/overview.md)
- [Agent Lifecycle](docs/architecture/agent-lifecycle.md)
- [Configuration System](docs/architecture/configuration-system.md)
- [Tool Management](docs/architecture/tool-management.md)

### Observability
- [Logging](docs/observability/logging.md)
- [OpenTelemetry & Tracing](docs/observability/telemetry.md)
- [Monitoring](docs/observability/monitoring.md)

### Development
- [Development Setup](docs/development/setup.md)
- [Testing](docs/development/testing.md)
- [Debugging](docs/development/debugging.md)

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

## Deployment

```bash
docker pull synteles/agentlet-core:latest

docker run -it --rm \
  -e ANTHROPIC_API_KEY="your-key" \
  synteles/agentlet-core:latest \
  agentlet-core --agentlet generic-assistant --prompt "Hello"
```

See [Deployment Guide](docs/reference/deployment.md) for Kubernetes and production patterns.

## License

Synteles Agentlet is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

## Code of Conduct

This project adheres to the [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Security

For security vulnerabilities, please **do not** open a public GitHub issue. Instead, see [SECURITY.md](SECURITY.md) for responsible disclosure guidelines.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Ways to contribute
- Development setup
- Pull request guidelines
- Testing and quality standards
- Security guidelines
- Responsible AI-assisted coding policy

## Known Limitations

- Pre-v1.0 software: APIs and configurations may change
- Security support is best-effort until stable release
- Production deployment requires manual review and hardening
- Observability and error handling are prioritized, but log outputs are still in early iteration

## Support

- **Issues**: [GitHub Issues](https://github.com/Synteles/agentlet/issues)
- **Documentation**: [Complete Docs](docs/README.md)
- **Security Issues**: [SECURITY.md](SECURITY.md)
- **Docker Hub**: [synteles/agentlet-core](https://hub.docker.com/r/synteles/agentlet-core)

## Maintainer

Synteles Agentlet is maintained by [Emin Askerov](https://github.com/emaskerov) as part of the Synteles project.

For questions or feedback, reach out via:
- **Email**: hello@synteles.io
- **GitHub Issues**: [Create an issue](https://github.com/Synteles/agentlet/issues)
- **GitHub Discussions**: [Start a discussion](https://github.com/Synteles/agentlet/discussions)

---

Built with ❤️ by the Synteles team
