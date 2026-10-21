import copy, json, shutil, subprocess, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skillpact import core, cli

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT.parent / "samples" / "ffmpeg-skill"
POL = lambda n: json.loads((ROOT / "policies" / f"{n}.json").read_text())

@pytest.fixture
def skill(tmp_path):
    d = tmp_path / "ffmpeg-skill"; shutil.copytree(SAMPLE, d, ignore=shutil.ignore_patterns("__pycache__")); return d

def C(d): return json.loads((d / "skill.contract.json").read_text())
def W(d, c): (d / "skill.contract.json").write_text(json.dumps(c))

def test_sample_valid(): assert core.validate(SAMPLE)["ok"]

def test_flagship_all_42_tools_conformance_pass_network_sandboxed():
    r = core.run_tests(SAMPLE); assert r["ok"], [c for c in r["cases"] if not c["ok"]]
    assert r["total"] >= 78 and r["passed"] == r["total"] and all(c["network_sandboxed"] for c in r["cases"])
    tested = {c["capability"] for c in r["cases"]}; assert len(tested) == 42

def test_flagship_matches_native_contract():
    native = json.loads(subprocess.run(["python3", "scripts/_contract.py", "contract", "--json"], cwd=SAMPLE, capture_output=True, text=True).stdout)
    c = C(SAMPLE)
    assert {t["name"] for t in native["tools"]} == {x["entry"]["mcp_tool"] for x in c["capabilities"]}
    assert c["skill"]["version"] == native["skill"]["version"]
    ff = next(b for b in c["requirements"]["binaries"] if b["name"] == "ffmpeg"); assert ff["version"] == ">=5.0"

def test_flagship_mcp_server_matches_contract():
    import os
    os.environ["FFMPEG_SKILL_MCP_FULL"] = "1"
    r = core.mcp_check(SAMPLE, ["python3", "$SKILL_DIR/mcp/server.py"]); assert r["ok"], r["problems"]
    assert r["tools_served"] == r["tools_mapped"] == 42

def test_flagship_is_L3():
    assert cli.main(["conformance", str(SAMPLE), "--trusted-key", (ROOT.parent / "keys/public/seventhwell-skill-signing.pub").read_text().strip()]) == 0

def test_undeclared_effect(skill):
    c = C(skill); c["capabilities"][0]["effects"].append("send"); W(skill, c)
    assert "UNDECLARED_EFFECT" in [f["code"] for f in core.validate(skill)["findings"]]

def test_schema_error(skill):
    c = C(skill); c["permissions"]["send"]["level"] = "maybe"; W(skill, c)
    assert not core.validate(skill)["ok"]

def test_name_mismatch_and_missing_entry(skill):
    c = C(skill); c["skill"]["name"] = "other"; c["capabilities"][0]["entry"]["cli"] = ["python3", "$SKILL_DIR/scripts/nope.py"]; W(skill, c)
    codes = {f["code"] for f in core.validate(skill)["findings"]}
    assert {"NAME_MISMATCH", "ENTRY_MISSING"} <= codes

def test_backward_compat_skill_md_unchanged():
    assert (SAMPLE / "SKILL.md").read_bytes() == (ROOT.parent / "ffmpeg-skill-ro" / "SKILL.md").read_bytes()

def test_failing_test_detected(skill):
    c = C(skill); case = next(t for t in c["tests"]["cases"] if t["id"] == "probe-basic"); case["expect"]["stdout_json"][0]["equals"] = 999; W(skill, c)
    r = core.run_tests(skill, only=["probe-basic"]); assert not r["ok"] and r["cases"][0]["failures"]

def test_network_actually_blocked(skill):
    c = C(skill); c["tests"]["cases"] = [{"id": "net", "run": ["python3", "-c", "import socket;socket.create_connection(('1.1.1.1',53),2)"], "expect": {"exit_code": 0}}]; W(skill, c)
    assert not core.run_tests(skill)["ok"]

def test_missing_binary(skill):
    c = C(skill); c["requirements"]["binaries"].append({"name": "definitely-not-a-binary"}); W(skill, c)
    r = core.run_tests(skill); assert not r["ok"] and r["error"] == "requirements not met"

def test_hash_sign_verify_and_tamper(skill, tmp_path):
    key = tmp_path / "k.pem"; pub = core.keygen(key)
    assert core.hash_files(skill) > 10; core.sign(skill, key, "shogo")
    c = C(skill); assert core.verify_signatures(c) == {pub: True} and core.validate(skill)["ok"]
    (skill / "scripts" / "probe.py").write_text("# tampered\n")
    assert "INTEGRITY_MISMATCH" in [f["code"] for f in core.validate(skill)["findings"]]
    c["skill"]["version"] = "9.9.9"; assert core.verify_signatures(c) == {pub: False}

# ---- harness policy ----
def test_policy_solo_dev_allows_ffmpeg():
    r = core.match_policy(C(SAMPLE), POL("solo-dev"))
    assert r["decision"] == "allow", r
    assert {c["capability"]: c["decision"] for c in r["capabilities"]}["media.cut"] == "allow"

def test_policy_write_outside_scope_asks():
    c = C(SAMPLE); c["permissions"]["write"]["scope"] = ["~/Movies/**"]
    r = core.match_policy(c, POL("solo-dev")); assert r["decision"] == "ask"

def test_policy_spend_denied_and_send_any_never_auto():
    c = copy.deepcopy(C(SAMPLE)); c["permissions"]["send"] = {"level": "any"}; c["permissions"]["spend"] = {"level": "scoped", "scope": ["stripe"]}
    c["capabilities"].append({"id": "share.post", "summary": "post", "effects": ["send"]})
    c["capabilities"].append({"id": "buy.credits", "summary": "buy", "effects": ["spend"]})
    pol = POL("solo-dev"); pol["rules"].append({"effect": "send", "decision": "allow"})
    r = core.match_policy(c, pol); d = {x["capability"]: x["decision"] for x in r["capabilities"]}
    assert d["share.post"] == "ask" and d["buy.credits"] == "deny" and r["decision"] == "deny"

def test_policy_destructive_asks():
    c = C(SAMPLE); next(x for x in c["capabilities"] if x["id"] == "media.cut")["destructive"] = True
    assert {x["capability"]: x["decision"] for x in core.match_policy(c, POL("solo-dev"))["capabilities"]}["media.cut"] == "ask"

def test_policy_first_match_wins():
    pol = POL("solo-dev"); pol["rules"].insert(0, {"id": "no-ffmpeg", "effect": "exec", "scope": ["ffmpeg"], "decision": "deny"})
    r = core.match_policy(C(SAMPLE), pol)
    # contract scope [ffmpeg, ffprobe, python3] is not fully covered by ["ffmpeg"] -> rule doesn't match; next rule allows
    assert r["decision"] == "allow"
    pol["rules"][0]["scope"] = ["*"]; assert core.match_policy(C(SAMPLE), pol)["decision"] == "deny"

def test_policy_signature_required(skill, tmp_path):
    pol = POL("strict-ci"); assert core.match_policy(C(skill), pol)["decision"] == "deny"
    key = tmp_path / "k.pem"; pub = core.keygen(key); core.hash_files(skill); core.sign(skill, key)
    pol["trusted_keys"] = [pub]; assert core.match_policy(C(skill), pol)["decision"] == "allow"

def test_policy_skill_denylist_and_invalid_policy():
    pol = POL("solo-dev"); pol["skills"] = {"deny": ["ffmpeg-skill"]}
    assert core.match_policy(C(SAMPLE), pol)["decision"] == "deny"
    with pytest.raises(ValueError): core.match_policy(C(SAMPLE), {"policy_version": "0.1"})

def test_compile_targets():
    c, p = C(SAMPLE), POL("solo-dev")
    cc = core.compile_native(c, p, "claude-code"); assert "Bash(ffmpeg *)" in cc["permissions"]["allow"]
    assert "Shell(ffprobe)" in core.compile_native(c, p, "cursor")["permissions"]["allow"]
    cx = core.compile_native(c, p, "codex"); assert cx["sandbox_mode"] == "workspace-write" and cx["approval_policy"] == "never"
    assert core.compile_native(c, POL("strict-ci"), "gemini-cli")["rule"][0]["decision"] == "deny"  # unsigned -> deny
    assert core.compile_native(c, p, "gemini-cli")["rule"][0]["decision"] == "allow"

def test_cli_exit_codes(capsys):
    assert cli.main(["validate", str(SAMPLE)]) == 0
    assert cli.main(["policy-check", str(SAMPLE), str(ROOT / "policies/solo-dev.json")]) == 0
    assert cli.main(["policy-check", str(SAMPLE), str(ROOT / "policies/strict-ci.json")]) == 1


# ---- v0.2 ----
def test_conditional_effects_worst_case():
    r = core.match_policy(C(SAMPLE), POL("solo-dev"))
    cap = {x["capability"]: x for x in r["capabilities"]}["media.caption"]
    assert cap["decision"] == "allow" and cap["decision_worst_case"] == "ask" and r["decision_worst_case"] == "ask"
    pol = POL("solo-dev"); pol["rules"].append({"effect": "network", "scope": ["huggingface.co", "*.huggingface.co", "*.hf.co", "openaipublic.azureedge.net"], "decision": "allow"})
    pol["rules"].append({"effect": "exec", "scope": ["whisper*", "parakeet*", "python3", "ffmpeg", "ffprobe"], "decision": "allow"})
    assert core.match_policy(C(SAMPLE), pol)["decision_worst_case"] == "allow"

def test_effect_scope_cannot_widen(skill):
    c = C(skill); c["capabilities"][0]["effect_scopes"] = {"exec": ["bash"]}; W(skill, c)
    assert "SCOPE_WIDENED" in [f["code"] for f in core.validate(skill)["findings"]]

def test_unknown_feature_kind_and_missing_feature(skill):
    c = C(skill); c["capabilities"][0]["requires_features"] = ["gpu:cuda"]; W(skill, c)
    assert "UNKNOWN_FEATURE_KIND" in [f["code"] for f in core.validate(skill)["findings"]]
    c["capabilities"][0]["requires_features"] = ["filter:definitely_not_a_filter"]; W(skill, c)
    r = core.run_tests(skill, only=["probe-basic"]); assert r["error"] == "requirements not met"

def test_features_present():
    reqs = core.check_requirements(C(SAMPLE)); f = [x for x in reqs if x.get("kind") == "feature"]
    assert f and all(x["ok"] for x in f)

def test_skill_dependency_located(tmp_path):
    c = C(SAMPLE); c["requirements"]["skills"] = [{"name": "ffmpeg-skill", "env": "X_FFMPEG_DIR"}]
    env, res = core.locate_skills(c, tmp_path / "other", [str(ROOT.parent / "samples")])
    assert res[0]["ok"] and env["X_FFMPEG_DIR"].endswith("ffmpeg-skill")

def test_alternative_binary(skill):
    c = C(skill); c["requirements"]["binaries"].append({"name": "not-here-bin", "alternatives": ["python3"]}); W(skill, c)
    assert all(r["ok"] for r in core.check_requirements(c))

def test_stderr_and_skip(skill):
    c = C(skill); c["tests"]["cases"] = [
        {"id": "e", "run": ["python3", "-c", "import sys;sys.stderr.write('boom')"], "expect": {"exit_code": 0, "stderr_contains": "boom"}},
        {"id": "s", "run": ["false"], "skip_unless_env": ["SURELY_UNSET_VAR_X"], "expect": {"exit_code": 0}},
        {"id": "env", "run": ["python3", "-c", "import os;assert os.environ['FOO']=='bar'"], "env": {"FOO": "bar"}, "expect": {"exit_code": 0}}]; W(skill, c)
    r = core.run_tests(skill); assert r["ok"] and r["skipped"] == 1

def test_init_heuristic_and_native(tmp_path):
    from skillpact import init
    d = tmp_path / "demo-skill"; (d / "scripts").mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: demo-skill\ndescription: Uploads files to the cloud API and posts to Slack.\n---\nRun ffmpeg.\n")
    (d / "scripts" / "run.py").write_text("import argparse;argparse.ArgumentParser().parse_args()\n")
    c = init.draft(d)
    assert c["permissions"]["network"]["level"] == "scoped" and c["permissions"]["send"]["level"] == "scoped"
    assert "/permissions/send" in c["x"]["init"]["uncertain"] and any(b["name"] == "ffmpeg" for b in c["requirements"]["binaries"])
    (d / "skill.contract.json").write_text(json.dumps(c)); assert core.validate(d)["ok"]
    i = tmp_path / "doc-skill"; i.mkdir(); (i / "SKILL.md").write_text("---\nname: doc-skill\ndescription: Writing guidance only.\n---\nBe concise.\n")
    c2 = init.draft(i); assert c2["kind"] == "instructions" and all(v["level"] == "none" for v in c2["permissions"].values())
    n = init.draft(SAMPLE); assert len(n["capabilities"]) == 42 and n["x"]["init"]["source"] == "native"

@pytest.mark.parametrize("target", ["claude-code", "cursor", "codex", "gemini-cli"])
@pytest.mark.parametrize("pol", ["solo-dev", "strict-ci"])
def test_compiled_configs_validate_against_harness_schemas(target, pol):
    from skillpact import harness
    cfg = core.compile_native(C(SAMPLE), POL(pol), target, "ffmpeg-skill")
    fn, text = harness.render(target, cfg); assert harness.validate_native(target, text) == []

def test_harness_schema_catches_bad_config():
    from skillpact import harness
    assert harness.validate_native("claude-code", json.dumps({"permissions": {"allow": ["Shellz(rm)"]}}))
    assert harness.validate_native("codex", 'sandbox_mode = "yolo"\n')
    assert harness.validate_native("gemini-cli", '[[rule]]\ntoolName = "x"\ndecision = "maybe"\n')
    assert harness.validate_native("cursor", json.dumps({"version": 1, "permissions": {"allow": ["Bash(ls)"], "deny": []}}))

def test_export_hushspec_strict_fields():
    import yaml
    from skillpact import export
    d = yaml.safe_load(export.export(C(SAMPLE), POL("solo-dev"), "hushspec"))
    assert set(d) <= {"hushspec", "name", "description", "extends", "merge_strategy", "rules", "extensions", "metadata"}
    assert isinstance(d["hushspec"], str) and d["rules"]["tool_access"]["default"] == "block" and "cut" in d["rules"]["tool_access"]["allow"]
    assert set(d["rules"]["tool_access"]) <= {"enabled", "when", "allow", "block", "require_confirmation", "default", "max_args_size"}
    assert set(d["rules"]["egress"]) <= {"enabled", "when", "allow", "block", "default"}

def test_export_rego_evaluates_with_opa(tmp_path):
    from skillpact import export
    opa = ROOT.parent / ".tools" / "opa"
    if not opa.exists(): pytest.skip("opa binary not available")
    f = tmp_path / "p.rego"; f.write_text(export.export(C(SAMPLE), POL("solo-dev"), "rego"))
    def ev(t): return subprocess.run([str(opa), "eval", "-d", str(f), "-I", "data.skillpact.ffmpeg_skill.decision", "-f", "raw"], input=json.dumps({"tool_name": t}), capture_output=True, text=True).stdout.strip()
    assert ev("cut") == "allow" and ev("unknown_tool") == "deny"

def test_other_samples_validate():
    for f in sorted((ROOT.parent / "samples" / "others").glob("*.contract.json")):
        repo = ROOT.parent / "repos" / f.name.replace(".contract.json", "")
        if not repo.exists(): continue
        r = core.validate(repo, f)
        errs = [x["code"] for x in r["findings"] if x["level"] == "error"]
        assert errs in ([], ["FM_DESCRIPTION"]), (f.name, errs)  # github-solo: real finding, description > 1024


# ---------------- v0.3 ----------------
from skillpact import interop, owasp, sigstore_sig

def test_schema_ids_canonical():
    for f in ("schema.json", "policy_schema.json"):
        assert json.loads((ROOT / "skillpact" / f).read_text())["$id"].startswith("https://seventh-well.com/skillpact/schema/")

def test_to_mda_and_lossy():
    c = C(SAMPLE); out = interop.to_mda(c, SAMPLE / "skill.contract.json"); r = out["metadata"]["mda"]["requires"]
    assert r["tools"] == ["Read", "Write", "Bash", "WebFetch"] and r["network"] == c["permissions"]["network"]["scope"]
    assert "ffmpeg" in r["packages"] and any(x.startswith("python3>=") for x in r["runtime"])
    assert len(out["metadata"]["skillpact"]["sha256"]) == 64 and any("tests" in x for x in out["lossy"])

def test_mda_roundtrip_keeps_effect_classes():
    c = C(SAMPLE); back = interop.from_mda({"metadata": interop.to_mda(c)["metadata"], "name": "ffmpeg-skill"})
    assert core_valid(back)
    for e in ("read", "write", "exec"): assert back["permissions"][e]["level"] == "any"
    assert back["permissions"]["network"] == {"level": "scoped", "scope": c["permissions"]["network"]["scope"]}
    assert back["permissions"]["spend"]["level"] == "none" and back["x"]["import"]["uncertain"]

def test_from_mda_variants():
    c = interop.from_mda({"tools": ["Read", "Bash(jq:*)", "Mystery"], "network": "local", "cost-hints": {"paid-apis": ["openai"]}, "model": {"vision": True}})
    assert c["permissions"]["exec"]["level"] == "any" and c["permissions"]["network"]["level"] == "scoped"
    assert c["permissions"]["spend"]["scope"] == ["openai"] and c["x"]["mda"] == {"model": {"vision": True}}
    assert any("Mystery" in u for u in c["x"]["import"]["uncertain"]); assert core_valid(c)

def test_autovault_roundtrip():
    c = C(SAMPLE); fm = interop.to_autovault(c)["frontmatter"]
    assert fm["capabilities"] == {"network": True, "filesystem": "readwrite", "tools": ["fs.read", "fs.write", "proc.exec", "http.fetch"]}
    back = interop.from_autovault(fm | {"name": "ffmpeg-skill", "version": "2.10.7", "requires-secrets": [{"name": "X", "description": "d"}]})
    assert {e for e, p in back["permissions"].items() if p["level"] != "none"} == {"read", "write", "exec", "network"}
    assert back["requirements"]["env"][0]["name"] == "X" and core_valid(back)

def test_convert_cli_from_skill_md(tmp_path):
    d = tmp_path / "s"; d.mkdir()
    (d / "SKILL.md").write_text("---\nname: pdf\ndescription: x\nmetadata:\n  mda:\n    requires:\n      tools: [Read]\n      network: none\n---\nbody\n")
    assert cli.main(["convert", str(d), "--from", "mda", "-o", str(d / "skill.contract.json")]) == 0
    c = C(d); assert c["skill"]["name"] == "pdf" and c["permissions"]["read"]["level"] == "any" and c["permissions"]["network"]["level"] == "none"

def core_valid(c):
    import jsonschema
    jsonschema.validate(c, json.loads((ROOT / "skillpact" / "schema.json").read_text())); return True

def _mock_signer_verifier():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    import base64
    k = Ed25519PrivateKey.generate()
    signer = lambda payload: ("kajisho5@users.noreply.github.com", "https://github.com/login/oauth", {"mediaType": "mock", "sig": base64.b64encode(k.sign(payload)).decode()})
    def verifier(payload, entry):
        try: k.public_key().verify(base64.b64decode(entry["bundle"]["sig"]), payload); return True
        except Exception: return False
    return signer, verifier

def test_sigstore_sign_verify_mocked(skill):
    """Keyless signing needs an OIDC token + Fulcio/Rekor; mocked here (no ambient token on the box)."""
    signer, verifier = _mock_signer_verifier()
    sigstore_sig.sign(skill, signer=signer)
    c = C(skill); assert core_valid(c)
    res = core.verify_signatures(c, sigstore_verifier=verifier)
    key = "sigstore:https://github.com/login/oauth|kajisho5@users.noreply.github.com"
    assert res[key] is True and all(res.values())
    c["skill"]["version"] = "9.9.9"; assert core.verify_signatures(c, sigstore_verifier=verifier)[key] is False
    pol = POL("strict-ci"); pol["trusted_keys"] = [key]; pol.setdefault("require_signature", True)

def test_sigstore_real_verifier_rejects_garbage():
    """Uses the real Sigstore trust root (TUF, network). Skipped if unreachable."""
    try:
        from sigstore.verify import Verifier; Verifier.production()
    except Exception as e: pytest.skip(f"sigstore trust root unavailable: {e}")
    entry = {"type": "sigstore", "identity": "a@b", "issuer": "https://x", "bundle": {"mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json"}}
    assert sigstore_sig.verify_entry({"a": 1}, entry) is False

def test_owasp_mapping_flagship():
    c = C(SAMPLE); rows = owasp.assess(c, {"ok": True}, core.verify_signatures(c))
    ids = [r["id"] for r in rows]; assert ids == [f"AST{i:02d}" for i in range(1, 11)]
    st = {r["id"]: r["status"] for r in rows}
    assert st["AST02"] == st["AST03"] == st["AST08"] == st["AST10"] == "addressed" and st["AST01"] == "partial"

def test_owasp_flags_unscoped():
    c = C(SAMPLE); c["permissions"]["exec"] = {"level": "any"}
    r = {x["id"]: x for x in owasp.assess(c, None, {})}
    assert r["AST03"]["status"] == "partial" and "exec" in r["AST03"]["gap"] and r["AST08"]["status"] == "partial"
