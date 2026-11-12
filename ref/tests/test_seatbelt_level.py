"""Proposal #11 (0.8.x, option 2): a level reported from Seatbelt mode carries RUNNER_PARTIAL_ISOLATION."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skillpact import cli, core

CASE = Path(__file__).resolve().parents[2] / "conformance" / "cases" / "v08-valid-signed"


def _conformance(monkeypatch, capsys, sandbox):
    t = {"ok": True, "passed": 1, "total": 1, "sandbox": sandbox, "fs_isolated": True, "network_isolated": True, "exec_audit": "none", "requirements": []}
    monkeypatch.setattr(core, "run_tests", lambda *a, **k: t)
    cli.main(["conformance", str(CASE)]); return json.loads(capsys.readouterr().out)


def test_seatbelt_level_is_marked(monkeypatch, capsys):
    r = _conformance(monkeypatch, capsys, "seatbelt")
    assert r["level"] == "L2-tested" and r["tests"]["sandbox"] == "seatbelt"
    assert [w["code"] for w in r["runner_warnings"]] == ["RUNNER_PARTIAL_ISOLATION"]


def test_bwrap_level_has_no_mark(monkeypatch, capsys):
    r = _conformance(monkeypatch, capsys, "bwrap")
    assert r["level"] == "L2-tested" and "runner_warnings" not in r
