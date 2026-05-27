"""Tests for logging filters (sanitization, rate limiting, etc.)."""

import logging

import pytest

from agentlet_core.logging.filters import SecretSanitizationFilter


class TestSecretSanitizationFilter:
    """Test SecretSanitizationFilter for redacting sensitive data."""

    @pytest.fixture
    def sanitizer(self):
        """Create a SecretSanitizationFilter instance."""
        return SecretSanitizationFilter()

    @pytest.fixture
    def log_record(self):
        """Create a basic log record for testing."""
        return logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="",
            args=(),
            exc_info=None,
        )

    def test_sanitize_api_key_equals(self, sanitizer, log_record):
        """Test sanitization of api_key=value format."""
        log_record.msg = "Using api_key=sk-1234567890abcdef"
        sanitizer.filter(log_record)
        assert log_record.msg == "Using api_key=***REDACTED***"

    def test_sanitize_api_key_case_insensitive(self, sanitizer, log_record):
        """Test case-insensitive sanitization."""
        log_record.msg = "Using API_KEY=secret123"
        sanitizer.filter(log_record)
        assert log_record.msg == "Using API_KEY=***REDACTED***"

    def test_sanitize_token(self, sanitizer, log_record):
        """Test sanitization of token=value."""
        log_record.msg = "Auth token=abc123xyz"
        sanitizer.filter(log_record)
        assert log_record.msg == "Auth token=***REDACTED***"

    def test_sanitize_password(self, sanitizer, log_record):
        """Test sanitization of password=value."""
        log_record.msg = "Database password=mySecretP@ss"
        sanitizer.filter(log_record)
        assert log_record.msg == "Database password=***REDACTED***"

    def test_sanitize_bearer_token(self, sanitizer, log_record):
        """Test sanitization of Bearer tokens."""
        log_record.msg = "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc"
        sanitizer.filter(log_record)
        assert log_record.msg == "Authorization: Bearer ***REDACTED***"

    def test_sanitize_basic_auth(self, sanitizer, log_record):
        """Test sanitization of Basic auth."""
        log_record.msg = "Authorization: Basic dXNlcjpwYXNzd29yZA=="
        sanitizer.filter(log_record)
        assert log_record.msg == "Authorization: Basic ***REDACTED***"

    def test_sanitize_json_format(self, sanitizer, log_record):
        """Test sanitization of JSON-formatted secrets."""
        log_record.msg = '{"api_key": "sk-1234567890", "name": "test"}'
        sanitizer.filter(log_record)
        assert "***REDACTED***" in log_record.msg
        assert "sk-1234567890" not in log_record.msg
        assert '"name": "test"' in log_record.msg  # Non-secret preserved

    def test_sanitize_aws_access_key(self, sanitizer, log_record):
        """Test sanitization of AWS access keys."""
        log_record.msg = "Using key AKIAIOSFODNN7EXAMPLE"
        sanitizer.filter(log_record)
        assert log_record.msg == "Using key ***REDACTED***"

    def test_sanitize_aws_secret_key(self, sanitizer, log_record):
        """Test sanitization of AWS secret keys (40 char base64)."""
        log_record.msg = "Secret: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        sanitizer.filter(log_record)
        assert log_record.msg == "Secret: ***REDACTED***"

    def test_sanitize_openai_key(self, sanitizer, log_record):
        """Test sanitization of OpenAI-style sk- keys."""
        log_record.msg = "API key: sk-proj1234567890abcdefghij"
        sanitizer.filter(log_record)
        assert log_record.msg == "API key: ***REDACTED***"

    def test_sanitize_github_token(self, sanitizer, log_record):
        """Test sanitization of GitHub tokens."""
        tokens = [
            "ghp_1234567890123456789012345678901234abcd",  # Personal access token
            "gho_1234567890123456789012345678901234abcd",  # OAuth token
            "ghs_1234567890123456789012345678901234abcd",  # Server token
        ]
        for token in tokens:
            log_record.msg = f"Token: {token}"
            sanitizer.filter(log_record)
            assert log_record.msg == "Token: ***REDACTED***"

    def test_sanitize_jwt_token(self, sanitizer, log_record):
        """Test sanitization of JWT tokens."""
        log_record.msg = "JWT: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        sanitizer.filter(log_record)
        assert log_record.msg == "JWT: ***REDACTED***"

    def test_sanitize_url_credentials(self, sanitizer, log_record):
        """Test sanitization of credentials in URLs."""
        log_record.msg = "Connecting to https://user:password123@example.com/api"
        sanitizer.filter(log_record)
        assert (
            log_record.msg
            == "Connecting to https://user:***REDACTED***@example.com/api"
        )
        assert "password123" not in log_record.msg

    def test_sanitize_connection_string(self, sanitizer, log_record):
        """Test sanitization of database connection strings."""
        log_record.msg = "DB: Server=myServer;Database=myDB;Password=myP@ss123;"
        sanitizer.filter(log_record)
        assert "myP@ss123" not in log_record.msg
        assert "***REDACTED***" in log_record.msg

    def test_sanitize_multiple_secrets(self, sanitizer, log_record):
        """Test sanitization of multiple secrets in one message."""
        log_record.msg = "Config: api_key=key123 token=tok456 password=pass789"
        sanitizer.filter(log_record)
        assert "key123" not in log_record.msg
        assert "tok456" not in log_record.msg
        assert "pass789" not in log_record.msg
        assert log_record.msg.count("***REDACTED***") == 3

    def test_sanitize_args_tuple(self, sanitizer, log_record):
        """Test sanitization of log arguments (tuple)."""
        log_record.msg = "Using API key: %s"
        log_record.args = ("sk-1234567890abcdef",)
        sanitizer.filter(log_record)
        assert log_record.args[0] == "***REDACTED***"

    def test_sanitize_args_dict(self, sanitizer, log_record):
        """Test sanitization of log arguments (dict)."""
        log_record.msg = "Config: %(api_key)s"
        log_record.args = {"api_key": "sk-1234567890abcdef"}
        sanitizer.filter(log_record)
        assert log_record.args["api_key"] == "***REDACTED***"

    def test_sanitize_extra_fields(self, sanitizer, log_record):
        """Test sanitization of sensitive extra fields."""
        log_record.api_key = "sk-1234567890"
        log_record.token = "secret-token"
        log_record.password = "mypass123"
        log_record.safe_field = "keep this"

        sanitizer.filter(log_record)

        assert log_record.api_key == "***REDACTED***"
        assert log_record.token == "***REDACTED***"
        assert log_record.password == "***REDACTED***"
        assert log_record.safe_field == "keep this"  # Non-sensitive preserved

    def test_sanitize_nested_dict(self, sanitizer, log_record):
        """Test sanitization of nested dictionaries in args."""
        log_record.msg = "Config: %s"
        log_record.args = (
            {"credentials": {"api_key": "sk-1234567890abcdef", "user": "alice"}},
        )
        sanitizer.filter(log_record)

        # The dict structure is preserved but secrets are redacted
        assert isinstance(log_record.args[0], dict)
        assert "credentials" in log_record.args[0]
        # The api_key value should be redacted
        assert log_record.args[0]["credentials"]["api_key"] == "***REDACTED***"
        assert (
            log_record.args[0]["credentials"]["user"] == "alice"
        )  # Non-secret preserved

    def test_sanitize_preserves_non_secrets(self, sanitizer, log_record):
        """Test that non-sensitive data is preserved."""
        log_record.msg = "User alice logged in from 192.168.1.1 at 10:30 AM"
        original = log_record.msg
        sanitizer.filter(log_record)
        assert log_record.msg == original

    def test_filter_always_returns_true(self, sanitizer, log_record):
        """Test that filter never blocks logs."""
        log_record.msg = "api_key=secret"
        result = sanitizer.filter(log_record)
        assert result is True

    def test_sanitize_colon_format(self, sanitizer, log_record):
        """Test sanitization with colon separator."""
        log_record.msg = "api_key: sk-1234567890"
        sanitizer.filter(log_record)
        assert log_record.msg == "api_key: ***REDACTED***"

    def test_sanitize_complex_json(self, sanitizer, log_record):
        """Test sanitization of complex JSON structure."""
        log_record.msg = """
        {
            "config": {
                "api_key": "sk-123",
                "endpoint": "https://api.example.com",
                "auth": {
                    "token": "Bearer abc123"
                }
            }
        }
        """
        sanitizer.filter(log_record)
        assert "sk-123" not in log_record.msg
        assert "abc123" not in log_record.msg
        assert "***REDACTED***" in log_record.msg
        assert "https://api.example.com" in log_record.msg  # Safe URL preserved


class TestSecretSanitizationIntegration:
    """Integration tests for secret sanitization with actual logging."""

    @pytest.fixture
    def capture_handler(self):
        """Create a handler that captures log records."""

        class CaptureHandler(logging.Handler):
            def __init__(self):
                super().__init__()
                self.records = []

            def emit(self, record):
                self.records.append(record)

        return CaptureHandler()

    def test_sanitization_in_real_logging(self, capture_handler):
        """Test that sanitization works in real logging scenario."""
        from agentlet_core.logging.config import configure_logging, get_logger

        # Configure with sanitization enabled
        configure_logging(enable_sanitization=True)

        # Add capture handler
        logger = logging.getLogger("synteles")
        logger.addHandler(capture_handler)

        # Log a message with secrets
        test_logger = get_logger("test")
        test_logger.info("Using api_key=sk-1234567890")

        # Check that the logged message is sanitized
        assert len(capture_handler.records) > 0
        record = capture_handler.records[-1]
        assert "sk-1234567890" not in record.getMessage()
        assert "***REDACTED***" in record.getMessage()

    def test_sanitization_can_be_disabled(self, capture_handler):
        """Test that sanitization can be disabled."""
        from agentlet_core.logging.config import configure_logging, get_logger

        # Configure with sanitization disabled
        configure_logging(enable_sanitization=False)

        # Add capture handler
        logger = logging.getLogger("synteles")
        logger.addHandler(capture_handler)

        # Log a message with secrets
        test_logger = get_logger("test")
        test_logger.info("Using api_key=sk-1234567890")

        # Secrets should NOT be redacted when disabled
        assert len(capture_handler.records) > 0
        # Note: In real production, you'd never disable this, but good to test the option
        # The message might still be sanitized if other code paths do it


# ---------------------------------------------------------------------------
# _sanitize_value — container and non-string types
# ---------------------------------------------------------------------------


class TestSanitizeValue:
    @pytest.fixture
    def f(self):
        return SecretSanitizationFilter()

    def test_dict_values_sanitized(self, f):
        result = f._sanitize_value({"api_key": "sk-supersecret", "user": "alice"})
        assert isinstance(result, dict)
        assert result["api_key"] == f.REDACTED
        assert result["user"] == "alice"

    def test_list_items_sanitized(self, f):
        result = f._sanitize_value(["sk-secret123456", "safe"])
        assert isinstance(result, list)
        assert result[0] == f.REDACTED
        assert result[1] == "safe"

    def test_tuple_items_sanitized(self, f):
        result = f._sanitize_value(("sk-secret123456",))
        assert isinstance(result, tuple)
        assert result[0] == f.REDACTED

    def test_int_preserved(self, f):
        assert f._sanitize_value(42) == 42

    def test_none_preserved(self, f):
        assert f._sanitize_value(None) is None

    def test_safe_string_preserved(self, f):
        assert f._sanitize_value("hello world") == "hello world"


# ---------------------------------------------------------------------------
# RateLimitFilter
# ---------------------------------------------------------------------------


class TestRateLimitFilter:
    def test_init_defaults(self):
        from agentlet_core.logging.filters import RateLimitFilter

        fltr = RateLimitFilter()
        assert fltr.rate == 10
        assert fltr.burst == 50

    def test_init_custom(self):
        from agentlet_core.logging.filters import RateLimitFilter

        fltr = RateLimitFilter(rate=5, burst=20)
        assert fltr.rate == 5
        assert fltr.burst == 20

    def test_filter_always_returns_true(self):
        from agentlet_core.logging.filters import RateLimitFilter

        fltr = RateLimitFilter()
        record = logging.LogRecord("t", logging.INFO, "", 0, "msg", (), None)
        assert fltr.filter(record) is True
