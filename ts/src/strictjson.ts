// Strict I-JSON parse (spec 0.8 s4.1, RFC 7493): no duplicate keys, integers within +-(2^53-1), finite numbers,
// no lone surrogates, nesting depth <= 64. Throws Error on any violation.
export const SAFE_INT = 9007199254740991;
export const MAX_DEPTH = 64;
const LONE = /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/;
export function parseStrict(text: string): unknown {
  let i = 0;
  const ws = () => { while (i < text.length && " \t\n\r".includes(text[i])) i++; };
  const str = (): string => {
    const start = i; i++;
    while (text[i] !== '"') { if (text[i] === "\\") i++; i++; if (i >= text.length) throw new Error("bad string"); }
    i++; const s = JSON.parse(text.slice(start, i)) as string;
    if (LONE.test(s)) throw new Error("string contains a lone surrogate"); return s;
  };
  const val = (depth: number): void => {
    ws(); const c = text[i];
    if (c === "{" || c === "[") {
      if (depth > MAX_DEPTH) throw new Error(`nesting deeper than ${MAX_DEPTH}`);
      if (c === "{") { i++; ws(); const seen = new Set<string>(); if (text[i] === "}") { i++; return; }
        for (;;) { ws(); const k = str(); if (seen.has(k)) throw new Error(`duplicate key ${JSON.stringify(k)}`); seen.add(k); ws(); i++; val(depth + 1); ws(); if (text[i] === ",") { i++; continue; } i++; return; } }
      i++; ws(); if (text[i] === "]") { i++; return; } for (;;) { val(depth + 1); ws(); if (text[i] === ",") { i++; continue; } i++; return; }
    }
    if (c === '"') { str(); return; }
    const start = i; while (i < text.length && !",]} \t\n\r".includes(text[i])) i++;
    const tok = text.slice(start, i);
    if (/^-?\d+$/.test(tok)) { const b = BigInt(tok); if (b > BigInt(SAFE_INT) || b < -BigInt(SAFE_INT)) throw new Error(`integer ${tok.slice(0, 24)} outside +-(2^53-1)`); }
    else if (/^-?\d/.test(tok) && !Number.isFinite(Number(tok))) throw new Error(`number ${tok.slice(0, 24)} is not finite`);
  };
  const out = JSON.parse(text); val(1); return out;
}
