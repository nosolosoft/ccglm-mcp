# CCGLM MCP Server

Servidor MCP que permite usar Claude Code con backend GLM de Z.AI desde la instancia principal de Claude Code (Anthropic Sonnet).

## 🎯 Propósito

Permite a Claude Code (con Sonnet de Anthropic) invocar otra instancia de Claude Code que utiliza los modelos GLM de Z.AI como backend, sin necesidad de cambiar la configuración principal.

## 🏗️ Arquitectura

```
Claude Code (Sonnet Anthropic)
    ↓
MCP Tool: mcp__ccglm-mcp__glm_route
    ↓
CCGLM MCP Server
    ↓
Claude CLI con env vars GLM
    ↓
Z.AI GLM API (https://api.z.ai/api/anthropic)
    ↓
Modelo GLM-4.6
```

## 📦 Instalación

### 1. Instalar Dependencias

```bash
cd ~/IA/ccglm-mcp
pip install -r requirements.txt
```

### 2. Configurar Credentials

Ya está configurado en `.env`:

```bash
GLM_BASE_URL=https://api.z.ai/api/anthropic
GLM_AUTH_TOKEN=5951e8ffb37b4f038ba9a47f49e86ff4.ZYOeeSK1MWARJ8YB
```

### 3. Registrar Servidor MCP

Añadir a `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "ccglm-mcp": {
      "command": "python3",
      "args": ["/home/manu/IA/ccglm-mcp/ccglm_mcp_server.py"],
      "timeout": 300000
    }
  }
}
```

### 4. Configurar Alias (Opcional)

Añadir a `~/.zshrc`:

```bash
# Z.AI GLM Integration
export GLM_API_TOKEN="5951e8ffb37b4f038ba9a47f49e86ff4.ZYOeeSK1MWARJ8YB"
alias ccglm='ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic ANTHROPIC_AUTH_TOKEN=$GLM_API_TOKEN claude --dangerously-skip-permissions -c'
```

Recargar:
```bash
source ~/.zshrc
```

## 🛠️ Herramienta Disponible

### `glm_route`

Única herramienta del servidor CCGLM-MCP. Enruta prompt a GLM-4.6 vía Claude CLI con backend Z.AI. Maneja todos los casos de uso: generación de código, análisis profundo y consultas generales.

**Uso desde Claude Code:**
```
Usa la herramienta mcp__ccglm-mcp__glm_route con el prompt: "Tu tarea aquí"
```

**Uso con hashtag (configurado en CLAUDE.md):**
```
#ccglm Explica qué es recursión
#ccglm Genera una API REST en Python
#ccglm Analiza este código en detalle
```

**Características:**
- ✅ Generación de código con tracking de archivos
- ✅ Análisis profundo (timeout 30 minutos)
- ✅ Consultas generales
- ✅ Excluye archivos internos (.claude/, .git/, etc.) del tracking

**Nota:** Usa el modelo GLM-4.6 configurado en `~/.claude/settings.json`.

## 🧪 Testing

Ejecutar tests:

```bash
cd ~/IA/ccglm-mcp
python3 test_server.py
```

Tests incluidos:
- ✅ File tracking (detección de archivos creados)
- ✅ Log sanitization (redacción de tokens)
- ⏸️ Basic prompt (comentado - requiere API call)
- ⏸️ Code generation (comentado - requiere API call)

## 🔒 Seguridad

- **Token protegido**: Almacenado en `.env` (gitignored)
- **Logs sanitizados**: Token redactado automáticamente en logs
- **Environment isolation**: Variables de entorno inyectadas solo en subprocess
- **Permisos**: `.env` debe tener permisos 0600

## 📊 Logging

Todos los logs van a **stderr** (no stdout) para no interferir con el protocolo MCP stdio.

**Ver logs en tiempo real:**
```bash
python3 /home/manu/IA/ccglm-mcp/ccglm_mcp_server.py 2>&1 | grep -i glm
```

**Niveles de log:**
- `INFO`: Operaciones normales
- `WARNING`: Situaciones anómalas
- `ERROR`: Fallos

## ⚙️ Configuración Avanzada

### Timeouts

Configurados en `ccglm_mcp_server.py`:

- `DEFAULT_TIMEOUT = 600` (10 minutos)
- `MAX_TIMEOUT = 2400` (40 minutos)

### Flags de Claude CLI

El servidor ejecuta Claude CLI con:
```bash
claude --dangerously-skip-permissions -c -p
```

- `--dangerously-skip-permissions`: Skip permissions prompts
- `-c`: Continue mode
- `-p`: Print mode (non-interactive)

## 🐛 Troubleshooting

### Error: "claude command not found"

Verifica que Claude CLI está instalado:
```bash
which claude
```

Si no está, instalar:
```bash
npm install -g @anthropic-ai/claude-code
```

### Error: "GLM authentication failed"

Verifica que el token en `.env` es correcto y está activo.

### Timeout errors

Si GLM tarda mucho, aumenta los timeouts en `ccglm_mcp_server.py`.

### No aparece en herramientas MCP

1. Verifica registro en `~/.claude/settings.json`
2. Reinicia Claude Code
3. Verifica logs: `python3 ccglm_mcp_server.py`

## 📝 Uso desde Terminal

Además del servidor MCP, puedes usar GLM directamente desde terminal con el alias:

```bash
# Uso interactivo
ccglm

# Con prompt directo
echo "Explain recursion" | ccglm
```

## 🔄 Actualización

Para actualizar el servidor:

```bash
cd ~/IA/ccglm-mcp
git pull  # Si está en git
pip install -r requirements.txt --upgrade
```

Reiniciar Claude Code para recargar el servidor MCP.

## 📚 Referencias

- [Documentación Z.AI GLM](https://docs.z.ai/devpack/tool/claude)
- [MCP Protocol](https://github.com/anthropics/mcp)
- [Claude Code CLI](https://github.com/anthropics/claude-code)

## 🤝 Créditos

- Basado en patrón de `ccr-mcp`
- Integración con Z.AI GLM API
- Implementado como parte del ecosistema Claude hybrid system

## 📄 Licencia

Uso interno - No redistribuir con credentials
