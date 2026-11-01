from agency.config import Settings
from agency.doctor import run_checks


def test_doctor_never_exposes_the_key(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-segreto")
    findings = run_checks(Settings())
    assert next(f for f in findings if f.name == "chiave API").ok
    assert all("sk-ant" not in f.detail for f in findings)
    assert "sk-ant" not in capsys.readouterr().out
