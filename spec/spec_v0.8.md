# SkillPact 0.8 Specification

## Abstract
SkillPact defines `skill.contract.json`, a machine-readable contract placed next to an unchanged Agent Skills `SKILL.md`. The contract declares what a skill does (capabilities), which side effects it may have (six effect classes with scopes), what it needs (requirements), executable conformance tests, and file hashes with signatures. Tools can check a contract **before a skill is installed**, decide allow / ask / deny against a harness policy, and compile that decision into native harness settings.

## Status of this document
- **Draft 0.8, 2026-10-22.** Editor's draft published by SEVENTHWELL (shogo kajiyama). This is a complete document, not a diff.
- Not yet stable. Breaking changes are possible between 0.x versions (see Versioning). A public review period will be announced; its dates are not set yet (see [REVIEW.md](https://github.com/kajisho5/skillpact/blob/main/REVIEW.md)).
- **The English text is normative.** The Japanese translation ([/ja/spec/](../ja/spec/)) is informative; if they differ, English wins.
- Feedback: GitHub issues on kajisho5/skillpact. Decision process: [GOVERNANCE.md](https://github.com/kajisho5/skillpact/blob/main/GOVERNANCE.md).
- Schema: `https://kajisho5.github.io/skillpact/schema/v0.8.json` · Policy schema: `.../schema/policy-v0.8.json`.
- License: text CC BY 4.0; schemas and implementations Apache-2.0. See IPR below.

## 1. Conventions and terminology
The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" are to be interpreted as described in BCP 14 (RFC 2119, RFC 8174) when, and only when, they appear in all capitals. Sections marked *informative*, examples and notes are not normative.

| Term | Meaning |
|---|---|
| skill | A directory containing `SKILL.md` (Agent Skills format) and the files it uses |
| skill directory | That directory; `$SKILL_DIR` |
| contract | The JSON document `skill.contract.json` |
| effect | One of six side-effect classes (§6) |
| capability | One tool / command / operation the skill offers (§7) |
| producer | Software or person that writes a contract |
| validator | Software that checks a contract and reports findings |
| runner | Software that executes the contract's tests (§10) |
| harness | The agent runtime that loads skills (e.g. Claude Code, Cursor, Codex, Gemini CLI) |
| policy | A harness policy document (§13) |
| finding | An error or warning with a code from Appendix A |
| signing input | The exact bytes that are signed (§11.1) |
| author signature | A signature with role `author` (§11) |

## 2. Scope and non-goals
In scope:
1. **Declaration**: what a skill does, needs, and which side effects it may have.
2. **Pre-install check**: contract × policy → allow / ask / deny per capability.
3. **Translation**: compile the decision into Claude Code, Cursor, Codex and Gemini CLI settings; export to HushSpec and Rego.

Non-goals:
- **Runtime enforcement.** Left to harnesses and runtime policy standards (APS, ACS, HushSpec). SkillPact only feeds them.
- **Proving a skill is safe.** A contract is a claim by its author; tests check part of it; a signature identifies who made it (§18).
- **Scanning / static analysis.** SkillPact does not compete with scanners; a contract is a useful input for them.
- **Distribution / registry.** Out of scope.
- **Changing Agent Skills.** `SKILL.md` stays unchanged.

## 3. File name, location and format
- The contract file MUST be named `skill.contract.json` and MUST be in the same directory as `SKILL.md`.
- Producers MUST NOT modify `SKILL.md` frontmatter or body for the contract. Harnesses that do not know SkillPact keep working.
- `skill.name` MUST equal the frontmatter `name` (`NAME_MISMATCH`). The frontmatter `name` MUST equal the name of the directory containing `SKILL.md` (`FM_NAME_DIR`; error for `contract_version` ≥ 0.7, warning before; not checked when validating a contract stored elsewhere).
- Media type and naming: see Appendix D.

## 4. JSON profile
### 4.1 Parsing (I-JSON)
A contract MUST be UTF-8 encoded JSON (RFC 8259) that also satisfies I-JSON (RFC 7493) and these limits. Validators MUST reject anything else with `CONTRACT_JSON`:
- no duplicate member names (after unescaping);
- integers within ±(2^53−1); all numbers finite;
- no lone surrogates in any string or member name;
- invalid UTF-8 is rejected;
- nesting depth at most 64 (the top-level value is depth 1).

Rationale: two parsers that disagree about a document can make a signature cover different content than the one evaluated.

## 5. Document structure
A contract MUST conform to the JSON Schema (Draft 2020-12) in §15 (`SCHEMA`).

| Key | Required | Content |
|---|---|---|
| `$schema` | no | schema URL |
| `contract_version` | yes | `"0.1"` … `"0.8"` |
| `kind` | no | `tool` (default) or `instructions` (no executables) |
| `skill` | yes | `name`, `version` (SemVer), `native_contract` |
| `permissions` | yes | §6 |
| `capabilities` | yes for `tool` | §7 |
| `requirements` | no | §8 |
| `compat` | no | §9 |
| `tests` | no (needed for L2) | §10 |
| `integrity` | no (needed for L3) | §11 |
| `x` | no | extensions, only `x.<vendor>.*` |

- Extensions MUST be under `x.<vendor>`; vendor names match `^[a-z0-9][a-z0-9-]*$`. Other unknown keys are schema errors.
- Validators MUST ignore the content of `x` they do not understand, except the draft markers in §14.

## 6. Permissions (six effects)
Each effect has `level` (`none` | `scoped` | `any`), `scope` (array), `why`, `confirm` (`never` | `each` | `session`).

| Effect | Meaning | Scope syntax |
|---|---|---|
| read | read files or data | path glob |
| write | create, change, delete | path glob, `remote:<host>/<path>` |
| network | talk to other hosts | host glob, `@local` |
| exec | run other programs | command name |
| spend | cost money | service name |
| send | reach a person (message, post, mail) | recipient kind / service name |

- Path variables: `$INPUT` `$INPUT_DIR` `$OUTPUT` `$WORKDIR` `$SKILL_DIR` `$TMPDIR`. Other `$` variables SHOULD produce `UNKNOWN_VARIABLE`.
- A `scoped` effect MUST have at least one scope (`SCOPE_EMPTY`). The skill-level scope MUST cover every case, including conditional ones.
- `level: any` for spend or send MUST produce `HIGH_RISK`.
- Scopes starting with `@` are reserved tokens. 0.8 defines `@local` for network: loopback, private networks and `*.local` (Appendix C). Unknown tokens SHOULD produce `UNKNOWN_SCOPE_TOKEN`. When writing harness or runtime policy, `@local` MUST be expanded to host patterns; what cannot be expressed (IPv6 unique-local) MUST be reported as lossy.

### 6.1 Globs and paths (normative)
All implementations MUST match globs exactly as follows; `fnmatch` or shell glob semantics MUST NOT be used.
- **Path and generic patterns** (read, write, exec, spend, send): `*` matches any run of characters except `/`; `?` matches one character except `/`; a whole segment `**` matches zero or more segments; a trailing `/**` also matches the base itself (`a/**` matches `a`). Other characters match themselves. Matching is case-sensitive.
- **Host patterns** (network): `*` matches within one DNS label; a leading `*.` matches one or more labels (`*.example.com` does not match `example.com`); a leading `**.` matches zero or more labels. Case-insensitive; a trailing dot is ignored.
- **Path scopes** (read, write, `effect_scopes`) MUST NOT contain `.` or `..` segments, empty segments or backslashes (`SCOPE_TRAVERSAL`). Absolute paths are allowed.
- **Coverage** (one scope inside another, used by `effect_scopes` and policy rules): a scope entry is covered when it is equal to a pattern or, treating its own wildcards as literals that only an equal or wider wildcard can match, it matches a pattern. A scope with traversal is never covered.

## 7. Capabilities
- Each capability has `id` (unique; `DUP_CAPABILITY`), `summary`, `entry` and `effects`.
- `entry` is `cli` (array), `mcp_tool` or `doc`. `$SKILL_DIR/...` tokens in `cli` MUST exist (`ENTRY_MISSING`). No entry with effects: `NO_ENTRY` warning.
- Every effect in `effects` MUST be non-`none` in permissions (`UNDECLARED_EFFECT`).
- `effect_scopes` MAY narrow a scope per capability and MUST NOT widen it (`SCOPE_WIDENED`).
- `conditional_effects[]` (`effect`, `when`, `scope`): effects that happen only in some cases; also MUST be declared.
- `destructive: true` SHOULD come with write, send or spend (`DESTRUCTIVE_NO_EFFECT`).
- Optional: `idempotent`, `dry_run`, `inputs` / `outputs` (JSON Schema; invalid → `BAD_SUBSCHEMA`), `requires` (MUST name a requirement, `UNKNOWN_REQUIREMENT`), `requires_features` / `optional_features` (`<kind>:<name>`, kind MUST be in `features_check`, `UNKNOWN_FEATURE_KIND`), `mcp_annotations`.

## 8. Requirements
- `binaries[]` / `runtimes[]`: `name`, `version` (e.g. `>=4.4`), `check`, `version_regex`, `optional`, `when`, `alternatives`, `features_check`.
- `packages[]`: `ecosystem`, `name`, `import`. `skills[]`: `name`, `version`, `env`, `optional`.
- `env[]`: `name`, `required`, `secret`, `description`. Secret values MUST NOT appear in a contract.

## 9. Compatibility
`compat.agents.<id>`: `status` (`tested` | `expected` | `unsupported`), `version`, `tested_at`, `notes`. `tested` SHOULD only be claimed after running §10 in that harness. Also `os`, `interfaces`.

## 10. Conformance tests
- `setup`: commands run in a fresh `$WORKDIR`. `cases[]`: `id`, `capability` (MUST exist, `TEST_UNKNOWN_CAPABILITY`), `run`, `timeout_s`, `network` (default false), `env`, `skip_unless_env`, `tags`, `expect` (`exit_code`, `stdout_contains`, `stderr_contains`, `stdout_json_schema`, `stdout_json[]`, `stdout_json_mode`, `files[]`, `validate_outputs`).
- A case with `network: true` requires `permissions.network` other than `none` (`TEST_UNDECLARED_NETWORK`; error from 0.8).
- A runner MUST run `setup` and every case in a sandbox that:
  1. has no network, except cases with `network: true`;
  2. makes the file system read-only except `$WORKDIR` (and `$SKILL_DIR` only when the write scope includes it);
  3. passes only an allowlist of environment variables: `PATH`, `LANG`, `LC_ALL`, `TZ`, `TERM`, the SkillPact variables, located dependency skills, variables named in `skip_unless_env`, and the case `env`. `HOME` and `TMPDIR` point inside `$WORKDIR`.
- A runner MUST detect changes to the skill directory by content hash (not by size or time) and fail the case unless the write scope includes `$SKILL_DIR`. When it cannot isolate the file system, it MUST also watch the parent directory and report writes outside the skill.
- A runner that cannot provide network isolation MUST NOT report L2. L2 also needs at least one passing isolated case that is not `network: true`.
- Skipped cases are not failures but MUST be counted and reported.
- The reference runner uses bubblewrap (`bwrap`), falling back to `unshare -rn` (network only, reported as `fs_isolated: false`).

## 11. Integrity and signatures
- `integrity.algorithm` is `sha256`; `integrity.files` maps relative paths to lowercase hex digests. Validators MUST check every listed file (`INTEGRITY_MISMATCH`, `INTEGRITY_MISSING`).
- `integrity.signatures[]`: ed25519 `{type, key: "ed25519:<b64>", sig, signer, role}` or Sigstore `{type, identity, issuer, bundle, instance, role}`.
- `role` is `author` (default), `reviewer` or `scanner`. Only a trusted **author** signature can make L3. Validators SHOULD report valid reviewer/scanner signatures as attestations.
- A key or identity MUST NOT sign the same contract more than once (`DUP_SIGNATURE`); a verifier treats a key as valid only if all its entries verify.
- Sigstore verifiers MUST match both identity and issuer against their trust list. Staging signatures MUST carry `instance: "staging"` and MUST NOT match production trust entries.
- Trust is set by policy `trusted_keys` (`ed25519:<b64>` or `sigstore:<issuer>|<identity>`). A valid signature by an untrusted key MUST NOT yield L3.

### 11.1 Signing input
- `contract_version` ≥ 0.8: the UTF-8 bytes of JCS (RFC 8785) of `{"contract": C, "role": R}`, where C is the contract without `integrity.signatures` and R is the entry's role (`"author"` if absent). The role is therefore signed; relabelling a signature breaks it.
- 0.4–0.7: JCS(C). The role is not signed (legacy; see §18.7).
- 0.1–0.3: legacy sorted form (keys sorted by code point, separators `,` `:`, no whitespace, non-ASCII as UTF-8). Only integers within ±(2^53−1) are supported; other numbers make the contract unverifiable and it MUST be migrated and re-signed.
- The form is chosen by `contract_version`; `integrity.canonicalization` is informative only.
- Test vectors: `conformance/vectors/jcs-ed25519.json` (test key with a published seed; it MUST NOT be used for real signatures).

### 11.2 File coverage (from 0.8)
- `integrity.files` MUST list every regular file in the skill directory except `skill.contract.json`, the default excludes (`.git/**`, `**/__pycache__/**`, `**/*.pyc`, `**/.DS_Store`) and patterns in the optional `integrity.exclude`.
- Protected files MUST always be listed and cannot be excluded: `SKILL.md`, `**/SKILL.md`, `**/CLAUDE.md`, `**/AGENTS.md`, `**/GEMINI.md`, `**/.mcp.json`, `.claude-plugin/**`, `.claude/**`, `.cursor/**`, `.codex/**`, `.gemini/**`, `.agents/**`, `hooks/**`, `package.json`, `pyproject.toml`, and every file named as `$SKILL_DIR/...` in entries, tests or setup.
- An unlisted file: `INTEGRITY_UNLISTED` (error from 0.8, warning before). `files` without `SKILL.md`: `INTEGRITY_EMPTY` (0.8).
- Paths MUST be relative POSIX paths without `.`/`..`/empty segments, backslashes or control characters; at most 1024 bytes and 32 segments; at most 10 000 entries. Symbolic links anywhere in the skill directory or in a listed path are rejected (`INTEGRITY_PATH`, all versions).
- For any version, L3 MUST NOT be granted while any `INTEGRITY_UNLISTED` or `INTEGRITY_PATH` finding exists.

## 12. MCP mapping
| annotation | derived from |
|---|---|
| `readOnlyHint` | no write / send / spend (including conditional) |
| `destructiveHint` | `destructive` |
| `idempotentHint` | `idempotent` |
| `openWorldHint` | network / send / spend present |

## 13. Harness policy and compilation
- Policies follow `policy-v0.8.json`. For each capability a matcher MUST output `decision` and `decision_worst_case` (including conditional effects).
- A path scope with traversal MUST be denied.
- `min_contract_version`: contracts older than this MUST be denied.
- `require_signature`: the matcher MUST verify the files (integrity with full coverage, §11.2) and require a trusted **author** signature; otherwise deny.
### 13.1 Compilation
- `policy-compile` emits native settings for Claude Code, Cursor, Codex and Gemini CLI, validated against each harness's public schema (or a schema derived from its documentation), and MUST list what the target cannot express in `lossy`.
- When a target cannot express a deny or ask, the output MUST be at least as strict as the decision (e.g. Codex `approval_policy: on-request`, never `never`).
- `export --format hushspec|rego` emits runtime policy documents.

## 14. Conversion and drafts
- `convert` maps to and from MDA Open Spec `requires` and AutoVault `capabilities`; exports list `lossy` items and point back to the contract with its sha256.
- Imports and `init` drafts list guesses in `x.import.uncertain` / `x.init.uncertain`, and may use `TODO(...)` strings. Such a contract is an unconfirmed draft: `UNCONFIRMED_DRAFT` (error from 0.8). A person must confirm and remove the markers.

## 15. Schemas
- Contract: `schema/v0.8.json` (`$id` `https://kajisho5.github.io/skillpact/schema/v0.8.json`). Policy: `schema/policy-v0.8.json`. Published schema files are never edited in place.

## 16. Conformance
### 16.1 Levels (of a contract)
- **L1 Declared**: no validator errors.
- **L2 Tested**: L1, and all cases pass in the sandbox of §10 with at least one network-isolated case.
- **L3 Signed**: L2, integrity matches with full coverage (§11.2), and a valid author signature by a trusted key or identity exists.

L3 means "these exact files were signed by someone you trust, and the declared tests pass in isolation". It does **not** mean the skill is safe.

### 16.2 Conformance classes (of software)
| Class | Requirements |
|---|---|
| Producer | emits contracts that satisfy §3–§11 and the schema |
| Validator | checks every MUST in §3–§11 and §14, reports Appendix A codes, passes the conformance suite |
| Runner | §10 sandbox, environment allowlist, content-hash change detection, skip reporting |
| Policy matcher | §13 decisions, `require_signature` and `min_contract_version` semantics |
| Compiler | §13.1, including `lossy` |
| Harness | SHOULD follow `decision_worst_case` and re-verify integrity before running |

### 16.3 Conformance suite
`conformance/manifest.json` and `conformance/cases/<id>/` (45 cases in 0.8). A validator claiming conformance MUST pass all of them: `python3 conformance/run.py --cmd '<validator> {dir}'`. Cases for 0.8 are generated by `conformance/gen_v08.py`. Both the Python reference implementation and the TypeScript implementation pass all cases.

## 17. Versioning, stability and deprecation
- Validators MUST accept every version they know and MUST reject unknown major versions (`CONTRACT_VERSION_UNSUPPORTED`). During 0.x an unknown minor version is treated as unknown major.
- From 1.0: minor versions only add (optional fields, new codes, new enum values); anything else needs a new major version. An unknown minor version MAY be processed with `CONTRACT_VERSION_NEWER`.
- Deprecation: announced at least one minor version before removal; validators SHOULD warn.
- `skill.version` is SemVer; widening permissions SHOULD bump major, and harnesses SHOULD ask again.
- `migrate` raises a contract to a newer version, drops signatures when content changes, and never signs or publishes.

## 18. Security considerations
### 18.1 Threat model
Protected: the user and their harness (files, credentials, network, money, messages to people). Trusted: the validator, runner, harness, and keys the user put in `trusted_keys`. Not trusted: skill authors, distribution channels, mirrors, contract content.

| Attacker | Can | Mitigation | Remaining risk |
|---|---|---|---|
| Malicious author | under-declare effects; behave only in tests | isolated tests, sandbox, worst-case decisions | untested paths; needs runtime enforcement |
| Distribution / mirror | swap files or contract | full-coverage hashes and signatures; L3 only for trusted keys | compromise of a trusted key |
| Relabeller | turn a reviewer signature into an author one | role is signed from 0.8 | 0.4–0.7 contracts (§18.7) |
| Downgrader | serve an older, laxer contract version | unknown versions rejected; `min_contract_version` | harness that does not record approved versions |
| Dependency | change a dependent skill or package | declared in `requirements` | content of dependencies is out of scope |
| Text injection | instructions in `why` / `summary` | decisions use structured fields only | harness that feeds free text to a model |

### 18.2 Declarations are self-reported
L1 shows only consistency. Harnesses SHOULD NOT auto-allow effectful capabilities based on L1 alone, and SHOULD combine SkillPact with runtime enforcement.
### 18.3 Integrity and TOCTOU
Files may change between check and run. Harnesses SHOULD run verified copies read-only or re-verify immediately before running.
### 18.4 Keys and identities
Private keys MUST NOT appear in contracts, repositories or logs. Rotate by signing with old and new keys for at least one release. On compromise, users MUST remove the key from `trusted_keys`. Sigstore identity MUST be matched in full (workflow path and ref), never by issuer or organisation only.
### 18.5 Parsing
§4.1 removes parser differences (duplicate keys, big integers, surrogates, depth).
### 18.6 Running tests
Running tests executes the skill's code. `setup` and `run` are untrusted input; §10 applies. Users' credentials MUST NOT be passed except variables named in `skip_unless_env`.
### 18.7 Legacy versions
Contracts before 0.8 do not sign the role and do not require full file coverage (unlisted files are warnings, but L3 is still refused). Policies SHOULD set `min_contract_version: "0.8"`.

## 19. Privacy considerations
- A contract contains no personal data by design except optional `signer` names and Sigstore identities (often an e-mail address or a CI workflow URL). Authors SHOULD use a role or project identity if they do not want a personal e-mail published; Sigstore entries are also recorded in a public transparency log.
- Secret values MUST NOT appear in contracts (§8).
- Validators and the browser checker work offline; the checker page sends nothing.
- Test runs get only allowlisted environment variables (§10).

## 20. Interoperability
- Agent Skills: unchanged `SKILL.md`; names follow its rules.
- MCP: annotations (§12), `mcp-check`.
- Harness settings: Claude Code, Cursor, Codex, Gemini CLI (§13.1), each with known losses.
- Runtime policy: HushSpec, Rego (for APS / ACS).
- Other formats: MDA Open Spec, AutoVault (§14). OWASP Agentic Skills Top 10: `spec/owasp_mapping.md` (partial coverage, stated honestly).

## 21. References
Normative: RFC 2119, RFC 8174 (BCP 14); RFC 8259 (JSON); RFC 7493 (I-JSON); RFC 8785 (JCS); RFC 8032 (EdDSA / Ed25519); JSON Schema 2020-12; Agent Skills specification (https://agentskills.io/specification); Semantic Versioning 2.0.0.

Informative: Sigstore; MCP tool annotations; OWASP Agentic Skills Top 10 (https://owasp.org/www-project-agentic-skills-top-10/); HushSpec; Agent Policy Specification; Microsoft Agent Control Specification; OPA / Rego; MDA Open Spec; AutoVault; bubblewrap; harness documentation (Claude Code, Cursor, Codex, Gemini CLI) as of 2026-10-22.

## Appendix A. Finding codes
Errors: `SKILL_MD_MISSING` `FRONTMATTER_MISSING` `FM_NAME` `FM_DESCRIPTION` `FM_COMPAT` `CONTRACT_MISSING` `CONTRACT_JSON` `CONTRACT_VERSION_UNSUPPORTED` `SCHEMA` `NAME_MISMATCH` `DUP_CAPABILITY` `UNDECLARED_EFFECT` `BAD_SUBSCHEMA` `UNKNOWN_REQUIREMENT` `ENTRY_MISSING` `TEST_UNKNOWN_CAPABILITY` `INTEGRITY_MISSING` `INTEGRITY_MISMATCH` `INTEGRITY_PATH` `INTEGRITY_EMPTY` `SIGNATURE_INVALID` `DUP_SIGNATURE` `SCOPE_WIDENED` `SCOPE_EMPTY` `SCOPE_TRAVERSAL` `UNKNOWN_FEATURE_KIND`

Version-dependent (error from the given version, warning before): `FM_NAME_DIR` (0.7), `INTEGRITY_UNLISTED` (0.8), `TEST_UNDECLARED_NETWORK` (0.8), `UNCONFIRMED_DRAFT` (0.8).

Warnings: `BODY_LONG` `HIGH_RISK` `DESTRUCTIVE_NO_EFFECT` `UNUSED_PERMISSION` `NO_TESTS` `UNTESTED_CAPABILITY` `NO_ENTRY` `UNKNOWN_VARIABLE` `UNKNOWN_SCOPE_TOKEN` `CONTRACT_VERSION_NEWER` `SIGSTORE_UNVERIFIED`

## Appendix B. Examples
Minimal (instructions only):
```json
{"contract_version": "0.8", "kind": "instructions",
 "skill": {"name": "style-guide", "version": "1.0.0"},
 "permissions": {"read": {"level": "none"}, "write": {"level": "none"}, "network": {"level": "none"},
                 "exec": {"level": "none"}, "spend": {"level": "none"}, "send": {"level": "none"}},
 "capabilities": [{"id": "guide", "summary": "writing guidance", "effects": []}]}
```
A tool with a test:
```json
{"contract_version": "0.8", "skill": {"name": "thumb", "version": "1.2.0"},
 "permissions": {"read": {"level": "scoped", "scope": ["$INPUT"]}, "write": {"level": "scoped", "scope": ["$OUTPUT"]},
   "network": {"level": "none"}, "exec": {"level": "scoped", "scope": ["python3"]},
   "spend": {"level": "none"}, "send": {"level": "none"}},
 "capabilities": [{"id": "make", "summary": "make a thumbnail", "effects": ["read", "write", "exec"],
   "entry": {"cli": ["python3", "$SKILL_DIR/scripts/thumb.py", "$INPUT", "$OUTPUT"]}}],
 "tests": {"cases": [{"id": "basic", "capability": "make", "run": ["python3", "$SKILL_DIR/scripts/thumb.py", "--selftest"],
   "expect": {"exit_code": 0}}]}}
```
Full signed examples: `samples/` (four skills at L3). Test vectors: `conformance/vectors/`. Conformance cases: `conformance/cases/`.

## Appendix C. `@local` expansion
`localhost`, `127.*.*.*`, `::1`, `10.*.*.*`, `172.16.*.*` … `172.31.*.*`, `192.168.*.*`, `*.local`. IPv6 unique-local (`fc00::/7`) is reported as lossy.

## Appendix D. Media type and file naming (registration note)
- File name: `skill.contract.json`, fixed, next to `SKILL.md`.
- Media type: `application/json` is used today. A specific type (e.g. `application/skillpact+json`) is **not registered** with IANA; registration will be considered after 1.0 if there is demand. Until then implementations MUST NOT rely on a specific media type.
- Schema URLs are immutable per version.

## Appendix E. Changes in 0.8
Full file coverage and path rules (§11.2); role inside the signing input (§11.1); `DUP_SIGNATURE`; I-JSON parsing (§4.1); normative globs and `SCOPE_TRAVERSAL` (§6.1); sandboxed setup, environment allowlist, content-hash change detection (§10); `TEST_UNDECLARED_NETWORK`; `UNCONFIRMED_DRAFT`; policy `min_contract_version` and file verification for `require_signature` (§13); stricter compilation with `lossy` (§13.1); English text becomes normative. Earlier history: [CHANGELOG.md](https://github.com/kajisho5/skillpact/blob/main/CHANGELOG.md).
