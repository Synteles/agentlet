"""Tests for retry logic with exponential backoff."""

import logging
import pytest
from unittest.mock import AsyncMock

from agentlet_core.config.models import RetryConfig
from agentlet_core.runtime.retry import RetryHandler
from agentlet_core.runtime.context import ExecutionContext


class MockRateLimitError(Exception):
    """Mock RateLimitError for testing."""

    pass


class MockNonRetryableError(Exception):
    """Mock non-retryable error for testing."""

    pass


@pytest.fixture
def retry_config():
    """Create a test retry configuration."""
    return RetryConfig(
        max_retries=3,
        initial_retry_interval=0.1,  # Short interval for testing
        backoff_factor=2.0,
        max_retry_interval=1.0,
        retry_on_errors=["MockRateLimitError"],
    )


@pytest.fixture
def logger():
    """Create a test logger."""
    return logging.getLogger("test")


@pytest.fixture
def context():
    """Create a test execution context."""
    return ExecutionContext(execution_id="test-123", agentlet_name="test-agent")


@pytest.fixture
def retry_handler(retry_config, logger, context):
    """Create a retry handler for testing."""
    return RetryHandler(retry_config, logger, context)


@pytest.mark.asyncio
async def test_retry_handler_success_no_retry(retry_handler):
    """Test successful execution without retry."""
    mock_func = AsyncMock(return_value="success")

    result = await retry_handler.retry_async(mock_func, "arg1", kwarg1="value1")

    assert result == "success"
    assert mock_func.call_count == 1
    mock_func.assert_called_with("arg1", kwarg1="value1")


@pytest.mark.asyncio
async def test_retry_handler_success_after_retries(retry_handler):
    """Test successful execution after retries."""
    mock_func = AsyncMock()
    # Fail twice, then succeed
    mock_func.side_effect = [
        MockRateLimitError("Rate limit exceeded"),
        MockRateLimitError("Rate limit exceeded"),
        "success",
    ]

    result = await retry_handler.retry_async(mock_func, "arg1")

    assert result == "success"
    assert mock_func.call_count == 3
    assert retry_handler.context.retry_attempts == 2


@pytest.mark.asyncio
async def test_retry_handler_exhausted_retries(retry_handler):
    """Test retry exhaustion."""
    mock_func = AsyncMock()
    # Always fail with retryable error
    mock_func.side_effect = MockRateLimitError("Rate limit exceeded")

    with pytest.raises(MockRateLimitError):
        await retry_handler.retry_async(mock_func, "arg1")

    # Should try max_retries + 1 times (initial + 3 retries)
    assert mock_func.call_count == 4
    assert retry_handler.context.retry_attempts == 3


@pytest.mark.asyncio
async def test_retry_handler_non_retryable_error(retry_handler):
    """Test non-retryable error is not retried."""
    mock_func = AsyncMock()
    mock_func.side_effect = MockNonRetryableError("Non-retryable error")

    with pytest.raises(MockNonRetryableError):
        await retry_handler.retry_async(mock_func, "arg1")

    # Should only try once
    assert mock_func.call_count == 1
    assert retry_handler.context.retry_attempts == 0


@pytest.mark.asyncio
async def test_retry_handler_async_generator(retry_handler):
    """Test retry with async generator function."""
    call_count = 0

    async def mock_generator():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise MockRateLimitError("Rate limit exceeded")
        yield "item1"
        yield "item2"

    results = []
    async for item in retry_handler.retry_async_generator(mock_generator):
        results.append(item)

    assert results == ["item1", "item2"]
    assert call_count == 3
    assert retry_handler.context.retry_attempts == 2


@pytest.mark.asyncio
async def test_retry_handler_backoff_calculation(retry_handler):
    """Test exponential backoff calculation."""
    # Test wait time calculation
    assert retry_handler._calculate_wait_time(0) == 0.1  # initial_retry_interval
    assert retry_handler._calculate_wait_time(1) == 0.2  # 0.1 * 2^1
    assert retry_handler._calculate_wait_time(2) == 0.4  # 0.1 * 2^2
    assert retry_handler._calculate_wait_time(3) == 0.8  # 0.1 * 2^3
    assert retry_handler._calculate_wait_time(4) == 1.0  # Capped at max_retry_interval


def test_should_retry_logic(retry_handler):
    """Test error type checking for retry logic."""
    # Should retry MockRateLimitError
    assert retry_handler._should_retry(MockRateLimitError("test"))

    # Should not retry other errors
    assert not retry_handler._should_retry(MockNonRetryableError("test"))
    assert not retry_handler._should_retry(ValueError("test"))


def test_retry_config_validation():
    """Test retry configuration validation."""
    # Valid config
    config = RetryConfig(
        max_retries=5,
        initial_retry_interval=30.0,
        backoff_factor=2.0,
        max_retry_interval=300.0,
        retry_on_errors=["RateLimitError"],
    )
    assert config.max_retries == 5
    assert config.initial_retry_interval == 30.0
    assert config.backoff_factor == 2.0
    assert config.max_retry_interval == 300.0
    assert config.retry_on_errors == ["RateLimitError"]

    # Test defaults
    default_config = RetryConfig()
    assert default_config.max_retries == 5
    assert default_config.initial_retry_interval == 30.0
    assert default_config.backoff_factor == 2.0
    assert default_config.max_retry_interval == 300.0
    assert default_config.retry_on_errors == [
        "RateLimitError",
        "EventLoopException",
        "APIConnectionError",
        "APITimeoutError",
        "litellm.RateLimitError",
    ]


def test_execution_context_retry_tracking():
    """Test retry attempt tracking in execution context."""
    context = ExecutionContext(execution_id="test-123", agentlet_name="test-agent")

    assert context.retry_attempts == 0

    context.record_retry_attempt()
    assert context.retry_attempts == 1

    context.record_retry_attempt()
    assert context.retry_attempts == 2

    # Check summary includes retry attempts
    summary = context.get_summary()
    assert summary["retry_attempts"] == 2


# ---------------------------------------------------------------------------
# _extract_api_suggested_wait_time
# ---------------------------------------------------------------------------


def test_extract_wait_time_retry_after(retry_handler):
    assert (
        retry_handler._extract_api_suggested_wait_time(
            Exception("Please retry after 60 seconds")
        )
        == 60.0
    )


def test_extract_wait_time_wait_n_seconds(retry_handler):
    assert (
        retry_handler._extract_api_suggested_wait_time(
            Exception("Rate limit exceeded, wait 30 seconds")
        )
        == 30.0
    )


def test_extract_wait_time_retry_in(retry_handler):
    assert (
        retry_handler._extract_api_suggested_wait_time(Exception("retry in 45 seconds"))
        == 45.0
    )


def test_extract_wait_time_no_pattern(retry_handler):
    assert (
        retry_handler._extract_api_suggested_wait_time(Exception("some generic error"))
        is None
    )


# ---------------------------------------------------------------------------
# _calculate_wait_time with api_suggested_wait
# ---------------------------------------------------------------------------


def test_calculate_wait_time_api_suggestion_first_time(retry_handler):
    retry_handler._last_api_suggested_wait = None
    wait = retry_handler._calculate_wait_time(0, api_suggested_wait=20.0)
    # Should be max(exponential, api+buffer) = max(0.1, 25.0) = 25.0, capped at max 1.0
    assert wait == 1.0  # capped at max_retry_interval


def test_calculate_wait_time_api_suggestion_repeated(retry_handler):
    retry_handler._last_api_suggested_wait = 20.0
    wait = retry_handler._calculate_wait_time(1, api_suggested_wait=20.5)  # within 5s
    # Progressive backoff: 20.5 * 1.5^1 = 30.75, capped
    assert wait == 1.0  # capped at max_retry_interval


def test_calculate_wait_time_no_api_suggestion(retry_handler):
    wait = retry_handler._calculate_wait_time(0, api_suggested_wait=None)
    assert wait == pytest.approx(0.1)  # initial_retry_interval * backoff_factor^0


# ---------------------------------------------------------------------------
# retry_async_generator — non-retryable error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_async_generator_non_retryable(retry_handler):
    """Non-retryable errors from an async generator are re-raised immediately."""
    call_count = 0

    async def failing_generator():
        nonlocal call_count
        call_count += 1
        raise MockNonRetryableError("fatal")
        yield  # make it a generator

    with pytest.raises(MockNonRetryableError):
        async for _ in retry_handler.retry_async_generator(failing_generator):
            pass

    assert call_count == 1
