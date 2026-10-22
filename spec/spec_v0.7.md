# SkillPact 0.7 — 統合仕様（ドラフト、1.0 直前）

- ステータス: ドラフト / 未公開。2026-10-22（JST）。v0.1〜v0.6 を含む完全版（差分文書ではない）。
- 正式 URL（予定）: 仕様 `https://kajisho5.github.io/skillpact/`、スキーマ `.../schema/v0.7.json`、ポリシー `.../schema/policy-v0.3.json`（0.4 で変更なし）
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
- `skill.name` は frontmatter の `name` と一致しなければならない（MUST、`NAME_MISMATCH`）。
- frontmatter の `name` は、`SKILL.md` を含むディレクトリの名前と一致しなければならない（MUST、`FM_NAME_DIR`。Agent Skills 仕様に合わせる）。検証者は `contract_version` が 0.7 以上ならエラー、0.6 以下なら警告とする。契約をスキルの外に置いて検証する場合（参照実装の `--contract`）は対象外。`name` は Agent Skills 仕様に従う（小文字英数とハイフン、64 字以内）。
- 契約は UTF-8 の JSON（RFC 8259）でなければならない（MUST）。

## 5. 文書構造
契約は §15 の JSON Schema（Draft 2020-12）に適合しなければならない（MUST、`SCHEMA`）。主なトップレベル:

| キー | 必須 | 内容 |
|---|---|---|
| `$schema` | 任意 | スキーマ URL（MAY） |
| `contract_version` | 必須 | `"0.1"`〜`"0.7"` |
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
- `@` で始まる scope は予約トークンである。0.7 で定義するのは network の `@local` だけで、ループバック（`localhost`、`127.0.0.0/8`、`::1`）、プライベートアドレス（`10/8`、`172.16/12`、`192.168/16`、`fc00::/7`）、`*.local` を表す。MDA の `network: local` と対応する。ハーネス設定や実行時ポリシーに書き出すときは、具体的なホストの並びに展開しなければならない（MUST）。未定義のトークンには警告 `UNKNOWN_SCOPE_TOKEN` を出すべきである（SHOULD）。
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
- 署名には任意の `role`（`author` | `reviewer` | `scanner`、既定は `author`）を付けられる。reviewer / scanner は、作者以外が同じ署名対象に付ける証明（attestation）である。L3 には信頼済みの **author** 署名が必要で、reviewer / scanner の署名だけでは L3 を名乗ってはならない（MUST NOT）。検証者は有効な reviewer / scanner 署名を、信頼の有無とともに報告するべきである（SHOULD）。
- Sigstore の staging 環境で作った署名には `instance: "staging"` を付けなければならない（MUST）。検証者は staging の署名を本番の信頼リストと照合してはならない（MUST NOT。参照実装は `sigstore-staging:` という別の接頭辞で扱う）。
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
- ポリシーはスキーマ `policy-v0.7.json`（0.3 と同内容）に従う。判定は capability ごとに `decision`（通常）と `decision_worst_case`（条件付き効果を含む）の 2 つを出さなければならない（MUST）。
- worst case が ask の場合、ハーネスは条件を満たした時点で確認するべきである（SHOULD）。
- `policy-compile --target claude-code|cursor|codex|gemini-cli` はネイティブ設定を生成し、公開スキーマ（無いものはドキュメントから書き起こしたスキーマ）で検証しなければならない（MUST）。変換で失われる情報（例: Codex にホスト許可リストが無い、Cursor に ask が無い、`limits` を書く標準キーが無い）は報告するべきである（SHOULD）。
- `export --format hushspec|rego|aps|acs`: HushSpec 1.0 文書、または OPA/Rego モジュール（`decision` = allow / ask / deny）。APS / ACS の manifest への配線は範囲外。

## 14. 他形式との変換
- `convert` は MDA Open Spec 1.0（`metadata.mda.requires`）と AutoVault（`capabilities` / `tools_required`）との双方向変換を行う。
- export は落ちた情報の一覧 `lossy` と、元の契約へのポインタ＋sha256 を出さなければならない（MUST）。
- import は推測した箇所を `x.import.uncertain` に列挙しなければならない（MUST）。tests は空なので L1 止まり。
- `init` は既存スキルから下書きを作る。不確かな項目を `x.init.uncertain` に入れ、人が確認するまで L1 を名乗るべきではない（SHOULD NOT）。

## 15. スキーマ
- 契約: `schema/v0.7.json`（`$id` `https://kajisho5.github.io/skillpact/schema/v0.7.json`、Draft 2020-12）。参照実装の `ref/skillpact/schema.json` と同一内容。
- ポリシー: `policy-v0.7.json`（内容は policy-v0.3.json と同じ。版の名前を契約スキーマに揃えた）。

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
### 16.3 適合テストスイート
- `conformance/manifest.json` と `conformance/cases/<id>/` が、検証者向けの実装非依存のテスト集である（0.7 時点で 30 ケース。Python 参照実装と TypeScript 実装の両方が全件合格）。
- 期待結果は `valid`、`errors`（全て報告されること）、`errors_any`（いずれかが報告されること。スキーマ違反は `SCHEMA` と個別コードのどちらで報告してもよい）、`warnings_include`。
- 適合する検証者を名乗る実装は、このスイートの全ケースに合格しなければならない（MUST）。ランナーは `conformance/run.py --cmd '<validator> {dir}'`。検証者は `ok` と `findings[].level/code` を含む JSON を出さなければならない（MUST）。
- 正規化と署名の既知の答えは `conformance/vectors/jcs-ed25519.json`。

### 16.4 実装
- 参照実装（Python、`ref/`）: 全機能（検証・テスト実行・署名・変換）。
- 第二実装（TypeScript、`ts/`、verify-only）: 検証・integrity・ed25519（JCS / 旧方式）。仕様とスキーマだけから独立に作成。Sigstore は未対応（警告 `SIGSTORE_UNVERIFIED` `UNKNOWN_SCOPE_TOKEN`）。
- 実例: `samples/` の ffmpeg-skill、subtitle-skill、thumbnail-skill、video-editing-skill（いずれも SEVENTHWELL 自作、0.7、L3）。

## 17. バージョニングと互換性
- `contract_version` は仕様の版。検証者は自分が知っている全ての版を受け付けなければならない（MUST）。知らない **major** 版は拒否しなければならない（MUST、`CONTRACT_VERSION_UNSUPPORTED`）。0.x の間は minor 版ごとに破壊的変更がありうるため、知らない 0.x 版も同様に拒否する。知らない **minor** 版（1.0 以降）は、警告 `CONTRACT_VERSION_NEWER` を出したうえで既知のフィールドとして処理してよい（MAY）。
- 0.x の間は破壊的変更がありうる。0.1〜0.3 の契約は 0.4 でもそのまま有効。
- 1.0 以降: minor 版は追加のみ（任意フィールド、新しいエラーコード、新しい enum 値）。必須化・削除・意味の変更は major 版でのみ行う。
- 非推奨: 削除の少なくとも 1 minor 版前に非推奨と明記し、検証者は警告を出すべきである（SHOULD）。
- `skill.version` はスキル自身の SemVer。permissions が広がる変更では major を上げるべきである（SHOULD）。ハーネスは広がりを検知したら再承認を求めるべきである（SHOULD）。
### 17.1 移行（`migrate`）
- `skillpact migrate <dir> [--to 0.5] [--write]` は 0.1〜0.4 の契約を最新の 0.x に上げる。既定は表示のみで、`--write` で書き込む。
- 行う変更: `contract_version` と `$schema` の更新、`scoped` で scope が空の区分に `["TODO(migrate)"]` を入れる（人が確認するまで L1 を名乗るべきではない。SHOULD NOT）、0.3 以前から上げる場合は `integrity.canonicalization: "jcs"` を付ける。
- 契約が変わった場合、既存の署名は無効になるため削除しなければならない（MUST）。結果の `needs_resign` が true なら再署名が必要。
- `migrate` は署名・push・公開を行ってはならない（MUST NOT）。知らない版からの移行は拒否する。

## 18. セキュリティの考慮事項

### 18.1 脅威モデル
**守る対象**: スキルを入れようとしている利用者とそのハーネス（ファイル、認証情報、通信、費用、人への送信）。
**信頼の前提**: 検証者・ランナー・ハーネス自身と、利用者が `trusted_keys` に入れた鍵・identity は信頼する。それ以外（スキルの作者、配布経路、ミラー、契約の中身）は信頼しない。

| 攻撃者 | できること | SkillPact の対策 | 残る危険 |
|---|---|---|---|
| 悪意あるスキル作者 | 効果を少なく申告する、テストでだけ行儀よく振る舞う | L2 の隔離テスト、`$SKILL_DIR` 変更検知、`decision_worst_case` | テストに出ない経路の振る舞いは検出できない → 実行時の強制が必要（§18.2） |
| 配布経路・ミラー | ファイルや契約の差し替え | integrity（sha256）と署名、L3 は信頼済みの鍵のみ | 信頼済み鍵そのものの漏えい（§18.4） |
| 版の差し替え | 古い版、弱い方式、緩い契約への差し戻し | 知らない版の拒否、JCS の統一、permissions が広がったら再承認（§17） | ハーネスが前回承認した版を覚えていない場合 |
| 依存先 | 依存スキル・パッケージの改ざん | `requirements.skills/packages` の宣言 | 依存先の中身は SkillPact の検証範囲外（依存先も契約を持つべき。SHOULD） |
| 契約を読む LLM | 契約内の文字列（`why`、`summary`）による指示の注入 | 判定は構造化フィールドだけで行う | 自由文をプロンプトに入れるハーネス |

**範囲外**: 実行時の強制、サンドボックスの強度、スキルの品質や正しさ、作者の身元確認（署名は「この鍵・identity が署名した」ことだけを示す）。

### 18.2 宣言は自己申告である
- 契約は作者の申告であり、L1 はその整合性しか示さない。ハーネスは L1 の契約だけを根拠に、効果を伴う capability を `allow` にするべきではない（SHOULD NOT）。
- L2 のテストは申告の一部を観測で確かめるだけで、網羅を保証しない。実行時の強制（APS / ACS / HushSpec、各ハーネスの権限設定）と組み合わせるべきである（SHOULD）。`policy-compile` と `export` はそのためにある。

### 18.3 integrity と TOCTOU
- 検証からインストール・実行までの間にファイルが差し替わるおそれがある。ハーネスは、検証したファイルと実行するファイルが同じであることを確かめるべきである（SHOULD）。たとえば検証済みのコピーを読み取り専用で使う、実行直前に integrity を再照合する、など。
- integrity に載っていないファイル（生成物、キャッシュ）は保護されない。生産者は実行に使う全ファイルを `integrity.files` に含めるべきである（SHOULD）。

### 18.4 鍵と identity
- ed25519 の秘密鍵は署名者が保管し、契約・リポジトリ・ログに含めてはならない（MUST NOT）。
- 鍵を交換するときは、新旧の鍵で並行して署名した版を 1 つ以上出し、その後に旧鍵を `trusted_keys` から外すべきである（SHOULD）。
- 鍵が漏えいした場合、利用者はその鍵を `trusted_keys` から外さなければならない（MUST）。作者は漏えいを公表し、新しい鍵で再署名するべきである（SHOULD）。失効リストの形式は将来の版で定める。
- Sigstore では、identity（ワークフローのパスと ref まで含む SAN）と issuer の両方を照合しなければならない（MUST、§11）。issuer だけ、または組織名だけでの照合をしてはならない（MUST NOT）。

### 18.5 正規化とパース
- 署名対象は JCS（§11.1）で一意に決まる。検証者は、重複キーを含む JSON を拒否するべきである（SHOULD）。JSON パーサーによって最後の値を採るか最初の値を採るかが異なり、署名した内容と判定した内容がずれるためである。
- 数値は IEEE 754 倍精度の範囲で扱う。範囲外の整数を含む契約は、実装間で結果が一致しないおそれがある。

### 18.6 テストの実行
- 適合テストの実行は、スキルのコードを動かすことである。ランナーは使い捨ての環境で、ネットワーク隔離（§10）をしたうえで実行するべきである（SHOULD）。利用者の認証情報を環境変数で渡してはならない（MUST NOT）。ただし `skip_unless_env` で明示されたものは除く。
- `setup` と `run` は契約に書かれたコマンドであり、信頼されていない入力として扱う。

### 18.7 ダウングレードと版
- 検証者は知らない major 版（0.x では知らない minor 版）を拒否する（§17）。
- ハーネスは承認済みの `skill.version` と permissions を記録し、permissions が広がった版を自動で入れてはならない（MUST NOT）。

### 18.8 OWASP Agentic Skills Top 10
各項目との対応は `owasp_mapping.md`（`skillpact owasp` で出力）。

## 付録 A. エラーコード
エラー: `SKILL_MD_MISSING` `FRONTMATTER_MISSING` `FM_NAME` `FM_DESCRIPTION` `CONTRACT_MISSING` `SCHEMA` `NAME_MISMATCH` `DUP_CAPABILITY` `UNDECLARED_EFFECT` `BAD_SUBSCHEMA` `UNKNOWN_REQUIREMENT` `ENTRY_MISSING` `TEST_UNKNOWN_CAPABILITY` `INTEGRITY_MISSING` `INTEGRITY_MISMATCH` `SIGNATURE_INVALID` `SCOPE_WIDENED` `UNKNOWN_FEATURE_KIND` `CONTRACT_VERSION_UNSUPPORTED` `SCOPE_EMPTY`
警告: `FM_NAME_DIR` `BODY_LONG` `HIGH_RISK` `DESTRUCTIVE_NO_EFFECT` `UNUSED_PERMISSION` `NO_TESTS` `UNTESTED_CAPABILITY` `NO_ENTRY` `UNKNOWN_VARIABLE` `CONTRACT_VERSION_NEWER` `SIGSTORE_UNVERIFIED`
（意味と重大度の正式な登録表は今後の版で作る。重複キーを含む JSON は `CONTRACT_JSON` で拒否する）

## 付録 B. 変更履歴
- 0.7: network の予約トークン `@local`、name とディレクトリ名の一致を MUST に（0.7 以上でエラー）、署名の `role`（author / reviewer / scanner）、Sigstore の `instance: staging`。警告 `UNKNOWN_SCOPE_TOKEN`。適合スイート 30 ケース。
- 0.6: 契約構造の変更なし。第二実装（TypeScript）と実例 3 件を追加。生産者が integrity に含めるべきファイルの既定に `src/**`・`pyproject.toml`・`package.json` を追加（参照実装）。警告 `SIGSTORE_UNVERIFIED` を追加。他仕様との比較を `comparison.md` に更新。
- 0.5: 実装非依存の適合テストスイート（§16.3）、`migrate`（§17.1）、セキュリティの考慮事項と脅威モデルを完成（§18）、Sigstore 署名用の GitHub Actions ワークフローを用意（未 push）。契約の構造に変更はない（0.1〜0.4 の契約はそのまま有効）。
- 0.4: 署名の正規化を RFC 8785（JCS）に変更（0.1〜0.3 は旧方式で検証）、テストベクトルを追加。新しいエラー・警告 `CONTRACT_VERSION_UNSUPPORTED` `SCOPE_EMPTY` `UNKNOWN_VARIABLE` `CONTRACT_VERSION_NEWER` `SIGSTORE_UNVERIFIED`。v0.1〜0.3 を 1 本に統合。BCP 14 の規範語で書き直し。適合（役割別）とバージョン・互換の方針を追加。スキーマ `$id` を v0.4 へ。セキュリティの考慮事項は下書き。0.3 以前の契約はそのまま有効（ただし `scoped` で scope が空のものは 0.4 からエラー）。
- 0.3: Sigstore 署名、MDA/AutoVault 変換、OWASP 対応、APS/ACS 書き出し、正式 `$id`。
- 0.2: `kind`、native_contract、依存スキル・パッケージ、features、条件付き効果、effect_scopes、遠隔リソース、全ケース隔離、MCP 対応、policy-compile、HushSpec/Rego 書き出し。
- 0.1: 初版。

## 付録 C. 参考
Agent Skills 仕様 https://agentskills.io/specification ／ RFC 2119, RFC 8174 ／ RFC 8785 (JCS) ／ JSON Schema 2020-12 ／ MCP tool annotations ／ Sigstore ／ HushSpec ／ OPA
