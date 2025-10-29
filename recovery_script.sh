#!/bin/bash
# CCGLM MCP Diagnostics and Recovery Script
# Only modifies ~/IA/ccglm-mcp/ directory

echo "🔍 CCGLM MCP Diagnostics & Recovery"
echo "=================================="

CCGLM_DIR="/home/manu/IA/ccglm-mcp"
cd "$CCGLM_DIR"

# 1. Kill existing processes safely
echo "📋 Step 1: Terminating existing CCGLM processes..."
pkill -f "ccglm_mcp_server.py" 2>/dev/null || true
sleep 2

# Verify no processes remain
REMAINING=$(pgrep -f "ccglm_mcp_server.py" | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "⚠️  Forcing termination of remaining processes..."
    pkill -9 -f "ccglm_mcp_server.py" 2>/dev/null || true
    sleep 1
fi

# 2. Clean temporary files and old logs
echo "📋 Step 2: Cleaning temporary files..."
find . -name "*.tmp" -delete 2>/dev/null || true
find . -name "*.pid" -delete 2>/dev/null || true
find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# 3. Create logs directory with proper permissions
echo "📋 Step 3: Setting up log directory..."
mkdir -p logs
chmod 755 logs

# 4. Test API connectivity before restart
echo "📋 Step 4: Testing API connectivity..."
source .env
API_RESPONSE=$(curl -s -X POST "https://api.z.ai/api/anthropic/v1/messages" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $GLM_AUTH_TOKEN" \
    -H "anthropic-version: 2023-06-01" \
    -d '{"model": "glm-4.6", "max_tokens": 10, "messages": [{"role": "user", "content": "test"}]}' \
    --connect-timeout 5 --max-time 10)

if echo "$API_RESPONSE" | grep -q '"content"'; then
    echo "✅ API connectivity test passed"
else
    echo "❌ API connectivity test failed"
    echo "Response: $API_RESPONSE"
    exit 1
fi

# 5. Restart server with single instance
echo "📋 Step 5: Starting fresh CCGLM MCP server..."
nohup python3 ccglm_mcp_server.py > logs/ccglm-restart-$(date +%Y%m%d_%H%M%S).log 2>&1 &
SERVER_PID=$!

echo "📋 Step 6: Verifying server startup..."
sleep 3

# Check if process is running
if kill -0 $SERVER_PID 2>/dev/null; then
    echo "✅ CCGLM MCP Server started successfully (PID: $SERVER_PID)"
else
    echo "❌ Server failed to start"
    exit 1
fi

# 6. Run quick test
echo "📋 Step 7: Running quick functionality test..."
sleep 2

# Test with simple prompt through Claude CLI
export ANTHROPIC_BASE_URL="https://api.z.ai/api/anthropic"
export ANTHROPIC_AUTH_TOKEN="$GLM_AUTH_TOKEN"
export ANTHROPIC_MODEL="glm-4.6"

TEST_RESPONSE=$(timeout 30s claude --dangerously-skip-permissions -c -p "Respond with just: OK" 2>/dev/null | grep -i ok || echo "FAILED")

if [[ "$TEST_RESPONSE" == *"OK"* ]]; then
    echo "✅ Functionality test passed"
else
    echo "⚠️  Functionality test failed - may need manual verification"
fi

echo ""
echo "🎉 Recovery completed!"
echo "📊 Current status:"
echo "  Server PID: $SERVER_PID"
echo "  Log directory: $CCGLM_DIR/logs"
echo "  API Status: Connected"
echo ""
echo "🔧 To monitor: tail -f logs/ccglm-restart-*.log"