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
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from research.config import ResearchConfig
from research.contracts import EdgeReport, Outcome
from research.costs import ComponentCostModel, CostModel
from research.measurement.forward_walk import forward_walk, forward_walk_oco
from research.measurement.metrics import EdgeAggregator
from research.provenance import provenance_block
from research.registry import get_hypothesis

log = logging.getLogger("research.runner")

# Same timeframe vocabulary as data_ingestion.dataset_integrity._TF_MINUTES — not imported
# from there to avoid coupling this module to dataset_integrity's private constant; kept in
# sync manually (both lists are short and change together only if a new timeframe is added).
_TF_TOKENS = ("M15", "M30", "M1", "M5", "H1", "H4", "D1")


def _pattern_timeframe(pattern: str) -> str:
    """Extract the timeframe token from a `universe.pattern` glob (e.g. "*_M15.csv" -> "M15").

    Only called when `config.window` is declared — `corpus_store.read` needs an EXPLICIT
    timeframe to resolve the right admitted corpus file, and guessing wrong would silently
    read a different instrument/timeframe pair than the one the config's universe glob
    actually matches. Raises rather than defaulting to "M15" on a pattern this can't parse
    (e.g. the literal template `*_{TF}.csv`), because a wrong silent default here is a wrong
    corpus, not a cosmetic error.
    """
    for tf in _TF_TOKENS:
        if re.search(rf"(?:^|[_.]){tf}(?:[_.]|$)", pattern):
            return tf
    raise ValueError(
        f"HypothesisRunner: cannot resolve a timeframe token from universe.pattern={pattern!r} "
        "(expected one of M1/M5/M15/M30/H1/H4/D1) — required when config.window is declared, "
        "since corpus_store.read needs an explicit timeframe to resolve the admitted corpus."
    )


def _bind_cost_model(config: ResearchConfig):
    """Resolve the cost model `config.cost_model` declares.

    "flat_bps" -> today's `CostModel(config.round_trip_bps)`, byte-identical to every run
    before this function existed. "component_measured" -> a `ComponentCostModel` built from
    `config.cost_model_manifest_path`, with the manifest's OWN sha256 recomputed and recorded
    at bind time — never trusted from the declared path alone (mirrors
    `visual_crt/measure.py:_bind_cost_model`'s "a provenance string nobody recomputes is a
    comment, not evidence"). Fails closed via `ComponentCostModel.from_manifest`'s own
    MEASURED-status gate — an unmeasured/partial manifest raises, it never silently degrades
    to the flat haircut.

    Returns `(cost_model, provenance_dict_or_None)`.
    """
    if config.cost_model == "flat_bps":
        return CostModel(config.round_trip_bps), None
    if config.cost_model != "component_measured":
        raise ValueError(f"_bind_cost_model: unrecognised cost_model {config.cost_model!r}")

    manifest_path = Path(config.cost_model_manifest_path)
    manifest_bytes = manifest_path.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes.decode("utf-8"))

    instruments = config.instruments
    if not (isinstance(instruments, list) and len(instruments) == 1):
        raise ValueError(
            "_bind_cost_model: cost_model='component_measured' requires universe.instruments "
            f"to be a single-element list (got {instruments!r}) — a component calibration is "
            "instrument-specific; binding one manifest to an ambiguous multi-instrument or "
            "'ALL' universe would silently misprice every instrument it doesn't match."
        )
    instrument = instruments[0]

    model = ComponentCostModel.from_manifest(
        manifest, instrument=instrument,
        source=f"{manifest_path.as_posix()} sha256:{manifest_sha256}",
    )
    return model, model.provenance()


@dataclass
class RunResult:
    hypothesis: str
    per_instrument: dict[str, EdgeReport]
    pooled: EdgeReport
    config_sha256: str
    hypothesis_sha256: str
    exit_model: str
    round_trip_bps: float
    cost_model_provenance: "dict | None" = None


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
        self.cost_model, self.cost_model_provenance = _bind_cost_model(config)
        self.agg = EdgeAggregator()
        # Populated per-instrument by `_load_candles` ONLY on the windowed corpus_store path
        # -- {instrument: {dataset_id, csv_sha256, csv_path, requested, resolved}} -- so a run
        # manifest can prove which exact admitted bytes a window read, per the same discipline
        # `corpus_gate.CorpusAdmission` states for the non-windowed path. Empty for a run with
        # no `config.window` declared (the plain CandleLoader path carries no such object to
        # surface today; adding that is a separate, larger change, out of this scope).
        self.corpus_provenance: "dict[str, dict]" = {}

    # -- candle loading -------------------------------------------------------
    def _load_candles(self, csv_path: str, instrument: str) -> "tuple[list, list[bool] | None]":
        """Returns (candles, in_window). `in_window` is None for the default whole-corpus
        `CandleLoader` path — byte-identical to every call before `config.window` existed.
        When `config.window` is declared, routes through the gated `corpus_store` instead
        and `csv_path` is IGNORED: `corpus_store.read` resolves its own admitted path by
        instrument/timeframe, so silently honoring a caller-supplied path here could serve
        different bytes than what the window's provenance claims to have read."""
        if self.config.window is not None:
            from data_ingestion import corpus_store
            w = self.config.window
            tf = _pattern_timeframe(self.config.pattern)
            r = corpus_store.read(
                instrument, tf,
                start=datetime.fromisoformat(w["start"]),
                end=datetime.fromisoformat(w["end"]),
                warmup_bars=w["lead_in_bars"], tail_bars=w["tail_bars"],
            )
            self.corpus_provenance[instrument] = {
                "dataset_id": r.dataset_id,
                "csv_path": r.csv_path,
                "csv_sha256": r.csv_sha256,
                "requested": [str(r.requested[0]), str(r.requested[1])],
                "resolved": [str(r.resolved[0]), str(r.resolved[1])],
                "lead_in_bars": r.lead_in_bars,
                "tail_bars": r.tail_bars,
            }
            return r.candles, r.in_window

        from runtime.backtest_v2 import CandleLoader   # reuse the proven loader
        candles = list(CandleLoader(csv_path, instrument).stream())
        for i, c in enumerate(candles):
            c.index = i                                 # absolute index = stream position
        return candles, None

    # -- single instrument ----------------------------------------------------
    def run_instrument(self, hyp, csv_path: str, instrument: str) -> tuple[EdgeReport, list[Outcome]]:
        cfg = self.config
        candles, in_window = self._load_candles(csv_path, instrument)
        ctx = {"instrument": instrument}
        outcomes: list[Outcome] = []
        n = len(candles)

        # No window declared: unchanged range(cfg.warmup, n), byte-identical to before this
        # existed. A window declared: detect ONLY on in-window bars (lead-in and tail bars
        # are loaded so the detect-window and forward-walk have real history/future to use,
        # but are never themselves signal-detection candidates — extending the measured range
        # by tail_bars would defeat the point of measuring exactly the requested window).
        # `in_window` is contiguous (False*, True*, False*) by corpus_store's own construction
        # (never interleaved), so its first/last True index bound a single detection range.
        if in_window is None:
            i_lo, i_hi = cfg.warmup, n
        else:
            true_idxs = [i for i, f in enumerate(in_window) if f]
            i_lo = max(true_idxs[0], cfg.warmup) if true_idxs else n
            i_hi = (true_idxs[-1] + 1) if true_idxs else n

        for i in range(i_lo, i_hi):
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
        # `pooled.round_trip_bps` (not `self.config.round_trip_bps`): for the flat model these
        # are numerically identical (EdgeAggregator sets it directly from `cost_model
        # .round_trip_bps`, which IS `config.round_trip_bps`) — byte-identical, verified. For a
        # component model there IS no single declared bps value; `pooled.round_trip_bps` is the
        # REALIZED mean effective bps EdgeAggregator already computes over this book, which is
        # the honest number to report, not a copy of an unrelated flat-model config default.
        return RunResult(hyp.name, per, pooled, self.config.sha256(), _hypothesis_sha256(hyp),
                         self.config.exit_model, pooled.round_trip_bps,
                         self.cost_model_provenance)


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
    # `cost_model=rr.cost_model_provenance` is None for the flat model (byte-identical to
    # every report before component costs existed — `truth_standard_block` treats an omitted
    # `cost_model` kwarg and an explicit `None` identically) and the full SEM-015 component
    # breakdown otherwise.
    d.update(provenance_block(rr.exit_model, rr.round_trip_bps, cost_model=rr.cost_model_provenance))
    return d


def edge_report_json(rr: RunResult) -> str:
    return json.dumps(run_result_to_dict(rr), sort_keys=True, indent=2)
