# エージェント「ハーネス」標準の調査 + harness_policy 0.1（ドラフト）
作成 2026-10-21（JST）。非公開。

## 1. 各ハーネスの設定の現状（出典は §6）
| ハーネス | 権限 | 承認 | フック | サンドボックス / 通信 | 予算・ループ上限 |
|---|---|---|---|---|---|
| Claude Code `settings.json` | `permissions.allow/ask/deny`、`Bash(npm run *)` `Read(./.env)` `WebFetch(domain:x)`。評価順 deny→ask→allow | `defaultMode`（acceptEdits 等） | PreToolUse 等。hook は allow/deny/ask を返せるが deny/ask ルールは上書き不可。skill frontmatter にも hook 可 | 作業ディレクトリ外読み取りの制限など | 標準キーなし |
| Cursor | CLI `cli-config.json` の `permissions.allow/deny`（`Shell(ls)` `Read()` `Write()` `WebFetch()` `Mcp(server:tool)`）。deny 優先。**ask リストなし** | 未許可は都度確認 | `hooks.json`: beforeShellExecution / beforeMCPExecution / beforeReadFile 等で allow/deny/ask。既定 fail-open、`failClosed` あり | sandbox フラグ | なし |
| Codex `config.toml` | 細かい権限ルールは少なめ（granular approval は新しめ） | `approval_policy` = untrusted / on-request / never ほか | notify 等 | `sandbox_mode` = read-only / workspace-write / danger-full-access、`network_access`、`writable_roots` | なし |
| Gemini CLI | Policy engine: `~/.gemini/policies/*.toml` の `[[rule]]`（toolName, commandPrefix, argsPattern, decision=allow/deny/ask_user, priority）。非対話では ask_user→deny | approval mode | hooks あり | sandbox（コンテナ）、trusted folders | なし |
| Zed ACP | ― | `session/request_permission`（allow_once / allow_always / reject_once / reject_always）= **承認のやり取りの通信規格** | ― | ― | ― |
| A2A | Agent Card の skill ごとの security（OAuth/mTLS 等） | ― | ― | HTTPS 必須 | ― |
| MCP | tool annotations（readOnly/destructive/idempotent/openWorld のヒント）、elicitation | クライアント任せ | ― | ― | ― |
| AGENTS.md | 自由文の指示（強制力なし。Claude 文書も「規則はハーネスが強制、CLAUDE.md は強制しない」と明記） | ― | ― | ― | ― |
| OpenTelemetry GenAI semconv | ― | ― | ― | ― | `invoke_agent` / `execute_tool` span、`gen_ai.tool.name` 等 = **監査ログの共通形式は既にある** |

## 2. 「エージェント用ポリシー」の既存の取り組み（重要：先行あり）
- **Agent Policy Specification (APS)**（Apache-2.0、DRAFT）: input / tool_call / output の 3 地点で allow / deny / redact / transform / audit。言語は Rego 等自由。実行時の「強制の約束」。
- **Microsoft Agent Control Specification (ACS)**（2026-06 発表、Agent Governance Toolkit）: 8 つの介入点（agent_startup, pre_tool_call …）、正規化された入力、fail-closed、allow / warn / deny / escalate。
- **HushSpec**: YAML でツール許可・禁止・要確認、パス、egress 許可リスト。ポータブルな実行時ポリシー。
- **OPA / Rego**: 汎用ポリシーエンジン。エージェントの語彙は持たない。

→ 「ポータブルな実行時ポリシーファイル」自体は **もう空白ではない**（APS / ACS / HushSpec）。

## 3. ギャップ仮説の検証
元の仮説: ポータブルなハーネスポリシー（権限・要承認・フック・ループ/予算・サンドボックス・egress）を作り、スキル契約の副作用宣言と照合して allow/ask/deny を自動判定。

判定: **部分的に成立（狭めれば成立）**。
- ✗ 実行時の「ツール呼び出しごと」の判定規格を新たに作るのは APS/ACS/HushSpec と正面衝突。作らない。
- ✓ 既存はどれも **ツール名・引数**（Bash(...) や toolName）で判定する。**スキルが事前に宣言した副作用の区分**（read/write/network/exec/spend/send＋範囲）と突き合わせて、**インストール前・実行前に** 決める仕組みは見当たらない。
- ✓ Claude / Cursor / Codex / Gemini の設定は書式も意味もバラバラ（ask の有無、評価順、サンドボックス概念）。**1 つのポリシーから各社のネイティブ設定を生成する** ものも見当たらない。
- ✓ ループ回数・ツール呼び出し数・時間・費用の上限は主要 CLI に標準キーがない。宣言だけでも置き場所を作る価値あり。

**位置づけ**: 「スキル契約 ↔ ポリシー」の橋渡し層。実行時強制は各ハーネス / APS / ACS / HushSpec に任せ、本仕様は (a) 事前判定、(b) ネイティブ設定への変換、(c) 監査を OTel GenAI に寄せる、の 3 つに絞る。

## 4. harness_policy 0.1（短い仕様）
ファイル: `harness.policy.json`（スキーマ `ref/skillpact/policy_schema.json`）。

```json
{
  "policy_version": "0.1",
  "defaults": {"read":"allow","write":"ask","network":"ask","exec":"ask","spend":"deny","send":"ask"},
  "rules": [{"id":"write-workdir","effect":"write","scope":["$OUTPUT","$WORKDIR/**"],"decision":"allow"}],
  "skills": {"allow": [], "deny": []},
  "require_signature": false, "trusted_keys": [],
  "ask_on_destructive": true,
  "limits": {"max_turns":200,"max_tool_calls":500,"max_wall_seconds":3600,"max_cost_usd":5},
  "sandbox": {"filesystem":"workdir","network":"allowlist","egress_allowlist":["*.github.com"]},
  "hooks": {"pre_action": [], "post_action": []},
  "audit": {"otel_genai": true}
}
```

判定アルゴリズム（MUST）:
1. `skills.deny` に名前 → **deny**。`require_signature` で `trusted_keys` の有効署名がなければ → **deny**。
2. 各 capability の各 effect について、`rules` を **上から順に、最初に一致したもの** を採用。一致しなければ `defaults[effect]`。
   - 一致条件: 契約側 `level=scoped` なら **宣言 scope の全要素** がルールの glob のどれかに一致。`level=any` は `scope` 省略または `["*"]` のルールにのみ一致。
3. spend / send が `level=any` のとき allow は ask に格下げ（`never_auto_allow_any`、既定 [spend, send]）。
4. 契約側 `confirm: each` は allow を ask に格下げ。`destructive: true` は `ask_on_destructive` なら ask。
5. capability の判定 = effect の中で最も厳しいもの（deny > ask > allow）。スキル全体 = capability の最も厳しいもの。
   ハーネスは capability 単位で使い分けてよい（例: probe は allow、export は ask）。
6. 非対話実行では ask を deny と扱う（SHOULD、Gemini CLI と同じ）。

ネイティブ変換（参照実装 `policy-compile`、ベストエフォート）:
- claude-code → `permissions.allow/ask/deny`（`Bash(ffmpeg *)`, `WebFetch(domain:…)`）
- cursor → `permissions.allow/deny`（ask は「どちらにも書かない＝毎回確認」）
- codex → `approval_policy`, `sandbox_mode`, `sandbox_workspace_write.network_access`
- gemini-cli → `[[rule]]`（commandPrefix, decision, priority）
変換で表せない項目（limits、spend/send）は捨てずに警告対象（v0.2 で出力に `unmapped` を追加予定）。

## 5. 参照実装とテスト
`ref/skillpact/core.py` の `match_policy` / `compile_native`、CLI `policy-check` / `policy-compile`。
サンプル方針 `ref/policies/solo-dev.json`（個人開発向け）→ ffmpeg-skill は **allow**、`strict-ci.json`（署名必須）→ 未署名なので **deny**、信頼鍵で署名すると allow。
テスト（全 19 件中ポリシー関連 9 件）: 範囲外 write は ask / spend は deny・send any は自動許可しない / destructive は ask / 最初の一致ルール優先 / 署名必須 / スキル拒否リスト / 不正ポリシー検出 / 4 ハーネスへの変換 / CLI 終了コード。

## 6. 出典
- Claude Code permissions: https://code.claude.com/docs/en/permissions ・ settings: https://code.claude.com/docs/en/settings-reference ・ hooks: https://code.claude.com/docs/en/hooks
- Cursor hooks: https://cursor.com/docs/hooks ・ CLI permissions: https://cursor.com/docs/cli/reference/permissions ・ config: https://cursor.com/docs/cli/reference/configuration
- Codex config reference: https://developers.openai.com/codex/config-reference.md ・ approvals/security: https://learn.chatgpt.com/docs/agent-approvals-security
- Gemini CLI policy engine: https://geminicli.com/docs/reference/policy-engine/
- Zed ACP tool calls / request_permission: https://github.com/zed-industries/agent-client-protocol/blob/main/docs/protocol/tool-calls.mdx
- A2A spec: https://a2a-protocol.org/latest/specification/
- MCP tools (annotations): https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- OpenTelemetry GenAI agent spans: https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md
- Agent Policy Specification: https://agentpolicyspecification.github.io/
- Microsoft ACS: https://commandline.microsoft.com/agent-control-specification-runtime-governance/ ・ https://github.com/microsoft/agent-governance-toolkit
- HushSpec: https://www.hushspec.org/docs/specification/core/
- OPA: https://www.openpolicyagent.org/

## 7. v0.2 の追加（2026-10-21 JST）
- スコープ確定（shogo）: 担うのは「インストール前の照合」と「ハーネス設定への変換」だけ。実行時の強制は HushSpec / APS / ACS / 各ハーネスに任せる。
- 変換結果を各ハーネスの公開スキーマで検証するようにした:
  - Claude Code: SchemaStore
  - Codex: developers.openai.com/codex/config-schema.json
  - Gemini CLI と Cursor: 公開スキーマが無いため、ドキュメントから書き起こしたスキーマ
- HushSpec 1.0 への書き出しを実装した（コア仕様のフィールド表に合わせ、未知フィールドなし）。
- Rego への書き出しを実装した（APS / ACS の中身として使う想定。OPA 1.21 で評価テスト済み）。
- 仕様の詳細: spec_v0.2.md §7–8。
