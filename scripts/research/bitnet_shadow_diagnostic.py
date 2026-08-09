"""bitnet_shadow_diagnostic.py — measure the EXISTING BitNet gate's effect on the CRT spine.

WHAT THIS IS
------------
A cheap, decisive A/B: run the production CRT spine with the BitNet main gate OFF
(active `v2_multi_2026_04`, `use_bitnet=false`) vs ON (`v2_multi_bitnet_shadow_2026_07`,
`use_bitnet=true`, the SAME existing `model.json`). Because the gate only *rejects*
candidates at `UltronRiskEngine.approve_with_soft_conf` (crt_engine_v2.py:1960-1968), the
ON entry set is a subset of OFF. We partition OFF entries into KEPT vs REMOVED-by-BitNet and
ask the only question that matters for the Authority Ladder (CLAUDE.md §6.5):

    does the gate remove net-LOSERS (helpful) or net-WINNERS (harmful) or nothing (inert)?

SCOPE / HONESTY
---------------
* Measures the EXISTING model, which was trained on PIPELINE feature-math (FM-020/021) but is
  served CRT geometry (FM-027/028) under the same legacy names — the F-050 CONDITIONAL_SKEW.
  So this quantifies "what flipping the flag does TODAY", not a properly-retrained gate.
* Expectancy = the spine's own realized `pnl_rr_net` (SpineEntry.meta) — the governed ledger,
  no re-derived exits.
* Research authority ONLY (§6.5). No promotion, no ACTIVE_VERSION change. Prior: F-019...F-041
  (entry information is null on these instruments) predicts ~zero economic improvement.

USAGE
-----
    python scripts/research/bitnet_shadow_diagnostic.py                 # all 4 majors
    python scripts/research/bitnet_shadow_diagnostic.py --instruments BNBUSDT
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from research.adapters.spine_signal_source import ProductionSpineSource, SpineEntry

OFF_CONFIG = "configs/research/research_config_spine_majors.json"          # use_bitnet=false
ON_CONFIG = "configs/research/research_config_spine_bitnet_shadow.json"    # use_bitnet=true
DEFAULT_INSTRUMENTS = ["BNBUSDT", "ETHUSDT", "BTCUSDT", "SOLUSDT"]


def _rr(entry: SpineEntry) -> float:
    """Spine's own realized net RR for this entry (governed ledger truth)."""
    return float(entry.meta.get("backtest_pnl_rr_net", 0.0))


def _stats(entries: list[SpineEntry]) -> dict:
    n = len(entries)
    if n == 0:
        return {"n": 0, "expectancy_rr": None, "win_rate": None, "profit_factor": None}
    rrs = [_rr(e) for e in entries]
    wins = [r for r in rrs if r > 0]
    losses = [r for r in rrs if r < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    return {
        "n": n,
        "expectancy_rr": round(sum(rrs) / n, 4),
        "win_rate": round(len(wins) / n, 4),
        "profit_factor": (round(pf, 4) if pf != float("inf") else "inf"),
        "sum_rr": round(sum(rrs), 4),
    }


def diagnose(instrument: str) -> dict:
    off_src = ProductionSpineSource(config_path=OFF_CONFIG)
    on_src = ProductionSpineSource(config_path=ON_CONFIG)

    off = off_src.entries(instrument)   # {research_index: SpineEntry}
    on = on_src.entries(instrument)

    off_keys, on_keys = set(off), set(on)
    kept_keys = off_keys & on_keys
    removed_keys = off_keys - on_keys     # in OFF, gone in ON (BitNet rejected -> trajectory diverged)
    added_keys = on_keys - off_keys       # NOT nested: a reset after a reject can form a new setup

    off_book = [off[k] for k in sorted(off_keys)]
    on_book = [on[k] for k in sorted(on_keys)]
    removed = [off[k] for k in sorted(removed_keys)]
    added = [on[k] for k in sorted(added_keys)]

    s_off, s_on = _stats(off_book), _stats(on_book)     # the HONEST book-level A/B
    s_removed, s_added = _stats(removed), _stats(added)

    # Book-level economic delta: does turning the gate ON improve realized expectancy?
    book_delta = None
    if s_off["expectancy_rr"] is not None and s_on["expectancy_rr"] is not None:
        book_delta = round(s_on["expectancy_rr"] - s_off["expectancy_rr"], 4)

    # Verdict on the ECONOMIC effect of enabling the gate (§6.5 Authority Ladder).
    if not removed_keys and not added_keys:
        verdict = "INERT"                       # gate rejected nothing that mattered
    elif book_delta is None:
        verdict = "UNDETERMINED"
    elif book_delta > 1e-9:
        verdict = "HELPFUL"                     # ON book expectancy higher
    elif book_delta < -1e-9:
        verdict = "HARMFUL"                     # ON book expectancy lower
    else:
        verdict = "NEUTRAL"

    return {
        "instrument": instrument,
        "n_off": len(off), "n_on": len(on),
        "n_removed_by_bitnet": len(removed_keys), "n_added_by_divergence": len(added_keys),
        "removed_research_indices": sorted(removed_keys),
        "added_research_indices": sorted(added_keys),
        "off_book": s_off, "on_book": s_on,
        "removed": s_removed, "added": s_added,
        "book_delta_expectancy": book_delta,
        "verdict": verdict,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BitNet existing-model shadow diagnostic (gate ON vs OFF).")
    ap.add_argument("--instruments", nargs="*", default=DEFAULT_INSTRUMENTS)
    ap.add_argument("--out", default="results/bitnet/shadow_diagnostic.json")
    args = ap.parse_args(argv)

    results = []
    pooled_off, pooled_on = [], []
    for inst in args.instruments:
        print(f"[RUN] {inst}: OFF spine + ON spine (BitNet gate) ...", flush=True)
        r = diagnose(inst)
        results.append(r)
        print(
            f"  {inst}: n_off={r['n_off']} n_on={r['n_on']} "
            f"removed={r['n_removed_by_bitnet']} added={r['n_added_by_divergence']} "
            f"| E_off={r['off_book']['expectancy_rr']} E_on={r['on_book']['expectancy_rr']} "
            f"delta={r['book_delta_expectancy']} | {r['verdict']}",
            flush=True,
        )
        # pooled book lists (sources are in-process cached from diagnose())
        off = ProductionSpineSource(config_path=OFF_CONFIG).entries(inst)
        on = ProductionSpineSource(config_path=ON_CONFIG).entries(inst)
        pooled_off.extend(off.values())
        pooled_on.extend(on.values())

    s_pool_off, s_pool_on = _stats(pooled_off), _stats(pooled_on)
    pool_delta = None
    if s_pool_off["expectancy_rr"] is not None and s_pool_on["expectancy_rr"] is not None:
        pool_delta = round(s_pool_on["expectancy_rr"] - s_pool_off["expectancy_rr"], 4)
    pooled = {"off_book": s_pool_off, "on_book": s_pool_on, "book_delta_expectancy": pool_delta}

    total_off = sum(r["n_off"] for r in results)
    total_on = sum(r["n_on"] for r in results)
    total_removed = sum(r["n_removed_by_bitnet"] for r in results)
    total_added = sum(r["n_added_by_divergence"] for r in results)

    report = {
        "kind": "bitnet_existing_model_shadow_diagnostic",
        "off_config": OFF_CONFIG, "on_config": ON_CONFIG,
        "model_artifact": "model.json (legacy_6input, F-050 skewed serve-math)",
        "scope": "research-authority-only; no promotion; use_bitnet stays false on active",
        "note": "Entry sets are NOT nested: a BitNet reject resets the CRT state machine, so gate-ON "
                "is a divergent trajectory (removed != added). Compare at the BOOK level (off vs on).",
        "per_instrument": results,
        "pooled": pooled,
        "totals": {"n_off": total_off, "n_on": total_on,
                   "n_removed_by_bitnet": total_removed, "n_added_by_divergence": total_added},
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n===== POOLED (book-level A/B) =====")
    print(f"  spine entries: OFF={total_off}  ON={total_on}  (removed={total_removed}, added={total_added})")
    print(f"  E_off : {s_pool_off['expectancy_rr']}  (PF {s_pool_off['profit_factor']}, WR {s_pool_off['win_rate']}, n {s_pool_off['n']})")
    print(f"  E_on  : {s_pool_on['expectancy_rr']}  (PF {s_pool_on['profit_factor']}, WR {s_pool_on['win_rate']}, n {s_pool_on['n']})")
    print(f"  book delta expectancy (on - off): {pool_delta}")
    print(f"\n[OK] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
