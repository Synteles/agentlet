# Changelog

All notable changes to Synteles will be documented in this file.

This project intends to follow semantic versioning once the public APIs, workflow definitions, and runtime interfaces become stable.

Before `v1.0`, breaking changes may occur without a major version bump.

## [Unreleased]

### Changed

- Restructured documentation layout: consolidated observability docs into `docs/reference/`, removed stale files (`ci-cd.md`, `deployment.md`, `versioning.md`, `core-concepts.md`), rewrote architecture docs to remove duplicated source code in favour of diagrams and tables, and synced README badges and section links with the current docs structure.

## [0.1.0-alpha] - 2026-05-27

### Added

- Initial open-source alpha release of Synteles Agentlet
- Ephemeral execution — clean spawn → execute → terminate lifecycle
- Multi-provider LLM — Anthropic, AWS Bedrock, OpenAI, Azure, and more via LiteLLM
- MCP support — integrate external tools via stdio, HTTP, and SSE transports
- Multiagency — orchestrator/sub-agentlet pipelines and peer-to-peer swarm patterns
- Declarative config — YAML/JSON with Pydantic validation and JSON Schema
- Production observability — 3-layer logging, OpenTelemetry traces/metrics, secret sanitization
- Local development setup with Docker Compose
- Comprehensive documentation: quickstart, concepts, architecture, operations, development, and observability
- Example agentlets and workflows
- Apache License 2.0 project licensing
- Code of Conduct, Security policy, and Governance documentation
- DCO-based contribution process
- Responsible AI-assisted coding contribution policy

### Changed

- None

### Fixed

- None

### Removed

- None

### Security

- Added initial security reporting policy

### Known Limitations

- Early alpha release
- APIs may change
- Runtime interfaces may change
- Production deployment requires manual review and hardening
- Security support is best-effort before stable release