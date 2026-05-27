# Deployment Guide

Deploy agentlet-core in production environments.

## Deployment Options

### 1. GitHub Release Wheel

**Best for:**
- Python applications
- Virtual environments
- Development and testing

Download the latest wheel from the [Releases page](https://github.com/Synteles/agentlet/releases):

```bash
# Install the wheel
pip install agentlet_core-<version>-py3-none-any.whl

# Or with uv
uv tool install agentlet_core-<version>-py3-none-any.whl
```

### 2. Docker Container

**Best for:**
- Containerized environments
- Kubernetes deployments
- Isolated execution

```bash
# Pull latest image
docker pull synteles/agentlet-core:latest

# Pull specific version
docker pull synteles/agentlet-core:0.1.0-alpha
```

### 3. Source Installation

**Best for:**
- Development builds
- Custom modifications
- Latest features

```bash
# Clone and install
git clone https://github.com/Synteles/agentlet.git
cd agentlet
uv sync
# Or with pip:
pip install -e .
```

## Docker Deployment

### Docker Run

```bash
# Basic run
docker run -it --rm \
  -v $(pwd):/workspace \
  -e ANTHROPIC_API_KEY="your-api-key" \
  synteles/agentlet-core:latest \
  agentlet-core --agentlet /workspace/my-agent.yaml --prompt "Hello"
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  agentlet:
    image: synteles/agentlet-core:0.1.0-alpha
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
    volumes:
      - ./agentlets:/workspace/agentlets
      - ./logs:/workspace/logs
    command: >
      agentlet-core
      --agentlet /workspace/agentlets/my-agent.yaml
      --prompt "Process task"
      --otel-enabled

  otel-collector:
    image: otel/opentelemetry-collector:latest
    ports:
      - "4318:4318"
    volumes:
      - ./otel-config.yaml:/etc/otel-config.yaml
    command: ["--config=/etc/otel-config.yaml"]
```

```bash
# Run with docker-compose
docker-compose up
```

### Custom Dockerfile

```dockerfile
# Dockerfile
FROM synteles/agentlet-core:0.1.0-alpha

# Copy agentlet configs
COPY agentlets/ /app/agentlets/

# Set environment variables
ENV ANTHROPIC_API_KEY=""
ENV OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"

# Set working directory
WORKDIR /app

# Run agentlet
CMD ["agentlet-core", "--agentlet", "/app/agentlets/production.yaml"]
```

```bash
# Build and run
docker build -t my-agentlet:latest .
docker run -e ANTHROPIC_API_KEY="key" my-agentlet:latest
```

## Kubernetes Deployment

### Basic Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agentlet-worker
  labels:
    app: agentlet
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agentlet
  template:
    metadata:
      labels:
        app: agentlet
    spec:
      containers:
      - name: agentlet
        image: synteles/agentlet-core:0.1.0-alpha
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: agentlet-secrets
              key: anthropic-api-key
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: "http://otel-collector:4318"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        volumeMounts:
        - name: config
          mountPath: /config
      volumes:
      - name: config
        configMap:
          name: agentlet-config
```

### ConfigMap

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: agentlet-config
data:
  my-agent.yaml: |
    agentlet:
      name: "production-agent"
      version: "1.0.0"
    model:
      provider: "anthropic"
      model_id: "claude-sonnet-4-6"
    system_prompt: "You are a production assistant."
    observability:
      otel:
        enabled: true
```

### Secret

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: agentlet-secrets
type: Opaque
stringData:
  anthropic-api-key: "your-api-key-here"
```

```bash
# Apply Kubernetes resources
kubectl apply -f secret.yaml
kubectl apply -f configmap.yaml
kubectl apply -f deployment.yaml

# Check status
kubectl get pods -l app=agentlet
kubectl logs -l app=agentlet --follow
```

### Job for One-Time Execution

```yaml
# job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: agentlet-task
spec:
  template:
    spec:
      containers:
      - name: agentlet
        image: synteles/agentlet-core:0.1.0-alpha
        command: ["agentlet-core"]
        args:
          - "--agentlet"
          - "/config/task-agent.yaml"
          - "--prompt"
          - "Process batch task"
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: agentlet-secrets
              key: anthropic-api-key
        volumeMounts:
        - name: config
          mountPath: /config
      restartPolicy: Never
      volumes:
      - name: config
        configMap:
          name: agentlet-config
  backoffLimit: 3
```

## Environment Configuration

### Environment Variables

**Required (choose LLM provider):**
```bash
# Anthropic
export ANTHROPIC_API_KEY="your-key"

# AWS Bedrock
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_REGION="us-east-1"

# OpenAI
export OPENAI_API_KEY="your-key"
```

**Optional:**
```bash
# OpenTelemetry
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer token"

# Debug
export LITELLM_DEBUG="true"  # Enable LiteLLM debug logs
```

### .env File

```bash
# Production .env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...

# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=https://otel.example.com:4318
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer prod-token

# Resource limits
MAX_EXECUTION_TIME=300
MAX_RETRIES=5

# Feature flags
BYPASS_TOOL_CONSENT=true
```

**Location:** Place `.env` in:
- Current directory
- `~/synteles/.env`

## Security Best Practices

### Secret Management

**DO ✅:**
```bash
# Use environment variables
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}"

# Use secret management services
aws secretsmanager get-secret-value --secret-id prod/agentlet/api-keys

# Use Kubernetes secrets
kubectl create secret generic agentlet-secrets \
  --from-literal=anthropic-api-key="$ANTHROPIC_API_KEY"

# Use .env files (add to .gitignore)
echo ".env" >> .gitignore
```

**DON'T ❌:**
```yaml
# Never hardcode secrets in configs
model:
  api_key: "sk-ant-hardcoded-key"  # DON'T DO THIS!

# Never commit .env files
git add .env  # DON'T DO THIS!
```

### API Key Rotation

```bash
# Rotate API keys periodically
# 1. Generate new key
# 2. Update environment variable
# 3. Restart service
# 4. Revoke old key

# Kubernetes secret update
kubectl create secret generic agentlet-secrets \
  --from-literal=anthropic-api-key="new-key" \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart pods to pick up new secret
kubectl rollout restart deployment/agentlet-worker
```

### Network Security

```yaml
# Kubernetes Network Policy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: agentlet-network-policy
spec:
  podSelector:
    matchLabels:
      app: agentlet
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: otel-collector
    ports:
    - protocol: TCP
      port: 4318
  - to:  # Allow LLM API calls
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 443
```

## Health Checks

### Basic Health Check

```python
# health_check.py
import asyncio
from agentlet_core.agents.base import BaseAgentlet
from agentlet_core.config.loader import load_config


async def health_check() -> bool:
    """Check if agentlet is healthy."""
    try:
        config = load_config("health-check.yaml")
        agentlet = BaseAgentlet(config, prompt="ping")

        result = []
        async for event in agentlet.run():
            if "data" in event:
                result.append(event["data"])

        return len(result) > 0
    except Exception:
        return False


if __name__ == "__main__":
    is_healthy = asyncio.run(health_check())
    exit(0 if is_healthy else 1)
```

### Kubernetes Liveness Probe

```yaml
livenessProbe:
  exec:
    command:
    - python
    - /app/health_check.py
  initialDelaySeconds: 30
  periodSeconds: 60
  timeoutSeconds: 30
  failureThreshold: 3
```

### Readiness Probe

```yaml
readinessProbe:
  exec:
    command:
    - python
    - -c
    - "import agentlet_core; print('ready')"
  initialDelaySeconds: 10
  periodSeconds: 5
```

## Monitoring

### Metrics Export

```python
# Export metrics to Prometheus
from prometheus_client import Counter, Histogram, start_http_server

executions_total = Counter(
    'agentlet_executions_total',
    'Total agentlet executions',
    ['agentlet_name', 'status']
)

execution_duration = Histogram(
    'agentlet_execution_duration_seconds',
    'Agentlet execution duration'
)

# Start metrics server
start_http_server(9090)
```

### Kubernetes ServiceMonitor

```yaml
# servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: agentlet-metrics
spec:
  selector:
    matchLabels:
      app: agentlet
  endpoints:
  - port: metrics
    interval: 30s
```

## Scaling

### Horizontal Pod Autoscaler

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agentlet-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: agentlet-worker
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Resource Requests

```yaml
resources:
  requests:
    memory: "512Mi"  # Baseline memory
    cpu: "500m"      # 0.5 CPU cores
  limits:
    memory: "2Gi"    # Max memory (OOM kill if exceeded)
    cpu: "2000m"     # Max CPU (throttled if exceeded)
```

## Production Checklist

- [ ] API keys stored in secret management
- [ ] Environment-specific configs (dev/staging/prod)
- [ ] Resource limits configured
- [ ] Health checks implemented
- [ ] Monitoring and alerting set up
- [ ] Logging configured (JSON format for production)
- [ ] OpenTelemetry enabled with sampling
- [ ] Network policies in place
- [ ] Backups for configs and data
- [ ] Disaster recovery plan
- [ ] Cost tracking enabled
- [ ] Rate limiting configured
- [ ] Security scanning in CI/CD

## Next Steps

- **[Versioning](versioning.md)** - Version management and releases
- **[CI/CD](ci-cd.md)** - Continuous integration and deployment
- **[Monitoring](../observability/monitoring.md)** - Production monitoring best practices
