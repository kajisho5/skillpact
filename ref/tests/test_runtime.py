"""Runtime declarations x.runtime (erratum 0.8.x, ECOSYSTEM_ROADMAP.md step 5): progress events and error classes.
The validator checks the declaration (RUNTIME_DECL); the runner checks what each case emits (PROGRESS_EVENT,
PROGRESS_MISSING, ERROR_UNCLASSIFIED); `conformance` and the Action report what a contract declares. The conformance
suite has the same cases (conformance/cases/v08x-*, run.py --test-cmd)."""
import json, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skillpact import cli, core, runtime
from test_action import run as run_action

REPO = Path(__file__).resolve().parents[2]
CASES = REPO / "conformance" / "cases"
SAMPLES = REPO / "samples"
RT = {"progress": {"stream": "stderr", "steps": ["read", "write"]}, "errors": {"classes": {"BAD_INPUT": "input", "BUSY": "transient"}}}


def codes(r): return [f["code"] for f in r["findings"] if f["level"] == "error"]


def case(tmp_path, name, decl=None, cap=None, script="echo hi\n", tags=None, exit_code=0):
    """A 0.8 tool skill `name` whose one capability runs scripts/run.sh (`script`) in one test case."""
    d = tmp_path / name; (d / "scripts").mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: runtime fixture\n---\nbody\n")
    (d / "scripts/run.sh").write_text(script)
    c = {"contract_version": "0.8", "kind": "tool", "skill": {"name": name, "version": "1.0.0"},
         "permissions": {e: {"level": "none"} for e in core.EFFECTS} | {"exec": {"level": "scoped", "scope": ["sh"]}},
         "capabilities": [{"id": "hello", "summary": "print", "entry": {"cli": ["sh", "$SKILL_DIR/scripts/run.sh"]}, "effects": ["exec"]}],
         "tests": {"cases": [{"id": "t1", "capability": "hello", "run": ["sh", "$SKILL_DIR/scripts/run.sh"], "expect": {"exit_code": exit_code},
                              **({"tags": tags} if tags else {})}]}}
    if decl is not None: c["x"] = {"runtime": decl}
    if cap is not None: c["capabilities"][0]["x"] = {"runtime": cap}
    (d / "skill.contract.json").write_text(json.dumps(c, indent=2))
    return d


def test_valid_minimal_is_still_valid_and_declares_nothing():
    assert core.validate(CASES / "valid-minimal")["ok"]
    c, _ = core.load_contract(CASES / "valid-minimal")
    assert runtime.declares(c) == {"capabilities": len(c["capabilities"]), "progress": [], "error_classes": {}}


def test_no_existing_contract_changes_level():
    # Staged: optional now, so every contract in this repository that was valid stays valid, with no new finding.
    for d in [*SAMPLES.iterdir(), *(p for p in CASES.iterdir() if not p.name.startswith("v08x-"))]:
        if not (d / "skill.contract.json").is_file(): continue
        assert "RUNTIME_DECL" not in codes(core.validate(d)), d.name


def test_declaration_errors(tmp_path):
    for decl, cap in (({"progress": {"stream": "log"}}, None), ({"errors": {"classes": {"X": "fatal"}}}, None),
                      ({"errors": {"classes": {}}}, None), ({"progress": {"stream": "stderr", "steps": []}}, None),
                      ({"progress": {"stream": "stderr", "flag": "progress"}}, None), ({"retries": 3}, None), ("yes", None),
                      (None, {"progress": True}), (RT, {"errors": {"classes": {"BUSY": "engine"}}})):
        d = case(tmp_path / str(len(list(tmp_path.iterdir()))), "rt", decl, cap)
        assert codes(core.validate(d)) and set(codes(core.validate(d))) == {"RUNTIME_DECL"}, (decl, cap)
    assert core.validate(case(tmp_path / "ok", "rt", RT, {"progress": False, "errors": {"classes": {"BUSY": "transient"}}}))["ok"]


def test_effective_declaration_merges_capability_over_contract():
    c = {"x": {"runtime": RT}, "capabilities": []}
    e = runtime.effective(c, {"x": {"runtime": {"progress": False, "errors": {"classes": {"OOPS": "engine"}}}}})
    assert "progress" not in e and e["errors"] == {"code_path": "error.code", "classes": {"BAD_INPUT": "input", "BUSY": "transient", "OOPS": "engine"}}
    assert runtime.effective(c, {})["progress"] == RT["progress"]
    assert runtime.effective({"capabilities": []}, {"x": {"runtime": {"errors": {"code_path": "err.kind", "classes": {"A": "policy"}}}}})["errors"]["code_path"] == "err.kind"


def test_check_case_progress():
    decl = {"progress": RT["progress"]}
    ok = '{"event":"progress","step":"read","percent":0,"eta_s":null}\nnot json\n{"event":"progress","step":"write","percent":100,"eta_s":0}\n'
    assert runtime.check_case(decl, "", ok, ["progress"]) == ([], {"progress_events": 2})
    fails, _ = runtime.check_case(decl, "", '{"event":"progress","step":"write","percent":60,"eta_s":1}\n{"event":"progress","step":"write","percent":20,"eta_s":1}\n')
    assert fails and fails[0].startswith("PROGRESS_EVENT: stderr line 2: percent went down")
    fails, _ = runtime.check_case(decl, "", '{"event":"progress","step":"dance","percent":1,"eta_s":1}\n')
    assert "is not one of" in fails[0]
    fails, _ = runtime.check_case(decl, "", '{"event":"progress","step":"read","percent":"5%","eta_s":-1}\n')
    assert len(fails) == 1 and "PROGRESS_EVENT" in fails[0]
    assert runtime.check_case(decl, "", "", ["progress"])[0][0].startswith("PROGRESS_MISSING")
    assert runtime.check_case(decl, "", "")[0] == []                           # untagged: emitting nothing is fine
    assert runtime.check_case({"progress": {"stream": "stdout"}}, ok, "")[1] == {"progress_events": 2}


def test_check_case_error_classes():
    decl = {"errors": {"code_path": "error.code", "classes": {"BAD_INPUT": "input"}}}
    assert runtime.check_case(decl, '{"ok": false, "error": {"code": "BAD_INPUT"}}', "") == ([], {"error_code": "BAD_INPUT", "error_class": "input"})
    fails, info = runtime.check_case(decl, 'log line\n{"ok": false, "error": {"code": "DISK_FULL"}}\n', "")
    assert fails[0].startswith("ERROR_UNCLASSIFIED") and info["error_code"] == "DISK_FULL"
    assert runtime.check_case(decl, '{"ok": true}', "") == ([], {})
    assert runtime.check_case(decl, "plain text", "") == ([], {})


def test_runner_fails_a_case_whose_events_break_the_declaration(tmp_path):
    bad = case(tmp_path, "rt-bad", RT, script='printf \'{"event":"progress","step":"read","percent":90,"eta_s":1}\\n{"event":"progress","step":"read","percent":10,"eta_s":1}\\n\' >&2\n')
    r = core.run_tests(bad)
    assert not r["ok"] and r["cases"][0]["failures"][0].startswith("PROGRESS_EVENT") and r["cases"][0]["progress_events"] == 2
    err = case(tmp_path, "rt-err", RT, script="echo '{\"ok\": false, \"error\": {\"code\": \"BUSY\"}}'; exit 3\n", exit_code=3)
    r = core.run_tests(err)
    assert r["ok"], r["cases"]
    assert r["cases"][0]["error_class"] == "transient"


def test_conformance_reports_what_is_declared(tmp_path, capsys):
    d = case(tmp_path, "rt-ok", RT, cap={"errors": {"classes": {"OOPS": "engine"}}},
             script='printf \'{"event":"progress","step":"read","percent":0,"eta_s":null}\\n\' >&2\n', tags=["progress"])
    cli.main(["conformance", str(d)])
    r = json.loads(capsys.readouterr().out)
    assert r["declares"] == {"capabilities": 1, "progress": ["hello"], "error_classes": {"BAD_INPUT": "input", "BUSY": "transient", "OOPS": "engine"}}
    p, outputs, summary = run_action(tmp_path, d, tests="true")
    assert json.loads(outputs["declares"])["error_classes"]["OOPS"] == "engine"
    assert "**declares**: progress events for 1 of 1 capabilities, error classes for 3 error code(s)" in summary


def test_runtime_schema_copies_are_identical():
    ref = (REPO / "ref/skillpact/runtime_schema.json").read_text()
    assert (REPO / "docs/schema/runtime-v0.8.json").read_text() == ref == (REPO / "ts/src/runtime_schema.json").read_text()
