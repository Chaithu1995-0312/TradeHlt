# MC-OPP-DETECT-01 - Detection Authority Contract

**Status:** FROZEN
**Frozen (IST):** 2026-09-20
**Layer:** Detection Authority (upstream of Measurement / MC-JOINT-01)
**Machine:** `multi_llm/parameter_usage_audit/MC-OPP-DETECT-01.json`

## 1. Charter (normative)

| Clause | Rule |
|--------|------|
| Goal | Detect trade opportunities. |
| Authority | MT5. No CRT / strategy gate may authorize or veto detection birth. |
| Source of Truth | Broker OHLCV admitted through `dataset_integrity` / `corpus_store`. |
| Immutable | `trade_id`, `dataset_identity`. Mutation after mint = contract breach. |
| May drift | Feature values and model predictions only. |
| Governance | Opportunity **schema** changes (add / rename / remove / type-change of identity or geometry columns) require explicit User approval before merge. Feature-column drift under `features.*` does not. |
| Observability | `trace_id` is required on every record at every stage that touches the opportunity (JSONL, parquet, clean_labels join, measurement emit). |

## 2. Gaps closed by this freeze

These were open before the card. The contract **closes** them by naming authority and fail-closed rules - not by leaving them as TODOs.

### G1 - `trade_id` (was missing)

**Closed rule:** `trade_id` is the immutable opportunity unit identity.

**Mint (canonical):** SHA1 hex of
`{instrument}|{timestamp_iso}|{direction}|{entry:.8f}|{sl:.8f}`
truncated to 16 chars - same recipe as `clean_labels.builder._unit_id`.

**Alias:** existing `unit_id` is a **legacy synonym** of `trade_id`. New writers emit `trade_id`. Readers MUST accept either until a schema-approval pass drops `unit_id`.

**Not** `trace_id`, `analysis_id`, or `run_id`.

### G2 - `dataset_identity` (was ungated on opportunity rows)

**Closed rule:** every opportunity record MUST carry `dataset_identity` as an object (or flattened pair):

``
dataset_identity = {
  "csv_sha256": <sha256 of admitted broker OHLCV file>,
  "dataset_id": <corpus admission dataset_id>
}
``

Provenance pair matches `corpus_store` / CorpusAdmission discipline. Rows without both fields are **non-admitted** for Detection Authority consumers.

### G3 - schema governance (was informal)

**Closed rule:** changes to REQUIRED_COLUMNS (below) or identity mint recipe need User approval (chat ACK or PR label). Feature payloads under `features.*` may evolve without that gate.

### G4 - `trace_id` dropped in parquet (observability hole)

**Closed rule:** parquet is not a second schema. Any materialization of opportunities (JSONL -> parquet, feather, DB) MUST preserve the full identity nest. A parquet file missing `trade_id` / `trace_id` / `dataset_identity` is **invalid under this contract** even if row geometry is intact.

Evidence of breach (pre-freeze):
`logs/XAUUSD/xauusd_phase1_20260723/opportunities.parquet` - 94332 rows, no identity columns - **non-compliant**; must be regenerated or stamped before use as Detection Authority input.

## 3. Identity nest (immutable spine)

``
dataset_identity          # broker OHLCV provenance
    └── trace_id          # campaign TR-*
          └── analysis_id # analysis AN-* within opportunity layer
                └── run_id      # scan pass (folder scope)
                      └── trade_id    # unit (mint recipe G1)
``

`trace_id` flows through all stages. Downstream measurement (MC-JOINT-01) consumes `trade_id` and MUST forward `trace_id` in meta - it does not mint a new campaign id.

## 4. REQUIRED_COLUMNS (opportunity record)

**Identity (immutable):**
`trade_id` · `trace_id` · `analysis_id` · `run_id` · `dataset_identity.csv_sha256` · `dataset_identity.dataset_id` · `instrument` · `timestamp`

**Geometry (fixed for the unit after mint):**
`direction` · `entry` · `sl` · `tp`

**May drift (not identity):**
`features.*` · prediction / score columns · diagnostic outcomes from scanner walks

Scanner walk labels (`outcome`, `rr_achieved`, ...) are **Detection diagnostics**, not Measurement authority. Money truth remains MC-JOINT-01 path / `y_R_net`.

## 5. Relation to MC-JOINT-01

| | MC-OPP-DETECT-01 | MC-JOINT-01 |
|--|------------------|-------------|
| Layer | Detection | Measurement |
| Birth | opportunity row | joint-state emit |
| Authority | MT5 OHLCV | path / `y_R_net` |
| Engine | OpportunityScanner | TradeLifecycleEngine v0 |
| Mismatch | n/a | state membership, not error |

Detection produces candidates. Measurement labels them. Neither layer may silently rewrite the other's immutable ids.

## 6. Fail-closed checks (normative)

1. Missing `trace_id` or `analysis_id` at scanner write -> abort (already live).
2. Missing `trade_id` (or legacy `unit_id`) on emit -> abort for contract-aware consumers.
3. Missing `dataset_identity` pair -> abort.
4. Parquet / export that strips identity columns -> reject artifact.
5. Schema change to REQUIRED_COLUMNS without User approval -> do not merge.

## 7. Remediation bind (implementation, not re-opened design)

| Item | Action | Closes |
|------|--------|--------|
| R1 | Scanner / clean_labels emit `trade_id` (= current `_unit_id` recipe) | G1 |
| R2 | Stamp `dataset_identity` from corpus admission onto every opportunity row | G2 |
| R3 | Parquet writers preserve identity nest; regenerate non-compliant XAUUSD parquet before Detection use | G4 |
| R4 | TradeLifecycleEngine meta forwards `trade_id` + `trace_id` | nest continuity |

Design is frozen. R1-R4 are implementation against this card - they do not re-open the charter.

## 8. Non-goals

- Does not authorize live orders.
- Does not change CRT / ResetLogic / HTF clock.
- Does not alter MC-JOINT-01 six-state ontology or path authority.
- Does not invent a seventh joint state.