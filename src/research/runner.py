"""runner.py — HypothesisRunner: stream CSVs → detect → forward_walk → EdgeReport.

The M3 deliverable. Its single most important property is **determinism**: the same
candles + the same config + the same hypothesis source ⇒ byte-identical `edge_report`.
That matters more than profit factor — reproducible evidence is the foundation the
qualification gate (M4) and the ledger (M5) stand on.

Determinism is achieved by:
  * loading candles deterministically via the existing `CandleLoader`,
  * iterating instruments in sorted order,
  * controls/hypotheses being pure + seeded,
  * the serialized `edge_report` carrying NO wall-clock (run_id / timestamp / git live
    only in the separate `run_manifest`),
  * numeric fields pre-rounded in `EdgeAggregator`.

Provenance: `config_sha256` and `hypothesis_sha256` ARE deterministic, so they live in
`edge_report` itself — making M5 ledger integrity trivial.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from research.config import ResearchConfig
from research.contracts import EdgeReport, Outcome
from research.costs import CostModel
from research.measurement.forward_walk import forward_walk, forward_walk_oco
from research.measurement.metrics import EdgeAggregator
from research.provenance import provenance_block
from research.registry import get_hypothesis

log = logging.getLogger("research.runner")


@dataclass
class RunResult:
    hypothesis: str
    per_instrument: dict[str, EdgeReport]
    pooled: EdgeReport
    config_sha256: str
    hypothesis_sha256: str
    exit_model: str
    round_trip_bps: float


def _hypothesis_sha256(hyp) -> str:
    """Hash the hypothesis's class source so a code change invalidates old reports."""
    try:
        src = inspect.getsource(type(hyp))
    except (OSError, TypeError):
        src = repr(type(hyp))
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


class HypothesisRunner:
    def __init__(self, config: ResearchConfig):
        self.config = config
        self.cost_model = CostModel(config.round_trip_bps)
        self.agg = EdgeAggregator()

    # -- candle loading -------------------------------------------------------
    def _load_candles(self, csv_path: str, instrument: str) -> list:
        from runtime.backtest_v2 import CandleLoader   # reuse the proven loader
        candles = list(CandleLoader(csv_path, instrument).stream())
        for i, c in enumerate(candles):
            c.index = i                                 # absolute index = stream position
        return candles

    # -- single instrument ----------------------------------------------------
    def run_instrument(self, hyp, csv_path: str, instrument: str) -> tuple[EdgeReport, list[Outcome]]:
        cfg = self.config
        candles = self._load_candles(csv_path, instrument)
        ctx = {"instrument": instrument}
        outcomes: list[Outcome] = []
        n = len(candles)

        for i in range(cfg.warmup, n):
            lo = max(0, i - cfg.window_size + 1)
            window = candles[lo:i + 1]
            for s in hyp.detect(window, {}, ctx):
                if cfg.apply_signal_defaults:
                    s = dataclasses.replace(s, sl_atr_mult=cfg.sl_atr_mult, tp_atr_mult=cfg.tp_atr_mult)
                if s.direction == "oco":
                    # Program-9 both-sided straddle: routed per-SIGNAL so every
                    # long/short hypothesis takes the pre-existing path verbatim.
                    if cfg.entry_ttl is None:
                        raise ValueError(
                            "HypothesisRunner: 'oco' signal requires forward_walk.entry_ttl in the research config")
                    future = candles[i + 1:i + 1 + cfg.max_forward + cfg.entry_ttl]
                    if future:
                        oc = forward_walk_oco(
                            s, future, max_forward=cfg.max_forward, entry_ttl=cfg.entry_ttl,
                            trail_mult=cfg.trail_mult, exit_model=cfg.exit_model)
                        if oc is not None:
                            outcomes.append(oc)
                    continue
                future = candles[i + 1:i + 1 + cfg.max_forward]
                if future:
                    outcomes.append(forward_walk(
                        s, future, max_forward=cfg.max_forward,
                        trail_mult=cfg.trail_mult, exit_model=cfg.exit_model))

        report = self.agg.aggregate(hyp.name, [instrument], outcomes, cost_model=self.cost_model)
        log.info("research.runner: %s/%s n=%d PF=%.3f E=%.4f",
                 hyp.name, instrument, report.n, report.profit_factor, report.expectancy_rr)
        return report, outcomes

    # -- raw per-instrument outcomes (for M4 IS/OOS split + permutation) ------
    def collect(self, hypothesis: str, csv_map: dict[str, str]) -> dict[str, list[Outcome]]:
        """Per-instrument ordered Outcomes (chronological within each instrument).
        Used by the M4 QualificationGate for the IS/OOS split and permutation test —
        kept separate from `run` so the deterministic edge_report path is untouched."""
        hyp = get_hypothesis(hypothesis)
        out: dict[str, list[Outcome]] = {}
        for instrument in sorted(csv_map):
            _, outs = self.run_instrument(hyp, csv_map[instrument], instrument)
            out[instrument] = outs
        return out

    # -- full universe --------------------------------------------------------
    def run(self, hypothesis: str, csv_map: dict[str, str]) -> RunResult:
        hyp = get_hypothesis(hypothesis)
        per: dict[str, EdgeReport] = {}
        pooled_outcomes: list[Outcome] = []

        for instrument in sorted(csv_map):               # sorted ⇒ deterministic
            rep, outs = self.run_instrument(hyp, csv_map[instrument], instrument)
            per[instrument] = rep
            pooled_outcomes.extend(outs)

        pooled = self.agg.aggregate(hyp.name, sorted(csv_map), pooled_outcomes, cost_model=self.cost_model)
        return RunResult(hyp.name, per, pooled, self.config.sha256(), _hypothesis_sha256(hyp),
                         self.config.exit_model, self.config.round_trip_bps)


# ── deterministic serialization ──────────────────────────────────────────────
def run_result_to_dict(rr: RunResult) -> dict:
    """The deterministic artifact — NO wall-clock; safe to byte-compare across runs."""
    d = {
        "hypothesis": rr.hypothesis,
        "config_sha256": rr.config_sha256,
        "hypothesis_sha256": rr.hypothesis_sha256,
        "pooled": dataclasses.asdict(rr.pooled),
        "per_instrument": {k: dataclasses.asdict(v) for k, v in sorted(rr.per_instrument.items())},
    }
    # Versioned realism/cost provenance — deterministic (no wall-clock), so the artifact
    # stays byte-comparable across runs while self-documenting the truth standard.
    d.update(provenance_block(rr.exit_model, rr.round_trip_bps))
    return d


def edge_report_json(rr: RunResult) -> str:
    return json.dumps(run_result_to_dict(rr), sort_keys=True, indent=2)
