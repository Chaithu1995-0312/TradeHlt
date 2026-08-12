import os, re

root = '.'
target_files = [
    'scripts/analysis/feature_math_drift_probe.py',
    'scripts/analysis/gd004_disp_rescale_probe.py',
    'scripts/analysis/pit_swing_blast_radius.py',
    'scripts/governance/behavioral_constant_authority_trace.py',
    'scripts/validate_integration.py',
    'tests/test_zone_gate.py',
    'tests/test_gd004_gd005_identity_closure.py',
    'tests/test_engine_runner_dual_gate.py',
    'tests/test_engine_runner_rr_fusion.py',
    'scripts/analysis/pit_swing_gateon_ab.py',
]

for fp in target_files:
    try:
        with open(os.path.join(root, fp), encoding='utf-8', errors='ignore') as f:
            content = f.read()
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if re.search(r'crt_engine\.compute|compute_scores\(|crt_compute\(', line):
                print(f"{fp}:{i}: {line.strip()}")
    except Exception as e:
        print(f"{fp}: ERROR: {e}")