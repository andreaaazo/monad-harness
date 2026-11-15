"""The exploration's pure rules (ADR-0058): no ledger, no files, no framework."""

from __future__ import annotations

from agency.contracts.ticket import Medium, TicketSpec, TicketType
from agency.studio.exploration.domain import (
    banned_exclusions,
    exploration_spec,
    explorer_assignments,
    plan_note,
)

DIRECTIONS = {"a": "direction-a", "b": "direction-b", "c": "direction-c"}


def test_banned_exclusions_finds_an_asset_inside_an_exclusion() -> None:
    assert banned_exclusions(["Merlo"], ["merlo stilizzato", "gradienti", "3D"]) == ["merlo stilizzato"]


def test_banned_exclusions_is_empty_when_every_exclusion_is_a_cliche() -> None:
    assert banned_exclusions(["Merlo", "officina"], ["gradienti", "3D", "lucido"]) == []


def test_explorer_assignments_pair_letters_with_levers_up_to_the_explorers() -> None:
    assert explorer_assignments(DIRECTIONS, ["x", "y", "z"], 2) == [
        ("a", "direction-a", "x"),
        ("b", "direction-b", "y"),
    ]


def test_explorer_assignments_stop_at_the_fewer_levers() -> None:
    assert explorer_assignments(DIRECTIONS, ["x"], 5) == [("a", "direction-a", "x")]


def test_exploration_spec_asks_the_explorer_for_its_card_and_sketches() -> None:
    spec = exploration_spec(
        root_request="Un segno per l'officina",
        letter="b",
        role="direction-b",
        lever="il gesto della mano",
        assets=["Merlo", "officina"],
        excluded=["gradienti", "3D", "lucido"],
        sender="design-director",
        parent="T-0001",
        workspace="explorations/r2/b",
        effort="high",
    )
    assert spec == TicketSpec(
        title="Esplorazione B",
        request="Un segno per l'officina\n\nLEVA: il gesto della mano\n\n"
        "RISORSE DEL CLIENTE: Merlo, officina\n\nCLICHÉ DA EVITARE\n- gradienti\n- 3D\n- lucido",
        type=TicketType.SKETCH,
        sender="design-director",
        assignee="direction-b",
        outputs=["scheda.json", "schizzi-b.vectorcraft", "foglio-b.png", "schizzo-b.png"],
        checks={"*.vectorcraft": ["master_open"], "*.png": ["visual_review"]},
        exempt={"scheda.json": "la scheda la giudicano critico e direttore"},
        media=[Medium.VECTOR],
        parent="T-0001",
        workspace="explorations/r2/b",
        prompt="explorer",
        effort="high",
    )


def test_plan_note_names_the_explorers_and_the_client_note() -> None:
    assert plan_note(5, "Più calore") == "Esploratori disponibili: 5. Più calore"


def test_plan_note_without_a_client_note_ends_at_the_explorers() -> None:
    assert plan_note(3, "") == "Esploratori disponibili: 3."
