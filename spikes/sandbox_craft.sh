#!/usr/bin/env bash
# ADR-0005 acceptance test: Craft and Blender in bwrap, with no network and a single writable folder.
# It does not use the API and writes nothing outside the temporary folder.
set -u
S="$(mktemp -d)"; trap 'rm -rf "$S"' EXIT
mkdir -p "$S/job" "$S/other"; echo riservato > "$S/other/altro.txt"
echo '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4"/></svg>' > "$S/job/a.svg"
echo '[]' > "$S/job/e.json"
BW=(bwrap --ro-bind /usr /usr --ro-bind /etc /etc --symlink usr/bin /bin --symlink usr/lib /lib
    --symlink usr/lib64 /lib64 --symlink usr/sbin /sbin --proc /proc --dev /dev --tmpfs /tmp
    --bind "$S/job" /job --chdir /job --unshare-net --unshare-pid --die-with-parent)
"${BW[@]}" vectorcraft-cli convert a.svg a.vectorcraft >/dev/null
"${BW[@]}" figcraft-cli run e.json --out f.figcraft >/dev/null
"${BW[@]}" photocraft-cli run --new '{"width":40,"height":40}' --out p.pcraft >/dev/null
"${BW[@]}" effectcraft-cli run file.saveAs '{"path":"/job/e.ecproj"}' >/dev/null
BLENDER="$(readlink -f "$(command -v blender)")"
"${BW[@]}" --ro-bind "$(dirname "$BLENDER")" "$(dirname "$BLENDER")" "$BLENDER" -b \
  --python-expr "import bpy;bpy.ops.wm.save_as_mainfile(filepath='/job/s.blend')" >/dev/null 2>&1
fail=0
for f in a.vectorcraft f.figcraft p.pcraft e.ecproj s.blend; do
  if [[ -s "$S/job/$f" ]]; then echo "ok   $f"; else echo "FAIL $f"; fail=1; fi
done
"${BW[@]}" sh -c "test ! -e '$S/other'" && echo "ok   other folders invisible" || { echo "FAIL isolation"; fail=1; }
"${BW[@]}" sh -c "getent hosts anthropic.com >/dev/null" && { echo "FAIL network present"; fail=1; } || echo "ok   no network"
"${BW[@]}" sh -c "touch /usr/x 2>/dev/null" && { echo "FAIL /usr writable"; fail=1; } || echo "ok   /usr read-only"
exit "$fail"
