#!/usr/bin/env python3
"""
Script de validación rápida para las correcciones del CCGLM MCP
Verifica que todos los componentes estén configurados correctamente
"""

import json
import sys
import os
import subprocess
from pathlib import Path

def check_timeout_sync():
    """Verifica que los timeouts estén sincronizados"""
    print("🔧 Checking timeout synchronization...")

    # Leer settings.json
    try:
        with open('/home/manu/.claude/settings.json', 'r') as f:
            settings = json.load(f)

        mcp_timeout = settings['mcpServers']['ccglm-mcp']['timeout']
        expected_timeout = 300000  # 5 minutos en milisegundos

        if mcp_timeout == expected_timeout:
            print(f"✅ Settings.json timeout: {mcp_timeout}ms (correct)")
            return True
        else:
            print(f"❌ Settings.json timeout: {mcp_timeout}ms (expected {expected_timeout}ms)")
            return False

    except Exception as e:
        print(f"❌ Error reading settings.json: {e}")
        return False

def check_server_code():
    """Verifica que el código del servidor tenga las correcciones"""
    print("\n🔍 Checking server code modifications...")

    server_file = '/home/manu/IA/ccglm-mcp/ccglm_mcp_server.py'

    try:
        with open(server_file, 'r') as f:
            content = f.read()

        checks = [
            ("MODEL DEBUG logging", "🎯 MODEL DEBUG: Requested=" in content),
            ("ENVIRONMENT DEBUG", "🔧 ENVIRONMENT DEBUG:" in content),
            ("Model requested field", '"model_requested": model' in content),
            ("Model configured field", '"model_configured": env["ANTHROPIC_MODEL"]' in content),
            ("Performance metrics", "📊 PERFORMANCE METRICS:" in content),
            ("Fast model warning", "FAST MODEL SLOW PERFORMANCE" in content)
        ]

        all_good = True
        for check_name, condition in checks:
            if condition:
                print(f"✅ {check_name}: Found")
            else:
                print(f"❌ {check_name}: Missing")
                all_good = False

        return all_good

    except Exception as e:
        print(f"❌ Error reading server file: {e}")
        return False

def check_hashtag_registry():
    """Verifica configuración de hashtags"""
    print("\n🏷️  Checking hashtag registry...")

    try:
        with open('/home/manu/.claude/agents/hashtag-registry.json', 'r') as f:
            registry = json.load(f)

        mappings = registry['hashtag_mappings']

        required_mappings = [
            ("#ccglm", "ccglm-agent"),
            ("#ccglm-fast", "ccglm-agent"),
            ("#glm", "ccglm-agent")
        ]

        all_good = True
        for hashtag, expected_agent in required_mappings:
            if hashtag in mappings and expected_agent in mappings[hashtag]:
                print(f"✅ {hashtag} → {expected_agent}")
            else:
                print(f"❌ {hashtag} mapping incorrect or missing")
                all_good = False

        return all_good

    except Exception as e:
        print(f"❌ Error reading hashtag registry: {e}")
        return False

def check_test_script():
    """Verifica que el script de testing esté creado y sea ejecutable"""
    print("\n🧪 Checking performance test script...")

    script_path = '/home/manu/IA/ccglm-mcp/test_ccglm_performance.sh'

    if os.path.exists(script_path):
        if os.access(script_path, os.X_OK):
            print("✅ Performance test script exists and is executable")
            return True
        else:
            print("❌ Performance test script exists but is not executable")
            return False
    else:
        print("❌ Performance test script not found")
        return False

def run_syntax_check():
    """Verifica sintaxis del servidor MCP"""
    print("\n🐍 Checking Python syntax...")

    try:
        result = subprocess.run([
            sys.executable, '-m', 'py_compile',
            '/home/manu/IA/ccglm-mcp/ccglm_mcp_server.py'
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ Server code syntax is valid")
            return True
        else:
            print(f"❌ Syntax errors found: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Error checking syntax: {e}")
        return False

def main():
    """Función principal de validación"""
    print("🔍 CCGLM MCP Fix Validation")
    print("=" * 40)

    checks = [
        ("Timeout Synchronization", check_timeout_sync),
        ("Server Code Modifications", check_server_code),
        ("Hashtag Registry", check_hashtag_registry),
        ("Performance Test Script", check_test_script),
        ("Python Syntax Check", run_syntax_check)
    ]

    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name} failed with exception: {e}")
            results.append((check_name, False))

    print("\n📊 VALIDATION SUMMARY")
    print("=" * 30)

    passed = 0
    total = len(results)

    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {check_name}")
        if result:
            passed += 1

    print(f"\nResults: {passed}/{total} checks passed")

    if passed == total:
        print("🎉 ALL FIXES VALIDATED SUCCESSFULLY!")
        print("\n📋 NEXT STEPS:")
        print("1. Restart Claude Code to reload MCP server")
        print("2. Run the performance test script:")
        print("   ./test_ccglm_performance.sh")
        print("3. Monitor logs in ~/.claude/logs/ for model selection debugging")
        return 0
    else:
        print("🚨 SOME FIXES NEED ATTENTION!")
        print("Please review the failed checks above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())