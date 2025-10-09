#!/bin/bash

# Script de testing controlado para CCGLM MCP Performance
# Mide tiempos reales de respuesta de ambos modelos

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/performance_test_$(date +%Y%m%d_%H%M%S).log"
PROMPT="Responde hola de forma amigable y breve"

echo "🧪 CCGLM MCP Performance Test" | tee "$LOG_FILE"
echo "==============================" | tee -a "$LOG_FILE"
echo "Timestamp: $(date)" | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Función para testear un modelo
test_model() {
    local model_name="$1"
    local model_code="$2"
    local prompt="$3"

    echo "🎯 Testing $model_name ($model_code)..." | tee -a "$LOG_FILE"
    echo "Prompt: '$prompt'" | tee -a "$LOG_FILE"

    # Tiempo inicial
    local start_time=$(date +%s.%N)

    # Ejecutar test usando MCP tool
    local response_file=$(mktemp)

    # Usar el comando claude con hashtag apropiado
    if [ "$model_code" = "glm-4.5-air" ]; then
        echo "#ccglm-fast $prompt" | timeout 600 claude > "$response_file" 2>&1 || {
            echo "❌ ERROR: Timeout o fallo ejecutando $model_name" | tee -a "$LOG_FILE"
            rm -f "$response_file"
            return 1
        }
    else
        echo "#ccglm $prompt" | timeout 600 claude > "$response_file" 2>&1 || {
            echo "❌ ERROR: Timeout o fallo ejecutando $model_name" | tee -a "$LOG_FILE"
            rm -f "$response_file"
            return 1
        }
    fi

    # Tiempo final
    local end_time=$(date +%s.%N)
    local duration=$(echo "$end_time - $start_time" | bc -l)

    echo "✅ Completed in ${duration}s" | tee -a "$LOG_FILE"

    # Analizar respuesta
    if [ -f "$response_file" ]; then
        local response_length=$(wc -c < "$response_file")
        echo "Response length: ${response_length} chars" | tee -a "$LOG_FILE"

        # Guardar contenido de respuesta (primeros 200 chars)
        echo "Response preview:" | tee -a "$LOG_FILE"
        head -c 200 "$response_file" | tee -a "$LOG_FILE"
        echo "" | tee -a "$LOG_FILE"
        echo "---" | tee -a "$LOG_FILE"

        # Buscar indicaciones de modelo en la respuesta
        if grep -q "glm-4.5-air\|GLM-4.5-air\|4.5-air" "$response_file"; then
            echo "✅ Model detected in response: glm-4.5-air" | tee -a "$LOG_FILE"
        elif grep -q "glm-4.6\|GLM-4.6\|4.6" "$response_file"; then
            echo "✅ Model detected in response: glm-4.6" | tee -a "$LOG_FILE"
        else
            echo "⚠️  Model not clearly identified in response" | tee -a "$LOG_FILE"
        fi

        rm -f "$response_file"
    else
        echo "❌ No response file generated" | tee -a "$LOG_FILE"
    fi

    echo "" | tee -a "$LOG_FILE"

    # Retornar duración para análisis posterior
    echo "$duration"
}

# Verificar que herramientas necesarias están disponibles
echo "🔧 Checking dependencies..." | tee -a "$LOG_FILE"

if ! command -v bc &> /dev/null; then
    echo "❌ ERROR: 'bc' calculator not found. Installing..." | tee -a "$LOG_FILE"
    sudo apt-get update && sudo apt-get install -y bc || {
        echo "❌ ERROR: Could not install bc. Please install manually." | tee -a "$LOG_FILE"
        exit 1
    }
fi

if ! command -v claude &> /dev/null; then
    echo "❌ ERROR: Claude CLI not found in PATH" | tee -a "$LOG_FILE"
    exit 1
fi

echo "✅ Dependencies OK" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Test 1: Modelo rápido (glm-4.5-air)
echo "🚀 Test 1: Fast Model (glm-4.5-air)" | tee -a "$LOG_FILE"
time_air=$(test_model "GLM-4.5-air" "glm-4.5-air" "$PROMPT")

if [ $? -ne 0 ]; then
    echo "❌ Failed to test glm-4.5-air" | tee -a "$LOG_FILE"
    exit 1
fi

# Esperar un poco entre tests
echo "⏳ Waiting 10 seconds before next test..." | tee -a "$LOG_FILE"
sleep 10

# Test 2: Modelo normal (glm-4.6)
echo "🧠 Test 2: Normal Model (glm-4.6)" | tee -a "$LOG_FILE"
time_46=$(test_model "GLM-4.6" "glm-4.6" "$PROMPT")

if [ $? -ne 0 ]; then
    echo "❌ Failed to test glm-4.6" | tee -a "$LOG_FILE"
    exit 1
fi

# Análisis de resultados
echo "📊 RESULTS SUMMARY" | tee -a "$LOG_FILE"
echo "==================" | tee -a "$LOG_FILE"
printf "GLM-4.5-air (fast): %.2f seconds\n" "$time_air" | tee -a "$LOG_FILE"
printf "GLM-4.6 (normal):   %.2f seconds\n" "$time_46" | tee -a "$LOG_FILE"

# Calcular diferencia
if (( $(echo "$time_air > 0 && $time_46 > 0" | bc -l) )); then
    if (( $(echo "$time_air < $time_46" | bc -l) )); then
        difference=$(echo "scale=2; ($time_46 - $time_air) / $time_46 * 100" | bc -l)
        faster=$(echo "scale=2; $time_46 / $time_air" | bc -l)
        echo "✅ GLM-4.5-air is ${difference}% faster (${faster}x)" | tee -a "$LOG_FILE"
    else
        difference=$(echo "scale=2; ($time_air - $time_46) / $time_46 * 100" | bc -l)
        slower=$(echo "scale=2; $time_air / $time_46" | bc -l)
        echo "⚠️  GLM-4.5-air is ${difference}% slower (${slower}x)" | tee -a "$LOG_FILE"
        echo "🚨 THIS INDICATES A PROBLEM - The 'fast' model should be faster!" | tee -a "$LOG_FILE"
    fi
else
    echo "❌ Could not calculate performance difference" | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"
echo "🎯 RECOMMENDATIONS:" | tee -a "$LOG_FILE"

if (( $(echo "$time_air < $time_46" | bc -l) )); then
    echo "✅ Performance is as expected - fast model is faster" | tee -a "$LOG_FILE"
else
    echo "🚨 PERFORMANCE ANOMALY DETECTED:" | tee -a "$LOG_FILE"
    echo "   - Check MCP server logs for model selection issues" | tee -a "$LOG_FILE"
    echo "   - Verify ANTHROPIC_MODEL environment variable is working" | tee -a "$LOG_FILE"
    echo "   - Check if both models are actually being used" | tee -a "$LOG_FILE"
    echo "   - Review Claude CLI logs for API response times" | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"
echo "📁 Full log saved to: $LOG_FILE" | tee -a "$LOG_FILE"
echo "🏁 Test completed at $(date)" | tee -a "$LOG_FILE"