# Development Setup

Set up your development environment for contributing to agentlet-core.

## Prerequisites

- **Python 3.13+** required
- **uv** package manager (recommended)
- **Git** for version control
- **Node.js** (optional, for MCP stdio tools testing)

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/Synteles/agentlet.git
cd agentlet
```

### 2. Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH
export PATH="$HOME/.cargo/bin:$PATH"
```

### 3. Install Dependencies

```bash
# Install all dependencies including dev tools
uv sync --group dev

# Or with OpenTelemetry support
uv sync --group dev --group otel
```

**Installed tools:**
- **pytest** - Testing framework
- **pytest-asyncio** - Async test support
- **pytest-cov** - Coverage reporting
- **mypy** - Type checking
- **ruff** - Linting and formatting
- **bandit** - Security analysis

### 4. Verify Installation

```bash
# Run tests
uv run pytest

# Type check
uv run mypy .

# Lint
uv run ruff check .

# All checks
make check
```

## IDE Setup

### VSCode

**Recommended Extensions:**
- Python (Microsoft)
- Pylance (Microsoft)
- Ruff (Astral)
- Python Test Explorer

**Settings** (`.vscode/settings.json`):
```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["-v"],
  "python.linting.enabled": true,
  "python.linting.mypyEnabled": true,
  "editor.formatOnSave": true,
  "python.formatting.provider": "none",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.codeActionsOnSave": {
      "source.organizeImports": true,
      "source.fixAll": true
    }
  },
  "ruff.path": ["${workspaceFolder}/.venv/bin/ruff"]
}
```

**Launch Configuration** (`.vscode/launch.json`):
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Current File",
      "type": "python",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal",
      "justMyCode": false
    },
    {
      "name": "Agentlet: Run Example",
      "type": "python",
      "request": "launch",
      "module": "agentlet_core.cli.main",
      "args": [
        "--agentlet", "examples/simple-assistant.yaml",
        "--prompt", "Say hello",
        "--debug"
      ],
      "console": "integratedTerminal",
      "justMyCode": false,
      "env": {
        "ANTHROPIC_API_KEY": "${env:ANTHROPIC_API_KEY}"
      }
    },
    {
      "name": "Pytest: Current File",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["-v", "${file}"],
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

### PyCharm

**Project Setup:**
1. Open project folder
2. Set Python interpreter to `.venv/bin/python`
3. Enable pytest as test runner
4. Configure ruff as external tool

**Run Configuration:**
```
Name: Run Agentlet
Module: agentlet_core.cli.main
Parameters: --agentlet examples/simple-assistant.yaml --prompt "Hello" --debug
Environment: ANTHROPIC_API_KEY=your-key
```

## Code Style

### Ruff (Linter & Formatter)

**Configuration** (`pyproject.toml`):
```toml
[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = ["E501"]  # Line too long (handled by formatter)
```

**Commands:**
```bash
# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check . --fix

# Format code
uv run ruff format .

# Or use make
make lint    # Check only
make format  # Format code
```

### Mypy (Type Checking)

**Configuration** (`pyproject.toml`):
```toml
[tool.mypy]
python_version = "3.13"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
```

**Commands:**
```bash
# Type check entire project
uv run mypy .

# Type check specific module
uv run mypy agentlet_core

# Or use make
make typecheck
```

### Bandit (Security)

```bash
# Security scan
uv run bandit -r agentlet_core/ -ll

# Or use make
make security
```

## Pre-commit Hooks

**Install pre-commit** (optional but recommended):

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install
```

**Configuration** (`.pre-commit-config.yaml`):
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.6
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.18.2
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/my-feature
```

### 2. Make Changes

Edit code, add tests, update documentation.

### 3. Run Checks

```bash
# All checks
make check

# Or individually
make lint
make typecheck
make security
make test
```

### 4. Commit Changes

```bash
git add .
git commit -m "feat: add new feature"
```

**Commit message format:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions/changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

### 5. Push and Create PR

```bash
git push origin feature/my-feature
```

Then create Pull Request on GitHub.

## Running Tests Locally

```bash
# All tests
uv run pytest

# Verbose output
uv run pytest -v

# Specific test file
uv run pytest tests/unit/test_config.py

# Specific test
uv run pytest tests/unit/test_config.py::test_model_config

# With coverage
uv run pytest --cov=agentlet_core --cov-report=html

# Or use make
make test
```

## Makefile Commands

```bash
make test          # Run all tests
make typecheck     # Type checking with mypy
make lint          # Linting with ruff
make format        # Format code with ruff
make security      # Security scan with bandit
make check         # All checks (lint + typecheck + security + test)
make clean         # Remove cache files
```

## Environment Variables

Create `.env` file for development:

```bash
# .env
ANTHROPIC_API_KEY=your-anthropic-key
OPENAI_API_KEY=your-openai-key
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key

# Debug
LITELLM_DEBUG=true
```

## Debugging

### Debug Mode

```bash
# Run with debug logging
uv run agentlet-core --agentlet examples/simple-assistant.yaml \
  --prompt "Hello" \
  --debug
```

**Debug mode provides:**
- DEBUG level logs to console
- Log file: `agentlet-core-{timestamp}.log`
- SDK internal logs (litellm, strands)
- Verbose error messages

### Python Debugger

```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use built-in breakpoint()
breakpoint()
```

### VSCode Debugger

Use the launch configurations from `.vscode/launch.json` above.

## Project Structure

```
agentlet-core/
├── agentlet_core/          # Main package
│   ├── agents/             # Agent lifecycle
│   ├── cli/                # CLI interface
│   ├── config/             # Configuration system
│   ├── logging/            # Logging system
│   ├── runtime/            # Execution context
│   ├── telemetry/          # OpenTelemetry
│   ├── tools/              # Tool management
│   └── utils/              # Utilities
├── tests/                  # Test suite
│   └── unit/               # Unit tests
├── examples/               # Example agentlets
│   └── agentlets/          # Example configs
├── docs/                   # Documentation
├── pyproject.toml          # Project config
├── Makefile                # Development commands
└── README.md               # Project README
```

## Documentation

When adding features, update documentation:

```bash
# Update relevant docs in docs/
docs/
├── getting-started/
├── user-guide/
├── architecture/
├── observability/
├── development/
└── operations/
```

## Common Issues

### Import Errors

```bash
# Ensure in project root and venv activated
cd agentlet-core
source .venv/bin/activate  # or let uv handle it
```

### Type Check Failures

```bash
# Add type hints or type: ignore
def my_function(param: str) -> int:  # type: ignore[return-value]
    ...
```

### Test Failures

```bash
# Run specific test with verbose output
uv run pytest -v -s tests/unit/test_config.py::test_model_config
```

## Next Steps

- **[Testing Guide](testing.md)** - Learn about testing patterns
- **[Contributing](contributing.md)** - Contribution guidelines
- **[Debugging](debugging.md)** - Advanced debugging techniques
