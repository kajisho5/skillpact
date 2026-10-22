# Governance

- **Editor**: shogo kajiyama (SEVENTHWELL) is the sole editor of the SkillPact specification until further notice. The editor decides on all normative changes and releases.
- **Licenses**: specification text CC BY 4.0; schemas, reference and second implementations Apache-2.0.

## Change process (SkillPact Proposal, "SPP")
1. Open a GitHub issue with the `proposal` label: problem, proposed text, compatibility impact (none / additive / breaking), affected conformance cases.
2. Discussion for at least 7 days (30 days for breaking changes once 1.0 is declared).
3. A pull request MUST update, together: the spec text, `schema/`, the conformance suite (`conformance/`), both implementations (`ref/`, `ts/`), and `CHANGELOG.md`.
4. The editor merges or declines with a written reason.

## Versioning
- `0.x`: breaking changes allowed between minor versions (see spec §17).
- `1.0` and later: minor versions are additive only; breaking changes only in a new major version.
- Each published version gets an immutable schema URL `https://kajisho5.github.io/skillpact/schema/v<version>.json`. Published schema files are never edited in place.

## Release checklist
- [ ] spec, schema, conformance suite, ref and ts updated
- [ ] `pytest` (ref) and `npm test` (ts) green; conformance suite passes on both implementations
- [ ] CHANGELOG and MIGRATION updated
- [ ] samples migrated and re-signed
- [ ] schema published on Pages, `$id` resolves (HTTP 200)

## Registries
- Error / warning codes: spec Appendix A. New codes are added by SPP.
- Vendor extensions: `x.<vendor>` — no registration needed; vendor names SHOULD be a domain or GitHub owner name.

## Security reports
Report vulnerabilities privately to kajiyama@seventh-well.com or via GitHub private vulnerability reporting on kajisho5/skillpact (see SECURITY.md). Do not open public issues for unpatched issues.
