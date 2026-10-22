"""`skillpact init`: draft a contract from an existing skill. Uncertain fields are listed in x.init.uncertain
(JSON pointers) and carry a 'TODO(init)' why — a human must confirm them before claiming L1."""
from __future__ import annotations
import json, re, subprocess
from pathlib import Path
from .core import read_frontmatter, LATEST

BIN_HINTS = ["ffmpeg", "ffprobe", "magick", "gh", "git", "node", "npx", "docker", "curl", "sips", "exiftool", "yt-dlp", "whisper"]
NET = re.compile(r"\b(https?://|api\b|REST|GraphQL|token|upload|download|fetch|webhook|cloud)", re.I)
SEND = re.compile(r"\b(send (an )?email|slack|post to|tweet|publish|notify|open (a )?(PR|pull request|issue)|comment on)", re.I)
SPEND = re.compile(r"\b(purchase|payment|checkout|stripe|billing|paid API|credits)\b", re.I)
WRITE = re.compile(r"(\s-o\s|--output|writes?\b|creates?\b|generat|overwrit|commit|apply)", re.I)
TODO = "TODO(init): confirm"
SUB = re.compile(r"""add_parser\(\s*["']([A-Za-z0-9_-]+)["']""")
MCP = re.compile(r"""@\w+\.tool\([^)]*\)\s*\n\s*(?:async\s+)?def\s+(\w+)|Tool\(\s*name\s*=\s*["']([\w.-]+)["']""")
READ_ONLY_SUBS = {"doctor", "validate", "check", "contract", "plan", "list", "info", "version", "inspect", "probe", "status", "lint", "verify"}
URL = re.compile(r"https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
GENERIC_HEADINGS = {"overview", "usage", "install", "installation", "requirements", "notes", "license", "examples", "example", "setup", "security", "troubleshooting", "references", "faq", "when to use", "description"}


def _slug(x): return re.sub(r"[^a-z0-9]+", "-", x.lower()).strip("-")


def _module_file(d: Path, mod: str):
    for base in (d / "src", d):
        p = base.joinpath(*mod.split(".")).with_suffix(".py")
        if p.exists(): return p
    return None


def _version(d: Path):
    if (d / "package.json").exists():
        try: return json.loads((d / "package.json").read_text()).get("version"), "package.json"
        except Exception: pass
    if (d / "pyproject.toml").exists():
        m = re.search(r'^version\s*=\s*"([^"]+)"', (d / "pyproject.toml").read_text(), re.M)
        if m: return m.group(1), "pyproject.toml"
    return None, None


def draft(skill_dir, from_native=None) -> dict:
    d = Path(skill_dir).resolve()
    fm, body = read_frontmatter(d / "SKILL.md")
    fm = fm or {}
    unc = []
    native_cmd = from_native
    if native_cmd is None and (d / "scripts" / "_contract.py").exists(): native_cmd = ["python3", "scripts/_contract.py", "contract", "--json"]
    if native_cmd:
        try:
            out = subprocess.run(native_cmd, cwd=d, capture_output=True, text=True, timeout=60)
            n = json.loads(out.stdout)
            if "tools" in n:
                from .native import native_to_contract
                c = native_to_contract(n, d.name); c["skill"]["name"] = fm.get("name", c["skill"]["name"])
                c.setdefault("x", {})["init"] = {"source": "native", "uncertain": ["/permissions/read/scope", "/permissions/write/scope", "/compat"]}
                return c
        except Exception: pass
    body = str(fm.get("description", "")) + "\n" + body
    text = body + "\n".join(p.read_text(errors="ignore")[:20000] for p in sorted((d / "scripts").glob("*.py"))[:60]) if (d / "scripts").exists() else body
    src_text = "\n".join(p.read_text(errors="ignore")[:20000] for p in sorted((d / "src").rglob("*.py"))[:80]) if (d / "src").exists() else ""
    ver, vsrc = _version(d)
    if not ver: ver = "0.0.0"; unc.append("/skill/version")
    bins = [b for b in BIN_HINTS if re.search(rf"(?<![\w-]){re.escape(b)}(?![\w-])", text + src_text)]
    scripts = sorted(p for p in (d / "scripts").glob("*.py") if not p.name.startswith("_")) if (d / "scripts").exists() else []
    pyproj = (d / "pyproject.toml").read_text() if (d / "pyproject.toml").exists() else ""
    entry_pts = re.findall(r'^([\w-]+)\s*=\s*"([\w.]+):(\w+)"', pyproj.split("[project.scripts]", 1)[1].split("\n[", 1)[0], re.M) if "[project.scripts]" in pyproj else []
    if entry_pts: scripts = []  # packaged skill: console scripts are the interface; scripts/ is usually repo tooling
    mcp_scripts = [p for p in scripts if "mcp" in p.stem]
    scripts = [p for p in scripts if p not in mcp_scripts]
    kind = "tool" if (scripts or entry_pts or bins) else "instructions"
    def perm(level, rx, eff, scope=None):
        hit = bool(rx.search(text + (src_text if eff == "write" else ""))) if rx else level != "none"
        if not hit: return {"level": "none"}
        unc.append(f"/permissions/{eff}")
        return {"level": "scoped", "scope": scope or ["TODO(init)"], "why": f"{TODO}: heuristic match in SKILL.md/scripts"}
    perms = {"read": {"level": "scoped", "scope": ["$INPUT", "$SKILL_DIR/**"], "why": f"{TODO}"} if kind == "tool" else {"level": "none"},
             "write": perm("scoped", WRITE, "write", ["$OUTPUT", "$WORKDIR/**"]) if kind == "tool" else {"level": "none"},
             "network": perm("scoped", NET, "network", sorted({h.lower() for h in URL.findall(text)} - {"example.com", "github.com"})[:10] or ["TODO(init)"]) if kind == "tool" else {"level": "none"},
             "exec": {"level": "scoped", "scope": sorted(set(bins) | {"python3"}), "why": TODO} if kind == "tool" else {"level": "none"},
             "spend": perm("scoped", SPEND, "spend") if kind == "tool" else {"level": "none"},
             "send": perm("scoped", SEND, "send") if kind == "tool" else {"level": "none"}}
    unc.append("/permissions/read")
    def effs():
        return [e for e in ("read", "write", "network", "exec", "spend", "send") if perms[e]["level"] != "none"]
    caps = []
    for s in scripts:
        subs = list(dict.fromkeys(SUB.findall(s.read_text(errors="ignore"))))
        for sub in subs or [None]:
            caps.append({"id": "tool." + _slug(s.stem) + (f".{_slug(sub)}" if sub else ""), "summary": f"{TODO} — scripts/{s.name}" + (f" {sub}" if sub else ""),
                         "entry": {"cli": ["python3", f"$SKILL_DIR/scripts/{s.name}"] + ([sub] if sub else [])}, "effects": effs()})
    for m_ in mcp_scripts:
        caps.append({"id": "mcp." + re.sub(r"[^a-z0-9]+", "-", m_.stem.lower()).strip("-"), "summary": f"{TODO} — MCP stdio server scripts/{m_.name}",
                     "entry": {"mcp_tool": "TODO", "doc": f"scripts/{m_.name}"}, "effects": effs()})
    def sub_effects(sub):  # 0.8.x: per-subcommand guess; read-only verbs get read (+exec) only
        e = effs()
        return [x for x in e if x in ("read", "exec")] if sub in READ_ONLY_SUBS else e
    for name, mod, fn in entry_pts:
        base = ["python3", "-m", mod]
        mf = _module_file(d, mod); subs = list(dict.fromkeys(SUB.findall(mf.read_text(errors="ignore")))) if mf else []
        if not subs:
            caps.append({"id": "cli." + _slug(name), "summary": f"{TODO} — console script {name} ({mod}:{fn})", "entry": {"cli": base}, "effects": effs()})
        for sub in subs:
            caps.append({"id": f"cli.{_slug(name)}.{_slug(sub)}", "summary": f"{TODO} — `{name} {sub}` ({mod}:{fn})",
                         "entry": {"cli": base + [sub]}, "effects": sub_effects(sub)})
    for f in sorted(((d / "src").rglob("*.py") if (d / "src").exists() else [])) + mcp_scripts:
        for a, b in MCP.findall(f.read_text(errors="ignore")):
            caps.append({"id": "mcp." + _slug(a or b), "summary": f"{TODO} — MCP tool {a or b} ({f.relative_to(d)})",
                         "entry": {"mcp_tool": a or b, "doc": str(f.relative_to(d))}, "effects": effs()})
    if not caps and kind == "instructions":
        for h in re.findall(r"^##\s+(.+?)\s*$", body, re.M):
            if h.strip().lower() not in GENERIC_HEADINGS and len(caps) < 12:
                caps.append({"id": "guide." + _slug(h), "summary": f"{TODO} — SKILL.md section \"{h.strip()}\"", "entry": {"doc": "SKILL.md"}, "effects": []})
    if not caps:
        caps = [{"id": "guide", "summary": (fm.get("description") or "instructions")[:300], "entry": {"doc": "SKILL.md"}, "effects": []}]
    unc.append("/capabilities")
    c = {"contract_version": LATEST, "kind": kind,
         "skill": {"name": fm.get("name", d.name), "version": ver, **({"license": fm["license"]} if fm.get("license") else {})},
         "compat": {"agents": {a: {"status": "expected"} for a in ("claude-code", "cursor", "codex")}, "interfaces": ["skill-md"] + (["cli"] if kind == "tool" else [])},
         "requirements": {"binaries": [{"name": b, "check": [b, "--version"]} for b in bins if b not in ("python3",)],
                          "runtimes": [{"name": "python3", "version": ">=3.9", "check": ["python3", "--version"]}] if kind == "tool" else []},
         "permissions": perms, "capabilities": caps,
         "tests": {"cases": [{"id": f"{x['id']}-help", "capability": x["id"], "run": x["entry"]["cli"] + ["--help"], "expect": {"exit_code": 0}} for x in caps if x.get("entry", {}).get("cli")]},
         "x": {"init": {"source": "heuristic", "version_from": vsrc, "uncertain": sorted(set(unc))}}}
    if bins: unc.append("/requirements/binaries")
    if (d / "pyproject.toml").exists() and "src" in [p.name for p in d.iterdir()]:
        for t in c["tests"]["cases"]: t["env"] = {"PYTHONPATH": "$SKILL_DIR/src"}
    pk = re.findall(r'"([A-Za-z0-9_.-]+)\s*([<>=!~][^"]*)?"', pyproj.split("dependencies", 1)[1].split("]", 1)[0]) if "dependencies" in pyproj else []
    if pk: c["requirements"]["packages"] = [{"ecosystem": "pypi", "name": a, **({"version": b} if b else {}), **({"import": "PIL"} if a.lower() == "pillow" else {})} for a, b in pk]
    c["x"]["init"]["uncertain"] = sorted(set(unc))
    return c
