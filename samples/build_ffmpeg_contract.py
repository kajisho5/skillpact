"""Build the flagship contract for kajisho5/ffmpeg-skill: native contract -> SkillPact contract 0.3 (via init --from-native),
plus compat and one real conformance test per tool (and a 'dry run writes nothing' test per writing tool)."""
import json, subprocess, sys
from pathlib import Path
HERE = Path(__file__).parent; SK = HERE / "ffmpeg-skill"
sys.path.insert(0, str(HERE.parent / "ref"))
from skillpact import init

c = init.draft(SK)
c["x"]["init"]["uncertain"] = []  # reviewed by hand below
c["skill"].update({"license": "MIT", "authors": ["kajisho5"], "homepage": "https://github.com/kajisho5/ffmpeg-skill"})
c["compat"] = {"agents": {"claude-code": {"status": "expected", "notes": "SKILL.md + MCP stdio"}, "cursor": {"status": "expected"}, "codex": {"status": "expected"},
                          "gemini-cli": {"status": "expected"}, "grok-bot": {"status": "tested", "tested_at": "2026-10-21", "notes": "box: Debian 13, ffmpeg 7.1, python 3.13"}},
               "os": ["linux", "macos"], "interfaces": ["skill-md", "cli", "mcp-stdio"]}
c["permissions"]["exec"]["scope"].append("fc-match")  # found by the exec audit (0.8.x): scripts/_common/fonts.py asks fontconfig for font files
for cap in c["capabilities"]:
    if "exec" in cap.get("effect_scopes", {}): cap["effect_scopes"]["exec"].append("fc-match")   # fonts.py is shared by every tool
    if cap["id"] == "media.check" and "ffmpeg" not in cap["effect_scopes"]["exec"]: cap["effect_scopes"]["exec"].insert(0, "ffmpeg")   # exec audit: check.py measures loudness with ffmpeg
c["requirements"]["runtimes"].append({"name": "node", "version": ">=16", "check": ["node", "--version"], "optional": True, "when": "npx installer only"})
c["requirements"]["env"] = [{"name": "FFMPEG_SKILL_HW", "required": False, "description": "1 = Apple GPU encoders by default"},
                            {"name": "FFMPEG_SKILL_MCP_FULL", "required": False, "description": "1 = MCP tools/list shows all 42 tools"},
                            {"name": "HF_HUB_OFFLINE", "required": False, "description": "1 = never download speech models"}]
L = ["ffmpeg", "-loglevel", "error", "-y"]
V = lambda src, f, o: L + ["-f", "lavfi", "-i", f"{src}=d=4:s=320x240:r=25", "-f", "lavfi", "-i", f"sine=f={f}:d=4", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", o]
c["tests"] = {"setup": [V("testsrc", 440, "in.mp4"), V("testsrc2", 660, "b.mp4"),
    L + ["-f", "lavfi", "-i", "sine=f=440:d=4", "-ar", "48000", "a.wav"], L + ["-f", "lavfi", "-i", "color=c=red:s=64x64", "-frames:v", "1", "logo.png"],
    ["python3", "-c", "open('subs.srt','w').write('1\\n00:00:00,500 --> 00:00:02,000\\nHello\\n\\n2\\n00:00:02,200 --> 00:00:03,500\\nWorld\\n');open('chapters.txt','w').write('00:00 Intro\\n00:02 Part two\\n');import os,shutil;os.makedirs('frames',exist_ok=True);os.makedirs('folder',exist_ok=True);shutil.copy('in.mp4','folder/in.mp4');import json;json.dump({'steps':[['proxy.py','{in}','--width','160','-o','{out}']],'output_dir':'bout','suffix':'_p'},open('batch.json','w'))"],
    L + ["-f", "lavfi", "-i", "testsrc=d=1:s=160x120:r=10", "frames/frame_%04d.png"]], "cases": []}
# name -> (args, output file or None, extra expectations)
CASES = {
 "audio": ("in.mp4 --denoise -o o.mp4", "o.mp4"), "background": ("-o o.mp4 --duration 2 --width 320 --height 240 --color 0x101010", "o.mp4"),
 "batch": ("folder --recipe batch.json --jobs 1", "folder/bout/in_p.mp4"), "broll": ("in.mp4 --insert b.mp4 --at 1 --end 2 -o o.mp4", "o.mp4"),
 "caption": ("in.mp4 --srt subs.srt -o o.mp4", "o.mp4"), "color": ("in.mp4 --correct -o o.mp4", "o.mp4"),
 "crop": ("in.mp4 --x 0 --y 0 --width 160 --height 120 -o o.mp4", "o.mp4"), "cropdetect": ("in.mp4", None),
 "check": ("in.mp4 --platform youtube", None), "cut": ("in.mp4 --start 0.5 --end 2 -o o.mp4", "o.mp4"), "deinterlace": ("in.mp4 -o o.mp4", "o.mp4"),
 "denoise": ("in.mp4 --strength low -o o.mp4", "o.mp4"), "export": ("in.mp4 --preset youtube -o o.mp4", "o.mp4"),
 "fit": ("in.mp4 --duration 2 -o o.mp4", "o.mp4"), "freeze": ("in.mp4 --hold 1 -o o.mp4", "o.mp4"),
 "graphics": ("in.mp4 --template lower-third --name A --title B --start 0.5 --end 2 -o o.mp4", "o.mp4"),
 "grid": ("in.mp4 b.mp4 --cols 2 --rows 1 -o o.mp4", "o.mp4"), "insert": ("logo.png --duration 1 -o o.mp4", "o.mp4"),
 "join": ("in.mp4 b.mp4 -o o.mp4", "o.mp4"), "look": ("in.mp4 --tiles 2x1 -o o.png", "o.png"), "loop": ("in.mp4 --times 2 -o o.mp4", "o.mp4"),
 "loudness": ("in.mp4", None), "metadata": ("in.mp4 --chapters chapters.txt -o o.mp4", "o.mp4"),
 "multicam": ("in.mp4 b.mp4 --switch 0-2:0,2-4:1 -o o.mp4", "o.mp4"), "overlay": ("in.mp4 --image logo.png --position top-right -o o.mp4", "o.mp4"),
 "pad": ("in.mp4 --start 0.5 -o o.mp4", "o.mp4"), "probe": ("in.mp4", None), "proxy": ("in.mp4 --width 160 -o o.mp4", "o.mp4"),
 "redact": ("in.mp4 --x 10 --y 10 --width 50 --height 50 --mode pixelate -o o.mp4", "o.mp4"), "render": ("--template youtube in.mp4", None),
 "report": ("--after in.mp4 --before b.mp4 -o o.html", "o.html"), "reverse": ("in.mp4 -o o.mp4", "o.mp4"), "scenes": ("in.mp4", None),
 "sequence": ("--dir frames --pattern frame_%04d.png --start-number 1 --fps 10 -o o.mp4", "o.mp4"), "silence": ("in.mp4", None),
 "speedramp": ("in.mp4 --segment 0-2:1.0 --segment 2-4:2.0 -o o.mp4", "o.mp4"), "sphere": ("in.mp4 --yaw 90 -o o.mp4", "o.mp4"),
 "stabilize": ("in.mp4 -o o.mp4", "o.mp4"), "straighten": ("in.mp4 --degrees -2 -o o.mp4", "o.mp4"), "sync": ("in.mp4 a.wav", None),
 "verify": ("in.mp4", None), "waveform": ("a.wav -o o.mp4", "o.mp4"),
}
CHECKS = {"probe": [{"path": "$.video.width", "equals": 320}, {"path": "$.video.fps", "equals": 25.0}, {"path": "$.duration", "min": 3.9, "max": 4.1}],
          "cut": [{"path": "$.summary.duration_s", "min": 1.4, "max": 1.6}, {"path": "$.verified", "equals": True}],
          "crop": [{"path": "$.summary.width", "equals": 160}, {"path": "$.summary.height", "equals": 120}],
          "proxy": [{"path": "$.summary.width", "equals": 160}], "fit": [{"path": "$.summary.duration_s", "min": 1.8, "max": 2.2}],
          "loop": [{"path": "$.summary.duration_s", "min": 7.5, "max": 8.5}], "join": [{"path": "$.summary.duration_s", "min": 7.0, "max": 8.6}]}
BRIEF = {"cropdetect", "probe", "scenes", "verify", "sync", "loudness", "silence"}  # analysis tools: full --json
for t in c["capabilities"]:
    n = t["entry"]["mcp_tool"]; args, out = CASES[n]
    if out and out.startswith("o."): args, out = args.replace(" " + out, f" o_{n}{out[1:]}").replace("-o " + out, f"-o o_{n}{out[1:]}"), f"o_{n}{out[1:]}"
    if n == "check": continue  # covered by check-flags-loudness / check-passes-after-export
    run = ["python3", f"$SKILL_DIR/scripts/{n}.py"] + args.split() + (["--json"] if n in BRIEF else ["--json-brief"])
    ex = {"exit_code": 0}
    if n not in BRIEF and n != "render": ex["stdout_json"] = [{"path": "$.status", "equals": "completed"}]
    ex.setdefault("stdout_json", []).extend(CHECKS.get(n, []))
    if not ex["stdout_json"]: ex["stdout_json_schema"] = {"type": "object"}
    if n in ("batch", "report"): ex["stdout_json_mode"] = "last"  # FINDING: these print progress lines to stdout before the JSON
    if out: ex["files"] = [{"path": out, "min_bytes": 500}]
    c["tests"]["cases"].append({"id": f"{n}-basic", "capability": t["id"], "run": run, "timeout_s": 180, "expect": ex, "tags": [t["role"]]})
    if out and t["dry_run"]["supported"] and n not in ("batch",):
        c["tests"]["cases"].append({"id": f"{n}-dry-run-writes-nothing", "capability": t["id"], "timeout_s": 60, "tags": ["dry-run"],
            "run": ["python3", f"$SKILL_DIR/scripts/{n}.py"] + args.replace(out, "dry_" + out.split("/")[-1]).split() + ["--dry-run", "--json-brief"],
            "expect": {"exit_code": 0, "files": [{"path": "dry_" + out.split("/")[-1], "exists": False}]}})
# negative / safety cases
c["tests"]["cases"] += [
 {"id": "check-flags-loudness", "capability": "media.check", "tags": ["verification", "negative"], "run": ["python3", "$SKILL_DIR/scripts/check.py", "in.mp4", "--platform", "youtube"], "expect": {"exit_code": 1, "stderr_contains": "loudness"}},
 {"id": "check-passes-after-export", "capability": "media.check", "tags": ["verification"], "run": ["sh", "-c", "python3 \"$SKILL_DIR/scripts/export.py\" in.mp4 --preset youtube --normalize -o yt.mp4 >/dev/null && python3 \"$SKILL_DIR/scripts/check.py\" yt.mp4 --platform youtube"], "expect": {"exit_code": 0}},
 {"id": "cut-missing-input-fails", "capability": "media.cut", "tags": ["negative"], "run": ["python3", "$SKILL_DIR/scripts/cut.py", "nope.mp4", "--start", "0", "--end", "1", "-o", "x.mp4", "--json-brief"], "expect": {"exit_code": 1, "files": [{"path": "x.mp4", "exists": False}]}},
 {"id": "cut-refuses-overwrite", "capability": "media.cut", "tags": ["safety"], "run": ["sh", "-c", "cp in.mp4 keep.mp4 && ! python3 \"$SKILL_DIR/scripts/cut.py\" in.mp4 --start 0 --end 1 -o keep.mp4 && cmp -s in.mp4 keep.mp4"], "expect": {"exit_code": 0}},
 {"id": "input-never-mutated", "capability": "media.export", "tags": ["safety"], "run": ["sh", "-c", "sha256sum in.mp4 > h && python3 \"$SKILL_DIR/scripts/export.py\" in.mp4 --preset x -o m.mp4 >/dev/null && sha256sum -c h"], "expect": {"exit_code": 0}},
]
(SK / "skill.contract.json").write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n")
print(len(c["capabilities"]), "capabilities,", len(c["tests"]["cases"]), "tests")

# L3: hash + sign with the SEVENTHWELL skill-signing key (private key lives only on the box, outside /workspace)
from skillpact import core
import os
key = Path(os.environ.get("SEVENTHWELL_SIGNING_KEY", "/home/box/.secrets/seventhwell-skill-signing/private.pem"))
n = core.hash_files(SK); pub = core.sign(SK, key, "SEVENTHWELL (kajisho5) skill-signing key")
print("hashed", n, "files; signed by", pub)
