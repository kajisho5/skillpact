# Showcase: kajisho5/ffmpeg-skill (L3 signed)
One real skill that shows what a SkillPact-conformant skill looks like. Informative; the Japanese original is [showcase.md](showcase.md). Test figures were measured on 2026-10-21 (JST) on box (Debian 13, ffmpeg 7.1, Python 3.13). File counts and `policy-compile` output were re-taken on 2026-10-22 with the 0.8 reference implementation (0.8 requires full file coverage and compiles the worst case).

## In one line
Without changing a single byte of `SKILL.md`, a `skill.contract.json` next to it lets a machine decide:
- for each of the 42 tools, what it reads and writes and where it may connect
- what it needs to run (binaries, ffmpeg filters / encoders)
- whether it actually works (78 tests)
- whether it was changed (hashes of 331 files and a signature)

## Contents
| Item | Value |
|---|---|
| capabilities | 42, one per MCP tool name. execution 32 / verification 4 / analysis 3 / analysis_and_execution 3 |
| inputs / outputs | input JSON Schema for every tool (CLI flags in `x-cli`, exclusive options as `allOf/not`) and output JSON Schema |
| effects | read / exec for every tool; write for the 39 tools that produce files; no network. Exception: caption and silence with `--transcribe` may reach huggingface.co and similar hosts and run whisper-type CLIs (`conditional_effects`) |
| write scope | `$OUTPUT`, `$INPUT_DIR/**`, `$WORKDIR/**`, `$TMPDIR/**`. Inputs are not changed (checked by the safety tests) |
| requirements | ffmpeg / ffprobe ≥ 5.0, python3 ≥ 3.9, node optional. 24 ffmpeg features (`filter:subtitles`, `filter:vidstabdetect`, `encoder:libx264`, ...) are checked on the machine |
| tests | 78: 41 real runs (one per tool), 32 dry-run checks that nothing is written, 2 failure cases, 2 safety cases (overwrite refused, input unchanged), 2 check pass/fail cases (loudness fails before normalising, passes after `--normalize`). All network-isolated, about 40 s. The reference runner uses bubblewrap (`bwrap`) on Linux and falls back to `unshare -rn` (network only, `fs_isolated: false`) |
| native contract | converted from `scripts/_contract.py contract --json` (tool list, version, requirements); tests check that the tool set, version and ffmpeg requirements match |
| MCP | `mcp-check` against the real server (`FFMPEG_SKILL_MCP_FULL=1`): names and input properties of all 42 tools match the contract |
| signature | sha256 over 331 files (full coverage, required from 0.8: evals 90, docs 70, scripts 58, tests 33, .claude 20, others) + ed25519. SEVENTHWELL skill-signing key (fingerprint SHA256:r8icjIp2v7H/uzrVov8ksXK0MPGJy1s+HWaDnKwI3j4) |

## What a harness sees (`policy-check`, solo developer policy `ref/policies/solo-dev.json`)
- Normal use: **allow**. No prompt at install.
- Worst case: **ask**, because `--transcribe` in caption and silence may download a model (network) and run a speech CLI such as whisper (exec). To make it allow, the policy has to allow both the hosts (huggingface.co, ...) and the speech CLIs.
- `policy-compile` output for all four harnesses passes their schemas. Settings follow the worst case (including conditional effects): network becomes ask; exec is decided per program (proposal #12), so ffmpeg, ffprobe and python3 stay allowed and only the speech engines ask.

```
.claude/settings.json      permissions.allow: Edit(./**), Bash(ffmpeg *), Bash(ffprobe *), Bash(python3 *), mcp__ffmpeg-skill__cut, ... (42 MCP tools)
                           permissions.ask:   Bash(whisper *), Bash(whisper-cli *), WebFetch(domain:huggingface.co), ...   (per program, proposal #12)
.codex/config.toml         approval_policy = "on-request" / sandbox_mode = "workspace-write"
.gemini/policies/*.toml    [[rule]] toolName="cut" mcpName="ffmpeg-skill" decision="allow"
                           [[rule]] toolName="run_shell_command" commandPrefix="whisper " decision="ask_user"   (ffmpeg: allow)
.cursor/cli.json           allow: Write(**), Mcp(ffmpeg-skill:cut), ... (Shell is not allowed, so it prompts)
```

## Reproduce
```
cd ref && pip install -r requirements.txt
python3 ../samples/build_ffmpeg_contract.py         # native contract -> contract, tests, hashes, signature (SEVENTHWELL key)
python3 -m skillpact.cli conformance ../samples/ffmpeg-skill --trusted-key "$(cat ../keys/public/seventhwell-skill-signing.pub)"
#   -> {"level": "L3-signed", "tests": {"passed": 78, "total": 78}}
FFMPEG_SKILL_MCP_FULL=1 python3 -m skillpact.cli mcp-check ../samples/ffmpeg-skill python3 '$SKILL_DIR/mcp/server.py'
python3 -m skillpact.cli policy-check ../samples/ffmpeg-skill policies/solo-dev.json
```

## Suggestions for ffmpeg-skill (proposals, not sent)
1. Add annotations to MCP `tools/list`; the output of `mcp-annotations` can be used as is.
2. Make `batch.py` / `report.py` `--json-brief` print only JSON on stdout (tests currently work around this with `stdout_json_mode: last`).
3. Add an option to the native `_contract.py contract --json` that emits `skill.contract.json`, so no conversion is needed.
