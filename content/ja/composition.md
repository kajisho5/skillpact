# 組み合わせ：スキルを一緒に使うときの危険

契約は、スキル 1 つについて書くものです。でも、スキルを 1 つだけ入れることはまずありません。入れたスキルはすべて同じエージェントの中で動き、エージェントは、あるスキルが読んだものを別のスキルに渡せます。スキルを一つずつサンドボックスに入れても、これは止まりません。

## 例
- スキル A は、デプロイのために `~/.aws/credentials` を読みます。
- スキル B は、`api.example.com` に投稿します。

一つずつ見れば、どちらもおかしくありません。でも一緒に入れると**持ち出しの経路**ができます。エージェントが A で読み、B で送れるからです。

## SkillPact が確かめること（仕様 §13.3）
| パス | 条件 | 重大度 |
|---|---|---|
| exfiltration（持ち出し） | 秘密の場所や広い範囲の read ＋ `@local` 以外の network か send | 高 |
| persistence（居座り） | `$WORKDIR`・`$OUTPUT` の外への write ＋ exec | 中 |
| spend_untrusted | spend ＋ 信頼する作者の署名がないスキル | 高 |

```sh
skillpact compose skills/a skills/b skills/c
```
出力には、効果の和集合、見つかったパス、どのスキルがどの役割を担うか、スキルをまたぐかどうか、直し方の手がかりが出ます。

## ポリシー
```json
{ "policy_version": "0.8", "defaults": { "...": "..." },
  "compositions": { "exfiltration": "deny", "persistence": "ask", "spend_untrusted": "ask" } }
```
`policy-check a b c policy.json` は、スキルごとの判定はそのままにして、パスごとの判定を足します。`compositions` を書かなければ、結果はこれまでと同じです。

ハーネスの設定には「一緒に入れたときだけ拒否」とは書けません。そのため `policy-compile a b c policy.json --target claude-code` は、パスに関わる効果を **ask**（確認）にして、そのパスを `lossy` に挙げます。

## 限界
- 確かめるのは宣言だけです。スキルが実際に何をするかは見えません。
- 秘密の場所の一覧は、どうしても漏れが出ます。本当の対策は、範囲を狭く書くことです。
- あとからスキルを足すと組が変わります。組が変わるたびに確かめ直してください。
