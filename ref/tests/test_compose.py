import json, pathlib
from skillpact import compose as co, core
ROOT = pathlib.Path(__file__).parents[2]
V = json.loads((ROOT / "conformance/vectors/compose.json").read_text())

def C(name, perms):
    return {"contract_version": "0.8", "skill": {"name": name, "version": "1.0.0"}, "permissions": perms,
            "capabilities": [{"id": "x", "summary": "s", "effects": [e for e, p in perms.items() if p["level"] != "none"]}]}

def test_vectors():
    for v in V["cases"]:
        r = co.compose([(n, C(n, p)) for n, p in v["skills"].items()], v.get("trusted"))
        assert sorted(p["id"] for p in r["paths"]) == v["expect"], v["id"]
        for pid, cross in v.get("cross_skill", {}).items():
            assert next(p for p in r["paths"] if p["id"] == pid)["cross_skill"] == cross, v["id"]
        for p in r["paths"]: assert p["fix"] and p["message"]

def test_policy_set_and_compile():
    a = C("reader", json.loads(json.dumps(V["cases"][0]["skills"]["a"])))
    b = C("poster", json.loads(json.dumps(V["cases"][0]["skills"]["b"])))
    pol = {"policy_version": "0.8", "defaults": {e: "allow" for e in core.EFFECTS}}
    assert co.match_policy_set([(a, None, None), (b, None, None)], pol)["decision"] == "allow"   # additive: no rule, no change
    assert core.match_policy(a, {**pol, "compositions": {"exfiltration": "deny"}})["decision"] == "allow"  # single-contract unchanged
    pol["compositions"] = {"exfiltration": "deny"}
    r = co.match_policy_set([(a, None, None), (b, None, None)], pol)
    assert r["decision"] == "deny" and r["compositions"][0]["path"] == "exfiltration"
    for t in ("claude-code", "cursor", "codex", "gemini-cli"):
        out = co.compile_set([(a, None, None), (b, None, None)], pol, t)
        assert any(x.startswith("composition exfiltration") for x in out["lossy"]), t
    cc = co.compile_set([(a, None, None), (b, None, None)], pol, "claude-code")["configs"]["poster"]
    assert "WebFetch(domain:api.example.com)" not in json.dumps(cc.get("permissions", {}).get("allow", []))
