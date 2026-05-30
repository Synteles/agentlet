# Contributing to Synteles Agentlet

Thank you for your interest in contributing to Synteles Agentlet.

Synteles Agentlet is a Python runtime for autonomous AI agents built on the Strands Agent Framework. It provides standardized, containerized building blocks for AI agency with multi-provider LLM support, MCP tools integration, declarative configuration, and production observability.

Contributions are welcome across code, documentation, examples, tests, developer experience, security hardening, and architecture discussions.

## Table of Contents

- [Ways to Contribute](#ways-to-contribute)
- [Before You Start](#before-you-start)
- [Development Setup](#development-setup)
- [Contribution Workflow](#contribution-workflow)
- [Branch Naming](#branch-naming)
- [Commit Messages](#commit-messages)
- [Pull Request Guidelines](#pull-request-guidelines)
- [Coding Guidelines](#coding-guidelines)
- [Documentation Guidelines](#documentation-guidelines)
- [Testing Guidelines](#testing-guidelines)
- [Security Guidelines](#security-guidelines)
- [Responsible AI-Assisted Coding](#responsible-ai-assisted-coding)
- [Human Responsibility](#human-responsibility)
- [Disclosure](#disclosure)
- [Developer Certificate of Origin](#developer-certificate-of-origin)
- [Code of Conduct](#code-of-conduct)
- [Security Issues](#security-issues)
- [Governance](#governance)
- [License](#license)

## Ways to Contribute

You can contribute by:

- Reporting bugs and runtime issues
- Improving documentation and examples
- Suggesting agent runtime improvements
- Adding example agentlets (simple, multi-agent, swarm patterns)
- Building MCP tool integrations (stdio, HTTP, SSE)
- Improving observability (logging, OpenTelemetry, tracing)
- Improving tests and test coverage
- Improving local development and Docker setup
- Improving security posture and safe defaults
- Reviewing issues and pull requests
- Sharing feedback from real agent automation use cases

Good first areas for contribution include:

- Documentation fixes and clarifications
- Quick-start improvements
- Example agentlets and configurations
- Test coverage improvements
- Error message improvements
- Developer experience improvements
- CI/CD and build tooling

## Before You Start

For small changes, such as typo fixes or documentation improvements, you can open a pull request directly.

For larger changes, please open an issue first to discuss the proposal.

Larger changes may include:

- Agent runtime lifecycle or execution model changes
- Configuration schema changes
- MCP tool integration changes
- Observability or logging changes
- CLI interface changes
- Test framework or structure changes
- Breaking changes to user-facing APIs
- Security-sensitive functionality

A good proposal should explain:

- The problem being solved
- The proposed approach
- Alternatives considered
- Expected impact on users and maintainers
- Security, compatibility, or migration considerations

## Development Setup

Clone the repository:

```bash
git clone https://github.com/Synteles/agentlet.git
cd agentlet
```

Copy the example environment file:

```bash
cp .env.example .env
```

Install dependencies with `uv`:

```bash
uv sync --group dev
```

Run tests and quality checks:

```bash
make check      # lint, typecheck, security, test
make test       # pytest only
make lint       # ruff check
make typecheck  # mypy
make format     # ruff format
```

Run a quick example:

```bash
export ANTHROPIC_API_KEY="your-key"
uv run agentlet-core --agentlet examples/agentlets/simple-assistant.yaml --prompt "Say hello"
```

See the README and documentation in the `docs/` directory for detailed setup instructions.

If the setup fails, please open an issue with:

- Operating system
- Docker version
- Error logs
- Steps to reproduce
- Any local configuration differences

## Contribution Workflow

1. Fork the repository.
2. Create a feature branch:

   ```bash
   git checkout -b feature/your-change
   ```

3. Make your changes.
4. Add or update tests where relevant.
5. Add or update documentation where relevant.
6. Run local checks.
7. Commit your changes with a sign-off.
8. Open a pull request against `main`.

Example:

```bash
git commit -s -m "Add document processing workflow example"
```

## Branch Naming

Use short, descriptive branch names with a consistent prefix.

| Prefix | Use for | Example |
|---|---|---|
| `feature/` | New features or capabilities | `feature/document-processing-example` |
| `fix/` | Bug fixes | `fix/workflow-retry-handling` |
| `docs/` | Documentation changes only | `docs/quickstart-update` |
| `test/` | Adding or improving tests | `test/connector-runtime` |
| `refactor/` | Code restructuring without behavior change | `refactor/scheduler-error-handling` |
| `chore/` | Maintenance — config, tooling, CI, scripts | `chore/update-docker-compose-healthchecks` |
| `bump/` | Dependency or version bumps | `bump/litellm-1.50` |
| `security/` | Security fixes or hardening | `security/sanitize-execution-logs` |
| `perf/` | Performance improvements | `perf/agentlet-startup-time` |

## Commit Messages

Use clear, descriptive commit messages.

Good examples:

```text
Add document processing example workflow
Fix workflow retry handling
Update Docker Compose quickstart
Add connector interface documentation
```

Avoid vague messages such as:

```text
Update stuff
Fix bug
Changes
WIP
```

## Pull Request Guidelines

Please make sure your pull request:

- Has a clear title and description
- Explains the motivation for the change
- Keeps changes focused and reviewable
- Links to related issues where relevant
- Includes tests where appropriate
- Updates documentation if behavior changes
- Does not include secrets, credentials, private URLs, customer data, or local generated files
- Does not introduce unnecessary dependencies
- Does not include unrelated formatting or refactoring
- Uses a signed-off commit under the Developer Certificate of Origin

A good pull request description includes:

```markdown
## Summary

Briefly explain what changed.

## Motivation

Why is this change needed?

## Testing

How was this tested?

## Notes

Anything reviewers should pay attention to.
```

## Coding Guidelines

General guidelines:

- Keep changes simple and focused
- Prefer readable code over clever code
- Use explicit names for functions, classes, files, and agentlet configurations
- Handle errors intentionally and propagate context
- Avoid hidden side effects
- Avoid unnecessary global state
- Keep interfaces stable where possible
- Document public APIs, configuration options, and complex behaviors
- Keep dependencies minimal and justified
- Use type hints — this is a Python 3.13+ project

For agent runtime code:

- Make agent state transitions explicit
- Make tool calls traceable (for observability)
- Design clean execution boundaries (spawn → execute → terminate)
- Treat tool execution failures as first-class concerns
- Prefer clear, auditable error messages
- Avoid unsafe defaults
- Design for production observability from the start
- Consider retry and error recovery patterns

For MCP tool integration:

- Support stdio, HTTP, and SSE transports
- Validate tool schemas and error handling
- Test tool initialization and cleanup
- Document environment variable expansion
- Handle missing or misconfigured tools gracefully

For configuration:

- Use Pydantic for validation
- Provide clear error messages for invalid configs
- Support YAML, JSON, and environment variable expansion
- Document all configuration fields
- Consider backward compatibility for breaking changes

## Documentation Guidelines

Documentation is a core part of Synteles Agentlet.

When contributing documentation:

- Be clear and practical
- Prefer examples over abstract explanations
- Keep quickstart instructions copy-pasteable and tested
- Mention required environment variables (e.g., `ANTHROPIC_API_KEY`)
- Document assumptions and limitations
- Avoid overstating production readiness
- Use consistent terminology:
  - Agent, agentlet, autonomous agent
  - Model provider, LLM
  - MCP tools, tool integration
  - Configuration, YAML schema
  - Observable, observability, tracing, logging
  - Multiagency, sub-agentlet, swarm pattern
  - Execution context, spawn, execute, terminate

If you add a feature, please consider whether it needs updates to:

- `README.md`
- `docs/getting-started/` (quickstart, installation)
- `docs/user-guide/` (configuration, running agentlets, MCP integration)
- `docs/architecture/` (agent lifecycle, tool management)
- `docs/reference/` (logging, telemetry, monitoring)
- Example agentlets in `examples/agentlets/`

## Testing Guidelines

Contributions should include tests where practical.

Synteles Agentlet uses:

- **pytest** — test execution and discovery
- **pytest-asyncio** — async test support
- **pytest-cov** — coverage reporting
- **mypy** — type checking

Running tests:

```bash
make test           # Run all tests
make check          # Run lint, type, security, and tests
```

Test structure in `tests/unit/`:

- Config validation tests (`test_config.py`)
- Runtime tests (`test_runtime.py`)
- MCP tool integration tests (`test_mcp_manager.py`)
- Logging and observability tests
- Remote loading tests
- Retry logic tests
- Telemetry/OpenTelemetry tests
- Sub-agentlet and swarm pattern tests

For agent-related changes, test at least:

- Successful execution path
- Error and retry paths
- Tool invocation and error handling
- Configuration loading and validation
- Logging output and correlation context
- Cleanup and resource deallocation

Aim for comprehensive coverage — this project has 270+ tests across 15+ test files.

If a change is not tested, explain why in the pull request.

## Security Guidelines

Security-sensitive contributions require extra care.

Do not commit:

- API keys
- Access tokens
- Passwords
- Private keys
- Customer data
- Personal data
- Internal URLs or infrastructure details
- Private LLM prompts or configurations

Use `.env.example` for configuration templates.

Security-related changes should consider:

- LLM model access and tool execution boundaries
- Secret handling and sanitization in logs
- MCP tool permissions and least-privilege access
- Input validation and injection prevention
- Dependency risk and supply-chain security
- Error messages (avoid exposing internals)
- Safe defaults for agent configuration

Please report security vulnerabilities privately. Do not open public GitHub issues for vulnerabilities.

See [SECURITY.md](SECURITY.md).

## Responsible AI-Assisted Coding

AI-assisted coding tools are allowed when contributing to Synteles Agentlet.

Examples include code completion tools, chat-based coding assistants, AI-generated tests, AI-assisted documentation, and refactoring suggestions.

However, contributors remain fully responsible for all submitted work.

By submitting a contribution, you confirm that:

- You understand the code, documentation, or assets you are submitting
- You have reviewed and tested the contribution
- You have the right to submit the contribution under the project license
- The contribution does not knowingly include copyrighted or proprietary material copied from third-party sources without permission
- The contribution does not include confidential information, secrets, personal data, or employer-owned code
- The contribution does not introduce known security vulnerabilities
- The contribution does not rely on AI-generated output that you cannot explain, maintain, or license appropriately

AI-assisted contributions should follow the same quality, security, and licensing standards as any other contribution.

## Human Responsibility

AI tools may assist with drafting, coding, refactoring, testing, or documentation, but they do not replace human judgment.

The contributor is responsible for:

- Correctness
- Security
- Maintainability
- Licensing
- Compatibility with project goals
- Testing
- Reviewing generated code for hallucinated APIs, unsafe patterns, or hidden assumptions

Do not submit AI-generated code that you do not understand.

Do not submit code generated from private, proprietary, or confidential inputs unless you have the right to use and disclose those inputs.

Do not include prompts, generated outputs, or references that expose sensitive information.

## Disclosure

For normal small contributions, disclosure of AI assistance is not required.

For larger or security-sensitive contributions, please mention AI assistance in the pull request if it materially shaped the implementation.

Example:

```text
Parts of this implementation were drafted with AI assistance and manually reviewed, tested, and modified before submission.
```

Maintainers may ask follow-up questions about AI-assisted contributions, especially for security-sensitive, licensing-sensitive, or complex architectural changes.

## Developer Certificate of Origin

Synteles Agentlet uses the Developer Certificate of Origin, or DCO, for contributions.

By contributing to this project, you certify that you have the right to submit your contribution under the Apache License, Version 2.0.

Each commit must include a sign-off line:

```text
Signed-off-by: Your Name <your.email@example.com>
```

You can add this automatically with:

```bash
git commit -s
```

The sign-off means that you agree to the Developer Certificate of Origin below.

```text
Developer Certificate of Origin
Version 1.1
Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.
Developer's Certificate of Origin 1.1
By making a contribution to this project, I certify that:
(a) The contribution was created in whole or in part by me and I have the right
    to submit it under the open source license indicated in the file; or
(b) The contribution is based upon previous work that, to the best of my knowledge,
    is covered under an appropriate open source license and I have the right under
    that license to submit that work with modifications, whether created in whole
    or in part by me, under the same open source license unless I am permitted to
    submit under a different license, as indicated in the file; or
(c) The contribution was provided directly to me by some other person who certified
    (a), (b), or (c) and I have not modified it.
(d) I understand and agree that this project and the contribution are public and
    that a record of the contribution, including all personal information I submit
    with it, including my sign-off, is maintained indefinitely and may be
    redistributed consistent with this project or the open source license involved.
```

## Code of Conduct

All contributors and participants are expected to follow the project Code of Conduct.

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Security Issues

Please do not report security vulnerabilities through public GitHub issues.

See [SECURITY.md](SECURITY.md).

## Governance

Project governance is described in [GOVERNANCE.md](GOVERNANCE.md).

Synteles Agentlet is currently a founder-led open-source project. As the community grows, governance may evolve.

## License

By contributing to Synteles Agentlet, you agree that your contributions will be licensed under the Apache License, Version 2.0, unless explicitly stated otherwise.

See [LICENSE](LICENSE).

The Synteles name, logo, and related brand assets are not licensed under the Apache License, Version 2.0.

See [TRADEMARKS.md](TRADEMARKS.md).
