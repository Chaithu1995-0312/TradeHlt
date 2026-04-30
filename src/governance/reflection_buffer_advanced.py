import json
import pandas as pd
from pathlib import Path
from features.feature_schema import CANONICAL_FEATURES

class ReflectionBuffer:
    def __init__(self, logs_path="logs/collector.jsonl", trades_path="results/real_backtest/AUDUSD_trades.csv"):
        self.logs_path = Path(logs_path)
        self.trades_path = Path(trades_path)

    def load_and_merge(self) -> pd.DataFrame:
        decisions = []
        with open(self.logs_path, 'r') as f:
            for line in f:
                d = json.loads(line)
                row = {
                    "candle_idx": d.get("candle_idx"),
                    "decision": d.get("decision"),
                    "final_score": d.get("final_score", 0.0),
                    "reason": d.get("reason", "")
                }
                row.update(d.get("features", {}))
                decisions.append(row)

        df_decisions = pd.DataFrame(decisions)
        df_trades = pd.read_csv(self.trades_path)
        df_decisions['candle_idx'] = pd.to_numeric(df_decisions['candle_idx'], errors='coerce')
        df_trades['candle_idx'] = pd.to_numeric(df_trades['candle_idx'], errors='coerce')

        # Drop rows with missing candle_idx
        df_decisions = df_decisions.dropna(subset=['candle_idx'])
        df_trades = df_trades.dropna(subset=['candle_idx'])

        # Convert to int
        df_decisions['candle_idx'] = df_decisions['candle_idx'].astype(int)
        df_trades['candle_idx'] = df_trades['candle_idx'].astype(int)
        # Ensure candle_idx exists in trades
        if 'candle_idx' not in df_trades.columns:
            raise ValueError("trades.csv missing 'candle_idx' column. Did you apply Gap 3 patch?")

        df_merged = pd.merge(
            df_decisions,
            df_trades[['candle_idx', 'pnl_rr_net', 'exit_reason']],  # use pnl_rr_net
            on='candle_idx',
            how='left'
        )
        return df_merged

    def generate_prompt_payload(self, df: pd.DataFrame, output_path="logs/meta_prompt.txt"):
        # Filter only ACCEPT decisions (since REJECT has no outcome)
        df_accepts = df[df['decision'] == 'ACCEPT'].dropna(subset=['pnl_rr_net'])
        
        true_accepts = df_accepts[df_accepts['pnl_rr_net'] > 0]
        false_accepts = df_accepts[df_accepts['pnl_rr_net'] <= 0]

        if len(true_accepts) == 0 or len(false_accepts) == 0:
            print("Insufficient data for divergence analysis. Need both wins and losses.")
            return None

        ta_means = true_accepts[CANONICAL_FEATURES].mean()
        fa_means = false_accepts[CANONICAL_FEATURES].mean()

        divergence = (fa_means - ta_means).abs().sort_values(ascending=False)
        top_features = divergence.head(3).index.tolist()
        top_diffs = [f"{fa_means[f]-ta_means[f]:+.3f}" for f in top_features]

        prompt = f"""[SYSTEM] You are the Nexus Meta-Governor. Your role is strict, deterministic parameter optimization. Do not explain your reasoning. Output ONLY a valid JSON object.

[CURRENT STATE]
Total True Accepts (wins): {len(true_accepts)}
Total False Accepts (losses): {len(false_accepts)}

[FEATURE DIVERGENCE]
The following features show the highest deviation during losing trades:
1. {top_features[0]}: {top_diffs[0]} (losses - wins)
2. {top_features[1]}: {top_diffs[1]}
3. {top_features[2]}: {top_diffs[2]}

[TASK]
Based on this divergence, output a JSON patch to adjust `fusion_min_score` and `weak_component_threshold` to filter out these losing setups.

[REQUIRED OUTPUT FORMAT]
{{
    "decision_engine": {{
        "weak_component_threshold": <float>
    }},
    "fusion_min_score": <float>
}}"""
        with open(output_path, 'w') as f:
            f.write(prompt)
        print(f"Reflection payload written to {output_path}")
        return prompt