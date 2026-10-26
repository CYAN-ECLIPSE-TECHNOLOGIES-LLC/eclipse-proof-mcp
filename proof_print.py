#!/usr/bin/env python3
# Eclipse Proof MCP
# Copyright © 2026 Cyan Eclipse Technologies LLC · cetech.ai
"""Eclipse Proof Print — render verifier (Tool, §12). Separate from Proof
core and Proof Trace. Offline, editor-free. Verdicts: RENDER_VERIFIED |
RENDER_MISMATCH only. TEXT_VERBATIM fail-closed on low extraction
confidence. Usage: proof_print.py '<json {render_ref, approval_id?,
state_dir?, delivery_spec_id, ocr_text?, ocr_confidence?}>'"""
import hashlib, json, os, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from proof_engine import DELIVERY_SPECS, BRAND, canon

def verify(render_ref, approval=None, delivery_spec_id="SOCIAL_SHORTFORM_V1",
           ocr_text=None, ocr_confidence=None, preset=None):
    checks = []
    def chk(cid, exp, meas, ok, note=""):
        checks.append({"check_id": cid, "expected": exp, "measured": meas,
                       "result": "pass" if ok else "fail", **({"note": note} if note else {})})
    if approval is None:
        pack = {"pack_id": "vpack_" + uuid.uuid4().hex[:10], "refusal_code": "NO_APPROVAL_RECORD",
                "verdict": "RENDER_MISMATCH", "checks": [{"check_id": "APPROVAL_RECORD",
                "expected": "approval record", "measured": None, "result": "fail",
                "note": "NO_APPROVAL_RECORD — manual export, correct statement not an error"}],
                "issued_by": "PROOF_PRINT", "issued_at": int(time.time()), "brand": BRAND}
        return pack
    raw = open(render_ref, "rb").read()
    render = json.loads(raw)
    chk("FILE_HASH", render.get("render_hash"), hashlib.sha256(
        canon({k: v for k, v in render.items() if k != "render_hash"})).hexdigest()
        if render.get("render_hash") else hashlib.sha256(raw).hexdigest(),
        bool(render.get("render_hash")) and render["render_hash"] == hashlib.sha256(
            canon({k: v for k, v in render.items() if k != "render_hash"})).hexdigest())
    exp_dur = approval["duration_frames"]
    chk("DURATION", exp_dur, render.get("duration_frames"),
        abs((render.get("duration_frames") or -999) - exp_dur) <= 1)
    # TEXT_VERBATIM
    expected_texts = approval.get("approved_texts", [])
    if render.get("text_track") is not None:
        meas, ok, note = render["text_track"], render["text_track"] == expected_texts, "embedded text track"
    elif ocr_text is not None:
        if ocr_confidence is None or ocr_confidence < 0.85:
            meas, ok, note = None, False, "TEXT_EXTRACTION_LOW_CONFIDENCE"
        else:
            meas, ok, note = ocr_text, ocr_text == expected_texts, "ocr"
    else:
        meas, ok, note = None, False, "TEXT_EXTRACTION_LOW_CONFIDENCE"
    chk("TEXT_VERBATIM", expected_texts, meas, ok, note)
    if note == "TEXT_EXTRACTION_LOW_CONFIDENCE":
        checks[-1]["failure_code"] = "TEXT_EXTRACTION_LOW_CONFIDENCE"
    chk("TEMPLATE_PRESENCE", approval.get("template_instance_ids", []), render.get("template_markers", []),
        set(approval.get("template_instance_ids", [])) <= set(render.get("template_markers", [])))
    spec = DELIVERY_SPECS[delivery_spec_id]
    meas_l = render.get("loudness_lufs")
    chk("LOUDNESS", f"{spec['lufs']}±{spec['tol']} TP<={spec['tp']}", meas_l,
        meas_l is not None and abs(meas_l - spec["lufs"]) <= spec["tol"] and render.get("true_peak_dbtp", 99) <= spec["tp"])
    if preset:
        exp_f = {"container": preset["container"], "codec": preset["codec"], "width": preset["width"],
                 "height": preset["height"], "fps_rational": preset["fps_rational"]}
        meas_f = {k: render.get(k) for k in exp_f}
        chk("FORMAT", exp_f, meas_f, exp_f == meas_f)
    verdict = "RENDER_VERIFIED" if all(c["result"] == "pass" for c in checks) else "RENDER_MISMATCH"
    return {"pack_id": "vpack_" + uuid.uuid4().hex[:10], "approval_id": approval.get("approval_id"),
            "fingerprint": approval.get("fingerprint"), "coverage_version": approval.get("coverage_version"),
            "render_hash": render.get("render_hash"), "checks": checks, "verdict": verdict,
            "issued_by": "PROOF_PRINT", "issued_at": int(time.time()), "brand": BRAND}

def main():
    args = json.loads(sys.argv[1])
    approval = preset = None
    if args.get("approval_id") and args.get("state_dir"):
        st = json.load(open(os.path.join(args["state_dir"], "state.json")))
        approval = dict(st["approvals"][args["approval_id"]])
        canon_dec = approval.get("canonical", {}).get("decisions", [])
        texts = [d["text"] for d in sorted((x for x in canon_dec if x["decision_class"] == "text_content"),
                 key=lambda x: (x["track_index"], x["start_frame"], x["decision_id"]))]
        for d in canon_dec:
            if d["decision_class"] == "template_instances":
                for k in sorted(d.get("slot_values", {})):
                    if isinstance(d["slot_values"][k], str): texts.append(d["slot_values"][k])
        approval["approved_texts"] = texts
        preset = st["presets"].get(approval["preset_id"])
        pack = verify(args["render_ref"], approval, args.get("delivery_spec_id", "SOCIAL_SHORTFORM_V1"),
                      args.get("ocr_text"), args.get("ocr_confidence"), preset)
        st.setdefault("verification_packs", []).append(pack)
        json.dump(st, open(os.path.join(args["state_dir"], "state.json"), "w"), indent=1)
    else:
        pack = verify(args["render_ref"], None)
    print(json.dumps(pack, indent=1))

if __name__ == "__main__": main()
# Eclipse Proof MCP · © 2026 Cyan Eclipse Technologies LLC · cetech.ai
