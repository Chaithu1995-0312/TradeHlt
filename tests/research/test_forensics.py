"""Layer-6 forensics aggregation tests (pure — synthetic records, no candle run)."""
from types import SimpleNamespace

from research.forensics import (
    _classify,
    _clusters,
    _expectancy_decomposition,
    _intrabar_damage,
    _loss_mechanisms,
    _opp_bundle,
    _opportunity_profile,
)


def _rec(net_ib, net_co=0.0, gross_ib=None, oc_ib="SL_HIT", oc_co="SL_HIT",
         source="plain_stop_loss", mfe_r=0.0, favorable_first=False,
         bars_to_first_1r=None, **extra):
    gross_ib = net_ib if gross_ib is None else gross_ib
    r = {
        "rr_net_intrabar": net_ib, "rr_net_close_only": net_co,
        "rr_gross_intrabar": gross_ib, "rr_gross_close_only": net_co,
        "outcome_intrabar": oc_ib, "outcome_close_only": oc_co,
        "damage_rr": round(net_ib - net_co, 6), "damage_source": source,
        "hour": 0, "dow": 0, "month": "2025-01", "atr": 1.0, "duration": 5,
        "direction": "long", "trend_proxy": 0.0, "timestamp": "2025-01-01T00:00:00",
        "trade_id": "T",
        "max_favorable_excursion_r": mfe_r, "max_adverse_excursion_r": -1.0,
        "reached_0_5r": mfe_r >= 0.5, "reached_1r_horizon": mfe_r >= 1.0,
        "reached_1_5r": mfe_r >= 1.5, "reached_2r": mfe_r >= 2.0, "reached_3r": mfe_r >= 3.0,
        "favorable_first": favorable_first, "bars_to_first_1r": bars_to_first_1r,
    }
    r.update(extra)
    return r


# ── _classify branches ───────────────────────────────────────────────────────
def test_classify_branches():
    O = SimpleNamespace
    assert _classify(O(rr_achieved=1.0, outcome="TP_HIT"), O(rr_achieved=1.0, outcome="TP_HIT"), 0.5) == "winner"
    assert _classify(O(rr_achieved=0.3, outcome="TIMEOUT"), O(rr_achieved=0.3, outcome="TIMEOUT"), -0.05) == "cost_drag"
    assert _classify(O(rr_achieved=-1.0, outcome="SL_HIT"), O(rr_achieved=2.0, outcome="TP_HIT"), -1.0) == "same_bar_conflict"
    assert _classify(O(rr_achieved=-0.2, outcome="TIMEOUT"), O(rr_achieved=-0.2, outcome="TIMEOUT"), -0.3) == "timeout"
    assert _classify(O(rr_achieved=-1.0, outcome="SL_HIT"), O(rr_achieved=-1.0, outcome="SL_HIT"), -1.0) == "plain_stop_loss"


# ── expectancy decomposition identity ─────────────────────────────────────────
def test_expectancy_identity_reconciles():
    recs = [_rec(2.0), _rec(2.0), _rec(-1.0), _rec(-1.0), _rec(-1.0)]  # E = 0.2
    d = _expectancy_decomposition(recs)
    assert d["expectancy_net"] == 0.2
    assert abs(d["identity_check"] - d["expectancy_net"]) < 1e-6


# ── intrabar damage conversion matrix + same-bar count ────────────────────────
def test_conversion_matrix_and_same_bar():
    recs = [
        _rec(-1.0, net_co=2.0, oc_ib="SL_HIT", oc_co="TP_HIT"),   # winner_to_loser + same_bar
        _rec(0.5, net_co=2.0, oc_ib="TP_HIT", oc_co="TP_HIT"),    # winner_to_smaller_winner
        _rec(-1.0, net_co=-1.0),                                  # loser_to_loser (unchanged)
        _rec(2.0, net_co=2.0, oc_ib="TP_HIT", oc_co="TP_HIT"),    # unchanged (winner)
    ]
    d = _intrabar_damage(recs)
    m = d["conversion_matrix"]
    assert m["winner_to_loser"] == 1
    assert m["winner_to_smaller_winner"] == 1
    assert m["unchanged"] == 2          # the two abs(co-ib)<eps rows
    assert d["same_bar_sl_tp_count"] == 1


# ── loss_mechanisms: exclusive, ranked, r_lost_pct ~100 ───────────────────────
def test_loss_mechanisms_partition_and_rank():
    recs = [
        _rec(-3.0, source="same_bar_conflict"),
        _rec(-1.0, source="same_bar_conflict"),
        _rec(-1.0, source="plain_stop_loss"),
        _rec(-0.05, source="cost_drag"),
        _rec(2.0, source="winner"),       # winner excluded from loss attribution
    ]
    lm = _loss_mechanisms(recs)
    names = [d["name"] for d in lm]
    assert "winner" not in names                       # winners not a loss mechanism
    assert lm[0]["name"] == "same_bar_conflict"        # top destroyer by R
    assert lm[0]["mechanism_rank"] == 1
    assert abs(sum(d["r_lost_pct"] for d in lm) - 100.0) < 0.5
    assert lm[0]["count"] == 2 and lm[0]["avg_r_per_trade"] == -2.0


# ── clusters ───────────────────────────────────────────────────────────────--
def test_consecutive_clusters():
    # sequence: W W L L L W L  → loss runs [3,1], win runs [2,1]
    seq = [1.0, 1.0, -1.0, -1.0, -1.0, 1.0, -1.0]
    recs = [_rec(x) for x in seq]
    loss = _clusters(recs, win=False)
    wins = _clusters(recs, win=True)
    assert loss["max_consecutive"] == 3
    assert loss["cluster_lengths"] == {"1": 1, "3": 1}
    assert wins["max_consecutive"] == 2
    assert wins["cluster_lengths"] == {"1": 1, "2": 1}


# ── opportunity profile (Layer 2): World A vs World B ────────────────────────
def test_opp_bundle_capture_ratio_guards_zero_mfe():
    # mfe_r==0 rows excluded from capture ratio + n_with_opportunity.
    recs = [_rec(-1.0, mfe_r=0.0), _rec(1.0, mfe_r=2.0, bars_to_first_1r=4)]
    b = _opp_bundle(recs)
    assert b["n"] == 2 and b["n_with_opportunity"] == 1
    assert b["capture_ratio_p50"] == 0.5          # 1.0 / 2.0


def test_world_A_no_information():
    # All MFE < 0.5R → entries carry no favorable information.
    recs = [_rec(-1.0, mfe_r=0.2) for _ in range(20)]
    b = _opp_bundle(recs)
    assert b["pct_reached_0_5r"] == 0.0 and b["pct_reached_1r"] == 0.0
    assert b["n_reached_1r"] == 0


def test_world_B_sl_losers_carry_opportunity():
    # SL-losers that reached +1.5R favorable-first → World-B signature in by_exit_reason.sl_hit.
    recs = [_rec(-1.0, oc_ib="SL_HIT", mfe_r=1.6, favorable_first=True, bars_to_first_1r=6)
            for _ in range(10)]
    prof = _opportunity_profile(recs)
    sl = prof["by_exit_reason"]["sl_hit"]
    assert sl["pct_reached_1_5r"] == 100.0
    assert sl["pct_favorable_first"] == 100.0
    assert sl["bars_to_first_1r_p50"] == 6
    assert prof["by_result"]["loser"]["n"] == 10
