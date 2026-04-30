#!/usr/bin/env python3
"""
run_regime_search.py
Standalone manual execution script for regime weight optimization
"""
import sys
import json
import uuid
import hashlib
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)7s | %(name)s | %(message)s"
)

sys.path.insert(0, 'src')

from search.regime_weight_searcher import RegimeWeightSearcher
from runtime.backtest_v2 import BacktestRunner, BacktestConfig
from expansion.evaluator import Evaluator
from config_layer.llama_gate import llm_chat
from regime.config_router import ConfigRouter


def main():
    RUN_ID = str(uuid.uuid4())
    RUN_START = datetime.utcnow().isoformat()
    
    print("\n" + "=" * 80)
    print("REGIME WEIGHT OPTIMIZATION SEARCH")
    print(f"RUN ID: {RUN_ID}")
    print("=" * 80 + "\n")

    # Configuration
    BASE_CONFIG_PATH = "configs/production/v1_multi_2026_03.json"
    DATA_CSV_PATH = "data/AUDUSD_M15_first_20000.csv"
    TARGET_REGIMES = ["RANGING", "TRENDING", "HIGH_VOLATILITY"]

    # Load baseline config
    print(f"Loading base config: {BASE_CONFIG_PATH}")
    with open(BASE_CONFIG_PATH, encoding="utf-8") as f:
        base_config_dict = json.load(f)
    
    # Calculate config integrity hash
    config_hash = hashlib.sha256(json.dumps(base_config_dict, sort_keys=True).encode()).hexdigest()
    logging.info(f"[AUDIT] RUN={RUN_ID} | CONFIG_LOADED path={BASE_CONFIG_PATH} hash={config_hash[:12]}")
    
    # from_prod_config only takes instrument, pip_size, crt_config
    base_config = BacktestConfig.from_prod_config()
    
    # Hydrate all other fields manually onto the object
    for key, value in base_config_dict.items():
        if hasattr(base_config, key):
            setattr(base_config, key, value)
    
    logging.info(f"[AUDIT] RUN={RUN_ID} | CONFIG_HYDRATED | fields_applied={len(base_config_dict)}")

    # Initialize dependencies
    print("Initializing backtest runner and evaluator")
    backtest = BacktestRunner(base_config, csv_path=DATA_CSV_PATH)
    evaluator = Evaluator()
    llama_gate = None

    # Create searcher
    searcher = RegimeWeightSearcher(
        base_config=base_config,
        csv_paths=[DATA_CSV_PATH],
        llama_gate=llama_gate,
        backtest_runner=backtest,
        evaluator=evaluator
    )

    # Execute search
    print(f"\nStarting search for regimes: {TARGET_REGIMES}")
    search_start = datetime.utcnow()
    results = searcher.run(regimes=TARGET_REGIMES)
    search_duration = (datetime.utcnow() - search_start).total_seconds()
    
    logging.info(f"[AUDIT] RUN={RUN_ID} | SEARCH_COMPLETED | duration={search_duration:.2f}s | regimes_processed={len(results)}")

    # Print summary
    print("\n" + "=" * 80)
    print("SEARCH RESULTS SUMMARY")
    print("=" * 80)

    total_improvement = 0.0
    for res in results:
        print(f"""
✅ {res.regime}:
  Score: {res.baseline_score:.4f} → {res.best_score:.4f}
  Improvement: {res.improvement_pct:+.2f}%
  Weights: CRT={res.best_candidate.fusion_weights['crt']:.2f}  GAUSSIAN={res.best_candidate.fusion_weights['gaussian']:.2f}  ZONE={res.best_candidate.fusion_weights['zone']:.2f}  RR={res.best_candidate.fusion_weights['rr']:.2f}
  BitNet Threshold: {res.best_candidate.bitnet_threshold:.2f}
  Candidates: {res.candidates_accepted} accepted / {res.candidates_tested} tested
""")
        total_improvement += res.improvement_pct

    avg_improvement = total_improvement / len(results)
    print(f"\n📊 AVERAGE IMPROVEMENT: {avg_improvement:+.2f}%")

    # Update and persist regime map
    print("\nUpdating regime map...")
    router = ConfigRouter()
    
    # Log weight changes with delta for audit
    for res in results:
        before_weights = router.get_fusion_weights(res.regime)
        after_weights = res.best_candidate.fusion_weights
        delta = {k: round(after_weights.get(k, 0) - before_weights.get(k, 0), 4) for k in set(before_weights) | set(after_weights)}
        
        logging.info(f"[AUDIT] RUN={RUN_ID} | REGIME_WEIGHT_CHANGE | regime={res.regime} | score={res.baseline_score:.4f}→{res.best_score:.4f} | delta={delta}")
    
    router.update_regime_weights(results)
    router.save_map()
    
    final_map_hash = hashlib.sha256(json.dumps(router.get_map(), sort_keys=True).encode()).hexdigest()
    logging.info(f"[AUDIT] RUN={RUN_ID} | REGIME_MAP_SAVED | hash={final_map_hash[:12]}")
    print(f"✅ Regime map saved to: configs/production/regime_map.json")

    RUN_END = datetime.utcnow().isoformat()
    run_duration = (datetime.fromisoformat(RUN_END) - datetime.fromisoformat(RUN_START)).total_seconds()
    
    # Final audit entry
    audit_entry = {
        "run_id": RUN_ID,
        "start_time": RUN_START,
        "end_time": RUN_END,
        "duration_seconds": round(run_duration, 2),
        "base_config_path": BASE_CONFIG_PATH,
        "base_config_hash": config_hash,
        "target_regimes": TARGET_REGIMES,
        "average_improvement_pct": avg_improvement,
        "final_map_hash": final_map_hash,
        "status": "COMPLETED"
    }
    
    # Append to structured audit log
    audit_log_path = Path('logs/regime_search_audit.jsonl')
    audit_log_path.parent.mkdir(exist_ok=True)
    with open(audit_log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(audit_entry) + '\n')
    
    print("\n✅ SEARCH COMPLETED SUCCESSFULLY")
    print(f"\nRun ID: {RUN_ID}")
    print(f"Full audit log: {audit_log_path.absolute()}")
    print("\n")


if __name__ == "__main__":
    main()