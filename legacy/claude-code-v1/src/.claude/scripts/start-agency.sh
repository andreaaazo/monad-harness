#!/usr/bin/env bash
# Avvia Claude dalla radice dello studio con i soli server MCP locali.
# Non modifica la configurazione globale (una voce globale VectorCraft obsoleta resta ignorata).
set -euo pipefail
AGENCY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd -- "$AGENCY_ROOT"
# --strict-mcp-config dopo --mcp-config, così gli argomenti dell'utente restano separati.
exec claude --mcp-config "$AGENCY_ROOT/.mcp.json" --strict-mcp-config "$@"
