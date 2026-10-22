# SkillPact 適合テストスイート（spec 0.5）

実装を問わずに使える検証者（validator）向けのテスト集です。

- `manifest.json`: ケースの一覧と期待結果（valid / errors / errors_any / warnings_include）
- `cases/<id>/`: `SKILL.md` と `skill.contract.json`
- `vectors/jcs-ed25519.json`: 正規化（RFC 8785）と ed25519 署名の既知の答え
- `run.py`: ランナー。`--cmd` に、`{dir}` を受け取り JSON（`ok`, `findings[].level/code`）を出すコマンドを渡す

```
python3 run.py --cmd 'python3 -m skillpact.cli validate {dir}'   # ref/ で実行
```

署名ケースの鍵はテスト専用（シード公開）。実際の署名に使ってはいけません。
