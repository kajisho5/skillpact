# SkillPact 0.2（ドラフト）
ステータス: ドラフト / 非公開。2026-10-21（JST）。名称 SkillPact（2026-10-22 決定）。ファイル名 `skill.contract.json` は維持。
v0.1（`spec_v0.1.md`）に対する差分仕様。書いていない部分は v0.1 のまま有効。
ライセンス: 本文 CC BY 4.0 / スキーマ・参照実装 Apache-2.0（shogo 承認済み）。

## 0. スコープ（確定）
1. **インストール前の照合**: スキル契約（宣言された副作用）× ハーネスポリシー → capability ごとに allow / ask / deny。
2. **ハーネス設定への変換**: Claude Code / Cursor / Codex / Gemini CLI のネイティブ設定を生成し、各社の公開スキーマで検証する。
3. **実行時の強制はしない**: HushSpec / APS / ACS / 各ハーネスに任せ、そこへ書き出す（§8）。

## 1. 変更履歴（v0.1 → v0.2）
| # | 変更 | 理由（どのサンプルで見つかったか） |
|---|---|---|
| 1 | `contract_version` に `"0.2"` を追加（`"0.1"` も有効） | — |
| 2 | トップに `kind`: `tool` \| `instructions` | agent-instruction-hygiene は SKILL.md だけで実行物がない |
| 3 | `skill.native_contract.cli`: スキル独自の機械可読契約を出すコマンド | ffmpeg / imagemagick / video-editing / subtitle / thumbnail / qc はどれも独自の `contract --json` を持っている |
| 4 | `requirements.skills[]`（`name`, `version`, `env`, `optional`）。ランナーが見つけて `env` に入れる | video-editing / subtitle は ffmpeg-skill に依存し、`*_FFMPEG_SKILL_DIR` で場所を探す |
| 5 | `requirements.packages[]`（`pypi` / `npm` …、`import` 名） | thumbnail-skill は Pillow が必要 |
| 6 | `binaries[].alternatives`（どれか 1 つあれば可） | imagemagick-skill は `magick` か macOS の `sips` |
| 7 | `binaries[].features_check` と `capability.requires_features` / `optional_features`（`filter:subtitles`, `encoder:libx264` など） | ffmpeg は「入っている」だけでは不十分。ビルドによってフィルタやエンコーダが無い |
| 8 | `capability.conditional_effects[]`（`effect`, `when`, `scope`） | ffmpeg-skill の `--transcribe` は、初回だけ音声モデルをダウンロードする（通信が発生） |
| 9 | `capability.effect_scopes`（スキル全体の範囲より狭い、capability ごとの範囲。広げるのは不可＝`SCOPE_WIDENED`） | 全ツールが whisper 系 exec を持つように見えてしまい、判定が厳しくなりすぎた |
| 10 | 範囲の変数に `$INPUT_DIR` `$TMPDIR` を追加。遠隔リソースは `remote:<host>/<path>` | ffmpeg は既定で入力の隣に書く。batch.py は入力フォルダの下に書く。github-solo は GitHub 上の設定を書き換える |
| 11 | テストケースに `env`, `skip_unless_env`, `tags` を追加。`expect` に `stderr_contains`, `validate_outputs`, `stdout_json_mode`（`strict` が既定、`last` は互換用） | packaged skill は `PYTHONPATH=$SKILL_DIR/src` が必要。トークンが要るテストは自動でスキップ。batch / report は JSON の前後にログを出す |
| 12 | ネットワーク隔離は **全ケースが既定**（`network: true` のケースだけ解除）。v0.1 は permissions.network が none の場合だけだった | github-solo の `dependabot` は「通信しない」と書いたが、隔離して実行したら通信していた（契約を修正） |
| 13 | MCP 対応（§6）、`mcp-check`、`mcp-annotations` | ffmpeg-skill の MCP サーバー（42 ツール）と突き合わせ |
| 14 | 適合レベルの判定コマンド `conformance`（L1 / L2 / L3） | — |
| 15 | `init`（§5）、`export`（§8）、ハーネス設定のスキーマ検証（§7） | — |
| 16 | ポリシー判定で `decision_worst_case` を出す（条件付きの副作用まで含めた最悪の場合） | §1-8 の結果 |
| 17 | 検証コードの追加: `SCOPE_WIDENED` `UNKNOWN_FEATURE_KIND`（エラー）、`UNTESTED_CAPABILITY` `NO_ENTRY`（警告） | — |

## 2. 条件付きの副作用
```json
"conditional_effects": [{"effect": "network", "when": "--transcribe with an uncached model", "scope": ["huggingface.co", "*.hf.co"]}]
```
- 該当する区分は permissions で `none` 以外にする（MUST）。スキル全体の `permissions.*.scope` は「起こりうる全部」の上限。
- ハーネスの判定は `decision`（通常利用）と `decision_worst_case`（条件付きも含む）の 2 つ。ハーネスは worst case が ask なら、条件を満たしたとき（例: `--transcribe` が付いたとき）に確認するべき（SHOULD）。

## 3. 必要な機能（features）
```json
{"name": "ffmpeg", "version": ">=5.0", "features_check": {"filter": ["ffmpeg","-hide_banner","-filters"], "encoder": ["ffmpeg","-hide_banner","-encoders"]}}
```
`requires_features: ["filter:subtitles"]` は、`features_check.filter` の出力に `subtitles` という単語があれば満たす。足りなければテスト前に `requirements not met` で止まる。

## 4. 遠隔リソースと秘密情報
- `remote:github.com/repos/*/*/settings/**` のように、ホスト＋パスの glob で書く。ハーネス側でホストを network に、パスを write / read に対応させる。
- トークンは `requirements.env[].secret: true` で名前だけ宣言する。値は書かない（MUST NOT）。それを使うテストは `skip_unless_env` で書く。

## 5. `init`（既存スキルから下書きを作る）
- スキル独自の契約（`scripts/_contract.py contract --json` など）があれば、そこから変換する（`--from-native CMD` で指定も可）。
- 無ければ推測で作る。SKILL.md の description と本文、`scripts/*.py`、`pyproject` / `package.json` から次を拾う:
  - バイナリ名
  - 通信 / 送信 / 課金 / 書き込みを示す語
  - console scripts
  - バージョン
  - Python 依存
- 確信が持てない項目は `x.init.uncertain`（JSON Pointer の一覧）に入れ、`why` に `TODO(init): confirm` を付ける。人が確認し終えるまで L1 を名乗らないこと（SHOULD）。
- MCP サーバーのスクリプトには `--help` テストを付けない（stdio で待ち続けて止まるため）。

## 6. MCP との対応
capability → MCP tool annotations の導出規則（`mcp_annotations` で上書き可）:
| annotation | 規則 |
|---|---|
| `readOnlyHint` | effects（条件付きを含む）に write / send / spend が無い |
| `destructiveHint` | `destructive` |
| `idempotentHint` | `idempotent` |
| `openWorldHint` | effects（条件付きを含む）に network / send / spend がある |

`mcp-check <skill> <server cmd…>` は `tools/list` を実際に呼んで、次を照合する:
- ツール名
- 入力プロパティ（`x-cli-only` の付いた CLI 専用フラグは除く）
- サーバーが annotations を返す場合はその値

## 7. ハーネス設定の生成と検証
`policy-compile --target claude-code|cursor|codex|gemini-cli [--mcp-server NAME] [--render]`
| 対象 | 出力ファイル | 検証に使うスキーマ |
|---|---|---|
| Claude Code | `.claude/settings.json`（`permissions.allow/ask/deny`、`Bash(x *)`、`WebFetch(domain:…)`、`mcp__srv__tool`） | SchemaStore `claude-code-settings.json`（公開） |
| Codex | `.codex/config.toml`（`approval_policy`, `sandbox_mode`, `sandbox_workspace_write.network_access`） | `developers.openai.com/codex/config-schema.json`（公開） |
| Gemini CLI | `.gemini/policies/*.toml`（`[[rule]]` toolName / mcpName / commandPrefix / decision / priority） | 公開スキーマなし → ドキュメントから書き起こしたスキーマ |
| Cursor | `.cursor/cli.json`（`Shell()` `Read()` `Write()` `WebFetch()` `Mcp(srv:tool)`。ask はリストに書かない＝毎回確認） | 公開スキーマなし → ドキュメントから書き起こしたスキーマ |

変換で失われるもの: Codex には通信先の許可リストが無いため、`sandbox.network: allowlist` は `network_access = true` になる（ホストの絞り込みは失われる）。Cursor には ask が無い。どのハーネスにも `limits`（ループ回数・予算）を書く標準キーが無い。
Codex と Gemini の TOML は、Python 標準の `tomllib` で読み戻してから検証する。スキーマのコピーは `ref/skillpact/harness_schemas/`（2026-10-21 取得）。

## 8. 実行時ポリシーへの書き出し
- `export --format hushspec`: HushSpec 1.0 文書を作る。中身は次の 4 つ（未知フィールドなし、HushSpec の厳格な検証に合わせる）:
  - `tool_access`（allow / require_confirmation / block、default は block）
  - `egress`（許可されたホストのみ、default は block）
  - `path_allowlist`
  - `forbidden_paths`（`.env` / `.ssh` / `*.pem`）
- `$VARS` はホスト側で置き換える前提。HushSpec の host glob は `*` が 1 ラベルだけなので、`*.x` は `**.x` に変換する。
- `export --format rego|aps|acs`: OPA/Rego モジュール（`decision` は allow / ask / deny）。APS と ACS はどちらも Rego を使えるので、その中身として使える。
  - **APS / ACS の manifest の配線は生成しない**（形式をまだ検証していないため）。
  - Rego は OPA 1.21 で構文チェックと評価をテスト済み。

## 9. 適合レベル（v0.1 を明確化）
- **L1 declared**: `validate` がエラー 0。
- **L2 tested**: L1 に加え、`test` が全部通る（ネットワーク隔離あり。スキップは失敗に数えないが件数を報告する）。
- **L3 signed**: L2 に加え、integrity が一致し、ed25519 署名が有効。`--trusted-key` を指定した場合は、その鍵での署名に限る。

## 10. 実際のスキルで見つかったこと（スキル側への提案。どれも未修正・未送信）
- ffmpeg-skill:
  - MCP の `tools/list` に annotations が無い（42 件すべて）。契約から導出した値をそのまま付けられる。
  - `batch.py` / `report.py` は `--json-brief` でも stdout にログが混ざる。
  - 契約のサイズが約 630 KB ある（大半は出力スキーマ）。
- github-solo-skill:
  - SKILL.md の description が 1137 字で、agentskills.io の上限 1024 字を超えている。
  - どのマニフェストにもバージョンが書かれていない。
- video-editing-skill: pyproject は 0.2.0、独自契約は 0.4.0 で、バージョンが食い違っている。
- imagemagick-skill: 独自契約に「成果物を作るか」の項目が無く、変換すると write が未使用扱いになる。
