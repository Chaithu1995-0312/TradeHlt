# LAYER_TRACE_LAYOUT_DECISION_01 — frozen

**Choice:** **A — per-run trace files**  
**Frozen:** 2026-09-23 (UTC 2026-09-22T19:40:46Z) by User  
**Source answer:** A — per-run trace files

## Formula

TRACE_LAYOUT := PER_RUN_FILE; path := f(run_id); ¬SHARED_APPEND_MEGASTORE

## Options on record

| Option | Chosen? | Meaning |
|---|---|---|
| **A — per-run trace files** | **YES** | One layer_trace file per content 
un_id |
| **B — shared append (status quo)** | no | Keep XAUUSD_layer_trace.jsonl multi-run megastore |
| **C — hybrid pointer** | no | Shared write + per-run manifest (inferred third cell) |

## Does not authorize

Emitter rewrite, migration/deletion of the shared file, or HTF structural-break patch.

## Next (only if User authorizes Act)

1. Emitter → per-run path  
2. Catalog + join-map update  
3. Optional Run1 slice extract for forensics  

Machine record: LAYER_TRACE_LAYOUT_DECISION_01.json
