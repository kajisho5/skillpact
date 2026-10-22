// RFC 8785 JSON Canonicalization Scheme. ECMAScript number/string serialization is exactly what JCS specifies.
export function jcs(v: unknown): string {
  if (v === null || typeof v === "boolean") return JSON.stringify(v);
  if (typeof v === "number") { if (!Number.isFinite(v)) throw new Error("non-finite number"); return JSON.stringify(v); }
  if (typeof v === "string") return JSON.stringify(v);
  if (Array.isArray(v)) return "[" + v.map(jcs).join(",") + "]";
  if (typeof v === "object") {
    const o = v as Record<string, unknown>;
    const keys = Object.keys(o).sort(); // default sort = UTF-16 code units, as JCS requires
    return "{" + keys.filter(k => o[k] !== undefined).map(k => JSON.stringify(k) + ":" + jcs(o[k])).join(",") + "}";
  }
  throw new Error("unsupported value");
}

// 0.1-0.3 legacy form: keys sorted by code point, separators , : and no ASCII escaping.
// Numbers: integers within +-(2^53-1) only (spec 0.8 s11.1); anything else cannot be reproduced and is refused.
export function legacySorted(v: unknown): string {
  if (typeof v === "number" && (!Number.isInteger(v) || Math.abs(v) > 9007199254740991)) throw new Error("legacy (0.1-0.3) canonicalization supports integers only; migrate and re-sign");
  if (Array.isArray(v)) return "[" + v.map(legacySorted).join(",") + "]";
  if (v && typeof v === "object") {
    const o = v as Record<string, unknown>;
    const keys = Object.keys(o).sort((a, b) => { const A = [...a], B = [...b];
      for (let i = 0; i < Math.min(A.length, B.length); i++) { const d = A[i].codePointAt(0)! - B[i].codePointAt(0)!; if (d) return d; } return A.length - B.length; });
    return "{" + keys.map(k => JSON.stringify(k) + ":" + legacySorted(o[k])).join(",") + "}";
  }
  return JSON.stringify(v);
}
