// Copies static artifacts from the repo's docs/ (read-only) into public/ so they ship byte-for-byte.
import fs from "node:fs"; import path from "node:path";
const REPO = process.env.SKILLPACT_REPO || path.resolve("..");
const D = path.join(REPO, "docs"), P = path.resolve("public");
const cp = (rel) => { const s = path.join(D, rel), t = path.join(P, rel); fs.mkdirSync(path.dirname(t), { recursive: true }); fs.copyFileSync(s, t); };
for (const f of fs.readdirSync(path.join(D, "schema"))) if (f.endsWith(".json")) cp(`schema/${f}`);
for (const f of fs.readdirSync(path.join(D, "badges"))) if (f.endsWith(".svg")) cp(`badges/${f}`);
cp("check/skillpact-check.js"); cp("check/example.json");
console.log("synced from", D);
