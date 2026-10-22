// Platform-independent core (Node and browser).
import Ajv2020Mod from "ajv/dist/2020.js";
import { jcs, legacySorted } from "./jcs.js";
import SCHEMA_JSON from "./schema.json" with { type: "json" };

const Ajv2020: any = (Ajv2020Mod as any).default ?? Ajv2020Mod;
export const SCHEMA: any = SCHEMA_JSON;
export const EFFECTS = ["read", "write", "network", "exec", "spend", "send"] as const;
export const KNOWN_VERSIONS = ["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8"];
export const MAX_PATH_LEN = 1024, MAX_PATH_SEGMENTS = 32, MAX_FILES = 10000;
export const DEFAULT_EXCLUDE = [".git/**", "**/__pycache__/**", "**/*.pyc", "**/.DS_Store"];
export const PROTECTED = ["SKILL.md", "**/SKILL.md", "**/CLAUDE.md", "**/AGENTS.md", "**/GEMINI.md", "**/.mcp.json", ".claude-plugin/**",
  ".claude/**", ".cursor/**", ".codex/**", ".gemini/**", ".agents/**", "hooks/**", "package.json", "pyproject.toml"];
export const PATH_EFFECTS = ["read", "write"];
export const SCOPE_TOKENS: Record<string, string[]> = { network: ["@local"] };
export const vt = (v: string) => String(v).split(".").map(Number);
export const isV08 = (c: any) => { const [a, b] = vt(c?.contract_version ?? "0.1"); return a > 0 || b >= 8; };
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

/** Signing input (spec 0.8 s11.1). >= 0.8: JCS({"contract": C, "role": R}); 0.4-0.7: JCS(C); 0.1-0.3: legacy sorted. */
export function signingInputString(c: any, role?: string): string {
  const c2 = JSON.parse(JSON.stringify(c)); if (c2.integrity) delete c2.integrity.signatures;
  if (isV08(c)) return jcs({ contract: c2, role: role ?? "author" });
  return canonicalizationFor(c) === "jcs" ? jcs(c2) : legacySorted(c2);
}

// ---- normative globs (spec 0.8 s6.1) ----
const esc = (ch: string) => ch.replace(/[.*+?^${}()|[\]\\\/]/g, "\\$&");
function globRe(p: string): string {
  const parts = p.split("/"); let out = "", glue = false;
  parts.forEach((seg, i) => {
    const sep = i === 0 || glue ? "" : "/"; glue = false;
    if (seg === "**") { if (i === parts.length - 1) out += i ? "(?:/[^\\n]*)?" : "[^\\n]*"; else { out += sep + "(?:[^/]+/)*"; glue = true; } return; }
    out += sep + [...seg.replace(/\*+/g, "*")].map(ch => ch === "*" ? "[^/]*" : ch === "?" ? "[^/]" : esc(ch)).join("");
  });
  return out;
}
function hostMatch(h0: string, p0: string): boolean {
  const h = h0.toLowerCase().replace(/\.+$/, ""), p = p0.toLowerCase().replace(/\.+$/, "");
  if (p === "*") return true;
  const hl = h.split("."), pl = p.split(".");
  const lab = (s: string, q: string) => new RegExp("^(?:" + [...q].map(ch => ch === "*" ? "[^.]*" : ch === "?" ? "[^\\n]" : esc(ch)).join("") + ")$", "u").test(s);
  if ((pl[0] === "*" || pl[0] === "**") && pl.length > 1) {
    const rest = pl.slice(1), need = rest.length;
    if (hl.length < need + (pl[0] === "*" ? 1 : 0)) return false;
    const tail = hl.slice(-need); return rest.every((q, k) => lab(tail[k], q));
  }
  return hl.length === pl.length && pl.every((q, k) => lab(hl[k], q));
}
export type GlobKind = "path" | "host" | "generic";
export function globMatch(s: string, p: string, kind: GlobKind = "path"): boolean {
  if (kind === "host") return hostMatch(s, p);
  return new RegExp("^(?:" + globRe(p) + ")$", "u").test(s);
}
/** @deprecated name kept for compatibility: now the normative SkillPact glob, not fnmatch. */
export const fnmatch = (s: string, p: string) => globMatch(s, p, "generic");
export const effectKind = (eff: string): GlobKind => PATH_EFFECTS.includes(eff) ? "path" : eff === "network" ? "host" : "generic";
const asLiteral = (s: string, kind: GlobKind) => kind === "host" ? s : s.split("/").map(seg => seg === "**" ? "\x00/\x00" : seg.replace(/\*/g, "\x01*\x01")).join("/");
export function scopeTraversal(sc: string): boolean {
  if (sc.includes("\\")) return true;
  let segs = sc.split("/"); if (sc.startsWith("/")) segs = segs.slice(1);
  return segs.some(s => s === "" || s === "." || s === "..");
}
export const covered = (scope: string[], pats: string[], kind: GlobKind = "generic") =>
  scope.length > 0 && !(kind === "path" && scope.some(scopeTraversal)) && scope.every(s => pats.some(p => s === p || globMatch(asLiteral(s, kind), p, kind)));
const utf8len = (s: string) => new TextEncoder().encode(s).length;
export function integrityPathProblem(rel: string): string | null {
  if (typeof rel !== "string" || !rel) return "empty path";
  if (utf8len(rel) > MAX_PATH_LEN) return `longer than ${MAX_PATH_LEN} bytes`;
  if (rel.startsWith("/") || /^[A-Za-z]:/.test(rel)) return "absolute path";
  if (rel.includes("\\") || /[\x00-\x1f]/.test(rel)) return "backslash or control character";
  const segs = rel.split("/");
  if (segs.length > MAX_PATH_SEGMENTS) return `more than ${MAX_PATH_SEGMENTS} segments`;
  if (segs.some(s => s === "" || s === "." || s === "..")) return "'.', '..' or empty segment";
  return null;
}
export const excluded = (rel: string, pats: string[]) => pats.some(p => globMatch(rel, p));
/** Files that integrity must list whatever integrity.exclude says ($SKILL_DIR/... in entries, tests and setup). */
export function requiredPaths(c: any): Set<string> {
  const toks: unknown[] = [...(c.capabilities ?? []).flatMap((cap: any) => cap.entry?.cli ?? []),
    ...(c.tests?.cases ?? []).flatMap((t: any) => t.run ?? []), ...(c.tests?.setup ?? []).flat()];
  const out = new Set<string>();
  for (const t of toks) for (const m of String(t).matchAll(/\$SKILL_DIR\/([^\s'"]+)/g)) out.add(m[1]);
  return out;
}
export function draftMarkers(c: any): string[] {
  const out: string[] = [];
  for (const k of ["init", "import"]) if (c?.x?.[k]?.uncertain?.length) out.push(`x.${k}.uncertain`);
  const walk = (v: any, path: string) => {
    if (Array.isArray(v)) v.forEach((i, n) => walk(i, `${path}/${n}`));
    else if (v && typeof v === "object") for (const [k, i] of Object.entries(v)) walk(i, `${path}/${k}`);
    else if (typeof v === "string" && v.includes("TODO(")) out.push(path || "/");
  };
  const top: any = {}; for (const [k, v] of Object.entries(c)) if (k !== "x") top[k] = v; walk(top, "");
  return out;
}
export function duplicateSigners(c: any): string[] {
  const seen = new Set<string>(), dup: string[] = [];
  for (const s of c?.integrity?.signatures ?? []) { const k = sigKey(s); if (seen.has(k) && !dup.includes(k)) dup.push(k); seen.add(k); }
  return dup;
}
const makeAjv = (o: any) => new Ajv2020(o);


export type Env = { nameDirMismatch?: string; fileExists?: (rel: string) => boolean; fileSha256?: (rel: string) => string; skillName?: string | null;
  isFile?: (rel: string) => boolean; symlinkIn?: (rel: string) => string | null; unlisted?: (c: any) => [string, string][] };
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
    if (PATH_EFFECTS.includes(eff)) for (const sc of perms[eff].scope ?? []) if (scopeTraversal(sc)) err("SCOPE_TRAVERSAL", `permissions.${eff}.scope ${JSON.stringify(sc)} contains '.', '..', an empty segment or a backslash`, `/permissions/${eff}`);
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
    for (const [eff, sc] of Object.entries(cap.effect_scopes ?? {})) {
      if (PATH_EFFECTS.includes(eff)) for (const s of sc as string[]) if (scopeTraversal(s)) err("SCOPE_TRAVERSAL", `${cap.id}: effect_scopes.${eff} ${JSON.stringify(s)} escapes its base`, w);
      if (perms[eff].level === "scoped" && !covered(sc as string[], perms[eff].scope ?? [], effectKind(eff))) err("SCOPE_WIDENED", `${cap.id}: effect_scopes.${eff} wider than permissions`, w);
    }
    for (const f of cap.requires_features ?? []) if (!featureKinds.has(f.split(":")[0])) err("UNKNOWN_FEATURE_KIND", `${cap.id}: ${f}`, w);
    if ((c.kind ?? "tool") === "tool" && !cap.entry?.cli && !cap.entry?.mcp_tool && cap.effects.length) warn("NO_ENTRY", `${cap.id} has effects but no entry`, w);
  });
  const used = new Set(c.capabilities.flatMap((cap: any) => [...cap.effects, ...(cap.conditional_effects ?? []).map((x: any) => x.effect)]));
  for (const eff of EFFECTS) if (perms[eff].level !== "none" && !used.has(eff)) warn("UNUSED_PERMISSION", `permissions.${eff} unused`, `/permissions/${eff}`);
  const cases = c.tests?.cases ?? []; const v08 = isV08(c);
  for (const t of cases) {
    if (t.capability && !ids.has(t.capability)) err("TEST_UNKNOWN_CAPABILITY", `test ${t.id} refers to ${t.capability}`);
    if (t.network && perms.network.level === "none") (v08 ? err : warn)("TEST_UNDECLARED_NETWORK", `test ${t.id} has network: true but permissions.network is none`);
  }
  const drafts = draftMarkers(c);
  if (drafts.length) (v08 ? err : warn)("UNCONFIRMED_DRAFT", `unconfirmed draft content: ${drafts.slice(0, 5).join(", ")}`);
  if (!cases.length && (c.kind ?? "tool") === "tool") warn("NO_TESTS", "no conformance tests declared");
  const tested = new Set(cases.map((t: any) => t.capability)); const untested = [...ids].filter(i => !tested.has(i));
  if (cases.length && untested.length) warn("UNTESTED_CAPABILITY", `${untested.length} capabilities have no test`);
  if (c.integrity) {
    const files = c.integrity.files ?? {};
    if (v08 && !("SKILL.md" in files)) err("INTEGRITY_EMPTY", "integrity.files must list SKILL.md and every other skill file (spec 0.8 s11.2)", "/integrity/files");
    if (Object.keys(files).length > MAX_FILES) err("INTEGRITY_PATH", `integrity.files has too many entries (max ${MAX_FILES})`, "/integrity/files");
    for (const [rel, h] of Object.entries(files)) {
      const bad = integrityPathProblem(rel); if (bad) { err("INTEGRITY_PATH", `${JSON.stringify(rel)}: ${bad}`, "/integrity/files"); continue; }
      if (!env.fileSha256) continue;
      const link = env.symlinkIn?.(rel);
      if (link) err("INTEGRITY_PATH", `${JSON.stringify(rel)}: ${link} is a symbolic link`, "/integrity/files");
      else if (!(env.isFile ?? dirExists)(rel)) err("INTEGRITY_MISSING", `${rel} missing`); else if (env.fileSha256(rel) !== h) err("INTEGRITY_MISMATCH", `${rel} hash differs`);
    }
    if (env.unlisted) for (const [kind, rel] of env.unlisted(c)) {
      if (kind === "symlink") (v08 ? err : warn)("INTEGRITY_PATH", `${JSON.stringify(rel)} is a symbolic link (not allowed in a skill directory)`);
      else (v08 ? err : warn)("INTEGRITY_UNLISTED", `${rel} is not covered by integrity.files`);
    }
    for (const k of duplicateSigners(c)) err("DUP_SIGNATURE", `more than one signature by ${k}`, "/integrity/signatures");
  }
  return c;
}


/** key-or-identity -> role (author by default). Staging Sigstore identities get a distinct prefix. */
export function signatureRoles(c: any): Record<string, string> {
  // note: with duplicate signers (DUP_SIGNATURE) the last entry's role is reported
  const out: Record<string, string> = {};
  for (const s of c?.integrity?.signatures ?? []) out[sigKey(s)] = s.role ?? "author";
  return out;
}
export const sigKey = (s: any) => s.type === "sigstore" ? `${s.instance === "staging" ? "sigstore-staging" : "sigstore"}:${s.issuer}|${s.identity}` : s.key;
