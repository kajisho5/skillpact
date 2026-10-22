"""Token counts for the Why page table (cl100k_base): SKILL.md, a one-line-per-effect summary from the contract, and the full contract.
Usage: pip install tiktoken && python3 review/token_measure.py [skill_dir ...]   (default: the four samples)"""
import json, sys
from pathlib import Path
import tiktoken

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ["ffmpeg-skill", "subtitle-skill", "thumbnail-skill", "video-editing-skill"]


def summary(c):
    """One line per non-'none' effect: '<effect>: <level> <scope>, <scope>'."""
    out = []
    for eff, p in c["permissions"].items():
        if p["level"] == "none": continue
        out.append(f"{eff}: {p['level']}" + (" " + ", ".join(p["scope"]) if p.get("scope") else ""))
    return "\n".join(out)


def main(argv):
    enc = tiktoken.get_encoding("cl100k_base"); n = lambda s: len(enc.encode(s))
    dirs = [Path(a) for a in argv] or [ROOT / "samples" / s for s in SAMPLES]
    print("| Skill | `SKILL.md` | Effects summary from the contract | Full contract |\n|---|---|---|---|")
    for d in dirs:
        raw = (d / "skill.contract.json").read_text(encoding="utf-8")
        print(f"| {d.name} | {n((d / 'SKILL.md').read_text(encoding='utf-8')):,} | {n(summary(json.loads(raw))):,} | {n(raw):,} |")


if __name__ == "__main__": main(sys.argv[1:])
