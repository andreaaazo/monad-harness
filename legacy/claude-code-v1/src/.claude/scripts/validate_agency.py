#!/usr/bin/env python3
"""Valida il setup dello studio: ciò che la documentazione nomina deve esistere.

  validate_agency.py            # struttura, frontmatter, JSON, percorsi citati, script
  validate_agency.py --env      # anche eseguibili e moduli Python richiesti
  validate_agency.py --template # anche igiene del template (nessuno stato cliente)

Esce con 1 se trova errori. Solo libreria standard.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLAUDE = ROOT / ".claude"
# Percorsi che vivono nel progetto cliente, non nel template.
PROJECT_PREFIXES = (".agency/", "work/", "brand/", "proofs/", "exports/", "source/")
PATH_RE = re.compile(r"`([^`\s]+\.(?:md|py|mjs|sh|json|svg|png))`")
LINK_RE = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")

errors, warnings = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end < 0:
        return None, text
    data, key = {}, None
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if m:
            key, value = m.group(1), m.group(2).strip()
            if value.startswith("[") and value.endswith("]"):
                value = [v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()]
            elif value == "":
                value = []
            else:
                value = value.strip("\"'")
            data[key] = value
        elif line.lstrip().startswith("- ") and key and isinstance(data.get(key), list):
            data[key].append(line.lstrip()[2:].strip().strip("\"'"))
        else:
            err(f"{path.relative_to(ROOT)}: riga di frontmatter non riconosciuta: {line!r}")
    return data, text[end + 4:]


def check_json():
    for rel in (".mcp.json", ".claude/settings.json", ".claude/settings.local.json"):
        p = ROOT / rel
        if not p.exists():
            if rel != ".claude/settings.local.json":
                err(f"{rel}: assente")
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            err(f"{rel}: JSON non valido ({exc})")
            continue
        blob = json.dumps(data)
        for script in re.findall(r"\.claude/(?:scripts|hooks)/[\w.-]+", blob):
            if not (ROOT / script).exists():
                err(f"{rel}: riferisce {script}, che non esiste")
        if rel == ".mcp.json":
            for name, cfg in data.get("mcpServers", {}).items():
                cmd = cfg.get("command")
                if cmd and not shutil.which(cmd):
                    warn(f".mcp.json: server {name}: comando {cmd} non nel PATH")


def check_registries():
    """checks.json e budgets.json parlano solo di ruoli reali; i documenti solo di controlli registrati."""
    agents = {p.stem for p in (CLAUDE / "agents").glob("*.md")}
    try:
        checks = json.loads((CLAUDE / "design-agency/checks.json").read_text(encoding="utf-8"))["checks"]
        budgets = json.loads((CLAUDE / "design-agency/budgets.json").read_text(encoding="utf-8"))
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        err(f"registri dello studio: {exc}")
        return
    for name, spec in checks.items():
        if spec.get("kind") not in ("measure", "requirement", "observation", "reading", "judgement"):
            err(f"checks.json: {name}: kind non valido")
        if spec.get("independent") and not spec.get("roles"):
            err(f"checks.json: {name}: un controllo indipendente dichiara chi lo firma")
        for role in spec.get("roles", []):
            if role not in agents:
                err(f"checks.json: {name}: ruolo inesistente {role}")
    for role in budgets.get("agents", {}):
        if role not in agents:
            err(f"budgets.json: ruolo inesistente {role}")
    for doc in ("HANDOFFS.md", "QA.md"):
        text = (CLAUDE / "design-agency" / doc).read_text(encoding="utf-8")
        for spec in re.findall(r"`[^`]*=([a-z_+]+)`", text):
            for name in spec.split("+"):
                if name and name not in checks:
                    err(f"{doc}: controllo non registrato {name}")
        rows = text.split("## Controlli per deliverable")[-1] if doc == "QA.md" else ""
        for name in re.findall(r"`([a-z]+_[a-z_]+)`", rows):
            if name not in checks and not name.endswith(("_check.py",)) and name not in ("record_by",):
                err(f"QA.md: controllo non registrato {name}")


def check_skills():
    names = set()
    global NO_PRELOAD
    NO_PRELOAD = set()
    for skill in sorted((CLAUDE / "skills").glob("*/SKILL.md")):
        rel = skill.relative_to(ROOT)
        fm, body = frontmatter(skill)
        if fm is None:
            err(f"{rel}: frontmatter assente")
            continue
        if fm.get("name") != skill.parent.name:
            err(f"{rel}: name '{fm.get('name')}' diverso dalla cartella '{skill.parent.name}'")
        if not fm.get("description"):
            err(f"{rel}: description assente")
        elif len(fm["description"]) > 1024:
            warn(f"{rel}: description oltre 1024 caratteri")
        names.add(skill.parent.name)
        if str(fm.get("disable-model-invocation", "")).lower() == "true":
            NO_PRELOAD.add(skill.parent.name)
    return names


def check_python():
    for script in sorted(CLAUDE.rglob("*.py")):
        try:
            compile(script.read_text(encoding="utf-8"), str(script), "exec")
        except SyntaxError as exc:
            err(f"{script.relative_to(ROOT)}: errore di sintassi riga {exc.lineno}: {exc.msg}")


def check_agents(skill_names):
    agents = sorted((CLAUDE / "agents").glob("*.md"))
    if not agents:
        err(".claude/agents/: nessun agente")
    names = set()
    for agent in agents:
        rel = agent.relative_to(ROOT)
        fm, _ = frontmatter(agent)
        if fm is None:
            err(f"{rel}: frontmatter assente")
            continue
        if fm.get("name") != agent.stem:
            err(f"{rel}: name '{fm.get('name')}' diverso dal file")
        if not fm.get("description"):
            err(f"{rel}: description assente")
        skills = fm.get("skills", [])
        for s in skills if isinstance(skills, list) else [skills]:
            if s not in skill_names:
                err(f"{rel}: skill precaricata '{s}' inesistente")
            elif s in NO_PRELOAD:
                err(f"{rel}: '{s}' ha disable-model-invocation e non può essere precaricata")
        names.add(agent.stem)
    return names


ROLE_SUFFIXES = ("-director", "-designer", "-manager", "-inspector", "-reviewer", "-developer", "-strategist",
                 "-artist", "-researcher", "-writer", "-critic", "-lead", "-specialist")
SINGLE_ROLES = {"researcher", "copywriter", "critic", "illustrator", "typographer"}


def role_like(token):
    return token.endswith(ROLE_SUFFIXES) or token in SINGLE_ROLES


def check_org(agent_names):
    """Organigramma e catalogo: ogni agente vi compare, ogni ruolo nominato ha un file."""
    org = CLAUDE / "design-agency/ORG.md"
    if not org.exists():
        err("design-agency/ORG.md assente")
        return
    org_text = org.read_text(encoding="utf-8")
    for a in sorted(agent_names - set(re.findall(r"`([a-z]+(?:-[a-z]+)*)`", org_text))):
        err(f"ORG.md: l'agente `{a}` non compare nell'organigramma")
    for doc in ("ORG.md", "SERVICES.md", "ROUTING.md", "QA.md", "CLIENT.md", "HANDOFFS.md"):
        path = CLAUDE / "design-agency" / doc
        if not path.exists():
            err(f"design-agency/{doc} assente")
            continue
        # Nomi di ruolo, con o senza backtick, in tabelle e testo.
        for token in sorted(set(re.findall(r"(?<![\w/.-])([a-z]+(?:-[a-z]+)*)(?![\w/.-])", path.read_text(encoding="utf-8")))):
            if role_like(token) and token not in agent_names:
                err(f"{doc}: ruolo `{token}` senza file in .claude/agents/")


def check_references(agent_names):
    for md in sorted(CLAUDE.rglob("*.md")):
        if "runtime" in md.parts:
            continue
        rel = md.relative_to(ROOT)
        text = md.read_text(encoding="utf-8")
        for target in PATH_RE.findall(text):
            if any(c in target for c in "<>*{}$") or target.startswith(PROJECT_PREFIXES) or "://" in target:
                continue
            # Convenzione dichiarata nei prompt: templates/, references/ e i documenti in maiuscolo
            # stanno in .claude/design-agency/.
            candidates = [ROOT / target, md.parent / target, md.parent.parent / target,
                          CLAUDE / "design-agency" / target]
            if target.startswith("scripts/"):
                # Dentro una skill, `scripts/x.py` è relativo alla cartella della skill.
                skill_dir = next((p for p in md.parents if p.parent.name == "skills"), None)
                if skill_dir:
                    candidates.append(skill_dir / target)
            if "/" not in target:
                continue  # nomi di file d'esempio, non percorsi
            if not any(c.exists() for c in candidates):
                err(f"{rel}: percorso citato inesistente `{target}`")
        for target in LINK_RE.findall(text):
            if "://" in target or target.startswith("mailto:"):
                continue
            if not (md.parent / target).exists():
                err(f"{rel}: link rotto ({target})")
        for name in re.findall(r"`([a-z]+(?:-[a-z]+)+)`\s*\(agente\)", text):
            if name not in agent_names:
                err(f"{rel}: agente `{name}` inesistente")


def check_template():
    for rel in (".claude/PROGRESS.md", ".claude/memory.json", ".agency"):
        if (ROOT / rel).exists():
            err(f"template: {rel} contiene stato di un progetto")
    runtime = CLAUDE / "runtime"
    if runtime.exists() and any(runtime.iterdir()):
        err("template: .claude/runtime/ non è vuota")


def check_env():
    for exe, why in (("claude", "Claude Code"), ("vectorcraft-cli", "VectorCraft MCP e rendering SVG"),
                     ("effectcraft-cli", "EffectCraft MCP"), ("ffmpeg", "motion_probe"),
                     ("ffprobe", "motion_probe")):
        if not shutil.which(exe):
            warn(f"env: {exe} assente ({why})")
    for exe in ("vectorcraft-cli", "effectcraft-cli", "figcraft-cli", "photocraft-cli"):
        if shutil.which(exe):
            out = subprocess.run([exe, "mcp", "--help"], capture_output=True, text=True, timeout=20)
            text = out.stdout + out.stderr
            for flag in ("--automation-read-root", "--automation-write-root"):
                if flag not in text:
                    err(f"env: {exe} mcp non espone {flag}: start-craft.sh non può confinare i file")
    for mod, why in (("PIL", "logo_proof"), ("numpy", "motion_probe")):
        try:
            __import__(mod)
        except ImportError:
            warn(f"env: modulo Python {mod} assente ({why})")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--env", action="store_true")
    p.add_argument("--template", action="store_true")
    args = p.parse_args()

    check_json()
    check_registries()
    skills = check_skills()
    check_python()
    agents = check_agents(skills)
    check_org(agents)
    check_references(agents)
    if shutil.which("node"):
        for mjs in sorted(CLAUDE.rglob("*.mjs")):
            res = subprocess.run(["node", "--check", str(mjs)], capture_output=True, text=True)
            if res.returncode:
                msg = next((l for l in res.stderr.splitlines() if "Error" in l), res.stderr.strip()[:200])
                err(f"{mjs.relative_to(ROOT)}: sintassi JS ({msg.strip()})")
    for sh in list((CLAUDE / "scripts").glob("*.sh")) + list((CLAUDE / "hooks").glob("*.sh")) \
            + list((CLAUDE / "tools").glob("*.sh")) + [CLAUDE / "scripts/py", CLAUDE / "scripts/node"]:
        res = subprocess.run(["bash", "-n", str(sh)], capture_output=True, text=True)
        if res.returncode:
            err(f"{sh.relative_to(ROOT)}: sintassi bash ({res.stderr.strip()})")
    if args.template:
        check_template()
    if args.env:
        check_env()

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"{len(skills)} skill, {len(agents)} agenti — {len(errors)} errori, {len(warnings)} avvisi")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
