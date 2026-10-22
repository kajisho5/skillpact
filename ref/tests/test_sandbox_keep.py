import os, shutil, stat, subprocess, pytest
from skillpact import core


@pytest.mark.skipif(core._sandbox() != "bwrap", reason="needs bwrap")
def test_local_bin_invisible_unless_needed(tmp_path, monkeypatch):
    home = tmp_path / "home"; lb = home / ".local" / "bin"; lb.mkdir(parents=True)
    (home / ".local" / "secret.txt").write_text("s")
    tool = lb / "mytool"; tool.write_text("#!/bin/sh\necho TOOL\n"); tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("HOME", str(home)); monkeypatch.setenv("PATH", f"{lb}:{os.environ['PATH']}")
    work = tmp_path / "w"; work.mkdir()
    probe = ["sh", "-c", f"ls {lb} 2>/dev/null; cat {home}/.local/secret.txt 2>/dev/null; echo END"]
    out = subprocess.run(core._wrap(probe, "bwrap", False, work, None), capture_output=True, text=True).stdout
    assert "mytool" not in out and "s\nEND" not in out and "END" in out   # PATH entry not needed: hidden
    out = subprocess.run(core._wrap(probe, "bwrap", False, work, None, programs=["mytool"]), capture_output=True, text=True).stdout
    assert "mytool" in out and "s\nEND" not in out   # needed tool dir visible, its parent (~/.local) still hidden
