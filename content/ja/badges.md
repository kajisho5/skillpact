# バッジ

スキルの SkillPact レベルを README に表示できます。このサイトから配信する SVG です。`skillpact conformance`（または GitHub Action）で実際に出たレベルのバッジだけを使ってください。バッジは申告で、証明ではありません。読む人は[チェッカー](../check/)や Action で確かめ直せます。使い方の決まり：[TRADEMARKS.md](https://github.com/kajisho5/skillpact/blob/main/TRADEMARKS.md)。

[![SkillPact L1](../../badges/skillpact-L1.svg)](../) [![SkillPact L2](../../badges/skillpact-L2.svg)](../) [![SkillPact L3](../../badges/skillpact-L3.svg)](../)

## Markdown
```
[![SkillPact L3](https://kajisho5.github.io/skillpact/badges/skillpact-L3.svg)](https://kajisho5.github.io/skillpact/ja/)
```
必要に応じて `L3` を `L1` や `L2` に替えてください。

## CI で正しさを保つ
```yaml
- uses: kajisho5/skillpact@<commit-sha>   # コミット SHA で固定する
  with: { path: ., min-level: L2 }
```

## レベル
- **L1**：契約が正しい形をしている。
- **L2**：さらに、適合テストがサンドボックス（ネットなし）で通る。
- **L3**：さらに、全ファイルが integrity に載り、信頼する作者が署名している。L3 は「安全」という意味ではありません。
