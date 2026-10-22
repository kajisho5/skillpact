"""SkillPact reference implementation (spec 0.8): validate, hash, sign/verify, run declared tests, match against a harness policy."""
from __future__ import annotations
import base64, ipaddress, hashlib, json, math, os, re, shutil, subprocess, tempfile, time
from pathlib import Path
import yaml
from jsonschema import Draft202012Validator

HERE = Path(__file__).parent
SCHEMA = json.loads((HERE / "schema.json").read_text())
POLICY_SCHEMA = json.loads((HERE / "policy_schema.json").read_text())
EFFECTS = ["read", "write", "network", "exec", "spend", "send"]
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
CONTRACT_FILE = "skill.contract.json"
KNOWN_VERSIONS = ["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8"]
PATH_VARS = {"$INPUT", "$INPUT_DIR", "$OUTPUT", "$WORKDIR", "$SKILL_DIR", "$TMPDIR"}
JCS_FROM = (0, 4)
SCOPE_TOKENS = {"network": ("@local",)}  # @local = loopback + private networks (spec 0.7)
# @local expanded to host patterns with label semantics (spec 0.8 s6.2): '*' never crosses a dot.
LOCAL_HOSTS = ["localhost", "127.*.*.*", "::1", "10.*.*.*"] + [f"172.{n}.*.*" for n in range(16, 32)] + ["192.168.*.*", "169.254.*.*"]
_V4 = re.compile(r"(0|[1-9][0-9]{0,2})(\.(0|[1-9][0-9]{0,2})){3}")


def is_local_host(h: str) -> bool:
    """0.8.x erratum: @local = 'localhost' or an IP literal in 127/8, 10/8, 172.16/12, 192.168/16, 169.254/16, ::1, fe80::/10, fc00::/7.
    DNS names never match. IPv6 may be bracketed; zone ids and embedded IPv4 are rejected."""
    h = h.lower()
    if h == "localhost": return True
    if h.startswith("[") and h.endswith("]"): h = h[1:-1]
    if _V4.fullmatch(h):
        o = [int(x) for x in h.split(".")]
        if max(o) > 255: return False
        return o[0] in (127, 10) or (o[0] == 172 and 16 <= o[1] <= 31) or o[:2] in ([192, 168], [169, 254])
    if ":" not in h or "." in h or "%" in h or not re.fullmatch(r"[0-9a-f:]+", h): return False
    try: a = ipaddress.IPv6Address(h)
    except ValueError: return False
    n = int(a)
    return n == 1 or (n >> 118) == (0xfe80 >> 6) or (n >> 121) == (0xfc00 >> 9)
LOCAL_LOSSY = "IPv6 link-local and unique-local addresses (fe80::/10, fc00::/7) cannot be written as host patterns"
SIGNATURE_ROLES = ("author", "reviewer", "scanner")
V08 = (0, 8)
SAFE_INT = 2 ** 53 - 1
MAX_DEPTH = 64
MAX_PATH_LEN = 1024
MAX_PATH_SEGMENTS = 32
MAX_FILES = 10000
# integrity coverage (spec 0.8 s11.2): files excluded by default, and files that can never be excluded
DEFAULT_EXCLUDE = (".git/**", "**/.DS_Store")   # 0.8 errata: bytecode (__pycache__, *.pyc) is no longer excluded (it can shadow signed sources)
PROTECTED = ("SKILL.md", "**/SKILL.md", "**/CLAUDE.md", "**/AGENTS.md", "**/GEMINI.md", "**/.mcp.json", ".claude-plugin/**",
             ".claude/**", ".cursor/**", ".codex/**", ".gemini/**", ".agents/**", "hooks/**", "package.json", "pyproject.toml")
# 0.8 errata: code and bytecode can never be excluded either (an excluded module could be imported or sourced by a listed entry)
CODE_PROTECTED = tuple(f"**/*.{e}" for e in ("py", "pyc", "pyo", "pyd", "sh", "bash", "zsh", "fish", "js", "mjs", "cjs", "ts", "mts", "cts", "rb", "pl", "pm",
                       "php", "lua", "ps1", "psm1", "bat", "cmd", "exe", "so", "dylib", "dll", "jar", "class", "wasm", "pth"))
PROTECTED = PROTECTED + CODE_PROTECTED
BYTECODE = ("**/__pycache__/**", "**/*.pyc", "**/*.pyo")
PATH_EFFECTS = ("read", "write")


def _vt(v):
    try: return tuple(int(x) for x in str(v).split("."))
    except ValueError: return (0, 0)  # contract_version >= 0.4 signs RFC 8785 (JCS) bytes


def version_status(v):
    """'ok' | 'unknown_major' | 'unknown_minor' (spec 0.4 section 17)."""
    if not isinstance(v, str) or not re.fullmatch(r"\d+\.\d+", v): return "unknown_major"
    if v in KNOWN_VERSIONS: return "ok"
    major = int(v.split(".")[0]); known_majors = {int(k.split(".")[0]) for k in KNOWN_VERSIONS}
    if major == 0 or major not in known_majors: return "unknown_major"  # 0.x minors may break: treat as unknown major
    return "unknown_minor"


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


class ContractJSONError(ValueError):
    """Contract is not I-JSON (RFC 7493) within SkillPact limits (spec 0.8 s4.1)."""


def parse_json_strict(text: str):
    """I-JSON parse: no duplicate keys, integers within +-(2^53-1), finite numbers, well-formed Unicode, depth <= 64."""
    def pint(s):
        v = int(s)
        if abs(v) > SAFE_INT: raise ContractJSONError(f"integer {s[:24]} outside +-(2^53-1)")
        return v
    def pfloat(s):
        v = float(s)
        if not math.isfinite(v): raise ContractJSONError(f"number {s[:24]} is not finite")
        return v
    def pconst(s): raise ContractJSONError(f"{s} is not JSON")
    try: obj = json.loads(text, object_pairs_hook=_no_dup_keys, parse_int=pint, parse_float=pfloat, parse_constant=pconst)
    except RecursionError: raise ContractJSONError(f"nesting deeper than {MAX_DEPTH}")
    except json.JSONDecodeError as e: raise ContractJSONError(str(e))
    stack = [(obj, 1)]
    while stack:
        v, d = stack.pop()
        if isinstance(v, (dict, list)):
            if d > MAX_DEPTH: raise ContractJSONError(f"nesting deeper than {MAX_DEPTH}")
            items = list(v.items()) if isinstance(v, dict) else [(None, i) for i in v]
            for k, i in items:
                if k is not None: _wellformed(k)
                stack.append((i, d + 1))
        elif isinstance(v, str): _wellformed(v)
    return obj


def _wellformed(s):
    try: s.encode("utf-8")
    except UnicodeEncodeError: raise ContractJSONError("string contains a lone surrogate")


def load_contract(skill_dir: Path, contract_path: Path | None = None):
    p = contract_path or (Path(skill_dir) / CONTRACT_FILE)
    return parse_json_strict(Path(p).read_text(encoding="utf-8")), Path(p)


def _no_dup_keys(pairs):
    d = {}
    for k, v in pairs:
        if k in d: raise ContractJSONError(f"duplicate key {k!r}")
        d[k] = v
    return d


# ---------------- validate ----------------
def validate(skill_dir, contract_path=None) -> dict:
    skill_dir = Path(skill_dir).resolve(); r = Report()
    sm = skill_dir / "SKILL.md"
    fm = None; name_dir_mismatch = None
    if not sm.exists(): r.err("SKILL_MD_MISSING", "SKILL.md not found", str(sm))
    else:
        fm, body = read_frontmatter(sm)
        if fm is None: r.err("FRONTMATTER_MISSING", "SKILL.md has no YAML frontmatter", "SKILL.md")
        else:
            n, d = fm.get("name"), fm.get("description")
            if not isinstance(n, str) or not NAME_RE.match(n) or len(n) > 64: r.err("FM_NAME", f"invalid name {n!r} (agentskills.io rules)", "SKILL.md")
            elif n != skill_dir.name and not contract_path: name_dir_mismatch = f"name {n!r} != directory {skill_dir.name!r}"
            if not isinstance(d, str) or not (1 <= len(d) <= 1024): r.err("FM_DESCRIPTION", "description must be 1-1024 chars", "SKILL.md")
            if "compatibility" in fm and len(str(fm["compatibility"])) > 500: r.err("FM_COMPAT", "compatibility > 500 chars", "SKILL.md")
            if body.count("\n") > 500: r.warn("BODY_LONG", f"SKILL.md body has {body.count(chr(10))} lines (> 500 recommended max)", "SKILL.md")
    try: c, cpath = load_contract(skill_dir, Path(contract_path) if contract_path else None)
    except FileNotFoundError:
        r.err("CONTRACT_MISSING", f"{CONTRACT_FILE} not found"); return r.to_dict()
    except (ContractJSONError, json.JSONDecodeError, UnicodeDecodeError) as e:
        r.err("CONTRACT_JSON", str(e)); return r.to_dict()
    vs = version_status(c.get("contract_version") if isinstance(c, dict) else None)
    if vs == "unknown_major":
        r.err("CONTRACT_VERSION_UNSUPPORTED", f"contract_version {c.get('contract_version') if isinstance(c, dict) else None!r} is not supported (known: {', '.join(KNOWN_VERSIONS)})", "/contract_version"); return r.to_dict()
    if vs == "unknown_minor":
        r.warn("CONTRACT_VERSION_NEWER", f"contract_version {c['contract_version']!r} is newer than this validator; unknown fields may be ignored", "/contract_version")
        c = {**c, "contract_version": KNOWN_VERSIONS[-1]}
    for e in sorted(Draft202012Validator(SCHEMA).iter_errors(c), key=lambda e: list(e.path)):
        r.err("SCHEMA", e.message, "/" + "/".join(map(str, e.path)))
    if not r.ok: return r.to_dict()
    if name_dir_mismatch:  # Agent Skills: name MUST match the parent directory (error from 0.7)
        (r.err if _vt(c["contract_version"]) >= (0, 7) else r.warn)("FM_NAME_DIR", name_dir_mismatch, "SKILL.md")
    # cross checks
    if fm and fm.get("name") != c["skill"]["name"]: r.err("NAME_MISMATCH", f"contract skill.name {c['skill']['name']!r} != SKILL.md name {fm.get('name')!r}")
    perms = c["permissions"]
    for eff in ("spend", "send"):
        if perms[eff]["level"] == "any": r.warn("HIGH_RISK", f"{eff}: level 'any' — harnesses will usually ask or deny", f"/permissions/{eff}")
    for eff in EFFECTS:
        if perms[eff]["level"] == "scoped" and not perms[eff].get("scope"): r.err("SCOPE_EMPTY", f"permissions.{eff}: level 'scoped' needs at least one scope", f"/permissions/{eff}")
        for sc in perms[eff].get("scope", []):
            if sc.startswith("@") and sc not in SCOPE_TOKENS.get(eff, ()): r.warn("UNKNOWN_SCOPE_TOKEN", f"permissions.{eff}.scope token {sc} is not defined", f"/permissions/{eff}")
            for var in re.findall(r"\$[A-Z_]+", sc):
                if var not in PATH_VARS: r.warn("UNKNOWN_VARIABLE", f"permissions.{eff}.scope uses undefined variable {var}", f"/permissions/{eff}")
            if eff in PATH_EFFECTS and scope_traversal(sc): r.err("SCOPE_TRAVERSAL", f"permissions.{eff}.scope {sc!r} contains '.', '..', an empty segment or a backslash", f"/permissions/{eff}")
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
            if eff in PATH_EFFECTS:
                for s_ in sc:
                    if scope_traversal(s_): r.err("SCOPE_TRAVERSAL", f"{cap['id']}: effect_scopes.{eff} {s_!r} escapes its base", f"/capabilities/{i}")
            outer = perms[eff].get("scope", [])
            if perms[eff]["level"] == "scoped" and not _covered(sc, outer, effect_kind(eff)): r.err("SCOPE_WIDENED", f"{cap['id']}: effect_scopes.{eff} not within permissions.{eff}.scope", f"/capabilities/{i}")
        for f in cap.get("requires_features", []):
            if f.split(":", 1)[0] not in feature_kinds: r.err("UNKNOWN_FEATURE_KIND", f"{cap['id']}: {f} has no features_check for its kind", f"/capabilities/{i}")
        if c.get("kind", "tool") == "tool" and not cap.get("entry", {}).get("cli") and not cap.get("entry", {}).get("mcp_tool") and cap["effects"]:
            r.warn("NO_ENTRY", f"{cap['id']} has effects but no cli/mcp entry", f"/capabilities/{i}")
    used = {eff for cap in c["capabilities"] for eff in cap["effects"] + [x["effect"] for x in cap.get("conditional_effects", [])]}
    for eff in EFFECTS:
        if perms[eff]["level"] != "none" and eff not in used: r.warn("UNUSED_PERMISSION", f"permissions.{eff} declared but no capability uses it", f"/permissions/{eff}")
    v08 = _vt(c["contract_version"]) >= V08
    for t in c.get("tests", {}).get("cases", []):
        if t.get("capability") and t["capability"] not in ids: r.err("TEST_UNKNOWN_CAPABILITY", f"test {t['id']} refers to {t['capability']}")
        if t.get("network") and perms["network"]["level"] == "none":
            (r.err if v08 else r.warn)("TEST_UNDECLARED_NETWORK", f"test {t['id']} has network: true but permissions.network is 'none'")
    drafts = draft_markers(c)
    if drafts: (r.err if v08 else r.warn)("UNCONFIRMED_DRAFT", f"unconfirmed draft content: {', '.join(drafts[:5])}")
    if not c.get("tests", {}).get("cases") and c.get("kind", "tool") == "tool": r.warn("NO_TESTS", "no conformance tests declared")
    tested = {t.get("capability") for t in c.get("tests", {}).get("cases", [])}
    untested = [x for x in ids if x not in tested]
    if c.get("tests", {}).get("cases") and untested: r.warn("UNTESTED_CAPABILITY", f"{len(untested)} capabilities have no test: {', '.join(sorted(untested)[:8])}")
    if "integrity" in c:
        files = c["integrity"].get("files", {})
        if v08 and "SKILL.md" not in files: r.err("INTEGRITY_EMPTY", "integrity.files must list SKILL.md and every other skill file (spec 0.8 s11.2)", "/integrity/files")
        if len(files) > MAX_FILES: r.err("INTEGRITY_PATH", f"integrity.files has {len(files)} entries (max {MAX_FILES})", "/integrity/files")
        for rel, h in files.items():
            bad = integrity_path_problem(rel)
            if bad: r.err("INTEGRITY_PATH", f"{rel!r}: {bad}", "/integrity/files"); continue
            f = skill_dir / rel
            link = _symlink_in(skill_dir, rel)
            if link: r.err("INTEGRITY_PATH", f"{rel!r}: {link} is a symbolic link", "/integrity/files")
            elif not f.is_file(): r.err("INTEGRITY_MISSING", f"{rel} missing")
            elif sha256(f) != h: r.err("INTEGRITY_MISMATCH", f"{rel} hash differs")
        for kind, rel in unlisted_files(skill_dir, c, limit=200):   # 0.8 errata: also with an external contract (--contract)
            if kind == "symlink": (r.err if v08 else r.warn)("INTEGRITY_PATH", f"{rel!r} is a symbolic link (not allowed in a skill directory)")
            else: (r.err if v08 else r.warn)("INTEGRITY_UNLISTED", f"{rel} is not covered by integrity.files" + ("; it is Python bytecode: delete it (or set PYTHONDONTWRITEBYTECODE=1)" if _excluded(rel, BYTECODE) else ""))
        if c["integrity"].get("signatures"):
            for k in duplicate_signers(c): r.err("DUP_SIGNATURE", f"more than one signature by {k}", "/integrity/signatures")
            res = verify_signatures(c)
            if any(v is False for v in res.values()): r.err("SIGNATURE_INVALID", f"signature check failed: {res}")
            if any(v is None for v in res.values()): r.warn("SIGSTORE_UNVERIFIED", "a Sigstore signature could not be verified here (install skillpact[sigstore]; the trust root needs network on first use); it is neither valid nor trusted")
            if not v08: r.warn("SIGNATURE_ROLE_UNSIGNED", "before 0.8 the signer role is not signed, so it can be changed: such signatures never give L3 (0.8 errata); migrate and re-sign")
    return r.to_dict()


# ---------------- paths, globs and coverage (spec 0.8 s6.1, s11.2) ----------------
def scope_traversal(sc: str) -> bool:
    """True if a path scope contains '.', '..', an empty segment or a backslash (s6.1)."""
    if "\\" in sc: return True
    segs = sc.split("/")
    if sc.startswith("/"): segs = segs[1:]
    return any(s_ in ("", ".", "..") for s_ in segs)


def integrity_path_problem(rel: str):
    if not isinstance(rel, str) or not rel: return "empty path"
    if len(rel.encode("utf-8", "replace")) > MAX_PATH_LEN: return f"longer than {MAX_PATH_LEN} bytes"
    if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel): return "absolute path"
    if "\\" in rel or any(ord(ch) < 32 for ch in rel): return "backslash or control character"
    segs = rel.split("/")
    if len(segs) > MAX_PATH_SEGMENTS: return f"more than {MAX_PATH_SEGMENTS} segments"
    if any(s_ in ("", ".", "..") for s_ in segs): return "'.', '..' or empty segment"
    return None


def _symlink_in(root: Path, rel: str):
    cur = root
    for part in rel.split("/"):
        cur = cur / part
        if cur.is_symlink(): return str(cur.relative_to(root))
    return None


def _glob_re(p: str) -> str:
    parts, out, glue = p.split("/"), "", False
    for i, seg in enumerate(parts):
        sep = "" if i == 0 or glue else "/"; glue = False
        if seg == "**":
            if i == len(parts) - 1: out += "(?:/.*)?" if i else ".*"
            else: out += sep + "(?:[^/]+/)*"; glue = True
            continue
        out += sep + "".join("[^/]*" if ch == "*" else "[^/]" if ch == "?" else re.escape(ch) for ch in re.sub(r"\*+", "*", seg))
    return out


def _host_match(h: str, p: str) -> bool:
    if p == "@local": return h == "@local" or is_local_host(h)
    h, p = h.lower().rstrip("."), p.lower().rstrip(".")
    if p == "*": return True
    hl, pl = h.split("."), p.split(".")
    lab = lambda s_, q: re.fullmatch("".join("[^.]*" if ch == "*" else "." if ch == "?" else re.escape(ch) for ch in q), s_) is not None
    if pl[0] in ("*", "**") and len(pl) > 1:
        rest = pl[1:]; need = len(rest)
        if len(hl) < need + (1 if pl[0] == "*" else 0): return False
        return all(lab(a, b) for a, b in zip(hl[-need:], rest))
    return len(hl) == len(pl) and all(lab(a, b) for a, b in zip(hl, pl))


def glob_match(s: str, p: str, kind: str = "path") -> bool:
    """Normative SkillPact glob (s6.1). path/generic: '*' and '?' stay within one '/'-segment, a whole '**' segment spans
    zero or more segments. host: '*' stays within one DNS label; a leading '*.' spans one or more labels, '**.' zero or more."""
    if kind == "host": return _host_match(s, p)
    return re.fullmatch(_glob_re(p), s) is not None


def effect_kind(eff): return "path" if eff in PATH_EFFECTS else "host" if eff == "network" else "generic"


def _as_literal(s: str, kind: str) -> str:
    """A scope entry used as the subject of coverage: its own wildcards must only be matched by equal or wider ones."""
    if kind == "host": return s
    return "/".join("\x00/\x00" if seg == "**" else seg.replace("*", "\x01*\x01") for seg in s.split("/"))


def _covered(scope, patterns, kind="generic"):
    if not scope: return False
    if kind == "path" and any(scope_traversal(s_) for s_ in scope): return False
    return all(any(s_ == p or glob_match(_as_literal(s_, kind), p, kind) for p in patterns) for s_ in scope)


def _excluded(rel, pats): return any(glob_match(rel, p) for p in pats)


def required_paths(c) -> set:
    """Files that must be listed whatever integrity.exclude says: entries and test commands that name $SKILL_DIR/..."""
    out = set()
    toks = [t for cap in c.get("capabilities", []) for t in cap.get("entry", {}).get("cli", []) or []]
    toks += [t for case in c.get("tests", {}).get("cases", []) for t in case.get("run", [])]
    toks += [t for cmd in c.get("tests", {}).get("setup", []) for t in cmd]
    for t in toks:
        for m in re.findall(r"\$SKILL_DIR/([^\s'\"]+)", str(t)): out.add(m)
    return out


def unlisted_files(skill_dir: Path, c, limit=None) -> list:
    """[(kind, rel)] for files under skill_dir that integrity.files does not cover (s11.2)."""
    files = set(c.get("integrity", {}).get("files", {})); excl = list(DEFAULT_EXCLUDE) + list(c.get("integrity", {}).get("exclude", []))
    must = required_paths(c); out = []
    for root, dirs, names in os.walk(skill_dir, followlinks=False):
        rp = Path(root)
        for n in sorted(dirs + names):
            f = rp / n; rel = f.relative_to(skill_dir).as_posix()
            if rel == CONTRACT_FILE: continue
            protected = _excluded(rel, PROTECTED) or rel in must
            if f.is_symlink():
                if protected or not _excluded(rel, excl): out.append(("symlink", rel))
                continue
            if f.is_dir() or rel in files: continue
            if protected or not _excluded(rel, excl): out.append(("file", rel))
        if limit and len(out) >= limit: break
    return out


def draft_markers(c) -> list:
    out = []
    for k in ("init", "import"):
        if c.get("x", {}).get(k, {}).get("uncertain"): out.append(f"x.{k}.uncertain")
    def walk(v, path):
        if isinstance(v, dict):
            for k, i in v.items(): walk(i, f"{path}/{k}")
        elif isinstance(v, list):
            for n, i in enumerate(v): walk(i, f"{path}/{n}")
        elif isinstance(v, str) and "TODO(" in v: out.append(path or "/")
    walk({k: v for k, v in c.items() if k != "x"}, "")
    return out


# ---------------- integrity / signing ----------------
def sha256(p: Path) -> str: return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def hash_files(skill_dir, contract_path=None):
    """List every file of the skill (spec 0.8 s11.2): all regular files except skill.contract.json, the default excludes
    and integrity.exclude (protected files are always listed). Symbolic links are refused."""
    skill_dir = Path(skill_dir).resolve(); c, cpath = load_contract(skill_dir, contract_path)
    exclude = c.get("integrity", {}).get("exclude", [])
    c["integrity"] = {"algorithm": "sha256", "files": {}, **({"exclude": exclude} if exclude else {})}
    files = {}
    for kind, rel in unlisted_files(skill_dir, c):
        if kind == "symlink": raise SystemExit(f"refusing to hash: {rel} is a symbolic link")
        if _excluded(rel, BYTECODE): raise SystemExit(f"refusing to hash: {rel} is Python bytecode; delete __pycache__ and *.pyc before hashing (bytecode can shadow the signed sources)")
        files[rel] = sha256(skill_dir / rel)
    if len(files) > MAX_FILES: raise SystemExit(f"too many files ({len(files)} > {MAX_FILES})")
    c["integrity"] = {"algorithm": "sha256", "files": dict(sorted(files.items())), **({"exclude": exclude} if exclude else {}), "signatures": []}
    cpath.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n")
    return len(files)


def canonicalization_for(c):
    """'jcs' (RFC 8785) for contract_version >= 0.4, else 'legacy-sorted' (0.1-0.3)."""
    try: v = tuple(int(x) for x in str(c.get("contract_version", "0.1")).split("."))
    except ValueError: return "jcs"
    return "jcs" if v >= JCS_FROM else "legacy-sorted"


def jcs(obj) -> bytes:
    import rfc8785
    return rfc8785.dumps(obj)


def _legacy_numbers(v):
    """0.1-0.3 legacy form supports integer numbers within +-(2^53-1) only (spec 0.8 s11.1); integral floats become ints."""
    if isinstance(v, dict): return {k: _legacy_numbers(i) for k, i in v.items()}
    if isinstance(v, list): return [_legacy_numbers(i) for i in v]
    if isinstance(v, float):
        if not v.is_integer() or abs(v) > SAFE_INT: raise ContractJSONError("legacy (0.1-0.3) canonicalization supports integers only; migrate and re-sign")
        return int(v)
    return v


def _canonical(c, role=None):
    """Signing input. >= 0.8: JCS({"contract": C, "role": R}) so the role is signed; 0.4-0.7: JCS(C); 0.1-0.3: legacy sorted.
    C is the contract without integrity.signatures."""
    c2 = json.loads(json.dumps(c)); c2.get("integrity", {}).pop("signatures", None)
    if _vt(c.get("contract_version", "0.1")) >= V08: return jcs({"contract": c2, "role": role or "author"})
    if canonicalization_for(c) == "jcs": return jcs(c2)
    return json.dumps(_legacy_numbers(c2), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def signing_input(c, role="author"): return _canonical(c, role)


def keygen(path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization as s
    k = Ed25519PrivateKey.generate()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f: f.write(k.private_bytes(s.Encoding.PEM, s.PrivateFormat.PKCS8, s.NoEncryption()))
    pub = k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)
    return "ed25519:" + base64.b64encode(pub).decode()


def sign(skill_dir, key_path, signer="", contract_path=None, role="author"):
    from cryptography.hazmat.primitives import serialization as s
    skill_dir = Path(skill_dir).resolve(); c, cpath = load_contract(skill_dir, contract_path)
    if "integrity" not in c: raise SystemExit("run `hash` first")
    k = s.load_pem_private_key(Path(key_path).read_bytes(), None)
    pub = "ed25519:" + base64.b64encode(k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)).decode()
    sig = base64.b64encode(k.sign(_canonical(c, role))).decode()
    entry = {"type": "ed25519", "key": pub, "sig": sig, "signer": signer}
    if role != "author" or _vt(c.get("contract_version", "0.1")) >= V08: entry["role"] = role
    c["integrity"].setdefault("signatures", []).append(entry)
    cpath.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n")
    return pub


def verify_signatures(c, sigstore_verifier=None, offline=False) -> dict:
    """{key-or-identity: True | False | None}. ed25519 entries are keyed by public key, sigstore entries by
    'sigstore:<issuer>|<identity>'. None: a Sigstore entry that cannot be verified here (SIGSTORE_UNVERIFIED)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    out = {}
    for s_ in c.get("integrity", {}).get("signatures", []):
        k = sig_key(s_)
        if s_.get("type") == "sigstore":
            from . import sigstore_sig
            ok = sigstore_sig.verify_entry(c, s_, sigstore_verifier, offline)
        else:
            try:
                Ed25519PublicKey.from_public_bytes(base64.b64decode(s_["key"].split(":", 1)[1])).verify(base64.b64decode(s_["sig"]), _canonical(c, s_.get("role")))
                ok = True
            except Exception: ok = False
        prev = out.get(k, True)   # a key that signs twice is only valid if every entry is (s11, DUP_SIGNATURE)
        out[k] = False if False in (prev, ok) else None if None in (prev, ok) else True
    return out


def sig_key(s_):
    if s_.get("type") == "sigstore":
        pre = "sigstore-staging" if s_.get("instance") == "staging" else "sigstore"  # staging never matches a production trust entry
        return f"{pre}:{s_.get('issuer')}|{s_.get('identity')}"
    return s_.get("key")


def duplicate_signers(c) -> list:
    seen, dup = set(), []
    for s_ in c.get("integrity", {}).get("signatures", []):
        k = sig_key(s_)
        if k in seen and k not in dup: dup.append(k)
        seen.add(k)
    return dup


# ---------------- requirements & tests ----------------
def _ver_tuple(v): return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def _ver_ok(found, spec):
    m = re.match(r"^\s*(>=|>|==|<=|<)?\s*([\d.]+)", spec or "")
    if not m: return True
    op, want = m.group(1) or ">=", _ver_tuple(m.group(2))
    f = _ver_tuple(found)
    return {">=": f >= want, ">": f > want, "==": f[:len(want)] == want, "<=": f <= want, "<": f < want}[op]


PKG_CLAUSE = re.compile(r"^\s*(==|!=|>=|<=|~=|>|<)?\s*(\d+(?:\.\d+)*)\s*$")


def _pkg_version_ok(found, spec):
    """0.8.x erratum: requirements.packages[].version, e.g. '==1.106.2' or '>=1.0,<2'. Every comma-separated clause must hold;
    a clause that cannot be parsed fails (a pin that is not understood must not pass silently)."""
    f = _ver_tuple(found)
    for clause in spec.split(","):
        m = PKG_CLAUSE.match(clause)
        if not m: return False
        op, want = m.group(1) or "==", _ver_tuple(m.group(2))
        if op == "~=":
            if len(want) < 2 or f < want or f[:len(want) - 1] != want[:-1]: return False
        elif op == "!=":
            if f[:len(want)] == want: return False
        elif not _ver_ok(found, op + m.group(2)): return False
    return True


STARTUP_HOOKS = ("sitecustomize.py", "usercustomize.py")


def _dist(name):
    import importlib.metadata as md
    try: return md.distribution(name)
    except md.PackageNotFoundError: return None


def startup_hooks(dist) -> list:
    """Files a distribution installs at the top of site-packages that Python runs at start-up (*.pth, sitecustomize.py,
    usercustomize.py): the litellm 1.107.0 payload (2026-10-21) used both, so it ran without being imported."""
    return sorted(str(f) for f in (dist.files or []) if "/" not in str(f) and (str(f).endswith(".pth") or str(f) in STARTUP_HOOKS))


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
            found = importlib.util.find_spec(pk.get("import") or pk["name"].replace("-", "_").lower()) is not None
            d = _dist(pk["name"]) if found else None
            res = {"name": f"pypi:{pk['name']}", "found": found, "kind": "package", "required": pk.get("version"), "version": d.version if d else None}
            ok = found
            if found and pk.get("version"):   # 0.8.x erratum: an installed package must match its pin, even when optional
                if not d: ok, res["reason"] = False, "installed version unknown (no distribution metadata)"
                elif not _pkg_version_ok(d.version, pk["version"]): ok, res["reason"] = False, f"installed {d.version} does not satisfy {pk['version']}"
            if d and startup_hooks(d): res["startup_hooks"] = startup_hooks(d)
            res["ok"] = ok or (not found and pk.get("optional", False))
            out.append(res)
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


def _snapshot(d: Path, cap=20000):
    """Content hashes (not size/mtime) of every file under d (spec 0.8 s10.2)."""
    out = {}
    if not d.exists(): return out
    for p in d.rglob("*"):
        if len(out) >= cap: break
        try:
            if p.is_symlink(): out[str(p.relative_to(d))] = "link:" + os.readlink(p)
            elif p.is_file() and "__pycache__" not in p.parts: out[str(p.relative_to(d))] = sha256(p)
        except OSError: pass
    return out


ENV_ALLOW = ("PATH", "LANG", "LC_ALL", "TZ", "TERM")


def _sandbox():
    """'bwrap' (filesystem read-only except $WORKDIR + network namespace), 'unshare' (network namespace only) or None."""
    if os.environ.get("SKILLPACT_SANDBOX") == "none": return None
    if shutil.which("bwrap") and subprocess.run(["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--unshare-net", "true"], capture_output=True).returncode == 0: return "bwrap"
    if shutil.which("unshare") and subprocess.run(["unshare", "-rn", "true"], capture_output=True).returncode == 0: return "unshare"
    if os.path.exists(SEATBELT) and subprocess.run([SEATBELT, "-p", _seatbelt_profile("/nonexistent-skillpact", None, False), "true"], capture_output=True).returncode == 0: return "seatbelt"
    return None


SEATBELT = "/usr/bin/sandbox-exec"   # macOS Seatbelt; deprecated by Apple but functional (also used by Codex / Claude Code sandboxes)


def _masked_roots():
    """Locations hidden from tests (0.8 errata, s10 item 4): the user's home, temporary and runtime directories,
    which hold credentials and Unix sockets (D-Bus, Docker, agents)."""
    home = os.path.realpath(os.environ.get("HOME") or str(Path.home()))
    roots = [r for r in ("/tmp", "/var/tmp", "/run", "/dev/shm") if os.path.isdir(r)]
    if home not in ("/", "") and os.path.isdir(home): roots.append(home)
    return roots


def _keep_paths(extra=(), programs=()):
    """Paths re-exposed read-only under a masked root (0.8.x erratum): only the resolved directories of the programs the
    contract needs (exec scope, requirements, test and setup commands) plus their virtualenv root, located dependency
    skills, the skill itself, and SKILLPACT_SANDBOX_KEEP (colon separated). Other PATH entries (e.g. ~/.local/bin) and
    their parents stay hidden. System directories (/usr, /lib, /opt ...) are never masked."""
    masked = _masked_roots(); out = []
    def under(p_): return any(p_ == m or p_.startswith(m.rstrip("/") + "/") for m in masked)
    def add(q_):
        if q_ and os.path.isdir(q_) and under(q_) and q_ not in out: out.append(q_)
    for e in [e for e in os.environ.get("SKILLPACT_SANDBOX_KEEP", "").split(":") if e] + list(extra): add(os.path.realpath(e))
    for prog in programs:
        if not prog or "$" in prog: continue
        w_ = shutil.which(prog) if "/" not in prog else (prog if os.path.isfile(prog) else None)
        if not w_: continue
        for b_ in dict.fromkeys([os.path.dirname(os.path.abspath(w_)), os.path.dirname(os.path.realpath(w_))]):
            root = os.path.dirname(b_)
            add(root if os.path.isfile(os.path.join(root, "pyvenv.cfg")) else b_)
    for r_ in ("/run/systemd/resolve",):   # DNS for network: true cases
        if os.path.isdir(r_) and r_ not in out: out.append(r_)
    return out


def _programs(c):
    """Program names a contract's tests may start (for _keep_paths)."""
    t = c.get("tests") or {}; perm = (c.get("permissions") or {}).get("exec") or {}
    names = [x for x in perm.get("scope", []) if isinstance(x, str)]
    for r in (c.get("requirements") or {}).get("binaries", []) + (c.get("requirements") or {}).get("runtimes", []): names.append(r.get("name", ""))
    for cmd in list(t.get("setup", [])) + [x.get("run", []) for x in t.get("cases", [])]:
        if cmd and isinstance(cmd[0], str): names.append(cmd[0])
    return [n_ for n_ in dict.fromkeys(names) if n_ and not any(ch in n_ for ch in "*?")]


def _seatbelt_profile(work, rw_skill, net, keep=()):
    """SBPL profile: everything allowed except file writes outside $WORKDIR (+ $SKILL_DIR if allowed) and, unless net, all network."""
    q = lambda p_: '"' + os.path.realpath(p_).replace("\\", "\\\\").replace('"', '\\"') + '"'
    roots = " ".join(f"(subpath {q(r)})" for r in [work] + ([rw_skill] if rw_skill else []))
    home = os.path.realpath(os.environ.get("HOME") or str(Path.home()))
    reads = " ".join(f"(subpath {q(r)})" for r in [work] + ([rw_skill] if rw_skill else []) + list(keep))
    prof = ["(version 1)", "(allow default)", "(deny file-write*)",
            f'(allow file-write* {roots} (literal "/dev/null") (literal "/dev/tty") (regex #"^/dev/fd/"))']
    if home not in ("/", ""): prof += [f"(deny file-read* (subpath {q(home)}))", f"(allow file-read* {reads})"]
    if not net: prof.append("(deny network*)")
    else:  # 0.8.x erratum: even with network, no host Unix sockets (only the DNS resolver socket)
        prof += ["(deny network-outbound (remote unix-socket))",
                 '(allow network-outbound (remote unix-socket (path-literal "/private/var/run/mDNSResponder")))']
    return "\n".join(prof)


def _wrap(cmd, mode, net, work, rw_skill, ro=(), programs=()):
    """ro: paths to re-expose read-only under the masked roots (the skill directory, dependency skills)."""
    if mode == "bwrap":
        w = ["bwrap", "--die-with-parent", "--new-session", "--unshare-pid", "--unshare-ipc", "--unshare-uts", "--unshare-cgroup-try",
             "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc"]
        for m in _masked_roots(): w += ["--tmpfs", m]
        for k in _keep_paths(ro, list(programs) + cmd[:1]): w += ["--ro-bind", k, k]
        w += ["--bind", str(work), str(work)]
        if rw_skill: w += ["--bind", rw_skill, rw_skill]
        if not net: w += ["--unshare-net"]
        return w + ["--chdir", str(work), "--"] + cmd
    if mode == "unshare" and not net: return ["unshare", "-rn"] + cmd
    if mode == "seatbelt": return [SEATBELT, "-p", _seatbelt_profile(work, rw_skill, net, _keep_paths(ro, list(programs) + cmd[:1])), "--"] + cmd
    return cmd


def run_tests(skill_dir, contract_path=None, only=None, sandbox_network=True, skills_path=(), pass_env=()) -> dict:
    """Run the declared tests (spec 0.8 s10): setup and cases in a sandbox, allowlisted environment only,
    writes outside $WORKDIR prevented (bwrap) or detected by content hash (fallback)."""
    skill_dir = Path(skill_dir).resolve(); c, _ = load_contract(skill_dir, contract_path)
    skill_env, skill_reqs = locate_skills(c, skill_dir, skills_path)
    reqs = check_requirements(c) + skill_reqs
    if not all(r["ok"] for r in reqs):
        return {"ok": False, "requirements": reqs, "cases": [], "error": "requirements not met"}
    mode = _sandbox() if sandbox_network else None
    caps = {cap["id"]: cap for cap in c["capabilities"]}
    work = Path(tempfile.mkdtemp(prefix="skilltest-")); (work / ".home").mkdir(); (work / ".tmp").mkdir()
    scope = c["permissions"]["write"].get("scope", [])
    skill_dir_writes_allowed = any(s_.startswith("$SKILL_DIR") for s_ in scope)
    env = {k: os.environ[k] for k in ENV_ALLOW if k in os.environ}
    env.update({**skill_env, "SKILL_DIR": str(skill_dir), "WORKDIR": str(work), "HOME": str(work / ".home"), "TMPDIR": str(work / ".tmp"),
                "PYTHONDONTWRITEBYTECODE": "1", "LANG": env.get("LANG", "C.UTF-8")})
    ro = [str(skill_dir)] + list(skill_env.values()) + ([str(Path(contract_path).resolve().parent)] if contract_path else [])
    progs = _programs(c)
    wrap = lambda cmd, net=False: _wrap(cmd, mode, net, work, str(skill_dir) if skill_dir_writes_allowed else None, ro, progs)
    results = []
    watch = [skill_dir] + ([] if mode in ("bwrap", "seatbelt") else [skill_dir.parent])
    before = {str(d): _snapshot(d) for d in watch}
    setup_error = None
    try:
        for cmd in c.get("tests", {}).get("setup", []):
            p = subprocess.run(wrap([_subst(t, env) for t in cmd]), cwd=work, env=env, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL, start_new_session=True)
            if p.returncode != 0: setup_error = f"setup failed: {p.stderr[-500:]}"; break
        for t in ([] if setup_error else c.get("tests", {}).get("cases", [])):
            if only and t["id"] not in only: continue
            # 0.8 errata: a case only receives skip_unless_env variables the person running the tests allowed (--pass-env)
            if any(not os.environ.get(v) or v not in pass_env for v in t.get("skip_unless_env", [])):
                why = "not allowed (use --pass-env)" if all(os.environ.get(v) for v in t.get("skip_unless_env", [])) else "not set"
                results.append({"id": t["id"], "capability": t.get("capability"), "ok": True, "skipped": True, "skip_reason": f"skip_unless_env {why}", "failures": [], "seconds": 0, "network_sandboxed": False, "stderr_tail": ""}); continue
            cenv = {**env, **{v: os.environ[v] for v in t.get("skip_unless_env", [])}, **{k: _subst(v, env) for k, v in t.get("env", {}).items()}}
            cmd = wrap([_subst(x, env) for x in t["run"]], bool(t.get("network")))
            t0 = time.time(); fails = []
            try:
                p = subprocess.run(cmd, cwd=work, env=cenv, capture_output=True, text=True, stdin=subprocess.DEVNULL, start_new_session=True, timeout=t.get("timeout_s", 120) * float(os.environ.get("SKILLPACT_TIMEOUT_SCALE", "1")))
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
                            "seconds": round(time.time() - t0, 2), "network_sandboxed": bool(mode and not t.get("network")),
                            "stderr_tail": errout[-300:] if fails else ""})
    finally:
        after = {str(d): _snapshot(d) for d in watch}
        shutil.rmtree(work, ignore_errors=True)
    changed = lambda b, a: sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    wrote = changed(before[str(skill_dir)], after[str(skill_dir)])
    outside = []
    if mode not in ("bwrap", "seatbelt"):
        sk = skill_dir.name + "/"
        outside = [k for k in changed(before[str(skill_dir.parent)], after[str(skill_dir.parent)]) if not k.startswith(sk)]
    violations = [] if skill_dir_writes_allowed else wrote
    t_net = {t["id"]: bool(t.get("network")) for t in c.get("tests", {}).get("cases", [])}
    isolated_pass = sum(1 for r in results if r["ok"] and not r.get("skipped") and not t_net.get(r["id"]))
    res = {"ok": not setup_error and all(r["ok"] for r in results) and not violations and not outside, "requirements": reqs, "cases": results,
           "sandbox": mode or "none", "fs_isolated": mode in ("bwrap", "seatbelt"), "network_isolated": bool(mode) and isolated_pass > 0,
           "skill_dir_writes": violations, "outside_writes": outside,
           "network_cases": sum(1 for r in results if t_net.get(r["id"]) and not r.get("skipped")),
           "passed": sum(r["ok"] and not r.get("skipped") for r in results), "skipped": sum(bool(r.get("skipped")) for r in results), "total": len(results)}
    if setup_error: res["error"] = setup_error
    return res


# ---------------- harness policy matching ----------------
ORDER = {"allow": 0, "ask": 1, "deny": 2}


def match_policy(contract, policy, skill_dir=None, contract_path=None) -> dict:
    errs = list(Draft202012Validator(POLICY_SCHEMA).iter_errors(policy))
    if errs: raise ValueError("invalid policy: " + "; ".join(e.message for e in errs[:3]))
    name = contract["skill"]["name"]
    sk = policy.get("skills", {})
    def out(decision, reason, caps=None):
        return {"skill": name, "decision": decision, "reason": reason, "capabilities": caps or []}
    if name in sk.get("deny", []): return out("deny", "skill is on the deny list")
    mv = policy.get("min_contract_version")
    if mv and _vt(contract.get("contract_version", "0.1")) < _vt(mv): return out("deny", f"contract_version {contract.get('contract_version')} is below the policy minimum {mv}")
    if policy.get("require_signature"):
        # spec 0.8 s13.1: the files must match integrity (full coverage) and the trusted signature must be an author signature
        if skill_dir is None: return out("deny", "require_signature: the skill directory is needed to verify integrity")
        v = validate(skill_dir, contract_path)
        bad = [f["code"] for f in v["findings"] if f["level"] == "error" or f["code"] in ("INTEGRITY_UNLISTED", "INTEGRITY_PATH")]
        if bad: return out("deny", f"require_signature: contract or files do not verify ({', '.join(sorted(set(bad))[:4])})")
        if "integrity" not in contract: return out("deny", "require_signature: contract has no integrity section")
        if not trusted_author(contract, set(policy.get("trusted_keys", []))): return out("deny", "policy requires a valid author signature from a trusted key")
    perms = contract["permissions"]
    caps = []
    for cap in contract["capabilities"]:
        per = []
        for eff in cap["effects"]:
            pe = perms[eff]; d = policy["defaults"][eff]; why = f"default for {eff}"
            if eff in cap.get("effect_scopes", {}): pe = {**pe, "scope": cap["effect_scopes"][eff]}
            if eff in PATH_EFFECTS and pe["level"] == "scoped" and any(scope_traversal(s_) for s_ in pe.get("scope", [])):
                per.append({"effect": eff, "decision": "deny", "why": "scope escapes its base (SCOPE_TRAVERSAL)"}); continue
            for rule in policy.get("rules", []):          # first matching rule wins
                if rule["effect"] != eff: continue
                pats = rule.get("scope")   # 0.8 errata: a rule without scope matches every scope of the effect
                if pats is None or (pe["level"] == "scoped" and _covered(pe.get("scope", []), pats, effect_kind(eff))) or (pe["level"] == "any" and pats in (["*"], ["**"])):
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


# ---------------- compile to native harness configs (spec 0.8 s13.2) ----------------
def _native_path(sc, style):
    """Map a SkillPact path scope to a harness path rule, or None if it cannot be expressed statically."""
    if sc.startswith("$WORKDIR"):
        rest = sc[len("$WORKDIR"):].lstrip("/") or "**"
        return ("./" + rest) if style == "claude" else rest
    if sc.startswith("/"): return ("/" + sc) if style == "claude" else sc   # Claude Code: '//abs' is an absolute path
    return None


def compile_native(contract, policy, target, mcp_server=None, skill_dir=None, contract_path=None) -> dict:
    """Translate the allow/ask/deny result for one skill into a harness's native config fragment.
    Returns {"config": <native config>, "lossy": [what could not be expressed]} (s13.2: lossy MUST be reported)."""
    m = match_policy(contract, policy, skill_dir, contract_path)
    perms, lossy = contract["permissions"], []
    lvl = lambda e: perms[e]["level"]
    scope = lambda e: perms[e].get("scope", []) if lvl(e) == "scoped" else []
    cmds, hosts = scope("exec"), expand_scope(scope("network"))
    if "@local" in scope("network"): lossy.append(f"network @local: {LOCAL_LOSSY}; harness host globs such as 10.*.*.* can also match DNS names, while @local itself matches IP literals and localhost only")
    worst = {}
    for c_ in m["capabilities"]:
        for e in c_["effects"] + c_.get("conditional", []): worst[e["effect"]] = max(worst.get(e["effect"], "allow"), e["decision"], key=ORDER.get)  # 0.8 errata: conditional too
    skill_denied = m["decision"] == "deny" and not m["capabilities"]
    bucket = lambda eff: "deny" if skill_denied else worst.get(eff, "allow")
    used = lambda eff: lvl(eff) != "none"
    by = {x_["capability"]: x_["decision"] for x_ in m["capabilities"]}
    if skill_denied: lossy.append(f"skill is denied ({m['reason']}): do not install it; the fragment below only restricts what it could do")
    for eff in ("spend", "send"):
        if used(eff): lossy.append(f"{eff}: {target} has no native permission for {eff}; decision '{bucket(eff)}' is only enforced through exec/network/MCP rules")
    sb = policy.get("sandbox", {})
    if target == "claude-code":
        out = {"allow": [], "ask": [], "deny": []}
        for c_ in cmds: out[bucket("exec")].append(f"Bash({c_} *)")
        if used("exec") and lvl("exec") == "any": out[bucket("exec")].append("Bash")
        for h in hosts: out[bucket("network")].append(f"WebFetch(domain:{h})")
        if used("network"):
            if lvl("network") == "any": out[bucket("network")].append("WebFetch")
            lossy.append("network: WebFetch rules do not cover network use by Bash commands; enable Claude Code sandboxing to enforce hosts")
        for eff, tool in (("write", "Edit"), ("read", "Read")):
            if not used(eff): continue
            if lvl(eff) == "any":
                if bucket(eff) != "allow": out[bucket(eff)].append(tool)
                continue
            for sc in scope(eff):
                r_ = _native_path(sc, "claude")
                if r_: out[bucket(eff)].append(f"{tool}({r_})")
                else: lossy.append(f"{eff} scope {sc}: depends on a variable resolved at run time; not expressed")
        if mcp_server:
            for cap in contract["capabilities"]:
                t = cap.get("entry", {}).get("mcp_tool")
                if t: out[by.get(cap["id"], "deny")].append(f"mcp__{mcp_server}__{t}")
        return {"config": {"permissions": {k: sorted(set(v)) for k, v in out.items()}}, "lossy": lossy}
    if target == "cursor":
        out = {"allow": [], "deny": []}   # Cursor has no ask list: anything not allowed prompts
        put = lambda d, rule: out[d].append(rule) if d in out else None
        for c_ in cmds: put(bucket("exec"), f"Shell({c_})")
        for h in hosts: put(bucket("network"), f"WebFetch({h})")
        if used("network") and lvl("network") == "any": put(bucket("network"), "WebFetch(*)")
        for eff, tool in (("write", "Write"), ("read", "Read")):
            if not used(eff): continue
            for sc in (scope(eff) if lvl(eff) == "scoped" else ["/**"]):
                r_ = _native_path(sc, "cursor")
                if r_: put(bucket(eff), f"{tool}({r_})")
                else: lossy.append(f"{eff} scope {sc}: depends on a variable resolved at run time; not expressed")
        if mcp_server:
            for cap in contract["capabilities"]:
                t = cap.get("entry", {}).get("mcp_tool")
                if t: put(by.get(cap["id"], "deny"), f"Mcp({mcp_server}:{t})")
        return {"config": {"version": 1, "permissions": {k: sorted(set(v)) for k, v in out.items()}}, "lossy": lossy}
    if target == "codex":
        fs = {"read-only": "read-only", "workdir": "workspace-write", "repo": "workspace-write", "any": "danger-full-access"}.get(sb.get("filesystem", "workdir"))
        decisions = {e for e in worst.values()} | ({"deny"} if skill_denied else set())
        cfg = {"approval_policy": "on-request" if decisions & {"ask", "deny"} else "never", "sandbox_mode": fs}
        if "deny" in decisions: lossy.append("deny: Codex config.toml cannot block single commands or hosts; denied actions are only gated by approval prompts (on-request)")
        if cmds: lossy.append("exec: per-command allow/deny is not expressed (Codex execpolicy rules are out of scope)")
        net = sb.get("network", "off")
        if fs == "workspace-write": cfg["sandbox_workspace_write"] = {"network_access": net == "on"}
        if net == "allowlist": lossy.append("network allowlist: needs a Codex permissions profile with network.domains and features.network_proxy; network_access left false")
        if fs == "danger-full-access": lossy.append("filesystem 'any' maps to danger-full-access: no sandbox")
        return {"config": cfg, "lossy": lossy}
    if target == "gemini-cli":
        g = {"allow": "allow", "ask": "ask_user", "deny": "deny"}
        rules = [{"toolName": "run_shell_command", "commandPrefix": f"{c_} ", "decision": g[bucket("exec")], "priority": 100} for c_ in cmds]
        if cmds: lossy.append("exec: commandPrefix 'cmd ' does not match the bare command without arguments (falls back to the default)")
        if not used("write"): pass
        elif lvl("write") == "any" or bucket("write") != "allow": rules.append({"toolName": ["write_file", "replace"], "decision": g[bucket("write")], "priority": 100})
        else: lossy.append("write: Gemini CLI rules cannot scope write_file/replace by path; left to the default (ask)")
        if not used("network"): pass
        elif lvl("network") == "any" or bucket("network") != "allow": rules.append({"toolName": "web_fetch", "decision": g[bucket("network")], "priority": 100})
        else: lossy.append("network: Gemini CLI rules cannot scope web_fetch by host; left to the default (ask)")
        if mcp_server:
            if "_" in mcp_server: lossy.append(f"MCP server name {mcp_server!r} contains '_': Gemini CLI may mis-parse it; rename the server")
            rules += [{"toolName": cap["entry"]["mcp_tool"], "mcpName": mcp_server, "decision": g[by.get(cap["id"], "deny")], "priority": 100}
                      for cap in contract["capabilities"] if cap.get("entry", {}).get("mcp_tool")]
        return {"config": {"rule": rules}, "lossy": lossy}
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
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "skillpact", "version": "0.7"}}},
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


# ---------------- migrate (0.x -> latest) ----------------
LATEST = KNOWN_VERSIONS[-1]
SCHEMA_URL = "https://kajisho5.github.io/skillpact/schema/v{}.json"


def migrate(c: dict, to: str = None) -> tuple[dict, list]:
    """Return (new_contract, changes). Pure function: never signs. Signatures over a changed contract are dropped."""
    to = to or LATEST
    if version_status(c.get("contract_version")) == "unknown_major": raise ValueError(f"cannot migrate from {c.get('contract_version')!r}")
    if to not in KNOWN_VERSIONS: raise ValueError(f"unknown target {to!r}")
    n = json.loads(json.dumps(c)); ch = []
    old = n.get("contract_version")
    if old != to: n["contract_version"] = to; ch.append(f"contract_version {old} -> {to}")
    if "$schema" in n and n["$schema"] != SCHEMA_URL.format(to): n["$schema"] = SCHEMA_URL.format(to); ch.append("$schema updated")
    for eff in EFFECTS:
        pe = n.get("permissions", {}).get(eff, {})
        if pe.get("level") == "scoped" and not pe.get("scope"): pe["scope"] = ["TODO(migrate)"]; ch.append(f"permissions.{eff}.scope was empty -> ['TODO(migrate)'] (SCOPE_EMPTY in >=0.4; confirm by hand)")
    for t in n.get("tests", {}).get("cases", []):
        if t.get("expect", {}).get("stdout_json_mode") == "last": ch.append(f"tests.{t['id']}: stdout_json_mode 'last' is legacy; prefer strict (not changed)")
    integ = n.get("integrity")
    if integ:
        if old != to and (tuple(map(int, str(old).split("."))) < JCS_FROM <= tuple(map(int, to.split(".")))): integ["canonicalization"] = "jcs"
        if old != to and _vt(old) < V08 <= _vt(to): ch.append("integrity.files: 0.8 requires every skill file to be listed; re-run `skillpact hash` before signing")
        if integ.get("signatures") and ch:
            integ["signatures"] = []; ch.append("integrity.signatures removed: contract changed (and canonicalization is JCS from 0.4); re-sign")
    return n, ch


def signature_roles(c) -> dict:
    """{key-or-identity: role}; role defaults to author. From 0.8 the role is part of the signed bytes."""
    out = {}
    for s_ in c.get("integrity", {}).get("signatures", []): out[sig_key(s_)] = s_.get("role", "author")
    return out


def trusted_author(c, trusted) -> bool:
    """True if a valid signature with role author was made by a trusted key/identity."""
    if _vt(c.get("contract_version", "0.1")) < V08: return False   # 0.8 errata: role is unsigned before 0.8 (relabel attack)
    res, roles = verify_signatures(c), signature_roles(c)
    return any(ok and k in trusted and roles.get(k, "author") == "author" for k, ok in res.items())


def expand_scope(scope):
    """Replace reserved tokens (@local) by concrete host globs for harness configs / runtime policies."""
    out = []
    for s_ in scope: out.extend(LOCAL_HOSTS if s_ == "@local" else [s_])
    return out
