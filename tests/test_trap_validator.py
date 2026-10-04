"""
test_trap_validator.py — standalone integration tests for trap_validator_engine.
Run directly: python tests/test_trap_validator.py
Not collected by pytest (no pytest-style test functions).
"""
import ast
import sys

if __name__ == "__main__":
    from engines import trap_validator_engine as adapter_engine

    # Syntax check
    ast.parse(open('src/engines/trap_validator_engine.py').read())
    print('trap_validator_engine.py: syntax OK')

    print('\n=== TrapValidator Test Suite ===')

    # Test 1: Valid trap - all hard rules pass, near zone, strong displacement
    r1 = adapter_engine.compute('T1', {
        'recent_high': 1.3000, 'recent_low': 1.2900,
        'current_high': 1.3010, 'current_low': 1.2890,
        'candle': {'open': 1.2920, 'high': 1.3010, 'low': 1.2890, 'close': 1.2910},
        'structure_shift': True, 'sweep_event_exists': True,
        'current_price': 1.2910, 'zones': [1.2915], 'zone_threshold': 0.001,
        'impulse_move': 0.0030, 'ATR': 0.0010, 'overlap_ratio': 0.3,
    })
    print('T1 valid trap:', r1)
    assert r1['valid'] == True, r1
    assert r1['confidence_score'] > 0

    # Test 2: No sweep → HARD REJECT
    r2 = adapter_engine.compute('T2', {
        'recent_high': 1.3000, 'recent_low': 1.2900,
        'current_high': 1.2980, 'current_low': 1.2920,
        'candle': {'open': 1.2950, 'high': 1.2980, 'low': 1.2920, 'close': 1.2960},
        'structure_shift': True, 'sweep_event_exists': True,
        'current_price': 1.2960, 'zones': [], 'zone_threshold': 0.001,
        'impulse_move': 0.0010, 'ATR': 0.0010, 'overlap_ratio': 0.3,
    })
    print('T2 no sweep:', r2)
    assert r2['valid'] == False
    assert r2.get('reason') == 'no_liquidity_sweep'

    # Test 3: Flat candle (range=0) → Rule 2 rejects
    r3 = adapter_engine.compute('T3', {
        'recent_high': 1.3000, 'recent_low': 1.2900,
        'current_high': 1.3010, 'current_low': 1.2890,
        'candle': {'open': 1.2950, 'high': 1.2950, 'low': 1.2950, 'close': 1.2950},
        'structure_shift': True, 'sweep_event_exists': True,
        'current_price': 1.2950, 'zones': [], 'zone_threshold': 0.001,
        'impulse_move': 0.0030, 'ATR': 0.0010, 'overlap_ratio': 0.3,
    })
    print('T3 flat candle:', r3)
    assert r3['valid'] == False
    assert r3.get('reason') == 'weak_rejection'

    # Test 4: No structure shift → HARD REJECT
    r4 = adapter_engine.compute('T4', {
        'recent_high': 1.3000, 'recent_low': 1.2900,
        'current_high': 1.3010, 'current_low': 1.2890,
        'candle': {'open': 1.2920, 'high': 1.3010, 'low': 1.2890, 'close': 1.2910},
        'structure_shift': False, 'sweep_event_exists': False,
        'current_price': 1.2910, 'zones': [], 'zone_threshold': 0.001,
        'impulse_move': 0.0030, 'ATR': 0.0010, 'overlap_ratio': 0.3,
    })
    print('T4 no structure shift:', r4)
    assert r4['valid'] == False
    assert r4.get('reason') == 'no_structure_shift'

    # Test 5: Noisy setup → reduced confidence
    r5 = adapter_engine.compute('T5', {
        'recent_high': 1.3000, 'recent_low': 1.2900,
        'current_high': 1.3010, 'current_low': 1.2890,
        'candle': {'open': 1.2920, 'high': 1.3010, 'low': 1.2890, 'close': 1.2910},
        'structure_shift': True, 'sweep_event_exists': True,
        'current_price': 1.2910, 'zones': [], 'zone_threshold': 0.001,
        'impulse_move': 0.0005, 'ATR': 0.0010, 'overlap_ratio': 0.7,
    })
    print('T5 noisy setup:', r5)
    assert r5['valid'] == True
    assert r5['confidence_score'] < 0.5, f"conf={r5['confidence_score']}"

    # Test 6: Zero ATR → medium displacement, no crash
    r6 = adapter_engine.compute('T6', {
        'recent_high': 1.3000, 'recent_low': 1.2900,
        'current_high': 1.3010, 'current_low': 1.2890,
        'candle': {'open': 1.2920, 'high': 1.3010, 'low': 1.2890, 'close': 1.2910},
        'structure_shift': True, 'sweep_event_exists': True,
        'current_price': 1.2910, 'zones': [], 'zone_threshold': 0.001,
        'impulse_move': 0.0030, 'ATR': 0.0, 'overlap_ratio': 0.3,
    })
    print('T6 zero ATR:', r6)
    assert r6['valid'] == True
    assert r6['flags']['displacement'] == 'medium'

    # Test 7: structure_shift=True but sweep_event_exists=False → warn + reject
    r7 = adapter_engine.compute('T7', {
        'recent_high': 1.3000, 'recent_low': 1.2900,
        'current_high': 1.3010, 'current_low': 1.2890,
        'candle': {'open': 1.2920, 'high': 1.3010, 'low': 1.2890, 'close': 1.2910},
        'structure_shift': True, 'sweep_event_exists': False,
        'current_price': 1.2910, 'zones': [], 'zone_threshold': 0.001,
        'impulse_move': 0.0030, 'ATR': 0.0010, 'overlap_ratio': 0.3,
    })
    print('T7 inconsistent state:', r7)
    assert r7['valid'] == False
    assert r7.get('reason') == 'no_structure_shift'

    print('\n=== ALL 7 TESTS PASSED ===')
