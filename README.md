# Eclipse Proof MCP

**Eclipse Proof · Cyan Eclipse Technologies LLC · cetech.ai**

Governed video production: signed approval pins over exact edit states, hash-pinned templates, render evidence for every export.

## Status — honest labels
v0.1.0, local stdio, Python stdlib only. **CERTIFIED(local) — Verity bench 2026-10-25, scorecard `test-bench/results/eclipse-proof-mcp-2026-10-26-2.json` (run 2; run-1 FAILED retained append-only — sole failure was a bench-suite self-defect in NC-2's mapping tokens, no product defect). Certification scope = simulated adapter, below.**
P0 adapter is a **simulated Resolve-shaped adapter** (`resolve-sim`): no DaVinci Resolve Studio seat exists on this VM (spec LG-1/D3 — license purchase is an owner act), so no live-Resolve claim is made. The adapter seam mirrors the external scripting contract including its silent-failure mode; the governance core, fingerprint, gate, Print and Trace are real and benched end-to-end against it. Claim ceiling: `CERTIFIED(local)` against the simulated adapter.

## Novel mechanism (§1)
Agent assembles freely (T1), but export executes ONLY against a Herald-signed approval pinning {project, canonical edit-decision fingerprint, export-preset hash, principal, expiry}. Core re-fingerprints at export; any drift → `TIMELINE_CHANGED_SINCE_APPROVAL` with a localized DriftReport (caption/text track named first — text is a claim surface). Templates are hash-pinned signed artifacts, slots only (`TEMPLATE_PIN_MISMATCH`). Renders are independently verified by **Proof Print** (separate tool); interchange fingerprinting is **Proof Trace** (separate tool, detective-only, FCPXML at P0).

## Non-negotiables in code
- **Adapter law (§7.2):** every mutation read-back-verified; silent False/None or mismatch → `ADAPTER_MUTATION_UNVERIFIED` + automatic Eclipse Friction finding; mutation never asserted.
- **Canonical fingerprint:** integer-frame canonical JSON (sorted keys, decisions sorted by track/start/id, verbatim UTF-8 text, no float seconds), coverage `RESOLVE_COV_V1`; excluded classes named on every approval (grade/Fusion internals NOT claimed).
- **Gate order §6.3** verbatim codes incl. `LICENSE_STATE_UNKNOWN` blocking export (unknown/expired/scope), `PRESET_HASH_MISMATCH`, post-render guard (drift → render quarantined, approval not consumed, `stage: POST_RENDER`).
- **NO code-exec tool ever** (house T3); no publish tool; no license inference; unknown tool name → byte-identical `SURFACE_TOOL_UNKNOWN` (incl. operator-shaped names — no oracle).
- **Disjoint surfaces:** 15 agent tools in `server.py`; 6 operator tools in `proof_operator.py`, a separate process holding the Herald private key. Agent server holds the public key only.
- House guards: `coerce_int_param`, `parse_time` (float seconds refused), reference-type guard, deep-key scan, verified-approval pattern on the T3 export verb.

## Modules
| Module | File |
|---|---|
| Proof core (MCP) | `server.py` + `proof_engine.py` |
| Operator surface | `proof_operator.py` (register/retire template, register preset, set license, sign approval, pack read) |
| Proof Print (render verifier) | `proof_print.py` — DURATION / TEXT_VERBATIM (fail-closed `TEXT_EXTRACTION_LOW_CONFIDENCE`) / TEMPLATE_PRESENCE / LOUDNESS (delivery specs as data) / FORMAT / FILE_HASH |
| Proof Trace (interchange) | `proof_trace.py` — FCPXML fingerprint + diff, detective-only label on every output |

## Run
```bash
python3 tools/make_keys.py   # local Herald seed key (keys/, 600) + pinned herald_pubkey.pem
python3 server.py            # MCP over stdio
python3 smoke.py             # stdio smoke
python3 -m unittest discover tests   # 12 regression tests (bench shapes)
python3 dogfood.py           # White Report reel dogfood -> dogfood_output/
```
State: `$ECLIPSE_PROOF_STATE` or `./data`. Dogfood: HOUSE_REEL_V1 pinned template replaces chat approval inside the pipeline — owner approval becomes the Herald pin; posting rails unchanged.

## Not built / not claimed
Live Resolve Studio adapter (needs D3 license), Premiere UXP (P1), Frame.io connector (P2, specced §10), Trace OTIO/AAF/EDL (P2), OCR/ASR extraction path in Print (embedded text track at P0; low-confidence fixtures fail closed).

— Eclipse Proof · © 2026 Cyan Eclipse Technologies LLC · cetech.ai
