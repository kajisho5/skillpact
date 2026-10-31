---
name: skillpact
description: Write and check SkillPact contracts (skill.contract.json) for Agent Skills with the skillpact CLI - draft a contract from a SKILL.md, validate it, run its conformance tests network-isolated, hash and sign every file, report the level L1 / L2 / L3, match it against a harness policy (allow / ask / deny) and compile that decision to Claude Code, Cursor, Codex or Gemini CLI settings or export it to HushSpec, Rego, APS or ACS. Use when the user wants a skill's permissions declared or reviewed before install, a contract drafted, validated, signed or migrated, a conformance level or badge, a policy check, or harness permission settings made from a policy. Python 3.11+; bubblewrap on Linux for L2 and L3. Not a runtime sandbox and not a malware scanner - L3 means these files, signed by a trusted author, passed their tests, not that the skill is safe.
---

# skillpact

SkillPact adds a machine-readable contract, `skill.contract.json`, next to an
unchanged `SKILL.md`. It declares what the skill may do (capabilities, the
six effect classes `read` / `write` / `network` / `exec` / `spend` / `send`
with scopes), what it needs (binaries, packages, other skills), tests that
prove it, and a hash of every file with an ed25519 or Sigstore signature.
The normative text is `spec/spec_v0.8.md`; the schema is
`https://kajisho5.github.io/skillpact/schema/v0.8.json`.

Install from the repository (Python 3.11+):
`git clone https://github.com/kajisho5/skillpact && pip install -e skillpact/ref`.
Every command below is also `python3 -m skillpact.cli <command> ...` from
`ref/`. On Linux install `bubblewrap` (the test sandbox; without it tests run
network-isolated only and the level stops at L1) and `strace` (the exec
audit). macOS uses the built-in Seatbelt sandbox (experimental).

## Levels

| Level | Means |
|---|---|
| `none` | the contract is invalid, or files do not match their hashes |
| `L1-declared` | the contract is valid and every file matches |
| `L2-tested` | L1, and the declared tests passed in the full sandbox (bubblewrap or Seatbelt) |
| `L3-signed` | L2, integrity covers every file, and an author signature verifies against a key given with `--trusted-key` |

## Authoring a contract

1. `skillpact init <skill_dir> -o draft.json` drafts one from `SKILL.md`, the
   CLI subcommands and the MCP tools (`--from-native` reads a skill's own
   contract command; `--force` overwrites). The draft is marked unconfirmed:
   go through every capability, remove each `TODO(...)` and
   `x.init.uncertain`, then save it as `skill.contract.json`. An unconfirmed
   draft never passes L1 (`UNCONFIRMED_DRAFT`).
2. Narrow every scope (`$WORKDIR/**`, not `/**`); declare `spend` and `send`
   honestly; pin packages (`"version": "==1.2.3"`).
3. Add tests that run without network, then `skillpact test <skill_dir>`.
4. Delete `__pycache__/` and `*.pyc`, run `skillpact hash <skill_dir>`
   (lists every file; re-run after any change or `migrate`), then
   `skillpact sign <skill_dir> key.pem` (or `skillpact sign-sigstore` in CI).
5. `skillpact conformance <skill_dir> --trusted-key ed25519:<key>` reports the level.

## Commands

`<skill_dir>` holds `SKILL.md` and `skill.contract.json`; `--contract FILE`
reads the contract from elsewhere. Every command prints one JSON object.

| Task | Command |
|---|---|
| Draft a contract | `skillpact init <skill_dir> [-o draft.json] [--force] [--from-native CMD ...]` |
| Check the contract and the file hashes (L1) | `skillpact validate <skill_dir> [--contract FILE]` |
| Run the declared tests in the sandbox | `skillpact test <skill_dir> [--only ID ...] [--skills-path DIR ...] [--pass-env NAME ...] [--no-net-sandbox]` |
| Write the hash of every file into the contract | `skillpact hash <skill_dir>` |
| Make an ed25519 key | `skillpact keygen key.pem` |
| Sign | `skillpact sign <skill_dir> key.pem [--signer NAME] [--role author\|reviewer\|scanner]` |
| Sign keylessly (CI, Sigstore) | `skillpact sign-sigstore <skill_dir> [--identity-token TOKEN] [--staging]` |
| Check the signatures and hashes | `skillpact verify <skill_dir>` |
| Level L1 / L2 / L3 | `skillpact conformance <skill_dir> [--trusted-key KEY ...]` |
| Upgrade an older contract | `skillpact migrate <skill_dir> [--to VERSION] [--write]` |
| Policy decision per capability | `skillpact policy-check <skill_dir> [<skill_dir> ...] policy.json` |
| Harness settings from a policy | `skillpact policy-compile <skill_dir> policy.json --target claude-code\|cursor\|codex\|gemini-cli [--mcp-server NAME] [--render]` |
| Effects of a skill set and dangerous combinations | `skillpact compose <skill_dir> <skill_dir> ... [--trusted-key KEY ...]` |
| Runtime policy document | `skillpact export <skill_dir> policy.json --format hushspec\|rego\|aps\|acs` |
| Convert to or from MDA / AutoVault | `skillpact convert <skill_dir> --to mda\|autovault` or `skillpact convert SKILL.md --from mda\|autovault [-o draft.json]` |
| OS capability contract (kajisho5/Velisa registry): export, compare, import | `skillpact convert <skill_dir> --to os-capability [-o os.json] [--against contract.json]` or `skillpact convert contract.json --from os-capability [-o draft.json]` (spec/os_capability_mapping.md) |
| OWASP Agentic Skills Top 10 view | `skillpact owasp <skill_dir> [--no-tests]` |
| MCP server serves what the contract maps | `skillpact mcp-check <skill_dir> python3 '$SKILL_DIR/mcp/server.py'` |
| MCP tool annotations from the effects | `skillpact mcp-annotations <skill_dir>` |

Example policies: `ref/policies/solo-dev.json`, `ref/policies/strict-ci.json`.
A policy decides `allow` / `ask` / `deny` per effect and per rule, and can
require a trusted author signature (`require_signature`) and a minimum
contract version.

## Output and exit codes

stdout is one JSON object with `ok`. Exit `0` when `ok` is true, `1`
otherwise, `2` for bad arguments. `validate` returns the `errors` and `warnings` counts
and the `findings` (each with a `code` such as `INTEGRITY_MISMATCH`,
`INTEGRITY_UNLISTED` or `UNCONFIRMED_DRAFT`); `conformance` returns `level`,
the test summary and a `note` saying why a higher level was not granted;
`policy-check` returns `decision` and `decision_worst_case`;
`policy-compile` returns `config`, `schema_errors` and `lossy` (what the
harness format cannot express). With `--render`, `policy-compile` prints
the harness file itself instead of JSON.

## Being careful

* `init -o`, `hash`, `sign`, `sign-sigstore` and `migrate --write` write
  into the skill's contract (`init` without `-o` writes
  `skill.contract.json` and refuses an existing one unless `--force`).
  Changing any file after `hash` breaks L1 until it is hashed and signed
  again, so do it only when the user asked for the contract to be updated.
* Never print, copy or commit a private key; `keygen` writes it to the path
  given. Publish only the public key it returns.
* `test` and `conformance` run the skill's own test commands (sandboxed);
  run them only on a skill the user asked to check.
* A Sigstore signature that cannot be checked here is `SIGSTORE_UNVERIFIED`
  (a warning, not trusted); install `skillpact[sigstore]`.

## Report results as they are

Quote the level and the `note`; never call a skill "safe" or "verified"
beyond what the level says. L1 without a sandbox is not L2, and a valid
signature from a key nobody passed with `--trusted-key` is not L3. Runtime
enforcement belongs to the harness or a runtime policy (HushSpec, Rego).

## Not this skill's job

Running or sandboxing a skill at run time, scanning code for malware, and
judging whether a skill is safe to use. SkillPact checks what was declared,
tested and signed before install.
