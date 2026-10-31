"""The GitHub Action's check step (.github/action/verify.py, ECOSYSTEM_ROADMAP.md step 3): inputs, annotations, level, exit code.
.github/workflows/action.yml runs the action itself (action.yml) on the same fixtures in CI."""
import json, os, shutil, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VERIFY = REPO / ".github" / "action" / "verify.py"
CASES = REPO / "conformance" / "cases"


def run(tmp_path, path, *, contract="", tests="false", min_level="L1", keys=""):
    out, summary, runner = tmp_path / "out.txt", tmp_path / "summary.md", tmp_path / "runner"
    runner.mkdir(exist_ok=True)
    env = {**os.environ, "SP_PATH": str(path), "SP_CONTRACT": str(contract), "SP_TESTS": tests, "SP_MIN": min_level, "SP_KEYS": keys,
           "GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(summary), "RUNNER_TEMP": str(runner)}
    p = subprocess.run([sys.executable, str(VERIFY)], env=env, capture_output=True, text=True, cwd=tmp_path, timeout=600)
    outputs = dict(line.split("=", 1) for line in out.read_text().splitlines()) if out.exists() else {}
    return p, outputs, (summary.read_text() if summary.exists() else "")


def _copy_case(tmp_path, name, **edit):
    d = tmp_path / "skills" / name
    shutil.copytree(CASES / name, d)
    c = json.loads((d / "skill.contract.json").read_text())
    for k, v in edit.items():
        if v is None: c.pop(k, None)
        else: c[k] = v
    (d / "skill.contract.json").write_text(json.dumps(c, indent=2))
    return d


def test_valid_contract_is_l1_and_writes_nothing_into_the_skill(tmp_path):
    d = _copy_case(tmp_path, "valid-minimal")
    before = sorted(p.name for p in d.iterdir())
    p, outputs, summary = run(tmp_path, d)
    assert p.returncode == 0, p.stdout + p.stderr
    assert outputs["level"] == "L1-declared" and "SkillPact: `L1-declared`" in summary
    assert sorted(p.name for p in d.iterdir()) == before   # the report goes to RUNNER_TEMP, not the skill directory
    assert json.loads((tmp_path / "runner" / "skillpact-report.json").read_text())["ok"] is True


def test_invalid_contract_fails_with_one_annotation_per_finding(tmp_path):
    p, outputs, summary = run(tmp_path, CASES / "scope-widened")
    assert p.returncode == 1 and outputs["level"] == "none"
    assert "::error file=" in p.stdout and "title=SkillPact SCOPE_WIDENED::" in p.stdout
    assert "effect_scopes.write not within permissions.write.scope (at /capabilities/0)" in p.stdout
    assert "::warning " in p.stdout and "FM_NAME_DIR" in p.stdout
    assert "below min-level L1" in p.stdout and "| error | `SCOPE_WIDENED` |" in summary


def test_contract_input_points_at_a_manifest_outside_the_skill(tmp_path):
    d = tmp_path / "valid-minimal"; d.mkdir()
    shutil.copy(CASES / "valid-minimal" / "SKILL.md", d)
    manifest = tmp_path / "manifests" / "contract.json"; manifest.parent.mkdir()
    shutil.copy(CASES / "valid-minimal" / "skill.contract.json", manifest)
    p, _, _ = run(tmp_path, d)
    assert p.returncode == 1 and "SkillPact%3A no contract" in p.stdout and "set input `contract`" in p.stdout
    p, outputs, _ = run(tmp_path, d, contract=manifest)
    assert p.returncode == 0, p.stdout + p.stderr
    assert outputs["level"] == "L1-declared"


def test_bad_inputs_are_refused_before_anything_runs(tmp_path):
    p, outputs, _ = run(tmp_path, CASES / "valid-minimal", min_level="L2")
    assert p.returncode == 1 and "needs the conformance tests: set run-tests: true" in p.stdout and outputs["level"] == "none"
    p, _, _ = run(tmp_path, CASES / "valid-minimal", min_level="L4")
    assert p.returncode == 1 and "min-level must be L1, L2 or L3" in p.stdout
    p, _, _ = run(tmp_path, tmp_path / "missing")
    assert p.returncode == 1 and "SkillPact%3A no skill directory" in p.stdout


def test_tests_run_and_a_failing_case_is_named(tmp_path):
    ok = _copy_case(tmp_path, "v08-valid-signed", integrity=None)   # unsigned copy: L2 at most
    p, outputs, summary = run(tmp_path, ok, tests="true")
    assert p.returncode == 0, p.stdout + p.stderr
    assert outputs["level"] in ("L1-declared", "L2-tested") and "**tests**: 1/1 passed" in summary
    c = json.loads((ok / "skill.contract.json").read_text())
    c["tests"]["cases"][0]["expect"]["stdout_contains"] = "not-in-the-output"
    (ok / "skill.contract.json").write_text(json.dumps(c))
    p, outputs, summary = run(tmp_path, ok, tests="true", min_level="L2")
    assert p.returncode == 1 and outputs["level"] == "L1-declared"
    assert "title=SkillPact%3A test failed::case t1 (hello)" in p.stdout and "- failed: `t1` (hello)" in summary
