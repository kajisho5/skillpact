# Security policy

## Reporting a vulnerability
Please report vulnerabilities **privately**:
- e-mail **kajiyama@seventh-well.com** (subject: "SkillPact security"), or
- GitHub private vulnerability reporting on kajisho5/skillpact.

Do not open a public issue for an unfixed problem. Include the affected version (spec, schema, `ref`, `ts`, Action), steps or a minimal contract that reproduces it, and the impact.

## What happens next
- We aim to acknowledge within 5 business days and to agree on a fix and disclosure date with you. This is a best-effort project by a small team; there is no bug bounty.
- Fixes to the specification follow GOVERNANCE.md; security-relevant changes may be merged before the usual discussion period and explained afterwards.
- We credit reporters in the CHANGELOG unless you ask us not to.

## Scope
In scope: the specification (e.g. ways to reach L3 without the guarantees of §16), the schemas, the reference implementation (`ref/`), the TypeScript implementation (`ts/`), the browser checker, the GitHub Action, and the conformance suite.
Out of scope: third-party skills that publish contracts, harnesses, and runtime policy engines (report to their maintainers).

## Supported versions
Only the latest draft (currently 0.8) receives fixes until 1.0.

## Signing keys
The SEVENTHWELL sample-signing public key is in `keys/public/`. The test key in `conformance/vectors/` has a published seed and must never be trusted.
