// Browser entry: everything runs locally in the page; nothing is sent anywhere.
import { checkContract, signingInputString, EFFECTS, type Finding } from "./core.js";
import { parseStrict } from "./strictjson.js";

const b64 = (s: string) => Uint8Array.from(atob(s), c => c.charCodeAt(0));

async function edVerify(pub: string, sig: string, data: string): Promise<boolean | "unsupported"> {
  try {
    const key = await crypto.subtle.importKey("raw", b64(pub.split(":", 2)[1]), { name: "Ed25519" }, false, ["verify"]);
    return await crypto.subtle.verify({ name: "Ed25519" }, key, b64(sig), new TextEncoder().encode(data));
  } catch (e: any) { return e?.name === "NotSupportedError" ? "unsupported" : false; }
}

export async function check(text: string, trustedKeys: string[]) {
  const F: Finding[] = []; let c: any;
  try { c = parseStrict(text); } catch (e: any) { return { ok: false, level: "none", findings: [{ level: "error", code: "CONTRACT_JSON", message: e.message, where: "" }], risky: [], signatures: {} }; }
  const c2 = checkContract(c, {}, F);
  const sigs: Record<string, boolean | "unsupported"> = {};
  if (c2?.integrity?.signatures?.length) {
    const data = signingInputString(c2);
    for (const s of c2.integrity.signatures) {
      if (s.type === "sigstore") { sigs[`sigstore:${s.issuer}|${s.identity}`] = "unsupported"; continue; }
      sigs[s.key] = await edVerify(s.key, s.sig, data);
    }
    if (Object.values(sigs).some(v => v === false)) F.push({ level: "error", code: "SIGNATURE_INVALID", message: "signature check failed", where: "/integrity/signatures" });
  }
  const ok = !F.some(f => f.level === "error");
  const risky: string[] = [];
  if (c2) for (const e of EFFECTS) {
    const p = c2.permissions[e]; if (p.level === "none") continue;
    if (p.level === "any") risky.push(`${e}: any (制限なし)`);
    else if (["spend", "send", "exec", "network"].includes(e)) risky.push(`${e}: ${(p.scope ?? []).join(", ")}`);
  }
  const trusted = Object.entries(sigs).some(([k, v]) => v === true && trustedKeys.includes(k));
  const level = !ok ? "none" : trusted ? "L1 + 信頼済み署名（L3 にはテスト実行が必要）" : "L1-declared";
  return { ok, level, findings: F, risky, signatures: sigs, contract_version: c?.contract_version, skill: c?.skill };
}
(globalThis as any).SkillPact = { check };
