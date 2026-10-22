// Post-build: 404 page, sitemap, and a check that static artifacts are byte-identical to docs/.
import fs from "node:fs"; import path from "node:path"; import crypto from "node:crypto";
const out = path.resolve("dist"); const REPO = process.env.SKILLPACT_REPO || path.resolve("..");
const SITE = "https://kajisho5.github.io/skillpact/";
const pages = []; (function walk(d) { for (const f of fs.readdirSync(d)) { const p = path.join(d, f); if (fs.statSync(p).isDirectory()) walk(p); else if (f === "index.html") pages.push(path.relative(out, path.dirname(p))); } })(out);
fs.writeFileSync(path.join(out, "sitemap.xml"), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${pages.sort().map((p) => `  <url><loc>${SITE}${p ? p + "/" : ""}</loc></url>`).join("\n")}\n</urlset>\n`);
fs.writeFileSync(path.join(out, "robots.txt"), `User-agent: *\nAllow: /\nSitemap: ${SITE}sitemap.xml\n`);
const h = (p) => crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");
let bad = 0; for (const rel of ["schema", "badges"]) for (const f of fs.readdirSync(path.join(REPO, "docs", rel))) if (/\.(json|svg)$/.test(f)) { if (h(path.join(REPO, "docs", rel, f)) !== h(path.join(out, rel, f))) { console.error("MISMATCH", rel, f); bad++; } }
console.log(`pages: ${pages.length}; artifacts identical: ${bad === 0}`); if (bad) process.exit(1);

// Externalise inline scripts (so a strict CSP without 'unsafe-inline' works) and put <meta charset> first in <head>.
for (const p of pages) {
  const f = path.join(out, p, "index.html"); let t = fs.readFileSync(f, "utf8");
  t = t.replace(/\s*<meta charset="utf-8">/, "").replace("<head>", '<head><meta charset="utf-8">');
  t = t.replace(/<script>([\s\S]*?)<\/script>/g, (_, js) => {
    const name = `assets/boot-${crypto.createHash("sha256").update(js).digest("hex").slice(0, 12)}.js`;
    fs.writeFileSync(path.join(out, name), js); return `<script src="/skillpact/${name}"></script>`;
  });
  if (/<script>/.test(t)) { console.error("inline script left in", p); process.exit(1); }
  fs.writeFileSync(f, t);
}
// 404 page: copy of the home shell is not right; write a small static one.
fs.writeFileSync(path.join(out, "404.html"), `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Not found — SkillPact</title><script src="/skillpact/theme.js"></script><link rel="stylesheet" href="/skillpact/${fs.readdirSync(path.join(out, "assets")).find((x) => x.startsWith("app-") && x.endsWith(".css"))}"></head><body><main class="container max-w-[46rem] py-24"><p class="kbd text-muted-foreground">404</p><h1 class="mt-2 text-2xl font-semibold">Page not found · ページが見つかりません</h1><p class="mt-4"><a class="text-ink underline" href="/skillpact/">SkillPact</a> · <a class="text-ink underline" href="/skillpact/ja/">日本語</a></p></main></body></html>`);
console.log("post-processed", pages.length);
