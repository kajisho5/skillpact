# SkillPact v0.8 — Public review

**Status:** announced, open for comment · **Period:** START_DATE – END_DATE (30 days; the start date is the announcement date) · **Editor:** shogo kajiyama (SEVENTHWELL)

SkillPact is a draft standard: a `skill.contract.json` next to `SKILL.md` that declares a skill's effects (read / write / network / exec / spend / send), ships offline tests, and is signed. This review is the last step before the editor decides on v1.0.

## What to review
- Spec: [`spec/spec_v0.8.md`](spec/spec_v0.8.md) (English, normative; [Japanese translation](spec/spec_v0.8.ja.md); [web](https://kajisho5.github.io/skillpact/spec/)) · schema: <https://kajisho5.github.io/skillpact/schema/v0.8.json> · [Why SkillPact](https://kajisho5.github.io/skillpact/why/) · [schema reference](https://kajisho5.github.io/skillpact/schema/) ([日本語](https://kajisho5.github.io/skillpact/ja/schema/))
- Try it: [browser checker](https://kajisho5.github.io/skillpact/check/) (nothing is uploaded), the GitHub Action (`action.yml`), the conformance suite (`conformance/`), the Python reference implementation (`ref/`) and the TypeScript verifier (`ts/`)

## Feedback we want most
1. **Effects model** — are six effects and their scopes (incl. `@local` network) enough to describe your skills? What can't you express?
2. **Levels** — are L1 declared / L2 tested (network-isolated) / L3 signed (trusted *author* signature) useful in practice for your harness?
3. **Signing** — JCS (RFC 8785) + ed25519, Sigstore keyless, and reviewer/scanner attestations: anything unclear or unsafe?
4. **Interop** — mapping to Agent Skills `SKILL.md`, MDA, harness configs (Claude Code, Cursor, Codex, Gemini CLI).
5. **Implementability** — could you write a third implementation from the spec alone? Which conformance cases are missing?
6. **Breaking changes** you want *before* 1.0 freezes the format.

## How to give feedback
- Open an issue with the **Public review** template (one topic per issue). Proposals for normative text use the `proposal` process in [GOVERNANCE.md](GOVERNANCE.md).
- Security problems: please do not open a public issue; contact the editor privately via the [kajisho5](https://github.com/kajisho5) GitHub profile.
- Comments in Japanese or English are both welcome.

## How decisions are made
Per [GOVERNANCE.md](GOVERNANCE.md): the editor reads every comment and replies with a decision (accept / defer / decline) and a written reason in the issue. Accepted changes land as a further 0.x draft (spec, schema, conformance suite, both implementations and CHANGELOG together). After the 30 days the editor publishes a review summary; v1.0 is declared only after that, and only if no accepted breaking change is still open. Nothing in this review is final until then.
