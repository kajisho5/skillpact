"""Review day-1 fixes: composition trust verifies files; multi-skill CLI arguments; broad exec allows are reported lossy."""
import json, os, shutil, sys
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skillpact import cli, compose, core

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "conformance" / "cases"
TPUB = "ed25519:h4z5ZqAU97RzV18w3J26PraX7BcDlTuQY+BUIXN99ag="   # conformance test key (published seed)
SOLO = json.loads((ROOT / "ref" / "policies" / "solo-dev.json").read_text())


def _cp(tmp_path, name="v08-valid-signed"):
    d = tmp_path / name; shutil.copytree(CASES / name, d); return d


def test_trusted_files_needs_matching_files(tmp_path):
    d = _cp(tmp_path); c = json.loads((d / "skill.contract.json").read_text())
    assert core.trusted_author(c, {TPUB}) and core.trusted_files(c, d, None, {TPUB})
    (d / "SKILL.md").write_text((d / "SKILL.md").read_text() + "\nchanged\n")   # contract signature still verifies, files do not
    assert core.trusted_author(c, {TPUB}) and not core.trusted_files(c, d, None, {TPUB})


def test_policy_set_does_not_trust_tampered_files(tmp_path, monkeypatch):
    seen = {}
    real = compose.compose
    monkeypatch.setattr(compose, "compose", lambda items, trusted=None: seen.setdefault("t", set(trusted or [])) and real(items, trusted) or real(items, trusted))
    d = _cp(tmp_path); c = json.loads((d / "skill.contract.json").read_text()); pol = {**SOLO, "trusted_keys": [TPUB]}
    compose.match_policy_set([(c, d, None)], pol); assert seen.pop("t") == {"v08-valid-signed"}
    (d / "SKILL.md").write_text((d / "SKILL.md").read_text() + "\nchanged\n")
    compose.match_policy_set([(c, d, None)], pol); assert seen.pop("t") == set()


def test_multi_skill_contract_option_is_refused(tmp_path, capsys):
    a, b = _cp(tmp_path / "a"), _cp(tmp_path / "b")
    pol = tmp_path / "p.json"; pol.write_text(json.dumps(SOLO))
    assert cli.main(["policy-check", str(a), str(b), str(pol), "--contract", str(a / "skill.contract.json")]) == 1
    assert "--contract" in json.loads(capsys.readouterr().out)["error"]


def test_multi_skill_mcp_server_pairs(tmp_path, capsys):
    a = _cp(tmp_path / "a"); b = _cp(tmp_path / "b", "v08-valid-signed")
    for d in (a, b):
        c = json.loads((d / "skill.contract.json").read_text()); c["capabilities"][0]["entry"]["mcp_tool"] = "hello"
        (d / "skill.contract.json").write_text(json.dumps(c))
    pol = tmp_path / "p.json"; pol.write_text(json.dumps(SOLO))
    assert cli.main(["policy-compile", str(a), str(b), str(pol), "--target", "claude-code", "--mcp-server", "bad"]) == 1; capsys.readouterr()
    cfg = compose.compile_set([(json.loads((d / "skill.contract.json").read_text()), d, None) for d in (a, b)], SOLO, "claude-code", {"v08-valid-signed": "srv"})
    assert any("mcp__srv__hello" in v for perms in cfg["configs"].values() for v in sum(perms["permissions"].values(), []))


def test_broad_exec_allow_is_lossy():
    c = json.loads((ROOT / "samples" / "thumbnail-skill" / "skill.contract.json").read_text())
    for t in ("claude-code", "cursor", "gemini-cli"):
        lossy = core.compile_native(c, SOLO, t)["lossy"]
        assert any(x.startswith("exec: allowing") and "python3 can run arbitrary code" in x for x in lossy), t
