import puppeteer from "puppeteer-core"; import fs from "node:fs"; import path from "node:path";
const axe = fs.readFileSync("node_modules/axe-core/axe.min.js", "utf8");
const B = "http://localhost:4173";
const pages = []; (function walk(d) { for (const f of fs.readdirSync(d)) { const p = path.join(d, f); if (fs.statSync(p).isDirectory()) walk(p); else if (f === "index.html") pages.push("/skillpact/" + (path.relative("dist", d) ? path.relative("dist", d) + "/" : "")); } })("dist");
const browser = await puppeteer.launch({ executablePath: "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const links = new Set(); let viol = 0;
for (const u of pages) for (const theme of ["light", "dark"]) {
  const page = await browser.newPage(); await page.evaluateOnNewDocument((t) => localStorage.setItem("sp-theme", t), theme);
  await page.goto(B + u, { waitUntil: "networkidle0" });
  (await page.$$eval("a[href], link[rel=stylesheet], script[src], img[src]", (els) => els.map((e) => e.href || e.src))).forEach((h) => links.add(h.split("#")[0]));
  // axe-core is injected via the devtools protocol, so it runs even under the checker's CSP
  const cdp = await page.createCDPSession(); await cdp.send("Runtime.evaluate", { expression: axe });
  const r = await cdp.send("Runtime.evaluate", { expression: `axe.run(document,{runOnly:["wcag2a","wcag2aa","best-practice"]}).then(r=>JSON.stringify(r.violations.map(v=>({id:v.id,n:v.nodes.length,t:v.nodes.slice(0,2).map(x=>x.target.join(" "))}))))`, awaitPromise: true, returnByValue: true });
  const v = JSON.parse(r.result.value); if (v.length) { viol += v.length; console.log(u, theme, JSON.stringify(v)); }
  await page.close();
}
await browser.close();
let bad = 0;
for (const l of links) { if (!l.startsWith("http")) continue; const internal = l.startsWith(B);
  let code; try { code = (await fetch(l, { method: internal ? "GET" : "HEAD", redirect: "follow" })).status; } catch (e) { code = String(e.cause?.code || e); }
  if (code !== 200) { bad++; console.log("LINK", code, l); } }
console.log(`pages ${pages.length}, axe violations ${viol}, links ${links.size}, non-200 ${bad}`);
