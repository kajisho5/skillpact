# 移行ガイド（0.1〜0.7 → 0.8） / Migration guide (EN summary at the end)

## 1 行で
```
python3 -m skillpact.cli migrate <skill_dir>           # 変更内容を表示（書き込まない）
python3 -m skillpact.cli migrate <skill_dir> --write   # 書き込む
python3 -m skillpact.cli hash <skill_dir> && python3 -m skillpact.cli sign <skill_dir> <key.pem>   # 署名していた場合
```

## 何が変わるか
| 元の版 | 自動で直るもの | 手で確認が要るもの |
|---|---|---|
| 0.1〜0.3 | `contract_version`、`$schema`、`integrity.canonicalization: jcs`、署名の削除 | **再署名**（0.4 から署名対象が RFC 8785 JCS に変わった） |
| 0.1〜0.3 | `scoped` で scope が空 → `["TODO(migrate)"]` | 実際の範囲を書き、TODO を消す（0.4 から `SCOPE_EMPTY` はエラー） |
| 全版 | — | 未定義の `$` 変数（警告 `UNKNOWN_VARIABLE`）、`stdout_json_mode: last`（互換用。strict を推奨） |
| 0.4〜0.5 | 版と `$schema` | 契約が変わるので再署名 |

## 検証者・ハーネス側
- 0.8 の検証者は 0.1〜0.8 をすべて受け付ける。知らない版（例 0.9）は `CONTRACT_VERSION_UNSUPPORTED` で拒否する。
- L3 を出すには `--trusted-key` が必須になった（0.4〜）。
- 重複キーを含む JSON は `CONTRACT_JSON` で拒否する（0.5〜）。

## 0.7 で増えた確認点
- `SKILL.md` の `name` とフォルダ名が違うと、0.7 ではエラー（`FM_NAME_DIR`）。フォルダ名を合わせる。
- ネットワークがローカルだけなら `"scope": ["@local"]` と書ける（以前の `localhost` などの列挙もそのまま有効）。
- レビュアーの署名は `sign --role reviewer`。L3 には作者（author）の署名が必要。

## 0.8 で増えた確認点
- **再署名が必要**：0.8 では署名対象に role が入る（`{"contract", "role"}` の JCS）。`migrate --write` のあと `hash`→`sign`。
- `hash` はスキルの**全ファイル**を載せる。キャッシュなどは `integrity.exclude` で除外できるが、`SKILL.md`・`CLAUDE.md`・`AGENTS.md`・`.claude/**`・`hooks/**`・入口スクリプトなどは除外できない。シンボリックリンクは置けない。
- `network: true` のテストには network の宣言が要る（`TEST_UNDECLARED_NETWORK`）。
- `init` の下書き（`TODO(...)`、`x.init.uncertain`）は確認して消すまで L1 にならない（`UNCONFIRMED_DRAFT`）。
- パスの scope に `..` や `.` は書けない（`SCOPE_TRAVERSAL`）。`*` は 1 階層だけ、`**` で複数階層。
- 1.0 未満の旧版（0.4〜0.7）は role が署名されず、全ファイルの網羅も求めない。ポリシーに `"min_contract_version": "0.8"` を入れると旧版を拒否できる。
- Linux では bubblewrap を入れるとテストが完全なサンドボックスで動く（CI・Action は自動で入れる）。
- 0.1〜0.3 の署名で整数以外の数値を含むものは検証できない。移行して再署名する。

## English summary (0.8)
Re-sign after `migrate --write` (the role is now signed). `hash` lists every file; only non-protected files may be excluded via `integrity.exclude`; no symlinks. Declare network for `network: true` tests. Confirm `init` drafts. No `.`/`..` in path scopes; `*` is one segment. Set `min_contract_version: "0.8"` in policies to refuse older, weaker contracts. Install bubblewrap on Linux.
