# Roadmap — skillpact

Part of the [AI Video Production OS](https://github.com/kajisho5/AI-video-production-OS/blob/main/docs/ecosystem/ROADMAP.md) ecosystem: department **統制 (Governance)**, status `active`.
Written from a read-only audit of this repository on 2026-10-30. Each step below is meant to be one pull request; tick it off by linking the PR. This repository's own feature roadmap stays in [ROADMAP.md](ROADMAP.md); this file covers only its place in the ecosystem.

## Where it stands

v0.8.1 (spec in public review until 2026-11-21). Python ref + TS verifier; 19 test modules, 61 conformance cases.

## What this repository owns

`ecosystem.json` gives each job to exactly one repository. Work outside this list belongs to its owner and is handed over, not re-implemented.

| Owned job | Status | Note |
|---|---|---|
| スキル契約・署名 | done | first adopter: imagemagick-skill (contract, unsigned) |
| スキル適合性検査 | partial | imagemagick-skill CI runs it (L2) through the Action; the OS runs it weekly, non-blocking, on every Skill with a contract ([Velisa#127](https://github.com/kajisho5/Velisa/pull/127)) |

## Wiring

Not related to execution. SkillPact contracts and the OS capability contract are linked by `skillpact convert --to / --from os-capability` (step 2): the OS view lives under `x.os` in the SkillPact contract.

## Steps

- [x] **1. Root SKILL.md** — contract authoring / checking workflow — [#32](https://github.com/kajisho5/skillpact/pull/32)
  - Done when: marketplace install shows 1 skill
- [x] **2. SkillPact <-> OS capability contract** — `export --to os-capability` with a lossy report — [#34](https://github.com/kajisho5/skillpact/pull/34): shipped as `convert --to / --from os-capability` (plus `--against` to compare with a skill's published OS contract), since `export` is the policy -> runtime-policy command; mapping in [spec/os_capability_mapping.md](spec/os_capability_mapping.md)
  - Done when: round trip on the qc-skill fixture (OS -> SkillPact -> OS identical on Velisa's qc-skill fixture and its four other registry fixtures; `ref/tests/test_os_capability.py`)
- [x] **3. Reusable Action for skill repos** — document validate + test — [#33](https://github.com/kajisho5/skillpact/pull/33); first satellite: [imagemagick-skill#33](https://github.com/kajisho5/imagemagick-skill/pull/33) (L2 on every PR)
  - Done when: one satellite repo uses it
- [x] **4. (OS side) non-blocking conformance job** — qc-skill and ingest-skill first — [Velisa#127](https://github.com/kajisho5/Velisa/pull/127) (`skillpact-conformance.yml`, ADR-014): every Skill in `ecosystem.json` with a `skill.contract.json` is checked; today that is imagemagick-skill, which reached L2. qc-skill and ingest-skill have no contract yet, and the job picks them up once they add one.
  - Done when: L1 or better
- [ ] **5. Progress events and error classes in the contract** — contracts declare the progress events an op emits (JSON lines: step, percent, ETA) and map every error code to one class (`input`, `environment`, `engine`, `policy`, `transient`); conformance cases check both. Field review 2026-11-05 (Velisa ROADMAP, third round)
  - なぜ要るか：エージェントがどのスキルでも「あと何分か」「直すのは何か」を同じ読み方で扱える
  - Done when: conformance cases for both, and the OS weekly run reports which skills declare them
  - Status: partial ([#38](https://github.com/kajisho5/skillpact/pull/38), spec §7.1, erratum 0.8.x, optional). `x.runtime` declares `progress` and `errors.classes`. The validators report `RUNTIME_DECL`, and the runner reports `PROGRESS_EVENT`, `PROGRESS_MISSING` and `ERROR_UNCLASSIFIED`. Conformance has 8 new cases (57 in total), with the runner cases run through `run.py --test-cmd`. `conformance` and the Action expose `declares`. Released in 0.8.1. Still open: the OS weekly run has to read the Action's `declares` output (Velisa `skillpact-conformance.yml`).
- [x] **6. Idempotency conformance** — Done (spec §7.1, erratum 0.8.x): `capabilities[].x.runtime.idempotency` (`bit_exact` / `content_equivalent` / `none`, schema `runtime-v0.8-r1.json`, must agree with `idempotent`). The runner runs each case of a `bit_exact` op a second time after removing its `expect.files`, compares the outputs by SHA-256, and fails with `IDEMPOTENCY_DIFFERS`. `idempotent: true` alone is checked only by `test --check-idempotent`, and only reported: on ffmpeg-skill's sample, 33 cases were compared and none differed. Conformance case `v08x-idempotency-nondeterministic` catches a fixture skill whose output changes on every run ([#39](https://github.com/kajisho5/skillpact/pull/39)) — an op whose contract says `bit_exact` or idempotent is run twice on a fixture and the outputs compared by hash; a skill that declares it and differs fails
  - なぜ要るか：再実行・途中再開で結果が変わらないという約束を、各スキルについて機械で確かめられる
  - Done when: a conformance case that catches a non-deterministic fixture skill

---
Engine for every media operation: [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) (42 tools, treated as complete). Orchestrator: [video-production-agent](https://github.com/kajisho5/video-production-agent).
