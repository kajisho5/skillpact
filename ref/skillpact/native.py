"""Adapter: kajisho5 '*-skill' native contract (`_contract.py contract --json`, contract_version 2.x) -> SkillPact contract 0.3.
Used by `init --from-native`. Heuristic but deterministic; everything not mappable goes to x.native."""
from __future__ import annotations
import re

NONSTD = {"cli", "common", "required", "positional"}
IDEMPOTENT = {"bit_exact", "content_equivalent", "cached"}


def _prop(v):
    out = {k: v2 for k, v2 in v.items() if k not in NONSTD}
    if "cli" in v: out["x-cli"] = v["cli"]
    if any(f in ("--json", "--json-brief", "--progress") for f in v.get("cli", [])): out["x-cli-only"] = True  # transport flags, not MCP args
    if out.get("type") == "path": out["type"] = "string"
    return out


def input_schema(ns, mcp):
    props = {k: _prop(v) for k, v in ns.get("properties", {}).items()}
    pos = ns.get("positional", []) or []
    for name in pos:
        props.setdefault(name, {"type": "string"})
        props[name]["x-positional"] = True
    exc = (mcp or {}).get("argument_exceptions", {})
    if "output" in exc: props.setdefault("output", {"type": "string"})["x-cli"] = [exc["output"]]
    sch = {"type": "object", "properties": props, "additionalProperties": bool(ns.get("additionalProperties", False))}
    req = [k for k, v in ns.get("properties", {}).items() if v.get("required")]
    req += [p for p in pos if p not in req and p not in ("more_sources",)]
    if req: sch["required"] = req
    allof = [{"not": {"required": list(pair)}} for pair in ns.get("mutually_exclusive", []) or []]
    allof += [{"anyOf": [{"required": [k]} for k in grp]} for grp in ns.get("one_of_required", []) or [] if grp]
    if allof: sch["allOf"] = allof
    return sch


def _ver(spec):
    m = re.search(r"(>=|>|==)?\s*([\d.]+)", spec or ""); return f"{m.group(1) or '>='}{m.group(2)}" if m else None


def native_to_contract(n: dict, skill_dir_name: str) -> dict:
    sk = n["skill"]; exe = n.get("execution", {}); req = n.get("requirements", {})
    name = sk.get("name") or skill_dir_name
    downloads = exe.get("model_downloads")
    prefix = "media." if "ffmpeg" in req else ("image." if "magick" in str(req.get("backends", "")) else "tool.")
    caps = []
    for t in n["tools"]:
        writes = bool(t.get("produces_artifact"))
        effects = ["read", "exec"] + (["write"] if writes else [])
        ce = []
        props = t["input_schema"].get("properties", {})
        if downloads and "transcribe" in props:
            ce.append({"effect": "network", "when": "--transcribe with an uncached speech model (model download; media never uploaded)", "scope": ["huggingface.co", "*.huggingface.co", "*.hf.co", "openaipublic.azureedge.net"]})
            ce.append({"effect": "exec", "when": "--transcribe: local speech engine CLI", "scope": ["whisper-cli", "whisper-cpp", "whisper", "parakeet-mlx", "parakeet-cli"]})
        caps_req = t.get("capabilities", {})
        bins = [x for x in caps_req.get("required", []) if ":" not in x]
        feats = [x for x in caps_req.get("required", []) if ":" in x]
        cap = {
            "id": prefix + t["name"], "summary": (t.get("description") or t["name"]).rstrip(",;: ")[:300], "role": t.get("role", ""),
            "entry": {"cli": ["python3", f"$SKILL_DIR/{t.get('executable', 'scripts/' + t['name'] + '.py')}"], "mcp_tool": (t.get("mcp") or {}).get("tool", t["name"])},
            "effects": effects, "destructive": bool(t.get("mutates_input")), "idempotent": t.get("idempotency_hint") in IDEMPOTENT,
            "dry_run": {"supported": bool(t.get("supports_dry_run")), "flag": "--dry-run",
                        "effects": ["read", "exec"] if t.get("role") in ("analysis", "analysis_and_execution", "verification") else ["read"]},
            "inputs": input_schema(t["input_schema"], t.get("mcp")),
            "outputs": t.get("output_schema", {"type": "object"}),
            "requires": sorted(set(bins) | {"python3"}), "requires_features": feats,
            "optional_features": [{"feature": o["capability"], "when": o.get("when", "")} for o in caps_req.get("optional", [])],
            "x": {"native": {k: t[k] for k in ("id", "idempotency_hint", "verification", "requires_visual_verification", "reencodes_video", "reencodes_audio") if k in t}},
        }
        if ce: cap["conditional_effects"] = ce
        cap["effect_scopes"] = {"exec": sorted(set(bins) | {"python3"})}
        caps.append(cap)
    bins = []
    if "backends" in req and "magick" in str(req["backends"]):
        bins.append({"name": "magick", "alternatives": ["sips"], "check": ["magick", "-version"], "version_regex": r"ImageMagick (\d+\.\d+\.\d+)"})
    for b in [k for k in req if k not in ("python", "node", "backends")]:
        if True:
            bins.append({"name": b, "version": _ver(req[b]), "check": [b, "-version"], "version_regex": (b + r" version n?(\d+\.\d+)") if b in ("ffmpeg", "ffprobe") else r"(\d+\.\d+(?:\.\d+)?)",
                         **({"features_check": {"filter": ["ffmpeg", "-hide_banner", "-filters"], "encoder": ["ffmpeg", "-hide_banner", "-encoders"],
                                                 "decoder": ["ffmpeg", "-hide_banner", "-decoders"], "muxer": ["ffmpeg", "-hide_banner", "-muxers"]}} if b == "ffmpeg" else {})})
    has_dl = any("conditional_effects" in c for c in caps)
    return {
        "contract_version": "0.3", "kind": "tool",
        "skill": {"name": name, "version": sk.get("version", "0.0.0"), "license": sk.get("license", "MIT"),
                  "source": sk.get("repository", ""), "native_contract": {"cli": ["python3", "$SKILL_DIR/scripts/_contract.py", "contract", "--json"]}},
        "requirements": {"binaries": bins, "runtimes": [{"name": "python3", "version": _ver(req.get("python", ">=3.9")), "check": ["python3", "--version"]}]},
        "permissions": {
            "read": {"level": "scoped", "scope": ["$INPUT", "$INPUT_DIR/**", "$SKILL_DIR/**"], "why": "reads the media the user names (and sidecars next to it)"},
            "write": {"level": "scoped", "scope": ["$OUTPUT", "$INPUT_DIR/**", "$WORKDIR/**", "$TMPDIR/**"], "why": "writes new artifacts (default next to the input); never modifies the input; --overwrite required to replace", "confirm": "never"},
            "network": {"level": "scoped", "scope": ["huggingface.co", "*.huggingface.co", "*.hf.co", "openaipublic.azureedge.net"], "why": "only speech-model download on first --transcribe; HF_HUB_OFFLINE=1 disables"} if has_dl else {"level": "none"},
            "exec": {"level": "scoped", "scope": ["python3"] + [b["name"] for b in bins] + (["whisper-cli", "whisper-cpp", "whisper", "parakeet-mlx", "parakeet-cli"] if has_dl else []), "why": "argv lists only, no shell (" + str(exe.get("subprocess", ""))[:120] + ")"},
            "spend": {"level": "none"}, "send": {"level": "none"},
        },
        "capabilities": caps,
        "x": {"native": {"contract_version": n.get("contract_version"), "removed": n.get("removed"), "deprecated": n.get("deprecated")}},
    }
