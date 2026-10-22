"""Proposal #12: exec rules are compiled per program, not as one worst case per effect."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skillpact import core

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = json.loads((ROOT / "samples" / "ffmpeg-skill" / "skill.contract.json").read_text())
POL = lambda n: json.loads((ROOT / "ref" / "policies" / f"{n}.json").read_text())


def bash(cfg, bucket): return sorted(x for x in cfg["config"]["permissions"][bucket] if x.startswith("Bash("))


def test_declared_programs_keep_their_own_decision():
    cfg = core.compile_native(SAMPLE, POL("solo-dev"), "claude-code")
    assert {"Bash(ffmpeg *)", "Bash(ffprobe *)", "Bash(python3 *)"} <= set(bash(cfg, "allow"))
    assert "Bash(whisper *)" in bash(cfg, "ask")   # only the --transcribe engine is ask


def test_strict_policy_denies_unlisted_programs():
    pol = {**POL("strict-ci"), "require_signature": False}   # signature checks need the skill directory; not the point here
    cfg = core.compile_native(SAMPLE, pol, "claude-code")
    assert "Bash(ffmpeg *)" in bash(cfg, "allow") and "Bash(whisper *)" in bash(cfg, "deny")


def test_gemini_and_cursor_follow_the_same_split():
    g = core.compile_native(SAMPLE, POL("solo-dev"), "gemini-cli")["config"]["rule"]
    d = {r["commandPrefix"].strip(): r["decision"] for r in g if r.get("commandPrefix")}
    assert d["ffmpeg"] == "allow" and d["whisper"] == "ask_user"
    cu = core.compile_native(SAMPLE, POL("solo-dev"), "cursor")["config"]["permissions"]
    assert "Shell(ffmpeg)" in cu["allow"] and "Shell(whisper)" not in cu["allow"]   # Cursor: not allowed = prompts


def test_confirm_each_still_asks():
    c = json.loads(json.dumps(SAMPLE)); c["permissions"]["exec"]["confirm"] = "each"
    assert "Bash(ffmpeg *)" in bash(core.compile_native(c, POL("solo-dev"), "claude-code"), "ask")
