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

"""Environment variable utilities."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def load_env_file(env_file_path: Optional[str] = None) -> bool:
    """
    Load environment variables from .env file.

    Args:
        env_file_path: Path to .env file. If None, searches in:
            1. Current directory (.env)
            2. Synteles home directory (~/synteles/.env)

    Returns:
        True if .env file was found and loaded, False otherwise
    """
    if env_file_path:
        # Explicit path provided - validate and resolve
        try:
            path = Path(env_file_path).resolve(strict=False)
            # Ensure the resolved path doesn't escape intended directories
            if path.exists() and path.is_file():
                load_dotenv(path)
                return True
        except (OSError, ValueError):
            # Invalid path or path traversal attempt
            pass
        return False

    # Search default locations
    search_paths = [
        Path.cwd() / ".env",  # Current directory
        Path.home().resolve() / "synteles" / ".env",  # Synteles home
    ]

    for path in search_paths:
        try:
            if path.exists() and path.is_file():
                load_dotenv(path, override=False)  # Don't override existing env vars
                return True
        except (OSError, ValueError):
            # Skip invalid paths
            continue

    return False


def get_env_or_raise(key: str, error_msg: Optional[str] = None) -> str:
    """
    Get environment variable or raise error.

    Args:
        key: Environment variable name
        error_msg: Custom error message (optional)

    Returns:
        Environment variable value

    Raises:
        EnvironmentError: If environment variable not found
    """
    value = os.getenv(key)
    if value is None:
        msg = error_msg or f"Required environment variable not found: {key}"
        raise EnvironmentError(msg)
    return value


def get_env(key: str, default: str = "") -> str:
    """
    Get environment variable with default.

    Args:
        key: Environment variable name
        default: Default value if not found

    Returns:
        Environment variable value or default
    """
    return os.getenv(key, default)
