"""Skill contract 0.1 reference: validate, hash, sign/verify, run declared tests, match against a harness policy."""
from __future__ import annotations
import base64, fnmatch, hashlib, json, os, re, shutil, subprocess, tempfile, time
from pathlib import Path
import yaml
from jsonschema import Draft202012Validator

HERE = Path(__file__).parent
SCHEMA = json.loads((HERE / "schema.json").read_text())
POLICY_SCHEMA = json.loads((HERE / "policy_schema.json").read_text())
EFFECTS = ["read", "write", "network", "exec", "spend", "send"]
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
CONTRACT_FILE = "skill.contract.json"


class Report:
    def __init__(self): self.items = []
    def err(self, code, msg, where=""): self.items.append({"level": "error", "code": code, "message": msg, "where": where})
    def warn(self, code, msg, where=""): self.items.append({"level": "warn", "code": code, "message": msg, "where": where})
    @property
    def ok(self): return not any(i["level"] == "error" for i in self.items)
    def to_dict(self): return {"ok": self.ok, "errors": sum(i["level"] == "error" for i in self.items), "warnings": sum(i["level"] == "warn" for i in self.items), "findings": self.items}


def read_frontmatter(skill_md: Path):
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m: return None, text
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def load_contract(skill_dir: Path, contract_path: Path | None = None):
    p = contract_path or (skill_dir / CONTRACT_FILE)
    return json.loads(Path(p).read_text(encoding="utf-8")), Path(p)


# ---------------- validate ----------------
def validate(skill_dir, contract_path=None) -> dict:
    skill_dir = Path(skill_dir).resolve(); r = Report()
    sm = skill_dir / "SKILL.md"
    fm = None
    if not sm.exists(): r.err("SKILL_MD_MISSING", "SKILL.md not found", str(sm))
    else:
        fm, body = read_frontmatter(sm)
        if fm is None: r.err("FRONTMATTER_MISSING", "SKILL.md has no YAML frontmatter", "SKILL.md")
        else:
            n, d = fm.get("name"), fm.get("description")
            if not isinstance(n, str) or not NAME_RE.match(n) or len(n) > 64: r.err("FM_NAME", f"invalid name {n!r} (agentskills.io rules)", "SKILL.md")
            elif n != skill_dir.name and not contract_path: r.warn("FM_NAME_DIR", f"name {n!r} != directory {skill_dir.name!r}", "SKILL.md")
            if not isinstance(d, str) or not (1 <= len(d) <= 1024): r.err("FM_DESCRIPTION", "description must be 1-1024 chars", "SKILL.md")
            if "compatibility" in fm and len(str(fm["compatibility"])) > 500: r.err("FM_COMPAT", "compatibility > 500 chars", "SKILL.md")
            if body.count("\n") > 500: r.warn("BODY_LONG", f"SKILL.md body has {body.count(chr(10))} lines (> 500 recommended max)", "SKILL.md")
    try: c, cpath = load_contract(skill_dir, Path(contract_path) if contract_path else None)
    except FileNotFoundError:
        r.err("CONTRACT_MISSING", f"{CONTRACT_FILE} not found"); return r.to_dict()
    except json.JSONDecodeError as e:
        r.err("CONTRACT_JSON", str(e)); return r.to_dict()
    for e in sorted(Draft202012Validator(SCHEMA).iter_errors(c), key=lambda e: list(e.path)):
        r.err("SCHEMA", e.message, "/" + "/".join(map(str, e.path)))
    if not r.ok: return r.to_dict()
    # cross checks
    if fm and fm.get("name") != c["skill"]["name"]: r.err("NAME_MISMATCH", f"contract skill.name {c['skill']['name']!r} != SKILL.md name {fm.get('name')!r}")
    perms = c["permissions"]
    for eff in ("spend", "send"):
        if perms[eff]["level"] == "any": r.warn("HIGH_RISK", f"{eff}: level 'any' — harnesses will usually ask or deny", f"/permissions/{eff}")
    reqnames = {b["name"] for b in c.get("requirements", {}).get("binaries", []) + c.get("requirements", {}).get("runtimes", [])}
    ids = set()
    for i, cap in enumerate(c["capabilities"]):
        w = f"/capabilities/{i}"
        if cap["id"] in ids: r.err("DUP_CAPABILITY", f"duplicate id {cap['id']}", w)
        ids.add(cap["id"])
        for eff in cap["effects"]:
            if perms[eff]["level"] == "none": r.err("UNDECLARED_EFFECT", f"capability {cap['id']} has effect {eff!r} but permissions.{eff}.level is 'none'", w)
        if cap.get("destructive") and "write" not in cap["effects"] and "send" not in cap["effects"] and "spend" not in cap["effects"]:
            r.warn("DESTRUCTIVE_NO_EFFECT", f"{cap['id']} is destructive but declares no write/send/spend", w)
        for k in ("inputs", "outputs"):
            if k in cap:
                try: Draft202012Validator.check_schema(cap[k])
                except Exception as e: r.err("BAD_SUBSCHEMA", f"{cap['id']}.{k}: {str(e).splitlines()[0]}", w)
        for q in cap.get("requires", []):
            if q not in reqnames: r.err("UNKNOWN_REQUIREMENT", f"{cap['id']} requires {q!r} not in requirements", w)
        cli = cap.get("entry", {}).get("cli")
        if cli:
            for tok in cli:
                if tok.startswith("$SKILL_DIR/") and not (skill_dir / tok[len("$SKILL_DIR/"):]).exists():
                    r.err("ENTRY_MISSING", f"{cap['id']}: {tok} does not exist", w)
    feature_kinds = {k for b in c.get("requirements", {}).get("binaries", []) for k in b.get("features_check", {})}
    for i, cap in enumerate(c["capabilities"]):
        for ce in cap.get("conditional_effects", []):
            if perms[ce["effect"]]["level"] == "none": r.err("UNDECLARED_EFFECT", f"{cap['id']}: conditional effect {ce['effect']!r} but permissions.{ce['effect']}.level is 'none'", f"/capabilities/{i}")
        for eff, sc in cap.get("effect_scopes", {}).items():
            outer = perms[eff].get("scope", [])
            if perms[eff]["level"] == "scoped" and not _covered(sc, outer): r.err("SCOPE_WIDENED", f"{cap['id']}: effect_scopes.{eff} not within permissions.{eff}.scope", f"/capabilities/{i}")
        for f in cap.get("requires_features", []):
            if f.split(":", 1)[0] not in feature_kinds: r.err("UNKNOWN_FEATURE_KIND", f"{cap['id']}: {f} has no features_check for its kind", f"/capabilities/{i}")
        if c.get("kind", "tool") == "tool" and not cap.get("entry", {}).get("cli") and not cap.get("entry", {}).get("mcp_tool") and cap["effects"]:
            r.warn("NO_ENTRY", f"{cap['id']} has effects but no cli/mcp entry", f"/capabilities/{i}")
    used = {eff for cap in c["capabilities"] for eff in cap["effects"] + [x["effect"] for x in cap.get("conditional_effects", [])]}
    for eff in EFFECTS:
        if perms[eff]["level"] != "none" and eff not in used: r.warn("UNUSED_PERMISSION", f"permissions.{eff} declared but no capability uses it", f"/permissions/{eff}")
    for t in c.get("tests", {}).get("cases", []):
        if t.get("capability") and t["capability"] not in ids: r.err("TEST_UNKNOWN_CAPABILITY", f"test {t['id']} refers to {t['capability']}")
    if not c.get("tests", {}).get("cases") and c.get("kind", "tool") == "tool": r.warn("NO_TESTS", "no conformance tests declared")
    tested = {t.get("capability") for t in c.get("tests", {}).get("cases", [])}
    untested = [x for x in ids if x not in tested]
    if c.get("tests", {}).get("cases") and untested: r.warn("UNTESTED_CAPABILITY", f"{len(untested)} capabilities have no test: {', '.join(sorted(untested)[:8])}")
    if "integrity" in c:
        for rel, h in c["integrity"].get("files", {}).items():
            f = skill_dir / rel
            if not f.exists(): r.err("INTEGRITY_MISSING", f"{rel} missing")
            elif sha256(f) != h: r.err("INTEGRITY_MISMATCH", f"{rel} hash differs")
        if c["integrity"].get("signatures"):
            res = verify_signatures(c)
            if not all(res.values()): r.err("SIGNATURE_INVALID", f"signature check failed: {res}")
    return r.to_dict()


# ---------------- integrity / signing ----------------
def sha256(p: Path) -> str: return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def hash_files(skill_dir, contract_path=None, include=("SKILL.md", "scripts/**", "references/**", "assets/**", "templates/**", "mcp/**")):
    skill_dir = Path(skill_dir).resolve(); c, cpath = load_contract(skill_dir, contract_path)
    files = {}
    for pat in include:
        # Path.glob("x/**") yields only directories before Python 3.13; use rglob for portability
        found = skill_dir.joinpath(pat[:-3]).rglob("*") if pat.endswith("/**") else skill_dir.glob(pat)
        for f in sorted(found):
            if f.is_file() and "__pycache__" not in f.parts: files[str(f.relative_to(skill_dir))] = sha256(f)
    c["integrity"] = {"algorithm": "sha256", "files": files, "signatures": []}
    cpath.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n")
    return len(files)


def _canonical(c):
    c2 = json.loads(json.dumps(c)); c2.get("integrity", {}).pop("signatures", None)
    return json.dumps(c2, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def keygen(path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization as s
    k = Ed25519PrivateKey.generate()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f: f.write(k.private_bytes(s.Encoding.PEM, s.PrivateFormat.PKCS8, s.NoEncryption()))
    pub = k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)
    return "ed25519:" + base64.b64encode(pub).decode()


def sign(skill_dir, key_path, signer="", contract_path=None):
    from cryptography.hazmat.primitives import serialization as s
    skill_dir = Path(skill_dir).resolve(); c, cpath = load_contract(skill_dir, contract_path)
    if "integrity" not in c: raise SystemExit("run `hash` first")
    k = s.load_pem_private_key(Path(key_path).read_bytes(), None)
    pub = "ed25519:" + base64.b64encode(k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)).decode()
    sig = base64.b64encode(k.sign(_canonical(c))).decode()
    c["integrity"].setdefault("signatures", []).append({"type": "ed25519", "key": pub, "sig": sig, "signer": signer})
    cpath.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n")
    return pub


def verify_signatures(c, sigstore_verifier=None, offline=False) -> dict:
    """{key-or-identity: bool}. ed25519 entries are keyed by public key, sigstore entries by 'sigstore:<issuer>|<identity>'."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    out = {}
    for s_ in c.get("integrity", {}).get("signatures", []):
        if s_.get("type") == "sigstore":
            from . import sigstore_sig
            out[f"sigstore:{s_.get('issuer')}|{s_.get('identity')}"] = sigstore_sig.verify_entry(c, s_, sigstore_verifier, offline)
            continue
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(s_["key"].split(":", 1)[1])).verify(base64.b64decode(s_["sig"]), _canonical(c))
            out[s_["key"]] = True
        except Exception: out[s_["key"]] = False
    return out


# ---------------- requirements & tests ----------------
def _ver_tuple(v): return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def _ver_ok(found, spec):
    m = re.match(r"^\s*(>=|>|==|<=|<)?\s*([\d.]+)", spec or "")
    if not m: return True
    op, want = m.group(1) or ">=", _ver_tuple(m.group(2))
    f = _ver_tuple(found)
    return {">=": f >= want, ">": f > want, "==": f[:len(want)] == want, "<=": f <= want, "<": f < want}[op]


def check_requirements(c) -> list:
    out = []
    for b in c.get("requirements", {}).get("binaries", []) + c.get("requirements", {}).get("runtimes", []):
        res = {"name": b["name"], "required": b.get("version"), "optional": b.get("optional", False)}
        cmd = b.get("check") or [b["name"], "--version"]
        alt = next((a for a in b.get("alternatives", []) if shutil.which(a)), None)
        if not shutil.which(cmd[0]) and alt: res.update(found=None, ok=True, via=alt)
        elif not shutil.which(cmd[0]): res.update(found=None, ok=b.get("optional", False), reason="not on PATH")
        else:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            text = p.stdout + p.stderr
            m = re.search(b.get("version_regex", r"(\d+\.\d+(?:\.\d+)?)"), text)
            v = m.group(1) if m else None
            res.update(found=v, ok=bool(v) and _ver_ok(v, b.get("version")) or (not b.get("version")))
        out.append(res)
    feats = sorted({f for cap in c["capabilities"] for f in cap.get("requires_features", [])})
    checks = {k: cmd for b in c.get("requirements", {}).get("binaries", []) for k, cmd in b.get("features_check", {}).items()}
    cache = {}
    for f in feats:
        kind, name = f.split(":", 1)
        if kind not in checks: out.append({"name": f, "ok": False, "reason": "no features_check"}); continue
        if kind not in cache:
            try: cache[kind] = subprocess.run(checks[kind], capture_output=True, text=True, timeout=30).stdout
            except FileNotFoundError: cache[kind] = ""
        out.append({"name": f, "ok": re.search(r"(^|\s)" + re.escape(name) + r"(\s|$)", cache[kind], re.M) is not None, "kind": "feature"})
    import importlib.util
    for pk in c.get("requirements", {}).get("packages", []):
        if pk["ecosystem"] == "pypi":
            ok = importlib.util.find_spec(pk.get("import") or pk["name"].replace("-", "_").lower()) is not None
            out.append({"name": f"pypi:{pk['name']}", "ok": ok or pk.get("optional", False), "found": ok, "kind": "package"})
    return out


def locate_skills(c, skill_dir: Path, search=()):
    env, res = {}, []
    roots = [Path(p) for p in search] + [skill_dir.parent, Path.home() / ".claude/skills", Path.home() / ".cursor/skills", Path.home() / ".codex/skills"]
    for sk in c.get("requirements", {}).get("skills", []):
        found = os.environ.get(sk.get("env", ""), "") or next((str(r / sk["name"]) for r in roots if (r / sk["name"] / "SKILL.md").exists()), "")
        res.append({"name": f"skill:{sk['name']}", "ok": bool(found) or sk.get("optional", False), "found": found or None, "kind": "skill"})
        if found and sk.get("env"): env[sk["env"]] = found
    return env, res


def _jpath(obj, path):
    cur = obj
    for part in [p for p in path.lstrip("$").split(".") if p]:
        m = re.match(r"^(\w+)\[(\d+)\]$", part)
        if m: cur = cur[m.group(1)][int(m.group(2))]
        elif isinstance(cur, list): cur = cur[int(part)]
        else: cur = cur[part]
    return cur


def _subst(tok, env): return tok.replace("$SKILL_DIR", env["SKILL_DIR"]).replace("$WORKDIR", env["WORKDIR"])


def _snapshot(d: Path):
    return {str(p.relative_to(d)): (p.stat().st_size, p.stat().st_mtime_ns) for p in d.rglob("*") if p.is_file() and "__pycache__" not in p.parts}


def run_tests(skill_dir, contract_path=None, only=None, sandbox_network=True, skills_path=()) -> dict:
    skill_dir = Path(skill_dir).resolve(); c, _ = load_contract(skill_dir, contract_path)
    skill_env, skill_reqs = locate_skills(c, skill_dir, skills_path)
    reqs = check_requirements(c) + skill_reqs
    if not all(r["ok"] for r in reqs):
        return {"ok": False, "requirements": reqs, "cases": [], "error": "requirements not met"}
    netbox = sandbox_network and shutil.which("unshare") and subprocess.run(["unshare", "-rn", "true"]).returncode == 0
    caps = {cap["id"]: cap for cap in c["capabilities"]}
    work = Path(tempfile.mkdtemp(prefix="skilltest-"))
    env = {**os.environ, **skill_env, "SKILL_DIR": str(skill_dir), "WORKDIR": str(work), "PYTHONDONTWRITEBYTECODE": "1"}
    results = []
    before = _snapshot(skill_dir)
    try:
        for cmd in c.get("tests", {}).get("setup", []):
            p = subprocess.run([_subst(t, env) for t in cmd], cwd=work, env=env, capture_output=True, text=True, timeout=300)
            if p.returncode != 0: return {"ok": False, "requirements": reqs, "cases": [], "error": f"setup failed: {p.stderr[-500:]}"}
        for t in c.get("tests", {}).get("cases", []):
            if only and t["id"] not in only: continue
            if any(not os.environ.get(v) for v in t.get("skip_unless_env", [])):
                results.append({"id": t["id"], "capability": t.get("capability"), "ok": True, "skipped": True, "failures": [], "seconds": 0, "network_sandboxed": False, "stderr_tail": ""}); continue
            cmd = [_subst(x, env) for x in t["run"]]
            cenv = {**env, **{k: _subst(v, env) for k, v in t.get("env", {}).items()}}
            if netbox and not t.get("network"): cmd = ["unshare", "-rn"] + cmd
            t0 = time.time(); fails = []
            try:
                p = subprocess.run(cmd, cwd=work, env=cenv, capture_output=True, text=True, timeout=t.get("timeout_s", 120) * float(os.environ.get("SKILLPACT_TIMEOUT_SCALE", "1")))
                code, out, errout = p.returncode, p.stdout, p.stderr
            except subprocess.TimeoutExpired:
                code, out, errout = None, "", "timeout"; fails.append("timeout")
            ex = t["expect"]
            if code is not None and code != ex.get("exit_code", 0): fails.append(f"exit_code {code} != {ex.get('exit_code', 0)}")
            if "stdout_contains" in ex and ex["stdout_contains"] not in out: fails.append("stdout_contains not found")
            if "stderr_contains" in ex and ex["stderr_contains"] not in errout: fails.append("stderr_contains not found")
            if ex.get("validate_outputs") and t.get("capability") in caps and "outputs" in caps[t["capability"]]:
                ex = {**ex, "stdout_json_schema": {"allOf": [caps[t["capability"]]["outputs"], ex.get("stdout_json_schema", {})]}}
            if "stdout_json_schema" in ex or "stdout_json" in ex:
                try:
                    if ex.get("stdout_json_mode") == "last":
                        data, dec_ = None, json.JSONDecoder()
                        for mm in re.finditer(r"(?m)^[{\[]", out):
                            try: data = dec_.raw_decode(out, mm.start())[0]
                            except json.JSONDecodeError: pass
                        if data is None: raise json.JSONDecodeError("no JSON value", out, 0)
                    else: data = json.loads(out)
                    for e in Draft202012Validator(ex.get("stdout_json_schema", {})).iter_errors(data): fails.append(f"stdout schema: {e.message}")
                    for chk in ex.get("stdout_json", []):
                        try:
                            v = _jpath(data, chk["path"])
                            if "equals" in chk and v != chk["equals"]: fails.append(f"{chk['path']} = {v!r} != {chk['equals']!r}")
                            if "min" in chk and not v >= chk["min"]: fails.append(f"{chk['path']} = {v} < {chk['min']}")
                            if "max" in chk and not v <= chk["max"]: fails.append(f"{chk['path']} = {v} > {chk['max']}")
                        except (KeyError, IndexError, TypeError, ValueError):
                            if chk.get("exists", True): fails.append(f"{chk['path']} missing")
                except json.JSONDecodeError: fails.append("stdout is not JSON")
            for f in ex.get("files", []):
                fp = Path(_subst(f["path"], env)); fp = fp if fp.is_absolute() else work / fp
                if f.get("exists", True) and not fp.exists(): fails.append(f"file missing: {f['path']}")
                elif not f.get("exists", True) and fp.exists(): fails.append(f"file should not exist: {f['path']}")
                elif fp.exists() and fp.stat().st_size < f.get("min_bytes", 0): fails.append(f"file too small: {f['path']}")
            results.append({"id": t["id"], "capability": t.get("capability"), "ok": not fails, "failures": fails,
                            "seconds": round(time.time() - t0, 2), "network_sandboxed": bool(netbox and not t.get("network")),
                            "stderr_tail": errout[-300:] if fails else ""})
    finally:
        after = _snapshot(skill_dir)
        shutil.rmtree(work, ignore_errors=True)
    wrote = sorted(k for k in after if after[k] != before.get(k))
    scope = c["permissions"]["write"].get("scope", [])
    skill_dir_writes_allowed = any(s_.startswith("$SKILL_DIR") for s_ in scope)
    violations = [] if skill_dir_writes_allowed else wrote
    return {"ok": all(r["ok"] for r in results) and not violations, "requirements": reqs, "cases": results,
            "skill_dir_writes": violations, "passed": sum(r["ok"] and not r.get("skipped") for r in results), "skipped": sum(bool(r.get("skipped")) for r in results), "total": len(results)}


# ---------------- harness policy matching ----------------
ORDER = {"allow": 0, "ask": 1, "deny": 2}


def _covered(scope, patterns):
    return bool(scope) and all(any(fnmatch.fnmatchcase(s_, p) for p in patterns) for s_ in scope)


def match_policy(contract, policy) -> dict:
    errs = list(Draft202012Validator(POLICY_SCHEMA).iter_errors(policy))
    if errs: raise ValueError("invalid policy: " + "; ".join(e.message for e in errs[:3]))
    name = contract["skill"]["name"]
    sk = policy.get("skills", {})
    def out(decision, reason, caps=None):
        return {"skill": name, "decision": decision, "reason": reason, "capabilities": caps or []}
    if name in sk.get("deny", []): return out("deny", "skill is on the deny list")
    if policy.get("require_signature"):
        trusted = set(policy.get("trusted_keys", []))
        res = verify_signatures(contract)
        if not any(ok and k in trusted for k, ok in res.items()): return out("deny", "policy requires a valid signature from a trusted key")
    perms = contract["permissions"]
    caps = []
    for cap in contract["capabilities"]:
        per = []
        for eff in cap["effects"]:
            pe = perms[eff]; d = policy["defaults"][eff]; why = f"default for {eff}"
            if eff in cap.get("effect_scopes", {}): pe = {**pe, "scope": cap["effect_scopes"][eff]}
            for rule in policy.get("rules", []):          # first matching rule wins
                if rule["effect"] != eff: continue
                pats = rule.get("scope", ["*"])
                if (pe["level"] == "scoped" and _covered(pe.get("scope", []), pats)) or (pe["level"] == "any" and pats == ["*"]):
                    d, why = rule["decision"], f"rule {rule.get('id', eff)}"; break
            if pe["level"] == "any" and d == "allow" and eff in policy.get("never_auto_allow_any", ["spend", "send"]):
                d, why = "ask", f"{eff} with level 'any' is never auto-allowed"
            if pe.get("confirm") == "each" and d == "allow": d, why = "ask", f"skill requests confirmation for {eff}"
            per.append({"effect": eff, "decision": d, "why": why})
        cond = []
        for ce in cap.get("conditional_effects", []):
            sub = {"permissions": {**perms, ce["effect"]: {**perms[ce["effect"]], **({"scope": ce["scope"]} if ce.get("scope") else {})}}, "skill": contract["skill"],
                   "capabilities": [{"id": cap["id"], "summary": "", "effects": [ce["effect"]]}]}
            d2 = match_policy(sub, {**policy, "skills": {}, "require_signature": False})["capabilities"][0]["decision"]
            cond.append({"effect": ce["effect"], "when": ce["when"], "decision": d2})
        dec = max((p["decision"] for p in per), key=ORDER.get, default="allow")
        if cap.get("destructive") and dec == "allow" and policy.get("ask_on_destructive", True): dec = "ask"; per.append({"effect": "destructive", "decision": "ask", "why": "destructive capability"})
        worst = max([dec] + [x["decision"] for x in cond], key=ORDER.get)
        caps.append({"capability": cap["id"], "decision": dec, "decision_worst_case": worst, "effects": per, "conditional": cond})
    overall = max((c_["decision"] for c_ in caps), key=ORDER.get, default="allow")
    if name in sk.get("allow", []) and overall == "ask" and policy.get("allowlist_overrides_ask", False): overall = "allow"
    res = out(overall, "most restrictive capability decision", caps)
    res["decision_worst_case"] = max([overall] + [c_["decision_worst_case"] for c_ in caps], key=ORDER.get)
    return res


# ---------------- compile to native harness configs (best effort) ----------------
def compile_native(contract, policy, target, mcp_server=None) -> dict:
    """Translate the allow/ask/deny result for one skill into a harness's native config fragment."""
    m = match_policy(contract, policy)
    perms = contract["permissions"]
    cmds = perms["exec"].get("scope", []) if perms["exec"]["level"] == "scoped" else []
    hosts = perms["network"].get("scope", []) if perms["network"]["level"] == "scoped" else []
    dec = {e["effect"]: e["decision"] for c in m["capabilities"] for e in c["effects"]}
    bucket = lambda eff: "deny" if not m["capabilities"] and m["decision"] == "deny" else dec.get(eff, "allow")
    sb = policy.get("sandbox", {})
    if target == "claude-code":
        out = {"permissions": {"allow": [], "ask": [], "deny": []}}
        for c in cmds: out["permissions"][bucket("exec")].append(f"Bash({c} *)")
        for h in hosts: out["permissions"][bucket("network")].append(f"WebFetch(domain:{h})")
        if bucket("write") != "allow": out["permissions"]["ask" if bucket("write") == "ask" else "deny"].append("Write")
        if mcp_server:
            by = {x["capability"]: x["decision"] for x in m["capabilities"]}
            for cap in contract["capabilities"]:
                t = cap.get("entry", {}).get("mcp_tool")
                if t: out["permissions"][by.get(cap["id"], "deny")].append(f"mcp__{mcp_server}__{t}")
        return {"permissions": {k: sorted(set(v)) for k, v in out["permissions"].items()}}
    if target == "cursor":
        out = {"version": 1, "editor": {"vimMode": False}, "permissions": {"allow": [], "deny": []}}  # no 'ask' list: omission => prompt
        for c in cmds:
            if bucket("exec") in ("allow", "deny"): out["permissions"][bucket("exec")].append(f"Shell({c})")
        for h in hosts:
            if bucket("network") in ("allow", "deny"): out["permissions"][bucket("network")].append(f"WebFetch({h})")
        if mcp_server:
            by = {x["capability"]: x["decision"] for x in m["capabilities"]}
            for cap in contract["capabilities"]:
                t = cap.get("entry", {}).get("mcp_tool"); d = by.get(cap["id"], "deny")
                if t and d in ("allow", "deny"): out["permissions"][d].append(f"Mcp({mcp_server}:{t})")
        return out
    if target == "codex":
        fs = {"read-only": "read-only", "workdir": "workspace-write", "repo": "workspace-write", "any": "danger-full-access"}.get(sb.get("filesystem", "workdir"))
        ask = any(c["decision"] == "ask" for c in m["capabilities"])
        return {"approval_policy": "on-request" if ask else "never", "sandbox_mode": fs,
                "sandbox_workspace_write": {"network_access": sb.get("network", "off") != "off"}}
    if target == "gemini-cli":
        g = {"allow": "allow", "ask": "ask_user", "deny": "deny"}
        rules = [{"toolName": "run_shell_command", "commandPrefix": c, "decision": g[bucket("exec")], "priority": 100} for c in cmds]
        if mcp_server:
            by = {x["capability"]: x["decision"] for x in m["capabilities"]}
            rules += [{"toolName": cap["entry"]["mcp_tool"], "mcpName": mcp_server, "decision": g[by.get(cap["id"], "deny")], "priority": 100}
                      for cap in contract["capabilities"] if cap.get("entry", {}).get("mcp_tool")]
        return {"rule": rules}
    raise ValueError(f"unknown target {target}")


# ---------------- MCP mapping ----------------
def mcp_annotations(cap) -> dict:
    """Derived MCP tool annotations (spec section 'MCP mapping'); capability.mcp_annotations overrides."""
    effs = set(cap["effects"]) | {x["effect"] for x in cap.get("conditional_effects", [])}
    a = {"readOnlyHint": not (effs & {"write", "send", "spend"}), "destructiveHint": bool(cap.get("destructive", False)),
         "idempotentHint": bool(cap.get("idempotent", False)), "openWorldHint": bool(effs & {"network", "send", "spend"})}
    a.update(cap.get("mcp_annotations", {}))
    return a


def mcp_list_tools(cmd, env=None, timeout=30):
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "skillpact", "version": "0.3"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"}, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
    p = subprocess.run(cmd, input="".join(json.dumps(m) + "\n" for m in msgs), capture_output=True, text=True, timeout=timeout, env={**os.environ, **(env or {})})
    for line in p.stdout.splitlines():
        try: m = json.loads(line)
        except json.JSONDecodeError: continue
        if m.get("id") == 2: return m["result"]["tools"]
    raise RuntimeError("no tools/list response: " + p.stderr[-300:])


def mcp_check(skill_dir, server_cmd, env=None, contract_path=None) -> dict:
    """Compare a live MCP server's tools/list with the contract: names, input properties, annotations."""
    skill_dir = Path(skill_dir).resolve(); c, _ = load_contract(skill_dir, contract_path)
    tools = {t["name"]: t for t in mcp_list_tools([_subst(x, {"SKILL_DIR": str(skill_dir), "WORKDIR": str(skill_dir)}) for x in server_cmd], env)}
    rows, problems = [], []
    for cap in c["capabilities"]:
        name = cap.get("entry", {}).get("mcp_tool")
        if not name: continue
        t = tools.get(name)
        if not t: problems.append(f"{cap['id']}: MCP tool {name!r} not served"); continue
        want = {k for k, v in cap.get("inputs", {}).get("properties", {}).items() if not v.get("x-cli-only")}; got = set(t.get("inputSchema", {}).get("properties", {}))
        missing, extra = sorted(want - got), sorted(got - want)
        if missing: problems.append(f"{name}: contract inputs not in inputSchema: {missing[:5]}")
        derived = mcp_annotations(cap); served = t.get("annotations") or {}
        diff = {k: (served.get(k), v) for k, v in derived.items() if k in served and served[k] != v}
        if diff: problems.append(f"{name}: annotations differ (served, contract): {diff}")
        rows.append({"tool": name, "capability": cap["id"], "inputs_missing": missing, "inputs_extra": extra,
                     "annotations_served": bool(served), "annotations_contract": derived})
    unmapped = sorted(set(tools) - {cap.get("entry", {}).get("mcp_tool") for cap in c["capabilities"]})
    if unmapped: problems.append(f"served tools with no capability: {unmapped}")
    return {"ok": not problems, "tools_served": len(tools), "tools_mapped": len(rows), "problems": problems,
            "annotations_missing_on_server": sum(not r["annotations_served"] for r in rows), "tools": rows}
