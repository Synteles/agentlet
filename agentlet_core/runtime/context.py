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

"""Execution context for agentlet runtime."""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional


class ExecutionContext:
    """
    Manages ephemeral execution context for an agentlet.

    No persistent state - all context exists only during execution.
    """

    def __init__(
        self,
        execution_id: str,
        agentlet_name: str,
        working_dir: Optional[str] = None,
        start_time: Optional[datetime] = None,
    ):
        """
        Initialize execution context.

        Args:
            execution_id: Unique execution identifier
            agentlet_name: Name of the agentlet
            working_dir: Working directory (creates temp if not provided)
            start_time: Execution start timestamp
        """
        self.execution_id = execution_id
        self.agentlet_name = agentlet_name
        self.start_time = start_time or datetime.now()
        self.end_time: Optional[datetime] = None

        # Working directory setup
        if working_dir:
            self.working_dir = Path(working_dir).resolve()
            self._temp_dir = None
        else:
            self._temp_dir = tempfile.mkdtemp(prefix=f"agentlet_{execution_id}_")
            self.working_dir = Path(self._temp_dir)

        # Execution tracking
        self.tool_calls: list[dict] = []
        self.errors: list[str] = []
        self.retry_attempts = 0

        # Token and cost tracking
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_cost = 0.0

    @property
    def execution_time(self) -> float:
        """Get execution time in seconds."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    def start_execution(self) -> None:
        """Mark execution start."""
        self.start_time = datetime.now()

    def end_execution(self) -> None:
        """Mark execution end."""
        self.end_time = datetime.now()

    def record_tool_call(self, tool_name: str, args: dict) -> None:
        """Record a tool invocation."""
        self.tool_calls.append(
            {
                "tool": tool_name,
                "args": args,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def record_error(self, error: str) -> None:
        """Record an error."""
        self.errors.append(error)

    def record_retry_attempt(self) -> None:
        """Record a retry attempt."""
        self.retry_attempts += 1

    def add_tokens(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
    ) -> None:
        """
        Add token usage and cost information.

        Args:
            input_tokens: Number of input (prompt) tokens
            output_tokens: Number of output (completion) tokens
            cost: Cost in USD for this request
        """
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_cost += cost

    def cleanup(self) -> None:
        """Clean up temporary resources."""
        if self._temp_dir and Path(self._temp_dir).exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)

    def get_summary(self) -> dict:
        """Get execution summary."""
        return {
            "execution_id": self.execution_id,
            "agentlet_name": self.agentlet_name,
            "execution_time": f"{self.execution_time:.2f}s",
            "tool_calls": len(self.tool_calls),
            "errors": len(self.errors),
            "retry_attempts": self.retry_attempts,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "total_cost": f"${self.total_cost:.6f}",
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }
