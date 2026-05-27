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

"""Configuration loader for Agentlet Core."""

import json
import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from agentlet_core.logging.config import get_logger
from .models import AgentletConfig

# Module-level logger (synteles.agentlet.config.loader)
logger = get_logger(__name__)


class ConfigLoader:
    """Loads and validates agentlet configurations."""

    SEARCH_PATHS = [
        Path.cwd(),  # Current working directory
        Path.home() / ".synteles" / "agentlets",  # User home directory
        Path.cwd() / ".synteles" / "agentlets",  # Local directory
    ]

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> AgentletConfig:
        """
        Load agentlet configuration from file.

        Args:
            config_path: Explicit path to config file or agentlet name. If None, searches default locations.

        Returns:
            Validated AgentletConfig instance

        Raises:
            FileNotFoundError: If config file not found
            ValidationError: If config validation fails (from Pydantic)
            ValueError: If config format is invalid
        """
        if config_path:
            file_path = Path(config_path)
            if file_path.exists():
                # It's a valid file path
                pass
            elif "/" not in config_path and "\\" not in config_path:
                # It's likely an agentlet name, search for {name}.yaml
                file_path = cls._find_agentlet_by_name(config_path)
            else:
                raise FileNotFoundError(f"Config file not found: {config_path}")
        else:
            file_path = cls._find_config_file()

        return cls._load_from_file(file_path)

    @classmethod
    def _find_config_file(cls) -> Path:
        """Search for config file in default locations."""
        for search_path in cls.SEARCH_PATHS:
            if not search_path.exists():
                continue

            # Look for .yaml or .json files
            for pattern in ["*.yaml", "*.yml", "*.json"]:
                matches = list(search_path.glob(pattern))
                if matches:
                    return matches[0]  # Return first match

        raise FileNotFoundError(
            f"No agentlet config file found in search paths: {cls.SEARCH_PATHS}"
        )

    @classmethod
    def _find_agentlet_by_name(cls, name: str) -> Path:
        """Search for agentlet by name in search paths."""
        for search_path in cls.SEARCH_PATHS:
            if not search_path.exists():
                continue

            # Look for {name}.yaml first, then {name}.yml
            for ext in [".yaml", ".yml"]:
                config_file = search_path / f"{name}{ext}"
                if config_file.exists():
                    return config_file

        raise FileNotFoundError(
            f"Agentlet '{name}' not found in search paths: {cls.SEARCH_PATHS}"
        )

    @classmethod
    def _load_from_file(cls, file_path: Path) -> AgentletConfig:
        """Load and parse config file."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Expand environment variables in content
        content = os.path.expandvars(content)

        # Parse based on file extension
        suffix = file_path.suffix.lower()
        if suffix in [".yaml", ".yml"]:
            data = yaml.safe_load(content)
        elif suffix == ".json":
            data = json.loads(content)
        else:
            raise ValueError(f"Unsupported config format: {suffix}")

        try:
            return AgentletConfig(**data)
        except ValidationError:
            # Re-raise the original ValidationError with full details
            raise

    @classmethod
    def load_from_dict(cls, data: dict) -> AgentletConfig:
        """Load configuration from dictionary."""
        return AgentletConfig(**data)
