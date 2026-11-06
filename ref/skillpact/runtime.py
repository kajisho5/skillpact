"""Runtime declarations (erratum 0.8.x, optional; ECOSYSTEM_ROADMAP.md step 5): the progress events an op emits and the
class of every error code it returns, under `x.runtime` (contract) and `capabilities[].x.runtime` (per op, overriding
the contract key by key). No schema change: `x` is the extension space, and a contract without `x.runtime` gets no
finding (optional now; proposed as recommended for 0.9).

  validate   x.runtime against runtime_schema.json; a code mapped to two classes; -> RUNTIME_DECL (error)
  run        per test case, with its capability's effective declaration:
               progress  every JSON line `{"event": "progress", ...}` on the declared stream must match the event schema
                         (step, percent 0-100 or null, eta_s >= 0 or null), name a declared step, and percent must never
                         decrease -> PROGRESS_EVENT; a case tagged `progress` must emit at least one -> PROGRESS_MISSING
               errors    an error code found in the JSON result on stdout (code_path, default error.code) must have a
                         class -> ERROR_UNCLASSIFIED
  declares   what a contract declares, for `conformance` and the Action (the OS weekly run reports it)"""
from __future__ import annotations
import json, re
from pathlib import Path
from jsonschema import Draft202012Validator

SCHEMA = json.loads((Path(__file__).parent / "runtime_schema.json").read_text())
CLASSES = tuple(SCHEMA["$defs"]["class"]["enum"])
DEFAULT_CODE_PATH = "error.code"
PROGRESS_TAG = "progress"


def _validator(name):
    return Draft202012Validator({**{k: SCHEMA[k] for k in ("$schema", "$defs")}, "$ref": f"#/$defs/{name}"})


_CONTRACT, _CAPABILITY, _EVENT = _validator("contract"), _validator("capability"), _validator("event")


def _decl(obj):
    x = obj.get("x") if isinstance(obj, dict) else None
    return x.get("runtime") if isinstance(x, dict) and "runtime" in x else None


def validate(c, r) -> None:
    """Adds RUNTIME_DECL findings to the validator Report `r`."""
    top = _decl(c)
    if top is not None:
        for e in sorted(_CONTRACT.iter_errors(top), key=lambda e: list(e.path)):
            r.err("RUNTIME_DECL", f"x.runtime: {e.message}", "/x/runtime" + "".join(f"/{p}" for p in e.path))
    top_classes = ((top or {}).get("errors") or {}).get("classes") if isinstance(top, dict) else None
    for i, cap in enumerate(c.get("capabilities", [])):
        d = _decl(cap)
        if d is None: continue
        w = f"/capabilities/{i}/x/runtime"
        errs = sorted(_CAPABILITY.iter_errors(d), key=lambda e: list(e.path))
        for e in errs: r.err("RUNTIME_DECL", f"{cap.get('id')}: x.runtime: {e.message}", w + "".join(f"/{p}" for p in e.path))
        if errs or not isinstance(top_classes, dict): continue
        for code, cls in ((d.get("errors") or {}).get("classes") or {}).items():
            if code in top_classes and top_classes[code] != cls:
                r.err("RUNTIME_DECL", f"{cap.get('id')}: error code {code} is {cls!r} here but {top_classes[code]!r} in x.runtime.errors", w + "/errors/classes")


def effective(c, cap) -> dict:
    """The declaration that applies to one capability: the contract's, with the capability's keys on top. An error
    class map is merged (the capability adds codes); `progress: false` removes the contract's progress."""
    top = _decl(c) if isinstance(_decl(c), dict) else {}
    own = _decl(cap) if isinstance(_decl(cap), dict) else {}
    out = {}
    progress = own.get("progress", top.get("progress"))
    if isinstance(progress, dict): out["progress"] = progress
    te, oe = top.get("errors") or {}, own.get("errors") or {}
    if te or oe:
        out["errors"] = {"code_path": oe.get("code_path") or te.get("code_path") or DEFAULT_CODE_PATH,
                         "classes": {**(te.get("classes") or {}), **(oe.get("classes") or {})}}
    return out


def _events(text):
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s.startswith("{"): continue
        try: obj = json.loads(s)
        except ValueError: continue
        if isinstance(obj, dict) and obj.get("event") == "progress": out.append((n, obj))
    return out


def _result_json(out):
    """The JSON result on stdout: the whole of it, or else its last top-level JSON value (log lines before it)."""
    try: return json.loads(out)
    except ValueError: pass
    data, dec = None, json.JSONDecoder()
    for m in re.finditer(r"(?m)^[{\[]", out):
        try: data = dec.raw_decode(out, m.start())[0]
        except ValueError: pass
    return data


def _at(data, path):
    for part in path.split("."):
        if isinstance(data, dict) and part in data: data = data[part]
        else: return None
    return data


def check_case(decl, out, err, tags=()) -> tuple[list, dict]:
    """(failures, facts for the case result) for one finished case under its effective declaration."""
    fails, info = [], {}
    progress = decl.get("progress")
    if progress:
        events = _events(err if progress["stream"] == "stderr" else out)
        steps, last = progress.get("steps"), None
        for n, ev in events:
            problems = [e.message for e in _EVENT.iter_errors(ev)]
            if not problems and steps and ev["step"] not in steps: problems.append(f"step {ev['step']!r} is not one of {steps}")
            pct = ev.get("percent")
            if not problems and isinstance(pct, (int, float)):
                if last is not None and pct < last: problems.append(f"percent went down from {last} to {pct}")
                last = pct
            if problems: fails.append(f"PROGRESS_EVENT: {progress['stream']} line {n}: " + "; ".join(problems))
        info["progress_events"] = len(events)
        if PROGRESS_TAG in (tags or ()) and not events:
            fails.append(f"PROGRESS_MISSING: the case is tagged {PROGRESS_TAG!r} but no progress event was emitted on {progress['stream']}")
    errors = decl.get("errors")
    if errors:
        code = _at(_result_json(out), errors["code_path"])
        if isinstance(code, str):
            cls = errors["classes"].get(code)
            info["error_code"], info["error_class"] = code, cls
            if cls is None: fails.append(f"ERROR_UNCLASSIFIED: error code {code!r} (at {errors['code_path']}) has no class in x.runtime.errors.classes")
    return fails, info


def declares(c) -> dict:
    """What the contract declares (step 5), for the conformance report and the Action's `declares` output."""
    caps = c.get("capabilities", [])
    eff = [effective(c, cap) for cap in caps]
    codes = {}
    for e in eff: codes.update((e.get("errors") or {}).get("classes") or {})
    return {"capabilities": len(caps), "progress": sorted(cap["id"] for cap, e in zip(caps, eff) if e.get("progress")),
            "error_classes": dict(sorted(codes.items()))}
