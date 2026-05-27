# Telemetry

Agentlet-core provides comprehensive OpenTelemetry (OTel) integration for distributed tracing and metrics export.

## Overview

**Key Features:**
- **OTLP Traces** - Distributed tracing for agent executions
- **OTLP Metrics** - Performance metrics and resource usage
- **Signal-Specific Endpoints** - Separate endpoints for traces and metrics
- **Flexible Sampling** - Control trace volume with samplers
- **Console Exporter** - Debug traces locally without backend
- **Custom Attributes** - Enrich traces with business context
- **Log-Trace Correlation** - Automatic correlation of logs with traces

## Quick Start

### Enable OTel in Configuration

```yaml
observability:
  otel:
    # Enable OpenTelemetry trace export
    enabled: true

    # OTLP base endpoint (optional, defaults to http://localhost:4318)
    # OpenTelemetry automatically appends /v1/traces and /v1/metrics
    otlp_endpoint: "http://localhost:4318"

    # Enable metrics export (optional)
    enable_metrics: true

    # Enable console exporter for debugging (optional)
    console_exporter: false
```

### Run with OTel

```bash
# Run with OTel enabled
uv run agentlet-core --agentlet examples/otel-example.yaml \
  --prompt "Analyze this data"

# Override OTel settings via CLI
uv run agentlet-core --agentlet simple-assistant \
  --otel-enabled \
  --otlp-endpoint "http://collector:4318" \
  --prompt "Test"
```

## Configuration

### Basic Configuration

```yaml
observability:
  otel:
    enabled: true
    otlp_endpoint: "http://localhost:4318"
    enable_metrics: true
```

### Signal-Specific Endpoints

Send traces and metrics to different backends:

```yaml
observability:
  otel:
    enabled: true

    # Base endpoint (fallback)
    otlp_endpoint: "http://collector:4318"

    # Override for traces (e.g., send to Langfuse)
    otlp_traces_endpoint: "https://cloud.langfuse.com/api/public/otel"

    # Override for metrics (e.g., send to Prometheus)
    otlp_metrics_endpoint: "http://prometheus:4318"

    enable_metrics: true
```

**Important**: OpenTelemetry SDK automatically appends signal-specific paths:
- Traces: `/v1/traces`
- Metrics: `/v1/metrics`

### OTLP Headers

Add authentication headers for observability platforms:

```yaml
observability:
  otel:
    enabled: true
    otlp_endpoint: "https://api.honeycomb.io"
    otlp_headers:
      x-honeycomb-team: "${HONEYCOMB_API_KEY}"
      x-honeycomb-dataset: "agentlet-core"
```

### Sampling Configuration

Control trace volume with samplers:

```yaml
observability:
  otel:
    enabled: true

    # Sample 10% of traces (reduce overhead in production)
    sampler: "traceidratio"
    sampler_arg: 0.1  # 10% sampling
```

**Sampler Types**:
- `always_on` - Sample all traces (default, high overhead)
- `always_off` - Sample no traces (testing only)
- `traceidratio` - Sample a percentage of traces (production)
- `parentbased_always_on` - Respect parent span sampling decision

**Production Recommendation**: Use `traceidratio` with 0.01-0.1 (1-10%) for high-volume workloads.

### Console Exporter

Print traces to stdout for local debugging (without backend):

```yaml
observability:
  otel:
    enabled: true
    console_exporter: true  # Prints spans to stdout
```

**Use Case**: Local development, testing, troubleshooting without OTLP collector.

### Custom Trace Attributes

Add custom attributes to all traces:

```yaml
observability:
  otel:
    enabled: true
    trace_attributes:
      environment: "production"
      service.name: "agentlet-core"
      deployment.id: "v1.2.3"
      team: "ai-platform"
```

These attributes appear on all spans and help filter/group traces in observability platforms.

## CLI Overrides

Override OTel settings via command-line flags:

```bash
# Enable OTel for a config that doesn't have it
uv run agentlet-core --agentlet simple-assistant \
  --otel-enabled \
  --prompt "Test"

# Override endpoint
uv run agentlet-core --agentlet otel-example \
  --otlp-endpoint "http://collector:4318" \
  --prompt "Test"

# Override signal-specific endpoints
uv run agentlet-core --agentlet otel-example \
  --otlp-traces-endpoint "https://cloud.langfuse.com/api/public/otel" \
  --otlp-metrics-endpoint "http://prometheus:4318" \
  --prompt "Test"

# Enable console exporter
uv run agentlet-core --agentlet otel-example \
  --otel-console \
  --prompt "Test"
```

## Integration with Observability Platforms

### Jaeger (Local Development)

Run Jaeger locally with Docker:

```bash
# Start Jaeger all-in-one
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest

# Configure agentlet
uv run agentlet-core --agentlet simple-assistant \
  --otel-enabled \
  --otlp-endpoint "http://localhost:4318" \
  --prompt "Test"

# View traces at http://localhost:16686
```

### Grafana Tempo

Send traces to Tempo:

```yaml
observability:
  otel:
    enabled: true
    otlp_traces_endpoint: "http://tempo:4318"
    enable_metrics: false  # Tempo is traces-only
```

### Honeycomb

Send traces to Honeycomb cloud:

```yaml
observability:
  otel:
    enabled: true
    otlp_endpoint: "https://api.honeycomb.io"
    otlp_headers:
      x-honeycomb-team: "${HONEYCOMB_API_KEY}"
      x-honeycomb-dataset: "agentlet-core"
    sampler: "traceidratio"
    sampler_arg: 0.1  # 10% sampling
```

### AWS X-Ray

Send traces to AWS X-Ray via OTLP:

```yaml
observability:
  otel:
    enabled: true
    otlp_endpoint: "http://xray-collector:4318"
    trace_attributes:
      aws.service: "agentlet-core"
      aws.environment: "production"
```

### Langfuse (LLM Observability)

Send LLM traces to Langfuse:

```yaml
observability:
  otel:
    enabled: true
    otlp_traces_endpoint: "https://cloud.langfuse.com/api/public/otel"
    otlp_headers:
      Authorization: "Bearer ${LANGFUSE_API_KEY}"
    enable_metrics: false  # Langfuse doesn't support metrics
```

**Note**: OpenTelemetry automatically appends `/v1/traces` to the endpoint.

### Prometheus (Metrics)

Export metrics to Prometheus:

```yaml
observability:
  otel:
    enabled: true
    otlp_metrics_endpoint: "http://prometheus:4318"
    enable_metrics: true
```

Configure Prometheus to scrape OTLP metrics endpoint.

## Log-Trace Correlation

### Automatic Correlation

When both logging and OTel are enabled, logs automatically include trace context:

```python
from agentlet_core.logging import get_logger, log_context
from agentlet_core.telemetry import inject_trace_context

logger = get_logger(__name__)

# Inject trace context into logs
with log_context(**inject_trace_context(), execution_id=exec_id):
    logger.info("Processing request")  # Includes trace_id, span_id
```

### Trace Context Fields

Injected fields:
- `trace_id` - 32-character hex trace ID
- `span_id` - 16-character hex span ID
- `trace_flags` - Trace flags (sampling decision)

**JSON Log Output**:
```json
{
  "timestamp": "2026-01-30T10:30:45.123456+00:00",
  "level": "INFO",
  "message": "Processing request",
  "trace_id": "abc123...",
  "span_id": "def456...",
  "trace_flags": 1,
  "context": {
    "execution_id": "exec-123"
  }
}
```

### Benefits

- **Unified View** - View logs and traces together in observability platform
- **Root Cause Analysis** - Jump from trace span to logs and vice versa
- **Performance Debugging** - Correlate slow traces with error logs
- **Compliance** - Complete audit trail across logs and traces

## Telemetry API

### Configure Telemetry

```python
from agentlet_core.telemetry import configure_telemetry
from agentlet_core.config.models import OTELConfig

otel_config = OTELConfig(
    enabled=True,
    otlp_endpoint="http://localhost:4318",
    enable_metrics=True,
    console_exporter=True,
)

telemetry = configure_telemetry(otel_config)
```

### Get Telemetry Instance

```python
from agentlet_core.telemetry import get_telemetry_instance

telemetry = get_telemetry_instance()
if telemetry:
    # Telemetry is enabled
    pass
```

### Inject Trace Context

```python
from agentlet_core.telemetry import inject_trace_context

trace_context = inject_trace_context()
# Returns: {"trace_id": "...", "span_id": "...", "trace_flags": 1}
```

## Metrics

### Exported Metrics

When `enable_metrics: true`, agentlet-core exports:

- **Execution Time** - Duration of agentlet executions
- **Token Usage** - Input/output tokens per execution
- **Cost** - Estimated cost per execution
- **Tool Calls** - Number of tool invocations
- **Error Rate** - Errors per execution
- **Retry Count** - Retry attempts

### Metric Labels

All metrics include:
- `agentlet` - Agentlet name
- `model` - LLM model ID
- `provider` - LLM provider
- `execution_id` - Unique execution ID

## Troubleshooting

### OTel Not Working

**Check installation**:
```bash
# Install OTel dependencies
uv sync --group otel
# Or: pip install 'strands-agents[otel]'
```

**Check configuration**:
```python
from agentlet_core.telemetry import get_telemetry_instance

telemetry = get_telemetry_instance()
if not telemetry:
    print("OTel not enabled or failed to initialize")
```

### Traces Not Appearing in Backend

**Check endpoint connectivity**:
```bash
# Test OTLP endpoint (should return 405 Method Not Allowed for GET)
curl http://localhost:4318/v1/traces
```

**Check sampling**:
```yaml
# Ensure sampling is enabled
sampler: "always_on"  # Or remove sampler config
```

**Check headers**:
```yaml
# Verify authentication headers
otlp_headers:
  authorization: "Bearer ${API_KEY}"
```

### High Overhead

**Reduce sampling**:
```yaml
sampler: "traceidratio"
sampler_arg: 0.01  # 1% sampling
```

**Disable metrics**:
```yaml
enable_metrics: false  # Traces only
```

**Disable console exporter**:
```yaml
console_exporter: false  # Production setting
```

### Console Exporter Not Showing Spans

**Check stdout redirection**:
```bash
# Console exporter prints to stdout, not logs
uv run agentlet-core --agentlet otel-example \
  --otel-console \
  --prompt "Test" | grep -A 10 "Span"
```

**Check OTel is enabled**:
```yaml
enabled: true
console_exporter: true
```

### Signal-Specific Endpoints Not Working

**Verify endpoint format**:
```yaml
# Correct - OpenTelemetry appends /v1/traces
otlp_traces_endpoint: "https://api.example.com/otlp"

# Incorrect - double path
otlp_traces_endpoint: "https://api.example.com/otlp/v1/traces"
```

**Check environment variables**:
```bash
# These override config
echo $OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
echo $OTEL_EXPORTER_OTLP_METRICS_ENDPOINT
```

## Best Practices

### DO ✅

**Use sampling in production**:
```yaml
# Good - reduces overhead
sampler: "traceidratio"
sampler_arg: 0.1  # 10%
```

**Use signal-specific endpoints**:
```yaml
# Good - specialized backends
otlp_traces_endpoint: "https://langfuse.com/api/public/otel"
otlp_metrics_endpoint: "http://prometheus:4318"
```

**Add custom attributes for context**:
```yaml
# Good - helps filter/group traces
trace_attributes:
  environment: "production"
  team: "ai-platform"
  version: "1.2.3"
```

**Enable log-trace correlation**:
```python
# Good - unified observability
with log_context(**inject_trace_context(), execution_id=exec_id):
    logger.info("Processing")
```

### DON'T ❌

**Don't use `always_on` in production**:
```yaml
# Bad - high overhead
sampler: "always_on"

# Good - sample percentage
sampler: "traceidratio"
sampler_arg: 0.1
```

**Don't hardcode API keys**:
```yaml
# Bad - security risk
otlp_headers:
  x-api-key: "sk-1234567890"

# Good - use environment variables
otlp_headers:
  x-api-key: "${API_KEY}"
```

**Don't enable console exporter in production**:
```yaml
# Bad - pollutes logs
console_exporter: true

# Good - production setting
console_exporter: false
```

**Don't send all metrics to LLM observability platforms**:
```yaml
# Bad - Langfuse doesn't support metrics
otlp_endpoint: "https://langfuse.com/api/public/otel"
enable_metrics: true

# Good - traces only
otlp_traces_endpoint: "https://langfuse.com/api/public/otel"
enable_metrics: false
```

## Example Configurations

### Production Setup (AWS X-Ray + Prometheus)

```yaml
observability:
  otel:
    enabled: true

    # Traces to X-Ray
    otlp_traces_endpoint: "http://xray-collector:4318"

    # Metrics to Prometheus
    otlp_metrics_endpoint: "http://prometheus:4318"

    enable_metrics: true

    # Sample 1% of traces
    sampler: "traceidratio"
    sampler_arg: 0.01

    # Custom attributes
    trace_attributes:
      environment: "production"
      service.name: "agentlet-core"
      aws.region: "us-west-2"
```

### Local Development (Jaeger)

```yaml
observability:
  otel:
    enabled: true
    otlp_endpoint: "http://localhost:4318"
    console_exporter: true  # Debug traces
    enable_metrics: true
    sampler: "always_on"  # Sample all for debugging
```

### Multi-Backend (Langfuse + Prometheus)

```yaml
observability:
  otel:
    enabled: true

    # LLM traces to Langfuse
    otlp_traces_endpoint: "https://cloud.langfuse.com/api/public/otel"
    otlp_headers:
      Authorization: "Bearer ${LANGFUSE_API_KEY}"

    # Metrics to Prometheus
    otlp_metrics_endpoint: "http://prometheus:4318"

    enable_metrics: true
    sampler: "traceidratio"
    sampler_arg: 0.1  # 10% sampling
```

## See Also

- [Logging](logging.md) - Log-trace correlation
- [Monitoring](monitoring.md) - Production monitoring strategies
- [Architecture: Configuration System](../architecture/configuration-system.md) - OTel configuration schema
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
