"""Read-only parity/runtime-authority probes (in memory; writes only the JSON given by --out)."""
import argparse, glob, hashlib, json, logging, sys, zipfile
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src")); logging.disable(logging.CRITICAL)
out = {}

from features import feature_schema as fs, dataset_builder as db
CF = list(fs.CANONICAL_FEATURES)
mx = json.loads((ROOT / "model_export_format.json").read_text())
out["P1_schema_sources"] = {
    "CANONICAL_FEATURES": len(CF), "dataset_builder_order_equal": CF == list(db.CANONICAL_FEATURE_ORDER),
    "model_export_order_equal": mx["feature_order"] == CF, "model_export_schema_version": mx["schema_version"],
    "module_SCHEMA_VERSION": fs.SCHEMA_VERSION, "SchemaObject_version": fs.GAUSSIAN_SCHEMA.version,
    "SCHEMA_HASH_names_only_md5": fs.SCHEMA_HASH, "SchemaObject_checksum_md5_json": fs.GAUSSIAN_SCHEMA.checksum,
    "hashes_comparable": fs.SCHEMA_HASH == fs.GAUSSIAN_SCHEMA.checksum,
    "extra_validate_vector_implementations": ["features/feature_schema.py::validate_vector (raises ValueError)", "features/schema_validator.py::validate_vector (raises AssertionError)"],
}
from training import trainer
inv = []
for p in sorted(glob.glob(str(ROOT / "models/gaussian_*.json"))):
    n = Path(p).name
    if "registry" in n: continue
    b = json.loads(Path(p).read_text()); fsch = b.get("feature_schema", [])
    try:
        trainer.load_gaussian_model(n); res = "loads"
    except Exception as e:
        res = f"rejected:{type(e).__name__}"
    inv.append(dict(file=n, n_features=len(fsch), checksum=b.get("schema_checksum", "")[:8], load=res,
                    missing=[x for x in CF if x not in fsch][:5], timeframe_recorded=any(k in b for k in ("timeframe", "provenance"))))
out["P2_gaussian_inventory"] = inv
tn = []
for p in sorted(glob.glob(str(ROOT / "models/tradenet_p5_*.pth"))):
    z = zipfile.ZipFile(p); sz = {n.split("/")[-1]: z.getinfo(n).file_size // 4 for n in z.namelist() if "/data/" in n}
    tn.append(dict(file=Path(p).name, first_layer_inputs=sz["0"] // 32, expected_inputs=fs.TRADENET_SCHEMA.n_features))
out["P3_tradenet_inventory"] = dict(checkpoints=tn, torch_installed=bool(__import__("importlib").util.find_spec("torch")),
                                     note="loader (trainer.load_model) has no schema check and uses torch.load without weights_only; not executable here (no torch)")
res = {}
try:
    from features.dataset_builder import build_feature_vector  # noqa
    res["build_feature_vector"] = "present"
except Exception as e:
    res["build_feature_vector"] = f"{type(e).__name__}: {e}"
try:
    from features.dataset_builder import validate_feature_vector  # noqa
    res["validate_feature_vector"] = "present"
except Exception as e:
    res["validate_feature_vector"] = f"{type(e).__name__}: {e}"
try:
    from runtime.live_engine_hook import LiveEngineHook  # noqa
    res["LiveEngineHook"] = "present"
except Exception as e:
    res["LiveEngineHook"] = f"{type(e).__name__}: {e}"
res["trade_data_producers_in_repo"] = [str(p.relative_to(ROOT)) for p in list((ROOT / "src").rglob("*.py")) + list((ROOT / "scripts").rglob("*.py"))
                                       if "trade_data" in p.read_text(errors="ignore") and "analysis" not in p.parts]
out["P4_live_path"] = res
# formulas on one synthetic candle
o, h, l, c = 100.0, 104.0, 98.0, 102.0
from features.feature_pipeline import FeaturePipeline
from runtime.live_engine_hook import _build_ohlcv_and_auxiliary
from features.bitnet_feature_builder import build_bitnet_features
ohlcv, aux = _build_ohlcv_and_auxiliary(dict(open=o, high=h, low=l, close=c, volume=1.0))
bf = build_bitnet_features({}, dict(open=o, high=h, low=l, close=c, volume=1), {})
from config_layer.crt_engine_v2 import Candle
import inspect
cd = Candle(**{k: v for k, v in dict(timestamp=pd.Timestamp("2025-01-01"), open=o, high=h, low=l, close=c, volume=1.0).items() if k in inspect.signature(Candle).parameters})
out["P5_formulas_one_candle(O100,H104,L98,C102)"] = {
    "pipeline/CRT Candle/manual_backtest": {"body_size": abs(c - o), "wick_size": cd.wick_size, "body_ratio": cd.body_ratio},
    "live_engine_hook": {"wick_size": aux["wick_size"], "body_ratio": aux["body_ratio"]},
    "bitnet_feature_builder(no callers)": {"wick_size": bf["wick_size"], "body_ratio": bf["body_ratio"]},
}
# double_sweep: +1 sweep, 6 quiet bars, -1 sweep
from core.feature_store import FeatureStore
seq = [1, 0, 0, 0, 0, 0, 0, -1]
st = FeatureStore(); last = None
for i, s in enumerate(seq):
    d = dict(open=1, high=2, low=0.5, close=1.5, volume=1.0, atr=0.001, ema_fast=1, ema_slow=1, session=1, liquidity_sweep=s)
    d.update({k: 0.0 for k in CF if k not in d})
    st._compute_derived(d, i); last = d["double_sweep"]
pipe = bool(np.any(np.array(seq[-5:]) > 0) and np.any(np.array(seq[-5:]) < 0))
out["P6_double_sweep(+1,6x0,-1)"] = {"FeatureStore_deque10": int(last), "pipeline_window5": int(pipe)}
# session encodings
hours = [3, 10, 20]
out["P7_session"] = {"pipeline(hour<8:0,<16:1,else:2)": [0 if x < 8 else 1 if x < 16 else 2 for x in hours],
                     "feature_schema.SESSION_MAP": fs.SESSION_MAP, "hook_normalize_output_examples": [0, 1, 2], 
                     "hook_strings": [__import__("runtime.live_engine_hook", fromlist=["x"])._normalize_session(i) for i in (0, 1, 2)]}
# live-built dict -> consumer
frame = FeatureStore().process(0, "t", ohlcv, aux).features
try:
    db.extract_feature_vector(frame); ev = "ok"
except Exception as e:
    ev = f"{type(e).__name__}: {e}"
from engines.ml_gaussian_engine import MLGaussianEngine
num = {k: float(0) for k in CF}; num["session"] = 1.0
out["P8_consumer_on_live_built_dict"] = {"session_type": type(frame["session"]).__name__, "extract_feature_vector": ev,
                                         "MLGaussianEngine.compute": MLGaussianEngine({}).compute(frame),
                                         "MLGaussianEngine.compute_numeric_session": MLGaussianEngine({}).compute(num)}
# registries
from engines.heuristic_gaussian_engine import GaussianRegistry
from core.model_registry import get_active_gaussian
reg = {}
for lab, pth in (("current", "models/gaussian_registry.json"), ("pre_change_backup", "models/gaussian_registry.pre_xau_m15_causal_n9_20261011.json")):
    try:
        r = GaussianRegistry(str(ROOT / pth)).load(); reg[lab] = dict(heuristic_reader_active=r.active_version, mu=r.mu, sigma=r.sigma)
    except Exception as e:
        reg[lab] = f"{type(e).__name__}: {e}"
reg["model_registry.get_active_gaussian()"] = get_active_gaussian()
reg["v1.json"] = json.loads((ROOT / "models/v1.json").read_text())
reg["production_gaussian_impl"] = json.loads((ROOT / "configs/production/v1_multi_2026_03.json").read_text()).get("engine_runner", {}).get("gaussian_impl") or "see engine_runner.py:72"
out["P9_registry_readers"] = reg
Path(sys.argv[sys.argv.index("--out") + 1]).parent.mkdir(parents=True, exist_ok=True)
Path(sys.argv[sys.argv.index("--out") + 1]).write_text(json.dumps(out, indent=2, default=str))
print(json.dumps({k: out[k] for k in ("P4_live_path", "P5_formulas_one_candle(O100,H104,L98,C102)", "P6_double_sweep(+1,6x0,-1)", "P8_consumer_on_live_built_dict", "P9_registry_readers")}, indent=1, default=str)[:3800])
