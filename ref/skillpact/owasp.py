"""Map a SkillPact contract onto the OWASP Agentic Skills Top 10 (https://owasp.org/www-project-agentic-skills-top-10/, 2026).
status: addressed = the contract gives machine-checkable evidence; partial = helps but does not settle it; out_of_scope."""
from . import core

def _scoped(c, e): return c.get("permissions", {}).get(e, {}).get("level", "none") in ("none", "scoped")

def assess(c, test_result=None, sig_result=None):
    perms = c.get("permissions", {}); caps = c.get("capabilities", [])
    signed = bool(sig_result) and all(sig_result.values()); hashed = bool(c.get("integrity", {}).get("files"))
    tested = bool(test_result and test_result.get("ok")); ntests = len(c.get("tests", []))
    scoped_all = all(_scoped(c, e) for e in ("read", "write", "network", "exec"))
    R = lambda id_, name, status, evidence, gap="": {"id": id_, "name": name, "status": status, "evidence": evidence, "gap": gap}
    return [
        R("AST01", "Malicious Skills", "partial", f"declared effects per tool ({len(caps)} capabilities) + {ntests} conformance tests" + (" passed" if tested else ""),
          "a contract cannot prove absence of malice; runtime enforcement (APS/ACS/HushSpec export) and review still needed"),
        R("AST02", "Supply Chain Compromise", "addressed" if signed and hashed else "partial",
          f"sha256 over {len(c.get('integrity', {}).get('files', {}))} files; signatures valid={signed}", "" if signed else "sign with ed25519 or Sigstore"),
        R("AST03", "Over-Privileged Skills", "addressed" if scoped_all else "partial",
          "explicit per-effect permissions with path/host/command scopes; policy-check denies unscoped grants",
          "" if scoped_all else "some effects are level=any: " + ", ".join(e for e in ("read", "write", "network", "exec") if not _scoped(c, e))),
        R("AST04", "Insecure Metadata", "addressed", "JSON Schema validation (unknown keys only under x.<vendor>), canonical JSON signed", ""),
        R("AST05", "Untrusted External Instructions", "partial", "network scope lists every host the skill may contact",
          "content fetched from those hosts is not covered"),
        R("AST06", "Weak Isolation", "partial", "conformance tests run network-isolated (unshare -rn); policy-compile emits harness sandbox/permission config",
          "host must enforce; SkillPact does not sandbox at runtime"),
        R("AST07", "Update Drift", "addressed" if hashed else "partial", "version + file hashes; any change breaks the signature and requires re-sign", ""),
        R("AST08", "Poor Scanning", "addressed" if tested else "partial",
          "author-declared behaviour checked by executable tests (declare+test+sign) instead of relying on a scanner verdict",
          "" if tested else "run `skillpact test`"),
        R("AST09", "No Governance", "partial", "harness policy files (first-match rules, decision_worst_case) are versionable and reviewable", "org process not covered"),
        R("AST10", "Cross-Platform Reuse", "addressed", "one contract compiles to Claude Code / Cursor / Codex / Gemini CLI configs; MDA/AutoVault interop", ""),
    ]
