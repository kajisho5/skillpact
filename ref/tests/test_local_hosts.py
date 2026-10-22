import json, pathlib
from skillpact.core import is_local_host, glob_match
V = json.loads((pathlib.Path(__file__).parents[2] / "conformance/vectors/local-hosts.json").read_text())

def test_local_vectors():
    for h, want in V["cases"]:
        assert is_local_host(h) == bool(want), h
        assert glob_match(h, "@local", "host") == bool(want), h
