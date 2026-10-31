# SkillPact contract <-> OS capability contract

Informative, 0.8.x. Reference implementation: `ref/skillpact/interop.py` (`to_os`, `from_os`, `os_check`), CLI `skillpact convert --to / --from os-capability`. Tests: `ref/tests/test_os_capability.py`.

The AI video production OS ([kajisho5/Velisa](https://github.com/kajisho5/Velisa)) keeps a registry of which skill provides which capability. Each media skill publishes an **OS capability contract** with `contract --json` (`<skill> contract --json`); its shape is `registry/capability_contract.schema.json`, read by `registry/contract.py`. A copy of the schema is in `ref/skillpact/os_schemas/` (commit in `FETCHED.txt`), and the registry's five real fixtures (qc-skill, media-analysis-skill, video-editing-skill, transcription-skill, ffmpeg-skill) are in `examples/os-capability/`.

## What each side says

| | SkillPact contract | OS capability contract |
|---|---|---|
| question | what may this skill touch, does it work, who signed it | which capability ids does this skill provide, under which tool |
| identity | `skill.name` (Agent Skills name, e.g. `qc-skill`) | `skill_id`, `id` or `skill.id` (OS id, e.g. `qc`) |
| unit | capability = one entry point (CLI / MCP tool) with its effects | `provides[]` entry = one capability id (`<domain>.<verb>`, e.g. `measure.audio.loudness`) with `lifecycle` and `tool_id` |
| effects, scopes, requirements, tests, integrity, signatures | yes | no |
| lifecycle (`PROPOSED` ... `RETIRED`), registry collisions | no | yes |
| dependencies on other skills | `requirements.skills[]` (`name`, `version`) | `dependencies[]` (`skill_id`, `version_range`) |

The two axes differ: one SkillPact capability (one tool) can provide several OS capability ids. qc-skill has one CLI entry, OS tool `qc/run`, which provides 10 ids. So a SkillPact capability maps to an OS `tool_id`, and the OS ids hang under it.

## Where the OS view lives in a SkillPact contract

Under the `x.os` vendor extension (§5), so no schema change is needed and a signed contract covers it like any other field:

```json
{
  "skill": {"name": "qc-skill", "version": "0.1.0"},
  "capabilities": [{
    "id": "cli.qc", "summary": "...", "entry": {"cli": ["python3", "-m", "qc_skill.cli"]}, "effects": ["read", "exec"],
    "x": {"os": {"tool_id": "qc/run", "provides": [
      {"id": "measure.audio.loudness", "lifecycle": "EXPERIMENTAL", "checks": ["audio.integrated_loudness_within_tolerance"]}
    ]}}
  }],
  "x": {"os": {"document": {"skill_id": "qc"}}}
}
```

- `x.os.document` (top level): the OS document without `provides`, kept as is (identity, `contract_version`, `not_provided`, ...).
- `x.os.order` (top level, only when needed): the original order of the `provides` ids, when one tool's entries were not next to each other (media-analysis-skill).
- `capabilities[].x.os`: `tool_id` and that tool's `provides` entries without `tool_id`, with every skill-specific field (`checks`, `kind`, ...).

## Export: `skillpact convert <skill_dir> --to os-capability`

Output: `document` (the OS contract), `lossy`, `guessed`, `schema_errors` (the document checked against the vendored OS schema, plus duplicate ids), and with `--against os.json` also `mismatches`. `-o` writes the document. Exit code 1 on schema errors or mismatches.

- Identity: from `x.os.document`; without it, `skill_id` = `skill.name`.
- Version: `skill.version` replaces the OS version (flat `version`, or `skill.version` for the nested shape). A non-semver OS version is kept, and so is a missing one when `skill.version` is the import placeholder `0.0.0`.
- `provides`: the `x.os` entries of each capability with its `tool_id`. A capability without `x.os` gets one entry: `id` = capability id, `lifecycle` = `EXPERIMENTAL` (SkillPact has no lifecycle, listed in `guessed`), `tool_id` = `<skill id>/<entry.mcp_tool or capability id>`, `input_schema` / `output_schema` from `inputs` / `outputs`, `mutates_input` from `destructive`.
- `dependencies`: from `requirements.skills[]` with a version and not optional, when `x.os.document` has none.
- `x-skillpact`: pointer to the contract and its sha256, as for MDA / AutoVault (§14). The OS schema allows extra top-level keys.
- Lossy (always): permissions and scopes, per-capability effects / scopes / conditional effects, dry run, idempotent, summary, entry, binaries / runtimes / packages / env, tests, integrity and signatures, compat. Conditionally: `destructive` -> `mutates_input` (destructive also covers deletes and sends), capability ids where `entry.mcp_tool` differs, skills without a version.

## Import: `skillpact convert os.json --from os-capability [-o draft.json]`

The document must pass the OS schema (and have no duplicate ids); otherwise the command fails with the problems. Result: one capability per `tool_id`, id = `tool_id` without the `<skill id>/` prefix (`qc/run` -> `run`), with the entries under `x.os`; `inputs` / `outputs` / `destructive` when every entry of the tool agrees. `skill.name` = `package` when it is a valid name, else the OS id. Effects and permissions are unknown (all `none`, `effects: []`) and listed in `x.import.uncertain`, with `TODO(import)` summaries, so the draft is `UNCONFIRMED_DRAFT` (§14) until a person declares effects, entries and tests.

## Compare: `--against`

`os_check` exports the contract and compares identity, version and every `provides` entry field by field with the OS contract a skill actually publishes (`<skill> contract --json > os.json`). It names each difference (`provides 'x'.lifecycle: contract 'EXPERIMENTAL', OS contract 'STABLE'`, ids only on one side). Use it in a skill's CI to keep both contracts in step.

## Round trip (done criterion of ECOSYSTEM_ROADMAP step 2)

- OS -> SkillPact -> OS gives the same document back (apart from the added `x-skillpact` pointer) for the qc-skill fixture and the four other registry fixtures, covering all three identity shapes and interleaved tools.
- SkillPact -> OS -> SkillPact on `examples/contracts/qc-skill.contract.json` keeps what the OS contract carries (skill name, version, capability ids), and a second export is identical.
- The qc-skill example plus its `x.os` view exports exactly the registry's qc-skill fixture, and `--against` reports only the version the trimmed fixture lacks.

## What this deliberately is not

- Not a change to the SkillPact schema or to the OS schema. Nothing here is normative.
- Not a trust bridge: a SkillPact level (L1-L3) says nothing about OS lifecycle, and an OS `STABLE` entry says nothing about effects.
- Not live: no skill process is run. Fetching `contract --json` is the caller's job, as in the OS registry.
