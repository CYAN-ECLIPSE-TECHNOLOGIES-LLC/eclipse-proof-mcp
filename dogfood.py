#!/usr/bin/env python3
# Eclipse Proof MCP
# Copyright © 2026 Cyan Eclipse Technologies LLC · cetech.ai
"""Dogfood (§14.2): White Report reel under pinned HOUSE_REEL_V1.
Assembly (PD clip + VO + caption text verbatim + payoff template) ->
approval_request (REEL_916_V1 / SOCIAL_SHORTFORM_V1) -> Herald sign
(operator process, replaces chat approval inside pipeline) ->
export_execute -> Proof Print -> session_close ProductionPack.
Evidence written to dogfood_output/. Simulated Resolve adapter + simulated
render (no Studio seat on this VM) — pack states that honestly."""
import json, os, subprocess, sys
BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
STATE = os.path.join(BASE, "dogfood_state"); OUT = os.path.join(BASE, "dogfood_output")
os.makedirs(OUT, exist_ok=True)
KEYF = os.path.join(BASE, "keys", "herald-key.local.json")
if not os.path.exists(KEYF): subprocess.run([sys.executable, os.path.join(BASE, "tools/make_keys.py")], check=True)
os.environ["ECLIPSE_PROOF_STATE"] = STATE
from proof_engine import ProofCore
LIC_PD = {"source": "catalog:public-domain-archive", "license_class": "PUBLIC_DOMAIN", "scope": "export", "expiry": "2030-01-01"}
LIC_MUS = {"source": "catalog:house-music", "license_class": "LICENSED", "scope": "export", "expiry": "2027-01-01"}
SCHEMA = {"slots": [{"slot_id": "title", "type": "TEXT(90)", "required": True},
                    {"slot_id": "call", "type": "TEXT(120)", "required": True},
                    {"slot_id": "date", "type": "TEXT(30)", "required": False}]}
def op(cmd, args):
    env = dict(os.environ, ECLIPSE_PROOF_STATE=STATE, ECLIPSE_PROOF_HERALD_KEY_FILE=KEYF)
    r = subprocess.run([sys.executable, os.path.join(BASE, "proof_operator.py"), cmd, json.dumps(args)],
                       capture_output=True, text=True, env=env); assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)
pub = open(os.path.join(BASE, "herald_pubkey.pem")).read()
preset = op("register_preset", {"preset_id": "REEL_916_V1", "editor_class": "Resolve", "container": "mp4",
    "codec": "h264", "width": 1080, "height": 1920, "fps_rational": "30/1",
    "audio_spec_ref": "SOCIAL_SHORTFORM_V1", "embed_text_track": True})
tmpl = op("register_template", {"artifact_path": os.path.join(BASE, "fixtures/HOUSE_REEL_V1.template"),
    "slot_schema": SCHEMA, "name": "HOUSE_REEL_V1"})
core = ProofCore(STATE, pub)
o = core.project_open("Resolve", "white-report/ep-dogfood"); sid = o["session_id"]
call_text = "BTC below $80,000 by Oct 28"
clip = core.media_import(sid, "pd/powell-hearing-clip.mp4", LIC_PD)
music = core.media_import(sid, "catalog/house-music-bed.mp3", LIC_MUS)
core.clip_place(sid, "main", clip["media_id"], 1, 0, 0, 900)
core.text_set(sid, "main", 2, "NEW", call_text, 0, 900)
core.text_set(sid, "main", 2, "NEW", "Powell: we will assess the data carefully.", 30, 300)
core.template_instantiate(sid, "main", tmpl["template_hash"], 3, 810,
    {"title": "The Call", "call": call_text, "date": "Oct 28"})
core.marker_set(sid, "main", 810, "payoff_card", {})
appr = core.approval_request(sid, "main", "REEL_916_V1")
signed = op("sign_approval", {"approval_id": appr["approval_id"], "principal": "herald-owner"})
core = ProofCore(STATE, pub)
exp = core.export_execute(sid, appr["approval_id"])
env = dict(os.environ)
r = subprocess.run([sys.executable, os.path.join(BASE, "proof_print.py"), json.dumps(
    {"render_ref": exp["render_ref"], "approval_id": appr["approval_id"], "state_dir": STATE,
     "delivery_spec_id": "SOCIAL_SHORTFORM_V1"})], capture_output=True, text=True, env=env)
assert r.returncode == 0, r.stderr
vpack = json.loads(r.stdout)
core = ProofCore(STATE, pub)
sealed = core.session_close(sid)
evidence = {"episode": "white-report-dogfood-ep", "template_pin": tmpl["template_hash"],
            "preset_hash": preset["preset_hash"], "fingerprint": appr["fingerprint"],
            "coverage_version": "RESOLVE_COV_V1", "approval_id": appr["approval_id"],
            "render_hash": exp["render_hash"], "verification_verdict": vpack["verdict"],
            "verification_pack": vpack["pack_id"], "production_pack": sealed["pack_hash"],
            "adapter": "resolve-sim (simulated render — no Studio seat on VM; LIVE claim NOT made)",
            "posting": "UNCHANGED rails (IG first, then Connect->YouTube) — Proof hands off verified file+pack only"}
json.dump(evidence, open(os.path.join(OUT, "dogfood-evidence.json"), "w"), indent=1)
json.dump(vpack, open(os.path.join(OUT, "verification-pack.json"), "w"), indent=1)
print(json.dumps(evidence, indent=1))
assert vpack["verdict"] == "RENDER_VERIFIED", vpack
print("DOGFOOD OK")
# Eclipse Proof MCP · © 2026 Cyan Eclipse Technologies LLC · cetech.ai
