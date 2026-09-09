"""
corpus_gate.py
================================================================================
The single corpus admission seam: IDENTITY, then SEQUENCE, then PLAUSIBILITY.

Composes the two gates that already exist rather than adding a third:

  1. ``dataset_registry.admit_csv_path`` -- R3 IDENTITY. Which bound dataset is
     this path, is its canonical artifact hash intact, and is the request a
     declared-forensic one? Always fail-closed: identity is not a threshold
     question, so ``enforce`` does not soften it.
  2. ``dataset_integrity.validate_dataset`` -- L2 whole-SEQUENCE completeness.
     Duplicates, monotonicity, future stamps, modal delta, missing candles.
  3. ``_plausibility`` (this module) -- the checks a *completeness* gate cannot
     make. See D-1..D-4 below.

Ordering is deliberate: verify WHAT THE FILE IS before spending O(n) on WHAT IS
IN IT. A forensic H4 CSV is rejected before a single candle is parsed.

WHY THIS MODULE EXISTS
----------------------
``backtest_v2._preflight_dataset`` was the only place steps 1-2 were composed.
Every ``src/research/`` consumer read its corpus with a bare ``pd.read_csv`` --
no identity, no sequence gate, not even ``CandleLoader.stream()``'s inline L1/L2
backstop (F-039). Their artifacts therefore carry no dataset provenance, which
is why two resolver runs on nominally the same corpus can disagree with nothing
recording whether they read the same bytes. This module is the one composition;
``_preflight_dataset`` delegates to it so a research copy cannot drift from the
backtest one (the F-052 discipline: one behaviour, one authority).

PLAUSIBILITY CHECKS (D-1..D-4)
------------------------------
Injected from how MT5-sourced FX/metals corpora actually fail. Each has a named
downstream consequence in THIS codebase; none is a generic lint.

  D-1  LATTICE PHASE  -> HARD
       Modal-delta passes on a file whose bars are all 15 min apart but sit at
       :07/:22/:37. ``build_htf_id_timeline`` phase-locks HTF windows by index,
       so an off-phase corpus silently mis-assigns every ``htf_id`` -- the
       resolver's own docstring warns this inflates SWEEP<->RANGE cells, and
       F-080 had to MEASURE the H4 grid phase for the same reason. F-099's
       Test 2 hit this defect directly (19/20 samples off-lattice).
       The phase VALUE is not required to be zero (a broker day may open at
       01:00); it is required to be CONSTANT.

  D-2  FROZEN BARS (o==h==l==c)  -> observation, WARN only if configured
       ``candle_math.body_ratio`` guards the zero-range divide and returns 0.0,
       so a frozen bar is indistinguishable from a genuine doji in the 48-dim
       vector and classifies into RANGE via the first-match exhaust.

  D-3  ZERO-VOLUME BARS  -> observation, WARN only if configured
       F-099 established MT5 ``volume`` is TICK_VOLUME_APPROXIMATE; a zero means
       no ticks arrived (feed gap / synthetic fill), not a quiet market.
       ``compute_volume_features`` derives ``volume_ratio`` and the adaptive
       ``volume_spike`` percentile from these.

  D-4  PRICE-GAP MAGNITUDE  -> observation, WARN only if configured
       The sequence gate counts missing BARS and never looks at price
       DISCONTINUITY. Gold gaps on the Sunday open; F-080 localised 30 of 30
       engine/TradingView divergences to one slot per trading day.
       Reported as |open[i] - close[i-1]| / median_true_range.

AUTHORITY: D-1 is HARD because it silently corrupts HTF assignment -- a
correctness failure, not a quality opinion. D-2/D-3/D-4 are OBSERVATIONS and per
CLAUDE.md 6.5 an observation earns no authority: they never reject a corpus, and
they stay silent unless a ``plausibility`` config block explicitly arms a
threshold. Absence of that block means NO behaviour, not an assumed default.
================================================================================
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from data_ingestion.dataset_registry import DatasetAdmissionError, admit_csv_path
from data_ingestion.dataset_integrity import (
    _TF_MINUTES,
    DatasetDecision,
    DatasetIntegrityError,
    _cfg,
    _parse_symbol_tf,
    _stream_candles,
    validate_dataset,
)
from data_ingestion.xauusd_phase1_candidate import Phase1CandidateError

logger = logging.getLogger("CRT.CorpusGate")


@dataclass(frozen=True)
class CorpusAdmission:
    """Everything a caller needs to read a corpus AND to attribute what it read.

    ``dataset_id`` + ``file_hash`` are the provenance pair: they are what a run
    manifest records so a later reader can tell whether two runs read the same
    bytes. That question is currently unanswerable for every research artifact
    in the repo, which is the whole reason this type exists.
    """

    filepath: str
    dataset_id: Optional[str]
    bound: bool
    rewritten: bool
    decision: str
    file_hash: Optional[str]
    plausibility: dict = field(default_factory=dict)
    report: dict = field(default_factory=dict)

    @property
    def approved(self) -> bool:
        return self.decision != DatasetDecision.REJECT.value


def _median_true_range(highs, lows, closes) -> float:
    """Median TR over the corpus. Scale reference for D-4, deliberately median
    (not mean) so a handful of gap bars cannot inflate their own yardstick."""
    trs = []
    prev_close = None
    for h, l, c in zip(highs, lows, closes):
        if prev_close is None:
            trs.append(h - l)
        else:
            trs.append(max(h - l, abs(h - prev_close), abs(l - prev_close)))
        prev_close = c
    trs = [t for t in trs if t > 0]
    return statistics.median(trs) if trs else 0.0


def _plausibility(
    path: Path, bar_minutes: int, cfg: dict
) -> tuple[dict, list[str], list[str]]:
    """D-1..D-4 over one streaming pass. Returns (metrics, hard, warnings).

    A SECOND pass over the file, deliberately. Folding these into
    ``validate_dataset``'s own walk would mean threading a flag through the gate
    every backtest instrument shares, to save one O(n) read of a few-MB CSV.
    The shared surface is worth more than the pass.
    """
    period = bar_minutes * 60
    phases: set[int] = set()
    frozen = 0
    zero_vol = 0
    n = 0
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    gaps: list[float] = []
    prev_close: Optional[float] = None

    for _line, ts, o, h, l, c, v in _stream_candles(path):
        n += 1
        phases.add(int(ts.timestamp()) % period)
        if o == h == l == c:
            frozen += 1
        if v == 0:
            zero_vol += 1
        if prev_close is not None:
            gaps.append(abs(o - prev_close))
        prev_close = c
        highs.append(h)
        lows.append(l)
        closes.append(c)

    hard: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {"rows": n}

    if n == 0:
        return metrics, hard, warnings

    # -- D-1 lattice phase (HARD) ---------------------------------------------
    metrics["lattice_phase_seconds"] = sorted(phases)[:8]
    metrics["lattice_phase_constant"] = len(phases) == 1
    if len(phases) != 1:
        hard.append(
            f"D-1 lattice: timestamps occupy {len(phases)} distinct phases mod "
            f"{period}s (first few: {sorted(phases)[:8]}); expected exactly 1. "
            "An off-phase corpus mis-assigns every htf_id downstream."
        )

    # -- D-2 frozen bars ------------------------------------------------------
    metrics["frozen_bars"] = frozen
    metrics["frozen_pct"] = round(frozen / n, 6)

    # -- D-3 zero-volume bars -------------------------------------------------
    metrics["zero_volume_bars"] = zero_vol
    metrics["zero_volume_pct"] = round(zero_vol / n, 6)

    # -- D-4 price-gap magnitude ----------------------------------------------
    mtr = _median_true_range(highs, lows, closes)
    metrics["median_true_range"] = round(mtr, 8)
    if gaps and mtr > 0:
        ordered = sorted(gaps)
        p99 = ordered[min(len(ordered) - 1, int(0.99 * len(ordered)))]
        metrics["gap_p99_tr"] = round(p99 / mtr, 4)
        metrics["gap_max_tr"] = round(max(gaps) / mtr, 4)
        metrics["gap_over_3tr"] = sum(1 for g in gaps if g > 3 * mtr)
    else:
        metrics["gap_p99_tr"] = None
        metrics["gap_max_tr"] = None
        metrics["gap_over_3tr"] = 0

    # -- thresholds are OPT-IN. No block => observation only, never a warning.
    # Absence means no behaviour, not an assumed default (CLAUDE.md 6.5).
    pl = cfg.get("plausibility")
    if isinstance(pl, dict):
        if "max_frozen_pct" in pl and metrics["frozen_pct"] > float(pl["max_frozen_pct"]):
            warnings.append(
                f"D-2 frozen bars {metrics['frozen_pct']:.2%} ({frozen}/{n}) "
                f"exceeds {float(pl['max_frozen_pct']):.2%}"
            )
        if "max_zero_volume_pct" in pl and metrics["zero_volume_pct"] > float(
            pl["max_zero_volume_pct"]
        ):
            warnings.append(
                f"D-3 zero-volume bars {metrics['zero_volume_pct']:.2%} "
                f"({zero_vol}/{n}) exceeds {float(pl['max_zero_volume_pct']):.2%}"
            )
        if "max_gap_true_ranges" in pl and metrics["gap_max_tr"] is not None:
            lim = float(pl["max_gap_true_ranges"])
            if metrics["gap_max_tr"] > lim:
                warnings.append(
                    f"D-4 largest price gap {metrics['gap_max_tr']:.2f}x median TR "
                    f"exceeds {lim:.2f}x ({metrics['gap_over_3tr']} bars over 3x)"
                )

    return metrics, hard, warnings


def admit_corpus(
    filepath: str | Path,
    instrument: str = "",
    *,
    enforce: bool = True,
    write_report: bool = True,
    check_plausibility: bool = True,
    log: Optional[logging.Logger] = None,
) -> CorpusAdmission:
    """Admit one historical OHLCV corpus, or fail closed.

    Args:
        filepath: requested path. May be rewritten to a bound record's canonical
            artifact (the legacy XAUUSD_M15* path).
        instrument: symbol hint, used by both the admission heuristics and the
            integrity gate's path/symbol agreement check.
        enforce: True -> a REJECT decision raises DatasetIntegrityError.
            False -> return with decision=REJECT and let the caller skip.
            ONLY affects the SEQUENCE/PLAUSIBILITY decision. IDENTITY failures
            raise either way.
        write_report: forwarded to validate_dataset. Research callers should
            pass False -- see the report-slot collision note below.
        check_plausibility: run D-1..D-4. One extra streaming pass.

    Raises:
        DatasetAdmissionError: identity -- unbound guard, forensic path, hash drift.
        DatasetIntegrityError: sequence/plausibility REJECT, when enforce=True.

    NOTE on write_report: ``_write_fingerprint`` names reports
    ``{symbol}_{tf}.json``, so ``data/mt5/XAUUSD_M15.csv`` (canonical, 47,275
    rows) and ``data/XAUUSD_M15.csv`` (a declared forensic_paths entry, 2,116
    rows) COLLIDE on one slot. A research caller passing write_report=True would
    overwrite whichever ran last and make the on-disk report unattributable.
    Pass False and persist ``report`` into the run manifest instead.
    """
    log = log or logger
    original = str(filepath)

    # -- 1. IDENTITY -- always fail-closed, before any content is read --------
    try:
        adm = admit_csv_path(filepath, instrument)
    except Phase1CandidateError as exc:
        raise DatasetAdmissionError(str(exc)) from exc

    if adm.rewritten:
        log.info(
            "[corpus_gate] path rewritten to canonical artifact: %s -> %s (%s)",
            original,
            adm.filepath,
            adm.dataset_id,
        )
    if not adm.bound:
        log.warning(
            "[corpus_gate] %s is UNBOUND (path passthrough) -- no dataset_id, no "
            "hash verification. Provenance for this run is unattributable.",
            adm.filepath,
        )

    # -- 2. SEQUENCE ----------------------------------------------------------
    report = validate_dataset(
        adm.filepath,
        instrument=instrument or None,
        raise_on_fail=False,
        write_report=write_report,
    )
    decision = report.get("decision", DatasetDecision.APPROVE.value)
    hard = list(report.get("hard_failures", []))
    warns = list(report.get("warnings", []))

    # -- 3. PLAUSIBILITY ------------------------------------------------------
    metrics: dict = {}
    if check_plausibility:
        path = Path(adm.filepath)
        _sym, tf = _parse_symbol_tf(path)
        cfg = _cfg()
        bar_minutes = _TF_MINUTES.get((tf or "").upper()) or int(
            cfg.get("default_bar_minutes", 15)
        )
        metrics, p_hard, p_warn = _plausibility(path, bar_minutes, cfg)
        hard.extend(p_hard)
        warns.extend(p_warn)
        if p_hard:
            decision = DatasetDecision.REJECT.value
        elif p_warn and decision == DatasetDecision.APPROVE.value:
            decision = DatasetDecision.WARN.value
        # Keep the returned report self-consistent with the returned decision --
        # a caller persisting `report` must not see a stale APPROVE.
        report = {
            **report,
            "decision": decision,
            "hard_failures": hard,
            "warnings": warns,
            "plausibility": metrics,
        }

    result = CorpusAdmission(
        filepath=adm.filepath,
        dataset_id=adm.dataset_id,
        bound=adm.bound,
        rewritten=adm.rewritten,
        decision=decision,
        file_hash=report.get("file_hash"),
        plausibility=metrics,
        report=report,
    )

    if decision == DatasetDecision.REJECT.value:
        msg = f"{adm.filepath}: " + "; ".join(hard)
        log.error(
            "[corpus_gate] REJECT %s (%s): %s", adm.filepath, instrument, "; ".join(hard)
        )
        if enforce:
            raise DatasetIntegrityError(msg)
    elif decision == DatasetDecision.WARN.value:
        log.warning(
            "[corpus_gate] WARN %s (%s): %s", adm.filepath, instrument, "; ".join(warns)
        )
    else:
        log.info(
            "[corpus_gate] APPROVE %s (dataset_id=%s hash=%s)",
            adm.filepath,
            adm.dataset_id,
            (result.file_hash or "")[:12],
        )

    return result
