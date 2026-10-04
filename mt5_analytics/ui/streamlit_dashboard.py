"""
streamlit_dashboard — READ-ONLY visualization of the MT5 analytics ledger (Phase 8).

A capability plugin, not a foundation: it consumes the persisted artifacts/reports and
renders them. It never connects to MT5, reconstructs, or writes — *the dashboard consumes
truth, it never creates truth*. All loading/aggregation lives in the Streamlit-free,
CI-tested `dashboard_data`; this file is a thin render shell.

Run:
    streamlit run mt5_analytics/ui/streamlit_dashboard.py
"""
from __future__ import annotations

import streamlit as st

from ..analytics_config import _require, load_config
from . import dashboard_data as dd


def render() -> None:
    st.set_page_config(page_title="MT5 Analytics", layout="wide")
    cfg = load_config()
    artifact_root = str(_require(cfg, "artifact_root"))
    report_root = str(_require(cfg, "report_root"))

    episodes = dd.load_episodes(artifact_root)
    features = dd.load_features(artifact_root)

    st.title("MT5 Analytics")
    st.caption("Read-only view of MT5-reconstructed positions. MT5 owns truth; this only reads it.")

    # 1 — Verification (most valuable)
    st.header("Verification")
    vmd = dd.load_verification_md(report_root)
    if vmd:
        status = "PASS" if "**Status:** PASS" in vmd else (
            "FAIL" if "**Status:** FAIL" in vmd else "?")
        (st.success if status == "PASS" else st.error if status == "FAIL" else st.info)(
            f"Reconciliation status: {status}")
        with st.expander("verification report"):
            st.markdown(vmd)
    else:
        st.info("No verification report yet — run `python -m mt5_analytics.core.verify`.")

    # 2 — Coverage maturity
    st.header("Broker-semantics coverage")
    cov, gaps = dd.load_coverage(report_root), dd.load_coverage_gaps(report_root)
    if cov:
        c1, c2, c3 = st.columns(3)
        c1.metric("Maturity", f"{cov.get('coverage_score', 0)}/100", cov.get("tier", ""))
        c2.metric("Trade positions", cov.get("trade_positions", 0))
        c3.metric("Account ops skipped", cov.get("account_ops_skipped", 0))
        if cov.get("account_type"):
            st.caption(f"Account: {cov['account_type']} · "
                       f"score is observed / reachable (N/A patterns excluded)")
        if gaps:
            st.write("**Validated:**", ", ".join(gaps.get("validated", [])) or "(none)")
            if "n_a" in gaps:   # account-aware format
                st.write("**Reachable but unseen:**",
                         ", ".join(gaps.get("reachable_unseen", [])) or "(none)")
                st.write("**N/A for this broker:**",
                         ", ".join(gaps.get("n_a", [])) or "(none)")
            else:
                st.write("**Missing (unseen by reality):**",
                         ", ".join(gaps.get("missing", [])) or "(none)")
        bs = dd.load_broker_semantics(report_root)
        if bs:
            st.write("**Broker capability registry (monotonic):**")
            st.json(bs)
    else:
        st.info("No coverage yet — run `python -m mt5_analytics.core.coverage`.")

    # 3 — Summary
    st.header("Performance summary")
    s = dd.summary_stats(features)
    cols = st.columns(5)
    cols[0].metric("Episodes", s["n_episodes"])
    cols[1].metric("Win rate", s["win_rate"] if s["win_rate"] is not None else "—")
    cols[2].metric("Profit factor", s["profit_factor"] if s["profit_factor"] is not None else "—")
    cols[3].metric("Expectancy (R)", s["expectancy_r"] if s["expectancy_r"] is not None else "—")
    cols[4].metric("Max DD (R)", s["max_drawdown_r"] if s["max_drawdown_r"] is not None else "—")

    # 4 — Trade table (one row per episode)
    st.header("Trades")
    if features:
        keep = ("entry_time", "symbol", "direction", "realized_r", "mfe_r", "mae_r",
                "duration_minutes", "session", "regime")
        st.dataframe([{k: f.get(k) for k in keep} for f in features], use_container_width=True)
    else:
        st.info("No episodes yet — run `python -m mt5_analytics.core.rebuild`.")

    # 5 — MFE vs MAE
    st.header("MFE vs MAE (R)")
    pts = dd.mfe_mae_points(features)
    if pts:
        st.scatter_chart({"mfe_r": [p[0] for p in pts], "mae_r": [p[1] for p in pts]},
                         x="mae_r", y="mfe_r")
    else:
        st.info("No excursion data yet.")

    # 6 — Session breakdown / 7 — Regime + duration
    c_left, c_right = st.columns(2)
    with c_left:
        st.header("Session")
        sb = dd.session_breakdown(features)
        if sb:
            st.bar_chart({s: d["n"] for s, d in sb.items()})
            st.dataframe([{"session": s, **d} for s, d in sb.items()])
    with c_right:
        st.header("Regime")
        rb = dd.regime_breakdown(features)
        if rb:
            st.bar_chart(rb)

    st.header("Holding duration (minutes)")
    durs = dd.durations_minutes(features)
    if durs:
        st.bar_chart({"count": durs})


if __name__ == "__main__":
    render()
