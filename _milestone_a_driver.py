"""
Milestone A — complete the EFAP join-gate acceptance matrix with real CLI evidence.

Four genuinely-minted identity records -> three validate-join audits:

  [1] UNVERIFIED_OPERAND    left=VERIFIED  right=historic bare run (no identity)
  [2] RUN_ID_MISMATCH        left=VERIFIED(run A)  right=VERIFIED(run B)  -> diff run_id
  [3] CONFIG_HASH_MISMATCH   left/right same run_id, different REAL config hashes

Every identity is minted through the canonical authority:
    governance.run_identity.build_identity(...)  with
    config_hash  = config_layer.production_config registry hash (real, verified)
    dataset_hash = governance.run_identity.dataset_hash() over a real CSV bytes  (real)
No hash is invented. Artifacts are written under logs/scratch_efap_audit/.
The join gate is exercised via the real CLI:  python -m governance.run_identity validate-join
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

from governance.run_identity import build_identity, dataset_hash
from config_layer.production_config import get_prod_metadata, PROD_VERSION, PRODUCTION_REGISTRY_DIR, _compute_params_hash

OUT = Path("logs/scratch_efap_audit")
OUT.mkdir(parents=True, exist_ok=True)

ACTIVE = get_prod_metadata()
ACTIVE_CFG_HASH = str(ACTIVE.get("config_hash") or "")
# Second REAL config hash: v4_multi_2026_06 passes IFF its params differ (verified distinct earlier).
V4 = Path(PRODUCTION_REGISTRY_DIR) / "v4_multi_2026_06.json"
V4_CFG_HASH = _compute_params_hash(json.loads(V4.read_text(encoding="utf-8"))["params"])

DATASETS = {
    "BNBUSDT": Path("data/BNBUSDT_M15.csv"),
    "BTCUSDT": Path("data/BTCUSDT_M15.csv"),
    "DOGEUSDT": Path("data/DOGEUSDT_M15.csv"),
}
for k, p in DATASETS.items():
    if not p.exists():
        raise SystemExit(f"missing data CSV for {k}: {p}")

TS = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

def stamp(name: str, run_id: str, cfg_hash: str, ds_hash: str, cfg_version: str) -> Path:
    ident = build_identity(run_id, cfg_version, cfg_hash, ds_hash).to_dict()
    p = OUT / name
    p.write_text(json.dumps(ident, indent=2), encoding="utf-8")
    return p

def cli(left: Path, right: Path) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, "-m", "governance.run_identity", "validate-join", str(left), str(right)],
        capture_output=True, text=True,
    )
    return r.returncode, (r.stdout or r.stderr).strip()

# ── 1) UNVERIFIED_OPERAND -----------------------------------------------------
left_unv = stamp(
    "1_unverified_left_VERIFIED.json",
    f"run_{TS}_UNV_L", ACTIVE_CFG_HASH, dataset_hash(DATASETS["BNBUSDT"]), PROD_VERSION,
)
right_unv = OUT / "1_unverified_right_HISTORIC_bare.json"
_hist_run_id = "run_20260903_161258_XAUUSD"   # derived from historic run dir name (real artifact)
_HIST_PATH = Path("logs/dual_construction/scratch_roots/arm_a_v2_baseline/results/run_20260903_161258_XAUUSD")
assert (_HIST_PATH / "XAUUSD_events.jsonl").exists(), "historic artifact missing"
right_unv.write_text(json.dumps({"run_id": _hist_run_id}), encoding="utf-8")

# ── 2) RUN_ID_MISMATCH (both VERIFIED, different real datasets) ---------------
left_rid = stamp(
    "2_runid_left_A.json",
    f"run_{TS}_RA", ACTIVE_CFG_HASH, dataset_hash(DATASETS["BNBUSDT"]), PROD_VERSION,
)
right_rid = stamp(
    "2_runid_right_B.json",
    f"run_{TS}_RB", ACTIVE_CFG_HASH, dataset_hash(DATASETS["DOGEUSDT"]), PROD_VERSION,
)

# ── 3) CONFIG_HASH_MISMATCH (same run_id, two REAL config hashes) -------------
left_cfh = stamp(
    "3_cfgleft_ACTIVE_hash.json",
    f"run_{TS}_CFH", ACTIVE_CFG_HASH, dataset_hash(DATASETS["BNBUSDT"]), PROD_VERSION,
)
right_cfh = stamp(
    "3_cfgright_v4_hash.json",
    f"run_{TS}_CFH", V4_CFG_HASH, dataset_hash(DATASETS["BNBUSDT"]), "v4_multi_2026_06",
)

print("ACTIVE_CFG_HASH:", ACTIVE_CFG_HASH)
print("V4_CFG_HASH    :", V4_CFG_HASH)
print()
rows = [
    ("UNVERIFIED_OPERAND", left_unv, right_unv),
    ("RUN_ID_MISMATCH",    left_rid, right_rid),
    ("CONFIG_HASH_MISMATCH", left_cfh, right_cfh),
]
for code, a, b in rows:
    rc, reason = cli(a, b)
    print(f"[{code}] exit={rc}")
    print(f"    {reason}")
    print()