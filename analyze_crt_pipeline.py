import json
import csv
import os
import statistics
from collections import defaultdict, Counter

LOG_DIR = "logs"
TRADE_FILE = "results/alignment/AUDUSD_20260420_205658_v2_truth/run_20260421_022708_AUDUSD/AUDUSD_trades.csv"

def step1_analyze_decision_logs():
    print("=== STEP 1: DECISION LOG ANALYSIS ===")
    
    total_signals = 0
    accept_count = 0
    reject_count = 0
    rejection_stages = Counter()
    bitnet_scores = []
    final_scores = []
    missing_score = 0
    
    decision_files = [f for f in os.listdir(LOG_DIR) if f.startswith("backtest_decisions_")]
    
    for filename in decision_files:
        filepath = os.path.join(LOG_DIR, filename)
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    total_signals += 1
                    
                    if 'bitnet_score' in record:
                        bitnet_scores.append(record['bitnet_score'])
                    
                    if 'score' in record:
                        final_scores.append(record['score'])
                    else:
                        missing_score += 1
                    
                    if record.get('decision') == 'ACCEPT':
                        accept_count += 1
                    elif record.get('decision') == 'REJECT':
                        reject_count += 1
                        stage = record.get('rejection_stage', 'unknown')
                        rejection_stages[stage] += 1
                        
                except json.JSONDecodeError:
                    continue
    
    print(f"Total signals processed: {total_signals}")
    print(f"ACCEPT: {accept_count}")
    print(f"REJECT: {reject_count}")
    print(f"Acceptance rate: {accept_count / total_signals * 100:.2f}%")
    print("\nRejection breakdown:")
    for stage, count in rejection_stages.most_common():
        print(f"  {stage}: {count} ({count / reject_count * 100:.1f}%)")
    
    print("\nScore statistics:")
    if bitnet_scores:
        print(f"BitNet score: min={min(bitnet_scores):.4f}, max={max(bitnet_scores):.4f}, mean={statistics.mean(bitnet_scores):.4f}")
    if final_scores:
        print(f"Final score: min={min(final_scores):.4f}, max={max(final_scores):.4f}, mean={statistics.mean(final_scores):.4f}")
    print(f"Records missing score field: {missing_score}")
    
    max_final = max(final_scores) if final_scores else 0
    print(f"\nACCEPT path exists: {accept_count > 0}")
    
    return {
        'total_signals': total_signals,
        'accept_count': accept_count,
        'reject_count': reject_count,
        'rejection_stages': rejection_stages,
        'max_final_score': max_final,
        'bitnet_scores': bitnet_scores,
        'final_scores': final_scores
    }

def step2_analyze_engine_fusion():
    print("\n=== STEP 2: ENGINE + FUSION ANALYSIS ===")
    
    engines = {
        'crt_score': [],
        'gaussian_score': [],
        'rr_score': [],
        'zone_score': [],
        'fusion_score': []
    }
    
    fusion_total = 0
    fusion_pass = 0
    fusion_reject = 0
    
    with open(os.path.join(LOG_DIR, 'flow_collector.log'), 'r') as f:
        for line in f:
            if 'fusion_eval' in line:
                fusion_total += 1
                try:
                    parts = line.split('|')
                    for part in parts:
                        part = part.strip()
                        for eng in engines.keys():
                            if part.startswith(eng):
                                val = float(part.split('=')[1])
                                engines[eng].append(val)
                        if 'fusion_decision=PASS' in part:
                            fusion_pass += 1
                        if 'fusion_decision=REJECT' in part:
                            fusion_reject += 1
                except:
                    continue
    
    print("Engine score distributions:")
    for name, scores in engines.items():
        if scores:
            print(f"  {name}: count={len(scores)}, min={min(scores):.4f}, max={max(scores):.4f}, mean={statistics.mean(scores):.4f}")
            if max(scores) == 0.0:
                print(f"    WARNING: ENGINE DEAD: always zero")
            if max(scores) >= 0.99:
                print(f"    WARNING: ENGINE SATURATED")
    
    print(f"\nFusion: total={fusion_total}, PASS={fusion_pass}, REJECT={fusion_reject}")
    if fusion_total > 0:
        print(f"Fusion acceptance rate: {fusion_pass / fusion_total * 100:.2f}%")
    else:
        print("Fusion acceptance rate: N/A (no records found)")
    
    return {
        'engines': engines,
        'fusion_total': fusion_total,
        'fusion_pass': fusion_pass,
        'fusion_reject': fusion_reject
    }

def step3_pipeline_trace(step1_data, step2_data):
    print("\n=== STEP 3: PIPELINE TRACE ===")
    
    fusion_pass = step2_data['fusion_pass']
    decision_input = step1_data['total_signals']
    decision_pass = step1_data['accept_count']
    
    print(f"BitNet → Engines: {step2_data['fusion_total']} signals")
    print(f"Engines → Fusion PASS: {fusion_pass} signals ({fusion_pass / step2_data['fusion_total'] * 100:.1f}%)")
    print(f"Fusion → Decision input: {decision_input} signals")
    print(f"Decision → Ultron input: {decision_pass} signals ({decision_pass / decision_input * 100:.1f}%)")
    
    dropoff = fusion_pass - decision_input
    if dropoff > 0:
        print(f"\nWARNING: SIGNAL LOSS between Fusion and Decision: {dropoff} signals missing")
    
    return {
        'fusion_to_decision': decision_input,
        'decision_to_ultron': decision_pass
    }

def step4_decision_gate_validation(step1_data):
    print("\n=== STEP 4: DECISION GATE VALIDATION ===")
    
    threshold = None
    condition = None
    
    with open(os.path.join(LOG_DIR, 'trade_system.log'), 'r') as f:
        for line in f:
            if 'decision_threshold' in line:
                threshold = float(line.split('=')[1].strip())
            if 'decision_condition' in line:
                condition = line.split('=')[1].strip()
    
    print(f"Decision threshold: {threshold}")
    print(f"Decision condition: {condition}")
    print(f"Maximum incoming score: {step1_data['max_final_score']:.4f}")
    
    if step1_data['max_final_score'] < threshold:
        print("\nERROR: MATHEMATICAL BLOCK: No signal can ever pass decision gate")
        print(f"   Max score = {step1_data['max_final_score']:.4f} < threshold = {threshold}")
        return {'blocked': True, 'threshold': threshold}
    
    return {'blocked': False, 'threshold': threshold}

def step5_ultron_analysis():
    print("\n=== STEP 5: ULTRON ANALYSIS ===")
    
    ultron_input = 0
    ultron_pass = 0
    ultron_reject = 0
    reject_reasons = Counter()
    
    with open(os.path.join(LOG_DIR, 'trade_system.log'), 'r') as f:
        for line in f:
            if 'ULTRON input' in line:
                ultron_input += 1
            if 'ULTRON PASS' in line:
                ultron_pass += 1
            if 'ULTRON REJECT' in line:
                ultron_reject += 1
                parts = line.split('reason=')
                if len(parts) > 1:
                    reason = parts[1].split()[0]
                    reject_reasons[reason] += 1
    
    print(f"Signals reaching Ultron: {ultron_input}")
    
    if ultron_input == 0:
        print("ERROR: ULTRON STARVED: No signals received")
    else:
        print(f"Ultron PASS: {ultron_pass}")
        print(f"Ultron REJECT: {ultron_reject}")
        if reject_reasons:
            print("Rejection reasons:")
            for reason, count in reject_reasons.most_common():
                print(f"  {reason}: {count}")
    
    return {
        'ultron_input': ultron_input,
        'ultron_pass': ultron_pass,
        'ultron_reject': ultron_reject,
        'reject_reasons': reject_reasons
    }

def step6_final_trade_output():
    print("\n=== STEP 6: FINAL TRADE OUTPUT ===")
    
    total_trades = 0
    
    if os.path.exists(TRADE_FILE):
        with open(TRADE_FILE, 'r') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for row in reader:
                if row:
                    total_trades += 1
    
    print(f"Total trades generated: {total_trades}")
    
    return {'total_trades': total_trades}

if __name__ == "__main__":
    print("CRT Trading System Pipeline Analyzer")
    print("====================================")
    
    s1 = step1_analyze_decision_logs()
    s2 = step2_analyze_engine_fusion()
    s3 = step3_pipeline_trace(s1, s2)
    s4 = step4_decision_gate_validation(s1)
    s5 = step5_ultron_analysis()
    s6 = step6_final_trade_output()
    
    print("\n" + "="*60)
    print("FINAL SYSTEM VERDICT")
    print("="*60)
    
    if s4['blocked']:
        print("\nVERDICT: NON-FUNCTIONAL")
        print("\nROOT CAUSE:")
        print(f"Maximum fusion/decision score = {s1['max_final_score']:.4f}")
        print(f"Decision threshold = {s4['threshold']}")
        print(f"\nAll scores are below threshold. No signal can mathematically pass.")
        print("\nSystem is completely blocked at Decision layer.")
    elif s5['ultron_input'] == 0:
        print("\nVERDICT: NON-FUNCTIONAL")
        print("\nROOT CAUSE: Ultron is starved - no signals reach final gate")
    elif s6['total_trades'] == 0:
        print("\nVERDICT: DEGRADED")
        print("\nROOT CAUSE: Pipeline functions but produces zero trades")
    else:
        print("\nVERDICT: SYSTEM HEALTHY")
    
    print("\nAnalysis complete.")