#!/usr/bin/env bash
# Installa la toolchain dello studio a livello utente, fuori dai progetti e senza sudo.
#   bash .claude/tools/setup_tools.sh            # Python (venv + lock) e Node (versioni fisse) + Chromium per Playwright
#   bash .claude/tools/setup_tools.sh --lock     # rigenera requirements.lock (pacchetti pubblicati prima di EXCLUDE_NEWER)
#   bash .claude/tools/setup_tools.sh --system   # stampa soltanto il comando apt per i tool di sistema (richiede sudo, lo esegue l'utente)
#   bash .claude/tools/setup_tools.sh --blender [archivio.tar.xz]   # build ufficiale di Blender (la build apt non ha i kernel GPU)
# Destinazione: $DESIGN_AGENCY_HOME (default ~/.local/share/design-agency); Blender in ~/.local/opt, link in ~/.local/bin.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
HOME_DIR="${DESIGN_AGENCY_HOME:-$HOME/.local/share/design-agency}"
EXCLUDE_NEWER="${EXCLUDE_NEWER:-2026-10-15}"
APT_PACKAGES="inkscape librsvg2-bin potrace libimage-exiftool-perl optipng oxipng webp libavif-bin ghostscript poppler-utils fonts-noto-core"
BLENDER_VERSION="5.2.3"
BLENDER_SHA256="78486c018b4443efe5e75ab54c290ed8c15abafd249b862c2c9ce2530a918eec"
BLENDER_DIR="blender-$BLENDER_VERSION-linux-x64"

if [[ "${1:-}" == --system ]]; then
  printf 'Tool di sistema (da eseguire a cura dell'\''utente):\n  sudo apt install %s\n' "$APT_PACKAGES"
  exit 0
fi

if [[ "${1:-}" == --blender ]]; then
  ARCHIVE="${2:-$HOME_DIR/$BLENDER_DIR.tar.xz}"
  mkdir -p -- "$HOME_DIR" "$HOME/.local/opt" "$HOME/.local/bin"
  [[ -f "$ARCHIVE" ]] || curl -fL --output "$ARCHIVE" \
    "https://download.blender.org/release/Blender${BLENDER_VERSION%.*}/$BLENDER_DIR.tar.xz"
  printf '%s  %s\n' "$BLENDER_SHA256" "$ARCHIVE" | sha256sum --check --quiet
  [[ -x "$HOME/.local/opt/$BLENDER_DIR/blender" ]] || tar -xf "$ARCHIVE" -C "$HOME/.local/opt"
  ln -sfn -- "$HOME/.local/opt/$BLENDER_DIR/blender" "$HOME/.local/bin/blender"
  echo "blender: $HOME/.local/bin/blender ($BLENDER_VERSION)"
  exit 0
fi

command -v uv >/dev/null || { echo "uv assente: installalo da https://docs.astral.sh/uv/ e riprova" >&2; exit 127; }
command -v npm >/dev/null || { echo "npm assente" >&2; exit 127; }
mkdir -p -- "$HOME_DIR"

if [[ "${1:-}" == --lock || ! -f "$HERE/requirements.lock" ]]; then
  uv pip compile "$HERE/requirements.in" --exclude-newer "$EXCLUDE_NEWER" --python-version 3.14 \
    --output-file "$HERE/requirements.lock" --quiet
  echo "lock: $HERE/requirements.lock (pacchetti pubblicati prima di $EXCLUDE_NEWER)"
fi

[[ -x "$HOME_DIR/venv/bin/python" ]] || uv venv --python 3.14 "$HOME_DIR/venv" --quiet
uv pip sync --python "$HOME_DIR/venv/bin/python" "$HERE/requirements.lock" --quiet
echo "python: $HOME_DIR/venv"

mkdir -p -- "$HOME_DIR/node"
cp -- "$HERE/package.json" "$HOME_DIR/node/package.json"
[[ ! -f "$HERE/package-lock.json" ]] || cp -- "$HERE/package-lock.json" "$HOME_DIR/node/package-lock.json"
(cd -- "$HOME_DIR/node" && npm install --no-audit --no-fund --loglevel=error)
cp -- "$HOME_DIR/node/package-lock.json" "$HERE/package-lock.json"
(cd -- "$HOME_DIR/node" && npx --no-install playwright install chromium)
echo "node: $HOME_DIR/node"

echo "Fatto. Verifica: .claude/scripts/py .claude/scripts/tools.py check"
echo "Tool di sistema opzionali: bash .claude/tools/setup_tools.sh --system"
echo "Blender con GPU: bash .claude/tools/setup_tools.sh --blender"
