# Specification documentation checklist

Audit of SkillPact 0.8 against the material usually expected of W3C / IETF specifications and OpenSSF / CNCF projects. EN = English, JA = Japanese. "Pages" = kajisho5.github.io/skillpact.

| # | Item | Status | Location (repo) | Pages (en / ja) |
|---|---|---|---|---|
| 1 | Abstract | done | `spec/spec_v0.8.md` Abstract | `/spec/#abstract` · `/ja/spec/` |
| 2 | Status of this document | done | spec "Status of this document"; `REVIEW.md` | `/spec/` · `/ja/spec/` · `/about/` |
| 3 | Scope and non-goals | done | spec §2 | `/spec/` · `/ja/spec/` |
| 4 | Terminology / glossary | done | spec §1 | `/spec/` · `/ja/spec/` |
| 5 | Conformance language (BCP 14) | done | spec §1 | `/spec/` |
| 6 | Conformance classes and requirements | done | spec §16.2 | `/spec/` · `/ja/spec/` |
| 7 | Conformance levels | done | spec §16.1 | `/spec/` · `/why/` |
| 8 | Conformance test suite | done (48 cases, both implementations pass) | `conformance/` | — |
| 9 | Test vectors | done | `conformance/vectors/jcs-ed25519.json` | — |
| 10 | Examples, minimal to full | done | spec Appendix B; `samples/`; `examples/` | `/spec/#appendix-b-examples` |
| 11 | Design rationale / decision records | done (DR-1…DR-10) | `content/en/rationale.md` | `/rationale/` · `/ja/rationale/` |
| 12 | Security considerations | done | spec §18 | `/spec/` · `/ja/spec/` |
| 13 | Threat model | done | spec §18.1 | `/spec/` · `/ja/spec/` |
| 14 | Privacy considerations | done | spec §19 | `/spec/` · `/ja/spec/` |
| 15 | Interoperability and mappings | done | spec §12–14, §20; `spec/comparison.md`; `spec/owasp_mapping.md` | `/spec/` · `/why/` |
| 16 | Versioning, stability, deprecation policy | done | spec §17; `GOVERNANCE.md` | `/spec/` |
| 17 | Normative vs informative references | done | spec §21 | `/spec/` |
| 18 | Error / finding code registry with severities | done | spec Appendix A | `/spec/` |
| 19 | Schemas with immutable URLs | done | `docs/schema/v0.8.json`, `policy-v0.8.json` | `/schema/` · `/ja/schema/` |
| 20 | Adoption guides per role (user, author, harness vendor, enterprise/CI) | done | `content/en/guides.md` | `/guides/` · `/ja/guides/` |
| 21 | Why / motivation, benefits, who benefits | done | `content/en/why.md`; README | `/why/` · `/ja/why/` · top pages |
| 22 | FAQ | done | why page "FAQ" | `/why/#faq` · `/ja/why/` |
| 23 | Limitations / what it does not guarantee | done | why page; spec §16.1, §18.2 | `/why/` · `/ja/why/` |
| 24 | Governance and decision process | done | `GOVERNANCE.md` | `/about/` · `/ja/about/` |
| 25 | CONTRIBUTING | done | `CONTRIBUTING.md` | linked from `/about/` |
| 26 | Code of conduct | done (Contributor Covenant 2.1) | `CODE_OF_CONDUCT.md` | linked from `/about/` |
| 27 | Security policy / vulnerability reporting | done (kajiyama@seventh-well.com) | `SECURITY.md` | `/about/` |
| 28 | Patent / IPR statement | done (royalty-free non-assertion covenant with defensive termination, EN + JA) | `IPR.md`, `LICENSE`, `LICENSE-spec-CC-BY-4.0.txt` | `/about/` |
| 29 | Trademark / brand and badge usage | done | `TRADEMARKS.md` | `/about/`, `/badges/` |
| 30 | Citation | done | `CITATION.cff` | `/about/` |
| 31 | Changelog | done | `CHANGELOG.md`; spec Appendix E | — |
| 32 | Migration guide | done | `spec/MIGRATION.md` | — |
| 33 | Roadmap | done | `ROADMAP.md` | `/about/` |
| 34 | Acknowledgements | done | `ACKNOWLEDGEMENTS.md` | `/about/` |
| 35 | Media type / file naming registration note | done (not registered; to be considered after 1.0) | spec Appendix D | `/spec/` · `/about/` |
| 36 | Accessibility of the site | done (self-assessed, WCAG 2.2 AA target) | `ACCESSIBILITY.md` | `/about/` |
| 37 | Translations and which text is normative | done (EN normative) | spec Status | `/spec/` · `/ja/spec/` |
| 38 | Licence for text and code | done | `LICENSE*`, README | footer of every page |
| 39 | Independent implementations | done (Python reference, TypeScript) | `ref/`, `ts/` | — |
| 40 | Public review / feedback channel | done (open 2026-10-22 – 2026-11-21 JST; tracking issue #1) | `REVIEW.md`, `.github/ISSUE_TEMPLATE/`, `review/tracking-issue.md` | review banner on every page (en / ja) |

Open items (need a decision by the editor): none.
