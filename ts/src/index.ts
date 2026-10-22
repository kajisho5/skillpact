// SkillPact verify-only implementation (TypeScript, Node). Independent of the Python reference implementation.
import { readFileSync, existsSync } from "node:fs";
import { createHash, createPublicKey, verify as edVerify } from "node:crypto";
import { join, resolve, basename } from "node:path";
import YAML from "yaml";
import { parseStrict } from "./strictjson.js";
import { checkContract, signingInputString, signatureRoles, sigKey, NAME_RE, type Finding, type Report } from "./core.js";
export * from "./core.js";

export function signingInput(c: any): Buffer { return Buffer.from(signingInputString(c), "utf8"); }

const ED_SPKI_PREFIX = Buffer.from("302a300506032b6570032100", "hex");
export function verifyEd25519(pub: string, sigB64: string, data: Buffer): boolean {
  try {
    const raw = Buffer.from(pub.split(":", 2)[1], "base64"); if (raw.length !== 32) return false;
    const key = createPublicKey({ key: Buffer.concat([ED_SPKI_PREFIX, raw]), format: "der", type: "spki" });
    return edVerify(null, data, key, Buffer.from(sigB64, "base64"));
  } catch { return false; }
}

/** {key: true|false} for ed25519; Sigstore entries are reported as "unsupported" (verify-only impl does not ship a Sigstore client). */
export function verifySignatures(c: any): Record<string, boolean | "unsupported"> {
  const out: Record<string, boolean | "unsupported"> = {}; const data = signingInput(c);
  for (const s of c?.integrity?.signatures ?? []) {
    if (s.type === "sigstore") { out[sigKey(s)] = "unsupported"; continue; }
    out[s.key] = verifyEd25519(s.key, s.sig, data);
  }
  return out;
}

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
  try { c = parseStrict(readFileSync(cp, "utf8")); } catch (e: any) { err("CONTRACT_JSON", String(e.message)); return done(); }
  const c2 = checkContract(c, { nameDirMismatch, fileExists: rel => existsSync(join(dir, rel)), fileSha256: rel => sha256(join(dir, rel)), skillName: fm ? fm.name : undefined }, F);
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
  const c = JSON.parse(readFileSync(contractPath ?? join(resolve(skillDir), "skill.contract.json"), "utf8"));
  const sig = verifySignatures(c);
  const roles = signatureRoles(c);
  const trustedValid = Object.entries(sig).some(([k, ok]) => ok === true && trustedKeys.includes(k) && roles[k] === "author");
  const attestations = Object.entries(sig).filter(([k, ok]) => ok === true && roles[k] !== "author").map(([k]) => ({ key: k, role: roles[k], trusted: trustedKeys.includes(k) }));
  return { level: "L1-declared", signature_trusted: trustedValid, attestations, signatures: sig, note: "tests are not run by the verify-only implementation; L2/L3 need a runner", validate: v };
}

