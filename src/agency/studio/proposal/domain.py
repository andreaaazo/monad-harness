"""The proposal's rules: pure, with no ledger, no files and no framework (ADR-0058)."""

from __future__ import annotations

from agency.contracts.ticket import Medium, TicketSpec, TicketType


def proposal_spec(
    *,
    title: str,
    anon: str,
    turn: int,
    card_json: str,
    applications: list[dict[str, str]],
    root: str,
    effort: str,
) -> TicketSpec:
    """The ticket that develops one chosen idea into a proposal: the mark as master, SVG and PNG, and each
    application the director planned, in its own folder of the round."""
    letter = anon.lower()
    names = "\n".join(f"- {item['name']}: {item['size']}" for item in applications)
    return TicketSpec(
        title=title,
        request=f"Sviluppa questa idea in una proposta.\n\n{card_json}\n\nAPPLICAZIONI\n{names}",
        type=TicketType.PROPOSAL,
        sender="design-director",
        assignee="identity-designer",
        outputs=[
            f"proposta-{letter}.vectorcraft",
            f"proposta-{letter}.svg",
            f"proposta-{letter}.png",
            f"applicazioni-{letter}/*.png",
        ],
        checks={
            "*.vectorcraft": ["master_open"],
            "*.svg": ["svg_audit"],
            "*.png": ["visual_review"],
        },
        media=[Medium.VECTOR],
        inputs=["scheda.json", "schizzo.png"],
        parent=root,
        workspace=f"proposals/r{turn}/{letter}",
        prompt="proposer",
        effort=effort,
    )
