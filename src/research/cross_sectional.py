"""cross_sectional.py — Program 5: cross-sectional relative-value (dispersion) measurement.

The object under test is **dispersion**, not momentum: at each rebalance bar `t` the N coins
are ranked by an interpreter's score, the top-k are bought and the bottom-k sold (equal-weight,
market-neutral), held `H` bars, and the long-short spread is measured NET of a flat round-trip
cost. Momentum / reversal / inverse-vol are merely candidate *interpreters* of the dispersion.

Why a new module and not a `Hypothesis`: the M3 `Hypothesis.detect()` → `forward_walk()` path is
single-instrument SL/TP geometry whose statistical unit is a trade `Outcome`. A market-neutral
fixed-horizon spread has no per-leg SL/TP — its unit is *one spread return per rebalance*. So this
reuses the M4 **statistics** (`permutation_p_value`, `benjamini_hochberg`) and the **cost standard**
(`DEFAULT_ROUND_TRIP_BPS`) on a native panel, never the trade geometry.

ISOLATION: pure stdlib + research-internal imports only — never the live spine.
DETERMINISM: panels iterate symbols/timestamps in sorted order; every RNG is seeded from a stable
string; the serialized report carries NO wall-clock — byte-comparable across runs.
NO-LOOKAHEAD: a score at bar `t` reads only closes ≤ `t`; the position is entered at `close[t]` and
exited at `close[t+H]` (future bars strictly `> t`).

Full design: docs/research-readiness/program-5-cross-sectional-preregistration.md.
"""

from __future__ import annotations

import bisect
import hashlib
import random
import statistics
from dataclasses import dataclass, field

from research.costs import DEFAULT_ROUND_TRIP_BPS
from research.qualification import benjamini_hochberg, permutation_p_value

# Verdict labels (the §6 ladder). REDUNDANT = passes gates 1–6 but does not beat the
# equal-weight market basket (dispersion real but not monetizable beyond beta).
PROMOTE, REJECT, INSUFFICIENT, REDUNDANT = "PROMOTE", "REJECT", "INSUFFICIENT", "REDUNDANT"
# Program 6b: funding-only decompositions are NOT realizable trades — they may ONLY carry these two
# diagnostic verdicts, never PROMOTE, and never enter the BH cohort (no authority leakage).
DIAGNOSTIC_POSITIVE, DIAGNOSTIC_NEGATIVE = "DIAGNOSTIC_POSITIVE", "DIAGNOSTIC_NEGATIVE"

CROSS_SECTIONAL_VERSION = "1.0"   # bump when the construction / gate sequence changes
_PF_CAP = 9999.0                  # finite stand-in for an all-wins profit factor (JSON-safe)


# ─────────────────────────────────────────────────────────────────────────────
# panel
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Panel:
    """A time-aligned close-price panel: every symbol shares the same `timestamps`.

    `funding` / `basis` are OPTIONAL perp side-channels (Program 6), parallel to `timestamps`
    when present and empty otherwise — so a Program-5 close-only `Panel` is unchanged.
    """
    symbols: tuple[str, ...]                 # sorted
    timestamps: tuple                        # common (inner-joined), sorted
    closes: dict[str, tuple[float, ...]]      # symbol -> closes parallel to `timestamps`
    funding: dict[str, tuple[float, ...]] = field(default_factory=dict)  # ffilled 8h->panel ts
    basis: dict[str, tuple[float, ...]] = field(default_factory=dict)    # native M15 premium index
    funding_settle: dict[str, tuple[float, ...]] = field(default_factory=dict)  # DISCRETE 8h amount at settle bars, else 0 (Program 6b)

    def __len__(self) -> int:
        return len(self.timestamps)


def _read_perp(perp_dir, symbol: str, parse_ts):
    """Read a symbol's perp side-channels from `perp_dir` (fail-fast if absent).

    Returns (funding_times sorted, funding_rates parallel, basis_map[ts->premium]). Timestamps are
    parsed with the SAME parser CandleLoader uses, so they key-match the close panel exactly.
    """
    import csv
    from pathlib import Path

    fpath = Path(perp_dir) / f"{symbol}_FUNDING_8H.csv"
    bpath = Path(perp_dir) / f"{symbol}_BASIS_M15.csv"
    if not fpath.exists() or not bpath.exists():
        raise FileNotFoundError(
            f"load_panel: perp data for {symbol} missing under {perp_dir} "
            f"(need {fpath.name} + {bpath.name}). Run scripts/data/fetch_perp_funding.py."
        )

    ftimes: list = []
    frates: list[float] = []
    with open(fpath, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ftimes.append(parse_ts(row["timestamp"]))
            frates.append(float(row["funding_rate"]))
    order = sorted(range(len(ftimes)), key=lambda i: ftimes[i])   # ascending by settlement time
    ftimes = [ftimes[i] for i in order]
    frates = [frates[i] for i in order]

    bmap: dict = {}
    with open(bpath, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            bmap[parse_ts(row["timestamp"])] = float(row["premium_index"])
    if not ftimes or not bmap:
        raise ValueError(f"load_panel: empty perp series for {symbol}")
    return ftimes, frates, bmap


def load_panel(csv_map: dict[str, str], perp_dir: str | None = None) -> Panel:
    """Inner-join the given symbols' M15 closes on common timestamps (fail-fast on empties).

    Reuses the proven `CandleLoader` (imported lazily so unit tests that construct a `Panel`
    directly never pull the heavy runtime import).

    When `perp_dir` is given (Program 6), each symbol's funding (8h) + basis (M15) are loaded and
    aligned to the panel: **basis** is the contemporaneous premium-index at `t`; **funding** is
    FORWARD-FILLED — the last settlement with time <= `t` (no-lookahead). `perp_dir=None` leaves the
    close-only Program-5 path byte-for-byte unchanged.
    """
    from runtime.backtest_v2 import CandleLoader   # reuse the proven loader

    by_symbol: dict[str, dict] = {}
    for symbol in sorted(csv_map):
        series: dict = {}
        for c in CandleLoader(csv_map[symbol], symbol).stream():
            series[c.timestamp] = float(c.close)
        if not series:
            raise ValueError(f"load_panel: no candles for {symbol} ({csv_map[symbol]})")
        by_symbol[symbol] = series

    if len(by_symbol) < 2:
        raise ValueError("load_panel: cross-sectional requires >= 2 symbols")

    common = set.intersection(*(set(s) for s in by_symbol.values()))

    perp: dict = {}
    if perp_dir is not None:
        from data_ingestion.ohlcv_schema import parse_ohlcv_timestamp   # same parser as CandleLoader
        for symbol in sorted(by_symbol):
            ftimes, frates, bmap = _read_perp(perp_dir, symbol, parse_ohlcv_timestamp)
            perp[symbol] = (ftimes, frates, bmap)
            common &= set(bmap)                 # require a basis value at every panel ts

    if not common:
        raise ValueError("load_panel: symbols share no common timestamps (inner-join empty)")
    ts = tuple(sorted(common))
    closes = {sym: tuple(by_symbol[sym][t] for t in ts) for sym in sorted(by_symbol)}
    for sym, cs in closes.items():
        if any(c <= 0 for c in cs):
            raise ValueError(f"load_panel: non-positive close for {sym}")

    funding: dict = {}
    basis: dict = {}
    funding_settle: dict = {}
    if perp_dir is not None:
        for sym in sorted(by_symbol):
            ftimes, frates, bmap = perp[sym]
            settle_map = dict(zip(ftimes, frates))     # settlement time -> rate (8h grid ⊂ M15 grid)
            f_aligned: list[float] = []
            for t in ts:
                idx = bisect.bisect_right(ftimes, t) - 1   # last settlement with time <= t (ffill)
                if idx < 0:
                    raise ValueError(f"load_panel: no funding settlement <= {t} for {sym}")
                f_aligned.append(frates[idx])
            funding[sym] = tuple(f_aligned)
            basis[sym] = tuple(bmap[t] for t in ts)
            # discrete per-bar settlement: the rate IF a settlement lands on this exact bar, else 0
            funding_settle[sym] = tuple(settle_map.get(t, 0.0) for t in ts)

    return Panel(tuple(sorted(by_symbol)), ts, closes, funding, basis, funding_settle)


def build_panel(symbols, timestamps, closes, funding=None, basis=None, funding_settle=None) -> Panel:
    """Construct + validate a Panel from in-memory series (used by tests).

    `funding` / `basis` / `funding_settle` are optional; when given they must align to `timestamps`
    like `closes`.
    """
    syms = tuple(sorted(symbols))
    ts = tuple(timestamps)
    n = len(ts)
    out: dict[str, tuple[float, ...]] = {}
    for s in syms:
        cs = tuple(float(x) for x in closes[s])
        if len(cs) != n:
            raise ValueError(f"build_panel: {s} length {len(cs)} != {n} (misaligned)")
        out[s] = cs

    def _aux(d, label: str) -> dict:
        if d is None:
            return {}
        r: dict[str, tuple[float, ...]] = {}
        for s in syms:
            vs = tuple(float(x) for x in d[s])
            if len(vs) != n:
                raise ValueError(f"build_panel: {label} {s} length {len(vs)} != {n} (misaligned)")
            r[s] = vs
        return r

    return Panel(syms, ts, out, _aux(funding, "funding"), _aux(basis, "basis"),
                 _aux(funding_settle, "funding_settle"))


# ─────────────────────────────────────────────────────────────────────────────
# scores (no-lookahead: read closes <= t only)
# ─────────────────────────────────────────────────────────────────────────────
def scores(panel: Panel, t: int, kind: str, L: int) -> dict[str, float]:
    """Per-symbol cross-sectional score at bar `t` using only data in [t-L, t] (no-lookahead).

    Program-5 kinds read closes; Program-6 carry/basis kinds read the perp side-channels (trailing
    mean over L, mirroring the `vol` window). Sign convention: `carry`/`basis` score = -mean (long
    the LOW-funding / LOW-basis names — classic carry/convergence); the `_inv` kinds flip the sign
    (long the HIGH names) so both directions are tested as separate interpreters under BH.
    """
    out: dict[str, float] = {}
    for s in panel.symbols:
        c = panel.closes[s]
        if kind == "momentum":
            out[s] = c[t] / c[t - L] - 1.0
        elif kind == "reversal":
            out[s] = -(c[t] / c[t - L] - 1.0)              # long the losers
        elif kind == "vol":
            rets = [c[i] / c[i - 1] - 1.0 for i in range(t - L + 1, t + 1)]
            out[s] = -statistics.pstdev(rets) if len(rets) > 1 else 0.0   # long the calm
        elif kind in ("carry", "carry_inv"):
            f = panel.funding[s]
            m = sum(f[t - L + 1:t + 1]) / L                 # trailing-mean funding (carry regime)
            out[s] = -m if kind == "carry" else m           # carry: long LOW funding
        elif kind in ("basis", "basis_inv"):
            b = panel.basis[s]
            m = sum(b[t - L + 1:t + 1]) / L                 # trailing-mean premium (basis regime)
            out[s] = -m if kind == "basis" else m           # basis: long LOW basis (convergence)
        else:
            raise ValueError(f"scores: unknown kind {kind!r}")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# weight formers (deterministic; ties broken by symbol name)
# ─────────────────────────────────────────────────────────────────────────────
def _ranked(score: dict[str, float]) -> list[str]:
    return sorted(score, key=lambda s: (score[s], s), reverse=True)   # high score first


def long_short_weights(score: dict[str, float], k: int) -> dict[str, float]:
    """Top-k long (+1/k) / bottom-k short (-1/k) — market-neutral (Σw = 0)."""
    order = _ranked(score)
    w = {s: 0.0 for s in score}
    for s in order[:k]:
        w[s] += 1.0 / k
    for s in order[-k:]:
        w[s] += -1.0 / k
    return w


def long_only_weights(score: dict[str, float], k: int) -> dict[str, float]:
    order = _ranked(score)
    w = {s: 0.0 for s in score}
    for s in order[:k]:
        w[s] = 1.0 / k
    return w


def market_weights(symbols) -> dict[str, float]:
    n = len(symbols)
    return {s: 1.0 / n for s in symbols}


def shuffled_weights(score: dict[str, float], k: int, rng: random.Random) -> dict[str, float]:
    """L/S after permuting the score VALUES across symbols (destroys the ranking link)."""
    syms = sorted(score)
    vals = [score[s] for s in syms]
    rng.shuffle(vals)
    return long_short_weights(dict(zip(syms, vals)), k)


def random_ls_weights(symbols, k: int, rng: random.Random) -> dict[str, float]:
    syms = sorted(symbols)
    picks = rng.sample(syms, min(2 * k, len(syms)))
    w = {s: 0.0 for s in syms}
    for s in picks[:k]:
        w[s] = 1.0 / k
    for s in picks[k:2 * k]:
        w[s] = -1.0 / k
    return w


# ─────────────────────────────────────────────────────────────────────────────
# net return series
# ─────────────────────────────────────────────────────────────────────────────
def rebalance_grid(L: int, H: int, n: int, warmup: int = 0) -> list[int]:
    """Non-overlapping rebalance points: start = max(L, warmup), step H, need t+H < n."""
    start = max(L, warmup)
    t, grid = start, []
    while t + H < n:
        grid.append(t)
        t += H
    return grid


def net_series(panel: Panel, grid: list[int], weight_at, H: int,
               round_trip_bps: float = DEFAULT_ROUND_TRIP_BPS) -> list[float]:
    """Per-rebalance NET spread return: Σ wₛ·fwd_returnₛ − (Σ|wₛ|)·bps. `weight_at(t)`→weights."""
    haircut = round_trip_bps / 10_000.0
    out: list[float] = []
    for t in grid:
        w = weight_at(t)
        gross = sum(w[s] * (panel.closes[s][t + H] / panel.closes[s][t] - 1.0) for s in w)
        gross_notional = sum(abs(x) for x in w.values())
        out.append(gross - gross_notional * haircut)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# series statistics (R-free: native fractional-return units)
# ─────────────────────────────────────────────────────────────────────────────
def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _profit_factor(xs: list[float]) -> float:
    gp = sum(x for x in xs if x > 0)
    gl = -sum(x for x in xs if x < 0)
    if gl <= 0:
        return _PF_CAP if gp > 0 else 0.0
    return min(gp / gl, _PF_CAP)


def _win_rate(xs: list[float]) -> float:
    return sum(1 for x in xs if x > 0) / len(xs) if xs else 0.0


def _split_is_oos(series: list[float], oos_split: float) -> tuple[list[float], list[float]]:
    cut = int(round(len(series) * (1.0 - oos_split)))
    return series[:cut], series[cut:]


def _seed_for(name: str) -> int:
    return int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:8], 16)


# ─────────────────────────────────────────────────────────────────────────────
# qualification
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Interpreter:
    name: str
    kind: str        # momentum | reversal | vol | carry | carry_inv | basis | basis_inv
    L: int
    H: int


@dataclass(frozen=True)
class XSQualConfig:
    k: int
    min_samples: int
    expectancy_min: float
    pf_min: float
    oos_split: float
    oos_retention_min: float
    n_permutations: int
    significance_alpha: float
    round_trip_bps: float = DEFAULT_ROUND_TRIP_BPS
    warmup: int = 0


# control names, in deterministic order. `equal_weight_market` is the redundancy benchmark.
CONTROL_NAMES = ("reversed", "shuffled", "long_only", "equal_weight_market", "random_ls")


def _interpreter_series(panel, itp: Interpreter, qcfg: XSQualConfig):
    """Build the interpreter's net series + each control's net series (paired, same grid/H)."""
    grid = rebalance_grid(itp.L, itp.H, len(panel), qcfg.warmup)
    k = qcfg.k
    rng_shuf = random.Random(_seed_for(itp.name + "::shuffled"))
    rng_rand = random.Random(_seed_for(itp.name + "::random_ls"))

    def sc(t):
        return scores(panel, t, itp.kind, itp.L)

    weight_fns = {
        "_interp": lambda t: long_short_weights(sc(t), k),
        "reversed": lambda t: long_short_weights({s: -v for s, v in sc(t).items()}, k),
        "shuffled": lambda t: shuffled_weights(sc(t), k, rng_shuf),
        "long_only": lambda t: long_only_weights(sc(t), k),
        "equal_weight_market": lambda t: market_weights(panel.symbols),
        "random_ls": lambda t: random_ls_weights(panel.symbols, k, rng_rand),
    }
    series = {name: net_series(panel, grid, fn, itp.H, qcfg.round_trip_bps)
              for name, fn in weight_fns.items()}
    return grid, series


def _evaluate(itp, series: dict, qcfg: XSQualConfig,
              control_names=CONTROL_NAMES, market_key: str = "equal_weight_market") -> dict:
    """Gates 1–6 + the redundancy check for one interpreter (BH/gate-7 applied later).

    `control_names`/`market_key` default to the Program-5 set (byte-identical for Programs 5/6);
    Program 6b passes `HARVEST_CONTROL_NAMES` (adds the `cash` zero-series benchmark).
    """
    interp = series["_interp"]
    n = len(interp)
    mean_net = _mean(interp)
    pf = _profit_factor(interp)
    is_s, oos_s = _split_is_oos(interp, qcfg.oos_split)
    is_mean, oos_mean = _mean(is_s), _mean(oos_s)
    retention = (oos_mean / is_mean) if is_mean > 0 else 0.0

    control_means = {c: _mean(series[c]) for c in control_names}
    win_name = max(control_means, key=lambda c: control_means[c])
    win_mean = control_means[win_name]
    baseline_delta = mean_net - win_mean
    market_mean = control_means[market_key]
    beats_market = (mean_net - market_mean) > 0
    p_value = permutation_p_value(interp, series[win_name],
                                  qcfg.n_permutations, _seed_for(itp.name))

    reasons: list[str] = []
    insufficient = False
    if n < qcfg.min_samples:
        reasons.append(f"FAILED_gate1_sample: n={n} < {qcfg.min_samples}")
        insufficient = True
    elif mean_net < qcfg.expectancy_min:
        reasons.append(f"FAILED_gate2_expectancy: E={mean_net:.6f} < {qcfg.expectancy_min}")
    elif pf < qcfg.pf_min:
        reasons.append(f"FAILED_gate3_profit_factor: PF={pf:.4f} < {qcfg.pf_min}")
    elif baseline_delta <= 0:
        reasons.append(f"FAILED_gate4_beats_control: E={mean_net:.6f} <= {win_name} {win_mean:.6f}")
    elif not (is_mean > 0 and oos_mean > 0 and retention >= qcfg.oos_retention_min):
        reasons.append(f"FAILED_gate5_oos_retention: is={is_mean:.6f} oos={oos_mean:.6f} "
                       f"ret={retention:.4f} < {qcfg.oos_retention_min}")
    elif p_value > qcfg.significance_alpha:
        reasons.append(f"FAILED_gate6_permutation: p={p_value:.4f} > {qcfg.significance_alpha}")

    return {
        "name": itp.name, "kind": itp.kind, "L": itp.L, "H": itp.H, "n": n,
        "expectancy": round(mean_net, 8), "profit_factor": round(pf, 4),
        "win_rate": round(_win_rate(interp), 4),
        "is_mean": round(is_mean, 8), "oos_mean": round(oos_mean, 8),
        "oos_retention": round(retention, 4),
        "winning_control": win_name, "winning_control_mean": round(win_mean, 8),
        "baseline_delta": round(baseline_delta, 8),
        "market_mean": round(market_mean, 8), "beats_market": beats_market,
        "control_means": {c: round(control_means[c], 8) for c in control_names},
        "p_value": round(p_value, 6),
        "_passed_1_to_6": not reasons, "_insufficient": insufficient,
        "reject_reasons": reasons,
    }


def _finalize(rec: dict, bh_survivors: set, alpha: float) -> dict:
    reasons = list(rec["reject_reasons"])
    if rec["_insufficient"]:
        verdict = INSUFFICIENT
    elif reasons:
        verdict = REJECT
    elif not rec["beats_market"]:
        verdict = REDUNDANT
        reasons.append(f"REDUNDANT_vs_market: E={rec['expectancy']} <= market {rec['market_mean']}")
    elif rec["name"] not in bh_survivors:
        verdict = REJECT
        reasons.append(f"FAILED_gate7_bh: p={rec['p_value']} not significant after BH FDR={alpha}")
    else:
        verdict = PROMOTE
    out = {kk: vv for kk, vv in rec.items() if not kk.startswith("_")}
    out["reject_reasons"] = reasons
    out["verdict"] = verdict
    return out


def qualify(panel: Panel, interpreters: list[Interpreter], qcfg: XSQualConfig) -> dict:
    """Run the full cohort: gates 1–6 per interpreter, then cohort BH (gate 7), then finalize."""
    pre = {}
    for itp in interpreters:
        _, series = _interpreter_series(panel, itp, qcfg)
        pre[itp.name] = _evaluate(itp, series, qcfg)

    bh_inputs = {n: r["p_value"] for n, r in pre.items() if r["_passed_1_to_6"]}
    bh_survivors = benjamini_hochberg(bh_inputs, qcfg.significance_alpha)

    results = {n: _finalize(pre[n], bh_survivors, qcfg.significance_alpha) for n in sorted(pre)}
    return {
        "cross_sectional_version": CROSS_SECTIONAL_VERSION,
        "universe": list(panel.symbols),
        "n_rebalances_total": len(panel),
        "k": qcfg.k,
        "round_trip_bps": qcfg.round_trip_bps,
        "alpha": qcfg.significance_alpha,
        "n_permutations": qcfg.n_permutations,
        "controls": list(CONTROL_NAMES),
        "interpreters": results,
        "promoted": [n for n, r in results.items() if r["verdict"] == PROMOTE],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Program 6b — carry HARVEST (funding cashflow + price/basis)
# ─────────────────────────────────────────────────────────────────────────────
# Adds the `cash` zero-series benchmark (you must beat doing nothing). `equal_weight_market` stays the
# redundancy/beta benchmark, so the verdict ladder + `_finalize` are reused unchanged.
HARVEST_CONTROL_NAMES = ("reversed", "shuffled", "long_only", "equal_weight_market", "random_ls", "cash")


@dataclass(frozen=True)
class HarvestSpec:
    """A carry-harvest interpreter. `include_price=False` is the funding-only DIAGNOSTIC twin."""
    name: str
    L: int
    H: int
    include_price: bool

    @property
    def kind(self) -> str:
        return "harvest_full" if self.include_price else "harvest_funding_only"


def harvest_net_series(panel: Panel, grid: list[int], weight_at, H: int,
                       round_trip_bps: float, include_price: bool) -> list[float]:
    """Per-rebalance NET harvest return for a long-low/short-high funding perp basket.

    For hold (t, t+H]: funding accrued = Σ_{i=t+1..t+H} funding_settle (a LONG perp PAYS when rate>0
    ⇒ the −w sign). When `include_price`, add the perp price move ≈ spot return + basis change
    (perp ≈ spot·(1+premium), so the basis-convergence PnL falls out of the premium-index change).
    """
    haircut = round_trip_bps / 10_000.0
    out: list[float] = []
    for t in grid:
        w = weight_at(t)
        gross_notional = sum(abs(x) for x in w.values())
        total = 0.0
        for s, wt in w.items():
            if wt == 0.0:
                continue
            fa = sum(panel.funding_settle[s][i] for i in range(t + 1, t + H + 1))  # (t, t+H]
            r = -wt * fa
            if include_price:
                spot_ret = panel.closes[s][t + H] / panel.closes[s][t] - 1.0
                basis_chg = panel.basis[s][t + H] - panel.basis[s][t]
                r += wt * (spot_ret + basis_chg)
            total += r
        out.append(total - gross_notional * haircut)
    return out


def _harvest_income_series(panel: Panel, grid: list[int], weight_at, H: int) -> list[float]:
    """Pre-cost funding income per rebalance (= −Σ w·funding_accrued); reported as a diagnostic."""
    out: list[float] = []
    for t in grid:
        w = weight_at(t)
        inc = 0.0
        for s, wt in w.items():
            if wt == 0.0:
                continue
            inc += -wt * sum(panel.funding_settle[s][i] for i in range(t + 1, t + H + 1))
        out.append(inc)
    return out


def _harvest_series(panel: Panel, spec: HarvestSpec, qcfg: XSQualConfig):
    """Build the spec's net harvest series + each control's (incl. the `cash` zero series)."""
    grid = rebalance_grid(spec.L, spec.H, len(panel), qcfg.warmup)
    k = qcfg.k
    rng_shuf = random.Random(_seed_for(spec.name + "::shuffled"))
    rng_rand = random.Random(_seed_for(spec.name + "::random_ls"))

    def sc(t):
        return scores(panel, t, "carry", spec.L)   # carry = −mean(funding) ⇒ long LOW funding

    weight_fns = {
        "_interp": lambda t: long_short_weights(sc(t), k),
        "reversed": lambda t: long_short_weights({s: -v for s, v in sc(t).items()}, k),
        "shuffled": lambda t: shuffled_weights(sc(t), k, rng_shuf),
        "long_only": lambda t: long_only_weights(sc(t), k),
        "equal_weight_market": lambda t: market_weights(panel.symbols),
        "random_ls": lambda t: random_ls_weights(panel.symbols, k, rng_rand),
    }
    series = {name: harvest_net_series(panel, grid, fn, spec.H, qcfg.round_trip_bps, spec.include_price)
              for name, fn in weight_fns.items()}
    series["cash"] = [0.0] * len(grid)               # beat doing nothing
    return grid, series


def _finalize_diagnostic(rec: dict, funding_income: float) -> dict:
    """Funding-only twin: strip private keys, assign a DIAGNOSTIC verdict (never PROMOTE)."""
    out = {kk: vv for kk, vv in rec.items() if not kk.startswith("_")}
    out["verdict"] = DIAGNOSTIC_POSITIVE if rec["expectancy"] > 0 else DIAGNOSTIC_NEGATIVE
    out["funding_income"] = funding_income
    return out


def qualify_harvest(panel: Panel, specs: list[HarvestSpec], qcfg: XSQualConfig) -> dict:
    """Program 6b cohort. Tradeable `harvest_full` specs run the full ladder + BH and feed `promoted`;
    funding-only specs are DIAGNOSTIC-only (no BH, no PROMOTE) and live in a separate `diagnostics`
    appendix so they never leak authority into the ranking."""
    pre: dict = {}
    income: dict = {}
    for spec in specs:
        grid, series = _harvest_series(panel, spec, qcfg)
        pre[spec.name] = _evaluate(spec, series, qcfg, HARVEST_CONTROL_NAMES, "equal_weight_market")
        income[spec.name] = round(_mean(_harvest_income_series(
            panel, grid, lambda t, L=spec.L: long_short_weights(scores(panel, t, "carry", L), qcfg.k),
            spec.H)), 8)

    tradeable = [s.name for s in specs if s.include_price]
    diagnostic = [s.name for s in specs if not s.include_price]

    bh_inputs = {n: pre[n]["p_value"] for n in tradeable if pre[n]["_passed_1_to_6"]}
    bh_survivors = benjamini_hochberg(bh_inputs, qcfg.significance_alpha)

    interpreters: dict = {}
    for n in sorted(tradeable):
        rec = _finalize(pre[n], bh_survivors, qcfg.significance_alpha)
        rec["funding_income"] = income[n]
        interpreters[n] = rec
    diagnostics = {n: _finalize_diagnostic(pre[n], income[n]) for n in sorted(diagnostic)}

    return {
        "cross_sectional_version": CROSS_SECTIONAL_VERSION,
        "universe": list(panel.symbols),
        "n_rebalances_total": len(panel),
        "k": qcfg.k,
        "round_trip_bps": qcfg.round_trip_bps,
        "alpha": qcfg.significance_alpha,
        "n_permutations": qcfg.n_permutations,
        "controls": list(HARVEST_CONTROL_NAMES),
        "interpreters": interpreters,      # tradeable only — the promotion surface
        "diagnostics": diagnostics,        # funding-only appendix — never promotable
        "promoted": [n for n, r in interpreters.items() if r["verdict"] == PROMOTE],
    }
