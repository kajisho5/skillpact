# Adoption guides

How to start, by role. Packages are not published yet; install from the repository: `git clone https://github.com/kajisho5/skillpact && pip install -e skillpact/ref`.

## Users
1. Look for `skill.contract.json` next to `SKILL.md`, or a SkillPact badge.
2. Paste the contract into the [checker](../check/) (runs in your browser, sends nothing). Read the effects list: does the skill touch more than it needs?
3. For the full level, run `python3 -m skillpact.cli conformance <skill_dir> --trusted-key <author key>`. L3 only means "these files, signed by that key, tests passed".
4. Keep your harness's own permission prompts on. SkillPact does not enforce anything at run time.

## Skill authors
1. `python3 -m skillpact.cli init <skill_dir> -o skill.contract.json` creates a draft. Confirm every item and remove `TODO(...)` markers and `x.init.uncertain` (otherwise `UNCONFIRMED_DRAFT`).
2. Narrow scopes (`$WORKDIR/**` rather than `/**`). Declare spend and send honestly.
3. Add tests that run without network. Run `skillpact test <skill_dir>`; install bubblewrap on Linux for the full sandbox.
4. `skillpact hash <skill_dir>` (lists every file), then `skillpact sign <skill_dir> key.pem` or `sign-sigstore` in CI. Publish your public key.
5. Add the GitHub Action, pinned to a commit SHA, on `pull_request` (not `pull_request_target`):
```yaml
- uses: kajisho5/skillpact@<commit-sha>
  with: { path: ., min-level: L2 }
```
6. Show the badge from [badges](../badges/) that matches the level CI reports.

## Harness vendors
1. On install, read `skill.contract.json` and validate it (Python library or the TypeScript `validate`).
2. Match it against the user's policy (`match_policy`); show `decision` and `decision_worst_case` per capability.
3. Turn the result into your permission settings; see `policy-compile` for Claude Code, Cursor, Codex and Gemini CLI, and its `lossy` list.
4. Re-verify integrity right before running (TOCTOU) and ask again when permissions widen between versions.
5. Run the conformance suite against your validator: `python3 conformance/run.py --cmd '<your validator> {dir}'`.

## Enterprises and CI
1. Write one policy: defaults per effect, rules, `trusted_keys`, `require_signature: true`, `min_contract_version: "0.8"`.
2. In CI, run `conformance` on every skill and fail below the level you require.
3. Distribute compiled harness settings from that policy; review the `lossy` list for each harness.
4. Use runtime policy (HushSpec, Rego for APS / ACS) for enforcement during execution.
5. Keep the signed contract as the review record for each approved skill version.
