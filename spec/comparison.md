# 隣接仕様との比較（2026-10-22 時点、Web で再確認）

| 観点 | SkillPact 0.8 | Agent Skills（agentskills.io） | MDA Open Spec 1.0（sno-ai/mda） | AutoVault | SkillSeal（複数の同名プロジェクト） |
|---|---|---|---|---|---|
| 置き場所 | `SKILL.md` の横の `skill.contract.json`（SKILL.md は変えない） | `SKILL.md` frontmatter | `.mda` → `SKILL.md` などへコンパイル、`metadata.mda.*` | `SKILL.md` frontmatter の拡張フィールド | 署名ファイル / 1 行トークン / 証明書カタログ |
| 効果の宣言 | 6 区分（read/write/network/exec/spend/send）＋範囲・条件付き効果 | `allowed-tools`（実験的）、`compatibility` は自由文 | `requires`: runtime / tools / network（none・local・public・ホスト）/ packages / model / cost-hints | `capabilities`: network(bool)・filesystem(ro/rw)・tools、`tools_required` | なし |
| テスト | オフラインの適合テスト（L2） | なし | 仕様の適合フィクスチャ（V/C レベル）はあるが、スキル自体のテストはない | 宣言と本文の照合（静的） | skillseal/skillseal は実行証拠に署名 |
| 署名 | ed25519 / Sigstore、JCS（RFC 8785） | なし | Sigstore 系の署名（任意） | Ed25519 のマニフェスト（ボルト側の鍵） | ed25519（getskillseal）、GPG・SSH・複数鍵・レビュアー証明（mcyork） |
| ハーネス設定への変換 | Claude Code / Cursor / Codex / Gemini CLI、HushSpec / Rego | なし | ベンダー名前空間 `metadata.<vendor>.*` | エージェントごとの tool 名変換（transformations） | Claude Code 用フック（mcyork） |
| 仕様の成熟度 | 0.8 ドラフト、BCP 14（英語が規範）、適合スイート 48 ケース、2 実装 | 安定、参照バリデータあり | 1.0 Stable、BCP 14、適合マニフェスト、REGISTRY.md | 製品仕様（単一実装） | 製品・ツール |

## 取り込むべき点（v1.0 前の検討項目）
1. **network: local**（MDA）: ループバック・社内網だけを表す区分が SkillPact にはない。`scope` に `localhost` などを書けば表せるが、標準の書き方を決めると変換が無損失になる。
2. **名前の規則**（Agent Skills）: name は親ディレクトリ名と一致が MUST。SkillPact の検証者は警告（`FM_NAME_DIR`）に留めている。`--contract` で別置きの契約を検証する場合を除いてエラーにするか検討。
3. **レビュアー証明**（SkillSeal / mcyork）: 作者以外（レビュアー・スキャナー）の署名を区別する `role` が無い。`signatures[].role`（author / reviewer / scanner）を任意フィールドで足す案。
4. **共通の tool 名**（AutoVault）: `fs.read` などの共通名と、エージェントごとの変換。SkillPact は効果区分で抽象化しているため必須ではないが、`convert --to autovault` の損失を減らせる。
5. **レジストリの運用**（MDA REGISTRY.md）: 拡張 `x.<vendor>` と新しい効果・キーの登録手続き。GOVERNANCE.md に取り込み済み（簡易版）。

## 差別化（変わらない点）
効果 6 区分（特に spend / send の分離）× 隔離した適合テスト × 署名 × 各ハーネス設定への変換を 1 ファイルで持つものは、調べた範囲では他にない。

出典: https://agentskills.io/specification ／ https://github.com/sno-ai/mda/blob/main/spec/v1.0/10-capabilities.md ／ https://mda.sno.dev/mdx/specification ／ https://autovault.dev/authoring ／ https://github.com/autoworks-ai/autovault ／ https://github.com/mcyork/skillseal ／ https://github.com/getskillseal/skillseal ／ https://github.com/skillseal/skillseal
