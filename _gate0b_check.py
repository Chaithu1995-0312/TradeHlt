import json

# Load DAG layers
with open('docs/governance/feature_dag_layers-2026-07-12.json') as f:
    dag = json.load(f)

# Extract canonical nodes sorted by canonical_index
dag_canonical = [n for n in dag['nodes'] if n['in_canonical_vector']]
dag_canonical_sorted = sorted(dag_canonical, key=lambda n: n['canonical_index'])

print(f'DAG canonical node count: {len(dag_canonical_sorted)}')
print(f'Canonical index range: {dag_canonical_sorted[0]["canonical_index"]}..{dag_canonical_sorted[-1]["canonical_index"]}')

# Check contiguous indices
indices = [n['canonical_index'] for n in dag_canonical_sorted]
expected = list(range(38))
contiguous = indices == expected
print(f'Indices contiguous 0..37: {contiguous}')

# Check no duplicate indices
unique_indices = set(indices)
print(f'No duplicate indices: {len(unique_indices) == 38}')

# Check no duplicate names
names = [n['name'] for n in dag_canonical_sorted]
unique_names = set(names)
print(f'No duplicate names: {len(unique_names) == 38}')

# Runtime canonical features
runtime_features = [
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
]

# Compare DAG canonical order vs runtime order
dag_names = [n['name'] for n in dag_canonical_sorted]
print(f'\nDAG canonical names (by index): {dag_names}')
print(f'Runtime canonical names:        {runtime_features}')
print(f'Exact match: {dag_names == runtime_features}')

# Check set equality
dag_set = set(dag_names)
runtime_set = set(runtime_features)
print(f'Set equality: {dag_set == runtime_set}')
if dag_set != runtime_set:
    print(f'In DAG but not runtime: {dag_set - runtime_set}')
    print(f'In runtime but not DAG: {runtime_set - dag_set}')

# Check each DAG canonical node's formula_id
print('\n=== DAG canonical formula_id coverage ===')
for n in dag_canonical_sorted:
    fid = n.get('formula_id')
    print(f'  idx {n["canonical_index"]:2d}: {n["name"]:30s} formula_id={fid}')