#!/usr/bin/env python3
"""
CCGLM MCP Server - Versión simplificada basada en patrón CCR-MCP
Rutea prompts a GLM vía Claude CLI con configuración Z.AI
"""

import asyncio
import json
import logging
import os
import sys
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import shlex
from dotenv import load_dotenv

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

# Cargar variables de entorno desde .env
load_dotenv()

# CRÍTICO: Usar stderr para logs, NO stdout (patrón de CCR-MCP)
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,  # ✅ stderr para no interferir con stdio
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ccglm-mcp")

# Crear servidor MCP
server = Server("ccglm-mcp")

# Configuración de timeouts alineada con Claude (300s)
DEFAULT_TIMEOUT = 300  # 4.6 minutos (un poco menos que Claude)
MAX_TIMEOUT = 600      # 4.9 minutos (margen de seguridad)

# Configuración GLM desde variables de entorno
GLM_BASE_URL = os.getenv("GLM_BASE_URL", "https://api.z.ai/api/anthropic")
GLM_AUTH_TOKEN = os.getenv("GLM_AUTH_TOKEN")

# Validar configuración
if not GLM_AUTH_TOKEN:
    logger.error("❌ GLM_AUTH_TOKEN no configurado")
    sys.exit(1)

def get_current_files(directory: str = ".") -> Set[str]:
    """Obtener conjunto de archivos actuales en el directorio"""
    try:
        files = set()
        for root, dirs, filenames in os.walk(directory):
            # Excluir directorios internos
            dirs[:] = [d for d in dirs if d not in {'.claude', '.git', 'node_modules', '__pycache__', '.venv', '.next', 'dist', 'build'}]
            for filename in filenames:
                files.add(os.path.join(root, filename))
        return files
    except Exception as e:
        logger.warning(f"Error scanning directory {directory}: {e}")
        return set()

def detect_new_files(before: Set[str], after: Set[str]) -> List[str]:
    """Detectar archivos nuevos comparando dos sets"""
    new_files = after - before
    return sorted(list(new_files))

def format_file_summary(new_files: List[str], stdout_text: str) -> str:
    """Formatear resumen de archivos creados"""
    if not new_files:
        return stdout_text

    # Crear resumen de archivos creados
    summary_lines = [
        f"✅ GLM execution completed successfully!",
        f"📁 {len(new_files)} files created:"
    ]

    for file_path in new_files[:10]:  # Limitar a primeros 10 archivos
        try:
            file_size = os.path.getsize(file_path)
            summary_lines.append(f"  • {file_path} ({file_size} bytes)")
        except:
            summary_lines.append(f"  • {file_path}")

    if len(new_files) > 10:
        summary_lines.append(f"  ... and {len(new_files) - 10} more files")

    # Agregar el output original si existe y es relevante
    if stdout_text and len(stdout_text.strip()) > 0:
        summary_lines.extend([
            "",
            "📝 Original output:",
            stdout_text
        ])

    return "\n".join(summary_lines)

def contains_chinese(text: str) -> bool:
    """Detectar si el texto contiene caracteres chinos"""
    try:
        # Verificar rangos Unicode de caracteres chinos comunes
        for char in text:
            code = ord(char)
            if (0x4E00 <= code <= 0x9FFF or  # CJK Unified Ideographs
                0x3400 <= code <= 0x4DBF or  # CJK Extension A
                0x20000 <= code <= 0x2A6DF or  # CJK Extension B
                0x2A700 <= code <= 0x2B73F or  # CJK Extension C
                0x2B740 <= code <= 0x2B81F or  # CJK Extension D
                0x2B820 <= code <= 0x2CEAF or  # CJK Extension E
                0x2CEB0 <= code <= 0x2EBEF or  # CJK Extension F
                0x3000 <= code <= 0x303F or    # CJK Symbols and Punctuation
                0xFF00 <= code <= 0xFFEF):     # Halfwidth and Fullwidth Forms
                return True
        return False
    except Exception:
        return False

@server.list_tools()
async def list_tools() -> List[types.Tool]:
    """Listar herramientas disponibles"""
    return [
        types.Tool(
            name="ccglm",
            description="Route prompt to GLM-4.6 (default) or glm-4.5-air (fast) via Claude CLI with Z.AI credentials",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Prompt to send to GLM"
                    },
                    "model": {
                        "type": "string",
                        "description": "GLM model to use (glm-4.6 or glm-4.5-air)",
                        "default": "glm-4.6",
                        "enum": ["glm-4.6", "glm-4.5-air"]
                    }
                },
                "required": ["prompt"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Ejecutar herramienta"""
    start_time = time.time()

    try:
        if name == "ccglm":
            prompt = arguments.get("prompt", "")

            # VALIDACIÓN DE IDIOMA
            if contains_chinese(prompt):
                error_msg = (
                    "❌ CCGLM-MCP: Idioma no soportado\n\n"
                    "GLM-4.6 está optimizado para español e inglés. "
                    "Por favor, usa español o inglés para mejores resultados.\n\n"
                    f"Texto detectado: {prompt[:100]}..."
                )
                return [types.TextContent(type="text", text=error_msg)]

            result = await ccglm_route(arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}

        # Formatear respuesta
        if isinstance(result, dict):
            if "error" in result:
                response = f"❌ Error: {result['error']}"
            else:
                response = result.get("response", "No response received")
        else:
            response = str(result)

        return [types.TextContent(type="text", text=response)]

    except Exception as e:
        logger.error(f"Tool execution failed: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"❌ Error executing {name}: {str(e)}"
        )]

async def ccglm_route(args: Dict[str, Any]) -> Dict[str, Any]:
    """Route prompt to GLM via Claude CLI con Z.AI credentials"""
    prompt = args.get("prompt", "")
    start_time = time.time()

    if not prompt:
        logger.error("No prompt provided in ccglm request")
        return {"error": "No prompt provided"}

    try:
        # Logging básico
        prompt_preview = prompt[:200] if len(prompt) > 200 else prompt
        logger.info(f"🚀 Starting GLM routing - Prompt length: {len(prompt)} chars")
        logger.info(f"📝 Prompt preview: {prompt_preview}...")

        # Capturar archivos antes de la ejecución
        cwd = os.getcwd()
        logger.info(f"📁 Working directory: {cwd}")
        files_before = get_current_files(cwd)
        logger.info(f"📊 Files before execution: {len(files_before)}")

        # Preparar environment con credenciales GLM
        env = os.environ.copy()
        env["ANTHROPIC_BASE_URL"] = GLM_BASE_URL
        env["ANTHROPIC_AUTH_TOKEN"] = GLM_AUTH_TOKEN

        # Seleccionar modelo
        model = args.get("model", "glm-4.6")
        env["ANTHROPIC_MODEL"] = model

        # Determinar timeout basado en modelo
        model_timeout = 120 if model == "glm-4.5-air" else DEFAULT_TIMEOUT
        effective_timeout = min(model_timeout, MAX_TIMEOUT)

        logger.info(f"🎯 Using GLM model: {model} (timeout: {effective_timeout}s)")
        logger.info(f"🔧 GLM endpoint: {GLM_BASE_URL}")

        # Comando Claude CLI con flags requeridos
        cmd = ["claude", "--dangerously-skip-permissions", "-c", "-p"]
        logger.info(f"💻 Executing command: {' '.join(cmd)}")

        # Crear proceso con comunicación stdin (patrón CCR-MCP)
        logger.info("🔄 Creating subprocess for GLM communication")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
            env=env
        )

        try:
            # Enviar prompt por stdin y capturar salida
            logger.info(f"📤 Sending prompt via stdin (timeout: {effective_timeout}s)")
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=prompt.encode('utf-8')),
                timeout=effective_timeout
            )

            execution_time = time.time() - start_time
            logger.info(f"⏱️  GLM execution completed in {execution_time:.2f}s")

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.warning(f"⏰ GLM process timed out after {effective_timeout}s (execution time: {execution_time:.2f}s)")

            # Terminar proceso
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5)
                logger.info("✅ Process terminated gracefully")
            except asyncio.TimeoutError:
                logger.warning("Process didn't terminate gracefully, forcing kill")
                process.kill()
                await process.wait()

            return {"error": f"Request timed out after {effective_timeout}s for model {model}"}

        # Decodificar salidas
        stdout_text = stdout.decode('utf-8', errors='replace').strip()
        stderr_text = stderr.decode('utf-8', errors='replace').strip()

        # Logging del resultado
        logger.info(f"📊 GLM process results:")
        logger.info(f"  • Exit code: {process.returncode}")
        logger.info(f"  • Stdout length: {len(stdout_text)} chars")
        logger.info(f"  • Stderr length: {len(stderr_text)} chars")

        if stderr_text:
            stderr_preview = stderr_text[:500] if len(stderr_text) > 500 else stderr_text
            logger.info(f"⚠️  Stderr content: {stderr_preview}...")

        # Capturar archivos después de la ejecución
        files_after = get_current_files(cwd)
        new_files = detect_new_files(files_before, files_after)
        logger.info(f"📁 Files after execution: {len(files_after)} total, {len(new_files)} new")

        if new_files:
            logger.info("✨ New files created:")
            for file_path in new_files[:5]:  # Log primeros 5 archivos
                try:
                    file_size = os.path.getsize(file_path)
                    logger.info(f"  • {file_path} ({file_size} bytes)")
                except:
                    logger.info(f"  • {file_path}")
            if len(new_files) > 5:
                logger.info(f"  ... and {len(new_files) - 5} more files")

        # Manejo de códigos de salida
        if process.returncode != 0:
            if stdout_text and len(stdout_text) > 10:
                logger.warning(f"⚠️  GLM returned error code {process.returncode} but has output ({len(stdout_text)} chars)")
            elif new_files:
                logger.warning(f"⚠️  GLM returned error code {process.returncode} but created {len(new_files)} files")
            else:
                error_msg = stderr_text or f"GLM exited with code {process.returncode}"
                logger.error(f"❌ GLM command failed: {error_msg}")
                return {"error": f"GLM failed: {error_msg}"}

        # Formatear respuesta
        if new_files:
            response_text = format_file_summary(new_files, stdout_text)
        elif stdout_text:
            response_text = stdout_text
        else:
            response_text = "GLM execution completed (no output or files created)"

        logger.info(f"✅ GLM routing completed successfully in {execution_time:.2f}s")
        return {"response": response_text}

    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"💥 GLM routing failed after {execution_time:.2f}s: {e}", exc_info=True)
        return {"error": f"Unexpected error: {str(e)}"}

async def main():
    """Main entry point"""
    logger.info("CCGLM MCP Server starting (simplified version)...")
    logger.info("GLM routing mode - routes prompts via Claude CLI to Z.AI GLM backend")
    logger.info(f"GLM endpoint: {GLM_BASE_URL}")
    logger.info(f"Timeouts - Default: {DEFAULT_TIMEOUT}s, Max: {MAX_TIMEOUT}s")

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        logger.info("Server ready, waiting for connections...")
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
