"""SkillPact <-> OS capability contract (kajisho5/Velisa registry/capability_contract.schema.json), spec/os_capability_mapping.md."""
import copy, json, pathlib
import jsonschema, pytest
from skillpact import cli, core, interop
ROOT = pathlib.Path(__file__).parents[2]
OS = ROOT / "examples/os-capability"
QC_OS = json.loads((OS / "qc-skill.provides.json").read_text())
QC_SP = json.loads((ROOT / "examples/contracts/qc-skill.contract.json").read_text())
SCHEMA = json.loads((ROOT / "ref/skillpact/schema.json").read_text())

def strip(doc): return {k: v for k, v in doc.items() if k != "x-skillpact"}

def qc_with_os():
    """The qc-skill example contract with the OS view an author adds: its one CLI capability is the OS tool qc/run."""
    c = copy.deepcopy(QC_SP); back = interop.from_os(QC_OS)
    c["x"]["os"] = back["x"]["os"]; c["capabilities"][0]["x"] = {"os": back["capabilities"][0]["x"]["os"]}
    return c

def test_vendored_schema_is_velisa_and_fixtures_validate():
    assert interop.OS_SCHEMA["$id"] == "https://github.com/kajisho5/Velisa/registry/capability_contract.schema.json"
    jsonschema.Draft202012Validator.check_schema(interop.OS_SCHEMA)
    fixtures = sorted(OS.glob("*.provides.json")); assert len(fixtures) == 5
    for f in fixtures: assert interop.os_problems(json.loads(f.read_text())) == [], f.name

def test_qc_os_roundtrip_is_exact():
    c = interop.from_os(QC_OS)
    jsonschema.validate(c, SCHEMA)
    assert [x["id"] for x in c["capabilities"]] == ["run"] and c["skill"] == {"name": "qc", "version": "0.0.0"}
    assert len(c["capabilities"][0]["x"]["os"]["provides"]) == 10 and c["capabilities"][0]["x"]["os"]["tool_id"] == "qc/run"
    out = interop.to_os(c)
    assert out["schema_errors"] == [] and strip(out["document"]) == QC_OS
    assert out["document"]["x-skillpact"]["spec"] == interop.CANON

def test_qc_os_import_is_an_unconfirmed_draft():
    c = interop.from_os(QC_OS)
    assert all(p == {"level": "none"} for p in c["permissions"].values()) and c["capabilities"][0]["effects"] == []
    assert any("permissions" in u for u in c["x"]["import"]["uncertain"])
    assert "x.import.uncertain" in core.draft_markers(c)

def test_qc_skillpact_roundtrip_keeps_what_os_carries():
    out = interop.to_os(QC_SP); doc = out["document"]
    assert out["schema_errors"] == [] and doc["skill_id"] == "qc-skill" and doc["version"] == "0.1.0"
    assert doc["provides"] == [{"id": "cli.qc", "lifecycle": "EXPERIMENTAL", "tool_id": "qc-skill/cli.qc"}]
    assert out["guessed"] and any(x.startswith("permissions") for x in out["lossy"]) and any("tests" in x for x in out["lossy"])
    back = interop.from_os(doc)
    assert back["skill"] == QC_SP["skill"] and [x["id"] for x in back["capabilities"]] == [x["id"] for x in QC_SP["capabilities"]]
    assert strip(interop.to_os(back)["document"]) == strip(doc)

def test_qc_with_os_view_exports_the_os_fixture():
    c = qc_with_os()   # examples/contracts/ are 0.3 init drafts, not 0.8-valid contracts; only the OS side is checked here
    doc = interop.to_os(c)["document"]
    assert doc["version"] == "0.1.0" and {k: v for k, v in strip(doc).items() if k != "version"} == QC_OS
    assert interop.os_check(c, QC_OS) == ["version: contract '0.1.0', OS contract None"]
    assert interop.os_check(c, {**QC_OS, "version": "0.1.0"}) == []

def test_os_check_names_differences():
    c = qc_with_os(); os_doc = copy.deepcopy({**QC_OS, "version": "0.1.0"})
    os_doc["skill_id"] = "qc2"; os_doc["provides"][0]["lifecycle"] = "STABLE"; os_doc["provides"].pop()
    os_doc["provides"].append({"id": "measure.new", "lifecycle": "PROPOSED", "tool_id": "qc/run"})
    m = interop.os_check(c, os_doc)
    assert "skill id: contract gives 'qc', OS contract 'qc2'" in m
    assert "provides 'measure.audio.channel_layout'.lifecycle: contract 'EXPERIMENTAL', OS contract 'STABLE'" in m
    assert "provides 'measure.video.freeze': only in the SkillPact contract" in m and "provides 'measure.new': only in the OS contract" in m

@pytest.mark.parametrize("name", ["ffmpeg-skill", "media-analysis-skill", "transcription-skill", "video-editing-skill"])
def test_other_os_fixtures_roundtrip(name):
    d = json.loads((OS / f"{name}.provides.json").read_text()); c = interop.from_os(d)
    jsonschema.validate(c, SCHEMA)
    assert strip(interop.to_os(c)["document"]) == d

def test_identity_shapes_and_order():
    ff = json.loads((OS / "ffmpeg-skill.provides.json").read_text()); c = interop.from_os(ff)
    assert c["skill"] == {"name": "ffmpeg-skill", "version": "2.22.1"} and c["capabilities"][0]["id"] == "audio"
    c["skill"]["version"] = "2.23.0"; assert interop.to_os(c)["document"]["skill"] == {"id": "ffmpeg-skill", "version": "2.23.0"}
    ma = json.loads((OS / "media-analysis-skill.provides.json").read_text())
    assert "order" in interop.from_os(ma)["x"]["os"]   # tools interleave in provides[]; grouping per tool keeps the order apart

def test_from_os_rejects_invalid_documents():
    for bad in ({"provides": []}, {"skill_id": "x", "provides": [{"id": "a", "lifecycle": "DONE", "tool_id": "x/a"}]},
                {"skill_id": "x", "provides": [{"id": "a", "lifecycle": "STABLE", "tool_id": "x/a"}, {"id": "a", "lifecycle": "STABLE", "tool_id": "x/b"}]}):
        with pytest.raises(ValueError): interop.from_os(bad)

def test_dependencies_map_to_required_skills():
    d = {"skill_id": "video-editing", "version": "1.2.0", "provides": [{"id": "video.cut", "lifecycle": "STABLE", "tool_id": "video-editing/cut", "mutates_input": False}],
         "dependencies": [{"skill_id": "ffmpeg-skill", "version_range": ">=0.10.0"}]}
    c = interop.from_os(d)
    assert c["requirements"]["skills"] == [{"name": "ffmpeg-skill", "version": ">=0.10.0"}] and c["capabilities"][0]["destructive"] is False
    assert strip(interop.to_os(c)["document"]) == d
    c2 = copy.deepcopy(QC_SP); c2["requirements"]["skills"] = [{"name": "ffmpeg-skill", "version": ">=2.0.0"}, {"name": "x", "optional": True}]
    out = interop.to_os(c2)
    assert out["document"]["dependencies"] == [{"skill_id": "ffmpeg-skill", "version_range": ">=2.0.0"}] and any("requirements.skills" in x for x in out["lossy"])

def test_cli(tmp_path, capsys):
    d = tmp_path / "qc-skill"; d.mkdir(); (d / "skill.contract.json").write_text(json.dumps(qc_with_os()))
    good = tmp_path / "os.json"; good.write_text(json.dumps({**QC_OS, "version": "0.1.0"}))
    assert cli.main(["convert", str(d), "--to", "os-capability", "-o", str(tmp_path / "out.json"), "--against", str(good)]) == 0
    r = json.loads(capsys.readouterr().out); assert r["mismatches"] == [] and len(r["document"]["x-skillpact"]["sha256"]) == 64
    assert strip(json.loads((tmp_path / "out.json").read_text())) == {**QC_OS, "version": "0.1.0"}
    assert cli.main(["convert", str(d), "--to", "os-capability", "--against", str(OS / "qc-skill.provides.json")]) == 1
    assert json.loads(capsys.readouterr().out)["mismatches"]
    assert cli.main(["convert", str(OS / "qc-skill.provides.json"), "--from", "os-capability", "-o", str(tmp_path / "draft.json")]) == 0
    capsys.readouterr(); assert json.loads((tmp_path / "draft.json").read_text())["x"]["import"]["source"] == "os-capability"
    bad = tmp_path / "bad.json"; bad.write_text("{}")
    assert cli.main(["convert", str(bad), "--from", "os-capability"]) == 1 and "skill_id" in capsys.readouterr().out
    assert cli.main(["convert", str(d), "--to", "mda", "--against", str(good)]) == 1
