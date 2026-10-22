"""0.8.x erratum: programs a test case starts are recorded (strace, outside the sandbox) and checked against the exec scope."""
import json, os, shutil, sys
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skillpact import core

CASES = Path(__file__).resolve().parents[2] / "conformance" / "cases"
needs_strace = pytest.mark.skipif(not core._exec_tracer(), reason="needs strace")


def test_tree_attribution():
    # 1 = bwrap, forks 2 (pid 1 in the sandbox) -> 3 = sh -c; sh starts cp (plumbing) and git (counted) and python3;
    # python3 starts fc-match (counted: below the shell's direct children)
    ev = {1: [("exec", "/usr/bin/bwrap"), ("fork", 2)], 2: [("fork", 3)],
          3: [("exec", "/usr/bin/sh"), ("fork", 4), ("fork", 5), ("fork", 6)],
          4: [("exec", "/usr/bin/cp")], 5: [("exec", "/usr/bin/git")], 6: [("exec", "/usr/bin/python3"), ("fork", 7)],
          7: [("exec", "/usr/bin/fc-match")]}
    assert sorted(core.skill_execs(ev, inline_shell=True)) == ["/usr/bin/fc-match", "/usr/bin/git", "/usr/bin/python3"]


def test_tree_attribution_no_shell_counts_children():
    ev = {1: [("exec", "/usr/bin/python3"), ("fork", 2)], 2: [("exec", "/usr/bin/cp")]}
    assert core.skill_execs(ev, inline_shell=False) == ["/usr/bin/cp"]


def test_env_shebang_is_transparent():
    ev = {1: [("exec", "/usr/bin/sh"), ("fork", 2)], 2: [("exec", "/usr/bin/env"), ("exec", "/usr/bin/python3"), ("fork", 3)], 3: [("exec", "/usr/bin/curl")]}
    assert sorted(core.skill_execs(ev, inline_shell=True)) == ["/usr/bin/curl", "/usr/bin/python3"]


def test_scope_and_skill_files(tmp_path):
    c = {"permissions": {"exec": {"level": "scoped", "scope": ["python3", "ff*"]}}}
    paths = ["/usr/bin/python3", "/usr/bin/ffprobe", "/usr/bin/git", str(tmp_path / "scripts" / "run.sh")]
    assert core.undeclared_execs(paths, c, [str(tmp_path)]) == ["git"]
    cap = {"effect_scopes": {"exec": ["python3"]}}
    assert core.undeclared_execs(paths, c, [str(tmp_path)], cap) == ["ffprobe", "git"]
    assert core.undeclared_execs(paths, {"permissions": {"exec": {"level": "any"}}}) == []


def _case(tmp_path, run):
    d = tmp_path / "v08-valid-signed"; shutil.copytree(CASES / "v08-valid-signed", d)
    c = json.loads((d / "skill.contract.json").read_text())
    c["tests"]["cases"] = [{"id": "x", "capability": c["capabilities"][0]["id"], "run": run, "expect": {"exit_code": 0}}]
    (d / "skill.contract.json").write_text(json.dumps(c)); return d


@needs_strace
def test_undeclared_exec_fails(tmp_path):
    # exec scope is ['sh']: git and perl are neither declared nor test utilities
    r = core.run_tests(_case(tmp_path, ["sh", "-c", "git --version >/dev/null && perl -e 1 && echo ok"]))
    assert r["exec_audit"] == "strace" and not r["ok"] and r["cases"][0]["exec_undeclared"] == ["git", "perl"]


@needs_strace
def test_test_utilities_in_inline_shell_pass(tmp_path):
    r = core.run_tests(_case(tmp_path, ["sh", "-c", "echo a > f && cp f g && cmp f g && sha256sum f > /dev/null"]))
    assert r["ok"], r["cases"]


@needs_strace
def test_program_started_by_skill_code_is_counted(tmp_path):
    r = core.run_tests(_case(tmp_path, ["sh", "-c", "sh -c 'cp /dev/null x'"]))   # cp below the test shell's direct child
    assert not r["ok"] and r["cases"][0]["exec_undeclared"] == ["cp"]


@needs_strace
def test_audit_can_be_turned_off(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLPACT_EXEC_AUDIT", "0")
    r = core.run_tests(_case(tmp_path, ["sh", "-c", "git --version"])); assert r["ok"] and r["exec_audit"] == "none"
