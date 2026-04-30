import subprocess
import json
import re
import os
from datetime import datetime, timezone

class MetaGovernorExecutor:
    def __init__(
        self,
        bitnet_bin="./bitnet/bin/main",
        model_path="./models/bitnet_b1_58_70b.gguf",
        audit_log_path="logs/governance_audit.jsonl",
    ):
        self.bitnet_bin = bitnet_bin
        self.model_path = model_path
        self.audit_log_path = audit_log_path

    def run_inference(self, prompt_path="logs/meta_prompt.txt") -> str:
        with open(prompt_path, 'r') as f:
            prompt = f.read()

        cmd = [
            self.bitnet_bin,
            "-m", self.model_path,
            "-p", prompt,
            "-n", "256",
            "--temp", "0.1",
            "-c", "2048"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout

    def extract_and_validate_config(self, raw_output: str) -> dict:
        match = re.search(r'\{.*\}', raw_output, re.DOTALL)

        if not match:
            raise ValueError("No JSON found.")

        json_str = match.group(0)
        candidate_config = json.loads(json_str)

        if "fusion_min_score" not in candidate_config:
            raise KeyError("Missing keys")

        return candidate_config

    def log_governance_event(
        self,
        event_type: str,
        engine_id: str,
        metrics_snapshot,
        decision,
        audit_log_path: str = None,
    ) -> dict:
        if not event_type:
            raise ValueError("event_type is required")
        if not engine_id:
            raise ValueError("engine_id is required")

        if isinstance(metrics_snapshot, dict):
            normalized_metrics = metrics_snapshot
        elif metrics_snapshot is None:
            normalized_metrics = {}
        else:
            normalized_metrics = {"value": metrics_snapshot}

        if isinstance(decision, dict):
            normalized_decision = decision
        else:
            normalized_decision = {"summary": str(decision)}

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "event_type": event_type,
            "engine_id": engine_id,
            "metrics_snapshot": normalized_metrics,
            "decision": normalized_decision,
        }

        path = audit_log_path or self.audit_log_path
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        print(f"📝 Writing governance event to: {os.path.abspath(path)}")
        
        with open(path, "a", encoding="utf-8") as f:
            line = json.dumps(event, sort_keys=True) + "\n"
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        
        print(f"✅ Event written OK: {event['event_type']} / {event['engine_id']}")

        return event
