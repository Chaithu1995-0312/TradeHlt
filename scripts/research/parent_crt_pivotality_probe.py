#!/usr/bin/env python
"""parent_crt_pivotality_probe.py — is the F-075 parent-CRT bias gate PIVOTAL?

OBSERVATION_ONLY. Reads governed config, runs the spine twice, compares. Writes no
config, never touches `ACTIVE_VERSION`, makes no promotion or economic claim.

THE QUESTION
------------
`parent_crt.enabled` is `true` on `ACTIVE_VERSION` (`v2_htfcrt_2026_08`) and `false` on
`v2_multi_2026_04`. Those two registry configs have IDENTICAL `params` (same
`config_hash` — `parent_crt` is a non-`params` section and therefore hash-neutral, §6.5),
which makes them a natural A/B of that one gate.

They are NOT byte-identical elsewhere, and saying so would be an overclaim: they differ in
12 top-level sections. Eleven of those are provenance/comment fields; the twelfth is
`ultron_risk_gate`, where the ON config DECLARES the four F-082 cost-tax keys at values
that exactly equal the in-code defaults, each behind a `> 0` guard that is false in both
arms. `compare_configs` enumerates that explicitly rather than asserting an empty diff, so
the isolation claim is auditable and any NEW difference invalidates the run.

`REACHABLE != PIVOTAL` (§6.8 `different != wrong`, and the §6.5 Authority Ladder). F-075
established the gate is reachable on the armed config. This probe asks the next question:
when it fires, does any DECISION change, or only the recorded REASON?

VERDICTS
--------
  INVALID_AB        the configs differ BEHAVIOURALLY beyond `parent_crt.enabled` -> the
                    comparison is confounded and no verdict is emitted
  VACUOUS           the gate never fired -> it is UNTESTED, not neutral (the F-070 guard;
                    a gate with nothing to veto proves nothing)
  DECISION_NEUTRAL  the gate fired, but every candidate it vetoed was already being
                    vetoed for another reason -> reasons change, outcomes do not
  PIVOTAL           at least one decision differs (state sequence, rejection set, or
                    trade counts)

WHY IT RE-RUNS THE SPINE RATHER THAN READING AN ARTIFACT
--------------------------------------------------------
The obvious shortcut is to diff two existing run directories, but those live under
gitignored `results/`, so such a probe would not reproduce from a clean clone. This runs
both arms itself through the SAME governed registry loader the live path uses
(`load_prod_config_from_registry`, F-057 discipline), reusing
`charts.crt_overlay.run_spine_for_states`, whose cache is already version-scoped so the
two arms cannot collide. First run is slow (two full spine passes); later runs are cached.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# The two registry versions under comparison. Both must exist in the production registry;
# neither is modified.
GATE_ON_VERSION = "v2_htfcrt_2026_08"
GATE_OFF_VERSION = "v2_multi_2026_04"

# Substring identifying a rejection attributable to the parent-bias gate. Matches the
# engine's own reason text ("Against parent-timeframe bias (LONG)").
PARENT_BIAS_MARKER = "parent-timeframe bias"

# Events that move the CRT state machine (both are required — the engine returns to RANGE
# only via RESET; see src/charts/crt_overlay.py).
_STATE_EVENTS = ("STATE_TRANSITION", "RESET")
_TRADE_EVENTS = ("TRADE_OPENED", "TRADE_TP1", "TRADE_TP2", "TRADE_STOPPED")

VERDICT_INVALID = "INVALID_AB"
VERDICT_VACUOUS = "VACUOUS"
VERDICT_NEUTRAL = "DECISION_NEUTRAL"
VERDICT_PIVOTAL = "PIVOTAL"


# ── validity gate 1: the A/B must isolate exactly one BEHAVIOURAL knob ─────────
#
# CORRECTED 2026-08-22 (E-001). The first version of this gate demanded byte-equality of
# every non-`parent_crt` section, and an initial hand-check that compared only top-level
# KEY SETS + `params` + `config_hash` wrongly concluded "these configs differ only in
# parent_crt.enabled". They differ in **12** sections. The behavioural conclusion survived
# re-checking, but the claim as first stated was false, so the gate now enumerates what is
# inert and WHY, rather than pretending the diff is empty.

# Provenance/audit fields. Never read by the engine; differ on every promoted config.
_METADATA_KEYS = frozenset({
    "config_id", "created_at", "promoted_at", "notes", "version", "validation_summary",
})

# Sub-keys that are documentation inside an otherwise-behavioural section.
_DOC_SUBKEYS = frozenset({"note"})

# Differences ADJUDICATED inert, keyed by dotted path -> (value_on, value_off, why).
#
# VALUE-SPECIFIC ON PURPOSE. An entry exempts one exact (ON, OFF) value pair, never the
# key in general: `spread_pips` declared at the in-code default 0.0 is inert, but
# `spread_pips: 1.5` is a live cost tax and MUST invalidate the A/B. Keying the allowlist
# by name alone would silently wave a real behavioural change through — the first version
# of this file did exactly that, and its own floor caught it.
_MISSING = object()

_ADJUDICATED_INERT: dict[str, tuple[object, object, str]] = {
    "ultron_risk_gate.spread_pips": (0.0, _MISSING,
        "in-code default is 0.0 (src/core/ultron_risk_gate.py:238) and the cost tax is "
        "guarded by `total_cost_pips > 0` (:242), false in BOTH arms. F-082 "
        "declared-not-activated."),
    "ultron_risk_gate.slippage_pips": (0.0, _MISSING,
        "in-code default 0.0 (:239); same `> 0` guard (:242). F-082."),
    "ultron_risk_gate.pip_size": (0.0001, _MISSING,
        "0.0001 IS the in-code default (:240); only consulted when a cost/floor guard "
        "is already true, and neither is. F-082."),
    "ultron_risk_gate.min_sl_pips": (0.0, _MISSING,
        "in-code default 0.0 (:312); the FRAG-6 floor is guarded by `min_sl_pips > 0` "
        "(:313), false in BOTH arms. F-082."),
}


def _behavioural_diff(cfg_on, cfg_off, prefix: str = "") -> list[str]:
    """Recursively collect differences that are not metadata, docs, or adjudicated inert.

    Recursion matters: `rr_model.confidence_gate` differs only in a nested `note` string,
    which a one-level comparison reports as a whole differing section.
    """
    out: list[str] = []
    keys = sorted(set(cfg_on) | set(cfg_off))
    for key in keys:
        path = f"{prefix}{key}"
        if key.startswith("_comment") or key in _DOC_SUBKEYS:
            continue
        if not prefix and (key in _METADATA_KEYS or key == "parent_crt"):
            continue

        a = cfg_on.get(key, _MISSING)
        b = cfg_off.get(key, _MISSING)
        if a is _MISSING and b is _MISSING:
            continue
        if a == b:
            continue

        adj = _ADJUDICATED_INERT.get(path)
        if adj is not None and a == adj[0] and b is adj[1]:
            continue
        if adj is not None and a == adj[0] and b == adj[1]:
            continue

        if isinstance(a, dict) and isinstance(b, dict):
            out.extend(_behavioural_diff(a, b, prefix=f"{path}."))
        else:
            out.append(path)
    return out


def compare_configs(cfg_on: dict, cfg_off: dict) -> dict:
    """Confirm the two configs isolate `parent_crt.enabled` BEHAVIOURALLY.

    Without this the comparison is confounded: a future edit to either config would
    silently turn this probe into a diff of two unrelated objects while still printing a
    confident verdict.
    """
    pa, pb = cfg_on.get("params", {}), cfg_off.get("params", {})
    params_diff = sorted(k for k in set(pa) | set(pb) if pa.get(k) != pb.get(k))

    hash_on, hash_off = cfg_on.get("config_hash"), cfg_off.get("config_hash")
    enabled_on = (cfg_on.get("parent_crt") or {}).get("enabled")
    enabled_off = (cfg_off.get("parent_crt") or {}).get("enabled")
    behavioural = _behavioural_diff(cfg_on, cfg_off)

    valid = (
        not params_diff
        and hash_on == hash_off
        and not behavioural
        and enabled_on is True and enabled_off is False
    )
    return {
        "valid": valid,
        "params_diff": params_diff,
        "config_hash_equal": hash_on == hash_off,
        "config_hash": hash_on,
        "unexplained_behavioural_diffs": behavioural,
        "adjudicated_inert": sorted(_ADJUDICATED_INERT),
        "parent_crt_enabled_on": enabled_on,
        "parent_crt_enabled_off": enabled_off,
    }


# ── validity gate 3: corpus identity ──────────────────────────────────────────
def verify_corpus(csv_path: str | Path) -> dict:
    """Fail closed unless the corpus is the Phase-1 frozen candidate."""
    from data_ingestion.xauusd_phase1_candidate import PHASE1_SHA256

    h = hashlib.sha256()
    with open(csv_path, "rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    got = h.hexdigest()
    return {"ok": got == PHASE1_SHA256, "expected": PHASE1_SHA256, "got": got}


# ── event-stream profile ──────────────────────────────────────────────────────
def load_profile(events_path: str | Path) -> dict:
    """Reduce one run's event stream to the surfaces a decision could differ on."""
    seq: list[tuple] = []
    events: collections.Counter = collections.Counter()
    rejections: dict[str, str] = {}

    with open(events_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = rec.get("event")
            events[kind] += 1
            if kind in _STATE_EVENTS:
                seq.append((kind, rec.get("timestamp"),
                            rec.get("state_from"), rec.get("state_to")))
            elif kind == "FILTER_REJECTED":
                rejections[str(rec.get("timestamp"))] = str(rec.get("reason") or "")

    return {
        "state_seq_sha256": hashlib.sha256(
            json.dumps(seq, sort_keys=False).encode("utf-8")).hexdigest(),
        "state_events": len(seq),
        "event_counts": dict(events),
        "rejections": rejections,
        "trades": {k: events.get(k, 0) for k in _TRADE_EVENTS},
    }


def classify(prof_on: dict, prof_off: dict) -> dict:
    """Compare two profiles and name what changed."""
    rej_on, rej_off = prof_on["rejections"], prof_off["rejections"]
    ts_on, ts_off = set(rej_on), set(rej_off)

    only_on = sorted(ts_on - ts_off)
    only_off = sorted(ts_off - ts_on)
    reasons_changed = sorted(t for t in (ts_on & ts_off) if rej_on[t] != rej_off[t])

    gate_fired = sorted(t for t, r in rej_on.items() if PARENT_BIAS_MARKER in r)
    seq_equal = prof_on["state_seq_sha256"] == prof_off["state_seq_sha256"]
    trades_equal = prof_on["trades"] == prof_off["trades"]

    # An OUTCOME difference is any of: a different state sequence, a rejection that
    # exists in one arm only, or a different trade tally. A changed REASON on a rejection
    # that both arms make is NOT an outcome difference — the candidate died either way.
    outcomes_changed = (
        (0 if seq_equal else 1) + len(only_on) + len(only_off) + (0 if trades_equal else 1)
    )

    if not gate_fired:
        verdict = VERDICT_VACUOUS
    elif outcomes_changed:
        verdict = VERDICT_PIVOTAL
    else:
        verdict = VERDICT_NEUTRAL

    return {
        "verdict": verdict,
        "gate_fired": len(gate_fired),
        "gate_fired_at": gate_fired,
        "reasons_changed": len(reasons_changed),
        "reasons_changed_detail": [
            {"timestamp": t, "gate_off": rej_off[t], "gate_on": rej_on[t]}
            for t in reasons_changed
        ],
        "outcomes_changed": outcomes_changed,
        "state_sequence_equal": seq_equal,
        "state_seq_sha256_on": prof_on["state_seq_sha256"],
        "state_seq_sha256_off": prof_off["state_seq_sha256"],
        "state_events": prof_on["state_events"],
        "trades_equal": trades_equal,
        "trades_on": prof_on["trades"],
        "trades_off": prof_off["trades"],
        "rejections_total_on": len(rej_on),
        "rejections_total_off": len(rej_off),
        "rejections_only_in_gate_on": only_on,
        "rejections_only_in_gate_off": only_off,
    }


# ── driver ────────────────────────────────────────────────────────────────────
def _load_registry_config(version: str) -> dict:
    path = _REPO / "configs" / "production" / f"{version}.json"
    if not path.is_file():
        raise FileNotFoundError(f"registry config not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def run(instrument: str, csv_path: str, on_version: str, off_version: str) -> dict:
    from charts.crt_overlay import run_spine_for_states

    cfg_on = _load_registry_config(on_version)
    cfg_off = _load_registry_config(off_version)
    ab = compare_configs(cfg_on, cfg_off)

    corpus = verify_corpus(csv_path) if instrument == "XAUUSD" else {"ok": True,
                                                                    "expected": None,
                                                                    "got": None}
    result: dict = {
        "probe": "parent_crt_pivotality",
        "instrument": instrument,
        "corpus_path": str(csv_path).replace("\\", "/"),
        "gate_on_version": on_version,
        "gate_off_version": off_version,
        "config_ab": ab,
        "corpus_identity": corpus,
    }

    if not corpus["ok"]:
        result["verdict"] = VERDICT_INVALID
        result["reason"] = "corpus sha256 does not match the Phase-1 frozen candidate"
        return result
    if not ab["valid"]:
        result["verdict"] = VERDICT_INVALID
        result["reason"] = (
            "the two configs differ in more than parent_crt.enabled; the A/B is "
            "confounded and no pivotality verdict is meaningful"
        )
        return result

    ev_on = run_spine_for_states(instrument, csv_path, on_version)
    ev_off = run_spine_for_states(instrument, csv_path, off_version)
    result["events_gate_on"] = str(ev_on).replace("\\", "/")
    result["events_gate_off"] = str(ev_off).replace("\\", "/")
    result.update(classify(load_profile(ev_on), load_profile(ev_off)))
    return result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--instrument", default="XAUUSD")
    p.add_argument("--csv", default=None,
                   help="base M15 corpus (default data/mt5/<INSTRUMENT>_M15.csv)")
    p.add_argument("--gate-on-version", default=GATE_ON_VERSION)
    p.add_argument("--gate-off-version", default=GATE_OFF_VERSION)
    p.add_argument("--json", dest="json_out", default=None,
                   help="also write the full result to this path")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inst = args.instrument.upper()
    csv_path = args.csv or f"data/mt5/{inst}_M15.csv"

    res = run(inst, csv_path, args.gate_on_version, args.gate_off_version)

    print(f"instrument      : {inst}")
    print(f"gate ON  config : {res['gate_on_version']}  "
          f"(parent_crt.enabled={res['config_ab']['parent_crt_enabled_on']})")
    print(f"gate OFF config : {res['gate_off_version']}  "
          f"(parent_crt.enabled={res['config_ab']['parent_crt_enabled_off']})")
    print(f"A/B isolates one knob : {res['config_ab']['valid']}  "
          f"(config_hash equal={res['config_ab']['config_hash_equal']})")
    print()
    print(f"VERDICT         : {res['verdict']}")

    if res["verdict"] != VERDICT_INVALID and "gate_fired" in res:
        print(f"gate fired      : {res['gate_fired']}")
        print(f"reasons changed : {res['reasons_changed']}")
        print(f"outcomes changed: {res['outcomes_changed']}")
        print(f"state seq equal : {res['state_sequence_equal']} "
              f"({res['state_events']} events, sha {res['state_seq_sha256_on'][:16]})")
        print(f"trades equal    : {res['trades_equal']}  {res['trades_on']}")
        for d in res.get("reasons_changed_detail", []):
            print(f"   {d['timestamp']}  OFF: {d['gate_off']!r}  ->  ON: {d['gate_on']!r}")
    else:
        print(f"reason          : {res.get('reason')}")

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(res, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nwrote {out}")

    # Non-zero only when the comparison itself was invalid; a PIVOTAL or NEUTRAL verdict
    # is a legitimate measurement outcome, not a failure.
    return 2 if res["verdict"] == VERDICT_INVALID else 0


if __name__ == "__main__":
    raise SystemExit(main())
