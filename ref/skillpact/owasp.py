"""Map a SkillPact contract onto the OWASP Agentic Skills Top 10 (https://owasp.org/www-project-agentic-skills-top-10/, 2026).
status: addressed = the contract gives machine-checkable evidence; partial = helps but does not settle it; out_of_scope."""
from . import core

def _scoped(c, e): return c.get("permissions", {}).get(e, {}).get("level", "none") in ("none", "scoped")

def assess(c, test_result=None, sig_result=None, coverage_ok=False):
    perms = c.get("permissions", {}); caps = c.get("capabilities", [])
    signed = bool(sig_result) and all(sig_result.values()); hashed = bool(c.get("integrity", {}).get("files"))
    tested = bool(test_result and test_result.get("ok")); ntests = len(c.get("tests", []))
    scoped_all = all(_scoped(c, e) for e in ("read", "write", "network", "exec"))
    R = lambda id_, name, status, evidence, gap="": {"id": id_, "name": name, "status": status, "evidence": evidence, "gap": gap}
    return [
        R("AST01", "Malicious Skills", "partial", f"declared effects per tool ({len(caps)} capabilities) + {ntests} conformance tests" + (" passed" if tested else ""),
          "a contract cannot prove absence of malice; runtime enforcement (APS/ACS/HushSpec export) and review still needed"),
        R("AST02", "Supply Chain Compromise", "partial",
          f"sha256 over {len(c.get('integrity', {}).get('files', {}))} files (every skill file covered: {coverage_ok}); signatures valid={signed}",
          "a signature shows who signed, not that the code is safe; dependencies outside the skill directory are not covered" + ("" if signed and coverage_ok else "; sign with full file coverage (spec 0.8 s11.2)")),
        R("AST03", "Over-Privileged Skills", "addressed" if scoped_all else "partial",
          "explicit per-effect permissions with path/host/command scopes; policy-check denies unscoped grants",
          "" if scoped_all else "some effects are level=any: " + ", ".join(e for e in ("read", "write", "network", "exec") if not _scoped(c, e))),
        R("AST04", "Insecure Metadata", "addressed" if signed and coverage_ok else "partial", "JSON Schema validation (unknown keys only under x.<vendor>), I-JSON parsing, JCS signing input including the signer role",
          "" if signed and coverage_ok else "unsigned or not fully covered"),
        R("AST05", "Untrusted External Instructions", "partial", "network scope lists every host the skill may contact",
          "content fetched from those hosts is not covered"),
        R("AST06", "Weak Isolation", "partial", "conformance tests run in a sandbox (bubblewrap: read-only filesystem, no network, allowlisted environment); policy-compile emits harness permission config and reports what it cannot express",
          "only the tests are sandboxed; the harness must enforce isolation when the skill really runs"),
        R("AST07", "Update Drift", "addressed" if hashed and signed and coverage_ok else "partial", "version + hashes of every skill file; a change to any covered file breaks verification",
          "" if hashed and signed and coverage_ok else "files outside integrity.files are not protected; harness must re-verify before each run (TOCTOU)"),
        R("AST08", "Poor Scanning", "partial",
          "author-declared behaviour checked by executable tests" + (" (passed)" if tested else ""),
          "tests are written by the author and cover only what they exercise; complements scanners, does not replace them"),
        R("AST09", "No Governance", "partial", "harness policy files (first-match rules, decision_worst_case) are versionable and reviewable", "org process not covered"),
        R("AST10", "Cross-Platform Reuse", "partial", "one contract compiles to Claude Code / Cursor / Codex / Gemini CLI configs; MDA/AutoVault interop",
          "each target loses some constraints; policy-compile lists them in 'lossy'"),
    ]
