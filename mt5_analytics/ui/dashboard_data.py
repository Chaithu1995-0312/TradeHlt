"""
dashboard_data — pure, READ-ONLY loaders + display aggregations for the dashboard.

No Streamlit, no MT5, no writes — it only reads the persisted artifacts/reports and rolls
them up for display. Aggregation here is *information not authority* (§6.5): a dashboard
shows truth, it never creates it. Kept Streamlit-free so it is CI-testable without the UI dep.
Reuses the independent `analytics.metrics_oracle` for the rollups.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from utils.jsonl_writer import read_jsonl  # type: ignore
from analytics.metrics_oracle import (  # type: ignore
    expectancy_mean,
    max_drawdown_rr,
    profit_factor,
    win_rate,
)


# ── loaders (read-only) ─────────────────────────────────────────────────────────
def _load_kind(artifact_root: "str | Path", kind: str) -> list[dict]:
    root = Path(artifact_root)
    recs: list[dict] = []
    for f in sorted(root.glob(f"{kind}/*/*/*/{kind}.jsonl")):
        recs.extend(read_jsonl(f))
    return recs


def load_episodes(artifact_root) -> list[dict]:
    return _load_kind(artifact_root, "episodes")


def load_features(artifact_root) -> list[dict]:
    return _load_kind(artifact_root, "features")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load_coverage(report_root) -> "dict | None":
    return _read_json(Path(report_root) / "reality" / "deal_coverage.json")


def load_coverage_gaps(report_root) -> "dict | None":
    return _read_json(Path(report_root) / "reality" / "coverage_gaps.json")


def load_broker_semantics(report_root) -> "dict | None":
    return _read_json(Path(report_root) / "reality" / "broker_semantics.json")


def load_verification_md(report_root) -> "str | None":
    p = Path(report_root) / "verification" / "daily_verification.md"
    return p.read_text(encoding="utf-8") if p.exists() else None


# ── display aggregations (info, not authority) ──────────────────────────────────
def _realized(features) -> list[float]:
    return [float(f["realized_r"]) for f in features if f.get("realized_r") is not None]


def summary_stats(features) -> dict:
    rr = _realized(features)
    return {
        "n_episodes": len(features),
        "n_with_r": len(rr),
        "win_rate": round(win_rate(rr), 4) if rr else None,
        "profit_factor": round(profit_factor(rr), 4) if rr else None,
        "expectancy_r": round(expectancy_mean(rr), 4) if rr else None,
        "max_drawdown_r": round(max_drawdown_rr(rr), 4) if rr else None,
    }


def session_breakdown(features) -> dict:
    acc: dict[str, dict] = defaultdict(lambda: {"n": 0, "rr": []})
    for f in features:
        s = f.get("session") or "?"
        acc[s]["n"] += 1
        if f.get("realized_r") is not None:
            acc[s]["rr"].append(float(f["realized_r"]))
    return {
        s: {"n": d["n"],
            "expectancy_r": round(expectancy_mean(d["rr"]), 4) if d["rr"] else None}
        for s, d in acc.items()
    }


def regime_breakdown(features) -> dict:
    return dict(Counter(
        (f.get("regime") if f.get("regime") is not None else "INSUFFICIENT")
        for f in features
    ))


def mfe_mae_points(features) -> list[tuple[float, float]]:
    return [
        (float(f["mfe_r"]), float(f["mae_r"]))
        for f in features
        if f.get("mfe_r") is not None and f.get("mae_r") is not None
    ]


def durations_minutes(features) -> list[float]:
    return [float(f["duration_minutes"]) for f in features
            if f.get("duration_minutes") is not None]


# ── intelligence read model (v0.6.0) ────────────────────────────────────────────
def insight_summary(features, episodes, *, min_n: int = 30):
    """Delegate to the post-trade intelligence read model (info, not authority).

    Returns the immutable `InsightReport` (exit efficiency / cost drag / risk-adjusted /
    sufficiency-gated attribution / concentration). Imported lazily so the basic display
    loaders above stay dependency-light."""
    from ..analytics.insight_report import build_insight
    return build_insight(episodes, features, min_n=min_n)
