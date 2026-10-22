// JSON.parse plus duplicate-key detection (spec 0.5 s18.5). Throws on duplicates.
export function parseStrict(text: string): unknown {
  let i = 0;
  const ws = () => { while (i < text.length && " \t\n\r".includes(text[i])) i++; };
  const str = (): string => { const start = i; i++; while (text[i] !== '"') { if (text[i] === "\\") i++; i++; if (i >= text.length) throw new Error("bad string"); } i++; return JSON.parse(text.slice(start, i)); };
  const val = (): void => {
    ws(); const c = text[i];
    if (c === "{") { i++; ws(); const seen = new Set<string>(); if (text[i] === "}") { i++; return; }
      for (;;) { ws(); const k = str(); if (seen.has(k)) throw new Error(`duplicate key ${JSON.stringify(k)}`); seen.add(k); ws(); i++; val(); ws(); if (text[i] === ",") { i++; continue; } i++; return; } }
    if (c === "[") { i++; ws(); if (text[i] === "]") { i++; return; } for (;;) { val(); ws(); if (text[i] === ",") { i++; continue; } i++; return; } }
    if (c === '"') { str(); return; }
    while (i < text.length && !",]} \t\n\r".includes(text[i])) i++;
  };
  const out = JSON.parse(text); val(); return out;
}
