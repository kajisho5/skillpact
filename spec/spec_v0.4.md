# SkillPact 0.4 — 統合仕様（ドラフト）

- ステータス: ドラフト / 未公開。2026-10-22（JST）。v0.1〜v0.3 を 1 本に統合した完全版（差分文書ではない）。
- 正式 URL（予定）: 仕様 `https://kajisho5.github.io/skillpact/`、スキーマ `.../schema/v0.4.json`、ポリシー `.../schema/policy-v0.3.json`（0.4 で変更なし）
- ライセンス: 本文 CC BY 4.0 / スキーマ・参照実装 Apache-2.0。© 2026 SEVENTHWELL (shogo kajiyama)
- 本文は日本語、識別子は英語。

## 1. 規範語
本文書の「MUST」「MUST NOT」「REQUIRED」「SHALL」「SHALL NOT」「SHOULD」「SHOULD NOT」「RECOMMENDED」「MAY」「OPTIONAL」は、BCP 14（RFC 2119、RFC 8174）に従い、すべて大文字で現れた場合に限りそこに定める意味で解釈する。

## 2. 目的とスコープ
SkillPact は Agent Skills（`SKILL.md`）の隣に置く機械可読の契約 `skill.contract.json` を定める。対象は次の 3 つ:
1. **宣言**: スキルが何をし、何を必要とし、どんな副作用を持つか。
2. **インストール前の照合**: 契約 × ハーネスポリシー → capability ごとに allow / ask / deny。
3. **ハーネス設定への変換**: Claude Code / Cursor / Codex / Gemini CLI のネイティブ設定、HushSpec / Rego への書き出し。

対象外: 実行時の強制（APS / ACS / HushSpec / 各ハーネスに任せる）、静的解析・LLM による検査（スキャナーとは競合せず、その入力になる）、配布レジストリ。

## 3. 用語
- **契約（contract）**: `skill.contract.json` の内容。
- **生産者（producer）**: 契約を書く・生成するもの。
- **検証者（validator）**: 契約を検証し適合レベルを判定するもの。
- **ランナー（runner）**: 適合テストを実行するもの。
- **ハーネス（harness）**: スキルを読み込むエージェント実行環境。
- **効果（effect）**: §6 の 6 区分の副作用。

## 4. 配置と後方互換
- 契約のファイル名は `skill.contract.json` で、`SKILL.md` と同じディレクトリに置かなければならない（MUST）。
- 生産者は `SKILL.md` の frontmatter と本文を契約のために変更してはならない（MUST NOT）。契約を知らないハーネスは従来どおり動く。
- `skill.name` は frontmatter の `name` と一致しなければならない（MUST、`NAME_MISMATCH`）。`name` は Agent Skills 仕様に従う（小文字英数とハイフン、64 字以内）。
- 契約は UTF-8 の JSON（RFC 8259）でなければならない（MUST）。

## 5. 文書構造
契約は §15 の JSON Schema（Draft 2020-12）に適合しなければならない（MUST、`SCHEMA`）。主なトップレベル:

| キー | 必須 | 内容 |
|---|---|---|
| `$schema` | 任意 | スキーマ URL（MAY） |
| `contract_version` | 必須 | `"0.1"`〜`"0.4"` |
| `kind` | 任意 | `tool`（既定）\| `instructions`（実行物なし） |
| `skill` | 必須 | `name`, `version`（SemVer）, `native_contract.cli` |
| `permissions` | 必須 | §6 |
| `capabilities` | `kind: tool` で必須 | §7 |
| `requirements` | 任意 | §8 |
| `compat` | 任意 | §9 |
| `tests` | 任意（L2 以上で必須） | §10 |
| `integrity` | 任意（L3 で必須） | §11 |
| `x` | 任意 | 拡張。`x.<vendor>.*` のみ |

- 拡張は `x.<vendor>.*` に置かなければならない（MUST）。それ以外の未知キーはスキーマエラーとなる。
- `x` 直下のキー（vendor 名）は `^[a-z0-9][a-z0-9-]*$` に従わなければならない（MUST）。
- 検証者は `x` の中身を理解できなくても無視して処理を続けなければならない（MUST）。

## 6. permissions（効果 6 区分）
各区分は `level`（`none` | `scoped` | `any`）、`scope`（配列）、`why`、`confirm`（`never` | `each` | `session`）を持つ。

| 区分 | 意味 | scope の書式 |
|---|---|---|
| read | ファイル・データの読み取り | パス glob |
| write | 作成・変更・削除 | パス glob、`remote:<host>/<path>` |
| network | 外部通信 | ホスト glob（`*.github.com`） |
| exec | 外部コマンド実行 | コマンド名 |
| spend | 課金・購入・有料 API | サービス名 |
| send | 人に届く送信・投稿 | 宛先種別 / サービス名 |

- パス変数: `$INPUT` `$INPUT_DIR` `$OUTPUT` `$WORKDIR` `$SKILL_DIR` `$TMPDIR`。検証者はこれ以外の `$` 変数を未定義として扱い、警告 `UNKNOWN_VARIABLE` を出すべきである（SHOULD）。
- 遠隔リソースは `remote:<host>/<path-glob>` で書く。ハーネスはホストを network に、パスを read / write に対応させるべきである（SHOULD）。
- `level: scoped` の区分は 1 つ以上の `scope` を持たなければならない（MUST、`SCOPE_EMPTY`）。
- スキル全体の `scope` は、条件付きを含めて起こりうる全範囲の上限でなければならない（MUST）。
- spend / send を `any` にした場合、検証者は警告 `HIGH_RISK` を出さなければならない（MUST）。

## 7. capabilities
- 各 capability は `id`（ドット区切り、契約内で一意。MUST、`DUP_CAPABILITY`）、`summary`、`entry`、`effects` を持つ。
- `entry` は `cli`（配列）/ `mcp_tool` / `doc` のいずれか。`cli` 中の `$SKILL_DIR/...` は実在しなければならない（MUST、`ENTRY_MISSING`）。entry が無い場合は警告 `NO_ENTRY`。
- `effects` に含まれる区分は、permissions で `none` 以外でなければならない（MUST、`UNDECLARED_EFFECT`）。
- `effect_scopes` で capability ごとの範囲を狭めてよい（MAY）。スキル全体の範囲を広げてはならない（MUST NOT、`SCOPE_WIDENED`）。
- `conditional_effects[]`（`effect`, `when`, `scope`）は条件付きの効果を表す。該当区分は permissions で `none` 以外でなければならない（MUST）。
- `destructive: true` の capability は write / send / spend のいずれかを持つべきである（SHOULD、警告 `DESTRUCTIVE_NO_EFFECT`）。
- `idempotent`、`dry_run`（`supported`, `effects`）、`inputs` / `outputs`（JSON Schema。不正なら `BAD_SUBSCHEMA`）は任意。
- `requires` は requirements の名前を参照し、存在しなければならない（MUST、`UNKNOWN_REQUIREMENT`）。
- `requires_features` / `optional_features` は `<kind>:<name>` 形式（例 `filter:subtitles`）。kind は `features_check` に定義されていなければならない（MUST、`UNKNOWN_FEATURE_KIND`）。
- `mcp_annotations` で §12 の導出値を上書きしてよい（MAY）。

## 8. requirements
- `binaries[]` / `runtimes[]`: `name`, `version`（`>=4.4` 等）, `check`, `version_regex`, `optional`, `when`, `alternatives`（どれか 1 つで可）, `features_check`。
- `packages[]`: `ecosystem`（`pypi` / `npm` …）, `name`, `import`。
- `skills[]`: `name`, `version`, `env`, `optional`。ランナーは依存スキルを見つけ、その場所を `env` に入れるべきである（SHOULD）。
- `env[]`: `name`, `required`, `secret`, `description`。秘密値を契約に書いてはならない（MUST NOT）。

## 9. compat
- `agents.<id>`: `status`（`tested` | `expected` | `unsupported`）, `version`, `tested_at`, `notes`。推奨 id: `claude-code` `cursor` `codex` `gemini-cli` `grok-bot` `copilot`。
- `tested` は、§10 のテストをそのハーネス環境で通した場合にのみ名乗るべきである（SHOULD）。
- `os`、`interfaces`（`skill-md` `cli` `mcp-stdio` `mcp-http`）。

## 10. 適合テスト（tests）
- `setup`: コマンド配列の列。一時ディレクトリ `$WORKDIR` で実行する。テスト素材はその場で生成するべきである（SHOULD）。
- `cases[]`: `id`, `capability`（存在しなければならない。MUST、`TEST_UNKNOWN_CAPABILITY`）, `run`, `timeout_s`, `network`（既定 false）, `env`, `skip_unless_env`, `tags`, `expect`。
- `expect`: `exit_code`, `stdout_contains`, `stderr_contains`, `stdout_json_schema`, `stdout_json[]`（`path` `$.a.b`、`equals`/`min`/`max`/`exists`）, `stdout_json_mode`（`strict` 既定 / `last`）, `files[]`, `validate_outputs`。
- ランナーは、`network: true` でない全ケースをネットワークから隔離して実行しなければならない（MUST）。隔離できない環境では L2 の判定を出してはならない（MUST NOT）。
- ランナーは実行前後で `$SKILL_DIR` の変更を検知し、write scope に `$SKILL_DIR` が無いのに変更があればそのケースを失敗にしなければならない（MUST）。
- `skip_unless_env` が満たされないケースはスキップとし、失敗に数えない。ただし件数を報告しなければならない（MUST）。
- 結果は JSON（`passed` / `skipped` / `total` / `cases[].failures`）で出すべきである（SHOULD）。

## 11. integrity と署名
- `integrity.files`: 相対パス → sha256（16 進小文字）。検証者は全ファイルを照合しなければならない（MUST、`INTEGRITY_MISMATCH` / `INTEGRITY_MISSING`）。
- `integrity.signatures[]` は次のいずれか:
  - ed25519: `{"type":"ed25519","key":"ed25519:<base64>","sig":<base64>,"signer"}`
  - Sigstore: `{"type":"sigstore","identity":<SAN>,"issuer":<OIDC issuer>,"bundle":<Sigstore bundle>}`
- 署名対象バイトは §11.1 の正規化で作らなければならない（MUST）。files のハッシュを含むので中身の改ざんも検出できる。
- Sigstore の検証者は bundle の検証に加え、identity と issuer を自分の信頼リストと照合しなければならない（MUST）。
- 鍵・identity の信頼はハーネスポリシーの `trusted_keys`（`ed25519:<b64>` / `sigstore:<issuer>|<identity>`）で決める。署名が数学的に正しくても、信頼されていない鍵の署名で L3 を名乗ってはならない（MUST NOT）。参照実装の `conformance` は `--trusted-key` に一致する署名がなければ L2 に留める。

### 11.1 正規化（確定：RFC 8785 JCS、2026-10-22 shogo 承認）
- `contract_version` が `"0.4"` 以上の契約では、署名対象バイトは、`integrity.signatures` を取り除いた契約全体を RFC 8785 JSON Canonicalization Scheme（JCS）で直列化した UTF-8 バイト列でなければならない（MUST）。
- `contract_version` が `"0.1"`〜`"0.3"` の契約では、検証者は互換のため旧方式（キーを辞書順ソート、区切り `,` `:`、空白なし、非 ASCII はそのまま UTF-8）で検証しなければならない（MUST）。生産者は新しく署名するとき、契約を 0.4 以上に上げて JCS で署名するべきである（SHOULD）。
- 正規化の方式は `contract_version` から決まる。`integrity.canonicalization`（`jcs` | `legacy-sorted`）は参考情報で、検証者はこれに頼ってはならない（MUST NOT）。
- 既知の答え（テストベクトル）: `conformance/vectors/jcs-ed25519.json`。数値の表記、Unicode とエスケープ、UTF-16 順のキー並び、署名の除外を含む。テスト専用の鍵（公開シード）を使い、実際の署名に使ってはならない（MUST NOT）。

## 12. MCP との対応
| annotation | 導出規則 |
|---|---|
| `readOnlyHint` | effects（条件付きを含む）に write / send / spend が無い |
| `destructiveHint` | `destructive` |
| `idempotentHint` | `idempotent` |
| `openWorldHint` | effects（条件付きを含む）に network / send / spend がある |

`mcp-check` は `tools/list` を呼び、ツール名・入力プロパティ（`x-cli-only` は除く）・annotations を照合する。

## 13. ハーネスポリシーと変換
- ポリシーはスキーマ `policy-v0.3.json` に従う。判定は capability ごとに `decision`（通常）と `decision_worst_case`（条件付き効果を含む）の 2 つを出さなければならない（MUST）。
- worst case が ask の場合、ハーネスは条件を満たした時点で確認するべきである（SHOULD）。
- `policy-compile --target claude-code|cursor|codex|gemini-cli` はネイティブ設定を生成し、公開スキーマ（無いものはドキュメントから書き起こしたスキーマ）で検証しなければならない（MUST）。変換で失われる情報（例: Codex にホスト許可リストが無い、Cursor に ask が無い、`limits` を書く標準キーが無い）は報告するべきである（SHOULD）。
- `export --format hushspec|rego|aps|acs`: HushSpec 1.0 文書、または OPA/Rego モジュール（`decision` = allow / ask / deny）。APS / ACS の manifest への配線は範囲外。

## 14. 他形式との変換
- `convert` は MDA Open Spec 1.0（`metadata.mda.requires`）と AutoVault（`capabilities` / `tools_required`）との双方向変換を行う。
- export は落ちた情報の一覧 `lossy` と、元の契約へのポインタ＋sha256 を出さなければならない（MUST）。
- import は推測した箇所を `x.import.uncertain` に列挙しなければならない（MUST）。tests は空なので L1 止まり。
- `init` は既存スキルから下書きを作る。不確かな項目を `x.init.uncertain` に入れ、人が確認するまで L1 を名乗るべきではない（SHOULD NOT）。

## 15. スキーマ
- 契約: `schema/v0.4.json`（`$id` `https://kajisho5.github.io/skillpact/schema/v0.4.json`、Draft 2020-12）。参照実装の `ref/skillpact/schema.json` と同一内容。
- ポリシー: `policy-v0.3.json`（0.4 で変更なし）。

## 16. 適合（Conformance）
### 16.1 適合レベル（契約に対して）
- **L1 Declared**: 検証者のエラーが 0。
- **L2 Tested**: L1 に加え、§10 の全ケースが（隔離して）通過。スキップは件数を報告する。
- **L3 Signed**: L2 に加え、integrity が一致し、信頼済みの ed25519 鍵または Sigstore identity による有効な署名が 1 つ以上ある。

### 16.2 実装の適合（役割ごと）
- **適合する生産者**: 出力する契約は §15 のスキーマに適合し、§4〜§11 の MUST を満たさなければならない。
- **適合する検証者**: §6〜§11 の全 MUST を検査し、付録 A のエラーコードで報告しなければならない。未知の `x.*` で失敗してはならない。
- **適合するランナー**: §10 の隔離・`$SKILL_DIR` 変更検知・スキップ報告を満たさなければならない。
- **適合するハーネス**: §13 の 2 種類の判定に従うべきである。
- 実装を問わない適合テストスイート（`conformance/`）は v0.5 で提供予定。

## 17. バージョニングと互換性
- `contract_version` は仕様の版。検証者は自分が知っている全ての版を受け付けなければならない（MUST）。知らない **major** 版は拒否しなければならない（MUST、`CONTRACT_VERSION_UNSUPPORTED`）。0.x の間は minor 版ごとに破壊的変更がありうるため、知らない 0.x 版も同様に拒否する。知らない **minor** 版（1.0 以降）は、警告 `CONTRACT_VERSION_NEWER` を出したうえで既知のフィールドとして処理してよい（MAY）。
- 0.x の間は破壊的変更がありうる。0.1〜0.3 の契約は 0.4 でもそのまま有効。
- 1.0 以降: minor 版は追加のみ（任意フィールド、新しいエラーコード、新しい enum 値）。必須化・削除・意味の変更は major 版でのみ行う。
- 非推奨: 削除の少なくとも 1 minor 版前に非推奨と明記し、検証者は警告を出すべきである（SHOULD）。
- `skill.version` はスキル自身の SemVer。permissions が広がる変更では major を上げるべきである（SHOULD）。ハーネスは広がりを検知したら再承認を求めるべきである（SHOULD）。
- 0.x → 1.0 の移行ガイドと `migrate` コマンドは v0.5 で提供予定。

## 18. セキュリティの考慮事項 — **【下書き：v0.5 で完成】**
扱う予定の項目（TODO）:
- 宣言の虚偽: 契約は自己申告であり、L2 の隔離テストで一部しか確かめられない。実行時の強制は別途必要。
- 署名鍵の漏えい・失効・交換の手順。
- ダウングレード攻撃（古い版や弱い署名方式への差し替え）。
- TOCTOU（検証した後でファイルが差し替わる）。
- 依存スキル・パッケージの改ざん。
- 正規化の不一致による署名回避（§11.1。0.4 で JCS に統一）。
- 脅威モデル: 攻撃者の能力と、SkillPact が守らないもの。
- OWASP Agentic Skills Top 10 との対応は `owasp_mapping.md`（`skillpact owasp` で出力）。

## 付録 A. エラーコード
エラー: `SKILL_MD_MISSING` `FRONTMATTER_MISSING` `FM_NAME` `FM_DESCRIPTION` `CONTRACT_MISSING` `SCHEMA` `NAME_MISMATCH` `DUP_CAPABILITY` `UNDECLARED_EFFECT` `BAD_SUBSCHEMA` `UNKNOWN_REQUIREMENT` `ENTRY_MISSING` `TEST_UNKNOWN_CAPABILITY` `INTEGRITY_MISSING` `INTEGRITY_MISMATCH` `SIGNATURE_INVALID` `SCOPE_WIDENED` `UNKNOWN_FEATURE_KIND` `CONTRACT_VERSION_UNSUPPORTED` `SCOPE_EMPTY`
警告: `FM_NAME_DIR` `BODY_LONG` `HIGH_RISK` `DESTRUCTIVE_NO_EFFECT` `UNUSED_PERMISSION` `NO_TESTS` `UNTESTED_CAPABILITY` `NO_ENTRY` `UNKNOWN_VARIABLE` `CONTRACT_VERSION_NEWER`
（意味と重大度の正式な登録表は v0.5 で作る）

## 付録 B. 変更履歴
- 0.4: 署名の正規化を RFC 8785（JCS）に変更（0.1〜0.3 は旧方式で検証）、テストベクトルを追加。新しいエラー・警告 `CONTRACT_VERSION_UNSUPPORTED` `SCOPE_EMPTY` `UNKNOWN_VARIABLE` `CONTRACT_VERSION_NEWER`。v0.1〜0.3 を 1 本に統合。BCP 14 の規範語で書き直し。適合（役割別）とバージョン・互換の方針を追加。スキーマ `$id` を v0.4 へ。セキュリティの考慮事項は下書き。0.3 以前の契約はそのまま有効（ただし `scoped` で scope が空のものは 0.4 からエラー）。
- 0.3: Sigstore 署名、MDA/AutoVault 変換、OWASP 対応、APS/ACS 書き出し、正式 `$id`。
- 0.2: `kind`、native_contract、依存スキル・パッケージ、features、条件付き効果、effect_scopes、遠隔リソース、全ケース隔離、MCP 対応、policy-compile、HushSpec/Rego 書き出し。
- 0.1: 初版。

## 付録 C. 参考
Agent Skills 仕様 https://agentskills.io/specification ／ RFC 2119, RFC 8174 ／ RFC 8785 (JCS) ／ JSON Schema 2020-12 ／ MCP tool annotations ／ Sigstore ／ HushSpec ／ OPA
