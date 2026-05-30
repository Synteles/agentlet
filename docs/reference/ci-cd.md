# CI/CD Automation

Continuous Integration and Continuous Deployment for agentlet-core.

## Overview

Agentlet-core uses GitHub Actions for automated testing, building, and releasing.

**Workflows:**
- **pr-checks.yml** - CI pipeline (lint, typecheck, test, security)
- **release.yml** - CD pipeline (build, push to Docker Hub, GitHub Release)

## CI Pipeline (pr-checks.yml)

### Triggers

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

**Runs on:**
- Every push to `main`
- Every pull request to `main`

### Jobs

#### 1. Quality Checks

```yaml
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v1

      # Lint with ruff
      - run: uv run ruff check .

      # Type check with mypy
      - run: uv run mypy agentlet_core

      # Security scan with bandit
      - run: uv run bandit -r agentlet_core/ -ll
```

#### 2. Tests

```yaml
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v1
        with:
          python-version: ${{ matrix.python-version }}

      # Install dependencies
      - run: uv sync --group dev

      # Run tests with coverage
      - run: uv run pytest --cov=agentlet_core --cov-report=xml

      # Upload coverage to Codecov
      - uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

### Required Status Checks

PRs must pass:
- ✅ Linting (ruff)
- ✅ Type checking (mypy)
- ✅ Security scan (bandit)
- ✅ Tests (pytest)
- ✅ Coverage threshold (80%+)

### Branch Protection

**Settings → Branches → main:**
- ✅ Require pull request reviews (1 approver)
- ✅ Require status checks to pass
- ✅ Require conversation resolution
- ✅ Do not allow bypassing

## CD Pipeline (release.yml)

### Triggers

```yaml
on:
  push:
    tags:
      - 'v*'  # Triggers on version tags like v0.2.2
```

**How to trigger:**
```bash
git tag -a v0.3.0 -m "Release v0.3.0"
git push origin v0.3.0
```

### Jobs

#### 1. Quality Gate

Same checks as CI pipeline - ensures release quality.

#### 2. Build Python Package

```yaml
  build:
    runs-on: ubuntu-latest
    needs: quality
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v1

      # Build wheel and source distribution
      - run: uv build

      # Upload artifacts
      - uses: actions/upload-artifact@v3
        with:
          name: dist
          path: dist/
```

**Artifacts created:**
- `agentlet_core-0.3.0-py3-none-any.whl` (wheel)
- `agentlet_core-0.3.0.tar.gz` (source)

#### 3. Build Docker Images

```yaml
  docker-build:
    runs-on: ubuntu-latest
    needs: build
    steps:
      - uses: actions/checkout@v4

      # Set up QEMU for multi-platform builds
      - uses: docker/setup-qemu-action@v3

      # Set up Docker Buildx
      - uses: docker/setup-buildx-action@v3

      # Login to Docker Hub
      - uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      # Extract version from tag
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: synteles/agentlet-core
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=raw,value=latest

      # Build and push multi-platform images
      - uses: docker/build-push-action@v5
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

**Images created:**
- `synteles/agentlet-core:0.3.0` (version tag)
- `synteles/agentlet-core:0.3` (minor version)
- `synteles/agentlet-core:latest` (latest tag)
- Multi-platform: `linux/amd64`, `linux/arm64`

#### 4. Create GitHub Release

```yaml
  github-release:
    runs-on: ubuntu-latest
    needs: [docker-build]
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4

      # Create release with notes
      - uses: softprops/action-gh-release@v1
        with:
          generate_release_notes: true
          files: |
            dist/*.whl
            dist/*.tar.gz
```

**Release includes:**
- Auto-generated release notes from commits
- Wheel file attached as release asset
- Links to Docker images on Docker Hub

## Secrets Management

### Required Secrets

Add these in **GitHub → Settings → Secrets and variables → Actions → Repository secrets**:

| Secret | Description |
|---|---|
| `DOCKERHUB_USERNAME` | Docker Hub username (e.g. `synteles`) |
| `DOCKERHUB_TOKEN` | Docker Hub access token (not your password — generate one at hub.docker.com → Account Settings → Security) |

Both are required for the `release.yml` workflow to push images to Docker Hub. Without them the build-push-docker job will fail.

The `GITHUB_TOKEN` secret used to create GitHub Releases is provided automatically by GitHub Actions — no setup needed.

## Workflow Customization

### Environment Variables

```yaml
env:
  PYTHON_VERSION: "3.13"
  UV_VERSION: "latest"
  COVERAGE_THRESHOLD: 80
```

### Matrix Testing (Multiple Python Versions)

```yaml
strategy:
  matrix:
    python-version: ["3.13", "3.14"]
    os: [ubuntu-latest, macos-latest, windows-latest]

runs-on: ${{ matrix.os }}
steps:
  - uses: astral-sh/setup-uv@v1
    with:
      python-version: ${{ matrix.python-version }}
```

### Conditional Steps

```yaml
# Only run on main branch
- name: Deploy to staging
  if: github.ref == 'refs/heads/main'
  run: ./deploy-staging.sh

# Only run on tags
- name: Deploy to production
  if: startsWith(github.ref, 'refs/tags/v')
  run: ./deploy-production.sh
```

## Local CI Simulation

### Run Checks Locally

```bash
# All checks (same as CI)
make check

# Individual checks
make lint       # Ruff
make typecheck  # Mypy
make security   # Bandit
make test       # Pytest
```

### Act (Run GitHub Actions Locally)

```bash
# Install act
brew install act  # macOS
# or
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run workflow
act push

# Run specific job
act -j quality

# With secrets
act -s DOCKER_PASSWORD=token
```

## Continuous Deployment Strategies

### Option 1: Tag-Based (Current)

**Flow:**
```
Code → PR → Merge → Tag → Release → Deploy
```

**Pros:**
- Manual control over releases
- Explicit versioning
- Test before release

**Cons:**
- Manual tagging required
- Slower release cycle

### Option 2: Automatic Releases

**Flow:**
```
Code → PR → Merge → Auto-Release → Deploy
```

**Implementation:**
```yaml
# On every merge to main, auto-release
on:
  push:
    branches: [main]

jobs:
  auto-release:
    runs-on: ubuntu-latest
    steps:
      # Auto-bump version based on commits
      - uses: cycjimmy/semantic-release-action@v3
        with:
          branches: |
            ['main']
```

**Pros:**
- Fast release cycle
- No manual steps
- Conventional commits drive versioning

**Cons:**
- Less control
- Requires discipline in commit messages

### Option 3: Scheduled Releases

**Flow:**
```
Code → Accumulate → Weekly Release → Deploy
```

**Implementation:**
```yaml
# Release every Monday at 9 AM UTC
on:
  schedule:
    - cron: '0 9 * * 1'
```

**Pros:**
- Predictable release schedule
- Batch multiple changes

**Cons:**
- Delayed releases
- Potential for large changes

## Deployment Environments

### Staging Environment

```yaml
# .github/workflows/deploy-staging.yml
on:
  push:
    branches: [main]

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4
      # Deploy to staging cluster
      - run: kubectl apply -f k8s/staging/
```

### Production Environment

```yaml
# .github/workflows/deploy-production.yml
on:
  push:
    tags: ['v*']

jobs:
  deploy-production:
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      # Deploy to production cluster
      - run: kubectl apply -f k8s/production/
```

**Environment Protection:**
- Settings → Environments → production
- ✅ Required reviewers (2)
- ✅ Wait timer (5 minutes)

## Monitoring CI/CD

### GitHub Actions Insights

**Actions → Insights:**
- Success rate per workflow
- Execution time trends
- Failure patterns

### Notifications

```yaml
# Notify on failure
- name: Notify Slack on failure
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK }}
    payload: |
      {
        "text": "CI failed on ${{ github.repository }}"
      }
```

### Status Badge

Add to README:
```markdown
![CI Status](https://github.com/Synteles/agentlet/workflows/PR%20Checks/badge.svg)
```

## Troubleshooting

### Workflow Fails

**Check logs:**
```
GitHub → Actions → Failed workflow → Click job → View logs
```

**Common issues:**
- Missing secrets
- Environment variables not set
- Dependency installation failures
- Test failures

### Docker Build Fails

**Error:** "No space left on device"

**Solution:**
```yaml
# Add cleanup step
- name: Free disk space
  run: |
    docker system prune -af
    sudo rm -rf /usr/share/dotnet
```

### Multi-Platform Build Slow

**Solution:** Use build cache:
```yaml
cache-from: type=gha
cache-to: type=gha,mode=max
```

## Best Practices

### DO ✅

1. **Pin action versions**
   ```yaml
   uses: actions/checkout@v4  # Not @main
   ```

2. **Use matrix for testing**
   - Test multiple Python versions
   - Test on different OS

3. **Cache dependencies**
   ```yaml
   - uses: actions/cache@v3
     with:
       path: ~/.cache/pip
       key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
   ```

4. **Fail fast**
   ```yaml
   strategy:
     fail-fast: true
   ```

5. **Use secrets for credentials**
   - Never hardcode tokens

### DON'T ❌

1. **Don't commit secrets**
2. **Don't skip tests in CI**
3. **Don't use `always()` without reason**
4. **Don't ignore security warnings**

## Next Steps

- **[Deployment](deployment.md)** - Deploy to production
- **[Versioning](versioning.md)** - Version management
- **[Monitoring](../observability/monitoring.md)** - Monitor CI/CD health
