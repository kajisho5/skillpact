# Why SkillPact

Agent skills run with your permissions. SkillPact lets you see, before installing one, what it is allowed to do, and lets tools check that automatically.

## The problem
- An agent skill is a folder with a `SKILL.md` and often scripts. When an agent uses it, the scripts run as **you**: your files, your network, your credentials, sometimes your money and your accounts.
- `SKILL.md` is prose written for a model. Nothing in it is machine-checkable before install: there is no standard place that says "this skill writes files here, talks to these hosts, runs these commands, can send messages".
- The OWASP Agentic Skills Top 10 (an OWASP incubator project, [owasp.org/www-project-agentic-skills-top-10](https://owasp.org/www-project-agentic-skills-top-10/)) lists the risk classes for skills, among them malicious skills, supply-chain compromise, over-privileged skills, insecure metadata, weak isolation and update drift. Incidents it cites as motivation include the "ClawHavoc" campaign (1,184 malicious skills in a public skill marketplace) and CVE-2025-59536 in Claude Code (repository configuration files triggering code execution when a project is opened), per the OWASP [assessment checklist](https://owasp.org/www-project-agentic-skills-top-10/checklist.html). We have not verified these incidents independently. See our [OWASP mapping](https://github.com/kajisho5/skillpact/blob/main/spec/owasp_mapping.md) for what SkillPact does and does not cover for each.

## What SkillPact adds
A file `skill.contract.json` next to the unchanged `SKILL.md`. The author **declares** every side effect in six classes (read, write, network, exec, spend, send) with scopes, adds **tests** that run without network, and **signs** the files. Tools check this before install.

## Benefits
- **See before you install.** A short, structured list of what the skill may touch, instead of reading the whole `SKILL.md` and its scripts.
- **Automatic allow / ask / deny.** A policy (yours or your organisation's) decides per capability. Users do not have to judge each skill by hand.
- **Fewer permission prompts.** Declared, policy-approved effects can be pre-approved in the harness; prompts are left for what is undeclared or risky.
- **Tamper detection.** Hashes cover every file in the skill (except `.git/` and `.DS_Store`), so a changed file fails verification. It detects changes; it does not stop a harness that skips verification.
- **Write the policy once.** The same decision compiles to Claude Code, Cursor, Codex and Gemini CLI settings (with a list of what each cannot express) and exports to HushSpec / Rego.
- **Trust badges for authors.** L1 / L2 / L3 show how far a skill has been declared, tested and signed.
- **An audit artifact for organisations.** A signed, versioned contract is something a security review can approve and a CI job can re-check.

### A secondary benefit: fewer tokens to answer "what can it touch?"
The contract is read mainly by **tools**, not by the model. Still, when a model or person only needs the effect list, a summary derived from the contract is much shorter than the `SKILL.md`. Measured with the `cl100k_base` tokenizer on the four sample skills (2026-10-22; none of their `SKILL.md` files links to other `.md` files):

| Skill | `SKILL.md` | Effects summary from the contract | Full contract |
|---|---|---|---|
| ffmpeg-skill | 8,459 | 109 | 158,308 |
| subtitle-skill | 2,522 | 63 | 4,150 |
| thumbnail-skill | 642 | 41 | 3,527 |
| video-editing-skill | 885 | 51 | 3,627 |

The summary is one line per non-`none` effect with its scopes (script: `review/token_measure.py`). It answers only "what may this skill touch"; it does not replace `SKILL.md`. The full contract is larger than `SKILL.md` (it includes hashes and tests) and is not meant to be put in a prompt.

## Who benefits
- **Users**: know what a skill can do before installing; fewer prompts.
- **Skill authors**: one file that every harness can read; a badge that shows the skill was tested and signed.
- **Harness vendors**: a standard input for install dialogs and permission settings, without inventing a new format.
- **Enterprises and CI**: a policy that is enforced the same way everywhere, and a reviewable, signed record.

## Why not existing tools?
- **Runtime policy standards (APS, Microsoft ACS, HushSpec)** decide each tool call while the agent runs. They do not describe what a skill declares before install. SkillPact exports to them instead of competing.
- **MDA Open Spec** has `requires` (runtime, tools, network, packages). It has no spend/send separation, no per-skill tests, and no compile step to harness settings. SkillPact converts to and from it.
- **AutoVault** declares capabilities in frontmatter and signs a manifest on the vault side; it checks declarations statically and does not run tests. SkillPact converts to and from it.
- **SkillSeal** (several projects with this name) focuses on signatures and attestations; it does not declare effects.
- **Scanners** guess after the fact. A contract gives them a declaration to compare against.

Details and sources: [comparison](https://github.com/kajisho5/skillpact/blob/main/spec/comparison.md).

## What the tests check
The tests are where a declaration meets reality: the runner starts the skill in a sandbox and fails a case that does something the contract does not declare. During the public review the editor found that 0.8 checked less than it said, and proposed fixes. Until they are merged, the right-hand column is a proposal, not the current behaviour.

| Check during `skillpact test` | 0.8 (current) | Proposed in the review |
|---|---|---|
| Network for a case without `network: true` | blocked | blocked |
| Hosts for a case with `network: true` | any host | only declared hosts, through a proxy; others fail ([#6](https://github.com/kajisho5/skillpact/pull/6)) |
| Programs a case starts (`exec`) | not checked | every program recorded from outside the sandbox; undeclared ones fail ([#5](https://github.com/kajisho5/skillpact/pull/5)) |
| Files outside the skill and `$WORKDIR` | read-only with bubblewrap | same; and without bubblewrap no L2/L3 ([#3](https://github.com/kajisho5/skillpact/pull/3)) |
| Dependency versions (`requirements.packages`) | not checked | pinned versions must match before tests run; start-up hooks reported ([#4](https://github.com/kajisho5/skillpact/pull/4)) |

The first exec check already found two undeclared programs in the flagship sample (`fc-match`, and `ffmpeg` in `media.check`). All of this happens **in the tests**: it shows whether the declaration is complete for what the tests exercise. It is still not run-time enforcement. Review log: [#1](https://github.com/kajisho5/skillpact/issues/1).

## What SkillPact does not guarantee
- A contract is the author's **claim**. L1 means it is consistent, not true.
- Tests check what they exercise, nothing more. A skill can behave differently outside its tests.
- **L3 = these exact files + a trusted author's signature + tests passed in isolation. It does not mean "safe".**
- SkillPact does not enforce anything at run time; your harness or a runtime policy must.
- Dependencies outside the skill directory are not covered.
- The checker in your browser cannot see files, so it shows L1 and signature status only.

## FAQ
**Why six effects?** They match decisions people actually make: reading and writing files, network access, running programs, spending money, and contacting people. Spend and send are separate because they reach outside the computer and cannot be undone. More classes would be harder to review; fewer would merge decisions that need different answers.

**Why sign?** Hashes show the files did not change; a signature shows who vouched for them. Without a signature, anyone who can change the files can also change the hashes.

**Why offline tests?** Tests that need the network can pass or fail for reasons outside the skill, and they could leak data. Isolated tests show the declared behaviour without network access.

**What does adoption cost?** For an author: run `skillpact init`, confirm the draft, add a few tests, hash and sign. For a harness: read one JSON file and call the checker or the library. Nothing in `SKILL.md` changes.

**Is it stable?** Not yet. This is draft 0.8; see [status](../spec/#status-of-this-document).
