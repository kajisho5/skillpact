from skillpact.init import draft
from skillpact import core


def test_init_infers_subcommands_mcp_and_headings(tmp_path):
    d = tmp_path / "s"; (d / "src" / "pkg").mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: s\ndescription: renders images with ffmpeg\n---\n# S\n")
    (d / "pyproject.toml").write_text('[project]\nname="s"\nversion="1.2.3"\n[project.scripts]\ns = "pkg.cli:main"\n')
    (d / "src" / "pkg" / "cli.py").write_text('import argparse\np=argparse.ArgumentParser();sp=p.add_subparsers()\nsp.add_parser("doctor")\nsp.add_parser("render")\n')
    (d / "src" / "pkg" / "server.py").write_text('@mcp.tool()\ndef make_thumb(x):\n    return x\n')
    c = draft(d); ids = {x["id"]: x for x in c["capabilities"]}
    assert {"cli.s.doctor", "cli.s.render", "mcp.make-thumb"} <= set(ids)
    assert ids["cli.s.doctor"]["effects"] == ["read", "exec"] and ids["cli.s.render"]["entry"]["cli"][-1] == "render"
    assert core.draft_markers(c)  # still an unconfirmed draft

    g = tmp_path / "g"; g.mkdir()
    (g / "SKILL.md").write_text("---\nname: g\ndescription: d\n---\n## Overview\nx\n## Write release notes\ny\n## Review a PR\nz\n")
    caps = [x["id"] for x in draft(g)["capabilities"]]
    assert caps == ["guide.write-release-notes", "guide.review-a-pr"]
