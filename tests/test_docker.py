"""Il cruscotto in Docker (ADR-0040): cosa si pubblica, cosa si monta, cosa resta fuori dalle immagini.

La configurazione si legge come la legge Compose, con `docker compose config`, che non ha bisogno del demone.
Docker serve al cruscotto, non al motore: su una macchina senza il client queste prove si saltano e lo dicono.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from agency.config import REPO_ROOT

DOCKER = shutil.which("docker")
pytestmark = pytest.mark.skipif(DOCKER is None, reason="il client docker non c'è su questa macchina")
FOLDER = REPO_ROOT / "docker"
COMPOSE = FOLDER / "compose.yaml"
CANARY = "e2e-canary-not-a-key"
MISE = tomllib.loads((REPO_ROOT / "mise.toml").read_text(encoding="utf-8"))["tools"]
DIGEST = r"@sha256:[0-9a-f]{64}"


def compose(tmp_path: Path, *arguments: str, **variables: str) -> subprocess.CompletedProcess[str]:
    """Compose con le variabili di `task docker:up`, più una chiave finta nell'ambiente di chi lo avvia."""
    environment = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", str(tmp_path))}
    environment |= {"ANTHROPIC_API_KEY": CANARY, "AGENCY_ANTHROPIC_API_KEY": CANARY}
    environment |= {"AGENCY_DATA_DIR": str(tmp_path), "AGENCY_UID": "1000", "AGENCY_GID": "1000"} | variables
    environment = {key: value for key, value in environment.items() if value}
    command = [str(DOCKER), "compose", "-f", str(COMPOSE), *arguments]
    return subprocess.run(command, env=environment, capture_output=True, text=True, check=False)


def rendered(tmp_path: Path, **variables: str) -> dict:
    done = compose(tmp_path, "config", "--format", "json", **variables)
    assert done.returncode == 0, done.stderr
    assert CANARY not in done.stdout, "la chiave dell'ambiente è finita nella configurazione"
    return json.loads(done.stdout)


def dockerfile(name: str) -> str:
    return (FOLDER / name).read_text(encoding="utf-8")


def rules(name: str) -> list[str]:
    lines = (FOLDER / f"{name}.dockerignore").read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def test_only_the_interface_is_published_and_only_on_loopback(tmp_path: Path) -> None:
    """web condivide la rete di api: la porta dell'interfaccia si pubblica lì, e Django non ne ha una."""
    services = rendered(tmp_path)["services"]
    assert set(services) == {"api", "web"}
    published = [
        (name, port["host_ip"], port["target"], port["published"])
        for name, service in services.items()
        for port in service.get("ports", [])
    ]
    assert published == [("api", "127.0.0.1", 3000, "3000")]
    assert services["web"]["network_mode"] == "service:api"


def test_the_api_mounts_the_registry_as_the_host_user_and_keeps_its_projection_in_memory(
    tmp_path: Path,
) -> None:
    services = rendered(tmp_path)["services"]
    api, web = services["api"], services["web"]
    assert [(volume["type"], volume["source"], volume["target"]) for volume in api["volumes"]] == [
        ("bind", str(tmp_path), "/data")
    ]
    # Non in sola lettura: un registro WAL chiuso dal motore non si apre senza creare il suo -shm
    # (tests/test_insights.py, test_a_registry_that_cannot_be_opened_is_explained_not_crashed).
    assert not api["volumes"][0].get("read_only", False)
    assert api["user"] == "1000:1000"
    assert api["environment"] == {"AGENCY_DATA_DIR": "/data", "AGENCY_PROJECTION_DIR": "/projection"}
    assert "/projection" in api["tmpfs"]
    # L'interfaccia non ha dati: niente volumi, niente variabili.
    assert ("volumes" not in web, "environment" not in web) == (True, True)


def test_compose_mounts_agency_data_dir(tmp_path: Path) -> None:
    """The host data root is AGENCY_DATA_DIR, like every other process; AGENCY_DATA is ignored (ADR-0045)."""
    elsewhere = tmp_path / "elsewhere"
    old = str(tmp_path / "old")
    api = rendered(tmp_path, AGENCY_DATA_DIR=str(elsewhere), AGENCY_DATA=old)["services"]["api"]
    assert [(volume["source"], volume["target"]) for volume in api["volumes"]] == [(str(elsewhere), "/data")]


def test_compose_names_agency_data_dir_when_missing(tmp_path: Path) -> None:
    done = compose(tmp_path, "config", AGENCY_DATA_DIR="", AGENCY_DATA=str(tmp_path))
    assert done.returncode != 0
    assert "AGENCY_DATA_DIR" in done.stderr and "task docker:up" in done.stderr


def test_no_key_and_no_env_file_reach_the_containers(tmp_path: Path) -> None:
    """Compose legge da solo il .env della cartella del progetto: per questo il file non sta nella radice."""
    services = rendered(tmp_path)["services"]
    assert not any("env_file" in service for service in services.values())
    assert COMPOSE.parent != REPO_ROOT
    assert not any(
        (REPO_ROOT / name).exists() for name in ("compose.yaml", "compose.yml", "docker-compose.yml")
    )
    assert not (FOLDER / ".env").exists()


def test_every_container_is_hardened(tmp_path: Path) -> None:
    for name, service in rendered(tmp_path)["services"].items():
        assert service["read_only"] is True, name
        assert service["cap_drop"] == ["ALL"], name
        assert "no-new-privileges:true" in service["security_opt"], name
        assert service["init"] is True, name
        assert "/tmp" in service["tmpfs"], name


def test_without_the_variables_of_task_compose_refuses_to_start(tmp_path: Path) -> None:
    for missing in ("AGENCY_DATA_DIR", "AGENCY_UID", "AGENCY_GID"):
        done = compose(tmp_path, "config", **{missing: ""})
        assert done.returncode != 0 and "task docker:up" in done.stderr, missing


def test_images_are_pinned_by_digest_and_match_the_local_tools() -> None:
    """Le stesse versioni di mise.toml e di .python-version, e immagini che non cambiano sotto i piedi."""
    server, web = dockerfile("server.Dockerfile"), dockerfile("web.Dockerfile")
    python = (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip()
    assert re.search(
        rf"^ARG PYTHON=python:{re.escape(python)}\.\d+-slim-trixie{DIGEST}$", server, re.MULTILINE
    )
    assert re.search(rf"^ARG UV=ghcr\.io/astral-sh/uv:{re.escape(MISE['uv'])}{DIGEST}$", server, re.MULTILINE)
    assert re.search(rf"^ARG NODE=node:{re.escape(MISE['node'])}-trixie-slim{DIGEST}$", web, re.MULTILINE)
    assert re.search(rf"^ARG PNPM={re.escape(MISE['pnpm'])}$", web, re.MULTILINE)
    for text in (server, web):
        assert all(line.split()[1].startswith("${") for line in text.splitlines() if line.startswith("FROM "))


def test_the_containers_never_run_as_root_and_django_stays_on_loopback() -> None:
    server, web = dockerfile("server.Dockerfile"), dockerfile("web.Dockerfile")
    assert re.findall(r"^USER (.+)$", server, re.MULTILINE)[-1] == "10001:10001"
    assert re.findall(r"^USER (.+)$", web, re.MULTILINE)[-1] == "node"
    assert 'CMD ["--host", "127.0.0.1", "--port", "8000"]' in server
    # Next.js ascolta su tutte le interfacce del suo spazio di rete; fuori si pubblica solo su loopback.
    assert "HOSTNAME=0.0.0.0" in web and "HOSTNAME" not in server


def test_build_contexts_let_in_only_what_each_image_needs() -> None:
    """Il contesto è la radice, con .env, .data e i progetti del cliente: tutto escluso, poi si riammette."""
    server, web = rules("server.Dockerfile"), rules("web.Dockerfile")
    assert server[0] == "*" and web[0] == "*"
    assert {rule for rule in server if rule.startswith("!")} == {
        "!pyproject.toml",
        "!uv.lock",
        "!README.md",
        "!src/",
    }
    assert {rule for rule in web if rule.startswith("!")} == {"!web/"}
    assert {"web/node_modules", "web/**/.env*", "web/e2e/.data", "web/e2e/.results", "web/.next"} <= set(web)
