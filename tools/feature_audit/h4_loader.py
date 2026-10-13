"""Load data/mt5/XAUUSD_H4.csv with timestamps converted to UTC through its DECLARED clock.

Read-only: `require_reviewed_clock` checks the registry record + file SHA, and `to_utc_series` is the
repo's pure conversion. Nothing is written (unlike corpus_store.load, which caches into data/).
"""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
import pandas as pd
from data_ingestion.clock_registry import require_reviewed_clock
from data_ingestion.clock_contract import to_utc_series

H4_PATH = os.path.join(ROOT, "data", "mt5", "XAUUSD_H4.csv")

def load_h4_utc():
    resolved = require_reviewed_clock("data/mt5/XAUUSD_H4.csv")
    raw = pd.read_csv(H4_PATH)
    raw["timestamp"] = to_utc_series(pd.to_datetime(raw["timestamp"]), resolved.clock)
    # Same tag corpus_store.frame() sets (corpus_store.py:625). Without it FeaturePipeline falls back
    # to the UTC calendar (feature_pipeline.py:475-478) instead of fx_metals (17:00 New York day).
    raw.attrs["instrument"] = "XAUUSD"
    return raw, resolved.clock.clock_id

def load_h4_file_time():
    raw = pd.read_csv(H4_PATH)
    raw["timestamp"] = pd.to_datetime(raw["timestamp"])
    return raw
