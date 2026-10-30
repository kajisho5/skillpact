<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="brand/app-icon-dark.png">
    <img src="brand/app-icon.png" width="128" alt="skillpact app icon">
  </picture>
</p>

# SkillPact — machine-readable contracts for Agent Skills (draft 0.8)


[![SkillPact L3](https://kajisho5.github.io/skillpact/badges/skillpact-L3.svg)](https://kajisho5.github.io/skillpact/) · [Checker (in your browser)](https://kajisho5.github.io/skillpact/check/) · [Why](https://kajisho5.github.io/skillpact/why/) · [Spec](https://kajisho5.github.io/skillpact/spec/) · [Guides](https://kajisho5.github.io/skillpact/guides/) · [Schema](https://kajisho5.github.io/skillpact/schema/) · [Badges](https://kajisho5.github.io/skillpact/badges/) · [日本語](https://kajisho5.github.io/skillpact/ja/)

## Why
Agent skills run with your permissions, but `SKILL.md` is prose: nothing in it can be checked by a machine before install. SkillPact adds a contract that tools check first: you see what a skill may touch, your policy decides allow / ask / deny (and can pre-approve declared effects so fewer prompts remain), and any changed file is detected. **L3 means "these files, signed by an author you trust, tests passed in isolation" — not "safe".** Runtime enforcement stays with your harness or a runtime policy. More: [Why SkillPact](https://kajisho5.github.io/skillpact/why/) · [What it does not guarantee](https://kajisho5.github.io/skillpact/why/#what-skillpact-does-not-guarantee).

## What it is
`skill.contract.json` sits next to an unchanged `SKILL.md` and declares, so any agent harness can check it *before install*:
- **capabilities**: entries (CLI / MCP tool), input & output JSON Schemas
- **side effects**: read / write / network / exec / spend / send, with scopes, conditional effects and per-capability narrowing
- **requirements**: binaries, versions, binary features (e.g. ffmpeg filters), packages, other skills
- **conformance tests**: they run network-isolated, so any agent can verify the skill works
- **integrity over every file (except `.git/` and `.DS_Store`) + ed25519 / Sigstore signature** (the signer role is signed too, from 0.8). Detection only: a harness must re-verify before each run

A small **harness policy** file then decides allow / ask / deny for each capability. The same decision is compiled to Claude Code, Cursor, Codex and Gemini CLI configs (each validated against that harness's schema) and exported to HushSpec / Rego for runtime enforcement.

## Positioning — declare + test + sign, before install
Scanners guess what a skill does after the fact. SkillPact makes the author **declare** every effect, ships executable **tests** that prove the declaration, and **signs** both (ed25519 or Sigstore). A harness checks this *before install* and compiles the result into its own permission config.
Runtime enforcement is deliberately **not** reinvented: decisions export to APS / ACS / HushSpec / Rego, which enforce at run time. SkillPact complements scanners (a contract is a better scanner input) and interoperates with MDA Open Spec `requires` and AutoVault `capabilities` (`skillpact convert`). OWASP Agentic Skills Top 10 coverage: `owasp_mapping.md`.

Schema: `https://kajisho5.github.io/skillpact/schema/v0.8.json` · License: spec CC BY 4.0, code Apache-2.0 · © SEVENTHWELL

| doc | |
|---|---|
| `spec/spec_v0.8.md` | full normative spec (English, BCP 14); Japanese translation `spec/spec_v0.8.ja.md` |
| `content/` | sources of the Why / Spec / Rationale / Guides / About pages (en + ja) |
| `SECURITY.md` / `CODE_OF_CONDUCT.md` / `IPR.md` / `TRADEMARKS.md` / `CITATION.cff` / `ROADMAP.md` | policies and project info; full list in `STANDARDS_CHECKLIST.md` |
| `spec/MIGRATION.md` / `spec/comparison.md` | migration from 0.x · comparison with Agent Skills, MDA, AutoVault, SkillSeal |
| `conformance/` | implementation-independent conformance suite + JCS / ed25519 test vectors |
| `ts/` | second implementation (TypeScript, verify-only); also powers the browser checker |
| `action.yml` | reusable GitHub Action (pin to a commit SHA) |
| `GOVERNANCE.md` | editor, change process, release checklist |
| `spec/owasp_mapping.md` | OWASP Agentic Skills Top 10 mapping |
| `spec/harness_research.md` | harness/runtime landscape, gap, harness_policy 0.1 (JA) |
| `spec/showcase.md` / `spec/showcase.en.md` | flagship: kajisho5/ffmpeg-skill at L3 (42 tools, 78 tests); Japanese original and English version |
| `CHANGELOG.md` / `CONTRIBUTING.md` | history / how to propose changes |
| `site/` | GitHub Pages site (kajisho5.github.io/skillpact/), React + shadcn/ui, built from `content/` and `docs/` by `.github/workflows/pages.yml` |
| `docs/` | Canonical static artifacts served as-is: `schema/*.json`, `badges/*.svg`, `check/` (browser checker bundle + example) |
| `examples/` | example harness policies and contracts for 7 other skills |
| `samples/` | signed L3 examples: ffmpeg-skill, subtitle-skill, thumbnail-skill, video-editing-skill |

## One-line use
```yaml
# .github/workflows/skillpact.yml in your skill repo
# pin to a full commit SHA; run on pull_request (not pull_request_target)
- uses: kajisho5/skillpact@<commit-sha>
  with: { path: ., min-level: L2 }
```
Packages are **not published yet** (PyPI / npm come with 1.0). Install from the repository:
```
git clone https://github.com/kajisho5/skillpact && pip install -e skillpact/ref
sudo apt-get install bubblewrap   # Linux: sandbox for conformance tests
```

## Quick start
```
python3 -m skillpact.cli init        <skill_dir> -o draft.json       # draft from SKILL.md / native contract
python3 -m skillpact.cli validate    <skill_dir>
python3 -m skillpact.cli test        <skill_dir>                     # network-isolated conformance run
python3 -m skillpact.cli conformance <skill_dir> [--trusted-key ed25519:...]   # L1 / L2 / L3
python3 -m skillpact.cli hash <skill_dir> && python3 -m skillpact.cli sign <skill_dir> key.pem
python3 -m skillpact.cli policy-check   <skill_dir> policies/solo-dev.json
python3 -m skillpact.cli policy-compile <skill_dir> policies/solo-dev.json --target claude-code --mcp-server NAME --render
python3 -m skillpact.cli export         <skill_dir> policies/solo-dev.json --format hushspec|rego
python3 -m skillpact.cli convert <skill_dir> --to mda|autovault   # or: convert SKILL.md --from mda|autovault
python3 -m skillpact.cli sign-sigstore <skill_dir>                 # keyless, CI
python3 -m skillpact.cli owasp <skill_dir>
python3 -m skillpact.cli mcp-check      <skill_dir> python3 '$SKILL_DIR/mcp/server.py'
python3 -m pytest -q ref/tests                                           # 100 tests (some skip without bwrap / opa / Sigstore)
```
Requires Python ≥ 3.11 (tomllib), ffmpeg for the flagship tests, bubblewrap (`bwrap`) for the test sandbox on Linux (fallback `unshare -rn`: network only, so no L2 / L3). `strace` for the exec audit (optional; without it, programs started by tests are not checked). Optional: `.tools/opa` for the Rego test.

## Layout
```
ref/skillpact/                   schema.json, policy_schema.json, core.py (validate/test/sign/policy/mcp), compose.py, init.py,
                                 native.py, harness.py (+ harness_schemas/), export.py, interop.py, owasp.py, sigstore_sig.py, cli.py
ref/policies/                    solo-dev.json, strict-ci.json
samples/ffmpeg-skill/            local copy of kajisho5/ffmpeg-skill @4334225 + skill.contract.json (L3, SEVENTHWELL key)
samples/build_ffmpeg_contract.py regenerates it
samples/{subtitle,thumbnail,video-editing}-skill/   further signed L3 samples
examples/contracts/*.contract.json  light contracts for 7 other kajisho5 skills
keys/public/                     SEVENTHWELL skill-signing public key + fingerprint
```
License: spec text CC BY 4.0, code Apache-2.0 (see LICENSE).
