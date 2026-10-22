"""0.8.x erratum: requirements.packages[].version is checked, and start-up hooks of declared packages are reported."""
import importlib, json, os, shutil, sys
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skillpact import core

CASES = Path(__file__).resolve().parents[2] / "conformance" / "cases"


def fake_dist(root: Path, version: str, hooks=()):
    """A minimal installed distribution 'spfake' (import name spfake) in its own site directory."""
    (root / "spfake").mkdir(parents=True); (root / "spfake" / "__init__.py").write_text("")
    info = root / f"spfake-{version}.dist-info"; info.mkdir()
    (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: spfake\nVersion: {version}\n")
    for h in hooks: (root / h).write_text("")
    (info / "RECORD").write_text("".join(f"{f},,\n" for f in ["spfake/__init__.py", *hooks, f"{info.name}/METADATA", f"{info.name}/RECORD"]))


@pytest.fixture
def site(tmp_path, monkeypatch):
    def make(version, hooks=()):
        d = tmp_path / f"site-{version}"; fake_dist(d, version, hooks)
        monkeypatch.syspath_prepend(str(d)); importlib.invalidate_caches(); return d
    return make


def contract(version=None, optional=False):
    pk = {"ecosystem": "pypi", "name": "spfake", "import": "spfake", **({"version": version} if version else {}), **({"optional": True} if optional else {})}
    return {"capabilities": [], "requirements": {"packages": [pk]}}


def pkg(c): return next(r for r in core.check_requirements(c) if r["kind"] == "package")


@pytest.mark.parametrize("found,spec,ok", [
    ("1.106.2", "==1.106.2", True), ("1.107.0", "==1.106.2", False), ("1.106.2", ">=1.0,<1.107", True),
    ("1.107.0", ">=1.0,<1.107", False), ("1.107.0", "!=1.107.0", False), ("1.106.9", "~=1.106.0", True),
    ("1.107.0", "~=1.106.0", False), ("1.106.2", "1.106.2", True), ("1.106.2", "latest", False), ("1.106.2", "^1.106", False)])
def test_pkg_version_spec(found, spec, ok):
    assert core._pkg_version_ok(found, spec) is ok


def test_pinned_version_mismatch_is_unmet(site):
    site("1.107.0"); r = pkg(contract("==1.106.2"))
    assert not r["ok"] and r["version"] == "1.107.0" and "does not satisfy" in r["reason"]


def test_pinned_version_match_is_met(site):
    site("1.106.2"); r = pkg(contract("==1.106.2")); assert r["ok"] and r["version"] == "1.106.2"


def test_optional_package_with_wrong_version_still_fails(site):
    site("1.107.0"); assert not pkg(contract("==1.106.2", optional=True))["ok"]


def test_optional_package_absent_is_met():
    importlib.invalidate_caches(); assert pkg(contract("==1.106.2", optional=True))["ok"]


def test_startup_hooks_reported(site):
    # litellm 1.107.0 (2026-10-21) shipped cook.pth and sitecustomize.py, which Python runs at start-up
    site("1.107.0", hooks=("cook.pth", "sitecustomize.py")); r = pkg(contract())
    assert r["ok"] and r["startup_hooks"] == ["cook.pth", "sitecustomize.py"]


def test_unmet_pin_blocks_tests(site, tmp_path):
    site("1.107.0")
    d = tmp_path / "v08-valid-signed"; shutil.copytree(CASES / "v08-valid-signed", d)
    c = json.loads((d / "skill.contract.json").read_text())
    c.setdefault("requirements", {})["packages"] = contract("==1.106.2")["requirements"]["packages"]
    (d / "skill.contract.json").write_text(json.dumps(c))
    r = core.run_tests(d); assert not r["ok"] and r["error"] == "requirements not met" and r["cases"] == []


def test_pth_is_protected_from_exclude():
    assert core._excluded("hook.pth", core.PROTECTED) and core._excluded("lib/x.pth", core.PROTECTED)
