# Monitoring

Best practices and strategies for monitoring agentlet-core in production environments.

## Overview

Effective monitoring of agentlet-core involves tracking:
- **Execution Metrics** - Duration, success rate, throughput
- **Resource Usage** - Token consumption, memory, CPU
- **Cost Management** - LLM API costs and optimization
- **Error Tracking** - Failures, retries, timeouts
- **Performance** - Latency, tool calls, response time

## Key Metrics

> **Note:** The metric names below (e.g. `agentlet.execution.duration_seconds`) are recommended conventions for custom instrumentation. Agentlet-core does not emit these metrics automatically — it exports traces via OTLP (see [Telemetry](telemetry.md)) and logs execution summaries (see [Logging](logging.md)). Use the `ExecutionContext` object in custom wrappers to publish metrics to your backend.

### Execution Metrics

**Execution Time**:
- **Metric**: `agentlet.execution.duration_seconds`
- **Type**: Histogram
- **Labels**: `agentlet`, `model`, `provider`
- **Description**: Time from spawn to terminate
- **Alerts**: `p95 > 300s` (5 minutes)

**Success Rate**:
- **Metric**: `agentlet.execution.status`
- **Type**: Counter
- **Labels**: `agentlet`, `model`, `status` (success/error/timeout)
- **Description**: Execution outcome
- **Alerts**: `error_rate > 5%`

**Throughput**:
- **Metric**: `agentlet.execution.count`
- **Type**: Counter
- **Labels**: `agentlet`, `model`
- **Description**: Total executions
- **Alerts**: `throughput < baseline * 0.5` (50% drop)

### Resource Metrics

**Token Usage**:
- **Metric**: `agentlet.tokens.total`
- **Type**: Histogram
- **Labels**: `agentlet`, `model`, `type` (input/output)
- **Description**: Token consumption per execution
- **Alerts**: `p95 > context_window * 0.8`

**Token Rate**:
- **Metric**: `agentlet.tokens.rate`
- **Type**: Gauge
- **Labels**: `agentlet`, `model`
- **Description**: Tokens per second
- **Alerts**: `rate > provider_limit * 0.9`

**Memory Usage**:
- **Metric**: `agentlet.memory.bytes`
- **Type**: Gauge
- **Labels**: `agentlet`
- **Description**: Process memory usage
- **Alerts**: `memory > resource_limit * 0.9`

### Cost Metrics

**Total Cost**:
- **Metric**: `agentlet.cost.total_usd`
- **Type**: Counter
- **Labels**: `agentlet`, `model`, `provider`
- **Description**: Cumulative LLM API costs
- **Alerts**: `daily_cost > budget`

**Cost per Execution**:
- **Metric**: `agentlet.cost.per_execution_usd`
- **Type**: Histogram
- **Labels**: `agentlet`, `model`
- **Description**: Cost distribution per execution
- **Alerts**: `p95 > expected_cost * 2`

**Cost Rate**:
- **Metric**: `agentlet.cost.rate_usd_per_hour`
- **Type**: Gauge
- **Labels**: `agentlet`
- **Description**: Hourly spend rate
- **Alerts**: `rate > hourly_budget`

### Error Metrics

**Error Rate**:
- **Metric**: `agentlet.errors.rate`
- **Type**: Gauge
- **Labels**: `agentlet`, `error_type`
- **Description**: Errors per minute
- **Alerts**: `rate > 1` (1 error/min)

**Retry Count**:
- **Metric**: `agentlet.retries.total`
- **Type**: Counter
- **Labels**: `agentlet`, `reason`
- **Description**: Total retry attempts
- **Alerts**: `retry_rate > 10%`

**Timeout Count**:
- **Metric**: `agentlet.timeouts.total`
- **Type**: Counter
- **Labels**: `agentlet`, `timeout_type` (execution/tool/model)
- **Description**: Timeout events
- **Alerts**: `timeout_rate > 1%`

### Performance Metrics

**Tool Call Latency**:
- **Metric**: `agentlet.tool.duration_seconds`
- **Type**: Histogram
- **Labels**: `agentlet`, `tool`
- **Description**: Tool execution time
- **Alerts**: `p95 > tool_sla`

**Model Latency**:
- **Metric**: `agentlet.model.duration_seconds`
- **Type**: Histogram
- **Labels**: `agentlet`, `model`, `provider`
- **Description**: LLM API response time
- **Alerts**: `p95 > provider_sla`

**Tool Call Count**:
- **Metric**: `agentlet.tool.calls.total`
- **Type**: Counter
- **Labels**: `agentlet`, `tool`
- **Description**: Total tool invocations
- **Alerts**: `calls > max_allowed`

## Alerting Strategies

### Critical Alerts (Page Immediately)

**High Error Rate**:
```yaml
alert: AgentletHighErrorRate
expr: rate(agentlet_execution_status{status="error"}[5m]) > 0.05
for: 5m
severity: critical
message: "Agentlet {{ $labels.agentlet }} error rate > 5%"
```

**Cost Overrun**:
```yaml
alert: AgentletCostOverrun
expr: rate(agentlet_cost_total_usd[1h]) * 24 > daily_budget
for: 15m
severity: critical
message: "Agentlet {{ $labels.agentlet }} projected daily cost exceeds budget"
```

**Service Down**:
```yaml
alert: AgentletServiceDown
expr: up{job="agentlet-core"} == 0
for: 2m
severity: critical
message: "Agentlet service is down"
```

### Warning Alerts (Investigate During Business Hours)

**High Latency**:
```yaml
alert: AgentletHighLatency
expr: histogram_quantile(0.95, agentlet_execution_duration_seconds) > 300
for: 10m
severity: warning
message: "Agentlet {{ $labels.agentlet }} p95 latency > 5 minutes"
```

**High Token Usage**:
```yaml
alert: AgentletHighTokenUsage
expr: rate(agentlet_tokens_total[1h]) > 1000000
for: 15m
severity: warning
message: "Agentlet {{ $labels.agentlet }} token rate > 1M/hour"
```

**Increased Retries**:
```yaml
alert: AgentletHighRetryRate
expr: rate(agentlet_retries_total[10m]) / rate(agentlet_execution_count[10m]) > 0.1
for: 15m
severity: warning
message: "Agentlet {{ $labels.agentlet }} retry rate > 10%"
```

### Informational Alerts (Trending/Capacity Planning)

**Token Usage Trending Up**:
```yaml
alert: AgentletTokenUsageTrend
expr: predict_linear(agentlet_tokens_total[1h], 3600 * 24) > daily_token_limit
for: 30m
severity: info
message: "Agentlet {{ $labels.agentlet }} token usage trending toward limit"
```

**Cost Trending Up**:
```yaml
alert: AgentletCostTrend
expr: predict_linear(agentlet_cost_total_usd[6h], 3600 * 24) > daily_budget * 1.2
for: 1h
severity: info
message: "Agentlet {{ $labels.agentlet }} cost trending 20% over budget"
```

## Performance Tuning

### Execution Time Optimization

**Reduce Tool Calls**:
```yaml
# Optimize system prompt to minimize unnecessary tool usage
system_prompt: |
  You are an assistant. Use tools only when necessary.
  Before using a tool, explain why it's needed.
```

**Parallel Tool Execution**:
```python
# Configure agent to execute independent tools in parallel
# (requires Strands Agent Framework support)
```

**Caching Strategy**:
```python
# Cache expensive tool results
from functools import lru_cache

@lru_cache(maxsize=100)
def expensive_tool_call(args):
    # Tool implementation
    pass
```

### Token Usage Optimization

**Prompt Engineering**:
```yaml
# Concise system prompts reduce input tokens
system_prompt: "You are a helpful assistant. Be concise."

# Bad - verbose system prompt
system_prompt: |
  You are a helpful assistant. You should always be polite and respectful.
  You should provide detailed explanations. You should use markdown formatting.
  [... 500 more words ...]
```

**Context Window Management**:
```yaml
# Limit max tokens to avoid runaway generations
model:
  parameters:
    max_tokens: 2048  # Prevent 100K token responses
```

**Tool Output Truncation**:
```python
# Truncate large tool outputs before sending to model
def truncate_output(output: str, max_chars: int = 5000) -> str:
    if len(output) > max_chars:
        return output[:max_chars] + "\n[... truncated]"
    return output
```

### Cost Optimization

**Model Selection**:
```yaml
# Use cost-effective models for simple tasks
model:
  provider: "anthropic"
  model_id: "claude-haiku-3-5"  # Cheaper for simple tasks

# Use expensive models only for complex reasoning
model:
  provider: "anthropic"
  model_id: "claude-sonnet-4-6"  # Complex tasks
```

**Prompt Caching** (Anthropic):
```yaml
# Enable prompt caching to reduce input token costs
model:
  parameters:
    cache_control: true
```

**Batching**:
```python
# Batch multiple requests to amortize fixed costs
async def batch_execute(prompts: list[str]) -> list[str]:
    # Execute multiple agentlets in parallel
    tasks = [agentlet.run(prompt) for prompt in prompts]
    return await asyncio.gather(*tasks)
```

**Token Limits**:
```yaml
# Set strict token limits to prevent cost overruns
resource_limits:
  max_tokens: 10000  # Hard limit per execution
```

## Resource Limits

### Execution Constraints

```yaml
resource_limits:
  # Maximum execution time (seconds)
  max_execution_time: 300  # 5 minutes

  # Maximum total tokens (input + output) — passed as max_tokens to the model
  max_tokens: 10000

  # Maximum tool calls per execution
  max_tool_calls: 20
```

> **Note:** `max_concurrent_executions` is not a built-in config field. Use OS-level process limits, container resource constraints, or a semaphore in your orchestration layer to cap concurrency.

### Memory Limits

**Container/Process Limits**:
```yaml
# Docker Compose
services:
  agentlet-core:
    mem_limit: 1g
    mem_reservation: 512m

# Kubernetes
resources:
  limits:
    memory: "1Gi"
  requests:
    memory: "512Mi"
```

**Working Directory Cleanup**:
```python
# Automatically cleanup temp directories after execution
# (handled by ExecutionContext.cleanup())
```

### Rate Limiting

**Provider Rate Limits**:

`model.parameters` is a pass-through dict to LiteLLM — it does not define `rpm_limit` or `tpm_limit` fields. To control provider rate limiting, configure your LiteLLM proxy or use the retry/backoff settings on the `model.retry` block:

```yaml
model:
  retry:
    max_retries: 5
    initial_retry_interval: 30.0  # back off when throttled
    backoff_factor: 2.0
```

**Application Rate Limiting**:
```python
# Use semaphore to limit concurrent executions
import asyncio

semaphore = asyncio.Semaphore(10)  # Max 10 concurrent

async def execute_with_limit(agentlet, prompt):
    async with semaphore:
        return await agentlet.run(prompt)
```

## Production Checklist

### Configuration

- [ ] **Resource limits configured** - Set `max_execution_time`, `max_tokens`
- [ ] **Retry logic enabled** - Configure `max_retries` and backoff
- [ ] **Timeout values set** - Prevent runaway executions
- [ ] **Model selection optimized** - Use cost-effective models where possible
- [ ] **Prompt caching enabled** - Reduce input token costs (if supported)

### Observability

- [ ] **Logging configured** - Production logging (INFO level, no debug)
- [ ] **OTel enabled** - Traces and metrics to observability backend
- [ ] **Sampling configured** - Use `traceidratio` sampler (1-10%)
- [ ] **Custom attributes added** - Environment, team, version labels
- [ ] **Log-trace correlation enabled** - `inject_trace_context()`

### Monitoring

- [ ] **Metrics exported** - Prometheus/CloudWatch/Datadog integration
- [ ] **Dashboards created** - Execution time, cost, errors, token usage
- [ ] **Alerts configured** - Critical (error rate, cost), warning (latency)
- [ ] **Cost tracking setup** - Daily/monthly budget alerts
- [ ] **On-call runbook created** - Incident response procedures

### Security

- [ ] **Secret sanitization enabled** - `enable_sanitization=True`
- [ ] **API keys in env vars** - Never hardcode credentials
- [ ] **Network policies set** - Restrict egress to necessary endpoints
- [ ] **MCP tool permissions configured** - Limit filesystem access
- [ ] **Audit logging enabled** - Track all tool executions

### Resilience

- [ ] **Error handling tested** - Handle provider outages gracefully
- [ ] **Retry logic tested** - Verify exponential backoff works
- [ ] **Timeout handling tested** - Ensure cleanup happens on timeout
- [ ] **Rate limit handling** - Backoff on provider throttling
- [ ] **Graceful degradation** - Fallback to simpler models on failure

### Performance

- [ ] **Load testing completed** - Validate under expected load
- [ ] **Latency SLAs defined** - p50, p95, p99 targets
- [ ] **Token usage baseline** - Track deviations from baseline
- [ ] **Cost projections calculated** - Budget for expected usage
- [ ] **Optimization opportunities identified** - Prompt, model, caching

## Example Monitoring Setups

### CloudWatch (AWS)

**Export Metrics to CloudWatch**:
```python
from agentlet_core.runtime.context import ExecutionContext
import boto3

cloudwatch = boto3.client("cloudwatch")

def publish_metrics(ctx: ExecutionContext):
    metrics = [
        {
            "MetricName": "ExecutionDuration",
            "Value": ctx.execution_time,
            "Unit": "Seconds",
            "Dimensions": [
                {"Name": "Agentlet", "Value": ctx.agentlet_name},
            ],
        },
        {
            "MetricName": "TokenUsage",
            "Value": ctx.input_tokens + ctx.output_tokens,
            "Unit": "Count",
        },
        {
            "MetricName": "Cost",
            "Value": ctx.total_cost,
            "Unit": "None",
        },
    ]

    cloudwatch.put_metric_data(
        Namespace="AgentletCore",
        MetricData=metrics,
    )
```

**CloudWatch Alarms**:
```bash
# Create alarm for high error rate
aws cloudwatch put-metric-alarm \
  --alarm-name agentlet-high-error-rate \
  --alarm-description "Alert when error rate > 5%" \
  --metric-name ExecutionStatus \
  --namespace AgentletCore \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 0.05 \
  --comparison-operator GreaterThanThreshold
```

### Prometheus + Grafana

**Prometheus Scrape Config**:
```yaml
scrape_configs:
  - job_name: "agentlet-core"
    static_configs:
      - targets: ["localhost:9090"]
    metrics_path: "/metrics"
    scrape_interval: 15s
```

**Grafana Dashboard Panels**:
```json
{
  "title": "Agentlet Execution Time (p95)",
  "targets": [
    {
      "expr": "histogram_quantile(0.95, agentlet_execution_duration_seconds)",
      "legendFormat": "{{ agentlet }}"
    }
  ]
}
```

### Datadog

**Datadog Agent Configuration**:
```yaml
# datadog.yaml
logs:
  - type: file
    path: /var/log/agentlet-core*.log
    service: agentlet-core
    source: python

apm_config:
  enabled: true
  env: production

# OTel integration
otlp_config:
  receiver:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"
      http:
        endpoint: "0.0.0.0:4318"
```

**Agentlet Configuration**:
```yaml
observability:
  otel:
    enabled: true
    otlp_endpoint: "http://datadog-agent:4318"
    trace_attributes:
      env: "production"
      service: "agentlet-core"
```

### Custom Metrics Export

**Export to Time-Series Database**:
```python
from agentlet_core.runtime.context import ExecutionContext
import influxdb_client

def export_metrics(ctx: ExecutionContext):
    client = influxdb_client.InfluxDBClient(url="http://influxdb:8086")
    write_api = client.write_api()

    point = (
        influxdb_client.Point("agentlet_execution")
        .tag("agentlet", ctx.agentlet_name)
        .field("duration", ctx.execution_time)
        .field("tokens", ctx.input_tokens + ctx.output_tokens)
        .field("cost", ctx.total_cost)
        .field("tool_calls", len(ctx.tool_calls))
        .field("errors", len(ctx.errors))
    )

    write_api.write(bucket="agentlet-metrics", record=point)
```

## Cost Optimization Strategies

### Token Usage Reduction

**Optimize System Prompts**:
```python
# Before: 500 tokens
system_prompt = """
You are a helpful assistant with extensive knowledge.
You should always provide detailed explanations with examples.
You should format your responses in markdown with headers and lists.
[... verbose instructions ...]
"""

# After: 50 tokens
system_prompt = "You are a helpful assistant. Be concise and accurate."
```

**Tool Output Summarization**:
```python
# Summarize large tool outputs before sending to model
def summarize_tool_output(output: str, max_chars: int = 1000) -> str:
    if len(output) <= max_chars:
        return output

    # Keep first/last portions, summarize middle
    head = output[:max_chars // 2]
    tail = output[-(max_chars // 2):]
    return f"{head}\n\n[... {len(output) - max_chars} chars omitted ...]\n\n{tail}"
```

### Model Selection Strategy

**Tiered Model Approach**:
```python
# Route simple tasks to cheaper models
def select_model(task_complexity: str) -> str:
    if task_complexity == "simple":
        return "anthropic/claude-haiku-3-5"  # $0.25/$1.25 per M tokens
    elif task_complexity == "medium":
        return "anthropic/claude-sonnet-4-6"  # $3/$15 per M tokens
    else:
        return "anthropic/claude-opus-4-5"  # $15/$75 per M tokens
```

**Complexity Detection**:
```python
# Analyze prompt to determine task complexity
def detect_complexity(prompt: str) -> str:
    # Simple: short prompts, basic questions
    if len(prompt) < 100 and "?" in prompt:
        return "simple"

    # Complex: analysis, multi-step reasoning
    keywords = ["analyze", "compare", "design", "implement", "debug"]
    if any(kw in prompt.lower() for kw in keywords):
        return "complex"

    return "medium"
```

### Caching Strategies

**Prompt Caching** (Anthropic):
```yaml
# Enable prompt caching to reduce input token costs
model:
  parameters:
    cache_control:
      type: "ephemeral"  # Cache system prompt
```

**Response Caching**:
```python
# Cache responses for duplicate prompts
import hashlib
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_execute(prompt_hash: str, agentlet_name: str):
    # Execute agentlet and cache result
    pass

# Hash prompt for cache key
prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
result = cached_execute(prompt_hash, agentlet.name)
```

### Budget Controls

**Daily Budget Limits**:
```python
# Track daily spend and stop when budget exceeded
class BudgetController:
    def __init__(self, daily_budget_usd: float):
        self.daily_budget = daily_budget_usd
        self.daily_spend = 0.0
        self.last_reset = datetime.now().date()

    def check_budget(self, estimated_cost: float) -> bool:
        # Reset daily spend at midnight
        if datetime.now().date() > self.last_reset:
            self.daily_spend = 0.0
            self.last_reset = datetime.now().date()

        # Check if execution would exceed budget
        if self.daily_spend + estimated_cost > self.daily_budget:
            return False

        self.daily_spend += estimated_cost
        return True

# Usage
budget = BudgetController(daily_budget_usd=100.0)
if budget.check_budget(estimated_cost=0.05):
    result = await agentlet.run(prompt)
else:
    raise BudgetExceededError("Daily budget exhausted")
```

**Per-User Limits**:
```python
# Track spend per user/tenant
user_budgets = {
    "user_123": {"daily": 10.0, "monthly": 200.0},
    "user_456": {"daily": 50.0, "monthly": 1000.0},
}

def check_user_budget(user_id: str, cost: float) -> bool:
    budget = user_budgets.get(user_id)
    # Check daily and monthly limits
    return cost <= budget["daily"]
```

## See Also

- [Logging](logging.md) - Production logging best practices
- [Telemetry](telemetry.md) - OpenTelemetry integration
- [Architecture: Execution Context](../architecture/agent-lifecycle.md) - Metrics collection
- [Reference: Configuration](../reference/configuration.md) - Resource limits configuration
