import hashlib, json

# From src/features/feature_schema.py
CANONICAL_FEATURES = (
    'open', 'high', 'low', 'close', 'volume',
    'volume_ratio',
    'double_sweep',
    'ema_fast', 'ema_slow', 'ema_spread',
    'trend_bias', 'trend_strength',
    'momentum_score',
    'atr', 'volatility_ratio',
    'rsi_14',
    'macd_line', 'macd_signal', 'macd_hist',
    'sweep_detected', 'liquidity_sweep', 'break_of_structure',
    'swing_high', 'swing_low', 'higher_high', 'lower_low',
    'body_size', 'wick_size', 'body_ratio',
    'volatility_regime',
    'session', 'hour_of_day',
    'disp_strength', 'retest_depth', 'candles_since_retest',
    'liquidity_distance',
    'liquidity_pressure_score',
    'volume_spike',
)

print('=== RUNTIME SCHEMA AUTHORITY ===')
print(f'CANONICAL_FEATURE_DIM: {len(CANONICAL_FEATURES)}')
print(f'CANONICAL_FEATURES: {list(CANONICAL_FEATURES)}')

# SCHEMA_HASH (MD5 of concatenated names)
schema_hash = hashlib.md5(''.join(CANONICAL_FEATURES).encode()).hexdigest()
print(f'SCHEMA_HASH (MD5): {schema_hash}')

# FEATURE_ORDER_HASH (SHA-256[:16] of JSON-encoded list)
payload = json.dumps(list(CANONICAL_FEATURES), sort_keys=False).encode()
feature_order_hash = hashlib.sha256(payload).hexdigest()[:16]
print(f'FEATURE_ORDER_HASH (SHA256[:16]): {feature_order_hash}')

# Compare with lineage census LATEST
print()
print('=== COMPARISON WITH LINEAGE CENSUS LATEST ===')
print(f'Lineage census schema_hash: 1ba02abbafdd0786831181677de547c1')
print(f'Runtime schema_hash:        {schema_hash}')
match_schema = schema_hash == '1ba02abbafdd0786831181677de547c1'
print(f'MATCH: {match_schema}')
print(f'Lineage census feature_order_hash: 235553310100a340')
print(f'Runtime feature_order_hash:        {feature_order_hash}')
match_order = feature_order_hash == '235553310100a340'
print(f'MATCH: {match_order}')