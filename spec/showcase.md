# 適合スキルの見本: kajisho5/ffmpeg-skill（L3 signed）
「`SkillPact` に準拠したスキルとはこういうもの」を、実物 1 つで示す文書。数値は 2026-10-21（JST）に box（Debian 13、ffmpeg 7.1、Python 3.13）で実測した。ファイル数と `policy-compile` の出力は 2026-10-22 に 0.8 の参照実装で取り直した（0.8 で全ファイル網羅・最悪ケースでの変換に変わったため）。

## 1 行でいうと
SKILL.md は 1 バイトも変えずに、隣に `skill.contract.json` を置くだけで、次のことを機械が判定できるようになる。
- 42 ツールそれぞれについて、何を読み書きし、どこへ通信しうるか
- 動作に必要なもの（バイナリ、ffmpeg のフィルタ／エンコーダ）
- 本当に動くか（78 テスト）
- 改ざんされていないか（331 ファイルのハッシュと署名）

## 中身
| 項目 | 値 |
|---|---|
| capabilities | 42（MCP ツール名と 1 対 1）。内訳は execution 32 / verification 4 / analysis 3 / analysis_and_execution 3 |
| 入出力 | 全ツールに入力 JSON Schema（CLI フラグは `x-cli`、排他オプションは `allOf/not`）と出力 JSON Schema |
| 副作用 | read / exec は全ツール。write は成果物を作る 39 ツール。network は無し。例外は caption と silence で、`--transcribe` のときだけ huggingface.co などへの通信と whisper 系の実行が起きる（`conditional_effects`） |
| 書き込み範囲 | `$OUTPUT`、`$INPUT_DIR/**`、`$WORKDIR/**`、`$TMPDIR/**`。入力は変更しない（安全テストで確認） |
| 必要なもの | ffmpeg / ffprobe 5.0 以上、python3 3.9 以上、node は任意。ffmpeg の機能 24 個（`filter:subtitles`、`filter:vidstabdetect`、`encoder:libx264` など）を実際に確認 |
| テスト | 78 件。各ツールの実実行 41 件、dry-run で何も書かないことの確認 32 件、失敗系 2 件、安全系 2 件（上書き拒否・入力不変）、check の合否 2 件（正規化前は loudness で失敗、`--normalize` で書き出した後は合格）。全件ネットワーク隔離で、約 40 秒。参照ランナーは Linux では bubblewrap（`bwrap`）を使い、ない場合は `unshare -rn`（ネットワークのみ隔離、`fs_isolated: false`）に落ちる |
| 独自契約との一致 | `scripts/_contract.py contract --json` からツール一覧・バージョン・必要条件を変換。テストでツール集合・バージョン・ffmpeg の要件が一致することを確認 |
| MCP | `mcp-check` で、実サーバー（`FFMPEG_SKILL_MCP_FULL=1`）の 42 ツールのツール名と入力プロパティが契約と一致 |
| 署名 | sha256 で 331 ファイル（0.8 で全ファイル網羅が必須に。evals 90、docs 70、scripts 58、tests 33、.claude 20 ほか）＋ ed25519 署名。SEVENTHWELL skill-signing key（指紋 SHA256:r8icjIp2v7H/uzrVov8ksXK0MPGJy1s+HWaDnKwI3j4） |

## ハーネスから見た結果（`policy-check`、個人開発向けポリシー `ref/policies/solo-dev.json`）
- 通常利用は **allow**。インストール時に確認は出ない。
- 最悪の場合は **ask**。caption と silence の `--transcribe` が、モデルのダウンロード（network）と音声認識 CLI の実行（whisper など、exec）を起こしうるため。allow にするには、ポリシーで両方（huggingface.co などのホストと音声認識 CLI）を許可する必要がある。
- `policy-compile` で 4 ハーネスの設定を生成すると、どれもスキーマ検証を通る。設定は最悪ケース（条件付きの効果を含む）に合わせて出るため、network は ask になる。exec はプログラムごとに判定するので（提案 #12）、ffmpeg・ffprobe・python3 は allow のまま、音声認識エンジンだけが ask になる。

```
.claude/settings.json      permissions.allow: Edit(./**), Bash(ffmpeg *), Bash(ffprobe *), Bash(python3 *), mcp__ffmpeg-skill__cut, ... (MCP 42)
                           permissions.ask:   Bash(whisper *), Bash(whisper-cli *), WebFetch(domain:huggingface.co), ...   (per program, proposal #12)
.codex/config.toml         approval_policy = "on-request" / sandbox_mode = "workspace-write"
.gemini/policies/*.toml    [[rule]] toolName="cut" mcpName="ffmpeg-skill" decision="allow"
                           [[rule]] toolName="run_shell_command" commandPrefix="whisper " decision="ask_user"   (ffmpeg: allow)
.cursor/cli.json           allow: Write(**), Mcp(ffmpeg-skill:cut), ...（Shell は allow に入らず、確認が出る）
```

## 再現手順
```
cd ref && pip install -r requirements.txt
python3 ../samples/build_ffmpeg_contract.py         # 独自契約→契約、テスト生成、ハッシュ、署名（SEVENTHWELL 鍵）
python3 -m skillpact.cli conformance ../samples/ffmpeg-skill --trusted-key "$(cat ../keys/public/seventhwell-skill-signing.pub)"
#   -> {"level": "L3-signed", "tests": {"passed": 78, "total": 78}}
FFMPEG_SKILL_MCP_FULL=1 python3 -m skillpact.cli mcp-check ../samples/ffmpeg-skill python3 '$SKILL_DIR/mcp/server.py'
python3 -m skillpact.cli policy-check ../samples/ffmpeg-skill policies/solo-dev.json
```

## ffmpeg-skill 側にあるとさらに良いもの（提案。未送信）
1. MCP の `tools/list` に annotations を付ける。値は `mcp-annotations` の出力をそのまま使える。
2. `batch.py` / `report.py` の `--json-brief` で、stdout を JSON だけにする（いまはテストで `stdout_json_mode: last` を使って回避している）。
3. 独自の `_contract.py contract --json` に、`skill.contract.json` を出すオプションを付ける。そうすれば変換が要らなくなる。
