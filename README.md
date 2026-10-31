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
| `action.yml` | reusable GitHub Action (pin to a commit SHA); its check step is `.github/action/verify.py`, see "Use it in your skill's CI" below |
| `SKILL.md` | SkillPact itself as an Agent Skill: when to use it, the authoring / checking workflow, every CLI command; `ref/tests/test_skill.py` keeps it to commands and options that exist |
| `GOVERNANCE.md` | editor, change process, release checklist |
| `spec/owasp_mapping.md` | OWASP Agentic Skills Top 10 mapping |
| `spec/os_capability_mapping.md` | SkillPact contract <-> kajisho5/Velisa OS capability contract (`convert --to/--from os-capability`); fixtures in `examples/os-capability/` |
| `spec/harness_research.md` | harness/runtime landscape, gap, harness_policy 0.1 (JA) |
| `spec/showcase.md` / `spec/showcase.en.md` | flagship: kajisho5/ffmpeg-skill at L3 (42 tools, 78 tests); Japanese original and English version |
| `CHANGELOG.md` / `CONTRIBUTING.md` | history / how to propose changes |
| `site/` | GitHub Pages site (kajisho5.github.io/skillpact/), React + shadcn/ui, built from `content/` and `docs/` by `.github/workflows/pages.yml` |
| `docs/` | Canonical static artifacts served as-is: `schema/*.json`, `badges/*.svg`, `check/` (browser checker bundle + example) |
| `examples/` | example harness policies and contracts for 7 other skills |
| `samples/` | signed L3 examples: ffmpeg-skill, subtitle-skill, thumbnail-skill, video-editing-skill |

## Use it in your skill's CI (GitHub Action)
`action.yml` is a composite action: it installs the reference implementation from the action's own checkout, runs `skillpact validate` (every finding becomes an annotation on the contract), then `skillpact conformance` (your declared tests, in bubblewrap with the exec audit), and fails the job when the level is below `min-level`. A failing test case is named with its failures and stderr; a requirement missing on the runner is named too. The report goes to the job summary and `$RUNNER_TEMP/skillpact-report.json`, never into your skill directory.
```yaml
# .github/workflows/skillpact.yml in your skill repo
name: skillpact
on: [push, pull_request]          # pull_request, never pull_request_target
permissions:
  contents: read
jobs:
  skillpact:
    runs-on: ubuntu-latest        # Linux: bubblewrap sandbox, needed for L2 / L3
    steps:
      - uses: actions/checkout@v4
      # install here whatever your contract's requirements name (binaries, packages)
      - uses: kajisho5/skillpact@<commit-sha>   # a full 40-character commit SHA, never a branch or tag
        with:
          path: .                   # skill directory (SKILL.md)
          min-level: L2
```
Get the SHA of a released version with `git ls-remote https://github.com/kajisho5/skillpact refs/tags/v<version>` (or the merge commit you want), and let Dependabot (`package-ecosystem: github-actions`) move it.

| input | default | |
|---|---|---|
| `path` | `.` | skill directory (contains `SKILL.md`) |
| `contract` | `<path>/skill.contract.json` | the contract (manifest) when it lives elsewhere |
| `python-version` | `3.13` | Python that runs SkillPact (>= 3.11); also the first `python3` on `PATH` for your tests |
| `run-tests` | `true` | `false` = validate only (L1) |
| `min-level` | `L1` | `L1`, `L2` or `L3`; L2 / L3 need `run-tests: true` |
| `trusted-key` | (none) | space-separated `ed25519:<b64>` / `sigstore:<issuer>\|<identity>` keys; L3 needs your author key here |

Output `level`: `none`, `L1-declared`, `L2-tested` or `L3-signed`. `.github/workflows/action.yml` runs the action on this repository's fixtures (a signed sample at L3, an explicit `contract` on Python 3.11, an invalid contract that must fail).

## Install
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
python3 -m skillpact.cli convert <skill_dir> --to os-capability [--against os.json]   # Velisa OS capability contract; or: convert os.json --from os-capability
python3 -m skillpact.cli sign-sigstore <skill_dir>                 # keyless, CI
python3 -m skillpact.cli owasp <skill_dir>
python3 -m skillpact.cli mcp-check      <skill_dir> python3 '$SKILL_DIR/mcp/server.py'
python3 -m pytest -q ref/tests                                           # 166 tests (some skip without bwrap / opa / Sigstore)
```
Requires Python ≥ 3.11 (tomllib), ffmpeg for the flagship tests, bubblewrap (`bwrap`) for the test sandbox on Linux (fallback `unshare -rn`: network only, so no L2 / L3). `strace` for the exec audit (optional; without it, programs started by tests are not checked). Optional: `.tools/opa` for the Rego test.

## Layout
```
ref/skillpact/                   schema.json, policy_schema.json, core.py (validate/test/sign/policy/mcp), compose.py, init.py,
                                 native.py, harness.py (+ harness_schemas/), export.py, interop.py (+ os_schemas/), owasp.py, sigstore_sig.py, cli.py
ref/policies/                    solo-dev.json, strict-ci.json
samples/ffmpeg-skill/            local copy of kajisho5/ffmpeg-skill @4334225 + skill.contract.json (L3, SEVENTHWELL key)
samples/build_ffmpeg_contract.py regenerates it
samples/{subtitle,thumbnail,video-editing}-skill/   further signed L3 samples
examples/contracts/*.contract.json  light contracts for 7 other kajisho5 skills
keys/public/                     SEVENTHWELL skill-signing public key + fingerprint
```
License: spec text CC BY 4.0, code Apache-2.0 (see LICENSE).
