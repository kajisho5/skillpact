# SkillPact spec draft 0.3 — 差分 (base: spec_v0.2.md)

License: CC BY 4.0 (spec) / Apache-2.0 (reference code). © 2026 SEVENTHWELL (shogo kajiyama). **Unpublished draft.**

## 1. 正式 URL
- Contract schema: `https://seventh-well.com/skillpact/schema/v0.3.json`
- Policy schema: `https://seventh-well.com/skillpact/schema/policy-v0.3.json`
- Contract は `"$schema"` にこの URL を書いてよい(任意)。`contract_version` は `"0.3"`(0.1/0.2 も引き続き valid)。

## 2. Sigstore 署名(任意、ed25519 と併用可)
- `integrity.signatures[]` に `{"type":"sigstore","identity":<SAN>,"issuer":<OIDC issuer>,"bundle":<Sigstore bundle>}` を追加。
- 署名対象バイトは ed25519 と同じ canonical JSON(signatures を除き key ソート)。
- 検証者は bundle の検証に加え、identity+issuer を自分の信頼リストと照合しなければならない(MUST)。
- CLI: `skillpact sign-sigstore <dir> [--identity-token T] [--staging]`。CI(GitHub Actions `id-token: write`)向け。
- `conformance --trusted-key` には `ed25519:<b64>` か `sigstore:<issuer>|<identity>` を渡す。
- L3 は「信頼済み ed25519 鍵 **または** 信頼済み Sigstore identity の署名が 1 つ以上有効」。

## 3. 他形式との相互変換(`skillpact convert`)
| 形式 | export | import |
|---|---|---|
| MDA Open Spec 1.0 `metadata.mda.requires` | tools / network / packages / runtime / cost-hints | 各ツールを effect に対応、scope 無しは `level:any` |
| AutoVault `capabilities` / `tools_required` | network(bool) / filesystem / tools | 同上、`requires-secrets` → `requirements.env` |
- export は必ず `lossy`(落ちた情報の一覧)と、元 contract へのポインタ+sha256(`metadata.skillpact` / `x-skillpact`)を出す。
- import は推測した箇所を `x.import.uncertain` に列挙。tests は空なので L1 止まり。

## 4. OWASP Agentic Skills Top 10 対応
- `skillpact owasp <dir>` が AST01–AST10 ごとに addressed / partial と根拠・残課題を出す。表は `owasp_mapping.md`。

## 5. 位置付け(明文化)
- SkillPact は **インストール前** の「宣言 + テスト + 署名」と、各ハーネス設定への変換を担う。
- 実行時の強制は APS / ACS / HushSpec など既存ランタイムに任せる(`export --format hushspec|rego|aps|acs`)。
- スキャナー(静的解析・LLM 判定)と競合せず、スキャナーの入力にもなる。

## Changelog 0.2 → 0.3
- 追加: Sigstore 署名、MDA/AutoVault 変換、OWASP 対応表と CLI、APS/ACS export、正式 `$id`。
- 変更: schema `$id` を seventh-well.com/skillpact/schema/ 配下へ。
- 互換: 0.2 contract はそのまま valid。
