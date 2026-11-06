"""Idempotency conformance (erratum 0.8.x, ECOSYSTEM_ROADMAP.md step 6): a capability whose x.runtime.idempotency is
`bit_exact` has each case run twice on the same fixture, and its output files (expect.files) must hash the same;
`idempotent: true` alone is checked only with `test --check-idempotent`, and only reported. The conformance suite has
the same cases (conformance/cases/v08x-idempotency-*)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skillpact import cli, core, runtime

NONDET = 'date +%s%N > "$WORKDIR/out.txt"\n'
DET = 'echo same > "$WORKDIR/out.txt"\n'


def skill(tmp_path, name, script, idempotency=None, idempotent=None, files=("out.txt",)):
    d = tmp_path / name; (d / "scripts").mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: idempotency fixture\n---\nbody\n")
    (d / "scripts/run.sh").write_text(script)
    cap = {"id": "make", "summary": "write out.txt", "entry": {"cli": ["sh", "$SKILL_DIR/scripts/run.sh"]}, "effects": ["exec", "write"]}
    if idempotency: cap["x"] = {"runtime": {"idempotency": idempotency}}
    if idempotent is not None: cap["idempotent"] = idempotent
    c = {"contract_version": "0.8", "kind": "tool", "skill": {"name": name, "version": "1.0.0"},
         "permissions": {e: {"level": "none"} for e in core.EFFECTS} | {"exec": {"level": "scoped", "scope": ["sh", "date"]},
                                                                       "write": {"level": "scoped", "scope": ["$WORKDIR/**"]}},
         "capabilities": [cap],
         "tests": {"cases": [{"id": "t1", "capability": "make", "run": ["sh", "$SKILL_DIR/scripts/run.sh"],
                              "expect": {"exit_code": 0, "files": [{"path": f} for f in files]}}]}}
    (d / "skill.contract.json").write_text(json.dumps(c, indent=2))
    assert core.validate(d)["ok"], core.validate(d)
    return d


def test_bit_exact_nondeterministic_fails_and_deterministic_passes(tmp_path):
    r = core.run_tests(skill(tmp_path, "nondet", NONDET, "bit_exact"))
    case = r["cases"][0]
    assert not r["ok"] and case["failures"][0].startswith("IDEMPOTENCY_DIFFERS: bit_exact")
    assert case["idempotency"] == {"mode": "bit_exact", "enforced": True, "compared": ["out.txt"], "differs": ["out.txt"]}
    r = core.run_tests(skill(tmp_path, "det", DET, "bit_exact"))
    assert r["ok"], r["cases"]
    assert r["cases"][0]["idempotency"]["differs"] == []


def test_rerun_that_fails_or_drops_the_file_is_caught(tmp_path):
    # the second run finds its own first output gone and refuses with another exit code: not idempotent either
    once = 'if [ -e "$WORKDIR/marker" ]; then exit 4; fi; : > "$WORKDIR/marker"; echo same > "$WORKDIR/out.txt"\n'
    r = core.run_tests(skill(tmp_path, "once", once, "bit_exact"))
    f = r["cases"][0]["failures"][0]
    assert not r["ok"] and "out.txt sha256" in f and "then missing" in f and "exit code 0 then 4" in f


def test_not_checked_without_output_files_or_after_a_failed_run(tmp_path):
    r = core.run_tests(skill(tmp_path, "nofiles", NONDET, "bit_exact", files=()))
    assert r["ok"] and r["cases"][0]["idempotency"]["skipped"].startswith("the case lists no output file")
    r = core.run_tests(skill(tmp_path, "missing", "true\n", "bit_exact", files=("never.txt",)))
    assert not r["ok"] and "idempotency" in r["cases"][0] and r["cases"][0]["idempotency"]["skipped"] == "the first run failed"


def test_other_modes_are_not_hash_checked(tmp_path):
    for mode in ("content_equivalent", "none"):
        r = core.run_tests(skill(tmp_path, f"m-{mode.replace('_', '-')}", NONDET, mode, idempotent=mode != "none"))
        assert r["ok"] and "idempotency" not in r["cases"][0]


def test_idempotent_flag_is_reported_only_with_check_idempotent(tmp_path):
    d = skill(tmp_path, "legacy", NONDET, idempotent=True)       # the existing boolean, as init --from-native writes it
    r = core.run_tests(d)
    assert r["ok"] and "idempotency" not in r["cases"][0]           # staged: never checked by default
    r = core.run_tests(d, check_idempotent=True)
    assert r["ok"] and r["cases"][0]["idempotency"] == {"mode": "idempotent", "enforced": False, "compared": ["out.txt"], "differs": ["out.txt"]}


def test_cli_flag_and_declares(tmp_path, capsys):
    d = skill(tmp_path, "cli", NONDET, idempotent=True)
    assert cli.main(["test", str(d), "--check-idempotent"]) == 0
    assert json.loads(capsys.readouterr().out)["cases"][0]["idempotency"]["differs"] == ["out.txt"]
    c, _ = core.load_contract(skill(tmp_path, "dec", DET, "bit_exact"))
    assert runtime.declares(c)["idempotency"] == {"bit_exact": ["make"], "content_equivalent": [], "none": []}


def test_contradiction_with_idempotent_flag(tmp_path):
    d = skill(tmp_path, "contra", DET, "bit_exact")
    c = json.loads((d / "skill.contract.json").read_text())
    for mode, flag in (("bit_exact", False), ("content_equivalent", False), ("none", True)):
        c["capabilities"][0]["x"]["runtime"]["idempotency"], c["capabilities"][0]["idempotent"] = mode, flag
        (d / "skill.contract.json").write_text(json.dumps(c))
        assert [f["code"] for f in core.validate(d)["findings"] if f["level"] == "error"] == ["RUNTIME_DECL"], (mode, flag)
