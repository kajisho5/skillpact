"""Render compiled configs in each harness's native file format and validate them against the harness's published schema.
Schemas in harness_schemas/ (fetched 2026-10-21): Claude Code settings (SchemaStore), Codex config (developers.openai.com),
Gemini CLI settings (google-gemini/gemini-cli). Gemini policy TOML and Cursor cli-config have no published JSON Schema:
we validate them against schemas transcribed from their documentation (marked 'doc-derived')."""
from __future__ import annotations
import json, tomllib
from pathlib import Path
from jsonschema import Draft7Validator, Draft202012Validator

HS = Path(__file__).parent / "harness_schemas"
DOC_DERIVED = {
    "gemini-cli-policy": {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Gemini CLI policy TOML (doc-derived: geminicli.com/docs/reference/policy-engine)",
        "type": "object", "additionalProperties": False, "properties": {"rule": {"type": "array", "items": {"type": "object", "additionalProperties": False,
        "required": ["toolName", "decision"], "properties": {"toolName": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}, "mcpName": {"type": "string"}, "commandPrefix": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
        "commandRegex": {"type": "string"}, "argsPattern": {"type": "string"}, "decision": {"enum": ["allow", "deny", "ask_user"]},
        "priority": {"type": "integer", "minimum": 0, "maximum": 999}, "denyMessage": {"type": "string"}, "allowRedirection": {"type": "boolean"}, "interactive": {"type": "boolean"}, "modes": {"type": "array"}}}}}},
    "cursor-cli-config": {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Cursor CLI permissions (doc-derived: cursor.com/docs/cli/reference/permissions)",
        "type": "object", "required": ["version", "permissions"], "properties": {"version": {"const": 1}, "permissions": {"type": "object", "additionalProperties": False,
        "required": ["allow", "deny"], "properties": {k: {"type": "array", "items": {"type": "string", "pattern": r"^(Shell|Read|Write|WebFetch|Mcp)\([^)]+\)$"}} for k in ("allow", "deny")}}}},
}


def _toml_val(v):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, str): return json.dumps(v)
    if isinstance(v, list): return "[" + ", ".join(_toml_val(x) for x in v) + "]"
    raise TypeError(v)


def to_toml(d: dict) -> str:
    lines, tables, arrays = [], [], []
    for k, v in d.items():
        if isinstance(v, dict): tables.append((k, v))
        elif isinstance(v, list) and v and isinstance(v[0], dict): arrays.append((k, v))
        else: lines.append(f"{k} = {_toml_val(v)}")
    for k, v in tables:
        lines += ["", f"[{k}]"] + [f"{a} = {_toml_val(b)}" for a, b in v.items()]
    for k, items in arrays:
        for it in items: lines += ["", f"[[{k}]]"] + [f"{a} = {_toml_val(b)}" for a, b in it.items()]
    return "\n".join(lines) + "\n"


def render(target, cfg) -> tuple[str, str]:
    """-> (filename, text)"""
    if target == "claude-code": return ".claude/settings.json", json.dumps(cfg, indent=2) + "\n"
    if target == "cursor": return ".cursor/cli.json", json.dumps(cfg, indent=2) + "\n"
    if target == "codex": return ".codex/config.toml", to_toml(cfg)
    if target == "gemini-cli": return ".gemini/policies/skillpact.toml", to_toml(cfg)
    raise ValueError(target)


def validate_native(target, text) -> list[str]:
    if target == "claude-code": data, sch, V = json.loads(text), json.loads((HS / "claude-code-settings.schema.json").read_text()), Draft7Validator
    elif target == "codex": data, sch, V = tomllib.loads(text), json.loads((HS / "codex-config.schema.json").read_text()), Draft7Validator
    elif target == "gemini-cli": data, sch, V = tomllib.loads(text), DOC_DERIVED["gemini-cli-policy"], Draft202012Validator
    elif target == "cursor": data, sch, V = json.loads(text), DOC_DERIVED["cursor-cli-config"], Draft202012Validator
    else: raise ValueError(target)
    return [f"{'/'.join(map(str, e.path))}: {e.message}" for e in V(sch).iter_errors(data)]
