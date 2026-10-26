#!/usr/bin/env python3
# Eclipse Proof MCP
# Copyright © 2026 Cyan Eclipse Technologies LLC · cetech.ai
"""Eclipse Proof core engine — governed video production (spec 2026-10-25).

Novel mechanism (§1): export executes ONLY against a Herald-signed approval
pinning {project, canonical edit-decision fingerprint (RESOLVE_COV_V1,
integer-frame canonical JSON), export-preset hash, principal, expiry};
templates are hash-pinned signed artifacts filled by slots only; every
adapter mutation is read-back-verified (Resolve API fails SILENTLY — §7.2);
exported renders are independently verified by Proof Print.

P0 adapter: simulated in-process Resolve-shaped adapter (no Studio seat /
Resolve install on this VM — honest scope, README). Adapter seam mirrors
the external scripting API contract: mutations return True/False/None with
NO error channel; a source_ref under `silent-fail/` returns False (fixture
of the silent-failure class), and an external editor edit during render is
simulated by a `mid_render_edit.json` file in the state dir dropped by the
test/editor between gate check and render end (HS-11 shape).
NO code-exec tool exists on any surface (house T3, §9).
"""
import base64, hashlib, json, os, time, uuid
from fractions import Fraction

BRAND = "Eclipse Proof · Cyan Eclipse Technologies LLC · cetech.ai"
COVERAGE_VERSION = "RESOLVE_COV_V1"
COVERED = ["clip_placement", "text_content", "template_instances",
           "track_structure", "markers", "audio_structure"]
EXCLUDED = ["grade_node_internals", "fusion_node_graph_internals_beyond_template_pins",
            "per_effect_parameter_internals", "project_settings_not_in_preset"]
DELIVERY_SPECS = {
    "SOCIAL_SHORTFORM_V1": {"lufs": -14.0, "tol": 1.0, "tp": -1.0},
    "EBU_R128_V1": {"lufs": -23.0, "tol": 0.5, "tp": -1.0},
    "ATSC_A85_V1": {"lufs": -24.0, "tol": 2.0, "tp": -2.0},
}
FORBIDDEN_KEYS = {"eval", "exec", "code", "script", "run_script", "execute_code",
                  "private_key", "seed", "__proto__", "command", "shell"}

class Refusal(Exception):
    def __init__(self, code, detail="", drift=None):
        super().__init__(code); self.code = code; self.detail = detail; self.drift = drift
    def payload(self):
        p = {"refusal_code": self.code, "detail": self.detail, "brand": BRAND}
        if self.drift: p["drift_report"] = self.drift
        return p

# ---- house guards -------------------------------------------------------
def coerce_int_param(v, name):
    if isinstance(v, bool): raise Refusal("PARAM_INT_INVALID", name)
    if isinstance(v, int): return v
    if isinstance(v, str) and v.strip().lstrip("-").isdigit(): return int(v)
    raise Refusal("PARAM_INT_INVALID", name)

def parse_time(v, fps_num=30, fps_den=1, name="time"):
    """Integer frames only, or HH:MM:SS:FF string. Float seconds rejected."""
    if isinstance(v, (int, str)) and not isinstance(v, bool):
        if isinstance(v, int): return v
        if ":" in v:
            parts = v.split(":")
            if len(parts) != 4: raise Refusal("PARAM_TIME_INVALID", name)
            h, m, s, f = (coerce_int_param(x, name) for x in parts)
            return ((h * 3600 + m * 60 + s) * fps_num) // fps_den + f
        return coerce_int_param(v, name)
    raise Refusal("PARAM_TIME_INVALID", name)

def ref_str(v, name):
    if not isinstance(v, str) or not v: raise Refusal("REFERENCE_TYPE_INVALID", name)
    return v

def deep_key_scan(obj, path=""):
    if isinstance(obj, dict):
        for k, val in obj.items():
            if isinstance(k, str) and k.lower() in FORBIDDEN_KEYS:
                raise Refusal("SCHEMA_FORBIDDEN_KEY", f"{path}{k}")
            deep_key_scan(val, path + str(k) + ".")
    elif isinstance(obj, list):
        for i, val in enumerate(obj): deep_key_scan(val, f"{path}{i}.")

def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
def sha(b):
    if isinstance(b, str): b = b.encode("utf-8")
    return hashlib.sha256(b).hexdigest()

# ---- simulated Resolve adapter ------------------------------------------
class ResolveAdapter:
    """Resolve-shaped seam. Mutations return bool/None, NO error channel (§7.1/7.2)."""
    adapter_id = "resolve-sim"; adapter_version = "0.1.0"
    editor_class = "Resolve"; editor_version = "19.1-sim"
    def __init__(self, state):
        self.state = state  # projects: {project_id: {timelines:{tid:{...decisions}}}}
    def open_project(self, project_ref):
        if project_ref.startswith("missing"): return None
        pid = "proj_" + sha(project_ref)[:12]
        if pid not in self.state["projects"]:
            self.state["projects"][pid] = {
                "project_id": pid, "project_ref": project_ref,
                "identity_hash": sha("identity:" + project_ref),
                "timelines": {"main": {"timeline_id": "main", "fps_rational": "30/1",
                    "tracks": [{"track_index": 3, "type": "V", "locked": False, "muted": False},
                               {"track_index": 2, "type": "T", "locked": False, "muted": False},
                               {"track_index": 1, "type": "V", "locked": False, "muted": False},
                               {"track_index": 0, "type": "A", "locked": False, "muted": False}],
                    "decisions": []}}}
        return self.state["projects"][pid]
    def _silent(self, ref):
        return isinstance(ref, str) and "silent-fail" in ref
    def mutate(self, project, timeline_id, apply_fn, probe_ref=""):
        if self._silent(probe_ref): return False  # Resolve silent failure
        try: apply_fn(project["timelines"][timeline_id]); return True
        except Exception: return None
    def read_timeline(self, project, timeline_id):
        tl = project["timelines"].get(timeline_id)
        return json.loads(json.dumps(tl)) if tl else None
    def render(self, project, timeline_id, preset, state_dir):
        """Render to staging. External mid-render edit seam: mid_render_edit.json."""
        tl = self.read_timeline(project, timeline_id)
        hook = os.path.join(state_dir, "mid_render_edit.json")
        if os.path.exists(hook):
            edit = json.load(open(hook))
            for d in project["timelines"][timeline_id]["decisions"]:
                if d.get("decision_id") == edit.get("decision_id") and "text" in d:
                    d["text"] = edit.get("text", d["text"])
        decisions = tl["decisions"]
        texts = [d["text"] for d in sorted(
            (x for x in decisions if x["decision_class"] == "text_content"),
            key=lambda x: (x["track_index"], x["start_frame"], x["decision_id"]))]
        tmpl_texts = []
        for d in decisions:
            if d["decision_class"] == "template_instances":
                for k in sorted(d.get("slot_values", {})):
                    if isinstance(d["slot_values"][k], str): tmpl_texts.append(d["slot_values"][k])
        duration = max([d.get("end_frame", d.get("start_frame", 0)) for d in decisions], default=0)
        render = {"container": preset["container"], "codec": preset["codec"],
                  "width": preset["width"], "height": preset["height"],
                  "fps_rational": preset["fps_rational"], "duration_frames": duration,
                  "text_track": texts + tmpl_texts,
                  "template_markers": [d["decision_id"] for d in decisions
                                       if d["decision_class"] == "template_instances"],
                  "loudness_lufs": -14.0, "true_peak_dbtp": -1.2,
                  "simulated_render": True, "brand": BRAND}
        return render

# ---- core -----------------------------------------------------------------
class ProofCore:
    def __init__(self, state_dir, herald_pubkey_pem=None):
        self.dir = state_dir; os.makedirs(state_dir, exist_ok=True)
        for sub in ("renders", "templates", "packs"): os.makedirs(os.path.join(state_dir, sub), exist_ok=True)
        self.path = os.path.join(state_dir, "state.json")
        self.state = json.load(open(self.path)) if os.path.exists(self.path) else {
            "projects": {}, "sessions": {}, "media": {}, "templates": {}, "presets": {},
            "approvals": {}, "receipts": [], "friction": [], "packs": []}
        self.adapter = ResolveAdapter(self.state)
        try: self._mtime = os.path.getmtime(self.path)
        except OSError: self._mtime = None
        import signing
        self._signing = signing
        self.herald_point = None
        if herald_pubkey_pem:
            self.herald_point = signing.parse_public_key_pem(herald_pubkey_pem)
    def save(self):
        tmp = self.path + ".tmp"; json.dump(self.state, open(tmp, "w"), indent=1); os.replace(tmp, self.path)
        try: self._mtime = os.path.getmtime(self.path)
        except OSError: self._mtime = None
    def reload_if_changed(self):
        """Operator/Print are disjoint processes writing the same store;
        pick up their writes (signatures, packs) instead of serving stale state."""
        try: m = os.path.getmtime(self.path)
        except OSError: return
        if getattr(self, "_mtime", None) != m and os.path.exists(self.path):
            with open(self.path) as fh: self.state = json.load(fh)
            self.adapter.state = self.state; self._mtime = m
    def _chain(self, store, rec):
        prev = store[-1]["record_hash"] if store else "0" * 64
        rec = dict(rec); rec["seq"] = len(store) + 1; rec["prev_hash"] = prev
        rec["record_hash"] = sha(canon({k: v for k, v in rec.items() if k != "record_hash"}))
        store.append(rec); return rec
    def receipt(self, session_id, tool, code, detail=""):
        return self._chain(self.state["receipts"], {"kind": "refusal", "session_id": session_id,
                             "tool": tool, "refusal_code": code, "detail": detail, "at": int(time.time())})
    def friction(self, kind, detail):
        return self._chain(self.state["friction"], {"kind": "FRICTION_FINDING", "finding_class": kind,
                             "detail": detail, "filed_by": "eclipse-proof-adapter-law", "at": int(time.time())})
    # fingerprint / drift
    def canonical_timeline(self, project, timeline_id):
        tl = self.adapter.read_timeline(project, timeline_id)
        if tl is None: raise Refusal("TIMELINE_NOT_FOUND", timeline_id)
        decisions = sorted(tl["decisions"], key=lambda d: (d["track_index"], d["start_frame"], d["decision_id"]))
        return {"coverage_version": COVERAGE_VERSION, "timeline_id": timeline_id,
                "fps_rational": tl["fps_rational"], "tracks": tl["tracks"], "decisions": decisions}
    def fingerprint(self, project, timeline_id):
        c = self.canonical_timeline(project, timeline_id)
        return sha(canon(c)), c
    def drift_report(self, approved_canon, current_canon, agent_copy=True):
        a = {d["decision_id"]: d for d in approved_canon["decisions"]}
        b = {d["decision_id"]: d for d in current_canon["decisions"]}
        changes = []
        for did in sorted(set(a) | set(b)):
            if a.get(did) == b.get(did): continue
            src = b.get(did) or a.get(did)
            ch = {"decision_class": src["decision_class"], "track_index": src.get("track_index"),
                  "track_type": src.get("track_type"), "item_ref": did,
                  "field": "decision", "approved_hash": sha(canon(a[did])) if did in a else None,
                  "current_hash": sha(canon(b[did])) if did in b else None}
            if src["decision_class"] == "text_content":
                ch["track_named"] = f"caption/text track_index={src.get('track_index')}"
                if not agent_copy:
                    ch["approved_text"] = a.get(did, {}).get("text"); ch["current_text"] = b.get(did, {}).get("text")
            changes.append(ch)
        order = {"text_content": 0}
        changes.sort(key=lambda c: (order.get(c["decision_class"], 1), c["decision_class"]))
        if [t for t in (approved_canon["tracks"], current_canon["tracks"])] and \
           approved_canon["tracks"] != current_canon["tracks"]:
            changes.append({"decision_class": "track_structure", "item_ref": "tracks", "field": "tracks",
                            "approved_hash": sha(canon(approved_canon["tracks"])),
                            "current_hash": sha(canon(current_canon["tracks"]))})
        return {"base_fingerprint": sha(canon(approved_canon)), "current_fingerprint": sha(canon(current_canon)),
                "changes": changes}
    # session helpers
    def _session(self, sid):
        if not isinstance(sid, str): raise Refusal("REFERENCE_TYPE_INVALID", "session_id")
        s = self.state["sessions"].get(sid)
        if not s or s.get("sealed"): raise Refusal("SESSION_NOT_OPEN", str(sid))
        return s
    def _project(self, s): return self.state["projects"][s["project_id"]]
    def _mutate_verified(self, session, timeline_id, tool, apply_fn, probe_ref, expect_fn):
        """Adapter law §7.2: mutate -> read-back -> compare; else unverified+friction."""
        project = self._project(session)
        ok = self.adapter.mutate(project, timeline_id, apply_fn, probe_ref)
        rb = self.adapter.read_timeline(project, timeline_id) if ok else None
        verified = bool(ok) and rb is not None and expect_fn(rb)
        if not verified:
            self.friction("ADAPTER_SILENT_FAILURE", f"{tool} mutation unverified probe={probe_ref}")
            self.receipt(session["session_id"], tool, "ADAPTER_MUTATION_UNVERIFIED", probe_ref)
            self.save()
            raise Refusal("ADAPTER_MUTATION_UNVERIFIED", probe_ref)
        self.save(); return rb
    # T0
    def project_open(self, editor_class, project_ref):
        ref_str(editor_class, "editor_class"); ref_str(project_ref, "project_ref")
        if editor_class != "Resolve": raise Refusal("ADAPTER_UNAVAILABLE", editor_class)
        p = self.adapter.open_project(project_ref)
        if p is None: raise Refusal("PROJECT_NOT_FOUND", project_ref)
        sid = "sess_" + uuid.uuid4().hex[:12]
        att = self._attest(p, sid)
        self.state["sessions"][sid] = {"session_id": sid, "project_id": p["project_id"],
            "state": "ATTESTED", "attestation": att, "sealed": False}
        self.save(); return {"session_id": sid, "attestation": att, "brand": BRAND}
    def _attest(self, p, opened_by=""):
        return {"project_id": p["project_id"], "editor_class": "Resolve",
                "editor_version": self.adapter.editor_version, "adapter_id": self.adapter.adapter_id,
                "adapter_version": self.adapter.adapter_version,
                "project_identity_hash": p["identity_hash"], "opened_by_principal": opened_by,
                "attested_at": int(time.time()), "evidence_grade": "LIVE_READBACK"}
    def project_attest(self, session_id):
        s = self._session(session_id); p = self._project(s)
        att = self._attest(p, session_id)
        if att["project_identity_hash"] != s["attestation"]["project_identity_hash"]:
            raise Refusal("PROJECT_IDENTITY_CHANGED", p["project_id"])
        return att
    def timeline_read(self, session_id, timeline_id):
        s = self._session(session_id); return self.canonical_timeline(self._project(s), ref_str(timeline_id, "timeline_id"))
    def timeline_fingerprint(self, session_id, timeline_id):
        s = self._session(session_id); fp, _ = self.fingerprint(self._project(s), timeline_id)
        return {"fingerprint": fp, "coverage_version": COVERAGE_VERSION,
                "evidence_grade": "LIVE_READBACK", "computed_at": int(time.time())}
    def export_presets_list(self, session_id):
        self._session(session_id)
        return {"presets": [{"preset_id": p["preset_id"], "preset_hash": p["preset_hash"],
                "delivery_spec_id": p["audio_spec_ref"]} for p in self.state["presets"].values() if not p.get("retired")]}
    def template_list(self, session_id, editor_class):
        self._session(session_id)
        return {"templates": [{"template_hash": t["template_hash"], "version": t["version"],
                "slot_schema": t["slot_schema"], "name": t.get("name")} for t in self.state["templates"].values() if not t.get("retired")]}
    # T1
    def media_import(self, session_id, source_ref, license_state=None):
        s = self._session(session_id); ref_str(source_ref, "source_ref")
        if license_state is None: raise Refusal("LICENSE_STATE_MISSING", source_ref)
        if not isinstance(license_state, dict): raise Refusal("REFERENCE_TYPE_INVALID", "license_state")
        for f in ("source", "license_class", "scope", "expiry"):
            if f not in license_state: raise Refusal("LICENSE_STATE_MISSING", f)
        if source_ref.startswith("missing"): raise Refusal("MEDIA_NOT_FOUND", source_ref)
        mid = "media_" + sha(source_ref)[:12]
        item = {"media_id": mid, "source_ref": source_ref, "content_hash": sha("media:" + source_ref),
                "license_state": license_state, "imported_by": session_id, "imported_at": int(time.time())}
        def apply(tl): tl.setdefault("media_pool", []).append(mid)
        rb = self._mutate_verified(s, "main", "media_import", apply, source_ref,
                                    lambda tl: mid in tl.get("media_pool", []))
        self.state["media"][mid] = item; self.save(); return item
    def _decision(self, s, timeline_id, dec):
        project = self._project(s)
        def apply(tl):
            tl["decisions"] = [d for d in tl["decisions"] if d["decision_id"] != dec["decision_id"]] + [dec]
        return self._mutate_verified(s, timeline_id, "mutate", apply, dec.get("probe_ref", ""),
                                     lambda tl: any(d["decision_id"] == dec["decision_id"] and d == dec for d in tl["decisions"]))
    def clip_place(self, session_id, timeline_id, media_id, track_index, start_frame, source_in, source_out):
        s = self._session(session_id)
        track_index = coerce_int_param(track_index, "track_index"); start_frame = parse_time(start_frame)
        source_in = parse_time(source_in); source_out = parse_time(source_out)
        if media_id not in self.state["media"]: raise Refusal("MEDIA_NOT_FOUND", str(media_id))
        if not (0 <= track_index <= 3): raise Refusal("TRACK_OUT_OF_RANGE", str(track_index))
        m = self.state["media"][media_id]
        dec = {"decision_id": "clip_" + sha(f"{media_id}{start_frame}{track_index}")[:10],
               "decision_class": "clip_placement", "track_index": track_index, "track_type": "V",
               "item_ref": media_id, "media_hash": m["content_hash"], "start_frame": start_frame,
               "source_in": source_in, "source_out": source_out, "end_frame": start_frame + (source_out - source_in),
               "enabled": True, "probe_ref": m["source_ref"]}
        tl = self.canonical_timeline(self._project(s), timeline_id)
        for d in tl["decisions"]:
            if d["decision_class"] == "clip_placement" and d["track_index"] == track_index and \
               not (dec["end_frame"] <= d["start_frame"] or start_frame >= d["end_frame"]):
                raise Refusal("PLACEMENT_COLLISION", d["decision_id"])
        self._decision(s, timeline_id, dec); return dec
    def clip_trim(self, session_id, timeline_id, clip_ref, source_in, source_out, start_frame):
        s = self._session(session_id); source_in = parse_time(source_in); source_out = parse_time(source_out)
        start_frame = parse_time(start_frame)
        if source_out <= source_in: raise Refusal("TRIM_OUT_OF_RANGE", clip_ref)
        tl = self.canonical_timeline(self._project(s), timeline_id)
        old = next((d for d in tl["decisions"] if d["decision_id"] == clip_ref), None)
        if not old: raise Refusal("CLIP_NOT_FOUND", str(clip_ref))
        dec = dict(old); dec.update({"source_in": source_in, "source_out": source_out,
            "start_frame": start_frame, "end_frame": start_frame + (source_out - source_in)})
        self._decision(s, timeline_id, dec); return dec
    def text_set(self, session_id, timeline_id, track_index, item_ref, text, start_frame, end_frame):
        s = self._session(session_id); track_index = coerce_int_param(track_index, "track_index")
        if not isinstance(text, str): raise Refusal("REFERENCE_TYPE_INVALID", "text")
        tl = self.canonical_timeline(self._project(s), timeline_id)
        track = next((t for t in tl["tracks"] if t["track_index"] == track_index), None)
        if track is None or track["type"] not in ("T", "V"): raise Refusal("TRACK_NOT_TEXT", str(track_index))
        if item_ref != "NEW" and not any(d["decision_id"] == item_ref for d in tl["decisions"]):
            raise Refusal("TEXT_ITEM_NOT_FOUND", str(item_ref))
        did = item_ref if item_ref != "NEW" else "text_" + sha(text + str(start_frame))[:10]
        dec = {"decision_id": did, "decision_class": "text_content", "track_index": track_index,
               "track_type": track["type"], "item_ref": did, "text": text,
               "start_frame": parse_time(start_frame), "end_frame": parse_time(end_frame)}
        self._decision(s, timeline_id, dec); return dec
    def template_instantiate(self, session_id, timeline_id, template_hash, track_index, start_frame, slot_values):
        s = self._session(session_id)
        t = self.state["templates"].get(template_hash)
        if not t or t.get("retired"): raise Refusal("TEMPLATE_NOT_FOUND", str(template_hash))
        art_path = os.path.join(self.dir, "templates", template_hash + ".bin")
        live_hash = sha(open(art_path, "rb").read() + canon(t["slot_schema"])) if os.path.exists(art_path) else "missing"
        if live_hash != template_hash: raise Refusal("TEMPLATE_PIN_MISMATCH", template_hash)
        if not isinstance(slot_values, dict): raise Refusal("REFERENCE_TYPE_INVALID", "slot_values")
        schema = {x["slot_id"]: x for x in t["slot_schema"]["slots"]}
        for k in slot_values:
            if k not in schema: raise Refusal("TEMPLATE_SLOT_SCHEMA_VIOLATION", k)
        for sid_, spec in schema.items():
            if spec.get("required") and sid_ not in slot_values:
                raise Refusal("TEMPLATE_SLOT_SCHEMA_VIOLATION", sid_)
            if sid_ not in slot_values: continue
            v = slot_values[sid_]; typ = spec["type"]
            if typ.startswith("TEXT"):
                if not isinstance(v, str): raise Refusal("TEMPLATE_SLOT_TYPE_MISMATCH", sid_)
                mx = int(typ[typ.find("(") + 1:typ.find(")")]) if "(" in typ else 10**9
                if len(v) > mx: raise Refusal("TEMPLATE_SLOT_SCHEMA_VIOLATION", f"{sid_}>{mx} chars")
            elif typ == "MEDIA_REF":
                if not isinstance(v, str) or v not in self.state["media"]:
                    raise Refusal("TEMPLATE_SLOT_TYPE_MISMATCH", sid_)
            elif typ.startswith("NUMBER"):
                if isinstance(v, bool) or not isinstance(v, (int, float)): raise Refusal("TEMPLATE_SLOT_TYPE_MISMATCH", sid_)
            elif typ.startswith("ENUM"):
                if v not in spec.get("values", []): raise Refusal("TEMPLATE_SLOT_TYPE_MISMATCH", sid_)
        did = "tmpl_" + sha(template_hash + str(start_frame) + canon(slot_values).decode())[:10]
        dec = {"decision_id": did, "decision_class": "template_instances",
               "track_index": coerce_int_param(track_index, "track_index"), "track_type": "V",
               "item_ref": did, "template_hash": template_hash, "instance_id": did,
               "slot_values": slot_values, "start_frame": parse_time(start_frame),
               "end_frame": parse_time(start_frame) + 90}
        self._decision(s, timeline_id, dec)
        return {"instance_id": did, "template_hash": template_hash, "slot_values": slot_values, "timeline_ref": timeline_id}
    def marker_set(self, session_id, timeline_id, frame, label, payload):
        s = self._session(session_id); ref_str(label, "label")
        did = "mark_" + sha(label + str(frame))[:10]
        dec = {"decision_id": did, "decision_class": "markers", "track_index": 0, "track_type": "V",
               "item_ref": did, "start_frame": parse_time(frame), "end_frame": parse_time(frame),
               "label": label, "payload": payload}
        self._decision(s, timeline_id, dec); return dec
    # Gate
    def approval_request(self, session_id, timeline_id, preset_id):
        s = self._session(session_id)
        preset = self.state["presets"].get(preset_id)
        if not preset: raise Refusal("PRESET_NOT_PINNED", str(preset_id))
        fp, c = self.fingerprint(self._project(s), timeline_id)
        warnings = self._license_blockers(c)
        aid = "appr_" + uuid.uuid4().hex[:12]
        rec = {"approval_id": aid, "state": "REQUESTED", "principal": None, "project_id": s["project_id"],
               "timeline_id": timeline_id, "fingerprint": fp, "coverage_version": COVERAGE_VERSION,
               "preset_id": preset_id, "preset_hash": preset["preset_hash"],
               "issued_at": None, "expires_at": None, "single_use": True,
               "covered_classes": COVERED, "excluded_classes": EXCLUDED,
               "canonical": c, "duration_frames": max([d.get("end_frame", 0) for d in c["decisions"]], default=0),
               "template_instance_ids": [d["decision_id"] for d in c["decisions"] if d["decision_class"] == "template_instances"],
               "herald_signature": None,
               "license_warning": [x["media_id"] for x in warnings] or None}
        self.state["approvals"][aid] = rec; s["state"] = "APPROVAL_PENDING"; self.save()
        out = dict(rec); out.pop("canonical"); return out
    def _license_blockers(self, c):
        blockers, now = [], int(time.time())
        ids = {d["item_ref"] for d in c["decisions"] if d["decision_class"] == "clip_placement"}
        ids |= {v for d in c["decisions"] if d["decision_class"] == "template_instances"
                for v in d.get("slot_values", {}).values() if isinstance(v, str) and v in self.state["media"]}
        for mid in sorted(ids):
            ls = self.state["media"].get(mid, {}).get("license_state", {})
            exp = ls.get("expiry")
            exp_ts = int(time.mktime(time.strptime(exp, "%Y-%m-%d"))) if isinstance(exp, str) and exp else 0
            if ls.get("license_class") in (None, "UNKNOWN"): blockers.append({"media_id": mid, "reason": "unknown"})
            elif exp and exp_ts < now: blockers.append({"media_id": mid, "reason": "expired"})
            elif ls.get("scope") not in ("export", "all", "distribution", None): blockers.append({"media_id": mid, "reason": "scope"})
        return blockers
    def approval_bytes(self, rec):
        body = {k: rec[k] for k in ("approval_id", "project_id", "fingerprint", "coverage_version",
                "preset_hash", "principal", "expires_at")}
        return canon(body)
    def export_execute(self, session_id, approval_id):
        s = self._session(session_id)
        rec = self.state["approvals"].get(approval_id)
        def fail(code, detail="", drift=None, stage=None):
            self.receipt(session_id, "export_execute", code, detail); self.save()
            r = Refusal(code, detail, drift)
            if stage: r.payload_stage = stage
            raise r
        if not rec: fail("APPROVAL_NOT_FOUND", str(approval_id))
        sig_ok = False
        if rec.get("herald_signature") and self.herald_point and rec.get("principal"):
            try: sig_ok = self._signing.verify(self.herald_point, self.approval_bytes(rec),
                                                base64.b64decode(rec["herald_signature"]))
            except Exception: sig_ok = False
        if not sig_ok: fail("APPROVAL_NOT_SIGNED", approval_id)
        if rec["state"] != "SIGNED_PINNED": fail("APPROVAL_NOT_ACTIVE", rec["state"])
        if int(time.time()) >= (rec.get("expires_at") or 0):
            rec["state"] = "EXPIRED"; fail("APPROVAL_EXPIRED", approval_id)
        if rec["project_id"] != s["project_id"]: fail("APPROVAL_SCOPE_MISMATCH", rec["project_id"])
        preset = next((p for p in self.state["presets"].values() if p["preset_id"] == rec["preset_id"]), None)
        if not preset or preset["preset_hash"] != rec["preset_hash"]: fail("PRESET_HASH_MISMATCH", rec["preset_id"])
        project = self._project(s)
        fp, c = self.fingerprint(project, rec["timeline_id"])
        blockers = self._license_blockers(c)
        if blockers: fail("LICENSE_STATE_UNKNOWN", ",".join(x["media_id"] + ":" + x["reason"] for x in blockers))
        for d in c["decisions"]:
            if d["decision_class"] == "template_instances":
                art = os.path.join(self.dir, "templates", d["template_hash"] + ".bin")
                t = self.state["templates"].get(d["template_hash"], {})
                live = sha(open(art, "rb").read() + canon(t.get("slot_schema", {}))) if os.path.exists(art) else "missing"
                if live != d["template_hash"]: fail("TEMPLATE_PIN_MISMATCH", d["decision_id"])
        if fp != rec["fingerprint"]:
            drift = self.drift_report(rec["canonical"], c)
            fail("TIMELINE_CHANGED_SINCE_APPROVAL", "drift localized in drift_report", drift)
        attempt = "att_" + uuid.uuid4().hex[:10]
        render_obj = self.adapter.render(project, rec["timeline_id"], preset, self.dir)
        fp2, c2 = self.fingerprint(project, rec["timeline_id"])
        if fp2 != rec["fingerprint"]:
            quarantined = os.path.join(self.dir, "renders", attempt + ".QUARANTINED.json")
            json.dump(render_obj, open(quarantined, "w"))
            drift = self.drift_report(rec["canonical"], c2)
            r = Refusal("TIMELINE_CHANGED_SINCE_APPROVAL", "stage: POST_RENDER", drift)
            r.stage = "POST_RENDER"
            self.receipt(session_id, "export_execute", r.code, "POST_RENDER"); self.save(); raise r
        render_bytes = canon(render_obj)
        render_obj = dict(render_obj); render_obj["render_hash"] = sha(render_bytes)
        path = os.path.join(self.dir, "renders", attempt + ".render.json")
        json.dump(render_obj, open(path, "w"), indent=1)
        rec["state"] = "CONSUMED"; s["state"] = "EXPORTED"
        self._chain(self.state["receipts"], {"kind": "export", "attempt_id": attempt, "approval_id": approval_id,
                      "pre_render_fingerprint": fp, "post_render_fingerprint": fp2, "outcome": "EXPORTED",
                      "render_staging_ref": path, "render_hash": render_obj["render_hash"], "at": int(time.time())})
        self.save()
        return {"render_hash": render_obj["render_hash"], "attempt_id": attempt, "render_ref": path,
                "render_file": {"render_hash": render_obj["render_hash"], "size_bytes": len(render_bytes),
                    "duration_frames": render_obj["duration_frames"], "container": render_obj["container"],
                    "codec": render_obj["codec"], "width": render_obj["width"], "height": render_obj["height"],
                    "fps_rational": render_obj["fps_rational"]},
                "verification": "QUEUED_PROOF_PRINT", "brand": BRAND}
    def session_close(self, session_id):
        s = self._session(session_id)
        exports = [r for r in self.state["receipts"] if r.get("kind") == "export"]
        packs = self.state.get("verification_packs", [])
        if exports and not packs:
            # Print may be run standalone; close blocked until a pack exists (spec §5.4)
            raise Refusal("EXPORT_UNVERIFIED", session_id)
        if s.get("sealed"): raise Refusal("SESSION_ALREADY_SEALED", session_id)
        pack = {"pack_id": "pack_" + uuid.uuid4().hex[:10], "session_id": session_id,
                "brand": BRAND, "attestation": s["attestation"],
                "approvals": list(self.state["approvals"].values()),
                "refusals": [r for r in self.state["receipts"] if r.get("kind") == "refusal"],
                "exports": exports, "verification_packs": packs,
                "template_pins": list(self.state["templates"].values()),
                "license_states": {k: v["license_state"] for k, v in self.state["media"].items()},
                "adapter": self.adapter.adapter_id, "coverage_version": COVERAGE_VERSION}
        for a in pack["approvals"]: a.pop("canonical", None)
        pack["pack_hash"] = sha(canon(pack))
        json.dump(pack, open(os.path.join(self.dir, "packs", pack["pack_id"] + ".json"), "w"), indent=1)
        s["sealed"] = True; s["state"] = "SEALED"; self.state["packs"].append(pack["pack_id"]); self.save()
        return {"production_pack": pack, "pack_hash": pack["pack_hash"]}

AGENT_TOOLS = ["project_open", "project_attest", "timeline_read", "timeline_fingerprint",
               "export_presets_list", "template_list", "media_import", "clip_place", "clip_trim",
               "text_set", "template_instantiate", "marker_set", "approval_request",
               "export_execute", "session_close"]

# Eclipse Proof MCP · © 2026 Cyan Eclipse Technologies LLC · cetech.ai
