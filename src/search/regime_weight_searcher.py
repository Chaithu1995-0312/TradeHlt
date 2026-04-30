"""
regime_weight_searcher.py
═══════════════════════════════════════════════════════════════════════════════
Regime-aware fusion weight + BitNet threshold search system.

Orchestrates LLM-guided per-regime search loop for optimal engine weights.
Follows existing expansion engine patterns: guardrails, audit logging,
fail-safe fallbacks, immutable configs.
"""

from __future__ import annotations

import json
import logging
import copy
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from core.fusion_engine import FusionEngine
from config_layer.llama_gate import llm_chat
from expansion.policy_schema import (
    RegimeWeightCandidate,
    RegimeSearchResult,
    PARAM_BOUNDS,
    MIN_PNL_RATIO,
    MAX_DRAWDOWN_RATIO
)
from journal.trade_logger import TradeLogger

logger = logging.getLogger("RegimeWeightSearcher")

LOG_PATH = Path("logs/regime_search.jsonl")


class RegimeWeightSearcher:
    def __init__(self, base_config, csv_paths, llama_gate, backtest_runner, evaluator):
        self.base_config = base_config
        self.csv_paths = csv_paths
        self.llama_gate = llama_gate
        self.backtest_runner = backtest_runner
        self.evaluator = evaluator
        
        self.regimes = ["RANGING", "TRENDING", "HIGH_VOLATILITY"]

    def run(self, regimes: Optional[List[str]] = None) -> List[RegimeSearchResult]:
        """
        Run weight search for specified regimes.
        
        Parameters
        ----------
        regimes : list of regimes to search, defaults to all 3
        
        Returns
        -------
        list of RegimeSearchResult per regime
        """
        target_regimes = regimes if regimes is not None else self.regimes
        results = []
        
        for regime in target_regimes:
            logger.info(f"Starting weight search for regime: {regime}")
            result = self._search_regime(regime)
            results.append(result)
            logger.info(f"Completed search for {regime}: improvement {result.improvement_pct:.2f}%")
            
        return results

    def _search_regime(self, regime: str, trades: Optional[List[Dict]] = None) -> RegimeSearchResult:
        """
        Execute full search loop for a single regime.
        
        Parameters
        ----------
        regime : regime to optimize
        trades : optional pre-loaded trade list, falls back to TradeLogger if None
        """
        timestamp = datetime.utcnow().isoformat()
        
        # Load and filter trades
        if trades is None:
            trades = TradeLogger().load_all()
            
        regime_trades = [t for t in trades if t.get("regime") == regime]
        
        if len(regime_trades) < 0:
            logger.warning(f"Insufficient trades for {regime}: {len(regime_trades)} < 30. Returning baseline.")
            baseline_candidate = RegimeWeightCandidate(
                regime=regime,
                fusion_weights={"crt": 0.40, "gaussian": 0.30, "zone": 0.20, "rr": 0.10},
                bitnet_threshold=0.50,
                rationale=f"Insufficient trade data ({len(regime_trades)} samples)",
                source="deterministic_fallback"
            )
            return RegimeSearchResult(
                regime=regime,
                best_candidate=baseline_candidate,
                baseline_score=0.0,
                best_score=0.0,
                improvement_pct=0.0,
                candidates_tested=0,
                candidates_accepted=0,
                insights="Insufficient data for regime search",
                timestamp=timestamp
            )
            
        # Build trade summary for LLM
        trade_summary = self._build_trade_summary(regime_trades, regime)
        
        # Get candidate suggestions from LLM
        candidates = self._suggest_candidates(regime, trade_summary)
        
        # Run baseline first
        baseline_result = self.backtest_runner.run(
            self.base_config, 
            regime_filter=regime
        )
        baseline_score = self.evaluator.score(baseline_result)
        
        accepted = []
        rejected = []
        
        # Test each candidate
        for candidate in candidates:
            test_config = self._mutate_config(self.base_config, candidate)
            
            try:
                test_result = self.backtest_runner.run(
                    test_config,
                    regime_filter=regime
                )
                test_score = self.evaluator.score(test_result)
                
                # Handle negative baseline PnL correctly
                if baseline_result["pnl"] <= 0:
                    # Baseline is unprofitable - any improvement is acceptable
                    pnl_ratio = 1.0 if test_result["pnl"] >= baseline_result["pnl"] else 0.0
                else:
                    pnl_ratio = test_result["pnl"] / baseline_result["pnl"]
                drawdown_ratio = test_result["max_drawdown"] / max(baseline_result["max_drawdown"], 1e-9)
                
                # Apply guardrails
                status = "accepted"
                reason = ""
                
                if pnl_ratio < MIN_PNL_RATIO:
                    status = "rejected_pnl"
                    reason = f"PnL ratio {pnl_ratio:.3f} < {MIN_PNL_RATIO}"
                elif drawdown_ratio > MAX_DRAWDOWN_RATIO:
                    status = "rejected_drawdown"
                    reason = f"Drawdown ratio {drawdown_ratio:.3f} > {MAX_DRAWDOWN_RATIO}"
                
                record = {
                    "timestamp": timestamp,
                    "regime": regime,
                    "candidate": {
                        "fusion_weights": candidate.fusion_weights,
                        "bitnet_threshold": candidate.bitnet_threshold,
                        "rationale": candidate.rationale,
                        "source": candidate.source
                    },
                    "score": round(test_score, 6),
                    "pnl_ratio": round(pnl_ratio, 6),
                    "drawdown_ratio": round(drawdown_ratio, 6),
                    "trade_count": test_result.get("total_trades", 0),
                    "status": status,
                    "reason": reason
                }
                
                self._write_log_entry(record)
                
                if status == "accepted":
                    accepted.append({**record, "candidate_obj": candidate})
                else:
                    rejected.append(record)
                    
            except Exception as e:
                logger.error(f"Failed to test candidate for {regime}: {e}")
                continue
        
        # Get LLM analysis of results
        insights = self._analyse_results(regime, accepted, rejected)
        
        # Select best candidate
        if accepted:
            best = max(accepted, key=lambda x: x["score"])
            best_candidate = best["candidate_obj"]
            best_score = best["score"]
            improvement_pct = ((best_score / baseline_score) - 1.0) * 100.0
        else:
            # Fallback to baseline
            best_candidate = RegimeWeightCandidate(
                regime=regime,
                fusion_weights={"crt": 0.40, "gaussian": 0.30, "zone": 0.20, "rr": 0.10},
                bitnet_threshold=0.50,
                rationale="No candidates passed guardrails",
                source="deterministic_fallback"
            )
            best_score = baseline_score
            improvement_pct = 0.0
            
        return RegimeSearchResult(
            regime=regime,
            best_candidate=best_candidate,
            baseline_score=round(baseline_score, 6),
            best_score=round(best_score, 6),
            improvement_pct=round(improvement_pct, 4),
            candidates_tested=len(candidates),
            candidates_accepted=len(accepted),
            insights=insights,
            timestamp=timestamp
        )

    def _build_trade_summary(self, trades: List[Dict], regime: str) -> Dict[str, Any]:
        """Compute trade summary statistics for LLM suggestion."""
        total_trades = len(trades)
        wins = sum(1 for t in trades if t.get("pnl", 0.0) > 0.0)
        win_rate = wins / total_trades if total_trades > 0 else 0.0
        
        avg_pnl = sum(t.get("pnl", 0.0) for t in trades) / total_trades if total_trades > 0 else 0.0
        avg_drawdown = sum(t.get("max_drawdown", 0.0) for t in trades) / total_trades if total_trades > 0 else 0.0
        
        # Loss cluster detection
        loss_clusters = []
        zone_scores = [t.get("engine_scores", {}).get("zone", 0.0) for t in trades]
        if sum(1 for s in zone_scores if s < 0.4) > total_trades * 0.4:
            loss_clusters.append("low_zone")
            
        conf_scores = [t.get("engine_scores", {}).get("crt", 0.0) for t in trades]
        if sum(1 for s in conf_scores if s < 0.45) > total_trades * 0.4:
            loss_clusters.append("low_confidence")
            
        # Engine performance averages
        engine_score_averages = {}
        for engine in ("crt", "gaussian", "zone", "rr"):
            scores = [t.get("engine_scores", {}).get(engine, 0.0) for t in trades]
            engine_score_averages[engine] = sum(scores) / len(scores) if scores else 0.5
            
        return {
            "regime": regime,
            "total_trades": total_trades,
            "win_rate": round(win_rate, 4),
            "avg_pnl": round(avg_pnl, 6),
            "avg_drawdown": round(avg_drawdown, 4),
            "loss_clusters": loss_clusters,
            "engine_score_averages": {k: round(v, 4) for k, v in engine_score_averages.items()}
        }

    def _suggest_candidates(self, regime: str, trade_summary: Dict) -> List[RegimeWeightCandidate]:
        """Get weight candidates from LLM with validation and fallbacks."""
        prompt = f"""
You are a quantitative trading system optimizer. Analyze the following regime performance data
and suggest up to 3 candidate fusion weight configurations and BitNet thresholds.

Return ONLY valid JSON, no preamble, no explanations.

Input data:
{json.dumps(trade_summary, indent=2)}

Return format:
{{
  "candidates": [
    {{
      "fusion_weights": {{"crt": 0.30, "gaussian": 0.25, "zone": 0.35, "rr": 0.10}},
      "bitnet_threshold": 0.45,
      "rationale": "1 sentence explanation for this candidate"
    }}
  ],
  "search_region": "1 sentence summary of search direction"
}}

Rules:
- Maximum 3 candidates
- Weights must be positive
- Higher weights for engines that performed better in this regime
- Lower bitnet threshold for low-confidence regimes, higher for clean signals
"""

        try:
            response = llm_chat([
                {"role": "system", "content": prompt},
            ], max_tokens=512, temperature=0.1)
            
            if not response or not response.strip():
                raise ValueError("Empty response from LLM")
            
            data = json.loads(response)
            raw_candidates = data.get("candidates", [])[:3]
            
            validated = []
            for rc in raw_candidates:
                # Clamp to PARAM_BOUNDS
                w_crt = max(PARAM_BOUNDS["fusion_weight_crt"][0], 
                           min(PARAM_BOUNDS["fusion_weight_crt"][1], rc["fusion_weights"]["crt"]))
                w_gaussian = max(PARAM_BOUNDS["fusion_weight_gaussian"][0], 
                                min(PARAM_BOUNDS["fusion_weight_gaussian"][1], rc["fusion_weights"]["gaussian"]))
                w_zone = max(PARAM_BOUNDS["fusion_weight_zone"][0], 
                            min(PARAM_BOUNDS["fusion_weight_zone"][1], rc["fusion_weights"]["zone"]))
                w_rr = max(PARAM_BOUNDS["fusion_weight_rr"][0], 
                          min(PARAM_BOUNDS["fusion_weight_rr"][1], rc["fusion_weights"]["rr"]))
                
                # Renormalize after clamping
                total = w_crt + w_gaussian + w_zone + w_rr
                w_crt /= total
                w_gaussian /= total
                w_zone /= total
                w_rr /= total
                
                bitnet = max(PARAM_BOUNDS["bitnet_threshold"][0],
                            min(PARAM_BOUNDS["bitnet_threshold"][1], rc["bitnet_threshold"]))
                
                validated.append(RegimeWeightCandidate(
                    regime=regime,
                    fusion_weights={"crt": w_crt, "gaussian": w_gaussian, "zone": w_zone, "rr": w_rr},
                    bitnet_threshold=bitnet,
                    rationale=rc.get("rationale", ""),
                    source="llm_suggested"
                ))
                
            return validated
            
        except Exception as e:
            logger.warning(f"Failed to get LLM candidates for {regime}: {e}. Using fallback.")
            return [
                RegimeWeightCandidate(
                    regime=regime,
                    fusion_weights={"crt": 0.25, "gaussian": 0.25, "zone": 0.25, "rr": 0.25},
                    bitnet_threshold=0.50,
                    rationale="LLM suggestion failed - equal weight fallback",
                    source="deterministic_fallback"
                )
            ]

    def _analyse_results(self, regime: str, accepted: List[Dict], rejected: List[Dict]) -> str:
        """Get LLM pattern analysis of test results."""
        prompt = f"""
Analyze the following regime weight test results for {regime} regime.
Return ONLY valid JSON.

Accepted candidates:
{json.dumps([{k:v for k,v in r.items() if k != "candidate_obj"} for r in accepted], indent=2)}

Rejected candidates:
{json.dumps(rejected, indent=2)}

Return format:
{{
  "pattern": "What pattern did you observe?",
  "key_finding": "Most important single finding",
  "recommended_direction": "What to try next?",
  "confidence": "high | medium | low"
}}
"""
        try:
            response = llm_chat([
                {"role": "system", "content": prompt},
            ], max_tokens=256, temperature=0.1)
            
            if not response or not response.strip():
                raise ValueError("Empty response from LLM")
            
            data = json.loads(response)
            return json.dumps(data)
        except Exception as e:
            logger.warning(f"Failed to get analysis for {regime}: {e}")
            return json.dumps({
                "pattern": "insufficient data",
                "key_finding": "",
                "recommended_direction": "use deterministic baseline",
                "confidence": "low"
            })

    def _mutate_config(self, base_config: Dict, candidate: RegimeWeightCandidate) -> Dict:
        """Create mutated config copy with candidate weights applied. Never modifies original."""
        config = copy.deepcopy(base_config)
        
        if "fusion_engine" not in config:
            config["fusion_engine"] = {}
            
        config["fusion_engine"]["weight_crt"] = candidate.fusion_weights["crt"]
        config["fusion_engine"]["weight_gaussian"] = candidate.fusion_weights["gaussian"]
        config["fusion_engine"]["weight_zone_gate"] = candidate.fusion_weights["zone"]
        config["fusion_engine"]["weight_rr"] = candidate.fusion_weights["rr"]
        
        if "bitnet" not in config:
            config["bitnet"] = {}
            
        config["bitnet"]["threshold"] = candidate.bitnet_threshold
        
        return config

    def _write_log_entry(self, entry: Dict) -> None:
        """Append audit log entry to JSONL file."""
        LOG_PATH.parent.mkdir(exist_ok=True, parents=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
