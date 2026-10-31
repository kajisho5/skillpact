"""The `SkillPact verify` composite action's check step (action.yml). Reads its inputs from the environment:

SP_PATH      skill directory                       SP_CONTRACT  contract path ("" = <SP_PATH>/skill.contract.json)
SP_KEYS      space-separated trusted signer keys   SP_TESTS     "true" = run the declared tests (conformance)
SP_MIN       lowest level that passes (L1, L2, L3)

It runs `skillpact validate` (every finding becomes an annotation), then `skillpact conformance` when tests are on,
writes `level` to $GITHUB_OUTPUT and a report to $GITHUB_STEP_SUMMARY, and exits 1 when the level is below SP_MIN.
Reports go to $RUNNER_TEMP, never into the skill directory: a file written there would itself be an unlisted file
for integrity (L3) and a change the test runner reports. Standard library only: it runs before anything else is known
to be installed, with the Python the action set up.
"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

RANK = {"none": 0, "L1": 1, "L2": 2, "L3": 3}
MAX_ANNOTATIONS = 20   # GitHub shows at most 10 errors and 10 warnings per step; the summary lists everything


def rank(level):
    return RANK.get((level or "none")[:2], 0)


def _esc(s, prop=False):
    s = str(s).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return s.replace(":", "%3A").replace(",", "%2C") if prop else s


def annotate(kind, msg, title=None, file=None):
    props = ",".join(f"{k}={_esc(v, True)}" for k, v in (("file", file), ("title", title)) if v)
    print(f"::{kind}{' ' + props if props else ''}::{_esc(msg)}", flush=True)


def skillpact(*argv):
    """(exit code, parsed JSON or None, raw stdout+stderr) of `python -m skillpact.cli ...`."""
    p = subprocess.run([sys.executable, "-m", "skillpact.cli", *argv], capture_output=True, text=True)
    try: data = json.loads(p.stdout)
    except ValueError: data = None
    return p.returncode, data, (p.stdout + p.stderr)


def _out(name, value):
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f: f.write(f"{name}={value}\n")


def main():
    path, contract = os.environ.get("SP_PATH") or ".", os.environ.get("SP_CONTRACT", "")
    keys, tests = os.environ.get("SP_KEYS", "").split(), os.environ.get("SP_TESTS", "true") == "true"
    want = (os.environ.get("SP_MIN") or "L1").strip()
    cfile = contract or str(Path(path) / "skill.contract.json")
    summary = [f"### SkillPact: `{path}`", ""]

    def finish(level, code):
        _out("level", level)
        summary[0] = f"### SkillPact: `{level}` ({path})"
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f: f.write("\n".join(summary) + "\n")
        return code

    if want not in ("L1", "L2", "L3"):
        annotate("error", f"min-level must be L1, L2 or L3 (got {want!r})", "SkillPact: bad input"); return finish("none", 1)
    if rank(want) > 1 and not tests:
        annotate("error", f"min-level {want} needs the conformance tests: set run-tests: true (or lower min-level to L1)", "SkillPact: bad input")
        return finish("none", 1)
    if not Path(path).is_dir():
        annotate("error", f"skill directory {path!r} does not exist (input `path`, relative to {os.getcwd()})", "SkillPact: no skill directory")
        return finish("none", 1)
    if not Path(cfile).is_file():
        annotate("error", f"no contract at {cfile!r}: add skill.contract.json (`skillpact init {path} -o skill.contract.json`) or set input `contract`", "SkillPact: no contract")
        return finish("none", 1)
    copt = ["--contract", contract] if contract else []

    # 1. validate: every finding, so a failure says what is wrong and where
    _, v, raw = skillpact("validate", path, *copt)
    if v is None:
        annotate("error", f"`skillpact validate` did not print JSON:\n{raw[-2000:]}", "SkillPact: validator crashed", cfile); return finish("none", 1)
    findings = v.get("findings", [])
    for f in sorted(findings, key=lambda f: f["level"] != "error")[:MAX_ANNOTATIONS]:
        annotate("error" if f["level"] == "error" else "warning", f"{f['message']} (at {f.get('where') or '-'})", f"SkillPact {f['code']}", cfile)
    summary += [f"**validate**: {v.get('errors', 0)} error(s), {v.get('warnings', 0)} warning(s)", ""]
    if findings:
        summary += ["| level | code | where | message |", "|---|---|---|---|"]
        summary += [f"| {f['level']} | `{f['code']}` | `{f.get('where') or '-'}` | {str(f['message']).replace('|', '/')} |" for f in findings] + [""]

    # 2. level: conformance (runs the declared tests in the sandbox), or L1 from validate alone
    if not tests:
        level = "L1-declared" if v.get("ok") else "none"
        report = v
    else:
        _, report, raw = skillpact("conformance", path, *copt, *(["--trusted-key", *keys] if keys else []))
        if report is None:
            annotate("error", f"`skillpact conformance` did not print JSON:\n{raw[-2000:]}", "SkillPact: conformance crashed", cfile); return finish("none", 1)
        level = report.get("level", "none")
        t = report.get("tests") or {}
        if t: summary += [f"**tests**: {t.get('passed', 0)}/{t.get('total', 0)} passed, sandbox `{t.get('sandbox')}`, file system isolated: {t.get('fs_isolated')}, exec audit: {t.get('exec_audit') or 'off'}", ""]
        for r in report.get("requirements_failed", []):
            annotate("error", f"requirement not met on this runner: {r}. Install it in an earlier step, or mark it optional in the contract", "SkillPact: requirement", cfile)
        if t.get("error"): annotate("error", t["error"], "SkillPact: tests did not run", cfile)
        if report.get("note"): annotate("warning" if rank(level) < rank(want) else "notice", report["note"], "SkillPact: level")
        if rank(level) < rank(want) and t and (t.get("passed", 0) + t.get("skipped", 0) < t.get("total", 0) or not report.get("note")):
            # conformance reports counts only; a second, diagnostic run names the failing cases (or the sandbox
            # violation that failed a run whose cases all passed)
            _, d, _ = skillpact("test", path, *copt)
            for c in (d or {}).get("cases", []):
                if c.get("ok"): continue
                why = "; ".join(map(str, c.get("failures") or [])) or "failed"
                if c.get("exec_undeclared"): why += f"; started programs not in the exec scope: {', '.join(c['exec_undeclared'])}"
                if c.get("stderr_tail"): why += f"\nstderr: {c['stderr_tail'][-600:]}"
                annotate("error", f"case {c.get('id')} ({c.get('capability')}): {why}", "SkillPact: test failed", cfile)
                summary.append(f"- failed: `{c.get('id')}` ({c.get('capability')}): {why.splitlines()[0]}")
            if d and (d.get("outside_writes") or d.get("skill_dir_writes")):
                annotate("error", f"writes outside $WORKDIR or changes to the skill directory: {json.dumps({k: d.get(k) for k in ('outside_writes', 'skill_dir_writes') if d.get(k)})[:1500]}", "SkillPact: sandbox violation", cfile)
            summary.append("")

    out = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()) / "skillpact-report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    summary += ["<details><summary>JSON</summary>", "", "```json", json.dumps(report, indent=2, ensure_ascii=False), "```", "</details>"]
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if rank(level) < rank(want):
        annotate("error", f"SkillPact level {level} is below min-level {want}", "SkillPact: level too low"); return finish(level, 1)
    print(f"SkillPact level: {level} (min-level {want})")
    return finish(level, 0)


if __name__ == "__main__":
    sys.exit(main())
