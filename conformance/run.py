#!/usr/bin/env python3
"""SkillPact conformance suite runner (implementation-independent).

Usage: run.py --cmd 'python3 -m skillpact.cli validate {dir}' [--test-cmd 'python3 -m skillpact.cli test {dir}']
The command is run per case with {dir} replaced by the case directory. It MUST print one JSON object
with "ok" (bool) and "findings": [{"level": "error"|"warn", "code": str}, ...]. Exit code is ignored.
--test-cmd (runners, erratum 0.8.x) is run for the cases whose expectation has "test"; it MUST print one JSON object
with "ok" and "cases": [{"failures": [str, ...]}, ...].
Expectation semantics (manifest.json):
  valid            -> ok must equal this
  errors           -> every listed code must be reported as an error
  errors_any       -> at least one listed code must be reported as an error
  warnings_include -> every listed code must be reported as a warning
  test             -> with --test-cmd: {"ok": bool, "failures_include": [code prefix of a case failure, ...]}
"""
import argparse, json, shlex, subprocess, sys
from pathlib import Path

HERE = Path(__file__).parent


def run_test(cmd: str, d: Path, ex: dict) -> list:
    p = subprocess.run([a.replace("{dir}", str(d)) for a in shlex.split(cmd)], capture_output=True, text=True, timeout=300)
    try: out = json.loads(p.stdout)
    except json.JSONDecodeError: return ["test output is not JSON"]
    fails = []
    if bool(out.get("ok")) != ex["ok"]: fails.append(f"test ok={out.get('ok')} expected {ex['ok']}")
    reported = [f for c in out.get("cases", []) for f in c.get("failures", [])]
    for code in ex.get("failures_include", []):
        if not any(str(f).startswith(code) for f in reported): fails.append(f"no case failure {code} (got {reported})")
    return fails


def run(cmd: str, only=None, test_cmd=None) -> dict:
    m = json.loads((HERE / "manifest.json").read_text()); res = []
    for case in m["cases"]:
        if only and case["id"] not in only: continue
        d = HERE / "cases" / case["id"]; ex = case["expect"]; fails = []
        p = subprocess.run([a.replace("{dir}", str(d)) for a in shlex.split(cmd)], capture_output=True, text=True, timeout=120)
        try: out = json.loads(p.stdout)
        except json.JSONDecodeError: res.append({"id": case["id"], "ok": False, "failures": ["output is not JSON"]}); continue
        errs = {f["code"] for f in out.get("findings", []) if f.get("level") == "error"}
        warns = {f["code"] for f in out.get("findings", []) if f.get("level") == "warn"}
        if bool(out.get("ok")) != ex["valid"]: fails.append(f"ok={out.get('ok')} expected {ex['valid']}")
        for code in ex.get("errors", []):
            if code not in errs: fails.append(f"missing error {code}")
        if ex.get("errors_any") and not errs & set(ex["errors_any"]): fails.append(f"none of {ex['errors_any']} reported")
        for code in ex.get("warnings_include", []):
            if code not in warns: fails.append(f"missing warning {code}")
        if test_cmd and "test" in ex: fails += run_test(test_cmd, d, ex["test"])
        res.append({"id": case["id"], "ok": not fails, "failures": fails})
    return {"suite": m["suite"], "spec_version": m["spec_version"], "passed": sum(r["ok"] for r in res), "total": len(res), "ok": all(r["ok"] for r in res), "cases": res}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--cmd", required=True); ap.add_argument("--only", nargs="*")
    ap.add_argument("--test-cmd", help="runner command for the cases with a `test` expectation (erratum 0.8.x)")
    a = ap.parse_args(); r = run(a.cmd, a.only, a.test_cmd); print(json.dumps(r, ensure_ascii=False, indent=2)); sys.exit(0 if r["ok"] else 1)
