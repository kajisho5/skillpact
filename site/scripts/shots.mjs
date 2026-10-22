import puppeteer from "puppeteer-core";
const B = "http://localhost:4173/skillpact/";
const routes = (process.env.ROUTES || "|why|spec|schema|check|badges|guides|ja|ja/check|ja/why").split("|");
const browser = await puppeteer.launch({ executablePath: "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const errors = [];
for (const r of routes) for (const w of [1280, 390]) for (const theme of ["light", "dark"]) {
  const page = await browser.newPage();
  page.on("console", (m) => { if (m.type() === "error") errors.push(`${r} ${m.text()}`); });
  page.on("pageerror", (e) => errors.push(`${r} ${e.message}`));
  await page.setViewport({ width: w, height: w > 500 ? 900 : 844, deviceScaleFactor: w > 500 ? 1 : 2 });
  await page.evaluateOnNewDocument((t) => localStorage.setItem("sp-theme", t), theme);
  await page.goto(B + (r ? r + "/" : ""), { waitUntil: "networkidle0" });
  if (r.endsWith("check")) { await page.click("#ex"); await new Promise((s) => setTimeout(s, 300)); await page.click("#go"); await new Promise((s) => setTimeout(s, 800)); }
  const name = (r || "home").replace("/", "_");
  await page.screenshot({ path: `/workspace/shots/react_${name}_${w}_${theme}.png`, fullPage: process.env.FULL !== "0" });
  await page.close();
}
await browser.close();
console.log(errors.length ? errors.map((e) => e.slice(0, 200)).join("\n") : "no console errors");
