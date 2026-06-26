"""
test_insight_report — v0.6.0 post-trade intelligence read model.

Covers: cost drag off first-class episode fields, exit efficiency (capture/giveback),
risk-adjusted rollup, sufficiency gating (underpowered buckets make NO claim),
Herfindahl effective_n on an outlier-carried ledger, determinism, and the empty case.
"""
from mt5_analytics.analytics.insight_report import (
    SufficiencyStatus,
    build_insight,
)


def _feat(realized_r=None, mfe_r=None, mae_r=None, session=None, regime=None,
          duration_minutes=None):
    return {"realized_r": realized_r, "mfe_r": mfe_r, "mae_r": mae_r,
            "session": session, "regime": regime, "duration_minutes": duration_minutes}


def _ep(commission=0.0, swap=0.0, gross_profit=0.0, net_pnl=0.0):
    return {"commission": commission, "swap": swap,
            "gross_profit": gross_profit, "net_pnl": net_pnl}


# ── cost drag (schema-free, off PositionEpisode fields) ─────────────────────────
def test_cost_drag_from_episode_fields():
    eps = [
        _ep(commission=-0.04, swap=-0.01, gross_profit=2.0, net_pnl=1.95),
        _ep(commission=-0.06, swap=0.0, gross_profit=-1.0, net_pnl=-1.06),
    ]
    rpt = build_insight(eps, [], min_n=1)
    cd = rpt.cost_drag
    assert cd.n == 2
    assert cd.total_commission == -0.10
    assert cd.total_swap == -0.01
    assert cd.total_cost == -0.11
    assert cd.gross_profit_sum == 1.0
    assert cd.net_pnl_sum == 0.89
    assert abs(cd.cost_fraction_of_gross - 0.11) < 1e-9
    assert cd.gross_expectancy == 0.5
    assert cd.net_expectancy == 0.445


def test_cost_drag_zero_gross_returns_none_fraction():
    # mirrors the real IC Markets demo (gross_profit 0, all cost = commission)
    rpt = build_insight([_ep(commission=-0.08, gross_profit=0.0, net_pnl=-0.08)], [], min_n=1)
    assert rpt.cost_drag.cost_fraction_of_gross is None
    assert rpt.cost_drag.total_cost == -0.08


# ── exit efficiency ─────────────────────────────────────────────────────────────
def test_exit_efficiency_capture_and_giveback():
    feats = [_feat(realized_r=1.0, mfe_r=2.0), _feat(realized_r=0.5, mfe_r=1.0)]
    ee = build_insight([], feats, min_n=1).exit_efficiency
    assert ee.n == 2
    assert ee.median_capture_ratio == 0.5
    assert ee.mean_capture_ratio == 0.5
    assert ee.total_giveback_r == 1.5          # (2-1) + (1-0.5)


def test_exit_efficiency_skips_nonpositive_mfe():
    feats = [_feat(realized_r=0.3, mfe_r=0.0), _feat(realized_r=0.3, mfe_r=None)]
    ee = build_insight([], feats, min_n=1).exit_efficiency
    assert ee.n == 0
    assert ee.median_capture_ratio is None


# ── sufficiency gating (the central guardrail) ──────────────────────────────────
def test_attribution_sufficiency_gating():
    feats = (
        [_feat(realized_r=1.0, mfe_r=2.0, session="London") for _ in range(3)]
        + [_feat(realized_r=2.0, mfe_r=4.0, session="Asia") for _ in range(2)]
    )
    rpt = build_insight([], feats, min_n=3)
    by_session = {b.key: b for b in rpt.attribution.by_session}

    london = by_session["London"]
    assert london.n == 3
    assert london.status is SufficiencyStatus.SUFFICIENT
    assert london.expectancy == 1.0                  # claim allowed at n>=min_n
    assert london.capture_ratio == 0.5

    asia = by_session["Asia"]
    assert asia.n == 2
    assert asia.status is SufficiencyStatus.INSUFFICIENT
    assert asia.expectancy is None                   # underpowered -> NO claim
    assert asia.capture_ratio is None
    assert asia.min_n == 3                            # self-describing for the UI


def test_overall_status_tracks_min_n():
    feats = [_feat(realized_r=0.5, mfe_r=1.0) for _ in range(4)]
    assert build_insight([], feats, min_n=5).overall_status is SufficiencyStatus.INSUFFICIENT
    assert build_insight([], feats, min_n=4).overall_status is SufficiencyStatus.SUFFICIENT


# ── concentration / effective_n ─────────────────────────────────────────────────
def test_effective_n_two_outliers_carry_the_ledger():
    feats = [_feat(realized_r=10.0)] * 2 + [_feat(realized_r=-0.1)] * 98
    conc = build_insight([], feats, min_n=1).concentration
    assert conc.n == 100
    assert abs(conc.effective_n - 2.0) < 1e-9        # 100 trades, but ~2 effective bets
    assert conc.largest_winner_r == 10.0
    assert conc.largest_loser_r == -0.1


def test_effective_n_none_without_winners():
    feats = [_feat(realized_r=-0.5), _feat(realized_r=-0.2)]
    assert build_insight([], feats, min_n=1).concentration.effective_n is None


# ── risk-adjusted ───────────────────────────────────────────────────────────────
def test_risk_adjusted_rollup():
    feats = [_feat(realized_r=r) for r in (1.0, -0.5, 2.0, -1.0, 0.5)]
    ra = build_insight([], feats, min_n=1).risk_adjusted
    assert ra.n == 5
    assert abs(ra.expectancy_r - 0.4) < 1e-9
    assert abs(ra.win_rate - 0.6) < 1e-9
    assert ra.r_p50 == 0.5


# ── determinism + empty ─────────────────────────────────────────────────────────
def test_determinism_same_input_equal_report():
    eps = [_ep(commission=-0.04, gross_profit=1.0, net_pnl=0.96)]
    feats = [_feat(realized_r=1.0, mfe_r=2.0, session="London", regime="N",
                   duration_minutes=42.0)]
    assert build_insight(eps, feats, min_n=2) == build_insight(eps, feats, min_n=2)


def test_empty_input_is_wellformed_and_insufficient():
    rpt = build_insight([], [], min_n=30)
    assert rpt.n_episodes == 0
    assert rpt.overall_status is SufficiencyStatus.INSUFFICIENT
    assert rpt.cost_drag.n == 0
    assert rpt.cost_drag.gross_expectancy is None
    assert rpt.concentration.effective_n is None
    assert rpt.attribution.by_session == ()
