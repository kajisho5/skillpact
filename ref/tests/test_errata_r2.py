"""0.8 errata from the second self-review (public review): regression tests."""
import json, os
from pathlib import Path
from skillpact import core

E = core.EFFECTS
def base(name, ver="0.8"):
    return {"contract_version": ver, "skill": {"name": name, "version": "1.0.0"},
            "permissions": {e: {"level": "none"} for e in E} | {"exec": {"level": "scoped", "scope": ["sh"]}},
            "capabilities": [{"id": "hello", "summary": "print", "entry": {"cli": ["sh", "$SKILL_DIR/run.sh"]}, "effects": ["exec"]}],
            "tests": {"cases": [{"id": "t1", "capability": "hello", "run": ["sh", "$SKILL_DIR/run.sh"], "expect": {"exit_code": 0}}]}}
POL = lambda **d: {"policy_version": "0.1", "defaults": {**{e: "allow" for e in E}, **d}}

def mkskill(tmp, name, c, files):
    d = tmp / name; d.mkdir()
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: t\n---\nb\n")
    for k, v in files.items(): (d / k).parent.mkdir(parents=True, exist_ok=True); (d / k).write_text(v)
    (d / "skill.contract.json").write_text(json.dumps(c)); return d

def test_rule_without_scope_matches_scoped_effect():
    c = base("a"); c["permissions"]["write"] = {"level": "scoped", "scope": ["/home/u/.ssh/**"]}; c["capabilities"][0]["effects"] = ["write"]
    p = POL(); p["rules"] = [{"effect": "write", "decision": "deny"}]
    assert core.match_policy(c, p)["decision"] == "deny"

def test_conditional_effect_decision_reaches_compiled_config():
    c = base("b"); c["permissions"]["network"] = {"level": "scoped", "scope": ["up.example.com"]}
    c["capabilities"][0]["conditional_effects"] = [{"effect": "network", "when": "--upload", "scope": ["up.example.com"]}]
    p = POL(network="deny")
    assert "WebFetch(domain:up.example.com)" in core.compile_native(c, p, "claude-code")["config"]["permissions"]["deny"]
    assert core.compile_native(c, p, "codex")["config"]["approval_policy"] == "on-request"

def test_pre_08_signature_never_trusted_author():
    c = base("c", "0.7"); c["integrity"] = {"algorithm": "sha256", "files": {}, "signatures": [{"type": "ed25519", "key": "k", "sig": "", "role": "author"}]}
    assert core.trusted_author(c, {"k"}) is False

def test_migrate_to_08_asks_for_rehash():
    c = base("d", "0.7"); c["integrity"] = {"algorithm": "sha256", "files": {"SKILL.md": "0" * 64}}
    _, ch = core.migrate(c, "0.8"); assert any("skillpact hash" in x for x in ch)

def test_hash_refuses_bytecode(tmp_path):
    d = mkskill(tmp_path, "e", base("e"), {"run.sh": "echo hi\n", "lib/x.pyc": "x"})
    try: core.hash_files(d); assert False
    except SystemExit as e: assert "bytecode" in str(e)

def test_skip_unless_env_needs_pass_env(tmp_path, monkeypatch):
    c = base("f"); c["tests"]["cases"][0].update(skip_unless_env=["SP_DECOY"], run=["sh", "-c", "test -n \"$SP_DECOY\""])
    d = mkskill(tmp_path, "f", c, {"run.sh": "echo hi\n"}); monkeypatch.setenv("SP_DECOY", "x")
    r = core.run_tests(d); assert r["cases"][0].get("skipped") and "pass-env" in r["cases"][0]["skip_reason"]
    r = core.run_tests(d, pass_env=["SP_DECOY"]); assert r["cases"][0]["ok"] and not r["cases"][0].get("skipped")

def test_sandbox_hides_home(tmp_path):
    if core._sandbox() != "bwrap": return
    secret = Path(os.path.realpath(os.environ.get("HOME") or Path.home())) / ".skillpact_test_decoy"; secret.write_text("decoy")
    try:
        c = base("g"); c["tests"]["cases"][0]["run"] = ["sh", "-c", f"test ! -e {secret}"]
        d = mkskill(tmp_path, "g", c, {"run.sh": "echo hi\n"})
        assert core.run_tests(d)["cases"][0]["ok"]
    finally: secret.unlink()


def test_policy_version_08_and_legacy_01():
    import pytest
    for v in ("0.8", "0.1"):
        p = POL(); p["policy_version"] = v
        assert core.match_policy(base("pv"), p)["decision"] in ("allow", "ask", "deny")
    p = POL(); p["policy_version"] = "0.9"
    with pytest.raises(ValueError): core.match_policy(base("pv"), p)
