"""Craft commands as data: a search index, a schema on request, validated execution (ADR-0004)."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from agency.contracts.sandbox import JOB, OPS, SandboxPort
from agency.workshop.files import (
    MAX_DOCUMENT_BYTES,
    MAX_TEXT_FILE_BYTES,
    ensure_dir_under,
    inside,
    is_file_under,
    read_under,
    replace_under,
)

TOKEN = re.compile(r"[a-zA-Z0-9]+")
PARTIAL = ".partial"  # in /job: where vectorcraft-cli exports, before the harness copies the result out
K1, B = 1.5, 0.75


def _tokens(text: str) -> list[str]:
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return [token.lower() for token in TOKEN.findall(spaced)]


@dataclass(frozen=True)
class Command:
    """One command of a Craft CLI's catalogue, as its `commands` subcommand lists it."""

    id: str
    label: str
    menu: str
    params: str


class CommandIndex:
    """BM25 over the CLI's command catalogue, fetched again when the CLI's version changes."""

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
        # The CLI runs on the host, outside the sandbox: it gets PATH alone, so the API key and anything else
        # in the harness's environment stay out, as for the fingerprint's tool versions.
        host = {"PATH": os.environ.get("PATH", "")}
        version = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=30, env=host
        ).stdout.strip()
        cache = cache_dir / f"{app}-{re.sub(r'[^0-9.]', '', version) or 'x'}.json"
        if not cache.exists():
            raw = subprocess.run(
                [binary, "commands"], capture_output=True, text=True, timeout=60, check=True, env=host
            )
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
    sandbox: SandboxPort,
    index: CommandIndex,
    document: str,
    steps: list[dict],
    operation_id: str,
    records: Path,
) -> dict:
    """Runs the steps on a copy and replaces the document only when they are done.

    The plan goes to the sandbox's /ops, which it cannot write. The record of the run, its results and the
    built document, is the harness's copy in `records`, which no sandbox sees. If the process dies, resume
    copies the same document again instead of repeating the steps, so no effect is applied twice. Nothing
    the sandbox can write, in /job or anywhere else, is ever read as a record (ADR-0044).
    """
    unknown = sorted({step.get("command", "") for step in steps} - set(index.commands))
    if unknown:
        return {"ok": False, "error": f"comandi inesistenti: {', '.join(unknown)}. Usa craft_search."}
    inputs = sandbox.ops
    if inputs is None:
        raise ValueError("run_steps needs a sandbox with its /ops folder: the plan never goes into /job")
    result_name, built_name = f"{operation_id}.result.json", f"{operation_id}.vectorcraft"
    inside(sandbox.work, document)
    if not ((records / result_name).is_file() and (records / built_name).is_file()):
        plan = f"{operation_id}.steps.json"
        replace_under(inputs, plan, json.dumps(steps).encode("utf-8"))
        ensure_dir_under(sandbox.work, PARTIAL)
        partial = f"{PARTIAL}/{built_name}"
        command = ["vectorcraft-cli", "run"]
        if is_file_under(sandbox.work, document):
            command += ["--in", f"{JOB}/{document}"]
        command += ["--commands", f"{OPS}/{plan}", "--export", f"{JOB}/{partial}"]
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
        replace_under(records, built_name, read_under(sandbox.work, partial, MAX_DOCUMENT_BYTES))
        replace_under(records, result_name, json.dumps(results).encode("utf-8"))
    folder = PurePosixPath(document).parent
    if folder.parts:
        ensure_dir_under(sandbox.work, str(folder))
    replace_under(sandbox.work, document, read_under(records, built_name, MAX_DOCUMENT_BYTES))
    return {
        "ok": True,
        "document": document,
        "results": json.loads(read_under(records, result_name, MAX_TEXT_FILE_BYTES)),
    }
