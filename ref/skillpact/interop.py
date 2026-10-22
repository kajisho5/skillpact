"""Bidirectional conversion between SkillPact contracts and
- MDA Open Spec v1.0 `metadata.mda.requires` (spec/v1.0/10-capabilities.md)
- AutoVault SKILL.md frontmatter `capabilities` / `tools_required` (autovault.dev/authoring)
Both targets are coarser than SkillPact. Every export reports what it dropped (`lossy`) and embeds a pointer
(`metadata.skillpact` / `x-skillpact`) to the full contract plus its sha256, so a consumer that understands SkillPact
can recover the exact contract. Every import marks what it had to guess under x.import.uncertain."""
import hashlib, json, re
from pathlib import Path

CANON = "https://kajisho5.github.io/skillpact/"
_TOOL = {"read": "Read", "write": "Write", "exec": "Bash", "network": "WebFetch"}
_AV = {"read": "fs.read", "write": "fs.write", "exec": "proc.exec", "network": "http.fetch"}
_AV_REV = {"fs.read": "read", "fs.write": "write", "proc.exec": "exec", "shell.exec": "exec", "http.fetch": "network", "net.fetch": "network"}
_MDA_TOOL_REV = {"read": "read", "grep": "read", "glob": "read", "write": "write", "edit": "write", "multiedit": "write",
                 "bash": "exec", "webfetch": "network", "websearch": "network"}


def _effects_used(c):
    used = {e for cap in c.get("capabilities", []) for e in cap.get("effects", [])}
    used |= {e for e, p in c.get("permissions", {}).items() if p.get("level", "none") != "none"}
    return used


def _pointer(c, contract_path):
    p = {"contract": "skill.contract.json", "contract_version": c.get("contract_version"), "spec": CANON}
    if contract_path and Path(contract_path).exists(): p["sha256"] = hashlib.sha256(Path(contract_path).read_bytes()).hexdigest()
    return p


def _lossy_common(c):
    out = []
    perms = c.get("permissions", {})
    for e in ("read", "write", "exec"):
        if perms.get(e, {}).get("level") == "scoped": out.append(f"permissions.{e}.scope (path/command scopes)")
    for e in ("spend", "send"):
        if perms.get(e, {}).get("level", "none") != "none": out.append(f"permissions.{e} (no equivalent effect class)")
    if any(cap.get("conditional_effects") for cap in c.get("capabilities", [])): out.append("capabilities[].conditional_effects")
    out += ["capabilities[] per-tool effects (flattened to skill level)", "tests (conformance tests)",
            "requirements version checks / features_check", "dry_run, destructive, idempotent", "integrity + signatures"]
    return out


# ---------------- MDA ----------------
def to_mda(c, contract_path=None):
    used = _effects_used(c); perms = c.get("permissions", {}); req = c.get("requirements", {})
    r = {"tools": [_TOOL[e] for e in ("read", "write", "exec", "network") if e in used]}
    net = perms.get("network", {})
    lvl = net.get("level", "none") if "network" in used or net else "none"
    r["network"] = "none" if lvl == "none" else ("local" if lvl == "scoped" and net.get("scope") == ["@local"] else (list(net.get("scope", [])) if lvl == "scoped" and net.get("scope") else "public"))
    pk = [b["name"] for b in req.get("binaries", [])] + [p["name"] if isinstance(p, dict) else p for p in req.get("packages", [])]
    if pk: r["packages"] = pk
    rt = [f'{x["name"]}{x.get("version", "")}' for x in req.get("runtimes", []) if not x.get("optional")]
    if rt: r["runtime"] = rt
    if perms.get("spend", {}).get("level", "none") != "none":
        r["cost-hints"] = {"paid-apis": list(perms["spend"].get("scope", []))}
    lossy = _lossy_common(c)
    if "cost-hints" in r: lossy = [x for x in lossy if not x.startswith("permissions.spend")] + ["permissions.spend (only names kept, in cost-hints.paid-apis)"]
    return {"metadata": {"mda": {"requires": r}, "skillpact": _pointer(c, contract_path)}, "lossy": lossy}


def from_mda(frontmatter_or_requires, name="unnamed-skill", version="0.0.0"):
    fm = frontmatter_or_requires
    req = fm.get("metadata", {}).get("mda", {}).get("requires", fm) if isinstance(fm, dict) else {}
    if isinstance(fm, dict) and "name" in fm: name = fm["name"]
    unc, perms = [], {e: {"level": "none"} for e in ("read", "write", "network", "exec", "spend", "send")}
    for t in req.get("tools", []):
        e = _MDA_TOOL_REV.get(re.sub(r"\(.*", "", str(t)).strip().lower())
        if e is None: unc.append(f"tool {t!r}: unknown, not mapped"); continue
        if e != "network":
            perms[e] = {"level": "any", "why": f"imported from MDA tools: {t}"}
            unc.append(f"permissions.{e}: MDA has no scopes, imported as level=any")
    net = req.get("network")
    if isinstance(net, list): perms["network"] = {"level": "scoped", "scope": net}
    elif net in ("public", "local"):
        perms["network"] = {"level": "any" if net == "public" else "scoped", **({"scope": ["@local"]} if net == "local" else {})}
    elif net is None and any(_MDA_TOOL_REV.get(str(t).lower()) == "network" for t in req.get("tools", [])):
        perms["network"] = {"level": "any"}; unc.append("permissions.network: only implied by tools, imported as any")
    if (req.get("cost-hints") or {}).get("paid-apis"):
        perms["spend"] = {"level": "scoped", "scope": req["cost-hints"]["paid-apis"]}
        unc.append("permissions.spend: from advisory cost-hints.paid-apis")
    reqs = {"binaries": [{"name": p} for p in req.get("packages", [])], "runtimes": []}
    for r_ in req.get("runtime", []):
        m = re.match(r"([A-Za-z0-9_.-]+)(.*)", r_); reqs["runtimes"].append({"name": m.group(1), **({"version": m.group(2)} if m.group(2) else {})})
    effects = [e for e in ("read", "write", "network", "exec", "spend", "send") if perms[e]["level"] != "none"]
    extra = {k: v for k, v in req.items() if k not in ("tools", "network", "packages", "runtime", "cost-hints")}
    c = {"contract_version": "0.7", "kind": "tool", "skill": {"name": name, "version": version},
         "requirements": reqs, "permissions": perms,
         "capabilities": [{"id": "skill", "summary": "whole skill (MDA declares at skill level only)", "role": "execution", "effects": effects}],
         "x": {"import": {"source": "mda-1.0", "uncertain": unc + ["capabilities: single whole-skill capability; split per tool by hand", "tests: none (add before claiming L2)"]}}}
    if extra: c["x"]["mda"] = extra
    return c


# ---------------- AutoVault ----------------
def to_autovault(c, contract_path=None):
    used = _effects_used(c)
    tools = [_AV[e] for e in ("read", "write", "exec", "network") if e in used]
    fs = "readwrite" if "write" in used else "readonly"
    return {"frontmatter": {"tools_required": tools, "capabilities": {"network": "network" in used, "filesystem": fs, "tools": tools},
                            "x-skillpact": _pointer(c, contract_path)},
            "lossy": _lossy_common(c) + ["permissions.network.scope (AutoVault network is boolean)"] * ("network" in used)}


def from_autovault(fm, name=None, version=None):
    caps = fm.get("capabilities", {}) or {}; tools = list(dict.fromkeys((fm.get("tools_required") or []) + (caps.get("tools") or [])))
    perms = {e: {"level": "none"} for e in ("read", "write", "network", "exec", "spend", "send")}; unc = []
    if caps.get("filesystem") in ("readonly", "readwrite"): perms["read"] = {"level": "any"}
    if caps.get("filesystem") == "readwrite": perms["write"] = {"level": "any"}
    if caps.get("network"): perms["network"] = {"level": "any"}
    for t in tools:
        e = _AV_REV.get(t) or _AV_REV.get(t.split(".")[0] + ".exec" if t.split(".")[0] in ("proc", "shell") else "")
        if t.startswith("browser."): e = "network"
        if e is None: unc.append(f"tool {t!r}: not mapped"); continue
        if perms[e]["level"] == "none": perms[e] = {"level": "any"}
    for e in ("read", "write", "network", "exec"):
        if perms[e]["level"] == "any": unc.append(f"permissions.{e}: AutoVault has no scopes, imported as level=any")
    if fm.get("requires-secrets"): unc.append("requires-secrets: kept as requirements.env (required=true)")
    effects = [e for e in ("read", "write", "network", "exec", "spend", "send") if perms[e]["level"] != "none"]
    return {"contract_version": "0.7", "kind": "tool",
            "skill": {"name": name or fm.get("name", "unnamed-skill"), "version": str(version or fm.get("version", "0.0.0")), **({"license": fm["license"]} if fm.get("license") else {})},
            "requirements": {"env": [{"name": s["name"], "required": bool(s.get("required", True)), "description": s.get("description", "")} for s in fm.get("requires-secrets", [])]},
            "permissions": perms,
            "capabilities": [{"id": "skill", "summary": fm.get("description", "whole skill"), "role": "execution", "effects": effects}],
            "x": {"import": {"source": "autovault", "uncertain": unc + ["capabilities: single whole-skill capability", "tests: none"]},
                  **({"autovault": {"transformations": fm["transformations"]}} if fm.get("transformations") else {})}}
