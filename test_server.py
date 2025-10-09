#!/usr/bin/env python3
"""
Test script for CCGLM MCP Server
"""

import asyncio
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_basic_prompt():
    """Test basic GLM routing with simple prompt"""
    print("=" * 60)
    print("TEST 1: Basic GLM Route")
    print("=" * 60)

    from ccglm_mcp_server import glm_route

    args = {"prompt": "What is 2+2? Answer briefly."}
    result = await glm_route(args)

    print(f"Success: {result.get('success', False)}")
    print(f"Model: {result.get('model', 'unknown')}")
    print(f"Execution time: {result.get('execution_time', 0)}s")
    print(f"Response preview: {result.get('response', '')[:200]}...")

    assert result.get('success'), "GLM route should succeed"
    assert '4' in result.get('response', '').lower() or 'four' in result.get('response', '').lower(), "Should contain answer"

    print("✅ Test 1 PASSED\n")


async def test_code_generation():
    """Test code generation with GLM"""
    print("=" * 60)
    print("TEST 2: Code Generation")
    print("=" * 60)

    from ccglm_mcp_server import glm_route

    args = {"prompt": "Write a Python function to add two numbers. Just the code, no explanation."}
    result = await glm_route(args)

    print(f"Success: {result.get('success', False)}")
    print(f"Files created: {result.get('files_created', 0)}")
    print(f"Response preview: {result.get('response', '')[:200]}...")

    assert result.get('success'), "GLM code should succeed"

    print("✅ Test 2 PASSED\n")


async def test_file_tracking():
    """Test file creation tracking"""
    print("=" * 60)
    print("TEST 3: File Tracking")
    print("=" * 60)

    from ccglm_mcp_server import get_current_files, detect_new_files

    # Get initial files
    files_before = get_current_files(".")
    print(f"Files before: {len(files_before)}")

    # Create a test file
    test_file = "test_file_tracking.txt"
    with open(test_file, "w") as f:
        f.write("test content")

    # Get files after
    files_after = get_current_files(".")
    print(f"Files after: {len(files_after)}")

    # Detect new files
    new_files = detect_new_files(files_before, files_after)
    print(f"New files detected: {new_files}")

    # Cleanup
    os.remove(test_file)

    # Check if file is in new_files (may have ./ prefix)
    assert any(test_file in f for f in new_files), f"Should detect {test_file}"

    print("✅ Test 3 PASSED\n")


async def test_sanitization():
    """Test log sanitization"""
    print("=" * 60)
    print("TEST 4: Log Sanitization")
    print("=" * 60)

    from ccglm_mcp_server import sanitize_for_log, GLM_AUTH_TOKEN

    test_text = f"Error: Authentication failed with token {GLM_AUTH_TOKEN}"
    sanitized = sanitize_for_log(test_text)

    print(f"Original (truncated): {test_text[:50]}...")
    print(f"Sanitized: {sanitized}")

    assert GLM_AUTH_TOKEN not in sanitized, "Token should be redacted"
    assert "***REDACTED***" in sanitized, "Should contain redaction marker"

    print("✅ Test 4 PASSED\n")


async def main():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "CCGLM MCP SERVER TEST SUITE" + " " * 20 + "║")
    print("╚" + "=" * 58 + "╝")
    print("\n")

    tests = [
        ("File Tracking", test_file_tracking),
        ("Log Sanitization", test_sanitization),
        # Comentados para evitar llamadas reales a la API en tests automáticos
        # ("Basic Prompt", test_basic_prompt),
        # ("Code Generation", test_code_generation),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except Exception as e:
            print(f"❌ Test {test_name} FAILED: {e}\n")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        print("\n⚠️  Some tests failed. Please review the output above.")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
