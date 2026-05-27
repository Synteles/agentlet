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

"""Logging filters for security and performance.

Provides filters for sanitizing sensitive data, rate limiting, and other
logging enhancements to ensure secure and efficient log production.
"""

import logging
import re
from typing import Any, Pattern


class SecretSanitizationFilter(logging.Filter):
    """
    Logging filter that redacts sensitive information from log messages.

    This filter scans log messages and arguments for common patterns that
    might contain secrets (API keys, tokens, passwords, bearer tokens, etc.)
    and replaces them with a safe placeholder.

    The filter is applied automatically during configure_logging() and protects
    against accidental logging of sensitive data.

    Security Notes:
        - This filter provides defense-in-depth but is not foolproof
        - Developers should still avoid logging sensitive data intentionally
        - Custom secret formats may not be detected
        - Secrets in structured data (dicts, objects) are partially sanitized

    Example:
        Before: "Using api_key=sk-1234567890abcdef"
        After:  "Using api_key=***REDACTED***"

        Before: "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
        After:  "Authorization: Bearer ***REDACTED***"
    """

    # Redaction placeholder
    REDACTED = "***REDACTED***"

    # Compiled regex patterns for common secret formats
    # Each tuple is (pattern, replacement)
    PATTERNS: list[tuple[Pattern[str], str]] = [
        # API keys and secrets in key=value format
        # Matches: api_key=xxx, api-key=xxx, apiKey=xxx, token=xxx, secret=xxx, password=xxx
        (
            re.compile(
                r"((?:api[_-]?key|token|password|secret|auth[_-]?token|access[_-]?key)"
                r"\s*[=:]\s*)([^\s&\"']+)",
                re.IGNORECASE,
            ),
            rf"\1{REDACTED}",
        ),
        # Bearer tokens in Authorization headers
        # Matches: Bearer xxx, bearer xxx
        (
            re.compile(r"(Bearer\s+)([A-Za-z0-9\-._~+/]+=*)", re.IGNORECASE),
            rf"\1{REDACTED}",
        ),
        # Basic auth in Authorization headers
        # Matches: Basic xxx
        (
            re.compile(r"(Basic\s+)([A-Za-z0-9+/]+=*)", re.IGNORECASE),
            rf"\1{REDACTED}",
        ),
        # JSON/YAML format: "key": "value"
        # Matches: "api_key": "xxx", "token": "xxx", etc.
        (
            re.compile(
                r'("(?:api[_-]?key|token|password|secret|auth[_-]?token|access[_-]?key)"\s*:\s*")'
                r'([^"]+)(")',
                re.IGNORECASE,
            ),
            rf"\1{REDACTED}\3",
        ),
        # AWS access keys (starts with AKIA, ASIA, etc.)
        # Matches: AKIAIOSFODNN7EXAMPLE
        (
            re.compile(r"\b(A[SK]IA[A-Z0-9]{16})\b"),
            REDACTED,
        ),
        # AWS secret access keys (40 characters base64-like)
        # Matches: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
        (
            re.compile(r"\b([A-Za-z0-9/+=]{40})\b"),
            REDACTED,
        ),
        # Generic API keys with sk- prefix (like OpenAI)
        # Matches: sk-1234567890abcdef (minimum 10 chars after sk-)
        (
            re.compile(r"\b(sk-[a-zA-Z0-9]{10,})\b"),
            REDACTED,
        ),
        # GitHub tokens (ghp_, gho_, etc.)
        # Matches: ghp_1234567890abcdef
        (
            re.compile(r"\b(gh[ospru]_[A-Za-z0-9]{36,})\b"),
            REDACTED,
        ),
        # JWT tokens (three base64 segments separated by dots)
        (
            re.compile(r"\b(eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b"),
            REDACTED,
        ),
        # URL-encoded credentials
        # Matches: https://user:pass@host, https://token@host
        (
            re.compile(r"(https?://[^:]+:)([^@]+)(@)"),
            rf"\1{REDACTED}\3",
        ),
        # Connection strings with passwords
        # Matches: password=xxx; pwd=xxx;
        (
            re.compile(r"((?:password|pwd)\s*=\s*)([^;\s\"']+)", re.IGNORECASE),
            rf"\1{REDACTED}",
        ),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Sanitize the log record message and arguments.

        This method modifies the log record in-place, replacing sensitive
        patterns with the redaction placeholder.

        Args:
            record: Log record to sanitize

        Returns:
            Always True (never filters out logs, only sanitizes them)
        """
        # Sanitize the message string
        if isinstance(record.msg, str):
            record.msg = self._sanitize_string(record.msg)

        # Sanitize message arguments (for logs like logger.info("Key: %s", api_key))
        if record.args:
            if isinstance(record.args, dict):
                # Named arguments: logger.info("%(key)s", {"key": value})
                record.args = {
                    k: self._sanitize_value(v) for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                # Positional arguments: logger.info("%s %s", arg1, arg2)
                record.args = tuple(self._sanitize_value(arg) for arg in record.args)

        # Sanitize extra fields (context data passed via extra={...})
        # Check common sensitive field names
        sensitive_fields = {
            "api_key",
            "apiKey",
            "api-key",
            "token",
            "password",
            "secret",
            "auth_token",
            "authToken",
            "access_key",
            "accessKey",
            "private_key",
            "privateKey",
        }

        for field in sensitive_fields:
            if hasattr(record, field):
                setattr(record, field, self.REDACTED)

        return True

    def _sanitize_string(self, text: str) -> str:
        """
        Apply all sanitization patterns to a string.

        Args:
            text: String to sanitize

        Returns:
            Sanitized string with secrets redacted
        """
        for pattern, replacement in self.PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    def _sanitize_value(self, value: Any) -> Any:
        """
        Sanitize a single value (recursively handles containers).

        Args:
            value: Value to sanitize (can be string, dict, list, or other)

        Returns:
            Sanitized value
        """
        if isinstance(value, str):
            # Check if the entire string looks like a secret
            sanitized = self._sanitize_string(value)
            if sanitized != value:
                return sanitized
            # Also check if string matches standalone secret patterns
            for pattern, _ in self.PATTERNS:
                if pattern.search(value):
                    return self.REDACTED
            return value
        elif isinstance(value, dict):
            return {k: self._sanitize_value(v) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            container_type = type(value)
            return container_type(self._sanitize_value(item) for item in value)
        else:
            # For non-string types, preserve as-is
            return value


class RateLimitFilter(logging.Filter):
    """
    Logging filter that rate-limits repeated log messages.

    This filter tracks message frequency and suppresses messages that
    occur too frequently, helping to prevent log storms and reduce costs
    in production.

    Note: This is a placeholder implementation for future enhancement.
    Currently not used by default.

    Args:
        rate: Maximum messages per second (default: 10)
        burst: Maximum burst size (default: 50)

    Example:
        >>> from agentlet_core.logging.filters import RateLimitFilter
        >>> rate_limiter = RateLimitFilter(rate=10, burst=50)
        >>> handler.addFilter(rate_limiter)
    """

    def __init__(self, rate: int = 10, burst: int = 50):
        """
        Initialize rate limit filter.

        Args:
            rate: Maximum messages per second
            burst: Maximum burst size
        """
        super().__init__()
        self.rate = rate
        self.burst = burst
        # TODO: Implement token bucket algorithm for rate limiting

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Check if message should be allowed through rate limiter.

        Args:
            record: Log record to check

        Returns:
            True if message should be logged, False to suppress
        """
        # Placeholder: always allow for now
        # Future: implement token bucket or sliding window rate limiting
        return True
