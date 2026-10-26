#!/usr/bin/env python3
# Eclipse Proof MCP
# Copyright © 2026 Cyan Eclipse Technologies LLC · cetech.ai
"""Eclipse Proof Trace — fingerprint/interchange kit (Tool, §12.4). Separate
from Proof core and Proof Print. P0: FCPXML only.
Every output carries: DETECTIVE ONLY — proves post-export match/mismatch vs
approved state; cannot prevent an in-app export."""
import json, sys, xml.etree.ElementTree as ET
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from proof_engine import canon, sha, ProofCore

LABEL = "DETECTIVE ONLY — proves post-export match/mismatch vs approved state; cannot prevent an in-app export."

def fingerprint_fcpXML(path):
    root = ET.parse(path).getroot()
    decisions = []
    for i, el in enumerate(root.iter()):
        tag = el.tag.split("}")[-1]
        if tag in ("asset-clip", "clip", "title"):
            name = el.get("name", f"item{i}")
            start = el.get("start", "0s"); dur = el.get("duration", "0s")
            def frames(v):
                v = v.rstrip("s")
                if "/" in v:
                    n, d = v.split("/"); return int(n) // int(d)
                return int(float(v) * 30)
            text = ""
            for t in el.iter():
                if t.tag.split("}")[-1] == "text" and t.text: text = t.text
            decisions.append({"decision_id": f"fcpx_{i}_{name}", "decision_class":
                "text_content" if tag == "title" or text else "clip_placement",
                "track_index": 0, "track_type": "V", "item_ref": name,
                "start_frame": frames(start), "end_frame": frames(start) + frames(dur),
                **({"text": text} if text else {})})
    c = {"coverage_version": "FCPXML_COV_V1", "timeline_id": "fcpxml", "fps_rational": "30/1",
         "tracks": [], "decisions": sorted(decisions, key=lambda d: (d["track_index"], d["start_frame"], d["decision_id"]))}
    return {"fingerprint": sha(canon(c)), "coverage_id": "FCPXML_COV_V1",
            "evidence_grade": "FILE_PARSE", "canonical": c, "label": LABEL}

def diff(a, b):
    core = ProofCore.__new__(ProofCore)
    return {**core.drift_report(a["canonical"], b["canonical"]), "label": LABEL}

if __name__ == "__main__":
    cmd, args = sys.argv[1], json.loads(sys.argv[2])
    if cmd == "fingerprint": print(json.dumps(fingerprint_fcpXML(args["file_ref"]), indent=1))
    elif cmd == "diff":
        print(json.dumps(diff(fingerprint_fcpXML(args["a"]), fingerprint_fcpXML(args["b"])), indent=1))
# Eclipse Proof MCP · © 2026 Cyan Eclipse Technologies LLC · cetech.ai
