#!/usr/bin/env bash
# Launcher sottile per i server MCP Craft: confina letture e scritture alla radice dello studio.
set -euo pipefail
AGENCY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd -- "$AGENCY_ROOT"

case "${1:-}" in
  vectorcraft|effectcraft|figcraft|photocraft) AGENCY_APP="$1" ;;
  *) printf '%s\n' 'Uso: start-craft.sh vectorcraft|effectcraft|figcraft|photocraft' >&2; exit 2 ;;
esac
AGENCY_BIN="${AGENCY_APP}-cli"
command -v "$AGENCY_BIN" >/dev/null || { printf 'Eseguibile assente: %s\n' "$AGENCY_BIN" >&2; exit 127; }
AGENCY_HELP="$("$AGENCY_BIN" mcp --help 2>&1 || true)"
for AGENCY_FLAG in --automation-read-root --automation-write-root; do
  if [[ "$AGENCY_HELP" != *"$AGENCY_FLAG"* ]]; then
    printf '%s non espone più %s: rivedere l'\''help della CLI prima di aggiornare il launcher.\n' "$AGENCY_BIN" "$AGENCY_FLAG" >&2
    exit 2
  fi
done
AGENCY_ARGS=(mcp --automation-read-root "$AGENCY_ROOT" --automation-write-root "$AGENCY_ROOT")
case "$AGENCY_APP" in
  vectorcraft)
    [[ "$AGENCY_HELP" != *--headless* ]] || AGENCY_ARGS+=(--headless) ;;
  effectcraft)
    export XDG_CONFIG_HOME="$AGENCY_ROOT/.claude/runtime/config"
    mkdir -p -- "$XDG_CONFIG_HOME"
    # Niente --autosave: il master assegnato si salva esplicitamente.
    case "${AGENCY_EFFECTCRAFT_RENDERER:-auto}" in
      auto) [[ "$AGENCY_HELP" != *--gpu* ]] || AGENCY_ARGS+=(--gpu) ;;
      gpu)
        [[ "$AGENCY_HELP" == *--gpu* ]] || { printf '%s\n' 'Flag --gpu non disponibile in questa CLI.' >&2; exit 2; }
        AGENCY_ARGS+=(--gpu) ;;
      native) ;;
      *) printf '%s\n' 'AGENCY_EFFECTCRAFT_RENDERER deve essere auto, gpu o native.' >&2; exit 2 ;;
    esac ;;
  figcraft|photocraft) ;;  # headless di default con i root; il bridge all'app si configura nell'app stessa
esac
exec "$AGENCY_BIN" "${AGENCY_ARGS[@]}"
