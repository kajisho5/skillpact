"""The repository's root SKILL.md (ECOSYSTEM_ROADMAP.md step 1) names only commands and options the CLI has."""
import re, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skillpact import core, cli

REPO = Path(__file__).resolve().parents[2]
SKILL_MD = REPO / "SKILL.md"


def _help(capsys, *argv):
    with pytest.raises(SystemExit): cli.main([*argv, "--help"])
    return capsys.readouterr().out


def _subcommands(capsys):
    m = re.search(r"\{([a-z,-]+)\}", _help(capsys)); assert m
    return m.group(1).split(",")


def test_frontmatter_is_strict_and_valid():
    text = SKILL_MD.read_text(encoding="utf-8")
    fm, body = core.read_frontmatter(SKILL_MD)
    assert set(fm) == {"name", "description"}
    assert fm["name"] == "skillpact"   # agentskills.io: equals the directory the marketplace installs it into
    assert core.NAME_RE.match(fm["name"])
    d = fm["description"]; assert 20 <= len(d) <= 1024 and "<" not in d and ">" not in d
    for line in text.split("---", 2)[1].strip().splitlines():   # plain scalars only: a strict YAML reader must not see a second mapping
        key, _, value = line.partition(": "); assert key in fm and ": " not in value and not value.startswith(("'", '"', "|", ">"))
    assert body.count("\n") <= 500   # BODY_LONG threshold of `skillpact validate`


def test_every_command_and_option_exists(capsys):
    subs = set(_subcommands(capsys)); text = SKILL_MD.read_text(encoding="utf-8")
    used = re.findall(r"`skillpact ([a-z-]+)([^`]*)`", text); assert used
    for cmd, rest in used:
        assert cmd in subs, f"SKILL.md names `skillpact {cmd}`, which the CLI does not have"
        opts = set(re.findall(r"(?<![\w-])(--?[a-z][a-z-]*)", _help(capsys, cmd)))
        for o in re.findall(r"(?<![\w$-])(--?[a-z][a-z-]*)", rest):
            assert o in opts, f"`skillpact {cmd}` has no option {o}"


def test_every_subcommand_is_documented(capsys):
    named = set(re.findall(r"`skillpact ([a-z-]+)", SKILL_MD.read_text(encoding="utf-8")))
    assert set(_subcommands(capsys)) - named == set()


def test_level_names_match_conformance():
    text = SKILL_MD.read_text(encoding="utf-8"); src = (REPO / "ref" / "skillpact" / "cli.py").read_text()
    for level in ("L1-declared", "L2-tested", "L3-signed"):
        assert f"`{level}`" in text and f'"{level}"' in src
