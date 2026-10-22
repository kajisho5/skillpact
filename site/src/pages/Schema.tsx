import { schemaFiles, schemaOf, latest, latestPolicy, type Lang } from "@/content";
import { Layout, PageHeader } from "@/components/Layout";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Toc } from "./Doc";

type Row = { path: string; type: string; req: boolean; notes: string; desc?: string };
const refName = (r: string) => r.replace("#/$defs/", "");
function typeOf(s: any): string {
  if (!s) return "any";
  if (s.$ref) return refName(s.$ref);
  if (s.enum) return "enum";
  if (s.const !== undefined) return "const";
  if (s.oneOf || s.anyOf) return (s.oneOf || s.anyOf).map(typeOf).join(" | ");
  if (s.type === "array") return `${typeOf(s.items)}[]`;
  return Array.isArray(s.type) ? s.type.join(" | ") : s.type || "any";
}
function notes(s: any): string {
  const n: string[] = [];
  if (s.enum) n.push(s.enum.map((v: any) => JSON.stringify(v)).join(", "));
  if (s.const !== undefined) n.push(JSON.stringify(s.const));
  if (s.items?.enum) n.push(s.items.enum.map((v: any) => JSON.stringify(v)).join(", "));
  if (s.pattern) n.push(`pattern ${s.pattern}`);
  for (const k of ["minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems"]) if (s[k] !== undefined) n.push(`${k} ${s[k]}`);
  if (s.default !== undefined) n.push(`default ${JSON.stringify(s.default)}`);
  if (s.additionalProperties && typeof s.additionalProperties === "object") n.push(`values: ${typeOf(s.additionalProperties)}`);
  return n.join(" · ");
}
function flatten(s: any, base = "", out: Row[] = [], depth = 0): Row[] {
  const req = new Set<string>(s.required || []);
  for (const [k, v] of Object.entries<any>(s.properties || {})) {
    const path = base ? `${base}.${k}` : k;
    out.push({ path, type: typeOf(v), req: req.has(k), notes: notes(v), desc: v.description });
    const inner = v.type === "array" ? v.items : v;
    if (inner && inner.properties && depth < 3) flatten(inner, v.type === "array" ? `${path}[]` : path, out, depth + 1);
  }
  return out;
}
function Fields({ rows, lang }: { rows: Row[]; lang: Lang }) {
  const h = lang === "ja" ? ["項目", "型", "必須", "値・制約"] : ["Field", "Type", "Required", "Values and constraints"];
  return (
    <div role="table" className="text-[0.8125rem]">
      <div role="row" className="hidden border-b pb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground sm:grid sm:grid-cols-[minmax(0,15rem)_9rem_5rem_minmax(0,1fr)] sm:gap-4">
        {h.map((x) => <span role="columnheader" key={x}>{x}</span>)}
      </div>
      {rows.map((r) => (
        <div role="row" key={r.path} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 border-b py-2.5 sm:grid-cols-[minmax(0,15rem)_9rem_5rem_minmax(0,1fr)]">
          <span role="cell" className="kbd break-all">{r.path.split(".").map((p, i, a) => i < a.length - 1 ? <span key={i} className="text-muted-foreground">{p}.</span> : <span key={i} className="font-medium">{p}</span>)}</span>
          <span role="cell" className="kbd text-right text-ink sm:text-left">{r.type}</span>
          <span role="cell" className={`text-muted-foreground ${r.req ? "" : "hidden sm:block"}`}>{r.req ? (lang === "ja" ? "必須" : "required") : ""}</span>
          <span role="cell" className={`col-span-2 break-words text-muted-foreground sm:col-span-1 ${r.notes || r.desc ? "" : "hidden sm:block"}`}><span className="kbd">{r.notes}</span>{r.desc && <span className="block">{r.desc}</span>}</span>
        </div>
      ))}
    </div>
  );
}
function Block({ id, title, schema, lang }: { id: string; title: string; schema: any; lang: Lang }) {
  const defs = Object.entries<any>(schema.$defs || {});
  return (
    <section aria-labelledby={id} className="border-t pt-10">
      <h2 id={id} className="text-xl font-semibold tracking-tight">{title}</h2>
      <p className="kbd mt-2 break-all text-muted-foreground">$id {schema.$id}</p>
      <div className="mt-6"><Fields rows={flatten(schema)} lang={lang} /></div>
      {defs.map(([name, d]) => (
        <div key={name} className="mt-10">
          <h3 id={`${id}-${name}`} className="kbd text-[0.95rem] font-medium">$defs/{name} <span className="font-normal text-muted-foreground">{typeOf(d)}</span></h3>
          {d.properties ? <div className="mt-3"><Fields rows={flatten(d)} lang={lang} /></div> : <p className="kbd mt-2 text-[0.8125rem] text-muted-foreground">{notes(d) || typeOf(d)}</p>}
        </div>
      ))}
    </section>
  );
}

export default function Schema({ lang }: { lang: Lang }) {
  const ja = lang === "ja";
  const c = schemaOf("contract", latest), p = schemaOf("policy", latestPolicy);
  const title = ja ? "スキーマ" : "Schema reference";
  const lead = ja ? `skill.contract.json とハーネスポリシーの JSON Schema（draft 2020-12）。下の一覧は最新の v${latest} から自動で生成しています。各ファイルは $id の URL でそのまま公開しています。`
    : `JSON Schemas (draft 2020-12) for skill.contract.json and the harness policy. The reference below is generated from the latest files (v${latest}). Every file is served unchanged at its $id URL.`;
  const heads = [{ depth: 2, id: "files", text: ja ? "ファイル" : "Files" }, { depth: 2, id: "contract", text: ja ? "契約" : "Contract" }, { depth: 2, id: "policy", text: ja ? "ポリシー" : "Policy" }];
  return (
    <Layout lang={lang} slug="schema" title={title} description={lead}>
      <div className="grid gap-x-16 lg:grid-cols-[minmax(0,1fr)_13rem]">
        <div className="min-w-0">
          <PageHeader eyebrow="JSON Schema" title={title} lead={lead} />
          <section aria-labelledby="files" className="border-t pt-10">
            <h2 id="files" className="text-xl font-semibold tracking-tight">{heads[0].text}</h2>
            <div className="mt-6">
              <Table className="text-[0.875rem]">
                <TableHeader><TableRow><TableHead>{ja ? "版" : "Version"}</TableHead><TableHead>{ja ? "契約" : "Contract"}</TableHead><TableHead>{ja ? "ポリシー" : "Policy"}</TableHead></TableRow></TableHeader>
                <TableBody>
                  {[...new Set(schemaFiles.map((s) => s.version))].map((v) => {
                    const f = (k: string) => schemaFiles.find((s) => s.kind === k && s.version === v);
                    const cell = (k: string) => { const x = f(k); return x ? <a className="kbd text-ink underline-offset-4 hover:underline" href={`/skillpact/schema/${x.file}`}>{x.file}</a> : <span className="text-muted-foreground">—</span>; };
                    return <TableRow key={v}><TableCell className="kbd">{v}{v === latest && <span className="ml-2 text-muted-foreground">{ja ? "最新" : "latest"}</span>}</TableCell><TableCell>{cell("contract")}</TableCell><TableCell>{cell("policy")}</TableCell></TableRow>;
                  })}
                </TableBody>
              </Table>
            </div>
          </section>
          <div className="mt-12 space-y-14">
            <Block id="contract" title={`${heads[1].text} · v${latest}`} schema={c} lang={lang} />
            <Block id="policy" title={`${heads[2].text} · policy-v${latestPolicy}`} schema={p} lang={lang} />
          </div>
        </div>
        <aside className="hidden pt-16 lg:block"><Toc headings={heads} label={ja ? "このページの内容" : "On this page"} /></aside>
      </div>
    </Layout>
  );
}
