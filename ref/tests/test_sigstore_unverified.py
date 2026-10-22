"""A Sigstore signature that cannot be verified here (sigstore not installed, trust root unreachable) is unverified:
a SIGSTORE_UNVERIFIED warning, never SIGNATURE_INVALID, and never trusted."""
import json, os, shutil, sys
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skillpact import core, sigstore_sig

CASES = Path(__file__).resolve().parents[2] / "conformance" / "cases"
KEY = "sigstore:https://token.actions.githubusercontent.com|https://github.com/o/r/.github/workflows/s.yml@refs/heads/main"


def _signed(tmp_path):
    d = tmp_path / "v08-valid-signed"; shutil.copytree(CASES / "v08-valid-signed", d)
    c = json.loads((d / "skill.contract.json").read_text())
    c["integrity"]["signatures"] = [{"type": "sigstore", "issuer": "https://token.actions.githubusercontent.com", "role": "author",
                                     "identity": "https://github.com/o/r/.github/workflows/s.yml@refs/heads/main", "bundle": {}}]
    (d / "skill.contract.json").write_text(json.dumps(c)); return d, c


def test_unverifiable_is_warning_not_invalid(tmp_path, monkeypatch):
    monkeypatch.setattr(sigstore_sig, "_verifier", lambda offline=False, staging=False: None)
    d, c = _signed(tmp_path)
    assert core.verify_signatures(c) == {KEY: None}
    codes = {f["code"]: f["level"] for f in core.validate(d)["findings"]}
    assert codes.get("SIGSTORE_UNVERIFIED") == "warn" and "SIGNATURE_INVALID" not in codes
    assert not core.trusted_author(c, {KEY})


def test_bad_bundle_with_working_verifier_is_invalid(tmp_path, monkeypatch):
    class V:
        def verify_artifact(self, *a): raise ValueError("bad")
    monkeypatch.setattr(sigstore_sig, "_verifier", lambda offline=False, staging=False: V())
    monkeypatch.setattr(sigstore_sig, "_verify_with", lambda v, *a: v.verify_artifact(*a))
    d, c = _signed(tmp_path)
    assert core.verify_signatures(c) == {KEY: False}
    assert "SIGNATURE_INVALID" in {f["code"] for f in core.validate(d)["findings"]}
