# Multi-Agent Systems

A complete guide to the **agent-as-tool** multiagency pattern in agentlet-core.

## Overview

Agentlet-core supports orchestrating multiple specialised AI agents within a single execution. An **orchestrator agentlet** declares one or more **sub-agentlets** inline in its YAML configuration. At runtime each sub-agentlet is wrapped as a callable Strands tool — the orchestrator's LLM decides when to delegate work and which sub-agentlet to call.

**Key properties:**

- Sub-agentlets run **in-process** — no subprocess overhead, no IPC
- **Model inheritance** — omit `model` to reuse the orchestrator's model
- **Full tool support** — each sub-agentlet declares its own `tools` and `mcp_tools`
- **Per-sub-agentlet statistics** — execution time, tokens, and cost logged after each call
- **OTel trace nesting** — sub-agent spans are automatically children of the orchestrator's span
- **Isolated lifecycle** — sub-agentlets have no `ExecutionContext`; the orchestrator owns lifecycle tracking

## Quick Start

```yaml
# orchestrator.yaml
agentlet:
  name: research-and-write
  version: "1.0.0"

system_prompt: |
  You are an orchestrator. Use research_agent to gather information,
  then writing_agent to produce polished output.

model:
  provider: anthropic
  model_id: claude-sonnet-4-6

sub_agentlets:
  - name: research_agent
    description: "Finds factual information on any topic and returns a structured summary."
    system_prompt: "You are a research specialist. Find accurate, up-to-date information."
    tools:
      - http_request

  - name: writing_agent
    description: "Transforms research notes into well-structured written content."
    system_prompt: "You are a professional writer. Produce clear, well-structured prose."
    model:
      provider: anthropic
      model_id: claude-haiku-4-5   # cheaper model for this sub-task
```

```bash
agentlet-core --agentlet orchestrator.yaml \
  --prompt "Research vector databases and write a short report"
```

See the full working example at `examples/multi-agent-example.yaml`.

## Configuration Reference

Sub-agentlets are declared under the `sub_agentlets` key on the root `AgentletConfig`.

```yaml
sub_agentlets:
  - name: <string>           # Required — tool name exposed to the orchestrator LLM
    description: <string>    # Required — tool docstring; what the LLM reads to decide when to call it
    system_prompt: <string>  # Required — the sub-agentlet's specialisation instructions
    model:                   # Optional — omit to inherit the orchestrator's model
      provider: <string>
      model_id: <string>
      parameters:
        temperature: <float>
    tools:                   # Optional — Strands default tools (bash, file_editor, http_request, …)
      - <tool_name>
    mcp_tools:               # Optional — MCP protocol tools (stdio, HTTP, SSE)
      - name: <string>
        server: stdio | http | sse
        ...
```

### Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | Yes | — | Tool name. Must be a valid Python identifier. Used as the tool name in the orchestrator's tool list. |
| `description` | Yes | — | Plain-English description. The orchestrator LLM reads this to decide when to call the sub-agentlet. Write clear, specific descriptions. |
| `system_prompt` | Yes | — | Instructions that specialise the sub-agentlet's behaviour. |
| `model` | No | Inherits orchestrator's model | Override with a different provider/model. Useful for cost optimisation (e.g., haiku for generative tasks). |
| `tools` | No | `[]` | Strands built-in tools available to this sub-agentlet. Same values as the top-level `tools` field. |
| `mcp_tools` | No | `[]` | MCP tools available to this sub-agentlet. Same schema as the top-level `mcp_tools` field. |
| `output.show_messages` | No | `false` | Print the sub-agentlet's assistant messages inline during execution. |
| `output.show_reasoning` | No | `false` | Print the sub-agentlet's reasoning/thinking blocks inline. |
| `output.show_tool_calls` | No | `false` | Print the sub-agentlet's tool invocations and results inline. |

## How It Works

### Spawn Phase

When the orchestrator spawns, for each entry in `sub_agentlets`:

1. Resolve the model — use the sub-agentlet's `model` if specified, otherwise share the orchestrator's `LiteLLMModel` instance.
2. Load default Strands tools declared in `tools`.
3. Initialise any `mcp_tools` connections (stored in `_sub_mcp_managers` for cleanup).
4. Create a bare Strands `Agent` with the sub-agentlet's `system_prompt` and tools.
5. Wrap it in a `@tool`-decorated function that captures execution statistics.

The resulting tool objects are prepended to the orchestrator's tool list so the LLM sees them alongside any other tools.

### Execute Phase

When the orchestrator LLM decides to delegate:

1. It calls the sub-agentlet tool with a `query: str` argument.
2. The wrapper invokes the Strands `Agent` synchronously and captures the `AgentResult`.
3. Token usage and cost are extracted from `result.metrics.accumulated_usage`.
4. Statistics are stored and logged after the orchestrator's response completes.
5. The sub-agentlet's text response is returned to the orchestrator LLM as a string.

### Terminate Phase

On termination, all MCP connections belonging to sub-agentlets are closed alongside the orchestrator's own MCP connections.

## Statistics

After each execution, agentlet-core logs per-sub-agentlet statistics:

```
Sub-agentlet stats:
┌─────────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│ Sub-agentlet    │ Exec Time    │ Input Tokens │ Output Tokens│ Cost         │
├─────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ research_agent  │ 4.23s        │ 1,240        │ 387          │ $0.0021      │
│ writing_agent   │ 2.91s        │ 891          │ 612          │ $0.0008      │
└─────────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

Statistics are captured per call — if the orchestrator calls a sub-agentlet multiple times, each call overwrites the previous entry (the last call's stats are reported).

## OpenTelemetry Tracing

Sub-agentlet spans are automatically nested under the orchestrator's trace because all agents run in the same process and share the same OTel context.

Custom trace attributes added to each sub-agentlet span:

| Attribute | Value |
|-----------|-------|
| `sub_agentlet.name` | Sub-agentlet name |
| `sub_agentlet.parent_execution_id` | Orchestrator's execution ID |

This lets you filter traces by sub-agentlet name or correlate sub-agent work back to the parent execution.

## Error Handling

If a sub-agentlet raises an unhandled exception:

1. The exception is caught by the `@tool` wrapper.
2. An error is logged at `ERROR` level with the sub-agentlet name and message.
3. An error string is returned to the orchestrator LLM: `"Error: sub-agentlet '<name>' failed — <message>"`.
4. The orchestrator LLM can then decide how to proceed (retry, fall back, report to user).

This follows the Strands tool error contract — the orchestrator is never hard-crashed by a sub-agentlet failure.

## Model Inheritance vs Override

**Inherit (default):** Omit `model` in the sub-agentlet config. The sub-agentlet shares the orchestrator's `LiteLLMModel` instance — same provider, model, temperature, and parameters.

```yaml
sub_agentlets:
  - name: helper
    description: "..."
    system_prompt: "..."
    # No model — inherits orchestrator's model
```

**Override:** Specify `model` to use a different model. This is useful for cost optimisation (e.g., use a cheaper model for summarisation) or capability tuning (e.g., a coding model for code generation).

```yaml
sub_agentlets:
  - name: code_writer
    description: "Writes code based on specifications."
    system_prompt: "You are an expert programmer."
    model:
      provider: anthropic
      model_id: claude-opus-4-5   # More capable for complex coding
      parameters:
        temperature: 0.1           # Low temperature for deterministic code

  - name: summariser
    description: "Summarises long text into bullet points."
    system_prompt: "You are a concise summariser."
    model:
      provider: anthropic
      model_id: claude-haiku-4-5  # Cheaper for simple text tasks
```

## Writing Effective System Prompts

### Orchestrator

The orchestrator's system prompt should:

- List available sub-agentlets by name and describe when to use each.
- Define the workflow (e.g., always research before writing).
- Instruct the LLM to delegate rather than do the work itself.

```yaml
system_prompt: |
  You are an orchestrator. You have two specialised agents:
  - research_agent: Use to find factual information on any topic.
  - writing_agent: Use to produce well-structured written content from notes.

  Workflow:
  1. Use research_agent to gather information.
  2. Pass the findings to writing_agent.
  3. Return the final written output to the user.

  Always delegate — do not research or write yourself.
```

### Sub-agentlets

Sub-agentlet system prompts should:

- Focus on one task (single responsibility).
- Define the expected input format.
- Define the expected output format (the orchestrator reads this).
- Be concise — the sub-agentlet doesn't need to know about other sub-agentlets.

```yaml
system_prompt: |
  You are a research specialist. Given a topic:
  - Search for accurate, up-to-date information.
  - Extract key facts, statistics, and insights.
  - Return a structured summary: key findings, supporting details, sources.
  Be concise — your output goes to a writer agent, not directly to the user.
```

## Writing Effective Descriptions

The `description` field is the sub-agentlet's **tool docstring** — the orchestrator LLM reads it to decide whether and when to call that sub-agentlet. Write descriptions that:

- Start with a verb ("Searches", "Transforms", "Generates").
- State the input clearly ("given a topic", "from research notes").
- State the output clearly ("returns a structured summary").
- Include guidance on when to use it ("Use for any task requiring…").

**Good:**
```yaml
description: >
  Searches for factual information on a given topic, retrieves relevant
  sources, and returns a concise research summary with key findings.
  Use for any task requiring up-to-date information or fact-checking.
```

**Bad:**
```yaml
description: "Does research"
```

## Sub-agentlet Output

By default sub-agentlets run silently — only the orchestrator's messages are displayed. You can opt in to see a sub-agentlet's internal execution inline:

```yaml
sub_agentlets:
  - name: research_agent
    description: "..."
    system_prompt: "..."
    output:
      show_messages: true      # Print assistant messages as they are generated
      show_reasoning: true     # Print reasoning/thinking blocks (extended thinking models)
      show_tool_calls: true    # Print tool invocations and their results
```

When any of these options is `true`, the sub-agentlet uses the Strands default callback handler, which prints its output inline during the tool call — before the orchestrator continues with its own response. All three options default to `false`.

## Constraints and Limitations

- **No `ExecutionContext`**: Sub-agentlets do not have their own `ExecutionContext`. Tool calls and errors made inside sub-agentlets are not tracked in the orchestrator's `ExecutionContext`.
- **Synchronous execution**: Sub-agentlets are called synchronously within the tool wrapper. Concurrent sub-agentlet execution is not supported.
- **No nested orchestration**: Sub-agentlets cannot themselves declare `sub_agentlets`. Only one level of orchestration is supported.
- **Stats per last call**: If the same sub-agentlet is called multiple times, only the last call's statistics are reported.
- **No per-sub-agentlet timeout**: Resource limits (`max_execution_time`) apply to the orchestrator as a whole, not individual sub-agentlet calls.

## Full Example

See `examples/multi-agent-example.yaml` for a complete, runnable example with:

- An orchestrator with two sub-agentlets
- Model inheritance and model override
- Tool configuration (http_request for research)
- Inline comments explaining each section

```bash
uv run agentlet-core \
  --agentlet examples/multi-agent-example.yaml \
  --prompt "Research the latest trends in vector databases and write a short report"
```

## Next Steps

- **[Configuration Reference](configuration.md)** — Full `sub_agentlets` schema
- **[Core Concepts](../tutorials/introduction.md)** — Multiagency overview
- **[Architecture Overview](../architecture/overview.md)** — How sub-agentlets fit the system design
- **[Tool Management](../architecture/tool-management.md)** — How tools are loaded and managed
