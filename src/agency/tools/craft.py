"""Comandi Craft come dati: indice di ricerca, schema a richiesta, esecuzione validata (ADR-0004)."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from agency.tools.files import ensure_dir_under, inside, open_under, replace_under
from agency.tools.sandbox import JOB, Sandbox

TOKEN = re.compile(r"[a-zA-Z0-9]+")
K1, B = 1.5, 0.75


def _tokens(text: str) -> list[str]:
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return [token.lower() for token in TOKEN.findall(spaced)]


@dataclass(frozen=True)
class Command:
    id: str
    label: str
    menu: str
    params: str


class CommandIndex:
    """BM25 sul catalogo della CLI, rigenerato quando cambia la versione."""

    def __init__(self, commands: list[Command]) -> None:
        self.commands = {command.id: command for command in commands}
        self.documents = [
            (
                command.id,
                Counter(
                    _tokens(f"{command.id} {command.id} {command.label} {command.menu} {command.params}")
                ),
            )
            for command in commands
        ]
        self.average = sum(sum(counts.values()) for _, counts in self.documents) / max(len(commands), 1)
        self.frequency: Counter[str] = Counter()
        for _, counts in self.documents:
            self.frequency.update(counts.keys())

    @classmethod
    def load(cls, cache_dir: Path, app: str = "vectorcraft") -> CommandIndex:
        binary = f"{app}-cli"
        version = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=30
        ).stdout.strip()
        cache = cache_dir / f"{app}-{re.sub(r'[^0-9.]', '', version) or 'x'}.json"
        if not cache.exists():
            raw = subprocess.run([binary, "commands"], capture_output=True, text=True, timeout=60, check=True)
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(raw.stdout, encoding="utf-8")
        items = json.loads(cache.read_text(encoding="utf-8"))
        return cls(
            [
                Command(
                    item["id"],
                    item.get("label", ""),
                    " ".join(item.get("menu") or []),
                    item.get("params", ""),
                )
                for item in items
            ]
        )

    def search(self, query: str, limit: int = 12) -> list[Command]:
        total = len(self.documents)
        scored = []
        for command_id, counts in self.documents:
            length = sum(counts.values())
            score = 0.0
            for term in _tokens(query):
                found = counts.get(term, 0)
                if not found:
                    continue
                rarity = math.log(1 + (total - self.frequency[term] + 0.5) / (self.frequency[term] + 0.5))
                score += rarity * found * (K1 + 1) / (found + K1 * (1 - B + B * length / self.average))
            if score:
                scored.append((score, command_id))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [self.commands[command_id] for _, command_id in scored[:limit]]


def run_steps(
    sandbox: Sandbox, index: CommandIndex, document: str, steps: list[dict], operation_id: str
) -> dict:
    """Esegue i passi su una copia e la sostituisce solo a fine lavoro.

    Il risultato vive in `.ops/<operazione>`: se il processo muore, la ripresa ricopia lo stesso
    file invece di ripetere i passi, quindi nessun effetto viene applicato due volte.
    """
    unknown = sorted({step.get("command", "") for step in steps} - set(index.commands))
    if unknown:
        return {"ok": False, "error": f"comandi inesistenti: {', '.join(unknown)}. Usa craft_search."}
    ensure_dir_under(sandbox.work, ".ops")
    ops = sandbox.work / ".ops"
    result_file = ops / f"{operation_id}.result.json"
    built = ops / f"{operation_id}.vectorcraft"
    target = inside(sandbox.work, document)
    if not (result_file.exists() and built.exists()):
        plan = ops / f"{operation_id}.steps.json"
        replace_under(sandbox.work, f".ops/{plan.name}", json.dumps(steps).encode("utf-8"))
        partial = f".ops/{operation_id}.partial.vectorcraft"
        command = ["vectorcraft-cli", "run"]
        if target.exists():
            command += ["--in", f"{JOB}/{document}"]
        command += ["--commands", f"{JOB}/.ops/{plan.name}", "--export", f"{JOB}/{partial}"]
        done = sandbox.run(command, timeout=120)
        if done.code:
            return {"ok": False, "error": done.output.strip()[-900:]}
        results = []
        for line in done.stdout.splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("step") == "cmd":
                results.append(entry.get("result"))
        folder = open_under(sandbox.work, ".ops", os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.replace(Path(partial).name, built.name, src_dir_fd=folder, dst_dir_fd=folder)
        finally:
            os.close(folder)
        replace_under(sandbox.work, f".ops/{result_file.name}", json.dumps(results).encode("utf-8"))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built, target)
    return {"ok": True, "document": document, "results": json.loads(result_file.read_text(encoding="utf-8"))}
