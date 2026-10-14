"""CRT state resolver group on XAUUSD H4: the EXPANSION timeout boundary.

Trunk = `CRTStateResolver` as it is on this branch: EXPANSION expires when its age reaches the
limit (`age >= max_expansion_age_candles` or `hours >= max_expansion_age_hours`,
src/features/crt_state_resolver.py `_check_expired`).

Branch (implementation) = strict `>` (expires only once the limit is EXCEEDED), the engine's
Phase 3b `_ttl_exceeded` rule. It was written on grok/program12-slice1 (commit 63a6a1d) and NOT
merged into trunk; the decision is taken on the page. Here it is a subclass override, so nothing
under src/ changes.

The resolver is fed the same feature rows both times, built the way
scripts/research/crt_state_confusion_matrix.py builds them (canonical features + retest/displacement
flags + rsi_state), with the resolver's own HTF counter. Thresholds come from the resolver's default
XAUUSD config. They were tuned on M15, so besides the page's H4 bars the script also runs the M15
corpus (through corpus_store, the corpus SSOT) and a planted-limit sensitivity check, so that a zero
count cannot come from an override that never runs.
"""
import sys, os, re, json, logging
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, _HERE)
logging.disable(logging.WARNING)
import numpy as np
import pandas as pd
from features.feature_pipeline import FeaturePipeline
from features.feature_schema import CANONICAL_FEATURES
from features.crt_state_resolver import CRTStateResolver
from h4_loader import load_h4_utc

STATES = ["RANGE", "SHADOW_PENDING", "SWEEP", "DISPLACEMENT", "EXPANSION", "EXPIRED", "RETEST",
          "EXECUTION", "RESOLUTION"]


class StrictTTLResolver(CRTStateResolver):
    """Branch: EXPANSION expires only when the age EXCEEDS the limit (engine `_ttl_exceeded`)."""

    def _check_expired(self, timestamp=None):
        thresholds = self._config.get("thresholds", {})
        max_candles = thresholds["max_expansion_age_candles"]
        max_hours = thresholds["max_expansion_age_hours"]
        if max_candles > 0:
            if self._memory.candle_index - self._memory.expansion_entry_index > max_candles:
                return True
        if max_hours > 0 and timestamp is not None and self._memory.expansion_entry_ts is not None:
            try:
                if (timestamp - self._memory.expansion_entry_ts).total_seconds() / 3600 > max_hours:
                    return True
            except (TypeError, AttributeError):
                pass
        return False


def run(cls, enr):
    """Resolve every row of a FeaturePipeline frame with resolver class `cls`."""
    names = [n for n in CANONICAL_FEATURES if n in enr.columns]
    flags = ["retest_flag", "displacement_flag"]
    cols = names + [f for f in flags if f in enr.columns]
    vals = np.nan_to_num(enr[cols].to_numpy(float), nan=0.0)
    tss = list(pd.to_datetime(enr["timestamp"]))
    res = cls(instrument="XAUUSD")
    thr = res._config.get("thresholds", {})
    ob, os_ = float(thr.get("rsi_overbought", 70.0)), float(thr.get("rsi_oversold", 30.0))
    out = []
    for i in range(len(enr)):
        fv = dict(zip(cols, vals[i].tolist()))
        for f in flags:
            fv.setdefault(f, 0.0)
        rsi = fv.get("rsi_14", 50.0)
        fv["rsi_state"] = 1.0 if rsi > ob else (-1.0 if rsi < os_ else 0.0)
        out.append(res.resolve(fv, timestamp=tss[i]))
    return out, thr


raw, CLOCK_ID = load_h4_utc()
enr, _ = FeaturePipeline(raw.copy(), timeframe="H4").run(); enr = enr.reset_index(drop=True)
ts = pd.to_datetime(enr["timestamp"]); NE = len(enr)
trunk, THR = run(CRTStateResolver, enr)
branch, _ = run(StrictTTLResolver, enr)

# M15: the resolver's native timeframe (its limits were tuned there), read through the corpus SSOT.
from data_ingestion.corpus_store import load as corpus_load
m15 = corpus_load("data/mt5/XAUUSD_M15.csv", "XAUUSD").frame()
enr15, _ = FeaturePipeline(m15, timeframe="M15").run(); enr15 = enr15.reset_index(drop=True)
t15, _ = run(CRTStateResolver, enr15)
b15, _ = run(StrictTTLResolver, enr15)
N15 = len(enr15); d15 = [i for i in range(N15) if t15[i] != b15[i]]
ts15 = pd.to_datetime(enr15["timestamp"])


# Sensitivity check: a zero above could mean the override never runs. Plant a tiny candle limit
# (hour limit off) on the first 8,000 M15 rows; the two rules must then disagree.
def planted(cls, k):
    class P(cls):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self._config["thresholds"]["max_expansion_age_candles"] = k
            self._config["thresholds"]["max_expansion_age_hours"] = 0
    return P


SENS = {}
for k in (3, 8):
    a, _ = run(planted(CRTStateResolver, k), enr15.iloc[:8000])
    b, _ = run(planted(StrictTTLResolver, k), enr15.iloc[:8000])
    SENS[k] = sum(x != y for x, y in zip(a, b))
assert all(v > 0 for v in SENS.values()), f"sensitivity check failed: {SENS}"
unknown = sorted((set(trunk) | set(branch)) - set(STATES))
order = STATES + unknown
code = {s: i for i, s in enumerate(order)}
t_ord = np.array([code[s] for s in trunk], float); b_ord = np.array([code[s] for s in branch], float)
diff = t_ord != b_ord; n_diff = int(diff.sum())

OUTP = os.path.join(ROOT, "results", "divergence_h4.json")
D = json.load(open(OUTP, encoding="utf-8"))
pos = pd.Series(np.arange(NE), index=ts)
WIN = pos.reindex(pd.to_datetime(pd.Series(D["window"]["ts"]))).to_numpy()
assert not np.isnan(WIN).any(), "page window bars missing from the H4 resolver run"
WIN = WIN.astype(int)

pct = lambda k: f"{k:,} of {NE:,} bars ({k / NE * 100:.1f}%)"
cnt = lambda a: ", ".join(f"{s} {a.count(s):,}" for s in order if a.count(s))
first = [f"{str(ts.iloc[i])[:16]}: {trunk[i]} -> {branch[i]}" for i in np.where(diff)[0][:5]]
SRC = []
for dp, _, fs in os.walk(os.path.join(ROOT, "src")):
    for f in fs:
        if f.endswith(".py"):
            p = os.path.join(dp, f)
            SRC.append((os.path.relpath(p, os.path.join(ROOT, "src")).replace("\\", "/"), open(p, encoding="utf-8", errors="ignore").read()))
refs = sorted(p for p, t in SRC if "CRTStateResolver" in t and p != "features/crt_state_resolver.py")

b_ttl = {"id": "resolver-expansion-ttl-strict", "kind": "implementation",
         "title": "EXPANSION expires only after the limit is exceeded (engine rule)", "open": (n_diff + len(d15)) > 0,
         "formula": "expired = age > max_expansion_age_candles  or  hours > max_expansion_age_hours",
         "stats": {"H4: state differs from trunk": pct(n_diff),
                   "H4 trunk states": cnt(trunk), "H4 branch states": cnt(branch),
                   "M15 (native timeframe): state differs": f"{len(d15):,} of {N15:,} bars ({len(d15) / N15 * 100:.2f}%)",
                   "M15 trunk states": cnt(t15), "M15 branch states": cnt(b15),
                   "M15 first differing bars": "; ".join(f"{str(ts15.iloc[i])[:16]}: {t15[i]} -> {b15[i]}" for i in d15[:5]) or "none",
                   "Limits used": f"{THR['max_expansion_age_candles']} candles, {THR['max_expansion_age_hours']} hours",
                   "Sensitivity check (first 8,000 M15 bars, limit planted at 3 / 8 candles)":
                       f"{SENS[3]} / {SENS[8]} bars differ, so the rule is live; at the real limits no EXPANSION gets that old"},
         "decision_label": "resolved CRT state changes", "decision_count": n_diff + len(d15),
         "note": ("The CRT engine (crt_engine_v2 `_ttl_exceeded`) expires on age > max; this resolver uses >=, "
                  "so it can expire one bar or hour-mark earlier. The > version was written on branch "
                  "grok/program12-slice1 (commit 63a6a1d, with tests/test_crt_state_resolver_ttl_boundary.py) "
                  "and was not merged; trunk keeps >=. While no bar changes it is listed as closed; it opens "
                  "for a pick here once a run shows a state that differs."),
         "follows": None,
         "window": [float(x) for x in b_ord[WIN]], "window_mask": [bool(x) for x in diff[WIN]]}

D.setdefault("state_orders", {})["crt_state_resolved"] = order
D["features"]["crt_state_resolved"] = {
    "group": "crt", "fm": "CRT-RESOLVER",
    "plain": "The CRT state the research resolver assigns to each H4 bar (state names on the chart axis). "
             "Not a canonical vector slot: listed here so a resolver rule's branch can be decided on this page. "
             "There is no separate formula to recompute it from, so the trunk check below compares the resolver "
             "with itself and is not evidence; the branch numbers are.",
    "registered": "CRTStateResolver.resolve(); EXPANSION expires when age >= max_expansion_age_candles or hours >= max_expansion_age_hours",
    "trunk": {"bars": NE, "mismatch_count": 0, "mismatch_first": [], "max_abs_diff": 0.0},
    "window_pipe": [float(x) for x in t_ord[WIN]], "window_mine": [float(x) for x in t_ord[WIN]],
    "refs": refs, "branches": [b_ttl]}
json.dump(D, open(OUTP, "w"), indent=1, default=float)
print("clock", CLOCK_ID, "| bars", NE, "| limits", THR["max_expansion_age_candles"], THR["max_expansion_age_hours"])
print("H4 trunk", cnt(trunk)); print("H4 branch", cnt(branch)); print("H4 differ", n_diff, first)
print("M15 bars", N15, "| trunk", cnt(t15)); print("M15 branch", cnt(b15)); print("M15 differ", len(d15))
