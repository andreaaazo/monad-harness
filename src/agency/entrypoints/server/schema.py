"""Lo schema OpenAPI del cruscotto, generato dai modelli di insights: `uv run agency-schemas` (ADR-0022).

Si versiona in `schemas/openapi.json`, e da lì nascono i tipi TypeScript dell'interfaccia. Le chiavi sono in
ordine e il file finisce con un a capo: due generazioni uguali danno lo stesso file, e il diff si legge.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

SETTINGS = "agency.entrypoints.server.settings"
OUTPUT = Path("schemas/openapi.json")  # rispetto alla radice del repository, da cui si lancia il comando


def render() -> str:
    os.environ["DJANGO_SETTINGS_MODULE"] = SETTINGS  # sempre queste: lo schema è quello del server vero
    # Import qui dentro: Django Ninja legge le impostazioni già all'import, quindi viene dopo django.setup().
    import django

    django.setup()
    from agency.entrypoints.server.api import api

    return json.dumps(api.get_openapi_schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agency-schemas", description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true", help="non scrive: fallisce se non è allineato")
    args = parser.parse_args(argv)
    current = render()
    if args.check:
        if args.output.is_file() and args.output.read_text(encoding="utf-8") == current:
            print(f"schema allineato: {args.output}")
            return 0
        print(f"schema non allineato: {args.output}. Rigeneralo con uv run agency-schemas")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(current, encoding="utf-8")
    print(f"schema scritto: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
