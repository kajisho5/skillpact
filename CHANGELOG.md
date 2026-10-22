# Changelog
All notable changes to the SkillPact spec and implementations. Drafts until 1.0.


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
