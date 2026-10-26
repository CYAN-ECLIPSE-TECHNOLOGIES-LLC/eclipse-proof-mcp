#!/usr/bin/env python3
# Eclipse Proof MCP
# Copyright © 2026 Cyan Eclipse Technologies LLC · cetech.ai
"""Smoke: real stdio MCP — tools/list == 15, unknown -> SURFACE_TOOL_UNKNOWN,
project_open + fingerprint round-trip. Run: python3 smoke.py"""
import json, os, subprocess, sys, tempfile
BASE = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp()
env = dict(os.environ, ECLIPSE_PROOF_STATE=tmp)
p = subprocess.Popen([sys.executable, os.path.join(BASE, "server.py")], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, text=True, env=env)
def rpc(i, m, params=None):
    p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": i, "method": m, "params": params or {}}) + "\n"); p.stdin.flush()
    return json.loads(p.stdout.readline())
rpc(1, "initialize")
tools = rpc(2, "tools/list")["result"]["tools"]
assert len(tools) == 15, len(tools)
unk = rpc(3, "tools/call", {"name": "eval_code", "arguments": {}})["result"]["content"][0]["text"]
assert json.loads(unk)["refusal_code"] == "SURFACE_TOOL_UNKNOWN", unk
op = rpc(4, "tools/call", {"name": "op_approval_sign", "arguments": {}})["result"]["content"][0]["text"]
assert json.loads(op) == json.loads(unk), (op, unk)  # byte-identical unknown shape, no oracle
o = json.loads(rpc(5, "tools/call", {"name": "project_open", "arguments":
    {"editor_class": "Resolve", "project_ref": "smoke/ep"}})["result"]["content"][0]["text"])
assert o["session_id"].startswith("sess_"), o
p.terminate(); print("SMOKE OK: 15 tools, unknown/op names byte-identical SURFACE_TOOL_UNKNOWN, session opened")
# Eclipse Proof MCP · © 2026 Cyan Eclipse Technologies LLC · cetech.ai
