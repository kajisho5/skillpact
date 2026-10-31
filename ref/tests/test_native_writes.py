"""`init --from-native`: which native tool flags give a capability the write effect."""
import pytest
from skillpact.native import native_to_contract

def native(**flags):
    tool = {"name": "resize", "input_schema": {"properties": {"input": {"type": "path"}}}, **flags}
    return {"skill": {"name": "imagemagick-skill", "version": "0.8.1"}, "tools": [tool]}

@pytest.mark.parametrize("flags", [{"produces_artifact": True}, {"writes_output": True}])
def test_writing_flags_give_the_write_effect(flags):
    cap = native_to_contract(native(**flags), "imagemagick-skill")["capabilities"][0]
    assert "write" in cap["effects"]

@pytest.mark.parametrize("flags", [{}, {"writes_output": False}, {"produces_artifact": False}])
def test_tools_that_do_not_write_stay_read_only(flags):
    cap = native_to_contract(native(**flags), "imagemagick-skill")["capabilities"][0]
    assert "write" not in cap["effects"]
