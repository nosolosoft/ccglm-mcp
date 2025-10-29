#!/usr/bin/env python3
"""
CCGLM MCP Timeout Optimization
Adjusts timeout settings and adds better error handling
Only affects ~/IA/ccglm-mcp/ directory
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime

def backup_original_file():
    """Backup original server file"""
    original = "ccglm_mcp_server.py"
    backup = f"ccglm_mcp_server.py.backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if os.path.exists(original):
        shutil.copy2(original, backup)
        print(f"✅ Backup created: {backup}")
        return True
    return False

def optimize_timeouts():
    """Create optimized timeout configuration"""
    config = {
        "DEFAULT_TIMEOUT": 120,    # Reduced from 300s to 120s
        "MAX_TIMEOUT": 600,        # Reduced from 1800s to 600s
        "API_TIMEOUT": 60,         # New: API call timeout
        "QUICK_TIMEOUT": 30,       # New: Quick responses timeout
        "CONNECTION_TIMEOUT": 10,  # New: Connection timeout
        "RETRY_ATTEMPTS": 2,       # New: Retry attempts
        "HEALTH_CHECK_INTERVAL": 300  # New: Health check every 5 min
    }

    with open("timeout_config.json", "w") as f:
        json.dump(config, f, indent=2)

    print("✅ Timeout configuration created: timeout_config.json")
    return config

def create_enhanced_logging():
    """Create enhanced logging configuration"""
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "simple": {
                "format": "%(levelname)s: %(message)s"
            }
        },
        "handlers": {
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "logs/ccglm-mcp.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "formatter": "detailed"
            },
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "simple",
                "level": "INFO"
            }
        },
        "loggers": {
            "ccglm-mcp": {
                "level": "INFO",
                "handlers": ["file", "console"],
                "propagate": False
            }
        }
    }

    with open("logging_config.json", "w") as f:
        json.dump(logging_config, f, indent=2)

    print("✅ Enhanced logging configuration created: logging_config.json")

def create_health_check_script():
    """Create health check script for monitoring"""
    script = """#!/bin/bash
# CCGLM MCP Health Check Script
# Monitors server health and restarts if needed

CCGLM_DIR="/home/manu/IA/ccglm-mcp"
LOG_FILE="$CCGLM_DIR/logs/health-check.log"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Check if server process is running
check_server() {
    local pid_count=$(pgrep -f "ccglm_mcp_server.py" | wc -l)
    echo "$pid_count"
}

# Test API connectivity
test_api() {
    source "$CCGLM_DIR/.env"
    local response=$(curl -s -X POST "https://api.z.ai/api/anthropic/v1/messages" \\
        -H "Content-Type: application/json" \\
        -H "Authorization: Bearer $GLM_AUTH_TOKEN" \\
        -H "anthropic-version: 2023-06-01" \\
        -d '{"model": "glm-4.6", "max_tokens": 5, "messages": [{"role": "user", "content": "test"}]}' \\
        --connect-timeout 5 --max-time 10)

    if echo "$response" | grep -q '"content"'; then
        echo "OK"
    else
        echo "FAILED"
    fi
}

# Main health check
log "Starting health check..."

# Check process count
pid_count=$(check_server)
log "Process count: $pid_count"

if [ "$pid_count" -eq 0 ]; then
    log "❌ No CCGLM processes found, restarting..."
    cd "$CCGLM_DIR"
    ./recovery_script.sh
elif [ "$pid_count" -gt 1 ]; then
    log "⚠️  Multiple processes found ($pid_count), restarting..."
    cd "$CCGLM_DIR"
    ./recovery_script.sh
else
    log "✅ Single process running"
fi

# Test API connectivity
api_status=$(test_api)
log "API status: $api_status"

if [ "$api_status" != "OK" ]; then
    log "❌ API connectivity issue"
else
    log "✅ API connectivity OK"
fi

log "Health check completed"
"""

    with open("health_check.sh", "w") as f:
        f.write(script)

    os.chmod("health_check.sh", 0o755)
    print("✅ Health check script created: health_check.sh")

def create_cron_entry():
    """Create cron entry for automatic health checks"""
    cron_entry = "*/5 * * * * /home/manu/IA/ccglm-mcp/health_check.sh"

    with open("cron_entry.txt", "w") as f:
        f.write(f"# Add to crontab with: crontab -e\n")
        f.write(f"{cron_entry}\n")

    print("✅ Cron entry created: cron_entry.txt")
    print(f"   To enable: crontab -e and add: {cron_entry}")

def main():
    """Main optimization function"""
    print("🚀 CCGLM MCP Timeout Optimization")
    print("=================================")

    # Create logs directory
    os.makedirs("logs", exist_ok=True)

    # Step 1: Backup original file
    backup_original_file()

    # Step 2: Create optimized timeout configuration
    config = optimize_timeouts()

    # Step 3: Create enhanced logging configuration
    create_enhanced_logging()

    # Step 4: Create health check script
    create_health_check_script()

    # Step 5: Create cron entry
    create_cron_entry()

    print("\n📋 Optimization Summary:")
    print(f"  Default timeout: {config['DEFAULT_TIMEOUT']}s (was 300s)")
    print(f"  Max timeout: {config['MAX_TIMEOUT']}s (was 1800s)")
    print(f"  API timeout: {config['API_TIMEOUT']}s (new)")
    print(f"  Quick timeout: {config['QUICK_TIMEOUT']}s (new)")
    print(f"  Connection timeout: {config['CONNECTION_TIMEOUT']}s (new)")

    print("\n🎯 Next Steps:")
    print("  1. Run: ./recovery_script.sh")
    print("  2. Monitor: tail -f logs/ccglm-mcp.log")
    print("  3. Optional: Add cron entry for automatic health checks")

    print("\n✅ Optimization completed!")

if __name__ == "__main__":
    main()