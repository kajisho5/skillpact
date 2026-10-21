# SkillPact × OWASP Agentic Skills Top 10 (2026) — mapping (draft 0.3)

`skillpact owasp <skill_dir>` prints this per skill. Statuses: **addressed** = the contract gives machine-checkable evidence, **partial** = it helps but does not settle the risk.

| ID | Risk | SkillPact mechanism | Status (generic) | Remaining gap |
|---|---|---|---|---|
| AST01 | Malicious Skills | per-tool declared effects + conformance tests + policy-check | partial | cannot prove absence of malice → runtime enforcement (APS / ACS / HushSpec) + review |
| AST02 | Supply Chain Compromise | sha256 of every file + ed25519 or Sigstore signature, trusted-key list | addressed when signed | key management by publisher |
| AST03 | Over-Privileged Skills | 6 effect classes (read/write/network/exec/spend/send) with scopes; policy denies unscoped grants | addressed when all scoped | — |
| AST04 | Insecure Metadata | JSON Schema (draft 2020-12), vendor keys only under `x.*`, canonical JSON signed | addressed | — |
| AST05 | Untrusted External Instructions | network scope enumerates hosts | partial | fetched content itself |
| AST06 | Weak Isolation | tests run network-isolated; `policy-compile` emits harness sandbox/permission config | partial | host must enforce at runtime |
| AST07 | Update Drift | version + file hashes; any change invalidates the signature | addressed | — |
| AST08 | Poor Scanning | declare + test + sign instead of a scanner verdict | addressed when tested | — |
| AST09 | No Governance | versionable harness policies (first-match, worst-case decision) | partial | organisational process |
| AST10 | Cross-Platform Reuse | one contract → Claude Code / Cursor / Codex / Gemini CLI configs; MDA / AutoVault converters | addressed | — |

Flagship (kajisho5/ffmpeg-skill, L3): AST02/03/04/07/08/10 addressed, AST01/05/06/09 partial.
Source: OWASP Agentic Skills Top 10 project page (owasp.github.io/www-project-agentic-skills-top-10). IDs/names to be re-checked against the final OWASP text before publishing.
