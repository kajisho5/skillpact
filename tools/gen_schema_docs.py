#!/usr/bin/env python3
"""Generate docs/schema/index.html from docs/schema/*.json + real examples.
Run from repo root:  python3 tools/gen_schema_docs.py   (stdlib only)."""
import json, html, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://kajisho5.github.io/skillpact/"
VERSIONS = sorted((q.stem[1:] for q in (ROOT / "docs/schema").glob("v*.json")), key=lambda v: tuple(map(int, v.split("."))))
VER = VERSIONS[-1]  # latest published contract schema
C = json.loads((ROOT / f"docs/schema/v{VER}.json").read_text())
P = json.loads((ROOT / "docs/schema/policy-v0.3.json").read_text())
SAMPLE = json.loads((ROOT / "samples/ffmpeg-skill/skill.contract.json").read_text())
POL = {p.stem: json.loads(p.read_text()) for p in sorted((ROOT / "examples/policies").glob("*.json"))}
EFFECTS = ["read", "write", "network", "exec", "spend", "send"]

DESC = {
 "$schema": "URL of the schema this file conforms to.",
 "contract_version": "SkillPact contract version. New contracts should use \"" + VER + "\".",
 "kind": "tool = has executable entries; instructions = SKILL.md-only skill.",
 "skill": "Identity of the skill described by the neighbouring SKILL.md.",
 "skill.name": "Kebab-case skill name (≤ 64 chars), same as SKILL.md.",
 "skill.version": "SemVer version of the skill.",
 "skill.native_contract": "Optional command that prints the skill's own native contract (cross-checked by conformance).",
 "compat": "Which agents, OSes and interfaces the skill supports.",
 "requirements": "Binaries, runtimes, env vars, other skills and packages the skill needs.",
 "permissions": "Upper bound of every effect the skill may have. All six effects MUST be declared, even when level is none.",
 "permissions.*.level": "none = never; scoped = only within scope; any = unrestricted.",
 "permissions.*.why": "Human-readable justification shown at install time.",
 "permissions.*.confirm": "When the harness should ask the user: never, each call, or once per session.",
 "capabilities": "Every tool / command the skill exposes, with its effects. At least one.",
 "capabilities[].effects": "Subset of the six effects this capability may cause.",
 "capabilities[].destructive": "True if it can delete or overwrite user data (drives ask_on_destructive).",
 "capabilities[].dry_run": "Whether a dry-run flag exists and what effects remain under it.",
 "tests": "Conformance tests. Run with the network cut off unless a case sets network: true. Passing = level L2.",
 "integrity": "SHA-256 of every shipped file plus signatures. Hashes + a trusted signature = level L3.",
 "integrity.signatures": "ed25519 (key + sig) or Sigstore keyless (identity + issuer + bundle).",
 "x": "Vendor extensions, namespaced x.<vendor>.<key>.",
 "policy_version": "Harness policy version.",
 "defaults": "Decision per effect when no rule matches. All six effects required.",
 "rules": "Scoped overrides; matched against the scopes declared in the contract.",
 "rules[].scope": "Glob patterns matched against the contract's declared scope.",
 "skills": "Explicit allow / deny lists of skill names.",
 "require_signature": "Only accept L3 (signed) contracts.",
 "trusted_keys": "ed25519 public keys accepted for require_signature.",
 "ask_on_destructive": "Force ask for capabilities marked destructive, even if otherwise allowed.",
 "never_auto_allow_any": "Effects that are never auto-allowed when declared with level any.",
 "limits": "Run budgets compiled into harness configs where supported.",
 "sandbox": "Filesystem / network sandbox mode for harnesses that support it.",
 "hooks": "Commands run before / after each action.",
 "audit": "Audit logging (OpenTelemetry GenAI conventions, log path).",
}

def esc(s): return html.escape(str(s))

def resolve(node, root):
    while "$ref" in node:
        node = root["$defs"][node["$ref"].split("/")[-1]]
    return node

def typ(n, root):
    ref = n.get("$ref", "").split("/")[-1]
    n2 = resolve(n, root)
    if "const" in n2: return "const"
    if "enum" in n2: return "enum"
    t = n2.get("type", "any")
    if t == "array":
        it = resolve(n2.get("items", {}), root)
        inner = ref if ref in ("command",) else ("object" if it.get("type") == "object" else ("enum" if "enum" in it else it.get("type", "any")))
        return f"array&lt;{esc(inner)}&gt;"
    if t == "object" and ref: return f"object · {esc(ref)}"
    return esc(t)

def allowed(n, root):
    n = resolve(n, root)
    if n.get("type") == "array": n = resolve(n.get("items", {}), root)
    if "const" in n: return [n["const"]]
    return n.get("enum", [])

def rows(node, root, path="", depth=0, seen=()):
    node = resolve(node, root)
    req = set(node.get("required", []))
    out = []
    for k, v in node.get("properties", {}).items():
        p = f"{path}.{k}" if path else k
        vr = resolve(v, root)
        key = p
        if path.startswith("permissions.") : key = "permissions.*." + k
        d = DESC.get(key) or DESC.get(p) or v.get("description") or vr.get("description", "")
        extra = []
        if "pattern" in vr: extra.append(f"pattern <code>{esc(vr['pattern'])}</code>")
        if "maxLength" in vr: extra.append(f"max {vr['maxLength']} chars")
        out.append((p, typ(v, root), k in req, d, allowed(v, root), extra, depth))
        ref = v.get("$ref", "") or vr.get("items", {}).get("$ref", "") if vr.get("type") in ("object","array") or "$ref" in v else ""
        child = vr
        cp = p
        if vr.get("type") == "array" and isinstance(vr.get("items"), dict):
            child = resolve(vr["items"], root); cp = p + "[]"
        if vr.get("type") == "object" and "additionalProperties" in vr and isinstance(vr["additionalProperties"], dict) and not vr.get("properties"):
            child = resolve(vr["additionalProperties"], root); cp = p + ".<name>"
        if child.get("properties") and depth < 4 and id(child) not in seen:
            if p == "permissions":
                out += rows(root["$defs"]["permEntry"], root, "permissions.<effect>", depth + 1, seen + (id(child),))
            else:
                out += rows(child, root, cp, depth + 1, seen + (id(child),))
    return out

def table(schema, anchor):
    h = ['<div class="tw"><table class="ft"><thead><tr><th>Field</th><th>Type</th><th>Req.</th><th>Description / allowed values</th></tr></thead><tbody>']
    for p, t, r, d, al, extra, depth in rows(schema, schema):
        vals = " ".join(f"<code class=v>{esc(json.dumps(a))}</code>" for a in al)
        h.append(f'<tr class="d{depth}" id="{anchor}-{esc(p.replace("[]","").replace("<","").replace(">",""))}"><td><code class="f">{esc(p)}</code></td><td><span class=t>{t}</span></td>'
                 f'<td>{"<span class=req>required</span>" if r else "<span class=opt>optional</span>"}</td>'
                 f'<td>{esc(d)}{"<div class=vals>"+vals+"</div>" if vals else ""}{"<div class=x>"+" · ".join(extra)+"</div>" if extra else ""}</td></tr>')
    h.append("</tbody></table></div>")
    return "\n".join(h)

def snip(obj, title, src):
    s = json.dumps(obj, indent=2, ensure_ascii=False)
    return f'<figure class="code"><figcaption><span>{esc(title)}</span><span class=src>{esc(src)}</span><button class=cp type=button>Copy</button></figcaption><pre><code>{esc(s)}</code></pre></figure>'

def trim_cap(c):
    c = dict(c); ins = c.get("inputs", {}).get("properties", {})
    if ins:
        c["inputs"] = {"type": "object", "properties": {k: ins[k] for k in list(ins)[:2]}, "…": f"{len(ins)-2} more inputs"}
    c.pop("outputs", None); c["summary"] = c["summary"][:90] + ("…" if len(c["summary"]) > 90 else "")
    return c

def examples():
    s = SAMPLE; src = "samples/ffmpeg-skill/skill.contract.json"
    header = {k: s[k] for k in ("$schema", "contract_version", "kind", "skill")}
    caps = s["capabilities"]
    destr = next((c for c in caps if c.get("destructive")), caps[0])
    integ = {"algorithm": s["integrity"]["algorithm"],
             "files": dict(list(s["integrity"]["files"].items())[:2] + [("…", f"{len(s['integrity']['files'])-2} more files")]),
             "signatures": s["integrity"]["signatures"]}
    return {
      "header": snip(header, "Header & identity", src),
      "perm": snip(s["permissions"], "permissions — all six effects", src),
      "cap": snip(trim_cap(caps[0]), f"capabilities[] — {caps[0]['id']} (1 of {len(caps)})", src),
      "test": snip(s["tests"]["cases"][0], f"tests.cases[] (1 of {len(s['tests']['cases'])})", src),
      "integ": snip(integ, "integrity — hashes + ed25519 signature", src),
    }

CSS = (ROOT / "docs/assets/site.css").read_text() if (ROOT / "docs/assets/site.css").exists() else ""

def main():
    ex = examples()
    caps = SAMPLE["capabilities"]
    pol_snips = "".join(snip(v, f"examples/policies/{k}.json", "example policy") for k, v in POL.items())
    eff_desc = {"read": "Reads files or data", "write": "Creates or modifies files", "network": "Talks to hosts over the network",
                "exec": "Runs other programs", "spend": "Spends money / paid quota", "send": "Sends messages to people or services"}
    eff_cards = "".join(f'<div class="eff e-{e}"><b>{e}</b><span>{eff_desc[e]}</span><small>ffmpeg-skill: {esc(SAMPLE["permissions"][e]["level"])}</small></div>' for e in EFFECTS)
    OLDER = "".join(f'<a class="pill" href="v{v}.json">v{v}.json <small>older</small></a>' for v in reversed(VERSIONS[:-1]))
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Schema reference v{VER} — SkillPact · SEVENTHWELL</title>
<meta name="description" content="Field-by-field reference for skill.contract.json and harness policy (SkillPact v{VER}).">
<link rel="canonical" href="{BASE}schema/"><link rel="stylesheet" href="../assets/site.css">
</head><body>
<header class="top"><div class="wrap nav"><a class="brand" href="../"><span class="logo">◆</span> SkillPact <small>by SEVENTHWELL</small></a>
<nav><a href="../">Home</a><a href="#contract" >Contract</a><a href="#policy">Policy</a><a href="https://github.com/kajisho5/skillpact">GitHub</a></nav></div></header>
<main class="wrap">
<section class="hero sm"><p class="eyebrow">Schema reference · draft v{VER}</p><h1>skill.contract.json &amp; harness policy</h1>
<p class="lead">Every field, its type, whether it is required, and the allowed values — with real snippets from the signed <b>ffmpeg-skill</b> contract ({len(caps)} capabilities, {len(SAMPLE['tests']['cases'])} tests).</p>
<div class="pills"><a class="pill" href="v{VER}.json">v{VER}.json <small>contract</small></a>{OLDER}<a class="pill" href="policy-v0.3.json">policy-v0.3.json <small>policy</small></a></div>
<pre class="ids"><code>{esc(C['$id'])}
{esc(P['$id'])}</code></pre></section>

<section><h2 id="effects">The six effects</h2><p>Every contract declares a level for each effect (<code>none</code> · <code>scoped</code> · <code>any</code>); every capability lists the effects it may cause.</p>
<div class="effs">{eff_cards}</div></section>

<section><h2 id="levels">Conformance levels</h2><div class="levels">
<div class="lv"><span class="badge l1">L1</span><b>declared</b><p>Valid against the contract schema.</p></div>
<div class="lv"><span class="badge l2">L2</span><b>tested</b><p><code>tests.cases</code> pass with the network cut off.</p></div>
<div class="lv"><span class="badge l3">L3</span><b>signed</b><p><code>integrity</code> hashes match and a trusted ed25519 / Sigstore signature verifies.</p></div></div></section>

<section><h2 id="decisions">Policy decisions</h2><div class="levels">
<div class="lv"><span class="badge allow">allow</span><p>Run without asking.</p></div>
<div class="lv"><span class="badge ask">ask</span><p>Ask the user first.</p></div>
<div class="lv"><span class="badge deny">deny</span><p>Block install or call.</p></div></div></section>

<section><h2 id="contract">Contract fields <small>skill.contract.json</small></h2>
<details open><summary>Field table</summary>{table(C, "c")}</details>
<h3>Examples from ffmpeg-skill</h3>{ex['header']}{ex['perm']}{ex['cap']}{ex['test']}{ex['integ']}</section>

<section><h2 id="policy">Policy fields <small>harness policy</small></h2>
<details open><summary>Field table</summary>{table(P, "p")}</details>
<h3>Example policies</h3>{pol_snips}</section>
</main>
<footer class="wrap foot">Generated by <code>tools/gen_schema_docs.py</code> from the JSON schemas · Spec CC BY 4.0 · code Apache-2.0 · © 2026 SEVENTHWELL</footer>
<script>document.querySelectorAll('.cp').forEach(b=>b.onclick=()=>{{const t=b.closest('figure').querySelector('code').innerText;navigator.clipboard&&navigator.clipboard.writeText(t);b.textContent='Copied';setTimeout(()=>b.textContent='Copy',1200)}})</script>
</body></html>
"""
    (ROOT / "docs/schema/index.html").write_text(page)
    print("wrote docs/schema/index.html")

if __name__ == "__main__":
    main()
