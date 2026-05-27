# Copyright 2026 Emin Askerov
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Retry logic with exponential backoff for handling transient errors."""

import asyncio
import logging
import re
from typing import Any, AsyncIterator, Callable, TypeVar, TYPE_CHECKING, Optional

from agentlet_core.config.models import RetryConfig
from agentlet_core.logging.context import log_context

if TYPE_CHECKING:
    from agentlet_core.runtime.context import ExecutionContext

# Type variable for generic retry function return type
T = TypeVar("T")


class RetryHandler:
    """
    Handles retry logic with exponential backoff for transient errors.

    Specifically designed to handle LiteLLM RateLimitError exceptions
    and other configurable error types with adaptive wait times.
    """

    def __init__(
        self,
        config: RetryConfig,
        logger: logging.Logger,
        context: Optional["ExecutionContext"] = None,
    ):
        """
        Initialize retry handler.

        Args:
            config: Retry configuration with max_retries, intervals, etc.
            logger: Logger instance for retry attempt logging
            context: Optional execution context for tracking retry attempts
        """
        self.config = config
        self.logger = logger
        self.context = context
        self._last_api_suggested_wait: Optional[float] = (
            None  # Track API-suggested wait times
        )

    def _should_retry(self, error: Exception) -> bool:
        """
        Determine if an error should trigger a retry.

        Args:
            error: Exception that occurred

        Returns:
            True if error type is in retry_on_errors list
        """
        error_type = type(error).__name__

        # Check if the error type directly matches
        if error_type in self.config.retry_on_errors:
            return True

        # Check for nested exceptions (e.g., Strands EventLoopException wrapping LiteLLM errors)
        # Look for the actual error in the exception chain
        current_error = error
        while current_error:
            # Check the error message for specific error types
            error_msg = str(current_error)
            for retry_error_type in self.config.retry_on_errors:
                if retry_error_type in error_msg:
                    return True

            # Check if this is a wrapped exception with __cause__ or __context__
            if hasattr(current_error, "__cause__") and current_error.__cause__:
                cause = current_error.__cause__
                if isinstance(cause, Exception):
                    current_error = cause
            elif hasattr(current_error, "__context__") and current_error.__context__:
                context = current_error.__context__
                if isinstance(context, Exception):
                    current_error = context
            else:
                break

        return False

    def _extract_api_suggested_wait_time(self, error: Exception) -> Optional[float]:
        """
        Extract API-suggested wait time from error message.

        Args:
            error: Exception that may contain wait time suggestion

        Returns:
            Wait time in seconds if found, None otherwise
        """
        error_msg = str(error)

        # Look for patterns like "Please retry after 60 seconds" or "wait 51 seconds"
        patterns = [
            r"retry after (\d+) seconds",
            r"wait (\d+) seconds",
            r"Please wait (\d+) seconds",
            r"retry in (\d+) seconds",
        ]

        for pattern in patterns:
            match = re.search(pattern, error_msg, re.IGNORECASE)
            if match:
                return float(match.group(1))

        return None

    def _calculate_wait_time(
        self, attempt: int, api_suggested_wait: Optional[float] = None
    ) -> float:
        """
        Calculate wait time for retry attempt using adaptive exponential backoff.

        Args:
            attempt: Current attempt number (0-based)
            api_suggested_wait: API-suggested wait time in seconds

        Returns:
            Wait time in seconds, considering API suggestions and progressive backoff
        """
        # Start with exponential backoff
        exponential_wait = self.config.initial_retry_interval * (
            self.config.backoff_factor**attempt
        )

        # If API suggests a wait time, use it as the minimum
        if api_suggested_wait is not None:
            # Progressive backoff: if API keeps suggesting the same wait time,
            # it likely indicates a rolling window rate limit, so we increase the wait
            if (
                self._last_api_suggested_wait is not None
                and abs(api_suggested_wait - self._last_api_suggested_wait) < 5
            ):  # Within 5 seconds
                # Apply progressive multiplier for repeated suggestions
                progressive_wait = api_suggested_wait * (1.5**attempt)
                self.logger.info(
                    f"API repeatedly suggests {api_suggested_wait}s wait, "
                    f"applying progressive backoff: {progressive_wait:.1f}s"
                )
                wait_time = max(exponential_wait, progressive_wait)
            else:
                # Use API suggestion with small buffer, but respect exponential backoff minimum
                api_with_buffer = api_suggested_wait + 5
                wait_time = max(exponential_wait, api_with_buffer)

                if wait_time == api_with_buffer:
                    self.logger.info(
                        f"Using API-suggested wait time: {api_suggested_wait}s + 5s buffer = {wait_time:.1f}s"
                    )
                else:
                    self.logger.info(
                        f"Using exponential backoff: {exponential_wait:.1f}s (API suggested {api_suggested_wait}s + 5s = {api_with_buffer:.1f}s)"
                    )

            self._last_api_suggested_wait = api_suggested_wait
        else:
            wait_time = exponential_wait

        # Cap at maximum retry interval
        return min(wait_time, self.config.max_retry_interval)

    async def retry_async_generator(
        self, func: Callable[..., AsyncIterator[T]], *args: Any, **kwargs: Any
    ) -> AsyncIterator[T]:
        """
        Retry an async generator function with exponential backoff.

        This is specifically designed for agent.stream_async() which yields
        streaming events. On retry, it restarts the entire stream.

        Args:
            func: Async generator function to retry
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Yields:
            Items from the async generator

        Raises:
            Last exception if all retries are exhausted
        """
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            try:
                # Use log context to track retry attempts
                with log_context(retry_attempt=attempt + 1):
                    if attempt > 0:
                        # Extract API-suggested wait time from the last exception
                        api_suggested_wait = None
                        if last_exception:
                            api_suggested_wait = self._extract_api_suggested_wait_time(
                                last_exception
                            )

                        wait_time = self._calculate_wait_time(
                            attempt - 1, api_suggested_wait
                        )

                        self.logger.warning(
                            f"Retry attempt {attempt}/{self.config.max_retries} "
                            f"after {wait_time:.1f}s wait due to: {last_exception}"
                        )

                        # Record retry attempt in context if available
                        if self.context:
                            self.context.record_retry_attempt()

                        await asyncio.sleep(wait_time)

                    # Execute the async generator function
                    async for item in func(*args, **kwargs):
                        yield item

                    # If we get here, the function completed successfully
                    if attempt > 0:
                        self.logger.info(
                            f"Retry attempt {attempt} succeeded after {attempt} failures"
                        )
                    return

            except Exception as e:
                last_exception = e

                # Info logging for error analysis
                self.logger.info(
                    f"Caught exception in async generator: {type(e).__name__}: {e}"
                )

                # Check if we should retry this error
                should_retry = self._should_retry(e)
                self.logger.info(
                    f"Should retry {type(e).__name__}? {should_retry} "
                    f"(retry_on_errors: {self.config.retry_on_errors})"
                )

                if not should_retry:
                    self.logger.error(
                        f"Non-retryable error occurred: {type(e).__name__}: {e}"
                    )
                    raise e

                # Check if we've exhausted retries
                if attempt >= self.config.max_retries:
                    self.logger.error(
                        f"All {self.config.max_retries} retry attempts exhausted. "
                        f"Final error: {type(e).__name__}: {e}"
                    )
                    raise e

                # Log the error and continue to next retry
                self.logger.warning(
                    f"Retryable error on attempt {attempt + 1}: {type(e).__name__}: {e}"
                )

        # This should never be reached, but just in case
        if last_exception:
            raise last_exception

        # Return a default value to satisfy type checker (should never reach here)
        raise RuntimeError("Retry logic failed without raising an exception")

    async def retry_async(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        Retry a regular async function with exponential backoff.

        Args:
            func: Async function to retry
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from the function

        Raises:
            Last exception if all retries are exhausted
        """
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            try:
                # Use log context to track retry attempts
                with log_context(retry_attempt=attempt + 1):
                    if attempt > 0:
                        # Extract API-suggested wait time from the last exception
                        api_suggested_wait = None
                        if last_exception:
                            api_suggested_wait = self._extract_api_suggested_wait_time(
                                last_exception
                            )

                        wait_time = self._calculate_wait_time(
                            attempt - 1, api_suggested_wait
                        )

                        self.logger.warning(
                            f"Retry attempt {attempt}/{self.config.max_retries} "
                            f"after {wait_time:.1f}s wait due to: {last_exception}"
                        )

                        # Record retry attempt in context if available
                        if self.context:
                            self.context.record_retry_attempt()

                        await asyncio.sleep(wait_time)

                    # Execute the function
                    result: T
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)

                    # If we get here, the function completed successfully
                    if attempt > 0:
                        self.logger.info(
                            f"Retry attempt {attempt} succeeded after {attempt} failures"
                        )
                    return result

            except Exception as e:
                last_exception = e

                # Info logging for error analysis
                self.logger.info(
                    f"Caught exception in async function: {type(e).__name__}: {e}"
                )

                # Check if we should retry this error
                should_retry = self._should_retry(e)
                self.logger.info(
                    f"Should retry {type(e).__name__}? {should_retry} "
                    f"(retry_on_errors: {self.config.retry_on_errors})"
                )

                if not should_retry:
                    self.logger.error(
                        f"Non-retryable error occurred: {type(e).__name__}: {e}"
                    )
                    raise e

                # Check if we've exhausted retries
                if attempt >= self.config.max_retries:
                    self.logger.error(
                        f"All {self.config.max_retries} retry attempts exhausted. "
                        f"Final error: {type(e).__name__}: {e}"
                    )
                    raise e

                # Log the error and continue to next retry
                self.logger.warning(
                    f"Retryable error on attempt {attempt + 1}: {type(e).__name__}: {e}"
                )

        # This should never be reached, but just in case
        if last_exception:
            raise last_exception

        # Return a default value to satisfy type checker (should never reach here)
        raise RuntimeError("Retry logic failed without raising an exception")
