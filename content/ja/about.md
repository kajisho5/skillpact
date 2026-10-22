# この仕様について

位置づけ、運営、法的な事項、実務的な情報です。[仕様](../spec/)、[設計の理由](../rationale/)、[なぜ SkillPact か](../why/)もご覧ください。

## 位置づけ
ドラフト 0.8（2026-10-22）。編集者によるドラフトで、安定版ではありません。英語の仕様が規範で、日本語は翻訳です。1.0 はまだありません。公開レビューの日程は未定です。

## 運営と決め方
編集者は shogo kajiyama（SEVENTHWELL）です。変更は [GOVERNANCE.md](https://github.com/kajisho5/skillpact/blob/main/GOVERNANCE.md) の手順に従います：issue を立て、7 日以上議論し、仕様・スキーマ・適合スイート・両実装をまとめて更新するプルリクエストを出し、理由を書いて決定します。参加の仕方は [CONTRIBUTING.md](https://github.com/kajisho5/skillpact/blob/main/CONTRIBUTING.md)、行動規範は [CODE_OF_CONDUCT.md](https://github.com/kajisho5/skillpact/blob/main/CODE_OF_CONDUCT.md)。

## 脆弱性の報告
kajiyama@seventh-well.com か、GitHub の非公開の脆弱性報告で知らせてください。[SECURITY.md](https://github.com/kajisho5/skillpact/blob/main/SECURITY.md)。

## 知的財産
- 仕様の本文は CC BY 4.0。スキーマ、適合スイート、実装は Apache-2.0 で、貢献者それぞれの貢献に対する特許ライセンスを含みます。
- SEVENTHWELL と Shogo Kajiyama は、仕様の実装に対して防御的終了つきの無償の特許不主張を誓約しています（Microsoft Open Specification Promise と OWFa 1.0 を参考）。[IPR.md](https://github.com/kajisho5/skillpact/blob/main/IPR.md)。

## 商標とバッジ
「SEVENTHWELL」は発行者の名前です。「SkillPact」は仕様に従う実装や契約を説明するために使えます。L1/L2/L3 のバッジは、CI か `skillpact conformance` が実際に出したレベルだけを表示し、SEVENTHWELL の推薦を受けたように見せないでください。[TRADEMARKS.md](https://github.com/kajisho5/skillpact/blob/main/TRADEMARKS.md)。

## 引用
[CITATION.cff](https://github.com/kajisho5/skillpact/blob/main/CITATION.cff) を使ってください：「SkillPact Specification, draft 0.8, SEVENTHWELL, 2026.」

## ロードマップ
[ROADMAP.md](https://github.com/kajisho5/skillpact/blob/main/ROADMAP.md)。次は公開レビュー、その後に安定したスキーマ URL とパッケージ公開を伴う 1.0 です。

## メディアタイプとファイル名
ファイル名は常に `skill.contract.json` です。`application/json` で配信し、専用のメディアタイプは登録しておらず、IANA 登録は 1.0 の後に検討します（仕様の付録 D）。

## このサイトのアクセシビリティ
言語属性つきの意味のある HTML、ページごとに 1 つの見出し、表の見出し、見えるフォーカス、十分な色のコントラストを使っています。チェッカーはキーボードで操作できます。問題は GitHub issue で知らせてください。[ACCESSIBILITY.md](https://github.com/kajisho5/skillpact/blob/main/ACCESSIBILITY.md)。

## 謝辞
[ACKNOWLEDGEMENTS.md](https://github.com/kajisho5/skillpact/blob/main/ACKNOWLEDGEMENTS.md)。

## 文書のチェックリスト
仕様に期待される項目と、その置き場所：[STANDARDS_CHECKLIST.md](https://github.com/kajisho5/skillpact/blob/main/STANDARDS_CHECKLIST.md)。
