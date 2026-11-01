#!/usr/bin/env python3
"""Controlla un file di token in formato DTCG (Design Tokens Format Module 2025.10).

Verifica: $type presente o ereditato, tipi noti, alias {gruppo.token} risolvibili,
cicli di alias, forma dei valori color/dimension/duration/cubicBezier/fontWeight.
Solo libreria standard.  Uso: tokens_check.py tokens.json [--list]
"""
import argparse
import json
import re
import sys

TYPES = {"color", "dimension", "fontFamily", "fontWeight", "duration", "cubicBezier", "number",
         "strokeStyle", "border", "transition", "shadow", "gradient", "typography"}
ALIAS = re.compile(r"^\{([^{}]+)\}$")
COLOR_SPACES = {"srgb", "srgb-linear", "hsl", "hwb", "lab", "lch", "oklab", "oklch", "display-p3",
                "a98-rgb", "prophoto-rgb", "rec2020", "xyz-d65", "xyz-d50"}


def walk(node, path, inherited, out, problems):
    if not isinstance(node, dict):
        problems.append(("error", ".".join(path), "nodo non oggetto"))
        return
    own_type = node.get("$type", inherited)
    if "$value" in node:
        out[".".join(path)] = {"type": own_type, "value": node["$value"]}
        return
    for key, child in node.items():
        if key.startswith("$"):
            continue
        if any(c in key for c in "{}."):
            problems.append(("error", ".".join(path + [key]), "nome con caratteri riservati { } ."))
            continue
        walk(child, path + [key], own_type, out, problems)


def resolve(name, tokens, seen=()):
    if name in seen:
        raise ValueError("ciclo: " + " → ".join(seen + (name,)))
    if name not in tokens:
        raise KeyError(name)
    value = tokens[name]["value"]
    m = ALIAS.match(value) if isinstance(value, str) else None
    return resolve(m.group(1), tokens, seen + (name,)) if m else (name, value)


def check_value(kind, value):
    if kind == "color":
        if isinstance(value, str):
            return "warning", "colore come stringa: in 2025.10 il valore è {colorSpace, components, alpha?, hex?}"
        if not isinstance(value, dict) or value.get("colorSpace") not in COLOR_SPACES \
                or not isinstance(value.get("components"), list) or len(value["components"]) != 3:
            return "error", "colore non valido: servono colorSpace noto e 3 components"
    elif kind in ("dimension", "duration"):
        units = {"px", "rem"} if kind == "dimension" else {"ms", "s"}
        if not isinstance(value, dict) or not isinstance(value.get("value"), (int, float)) \
                or value.get("unit") not in units:
            return "error", f"{kind}: atteso {{value: numero, unit: {'|'.join(sorted(units))}}}"
    elif kind == "cubicBezier":
        if not (isinstance(value, list) and len(value) == 4 and all(isinstance(v, (int, float)) for v in value)
                and 0 <= value[0] <= 1 and 0 <= value[2] <= 1):
            return "error", "cubicBezier: [x1, y1, x2, y2] con x1, x2 in 0–1"
    elif kind == "fontWeight":
        names = {"thin", "hairline", "extra-light", "ultra-light", "light", "normal", "regular", "book",
                 "medium", "semi-bold", "demi-bold", "bold", "extra-bold", "ultra-bold", "black", "heavy",
                 "extra-black", "ultra-black"}
        if not ((isinstance(value, (int, float)) and 1 <= value <= 1000) or value in names):
            return "error", "fontWeight: numero 1–1000 o nome standard"
    elif kind == "number" and not isinstance(value, (int, float)):
        return "error", "number: atteso un numero"
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file")
    p.add_argument("--list", action="store_true", help="elenca i token risolti")
    args = p.parse_args()
    try:
        with open(args.file, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"ERROR {args.file}: {exc}")

    tokens, problems = {}, []
    walk(data, [], None, tokens, problems)
    for name, tok in tokens.items():
        value = tok["value"]
        m = ALIAS.match(value) if isinstance(value, str) else None
        try:
            target, resolved = resolve(name, tokens)
        except KeyError as exc:
            problems.append(("error", name, f"alias non risolto: {exc.args[0]}"))
            continue
        except ValueError as exc:
            problems.append(("error", name, str(exc)))
            continue
        kind = tok["type"] or (tokens[target]["type"] if m else None)
        if kind is None:
            problems.append(("error", name, "$type assente e non ereditato"))
            continue
        if kind not in TYPES:
            problems.append(("error", name, f"$type sconosciuto: {kind}"))
            continue
        if m and tokens[target]["type"] not in (None, kind):
            problems.append(("error", name, f"alias verso un tipo diverso ({tokens[target]['type']})"))
        issue = check_value(kind, resolved)
        if issue:
            problems.append((issue[0], name, issue[1]))
        if args.list:
            print(f"{name}  [{kind}]  {json.dumps(resolved, ensure_ascii=False)}" + (f"  ← {{{m.group(1)}}}" if m else ""))

    for level, name, msg in problems:
        print(f"{level.upper():7} {name or '(radice)'}: {msg}")
    errors = sum(1 for p_ in problems if p_[0] == "error")
    print(f"{len(tokens)} token, {errors} errori, {len(problems) - errors} avvisi")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
