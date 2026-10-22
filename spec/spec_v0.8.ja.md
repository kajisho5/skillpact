# SkillPact 0.8 仕様（日本語訳）

## 要約
SkillPact は Agent Skills の `SKILL.md`（変更しない）の隣に置く機械可読の契約 `skill.contract.json` を定めます。契約には、スキルが何をするか（capabilities）、どんな副作用がありうるか（範囲つきの 6 区分）、何が必要か（requirements）、実行できる適合テスト、ファイルのハッシュと署名を書きます。ツールはスキルを**インストールする前に**契約を確かめ、ハーネスのポリシーに照らして allow / ask / deny を決め、その結果を各ハーネスの設定に変換できます。

## この文書の位置づけ
- **ドラフト 0.8（2026-10-22）。** SEVENTHWELL（shogo kajiyama）が編集するドラフトです。差分ではなく完全版です。
- まだ安定版ではありません。0.x の間は版ごとに互換性のない変更がありえます（バージョニング参照）。公開レビューの期間はまだ決まっていません（[REVIEW.md](https://github.com/kajisho5/skillpact/blob/main/REVIEW.md)）。
- **規範となるのは英語版です。** この日本語訳は参考です。食い違う場合は[英語版](../../spec/)に従います。
- ご意見は kajisho5/skillpact の GitHub issue へ。決め方は [GOVERNANCE.md](https://github.com/kajisho5/skillpact/blob/main/GOVERNANCE.md) にあります。
- スキーマ：`https://kajisho5.github.io/skillpact/schema/v0.8.json`、ポリシー：`.../schema/policy-v0.8.json`。
- ライセンス：本文 CC BY 4.0、スキーマと実装 Apache-2.0。
- 特許：SEVENTHWELL と Shogo Kajiyama は、この仕様の実装に対して、防御的終了つきの無償の特許不主張を誓約しています：[IPR.md](https://github.com/kajisho5/skillpact/blob/main/IPR.md)。
- メディアタイプ：専用のメディアタイプの IANA 登録は 1.0 の後に検討します（付録 D）。

## 1. 表記と用語
「MUST」「MUST NOT」「REQUIRED」「SHALL」「SHALL NOT」「SHOULD」「SHOULD NOT」「RECOMMENDED」「MAY」「OPTIONAL」は、すべて大文字で書かれた場合に限り BCP 14（RFC 2119、RFC 8174）の意味で解釈します。「参考」と書いた節、例、注記は規範ではありません。

| 用語 | 意味 |
|---|---|
| スキル | `SKILL.md`（Agent Skills 形式）と、それが使うファイルを含むディレクトリ |
| スキルディレクトリ | そのディレクトリ（`$SKILL_DIR`） |
| 契約 | JSON 文書 `skill.contract.json` |
| 効果 | 6 区分の副作用（§6） |
| capability | スキルが提供する 1 つのツール・コマンド・操作（§7） |
| 生産者 | 契約を書く人・ソフトウェア |
| 検証者 | 契約を検査して結果を報告するソフトウェア |
| ランナー | 契約のテストを実行するソフトウェア（§10） |
| ハーネス | スキルを読み込むエージェント実行環境（Claude Code、Cursor、Codex、Gemini CLI など） |
| ポリシー | ハーネスのポリシー文書（§13） |
| 指摘 | 付録 A のコードを持つエラーまたは警告 |
| 署名対象 | 実際に署名するバイト列（§11.1） |
| 作者署名 | role が `author` の署名（§11） |

## 2. 対象と対象外
対象：
1. **宣言**：スキルが何をし、何を必要とし、どんな副作用を持ちうるか。
2. **インストール前の照合**：契約 × ポリシー → capability ごとに allow / ask / deny。
3. **変換**：判定結果を Claude Code・Cursor・Codex・Gemini CLI の設定に変換し、HushSpec・Rego に書き出す。

対象外：
- **実行時の強制。** ハーネスと実行時ポリシーの規格（APS、ACS、HushSpec）に任せます。SkillPact はそれらに情報を渡すだけです。
- **スキルが安全であることの証明。** 契約は作者の申告で、テストはその一部を確かめ、署名は誰が作ったかを示すだけです（§18）。
- **スキャン・静的解析。** スキャナーとは競合しません。契約はスキャナーの入力として役立ちます。
- **配布・レジストリ。**
- **Agent Skills の変更。** `SKILL.md` は変えません。

## 3. ファイル名・置き場所・形式
- 契約のファイル名は `skill.contract.json` で、`SKILL.md` と同じディレクトリに置かなければなりません（MUST）。
- 生産者は契約のために `SKILL.md` の frontmatter や本文を変えてはなりません（MUST NOT）。SkillPact を知らないハーネスはそのまま動きます。
- `skill.name` は frontmatter の `name` と一致しなければなりません（MUST、`NAME_MISMATCH`）。frontmatter の `name` は `SKILL.md` を含むディレクトリ名と一致しなければなりません（MUST、`FM_NAME_DIR`。0.7 以上はエラー、それより前は警告。契約を別の場所に置いて検証する場合は対象外）。
- メディアタイプと名前については付録 D。

## 4. JSON の扱い
### 4.1 パース（I-JSON）
契約は UTF-8 の JSON（RFC 8259）で、さらに I-JSON（RFC 7493）と次の制限を満たさなければなりません。満たさないものを検証者は `CONTRACT_JSON` で拒否しなければなりません（MUST）。
- 重複したキーがない（エスケープを戻したあとで比べる）
- 整数は ±(2^53−1) の範囲内、数値はすべて有限
- 文字列とキーに対になっていないサロゲートがない
- 不正な UTF-8 は拒否
- 入れ子の深さは 64 まで（最上位を 1 と数える）

理由：パーサーによって解釈が違うと、署名した内容と判定した内容がずれるためです。

## 5. 文書の構造
契約は §15 の JSON Schema（Draft 2020-12）に適合しなければなりません（MUST、`SCHEMA`）。

| キー | 必須 | 内容 |
|---|---|---|
| `$schema` | いいえ | スキーマ URL |
| `contract_version` | はい | `"0.1"`〜`"0.8"` |
| `kind` | いいえ | `tool`（既定）または `instructions`（実行物なし） |
| `skill` | はい | `name`、`version`（SemVer）、`native_contract` |
| `permissions` | はい | §6 |
| `capabilities` | `tool` では必須 | §7 |
| `requirements` | いいえ | §8 |
| `compat` | いいえ | §9 |
| `tests` | いいえ（L2 に必要） | §10 |
| `integrity` | いいえ（L3 に必要） | §11 |
| `x` | いいえ | 拡張。`x.<vendor>.*` のみ |

- 拡張は `x.<vendor>` に置かなければなりません（MUST）。vendor 名は `^[a-z0-9][a-z0-9-]*$`。それ以外の未知のキーはスキーマエラーです。
- 検証者は理解できない `x` の中身を無視しなければなりません（MUST）。ただし §14 の下書きの印は除きます。

## 6. permissions（6 種類の効果）
各効果は `level`（`none` | `scoped` | `any`）、`scope`（配列）、`why`、`confirm`（`never` | `each` | `session`）を持ちます。

| 効果 | 意味 | scope の書き方 |
|---|---|---|
| read | ファイルやデータを読む | パスの glob |
| write | 作る・変える・消す | パスの glob、`remote:<host>/<path>` |
| network | 他のホストと通信する | ホストの glob、`@local` |
| exec | 他のプログラムを動かす | コマンド名 |
| spend | お金を使う | サービス名 |
| send | 人に届く（メッセージ、投稿、メール） | 宛先の種類・サービス名 |

- パス変数：`$INPUT` `$INPUT_DIR` `$OUTPUT` `$WORKDIR` `$SKILL_DIR` `$TMPDIR`。それ以外の `$` 変数には `UNKNOWN_VARIABLE` を出すべきです（SHOULD）。
- `scoped` の効果は scope を 1 つ以上持たなければなりません（MUST、`SCOPE_EMPTY`）。スキル全体の scope は条件付きを含むすべての場合を含まなければなりません（MUST）。
- spend・send が `any` なら `HIGH_RISK` を出さなければなりません（MUST）。
- `@` で始まる scope は予約トークンです。0.8 で定めるのは network の `@local`（ループバック・プライベート・リンクローカルの IP アドレスと `localhost`。DNS 名は当てはまらない。付録 C）だけです。未知のトークンには `UNKNOWN_SCOPE_TOKEN` を出すべきです（SHOULD）。ハーネスや実行時ポリシーに書き出すときは `@local` をホストのパターンに展開しなければならず（MUST）、表せないもの（IPv6 の範囲や、ホストの glob が当たりうる DNS 名）は lossy として報告しなければなりません（MUST）。

### 6.1 glob とパス（規範）
すべての実装は glob を次のとおりに照合しなければなりません（MUST）。`fnmatch` やシェルの glob の意味を使ってはなりません（MUST NOT）。
- **パスと一般のパターン**（read、write、exec、spend、send）：`*` は `/` 以外の任意の文字列、`?` は `/` 以外の 1 文字、セグメント全体が `**` なら 0 個以上のセグメントに一致します。末尾の `/**` は基点そのものにも一致します（`a/**` は `a` に一致）。大文字小文字を区別します。
- **ホストのパターン**（network）：`*` は 1 つの DNS ラベルの中だけ。先頭の `*.` は 1 つ以上のラベル（`*.example.com` は `example.com` に一致しない）、先頭の `**.` は 0 個以上のラベル。大文字小文字を区別せず、末尾のドットは無視します。
- **パスの scope**（read、write、`effect_scopes`）は `.`・`..`・空のセグメント・バックスラッシュを含んではなりません（MUST NOT、`SCOPE_TRAVERSAL`）。絶対パスは使えます。
- **包含**（ある scope が別の scope に収まるか。`effect_scopes` とポリシーのルールで使う）：scope の各要素がパターンと同じか、自分のワイルドカードを「同じか広いワイルドカードにしか一致しない文字」として扱ってパターンに一致すれば、含まれるとします。`..` などを含む scope は決して含まれません。

## 7. capabilities
- 各 capability は `id`（一意。`DUP_CAPABILITY`）、`summary`、`entry`、`effects` を持ちます。
- `entry` は `cli`（配列）、`mcp_tool`、`doc` のいずれか。`cli` 中の `$SKILL_DIR/...` は実在しなければなりません（MUST、`ENTRY_MISSING`）。効果があるのに entry がなければ警告 `NO_ENTRY`。
- `effects` の各効果は permissions で `none` 以外でなければなりません（MUST、`UNDECLARED_EFFECT`）。
- `effect_scopes` は capability ごとに範囲を狭めてよく（MAY）、広げてはなりません（MUST NOT、`SCOPE_WIDENED`）。
- `conditional_effects[]`（`effect`、`when`、`scope`）：ある場合にだけ起きる効果。これも宣言が必要です。
- `destructive: true` には write・send・spend のいずれかを付けるべきです（SHOULD、`DESTRUCTIVE_NO_EFFECT`）。
- 任意：`idempotent`、`dry_run`、`inputs` / `outputs`（JSON Schema。不正なら `BAD_SUBSCHEMA`）、`requires`（requirements の名前。`UNKNOWN_REQUIREMENT`）、`requires_features` / `optional_features`（`<kind>:<name>`。kind は `features_check` にあること。`UNKNOWN_FEATURE_KIND`）、`mcp_annotations`。

## 8. requirements
- `binaries[]` / `runtimes[]`：`name`、`version`（例 `>=4.4`）、`check`、`version_regex`、`optional`、`when`、`alternatives`、`features_check`。
- `packages[]`：`ecosystem`、`name`、`import`。`skills[]`：`name`、`version`、`env`、`optional`。
- `env[]`：`name`、`required`、`secret`、`description`。秘密の値を契約に書いてはなりません（MUST NOT）。

## 9. compat
`compat.agents.<id>`：`status`（`tested` | `expected` | `unsupported`）、`version`、`tested_at`、`notes`。`tested` は、そのハーネスで §10 を実行してから名乗るべきです（SHOULD）。ほかに `os`、`interfaces`。

## 10. 適合テスト
- `setup`：新しい `$WORKDIR` で実行するコマンド。`cases[]`：`id`、`capability`（実在すること。MUST、`TEST_UNKNOWN_CAPABILITY`）、`run`、`timeout_s`、`network`（既定 false）、`env`、`skip_unless_env`、`tags`、`expect`（`exit_code`、`stdout_contains`、`stderr_contains`、`stdout_json_schema`、`stdout_json[]`、`stdout_json_mode`、`files[]`、`validate_outputs`）。
- `network: true` のケースには、`permissions.network` が `none` 以外であることが必要です（`TEST_UNDECLARED_NETWORK`。0.8 からエラー）。
- ランナーは `setup` と各ケースを次のサンドボックスで実行しなければなりません（MUST）。
  1. ネットワークなし（`network: true` のケースを除く）
  2. ファイルシステムは `$WORKDIR` 以外読み取り専用（write の scope に `$SKILL_DIR` がある場合だけ `$SKILL_DIR` も書き込み可）
  3. 環境変数は許可リストのものだけ：`PATH`、`LANG`、`LC_ALL`、`TZ`、`TERM`、SkillPact の変数、見つけた依存スキル、ケースの `env`。`HOME` と `TMPDIR` は `$WORKDIR` の中を指す。`skip_unless_env` に書かれたホストの変数は、テストを実行する人が許した場合だけ渡す（参照 CLI では `--pass-env NAME`）。許可がなければそのケースはスキップ（0.8.x 正誤）
  4. 利用者のホームと、ホストの一時・実行時ディレクトリ（`/tmp`、`/var/tmp`、`/run`、`/dev/shm`）を隠し、ユーザーのファイルを読んだりホストの Unix ソケットに接続したりできないようにする。プログラムの実行に要るディレクトリ（`PATH` の各要素）は読み取り専用で見せてよい（0.8.x 正誤）
  5. 制御端末から切り離した新しいセッションで、標準入力を閉じて実行する（0.8.x 正誤）
- ランナーはスキルディレクトリの変更を（大きさや時刻ではなく）内容のハッシュで検出し、write の scope に `$SKILL_DIR` がなければそのケースを失敗にしなければなりません（MUST）。ファイルシステムを隔離できない場合は親ディレクトリも監視し、スキルの外への書き込みを報告しなければなりません（MUST）。
- ネットワークを隔離できないランナーは L2 を出してはなりません（MUST NOT）。L2 には、`network: true` ではない隔離ケースが 1 つ以上通っていることも必要です。
- スキップしたケースは失敗ではありませんが、件数を報告しなければなりません（MUST）。
- 参照ランナーは Linux では bubblewrap（`bwrap`）を使い、なければ `unshare -rn`（ネットワークのみ。`fs_isolated: false` と報告）を使います。macOS では Seatbelt（`/usr/bin/sandbox-exec`、**試験的**）を使い、書き込みは `$WORKDIR`（宣言があれば `$SKILL_DIR` も）だけ、`network: true` 以外は通信をすべて拒否します。Apple は `sandbox-exec` を非推奨としていますが、現在も動作し、他のエージェントのサンドボックスでも使われています。0.8.x 正誤：Seatbelt のプロファイルは `network: true` のケースでも Unix ソケットへの接続（システムの DNS リゾルバを除く）を拒否します。ただし Mach/XPC の問い合わせは許したままなので、ケースが launchd のサービス（`open` など）にサンドボックスの外での処理を頼めます。このため Seatbelt は**試験的**のままで、L2 の要件をすべて満たすのは Linux の bubblewrap だけです。Windows には対応する方式がない（WSL2 かコンテナを使う）ため、L2 になりません。

## 11. integrity と署名
- `integrity.algorithm` は `sha256`。`integrity.files` は相対パス → 16 進小文字のハッシュ。検証者は載っている全ファイルを照合しなければなりません（MUST、`INTEGRITY_MISMATCH`、`INTEGRITY_MISSING`）。
- `integrity.signatures[]`：ed25519 `{type, key: "ed25519:<b64>", sig, signer, role}` または Sigstore `{type, identity, issuer, bundle, instance, role}`。
- `role` は `author`（既定）、`reviewer`、`scanner`。L3 になれるのは信頼済みの **author** 署名だけです。有効な reviewer・scanner の署名は証明（attestation）として報告するべきです（SHOULD）。
- 同じ鍵・identity が同じ契約に 2 回以上署名してはなりません（MUST NOT、`DUP_SIGNATURE`）。検証者は、その鍵のすべての署名が正しい場合にだけ有効とします。
- Sigstore の検証者は identity と issuer の両方を信頼リストと照合しなければなりません（MUST）。staging の署名には `instance: "staging"` を付け（MUST）、本番の信頼リストと照合してはなりません（MUST NOT）。
- 信頼はポリシーの `trusted_keys`（`ed25519:<b64>` または `sigstore:<issuer>|<identity>`）で決めます。信頼していない鍵の署名で L3 にしてはなりません（MUST NOT）。

### 11.1 署名対象
- `contract_version` が 0.8 以上：`{"contract": C, "role": R}` を JCS（RFC 8785）で直列化した UTF-8 バイト列。C は `integrity.signatures` を除いた契約、R はその署名の role（なければ `"author"`）。role も署名されるので、付け替えると署名が壊れます。
- 0.4〜0.7：JCS(C)。role は署名されません（旧方式。§18.7）。検証者は `SIGNATURE_ROLE_UNSIGNED` を警告し、その署名を信頼済みの author 署名として扱ってはなりません（MUST NOT）。0.8 より前の契約は L3 にならず、`require_signature` も満たしません（0.8.x 正誤）。
- 0.1〜0.3：旧方式（キーをコードポイント順に並べ、区切りは `,` `:`、空白なし、非 ASCII はそのまま UTF-8）。数値は ±(2^53−1) の整数だけ扱えます。それ以外の数値を含む契約は検証できないので、移行して署名し直さなければなりません（MUST）。
- 方式は `contract_version` で決まります。`integrity.canonicalization` は参考情報です。
- テストベクトル：`conformance/vectors/jcs-ed25519.json`（シードを公開したテスト用の鍵。本物の署名に使ってはなりません。MUST NOT）。

### 11.2 ファイルの網羅（0.8 から）
- `integrity.files` にはスキルディレクトリ内のすべての通常ファイルを載せなければなりません（MUST）。除外できるのは `skill.contract.json`、既定の除外（`.git/**`、`**/.DS_Store`）、任意の `integrity.exclude` のパターンだけです。0.8.x 正誤：Python は署名されたソースではなく未検証のバイトコードを実行しうるため、`__pycache__` と `*.pyc` は除外しなくなりました。ハッシュを取る前にバイトコードを消してください。
- 次の保護ファイルは必ず載せ、除外できません：`SKILL.md`、`**/SKILL.md`、`**/CLAUDE.md`、`**/AGENTS.md`、`**/GEMINI.md`、`**/.mcp.json`、`.claude-plugin/**`、`.claude/**`、`.cursor/**`、`.codex/**`、`.gemini/**`、`.agents/**`、`hooks/**`、`package.json`、`pyproject.toml`、entry・テスト・setup に `$SKILL_DIR/...` として出てくるファイル、および（0.8.x 正誤）コードとバイトコードのファイル（`*.py`、`*.pyc`、`*.sh`、`*.js`、`*.ts`、`*.so`、`*.dll`、`*.jar`、`*.wasm` など。一覧は参照実装）。契約をスキルディレクトリの外に置いた場合も網羅を確かめます。
- 載っていないファイル：`INTEGRITY_UNLISTED`（0.8 からエラー、それより前は警告）。`files` に `SKILL.md` がない：`INTEGRITY_EMPTY`（0.8）。
- パスは相対の POSIX パスで、`.`・`..`・空のセグメント、バックスラッシュ、制御文字を含まず、1024 バイト・32 セグメント以内、全体で 10 000 件以内。スキルディレクトリ内や載っているパスの途中にあるシンボリックリンクは拒否します（`INTEGRITY_PATH`、全版）。
- どの版でも、`INTEGRITY_UNLISTED` か `INTEGRITY_PATH` の指摘が 1 つでもあれば L3 にしてはなりません（MUST NOT）。

## 12. MCP との対応
| annotation | 導き方 |
|---|---|
| `readOnlyHint` | write・send・spend がない（条件付きを含む） |
| `destructiveHint` | `destructive` |
| `idempotentHint` | `idempotent` |
| `openWorldHint` | network・send・spend がある |

## 13. ハーネスポリシーと変換
- ポリシーは `policy-v0.8.json` に従います。照合器は capability ごとに `decision` と `decision_worst_case`（条件付きの効果を含む）を出さなければなりません（MUST）。
- `..` などを含むパスの scope は拒否しなければなりません（MUST）。
- `scope` のないポリシーのルールは、その効果のすべての scope（`level: any` を含む）に当てはまります（0.8.x 正誤）。
- `min_contract_version`：これより古い契約は拒否しなければなりません（MUST）。
- `require_signature`：照合器はファイル（§11.2 の網羅を含む integrity）を確かめ、信頼済みの **author** 署名を求めなければなりません（MUST）。満たさなければ拒否します。
### 13.1 変換
- `policy-compile` は Claude Code・Cursor・Codex・Gemini CLI の設定を出力し、各ハーネスの公開スキーマ（なければ文書から起こしたスキーマ）で検証します。変換先が表せないものは `lossy` に挙げなければなりません（MUST）。
- 変換先が deny や ask を表せない場合、出力は判定と同じかそれより厳しくなければなりません（MUST）（例：Codex は `approval_policy: on-request`。`never` にはしない）。変換した設定は条件付きの効果を含む `decision_worst_case` に従います（0.8.x 正誤）。
- `export --format hushspec|rego` は実行時ポリシーの文書を出力します。

## 14. 変換と下書き
- `convert` は MDA Open Spec の `requires`、AutoVault の `capabilities` と相互に変換します。書き出しは `lossy` と、元の契約とその sha256 を示します。
- 取り込みや `init` の下書きは、推測した箇所を `x.import.uncertain` / `x.init.uncertain` に挙げ、`TODO(...)` を使うことがあります。こうした契約は未確認の下書きで、`UNCONFIRMED_DRAFT`（0.8 からエラー）になります。人が確認して印を消す必要があります。

## 15. スキーマ
- 契約：`schema/v0.8.json`（`$id` `https://kajisho5.github.io/skillpact/schema/v0.8.json`）。ポリシー：`schema/policy-v0.8.json`。公開したスキーマファイルは書き換えません。

## 16. 適合
### 16.1 レベル（契約について）
- **L1 宣言済み**：検証者のエラーが 0。
- **L2 テスト済み**：L1 に加え、§10 のサンドボックスで全ケースが通り、ネットワークを隔離したケースが 1 つ以上ある。
- **L3 署名済み**：L2 に加え、全ファイルを網羅した integrity が一致し（§11.2）、信頼済みの鍵・identity による有効な作者署名がある。

L3 の意味は「このファイル一式は、あなたが信頼する人が署名したもので、宣言したテストが隔離環境で通る」ということです。スキルが安全だという意味では**ありません**。

### 16.2 適合クラス（ソフトウェアについて）
| クラス | 要件 |
|---|---|
| 生産者 | §3〜§11 とスキーマを満たす契約を出す |
| 検証者 | §3〜§11 と §14 の MUST をすべて検査し、付録 A のコードで報告し、適合スイートに合格する |
| ランナー | §10 のサンドボックス、環境変数の許可リスト、内容ハッシュによる変更検出、スキップの報告 |
| ポリシー照合器 | §13 の判定、`require_signature` と `min_contract_version` |
| 変換器 | §13.1（`lossy` を含む） |
| ハーネス | `decision_worst_case` に従い、実行前に integrity を確かめ直すべき（SHOULD） |

### 16.3 適合スイート
`conformance/manifest.json` と `conformance/cases/<id>/`（0.8 と 0.8.x 正誤で 48 ケース）。適合を名乗る検証者は全ケースに合格しなければなりません（MUST）：`python3 conformance/run.py --cmd '<validator> {dir}'`。0.8 のケースは `conformance/gen_v08.py` が作ります。Python の参照実装と TypeScript 実装の両方が全ケースに合格しています。

## 17. バージョン・安定性・非推奨
- 検証者は知っているすべての版を受け付け、知らない major 版を拒否しなければなりません（MUST、`CONTRACT_VERSION_UNSUPPORTED`）。0.x の間は、知らない minor 版も知らない major 版として扱います。
- 1.0 以降：minor 版は追加だけ（任意フィールド、新しいコード、新しい enum 値）。それ以外は新しい major 版が必要です。知らない minor 版は `CONTRACT_VERSION_NEWER` を出して処理してよい（MAY）。
- 非推奨：削除の少なくとも 1 minor 版前に告知し、検証者は警告するべきです（SHOULD）。
- `skill.version` は SemVer。permissions を広げる変更では major を上げ（SHOULD）、ハーネスは承認し直しを求めるべきです（SHOULD）。
- `migrate` は契約を新しい版に上げ、内容が変われば署名を外します。署名・公開はしません。

## 18. セキュリティの考慮事項
### 18.1 脅威モデル
守る対象：利用者とそのハーネス（ファイル、認証情報、通信、お金、人へのメッセージ）。信頼するもの：検証者、ランナー、ハーネス、利用者が `trusted_keys` に入れた鍵。信頼しないもの：スキルの作者、配布経路、ミラー、契約の中身。

| 攻撃者 | できること | 対策 | 残る危険 |
|---|---|---|---|
| 悪意ある作者 | 効果を少なく申告する、テストのときだけ行儀よくする | 隔離テスト、サンドボックス、最悪ケースの判定 | テストに出ない経路。実行時の強制が必要 |
| 配布経路・ミラー | ファイルや契約の差し替え | 全ファイルのハッシュと署名、L3 は信頼済みの鍵だけ | 信頼済みの鍵の漏えい |
| 署名の付け替え | reviewer の署名を author に見せかける | 0.8 から role も署名 | 0.4〜0.7 の契約（§18.7） |
| 版の差し戻し | 古くて緩い版の契約を出す | 知らない版の拒否、`min_contract_version` | 承認した版を記録しないハーネス |
| 依存先 | 依存スキルやパッケージの改ざん | `requirements` での宣言 | 依存先の中身は範囲外 |
| 文字列による指示の注入 | `why` や `summary` に指示を書く | 判定は構造化された項目だけで行う | 自由文をモデルに渡すハーネス |

### 18.2 宣言は自己申告
L1 は整合性しか示しません。ハーネスは L1 だけを根拠に、効果を伴う capability を自動で許可するべきではありません（SHOULD NOT）。実行時の強制と組み合わせるべきです（SHOULD）。
### 18.3 integrity と TOCTOU
確認してから実行するまでにファイルが変わるおそれがあります。ハーネスは確認したコピーを読み取り専用で実行するか、実行直前に確かめ直すべきです（SHOULD）。
### 18.4 鍵と identity
秘密鍵を契約、リポジトリ、ログに含めてはなりません（MUST NOT）。鍵を替えるときは、少なくとも 1 回のリリースで新旧両方の鍵で署名します。漏えいしたら利用者はその鍵を `trusted_keys` から外さなければなりません（MUST）。Sigstore の identity はワークフローのパスと ref まで完全に照合し、issuer や組織名だけで照合してはなりません（MUST NOT）。
### 18.5 パース
§4.1 がパーサー間の違い（重複キー、大きな整数、サロゲート、深さ）をなくします。
### 18.6 テストの実行
テストの実行はスキルのコードを動かすことです。`setup` と `run` は信頼できない入力として扱い、§10 に従います。利用者の認証情報は `skip_unless_env` に書かれた変数を除いて渡してはなりません（MUST NOT）。
### 18.7 旧版
0.8 より前の契約は role を署名せず、全ファイルの網羅も求めません（載っていないファイルは警告ですが、L3 にはなりません）。ポリシーには `min_contract_version: "0.8"` を設定するべきです（SHOULD）。

## 19. プライバシーの考慮事項
- 契約には、任意の `signer` 名と Sigstore の identity（メールアドレスや CI ワークフローの URL であることが多い）を除き、個人情報は含まれません。個人のメールアドレスを公開したくない作者は、役割用・プロジェクト用の identity を使うべきです（SHOULD）。Sigstore の記録は公開の透明性ログにも残ります。
- 秘密の値を契約に書いてはなりません（§8）。
- 検証者とブラウザのチェッカーはオフラインで動きます。チェッカーのページは何も送信しません。
- テストの実行には許可リストの環境変数だけが渡ります（§10）。

## 20. 相互運用
- Agent Skills：`SKILL.md` は変えず、名前はその規則に従います。
- MCP：annotations（§12）、`mcp-check`。
- ハーネス設定：Claude Code、Cursor、Codex、Gemini CLI（§13.1）。それぞれ表せないものがあります。
- 実行時ポリシー：HushSpec、Rego（APS・ACS 向け）。
- 他の形式：MDA Open Spec、AutoVault（§14）。OWASP Agentic Skills Top 10 との対応：`spec/owasp_mapping.md`（部分的な対応であることを正直に記載）。

## 21. 参照文献
規範：RFC 2119、RFC 8174（BCP 14）、RFC 8259（JSON）、RFC 7493（I-JSON）、RFC 8785（JCS）、RFC 8032（EdDSA / Ed25519）、JSON Schema 2020-12、Agent Skills 仕様（https://agentskills.io/specification）、Semantic Versioning 2.0.0。

参考：Sigstore、MCP tool annotations、OWASP Agentic Skills Top 10（https://owasp.org/www-project-agentic-skills-top-10/）、HushSpec、Agent Policy Specification、Microsoft Agent Control Specification、OPA / Rego、MDA Open Spec、AutoVault、bubblewrap、各ハーネスの文書（Claude Code、Cursor、Codex、Gemini CLI。2026-10-22 時点）。

## 付録 A. 指摘コード
重大度はコードと版ごとに決まっています。新しいコードは提案の手続き（GOVERNANCE.md）でのみ追加します。エラーがあれば L1 になりません。警告は L1 を妨げません。

| コード | 重大度 | 節 | 意味 |
|---|---|---|---|
| `SKILL_MD_MISSING` | エラー | 全体 | SKILL.md がない |
| `FRONTMATTER_MISSING` | エラー | 全体 | frontmatter がない |
| `FM_NAME` | エラー | 全体 | name が Agent Skills の規則に違反 |
| `FM_DESCRIPTION` | エラー | 全体 | description がない・1024 字超 |
| `FM_COMPAT` | エラー | 全体 | compatibility が 500 字超 |
| `FM_NAME_DIR` | エラー ≥0.7, それより前は警告 | §3 | name とディレクトリ名が違う |
| `CONTRACT_MISSING` | エラー | 全体 | 契約ファイルがない |
| `CONTRACT_JSON` | エラー | §4.1 | I-JSON でない（重複キー、大きな整数、サロゲート、深さ、文字コード） |
| `CONTRACT_VERSION_UNSUPPORTED` | エラー | §17 | 知らない major（0.x では minor）版 |
| `CONTRACT_VERSION_NEWER` | 警告 | §17 | 新しい minor 版（1.0 以降） |
| `SCHEMA` | エラー | §5 | スキーマ違反 |
| `NAME_MISMATCH` | エラー | §3 | skill.name と frontmatter の name が違う |
| `DUP_CAPABILITY` | エラー | §7 | capability の id が重複 |
| `UNDECLARED_EFFECT` | エラー | §7 | 使う効果が permissions で none |
| `BAD_SUBSCHEMA` | エラー | §7 | inputs/outputs が不正なスキーマ |
| `UNKNOWN_REQUIREMENT` | エラー | §7 | requires が requirements にない |
| `ENTRY_MISSING` | エラー | §7 | 入口ファイルがない |
| `UNKNOWN_FEATURE_KIND` | エラー | §7 | feature の kind が未定義 |
| `SCOPE_EMPTY` | エラー | §6 | scoped なのに scope が空 |
| `SCOPE_WIDENED` | エラー | §7 | effect_scopes が permissions より広い |
| `SCOPE_TRAVERSAL` | エラー | §6.1 | パス範囲に . / .. / 空 / \ |
| `TEST_UNKNOWN_CAPABILITY` | エラー | §10 | テストが未知の capability を参照 |
| `TEST_UNDECLARED_NETWORK` | エラー ≥0.8, それより前は警告 | §10 | network 宣言なしの network テスト |
| `UNCONFIRMED_DRAFT` | エラー ≥0.8, それより前は警告 | §14 | 下書きの印が残っている |
| `INTEGRITY_MISSING` | エラー | §11 | 載っているファイルがない |
| `INTEGRITY_MISMATCH` | エラー | §11 | ハッシュが違う |
| `INTEGRITY_PATH` | エラー (載っていないリンク: 警告 <0.8) | §11.2 | 不正なパス・シンボリックリンク・上限超え |
| `INTEGRITY_UNLISTED` | エラー ≥0.8, それより前は警告 | §11.2 | integrity に載っていないファイル |
| `INTEGRITY_EMPTY` | エラー (0.8+) | §11.2 | files に SKILL.md がない |
| `SIGNATURE_INVALID` | エラー | §11 | 署名が検証できない |
| `SIGNATURE_ROLE_UNSIGNED` | 警告 | §11.1 | 0.8 より前の契約の署名。role が署名されず L3 にならない（0.8.x） |
| `DUP_SIGNATURE` | エラー | §11 | 同じ鍵が 2 回以上署名 |
| `SIGSTORE_UNVERIFIED` | 警告 | §16.4 | Sigstore を検証できない実装 |
| `HIGH_RISK` | 警告 | §6 | spend/send が any |
| `UNKNOWN_SCOPE_TOKEN` | 警告 | §6 | 未定義の @ トークン |
| `UNKNOWN_VARIABLE` | 警告 | §6 | 未定義の $ 変数 |
| `DESTRUCTIVE_NO_EFFECT` | 警告 | §7 | destructive なのに write/send/spend がない |
| `NO_ENTRY` | 警告 | §7 | 効果があるのに entry がない |
| `UNUSED_PERMISSION` | 警告 | §6 | どの capability も使わない権限 |
| `NO_TESTS` | 警告 | §10 | テストがない |
| `UNTESTED_CAPABILITY` | 警告 | §10 | テストのない capability |
| `BODY_LONG` | 警告 | §3 | SKILL.md 本文が 500 行超 |

## 付録 B. 例
最小（説明だけのスキル）：
```json
{"contract_version": "0.8", "kind": "instructions",
 "skill": {"name": "style-guide", "version": "1.0.0"},
 "permissions": {"read": {"level": "none"}, "write": {"level": "none"}, "network": {"level": "none"},
                 "exec": {"level": "none"}, "spend": {"level": "none"}, "send": {"level": "none"}},
 "capabilities": [{"id": "guide", "summary": "writing guidance", "effects": []}]}
```
テスト付きのツール：
```json
{"contract_version": "0.8", "skill": {"name": "thumb", "version": "1.2.0"},
 "permissions": {"read": {"level": "scoped", "scope": ["$INPUT"]}, "write": {"level": "scoped", "scope": ["$OUTPUT"]},
   "network": {"level": "none"}, "exec": {"level": "scoped", "scope": ["python3"]},
   "spend": {"level": "none"}, "send": {"level": "none"}},
 "capabilities": [{"id": "make", "summary": "make a thumbnail", "effects": ["read", "write", "exec"],
   "entry": {"cli": ["python3", "$SKILL_DIR/scripts/thumb.py", "$INPUT", "$OUTPUT"]}}],
 "tests": {"cases": [{"id": "basic", "capability": "make", "run": ["python3", "$SKILL_DIR/scripts/thumb.py", "--selftest"],
   "expect": {"exit_code": 0}}]}}
```
署名済みの完全な例：`samples/`（L3 の 4 スキル）。テストベクトル：`conformance/vectors/`。適合ケース：`conformance/cases/`。

## 付録 C. `@local` の展開
0.8.x 正誤：`@local` に当てはまるのは `localhost` と IP アドレスの表記だけです。IPv4 は `127.0.0.0/8`、`10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`、`169.254.0.0/16`（10 進のドット表記、先頭ゼロなし）、IPv6 は `::1`、`fe80::/10`、`fc00::/7`（角かっこは可。ゾーン ID や IPv4 埋め込みは不可）。DNS 名は決して当てはまりません（`*.local`、`10.0.0.com`、`127.0.0.1.example.com`）。ベクトル：`conformance/vectors/local-hosts.json`。ハーネスのホスト glob（`127.*.*.*` など）に変換すると DNS 名にも当たりうるうえ IPv6 の範囲は書けないため、`lossy` で報告します。

## 付録 D. メディアタイプとファイル名（登録についての注記）
- ファイル名：`skill.contract.json`（固定、`SKILL.md` の隣）。
- メディアタイプ：現在は `application/json` を使います。専用のタイプ（例 `application/skillpact+json`）は IANA に**登録していません**。1.0 の後に検討します。それまで実装は特定のメディアタイプに頼ってはなりません（MUST NOT）。
- スキーマの URL は版ごとに固定です。

## 付録 E. 0.8 の変更点
全ファイルの網羅とパスの規則（§11.2）、署名対象への role の追加（§11.1）、`DUP_SIGNATURE`、I-JSON のパース（§4.1）、規範としての glob と `SCOPE_TRAVERSAL`（§6.1）、setup のサンドボックス化・環境変数の許可リスト・内容ハッシュでの変更検出（§10）、`TEST_UNDECLARED_NETWORK`、`UNCONFIRMED_DRAFT`、ポリシーの `min_contract_version` と `require_signature` でのファイル確認（§13）、`lossy` を伴うより厳しい変換（§13.1）、英語版を規範に変更。これまでの履歴：[CHANGELOG.md](https://github.com/kajisho5/skillpact/blob/main/CHANGELOG.md)。
