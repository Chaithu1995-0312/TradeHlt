"""
feature_dag_rolling_certification.py — SERIES-level certification of the first-class rolling
indicators FM-040..FM-046 (READ-ONLY).

Rolling indicators (true_range/atr/ema_fast/ema_slow/rsi_14/swings) are windowed — no scalar
float->float form exists — so they are certified by SERIES parity (an independent, causal,
float64 recompute ≡ the production pipeline column) + PIT prefix-invariance, NOT the scalar
derived_math parity battery. This probe supplies that evidence for the L1 promotion step of the
bottom-up certification program.

Verdict per indicator: CERTIFIED · REJECT. Swings (FM-045/046) are certified by REFERENCE to the
existing FC1-A causal-delayed-publication PIT floor (tests/test_pit_prefix_invariance.py), not
re-derived here (their stateful publication is proven prefix-invariant there).

Usage: python scripts/analysis/feature_dag_rolling_certification.py [--limit 8000]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from features.feature_pipeline import FeaturePipeline  # noqa: E402

_GOV = _ROOT / "docs" / "governance"
_STAMP = datetime.now(timezone.utc).strftime("%Y-%m-%d")
_MAJORS = ("BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT")
RTOL, ATOL = 1e-4, 1e-6          # float32 pipeline columns vs float64 independent recompute


def _synthetic(n=1200, seed=11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    open_ = close + rng.normal(0, 0.1, n)
    high = np.maximum(open_, close) + rng.uniform(0.05, 0.8, n)
    low = np.minimum(open_, close) - rng.uniform(0.05, 0.8, n)
    ts = pd.date_range("2024-01-01", periods=n, freq="15min")
    return pd.DataFrame({"timestamp": ts, "open": open_, "high": high, "low": low,
                         "close": close, "volume": rng.uniform(100, 1000, n)})


def _load(sym, limit):
    csv = _ROOT / "data" / f"{sym}_M15.csv"
    if not csv.exists():
        return None
    df = pd.read_csv(csv)
    df.columns = [c.strip().lower() for c in df.columns]
    return df.head(limit).copy() if limit else df


def _run(raw):
    feat, _ = FeaturePipeline(raw.copy()).run()
    return feat.set_index("timestamp")


def _independent(raw: pd.DataFrame) -> pd.DataFrame:
    """Causal float64 recompute of the numeric rolling indicators from OHLC alone."""
    df = raw.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    close = df["close"].astype("float64")
    high, low = df["high"].astype("float64"), df["low"].astype("float64")
    pc = close.shift(1)
    tr = np.maximum(high - low, np.maximum((high - pc).abs(), (low - pc).abs()))
    atr_raw = tr.rolling(14).mean()
    atr = np.where(close > 0, atr_raw / close, 0.0)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = (100.0 - 100.0 / (1.0 + gain / (loss + 1e-9))).clip(0.0, 100.0)
    out = pd.DataFrame({
        "true_range": tr, "atr": atr,
        "ema_fast": close.ewm(span=9, adjust=False).mean(),
        "ema_slow": close.ewm(span=21, adjust=False).mean(),
        "rsi_14": rsi,
    })
    out.index = pd.Index(pd.to_datetime(df["timestamp"]), name="timestamp")
    return out


_NUMERIC = ("true_range", "atr", "ema_fast", "ema_slow", "rsi_14")


def _series_parity(raw, label) -> dict:
    pipe = _run(raw)
    indep = _independent(raw)
    shared = pipe.index.intersection(indep.index)
    res = {}
    for col in _NUMERIC:
        a = indep.loc[shared, col].to_numpy("float64")
        b = pipe.loc[shared, col].to_numpy("float64")
        m = np.isfinite(a) & np.isfinite(b)
        agree = bool(np.allclose(a[m], b[m], rtol=RTOL, atol=ATOL)) if m.any() else False
        res[col] = {"parity": agree,
                    "max_resid": float(np.max(np.abs(a[m] - b[m]))) if m.any() else None,
                    "rows": int(m.sum())}
    return {"corpus": label, "per_indicator": res}


def _prefix_invariance(raw, cuts=(0.5, 0.8)) -> dict:
    full = _independent(raw)
    per = {c: True for c in _NUMERIC}
    for frac in cuts:
        pref = _independent(raw.head(int(len(raw) * frac)))
        shared = pref.index.intersection(full.index)
        for c in _NUMERIC:
            a, b = pref.loc[shared, c].to_numpy(), full.loc[shared, c].to_numpy()
            eq = (a == b) | (pd.isna(a) & pd.isna(b))
            if not eq.all():
                per[c] = False
    return per


def build_report(limit: int, include_corpus: bool = True) -> dict:
    synth = _synthetic()
    arms = [_series_parity(synth, "synthetic_1200")]
    if include_corpus:
        for s in _MAJORS:
            c = _load(s, limit)
            if c is not None:
                arms.append(_series_parity(c, f"{s}_M15"))
    pit = _prefix_invariance(synth)

    verdicts = {}
    for col in _NUMERIC:
        parity_ok = all(a["per_indicator"][col]["parity"] for a in arms)
        verdicts[col] = "CERTIFIED" if (parity_ok and pit[col]) else "REJECT"
    # swings certified by reference to the FC1-A PIT floor
    verdicts["swing_high"] = "CERTIFIED_BY_REFERENCE"
    verdicts["swing_low"] = "CERTIFIED_BY_REFERENCE"

    fmap = {"true_range": "FM-040", "atr": "FM-041", "rsi_14": "FM-042", "ema_fast": "FM-043",
            "ema_slow": "FM-044", "swing_high": "FM-045", "swing_low": "FM-046"}
    return {
        "probe": "feature_dag_rolling_certification",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "authority": ("research/governance only — SERIES-parity + PIT certification of windowed "
                      "rolling indicators; grants no activation authority (§6.5)."),
        "formula_id_map": fmap,
        "arms": arms,
        "prefix_invariance": pit,
        "swing_certification": "by reference to tests/test_pit_prefix_invariance.py (FC1-A causal "
                               "delayed publication — swing_high/swing_low prefix-invariant in the 38-vector)",
        "verdicts": verdicts,
        "overall": "CERTIFIED" if all(v.startswith("CERTIFIED") for v in verdicts.values()) else "REJECT",
        "permanent_floor": "tests/test_feature_dag_rolling_certification.py",
    }


def _write(rep) -> tuple[Path, str]:
    stem = f"feature_dag_rolling_certification-{_STAMP}"
    oj, om = _GOV / f"{stem}.json", _GOV / f"{stem}.md"
    payload = json.dumps(rep, indent=2) + "\n"
    oj.write_text(payload, encoding="utf-8")
    lines = [f"# Rolling-Indicator Series Certification (FM-040..046)", "",
             f"_Generated {rep['generated_at']} · READ-ONLY · overall **{rep['overall']}**._", ""]
    for c, v in rep["verdicts"].items():
        lines.append(f"- `{c}` [{rep['formula_id_map'][c]}]: **{v}**")
    om.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sha = hashlib.sha256(payload.encode()).hexdigest()
    (_GOV / "feature_dag_rolling_certification.LATEST.json").write_text(json.dumps({
        "path": str(oj.relative_to(_ROOT)).replace("\\", "/"), "generated_at": rep["generated_at"],
        "sha256": sha, "overall": rep["overall"],
    }, indent=2) + "\n", encoding="utf-8")
    return oj, sha


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8000)
    args = ap.parse_args()
    rep = build_report(args.limit)
    oj, sha = _write(rep)
    print(f"probe → {oj.relative_to(_ROOT)} (sha {sha[:12]})  overall={rep['overall']}")
    for c, v in rep["verdicts"].items():
        print(f"  {c:12s} {v}")
    return 0 if rep["overall"].startswith("CERTIFIED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
