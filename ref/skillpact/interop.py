"""Bidirectional conversion between SkillPact contracts and
- MDA Open Spec v1.0 `metadata.mda.requires` (spec/v1.0/10-capabilities.md)
- AutoVault SKILL.md frontmatter `capabilities` / `tools_required` (autovault.dev/authoring)
- the OS capability contract of kajisho5/Velisa (`provides[]` of each media skill's `contract --json`)
All targets are coarser than SkillPact. Every export reports what it dropped (`lossy`) and embeds a pointer
(`metadata.skillpact` / `x-skillpact`) to the full contract plus its sha256, so a consumer that understands SkillPact
can recover the exact contract. Every import marks what it had to guess under x.import.uncertain."""
import copy, hashlib, json, re
from pathlib import Path
from .core import LATEST

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
    c = {"contract_version": LATEST, "kind": "tool", "skill": {"name": name, "version": version},
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
    return {"contract_version": LATEST, "kind": "tool",
            "skill": {"name": name or fm.get("name", "unnamed-skill"), "version": str(version or fm.get("version", "0.0.0")), **({"license": fm["license"]} if fm.get("license") else {})},
            "requirements": {"env": [{"name": s["name"], "required": bool(s.get("required", True)), "description": s.get("description", "")} for s in fm.get("requires-secrets", [])]},
            "permissions": perms,
            "capabilities": [{"id": "skill", "summary": fm.get("description", "whole skill"), "role": "execution", "effects": effects}],
            "x": {"import": {"source": "autovault", "uncertain": unc + ["capabilities: single whole-skill capability", "tests: none"]},
                  **({"autovault": {"transformations": fm["transformations"]}} if fm.get("transformations") else {})}}


# ---------------- OS capability contract ----------------
# kajisho5/Velisa registry/capability_contract.schema.json (vendored in os_schemas/, see FETCHED.txt): what each media skill's
# `contract --json` publishes for the OS capability registry. It says which capability ids a skill provides (`provides[]`:
# `id`, `lifecycle`, `tool_id`) and which other skills it depends on; it declares no side effects, scopes, tests or signatures.
# SkillPact capability = one entry point = one OS `tool_id`; one tool may provide several OS capability ids (qc-skill: 10 ids,
# all `qc/run`). The OS view lives in the contract under x.os (top level: the rest of the OS document; per capability:
# `tool_id` and its `provides` entries without `tool_id`), so OS -> SkillPact -> OS gives the same document back.
OS_LIFECYCLES = ("PROPOSED", "EXPERIMENTAL", "STABLE", "DEPRECATED", "RETIRED")
OS_SCHEMA = json.loads((Path(__file__).parent / "os_schemas" / "capability_contract.schema.json").read_text())
_SEMVER = re.compile(r"^\d+\.\d+\.\d+([-+][0-9A-Za-z.-]+)?$")


def os_identity(doc):
    """The OS skill id: flat `skill_id`, nested `skill.id`, then flat `id` (same order as Velisa registry/contract.py)."""
    if isinstance(doc.get("skill_id"), str) and doc["skill_id"]: return doc["skill_id"]
    s = doc.get("skill")
    if isinstance(s, dict) and isinstance(s.get("id"), str) and s["id"]: return s["id"]
    if isinstance(doc.get("id"), str) and doc["id"]: return doc["id"]
    raise ValueError("OS capability contract has none of skill_id, skill.id, or id")


def _os_version(doc):
    if isinstance(doc.get("version"), str): return doc["version"]
    s = doc.get("skill")
    return s.get("version") if isinstance(s, dict) and isinstance(s.get("version"), str) else None


def os_problems(doc):
    """Problems with an OS capability contract: its JSON Schema, plus Velisa registry/contract.py's provides[] checks."""
    from jsonschema import Draft202012Validator
    if not isinstance(doc, dict): return ["(root): not a JSON object"]
    out = [f"{'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in sorted(Draft202012Validator(OS_SCHEMA).iter_errors(doc), key=lambda e: list(e.path))
           if not (e.validator == "anyOf" and not e.path)]   # the identity anyOf, said plainly below
    try: os_identity(doc)
    except ValueError as e: out.insert(0, str(e))
    ids = [p.get("id") for p in doc.get("provides", []) if isinstance(p, dict)] if isinstance(doc.get("provides"), list) else []
    out += [f"provides: duplicate capability id {i!r}" for i in sorted({i for i in ids if ids.count(i) > 1}, key=str)]
    return out


def _cap_id(tool_id, sid=""):
    t = tool_id[len(sid) + 1:] if sid and tool_id.startswith(sid + "/") else tool_id
    s = re.sub(r"[^a-z0-9._]+", "-", t.lower().replace("/", ".").replace("_", "-"))
    s = re.sub(r"-*([._])-*", r"\1", s).strip("-._")
    return s or "tool"


def to_os(c, contract_path=None):
    """SkillPact contract -> OS capability contract. Capabilities with x.os give exactly their declared OS entries; others
    get one entry each (id = capability id, tool_id = <skill id>/<mcp tool or capability id>, lifecycle guessed)."""
    xo = (c.get("x") or {}).get("os") or {}; doc = copy.deepcopy(xo.get("document") or {}); guessed = []
    if not any(k in doc for k in ("skill_id", "id", "skill")): doc["skill_id"] = c["skill"]["name"]
    sid = os_identity(doc); v = _os_version(doc)
    if v is None and not (xo.get("document") is not None and c["skill"]["version"] == "0.0.0"): doc["version"] = c["skill"]["version"]   # 0.0.0 = import placeholder
    elif v is not None and _SEMVER.match(v) and v != c["skill"]["version"]:
        if isinstance(doc.get("version"), str): doc["version"] = c["skill"]["version"]
        else: doc["skill"]["version"] = c["skill"]["version"]
    provides, origin = [], []
    for cap in c.get("capabilities", []):
        co = (cap.get("x") or {}).get("os")
        if co:
            for e in co.get("provides", []): provides.append({**copy.deepcopy(e), "tool_id": co["tool_id"]}); origin.append(cap["id"])
            continue
        e = {"id": cap["id"], "lifecycle": "EXPERIMENTAL", "tool_id": f"{sid}/{(cap.get('entry') or {}).get('mcp_tool') or cap['id']}"}
        if "inputs" in cap: e["input_schema"] = copy.deepcopy(cap["inputs"])
        if "outputs" in cap: e["output_schema"] = copy.deepcopy(cap["outputs"])
        if "destructive" in cap: e["mutates_input"] = bool(cap["destructive"])
        provides.append(e); origin.append(cap["id"])
        guessed.append(f"provides[{cap['id']}]: no x.os; OS capability id = SkillPact capability id, lifecycle EXPERIMENTAL (SkillPact has no lifecycle)")
    if xo.get("order") and sorted(xo["order"]) == sorted(p["id"] for p in provides):
        pos = {i: n for n, i in enumerate(xo["order"])}; provides.sort(key=lambda p: pos[p["id"]])
    doc["provides"] = provides
    skills = c.get("requirements", {}).get("skills", [])
    if skills and "dependencies" not in doc:
        doc["dependencies"] = [{"skill_id": s["name"], "version_range": s["version"]} for s in skills if s.get("version") and not s.get("optional")]
        if not doc["dependencies"]: del doc["dependencies"]
    lossy = ["permissions (six effects and their scopes): the OS contract declares no side effects",
             "capabilities[].effects / effect_scopes / conditional_effects", "capabilities[].dry_run, idempotent, summary, entry",
             "requirements binaries / runtimes / packages / env (versions, checks, features)", "tests (conformance tests)",
             "integrity + signatures (the x-skillpact pointer keeps the sha256 of the contract)", "compat"]
    if any(s.get("optional") or not s.get("version") for s in skills): lossy.append("requirements.skills without version or optional (OS dependencies need a version_range)")
    if any((cap.get("entry") or {}).get("mcp_tool") not in (None, cap["id"]) and not (cap.get("x") or {}).get("os") for cap in c.get("capabilities", [])):
        lossy.append("capabilities[].id where entry.mcp_tool differs: tool_id uses the MCP tool name, an import names the capability after it")
    if any("destructive" in cap and not (cap.get("x") or {}).get("os") for cap in c.get("capabilities", [])):
        lossy.append("capabilities[].destructive -> provides[].mutates_input (destructive also covers deletes and sends, not only the input)")
    doc["x-skillpact"] = _pointer(c, contract_path)
    return {"document": doc, "lossy": lossy, "guessed": guessed, "schema_errors": os_problems(doc)}


def from_os(doc, name=None):
    """OS capability contract -> SkillPact draft. One capability per tool_id; effects and permissions are unknown (none) and
    listed under x.import.uncertain, so the result is an unconfirmed draft until a person declares them."""
    probs = os_problems(doc)
    if probs: raise ValueError("not a valid OS capability contract: " + "; ".join(probs[:5]))
    sid = os_identity(doc); v = _os_version(doc); unc = []
    rest = {k: copy.deepcopy(val) for k, val in doc.items() if k not in ("provides", "x-skillpact")}
    name = name or (doc["package"] if isinstance(doc.get("package"), str) and core_name_ok(doc["package"]) else None) or _cap_id(sid).replace(".", "-").replace("_", "-")
    if v is None or not _SEMVER.match(v): unc.append(f"skill.version: OS version {v!r} is not MAJOR.MINOR.PATCH, set to 0.0.0 (kept out of the OS document on export)"); version = "0.0.0"
    else: version = v
    caps, by_tool, order = [], {}, []
    for e in doc.get("provides", []):
        t = e["tool_id"]
        if t not in by_tool:
            cid = _cap_id(t, sid); n = 2
            while any(x["id"] == cid for x in caps): cid = f"{_cap_id(t, sid)}-{n}"; n += 1
            by_tool[t] = {"id": cid, "summary": "", "effects": [], "x": {"os": {"tool_id": t, "provides": []}}}; caps.append(by_tool[t])
        by_tool[t]["x"]["os"]["provides"].append({k: copy.deepcopy(val) for k, val in e.items() if k != "tool_id"}); order.append(e["id"])
    for cap in caps:
        ents = cap["x"]["os"]["provides"]; t = cap["x"]["os"]["tool_id"]
        cap["summary"] = f"TODO(import): OS tool {t}, provides {', '.join(x['id'] for x in ents)}"
        for k, sk in (("input_schema", "inputs"), ("output_schema", "outputs")):
            vals = [x.get(k) for x in ents]
            if vals[0] is not None and all(x == vals[0] for x in vals): cap[sk] = copy.deepcopy(vals[0])
        mi = {x.get("mutates_input") for x in ents} - {None}
        if len(mi) == 1: cap["destructive"] = mi.pop()
        unc.append(f"capabilities[{cap['id']}]: entry and effects unknown (the OS contract names the tool, not how to start it or what it touches)")
    if not caps:
        caps = [{"id": "skill", "summary": "TODO(import): the OS contract provides no capability", "effects": []}]
    deps = [{"name": d["skill_id"], "version": d["version_range"]} for d in doc.get("dependencies", [])]
    if deps: unc.append("requirements.skills: from OS dependencies; names are OS skill ids, check them against the skills' names")
    xo = {"document": rest}
    grouped = [p for cap in caps for p in (cap.get("x", {}).get("os", {}).get("provides") or [])]
    if [p["id"] for p in grouped] != order: xo["order"] = order
    return {"contract_version": LATEST, "kind": "tool", "skill": {"name": name, "version": version},
            "requirements": {"skills": deps} if deps else {},
            "permissions": {e: {"level": "none"} for e in ("read", "write", "network", "exec", "spend", "send")},
            "capabilities": caps,
            "x": {"os": xo, "import": {"source": "os-capability", "uncertain": unc + [
                "permissions: the OS contract declares no side effects; all six are none until declared by hand", "tests: none (add before claiming L2)"]}}}


def os_check(c, doc):
    """Does a SkillPact contract agree with the OS contract a skill publishes? Compares what both carry."""
    exp = to_os(c)["document"]; out = []
    if os_identity(exp) != os_identity(doc): out.append(f"skill id: contract gives {os_identity(exp)!r}, OS contract {os_identity(doc)!r}")
    if _os_version(doc) != _os_version(exp): out.append(f"version: contract {_os_version(exp)!r}, OS contract {_os_version(doc)!r}")
    a = {p["id"]: p for p in exp["provides"]}; b = {p.get("id"): p for p in doc.get("provides", []) if isinstance(p, dict)}
    out += [f"provides {i!r}: only in the SkillPact contract" for i in sorted(a.keys() - b.keys())]
    out += [f"provides {i!r}: only in the OS contract" for i in sorted(b.keys() - a.keys(), key=str)]
    for i in sorted(a.keys() & b.keys()):
        for k in sorted(set(a[i]) | set(b[i])):
            if a[i].get(k) != b[i].get(k): out.append(f"provides {i!r}.{k}: contract {a[i].get(k)!r}, OS contract {b[i].get(k)!r}")
    return out


def core_name_ok(n): return bool(re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", n)) and len(n) <= 64
