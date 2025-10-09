#!/usr/bin/env python3
"""
Test script for CCGLM-MCP logging system
Validates dual logging, JSONL formatting, sanitization, and multi-process support
"""

import asyncio
import json
import logging
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, Any

# Import the logging utilities
from logging_utils import CCGLMLogger, SafeJSONFormatter, get_logger

def test_json_formatter():
    """Test SafeJSONFormatter with various data types"""
    print("🧪 Testing SafeJSONFormatter...")

    formatter = SafeJSONFormatter(max_preview_len=50, max_trace_len=100)

    # Create test log record
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None
    )

    # Add structured data
    record.event = "test_event"
    record.request_id = str(uuid.uuid4())
    record.prompt_preview = "This is a very long test prompt that should definitely be truncated because it exceeds the maximum length of 50 characters that we set for the preview"
    record.GLM_AUTH_TOKEN = "sensitive_token_12345"
    record.traceback = "A" * 500  # Long traceback

    # Format and parse
    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    # Validate
    assert parsed['event'] == "test_event"
    assert parsed['level'] == "INFO"
    assert 'sensitive_token_12345' not in formatted  # Should be redacted
    assert parsed['prompt_preview'].endswith("...[TRUNCATED]")
    assert parsed['traceback'].endswith("...[TRUNCATED]")

    print("✅ SafeJSONFormatter test passed")

def test_ccglm_logger():
    """Test CCGLMLogger initialization and basic functionality"""
    print("🧪 Testing CCGLMLogger...")

    # Create logger in temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ['CCGLM_MCP_LOG_DIR'] = temp_dir
        os.environ['CCGLM_MCP_PER_PROCESS_LOGS'] = 'true'

        logger = CCGLMLogger("test-ccglm")

        # Test basic logging
        logger.logger.info("Test message")

        # Give queue time to process
        time.sleep(0.1)

        # Test request/response tracking
        context = logger.create_request_context("test_tool", {"prompt": "test prompt"})
        logger.log_request(context)

        result = {"response": "test response", "files_created": 2}
        logger.log_response(context, result, time.perf_counter())

        # Test process event logging
        logger.log_process_event(context, "spawn", cmd_preview="test command")

        # Give queue time to process all events
        time.sleep(0.2)

        # Check log file was created
        log_file = logger.log_file
        assert log_file.exists(), f"Log file not created: {log_file}"

        # Read and validate log content
        with open(log_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) >= 4  # startup + request + response + process

            # Validate JSON structure
            for line in lines:
                json.loads(line)  # Should not raise exception

        print(f"✅ CCGLMLogger test passed - created {len(lines)} log entries")

def test_sanitization():
    """Test data sanitization"""
    print("🧪 Testing data sanitization...")

    formatter = SafeJSONFormatter()

    # Test sensitive data in string values (where regex patterns work)
    sensitive_string = "api_key=sk-123456789&GLM_AUTH_TOKEN=token_abc123&password=secret123"

    # Create log record with sensitive string as message
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg=sensitive_string,
        args=(),
        exc_info=None
    )

    formatted = formatter.format(record)
    formatted_str = str(formatted)

    # Check sanitization in strings
    assert "sk-123456789" not in formatted_str  # Should be redacted
    assert "token_abc123" not in formatted_str   # Should be redacted
    assert "secret123" not in formatted_str      # Should be redacted
    assert "***REDACTED***" in formatted_str     # Should contain redaction marker

    # Test with supported fields that trigger sanitization
    record2 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None
    )

    # Add supported fields that get sanitized
    record2.prompt_preview = "This contains API_KEY=sk-123456789 sensitive data"
    record2.response_preview = "Authorization: Bearer token_abc123"
    record2.message = "GLM_AUTH_TOKEN=token_abc123&other=data"

    formatted2 = formatter.format(record2)
    formatted_str2 = str(formatted2)

    # Check that sensitive data is redacted in supported fields
    assert "sk-123456789" not in formatted_str2  # Should be redacted from prompt_preview
    assert "Authorization:" not in formatted_str2  # Should be redacted from response_preview
    assert "GLM_AUTH_TOKEN=token_abc123" not in formatted_str2  # Should be redacted from message

    print("✅ Sanitization test passed")

def test_multi_process_logging():
    """Test multi-process logging support (simulated)"""
    print("🧪 Testing multi-process logging simulation...")

    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ['CCGLM_MCP_LOG_DIR'] = temp_dir
        os.environ['CCGLM_MCP_PER_PROCESS_LOGS'] = 'true'

        # Test that per-process logging creates files with PID in name
        logger = CCGLMLogger("test-process")

        # Log file should contain PID
        log_file = logger.log_file
        expected_pid = str(os.getpid())
        assert expected_pid in log_file.name, f"PID {expected_pid} not in log filename: {log_file}"

        # Log something
        logger.logger.info("Test message for multi-process")

        # Give queue time to process
        time.sleep(0.1)

        # Verify file exists and contains our message
        assert log_file.exists(), f"Log file not created: {log_file}"
        with open(log_file, 'r') as f:
            content = f.read()
            assert "Test message for multi-process" in content

        # Test with per-process disabled
        os.environ['CCGLM_MCP_PER_PROCESS_LOGS'] = 'false'
        logger2 = CCGLMLogger("test-single")
        logger2.logger.info("Single process test")
        time.sleep(0.1)
        log_file2 = logger2.log_file
        assert expected_pid not in log_file2.name, f"PID should not be in single log filename: {log_file2}"
        assert log_file2.exists(), f"Single process log file not created: {log_file2}"

        print("✅ Multi-process logging simulation test passed")

def test_queue_performance():
    """Test logging performance with queue handler"""
    print("🧪 Testing queue performance...")

    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ['CCGLM_MCP_LOG_DIR'] = temp_dir
        os.environ['CCGLM_MCP_PER_PROCESS_LOGS'] = 'false'

        logger = CCGLMLogger("performance-test")

        # Log many messages quickly
        start_time = time.time()
        message_count = 1000

        for i in range(message_count):
            logger.logger.info(f"Performance test message {i}")

        # Give queue time to process
        time.sleep(0.5)

        end_time = time.time()
        duration = end_time - start_time
        messages_per_second = message_count / duration

        # Check log file
        log_file = logger.log_file
        with open(log_file, 'r') as f:
            lines = f.readlines()

        # Should have startup + message_count
        assert len(lines) >= message_count

        print(f"✅ Queue performance test passed: {messages_per_second:.0f} messages/second")

def main():
    """Run all tests"""
    print("🚀 Starting CCGLM-MCP logging tests...")

    try:
        test_json_formatter()
        test_sanitization()
        test_ccglm_logger()
        test_multi_process_logging()
        test_queue_performance()

        print("\n🎉 All logging tests passed!")
        return 0

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())