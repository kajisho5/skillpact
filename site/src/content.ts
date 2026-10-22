import GithubSlugger from "github-slugger";

export type Lang = "en" | "ja";
const raw = import.meta.glob("@repo/content/*/*.md", { query: "?raw", import: "default", eager: true }) as Record<string, string>;
const schemas = import.meta.glob("@repo/docs/schema/*.json", { import: "default", eager: true }) as Record<string, any>;

export const docs: Record<Lang, Record<string, string>> = { en: {}, ja: {} };
for (const [p, src] of Object.entries(raw)) {
  const m = p.match(/content\/(en|ja)\/([\w-]+)\.md$/);
  if (m) docs[m[1] as Lang][m[2]] = src;
}
export const docSlugs = Object.keys(docs.en).sort();

const ver = (s: string) => s.split(".").map(Number);
const cmp = (a: string, b: string) => { const x = ver(a), y = ver(b); return x[0] - y[0] || x[1] - y[1]; };
export const schemaFiles = Object.entries(schemas).map(([p, json]) => {
  const file = p.split("/").pop()!; const m = file.match(/^(policy-)?v(\d+\.\d+)(-r\d+)?\.json$/)!;
  return { file, kind: m[1] ? "policy" : "contract", version: m[2], json };
}).sort((a, b) => cmp(b.version, a.version));
export const latest = schemaFiles.find((s) => s.kind === "contract")!.version;
export const latestPolicy = schemaFiles.find((s) => s.kind === "policy")!.version;
export const schemaOf = (kind: string, v: string) => schemaFiles.find((s) => s.kind === kind && s.version === v)!.json;

export type Heading = { depth: number; id: string; text: string };
export function parseDoc(src: string) {
  const slugger = new GithubSlugger(); const headings: Heading[] = []; let title = ""; let inCode = false;
  const body: string[] = [];
  for (const line of src.split("\n")) {
    if (line.startsWith("```")) inCode = !inCode;
    const m = !inCode && line.match(/^(#{1,6}) (.*)$/);
    if (m) {
      const text = m[2].replace(/[`*]/g, "").replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
      const id = slugger.slug(text);
      if (m[1].length === 1 && !title) { title = text; continue; }
      if (m[1].length <= 3) headings.push({ depth: m[1].length, id, text });
    }
    body.push(line);
  }
  // first paragraph after the H1 is used as the description
  const desc = body.join("\n").trim().split(/\n\s*\n/)[0].replace(/[*`]/g, "").replace(/\[([^\]]+)\]\([^)]+\)/g, "$1").slice(0, 200);
  return { title, headings, body: body.join("\n"), desc };
}
