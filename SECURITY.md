# Security Policy

Security is a top priority for Synteles Agentlet because the project is designed for autonomous AI agents, tool execution, integrations, and deployment across enterprise-controlled environments.

Synteles Agentlet is currently in early development. Security support is provided on a best-effort basis until the project reaches a stable release.

## Supported Versions

| Version | Supported |
|---|---|
| `main` | Best effort |
| `v0.x` releases | Best effort |

Breaking changes may occur before `v1.0`.

## Reporting a Vulnerability

Please do not report security vulnerabilities through public GitHub issues.

Report suspected vulnerabilities by email:

```text
security@synteles.io
```

Please include as much detail as possible:

- Description of the vulnerability
- Affected component or version
- Steps to reproduce
- Potential impact
- Any proof-of-concept or logs, if safe to share
- Suggested mitigation, if known
- Your preferred contact details for follow-up

## Response Expectations

We will make a best-effort attempt to:

- Acknowledge the report within 5 business days
- Investigate and validate the issue
- Prioritize a fix or mitigation based on severity
- Coordinate disclosure where appropriate
- Credit the reporter if desired and appropriate

Because Synteles Agentlet is currently maintained by a small team, response times may vary.

## Responsible Disclosure

Please give the maintainers reasonable time to investigate and address the issue before publicly disclosing details.

Please do not:

- Access, modify, delete, or exfiltrate data that does not belong to you
- Perform testing against systems you do not own or have permission to test
- Disrupt project infrastructure or third-party services
- Use social engineering, phishing, or physical attacks
- Publicly disclose exploit details before a fix or mitigation is available

## Security Scope

Examples of issues that are in scope:

- LLM model access and credential exposure
- MCP tool execution boundary violations
- Prompt injection or unsafe input handling
- Remote code execution via tool execution
- Agent state or execution context exposure
- Insecure default configuration with meaningful impact
- Unsafe MCP tool permissions or filters
- Tool execution that could lead to unauthorized system access
- Injection vulnerabilities in configuration or tool parameters
- Supply-chain or dependency risks
- Secrets, tokens, or credentials exposed in logs or errors
- Secret sanitization bypass

## Out of Scope

The following are generally out of scope unless they demonstrate a concrete security impact:

- Reports from automated scanners without exploitability details
- Denial-of-service issues in local-only development environments
- Issues requiring physical access to a developer machine
- Social engineering
- Missing security headers in local development deployments
- Vulnerabilities in third-party services not controlled by Synteles Agentlet
- Best-practice suggestions without a specific vulnerability

## Dependency Vulnerabilities

Synteles Agentlet dependencies are subject to automated security scanning via CI/CD.

If you discover a vulnerability in a dependency:

- **In Synteles Agentlet or its documentation:** Report privately to security@synteles.io
- **In upstream dependencies:** Report to the dependency maintainer directly (or their security contact)
- **If urgent or critical:** You may contact both the maintainer and the upstream project

Synteles Agentlet uses the following security tools:

- **bandit** — Python security linting (runs on all PRs)
- **mypy** — Type checking to catch unsafe patterns
- **Trivy** — Container image vulnerability scanning
- **Gitleaks** — Secret detection to prevent credential commits

Dependency updates and security patches are prioritized based on severity and impact to agent execution. Critical vulnerabilities will trigger patch releases.

## Handling Sensitive Data

When reporting an issue, please avoid sending real secrets, personal data, customer data, or confidential information.

If you accidentally discover sensitive data, stop testing and report the issue immediately.

## Security Best Practices for Users

When running Synteles Agentlet:

**Credential Management:**
- Do not commit real secrets to the repository
- Use `.env.example` as a template, not as a place for real credentials
- Rotate credentials if they are accidentally exposed
- Use least-privilege credentials for LLM providers and integrations
- Store credentials in environment variables or secrets management systems
- Never log or display API keys

**LLM Model Security:**
- Protect model provider API keys (Anthropic, AWS Bedrock, OpenAI, etc.)
- Use API keys with appropriate scopes and rate limits
- Monitor API usage for unexpected activity
- Be aware of prompt injection risks when user input reaches the model
- Review system prompts and user inputs before production use
- Consider using separate API keys for development and production

**MCP Tool Security:**
- Restrict tool access via `allowed` and `rejected` tool filters
- Use environment variable expansion carefully (validate what gets passed)
- Set `ALLOWED_DIRECTORIES` for file system tools (least privilege)
- Monitor tool execution output (can expose sensitive data)
- Validate tool responses before proceeding with agent logic
- Review tool definitions and permissions before production use

**Agent Execution:**
- Review agentlet configurations before deployment
- Monitor agent execution logs for errors or unexpected behavior
- Audit tool invocations and results
- Restrict deployments to trusted infrastructure
- Use separate credentials for development and production
- Implement rate limiting and timeout controls

## Production Use

Synteles Agentlet is currently pre-v1.0 and in early development.

Before using Synteles Agentlet in production, teams should:

- Perform their own security review of configurations
- Review and validate all MCP tool definitions and permissions
- Audit LLM model selection and API key management
- Assess data exposure risks in agent execution paths
- Test error handling and secret sanitization
- Review logs to ensure sensitive data is not exposed
- Implement monitoring and alerting for agent execution
- Establish incident response procedures
- Consider compliance requirements (GDPR, SOC 2, etc.)
- Review supply-chain security and dependency management
