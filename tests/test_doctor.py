from argparse import Namespace
from pathlib import Path

import pytest

from agency import doctor
from agency.cli import _doctor
from agency.config import Settings
from agency.doctor import Finding, run_checks
from agency.tools.sandbox import MEMORY_MAX_BYTES, TASKS_MAX


@pytest.fixture(autouse=True)
def no_gpu_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """`nvidia-smi` can take seconds on a GPU machine, and none of these tests asserts on the GPU."""
    monkeypatch.setattr("agency.doctor._gpu", lambda: "non rilevata")


def test_doctor_never_exposes_the_key(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-segreto")
    findings = run_checks(Settings())
    assert next(f for f in findings if f.name == "chiave API").ok
    assert all("sk-ant" not in f.detail for f in findings)
    assert "sk-ant" not in capsys.readouterr().out


def scope_finding():  # type: ignore[no-untyped-def]
    return next(f for f in run_checks(Settings()) if f.name == "limiti sandbox")


def test_doctor_shows_the_sandbox_caps_when_the_scope_can_be_created() -> None:
    finding = scope_finding()
    assert finding.ok
    assert finding.required
    assert f"{MEMORY_MAX_BYTES // 2**30} GiB" in finding.detail
    assert f"{TASKS_MAX} task" in finding.detail


def test_doctor_says_why_the_sandbox_scope_cannot_be_created(  # type: ignore[no-untyped-def]
    monkeypatch, tmp_path, capsys
) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "no-runtime-dir"))
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    finding = scope_finding()
    assert not finding.ok
    assert finding.required
    assert "systemd-run" in finding.detail
    assert _doctor(Namespace()) == 1
    lines = [line for line in capsys.readouterr().out.splitlines() if "limiti sandbox" in line]
    assert len(lines) == 1
    assert lines[0].startswith("ERR ")
    assert "systemd-run" in lines[0]


def finding(name: str) -> Finding:
    return next(item for item in run_checks(Settings()) if item.name == name)


def test_docker_is_optional_and_names_what_needs_it() -> None:
    """Only the dashboard in Docker needs it: a false ERR would teach the operator to read past red lines."""
    docker = finding("docker")
    assert not docker.required
    assert "task docker:up" in docker.detail


def test_chromium_is_found_at_the_revision_playwright_expects(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    expected = doctor._expected_browsers()
    assert expected is not None
    _, folders = expected
    assert {folder.split("-")[0] for folder in folders} == {"chromium", "chromium_headless_shell"}
    for folder in folders:
        (tmp_path / folder).mkdir()
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
    chromium = finding("Chromium")
    assert chromium.ok and chromium.required


def test_a_missing_chromium_is_an_error_that_gives_the_install_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
    chromium = finding("Chromium")
    assert not chromium.ok and chromium.required
    assert doctor.CHROMIUM_INSTALL in chromium.detail


def test_without_the_web_dependencies_doctor_says_to_run_setup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(doctor, "WEB", tmp_path)
    chromium = finding("Chromium")
    assert not chromium.ok and chromium.required
    assert "task setup" in chromium.detail
