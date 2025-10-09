#!/usr/bin/env python3
"""
CCGLM MCP Server - Claude Code con backend GLM vía Z.AI
Basado en patrón ccr-mcp con inyección de credenciales GLM
"""

import asyncio
import json
import logging
import os
import signal
import sys
import subprocess
import glob
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import shlex
from dotenv import load_dotenv

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

# Import enhanced logging utilities
from logging_utils import get_logger

# Initialize enhanced logger (replaces basic logging setup)
ccglm_logger = get_logger()
logger = ccglm_logger.logger

# Cargar variables de entorno desde .env
load_dotenv()

# Crear servidor MCP
server = Server("ccglm-mcp")

# Configuración de timeouts (mismo que CCR-MCP)
DEFAULT_TIMEOUT = 300   # 5 minutos
MAX_TIMEOUT = 1800      # 30 minutos

# Configuración GLM - cargada de variables de entorno o .env
GLM_BASE_URL = os.getenv("GLM_BASE_URL", "https://api.z.ai/api/anthropic")
GLM_AUTH_TOKEN = os.getenv("GLM_AUTH_TOKEN")

# Validar que el token esté configurado
if not GLM_AUTH_TOKEN:
    logger.error("❌ GLM_AUTH_TOKEN no configurado. Debe estar en variables de entorno o archivo .env")
    sys.exit(1)

def get_current_files(directory: str = ".") -> Set[str]:
    """Obtener conjunto de archivos actuales (excluye directorios internos)"""
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

def sanitize_for_log(text: str) -> str:
    """Sanitizar datos sensibles de los logs"""
    if GLM_AUTH_TOKEN:
        text = text.replace(GLM_AUTH_TOKEN, "***REDACTED***")
    return text


def contains_chinese(text: str) -> bool:
    """
    Detecta si el texto contiene caracteres chinos.

    Rangos Unicode cubiertos:
    - U+4E00–U+9FFF: CJK Unified Ideographs (caracteres comunes)
    - U+3400–U+4DBF: CJK Extension A
    - U+20000–U+2A6DF: CJK Extension B
    """
    if not text:
        return False

    for char in text:
        code = ord(char)
        # Rango principal CJK
        if 0x4E00 <= code <= 0x9FFF:
            return True
        # CJK Extension A
        if 0x3400 <= code <= 0x4DBF:
            return True
        # CJK Extension B
        if 0x20000 <= code <= 0x2A6DF:
            return True

    return False


@server.list_tools()
async def list_tools() -> List[types.Tool]:
    """Listar herramientas disponibles"""
    return [
        types.Tool(
            name="glm_route",
            description="Route prompt to GLM-4.6 (default) or glm-4.5-air (fast) via Claude CLI (handles all tasks: code generation, analysis, general queries)",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The prompt to send to GLM"
                    },
                    "model": {
                        "type": "string",
                        "description": "Model to use: glm-4.5-air (fast) or glm-4.6 (default)",
                        "enum": ["glm-4.5-air", "glm-4.6"],
                        "default": "glm-4.6"
                    }
                },
                "required": ["prompt"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Manejar llamadas a herramientas"""
    start_time = time.perf_counter()

    try:
        # Create request context with enhanced logging
        context = ccglm_logger.create_request_context(name, arguments)

        # Log request event
        ccglm_logger.log_request(context)

        if name == "glm_route":
            prompt = arguments.get("prompt", "")

            # VALIDACIÓN DE IDIOMA
            if contains_chinese(prompt):
                error_msg = (
                    "❌ CCGLM-MCP: Idioma no soportado\n\n"
                    "Los prompts en chino no son aceptados por este servidor.\n"
                    "GLM-4.6 está optimizado para español e inglés.\n\n"
                    "Idiomas permitidos: Español, Inglés\n"
                    "Idiomas bloqueados: Chino (中文/繁體/简体)\n\n"
                    "Sugerencia: Use el modelo Claude principal para procesamiento en chino."
                )
                logger.warning("Prompt rechazado por contener caracteres chinos")
                validation_result = {"error": error_msg}
                ccglm_logger.log_response(context, validation_result, start_time)
                return [types.TextContent(type="text", text=error_msg)]

            result = await glm_route(arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}

        # Log response event
        ccglm_logger.log_response(context, result, start_time)

        # Formatear respuesta
        if isinstance(result, dict):
            if "error" in result:
                response = f"❌ Error: {result['error']}"
            else:
                # Para GLM, mostrar solo la respuesta
                response = result.get("response", json.dumps(result, indent=2, ensure_ascii=False))
        else:
            response = str(result)

        return [types.TextContent(type="text", text=response)]

    except Exception as e:
        # Log error event with enhanced logging
        context = ccglm_logger.create_request_context(name, arguments)
        ccglm_logger.log_error(context, e, start_time)
        return [types.TextContent(
            type="text",
            text=f"❌ Error executing {name}: {str(e)}"
        )]

async def glm_route(args: Dict[str, Any]) -> Dict[str, Any]:
    """Route prompt to GLM via Claude CLI with Z.AI credentials"""
    prompt = args.get("prompt", "")
    start_time = time.time()

    if not prompt:
        logger.error("No prompt provided in glm_route request")
        return {"error": "No prompt provided"}

    # Create a basic context for subprocess logging (will be enhanced in call_tool)
    context = {
        "instance_id": ccglm_logger.instance_id,
        "pid": ccglm_logger.pid,
        "tool": "glm_route"
    }

    try:
        # Enhanced subprocess logging
        cwd = os.getcwd()
        files_before = get_current_files(cwd)

        # Log process start
        ccglm_logger.log_process_event(
            context, "spawn",
            cmd_preview="claude --dangerously-skip-permissions -c -p",
            cwd=cwd,
            files_before=len(files_before)
        )

        # Preparar environment con credenciales GLM
        env = os.environ.copy()
        env["ANTHROPIC_BASE_URL"] = GLM_BASE_URL
        env["ANTHROPIC_AUTH_TOKEN"] = GLM_AUTH_TOKEN

        # Seleccionar modelo
        model = args.get("model", "glm-4.6")
        env["ANTHROPIC_MODEL"] = model

        # Debug logging para verificar configuración del modelo
        logger.info(f"🎯 MODEL DEBUG: Requested={model}, ANTHROPIC_MODEL={env['ANTHROPIC_MODEL']}")
        logger.info(f"🔧 ENVIRONMENT DEBUG: GLM_BASE_URL={GLM_BASE_URL}")

        # Comando Claude CLI con flags requeridos
        cmd = ["claude", "--dangerously-skip-permissions", "-c", "-p"]

        # Crear proceso con comunicación stdin
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
            env=env
        )

        try:
            # Enviar prompt por stdin y capturar salida
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=prompt.encode('utf-8')),
                timeout=MAX_TIMEOUT
            )

            # Decodificar salidas
            stdout_text = stdout.decode('utf-8', errors='replace').strip()
            stderr_text = stderr.decode('utf-8', errors='replace').strip()

            # Capturar archivos después de la ejecución
            files_after = get_current_files(cwd)
            new_files = detect_new_files(files_before, files_after)

            # Log process completion with enhanced details
            ccglm_logger.log_process_event(
                context, "exit",
                exit_code=process.returncode,
                stdout_len=len(stdout_text),
                stderr_len=len(stderr_text),
                stderr_preview=stderr_text[:200] if stderr_text else None,
                files_after=len(files_after),
                files_created=len(new_files),
                new_files=new_files[:10]
            )

        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            logger.error(f"⏰ GLM timed out after {MAX_TIMEOUT}s")
            return {"error": f"Request timed out after {MAX_TIMEOUT}s"}

        # Manejo mejorado de códigos de salida
        if process.returncode != 0:
            # Verificar si hay respuesta útil en stdout a pesar del error
            if stdout_text and len(stdout_text) > 10:
                logger.warning(f"⚠️  GLM returned error code {process.returncode} but has output ({len(stdout_text)} chars)")
                # Continuar procesando la respuesta
            elif new_files:
                logger.warning(f"⚠️  GLM returned error code {process.returncode} but created {len(new_files)} files")
                # Continuar procesando aunque no haya stdout
            else:
                error_msg = stderr_text or f"GLM exited with code {process.returncode}"
                logger.error(f"❌ GLM command failed: {sanitize_for_log(error_msg)}")
                return {"error": f"GLM failed: {sanitize_for_log(error_msg)}"}

        # Enhanced logging for file creation
        if new_files:
            ccglm_logger.log_process_event(
                context, "file_creation",
                files_created=len(new_files),
                new_files=new_files[:10],
                file_summary=" ".join([os.path.basename(f) for f in new_files[:5]])
            )
            logger.info(f"✅ Success: GLM created {len(new_files)} files")
            response_text = format_file_summary(new_files, stdout_text)
        elif stdout_text and len(stdout_text.strip()) > 0:
            ccglm_logger.log_process_event(
                context, "text_output",
                output_length=len(stdout_text),
                response_preview=stdout_text[:200]
            )
            logger.info("✅ Success: GLM returned text output")
            response_text = stdout_text
        else:
            ccglm_logger.log_process_event(
                context, "empty_response",
                warning="No output or files created"
            )
            logger.warning("⚠️  GLM completed but returned empty response and created no files")
            response_text = "⚠️  GLM execution completed but returned no output or created files. Check GLM logs for details."

        final_response = {
            "response": response_text,
            "model_requested": model,
            "model_configured": env["ANTHROPIC_MODEL"],
            "model_used": model,  # Esto debería verificarse con la API en el futuro
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "execution_time": round(time.time() - start_time, 2),
            "exit_code": process.returncode,
            "files_created": len(new_files),
            "new_files": new_files[:10] if new_files else [],  # Limitar a primeros 10
            "stderr": sanitize_for_log(stderr_text) if stderr_text else None,
            "debug_info": {
                "glm_base_url": GLM_BASE_URL,
                "claude_command": "claude --dangerously-skip-permissions -c -p"
            }
        }

        # Enhanced success logging con métricas detalladas
        ccglm_logger.log_process_event(
            context, "success",
            execution_time=final_response['execution_time'],
            exit_code=process.returncode,
            files_created=len(new_files),
            response_length=len(response_text),
            model_requested=model,
            model_configured=env["ANTHROPIC_MODEL"]
        )

        # Logging detallado de rendimiento
        logger.info(f"🎉 GLM routing completed successfully in {final_response['execution_time']}s")
        logger.info(f"📊 PERFORMANCE METRICS:")
        logger.info(f"  Model requested: {model}")
        logger.info(f"  Model configured: {env['ANTHROPIC_MODEL']}")
        logger.info(f"  Execution time: {final_response['execution_time']}s")
        logger.info(f"  Response length: {len(response_text)} chars")
        logger.info(f"  Files created: {len(new_files)}")
        logger.info(f"  Exit code: {process.returncode}")

        # Alertas de rendimiento
        if final_response['execution_time'] > 60:
            logger.warning(f"⚠️  SLOW RESPONSE: {final_response['execution_time']}s exceeds 60s threshold")
        elif final_response['execution_time'] > 30:
            logger.warning(f"⚠️  MODERATE SLOW RESPONSE: {final_response['execution_time']}s exceeds 30s")

        if model == "glm-4.5-air" and final_response['execution_time'] > 45:
            logger.warning(f"🚨 FAST MODEL SLOW PERFORMANCE: glm-4.5-air took {final_response['execution_time']}s (should be <30s)")
        return final_response

    except FileNotFoundError:
        error_msg = "claude command not found. Make sure Claude CLI is installed and in PATH"
        ccglm_logger.log_process_event(
            context, "command_not_found",
            error_msg=error_msg
        )
        logger.error(f"❌ {error_msg}")
        return {"error": error_msg}
    except Exception as e:
        execution_time = time.time() - start_time
        ccglm_logger.log_process_event(
            context, "unhandled_exception",
            execution_time=execution_time,
            error_type=type(e).__name__,
            error_message=str(e)
        )
        logger.error(f"💥 GLM routing failed after {execution_time:.2f}s: {e}", exc_info=True)
        return {"error": f"Unexpected error: {str(e)}"}


async def main():
    """Main entry point"""
    logger.info("CCGLM MCP Server starting...")
    logger.info("GLM routing mode - routes prompts via Claude CLI to Z.AI GLM backend")
    logger.info(f"GLM endpoint: {GLM_BASE_URL}")
    logger.info(f"Default timeout: {DEFAULT_TIMEOUT}s, Max timeout: {MAX_TIMEOUT}s")

    # Debug logging inicial para variables de entorno
    logger.info("🔧 ENVIRONMENT DEBUG AT STARTUP:")
    logger.info(f"  GLM_BASE_URL: {GLM_BASE_URL}")
    logger.info(f"  GLM_AUTH_TOKEN: {'***CONFIGURED***' if GLM_AUTH_TOKEN else 'NOT_CONFIGURED'}")
    logger.info(f"  ANTHROPIC_MODEL (default): {os.getenv('ANTHROPIC_MODEL', 'NOT_SET')}")
    logger.info(f"  ANTHROPIC_BASE_URL (env): {os.getenv('ANTHROPIC_BASE_URL', 'NOT_SET')}")
    logger.info(f"  ANTHROPIC_AUTH_TOKEN (env): {'***SET***' if os.getenv('ANTHROPIC_AUTH_TOKEN') else 'NOT_SET'}")

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
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
