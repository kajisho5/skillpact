# Design rationale

Decision records for SkillPact. Each record states the decision, why, and what was rejected. Informative.

## DR-1 Six effect classes
**Decision**: read, write, network, exec, spend, send.
**Why**: these are the decisions people make when granting a tool access. Spend and send reach outside the machine (money, people) and cannot be undone, so they are separate from network.
**Rejected**: a free list of permissions (not comparable across skills); copying one harness's tool names (ties the format to one vendor); fewer classes (merges decisions that need different answers).

## DR-2 Three levels
**Decision**: L1 declared, L2 tested, L3 signed.
**Why**: each level adds one kind of evidence (consistency, observed behaviour, identity + integrity). Simple enough for a badge.
**Rejected**: a numeric score (implies a precision we do not have); a "safe" level (cannot be proven).

## DR-3 JCS (RFC 8785) for signing, role inside the signed bytes
**Decision**: sign JCS of `{"contract", "role"}` from 0.8.
**Why**: JCS is a published standard with independent implementations; two implementations (Python, TypeScript) agree on all fuzz cases. Including the role prevents relabelling a reviewer signature as an author one.
**Rejected**: signing the raw file (whitespace changes break signatures); a custom sort (0.1–0.3 used one; it could not represent floats reliably).

## DR-4 ed25519 and Sigstore
**Decision**: both.
**Why**: ed25519 works offline with a published key and small signatures. Sigstore ties a signature to a CI or account identity without managing keys.
**Rejected**: GPG (complex key handling); only Sigstore (needs online infrastructure to verify fully).

## DR-5 File name and location
**Decision**: `skill.contract.json` next to `SKILL.md`.
**Why**: does not change `SKILL.md`, so harnesses that do not know SkillPact are unaffected; one fixed name is easy to find.
**Rejected**: frontmatter fields (would change `SKILL.md` and mix prose with machine data); a central registry (out of scope).

## DR-6 JSON, not YAML
**Decision**: JSON with the I-JSON profile.
**Why**: one interpretation (YAML has several versions and implicit typing), JSON Schema tooling everywhere, and a standard canonical form (JCS) for signing.
**Rejected**: YAML (ambiguous types, harder to canonicalize); TOML (no canonical form).

## DR-7 Tests run offline in a sandbox
**Decision**: network isolation, read-only file system, environment allowlist.
**Why**: results do not depend on the outside world, and tests cannot leak data or change the user's files.
**Rejected**: running tests with full access (unsafe); no tests (L2 would be just a claim).

## DR-8 Full file coverage (0.8)
**Decision**: integrity lists every file except a short default list and allowed excludes; agent-instruction files cannot be excluded.
**Why**: the 0.7 self-review showed that unlisted entry scripts or `CLAUDE.md` could change behaviour without breaking the signature.

## DR-9 Pre-install only, export for runtime
**Decision**: SkillPact checks before install and exports to APS / ACS / HushSpec / Rego.
**Why**: runtime policy standards already exist; a second one would split the ecosystem.

## DR-10 English normative, Japanese translation
**Decision**: from 0.8 the English text is normative.
**Why**: most implementers read English; the editor maintains the Japanese translation.
