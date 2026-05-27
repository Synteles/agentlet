# Contributing to Agentlet Core

Thank you for your interest in contributing to agentlet-core! This guide will help you get started.

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct:

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Respect differing viewpoints and experiences

## Getting Started

### 1. Fork and Clone

```bash
# Fork on GitHub first, then:
git clone https://github.com/YOUR_USERNAME/agentlet-core.git
cd agentlet-core
```

### 2. Set Up Development Environment

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --group dev

# Verify setup
make check
```

See [Development Setup](setup.md) for detailed instructions.

### 3. Create Feature Branch

```bash
git checkout -b feature/my-feature
# or
git checkout -b fix/bug-description
```

## Development Workflow

### 1. Make Changes

- Write clean, maintainable code
- Follow existing code style
- Add tests for new functionality
- Update documentation as needed

### 2. Run Quality Checks

```bash
# All checks
make check

# Or individually
make lint      # Ruff linting
make typecheck # Mypy type checking
make security  # Bandit security scan
make test      # Pytest tests
```

### 3. Commit Changes

```bash
git add .
git commit -m "feat: add new feature"
```

**Commit Message Format:**

```
<type>: <short description>

<optional detailed description>

<optional footer>
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions or changes
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `chore:` - Maintenance tasks
- `ci:` - CI/CD changes

**Examples:**

```bash
# Feature
git commit -m "feat: add OpenTelemetry metrics export"

# Bug fix
git commit -m "fix: resolve MCP stdio process cleanup issue"

# Documentation
git commit -m "docs: update configuration guide with new options"

# With details
git commit -m "feat: add retry logic with exponential backoff

- Implement RetryHandler class
- Add adaptive wait time extraction
- Support progressive backoff
- Add tests for retry scenarios"
```

### 4. Push Changes

```bash
git push origin feature/my-feature
```

### 5. Create Pull Request

1. Go to GitHub repository
2. Click "New Pull Request"
3. Select your branch
4. Fill out PR template
5. Submit for review

## Pull Request Guidelines

### PR Template

When creating a PR, include:

**Title:** Clear, descriptive summary
```
feat: add OpenTelemetry metrics export
```

**Description:**

```markdown
## What

Brief description of what this PR does.

## Why

Why is this change needed? What problem does it solve?

## How

How does this implementation work? Any notable technical decisions?

## Testing

How was this tested? Include test scenarios.

## Checklist

- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Type hints added
- [ ] All checks passing
- [ ] Breaking changes documented (if any)
```

### Review Process

1. **Automated Checks** - All CI checks must pass
2. **Code Review** - At least one maintainer approval required
3. **Testing** - Reviewers may test manually
4. **Feedback** - Address review comments
5. **Merge** - Maintainer merges when approved

### Response to Feedback

- Address all review comments
- Ask for clarification if needed
- Update PR with requested changes
- Mark conversations as resolved
- Be patient and respectful

## Code Style

### Python Style

**Follow PEP 8** with these specifics:

```python
# Line length: 100 characters
# Use type hints
def process_config(config: AgentletConfig) -> ExecutionContext:
    """Process agentlet configuration.

    Args:
        config: Validated agentlet configuration

    Returns:
        Initialized execution context

    Raises:
        ValueError: If configuration is invalid
    """
    ...

# Use descriptive names
def calculate_retry_wait_time(attempt: int, base_interval: float) -> float:
    """Calculate exponential backoff wait time."""
    return min(base_interval * (2**attempt), 300.0)

# Prefer explicit over implicit
if error_type == "RateLimitError":
    retry = True
else:
    retry = False

# Use f-strings for formatting
message = f"Execution {execution_id} completed in {duration:.2f}s"

# Avoid magic numbers
MAX_RETRIES = 5  # At module level
TIMEOUT_SECONDS = 300

# Group imports
from typing import Optional, Dict  # Standard library
import asyncio

from pydantic import BaseModel  # Third-party

from agentlet_core.config import AgentletConfig  # Local
```

### Ruff Configuration

Ruff handles both linting and formatting:

```bash
# Check and auto-fix
uv run ruff check . --fix

# Format code
uv run ruff format .
```

### Type Hints

**Always use type hints:**

```python
from typing import Optional, Dict, List, Any


def load_config(path: str) -> AgentletConfig:
    """Load configuration from file."""
    ...


async def execute(prompt: str, timeout: Optional[int] = None) -> Dict[str, Any]:
    """Execute agentlet with optional timeout."""
    ...


class ExecutionContext:
    """Execution context manager."""

    def __init__(self, agentlet_name: str, work_dir: Path) -> None:
        self.agentlet_name: str = agentlet_name
        self.work_dir: Path = work_dir
        self.tool_calls: List[Dict[str, Any]] = []
```

### Documentation Strings

**Use Google-style docstrings:**

```python
def retry_async_generator(
    func: AsyncGenerator,
    max_retries: int = 5,
    error_types: Optional[List[str]] = None,
) -> AsyncGenerator:
    """Retry async generator with exponential backoff.

    Wraps an async generator to automatically retry on specific error types
    using exponential backoff with jitter.

    Args:
        func: Async generator to wrap
        max_retries: Maximum number of retry attempts (default: 5)
        error_types: List of error type names to retry on. If None, uses default
            set of retryable errors (RateLimitError, APIConnectionError, etc.)

    Yields:
        Events from the async generator

    Raises:
        Exception: Re-raises exception if max retries exceeded or error type
            not in retryable list

    Example:
        ```python
        async for event in retry_async_generator(
            agent.stream_async(prompt),
            max_retries=3
        ):
            process_event(event)
        ```
    """
    ...
```

## Testing Requirements

### All Changes Must Include Tests

**New features:**
```python
# tests/unit/test_new_feature.py
def test_new_feature_basic():
    """Test basic functionality of new feature."""
    ...


def test_new_feature_edge_cases():
    """Test edge cases for new feature."""
    ...


def test_new_feature_error_handling():
    """Test error handling in new feature."""
    ...
```

**Bug fixes:**
```python
def test_bug_fix_regression():
    """Test that bug fix prevents regression."""
    # Reproduce the bug scenario
    # Assert fix works
    ...
```

### Coverage Requirements

- **New code:** 80%+ coverage
- **Critical modules:** 90%+ coverage
- **No coverage decrease:** Total coverage should not decrease

```bash
# Check coverage
uv run pytest --cov=agentlet_core --cov-report=term-missing
```

## Documentation Requirements

### Update Documentation

When adding features, update relevant docs:

```
docs/
├── getting-started/    # For user-facing features
├── user-guide/         # For configuration/usage changes
├── architecture/       # For architectural changes
├── observability/      # For logging/telemetry changes
├── development/        # For dev process changes
└── operations/         # For deployment/ops changes
```

### Docstring Requirements

- All public functions/classes must have docstrings
- Include parameters, return values, exceptions
- Provide usage examples for complex functionality

### Code Comments

```python
# Use comments to explain WHY, not WHAT
# Good
retry_count += 1  # Progressive backoff for repeated rate limits

# Bad
retry_count += 1  # Increment retry count

# Explain complex logic
# Use API-suggested wait time if available, otherwise use exponential backoff
# This prevents overwhelming rate-limited APIs
wait_time = (
    self._extract_api_suggested_wait_time(error)
    or self._calculate_wait_time(attempt)
)
```

## Common Contribution Scenarios

### Adding a New Feature

1. **Discuss** - Open issue first for large features
2. **Design** - Consider architecture and integration points
3. **Implement** - Write code with tests
4. **Document** - Update user-facing and architecture docs
5. **Test** - Verify with various scenarios
6. **Submit PR** - Include comprehensive description

### Fixing a Bug

1. **Reproduce** - Write test that demonstrates bug
2. **Fix** - Implement fix
3. **Verify** - Test passes with fix, fails without
4. **Document** - Add comments explaining the fix
5. **Submit PR** - Reference issue number

### Improving Documentation

1. **Identify gap** - Find missing or unclear documentation
2. **Update** - Improve clarity, add examples
3. **Verify** - Check links, test code examples
4. **Submit PR** - Documentation-only PRs welcome!

### Adding Tests

1. **Identify coverage gaps** - Check coverage report
2. **Write tests** - Add missing test cases
3. **Verify** - Tests pass and coverage increases
4. **Submit PR** - Test-only PRs welcome!

## What to Contribute

### Good First Issues

Look for issues labeled:
- `good first issue` - Beginner-friendly
- `help wanted` - Maintainer needs help
- `documentation` - Documentation improvements

### Areas Needing Help

- **Tests** - Improve coverage
- **Documentation** - Examples, guides, tutorials
- **Bug fixes** - Check issue tracker
- **Performance** - Optimization opportunities
- **Examples** - More example agentlets

## Getting Help

### Questions

- **GitHub Discussions** - Ask questions, share ideas
- **GitHub Issues** - Bug reports, feature requests
- **Code Review** - Ask for clarification in PR comments

### Resources

- [Development Setup](setup.md) - Environment setup
- [Testing Guide](testing.md) - Testing patterns
- [Debugging Guide](debugging.md) - Debugging tips
- [Architecture Docs](../architecture/overview.md) - System design

## Release Process

Maintainers handle releases:

1. Version bump in `pyproject.toml`
2. Update CHANGELOG
3. Create git tag `v0.2.0`
4. GitHub Actions builds and publishes
5. PyPI and Docker Hub updated automatically

Contributors don't need to worry about versioning.

## Recognition

Contributors are recognized in:
- Git history
- GitHub contributors page
- Release notes (for significant contributions)

Thank you for contributing to agentlet-core! 🎉
