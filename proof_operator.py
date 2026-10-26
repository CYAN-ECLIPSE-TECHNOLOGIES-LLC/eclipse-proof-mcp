#!/usr/bin/env python3
# Eclipse Proof MCP
# Copyright © 2026 Cyan Eclipse Technologies LLC · cetech.ai
"""Operator surface — DISJOINT process (spec §5.5). Human principals only.
Holds the Herald private key (env ECLIPSE_PROOF_HERALD_KEY_FILE or
keys/herald-key.local.json); the agent server never sees it.
Commands: register_template, retire_template, register_preset,
set_license, sign_approval, pack_read. Usage: proof_operator.py <cmd> '<json>'
"""
import base64, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from proof_engine import ProofCore, canon, sha
import signing

STATE = os.environ.get("ECLIPSE_PROOF_STATE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
KEYF = os.environ.get("ECLIPSE_PROOF_HERALD_KEY_FILE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys", "herald-key.local.json")

def core(): return ProofCore(STATE, None)
def priv():
    return json.load(open(KEYF))["private_int"]

def main():
    cmd, args = sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    c = core(); out = {}
    if cmd == "register_template":
        data = open(args["artifact_path"], "rb").read()
        th = sha(data + canon(args["slot_schema"]))
        rec = {"template_hash": th, "editor_class": args.get("editor_class", "Resolve"),
               "slot_schema": args["slot_schema"], "version": args.get("version", "1"),
               "name": args.get("name"), "signed_by": "herald",
               "herald_signature": base64.b64encode(signing.sign(priv(), canon({"template_hash": th}))).decode(),
               "source_kind": args.get("source_kind", "RESOLVE_PROJECT"), "registered_at": int(time.time()), "retired": False}
        open(os.path.join(STATE, "templates", th + ".bin"), "wb").write(data)
        c.state["templates"][th] = rec; c.save(); out = rec
    elif cmd == "retire_template":
        c.state["templates"][args["template_hash"]]["retired"] = True; c.save(); out = {"retired": args["template_hash"]}
    elif cmd == "register_preset":
        p = dict(args); p["preset_hash"] = sha(canon({k: args[k] for k in
            ("preset_id", "editor_class", "container", "codec", "width", "height", "fps_rational", "audio_spec_ref", "embed_text_track")}))
        c.state["presets"][p["preset_id"]] = p; c.save(); out = p
    elif cmd == "set_license":
        c.state["media"][args["media_id"]]["license_state"] = args["license_state"]; c.save(); out = c.state["media"][args["media_id"]]
    elif cmd == "sign_approval":
        rec = c.state["approvals"][args["approval_id"]]
        if rec["state"] != "REQUESTED": out = {"refusal_code": "APPROVAL_NOT_ACTIVE", "detail": rec["state"]}
        else:
            # supersede prior signed approvals for same timeline
            for other in c.state["approvals"].values():
                if other["approval_id"] != rec["approval_id"] and other.get("timeline_id") == rec["timeline_id"] and other["state"] == "SIGNED_PINNED":
                    other["state"] = "SUPERSEDED"
            rec["principal"] = args.get("principal", "herald-owner")
            rec["issued_at"] = int(time.time())
            rec["expires_at"] = rec["issued_at"] + int(args.get("ttl_seconds", 24 * 3600))
            rec["herald_signature"] = base64.b64encode(signing.sign(priv(), c.approval_bytes(rec))).decode()
            rec["state"] = "SIGNED_PINNED"; c.save(); out = {k: v for k, v in rec.items() if k != "canonical"}
    elif cmd == "pack_read":
        out = json.load(open(os.path.join(STATE, "packs", args["pack_id"] + ".json")))
    else:
        out = {"refusal_code": "OPERATOR_TOOL_UNKNOWN", "detail": cmd}
    print(json.dumps(out, indent=1))

if __name__ == "__main__": main()
# Eclipse Proof MCP · © 2026 Cyan Eclipse Technologies LLC · cetech.ai
