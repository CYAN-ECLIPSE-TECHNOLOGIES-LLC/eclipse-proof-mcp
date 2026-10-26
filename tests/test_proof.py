#!/usr/bin/env python3
# Eclipse Proof MCP
# Copyright © 2026 Cyan Eclipse Technologies LLC · cetech.ai
"""Regression suite — replicates bench shapes byte-for-byte (DT/FT/HS/PV/TR ids)."""
import json, os, subprocess, sys, tempfile, unittest
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from proof_engine import ProofCore, Refusal, coerce_int_param, parse_time
import signing, proof_print, proof_trace

LIC = {"source": "catalog", "license_class": "PUBLIC_DOMAIN", "scope": "export", "expiry": "2030-01-01"}
PRESET = {"preset_id": "REEL_916_V1", "editor_class": "Resolve", "container": "mp4", "codec": "h264",
          "width": 1080, "height": 1920, "fps_rational": "30/1", "audio_spec_ref": "SOCIAL_SHORTFORM_V1",
          "embed_text_track": True}
SCHEMA = {"slots": [{"slot_id": "title", "type": "TEXT(90)", "required": True},
                    {"slot_id": "call", "type": "TEXT(120)", "required": True},
                    {"slot_id": "date", "type": "TEXT(30)", "required": False}]}

def run_op(state, keyf, cmd, args):
    env = dict(os.environ, ECLIPSE_PROOF_STATE=state, ECLIPSE_PROOF_HERALD_KEY_FILE=keyf)
    r = subprocess.run([sys.executable, os.path.join(BASE, "proof_operator.py"), cmd, json.dumps(args)],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)

class Setup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d, pt = signing.generate_keypair()
        self.keyf = os.path.join(self.tmp, "herald.json"); json.dump({"private_int": self.d}, open(self.keyf, "w"))
        self.pub = signing.public_key_pem(pt)
        self.core = ProofCore(self.tmp, self.pub)
        run_op(self.tmp, self.keyf, "register_preset", PRESET)
        self.tmpl = run_op(self.tmp, self.keyf, "register_template",
            {"artifact_path": os.path.join(BASE, "fixtures/HOUSE_REEL_V1.template"),
             "slot_schema": SCHEMA, "name": "HOUSE_REEL_V1"})
        self.core = ProofCore(self.tmp, self.pub)
        o = self.core.project_open("Resolve", "dogfood/ep1"); self.sid = o["session_id"]
    def build(self, text="BTC below $80,000 by Oct 28"):
        m = self.core.media_import(self.sid, "pd/clip1.mp4", LIC)
        self.core.clip_place(self.sid, "main", m["media_id"], 1, 0, 0, 300)
        t = self.core.text_set(self.sid, "main", 2, "NEW", text, 0, 300)
        inst = self.core.template_instantiate(self.sid, "main", self.tmpl["template_hash"], 3, 270,
            {"title": "The Call", "call": text, "date": "Oct 28"})
        return m, t, inst
    def approve(self):
        a = self.core.approval_request(self.sid, "main", "REEL_916_V1")
        run_op(self.tmp, self.keyf, "sign_approval", {"approval_id": a["approval_id"]})
        self.core = ProofCore(self.tmp, self.pub); return a["approval_id"]

class T(Setup):
    def test_ft1_stability(self):
        self.build(); fps = {self.core.timeline_fingerprint(self.sid, "main")["fingerprint"] for _ in range(20)}
        self.assertEqual(len(fps), 1)
    def test_ft3_text_1char_changes_hash(self):
        self.build(); h1 = self.core.timeline_fingerprint(self.sid, "main")["fingerprint"]
        tl = self.core.timeline_read(self.sid, "main")
        tid = [d for d in tl["decisions"] if d["decision_class"] == "text_content"][0]["decision_id"]
        self.core.text_set(self.sid, "main", 2, tid, "BTC below $80,000 by Oct 29", 0, 300)
        self.assertNotEqual(h1, self.core.timeline_fingerprint(self.sid, "main")["fingerprint"])
    def test_guards(self):
        self.assertEqual(coerce_int_param("42", "x"), 42)
        with self.assertRaises(Refusal): coerce_int_param(True, "x")
        with self.assertRaises(Refusal): parse_time(1.5)
        self.assertEqual(parse_time("00:00:10:15"), 315)
    def test_dt1_caption_drift_refuses(self):
        self.build(); aid = self.approve()
        tl = self.core.timeline_read(self.sid, "main")
        tid = [d for d in tl["decisions"] if d["decision_class"] == "text_content"][0]["decision_id"]
        self.core.text_set(self.sid, "main", 2, tid, "changed caption", 0, 300)
        with self.assertRaises(Refusal) as cm: self.core.export_execute(self.sid, aid)
        self.assertEqual(cm.exception.code, "TIMELINE_CHANGED_SINCE_APPROVAL")
        self.assertEqual(cm.exception.drift["changes"][0]["decision_class"], "text_content")
        self.assertIn("caption", cm.exception.drift["changes"][0]["track_named"])
        self.assertNotIn("current_text", json.dumps(cm.exception.drift))  # agent copy: hashes only
    def test_hs1_no_approval(self):
        self.build()
        with self.assertRaises(Refusal) as cm: self.core.export_execute(self.sid, "appr_nope")
        self.assertEqual(cm.exception.code, "APPROVAL_NOT_FOUND")
    def test_hs6_license_unknown(self):
        m = self.core.media_import(self.sid, "x.mp4", {"source": "c", "license_class": "UNKNOWN", "scope": "export", "expiry": "2030-01-01"})
        self.core.clip_place(self.sid, "main", m["media_id"], 1, 0, 0, 90)
        aid = self.approve()
        with self.assertRaises(Refusal) as cm: self.core.export_execute(self.sid, aid)
        self.assertEqual(cm.exception.code, "LICENSE_STATE_UNKNOWN"); self.assertIn(m["media_id"], cm.exception.detail)
    def test_hs7_silent_fail(self):
        with self.assertRaises(Refusal) as cm:
            self.core.media_import(self.sid, "silent-fail/clip.mp4", LIC)
        self.assertEqual(cm.exception.code, "ADAPTER_MUTATION_UNVERIFIED")
        self.assertTrue(self.core.state["friction"])
    def test_hs10_slot_smuggling(self):
        self.build()
        with self.assertRaises(Refusal) as cm:
            self.core.template_instantiate(self.sid, "main", self.tmpl["template_hash"], 3, 0,
                {"title": "x" * 200, "call": "y"})
        self.assertEqual(cm.exception.code, "TEMPLATE_SLOT_SCHEMA_VIOLATION")
    def test_happy_export_and_print(self):
        self.build(); aid = self.approve()
        out = self.core.export_execute(self.sid, aid)
        st = json.load(open(os.path.join(self.tmp, "state.json")))
        appr = dict(st["approvals"][aid]); appr["approved_texts"] = ["BTC below $80,000 by Oct 28", "BTC below $80,000 by Oct 28", "Oct 28", "The Call"]
        # approved_texts order: text items then template slot values sorted by slot key (call,date,title)
        appr["approved_texts"] = ["BTC below $80,000 by Oct 28", "BTC below $80,000 by Oct 28", "Oct 28", "The Call"]
        pack = proof_print.verify(out["render_ref"], appr, preset=PRESET)
        self.assertEqual(pack["verdict"], "RENDER_VERIFIED", pack)
    def test_print_no_approval(self):
        self.build(); aid = self.approve(); out = self.core.export_execute(self.sid, aid)
        pack = proof_print.verify(out["render_ref"], None)
        self.assertEqual(pack["refusal_code"], "NO_APPROVAL_RECORD")
    def test_fuzz_schema_enumerating(self):
        # every agent tool with valid-context wrong-typed params -> named refusal, no crash
        bad = [dict(session_id=123), dict(session_id=None), dict(session_id={"x": 1})]
        for b in bad:
            with self.assertRaises(Refusal): self.core.project_attest(b["session_id"])
    def test_trace_fcpXML(self):
        p = os.path.join(self.tmp, "a.fcpxml")
        open(p, "w").write('<fcpxml><asset-clip name="c1" start="0s" duration="10s"/></fcpxml>')
        f1 = proof_trace.fingerprint_fcpXML(p); f2 = proof_trace.fingerprint_fcpXML(p)
        self.assertEqual(f1["fingerprint"], f2["fingerprint"]); self.assertIn("DETECTIVE ONLY", f1["label"])

if __name__ == "__main__": unittest.main()
# Eclipse Proof MCP · © 2026 Cyan Eclipse Technologies LLC · cetech.ai
