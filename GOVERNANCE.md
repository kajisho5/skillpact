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

## Release
`.github/workflows/release.yml` runs on a tag `vX.Y.Z` (pre-releases `vX.Y.ZbN`). It checks that the tag, `ref/pyproject.toml` and `ts/package.json` carry the same version, builds the wheel, sdist and npm tarball, runs the TypeScript tests, writes `SHA256SUMS`, attests build provenance, and attaches everything to a GitHub release. A manual run builds without releasing.

Publishing runs on every tag (enabled by the editor on 2026-10-23, first release `v0.8.0b1`):
- PyPI (`skillpact`): trusted publishing (OIDC) through a pending publisher on pypi.org (account → Publishing): project `skillpact`, owner `kajisho5`, repository `skillpact`, workflow `release.yml`, environment `pypi`. No token is stored.
- npm (`skillpact`): trusted publishing can only be configured on an existing package, so the first version is published with the repository secret `NPM_TOKEN`. After that, add the trusted publisher in the package settings (repository `kajisho5/skillpact`, workflow `release.yml`, environment `npm`), remove `NODE_AUTH_TOKEN` from `release.yml` and delete the secret.
- Pre-releases go to npm under the `next` tag; GitHub marks them as pre-releases.

## Registries
- Error / warning codes: spec Appendix A. New codes are added by SPP.
- Vendor extensions: `x.<vendor>` — no registration needed; vendor names SHOULD be a domain or GitHub owner name.

## Security reports
Report vulnerabilities privately to kajiyama@seventh-well.com or via GitHub private vulnerability reporting on kajisho5/skillpact (see SECURITY.md). Do not open public issues for unpatched issues.
