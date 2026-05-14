"""Quick smoke test for BitNet module — run with: py bitnet/_smoke_test.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_zone_validator():
    from bitnet.zone_validator import ZoneValidator
    ok, reason = ZoneValidator.check({'trade_count':150,'avg_rr':0.5,'max_drawdown':0.1,'winrate':0.55})
    assert ok, f"Expected accept, got: {reason}"
    print(f"  PASS ZoneValidator accept: {reason}")

    ok2, reason2 = ZoneValidator.check({'trade_count':50,'avg_rr':0.5,'max_drawdown':0.1,'winrate':0.55})
    assert not ok2, "Expected reject for low trades"
    print(f"  PASS ZoneValidator reject (low trades): {reason2}")

    ok3, reason3 = ZoneValidator.check({'trade_count':150,'avg_rr':0.1,'max_drawdown':0.1,'winrate':0.55})
    assert not ok3, "Expected reject for low avg_rr"
    print(f"  PASS ZoneValidator reject (low rr): {reason3}")


def test_gaussian_scoring():
    from bitnet.zone_cosine_searcher import ZoneCandidate, compute_gaussian_score, compute_gaussian_score_from_candidate

    # Peak score at exact mu values
    cand = ZoneCandidate(
        mu={'depth':0.5,'body':0.6,'disp':2.0},
        sigma={'depth':0.1,'body':0.1,'disp':0.4},
        weights={'depth':0.4,'body':0.3,'disp':0.3},
        threshold=0.7,
    )
    score = compute_gaussian_score_from_candidate([0.5, 0.6, 2.0, 0, 1, 0, 0, 0, 0, 0, 0], cand)
    assert abs(score - 1.0) < 1e-6, f"Peak score expected 1.0, got {score}"
    print(f"  PASS Gaussian peak score: {score:.6f}")

    # Score should drop away from mu
    score_off = compute_gaussian_score_from_candidate([0.8, 0.3, 4.0, 0, 1, 0, 0, 0, 0, 0, 0], cand)
    assert score_off < 0.5, f"Off-peak score should be < 0.5, got {score_off}"
    print(f"  PASS Gaussian off-peak score: {score_off:.4f}")

    # Dict API
    params = cand.to_dict()
    s = compute_gaussian_score([0.5, 0.6, 2.0, 0, 1, 0, 0, 0, 0, 0, 0], params)
    assert abs(s - 1.0) < 1e-6, f"Dict API peak expected 1.0, got {s}"
    print(f"  PASS compute_gaussian_score dict API: {s:.6f}")


def test_evaluate_subset():
    import random
    from bitnet.zone_cosine_searcher import ZoneCandidate, _evaluate_subset

    rng = random.Random(99)
    N = 200
    X    = [[rng.uniform(0.3,0.8), rng.uniform(0.4,0.9), rng.uniform(1.0,3.0)] + [0]*8 for _ in range(N)]
    y_rr = [rng.gauss(0.4, 0.8) for _ in range(N)]
    y_win = [1 if r > 0 else 0 for r in y_rr]

    cand = ZoneCandidate(
        mu={'depth':0.55,'body':0.65,'disp':2.0},
        sigma={'depth':0.15,'body':0.15,'disp':0.5},
        weights={'depth':0.4,'body':0.3,'disp':0.3},
        threshold=0.5,
    )
    m = _evaluate_subset(X, y_rr, y_win, cand)
    assert m['trade_count'] > 0, "Expected some trades to pass"
    assert 0 <= m['winrate'] <= 1
    assert 0 <= m['max_drawdown'] <= 1
    print(f"  PASS _evaluate_subset: n={m['trade_count']} avg_rr={m['avg_rr']:.3f} wr={m['winrate']:.2f}")


def test_stability_checker():
    import random
    from bitnet.zone_cosine_searcher import ZoneCandidate
    from bitnet.stability_checker import StabilityChecker

    rng = random.Random(7)
    N = 150
    X    = [[rng.uniform(0.3,0.8), rng.uniform(0.4,0.9), rng.uniform(1.0,3.0)] + [0]*8 for _ in range(N)]
    y_rr = [rng.gauss(0.3, 0.8) for _ in range(N)]
    y_win = [1 if r > 0 else 0 for r in y_rr]

    cand = ZoneCandidate(
        mu={'depth':0.55,'body':0.65,'disp':2.0},
        sigma={'depth':0.20,'body':0.20,'disp':0.60},
        weights={'depth':0.4,'body':0.3,'disp':0.3},
        threshold=0.4,
    )
    stable, score, splits = StabilityChecker.check(X, y_rr, y_win, cand)
    print(f"  PASS StabilityChecker: stable={stable} score={score:.3f} splits={len(splits)}")


def test_zone_gate():
    from live_engine import BitNetZoneGate

    g = BitNetZoneGate.disabled()
    r = g.check([0.5]*11)
    assert r['allowed'] == True, "Disabled gate must allow all"
    print(f"  PASS BitNetZoneGate disabled: allowed={r['allowed']} reason={r['reason']}")

    g2 = BitNetZoneGate(zone_path='models/zone_registry_nonexistent.json')
    r2 = g2.check([0.5]*11)
    assert r2['allowed'] == True, "Missing registry must fail-open"
    print(f"  PASS BitNetZoneGate missing registry: allowed={r2['allowed']}")


def test_scoring_engine_api():
    from engines.scoring_engine import compute_gaussian_score
    params = {
        'mu':      {'depth':0.5,'body':0.6,'disp':2.0},
        'sigma':   {'depth':0.1,'body':0.1,'disp':0.4},
        'weights': {'depth':0.4,'body':0.3,'disp':0.3},
        'threshold': 0.7,
    }
    s = compute_gaussian_score([0.5, 0.6, 2.0, 0, 1, 0, 0, 0, 0, 0, 0], params)
    assert abs(s - 1.0) < 1e-6, f"Expected 1.0, got {s}"
    print(f"  PASS scoring_engine.compute_gaussian_score: {s:.6f}")


def test_train_pipeline_has_bitnet():
    import ast
    src = open('train_pipeline.py', encoding='utf-8', errors='replace').read()
    ast.parse(src)
    assert 'def run_bitnet_search' in src
    print("  PASS train_pipeline.py: run_bitnet_search defined, syntax OK")


if __name__ == '__main__':
    tests = [
        test_zone_validator,
        test_gaussian_scoring,
        test_evaluate_subset,
        test_stability_checker,
        test_zone_gate,
        test_scoring_engine_api,
        test_train_pipeline_has_bitnet,
    ]
    passed = 0
    failed = 0
    for t in tests:
        print(f"\n[{t.__name__}]")
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed / {failed} failed")
    if failed:
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")