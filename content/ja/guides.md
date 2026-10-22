# 導入ガイド

役割ごとの始め方です。パッケージはまだ公開していないので、リポジトリから入れます：`git clone https://github.com/kajisho5/skillpact && pip install -e skillpact/ref`。

## 利用者
1. `SKILL.md` の隣に `skill.contract.json` があるか、SkillPact のバッジがあるかを見ます。
2. 契約を[チェッカー](../check/)に貼り付けます（ブラウザの中だけで動き、何も送りません）。効果の一覧を読み、必要以上のものに触れないかを確かめます。
3. 正式なレベルは `python3 -m skillpact.cli conformance <skill_dir> --trusted-key <作者の鍵>` で確かめます。L3 の意味は「このファイル一式を、その鍵が署名し、テストが通った」ということだけです。
4. ハーネスの権限確認は切らないでください。SkillPact は実行時には何も強制しません。

## スキルの作者
1. `python3 -m skillpact.cli init <skill_dir> -o skill.contract.json` で下書きを作ります。すべての項目を確かめ、`TODO(...)` と `x.init.uncertain` を消します（残すと `UNCONFIRMED_DRAFT`）。
2. 範囲を狭くします（`/**` ではなく `$WORKDIR/**`）。spend と send は正直に宣言します。
3. ネットなしで動くテストを足し、`skillpact test <skill_dir>` で実行します。Linux は bubblewrap を入れると完全なサンドボックスになります。macOS は標準の Seatbelt（`sandbox-exec`）を自動で使います（試験的）。Windows は WSL2 か Linux コンテナの中で実行してください。テストからはホーム、`/tmp`、ホストの環境変数が見えません。`skip_unless_env` のケースに変数を渡すときは `--pass-env NAME` を付けます。
4. `__pycache__/` と `*.pyc` を消してから `skillpact hash <skill_dir>` で全ファイル（`migrate` の後も実行し直す）のハッシュを載せ、`skillpact sign <skill_dir> key.pem`（CI なら `sign-sigstore`）で署名します。公開鍵を公開します。
5. GitHub Action をコミット SHA で固定し、`pull_request_target` ではなく `pull_request` で動かします。書き方は次のとおりです。
```yaml
- uses: kajisho5/skillpact@<commit-sha>
  with: { path: ., min-level: L2 }
```
6. CI が出したレベルに合うバッジを[バッジ](../../badges/)から選んで表示します。

## ハーネスの開発元
1. インストール時に `skill.contract.json` を読んで検証します（Python のライブラリか TypeScript の `validate`）。
2. 利用者のポリシーと照合し（`match_policy`）、capability ごとに `decision` と `decision_worst_case` を示します。
3. 結果を自社の権限設定に変換します。Claude Code・Cursor・Codex・Gemini CLI については `policy-compile` と、その `lossy` の一覧を参考にしてください。
4. 実行直前に integrity を確かめ直し（TOCTOU 対策）、版が上がって権限が広がったら確認し直します。
5. 自社の検証者に適合スイートをかけます：`python3 conformance/run.py --cmd '<検証者> {dir}'`。

## 企業と CI
1. ポリシーを 1 つ書き、効果ごとの既定、ルール、`trusted_keys`、`require_signature: true`、`min_contract_version: "0.8"` を決めます。
2. CI ですべてのスキルに `conformance` をかけ、必要なレベルに届かなければ失敗させます。
3. そのポリシーから変換したハーネス設定を配ります。ハーネスごとの `lossy` の一覧を確認してください。
4. 実行中の強制には実行時ポリシー（HushSpec、APS / ACS 向けの Rego）を使います。
5. 承認したスキルの版ごとに、署名された契約をレビューの記録として残します。
