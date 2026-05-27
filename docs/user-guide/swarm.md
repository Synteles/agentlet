# Swarm Multi-Agent Pattern

A complete guide to the **swarm** multi-agent pattern in agentlet-core — peer-to-peer collaboration with no central coordinator.

## Overview

The swarm pattern enables multiple specialised agents to collaborate autonomously. Instead of a central orchestrator deciding who to call (the [sub-agentlets pattern](multi-agent.md)), agents in a swarm **hand off to each other directly** based on shared context. Any agent can transfer control to any other, and the swarm terminates when an agent decides the task is complete.

This enables two powerful use cases:

- **Expert panels** — a fixed set of specialist roles, possibly with multiple instances of each, collaborating without top-down routing.
- **Dynamically provisioned teams** — the LLM decides what specialists are needed per task and assembles the team at runtime.

Both modes are configured entirely in YAML. Existing single-agent and sub-agentlets configs are unaffected.

## Three Modes

| Mode | `swarm` section | `"swarm"` in `tools` | Description |
|------|:-:|:-:|---|
| **Declarative panel** | ✅ | ❌ | Agent types and counts defined in YAML; agentlet-core builds the team |
| **Dynamic** | ❌ | ✅ | Single orchestrator gets the `strands_tools.swarm` tool; LLM assembles the team at runtime |
| **Combined** | ✅ | ✅ | Pre-defined panel + dynamic tool for ad-hoc sub-swarms |

---

## Quick Start

### Declarative Expert Panel

```yaml
# expert-panel.yaml
agentlet:
  name: expert-panel
  version: "1.0.0"

system_prompt: |
  You are a solutions architect. Collaborate with your peers.
  Hand off to devops_engineer_* for infrastructure topics.
  Hand off to domain_expert_* for business context.

model:
  provider: bedrock
  model_id: claude-sonnet-4-6

swarm:
  entry_point: solutions_architect
  participants:
    - name: solutions_architect
      count: 2
      description: "Designs architecture and evaluates technical trade-offs."
      system_prompt: "You are a senior solutions architect..."

    - name: devops_engineer
      count: 3
      description: "Infrastructure, CI/CD, and reliability engineering."
      system_prompt: "You are a senior DevOps engineer..."
      tools: [shell, file_editor]

    - name: domain_expert
      count: 2
      description: "Business context and regulatory requirements."
      system_prompt: "You are a domain expert..."
      tools: [tavily]
```

```bash
agentlet-core --agentlet expert-panel.yaml \
  --prompt "Design a highly available payments system"
```

### Dynamic Swarm

```yaml
# dynamic-swarm.yaml
agentlet:
  name: dynamic-swarm-orchestrator
  version: "1.0.0"

system_prompt: |
  Use the swarm tool to assemble a bespoke team for each task.
  Identify what expertise is needed, define agents with clear
  system prompts, and launch the swarm.

model:
  provider: bedrock
  model_id: claude-sonnet-4-6

tools:
  - swarm   # gives the orchestrator the dynamic swarm tool
```

```bash
agentlet-core --agentlet dynamic-swarm.yaml \
  --prompt "Research and summarise quantum error correction breakthroughs"
```

See full working examples in `examples/`:
- `swarm-expert-panel.yaml` — declarative panel (2+3+2 agents)
- `swarm-dynamic.yaml` — LLM-provisioned team
- `swarm-combined.yaml` — panel + dynamic tool

---

## Declarative Mode: Configuration Reference

### `swarm` Section

```yaml
swarm:
  entry_point: <string>          # Optional — participant name that receives the first prompt
  max_handoffs: <int>            # Default: 20
  max_iterations: <int>          # Default: 20
  execution_timeout: <float>     # Default: 900.0 (seconds)
  node_timeout: <float>          # Default: 300.0 (seconds)
  repetitive_handoff_detection_window: <int>   # Default: 0 (disabled)
  repetitive_handoff_min_unique_agents: <int>  # Default: 0 (disabled)

  participants:
    - name: <string>             # Required — base name for this agent type
      count: <int>               # Default: 1 — number of instances to create
      description: <string>      # Required — shown to peers for routing decisions
      system_prompt: <string>    # Required — specialisation instructions
      model:                     # Optional — overrides top-level model
        provider: <string>
        model_id: <string>
        parameters:
          temperature: <float>
      tools:                     # Optional — Strands default tools
        - <tool_name>
      mcp_tools:                 # Optional — MCP tool servers
        - name: <string>
          server: stdio | http | sse
          ...
```

### `swarm` Field Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `entry_point` | `str \| null` | `null` (first participant) | Base name of the participant that receives the initial prompt. Resolves to the first instance of that type. |
| `max_handoffs` | `int` | `20` | Maximum total agent-to-agent handoffs before the swarm halts. |
| `max_iterations` | `int` | `20` | Maximum total agent iterations across all nodes. |
| `execution_timeout` | `float` | `900.0` | Wall-clock time limit for the entire swarm run (seconds). |
| `node_timeout` | `float` | `300.0` | Per-agent turn time limit (seconds). |
| `repetitive_handoff_detection_window` | `int` | `0` | Number of recent handoffs to inspect for loops. `0` disables detection. |
| `repetitive_handoff_min_unique_agents` | `int` | `0` | Minimum unique agents required in the detection window. `0` disables. |
| `participants` | `list` | required | Agent types in the panel. At least one entry required. |

### `SwarmParticipantConfig` Field Reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | Yes | — | Base name. When `count > 1`, instances are named `{name}_1`, `{name}_2`, … |
| `count` | No | `1` | Number of identical instances to create. Must be ≥ 1. |
| `description` | Yes | — | Shown to peer agents so they know when to hand off to this type. Be specific. |
| `system_prompt` | Yes | — | Specialisation instructions for this agent type. |
| `model` | No | Inherits top-level | Override the model for this participant type. |
| `tools` | No | `[]` | Strands built-in tools (e.g. `shell`, `http_request`, `tavily`). |
| `mcp_tools` | No | `[]` | MCP tool servers. Same schema as the top-level `mcp_tools` field. |

---

## Agent Instance Naming

The name expansion rule determines how instances are named when `count > 1`:

| `name` | `count` | Instance names |
|--------|---------|----------------|
| `solutions_architect` | `1` | `solutions_architect` |
| `solutions_architect` | `2` | `solutions_architect_1`, `solutions_architect_2` |
| `devops_engineer` | `3` | `devops_engineer_1`, `devops_engineer_2`, `devops_engineer_3` |

System prompts should refer to peer agents using the `*` wildcard pattern (e.g., `devops_engineer_*`) since each peer may have multiple instances and the handoff tool uses the actual expanded name.

### Entry Point Resolution

The `entry_point` field names the **base name** of the participant that receives the first user prompt:

- `entry_point: solutions_architect` with `count: 1` → first message goes to `solutions_architect`
- `entry_point: solutions_architect` with `count: 2` → first message goes to `solutions_architect_1`
- `entry_point: null` (omitted) → first message goes to the first instance of the first participant

---

## Dynamic Mode

In dynamic mode, the top-level agent has `"swarm"` in its `tools` list. The `strands_tools.swarm` tool lets the LLM:

1. Define any number of agents (name, system_prompt, tools).
2. Set an entry point.
3. Launch the swarm and receive its result.

No `swarm` section is needed. The LLM writes the full team specification at runtime.

```yaml
tools:
  - swarm
```

This is useful when the required expertise varies significantly between tasks, or when you cannot know the team composition in advance.

---

## Combined Mode

Combined mode provides both a pre-defined peer panel (for known specialist roles) and the `swarm` tool (for ad-hoc expertise outside the panel). The `"swarm"` tool is given **only to the entry-point agent** — other participants in the panel are not affected.

```yaml
tools:
  - swarm   # entry-point agent gets this tool for ad-hoc sub-swarms

swarm:
  entry_point: solutions_architect
  participants:
    - name: solutions_architect
      count: 2
      ...
    - name: devops_engineer
      count: 3
      ...
```

Use peer handoffs first (faster, cheaper). Reach for the `swarm` tool only when the task requires expertise outside the declared panel.

---

## Safety Parameters

All safety parameters map 1:1 to the Strands SDK `Swarm` constructor — no translation layer. The defaults match the SDK defaults.

### Handoff and Iteration Limits

```yaml
swarm:
  max_handoffs: 20      # Total handoffs across the entire run
  max_iterations: 20    # Total agent turns across the entire run
```

When either limit is reached, the swarm halts with an error. Size these to the expected complexity of your tasks. Multi-step research with many specialist handoffs may need 50–100.

### Timeouts

```yaml
swarm:
  execution_timeout: 900.0   # Entire swarm — 15 minutes default
  node_timeout: 300.0        # Single agent turn — 5 minutes default
```

`execution_timeout` is enforced by the Strands SDK (separate from the CLI `--timeout` flag, which is an outer wall-clock limit). If a task consistently hits `execution_timeout`, increase it here.

### Loop Detection

```yaml
swarm:
  repetitive_handoff_detection_window: 8   # Look at last N handoffs
  repetitive_handoff_min_unique_agents: 3  # Require at least N distinct agents in window
```

Both default to `0` (disabled). Enable loop detection when you want to guard against pathological A→B→A→B→… cycles. A reasonable starting point for a 3-type panel is `window: 8, min_unique: 3`.

Do **not** enable loop detection for panels with fewer than `min_unique_agents` participant types — the check would always fail.

---

## Model Configuration

### Inheriting the Top-Level Model

Omit `model` from a participant to inherit the top-level model:

```yaml
model:
  provider: bedrock
  model_id: claude-sonnet-4-6

swarm:
  participants:
    - name: analyst
      count: 2
      description: "..."
      system_prompt: "..."
      # No model — inherits bedrock/claude-sonnet-4-6
```

### Per-Participant Model Override

Override the model for specific participant types — useful for cost optimisation:

```yaml
swarm:
  participants:
    - name: analyst
      description: "Complex analysis requiring extended reasoning."
      system_prompt: "..."
      model:
        provider: bedrock
        model_id: claude-opus-4-6   # More capable for reasoning tasks

    - name: summariser
      description: "Summarises analysis into bullet points."
      system_prompt: "..."
      model:
        provider: bedrock
        model_id: claude-haiku-4-5  # Cheaper for simpler generative tasks
```

All instances of a participant type use the same model.

---

## Tools Configuration

### Participant-Level Tools

Each participant type declares its own tools. Tools are independent across participant types.

```yaml
swarm:
  participants:
    - name: researcher
      description: "..."
      system_prompt: "..."
      tools:
        - tavily          # Web search
        - http_request    # Fetch URLs

    - name: coder
      description: "..."
      system_prompt: "..."
      tools:
        - shell           # Execute shell commands
        - file_editor     # Read and write files
```

### Top-Level Tools in Swarm Mode

Top-level `tools` are applied **only to the entry-point agent** and only in combined mode. This is how `tools: [swarm]` gives the entry agent the dynamic sub-swarm tool without giving it to every participant:

```yaml
tools:
  - swarm          # Goes to entry_point agent only

swarm:
  entry_point: lead
  participants:
    - name: lead   # ← gets the swarm tool
      ...
    - name: worker # ← does NOT get the swarm tool
      ...
```

Top-level `mcp_tools` are **not** applied in swarm mode — a warning is logged at startup if any are set. Declare MCP tools at the participant level.

---

## Writing Effective Swarm Agents

### Entry-Point System Prompt

The entry-point agent receives the user's prompt first. Its system prompt should:

- Describe the peer agents by expanded name (or name pattern) and what they handle.
- Explain when to hand off vs. when to continue.
- Instruct when to synthesise and conclude.

```yaml
system_prompt: |
  You are a solutions architect on an expert panel.

  Your peers:
  - devops_engineer_1, devops_engineer_2, devops_engineer_3:
    Use for infrastructure, deployment, CI/CD, and reliability.
  - domain_expert_1, domain_expert_2:
    Use for regulatory requirements and business context.

  Workflow:
  1. Analyse the request.
  2. Hand off to appropriate peers for their specialist input.
  3. Synthesise all contributions into a final recommendation.
  4. Deliver the final answer without further handoffs.
```

### Peer Agent System Prompts

Peer agents' system prompts should:

- Focus on one specialist area.
- Describe what they return (so the entry agent knows what to expect).
- Specify when to hand back vs. hand off further.

```yaml
system_prompt: |
  You are a senior DevOps engineer on an expert panel.
  You handle infrastructure, deployment, and reliability concerns.
  When you have provided your input, hand back to solutions_architect
  for the architectural synthesis. Do not attempt to produce the
  final deliverable — that is the architect's responsibility.
```

### Participant Descriptions

The `description` field is how peer agents know when to hand off to this participant type. Descriptions should be:

- **Specific** about the domain covered.
- **Action-oriented** ("Use for…", "Handles…").
- **Distinct** from other participants to minimise routing ambiguity.

```yaml
# Good
description: >
  Handles infrastructure, CI/CD pipelines, reliability engineering,
  and operational concerns. Use for deployment strategies, monitoring,
  scaling, and site reliability topics.

# Bad
description: "DevOps stuff"
```

---

## Mutual Exclusion: `swarm` and `sub_agentlets`

The `swarm` pattern and the `sub_agentlets` (orchestrator-as-tool) pattern are **mutually exclusive**. Declaring both in the same config raises a validation error:

```yaml
# ❌ Invalid — will raise ValidationError
sub_agentlets:
  - name: helper
    ...

swarm:
  participants:
    - name: analyst
      ...
```

```
ValueError: Cannot combine 'swarm' and 'sub_agentlets' in the same config.
Use the swarm pattern for peer-to-peer coordination, or
sub_agentlets for orchestrator-as-tool pattern — not both.
```

Use `sub_agentlets` when you want top-down, deterministic routing from a central orchestrator. Use `swarm` when you want agents to self-organise and route autonomously.

---

## OpenTelemetry Tracing

Each swarm node gets these additional trace attributes so spans can be filtered and correlated in your observability backend:

| Attribute | Value |
|-----------|-------|
| `agentlet.name` | Expanded instance name (e.g., `solutions_architect_1`) |
| `swarm_participant.name` | Same as `agentlet.name` |
| `swarm.parent_execution_id` | The orchestrating agentlet's execution ID |

All swarm node spans are children of the same trace as the parent agentlet because all agents run in-process.

---

## Statistics

After each swarm execution, per-node wall-clock times are logged:

```
📊 Swarm node statistics:
📊     [solutions_architect_1]  8.3s
📊     [devops_engineer_2]      5.1s
📊     [domain_expert_1]        3.7s
```

Nodes that never received a handoff are silently omitted.

---

## Constraints and Limitations

| Constraint | Detail |
|-----------|--------|
| **In-process only** | All swarm agents run in the same process. Distributed (A2A) swarms are not supported by the Strands SDK. |
| **No nested swarms** | A swarm participant cannot itself declare a `swarm` section. |
| **`sub_agentlets` mutual exclusion** | Cannot combine `swarm` and `sub_agentlets` in the same config. |
| **MCP tools per participant** | Top-level `mcp_tools` are not propagated to swarm participants — a warning is logged at startup if any are declared. Declare MCP tools at the participant level. |
| **Same-process cleanup** | Participant MCP managers are stored in the shared `_sub_mcp_managers` list and cleaned up by `terminate()` alongside orchestrator MCP tools. |

---

## Execution Mode Decision Guide

```
Does the task require multiple specialised agents?
├── No → Use single agent (no swarm, no sub_agentlets)
└── Yes → Can the routing logic be predetermined?
    ├── Yes → Do you want central, deterministic control?
    │   └── Yes → Use sub_agentlets (orchestrator-as-tool)
    └── No (agents should self-organise) → Use swarm
        ├── Is the team composition known in advance?
        │   ├── Yes → Declarative swarm (swarm: section)
        │   └── No → Dynamic swarm (tools: [swarm])
        └── Both → Combined mode (swarm: section + tools: [swarm])
```

---

## Full Examples

| File | Pattern | Panel |
|------|---------|-------|
| `examples/swarm-expert-panel.yaml` | Declarative | 2× Solutions Architect, 3× DevOps Engineer, 2× Domain Expert |
| `examples/swarm-dynamic.yaml` | Dynamic | LLM-provisioned at runtime |
| `examples/swarm-combined.yaml` | Combined | Panel + ad-hoc sub-swarms |
| `examples/multi-agent-example.yaml` | sub_agentlets | Research agent + Writing agent |

---

## Next Steps

- **[Multi-Agent Systems (sub_agentlets)](multi-agent.md)** — Orchestrator-as-tool pattern
- **[Configuration Reference](configuration.md)** — Full config schema including `swarm`
- **[Tool Management](../architecture/tool-management.md)** — How tools are loaded per participant
- **[Telemetry](../observability/telemetry.md)** — OTel configuration for swarm trace filtering
