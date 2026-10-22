# SkillPact × OWASP Agentic Skills Top 10 — mapping (draft 0.8)

`skillpact owasp <skill_dir>` prints this per skill. Risk IDs and names checked against the OWASP project page on 2026-10-22 (https://owasp.org/www-project-agentic-skills-top-10/top10).

Statuses: **addressed** = the contract gives machine-checkable evidence for the main control OWASP names; **partial** = it helps, but the risk is not settled by SkillPact alone. Most items are partial: a contract is a signed, tested declaration, not proof of safety.

| ID | Risk | What SkillPact provides | Status | What remains |
|---|---|---|---|---|
| AST01 | Malicious Skills | declared effects per capability, sandboxed tests, author signatures, policy decisions | partial | cannot prove absence of malice; behavioural scanning, review and runtime enforcement still needed |
| AST02 | Supply Chain Compromise | sha256 over every skill file (0.8), ed25519 / Sigstore signatures with trusted keys | partial | a signature identifies the signer, not safety; dependencies outside the skill, SBOM and dependency pinning are not covered |
| AST03 | Over-Privileged Skills | six effects with scopes (paths, host allowlists, commands); policy denies unscoped or traversing scopes | addressed when every effect is scoped | scoped credentials and runtime enforcement are the harness's job |
| AST04 | Insecure Metadata | JSON Schema, I-JSON parsing, signed contract incl. signer role | addressed when signed with full coverage, otherwise partial | `SKILL.md` prose itself is not validated |
| AST05 | Untrusted External Instructions | network scope lists every host | partial | content fetched from those hosts is not covered |
| AST06 | Weak Isolation | tests run in a bubblewrap sandbox (no network, read-only FS, env allowlist); compiled harness settings | partial | only tests are sandboxed; isolation at real run time is the harness's job |
| AST07 | Update Drift | version + hashes of every file; any change breaks verification; policy `min_contract_version` | addressed when signed with full coverage | harness must re-verify before each run (TOCTOU) |
| AST08 | Poor Scanning | executable tests of declared behaviour; contract as scanner input | partial | tests are author-written and cover only what they exercise; complements scanners |
| AST09 | No Governance | versionable policies, signed contracts as review records | partial | organisational process, inventories, audit logging |
| AST10 | Cross-Platform Reuse | one contract compiles to Claude Code / Cursor / Codex / Gemini CLI settings; MDA / AutoVault converters | partial | each target loses some constraints (`lossy` list) |

Flagship (ffmpeg-skill, 0.8, L3): AST03 / AST04 / AST07 addressed; the rest partial.
