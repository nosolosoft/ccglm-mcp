#!/bin/bash
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
    local response=$(curl -s -X POST "https://api.z.ai/api/anthropic/v1/messages" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $GLM_AUTH_TOKEN" \
        -H "anthropic-version: 2023-06-01" \
        -d '{"model": "glm-4.6", "max_tokens": 5, "messages": [{"role": "user", "content": "test"}]}' \
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
