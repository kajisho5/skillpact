// Platform-independent core (Node and browser).
import Ajv2020Mod from "ajv/dist/2020.js";
import { jcs, legacySorted } from "./jcs.js";
import SCHEMA_JSON from "./schema.json" with { type: "json" };

const Ajv2020: any = (Ajv2020Mod as any).default ?? Ajv2020Mod;
export const SCHEMA: any = SCHEMA_JSON;
export const EFFECTS = ["read", "write", "network", "exec", "spend", "send"] as const;
export const KNOWN_VERSIONS = ["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7"];
export const SCOPE_TOKENS: Record<string, string[]> = { network: ["@local"] };
export const vt = (v: string) => String(v).split(".").map(Number);
export const PATH_VARS = new Set(["$INPUT", "$INPUT_DIR", "$OUTPUT", "$WORKDIR", "$SKILL_DIR", "$TMPDIR"]);
export const NAME_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;

export type Finding = { level: "error" | "warn"; code: string; message: string; where: string };
export type Report = { ok: boolean; errors: number; warnings: number; findings: Finding[] };

export function versionStatus(v: unknown): "ok" | "unknown_major" | "unknown_minor" {
  if (typeof v !== "string" || !/^\d+\.\d+$/.test(v)) return "unknown_major";
  if (KNOWN_VERSIONS.includes(v)) return "ok";
  const major = Number(v.split(".")[0]); const known = new Set(KNOWN_VERSIONS.map(k => Number(k.split(".")[0])));
  return major === 0 || !known.has(major) ? "unknown_major" : "unknown_minor";
}

export function canonicalizationFor(c: any): "jcs" | "legacy-sorted" {
  const [a, b] = String(c?.contract_version ?? "0.1").split(".").map(Number);
  return a > 0 || b >= 4 ? "jcs" : "legacy-sorted";
}

export function signingInputString(c: any): string {
  const c2 = JSON.parse(JSON.stringify(c)); if (c2.integrity) delete c2.integrity.signatures;
  return canonicalizationFor(c) === "jcs" ? jcs(c2) : legacySorted(c2);
}

export function fnmatch(s: string, p: string): boolean {
  let re = "";
  for (let i = 0; i < p.length; i++) {
    const ch = p[i];
    if (ch === "*") re += ".*"; else if (ch === "?") re += ".";
    else if (ch === "[") { const j = p.indexOf("]", i + 1); if (j < 0) re += "\\["; else { let cls = p.slice(i + 1, j); if (cls.startsWith("!")) cls = "^" + cls.slice(1); re += "[" + cls.replace(/\\/g, "\\\\") + "]"; i = j; } }
    else re += ch.replace(/[.+^${}()|\\\]]/g, "\\$&");
  }
  return new RegExp("^" + re + "$", "s").test(s);
}
export const covered = (scope: string[], pats: string[]) => scope.length > 0 && scope.every(s => pats.some(p => fnmatch(s, p)));
const makeAjv = (o: any) => new Ajv2020(o);


export type Env = { nameDirMismatch?: string; fileExists?: (rel: string) => boolean; fileSha256?: (rel: string) => string; skillName?: string | null };
/** Contract-level checks shared by Node and browser. Signatures are checked by the caller (sync in Node, WebCrypto in browser). */
export function checkContract(cIn: any, env: Env, F: Finding[]): any | null {
  const err = (code: string, message: string, where = "") => F.push({ level: "error", code, message, where });
  const warn = (code: string, message: string, where = "") => F.push({ level: "warn", code, message, where });
  let c = cIn; const dirExists = env.fileExists ?? (() => true);
  const fm = env.skillName === undefined ? null : { name: env.skillName };
  const vs = versionStatus(c?.contract_version);
  if (vs === "unknown_major") { err("CONTRACT_VERSION_UNSUPPORTED", `contract_version ${JSON.stringify(c?.contract_version)} is not supported`, "/contract_version"); return null; }
  if (vs === "unknown_minor") { warn("CONTRACT_VERSION_NEWER", "contract_version newer than this validator", "/contract_version"); c = { ...c, contract_version: KNOWN_VERSIONS.at(-1) }; }
  const ajv = makeAjv({ allErrors: true, strict: false, validateFormats: false });
  const vfn = ajv.compile(SCHEMA);
  if (!vfn(c)) { for (const e of vfn.errors ?? []) err("SCHEMA", e.message ?? "schema error", e.instancePath); return null; }
  if (env.nameDirMismatch) { const [a, b] = vt(c.contract_version); (a > 0 || b >= 7 ? err : warn)("FM_NAME_DIR", env.nameDirMismatch, "SKILL.md"); }
  if (fm && fm.name !== c.skill.name) err("NAME_MISMATCH", "contract skill.name != SKILL.md name");
  const perms = c.permissions;
  for (const eff of ["spend", "send"]) if (perms[eff].level === "any") warn("HIGH_RISK", `${eff}: level any`, `/permissions/${eff}`);
  for (const eff of EFFECTS) {
    if (perms[eff].level === "scoped" && !(perms[eff].scope?.length)) err("SCOPE_EMPTY", `permissions.${eff}: scoped needs a scope`, `/permissions/${eff}`);
    for (const sc of perms[eff].scope ?? []) if (sc.startsWith("@") && !(SCOPE_TOKENS[eff] ?? []).includes(sc)) warn("UNKNOWN_SCOPE_TOKEN", `scope token ${sc} is not defined`, `/permissions/${eff}`);
    for (const sc of perms[eff].scope ?? []) for (const v of sc.match(/\$[A-Z_]+/g) ?? []) if (!PATH_VARS.has(v)) warn("UNKNOWN_VARIABLE", `undefined variable ${v}`, `/permissions/${eff}`);
  }
  const req = c.requirements ?? {};
  const reqNames = new Set([...(req.binaries ?? []), ...(req.runtimes ?? [])].map((b: any) => b.name));
  const featureKinds = new Set((req.binaries ?? []).flatMap((b: any) => Object.keys(b.features_check ?? {})));
  const ids = new Set<string>();
  c.capabilities.forEach((cap: any, i: number) => {
    const w = `/capabilities/${i}`;
    if (ids.has(cap.id)) err("DUP_CAPABILITY", `duplicate id ${cap.id}`, w); ids.add(cap.id);
    for (const eff of cap.effects) if (perms[eff].level === "none") err("UNDECLARED_EFFECT", `${cap.id} has effect ${eff} but permissions.${eff} is none`, w);
    for (const ce of cap.conditional_effects ?? []) if (perms[ce.effect].level === "none") err("UNDECLARED_EFFECT", `${cap.id}: conditional effect ${ce.effect}`, w);
    if (cap.destructive && !cap.effects.some((e: string) => ["write", "send", "spend"].includes(e))) warn("DESTRUCTIVE_NO_EFFECT", `${cap.id} destructive without write/send/spend`, w);
    for (const k of ["inputs", "outputs"]) if (cap[k] !== undefined) { try { new Ajv2020({ strict: false }).compile(cap[k]); } catch (e: any) { err("BAD_SUBSCHEMA", `${cap.id}.${k}: ${e.message}`, w); } }
    for (const q of cap.requires ?? []) if (!reqNames.has(q)) err("UNKNOWN_REQUIREMENT", `${cap.id} requires ${q}`, w);
    for (const tok of cap.entry?.cli ?? []) if (typeof tok === "string" && tok.startsWith("$SKILL_DIR/") && !dirExists(tok.slice(11))) err("ENTRY_MISSING", `${cap.id}: ${tok} does not exist`, w);
    for (const [eff, sc] of Object.entries(cap.effect_scopes ?? {})) if (perms[eff].level === "scoped" && !covered(sc as string[], perms[eff].scope ?? [])) err("SCOPE_WIDENED", `${cap.id}: effect_scopes.${eff} wider than permissions`, w);
    for (const f of cap.requires_features ?? []) if (!featureKinds.has(f.split(":")[0])) err("UNKNOWN_FEATURE_KIND", `${cap.id}: ${f}`, w);
    if ((c.kind ?? "tool") === "tool" && !cap.entry?.cli && !cap.entry?.mcp_tool && cap.effects.length) warn("NO_ENTRY", `${cap.id} has effects but no entry`, w);
  });
  const used = new Set(c.capabilities.flatMap((cap: any) => [...cap.effects, ...(cap.conditional_effects ?? []).map((x: any) => x.effect)]));
  for (const eff of EFFECTS) if (perms[eff].level !== "none" && !used.has(eff)) warn("UNUSED_PERMISSION", `permissions.${eff} unused`, `/permissions/${eff}`);
  const cases = c.tests?.cases ?? [];
  for (const t of cases) if (t.capability && !ids.has(t.capability)) err("TEST_UNKNOWN_CAPABILITY", `test ${t.id} refers to ${t.capability}`);
  if (!cases.length && (c.kind ?? "tool") === "tool") warn("NO_TESTS", "no conformance tests declared");
  if (c.integrity) {
    for (const [rel, h] of Object.entries(c.integrity.files ?? {})) {
      if (!env.fileSha256) continue;
      if (!dirExists(rel)) err("INTEGRITY_MISSING", `${rel} missing`); else if (env.fileSha256(rel) !== h) err("INTEGRITY_MISMATCH", `${rel} hash differs`);
    }
  }
  return c;
}


/** key-or-identity -> role (author by default). Staging Sigstore identities get a distinct prefix. */
export function signatureRoles(c: any): Record<string, string> {
  const out: Record<string, string> = {};
  for (const s of c?.integrity?.signatures ?? []) out[sigKey(s)] = s.role ?? "author";
  return out;
}
export const sigKey = (s: any) => s.type === "sigstore" ? `${s.instance === "staging" ? "sigstore-staging" : "sigstore"}:${s.issuer}|${s.identity}` : s.key;
