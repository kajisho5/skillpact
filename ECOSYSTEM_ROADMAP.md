# Roadmap — skillpact

Part of the [AI Video Production OS](https://github.com/kajisho5/AI-video-production-OS/blob/main/docs/ecosystem/ROADMAP.md) ecosystem: department **統制 (Governance)**, status `active`.
Written from a read-only audit of this repository on 2026-10-30. Each step below is meant to be one pull request; tick it off by linking the PR. This repository's own feature roadmap stays in [ROADMAP.md](ROADMAP.md); this file covers only its place in the ecosystem.

## Where it stands

v0.8.0 (spec in public review until 2026-11-21). Python ref + TS verifier; 13 test modules, 49 conformance cases.

## What this repository owns

`ecosystem.json` gives each job to exactly one repository. Work outside this list belongs to its owner and is handed over, not re-implemented.

| Owned job | Status | Note |
|---|---|---|
| スキル契約・署名 | done | first adopter: imagemagick-skill (contract, unsigned) |
| スキル適合性検査 | partial | imagemagick-skill CI runs it (L2) through the Action; no OS CI yet |

## Wiring

Not related to execution. SkillPact contracts and the OS capability contract have no defined link.

## Steps

- [x] **1. Root SKILL.md** — contract authoring / checking workflow — [#32](https://github.com/kajisho5/skillpact/pull/32)
  - Done when: marketplace install shows 1 skill
- [ ] **2. SkillPact <-> OS capability contract** — `export --to os-capability` with a lossy report
  - Done when: round trip on the qc-skill fixture
- [x] **3. Reusable Action for skill repos** — document validate + test — [#33](https://github.com/kajisho5/skillpact/pull/33); first satellite: [imagemagick-skill#33](https://github.com/kajisho5/imagemagick-skill/pull/33) (L2 on every PR)
  - Done when: one satellite repo uses it
- [ ] **4. (OS side) non-blocking conformance job** — qc-skill and ingest-skill first
  - Done when: L1 or better

---
Engine for every media operation: [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) (42 tools, treated as complete). Orchestrator: [video-production-agent](https://github.com/kajisho5/video-production-agent).
