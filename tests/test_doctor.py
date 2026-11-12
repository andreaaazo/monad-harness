from argparse import Namespace

import pytest

from agency.cli import _doctor
from agency.config import Settings
from agency.doctor import run_checks
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
