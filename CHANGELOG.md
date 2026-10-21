# Changelog
All notable changes to the SkillPact spec and reference implementation. Unreleased drafts until 1.0.

## [0.3.0] - unreleased
### Added
- Sigstore keyless signatures (`sign-sigstore`), alongside ed25519; `--trusted-key sigstore:<issuer>|<identity>`.
- `convert`: import/export MDA Open Spec 1.0 `metadata.mda.requires` and AutoVault `capabilities` (lossy report + pointer back to the full contract).
- `owasp`: per-skill OWASP Agentic Skills Top 10 assessment; `spec/owasp_mapping.md`.
- `export --format aps|acs` in addition to hushspec / rego.
- Canonical schema URLs under `https://seventh-well.com/skillpact/schema/`.
### Changed
- README positioning: declare + test + sign before install; runtime enforcement delegated to APS / ACS / HushSpec.

## [0.2.0] - 2026-10-22 (local draft)
- harness_policy 0.1, `policy-check`, `policy-compile` (Claude Code / Cursor / Codex / Gemini CLI), HushSpec / Rego export, conditional effects, binary feature checks, `mcp-check`.

## [0.1.0] - 2026-10-21 (local draft)
- `skill.contract.json`: capabilities, 6 effect classes, requirements, conformance tests, integrity + ed25519.
