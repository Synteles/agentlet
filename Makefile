.PHONY: help test lint typecheck format security check all clean

# Default target
help:
	@echo "Available targets:"
	@echo "  make test       - Run tests with pytest"
	@echo "  make lint       - Run ruff linting"
	@echo "  make typecheck  - Run mypy type checking"
	@echo "  make security   - Run bandit security checks"
	@echo "  make format     - Format code with ruff"
	@echo "  make check      - Run all checks (lint + typecheck + security + test)"
	@echo "  make all        - Same as check"
	@echo "  make clean      - Remove cache files and build artifacts"

# Run tests with pytest
test:
	uv run pytest

# Run ruff linting
lint:
	uv run ruff check .

# Run mypy type checking
typecheck:
	uv run mypy agentlet_core

# Format code with ruff
format:
	uv run ruff format .

# Run bandit security checks
security:
	uv run bandit -r agentlet_core/ -ll

# Run all checks
check: lint typecheck security test

# Alias for check
all: check

# Clean up cache files and build artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
