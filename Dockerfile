# ============================================================
# Builder stage: Build the wheel package
# ============================================================
FROM python:3.13-slim-bookworm AS builder

# Install curl for uv installer
RUN apt update && apt install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# Install uv for building the wheel
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

# Set working directory for build
WORKDIR /build

# Copy only the files needed to build the wheel
COPY agentlet_core ./agentlet_core/
COPY pyproject.toml uv.lock README.md ./

# Build the wheel using uv
# This creates a .whl file in dist/ directory
RUN uv build --wheel

# ============================================================
# Runtime stage: Install wheel and setup runtime environment
# ============================================================
FROM python:3.13-slim-bookworm

ARG NODE_VERSION=25

# Install system dependencies and upgrade patched packages (gnutls CVE-2026-33845/33846/42009/42010/3833)
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates git zip \
 && apt-get upgrade -y --no-install-recommends libgnutls30 \
 && rm -rf /var/lib/apt/lists/*

# Install uv for MCP tools that need uvx
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin:$PATH"

# Install nvm for Node.js (needed for MCP tools)
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash

# Set environment variables
ENV NVM_DIR=/root/.nvm

# Install Node.js using nvm
RUN bash -c "source $NVM_DIR/nvm.sh && nvm install $NODE_VERSION"

# Set ENTRYPOINT for reloading nvm environment
ENTRYPOINT ["bash", "-c", "source $NVM_DIR/nvm.sh && exec \"$@\"", "--"]

# Copy the wheel from builder stage
COPY --from=builder /build/dist/*.whl /tmp/

# Install the wheel system-wide using pip (not uv)
# This makes agentlet-core available globally without .venv
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Install additional document/spreadsheet processing libraries
RUN pip install --no-cache-dir reportlab openpyxl python-docx python-pptx pdfplumber

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Pre-create input/output directories
RUN mkdir -p /tmp/input /tmp/output

# Set working directory
WORKDIR /workspace

# Copy the generic-assistant agentlet config to working directory
COPY examples/generic-assistant.yaml ./generic-assistant.yaml

CMD ["/entrypoint.sh"]