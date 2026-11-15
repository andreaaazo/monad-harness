"""The dashboard server: GET only, loopback only, no key, no database (M1.6, item 11)."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import tomllib
import urllib.request
from pathlib import Path

import pytest

# Django first: Django Ninja reads the settings on import.
os.environ["DJANGO_SETTINGS_MODULE"] = "agency.entrypoints.server.settings"
import django

django.setup()

from django.apps import apps  # noqa: E402
from django.conf import settings  # noqa: E402
from django.http import HttpRequest, HttpResponse  # noqa: E402
from django.test import Client, RequestFactory, override_settings  # noqa: E402

from agency.agents.transcript import Transcript  # noqa: E402
from agency.config import REPO_ROOT  # noqa: E402
from agency.contracts.layout import DataLayout  # noqa: E402
from agency.contracts.ledger import UsageEntry  # noqa: E402
from agency.contracts.project import ProjectName  # noqa: E402
from agency.contracts.ticket import TicketSpec, TicketType  # noqa: E402
from agency.entrypoints import cli  # noqa: E402
from agency.entrypoints.server import serve  # noqa: E402
from agency.entrypoints.server.middleware import ReadOnly  # noqa: E402
from agency.insights.behaviour import BehaviourReport  # noqa: E402
from agency.insights.compare import CompareReport  # noqa: E402
from agency.insights.domain import Provenance  # noqa: E402
from agency.insights.flow import FlowReport  # noqa: E402
from agency.insights.quality import QualityReport  # noqa: E402
from agency.insights.replay import ReplayReport  # noqa: E402
from agency.insights.views import ProjectReport, ProjectSummary  # noqa: E402
from agency.ledger import Ledger  # noqa: E402


def usage(seq: int, cost: float = 1.25, project: str = "officina") -> UsageEntry:
    return UsageEntry(
        at=f"2026-11-02T10:{seq:02d}:00+00:00",
        project=project,
        ticket_id="T-0001",
        role="design-director",
        instance="T-0001-a1",
        model="claude-opus-5-5",
        input_tokens=100,
        output_tokens=20,
        cost_usd=cost,
        stop_reason="tool_use",
        request_id=f"req_{project}_{seq}",
    )


@pytest.fixture
def studio(tmp_path: Path) -> Ledger:
    ledger = Ledger(tmp_path / "ledger.sqlite")
    ledger.set_project("officina", 30)
    spec = TicketSpec(
        title="Consegna officina",
        request="r",
        type=TicketType.DELIVERY,
        sender="router",
        assignee="design-director",
        outputs=["segno.svg"],
        checks={"*.svg": ["svg_audit"]},
    )
    ledger.open(spec, "officina")
    ledger.record_usage(usage(1))
    ledger.record_usage(usage(2))
    return ledger


@pytest.fixture
def client(tmp_path: Path, studio: Ledger):
    studio.engine.dispose()
    with override_settings(AGENCY_DATA_DIR=tmp_path):
        yield Client(HTTP_HOST="127.0.0.1")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# What it answers


def test_the_request_log_line_loses_control_characters(capsys: pytest.CaptureFixture[str]) -> None:
    handler = serve._Handler.__new__(serve._Handler)
    handler.client_address = ("127.0.0.1", 1)
    handler.log_message("%s", "GET /\x1b]0;forged\x07 HTTP/1.1")
    err = capsys.readouterr().err
    assert "\x1b" not in err and "\x07" not in err
    assert err.endswith("\n")


def test_projects_lists_what_the_registry_knows(client: Client) -> None:
    response = client.get("/api/projects")
    assert response.status_code == 200
    (summary,) = [ProjectSummary.model_validate(item) for item in response.json()]
    assert (summary.name, summary.calls, summary.cost_usd, summary.budget_usd) == ("officina", 2, 2.5, 30.0)


def test_report_is_the_same_model_as_agency_report(client: Client) -> None:
    response = client.get("/api/projects/officina/report")
    assert response.status_code == 200
    report = ProjectReport.model_validate(response.json())
    assert (report.project, report.calls, report.cost_usd) == ("officina", 2, 2.5)


def test_flow_and_behaviour_are_the_views_of_insights(client: Client) -> None:
    flow = FlowReport.model_validate(client.get("/api/projects/officina/flow").json())
    assert (flow.outcome.delivery_id, flow.outcome.delivery_status) == ("T-0001", "open")
    behaviour = BehaviourReport.model_validate(client.get("/api/projects/officina/behaviour").json())
    assert [(role.role, role.calls) for role in behaviour.roles] == [("design-director", 2)]
    quality = QualityReport.model_validate(client.get("/api/projects/officina/quality").json())
    assert (quality.project, quality.uses, quality.checks) == ("officina", 0, [])


def test_compare_puts_two_projects_side_by_side_and_refuses_one_with_itself(
    tmp_path: Path, studio: Ledger
) -> None:
    studio.set_project("bottega", 20)
    studio.record_usage(usage(3, project="bottega"))
    studio.engine.dispose()
    with override_settings(AGENCY_DATA_DIR=tmp_path):
        client = Client(HTTP_HOST="127.0.0.1")
        report = CompareReport.model_validate(client.get("/api/compare?before=bottega&after=officina").json())
        assert (report.before.project, report.after.project, report.after.calls) == ("bottega", "officina", 2)
        same = client.get("/api/compare?before=officina&after=officina")
        assert (same.status_code, "due volte" in same.json()["detail"]) == (400, True)
        unknown = client.get("/api/compare?before=fantasma&after=officina")
        assert (unknown.status_code, "fantasma" in unknown.json()["detail"]) == (404, True)
        assert client.post("/api/compare?before=bottega&after=officina").status_code == 405


def test_a_stored_name_the_rule_rejects_is_a_404_and_the_list_still_answers(
    tmp_path: Path, studio: Ledger
) -> None:
    """A registry written before the name rule may hold `Merlo`: its routes refuse it (COR-013)."""
    studio.set_project("Merlo", 5)
    studio.record_usage(usage(3, project="Merlo"))
    studio.engine.dispose()
    with override_settings(AGENCY_DATA_DIR=tmp_path):
        client = Client(HTTP_HOST="127.0.0.1")
        listing = client.get("/api/projects")
        assert listing.status_code == 200
        assert {item["name"] for item in listing.json()} == {"Merlo", "officina"}
        for route in ["report", "flow", "behaviour", "quality", "instances/T-0001-a1/replay"]:
            refused = client.get(f"/api/projects/Merlo/{route}")
            assert refused.status_code == 404, route
            assert "Merlo" in refused.json()["detail"], route
        assert client.get("/api/projects/Merlo/instances/T-0001-a1/images/0").status_code == 404
        assert client.get("/api/compare?before=Merlo&after=officina").status_code == 404
        assert client.get("/api/compare?before=officina&after=Merlo").status_code == 404
        assert client.get("/api/projects/officina/report").status_code == 200


PNG = b"\x89PNG\r\n\x1a\n un pixel"


def replayable(tmp_path: Path) -> None:
    """Instance T-0001-a1 of officina, as the engine writes it: one PNG image and one SVG."""
    transcript = Transcript(DataLayout(tmp_path).transcript(ProjectName("officina"), "T-0001-a1"))
    transcript.append({"role": "user", "content": "Il compito"})
    transcript.append(
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "u1", "name": "view_image", "input": {}}],
        },
        request_id="req_officina_1",
    )
    pictures = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": kind, "data": base64.b64encode(data).decode()},
        }
        for kind, data in (("image/png", PNG), ("image/svg+xml", b"<svg onload='alert(1)'/>"))
    ]
    transcript.append(
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "u1", "content": pictures}]}
    )


def test_replay_reads_an_instance_turn_by_turn_with_the_measures_of_its_call(
    client: Client, tmp_path: Path
) -> None:
    replayable(tmp_path)
    response = client.get("/api/projects/officina/instances/T-0001-a1/replay")
    assert response.status_code == 200
    report = ReplayReport.model_validate(response.json())
    assert (report.task, report.alignment, len(report.turns), report.images) == (
        "Il compito",
        "per richiesta",
        1,
        2,
    )
    assert report.turns[0].measured is not None and report.turns[0].measured.cost_usd == 1.25


def test_an_image_is_served_as_itself_never_cached_framed_sniffed_or_run(
    client: Client, tmp_path: Path
) -> None:
    replayable(tmp_path)
    response = client.get("/api/projects/officina/instances/T-0001-a1/images/0")
    assert (response.status_code, response["Content-Type"], response.content) == (200, "image/png", PNG)
    assert response["Cache-Control"] == "no-store"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Security-Policy"] == "default-src 'none'; sandbox"
    assert client.get("/api/projects/officina/instances/T-0001-a1/images/1").status_code == 404  # SVG
    assert client.get("/api/projects/officina/instances/T-0001-a1/images/2").status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/api/projects/officina/instances/T-0009-a1/replay",
        "/api/projects/officina/instances/..%2F..%2Fledger/replay",
        "/api/projects/fantasma/instances/T-0001-a1/replay",
        "/api/projects/officina/instances/T-0001-a1/images/-1",
        "/api/projects/fantasma/instances/T-0001-a1/images/0",
    ],
)
def test_what_is_not_a_known_instance_or_image_is_not_found(
    client: Client, tmp_path: Path, path: str
) -> None:
    replayable(tmp_path)
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("view", ["report", "flow", "behaviour", "quality"])
def test_an_unknown_project_is_not_found(client: Client, view: str) -> None:
    response = client.get(f"/api/projects/fantasma/{view}")
    assert response.status_code == 404
    assert "fantasma" in response.json()["detail"]


def test_provenance_says_where_the_data_came_from(client: Client) -> None:
    provenance = Provenance.model_validate(client.get("/api/provenance").json())
    assert (provenance.calls, provenance.from_registry, provenance.unmeasured) == (2, 0, 2)
    assert {source.name for source in provenance.sources} == {
        "ledger.sqlite",
        "ledger.sqlite-wal",
        "traces.jsonl",
    }


def test_the_dashboard_follows_the_engine_and_rebuilds_only_when_something_changed(
    client: Client, tmp_path: Path, studio: Ledger
) -> None:
    projection = tmp_path / "insights.sqlite"
    assert client.get("/api/provenance").status_code == 200
    built = projection.stat().st_ino
    assert client.get("/api/projects").status_code == 200
    assert projection.stat().st_ino == built  # nothing changed: the projection is not rebuilt
    ledger = Ledger(tmp_path / "ledger.sqlite")
    ledger.record_usage(usage(3, cost=2.0))  # the engine works and stays open: the new row is in the WAL
    try:
        report = ProjectReport.model_validate(client.get("/api/projects/officina/report").json())
    finally:
        ledger.engine.dispose()
    assert (report.calls, report.cost_usd) == (3, 4.5)


def test_an_outdated_registry_is_explained_not_hidden(tmp_path: Path) -> None:
    import sqlite3
    from contextlib import closing

    with closing(sqlite3.connect(tmp_path / "ledger.sqlite")) as connection:
        connection.execute("CREATE TABLE usage (seq INTEGER)")
    with override_settings(AGENCY_DATA_DIR=tmp_path):
        response = Client(HTTP_HOST="127.0.0.1").get("/api/projects")
    assert response.status_code == 503
    assert "agency migrate" in response.json()["detail"]


# What it does not do


ROUTES = [
    "/api/projects",
    "/api/projects/officina/report",
    "/api/projects/officina/flow",
    "/api/projects/officina/behaviour",
    "/api/projects/officina/quality",
    "/api/provenance",
]


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete", "head", "options"])
def test_the_api_cannot_write_and_the_registry_stays_intact(
    client: Client, tmp_path: Path, method: str
) -> None:
    before = digest(tmp_path / "ledger.sqlite")
    for route in ROUTES:
        assert client.get(route).status_code == 200
        response = getattr(client, method)(route)
        assert response.status_code == 405, (method, route)
        assert response["Allow"] == "GET"
    assert digest(tmp_path / "ledger.sqlite") == before


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_writes_stop_before_any_view_even_one_that_would_accept_them(method: str) -> None:
    """The second defence alone: even a future route written by mistake gets no write."""
    reached: list[str] = []

    def careless_view(request: HttpRequest) -> HttpResponse:
        reached.append(request.method or "")
        return HttpResponse("scritto")

    request = getattr(RequestFactory(HTTP_HOST="127.0.0.1"), method)("/api/projects")
    response = ReadOnly(careless_view)(request)
    assert (response.status_code, reached) == (405, [])


def test_a_foreign_host_is_refused_against_dns_rebinding(client: Client) -> None:
    response = Client(HTTP_HOST="attaccante.example").get("/api/projects")
    assert response.status_code == 400


def test_answers_are_never_cached_and_never_sniffed(client: Client) -> None:
    response = client.get("/api/projects")
    assert response["Cache-Control"] == "no-store"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["X-Frame-Options"] == "DENY"


def test_no_docs_page_that_loads_scripts_from_a_cdn(client: Client) -> None:
    assert client.get("/api/docs").status_code == 404


def test_django_owns_no_model_and_no_database() -> None:
    assert apps.get_models() == []
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.dummy"  # that is, no database
    assert settings.DEBUG is False
    assert settings.ALLOWED_HOSTS == ["127.0.0.1", "localhost"]


# The process


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "10.0.0.1", "example.com", "::", "localhost"])
def test_the_server_refuses_anything_but_loopback(host: str) -> None:
    with pytest.raises(ValueError, match="loopback"):
        serve.build(host, 0)


def test_a_busy_port_is_explained_not_dumped_as_a_traceback(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another dashboard is running: say so, and say how to choose another port."""
    monkeypatch.setattr(
        serve.os, "environ", dict(os.environ)
    )  # the server scrubs the environment: pass a copy
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        assert serve.main(["--port", str(port)]) == 1
    error = capsys.readouterr().err
    assert f"la porta {port} di 127.0.0.1 è già occupata" in error and "--port" in error
    assert "Traceback" not in error


def test_the_server_removes_the_api_key_from_its_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-prova")
    monkeypatch.setenv("AGENCY_ANTHROPIC_API_KEY", "sk-ant-prova")
    server = serve.build("127.0.0.1", 0)
    server.server_close()
    assert "ANTHROPIC_API_KEY" not in os.environ and "AGENCY_ANTHROPIC_API_KEY" not in os.environ


def test_the_server_listens_on_loopback_and_answers(
    tmp_path: Path, studio: Ledger, monkeypatch: pytest.MonkeyPatch
) -> None:
    studio.engine.dispose()
    server = serve.build("127.0.0.1", 0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://{host}:{port}/api/projects"
        with override_settings(AGENCY_DATA_DIR=tmp_path), urllib.request.urlopen(url, timeout=10) as answer:
            body = json.load(answer)
    finally:
        server.shutdown()
        server.server_close()
    assert host == "127.0.0.1"
    assert [item["name"] for item in body] == ["officina"]


def test_the_server_never_reads_dotenv_nor_loads_the_engine_settings(tmp_path: Path) -> None:
    """In a new process, with a .env that holds a key: the server does not see it."""
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-dal-dotenv\n", encoding="utf-8")
    probe = (
        "import os, sys\n"
        "os.environ['DJANGO_SETTINGS_MODULE'] = 'agency.entrypoints.server.settings'\n"
        "import django; django.setup()\n"
        "from django.conf import settings\n"
        "import agency.entrypoints.server.api, agency.entrypoints.server.serve\n"
        "values = str(vars(settings._wrapped)) + str(dict(os.environ))\n"
        "print('chiave' if 'sk-ant-dal-dotenv' in values else 'pulito', 'agency.config' in sys.modules)\n"
    )
    environment = {key: value for key, value in os.environ.items() if "ANTHROPIC" not in key}
    done = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout.split() == ["pulito", "False"]


def test_the_server_runs_as_its_own_process(tmp_path: Path, studio: Ledger) -> None:
    studio.engine.dispose()
    environment = dict(os.environ, AGENCY_DATA_DIR=str(tmp_path), ANTHROPIC_API_KEY="sk-ant-prova")
    process = subprocess.Popen(
        [sys.executable, "-m", "agency.entrypoints.server", "--port", "0"],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        assert process.stdout is not None
        line = process.stdout.readline()
        url = line.split()[-1]
        assert url.startswith("http://127.0.0.1:") and url.endswith("/api/")
        with urllib.request.urlopen(f"{url}provenance", timeout=10) as answer:
            assert json.load(answer)["calls"] == 2
    finally:
        process.terminate()
        process.wait(timeout=10)


RELATIVE = (
    "{name} deve essere un percorso assoluto, non {value!r}: uno relativo dipende dalla cartella da cui parte"
    " il comando"
)


def test_a_relative_data_root_is_refused_by_engine_and_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`AGENCY_DATA_DIR=.data task dashboard`: neither process starts, and both say why in the same line."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("AGENCY_")}
    for key in set(os.environ) - set(environment):
        monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    line = RELATIVE.format(name="AGENCY_DATA_DIR", value=".data") + "\n"

    monkeypatch.setenv("AGENCY_DATA_DIR", ".data")
    assert (cli.main(["verify"]), capsys.readouterr().out) == (1, line)
    monkeypatch.delenv("AGENCY_DATA_DIR")
    monkeypatch.setenv("AGENCY_PROJECTS_DIR", "projects")  # the projects folder follows the same rule
    projects = RELATIVE.format(name="AGENCY_PROJECTS_DIR", value="projects") + "\n"
    assert (cli.main(["verify"]), capsys.readouterr().out) == (1, projects)

    server = subprocess.run(
        [sys.executable, "-m", "agency.entrypoints.server", "--port", "0"],
        cwd=tmp_path,
        env=environment | {"AGENCY_DATA_DIR": ".data"},
        capture_output=True,
        text=True,
        timeout=30,  # a server that accepts the root serves until this kills it
    )
    assert (server.returncode, server.stderr) == (1, line)
    assert not (tmp_path / ".data").exists()


def clean_environment(**variables: str) -> dict[str, str]:
    """The process environment without any AGENCY_* variable of the machine, plus the given ones."""
    return {key: value for key, value in os.environ.items() if not key.startswith("AGENCY_")} | variables


def test_a_relative_projection_dir_is_refused_by_the_server(tmp_path: Path) -> None:
    """2.F35: `AGENCY_PROJECTION_DIR` follows the rule of the data root, not the server's current folder."""
    server = subprocess.run(
        [sys.executable, "-m", "agency.entrypoints.server", "--port", "0"],
        cwd=tmp_path,
        env=clean_environment(AGENCY_DATA_DIR=str(tmp_path), AGENCY_PROJECTION_DIR="projection"),
        capture_output=True,
        text=True,
        timeout=30,  # a server that accepts the folder serves until this kills it
    )
    line = RELATIVE.format(name="AGENCY_PROJECTION_DIR", value="projection") + "\n"
    assert (server.returncode, server.stderr) == (1, line)
    assert not (tmp_path / "projection").exists()


def test_an_absolute_projection_dir_is_taken_as_given(tmp_path: Path) -> None:
    from agency.contracts.layout import projection_root

    assert projection_root({}) is None
    assert projection_root({"AGENCY_PROJECTION_DIR": str(tmp_path)}) == tmp_path


SCHEMAS = "import sys; from agency.entrypoints.server import schema; sys.exit(schema.main(sys.argv[1:]))"


def run_schemas(folder: Path, *arguments: str, **variables: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", SCHEMAS, *arguments],
        cwd=folder,
        env=clean_environment(**({"AGENCY_DATA_DIR": str(folder)} | variables)),
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_agency_schemas_checks_the_schema_of_the_checkout_from_any_folder(tmp_path: Path) -> None:
    """2.F34: `uv run agency-schemas` from `web/` must not look for, or write, `web/schemas/openapi.json`."""
    done = run_schemas(tmp_path, "--check")
    assert (done.returncode, done.stdout) == (0, f"schema allineato: {REPO_ROOT / 'schemas/openapi.json'}\n")
    assert not (tmp_path / "schemas").exists()


@pytest.mark.parametrize("name", ["AGENCY_DATA_DIR", "AGENCY_PROJECTION_DIR"])
def test_agency_schemas_prints_the_refusal_of_a_relative_folder(tmp_path: Path, name: str) -> None:
    """2.F34: the settings load while the schema renders; the refusal is one line, not a traceback."""
    done = run_schemas(tmp_path, "--check", **{name: "relativo"})
    assert (done.returncode, done.stdout, done.stderr) == (
        1,
        RELATIVE.format(name=name, value="relativo") + "\n",
        "",
    )


# The boundaries


def forbidden_contracts() -> list[dict]:
    """The `forbidden` contracts of pyproject.toml: the ones that list packages by hand."""
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    contracts = config["tool"]["importlinter"]["contracts"]
    return [contract for contract in contracts if contract["type"] == "forbidden"]


def test_every_engine_package_is_forbidden_to_import_django() -> None:
    """The contract lists the packages by hand: a new package must not slip past it."""
    engine = contract_named("the engine imports neither Django nor the server")
    source = REPO_ROOT / "src" / "agency"
    present = {
        path.stem for path in source.iterdir() if path.suffix == ".py" or (path / "__init__.py").exists()
    }
    present -= {"__init__", "entrypoints"}
    # The CLI is an entry point, and it runs the engine: it must not import Django either.
    sources = {module.removeprefix("agency.") for module in engine["source_modules"]}
    assert sources == present | {"entrypoints.cli"}


# What each read-only slice may import from the engine. Every other package on disk must be forbidden.
SLICE_ALLOWED = {
    "agency.insights": {"contracts"},
    "agency.entrypoints.server": {"contracts", "insights"},
    "agency.evaluation": {"contracts"},
}


def test_every_slice_contract_forbids_every_engine_package() -> None:
    """A new engine package must reach every slice's forbidden list, not only the Django contract's."""
    contracts = forbidden_contracts()
    source = REPO_ROOT / "src" / "agency"
    present = {
        path.stem for path in source.iterdir() if path.suffix == ".py" or (path / "__init__.py").exists()
    } - {"__init__", "entrypoints"}
    for slice_, allowed in SLICE_ALLOWED.items():
        (contract,) = [contract for contract in contracts if contract["source_modules"] == [slice_]]
        forbidden = {module.removeprefix("agency.") for module in contract["forbidden_modules"]}
        unforbidden = present - forbidden - allowed - {slice_.removeprefix("agency.")}
        assert not unforbidden, f"{slice_} does not forbid {sorted(unforbidden)}"


def test_every_package_but_the_gateway_is_forbidden_to_import_anthropic() -> None:
    """The anthropic contract lists the packages by hand: a new package must not slip past it."""
    contracts = forbidden_contracts()
    (contract,) = [contract for contract in contracts if contract["forbidden_modules"] == ["anthropic"]]
    source = REPO_ROOT / "src" / "agency"
    present = {
        path.stem for path in source.iterdir() if path.suffix == ".py" or (path / "__init__.py").exists()
    } - {"__init__"}
    assert {module.removeprefix("agency.") for module in contract["source_modules"]} == present - {"gateway"}


def test_every_studio_slice_is_kept_apart_from_the_others() -> None:
    """The independence contract lists the slices by hand: a new slice must not slip past it (ADR-0021)."""
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    contracts = config["tool"]["importlinter"]["contracts"]
    independence = [contract for contract in contracts if contract["type"] == "independence"]
    assert len(independence) == 1, "one contract keeps the slices from importing each other"
    studio = REPO_ROOT / "src" / "agency" / "studio"
    slices = {f"agency.studio.{path.name}" for path in studio.iterdir() if (path / "__init__.py").exists()}
    assert set(independence[0]["modules"]) == slices


def contract_named(start: str) -> dict:
    """The one import-linter contract whose name starts with `start`."""
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    found = [
        contract
        for contract in config["tool"]["importlinter"]["contracts"]
        if contract["name"].startswith(start)
    ]
    assert len(found) == 1, f"one contract named {start!r}"
    return found[0]


def top_level_packages() -> set[str]:
    """The packages and modules right under src/agency, by name."""
    source = REPO_ROOT / "src" / "agency"
    return {
        path.stem for path in source.iterdir() if path.suffix == ".py" or (path / "__init__.py").exists()
    } - {"__init__"}


def test_every_engine_package_has_a_layer() -> None:
    """The layers contract lists the packages by hand: a new one must take a layer. Insights and the blind
    judgment depend only on the contracts, and their own contracts say so (ADR-0057)."""
    layers = contract_named("the engine's layers")["layers"]
    listed = {name.strip() for layer in layers for name in layer.replace("|", ":").split(":")}
    assert listed == {f"agency.{name}" for name in top_level_packages() - {"evaluation", "insights"}}


def test_every_package_but_the_process_and_the_studio_is_forbidden_langgraph() -> None:
    """The langgraph contract lists the packages by hand: a new package must not slip past it (ADR-0021)."""
    contract = contract_named("langgraph only")
    assert contract["forbidden_modules"] == ["langgraph", "langchain_core"]
    packages = {
        module.removeprefix("agency.") for module in contract["source_modules"] if module.count(".") == 1
    }
    assert packages == top_level_packages() - {"process", "studio"}


def test_every_studio_module_but_the_graph_adapters_is_forbidden_langgraph() -> None:
    """Inside the studio only the slices' nodes.py and studio.graph meet LangGraph (ADR-0058). A package's
    __init__ cannot be listed without its children, and none of them imports anything."""
    contract = contract_named("langgraph only")
    studio = REPO_ROOT / "src" / "agency"
    modules = {
        ".".join(path.relative_to(studio.parent).with_suffix("").parts)
        for path in (studio / "studio").rglob("*.py")
        if path.name not in {"__init__.py", "nodes.py", "graph.py"}
    }
    assert {module for module in contract["source_modules"] if module.startswith("agency.studio.")} == modules


def test_every_package_but_the_ledger_is_forbidden_the_orm() -> None:
    """The ORM contract lists the packages by hand: a new package must not slip past it (ADR-0021)."""
    contract = contract_named("sqlmodel, sqlalchemy and alembic only")
    assert contract["forbidden_modules"] == ["sqlmodel", "sqlalchemy", "alembic"]
    assert set(contract["source_modules"]) == {f"agency.{name}" for name in top_level_packages() - {"ledger"}}


def test_only_the_composition_roots_import_the_sqlite_ledger() -> None:
    """The ledger contract lists the packages by hand: everything but the ledger itself, the session and the
    CLI must reach the registry through its ports (ADR-0058). The server has its own, stricter contract."""
    contract = contract_named("only the composition roots reach the SQLite ledger")
    assert contract["forbidden_modules"] == ["agency.ledger"]
    process = REPO_ROOT / "src" / "agency" / "process"
    inner = {f"agency.process.{path.stem}" for path in process.glob("*.py")} - {
        "agency.process.__init__",
        "agency.process.session",
    }
    packages = {f"agency.{name}" for name in top_level_packages() - {"ledger", "process", "entrypoints"}}
    assert set(contract["source_modules"]) == packages | inner


FRAMEWORKS = [
    "anthropic",
    "langgraph",
    "langchain_core",
    "sqlmodel",
    "sqlalchemy",
    "alembic",
    "django",
    "ninja",
]
FRAMEWORKS += ["opentelemetry", "PIL"]


def modules_named(*names: str) -> set[str]:
    """The dotted names of the studio's and insights' modules with one of these file names."""
    source = REPO_ROOT / "src"
    found = [*(source / "agency" / "studio").rglob("*.py"), *(source / "agency" / "insights").rglob("*.py")]
    return {".".join(path.relative_to(source).with_suffix("").parts) for path in found if path.name in names}


def test_every_domain_and_application_is_kept_free_of_frameworks() -> None:
    """The framework contract lists the modules by hand: a new domain or application must not slip past it."""
    contract = contract_named("domain and application import no framework")
    assert set(contract["source_modules"]) == modules_named("domain.py", "application.py")
    adapters = [
        "agency.ledger",
        "agency.gateway",
        "agency.process",
        "agency.agents",
        "agency.workshop.sandbox",
    ]
    # The LangGraph adapters too: an application importing studio.graph or a nodes module reaches LangGraph.
    graph_adapters = ["agency.studio.graph", *sorted(modules_named("nodes.py"))]
    assert contract["forbidden_modules"] == FRAMEWORKS + adapters + graph_adapters


def test_every_domain_depends_only_on_the_contracts() -> None:
    """A domain imports the contracts and nothing else of the engine: every other package, and every module
    of the studio and of insights that is not a domain, is forbidden to it (ADR-0058)."""
    contract = contract_named("a domain depends only on the contracts")
    assert set(contract["source_modules"]) == modules_named("domain.py")
    others = {f"agency.{name}" for name in top_level_packages() - {"contracts", "studio", "insights"}}
    siblings = modules_named(*{path.name for path in (REPO_ROOT / "src/agency").rglob("*.py")}) - {
        *modules_named("domain.py", "__init__.py"),
    }
    adapters_package = {module for module in siblings if module.startswith("agency.insights.adapters.")}
    siblings = (siblings - adapters_package) | {"agency.insights.adapters"}
    assert set(contract["forbidden_modules"]) == others | siblings


def test_the_projection_can_live_away_from_the_registry(client: Client, tmp_path: Path) -> None:
    """In Docker the projection lives in memory: the server writes it there, and nothing beside the
    registry."""
    elsewhere = tmp_path / "in-memoria"
    elsewhere.mkdir()
    with override_settings(AGENCY_PROJECTION_DIR=elsewhere):
        assert client.get("/api/projects").status_code == 200
    assert (elsewhere / "insights.sqlite").is_file()
    assert not (tmp_path / "insights.sqlite").exists()


def test_by_default_the_projection_sits_next_to_the_registry(client: Client, tmp_path: Path) -> None:
    assert client.get("/api/projects").status_code == 200
    assert (tmp_path / "insights.sqlite").is_file()
    assert DataLayout(Path("/dati"), Path("/memoria")).insights == Path("/memoria/insights.sqlite")


def test_the_data_layout_has_one_owner() -> None:
    layout = DataLayout(Path("/dati"))
    assert (
        layout.ledger,
        layout.traces,
        layout.insights,
        layout.transcript(ProjectName("merlo"), "T-0002-a1"),
    ) == (
        Path("/dati/ledger.sqlite"),
        Path("/dati/traces.jsonl"),
        Path("/dati/insights.sqlite"),
        Path("/dati/runs/merlo/T-0002-a1.jsonl"),
    )
