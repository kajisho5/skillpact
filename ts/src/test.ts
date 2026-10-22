import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { jcs } from "./jcs.js";
import { verifyEd25519, signingInput, validate, verifyLevel } from "./index.js";
const ROOT = new URL("../../", import.meta.url).pathname;

test("JCS known-answer vectors + ed25519", () => {
  const doc = JSON.parse(readFileSync(ROOT + "conformance/vectors/jcs-ed25519.json", "utf8"));
  for (const v of doc.vectors) {
    const c2 = JSON.parse(JSON.stringify(v.contract)); if (c2.integrity) delete c2.integrity.signatures;
    assert.equal(jcs(c2), v.canonical_utf8, v.id);
    assert.ok(verifyEd25519(doc.test_public_key, v.ed25519_sig, signingInput(v.contract)), v.id);
  }
});

test("conformance suite passes", () => {
  const out = execFileSync("python3", [ROOT + "conformance/run.py", "--cmd", `node ${ROOT}ts/dist/cli.js validate {dir}`], { encoding: "utf8" });
  const r = JSON.parse(out); assert.ok(r.ok, JSON.stringify(r.cases.filter((c: any) => !c.ok)));
});

for (const n of ["ffmpeg-skill", "subtitle-skill", "thumbnail-skill", "video-editing-skill"]) {
  test(`sample ${n}: valid and signed by trusted key`, () => {
    const r = verifyLevel(ROOT + "samples/" + n, ["ed25519:moqKymSKFxCPXkaxDtETg/Qd8GvRwg8ckWAWIRQJXSQ="]);
    assert.equal(r.validate.ok, true, JSON.stringify(r.validate.findings.filter(f => f.level === "error")));
    // the TypeScript verifier cannot check Sigstore: a sample signed only by the repository's CI must carry that entry (Python verifies it)
    const c = JSON.parse(readFileSync(ROOT + "samples/" + n + "/skill.contract.json", "utf8"));
    const ci = (c.integrity.signatures || []).some((s: any) => s.type === "sigstore" && `sigstore:${s.issuer}|${s.identity}` === "sigstore:https://token.actions.githubusercontent.com|https://github.com/kajisho5/skillpact/.github/workflows/sigstore-sign.yml@refs/heads/main" && !s.instance);
    assert.ok((r as any).signature_trusted === true || ci, "neither the SEVENTHWELL key nor the CI signer");
  });
}

test("tampered contract fails", () => {
  const r = validate(ROOT + "conformance/cases/signed-jcs-tampered"); assert.equal(r.ok, false);
  assert.ok(r.findings.some(f => f.code === "SIGNATURE_INVALID"));
});

test("@local vectors (erratum 0.8.x: IP literals and localhost only)", async () => {
  const { isLocalHost, globMatch } = await import("./core.js");
  const doc = JSON.parse(readFileSync(ROOT + "conformance/vectors/local-hosts.json", "utf8"));
  for (const [h, want] of doc.cases) { assert.equal(isLocalHost(h), !!want, h); assert.equal(globMatch(h, "@local", "host"), !!want, h); }
});
