# Agentlet Core Documentation

**Agentlet-core** is a Python runtime for autonomous AI agents built on the Strands Agent Framework. It creates "Agentlets" - minimal viable units of autonomous AI agency that are standardized, containerized, and production-ready.

## Quick Links

- [GitHub Repository](https://github.com/Synteles/agentlet)
- [Docker Hub](https://hub.docker.com/r/synteles/agentlet-core)

## Documentation Structure

### 🚀 Getting Started
Perfect for first-time users and quick setup.

- **[Installation](getting-started/installation.md)** - Install agentlet-core with pip, uv, or Docker
- **[Quick Start](getting-started/quick-start.md)** - Run your first agentlet in 5 minutes
- **[Core Concepts](getting-started/core-concepts.md)** - Understand agentlets, ephemeral execution, and agent lifecycle

### 📖 User Guide
Comprehensive guides for using agentlet-core.

- **[Configuration](user-guide/configuration.md)** - Complete configuration reference for YAML/JSON configs
- **[Running Agentlets](user-guide/running-agentlets.md)** - CLI options, environment variables, and execution modes
- **[MCP Integration](user-guide/mcp-integration.md)** - Using Model Context Protocol tools (stdio, HTTP, SSE)
- **[Multi-Agent Systems](user-guide/multi-agent.md)** - Orchestrating sub-agentlets with the agent-as-tool pattern
- **[Swarm Pattern](user-guide/swarm.md)** - Peer-to-peer collaboration with declarative panels, dynamic teams, or both

### 🏗️ Architecture
Deep dives into system design and technical implementation.

- **[System Overview](architecture/overview.md)** - High-level architecture and component relationships
- **[Agent Lifecycle](architecture/agent-lifecycle.md)** - Spawn → Execute → Terminate lifecycle in detail
- **[Configuration System](architecture/configuration-system.md)** - Config loading, validation, and override mechanisms
- **[Tool Management](architecture/tool-management.md)** - Default tools and MCP tools manager

### 📊 Observability
Production-ready logging, tracing, and monitoring.

- **[Logging System](observability/logging.md)** - 3-layer logging model, correlation, and secret sanitization
- **[Telemetry](observability/telemetry.md)** - OpenTelemetry traces and metrics export (OTLP)
- **[Monitoring](observability/monitoring.md)** - Best practices for production monitoring

### 🛠️ Development
For contributors and advanced users.

- **[Development Setup](development/setup.md)** - Set up development environment with uv
- **[Testing Guide](development/testing.md)** - Running tests, writing tests, and coverage
- **[Contributing](development/contributing.md)** - Contribution guidelines and code style
- **[Debugging](development/debugging.md)** - Debugging tips and troubleshooting

### 🚢 Operations
Deployment, versioning, and CI/CD automation.

- **[Deployment](operations/deployment.md)** - Deployment options (Docker, source, GitHub Release)
- **[Versioning](operations/versioning.md)** - Semantic versioning and release strategy
- **[CI/CD Automation](operations/ci-cd.md)** - GitHub Actions workflows and automation

## Key Features

✅ **Multi-Provider LLM Support** - Works with Anthropic, AWS Bedrock, OpenAI, Azure, Vertex AI
✅ **MCP Protocol Integration** - Use external tools via Model Context Protocol (stdio, HTTP, SSE)
✅ **Ephemeral Execution** - No persistent state, clean spawn → execute → terminate lifecycle
✅ **Multiagency** - Orchestrate inline sub-agentlets as tools; per-sub-agent stats and OTel tracing
✅ **Production Logging** - 3-layer logging with automatic secret sanitization and correlation
✅ **OpenTelemetry Ready** - Built-in OTLP traces and metrics export; sub-agent spans auto-nested
✅ **Rich Console Output** - Beautiful terminal UX with panels, syntax highlighting, and progress indicators
✅ **Retry Logic** - Adaptive exponential backoff with API-suggested wait times

## Technology Stack

- **Python 3.13+** - Modern Python with latest features
- **Strands Agent Framework** - Agent orchestration and tool management
- **LiteLLM** - Multi-provider LLM support with cost tracking
- **Pydantic** - Configuration validation
- **Rich** - Beautiful console output
- **OpenTelemetry** - Distributed tracing and metrics

## Community & Support

- **Issues**: [GitHub Issues](https://github.com/Synteles/agentlet/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Synteles/agentlet/discussions)

## Quick Example

```yaml
# simple-assistant.yaml
agentlet:
  name: "simple-assistant"
  version: "1.0.0"

model:
  provider: "anthropic"
  model_id: "claude-sonnet-4-6"

system_prompt: "You are a helpful assistant."

tools:
  - "bash"
  - "file_editor"
```

```bash
# Run the agentlet
agentlet-core --agentlet simple-assistant.yaml --prompt "Say hello!"
```

## Version

Current version: **0.1.0-alpha**

See [Versioning Strategy](operations/versioning.md) for release information.
