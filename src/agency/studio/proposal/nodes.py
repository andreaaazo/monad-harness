"""The proposal nodes: each chosen idea becomes a proposal, developed in parallel."""

from __future__ import annotations

import json
from typing import Any

from langgraph.types import Send

from agency.contracts.concept import ConceptStatus
from agency.contracts.ticket import RUNNABLE, Medium, TicketSpec, TicketType
from agency.studio.shared import Crew, Node, ProjectState, Router, attempt, copy_capped, proposal_tickets
from agency.workshop.files import (
    MAX_IMAGE_FILE_BYTES,
    MAX_TEXT_FILE_BYTES,
    ensure_dir_under,
    read_under,
    sha256_under,
)


def prepare_proposals(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        project, turn, root = state["project"], state["exploration"], state["root"]
        work = crew.work_dir(project)
        existing = {crew.ledger.spec(ticket).title for ticket in proposal_tickets(crew, state)}
        applications = json.loads(
            read_under(work, f"explorations/r{turn}/applicazioni.json", MAX_TEXT_FILE_BYTES).decode("utf-8")
        )
        chosen = [row for row in crew.ledger.concepts(project, turn) if row.status == ConceptStatus.SELECTED]
        for row in sorted(chosen, key=lambda item: item.anon):
            title = f"Proposta {row.anon} r{turn}"
            if title in existing:  # a replay: the ticket was opened, the status may not have been set
                crew.ledger.update_concept(row.idea_ticket, status=ConceptStatus.IN_DEVELOPMENT)
                continue
            letter = row.anon.lower()
            workspace = f"proposals/r{turn}/{letter}"
            ensure_dir_under(work, workspace)
            source = f"explorations/r{turn}/{row.letter}"
            copy_capped(work, "brief.md", f"{workspace}/brief.md", MAX_TEXT_FILE_BYTES)
            copy_capped(work, f"{source}/scheda.json", f"{workspace}/scheda.json", MAX_TEXT_FILE_BYTES)
            copy_capped(work, row.sketch_file, f"{workspace}/schizzo.png", MAX_IMAGE_FILE_BYTES)
            names = "\n".join(f"- {item['name']}: {item['size']}" for item in applications)
            spec = TicketSpec(
                title=title,
                request=f"Sviluppa questa idea in una proposta.\n\n{row.card_json}\n\nAPPLICAZIONI\n{names}",
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
                workspace=workspace,
                prompt="proposer",
                effort=crew.settings.proposal_effort,
            )
            hashes = {path: sha256_under(work, f"{workspace}/{path}") for path in spec.inputs}
            crew.ledger.open(spec, project, hashes)
            crew.ledger.update_concept(row.idea_ticket, status=ConceptStatus.IN_DEVELOPMENT)
        return {}

    return node


def send_proposals(crew: Crew) -> Router:
    def route(state: ProjectState) -> list[Send] | str:
        tickets = [t for t in proposal_tickets(crew, state) if crew.ledger.status(t)[0] in RUNNABLE]
        return [Send("proposal", {"ticket": ticket}) for ticket in tickets] or "present"

    return route


def proposal(crew: Crew) -> Node:
    def node(state: Any) -> dict:
        crew.runner.run(state["ticket"], attempt(crew.ledger, state["ticket"]))
        return {}

    return node
