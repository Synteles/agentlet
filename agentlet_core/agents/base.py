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

"""Base Agentlet implementation using Agent Framework."""

import asyncio
import os
import time
from datetime import datetime
from typing import AsyncIterator, Optional, Any
from uuid import UUID, uuid4

import litellm
from strands import Agent, tool
from strands.agent.agent import null_callback_handler
from strands.models.litellm import LiteLLMModel
from strands.multiagent import Swarm

from agentlet_core.agents.image_utils import build_multimodal_content
from agentlet_core.config.models import AgentletConfig, SubAgentletConfig
from agentlet_core.runtime.context import ExecutionContext
from agentlet_core.runtime.retry import RetryHandler
from agentlet_core.tools.mcp_manager import MCPToolsManager
from agentlet_core.logging.config import get_logger
from agentlet_core.logging.handlers import RichLoggerAdapter
from agentlet_core.tools.tools_manager import DefaultToolsManager


def _build_sub_agentlet_tool(
    sub_agent: Agent,
    sub_cfg: SubAgentletConfig,
    model_id: str,
    stats_store: dict[str, dict],
    logger: RichLoggerAdapter,
) -> Any:
    """Build a Strands ``@tool``-decorated function that wraps a sub-agentlet.

    The returned tool captures per-invocation statistics (execution time, token
    usage, and cost) into ``stats_store`` keyed by the sub-agentlet's name.  On
    error the exception is caught, logged, and an error string is returned to
    the orchestrator LLM so it can reason about the failure rather than crashing.

    Args:
        sub_agent: The bare Strands ``Agent`` instance for the sub-agentlet.
        sub_cfg: Configuration for the sub-agentlet (name, description, …).
        model_id: LiteLLM model identifier (e.g. ``"bedrock/claude-sonnet-4-5"``)
            used to calculate cost via ``litellm.cost_per_token``.
        stats_store: Mutable dict on ``BaseAgentlet`` that receives per-call
            statistics once the tool returns.
        logger: Logger adapter used to emit structured error messages.

    Returns:
        A Strands-compatible tool callable wrapping the sub-agentlet.
    """
    name = sub_cfg.name
    description = sub_cfg.description

    @tool(name=name, description=description)
    def sub_agentlet_tool(query: str) -> str:
        """Invoke the sub-agentlet with the given query and return its response."""
        start = time.monotonic()
        try:
            result = sub_agent(query)
            elapsed = time.monotonic() - start

            # Extract token usage from EventLoopMetrics.accumulated_usage
            usage = result.metrics.accumulated_usage  # dict: inputTokens / outputTokens
            input_tokens = usage.get("inputTokens", 0)
            output_tokens = usage.get("outputTokens", 0)

            # Compute cost using LiteLLM's cost table (same approach as _calculate_cost)
            try:
                input_cost, output_cost = litellm.cost_per_token(
                    model=model_id,
                    prompt_tokens=input_tokens,
                    completion_tokens=output_tokens,
                )
                total_cost = input_cost + output_cost
            except Exception:
                total_cost = 0.0

            stats_store[name] = {
                "execution_time": elapsed,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_cost": total_cost,
            }
            return str(result)

        except Exception as e:
            elapsed = time.monotonic() - start
            stats_store[name] = {"execution_time": elapsed, "error": str(e)}
            logger.error(f"Sub-agentlet '{name}' failed: {e}")
            return f"Error: sub-agentlet '{name}' failed — {e}"

    return sub_agentlet_tool


def _expand_participant_name(base_name: str, count: int, index: int) -> str:
    """Return the expanded instance name for a swarm participant.

    When ``count == 1`` the base name is returned unchanged.
    When ``count > 1`` a ``_N`` suffix is appended (1-based index).

    Args:
        base_name: The participant's base name as declared in config.
        count: Total number of instances for this participant type.
        index: 1-based instance index.

    Returns:
        Expanded name string, e.g. ``"researcher"`` or ``"researcher_2"``.
    """
    if count == 1:
        return base_name
    return f"{base_name}_{index}"


class BaseAgentlet:
    """
    Base class for Agentlet agents.

    Implements the core lifecycle: Spawn -> Execute -> Terminate
    """

    def __init__(
        self,
        config: AgentletConfig,
        execution_id: Optional[str] = None,
        logger: Optional[RichLoggerAdapter] = None,
    ):
        """
        Initialize the agentlet.

        Args:
            config: Agentlet configuration
            execution_id: Unique execution identifier (generated if not provided)
            logger: Logger instance (created if not provided)
        """
        self.config = config
        self.execution_id = execution_id or self._resolve_execution_id()
        # Create logger if not provided (logging should already be configured)
        if logger is None:
            base_logger = get_logger(__name__)
            self.logger = RichLoggerAdapter(base_logger)
        else:
            self.logger = logger
        self.context: Optional[ExecutionContext] = None
        self._agent: Optional[Agent] = None
        self._mcp_manager: Optional[MCPToolsManager] = None
        self._tool_use_names: dict[str, str] = {}  # Map tool use IDs to tool names
        self._recorded_tool_calls: set[str] = (
            set()
        )  # Track recorded tool call IDs to avoid duplicates

        # Sub-agentlet state (populated in spawn())
        self._sub_mcp_managers: list[MCPToolsManager] = []
        self._sub_agentlet_stats: dict[str, dict] = {}

        # Swarm state (populated in spawn() when config.swarm is set)
        self._swarm: Optional[Any] = None  # strands.multiagent.Swarm instance
        self._swarm_node_times: dict[str, float] = {}  # per-node wall-clock times
        self._current_swarm_node: Optional[str] = (
            None  # active node for token attribution
        )
        self._swarm_node_tokens: dict[str, dict] = {}  # per-node token usage

        # Initialize retry handler
        self._retry_handler = RetryHandler(
            config=self.config.model.retry,
            logger=self.logger.logger,  # Use the underlying logger for retry logging
            context=None,  # Will be set when context is available
        )

    @staticmethod
    def _resolve_execution_id() -> str:
        """
        Resolve execution ID from SYNTELES_EXEC_ID env var or generate a new uuid4.

        If SYNTELES_EXEC_ID is set and contains a valid UUID4, it is used as-is.
        Otherwise a warning is logged and a new uuid4 is generated.
        """
        logger = get_logger(__name__)
        env_value = os.environ.get("SYNTELES_EXEC_ID")
        if env_value:
            try:
                parsed = UUID(env_value)
                if parsed.version == 4:
                    return env_value
                logger.warning(
                    "SYNTELES_EXEC_ID '%s' is not a UUID4 (version=%d); generating a new execution ID",
                    env_value,
                    parsed.version,
                )
            except ValueError:
                logger.warning(
                    "SYNTELES_EXEC_ID '%s' is not a valid UUID; generating a new execution ID",
                    env_value,
                )
        return str(uuid4())

    def _get_litellm_model_id(self) -> str:
        """
        Construct LiteLLM model ID with provider prefix.

        Returns:
            Model ID in format 'provider/model_id' for LiteLLM
        """
        provider = self.config.model.provider.lower()
        model_id = self.config.model.model_id

        # LiteLLM expects format: provider/model_id
        if not model_id.startswith(f"{provider}/"):
            return f"{provider}/{model_id}"
        return model_id

    def _calculate_cost(
        self, input_tokens: int, output_tokens: int, cache_read_tokens: int
    ) -> float:
        """
        Calculate LiteLLM cost for token usage.

        Args:
            input_tokens: Number of input (prompt) tokens
            output_tokens: Number of output (completion) tokens
            cache_read_tokens: Number of cache read tokens

        Returns:
            Total cost in USD
        """
        try:
            input_cost, output_cost = litellm.cost_per_token(
                model=self._get_litellm_model_id(),
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
                cache_read_input_tokens=cache_read_tokens,
            )
            return input_cost + output_cost
        except Exception as e:
            self.logger.metrics(f"Failed to calculate cost: {e}")
            return 0.0

    def _build_trace_attributes(self) -> dict[str, Any]:
        """
        Build trace attributes from config and execution context.

        These attributes will be attached to all trace spans created by the Agent,
        following OpenTelemetry semantic conventions for GenAI systems.

        Returns:
            Dictionary of trace attributes
        """
        attributes = {
            "gen_ai.system": "synteles-agentlet",
            "execution.id": self.execution_id,
            "agentlet.name": self.config.agentlet.name,
            "agentlet.version": self.config.agentlet.version,
            "model.provider": self.config.model.provider,
            "model.id": self.config.model.model_id,
        }
        # Add custom trace attributes from config
        attributes.update(self.config.observability.otel.trace_attributes)
        return attributes

    def _extract_result_text(self, content: Any) -> str:
        """Extract text from tool result content."""
        if isinstance(content, list) and len(content) > 0:
            first_content = content[0]
            if isinstance(first_content, dict):
                return str(first_content.get("text", str(first_content)))
            return str(first_content)
        return str(content)

    def _display_tool_result(self, tool_result: dict) -> None:
        """
        Display tool result with status and content.

        Args:
            tool_result: Tool result data from event
                Expected format: {
                    'status': 'success' | 'error',
                    'content': [{'text': '...'}],
                    'toolUseId': '...'
                }
        """
        tool_use_id = tool_result.get("toolUseId", "unknown")
        status = tool_result.get("status", "success")
        content = tool_result.get("content", [])
        is_error = status == "error"

        # Look up tool name from stored mapping (from tool call event)
        tool_name = self._tool_use_names.get(str(tool_use_id), "Tool")
        result_text = self._extract_result_text(content)

        # Build and display result
        result_data = {
            "status": status,
            "content": result_text,
            "is_error": is_error,
            "toolUseId": tool_use_id,
        }
        self.logger.tool_result(tool_name, result_data, success=not is_error)

        # Record tool errors in execution context for summary tracking
        if is_error and self.context:
            self.context.record_error(f"Tool '{tool_name}' failed: {result_text}")

    def _handle_token_usage(self, event: dict) -> None:
        """
        Extract and track token usage from agent events.

        Args:
            event: Agent event containing potential token usage metadata
        """
        if "event" not in event or not isinstance(event["event"], dict):
            return

        evt = event["event"]
        if "metadata" not in evt or not evt["metadata"]:
            return

        metadata = evt["metadata"]
        if "usage" not in metadata:
            return

        usage = metadata["usage"]
        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
        cache_read_tokens = usage.get("cacheReadInputTokens", 0)

        # Calculate cost
        cost = self._calculate_cost(input_tokens, output_tokens, cache_read_tokens)

        # Update context with token usage and cost
        if self.context:
            self.context.add_tokens(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
            )

        # Accumulate per-node stats in swarm mode
        if self._swarm and self._current_swarm_node:
            node = self._current_swarm_node
            if node not in self._swarm_node_tokens:
                self._swarm_node_tokens[node] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost": 0.0,
                }
            self._swarm_node_tokens[node]["input_tokens"] += input_tokens
            self._swarm_node_tokens[node]["output_tokens"] += output_tokens
            self._swarm_node_tokens[node]["cost"] += cost

        self.logger.metrics(
            f"Token usage: {input_tokens} in, {output_tokens} out, cost: ${cost:.6f}"
        )

    def _handle_text_event(self, event: dict, text_buffer: list[str]) -> Optional[str]:
        """
        Handle text data events from agent stream by buffering them.

        Args:
            event: Agent event containing text data
            text_buffer: List to accumulate text chunks

        Returns:
            Text chunk if present, None otherwise
        """
        if "data" not in event or not event["data"]:
            return None

        chunk = str(event["data"])
        text_buffer.append(chunk)  # Buffer instead of printing immediately
        return chunk

    def _handle_tool_call_event(self, event: dict) -> None:
        """
        Handle tool call events from agent stream.

        Args:
            event: Agent event containing tool call data
        """
        if not self.config.output.show_tool_calls or "current_tool_use" not in event:
            return

        tool_use = event["current_tool_use"]
        self.logger.tool_call(tool_use)

        # Store tool name for later use in tool result display
        tool_use_id = tool_use.get("toolUseId") or tool_use.get("id")
        tool_name = tool_use.get("name")
        if tool_use_id and tool_name:
            self._tool_use_names[str(tool_use_id)] = str(tool_name)

        # Record tool call in execution context (avoid duplicates)
        if (
            self.context
            and tool_use_id
            and tool_use_id not in self._recorded_tool_calls
        ):
            tool_args = tool_use.get("input", {})
            self.context.record_tool_call(tool_name, tool_args)
            self._recorded_tool_calls.add(tool_use_id)

    def _handle_tool_result_event(self, event: dict) -> None:
        """
        Handle tool result events from agent stream.

        Args:
            event: Agent event containing tool result data
        """
        if not self.config.output.show_tool_calls or "message" not in event:
            return

        msg = event["message"]
        if not isinstance(msg, dict) or msg.get("role") != "user":
            return

        content = msg.get("content")
        if not isinstance(content, list):
            return

        for item in content:
            if not isinstance(item, dict) or "toolResult" not in item:
                continue

            # Display the tool result
            self._display_tool_result(item["toolResult"])

    def _handle_message_event(self, event: dict, text_buffer: list[str]) -> None:
        """
        Handle complete message events - displays buffered text.

        Args:
            event: Agent event containing message data
            text_buffer: Accumulated text chunks for this message
        """
        if "message" not in event:
            return

        msg = event["message"]
        if not isinstance(msg, dict):
            return

        # Only display assistant messages
        if msg.get("role") == "assistant" and text_buffer:
            complete_text = "".join(text_buffer)
            if complete_text.strip() and self.config.output.show_messages:
                self.logger.assistant_message(complete_text)
            text_buffer.clear()

    def _handle_reasoning_event(self, event: dict, reasoning_buffer: list[str]) -> None:
        """
        Handle reasoning events from models that support extended thinking.

        Args:
            event: Agent event containing reasoning data
            reasoning_buffer: List to accumulate reasoning text
        """
        if not self.config.output.show_reasoning:
            return

        # Check for reasoning text in the event
        if event.get("reasoning") and "reasoningText" in event:
            reasoning_text = event["reasoningText"]
            if reasoning_text:
                reasoning_buffer.append(reasoning_text)

        # When reasoning completes, display the full block
        # Note: Strands may send a complete reasoning block in one event
        # or stream it incrementally - we handle both cases
        if reasoning_buffer and (
            event.get("reasoning_complete") or event.get("message")
        ):
            complete_reasoning = "".join(reasoning_buffer)
            if complete_reasoning.strip():
                self.logger.reasoning_block(complete_reasoning)
            reasoning_buffer.clear()

    def _handle_turn_boundary(self, event: dict, turn_counter: dict) -> None:
        """
        Handle turn boundary events in multi-turn conversations.

        Args:
            event: Agent event
            turn_counter: Dict with 'count' key tracking current turn number
        """
        if not self.config.output.show_turn_boundaries:
            return

        if event.get("start_event_loop"):
            turn_counter["count"] += 1
            # Only show turn boundary after turn 1 (don't show for first turn)
            if turn_counter["count"] > 1:
                self.logger.turn_boundary(turn_counter["count"])

    def _handle_swarm_node_event(self, event: dict, node_timer: dict) -> None:
        """Handle multiagent_node_start events from Swarm.stream_async.

        Logs which agent is taking control and tracks per-node wall-clock time
        by recording when each node starts.  The timer for the previous node is
        closed out when a new node starts.

        Args:
            event: Stream event dict. Acted on only when
                ``event.get("type") == "multiagent_node_start"``.
            node_timer: Mutable dict with keys ``current_node``, ``start_time``,
                and ``node_times``.  Updated in-place.
        """
        if not self._swarm:
            return
        if event.get("type") != "multiagent_node_start":
            return

        node_id = event.get("node_id", "unknown")
        now = time.monotonic()

        # Close out previous node's timer
        if (
            node_timer["current_node"] is not None
            and node_timer["start_time"] is not None
        ):
            elapsed = now - node_timer["start_time"]
            node_timer["node_times"][node_timer["current_node"]] = elapsed

        node_timer["current_node"] = node_id
        node_timer["start_time"] = now
        self._current_swarm_node = node_id
        self.logger.info(f"Swarm node '{node_id}' is active")

    def _handle_swarm_handoff_event(self, event: dict) -> None:
        """Handle multiagent_handoff events from Swarm.stream_async.

        Logs the handoff transition in the format ``from → to``.

        Args:
            event: Stream event dict. Acted on only when
                ``event.get("type") == "multiagent_handoff"``.
        """
        if not self._swarm:
            return
        if event.get("type") != "multiagent_handoff":
            return

        from_nodes = ", ".join(event.get("from_node_ids", []))
        to_nodes = ", ".join(event.get("to_node_ids", []))
        self.logger.info(f"Handoff: {from_nodes} → {to_nodes}")

    async def spawn(self, working_dir: Optional[str] = None) -> None:
        """
        Initialize agentlet execution context.

        Args:
            working_dir: Path to working directory
        """
        self.logger.info(
            f"Spawning agentlet '{self.config.agentlet.name}' "
            f"(execution_id={self.execution_id})"
        )
        self.logger.info(
            f"Using model: {self.config.model.provider}/{self.config.model.model_id}"
        )

        # Create execution context
        self.context = ExecutionContext(
            execution_id=self.execution_id,
            agentlet_name=self.config.agentlet.name,
            working_dir=working_dir,
            start_time=datetime.now(),
        )

        # Update retry handler with context
        self._retry_handler.context = self.context

        # --- Swarm mode: build Swarm instead of single Agent ---
        if self.config.swarm:
            if self.config.mcp_tools:
                self.logger.warning(
                    "Top-level mcp_tools are ignored in swarm mode. "
                    "Declare MCP tools per participant under swarm.participants[*].mcp_tools."
                )
            if self.config.tools:
                self.logger.info(
                    "Top-level tools are applied to the entry-point agent only in swarm mode. "
                    "Declare tools per participant under swarm.participants[*].tools for other agents."
                )
            model_params = {
                "max_tokens": self.config.resource_limits.max_tokens,
                **self.config.model.parameters,
                "num_retries": 0,
            }
            default_model = LiteLLMModel(
                model_id=self._get_litellm_model_id(),
                params=model_params,
            )
            nodes = self._build_swarm_nodes(default_model, self._get_litellm_model_id())

            # Resolve entry_point agent
            swarm_cfg = self.config.swarm
            if swarm_cfg.entry_point:
                entry_participant = next(
                    p for p in swarm_cfg.participants if p.name == swarm_cfg.entry_point
                )
                entry_name = _expand_participant_name(
                    swarm_cfg.entry_point, entry_participant.count, 1
                )
                entry_agent = next(n for n in nodes if n.name == entry_name)
            else:
                entry_agent = nodes[0]

            self._swarm = Swarm(
                nodes,
                entry_point=entry_agent,
                max_handoffs=swarm_cfg.max_handoffs,
                max_iterations=swarm_cfg.max_iterations,
                execution_timeout=swarm_cfg.execution_timeout,
                node_timeout=swarm_cfg.node_timeout,
                repetitive_handoff_detection_window=swarm_cfg.repetitive_handoff_detection_window,
                repetitive_handoff_min_unique_agents=swarm_cfg.repetitive_handoff_min_unique_agents,
            )
            # Pre-seed current node so tokens emitted before the first handoff event
            # are attributed to the entry agent rather than dropped.
            self._current_swarm_node = entry_agent.name
            self.logger.success(
                f"Swarm spawned: {len(nodes)} nodes, entry_point='{entry_agent.name}'"
            )
            return  # Skip single-agent path

        # Initialize MCP tools using Manual Context Management
        mcp_tools = []
        if self.config.mcp_tools:
            self._mcp_manager = MCPToolsManager(
                tools_config=self.config.mcp_tools,
                working_dir=str(self.context.working_dir),
                logger=self.logger,
            )
            # Initialize MCP clients
            self._mcp_manager.initialize()

            # Enter MCP client contexts (Manual Context Management)
            self._mcp_manager.enter_contexts()

            # Get actual tools from MCP clients (requires active context)
            mcp_tools = self._mcp_manager.get_tools_sync()

        # Create agent using Strands Agent Framework
        # Build model parameters from config
        model_params = {
            "max_tokens": self.config.resource_limits.max_tokens,
            **self.config.model.parameters,
        }

        # Disable LiteLLM internal retries to use our retry logic
        # Override any user-specified num_retries to ensure our retry logic is used
        model_params["num_retries"] = 0

        model = LiteLLMModel(
            model_id=self._get_litellm_model_id(),
            params=model_params,
        )

        # Use null callback handler to prevent agent framework from printing automatically
        # We handle all display through our RichLogger for consistent formatting
        callback_handler = null_callback_handler

        # Get default tools (bash, file_editor, etc.)
        default_tools = (
            DefaultToolsManager(*self.config.tools).get_tools()
            if self.config.tools
            else []
        )

        # Build sub-agentlet tools (each sub-agentlet becomes a callable tool)
        sub_agentlet_tools = self._build_sub_agentlet_tools(model)

        # Combine all tools: sub-agentlets first so the orchestrator LLM sees them
        # prominently, then orchestrator-level default tools and MCP tools.
        all_tools = sub_agentlet_tools + default_tools + mcp_tools

        # Build trace attributes for OTEL integration
        trace_attributes = self._build_trace_attributes()

        self._agent = Agent(
            model=model,
            name=self.config.agentlet.name,
            system_prompt=self.config.system_prompt,
            callback_handler=callback_handler,
            tools=all_tools,
            trace_attributes=trace_attributes,
        )

        self.logger.success("Agentlet spawned successfully")

    async def execute(
        self, prompt: str, images: Optional[list[str]] = None
    ) -> AsyncIterator[str]:
        """
        Execute the agentlet with given prompt and optional images.

        Displays complete messages per turn instead of character-by-character streaming.
        Supports reasoning blocks and turn boundaries for multi-turn conversations.

        Args:
            prompt: User prompt to process
            images: Optional list of image sources (file paths, HTTP URLs, or
                    base64 data URLs). Supported formats: JPEG, PNG, GIF, WebP.
                    When provided, builds a multimodal content list for vision-capable
                    models.

        Yields:
            Response chunks (text) for programmatic access

        Raises:
            RuntimeError: If agentlet not spawned
        """
        if (self._agent is None and self._swarm is None) or not self.context:
            raise RuntimeError("Agentlet not spawned. Call spawn() first.")

        self.logger.info(f"Executing task: {prompt[:100]}...")
        if images:
            self.logger.info(f"Attaching {len(images)} image(s) to prompt")

        # Build multimodal content when images are provided; plain string otherwise
        agent_input = build_multimodal_content(prompt, images or [])

        try:
            self.context.start_execution()
            self._recorded_tool_calls.clear()

            # Buffers for accumulating content
            text_buffer: list[str] = []  # Accumulate text chunks per message
            reasoning_buffer: list[str] = []  # Accumulate reasoning text
            turn_counter = {"count": 0}  # Track current turn number

            # Determine stream source: Swarm (declarative mode) or single Agent
            stream_fn = (
                self._swarm.stream_async
                if self._swarm is not None
                else self._agent.stream_async  # type: ignore[union-attr]
            )

            # Node timer for swarm mode wall-clock tracking
            node_timer: dict = {
                "current_node": None,
                "start_time": None,
                "node_times": {},
            }

            async for event in self._retry_handler.retry_async_generator(
                stream_fn, agent_input
            ):
                # Swarm-specific event handlers (no-ops in single-agent mode)
                self._handle_swarm_node_event(event, node_timer)
                self._handle_swarm_handoff_event(event)

                # Swarm node stream events wrap the inner agent event under "event".
                # Unwrap so all display/tracking handlers see a uniform event structure.
                inner = (
                    event.get("event", event)
                    if event.get("type") == "multiagent_node_stream"
                    else event
                )

                # Handle turn boundaries (show turn indicators)
                self._handle_turn_boundary(inner, turn_counter)

                # Handle text events (buffer chunks)
                chunk = self._handle_text_event(inner, text_buffer)
                if chunk:
                    yield chunk  # Still yield for programmatic access

                # Handle reasoning events (extended thinking)
                self._handle_reasoning_event(inner, reasoning_buffer)

                # Handle complete message events (display buffered text)
                self._handle_message_event(inner, text_buffer)

                # Handle tool calls and results
                self._handle_tool_call_event(inner)
                self._handle_tool_result_event(inner)

                # Track token usage
                self._handle_token_usage(inner)

            # Close out the final swarm node's timer
            if self._swarm and node_timer["current_node"] and node_timer["start_time"]:
                elapsed = time.monotonic() - node_timer["start_time"]
                node_timer["node_times"][node_timer["current_node"]] = elapsed
            self._swarm_node_times = node_timer["node_times"]

            self.context.end_execution()

            self.logger.success(f"Task completed in {self.context.execution_time:.2f}s")
            self._log_main_agentlet_stats()
            self._log_sub_agentlet_stats()
            self._log_swarm_stats()

        except asyncio.TimeoutError:
            self.logger.error(
                f"Execution timeout after {self.config.resource_limits.max_execution_time}s"
            )
            raise
        except Exception as e:
            self.logger.error(f"Execution failed: {e}")
            self.context.record_error(str(e))
            raise

    async def terminate(self) -> None:
        """Clean up resources and terminate agentlet."""
        self.logger.info("Terminating agentlet...")

        # Cleanup MCP tools - especially important for stdio servers
        # which spawn subprocesses that need explicit termination
        # Using synchronous cleanup to avoid asyncio recursion issues
        if self._mcp_manager:
            self._mcp_manager.cleanup_sync()

        # Cleanup sub-agentlet MCP managers
        for sub_mgr in self._sub_mcp_managers:
            sub_mgr.cleanup_sync()

        # Cleanup working directory if needed
        if self.context:
            self.context.cleanup()

        # Cleanup any remaining aiohttp sessions
        await self._cleanup_aiohttp_sessions()

        self.logger.success("Agentlet terminated")

    async def run(
        self,
        prompt: str,
        working_dir: Optional[str] = None,
        images: Optional[list[str]] = None,
    ) -> str:
        """
        Complete lifecycle: spawn, execute, terminate.

        Args:
            prompt: User prompt
            working_dir: Working directory path
            images: Optional list of image sources (file paths, HTTP URLs, or
                    base64 data URLs) to pass alongside the prompt.

        Returns:
            Complete response text
        """
        async with self:
            await self.spawn(working_dir)

            # Collect all chunks
            response_parts = []
            async for chunk in self.execute(prompt, images=images):
                response_parts.append(chunk)

            return "".join(response_parts)

    def _build_sub_agentlet_tools(self, orchestrator_model: LiteLLMModel) -> list[Any]:
        """Build Strands tool wrappers for all configured sub-agentlets.

        For each :class:`SubAgentletConfig` in ``self.config.sub_agentlets`` this
        method:

        1. Resolves the model — reuses the orchestrator's ``LiteLLMModel`` when no
           model is specified, or builds a new one when the sub-agentlet overrides it.
        2. Initialises any MCP tool servers declared for the sub-agentlet (using the
           same Manual Context Management pattern as the orchestrator).
        3. Loads Strands default tools declared for the sub-agentlet.
        4. Creates a bare Strands ``Agent`` with sub-agentlet-specific OTel trace
           attributes so its spans appear as children of the orchestrator's trace.
        5. Wraps the agent with :func:`_build_sub_agentlet_tool` which captures
           per-invocation statistics and handles errors gracefully.

        All MCP managers created here are stored in ``self._sub_mcp_managers`` and
        cleaned up in :meth:`terminate`.

        Args:
            orchestrator_model: The already-created ``LiteLLMModel`` for the
                orchestrator, reused by sub-agentlets that do not override the model.

        Returns:
            List of Strands-compatible tool callables, one per sub-agentlet.

        Raises:
            Exception: If a sub-agentlet's MCP server fails to initialise. Raises
                immediately rather than silently skipping — a missing tool would cause
                the orchestrator to run with incomplete capabilities.
        """
        sub_agentlet_tools = []

        for sub_cfg in self.config.sub_agentlets:
            self.logger.info(f"Initialising sub-agentlet '{sub_cfg.name}'")

            # --- 1. Resolve model ---
            if sub_cfg.model is None:
                sub_model = orchestrator_model
                sub_model_id = self._get_litellm_model_id()
            else:
                sub_provider = sub_cfg.model.provider.lower()
                sub_model_id_raw = sub_cfg.model.model_id
                sub_model_id = (
                    sub_model_id_raw
                    if sub_model_id_raw.startswith(f"{sub_provider}/")
                    else f"{sub_provider}/{sub_model_id_raw}"
                )
                sub_model_params = {
                    "max_tokens": self.config.resource_limits.max_tokens,
                    **sub_cfg.model.parameters,
                    "num_retries": 0,
                }
                sub_model = LiteLLMModel(
                    model_id=sub_model_id,
                    params=sub_model_params,
                )

            # --- 2. Initialise sub-agentlet MCP tools ---
            sub_mcp_tools: list[Any] = []
            if sub_cfg.mcp_tools:
                sub_mgr = MCPToolsManager(
                    tools_config=sub_cfg.mcp_tools,
                    working_dir=str(self.context.working_dir),  # type: ignore[union-attr]
                    logger=self.logger,
                )
                sub_mgr.initialize()
                sub_mgr.enter_contexts()
                sub_mcp_tools = sub_mgr.get_tools_sync()
                self._sub_mcp_managers.append(sub_mgr)

            # --- 3. Load sub-agentlet default tools ---
            sub_default_tools = (
                DefaultToolsManager(*sub_cfg.tools).get_tools() if sub_cfg.tools else []
            )

            # --- 4. Build OTel trace attributes ---
            # Sub-agent runs in-process so its spans are automatically children of the
            # orchestrator's active span. Custom attributes allow filtering in collectors.
            sub_trace_attributes = {
                **self._build_trace_attributes(),
                "sub_agentlet.name": sub_cfg.name,
                "sub_agentlet.parent_execution_id": self.execution_id,
                "agentlet.name": sub_cfg.name,  # override so spans are clearly labelled
            }

            # --- 5. Build bare Strands Agent ---
            # Use the Strands default callback (None) when any output display option is
            # enabled, so the sub-agentlet prints its own execution inline.  Otherwise
            # suppress all output — the orchestrator's display is sufficient.
            out = sub_cfg.output
            sub_callback = (
                None
                if (out.show_messages or out.show_reasoning or out.show_tool_calls)
                else null_callback_handler
            )

            sub_agent = Agent(
                model=sub_model,
                name=sub_cfg.name,
                system_prompt=sub_cfg.system_prompt,
                callback_handler=sub_callback,
                tools=sub_default_tools + sub_mcp_tools,
                trace_attributes=sub_trace_attributes,
            )

            # --- 6. Wrap with @tool for stats capture and error handling ---
            sub_agentlet_tools.append(
                _build_sub_agentlet_tool(
                    sub_agent=sub_agent,
                    sub_cfg=sub_cfg,
                    model_id=sub_model_id,
                    stats_store=self._sub_agentlet_stats,
                    logger=self.logger,
                )
            )

            self.logger.success(f"Sub-agentlet '{sub_cfg.name}' ready")

        return sub_agentlet_tools

    def _build_swarm_nodes(
        self, default_model: Any, default_model_id: str
    ) -> list[Any]:
        """Build Strands Agent instances for all swarm participants.

        Expands each :class:`SwarmParticipantConfig` into ``count`` Agent
        instances.  Model resolution follows the same pattern as
        :meth:`_build_sub_agentlet_tools`: reuse the default model when no
        override is declared, build a new ``LiteLLMModel`` otherwise.

        Top-level ``config.tools`` are applied to the entry-point agent only,
        enabling the combined mode (e.g. ``tools: [swarm]`` gives the entry
        agent the dynamic swarm tool while other participants are unaffected).

        Top-level ``config.mcp_tools`` are NOT applied in swarm mode — declare
        MCP tools on each participant instead.

        Args:
            default_model: The ``LiteLLMModel`` built from top-level
                ``config.model``; reused by participants without a model override.
            default_model_id: The LiteLLM model ID string for the default model
                (e.g. ``"bedrock/claude-sonnet-4-5"``).

        Returns:
            List of Strands ``Agent`` instances in participant declaration order.
        """
        swarm_cfg = self.config.swarm
        if swarm_cfg is None:
            raise RuntimeError(
                "_build_swarm_nodes() called without swarm configuration"
            )

        # Resolve which participant is the entry point
        entry_base = swarm_cfg.entry_point or swarm_cfg.participants[0].name

        # Load top-level tools once — applied to entry_point agent only
        top_level_tools = (
            DefaultToolsManager(*self.config.tools).get_tools()
            if self.config.tools
            else []
        )

        nodes: list[Any] = []

        for participant in swarm_cfg.participants:
            for i in range(1, participant.count + 1):
                expanded_name = _expand_participant_name(
                    participant.name, participant.count, i
                )
                is_entry_instance = participant.name == entry_base and i == 1

                # --- Resolve model ---
                if participant.model is None:
                    node_model = default_model
                else:
                    sub_provider = participant.model.provider.lower()
                    sub_model_id_raw = participant.model.model_id
                    sub_model_id = (
                        sub_model_id_raw
                        if sub_model_id_raw.startswith(f"{sub_provider}/")
                        else f"{sub_provider}/{sub_model_id_raw}"
                    )
                    node_model = LiteLLMModel(
                        model_id=sub_model_id,
                        params={
                            "max_tokens": self.config.resource_limits.max_tokens,
                            **participant.model.parameters,
                            "num_retries": 0,
                        },
                    )

                # --- Initialise participant MCP tools ---
                mcp_tools: list[Any] = []
                if participant.mcp_tools:
                    sub_mgr = MCPToolsManager(
                        tools_config=participant.mcp_tools,
                        working_dir=str(self.context.working_dir),  # type: ignore[union-attr]
                        logger=self.logger,
                    )
                    sub_mgr.initialize()
                    sub_mgr.enter_contexts()
                    mcp_tools = sub_mgr.get_tools_sync()
                    self._sub_mcp_managers.append(sub_mgr)

                # --- Load participant strands tools ---
                strands_tools = (
                    DefaultToolsManager(*participant.tools).get_tools()
                    if participant.tools
                    else []
                )

                # --- Entry-point gets top-level tools (e.g. swarm tool) ---
                extra_tools = top_level_tools if is_entry_instance else []

                # --- OTel trace attributes ---
                trace_attrs = {
                    **self._build_trace_attributes(),
                    "agentlet.name": expanded_name,
                    "swarm_participant.name": expanded_name,
                    "swarm.parent_execution_id": self.execution_id,
                }

                node = Agent(
                    name=expanded_name,
                    system_prompt=participant.system_prompt,
                    model=node_model,
                    tools=extra_tools + strands_tools + mcp_tools,
                    trace_attributes=trace_attrs,
                    callback_handler=null_callback_handler,
                )
                nodes.append(node)
                self.logger.info(f"Initialised swarm node '{expanded_name}'")

        return nodes

    def _log_main_agentlet_stats(self) -> None:
        """Log main orchestrator agentlet statistics before sub-agentlet stats.

        Displays the token usage and cost for the main orchestrator agentlet only,
        excluding sub-agentlet contributions. This provides visibility into the
        orchestrator's own resource consumption.

        Output format::

            📊 Main agentlet statistics:
            📊     5.2s  |  30,370 in / 1,438 out  |  $0.037560
        """
        if not self.context:
            return

        # At this point, context only contains orchestrator tokens
        # (sub-agentlet tokens are added later in _log_sub_agentlet_stats)
        orchestrator_input = self.context.input_tokens
        orchestrator_output = self.context.output_tokens
        orchestrator_cost = self.context.total_cost

        self.logger.metrics("Main agentlet statistics:")
        self.logger.metrics(
            f"    {self.context.execution_time:.1f}s"
            f"  |  {orchestrator_input:,} in / {orchestrator_output:,} out"
            f"  |  ${orchestrator_cost:.6f}"
        )

    def _log_sub_agentlet_stats(self) -> None:
        """Log per-sub-agentlet execution statistics after a completed run.

        Iterates over ``self._sub_agentlet_stats`` and emits a metrics line for
        each sub-agentlet that was invoked during the execution.  Sub-agentlets
        that were never called are silently skipped.

        Also aggregates sub-agentlet token usage and costs into the main
        execution context for accurate total reporting.

        Note: Square brackets are escaped (\\[name]) for Rich console output,
        which interprets unescaped brackets as markup tags.

        Output format (success)::

            📊 Sub-agentlet statistics:
            📊     [research_agent]  2.3s  |  1,240 in / 380 out  |  $0.000420

        Output format (error)::

            📊 Sub-agentlet statistics:
            📊     [code_reviewer]  1.1s  |  ERROR: <message>
        """
        if not self._sub_agentlet_stats:
            return

        self.logger.metrics("Sub-agentlet statistics:")
        for name, stats in self._sub_agentlet_stats.items():
            elapsed = stats.get("execution_time", 0.0)
            # Debug: log what we're processing
            self.logger.debug_log(
                f"Processing sub-agentlet: name='{name}', stats={stats}"
            )

            if "error" in stats:
                # Escape square brackets for Rich console (it interprets them as markup)
                self.logger.metrics(
                    f"    \\[{name}]  {elapsed:.1f}s  |  ERROR: {stats['error']}"
                )
            else:
                in_tok = stats.get("input_tokens", 0)
                out_tok = stats.get("output_tokens", 0)
                cost = stats.get("total_cost", 0.0)
                # Escape square brackets for Rich console (it interprets them as markup)
                self.logger.metrics(
                    f"    \\[{name}]  {elapsed:.1f}s"
                    f"  |  {in_tok:,} in / {out_tok:,} out"
                    f"  |  ${cost:.6f}"
                )

                # Add sub-agentlet tokens and costs to main execution context
                if self.context:
                    self.context.add_tokens(
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        cost=cost,
                    )

    def _log_swarm_stats(self) -> None:
        """Log per-node wall-clock times for a completed swarm execution.

        Iterates over ``self._swarm_node_times`` (populated during
        :meth:`execute`) and emits one metrics line per node that participated.
        Nodes that never received a handoff are silently skipped.

        Note: Square brackets are escaped (``\\[name]``) for Rich console output
        which interprets unescaped brackets as markup tags.

        Output format::

            📊 Swarm node statistics:
            📊     [researcher_1]  3.2s
            📊     [writer_1]      1.8s
        """
        if not self._swarm_node_times:
            return

        self.logger.metrics("Swarm node statistics:")
        for node_name, elapsed in self._swarm_node_times.items():
            node_tok = self._swarm_node_tokens.get(node_name, {})
            in_tok = node_tok.get("input_tokens", 0)
            out_tok = node_tok.get("output_tokens", 0)
            cost = node_tok.get("cost", 0.0)
            self.logger.metrics(
                f"    \\[{node_name}]  {elapsed:.1f}s"
                f"  |  {in_tok:,} in / {out_tok:,} out"
                f"  |  ${cost:.6f}"
            )

    async def _cleanup_aiohttp_sessions(self) -> None:
        """Clean up any unclosed aiohttp client sessions."""
        try:
            # Cleanup litellm client if available
            if hasattr(litellm, "close"):
                await litellm.close()

            # Brief delay for cleanup to complete
            await asyncio.sleep(0.1)

        except Exception as e:
            self.logger.debug_log(f"Cleanup error: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        """Async context manager exit with guaranteed cleanup."""
        await self.terminate()
        return False
