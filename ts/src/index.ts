// SkillPact verify-only implementation (TypeScript, Node). Independent of the Python reference implementation.
import { readFileSync, existsSync, lstatSync, readdirSync, statSync } from "node:fs";
import { createHash, createPublicKey, verify as edVerify } from "node:crypto";
import { join, resolve, basename } from "node:path";
import YAML from "yaml";
import { parseStrict } from "./strictjson.js";
import { checkContract, signingInputString, signatureRoles, sigKey, NAME_RE, excluded, requiredPaths, DEFAULT_EXCLUDE, PROTECTED, type Finding, type Report } from "./core.js";
export * from "./core.js";

export function signingInput(c: any, role?: string): Buffer { return Buffer.from(signingInputString(c, role), "utf8"); }

const ED_SPKI_PREFIX = Buffer.from("302a300506032b6570032100", "hex");
export function verifyEd25519(pub: string, sigB64: string, data: Buffer): boolean {
  try {
    const raw = Buffer.from(pub.split(":", 2)[1], "base64"); if (raw.length !== 32) return false;
    const key = createPublicKey({ key: Buffer.concat([ED_SPKI_PREFIX, raw]), format: "der", type: "spki" });
    return edVerify(null, data, key, Buffer.from(sigB64, "base64"));
  } catch { return false; }
}

/** {key: true|false} for ed25519; Sigstore entries are reported as "unsupported" (verify-only impl does not ship a Sigstore client). */
/** {key: true|false} for ed25519 (role-bound from 0.8; a key that signs twice is valid only if every entry is);
 *  Sigstore entries are reported as "unsupported" (verify-only impl does not ship a Sigstore client). */
export function verifySignatures(c: any): Record<string, boolean | "unsupported"> {
  const out: Record<string, boolean | "unsupported"> = {};
  for (const s of c?.integrity?.signatures ?? []) {
    if (s.type === "sigstore") { out[sigKey(s)] = "unsupported"; continue; }
    let ok = false; try { ok = verifyEd25519(s.key, s.sig, signingInput(c, s.role)); } catch { ok = false; }
    out[s.key] = (out[s.key] ?? true) === true && ok;
  }
  return out;
}

/** [kind, rel] for files in the skill directory not covered by integrity.files (spec 0.8 s11.2). */
export function unlistedFiles(dir: string, c: any, limit = 200): [string, string][] {
  const files = new Set(Object.keys(c?.integrity?.files ?? {})); const excl = [...DEFAULT_EXCLUDE, ...(c?.integrity?.exclude ?? [])];
  const must = requiredPaths(c); const out: [string, string][] = [];
  const walk = (rel: string) => {
    const names = readdirSync(join(dir, rel)).sort();
    const subdirs: string[] = [];
    for (const n of names) {
      const r = rel ? `${rel}/${n}` : n; if (r === "skill.contract.json") continue;
      const st = lstatSync(join(dir, r)); const prot = excluded(r, PROTECTED) || must.has(r);
      if (st.isSymbolicLink()) { if (prot || !excluded(r, excl)) out.push(["symlink", r]); continue; }
      if (st.isDirectory()) { subdirs.push(r); continue; }
      if (files.has(r)) continue;
      if (prot || !excluded(r, excl)) out.push(["file", r]);
    }
    if (limit && out.length >= limit) return;
    for (const s of subdirs) { walk(s); if (limit && out.length >= limit) return; }
  };
  walk(""); return limit ? out.slice(0, limit) : out;
}
function symlinkIn(dir: string, rel: string): string | null {
  let cur = "";
  for (const part of rel.split("/")) { cur = cur ? `${cur}/${part}` : part; try { if (lstatSync(join(dir, cur)).isSymbolicLink()) return cur; } catch { return null; } }
  return null;
}
const isFile = (f: string) => { try { return statSync(f).isFile(); } catch { return false; } };

const sha256 = (f: string) => createHash("sha256").update(readFileSync(f)).digest("hex");

export function validate(skillDir: string, contractPath?: string): Report {
  const dir = resolve(skillDir); const F: Finding[] = [];
  const err = (code: string, message: string, where = "") => F.push({ level: "error", code, message, where });
  const warn = (code: string, message: string, where = "") => F.push({ level: "warn", code, message, where });
  const done = (): Report => ({ ok: !F.some(f => f.level === "error"), errors: F.filter(f => f.level === "error").length, warnings: F.filter(f => f.level === "warn").length, findings: F });
  let fm: any = null; let nameDirMismatch: string | undefined;
  const sm = join(dir, "SKILL.md");
  if (!existsSync(sm)) err("SKILL_MD_MISSING", "SKILL.md not found", sm);
  else {
    const m = /^---\n([\s\S]*?)\n---\n?([\s\S]*)$/.exec(readFileSync(sm, "utf8"));
    if (!m) err("FRONTMATTER_MISSING", "SKILL.md has no YAML frontmatter", "SKILL.md");
    else {
      fm = YAML.parse(m[1]) ?? {}; const n = fm.name, d = fm.description;
      if (typeof n !== "string" || !NAME_RE.test(n) || n.length > 64) err("FM_NAME", `invalid name ${JSON.stringify(n)}`, "SKILL.md");
      else if (n !== basename(dir) && !contractPath) nameDirMismatch = `name ${n} != directory ${basename(dir)}`;
      if (typeof d !== "string" || d.length < 1 || d.length > 1024) err("FM_DESCRIPTION", "description must be 1-1024 chars", "SKILL.md");
      if ("compatibility" in fm && String(fm.compatibility).length > 500) err("FM_COMPAT", "compatibility > 500 chars", "SKILL.md");
      if ((m[2].match(/\n/g) ?? []).length > 500) warn("BODY_LONG", "SKILL.md body > 500 lines", "SKILL.md");
    }
  }
  const cp = contractPath ?? join(dir, "skill.contract.json");
  if (!existsSync(cp)) { err("CONTRACT_MISSING", "skill.contract.json not found"); return done(); }
  let c: any;
  try { c = parseStrict(new TextDecoder("utf-8", { fatal: true }).decode(readFileSync(cp))); } catch (e: any) { err("CONTRACT_JSON", String(e.message)); return done(); }
  const c2 = checkContract(c, { nameDirMismatch, fileExists: rel => existsSync(join(dir, rel)), fileSha256: rel => sha256(join(dir, rel)), skillName: fm ? fm.name : undefined,
    isFile: rel => isFile(join(dir, rel)), symlinkIn: rel => symlinkIn(dir, rel), unlisted: contractPath ? undefined : (cc: any) => unlistedFiles(dir, cc) }, F);
  if (!c2) return done(); c = c2;
  if (c.integrity) {
    if (c.integrity.signatures?.length) {
      const res = verifySignatures(c);
      if (Object.values(res).some(v => v === false)) err("SIGNATURE_INVALID", `signature check failed: ${JSON.stringify(res)}`);
      if (Object.values(res).some(v => v === "unsupported")) warn("SIGSTORE_UNVERIFIED", "Sigstore signatures are not verified by this implementation");
    }
  }
  return done();
}

/** L1 / L3-signature check without running tests (verify-only). */
export function verifyLevel(skillDir: string, trustedKeys: string[], contractPath?: string) {
  const v = validate(skillDir, contractPath); if (!v.ok) return { level: "none", validate: v };
  const c = parseStrict(readFileSync(contractPath ?? join(resolve(skillDir), "skill.contract.json"), "utf8")) as any;
  const sig = verifySignatures(c);
  const roles = signatureRoles(c);
  const coverage = !v.findings.some(f => f.code === "INTEGRITY_UNLISTED" || f.code === "INTEGRITY_PATH");
  const trustedValid = coverage && Object.entries(sig).some(([k, ok]) => ok === true && trustedKeys.includes(k) && roles[k] === "author");
  const attestations = Object.entries(sig).filter(([k, ok]) => ok === true && roles[k] !== "author").map(([k]) => ({ key: k, role: roles[k], trusted: trustedKeys.includes(k) }));
  const note = coverage ? "tests are not run by the verify-only implementation; L2/L3 need a runner" : "integrity does not cover every skill file: L3 not possible (spec 0.8 s11.2)";
  return { level: "L1-declared", signature_trusted: trustedValid, attestations, signatures: sig, note, validate: v };
}
