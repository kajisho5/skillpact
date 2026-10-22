# 移行ガイド（0.1〜0.5 → 0.6）

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
- 0.6 の検証者は 0.1〜0.6 をすべて受け付ける。知らない版（例 0.7）は `CONTRACT_VERSION_UNSUPPORTED` で拒否する。
- L3 を出すには `--trusted-key` が必須になった（0.4〜）。
- 重複キーを含む JSON は `CONTRACT_JSON` で拒否する（0.5〜）。
