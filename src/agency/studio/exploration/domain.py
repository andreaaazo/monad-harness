"""The exploration's rules: pure, with no ledger, no files and no framework (ADR-0058)."""

from __future__ import annotations

from agency.contracts.ticket import Medium, TicketSpec, TicketType


def banned_exclusions(assets: list[str], excluded: list[str]) -> list[str]:
    """The exclusions that would ban one of the client's assets: an exclusion names a cliché of execution,
    never the name or the subject."""
    words = [word.lower() for word in assets]
    return [item for item in excluded if any(word in item.lower() for word in words)]


def explorer_assignments(
    directions: dict[str, str], levers: list[str], explorers: int
) -> list[tuple[str, str, str]]:
    """Each explorer's letter, role and lever: the first lever goes to the first direction, up to
    `explorers`."""
    return [
        (letter, role, lever)
        for (letter, role), lever in zip(directions.items(), levers[:explorers], strict=False)
    ]


def exploration_spec(
    *,
    root_request: str,
    letter: str,
    role: str,
    lever: str,
    assets: list[str],
    excluded: list[str],
    sender: str,
    parent: str,
    workspace: str,
    effort: str,
) -> TicketSpec:
    """The sketch ticket of one explorer: the brief with its lever, the client's assets and the clichés to
    avoid, and a card with its sketches as the outputs."""
    cliches = "\n".join(f"- {item}" for item in excluded)
    return TicketSpec(
        title=f"Esplorazione {letter.upper()}",
        request=f"{root_request}\n\nLEVA: {lever}\n\nRISORSE DEL CLIENTE: {', '.join(assets)}\n\n"
        f"CLICHÉ DA EVITARE\n{cliches}",
        type=TicketType.SKETCH,
        sender=sender,
        assignee=role,
        outputs=[
            "scheda.json",
            f"schizzi-{letter}.vectorcraft",
            f"foglio-{letter}.png",
            f"schizzo-{letter}.png",
        ],
        checks={"*.vectorcraft": ["master_open"], "*.png": ["visual_review"]},
        exempt={"scheda.json": "la scheda la giudicano critico e direttore"},
        media=[Medium.VECTOR],
        parent=parent,
        workspace=workspace,
        prompt="explorer",
        effort=effort,
    )


def plan_note(explorers: int, client_note: str) -> str:
    """What the director reads when it plans a round: how many explorers it has, and what the client said."""
    return f"Esploratori disponibili: {explorers}. {client_note}".strip()
