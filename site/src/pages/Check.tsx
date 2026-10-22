import { useEffect, useState } from "react";
import type { Lang } from "@/content";
import { Layout, PageHeader } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

const EXAMPLE_KEY = "ed25519:moqKymSKFxCPXkaxDtETg/Qd8GvRwg8ckWAWIRQJXSQ=";
export const CHECK_CSP = "default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; font-src 'self'; connect-src 'self'; img-src 'self' data:; form-action 'none'; base-uri 'self'";
type Finding = { level: string; code: string; message: string; where?: string };
type Result = { ok: boolean; level: string; skill?: { name: string; version: string }; contract_version?: string; findings: Finding[]; risky: string[]; signatures: Record<string, boolean | null>; roles?: Record<string, string> };
declare global { interface Window { SkillPact?: { check: (c: string, keys: string[], opts?: { lang?: Lang }) => Promise<Result> } } }

const T = {
  en: { title: "Check a contract", lead: "Paste a skill.contract.json. Schema validation, cross-checks, risky effects and ed25519 signatures are checked by the TypeScript implementation running in this page. Nothing is uploaded: the page's Content Security Policy only allows requests to this site.",
    contract: "Contract JSON", keys: "Trusted keys", keysHint: "One per line. Optional.", run: "Check", example: "Load example (thumbnail-skill, signed)", result: "Result", errors: "Errors", warnings: "Warnings", risky: "Effects to review", sigs: "Signatures", valid: "valid", invalid: "invalid", na: "not checked in the browser", trusted: "trusted", role: "role", loading: "Loading checker…", none: "No findings.",
    notChecked: "Not checked here: files listed in integrity.files (the page only sees the contract), conformance tests (L2) and Sigstore bundles. Run pipx run skillpact conformance <dir> or the GitHub Action for the full level." },
  ja: { title: "契約を確認する", lead: "skill.contract.json を貼り付けてください。スキーマの検証、項目どうしの整合、注意が要る副作用、ed25519 署名を、このページの中で動く TypeScript 実装が確認します。何も送信しません。このページのセキュリティポリシーは、このサイト以外への通信を許可していません。",
    contract: "契約の JSON", keys: "信頼する鍵", keysHint: "1行に1つ。省略できます。", run: "確認する", example: "例を読み込む（thumbnail-skill、署名あり）", result: "結果", errors: "エラー", warnings: "警告", risky: "注意が要る副作用", sigs: "署名", valid: "有効", invalid: "無効", na: "ブラウザでは未確認", trusted: "信頼済み", role: "役割", loading: "チェッカーを読み込み中…", none: "指摘はありません。",
    notChecked: "ここで確認しないもの：integrity.files に書かれたファイル（このページは契約しか見ません）、適合テスト（L2）、Sigstore のバンドル。完全なレベルは pipx run skillpact conformance <dir> か GitHub Action で確認してください。" },
};

export default function Check({ lang }: { lang: Lang }) {
  const t = T[lang];
  const [ready, setReady] = useState(false);
  const [contract, setContract] = useState(""); const [keys, setKeys] = useState("");
  const [r, setR] = useState<Result | null>(null); const [err, setErr] = useState("");
  useEffect(() => {
    if (window.SkillPact) { setReady(true); return; }
    const s = document.createElement("script"); s.src = "/skillpact/check/skillpact-check.js"; s.onload = () => setReady(true); document.head.appendChild(s);
  }, []);
  const ks = keys.split(/\s+/).filter(Boolean);
  const run = async () => { setErr(""); try { setR(await window.SkillPact!.check(contract, ks, { lang })); } catch (e) { setErr(String(e)); setR(null); } };
  const loadEx = async () => { setContract(await fetch("/skillpact/check/example.json").then((x) => x.text())); setKeys(EXAMPLE_KEY); };
  const errs = r?.findings.filter((f) => f.level === "error") ?? [], warns = r?.findings.filter((f) => f.level === "warn") ?? [];
  return (
    <Layout lang={lang} slug="check" title={t.title} description={t.lead} csp={CHECK_CSP}>
      <PageHeader eyebrow={lang === "ja" ? "ブラウザ内で実行" : "Runs in your browser"} title={t.title} lead={t.lead} />
      <div className="grid gap-x-12 gap-y-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="space-y-5">
          <div>
            <label htmlFor="c" className="mb-1.5 block text-sm font-medium">{t.contract}</label>
            <Textarea id="c" spellCheck={false} value={contract} onChange={(e) => setContract(e.target.value)} placeholder='{"contract_version": "0.8", ...}' className="kbd min-h-[18rem] leading-relaxed" />
          </div>
          <div>
            <label htmlFor="k" className="mb-1.5 block text-sm font-medium">{t.keys} <span className="font-normal text-muted-foreground">{t.keysHint}</span></label>
            <Textarea id="k" spellCheck={false} value={keys} onChange={(e) => setKeys(e.target.value)} placeholder={EXAMPLE_KEY} className="kbd min-h-[3.5rem]" />
          </div>
          <div className="flex flex-wrap gap-3">
            <Button id="go" onClick={run} disabled={!ready || !contract.trim()}>{ready ? t.run : t.loading}</Button>
            <Button id="ex" variant="outline" onClick={loadEx}>{t.example}</Button>
          </div>
        </div>
        <div aria-live="polite" className="min-w-0">
          <h2 className="kbd mb-3 text-muted-foreground">{t.result}</h2>
          {err && <p className="text-destructive">{err}</p>}
          {!r && !err && <div className="rounded-md border border-dashed px-4 py-10 text-center text-sm text-muted-foreground">—</div>}
          {r && (
            <div className="divide-y rounded-md border text-sm">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-3">
                <span className={`kbd text-base font-semibold ${r.ok ? "text-ok" : "text-destructive"}`}>{r.level}</span>
                {r.skill && <span className="text-muted-foreground">{r.skill.name} {r.skill.version} · contract {r.contract_version}</span>}
              </div>
              {[[t.errors, errs, "text-destructive"], [t.warnings, warns, "text-warn"]].map(([h, list, cls]) => (list as Finding[]).length > 0 && (
                <div key={h as string} className="px-4 py-3"><h3 className="mb-2 font-medium">{h as string}</h3>
                  <ul className="space-y-1.5">{(list as Finding[]).map((f, i) => <li key={i}><code className={`kbd ${cls}`}>{f.code}</code> <span>{f.message}</span> {f.where && <span className="kbd text-muted-foreground">{f.where}</span>}</li>)}</ul></div>
              ))}
              {r.risky.length > 0 && <div className="px-4 py-3"><h3 className="mb-2 font-medium">{t.risky}</h3><ul className="list-disc space-y-1 pl-5">{r.risky.map((x) => <li key={x}>{x}</li>)}</ul></div>}
              {Object.keys(r.signatures).length > 0 && <div className="px-4 py-3"><h3 className="mb-2 font-medium">{t.sigs}</h3>
                <ul className="space-y-1.5">{Object.entries(r.signatures).map(([k, v]) => <li key={k} className="break-all"><code className="kbd">{k}</code> <span className="text-muted-foreground">· {t.role}: {r.roles?.[k] || "author"} · </span>
                  <span className={v === true ? "text-ok" : v === false ? "text-destructive" : "text-muted-foreground"}>{v === true ? t.valid : v === false ? t.invalid : t.na}</span>{ks.includes(k) && <span className="text-muted-foreground"> · {t.trusted}</span>}</li>)}</ul></div>}
              {!errs.length && !warns.length && <p className="px-4 py-3 text-muted-foreground">{t.none}</p>}
            </div>
          )}
          <p className="mt-6 text-[0.8125rem] leading-relaxed text-muted-foreground">{t.notChecked}</p>
        </div>
      </div>
    </Layout>
  );
}
