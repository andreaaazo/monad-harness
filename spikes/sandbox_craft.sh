#!/usr/bin/env bash
# ADR-0005 acceptance test: Craft and Blender run in the engine's own sandbox, with no network and a single
# writable folder. Run it from anywhere in the checkout: bash spikes/sandbox_craft.sh. It does not use the API and
# writes nothing outside its temporary folder. It stays out of `task check`: the Craft CLIs are licensed tools.
set -u
cd "$(dirname "$0")/.."

missing=()
for tool in uv bwrap systemd-run blender vectorcraft-cli figcraft-cli photocraft-cli effectcraft-cli; do
  command -v "$tool" >/dev/null || missing+=("$tool")
done
if ((${#missing[@]})); then
  echo "FAIL missing: ${missing[*]}. Install them as docs/04-TOOLS.md says, then run this again." >&2
  exit 1
fi

S="$(mktemp -d)"; trap 'rm -rf "$S"' EXIT
mkdir -p "$S/job" "$S/other"; echo reserved > "$S/other/other.txt"
echo '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4"/></svg>' > "$S/job/a.svg"
echo '[]' > "$S/job/e.json"
BLENDER="$(readlink -f "$(command -v blender)")"

# The prefix of the engine's own sandbox (agency.tools.sandbox): the same cgroup scope, mounts and namespaces, not
# a copy of them, started as the engine starts it, with only HOST_VARIABLES of this shell's environment (bwrap is
# pid 1 inside, and its environment is readable at /proc/1/environ). Blender's folder is bound read-only on top,
# as the engine binds its toolchain folder.
if ! mapfile -d '' -t BW < <(uv run --locked python -c '
import sys
from pathlib import Path
from agency.tools.sandbox import Sandbox, host_environment
environment = [f"{name}={value}" for name, value in host_environment().items()]
argv = Sandbox(Path(sys.argv[1]), read_only=(Path(sys.argv[2]),)).argv([])
print("\0".join(["env", "-i", *environment, *argv]), end="")
' "$S/job" "$(dirname "$BLENDER")") || ((${#BW[@]} == 0)); then
  echo "FAIL the engine's sandbox command could not be built: run task setup first." >&2
  exit 1
fi

fail=0
step() {  # step <file it must create> <command...>: the tool's output is kept and shown if it fails
  local file="$1"; shift
  "${BW[@]}" "$@" >"$S/$file.log" 2>&1
  if [[ -s "$S/job/$file" ]]; then
    echo "ok   $file"
  else
    echo "FAIL $file"; tail -n 5 "$S/$file.log" | sed 's/^/     /'; fail=1
  fi
}
step a.vectorcraft vectorcraft-cli convert a.svg a.vectorcraft
step f.figcraft figcraft-cli run e.json --out f.figcraft
step p.pcraft photocraft-cli run --new '{"width":40,"height":40}' --out p.pcraft
step e.ecproj effectcraft-cli run file.saveAs '{"path":"/job/e.ecproj"}'
step s.blend "$BLENDER" -b --python-expr "import bpy;bpy.ops.wm.save_as_mainfile(filepath='/job/s.blend')"

# Each probe prints its word only when its own condition holds inside the sandbox, so a sandbox that never
# started can never pass as isolated.
probe() {  # probe <label> <word> <shell command that prints the word when the condition holds>
  if [[ "$("${BW[@]}" sh -c "$3" 2>/dev/null)" == "$2" ]]; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi
}
probe "other folders invisible" hidden "test -e '$S/other' || echo hidden"
probe "no network" offline "getent hosts anthropic.com >/dev/null || echo offline"
probe "/usr read-only" readonly "touch /usr/x 2>/dev/null || echo readonly"
# A fake key in this shell's environment must reach no process of the sandbox, bwrap's own included. The
# environments must be readable (each holds a PATH=), or an empty read would pass for a clean one.
ANTHROPIC_API_KEY=sk-ant-spike-canary probe "no key in the sandbox" keyless \
  "all=\$(cat /proc/[0-9]*/environ 2>/dev/null | tr '\\0' '\\n'); \
   printf '%s\\n' \"\$all\" | grep -q '^PATH=' && ! printf '%s\\n' \"\$all\" | grep -q sk-ant-spike-canary && echo keyless"
exit "$fail"
