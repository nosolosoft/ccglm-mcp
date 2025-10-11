# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

CCGLM MCP Server is an MCP (Model Context Protocol) server that enables Claude Code to route requests to Z.AI's GLM models (GLM-4.6 and GLM-4.5-air) through the Claude CLI. This creates a hybrid system where the main Claude Code instance can delegate tasks to GLM models while maintaining the primary Sonnet backend.

## Architecture

The system follows this flow:
```
Claude Code (Sonnet) → MCP Tool → CCGLM Server → Claude CLI → Z.AI GLM API
```

**Key Components:**
- `ccglm_mcp_server.py` - Main MCP server implementation
- `logging_utils.py` - Advanced logging with JSONL structured output
- `test_server.py` - Test suite for validation
- `.env` - Contains GLM API credentials (gitignored)

## Common Development Commands

### Running Tests
```bash
# Run all tests
python3 test_server.py

# Run specific test categories
python3 test_server.py  # Tests are configured to skip API calls by default
```

### Server Operations
```bash
# Start MCP server manually (for debugging)
python3 ccglm_mcp_server.py

# View real-time logs
python3 ccglm_mcp_server.py 2>&1 | grep -i glm

# Check log files (JSONL format)
tail -f ~/.claude/logs/ccglm-mcp-*.jsonl
```

### Dependencies
```bash
# Install dependencies
pip install -r requirements.txt

# Required packages: mcp>=1.0.0, python-dotenv>=1.0.0
```

## Model Selection

The server supports two GLM models:
- `glm-4.6` (default) - Full capability model for complex tasks
- `glm-4.5-air` - Fast model for quick responses

Model selection is done via the `model` parameter in the `glm_route` tool.

## File Tracking System

The server implements automatic file creation tracking:
- Scans working directory before/after GLM execution
- Excludes internal directories (`.claude/`, `.git/`, `node_modules/`, etc.)
- Returns formatted summary of created files
- Limited to first 10 files in response to prevent overwhelming output

## Logging Infrastructure

Dual logging system:
- **stderr**: Human-readable logs for immediate feedback
- **JSONL files**: Structured logs for analysis and debugging

**Log location**: `~/.claude/logs/ccglm-mcp-{pid}.jsonl` (per-process) or `ccglm-mcp.jsonl` (shared)

**Environment variables for logging:**
- `CCGLM_MCP_LOG_LEVEL` - Set log level (INFO/WARNING/ERROR)
- `CCGLM_MCP_LOG_PATH` - Full path to log file
- `CCGLM_MCP_LOG_DIR` - Directory for logs
- `CCGLM_MCP_PER_PROCESS_LOGS` - Enable/disable per-process logs

## Security Features

- Token sanitization in logs (automatic redaction)
- Chinese language detection and blocking (GLM-4.6 optimized for Spanish/English)
- Environment variable isolation (credentials only in subprocess)
- `.env` file protection (gitignored, should have 0600 permissions)

## Timeout Configuration

- `DEFAULT_TIMEOUT = 300` seconds (5 minutes)
- `MAX_TIMEOUT = 1800` seconds (30 minutes)
- Configurable in `ccglm_mcp_server.py:40-41`

## Language Restrictions

The server automatically detects and blocks Chinese language prompts, as GLM-4.6 is optimized for Spanish and English languages. This is implemented in the `contains_chinese()` function.

## Claude CLI Integration

The server executes Claude CLI with specific flags:
```bash
claude --dangerously-skip-permissions -c -p
```
- `--dangerously-skip-permissions`: Bypass permission prompts
- `-c`: Continue mode
- `-p`: Print mode (non-interactive)

## Environment Setup

Required environment variables (in `.env`):
- `GLM_BASE_URL=https://api.z.ai/api/anthropic`
- `GLM_AUTH_TOKEN=<your-token>`

The server injects these into the Claude CLI subprocess environment as `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN`.

## Error Handling

- Graceful handling of Claude CLI not found
- Timeout management with process cleanup
- File permission error recovery
- Comprehensive error logging with context
- Performance alerts for slow responses (>60s warning, >30s moderate)

## Performance Monitoring

The server tracks:
- Execution time per request
- File creation counts
- Response lengths
- Model performance vs expectations
- Exit codes and stderr output

Performance alerts are automatically generated for unusual response times, especially for the fast `glm-4.5-air` model.