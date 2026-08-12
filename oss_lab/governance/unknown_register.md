# OSS Lab UNKNOWN Register

Policy: if source code, documentation, runtime evidence, or benchmark artifacts
cannot establish something — write **UNKNOWN**, then record:

- what was attempted
- which source was inspected
- what exact link is missing
- what test would close the gap

| UNKNOWN ID | Claim | Attempted | Source inspected | Missing link | Closing test |
|---|---|---|---|---|---|
| U-OSS-001 | Qlib exact version/commit suitable for lab pin | Registry seed only | user brief + knowledge_graph.json | no version pin, no install, no license scan artifact | supply-chain check + pin commit after APPROVED_FOR_LAB |
| U-OSS-002 | Nautilus fill-model parity with TL-FILL-INTRABAR-FIXED-V1 | Design only | user brief | no adapter run, no fill declaration | fill-model sensitivity scenario A/B/C |
| U-OSS-003 | FinRL license obligations | Registry seed | repository URL only | LICENSE file not fetched in this turn | open LICENSE + record obligations |
| U-OSS-004 | XAUUSD Phase-1 schema_hash for OHLCV columns | Bound corpus hash + row range | CORPUS_AUTHORITY + phase1 binding | ohlcv-output-contract hash not auto-bound into DatasetManifest.schema_hash | bind schema_hash from ohlcv-output-contract on first lab run |
| U-OSS-005 | Tradelatest offline ledger latency | Adapter maps NOT_APPLICABLE | journal + backtest ledgers | no wall-clock clocks in offline rows | live rail latency study (blocked F-073) |
| U-OSS-006 | Cross-engine Sharpe annualization basis | CanonicalMetrics refuses inventing | research.measurement.metrics | no declared return frequency for OSS engines | declare frequency per scenario |
| U-OSS-007 | Whether Qlib/Nautilus/FinRL can consume MT5 broker-local timestamps without re-label | Design | F-066 finding | no adapter implementation | dataset timezone certification per adapter |
| U-OSS-008 | Security/supply-chain status of all external OSS | NOT_ASSESSED | none | no SBOM / advisory scan | security check step in intake pipeline |
| U-OSS-009 | Codebase-Memory version pin + Windows SHA-256 | **CLOSED 2026-08-12** — pin v0.10.2 / b377c62a…; zip SHA-256 match | LICENSE@pin, release API, checksums.txt, local hash | — | residual SLSA/cosign still U-OSS-009b |
| U-OSS-009b | Codebase-Memory SLSA3 + cosign local verify | **ATTEMPTED 2026-08-12** — `gh`/`cosign` not on PATH; cosign **bundle downloaded** | SECURITY.md; local `.bundle` next to zip | tools not installed | install gh+cosign and run verify before/at first execute |
| U-OSS-009c | GitHub update-check residual on MCP initialize | Documented in SECURITY.md | SECURITY.md Runtime Network Behavior | whether lab can fully disable | block outbound or measure at first run |
| U-OSS-010 | Infigraph LICENSE byte-level confirmation | Monitor brief says Apache-2.0 | GitHub project page | LICENSE file not fetched this turn | open LICENSE on pin |
| U-OSS-011 | LEAN fill-model parity vs TL-FILL-INTRABAR-FIXED-V1 | Design only | lean.io docs (secondary) | no adapter run | fill-model A/B under BM-SCENARIO-EXECUTION-THREE-WAY |
| U-OSS-012 | RIG paper gains transfer to Tradelatest | Paper cited | arXiv:2601.10112 | no local agent structural Q&A benchmark | reproduce on fixed Tradelatest question set |
| U-OSS-013 | VectorBT authoritative license for intended pin | Monitor Commons Clause note | secondary LICENSE links | legal review incomplete | counsel + pin LICENSE hash |

Do **not**:

- infer hidden formulas
- infer architecture from filenames alone
- convert documentation into runtime truth
- convert backtest results into feature identity
- convert OSS claims into Tradelatest evidence
