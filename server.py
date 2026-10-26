#!/usr/bin/env python3
# Eclipse Proof MCP
# Copyright © 2026 Cyan Eclipse Technologies LLC · cetech.ai
"""Eclipse Proof MCP server (stdio, stdlib). Agent surface = 15 tools ONLY.
Operator surface is DISJOINT: proof_operator.py process, Herald key held
there, never here. Unknown tool name -> SURFACE_TOOL_UNKNOWN, byte-identical
shape for ANY unknown name (no oracle re operator surface, spec §5).
NO code-exec tool exists (house T3)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from proof_engine import ProofCore, Refusal, AGENT_TOOLS, deep_key_scan, BRAND

STATE = os.environ.get("ECLIPSE_PROOF_STATE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
PUB = os.environ.get("ECLIPSE_PROOF_HERALD_PUBKEY") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "herald_pubkey.pem")
core = ProofCore(STATE, open(PUB).read() if os.path.exists(PUB) else None)

SCHEMAS = {
 "project_open": {"editor_class": "str", "project_ref": "str"},
 "project_attest": {"session_id": "str"}, "timeline_read": {"session_id": "str", "timeline_id": "str"},
 "timeline_fingerprint": {"session_id": "str", "timeline_id": "str"},
 "export_presets_list": {"session_id": "str"}, "template_list": {"session_id": "str", "editor_class": "str"},
 "media_import": {"session_id": "str", "source_ref": "str", "license_state": "dict?"},
 "clip_place": {"session_id": "str", "timeline_id": "str", "media_id": "str", "track_index": "int", "start_frame": "int", "source_in": "int", "source_out": "int"},
 "clip_trim": {"session_id": "str", "timeline_id": "str", "clip_ref": "str", "source_in": "int", "source_out": "int", "start_frame": "int"},
 "text_set": {"session_id": "str", "timeline_id": "str", "track_index": "int", "item_ref": "str", "text": "str", "start_frame": "int", "end_frame": "int"},
 "template_instantiate": {"session_id": "str", "timeline_id": "str", "template_hash": "str", "track_index": "int", "start_frame": "int", "slot_values": "dict"},
 "marker_set": {"session_id": "str", "timeline_id": "str", "frame": "int", "label": "str", "payload": "any"},
 "approval_request": {"session_id": "str", "timeline_id": "str", "preset_id": "str"},
 "export_execute": {"session_id": "str", "approval_id": "str"},
 "session_close": {"session_id": "str"},
}
TOOLS = [{"name": n, "description": f"Eclipse Proof {n} · {BRAND}",
          "inputSchema": {"type": "object", "properties": {k: {"type": "string"} for k in SCHEMAS[n]},
                          "required": [k for k, v in SCHEMAS[n].items() if not v.endswith("?")]}}
         for n in AGENT_TOOLS]

def dispatch(name, args):
    if name not in AGENT_TOOLS:
        return {"refusal_code": "SURFACE_TOOL_UNKNOWN", "detail": "", "brand": BRAND}
    deep_key_scan(args)
    core.reload_if_changed()
    fn = getattr(core, name)
    # only pass declared params; missing -> engine/Refusal via TypeError mapping
    kwargs = {k: args[k] for k in SCHEMAS[name] if k in args}
    missing = [k for k, v in SCHEMAS[name].items() if not v.endswith("?") and k not in kwargs]
    if missing: return {"refusal_code": "SCHEMA_MISSING_PARAM", "detail": ",".join(missing), "brand": BRAND}
    try:
        return fn(**kwargs)
    except Refusal as r:
        p = r.payload()
        if getattr(r, "stage", None): p["stage"] = r.stage
        return p

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try: req = json.loads(line)
        except Exception: continue
        method, rid = req.get("method"), req.get("id")
        if method == "initialize":
            res = {"protocolVersion": "2025-03-26", "serverInfo": {"name": "eclipse-proof", "version": "0.1.0"}, "capabilities": {"tools": {}}}
        elif method == "ping": res = {}
        elif method == "tools/list": res = {"tools": TOOLS}
        elif method == "tools/call":
            p = req.get("params", {})
            try: out = dispatch(p.get("name"), p.get("arguments") or {})
            except Refusal as r: out = r.payload()
            except Exception as e: out = {"refusal_code": "INTERNAL_GUARD", "detail": type(e).__name__, "brand": BRAND}
            res = {"content": [{"type": "text", "text": json.dumps(out)}], "isError": "refusal_code" in out}
        else:
            res = {}
        if rid is not None:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": res}) + "\n"); sys.stdout.flush()

if __name__ == "__main__": main()
# Eclipse Proof MCP · © 2026 Cyan Eclipse Technologies LLC · cetech.ai
