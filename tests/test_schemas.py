"""Lo schema viene prima del codice: l'OpenAPI nel repository è l'API com'è (M1.6, punto 12; ADR-0022)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agency.config import REPO_ROOT
from agency.entrypoints.server import schema

COMMITTED = REPO_ROOT / "schemas" / "openapi.json"


def test_the_openapi_in_the_repository_is_the_api_as_it_is() -> None:
    """Se fallisce: uv run agency-schemas, poi si rivede il diff prima del commit."""
    assert COMMITTED.read_text(encoding="utf-8") == schema.render()


def test_every_operation_reads_and_none_writes() -> None:
    paths = json.loads(schema.render())["paths"]
    methods = {method for operations in paths.values() for method in operations}
    assert methods == {"get"}


def test_the_schema_carries_the_read_models_of_insights() -> None:
    components = json.loads(schema.render())["components"]["schemas"]
    assert {"ProjectReport", "ProjectSummary", "Provenance", "Problem"} <= set(components)


def test_rendering_is_stable() -> None:
    assert schema.render() == schema.render()
    assert schema.render().endswith("}\n")


def test_the_command_writes_the_schema_and_then_finds_it_aligned(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "openapi.json"
    assert schema.main(["--check", "--output", str(target)]) == 1
    assert "non allineato" in capsys.readouterr().out
    assert schema.main(["--output", str(target)]) == 0
    assert schema.main(["--check", "--output", str(target)]) == 0
    target.write_text(target.read_text(encoding="utf-8").replace('"get"', '"post"', 1), encoding="utf-8")
    assert schema.main(["--check", "--output", str(target)]) == 1


def operations() -> dict[str, dict]:
    paths = json.loads(schema.render())["paths"]
    return {
        f"{method.upper()} {path}": operation
        for path, ops in paths.items()
        for method, operation in ops.items()
    }


def test_operations_have_names_that_do_not_depend_on_where_the_code_lives() -> None:
    """I tipi TypeScript le chiamano per nome: un refactor dei moduli Python non deve cambiarlo."""
    names = {key: operation["operationId"] for key, operation in operations().items()}
    assert names == {
        "GET /api/projects": "listProjects",
        "GET /api/projects/{name}/report": "projectReport",
        "GET /api/projects/{name}/flow": "projectFlow",
        "GET /api/projects/{name}/behaviour": "projectBehaviour",
        "GET /api/projects/{name}/quality": "projectQuality",
        "GET /api/compare": "compareProjects",
        "GET /api/provenance": "provenance",
    }


def test_every_operation_declares_the_answer_when_the_registry_cannot_be_read() -> None:
    for key, operation in operations().items():
        answer = operation["responses"].get("503", {})
        assert answer.get("content", {}).get("application/json", {}).get("schema") == {
            "$ref": "#/components/schemas/Problem"
        }, key
