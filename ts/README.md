# skillpact-verify (TypeScript, verify-only)

SkillPact の 2 つ目の独立実装。Python 参照実装のコードは使わず、仕様（spec_v0.6.md）とスキーマだけから作った。

- できること: `validate`（スキーマ＋全検査、エラーコードは仕様の付録 A）、integrity の照合、ed25519 署名の検証（0.4 以上は RFC 8785 JCS、0.3 以前は旧方式）、重複キーの拒否
- できないこと: テストの実行（L2）、Sigstore の検証（`SIGSTORE_UNVERIFIED` の警告を出す）、署名の作成
- 旧方式（0.1〜0.3）の正規化は、Python の浮動小数点表記（`1.0` など）を再現できない。整数と文字列だけの契約では一致する

```
npm install && npm test            # JCS ベクトル、適合スイート 23 件、見本 4 件の署名
node dist/cli.js validate <skill_dir>
node dist/cli.js verify <skill_dir> --trusted-key ed25519:...
```
