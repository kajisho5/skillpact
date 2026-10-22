# Changelog
All notable changes to the SkillPact spec and implementations. Drafts until 1.0.


## 0.8.x errata (public review, 2026-10-22; no version tag)
From the second adversarial self-review (review/self_review_v0.8.md in the workspace). Spec text marked "erratum 0.8.x".
- Integrity: `__pycache__/` and `*.pyc` are no longer default excludes (unchecked-hash bytecode could run instead of signed source); code and bytecode files are protected and cannot be excluded; `hash` refuses bytecode; coverage is checked even with an external `--contract`.
- Signatures: contracts before 0.8 (role not signed) get `SIGNATURE_ROLE_UNSIGNED` and never L3 / `require_signature` (breaking for signed 0.4–0.7 contracts).
- Test sandbox (bwrap): home, `/tmp`, `/var/tmp`, `/run`, `/dev/shm` hidden; new session, IPC/UTS namespaces, stdin closed (blocks host-socket access, home reads and TIOCSTI). Seatbelt profile denies reads in home. Host variables for `skip_unless_env` only with `test --pass-env NAME`.
- Policy: a rule without `scope` matches every scope; `policy-compile` follows the worst case including conditional effects (e.g. Codex `on-request` instead of `never`).
- `migrate` across 0.8 tells you to re-run `skillpact hash`; `@local` lossy note documents the DNS-name caveat.
- Conformance: 48 cases (+ bytecode-unlisted, exclude-code, legacy-role-unsigned); Python and TypeScript pass all.
- `@local` matches only `localhost` and IP literals (127/8, 10/8, 172.16/12, 192.168/16, 169.254/16, ::1, fe80::/10, fc00::/7); DNS names, including `*.local`, never match. Vectors `conformance/vectors/local-hosts.json`; Python and TypeScript agree.
- macOS Seatbelt (experimental): host Unix sockets denied even for `network: true` cases (DNS resolver excepted); Mach/XPC (launchd, `open`) escape documented; Linux bwrap is the only full L2-grade mode. CI checks the socket block on macOS.
- `init`: capabilities per CLI subcommand, MCP tool and `SKILL.md` heading; read-only verbs get read/exec only; network scope from URLs instead of `TODO.example`. Output is still an unconfirmed draft. On shogo's subtitle / thumbnail / video-editing skills: 4 / 5 / 4 capabilities (was 1 each).
- Policy format: `policy_version` "0.8" ("0.1" still accepted as legacy name); new schema `schema/policy-v0.8-r1.json` (published `policy-v0.8.json` unchanged); bundled policies use "0.8".
- bwrap: only the resolved directories of programs the contract needs (and their virtualenv root) are re-exposed under the masked home/tmp; other PATH entries and parent directories such as `~/.local` are no longer visible (`SKILLPACT_SANDBOX_KEEP` to add paths).
- Docs: why / README / OWASP mapping no longer overstate tamper protection and isolation; guides mention bytecode and `--pass-env`.

## Unreleased (0.8 follow-up)
- Patent non-assertion covenant (EN/JA) in IPR.md and spec Status.
- IANA media type: to be considered after 1.0.
- Finding-code severity table (Appendix A).
- Experimental macOS Seatbelt runner mode; macOS CI job.
- Published schema/v0.1.json and v0.2.json (aliases of v0.3); /ja/badges/.

## 0.8 (draft, 2026-10-22) — fixes from the v0.7 self-review
Security (breaking for 0.8 contracts; older contracts keep their rules, see MIGRATION):
- Integrity must list **every** file of the skill (protected files such as `CLAUDE.md`, `.claude/**`, `hooks/**`, entry scripts cannot be excluded); new `integrity.exclude`; `INTEGRITY_UNLISTED`, `INTEGRITY_EMPTY`, `INTEGRITY_PATH` (path traversal, absolute paths, symlinks, limits). L3 refused for any version with unlisted files.
- Signer `role` is part of the signing input (`JCS({"contract", "role"})`); `DUP_SIGNATURE`.
- Test runner: setup is sandboxed too; bubblewrap sandbox (no network, read-only FS, env allowlist); skill-dir changes detected by content hash; writes outside the skill reported. `TEST_UNDECLARED_NETWORK`; L2 needs at least one isolated case.
- `policy-check` with `require_signature` verifies files and requires a trusted **author** signature; new policy field `min_contract_version`; traversing scopes are denied.
- Normative globs (path segments, DNS labels) identical in Python and TypeScript; `SCOPE_TRAVERSAL`.
- I-JSON parsing: big integers, non-finite numbers, lone surrogates, depth > 64 rejected (`CONTRACT_JSON`); legacy (0.1–0.3) signing supports integers only. Python and TypeScript agree on all fuzz cases.
- `policy-compile`: Codex never emits `approval_policy: never` when anything is ask/deny; Cursor output without `vimMode`; Gemini prefixes end with a space; every target reports `lossy`; checked against harness docs as of 2026-10-22.
- `init` drafts cannot pass L1 until confirmed (`UNCONFIRMED_DRAFT`).
Docs: English normative spec + Japanese translation, Why / Rationale / Guides / About pages, SECURITY, CODE_OF_CONDUCT, IPR, TRADEMARKS, CITATION, ROADMAP, ACCESSIBILITY, STANDARDS_CHECKLIST; honest OWASP mapping; README install wording; Action pinning guidance.
Conformance suite: 45 cases (15 new, one per exploit). Samples migrated to 0.8 and re-signed.

## 0.7 (draft, 2026-10-22)
- `@local` network scope token (maps to MDA `network: local`, expanded to concrete hosts for harness configs / HushSpec / Rego).
- `SKILL.md` name MUST equal the directory name (error from contract_version 0.7, warning before) — aligned with Agent Skills.
- Signature `role`: author / reviewer / scanner. L3 requires a trusted author signature; others are reported as attestations.
- Sigstore `instance: staging`; staging identities never match production trust entries. Signing workflow tested on Sigstore staging.
- Conformance suite: 30 cases. Samples migrated to 0.7 and re-signed.

## 0.6 (draft, 2026-10-22)
- Second, independent implementation: TypeScript verify-only (`ts/`), passes the full conformance suite and verifies all signed samples.
- Three more example skills (subtitle-skill, thumbnail-skill, video-editing-skill), all 0.6 and L3; ffmpeg-skill migrated to 0.6 and re-signed (JCS).
- Reference `hash` now includes `src/**`, `pyproject.toml`, `package.json`.
- New warning `SIGSTORE_UNVERIFIED`. GOVERNANCE.md, MIGRATION.md, comparison with adjacent specs.
- Packaging for one-command use (`pipx run skillpact`, `npx skillpact-verify`), a reusable GitHub Action, L1/L2/L3 badges, and a browser-only checker page.

## 0.5
- Implementation-independent conformance suite (`conformance/`), `migrate` command, completed security considerations and threat model, duplicate JSON keys rejected (`CONTRACT_JSON`).
- Prepared (not enabled) GitHub Actions workflow for Sigstore keyless signing.

## 0.4
- Consolidated, normative (BCP 14) spec. Signing input switched to RFC 8785 (JCS) for contract_version ≥ 0.4; 0.1–0.3 verify with the legacy form. Known-answer vectors.
- Unknown versions rejected (`CONTRACT_VERSION_UNSUPPORTED`), `SCOPE_EMPTY`, `UNKNOWN_VARIABLE`, L3 only with a trusted key, no L2 without network isolation.

## [0.3.0] - unreleased
### Added
- Sigstore keyless signatures (`sign-sigstore`), alongside ed25519; `--trusted-key sigstore:<issuer>|<identity>`.
- `convert`: import/export MDA Open Spec 1.0 `metadata.mda.requires` and AutoVault `capabilities` (lossy report + pointer back to the full contract).
- `owasp`: per-skill OWASP Agentic Skills Top 10 assessment; `spec/owasp_mapping.md`.
- `export --format aps|acs` in addition to hushspec / rego.
- Canonical schema URLs under `https://kajisho5.github.io/skillpact/schema/`.
### Changed
- README positioning: declare + test + sign before install; runtime enforcement delegated to APS / ACS / HushSpec.

## [0.2.0] - 2026-10-22 (local draft)
- harness_policy 0.1, `policy-check`, `policy-compile` (Claude Code / Cursor / Codex / Gemini CLI), HushSpec / Rego export, conditional effects, binary feature checks, `mcp-check`.

## [0.1.0] - 2026-10-21 (local draft)
- `skill.contract.json`: capabilities, 6 effect classes, requirements, conformance tests, integrity + ed25519.
