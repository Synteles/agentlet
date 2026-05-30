# Debugging Guide

Advanced debugging techniques for agentlet-core development.

## Debug Mode

### Enable Debug Logging

```bash
# Run with --debug flag
agentlet-core --agentlet my-agent.yaml --prompt "Hello" --debug
```

**Debug mode provides:**
- DEBUG level logs to console
- Log file: `agentlet-core-{timestamp}.log`
- SDK internal logs (litellm, strands, botocore)
- Verbose error messages with stack traces
- Tool call details
- Token usage tracking

### Debug Output Example

```
🐛 [DEBUG] Loading configuration from: my-agent.yaml
🐛 [DEBUG] Initializing MCP tools manager
🐛 [DEBUG] Starting stdio server: npx -y @modelcontextprotocol/server-filesystem
ℹ  [INFO]  Spawning agentlet 'my-agent'
🐛 [DEBUG] Creating LiteLLM model: anthropic/claude-sonnet-4-6
🐛 [DEBUG] Agent created with 3 default tools + 5 MCP tools
ℹ  [INFO]  Using model: anthropic/claude-sonnet-4-6
🐛 [DEBUG] Streaming agent response...
```

## Log File Analysis

### Log File Location

```bash
# Log file created in current directory
ls -l agentlet-core-*.log

# Example filename
agentlet-core-2025-01-30T14-30-00.log
```

### Log File Contents

**Standard logs:**
```
2025-01-30 14:30:00 | INFO  | synteles.agentlet.agents.base | Spawning agentlet 'my-agent'
2025-01-30 14:30:01 | DEBUG | synteles.agentlet.agents.base | Created execution context: 550e8400-e29b-41d4-a716-446655440000
2025-01-30 14:30:01 | INFO  | synteles.agentlet.agents.base | Using model: anthropic/claude-sonnet-4-6
```

**With JSON format:**
```json
{
  "timestamp": "2025-01-30T14:30:00.123456+00:00",
  "level": "DEBUG",
  "logger": "synteles.agentlet.agents.base",
  "message": "Created execution context",
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "agentlet": "my-agent"
}
```

### Searching Logs

```bash
# Find errors
grep "ERROR" agentlet-core-*.log

# Find specific execution
grep "550e8400" agentlet-core-*.log

# Find tool calls
grep "Tool call:" agentlet-core-*.log

# Find API errors
grep "RateLimitError\|APIConnectionError" agentlet-core-*.log

# Show context around error
grep -A 5 -B 5 "ERROR" agentlet-core-*.log
```

## Common Issues

### Configuration Issues

**Error:** Configuration not found

```bash
# Enable debug to see search paths
agentlet-core --agentlet my-agent --debug

# Output shows search locations:
# 🐛 Searching for config: ./my-agent.yaml
# 🐛 Searching for config: ~/.synteles/agentlets/my-agent.yaml
# 🐛 Searching for config: ./.synteles/agentlets/my-agent.yaml
```

**Solution:** Check file exists in search paths or use absolute path.

---

**Error:** Pydantic validation error

```python
ValidationError: 1 validation error for AgentletConfig
model.provider
  field required (type=value_error.missing)
```

**Debug:**
```bash
# Check config with verbose errors
python -c "
from agentlet_core.config.loader import load_config
config = load_config('my-agent.yaml')
print(config)
"
```

**Solution:** Fix missing required fields in config.

### LLM API Issues

**Error:** API key not found

```bash
ERROR: ANTHROPIC_API_KEY not found in environment
```

**Debug:**
```bash
# Check environment variables
env | grep API_KEY

# Check .env file loading
agentlet-core --agentlet my-agent --debug 2>&1 | grep "Loading .env"
```

**Solution:** Set API key in environment or `.env` file.

---

**Error:** Rate limit exceeded

```
RateLimitError: Rate limit exceeded. Retry after 30 seconds.
```

**Debug:**
```bash
# Enable debug to see retry logic
agentlet-core --agentlet my-agent --debug

# Output shows retry attempts:
# ⚠  [WARNING] Rate limit hit, retrying in 30.0 seconds (attempt 1/5)
# ⚠  [WARNING] Rate limit hit, retrying in 60.0 seconds (attempt 2/5)
```

**Solution:** Adjust retry settings or reduce request rate.

### MCP Tools Issues

**Error:** Command not found for MCP stdio tool

```
ERROR: Command not found: npx
```

**Debug:**
```bash
# Check command availability
which npx

# Try with absolute path
agentlet-core --agentlet my-agent.yaml --debug
```

**Solution:** Install Node.js or use absolute path in config.

---

**Error:** MCP process hangs

```bash
# Process doesn't terminate
ps aux | grep npx
```

**Debug:**
```bash
# Enable debug to see cleanup
agentlet-core --agentlet my-agent --debug

# Output shows cleanup process:
# 🐛 [DEBUG] Terminating MCP stdio process (PID: 12345)
# 🐛 [DEBUG] Sent SIGTERM to process 12345
# 🐛 [DEBUG] Sent SIGKILL to process 12345
```

**Solution:** Check MCP server implementation handles SIGTERM correctly.

### Tool Call Issues

**Error:** Tool not found

```
ERROR: Tool 'read_file' not available
```

**Debug:**
```bash
# List available tools in debug mode
agentlet-core --agentlet my-agent --debug 2>&1 | grep "tools available"

# Output:
# 🐛 [DEBUG] 8 tools available: bash, file_editor, fs_read_file, fs_write_file, ...
```

**Solution:** Check tool_filters and prefix configuration.

## Python Debugger

### Using breakpoint()

**Add to code:**
```python
# agentlet_core/agents/base.py
async def spawn(self) -> None:
    """Spawn the agentlet."""
    breakpoint()  # Execution stops here
    self.logger.info(f"Spawning agentlet '{self.config.agentlet.name}'")
    ...
```

**Run:**
```bash
python -m agentlet_core.cli.main --agentlet my-agent.yaml --prompt "Hello"

# Debugger starts:
> /path/to/base.py(187)spawn()
-> self.logger.info(f"Spawning agentlet '{self.config.agentlet.name}'")
(Pdb)
```

**Debugger commands:**
```
(Pdb) l         # List source code
(Pdb) n         # Next line
(Pdb) s         # Step into
(Pdb) c         # Continue
(Pdb) p var     # Print variable
(Pdb) pp obj    # Pretty-print object
(Pdb) w         # Where (stack trace)
(Pdb) h         # Help
(Pdb) q         # Quit
```

### Using pdb

```python
import pdb

# Set trace manually
pdb.set_trace()

# Conditional breakpoint
if error_count > 5:
    pdb.set_trace()
```

## VSCode Debugging

### Launch Configuration

`.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug Agentlet",
      "type": "python",
      "request": "launch",
      "module": "agentlet_core.cli.main",
      "args": [
        "--agentlet", "examples/simple-assistant.yaml",
        "--prompt", "Hello",
        "--debug"
      ],
      "console": "integratedTerminal",
      "justMyCode": false,
      "env": {
        "ANTHROPIC_API_KEY": "${env:ANTHROPIC_API_KEY}",
        "PYTHONPATH": "${workspaceFolder}"
      }
    },
    {
      "name": "Debug Current Test",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["-v", "-s", "${file}::${selectedText}"],
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

### Setting Breakpoints

1. Click left margin to add breakpoint (red dot)
2. Press F5 to start debugging
3. Use debug toolbar to step through code
4. Inspect variables in debug panel

### Watch Expressions

Add watch expressions to track values:
```
self.config.agentlet.name
len(self.context.tool_calls)
self.context.execution_id
```

## Remote Debugging

### debugpy Setup

```bash
# Install debugpy
pip install debugpy

# Add to code
import debugpy
debugpy.listen(5678)
print("Waiting for debugger...")
debugpy.wait_for_client()
```

### Connect from VSCode

```json
{
  "name": "Attach to Remote",
  "type": "python",
  "request": "attach",
  "connect": {
    "host": "localhost",
    "port": 5678
  }
}
```

## Performance Profiling

### Time Profiling

```python
import time


class ProfilingContext:
    """Profile execution time."""

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        duration = time.time() - self.start
        print(f"Duration: {duration:.2f}s")


# Usage
with ProfilingContext():
    expensive_operation()
```

### cProfile

```bash
# Profile execution
python -m cProfile -o profile.stats -m agentlet_core.cli.main \
  --agentlet my-agent.yaml --prompt "Hello"

# Analyze results
python -m pstats profile.stats

# In pstats shell:
stats> sort cumulative
stats> stats 20  # Show top 20 functions
stats> quit
```

### line_profiler

```bash
# Install
pip install line_profiler

# Add @profile decorator to function
# Then run:
kernprof -l -v script.py
```

## Memory Profiling

### memory_profiler

```bash
# Install
pip install memory-profiler

# Add @profile decorator
from memory_profiler import profile

@profile
def my_function():
    ...

# Run
python -m memory_profiler script.py
```

### Track Object Creation

```python
import tracemalloc

tracemalloc.start()

# Your code here
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

for stat in top_stats[:10]:
    print(stat)
```

## Network Debugging

### HTTP Requests

```bash
# Enable HTTP debugging
export HTTPX_LOG_LEVEL=DEBUG

# Or in code
import logging
logging.basicConfig(level=logging.DEBUG)
```

### MCP Protocol Debugging

```bash
# Capture MCP server output
agentlet-core --agentlet my-agent --debug 2>&1 | grep "MCP"
```

## Async Debugging

### AsyncIO Debug Mode

```bash
# Enable asyncio debug mode
PYTHONASYNCIODEBUG=1 agentlet-core --agentlet my-agent --debug
```

### Track Pending Tasks

```python
import asyncio


# Show pending tasks
tasks = asyncio.all_tasks()
print(f"Pending tasks: {len(tasks)}")
for task in tasks:
    print(f"  {task.get_name()}: {task}")
```

## Testing Debugging

### Run Single Test with Debugger

```bash
# VSCode: Click debug icon next to test
# Or use launch config for pytest

# Command line with pdb
python -m pytest --pdb tests/unit/test_config.py::test_model_config
```

### Show Test Output

```bash
# Show print statements
pytest -s tests/unit/test_config.py

# Show log output
pytest --log-cli-level=DEBUG tests/unit/test_config.py
```

## Environment Debugging

### Check Environment

```bash
# Python version
python --version

# Package versions
pip list | grep agentlet
pip list | grep strands
pip list | grep litellm

# Environment variables
env | grep -E "(API_KEY|AWS|ANTHROPIC|OPENAI)"
```

### Dependency Conflicts

```bash
# Check for conflicts
pip check

# Show dependency tree
pip install pipdeptree
pipdeptree -p agentlet-core
```

## Best Practices

### DO ✅

1. **Use debug mode first**
   ```bash
   agentlet-core --agentlet my-agent --debug
   ```

2. **Check logs before code**
   - Often reveals the issue immediately

3. **Isolate the problem**
   - Minimal reproduction case
   - Remove unnecessary complexity

4. **Use type hints**
   - Helps catch errors early with mypy

5. **Write tests**
   - Easier to debug in isolation

### DON'T ❌

1. **Don't debug in production**
   - Use separate dev environment

2. **Don't commit debug code**
   - Remove `breakpoint()` and `print()` statements

3. **Don't ignore warnings**
   - Warnings often indicate real issues

4. **Don't guess**
   - Use debugger to verify assumptions

## Getting Help

If stuck, provide:

1. **Full error message** with stack trace
2. **Debug logs** (use `--debug`)
3. **Configuration file** (redact secrets)
4. **Python version** and dependencies
5. **Steps to reproduce**

**Where to ask:**
- GitHub Issues (bugs)
- GitHub Discussions (questions)

## Next Steps

- **[Testing Guide](testing.md)** - Write better tests
- **[Development Setup](setup.md)** - Environment setup
- **[Contributing](contributing.md)** - Contribution guidelines
