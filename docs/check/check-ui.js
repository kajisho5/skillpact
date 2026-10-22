(function () {
  const BASE = new URL(".", document.currentScript.src);
  const JA = document.documentElement.lang === "ja";
  const T = JA
    ? { result: "結果", errors: "エラー", warnings: "警告", risky: "注意が要る副作用", sigs: "署名", valid: "有効", invalid: "無効", na: "ブラウザでは未確認", trusted: "（信頼済み）", role: "役割" }
    : { result: "Result", errors: "Errors", warnings: "Warnings", risky: "Effects to review", sigs: "Signatures", valid: "valid", invalid: "invalid", na: "not checked in browser", trusted: " (trusted)", role: "role" };
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  $("go").onclick = async () => {
    const keys = $("k").value.split(/\s+/).filter(Boolean);
    const r = await window.SkillPact.check($("c").value, keys);
    const errs = r.findings.filter((f) => f.level === "error"), warns = r.findings.filter((f) => f.level === "warn");
    let h = `<div class="box"><b>${T.result}:</b> <span class="${r.ok ? "ok" : "err"}">${esc(r.level)}</span>`;
    if (r.skill) h += ` · ${esc(r.skill.name)} ${esc(r.skill.version)} · contract ${esc(r.contract_version)}`;
    h += "</div>";
    if (errs.length) h += `<div class="box"><b>${T.errors}</b><ul>${errs.map((f) => `<li class="err"><code>${esc(f.code)}</code> ${esc(f.message)} <small>${esc(f.where)}</small></li>`).join("")}</ul></div>`;
    if (warns.length) h += `<div class="box"><b>${T.warnings}</b><ul>${warns.map((f) => `<li class="warn"><code>${esc(f.code)}</code> ${esc(f.message)}</li>`).join("")}</ul></div>`;
    if (r.risky.length) h += `<div class="box"><b>${T.risky}</b><ul>${r.risky.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
    const sig = Object.entries(r.signatures);
    if (sig.length) h += `<div class="box"><b>${T.sigs}</b><ul>${sig.map(([k, v]) => `<li><code>${esc(k)}</code> · ${T.role}: ${esc((r.roles || {})[k] || "author")} · ${v === true ? `<span class="ok">${T.valid}</span>` : v === false ? `<span class="err">${T.invalid}</span>` : T.na}${keys.includes(k) ? T.trusted : ""}</li>`).join("")}</ul></div>`;
    $("out").innerHTML = h;
  };
  $("ex").onclick = async () => { $("c").value = await fetch(new URL("example.json", BASE)).then((x) => x.text()); $("k").value = "ed25519:moqKymSKFxCPXkaxDtETg/Qd8GvRwg8ckWAWIRQJXSQ="; };
})();
