"""skillpact CLI (SkillPact 0.8): validate | test | hash | keygen | sign | sign-sigstore | verify | policy-check | policy-compile | init | mcp-* | export | convert | owasp | conformance"""
import argparse, json, sys
from pathlib import Path
from . import core

def main(argv=None):
    ap = argparse.ArgumentParser(prog="skillpact")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("validate", "test", "hash", "verify"):
        p = sub.add_parser(n); p.add_argument("skill_dir"); p.add_argument("--contract")
        if n == "test": p.add_argument("--only", nargs="*"); p.add_argument("--no-net-sandbox", action="store_true"); p.add_argument("--skills-path", nargs="*"); p.add_argument("--pass-env", nargs="*", default=[], help="environment variables a case may receive through skip_unless_env (default: none)")
    p = sub.add_parser("keygen"); p.add_argument("key_path")
    p = sub.add_parser("sign"); p.add_argument("skill_dir"); p.add_argument("key_path"); p.add_argument("--signer", default=""); p.add_argument("--contract"); p.add_argument("--role", default="author", choices=["author", "reviewer", "scanner"])
    p = sub.add_parser("policy-check"); p.add_argument("skill_dir", nargs="+", help="one or more skill dirs, then the policy"); p.add_argument("policy"); p.add_argument("--contract")
    p = sub.add_parser("policy-compile"); p.add_argument("skill_dir", nargs="+"); p.add_argument("policy"); p.add_argument("--target", required=True, choices=["claude-code", "cursor", "codex", "gemini-cli"]); p.add_argument("--contract"); p.add_argument("--mcp-server"); p.add_argument("--render", action="store_true")
    p = sub.add_parser("compose", help="union of effects and dangerous combinations for a skill set"); p.add_argument("skill_dirs", nargs="+"); p.add_argument("--trusted-key", nargs="*", default=[])
    p = sub.add_parser("init"); p.add_argument("skill_dir"); p.add_argument("-o", "--output"); p.add_argument("--force", action="store_true"); p.add_argument("--from-native", nargs="+")
    p = sub.add_parser("mcp-check"); p.add_argument("skill_dir"); p.add_argument("--contract"); p.add_argument("server", nargs="+")
    p = sub.add_parser("mcp-annotations"); p.add_argument("skill_dir"); p.add_argument("--contract")
    p = sub.add_parser("export"); p.add_argument("skill_dir"); p.add_argument("policy"); p.add_argument("--format", required=True, choices=["hushspec", "rego", "aps", "acs"]); p.add_argument("--contract")
    p = sub.add_parser("sign-sigstore"); p.add_argument("skill_dir"); p.add_argument("--identity-token"); p.add_argument("--staging", action="store_true"); p.add_argument("--contract")
    p = sub.add_parser("convert"); p.add_argument("source"); p.add_argument("--to", choices=["mda", "autovault"]); p.add_argument("--from", dest="from_", choices=["mda", "autovault"]); p.add_argument("--contract"); p.add_argument("-o", "--output")
    p = sub.add_parser("owasp"); p.add_argument("skill_dir"); p.add_argument("--contract"); p.add_argument("--no-tests", action="store_true")
    p = sub.add_parser("migrate"); p.add_argument("skill_dir"); p.add_argument("--contract"); p.add_argument("--to"); p.add_argument("--write", action="store_true")
    p = sub.add_parser("conformance"); p.add_argument("skill_dir"); p.add_argument("--contract"); p.add_argument("--trusted-key", nargs="*", default=[])
    a = ap.parse_args(argv)
    cp = Path(a.contract) if getattr(a, "contract", None) else None
    if a.cmd == "validate": r = core.validate(a.skill_dir, cp)
    elif a.cmd == "test": r = core.run_tests(a.skill_dir, cp, a.only, not a.no_net_sandbox, a.skills_path or (), a.pass_env)
    elif a.cmd == "hash": r = {"ok": True, "files": core.hash_files(a.skill_dir, cp)}
    elif a.cmd == "keygen": r = {"ok": True, "public_key": core.keygen(a.key_path)}
    elif a.cmd == "sign": r = {"ok": True, "public_key": core.sign(a.skill_dir, a.key_path, a.signer, cp, a.role)}
    elif a.cmd == "verify":
        c, _ = core.load_contract(Path(a.skill_dir), cp); res = core.verify_signatures(c); v = core.validate(a.skill_dir, cp)
        r = {"ok": bool(res) and all(x is True for x in res.values()) and v["ok"], "signatures": res, "integrity_ok": v["ok"]}
    elif a.cmd in ("policy-check", "policy-compile") and len(a.skill_dir) > 1:
        from . import compose as _co
        pol = json.loads(Path(a.policy).read_text()); ents = [(core.load_contract(Path(d), None)[0], d, None) for d in a.skill_dir]
        if a.cmd == "policy-check": r = _co.match_policy_set(ents, pol); r["ok"] = r["decision"] != "deny"
        else: r = _co.compile_set(ents, pol, a.target); r["ok"] = True; r["target"] = a.target
    elif a.cmd == "compose":
        from . import compose as _co
        cs = [core.load_contract(Path(d), None)[0] for d in a.skill_dirs]
        tr = {c["skill"]["name"] for c in cs if c.get("integrity") and core.trusted_author(c, set(a.trusted_key))}
        r = _co.compose([(c["skill"]["name"], c) for c in cs], tr); r["ok"] = not r["paths"]
    elif a.cmd == "policy-check":
        a.skill_dir = a.skill_dir[0]; c, _ = core.load_contract(Path(a.skill_dir), cp); r = core.match_policy(c, json.loads(Path(a.policy).read_text()), a.skill_dir, cp); r["ok"] = r["decision"] != "deny"
    elif a.cmd == "policy-compile":
        a.skill_dir = a.skill_dir[0]; c, _ = core.load_contract(Path(a.skill_dir), cp); comp = core.compile_native(c, json.loads(Path(a.policy).read_text()), a.target, a.mcp_server, a.skill_dir, cp); cfg = comp["config"]
        from . import harness as _h
        fn, text = _h.render(a.target, cfg); errs = _h.validate_native(a.target, text)
        r = {"ok": not errs, "target": a.target, "file": fn, "schema_errors": errs, "config": cfg, "lossy": comp["lossy"]}
        if a.render: print(text, end=""); return 0 if not errs else 1
    elif a.cmd == "init":
        from . import init as _init
        c = _init.draft(a.skill_dir, a.from_native)
        out = Path(a.output) if a.output else Path(a.skill_dir) / core.CONTRACT_FILE
        if out.exists() and not a.force: r = {"ok": False, "error": f"{out} exists (use --force or -o)"}
        else:
            out.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n")
            r = {"ok": True, "path": str(out), "capabilities": len(c["capabilities"]), "uncertain": c.get("x", {}).get("init", {}).get("uncertain", [])}
    elif a.cmd == "mcp-check": r = core.mcp_check(a.skill_dir, a.server, None, cp)
    elif a.cmd == "mcp-annotations":
        c, _ = core.load_contract(Path(a.skill_dir), cp); r = {"ok": True, "tools": {x.get("entry", {}).get("mcp_tool", x["id"]): core.mcp_annotations(x) for x in c["capabilities"]}}
    elif a.cmd == "export":
        from . import export as _ex
        c, _ = core.load_contract(Path(a.skill_dir), cp); r = {"ok": True, "format": a.format, "document": _ex.export(c, json.loads(Path(a.policy).read_text()), a.format, a.skill_dir)}
    elif a.cmd == "sign-sigstore":
        from . import sigstore_sig
        r = {"ok": True, **sigstore_sig.sign(a.skill_dir, a.identity_token, cp, staging=a.staging)}
    elif a.cmd == "convert":
        from . import interop
        if bool(a.to) == bool(a.from_): r = {"ok": False, "error": "give exactly one of --to or --from"}
        elif a.to:
            c, cpath = core.load_contract(Path(a.source), cp); r = {"ok": True, **(interop.to_mda(c, cpath) if a.to == "mda" else interop.to_autovault(c, cpath))}
        else:
            src = Path(a.source); src = src / "SKILL.md" if src.is_dir() else src
            fm = core.read_frontmatter(src)[0] if src.suffix == ".md" else json.loads(src.read_text())
            c = interop.from_mda(fm) if a.from_ == "mda" else interop.from_autovault(fm)
            if a.output: Path(a.output).write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n")
            r = {"ok": True, "contract": c, "uncertain": c["x"]["import"]["uncertain"]}
    elif a.cmd == "owasp":
        from . import owasp
        c, _ = core.load_contract(Path(a.skill_dir), cp); t = None if a.no_tests else core.run_tests(a.skill_dir, cp)
        v_ = core.validate(a.skill_dir, cp); cov = v_["ok"] and not any(f["code"] in ("INTEGRITY_UNLISTED", "INTEGRITY_PATH") for f in v_["findings"])
        rows = owasp.assess(c, t, core.verify_signatures(c), cov); r = {"ok": True, "items": rows, "addressed": sum(x["status"] == "addressed" for x in rows)}
    elif a.cmd == "migrate":
        c, cpath = core.load_contract(Path(a.skill_dir), cp)
        try: n, ch = core.migrate(c, a.to)
        except ValueError as e: r = {"ok": False, "error": str(e)}
        else:
            if a.write and ch: cpath.write_text(json.dumps(n, ensure_ascii=False, indent=2) + "\n")
            r = {"ok": True, "from": c.get("contract_version"), "to": n["contract_version"], "changes": ch, "written": bool(a.write and ch),
                 "needs_resign": any("re-sign" in x for x in ch)}
    elif a.cmd == "conformance":
        # spec 0.8 s16.1: L1 = no validator errors; L2 = all cases pass in the sandbox with >= 1 network-isolated case;
        # L3 = L2 + every skill file covered by integrity + a valid author signature by a trusted key
        v = core.validate(a.skill_dir, cp); level = "none"; t = None; note = None; r_extra = {}
        if v["ok"]:
            level = "L1-declared"; t = core.run_tests(a.skill_dir, cp)
            if t["ok"] and not t.get("network_isolated"):
                note = "tests passed but no case ran network-isolated (no sandbox, or every case has network: true): L2 not granted (spec 0.8 s10)"
            elif t["ok"] and not t.get("fs_isolated"):   # 0.8.x erratum: the unshare fallback isolates the network only
                note = f"tests passed but the runner could not isolate the file system (sandbox: {t.get('sandbox')}; install bubblewrap): L2 not granted (spec 0.8 s10, s16.1)"
            elif t["ok"]:
                level = "L2-tested"; c, _ = core.load_contract(Path(a.skill_dir), cp)
                unl = [f["message"] for f in v["findings"] if f["code"] in ("INTEGRITY_UNLISTED", "INTEGRITY_PATH")]
                sig = core.verify_signatures(c); roles = core.signature_roles(c)
                if "integrity" not in c: pass
                elif unl: note = f"integrity does not cover every skill file ({len(unl)} problem(s), e.g. {unl[0]}): L3 not granted (spec 0.8 s11.2)"
                elif sig and not any(x is False for x in sig.values()):
                    r_ok = [k for k, ok in sig.items() if ok and k in a.trusted_key]
                    if core.trusted_author(c, set(a.trusted_key)): level = "L3-signed"
                    elif core._vt(c.get("contract_version", "0.1")) < core.V08: note = "contract_version < 0.8: the signer role is not signed, so L3 is not granted (0.8 errata); migrate and re-sign"
                    elif any(sig.get(k) is None for k in a.trusted_key): note = "the trusted Sigstore signature could not be verified here (install skillpact[sigstore]; the trust root needs network): L3 not granted"
                    elif r_ok: note = "only reviewer/scanner signatures are trusted: L3 needs a trusted author signature (spec 0.8 s11)"
                    else: note = "signature is valid but no --trusted-key matched: L3 not granted (spec 0.8 s11)"
                r_extra["attestations"] = [{"key": k, "role": roles.get(k, "author"), "trusted": k in a.trusted_key} for k, ok in sig.items() if ok and roles.get(k, "author") != "author"]
        r = {"ok": level != "none", "level": level, "validate_errors": v["errors"], "warnings": v["warnings"],
             "tests": {k: t.get(k) for k in ("passed", "total", "skipped", "network_cases", "sandbox", "fs_isolated", "error") if t.get(k) is not None} if t else None, **r_extra}
        if note: r["note"] = note
        if t:   # 0.8.x erratum: say which requirement failed, and which declared packages install start-up hooks
            bad = [f"{x['name']}: {x.get('reason', 'not found')}" for x in t.get("requirements", []) if not x["ok"]]
            hooks = {x["name"]: x["startup_hooks"] for x in t.get("requirements", []) if x.get("startup_hooks")}
            if bad: r["requirements_failed"] = bad
            if hooks: r["package_startup_hooks"] = hooks
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r.get("ok") else 1

if __name__ == "__main__": sys.exit(main())
