# Testing Guide

Comprehensive guide for testing agentlet-core.

## Test Structure

```
tests/
└── unit/
    ├── test_config.py           # 17 tests - Pydantic validation (incl. SubAgentletConfig)
    ├── test_runtime.py          # 7 tests  - ExecutionContext
    ├── test_env.py              # 8 tests  - Environment loading
    ├── test_logger.py           # 9 tests  - Logging functionality
    ├── test_logging_config.py   # 17 tests - Logging configuration
    ├── test_logging_context.py  # 11 tests - Correlation context
    ├── test_logging_filters.py  # 25 tests - Secret sanitization
    ├── test_remote_loader.py    # 13 tests - Remote loading
    ├── test_mcp_manager.py      # 33 tests - MCP tools
    ├── test_tools_manager.py    # 10 tests - Default tools
    ├── test_retry.py            # 9 tests  - Retry logic
    ├── test_telemetry_config.py # 13 tests - OTEL config
    ├── test_otel_integration.py # 8 tests  - OTEL integration
    └── test_sub_agentlets.py    # 20 tests - Multiagency sub-agentlets
```

**Total:** 230 tests across 14 files

## Running Tests

### All Tests

```bash
# Run all tests
uv run pytest

# Verbose output
uv run pytest -v

# With coverage
uv run pytest --cov=agentlet_core

# HTML coverage report
uv run pytest --cov=agentlet_core --cov-report=html
open htmlcov/index.html

# Or use make
make test
```

### Specific Tests

```bash
# Single test file
uv run pytest tests/unit/test_config.py

# Specific test function
uv run pytest tests/unit/test_config.py::test_model_config

# Tests matching pattern
uv run pytest -k "test_model"

# Failed tests only
uv run pytest --lf  # last failed

# Stop on first failure
uv run pytest -x
```

### Output Options

```bash
# Show print statements
uv run pytest -s

# Quiet mode (minimal output)
uv run pytest -q

# Show test duration
uv run pytest --durations=10

# Parallel execution (install pytest-xdist)
uv run pytest -n auto
```

## Writing Tests

### Test File Template

```python
"""
Tests for module X.

Test coverage:
- Function A: Basic functionality
- Function B: Edge cases
- Error handling
"""

import pytest
from agentlet_core.module import FunctionToTest


class TestClassName:
    """Group related tests together."""

    def test_basic_functionality(self):
        """Test the happy path."""
        result = FunctionToTest(input_data)
        assert result == expected_output

    def test_edge_case(self):
        """Test edge case handling."""
        result = FunctionToTest(edge_case_input)
        assert result == expected_edge_output

    def test_error_handling(self):
        """Test error conditions."""
        with pytest.raises(ValueError, match="expected error message"):
            FunctionToTest(invalid_input)
```

### Testing Async Functions

```python
import pytest


@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await async_function()
    assert result == expected
```

### Using Fixtures

```python
import pytest
from pathlib import Path
import tempfile


@pytest.fixture
def temp_dir():
    """Provide temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config():
    """Provide sample configuration."""
    return {
        "agentlet": {"name": "test", "version": "1.0.0"},
        "model": {"provider": "anthropic", "model_id": "claude-sonnet-4-6"},
    }


def test_with_fixtures(temp_dir, sample_config):
    """Test using fixtures."""
    config_path = temp_dir / "config.yaml"
    # ... use fixtures
```

### Parametrized Tests

```python
@pytest.mark.parametrize(
    "input_value,expected",
    [
        ("anthropic", "anthropic"),
        ("openai", "openai"),
        ("bedrock", "bedrock"),
    ],
)
def test_provider_parsing(input_value, expected):
    """Test with multiple inputs."""
    result = parse_provider(input_value)
    assert result == expected
```

### Mocking

```python
from unittest.mock import Mock, patch, MagicMock


def test_with_mock():
    """Test with mocked dependencies."""
    mock_client = Mock()
    mock_client.get_tools.return_value = ["tool1", "tool2"]

    result = function_using_client(mock_client)
    assert len(result) == 2
    mock_client.get_tools.assert_called_once()


@patch("agentlet_core.module.external_api")
def test_with_patch(mock_api):
    """Test with patched external dependency."""
    mock_api.return_value = "mocked_response"

    result = function_calling_api()
    assert result == "mocked_response"
```

### Testing Exceptions

```python
def test_raises_exception():
    """Test that function raises expected exception."""
    with pytest.raises(ValueError) as exc_info:
        function_that_raises()

    assert "expected message" in str(exc_info.value)


def test_warns():
    """Test that function emits warning."""
    with pytest.warns(UserWarning, match="warning message"):
        function_that_warns()
```

## Test Patterns

### Configuration Testing

```python
from agentlet_core.config.models import AgentletConfig, ModelConfig
from pydantic import ValidationError


def test_valid_config():
    """Test valid configuration."""
    config = AgentletConfig(
        agentlet={"name": "test", "version": "1.0.0"},
        model=ModelConfig(provider="anthropic", model_id="claude-sonnet-4-6"),
    )
    assert config.agentlet.name == "test"


def test_invalid_config():
    """Test configuration validation."""
    with pytest.raises(ValidationError) as exc_info:
        AgentletConfig(agentlet={"name": "test"})  # Missing version

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("agentlet", "version") for e in errors)
```

### Runtime Testing

```python
from agentlet_core.runtime.context import ExecutionContext
import tempfile
from pathlib import Path


def test_execution_context():
    """Test execution context creation and cleanup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        context = ExecutionContext(
            agentlet_name="test", work_dir=Path(tmpdir) / "workspace"
        )

        # Test context properties
        assert context.agentlet_name == "test"
        assert context.execution_id is not None
        assert context.work_dir.exists()

        # Test cleanup
        context.cleanup()
        assert not context.work_dir.exists()
```

### Async Testing

```python
import pytest
import asyncio


@pytest.mark.asyncio
async def test_async_execution():
    """Test async agent execution."""
    config = load_test_config()
    agentlet = BaseAgentlet(config, prompt="Test prompt")

    events = []
    async for event in agentlet.run():
        events.append(event)

    assert len(events) > 0
    assert any("data" in e for e in events)
```

### Environment Variable Testing

```python
import os
from agentlet_core.utils.env import load_env_file


def test_env_loading(tmp_path):
    """Test environment variable loading."""
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_VAR=test_value\n")

    load_env_file(str(env_file))
    assert os.getenv("TEST_VAR") == "test_value"

    # Cleanup
    del os.environ["TEST_VAR"]
```

## Coverage Requirements

### Current Coverage

```bash
# Generate coverage report
uv run pytest --cov=agentlet_core --cov-report=term-missing
```

**Target coverage:** 80%+ for core modules

### Coverage by Module

- `agents/` - 85%+ (core functionality)
- `config/` - 90%+ (critical path)
- `cli/` - 70%+ (user-facing)
- `logging/` - 85%+ (production-critical)
- `runtime/` - 85%+ (core functionality)
- `tools/` - 75%+ (integration points)
- `utils/` - 80%+ (helper functions)

### Excluding from Coverage

```python
# In code
def debug_only_function():  # pragma: no cover
    """Only used in development."""
    ...
```

## CI/CD Testing

### GitHub Actions

Tests run automatically on:
- Push to main
- Pull requests
- Release tags

**Workflow** (`.github/workflows/test.yml`):
```yaml
name: Test
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v1
      - run: uv sync --group dev
      - run: uv run pytest --cov=agentlet_core
```

### Quality Gates

PRs must pass:
- ✅ All tests passing
- ✅ Type checking (mypy)
- ✅ Linting (ruff)
- ✅ Security scan (bandit)
- ✅ Coverage threshold (80%+)

## Best Practices

### DO ✅

1. **Write descriptive test names**
   ```python
   def test_config_loader_handles_missing_file_gracefully()
   ```

2. **Use fixtures for setup**
   ```python
   @pytest.fixture
   def sample_config():
       return load_test_config()
   ```

3. **Test edge cases**
   ```python
   def test_empty_input()
   def test_very_large_input()
   def test_special_characters()
   ```

4. **Clean up resources**
   ```python
   def test_with_cleanup(tmp_path):
       # Test uses tmp_path (auto-cleaned)
       ...
   ```

5. **Mock external dependencies**
   ```python
   @patch("requests.get")
   def test_api_call(mock_get):
       ...
   ```

### DON'T ❌

1. **Don't test implementation details**
   ```python
   # Bad
   assert obj._internal_method() == value

   # Good
   assert obj.public_method() == value
   ```

2. **Don't use real API calls**
   ```python
   # Bad
   response = anthropic.complete(...)  # Real API call

   # Good
   with patch("anthropic.complete") as mock:
       mock.return_value = "mocked"
   ```

3. **Don't ignore async/await**
   ```python
   # Bad
   result = asyncio.run(async_function())

   # Good
   @pytest.mark.asyncio
   async def test_async():
       result = await async_function()
   ```

4. **Don't leave debug code**
   ```python
   # Bad
   def test_something():
       import pdb; pdb.set_trace()  # Remove before commit
   ```

5. **Don't test multiple things in one test**
   ```python
   # Bad
   def test_everything():
       assert function1() == 1
       assert function2() == 2
       assert function3() == 3

   # Good - separate tests
   def test_function1():
       assert function1() == 1
   ```

## Debugging Failed Tests

### Verbose Output

```bash
# Show full output including print statements
uv run pytest -v -s tests/unit/test_config.py::test_model_config
```

### Debug with pdb

```bash
# Drop into debugger on failure
uv run pytest --pdb
```

### Show Locals on Failure

```bash
# Show local variables when test fails
uv run pytest -l
```

### Logging During Tests

```python
import logging


def test_with_logging(caplog):
    """Test captures log output."""
    with caplog.at_level(logging.DEBUG):
        function_that_logs()

    assert "expected log message" in caplog.text
```

## Performance Testing

```python
import time


def test_performance():
    """Test execution time."""
    start = time.time()
    expensive_function()
    duration = time.time() - start

    assert duration < 1.0, f"Too slow: {duration}s"
```

## Integration Testing

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_agentlet_execution():
    """Full integration test (requires API keys)."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("API key not set")

    config = load_test_config()
    agentlet = BaseAgentlet(config, prompt="Say hello")

    result = []
    async for event in agentlet.run():
        if "data" in event:
            result.append(event["data"])

    assert len(result) > 0
```

Run integration tests:
```bash
# Only integration tests
uv run pytest -m integration

# Skip integration tests
uv run pytest -m "not integration"
```

## Next Steps

- **[Development Setup](setup.md)** - Set up development environment
- **[Contributing](contributing.md)** - Contribution guidelines
- **[Debugging](debugging.md)** - Advanced debugging
