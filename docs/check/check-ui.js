(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  $("go").onclick = async () => {
    const keys = $("k").value.split(/\s+/).filter(Boolean);
    const r = await window.SkillPact.check($("c").value, keys);
    const errs = r.findings.filter((f) => f.level === "error"), warns = r.findings.filter((f) => f.level === "warn");
    let h = `<div class="box"><b>Result:</b> <span class="${r.ok ? "ok" : "err"}">${esc(r.level)}</span>`;
    if (r.skill) h += ` · ${esc(r.skill.name)} ${esc(r.skill.version)} · contract ${esc(r.contract_version)}`;
    h += "</div>";
    if (errs.length) h += `<div class="box"><b>Errors</b><ul>${errs.map((f) => `<li class="err"><code>${esc(f.code)}</code> ${esc(f.message)} <small>${esc(f.where)}</small></li>`).join("")}</ul></div>`;
    if (warns.length) h += `<div class="box"><b>Warnings</b><ul>${warns.map((f) => `<li class="warn"><code>${esc(f.code)}</code> ${esc(f.message)}</li>`).join("")}</ul></div>`;
    if (r.risky.length) h += `<div class="box"><b>Effects to review</b><ul>${r.risky.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
    const sig = Object.entries(r.signatures);
    if (sig.length) h += `<div class="box"><b>Signatures</b><ul>${sig.map(([k, v]) => `<li><code>${esc(k)}</code>: ${v === true ? '<span class="ok">valid</span>' : v === false ? '<span class="err">invalid</span>' : "not checked in browser"}${keys.includes(k) ? " (trusted)" : ""}</li>`).join("")}</ul></div>`;
    $("out").innerHTML = h;
  };
  $("ex").onclick = async () => { const t = await fetch("example.json").then((x) => x.text()); $("c").value = t; $("k").value = "ed25519:moqKymSKFxCPXkaxDtETg/Qd8GvRwg8ckWAWIRQJXSQ="; };
})();
