"""0.8.x erratum: network: true cases reach only the hosts in their network scope (bubblewrap mode). Offline: a local HTTP
server on the host stands in for a remote service."""
import http.server, json, os, shutil, sys, threading
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skillpact import core

CASES = Path(__file__).resolve().parents[2] / "conformance" / "cases"
needs_bwrap = pytest.mark.skipif(core._sandbox() != "bwrap", reason="needs bubblewrap")


@pytest.fixture(scope="module")
def server():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Quiet); threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s.server_address[1]; s.shutdown()


def _case(tmp_path, scope, code, cap_scope=None):
    d = tmp_path / "v08-valid-signed"; shutil.copytree(CASES / "v08-valid-signed", d)
    c = json.loads((d / "skill.contract.json").read_text()); cap = c["capabilities"][0]
    c["permissions"]["network"] = {"level": "scoped", "scope": scope}; cap["effects"].append("network")
    c["permissions"]["exec"]["scope"].append("python3")
    if cap_scope: cap["effect_scopes"] = {**cap.get("effect_scopes", {}), "network": cap_scope}
    c["tests"]["cases"] = [{"id": "x", "capability": cap["id"], "network": True, "run": ["python3", "-c", code], "expect": {"exit_code": 0, "stdout_contains": "200"}}]
    (d / "skill.contract.json").write_text(json.dumps(c)); return d


def fetch(port): return f"import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:{port}/', timeout=20).status)"


def test_network_scope_uses_capability_and_conditional_scopes():
    c = {"permissions": {"network": {"level": "scoped", "scope": ["a.com", "b.com"]}}}
    cap = {"effect_scopes": {"network": ["a.com"]}, "conditional_effects": [{"effect": "network", "when": "x", "scope": ["c.com"]}]}
    assert core.network_scope(c, cap) == (["a.com", "c.com"], "scoped") and core.network_scope(c) == (["a.com", "b.com"], "scoped")


@needs_bwrap
def test_declared_host_is_reached(tmp_path, server):
    r = core.run_tests(_case(tmp_path, ["@local"], fetch(server)))
    assert r["ok"] and r["network_egress"] == "allowlist" and r["cases"][0]["network_hosts"] == {"allowed": ["127.0.0.1"], "denied": []}


@needs_bwrap
def test_undeclared_host_fails(tmp_path, server):
    r = core.run_tests(_case(tmp_path, ["example.com"], fetch(server))); x = r["cases"][0]
    assert not r["ok"] and x["network_hosts"]["denied"] == ["127.0.0.1"] and any("undeclared host" in f for f in x["failures"])


@needs_bwrap
def test_capability_scope_narrows(tmp_path, server):
    r = core.run_tests(_case(tmp_path, ["@local", "example.com"], fetch(server), cap_scope=["example.com"]))
    assert not r["ok"] and r["cases"][0]["network_hosts"]["denied"] == ["127.0.0.1"]


@needs_bwrap
def test_direct_connection_has_no_route(tmp_path, server):
    code = f"import socket; socket.create_connection(('127.0.0.1', {server}), timeout=5); print(200)"   # ignores the proxy
    r = core.run_tests(_case(tmp_path, ["**"], code)); assert not r["ok"] and r["cases"][0]["network_hosts"] == {"allowed": [], "denied": []}
