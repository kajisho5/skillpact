"""Sigstore (keyless) signatures for SkillPact contracts, alongside ed25519.
Signed bytes: the same signing input as ed25519 (spec 0.8 s11.1: JCS, with the role included from 0.8).
Signature entry: {"type": "sigstore", "identity": <SAN>, "issuer": <OIDC issuer>, "bundle": <Sigstore bundle v0.3 JSON object>}.
Keyless signing needs an OIDC identity token (ambient CI token such as GitHub Actions `id-token: write`, or an
interactive browser flow). Verification needs the Sigstore trust root (TUF; network on first use, then cache).
`signer` / `verifier` hooks allow tests and air-gapped use to inject implementations."""
import json
from pathlib import Path
from . import core


def _bundle_cls():
    from sigstore.models import Bundle
    return Bundle


def sign(skill_dir, identity_token=None, contract_path=None, signer=None, staging=False, role="author"):
    skill_dir = Path(skill_dir).resolve(); c, cpath = core.load_contract(skill_dir, contract_path)
    if "integrity" not in c: raise SystemExit("run `hash` first")
    payload = core._canonical(c, role)
    if signer is None:
        from sigstore.oidc import IdentityToken, detect_credential, Issuer
        from sigstore.sign import SigningContext
        from sigstore.models import ClientTrustConfig
        tok = identity_token or detect_credential()
        if tok is None:
            tok = (Issuer.staging() if staging else Issuer.production()).identity_token()  # interactive browser flow
        tok = tok if isinstance(tok, IdentityToken) else IdentityToken(tok)
        ctx = SigningContext.from_trust_config(ClientTrustConfig.staging() if staging else ClientTrustConfig.production())
        with ctx.signer(tok) as s: bundle = s.sign_artifact(payload)
        identity, issuer, bjson = cert_identity(bundle.signing_certificate) or tok.identity, tok.issuer, json.loads(bundle.to_json())
    else:
        identity, issuer, bjson = signer(payload)
    entry = {"type": "sigstore", "identity": identity, "issuer": issuer, "bundle": bjson}
    if staging: entry["instance"] = "staging"
    if role != "author" or core._vt(c.get("contract_version", "0.1")) >= core.V08: entry["role"] = role
    c["integrity"].setdefault("signatures", []).append(entry)
    cpath.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n")
    return {"identity": identity, "issuer": issuer}


def cert_identity(cert):
    """The identity Sigstore verifies against: the certificate SAN (URI or email), not the token `sub`.
    For GitHub Actions this is the workflow URL, e.g. https://github.com/<o>/<r>/.github/workflows/<f>@refs/heads/main."""
    from cryptography.x509 import SubjectAlternativeName, UniformResourceIdentifier, RFC822Name
    try:
        san = cert.extensions.get_extension_for_class(SubjectAlternativeName).value
    except Exception:
        return None
    for t in (UniformResourceIdentifier, RFC822Name):
        v = san.get_values_for_type(t)
        if v: return v[0]
    return None


def verify_entry(c, entry, verifier=None, offline=False):
    """True / False for one sigstore entry, None when it cannot be verified here; the expected identity+issuer are the ones recorded in the entry,
    so callers must additionally check them against a trusted-identity list (see core.verify_signatures(trusted=...))."""
    payload = core._canonical(c, entry.get("role"))
    if verifier is not None: return bool(verifier(payload, entry))
    v = _verifier(offline, entry.get("instance") == "staging")
    if v is None: return None   # cannot verify here (sigstore not installed, or trust root unreachable): unverified, not invalid
    try:
        _verify_with(v, payload, entry["bundle"], entry["identity"], entry["issuer"]); return True
    except Exception:
        return False


def _verifier(offline=False, staging=False):
    try:
        from sigstore.verify import Verifier
        return Verifier.staging(offline=offline) if staging else Verifier.production(offline=offline)
    except Exception:
        return None


def _verify_with(v, payload, bundle_json, identity, issuer):
    from sigstore.verify import policy
    b = _bundle_cls().from_json(bundle_json if isinstance(bundle_json, (str, bytes)) else json.dumps(bundle_json))
    v.verify_artifact(payload, b, policy.Identity(identity=identity, issuer=issuer))


def verify_bytes(payload: bytes, bundle_json, identity, issuer, offline=False, staging=False):
    """Raise on failure. Plain Sigstore verification of `payload` (used for contracts and in integration tests)."""
    from sigstore.verify import Verifier
    _verify_with(Verifier.staging(offline=offline) if staging else Verifier.production(offline=offline), payload, bundle_json, identity, issuer)
