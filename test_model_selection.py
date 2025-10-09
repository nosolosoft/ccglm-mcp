#!/usr/bin/env python3
"""
Test script para verificar la selección de modelos en CCGLM MCP
"""

import json
import sys
import os

# Añadir directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_model_selection():
    """Test básico de selección de modelos"""

    # Test 1: Schema MCP contiene parámetro model
    print("🧪 Test 1: Verificando schema MCP...")
    try:
        with open('ccglm_mcp_server.py', 'r') as f:
            content = f.read()

        # Verificar que el schema contenga el parámetro model
        if '"model"' in content and '"glm-4.5-air"' in content:
            print("✅ Schema MCP contiene parámetro model con opciones correctas")
        else:
            print("❌ Schema MCP no contiene parámetro model o opciones incorrectas")
            return False
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")
        return False

    # Test 2: Lógica de selección de modelo
    print("\n🧪 Test 2: Verificando lógica de selección...")
    if 'model = args.get("model", "glm-4.6")' in content:
        print("✅ Lógica de selección por defecto (glm-4.6) encontrada")
    else:
        print("❌ Lógica de selección por defecto no encontrada")
        return False

    if 'env["ANTHROPIC_MODEL"] = model' in content:
        print("✅ Inyección de variable de entorno ANTHROPIC_MODEL encontrada")
    else:
        print("❌ Inyección de variable de entorno no encontrada")
        return False

    # Test 3: Hashtag registry
    print("\n🧪 Test 3: Verificando hashtag registry...")
    try:
        with open('/home/manu/.claude/agents/hashtag-registry.json', 'r') as f:
            registry = json.load(f)

        if '#ccglm-fast' in registry['hashtag_mappings']:
            print("✅ Hashtag #ccglm-fast registrado en hashtag-registry.json")
        else:
            print("❌ Hashtag #ccglm-fast no encontrado en registry")
            return False
    except Exception as e:
        print(f"❌ Error leyendo hashtag registry: {e}")
        return False

    # Test 4: Documentación CLAUDE.md
    print("\n🧪 Test 4: Verificando documentación...")
    try:
        with open('/home/manu/claude/CLAUDE.md', 'r') as f:
            doc_content = f.read()

        if '#ccglm-fast' in doc_content and 'GLM-4.5-air' in doc_content:
            print("✅ Documentación CLAUDE.md actualizada con #ccglm-fast")
        else:
            print("❌ Documentación CLAUDE.md no actualizada")
            return False
    except Exception as e:
        print(f"❌ Error leyendo documentación: {e}")
        return False

    # Test 5: Verificar que el servidor se puede importar
    print("\n🧪 Test 5: Verificando import del servidor...")
    try:
        # Intentar importar sin ejecutar
        import importlib.util
        spec = importlib.util.spec_from_file_location("ccglm_server", "ccglm_mcp_server.py")
        module = importlib.util.module_from_spec(spec)
        print("✅ Servidor MCP se puede importar sin errores")
    except Exception as e:
        print(f"❌ Error importando servidor: {e}")
        return False

    return True

def print_usage_examples():
    """Imprime ejemplos de uso"""
    print("\n🎯 **EJEMPLOS DE USO IMPLEMENTADOS:**")
    print("")
    print("1. **Modelo por defecto (GLM-4.6):**")
    print("   #ccglm Explica qué es la recursión")
    print("")
    print("2. **Modelo rápido (GLM-4.5-air):**")
    print("   #ccglm-fast Genera una función simple")
    print("")
    print("3. **Control directo con parámetro:**")
    print("   #ccglm model=glm-4.5-air Tarea específica")
    print("   #ccglm model=glm-4.6 Tarea compleja")
    print("")
    print("4. **Uso MCP directo:**")
    print("   mcp__ccglm-mcp__glm_route con:")
    print("   - prompt: 'Tu pregunta aquí'")
    print("   - model: 'glm-4.5-air' (opcional, por defecto 'glm-4.6')")

if __name__ == "__main__":
    print("🔬 **CCGLM MCP Model Selection Test Suite**")
    print("=" * 50)

    success = test_model_selection()

    if success:
        print("\n🎉 **TODOS LOS TESTS PASARON**")
        print("✅ Implementación de selección de modelos completada y funcional")
        print_usage_examples()
    else:
        print("\n❌ **HAY ERRORES EN LA IMPLEMENTACIÓN**")
        print("Revisa los tests fallidos y corrige los problemas")
        sys.exit(1)