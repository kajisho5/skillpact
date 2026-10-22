# skillpact (reference validator, v0.1)

```
pip install -r requirements.txt
python3 -m skillpact.cli validate <skill_dir>            # SKILL.md frontmatter + skill.contract.json
python3 -m skillpact.cli test <skill_dir>                # run declared conformance tests (sandboxed with bubblewrap; the `unshare -rn` fallback isolates the network only and gives no L2)
python3 -m skillpact.cli hash <skill_dir>                # write integrity.files (sha256)
python3 -m skillpact.cli keygen key.pem ; ... sign <skill_dir> key.pem ; ... verify <skill_dir>
python3 -m skillpact.cli policy-check <skill_dir> policies/solo-dev.json      # allow/ask/deny per capability
python3 -m skillpact.cli policy-compile <skill_dir> policies/solo-dev.json --target claude-code|cursor|codex|gemini-cli
python3 -m pytest -q tests                                   # 19 tests
```
Exit code 0 = ok / not denied, 1 = failure / denied. Output is JSON.
Sample: `../samples/ffmpeg-skill/skill.contract.json` (copy of kajisho5/ffmpeg-skill @4334225, SKILL.md untouched).
