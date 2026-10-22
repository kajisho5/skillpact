#!/usr/bin/env node
import { validate, verifyLevel } from "./index.js";
import { spawnSync } from "node:child_process";
const [cmd, dir, ...rest] = process.argv.slice(2);
const opt = (n: string) => { const i = rest.indexOf(n); return i >= 0 ? rest[i + 1] : undefined; };
const multi = (n: string) => rest.flatMap((a, i) => (rest[i - 1] === n ? [a] : []));
if (cmd === "validate" && dir) { const r = validate(dir, opt("--contract")); console.log(JSON.stringify(r, null, 2)); process.exit(r.ok ? 0 : 1); }
else if (cmd === "verify" && dir) { const r = verifyLevel(dir, multi("--trusted-key"), opt("--contract")); console.log(JSON.stringify(r, null, 2)); process.exit(r.level === "none" ? 1 : 0); }
else if (cmd && !["-h", "--help", "help"].includes(cmd)) {
  // Everything else (init, test, sign, policy-compile, ...) is handled by the Python reference CLI.
  const args = process.argv.slice(2);
  for (const [bin, pre] of [["pipx", ["run", "skillpact"]], ["uvx", ["skillpact"]], ["skillpact-py", []]] as const) {
    const r = spawnSync(bin, [...pre, ...args], { stdio: "inherit" });
    if (!r.error) process.exit(r.status ?? 1);
  }
  console.error(`'${cmd}' needs the Python CLI: install pipx (or uv) and retry, or run: pipx run skillpact ${args.join(" ")}`); process.exit(2);
}
else { console.error("usage: skillpact validate|verify <skill_dir> [--contract F] [--trusted-key K ...]\n       other commands (init, test, conformance, sign, policy-compile, ...) are delegated to `pipx run skillpact`"); process.exit(2); }
