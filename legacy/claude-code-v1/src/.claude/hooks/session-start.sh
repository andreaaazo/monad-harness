#!/usr/bin/env bash
# SessionStart: inietta lo stato del progetto (.agency/STATE.md) come contesto, con un limite di righe.
# Non scrive nulla. Senza stato, ricorda dove crearlo.
set -uo pipefail
ROOT="${CLAUDE_PROJECT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)}"
STATE="$ROOT/.agency/STATE.md"
DECISIONS="$ROOT/.agency/decisions.md"
if [[ -f "$STATE" && ! -L "$STATE" ]]; then
  printf '%s\n' "Stato del progetto da .agency/STATE.md (fonte autorevole; verificare i file prima di agire):"
  head -n 80 -- "$STATE"
  [[ $(wc -l < "$STATE") -le 80 ]] || printf '%s\n' "[… STATE.md oltre 80 righe: compattarlo]"
  if [[ -f "$DECISIONS" && ! -L "$DECISIONS" ]]; then
    printf '\n%s\n' "Indice decisioni (.agency/decisions.md):"
    grep -E '^## ' -- "$DECISIONS" | head -n 30
  fi
fi
CLIENT_STATUS="$(CLAUDE_PROJECT_DIR="$ROOT" python3 "$ROOT/.claude/scripts/client.py" status --brief 2>/dev/null)"
if [[ -n "$CLIENT_STATUS" ]]; then
  printf '\n%s\n' "$CLIENT_STATUS"
fi
if [[ ! -f "$STATE" ]]; then
  printf '%s\n' "Nessun .agency/STATE.md: per un lavoro che dura più di una sessione crearlo da .claude/design-agency/templates/state.md."
fi
exit 0
