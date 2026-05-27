"""Unit tests for environment utilities."""

import os
import tempfile

import pytest

from agentlet_core.utils.env import get_env, get_env_or_raise, load_env_file


def test_load_env_file_explicit_path(tmp_path):
    """Test loading .env from explicit path."""
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_VAR=test_value\n")

    # Clear any existing value
    if "TEST_VAR" in os.environ:
        del os.environ["TEST_VAR"]

    result = load_env_file(str(env_file))
    assert result is True
    assert os.getenv("TEST_VAR") == "test_value"

    # Cleanup
    del os.environ["TEST_VAR"]


def test_load_env_file_nonexistent():
    """Test loading non-existent .env file."""
    result = load_env_file("/nonexistent/path/.env")
    assert result is False


def test_load_env_file_auto_search(tmp_path, monkeypatch):
    """Test automatic .env search."""
    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    # Create .env in current directory
    env_file = tmp_path / ".env"
    env_file.write_text("AUTO_VAR=auto_value\n")

    # Clear any existing value
    if "AUTO_VAR" in os.environ:
        del os.environ["AUTO_VAR"]

    result = load_env_file()
    assert result is True
    assert os.getenv("AUTO_VAR") == "auto_value"

    # Cleanup
    del os.environ["AUTO_VAR"]


def test_get_env_with_default():
    """Test get_env with default value."""
    # Non-existent variable
    assert get_env("NONEXISTENT_VAR", "default") == "default"

    # Existing variable
    os.environ["EXISTING_VAR"] = "existing_value"
    assert get_env("EXISTING_VAR", "default") == "existing_value"
    del os.environ["EXISTING_VAR"]


def test_get_env_or_raise_success():
    """Test get_env_or_raise with existing variable."""
    os.environ["REQUIRED_VAR"] = "required_value"
    assert get_env_or_raise("REQUIRED_VAR") == "required_value"
    del os.environ["REQUIRED_VAR"]


def test_get_env_or_raise_failure():
    """Test get_env_or_raise with missing variable."""
    with pytest.raises(EnvironmentError, match="Required environment variable"):
        get_env_or_raise("MISSING_VAR")


def test_get_env_or_raise_custom_error():
    """Test get_env_or_raise with custom error message."""
    with pytest.raises(EnvironmentError, match="Custom error"):
        get_env_or_raise("MISSING_VAR", error_msg="Custom error")


def test_load_env_no_override():
    """Test that load_env_file doesn't override existing env vars."""
    # Set environment variable
    os.environ["OVERRIDE_TEST"] = "original_value"

    # Create .env with different value
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("OVERRIDE_TEST=new_value\n")
        env_file_path = f.name

    try:
        load_env_file(env_file_path)
        # Should keep original value
        assert os.getenv("OVERRIDE_TEST") == "original_value"
    finally:
        # Cleanup
        os.unlink(env_file_path)
        del os.environ["OVERRIDE_TEST"]
