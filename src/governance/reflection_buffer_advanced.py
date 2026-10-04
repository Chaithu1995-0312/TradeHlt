import json
import pandas as pd
from pathlib import Path
from features.feature_schema import CANONICAL_FEATURES

class ReflectionBuffer:
    def __init__(
        self,
        logs_path="logs/collector.jsonl",
        trades_path="results/real_backtest/AUDUSD_trades.csv",
        *,
        compressed_summary: dict | None = None,
    ):
        self.logs_path = Path(logs_path)
        self.trades_path = Path(trades_path)
        # Optional pre-computed summary produced by
        # scripts/analysis/compress_logs_for_llm.py. When set, the buffer
        # bypasses raw log parsing and builds prompts directly from the dict.
        self.compressed_summary = compressed_summary

    def load_and_merge(self) -> pd.DataFrame:
        if self.compressed_summary is not None:
            # Compressed-summary path skips the raw merge — return an empty
            # DataFrame so callers that only use generate_prompt_payload()
            # still work, and any column lookups fail loudly.
            return pd.DataFrame()
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
        if self.compressed_summary is not None:
            return self._prompt_from_compressed_summary(output_path)

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

    def _prompt_from_compressed_summary(self, output_path: str) -> str:
        """Build a meta-governor prompt directly from a compressed summary dict.

        Schema mirrors what scripts/analysis/compress_logs_for_llm.py emits:
          {summary, data, anomalies}
        Avoids re-parsing the raw collector log / trades CSV.
        """
        s = self.compressed_summary or {}
        summary = s.get("summary", {})
        data = s.get("data", {})
        anomalies = s.get("anomalies", [])
        n_total = summary.get("n_total", 0)
        counts_outcome = summary.get("counts_outcome", {})
        top_pos = data.get("top_positive_corr", [])[:3]
        top_neg = data.get("top_negative_corr", [])[:3]
        delta = data.get("top_tp_minus_sl_delta", [])[:3]
        anomaly_count = len(anomalies)

        def _fmt_pairs(pairs):
            return ", ".join(f"{name}={val:+.3f}" for name, val in pairs) or "n/a"

        prompt = (
            "[SYSTEM] You are the Nexus Meta-Governor. Your role is strict, "
            "deterministic parameter optimization. Do not explain your reasoning. "
            "Output ONLY a valid JSON object.\n\n"
            "[COMPRESSED SUMMARY]\n"
            f"records={n_total} | outcomes={counts_outcome} | "
            f"rr_mean={summary.get('rr_mean')} rr_std={summary.get('rr_std')}\n\n"
            "[TOP FEATURE CORRELATIONS WITH RR]\n"
            f"positive: {_fmt_pairs(top_pos)}\n"
            f"negative: {_fmt_pairs(top_neg)}\n"
            f"tp_minus_sl_delta: {_fmt_pairs(delta)}\n"
            f"anomalies_flagged: {anomaly_count}\n\n"
            "[TASK]\n"
            "Output a JSON patch adjusting `fusion_min_score` and "
            "`weak_component_threshold` so weak setups are filtered.\n\n"
            "[REQUIRED OUTPUT FORMAT]\n"
            "{\n"
            "    \"decision_engine\": {\"weak_component_threshold\": <float>},\n"
            "    \"fusion_min_score\": <float>\n"
            "}"
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(prompt)
        print(f"Reflection payload (compressed) written to {output_path}")
        return prompt