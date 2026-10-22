"""Multi-skill composition (spec 0.8.x additive, s13.3): union of effects over an installed skill set and dangerous
combinations ("paths"). Cross-skill flows go through the agent's context, so per-skill isolation does not stop them."""
from __future__ import annotations
import re
from . import core

SENSITIVE = re.compile(r"(\.ssh|\.aws|\.gnupg|\.kube|\.netrc|\.npmrc|\.pypirc|\.docker/config|(^|/)\.env(\.|$|/)|secret|credential|token|password|keychain|\.pem$|\.key$|id_rsa|id_ed25519)", re.I)
BROAD = {"/**", "**", "~/**", "$HOME/**", "/*", "~/*"}
EPHEMERAL = ("$WORKDIR", "$OUTPUT", "$TMPDIR")
PATHS = {
    "exfiltration": {"severity": "high", "summary": "sensitive or broad read + outbound channel (non-@local network or send)",
                     "fix": "narrow read scopes to $INPUT/$WORKDIR, limit network to named hosts or @local, or do not install these skills together"},
    "persistence": {"severity": "medium", "summary": "write outside $WORKDIR/$OUTPUT + exec",
                    "fix": "limit write scopes to $WORKDIR/** or $OUTPUT, or narrow the exec scope"},
    "spend_untrusted": {"severity": "high", "summary": "spend in a set that contains an untrusted skill",
                        "fix": "require trusted author signatures for every skill in the set, or ask on every spend"},
}


def _effects(c):
    """(effect, level, scopes) including conditional effects (worst case)."""
    perms = c["permissions"]; out = []
    for e in core.EFFECTS:
        p = perms.get(e, {"level": "none"})
        if p["level"] != "none": out.append((e, p["level"], list(p.get("scope", []))))
    for cap in c.get("capabilities", []):
        for ce in cap.get("conditional_effects", []):
            p = perms.get(ce["effect"], {"level": "none"})
            out.append((ce["effect"], p["level"] if p["level"] != "none" else "scoped", list(ce.get("scope") or p.get("scope", []))))
    return out


def _roles(c):
    r = set()
    for e, lvl, sc in _effects(c):
        if e == "read" and (lvl == "any" or any(s in BROAD or SENSITIVE.search(s) for s in sc)): r.add("secret_read")
        if (e == "network" and (lvl == "any" or any(s != "@local" for s in sc))) or e == "send": r.add("egress")
        if e == "write" and (lvl == "any" or any(not s.startswith(EPHEMERAL) for s in sc)): r.add("durable_write")
        if e == "exec": r.add("exec")
        if e == "spend": r.add("spend")
    return r


NEEDS = {"exfiltration": ("secret_read", "egress"), "persistence": ("durable_write", "exec")}
ROLE_EFFECT = {"secret_read": ["read"], "egress": ["network", "send"], "durable_write": ["write"], "exec": ["exec"], "spend": ["spend"]}


def compose(items, trusted=None) -> dict:
    """items: [(name, contract)]. trusted: names of skills with a trusted author signature (None = none known)."""
    trusted = set(trusted or [])
    roles = {n: _roles(c) for n, c in items}
    union = {}
    for n, c in items:
        for e, lvl, sc in _effects(c):
            u = union.setdefault(e, {"level": "scoped", "scope": [], "from": []})
            if lvl == "any": u["level"] = "any"
            u["scope"] += [s for s in sc if s not in u["scope"]]
            if n not in u["from"]: u["from"].append(n)
    paths = []
    for pid, need in NEEDS.items():
        src = {r: [n for n in roles if r in roles[n]] for r in need}
        if all(src.values()):
            names = sorted({n for v in src.values() for n in v})
            paths.append(_path(pid, src, len(names) > 1 and not any(all(r in roles[n] for r in need) for n in names)))
    spenders = [n for n in roles if "spend" in roles[n]]
    untrusted = [n for n, _ in items if n not in trusted]
    if spenders and untrusted and len(items) > 1:
        paths.append(_path("spend_untrusted", {"spend": spenders, "untrusted": untrusted}, True))
    return {"skills": [n for n, _ in items], "union": union, "paths": paths}


def _path(pid, src, cross):
    d = PATHS[pid]
    who = "; ".join(f"{r}: {', '.join(v)}" for r, v in src.items())
    return {"id": pid, "severity": d["severity"], "cross_skill": cross, "sources": src,
            "message": f"{pid} path ({d['summary']}) formed by {who}." + (" The skills are isolated from each other, but the agent can pass data between them." if cross else ""),
            "fix": d["fix"]}


def contributing(path):
    """[(skill, effect)] that make up a path."""
    out = []
    for r, names in path["sources"].items():
        for n in names:
            for e in ROLE_EFFECT.get(r, []): out.append((n, e))
    return out


def match_policy_set(entries, policy) -> dict:
    """entries: [(contract, skill_dir, contract_path)]. Per-skill decisions are unchanged; policy.compositions adds
    set-level decisions (optional, additive)."""
    per = [core.match_policy(c, policy, d, cp) for c, d, cp in entries]
    trusted = {r["skill"] for r, (c, d, cp) in zip(per, entries) if c.get("integrity") and core.trusted_author(c, set(policy.get("trusted_keys", [])))}
    comp = compose([(c["skill"]["name"], c) for c, _, _ in entries], trusted)
    rules = policy.get("compositions", {})
    found = []
    for p in comp["paths"]:
        d = rules.get(p["id"])
        if d: found.append({"path": p["id"], "decision": d, "sources": p["sources"], "message": p["message"], "fix": p["fix"]})
    overall = max([r["decision"] for r in per] + [f["decision"] for f in found], key=core.ORDER.get, default="allow")
    return {"decision": overall, "skills": per, "compositions": found, "union": comp["union"], "paths": comp["paths"]}


def compile_set(entries, policy, target) -> dict:
    """Compile each skill; for a set path the policy marks deny/ask, contributing effects become at least ask."""
    res = match_policy_set(entries, policy)
    bump, lossy = {}, []
    for f in res["compositions"]:
        if f["decision"] == "allow": continue
        p = next(x for x in res["paths"] if x["id"] == f["path"])
        for n, e in contributing(p): bump.setdefault(n, set()).add(e)
        lossy.append(f"composition {f['path']} ({f['decision']}): {target} cannot express conditions across skills; contributing effects compiled as ask ({', '.join(sorted({n + ':' + e for n, e in contributing(p)}))})")
    out = {}
    for c, d, cp in entries:
        n = c["skill"]["name"]; pol = policy
        if n in bump:
            pol = {**policy, "defaults": {**policy["defaults"]}, "rules": []}
            for e in bump[n]: pol["defaults"][e] = max(policy["defaults"][e], "ask", key=core.ORDER.get)
            for r in policy.get("rules", []):
                pol["rules"].append({**r, "decision": "ask"} if r["effect"] in bump[n] and r["decision"] == "allow" else r)
        comp = core.compile_native(c, pol, target, None, d, cp)
        out[n] = comp["config"]; lossy += [f"{n}: {x}" for x in comp["lossy"]]
    return {"decision": res["decision"], "configs": out, "lossy": lossy, "compositions": res["compositions"]}
