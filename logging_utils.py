#!/usr/bin/env python3
"""
Advanced logging utilities for CCGLM-MCP server
Provides dual logging: stderr (human-readable) + JSONL file (structured)
"""

import json
import logging
import logging.handlers
import os
import re
import hashlib
import time
import uuid
import threading
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional
from queue import Queue


class SafeJSONFormatter(logging.Formatter):
    """
    JSON formatter that sanitizes sensitive data and truncates long fields
    """

    def __init__(self, max_preview_len: int = 512, max_trace_len: int = 4000):
        super().__init__()
        self.max_preview_len = max_preview_len
        self.max_trace_len = max_trace_len

        # Patterns to redact sensitive information
        self.sensitive_patterns = [
            (re.compile(r'(token|api[_-]?key|secret|authorization|password|bearer)[\'"\s]*[:=][\'"\s]*([a-zA-Z0-9_-]+)', re.IGNORECASE), '***REDACTED***'),
            (re.compile(r'GLM_AUTH_TOKEN[\'"\s]*[:=][\'"\s]*([a-zA-Z0-9._-]+)', re.IGNORECASE), 'GLM_AUTH_TOKEN=***REDACTED***'),
        ]

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON line"""
        try:
            # Create base log entry
            log_entry = {
                "ts": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "level": record.levelname,
                "logger": record.name,
            }

            # Add structured data if present in record.__dict__
            if hasattr(record, 'event'):
                log_entry['event'] = record.event

            # Add standard fields if present
            for field in ['request_id', 'session_id', 'instance_id', 'tool', 'method',
                         'prompt_preview', 'prompt_sha256', 'response_preview', 'latency_ms',
                         'exit_code', 'files_created', 'files_modified', 'new_files',
                         'modified_files', 'stderr_preview', 'model', 'transport',
                         'pid', 'error_type', 'error_message', 'traceback', 'cmd_preview', 'cwd']:
                if hasattr(record, field):
                    log_entry[field] = getattr(record, field)

            # Handle message field
            if hasattr(record, 'msg') and record.msg:
                if isinstance(record.msg, dict):
                    # If msg is already a dict, merge it
                    log_entry.update(record.msg)
                else:
                    # If msg is a string, add as message field
                    log_entry['message'] = str(record.msg)

            # Sanitize sensitive data
            log_entry = self._sanitize_dict(log_entry)

            # Truncate long fields
            log_entry = self._truncate_fields(log_entry)

            return json.dumps(log_entry, ensure_ascii=False, default=str)

        except Exception as e:
            # Fallback to simple format if JSON formatting fails
            return json.dumps({
                "ts": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "level": "ERROR",
                "logger": "ccglm-mcp",
                "event": "format_error",
                "error": f"Failed to format log: {str(e)}",
                "original_message": str(record.msg) if hasattr(record, 'msg') else ""
            }, ensure_ascii=False)

    def _sanitize_dict(self, data: Any) -> Any:
        """Recursively sanitize dictionary values"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                # Check if key name looks sensitive
                if any(pattern[0].search(key) for pattern in self.sensitive_patterns):
                    sanitized[key] = "***REDACTED***"
                else:
                    sanitized[key] = self._sanitize_dict(value)
            return sanitized
        elif isinstance(data, (list, tuple)):
            return [self._sanitize_dict(item) for item in data]
        elif isinstance(data, str):
            # Check for sensitive patterns in string values
            for pattern, replacement in self.sensitive_patterns:
                data = pattern.sub(replacement, data)
            return data
        else:
            return data

    def _truncate_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Truncate long text fields"""
        truncated = data.copy()

        # Text fields to truncate
        text_fields = ['prompt_preview', 'response_preview', 'stderr_preview', 'message']
        for field in text_fields:
            if field in truncated and isinstance(truncated[field], str):
                if len(truncated[field]) > self.max_preview_len:
                    truncated[field] = truncated[field][:self.max_preview_len] + "...[TRUNCATED]"

        # Traceback field
        if 'traceback' in truncated and isinstance(truncated['traceback'], str):
            if len(truncated['traceback']) > self.max_trace_len:
                truncated['traceback'] = truncated['traceback'][:self.max_trace_len] + "...[TRUNCATED]"

        # Limit array sizes
        array_fields = ['new_files', 'modified_files']
        for field in array_fields:
            if field in truncated and isinstance(truncated[field], (list, tuple)):
                if len(truncated[field]) > 10:
                    truncated[field] = list(truncated[field][:10]) + [f"...and {len(truncated[field]) - 10} more"]

        return truncated


def hash_text(text: str) -> str:
    """Calculate SHA256 hash of text for correlation without exposing content"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


class CCGLMLogger:
    """Enhanced logger with dual sinks (stderr + JSONL file)"""

    def __init__(self, name: str = "ccglm-mcp"):
        self.name = name
        self.instance_id = str(uuid.uuid4())
        self.pid = os.getpid()
        self.session_id = os.getenv('CLAUDE_SESSION')

        # Determine log directory and file path
        self.log_dir = self._get_log_directory()
        self.log_file = self._get_log_file_path()

        # Setup logging infrastructure
        self.logger = self._setup_logging()

        # Log startup
        self.logger.info({
            "event": "startup",
            "log_file": str(self.log_file),
            "log_dir": str(self.log_dir)
        })

    def _get_log_directory(self) -> Path:
        """Determine log directory based on environment variables"""
        # Priority: CCGLM_MCP_LOG_PATH > CCGLM_MCP_LOG_DIR > CLAUDE_LOG_DIR > ~/.claude/logs
        if os.getenv('CCGLM_MCP_LOG_PATH'):
            return Path(os.getenv('CCGLM_MCP_LOG_PATH')).parent

        log_dir = (
            os.getenv('CCGLM_MCP_LOG_DIR') or
            os.getenv('CLAUDE_LOG_DIR') or
            Path.home() / '.claude' / 'logs'
        )

        return Path(log_dir)

    def _get_log_file_path(self) -> Path:
        """Determine log file path"""
        # Check if full path is specified
        if os.getenv('CCGLM_MCP_LOG_PATH'):
            return Path(os.getenv('CCGLM_MCP_LOG_PATH'))

        # Determine per-process logging
        per_process = os.getenv('CCGLM_MCP_PER_PROCESS_LOGS', 'true').lower() == 'true'

        if per_process:
            filename = f"ccglm-mcp-{self.pid}.jsonl"
        else:
            filename = "ccglm-mcp.jsonl"

        return self.log_dir / filename

    def _setup_logging(self) -> logging.Logger:
        """Setup dual logging infrastructure"""
        logger = logging.getLogger(self.name)
        logger.setLevel(logging.INFO)

        # Clear any existing handlers
        logger.handlers.clear()

        # Determine log level from environment
        log_level = os.getenv('CCGLM_MCP_LOG_LEVEL', 'INFO').upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))

        # Create log directory if it doesn't exist
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Fallback to local logs directory
            fallback_dir = Path.cwd() / 'logs'
            fallback_dir.mkdir(exist_ok=True)
            self.log_dir = fallback_dir
            self.log_file = fallback_dir / self.log_file.name

        # Setup queue for non-blocking logging
        self.log_queue = Queue(maxsize=10000)
        queue_handler = logging.handlers.QueueHandler(self.log_queue)

        # Setup file handler with JSON formatter
        try:
            file_handler = RotatingFileHandler(
                self.log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                delay=True,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(SafeJSONFormatter())

            # Setup stderr handler with human-readable format
            stderr_handler = logging.StreamHandler()
            stderr_handler.setLevel(logging.INFO)
            stderr_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            stderr_handler.setFormatter(stderr_formatter)

            # Setup queue listener
            self.queue_listener = logging.handlers.QueueListener(
                self.log_queue,
                file_handler,
                stderr_handler,
                respect_handler_level=True
            )
            self.queue_listener.start()

            # Add queue handler to logger
            logger.addHandler(queue_handler)
            logger.propagate = False

        except Exception as e:
            # Fallback to basic stderr logging only
            print(f"Warning: Failed to setup file logging: {e}")
            basic_handler = logging.StreamHandler()
            basic_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            logger.addHandler(basic_handler)

        return logger

    def create_request_context(self, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create request context with sanitized data"""
        request_id = str(uuid.uuid4())
        prompt = args.get('prompt', '')

        return {
            "request_id": request_id,
            "session_id": self.session_id,
            "instance_id": self.instance_id,
            "tool": tool,
            "method": "call_tool",
            "pid": self.pid,
            "prompt_preview": prompt[:self.max_preview_len] if hasattr(self, 'max_preview_len') else prompt[:512],
            "prompt_sha256": hash_text(prompt) if prompt else None,
            "args": self._sanitize_args(args)
        }

    def _sanitize_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize function arguments"""
        sanitized = args.copy()
        if 'prompt' in sanitized:
            prompt = sanitized['prompt']
            if len(prompt) > 512:
                sanitized['prompt'] = prompt[:512] + "...[TRUNCATED]"
        return sanitized

    def log_request(self, context: Dict[str, Any]) -> None:
        """Log request event"""
        log_data = {
            "event": "request",
            **context
        }
        self.logger.info(log_data)

    def log_response(self, context: Dict[str, Any], result: Dict[str, Any],
                     start_time: float) -> None:
        """Log response event"""
        latency_ms = (time.perf_counter() - start_time) * 1000

        log_data = {
            "event": "response",
            **context,
            "latency_ms": round(latency_ms, 2),
            "model": result.get('model', 'glm-4.6'),
            "response_preview": str(result.get('response', ''))[:512],
            "files_created": result.get('files_created', 0),
            "files_modified": result.get('files_modified', 0),
            "new_files": result.get('new_files', [])[:10],
            "modified_files": result.get('modified_files', [])[:10]
        }

        if 'error' in result:
            log_data['error_type'] = 'MCPError'
            log_data['error_message'] = result['error']

        self.logger.info(log_data)

    def log_error(self, context: Dict[str, Any], error: Exception,
                  start_time: float) -> None:
        """Log error event"""
        latency_ms = (time.perf_counter() - start_time) * 1000

        log_data = {
            "event": "error",
            **context,
            "latency_ms": round(latency_ms, 2),
            "error_type": type(error).__name__,
            "error_message": str(error)
        }

        # Add traceback if available
        import traceback
        log_data['traceback'] = traceback.format_exc()

        self.logger.error(log_data, exc_info=False)

    def log_process_event(self, context: Dict[str, Any], step: str,
                         cmd_preview: str = None, cwd: str = None, **kwargs) -> None:
        """Log subprocess process events"""
        log_data = {
            "event": "process",
            **context,
            "step": step
        }

        if cmd_preview:
            log_data['cmd_preview'] = cmd_preview
        if cwd:
            log_data['cwd'] = cwd

        log_data.update(kwargs)

        self.logger.info(log_data)

    def shutdown(self) -> None:
        """Graceful shutdown"""
        try:
            self.logger.info({
                "event": "shutdown",
                "instance_id": self.instance_id,
                "pid": self.pid
            })

            # Stop queue listener if it exists
            if hasattr(self, 'queue_listener'):
                self.queue_listener.stop()

        except Exception:
            pass  # Ignore errors during shutdown


# Global logger instance
_ccglm_logger = None

def get_logger() -> CCGLMLogger:
    """Get or create global CCGLM logger instance"""
    global _ccglm_logger
    if _ccglm_logger is None:
        _ccglm_logger = CCGLMLogger()
    return _ccglm_logger