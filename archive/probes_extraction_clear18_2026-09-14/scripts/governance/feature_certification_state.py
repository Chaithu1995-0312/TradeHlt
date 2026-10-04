"""
feature_certification_state.py — the per-feature certification ledger: seed + resolver.

The bottom-up certification program tracks each feature through a moving frontier:
  UNKNOWN → HYPOTHESIS → CERTIFIED → PROMOTED_PRODUCTION → (dependents recomputed) → next
with BLOCKED (a dependency not yet promoted) and STALE (an upstream formula changed after
this was certified) as off-ramps.

State lives in an APPEND-ONLY event ledger docs/governance/feature_certification_ledger.jsonl
(events: SEEDED / CERTIFIED / PROMOTED / BLOCKED / INVALIDATED_STALE / SUPERSEDED). This module
owns SEEDING (from the authoritative feature DAG + ontology intended-quantity) and RESOLVING
(fold events → current per-feature state, derive BLOCKED from the DAG). Mutation events
(CERTIFIED/PROMOTED/INVALIDATED_STALE) are appended by scripts/governance/feature_dag_certify.py.

DESCRIPTIVE ONLY (§6.5): the ledger RECORDS certification outcomes. The authority to promote a
config/model stays in src/governance/promotion_manager.py / src/research/qualification.py — every
PROMOTED event must attribute its authority there. The ledger sets no runtime threshold/config value.

Usage:
  python scripts/governance/feature_certification_state.py seed     # write initial ledger (if absent)
  python scripts/governance/feature_certification_state.py status   # print the moving frontier
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LEDGER = _ROOT / "docs" / "governance" / "feature_certification_ledger.jsonl"

FRONTIER_STATES = (
    "UNKNOWN", "HYPOTHESIS", "CERTIFIED", "PROMOTED_PRODUCTION", "BLOCKED", "STALE", "SUPERSEDED",
)
EVENT_TYPES = (
    "SEEDED", "CERTIFIED", "PROMOTED", "BLOCKED", "INVALIDATED_STALE", "SUPERSEDED",
    "PROVENANCE_REMEDIATED",
)
AUTHORITY_DISCLAIMER = ("research/governance only — descriptive certification record; grants no "
                        "runtime/production authority (§6.5)")
PROMOTION_AUTHORITY_SOURCES = ("src/governance/promotion_manager.py", "src/research/qualification.py")

_RAW = {"open", "high", "low", "close", "volume", "timestamp"}


def _load_dag() -> dict:
    probe = _ROOT / "scripts" / "analysis" / "feature_dag_layers.py"
    spec = importlib.util.spec_from_file_location("feature_dag_layers", probe)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["feature_dag_layers"] = mod
    spec.loader.exec_module(mod)
    return mod.build_dag()


# ── intended-quantity authority (ontology + curated for non-ontology nodes) ───────

def _intended_quantities(dag: dict) -> dict[str, str]:
    """The intended MARKET quantity per feature, from authoritative sources (ontology formula
    strings + IND identities + B0/B1). 'UNADJUDICATED' where not yet established (blocks a fix)."""
    from features.formula_registry import load_ontology
    ont = load_ontology()
    formulas: dict[str, str] = {}
    for section in ("primitives", "feature_compositions", "derived_metrics"):
        for name, spec in (ont.get(section) or {}).items():
            formulas[name] = spec.get("formula", "")
    # curated intended quantities for the rolling indicators + structural nodes (ontology treats
    # rolling indicators as descriptive IND-* / leaves; B0/B1 adjudicated ATR/RSI).
    curated = {
        "true_range": "max(high-low, |high-prev_close|, |low-prev_close|) — absolute-price true range",
        "atr": "SMA(14) of true_range, close-relative (atr_14_raw/close) — NOT Wilder, NOT absolute (IND-001, B0/B1 F3)",
        "rsi_14": "SMA(14) gain/loss, Wilder ratio form, clipped [0,100] (IND-002, B0/B1 F4)",
        "ema_fast": "EWM(span=9, adjust=False) of close",
        "ema_slow": "EWM(span=21, adjust=False) of close",
        "macd_line": "EWM(12) - EWM(26) of close", "macd_signal": "EWM(9) of macd_line",
        # v4.0 MACD split (feature_schema.py:82-84, Semantic Layer Certification Audit Tier 1
        # item 1/2): the single v3.0 `macd_hist` node is now two first-class registered slots.
        "macd_hist_raw": "macd_line - macd_signal (FM-049) -- the DECLARED formula; index 18",
        "macd_hist_z": (
            "rolling(50) z-score of macd_hist_raw (FM-053) -- what v3.0's single `macd_hist` "
            "column actually EMITTED (compute_normalization overwrote it in place); index 19"
        ),
        "swing_high": "causal delayed swing-high publication (FC1-A, centered math published with delay)",
        "swing_low": "causal delayed swing-low publication (FC1-A)",
        "volume_ratio": "volume / rolling(20) mean volume", "volume_spike": "1 if volume_ratio above threshold",
        "trend_bias": "sign(ema_fast - ema_slow) ∈ {-1,0,1}",
        # `candle_range` (FM-002, "high - low") resolves automatically via the ontology
        # `primitives` loop above -- no curated entry needed. The v3.0 DAG node name `wick_size`
        # (misnomer; the quantity was always the FULL RANGE, not a wick magnitude -- see F-046 /
        # candle_math.py) is retained only as a historical SUPERSEDED ledger entry, not a live node.
        "ema_spread_atr": "(ema_fast-ema_slow)/(atr*close) — scale-invariant dimensionless (FM-030, INTENDED correction of FM-022)",
        "momentum_score_atr": "close_delta/(atr*close) — scale-invariant dimensionless (FM-031, INTENDED correction of FM-023)",
        # L3 swing-structural detection family (ledger-only; refs are CAUSAL FC1-A
        # ref_high=last_swing_high_price.shift(1), ref_low=last_swing_low_price.shift(1);
        # boundaries pinned from feature_pipeline.py:462-484):
        "higher_high": "int8 {0,1}: high > prior causal swing-high ref (strict >) — bullish structure break-up",
        "lower_low": "int8 {0,1}: low < prior causal swing-low ref (strict <) — bearish structure break-down",
        "break_of_structure": "int8 {-1,0,1}: +1 close>ref_high, -1 close<ref_low, else 0 (strict >/<) — directional structural break",
        "liquidity_sweep": "int8 {-1,0,1}: +1 (high>ref_high AND close<=ref_high) sweep_high, -1 (low<ref_low AND close>=ref_low) sweep_low, else 0 — close-return INCLUSIVE <=/>=",
        "sweep_detected": "int8 {0,1}: 1 iff a liquidity sweep occurred this bar (liquidity_sweep != 0), else 0 — direction-agnostic sweep-presence flag over the directional liquidity_sweep; same-bar (feature_pipeline.py:590)",
        "double_sweep": "int8 {0,1}: 1 iff BOTH a bullish-side sweep (liquidity_sweep>0) AND a bearish-side sweep (liquidity_sweep<0) occurred within the trailing 5-bar window (rolling(5,min_periods=1).max) — a DIRECTIONAL CONJUNCTION, NOT a count threshold (two same-direction sweeps => 0); causal trailing window (feature_pipeline.py:612-626)",
        "candles_since_retest": "int16 >=0: bars since the last liquidity_sweep!=0 event (grouped cumcount) — SWEEP bar publishes 0, each non-sweep bar +1, 0 before the first sweep. NAME MISNOMER: resets on the SWEEP, NOT on retest_flag (feature_pipeline.py:655-672). Certified contract = PRODUCTION liquidity_sweep branch ONLY; the retest_flag fallback (col-absent) is NON-AUTHORITATIVE / unreachable in production (class B). No cap; causal; int16",
        "liquidity_distance": "FM-025 float32 >=0: ATR-normalized distance from close to the NEAREST of {prior swing-high ref, prior swing-low ref, last BOS level} = min_k |close-level_k|/(atr*close), clipped >=0; NaN when atr*close<=0 or no finite level. Dimensionless / scale-invariant; causal. Authoritative impl = derived_math.liquidity_distance (registry); level resolution pipeline-owned (feature_pipeline.py:692-718)",
        # M10 / F-054-RD IDENTITY_SPLIT: canonical retest_depth is GATED production composition;
        # FM-021 is the on-gate mathematical KERNEL only (derived_math.retest_depth), NOT the series.
        "retest_depth": (
            "GATED_PRODUCTION_COMPOSITION float32 [0,1] at canonical idx 33: "
            "recent_sweep = (liquidity_sweep!=0).rolling(10,min_periods=1).max (trailing causal, "
            "current bar included); near_fast_ema = |close-ema_fast| <= 1.0*atr*close (INCLUSIVE); "
            "retest_flag = recent_sweep AND near_fast_ema (intermediate, not a DAG node); "
            "kernel = FM-021 = clip-ready |close-ema_fast|/(atr*close) when atr>0 and close>0 else 0; "
            "emit = where(retest_flag==1 AND atr>0 AND close>0, kernel, 0.0).astype(float32) "
            "THEN clip[0,1].astype(float32) — OFF_GATE=0.0 constitutive (finalize survivorship). "
            "COMPONENT FM-021 ≠ full series. Deps: atr, close, ema_fast, liquidity_sweep. "
            "feature_pipeline.py:599-610,648-653"
        ),
        # M11: pure timestamp wall-clock hour (no TZ conversion; not session)
        "hour_of_day": (
            "int8 ∈ {0..23} at canonical idx 31: wall-clock hour component of timestamp after "
            "pd.to_datetime(timestamp) with NO utc/tz conversion — uses the hour field of the "
            "stored datetime as-is (naive local wall time if naive; .dt.hour of the object if "
            "tz-aware single-tz). Emission: timestamp.dt.hour.astype(np.int8). "
            "NaT/invalid: .dt.hour → NaN and astype(int8) FAILS (no silent sentinel; production "
            "assumes valid timestamps; finalize dropna is not a soft NaT path for this cast). "
            "Deps: [timestamp] only. Same-bar pure transform. feature_pipeline.py:378-379. "
            "NOTE: session is computed in the same function FROM hour_of_day intermediate but "
            "DAG session deps=[timestamp] only — do not auto-couple cert sessions."
        ),
        # M12B: canonical FeaturePipeline session ONLY (not SESSION_MAP / dashboard / CRT strings)
        # CORRECTED 2026-07-31: the witness below described the v3.0 3-value hour PARTITION
        # (0/1/2 for hours 00-07/08-15/16-23), which FM-052 replaced on 2026-07-22 with a
        # config-driven 5-value WINDOW model (session_windows_utc; ASIA/LONDON/NEWYORK/OVERLAP/
        # CLOSED). The 2026-07-14 CERTIFIED/PROMOTED ledger events for `session` carry a
        # formula_hash computed against the OLD (now-corrected) witness text below and therefore
        # no longer reflect the actually-running FM-052 v4.0 encoding -- see
        # feature_dag_certify_recertify_session-2026-07-31.json for the STALE + re-CERTIFY +
        # re-PROMOTE ledger events that close this gap.
        "session": (
            "int8 canonical session code at idx 31 (schema v4.0; was idx 30 under v3.0 before "
            "the MACD histogram split shifted the tail). FM-052 v4.0 (2026-07-22): a window "
            "model over configurable UTC hour ranges (feature_pipeline.session_windows_utc, "
            "half-open [start, end) per window, matching the `hour < end` convention), NOT the "
            "v3.0 3-value hour partition. Domain widened from {0,1,2} to {ASIA=0, LONDON=1, "
            "NEWYORK=2, OVERLAP=3, CLOSED=4}; OVERLAP (=LONDON n NEWYORK) and CLOSED (=no "
            "window) are DERIVED, not independently configurable. Owner: "
            "features/session_classifier.py (classify_session_feature_series), which is also "
            "the single source for the FILTER vocabulary (a distinct concept from this FEATURE). "
            "Emitted from hour_of_day (int8, derived same-bar from timestamp.dt.hour); invalid/"
            "NaT timestamps fail upstream during hour_of_day's int8 cast, no session-specific "
            "fallback. Executable reuses hour_of_day column (IMPLEMENTATION_REUSE) but governed "
            "root = timestamp (EXECUTABLE_REUSE_BUT_TIMESTAMP_IDENTITY; DAG deps=[timestamp]). "
            "NOT SESSION_MAP / dashboard 1-based / CRT string encodings. "
            "feature_pipeline.py:615-631 (compute_context) + features/session_classifier.py"
        ),
        # M13B: nested rolling of close — SMA10(diff(SMA20(close)))
        "trend_strength": (
            "signed float64 nested trailing rolling metric over close at canonical idx 11: "
            "SMA20(close) window=20/min_periods=20, then one-bar first difference of that SMA, "
            "then SMA10 of the slope window=10/min_periods=10; no normalization, clipping, fill, "
            "or sentinel; leading warmup NaN with first finite value at zero-based index 29 for a "
            "fully finite close series; intermediates ma_20/ma_slope_20 unpublished as DAG nodes; "
            "canonical feature vector publishes float32 cast of the column. "
            "Deps=[close] only. NOT ema_spread / trend_bias / dual_engine detect_regime. "
            "feature_pipeline.py:249,307-308"
        ),
        # M14B: rolling-causal tercile of absolute ATR14 (NOT relative atr)
        "volatility_regime": (
            "int8 categorical regime at canonical idx 29 from absolute-price ATR14 only: "
            "TR[t]=max(H-L,|H-C_prev|,|L-C_prev|) with TR[0]=NaN (np.maximum propagates NaN when "
            "prev close absent); ATR14=SMA14(TR) window=14/min_periods=14 (first finite index 14 "
            "when TR[0] is NaN and TR[1:] finite); PCT[t]=trailing rolling(200,min_periods=1)."
            "rank(pct=True, method=average) of ATR14 with current bar included and NaNs excluded "
            "from valid rank population; REGIME=0 if PCT<0.33, 1 if 0.33<=PCT<0.66, else 2 "
            "(NaN PCT => 2). Column int8; vector float32 cast. "
            "Deps=[high,low,close] (NOT published relative atr). Sidecars global_batch/"
            "expanding_causal are non-production. feature_pipeline.py:274-280,328-350"
        ),
    }
    out: dict[str, str] = {}
    for nd in dag["nodes"]:
        n = nd["name"]
        if n in _RAW:
            out[n] = f"raw OHLCV input: {n}"
        elif n in curated:
            out[n] = curated[n]
        elif n in formulas and formulas[n]:
            out[n] = formulas[n]
        else:
            out[n] = "UNADJUDICATED — intended quantity not yet established (fix BLOCKED per invariant 4)"
    return out


# ── seed ───────────────────────────────────────────────────────────────────────────

def seed_events(dag: dict, intended: dict[str, str]) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    events = []
    for nd in sorted(dag["nodes"], key=lambda x: (x["layer"], x["topo_index"])):
        n = nd["name"]
        # raw inputs are axiomatic — seed PROMOTED (nothing upstream to certify)
        state = "PROMOTED_PRODUCTION" if n in _RAW else "UNKNOWN"
        events.append({
            "event": "SEEDED",
            "feature_name": n,
            "formula_id": nd["formula_id"],
            "layer": nd["layer"],
            "layer_name": nd["layer_name"],
            "deps": nd["deps"],
            "in_canonical_vector": nd["in_canonical_vector"],
            "intended_quantity": intended[n],
            "frontier_state": state,
            "timestamp": now,
            "authority": AUTHORITY_DISCLAIMER,
            "reason": "initial seed from feature_dag_layers + ontology intended-quantity",
        })
    return events


# ── resolve ──────────────────────────────────────────────────────────────────────

def load_events() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(ln) for ln in LEDGER.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _event_identity_hash(ev: dict) -> str:
    """Stable identity for append-only targeting of a historical ledger event."""
    return hashlib.sha256(json.dumps(ev, sort_keys=True).encode("utf-8")).hexdigest()


def _resolve_artifact_path(path_str: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else (_ROOT / p)


def _artifact_hashes(path_str: str) -> dict[str, str | bool]:
    """Return both byte and canonical-text hashes for a provenance artifact when possible."""
    path = _resolve_artifact_path(path_str)
    if not path.exists() or not path.is_file():
        return {"exists": False}
    raw = path.read_bytes()
    out: dict[str, str | bool] = {
        "exists": True,
        "path": str(path),
        "bytes_sha256": hashlib.sha256(raw).hexdigest(),
    }
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return out
    out["canonical_text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return out


def _evidence_hash_match(path_str: str, expected_sha256: str) -> tuple[bool, str | None, dict[str, str | bool]]:
    meta = _artifact_hashes(path_str)
    if not meta.get("exists"):
        return False, None, meta
    if expected_sha256 == meta.get("bytes_sha256"):
        return True, "bytes_on_disk", meta
    if expected_sha256 == meta.get("canonical_text_sha256"):
        return True, "canonical_utf8_text", meta
    return False, None, meta


def _resolve_certification_provenance(cert_ev: dict, remediation_events: list[dict]) -> dict[str, object]:
    """Project provenance completeness for the latest authoritative CERTIFIED event."""
    evd = cert_ev.get("certification_evidence") or {}
    event_id = _event_identity_hash(cert_ev)
    base: dict[str, object] = {
        "certified_event_identity_hash": event_id,
        "provenance_complete": False,
        "provenance_status": "NO_CERTIFICATION_EVIDENCE",
        "resolved_certification_evidence": evd,
    }
    artifact = evd.get("artifact")
    if not artifact:
        return base
    if artifact == "recorded-inline":
        base["provenance_complete"] = True
        base["provenance_status"] = "RECORDED_INLINE"
        return base

    expected_sha = (evd.get("sha256") or "").strip()
    if expected_sha:
        ok, basis, meta = _evidence_hash_match(artifact, expected_sha)
        if ok:
            base["provenance_complete"] = True
            base["provenance_status"] = "HASHED_ARTIFACT_VERIFIED"
            base["resolved_certification_evidence"] = dict(evd, verification_basis=basis)
        else:
            base["provenance_status"] = "HASHED_ARTIFACT_MISMATCH" if meta.get("exists") else "HASHED_ARTIFACT_MISSING"
        return base

    for rem in remediation_events:
        if rem.get("target_event_identity_hash") != event_id:
            continue
        binding = rem.get("evidence_binding") or {}
        if binding.get("artifact") != artifact:
            continue
        rem_sha = (binding.get("sha256") or "").strip()
        if not rem_sha:
            continue
        ok, basis, meta = _evidence_hash_match(artifact, rem_sha)
        if not ok:
            base["provenance_status"] = "REMEDIATION_HASH_MISMATCH" if meta.get("exists") else "REMEDIATION_ARTIFACT_MISSING"
            continue
        base["provenance_complete"] = True
        base["provenance_status"] = "REMEDIATED_APPEND_ONLY"
        resolved = dict(evd)
        resolved["sha256"] = rem_sha
        if binding.get("canonical_text_sha256"):
            resolved["canonical_text_sha256"] = binding["canonical_text_sha256"]
        resolved["verification_basis"] = basis
        resolved["remediated_by_event"] = rem.get("timestamp")
        base["resolved_certification_evidence"] = resolved
        base["provenance_remediation_event"] = rem
        return base

    base["provenance_status"] = "MISSING_EVIDENCE_HASH"
    return base


def resolve_state(events: list[dict], dag: dict) -> dict[str, dict]:
    """Fold events (in order) → current explicit state per feature, then derive BLOCKED from the DAG:
    a feature is BLOCKED if any non-raw direct dependency is not PROMOTED_PRODUCTION."""
    deps_of = {nd["name"]: nd["deps"] for nd in dag["nodes"]}
    layer_of = {nd["name"]: nd["layer"] for nd in dag["nodes"]}
    explicit: dict[str, dict] = {}
    latest_certified_event: dict[str, dict] = {}
    provenance_remediations: dict[str, list[dict]] = {}
    for ev in events:
        # M6R used PROVENANCE_REMEDIATION + target_feature (no feature_name). Accept both
        # shapes so the fold never KeyErrors on append-only remediation rows.
        f = ev.get("feature_name") or ev.get("target_feature")
        if not f:
            continue
        cur = explicit.setdefault(f, {"feature_name": f, "layer": layer_of.get(f),
                                      "deps": deps_of.get(f, []), "history": 0})
        if "frontier_state" in ev:
            cur["frontier_state"] = ev["frontier_state"]
        elif "frontier_state" not in cur:
            cur["frontier_state"] = "UNKNOWN"
        for k in ("formula_hash", "dependency_contract_hash", "certified_at", "intended_quantity",
                  "certification_evidence", "superseded_by", "stale_reason", "upstream_trigger"):
            if k in ev:
                cur[k] = ev[k]
        cur["last_event"] = ev["event"]
        cur["history"] += 1
        if ev["event"] == "CERTIFIED":
            latest_certified_event[f] = ev
        elif ev["event"] in ("PROVENANCE_REMEDIATED", "PROVENANCE_REMEDIATION"):
            provenance_remediations.setdefault(f, []).append(ev)

    promoted = {f for f, s in explicit.items() if s.get("frontier_state") == "PROMOTED_PRODUCTION"}
    for f, s in explicit.items():
        non_raw_deps = [d for d in s["deps"] if d not in _RAW]
        blocking = sorted(d for d in non_raw_deps if d not in promoted)
        s["blocking_dependencies"] = blocking
        st = s.get("frontier_state", "UNKNOWN")
        if st in ("PROMOTED_PRODUCTION", "SUPERSEDED", "STALE", "CERTIFIED"):
            s["effective_state"] = st
        elif blocking:
            s["effective_state"] = "BLOCKED"
        elif st == "UNKNOWN":
            s["effective_state"] = "READY_TO_CERTIFY"
        else:
            s["effective_state"] = st
        cert_ev = latest_certified_event.get(f)
        if cert_ev:
            s.update(_resolve_certification_provenance(cert_ev, provenance_remediations.get(f, [])))
        else:
            s["provenance_complete"] = None
            s["provenance_status"] = "NOT_CERTIFIED"
            s["resolved_certification_evidence"] = None
    for f, s in explicit.items():
        tainted = sorted(
            d for d in s["deps"]
            if d in explicit and explicit[d].get("provenance_complete") is False
        )
        s["unresolved_upstream_provenance"] = tainted
        s["downstream_authority_status"] = (
            "TAINTED_BY_UNRESOLVED_PROVENANCE" if tainted else "CLEAN_OR_NOT_APPLICABLE"
        )
    return explicit


def _print_status(state: dict[str, dict], dag: dict) -> None:
    by_layer: dict[int | None, list[dict]] = {}
    for s in state.values():
        by_layer.setdefault(s["layer"], []).append(s)
    print("=== Feature certification frontier ===")
    # A SUPERSEDED feature_name that no longer exists as a DAG node (e.g. a v3.0 name renamed
    # away by a schema migration -- candle_range/macd_hist_raw/macd_hist_z superseding
    # wick_size/macd_hist, Semantic Layer Certification Audit 2026-07-31 Tier 1 item 2) has no
    # `layer` in the CURRENT dag, so `layer_of.get(f)` in resolve_state() returns None. Sort with
    # None last (an int key can't be compared to None directly) rather than crashing.
    for lvl in sorted(by_layer, key=lambda x: (x is None, x)):
        print(f"\n--- layer {lvl if lvl is not None else 'RETIRED (name not in current DAG)'} ---")
        for s in sorted(by_layer[lvl], key=lambda x: x["feature_name"]):
            blk = f"  pending:{s['blocking_dependencies']}" if s["blocking_dependencies"] else ""
            print(f"  {s['feature_name']:26s} {s['effective_state']:18s}{blk}")
    counts: dict[str, int] = {}
    for s in state.values():
        counts[s["effective_state"]] = counts.get(s["effective_state"], 0) + 1
    print(f"\nfrontier: {counts}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Feature certification ledger — seed + resolver.")
    ap.add_argument("command", choices=["seed", "status", "reseed"])
    args = ap.parse_args()
    dag = _load_dag()

    if args.command in ("seed", "reseed"):
        if LEDGER.exists() and args.command == "seed":
            print(f"ledger already exists ({LEDGER.relative_to(_ROOT)}); use 'reseed' to overwrite")
            return 1
        intended = _intended_quantities(dag)
        events = seed_events(dag, intended)
        LEDGER.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
        print(f"seeded {len(events)} features → {LEDGER.relative_to(_ROOT)}")
        return 0

    state = resolve_state(load_events(), dag)
    _print_status(state, dag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
