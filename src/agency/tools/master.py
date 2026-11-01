"""Master di produzione: ogni mezzo ha il suo file, e le consegne derivano da lì."""

from __future__ import annotations

import json
from dataclasses import dataclass

from agency.contracts.ticket import Medium
from agency.ledger import Ledger
from agency.ledger.models import DerivationRow
from agency.ledger.store import now
from agency.tools.files import inside, sha256
from agency.tools.sandbox import JOB, Sandbox


@dataclass(frozen=True)
class MediumSpec:
    master: str
    tool: str
    exports: tuple[str, ...]


MEDIA: dict[Medium, MediumSpec] = {
    Medium.VECTOR: MediumSpec(".vectorcraft", "VectorCraft", (".svg", ".pdf", ".eps", ".ai", ".png")),
    Medium.MOTION: MediumSpec(
        ".ecproj", "EffectCraft", (".mp4", ".mov", ".webm", ".gif", ".json", ".lottie")
    ),
    Medium.IMAGE: MediumSpec(".pcraft", "PhotoCraft", (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp")),
    Medium.INTERFACE: MediumSpec(".figcraft", "FigCraft", (".png", ".svg", ".pdf", ".webp", ".jpg")),
    Medium.THREE_D: MediumSpec(".blend", "Blender", ()),
}


def problem(sandbox: Sandbox, relative: str) -> str | None:
    """None se il master si apre e contiene lavoro; altrimenti il motivo."""
    path = inside(sandbox.work, relative)
    if not path.exists():
        return "non esiste"
    target = f"{JOB}/{relative}"
    extension = path.suffix.lower()
    if extension == ".vectorcraft":
        done = sandbox.run(["vectorcraft-cli", "info", target])
        if done.code:
            return f"VectorCraft non lo apre: {done.output.strip()[:200]}"
        return None if json.loads(done.stdout).get("info", {}).get("objects", 0) > 1 else "documento vuoto"
    if extension == ".figcraft":
        done = sandbox.run(["figcraft-cli", "info", target, "--json"])
        if done.code:
            return f"FigCraft non lo apre: {done.output.strip()[:200]}"
        frames = sum(page.get("topLevel", 0) for page in json.loads(done.stdout).get("pages", []))
        return None if frames else "documento vuoto: nessun frame"
    if extension == ".pcraft":
        done = sandbox.run(["photocraft-cli", "info", target])
        if done.code:
            return f"PhotoCraft non lo apre: {done.output.strip()[:200]}"
        return None if json.loads(done.stdout).get("layers") else "documento vuoto: nessun livello"
    if extension == ".ecproj":
        done = sandbox.run(["effectcraft-cli", "info", "--project", target, "--json"])
        if done.code:
            return f"EffectCraft non lo apre: {done.output.strip()[:200]}"
        layers = (json.loads(done.stdout).get("activeComp") or {}).get("layers")
        return None if layers else "progetto vuoto: nessun livello"
    if extension == ".blend":
        head = path.read_bytes()[:8]
        known = head[:7] == b"BLENDER" or head[:4] == b"\x28\xb5\x2f\xfd" or head[:2] == b"\x1f\x8b"
        return None if known else "non è un file Blender"
    return f"{extension}: non è un master dello studio"


def export(
    sandbox: Sandbox, ledger: Ledger, project: str, master: str, output: str, options: list[str]
) -> str | None:
    """Esporta dal master e registra il legame. Restituisce l'errore, se c'è."""
    why = problem(sandbox, master)
    if why:
        return f"{master}: {why}"
    if not master.lower().endswith(".vectorcraft"):
        return "in M1 l'export è disponibile solo per VectorCraft"
    destination = inside(sandbox.work, output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    done = sandbox.run(["vectorcraft-cli", "convert", f"{JOB}/{master}", f"{JOB}/{output}", *options])
    if done.code or not destination.exists():
        return f"export fallito: {done.output.strip()[:300]}"
    ledger.add_derivation(
        DerivationRow(
            at=now(),
            project=project,
            master=master,
            master_sha=sha256(inside(sandbox.work, master)),
            export=output,
            export_sha=sha256(destination),
            how="vectorcraft-cli convert",
        )
    )
    return None


def derivation_problem(
    sandbox: Sandbox, ledger: Ledger, project: str, export_path: str, masters: list[str]
) -> str | None:
    current = sha256(inside(sandbox.work, export_path))
    links = [
        row
        for row in ledger.derivations(project, export_path)
        if row.export_sha == current and row.master in masters
    ]
    if not links:
        return "non risulta esportato da un master del ticket"
    for row in links:
        path = inside(sandbox.work, row.master)
        if path.exists() and sha256(path) == row.master_sha:
            return None
    return "il master è cambiato dopo l'export: riesporta"
