# Skill Contract 0.1（ドラフト）— SKILL.md の後方互換な機械可読契約

ステータス: ドラフト / 非公開。作成 2026-10-21。名称は仮（`skill.contract.json`）。
本文は日本語、識別子は英語。キーワード MUST / SHOULD / MAY は RFC 2119 の意味。

## 0. 目的と位置づけ
Agent Skills（`SKILL.md`）は Claude Code・Cursor・Codex などで共通に読める「指示書」になったが、
**そのスキルが何をして、何を必要とし、どんな副作用を持ち、本当に動くのか** を機械が判定する手段がない。
本仕様は `SKILL.md` を一切変えずに、その隣に置く `skill.contract.json` で次を宣言する:

1. capabilities（できること・入口・入出力 JSON Schema）
2. requirements（必要なバイナリ・ランタイム・環境変数、バージョン条件と検査コマンド）
3. permissions（副作用 6 区分 read / write / network / exec / spend / send と範囲）
4. compat（エージェント別の検証状況、OS、提供インターフェース）
5. tests（どのエージェントでも実行できる適合テスト）
6. integrity（ファイルハッシュと署名）

## 1. 先行事例と差分（要約、出典は末尾）
| 先行 | あるもの | 足りないもの |
|---|---|---|
| Agent Skills 仕様（agentskills.io）/ Anthropic SKILL.md | name, description, license, compatibility(自由文), metadata, allowed-tools(実験的) | 副作用の区分、入出力スキーマ、必要バイナリの機械判定、テスト、署名 |
| Claude Code / Codex / Cursor の skills 実装 | 各社が SKILL.md を読む・allowed-tools 等の独自拡張 | 相互に意味が揃った権限語彙がない |
| MCP tool annotations | readOnlyHint / destructiveHint / idempotentHint / openWorldHint（ヒント扱い） | スキル単位でない、spend/send の区別なし、テストなし |
| skills.sh 等のレジストリ | 配布・検索・インストール数 | 「動くか」「何をするか」の検証情報 |
| npm package.json / OpenAPI | engines・bin・依存 / 入出力スキーマ・security | エージェント副作用、適合テスト |

**差分（本仕様が埋める穴）**: 「副作用の宣言」×「検証可能なテスト」×「エージェント横断の互換表明」を 1 ファイルで持つ規格は存在しない。

## 2. 配置と後方互換
- ファイル名は `skill.contract.json`、`SKILL.md` と同じディレクトリ（MUST）。
- `SKILL.md` の frontmatter / 本文を変更してはならない（MUST NOT）。契約を知らないエージェントは従来どおり動く。
- `skill.name` は frontmatter の `name` と一致（MUST）。`name` 規則は agentskills.io に従う（小文字英数とハイフン、64 字以内）。
- JSON Schema: `ref/skillpact/schema.json`（Draft 2020-12）。未知キーは `x.<vendor>.*` のみ許可。

## 3. permissions（副作用 6 区分）
各区分に `level`（`none` | `scoped` | `any`）、`scope`、`why`、`confirm`（`never` | `each` | `session`）。

| 区分 | 意味 | scope の書式 |
|---|---|---|
| read | ファイル・データの読み取り | パス glob。`$INPUT` `$OUTPUT` `$WORKDIR` `$SKILL_DIR` |
| write | ファイル作成・変更・削除 | 同上 |
| network | 外部通信 | ホスト glob（`*.github.com`） |
| exec | 外部コマンド実行 | コマンド名 |
| spend | 課金・購入・有料 API | サービス名 |
| send | 人に届く送信・投稿（メール、SNS、Slack） | 宛先種別 / サービス名 |

規則:
- capability の `effects` に含まれる区分は permissions で `none` 以外（MUST、違反は `UNDECLARED_EFFECT`）。
- `destructive: true` の capability は write/send/spend のいずれかを持つべき（SHOULD）。
- `dry_run.supported` と `dry_run.effects` で「試し実行時の副作用」を別に宣言できる。
- spend / send を `any` にするのは警告（`HIGH_RISK`）。

## 4. capabilities
`id`（ドット区切り）、`summary`、`entry`（`cli` 配列 / `mcp_tool` / `doc`）、`effects`、`destructive`、`idempotent`、
`dry_run`、`inputs` / `outputs`（JSON Schema）、`requires`（requirements の name 参照、MUST 存在）。
`entry.cli` の `$SKILL_DIR/...` は実在しなければならない（`ENTRY_MISSING`）。

## 5. requirements
`binaries` / `runtimes`: `name`, `version`（`>=4.4` 等）, `check`（コマンド配列）, `version_regex`, `optional`, `when`。
`env`: `name`, `required`, `secret`, `description`。秘密値そのものは書かない（MUST NOT）。

## 6. compat
`agents.<id>.status` = `tested` | `expected` | `unsupported`、`version`、`tested_at`、`notes`。
推奨 id: `claude-code`, `cursor`, `codex`, `gemini-cli`, `grok-bot`, `copilot`。`os`, `interfaces`（`skill-md` `cli` `mcp-stdio` `mcp-http`）。
`tested` は §7 のテストをそのエージェント環境で通した場合にのみ名乗れる（SHOULD）。

## 7. 適合テスト（tests）
- `setup`: コマンド配列の列。一時作業ディレクトリ `$WORKDIR` で実行（テスト用素材は生成して作る。例: ffmpeg lavfi）。
- `cases[]`: `id`, `capability`, `run`, `timeout_s`, `network`（既定 false）, `expect`。
- `expect`: `exit_code`, `stdout_contains`, `stdout_json_schema`, `stdout_json[]`（`path` は `$.a.b` 形式、`equals`/`min`/`max`/`exists`）, `files[]`（`path`, `exists`, `min_bytes`）。
- ランナーは permissions.network が `none` なら各ケースをネットワーク隔離して実行するべき（SHOULD、参照実装は `unshare -rn`）。
- ランナーは実行前後で `$SKILL_DIR` の変更を検知し、write scope に `$SKILL_DIR` が無ければ失敗とする（MUST）。
- 結果は JSON（`passed` / `total` / `cases[].failures`）。

## 8. integrity と署名（最小）
- `integrity.files`: 相対パス → sha256。`validate` で照合（`INTEGRITY_MISMATCH`）。
- `integrity.signatures[]`: `type: ed25519`, `key: "ed25519:<base64>"`, `sig`, `signer`。
  署名対象は `signatures` を除いた契約全体の正規化 JSON（キー順ソート、区切り `,` `:`、UTF-8）。files ハッシュを含むので中身の改ざんも検出。
- 鍵の信頼（誰の鍵か）は本仕様の外。ハーネスポリシー（harness_policy 0.1）の `trusted_keys` で決める。将来 Sigstore / SSH 署名を追加予定。

## 9. バージョニング
- `contract_version` = 仕様版（今は `"0.1"`）。0.x の間は破壊的変更あり。1.0 以降は minor で追加のみ。
- `skill.version` = スキル自身の SemVer。permissions が広がる変更は **major を上げる**（SHOULD）。ハーネスは広がりを検知したら再承認を求められる。

## 10. 検証コード（参照実装）
エラー: `SKILL_MD_MISSING` `FRONTMATTER_MISSING` `FM_NAME` `FM_DESCRIPTION` `CONTRACT_MISSING` `SCHEMA` `NAME_MISMATCH`
`DUP_CAPABILITY` `UNDECLARED_EFFECT` `BAD_SUBSCHEMA` `UNKNOWN_REQUIREMENT` `ENTRY_MISSING` `TEST_UNKNOWN_CAPABILITY`
`INTEGRITY_MISSING` `INTEGRITY_MISMATCH` `SIGNATURE_INVALID`。
警告: `FM_NAME_DIR` `BODY_LONG` `HIGH_RISK` `DESTRUCTIVE_NO_EFFECT` `UNUSED_PERMISSION` `NO_TESTS`。

## 11. 適合レベル
- **L1 Declared**: validate がエラーなし。
- **L2 Tested**: L1 + tests 全通過（ネットワーク隔離あり）。
- **L3 Signed**: L2 + integrity 一致 + 有効な署名。

## 12. ライセンス
仕様文書 CC BY 4.0、スキーマ・参照実装 Apache-2.0（予定。公開前に shogo 確認）。

## 13. サンプル
`samples/ffmpeg-skill/skill.contract.json`（kajisho5/ffmpeg-skill 2.10.7 / commit 4334225 のコピー。元リポジトリには書き込んでいない）。
4 capability（probe / cut / loudness / export）、network=none、4 テスト（probe 値、dry-run で書かない、cut の結果、存在しない入力で失敗）を box 上で L2 通過。

## 出典
- Agent Skills 仕様: https://agentskills.io/specification
- Anthropic Agent Skills: https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills/overview
- MCP tool annotations: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- skills.sh: https://skills.sh
- npm package.json: https://docs.npmjs.com/cli/configuring-npm/package-json
- OpenAPI 3.1: https://spec.openapis.org/oas/v3.1.0
