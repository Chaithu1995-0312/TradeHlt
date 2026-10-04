# OSS Lab Risk Register

| Risk ID | Risk | Severity | Mitigation | Status |
|---|---|---|---|---|
| R-OSS-001 | External OSS becomes de-facto authority over market semantics | Critical | Forbidden surfaces + T4 ban + adapter isolation | OPEN |
| R-OSS-002 | Silent pip install / global import pollution | High | Lab-only package; no production imports of oss_lab reverse; no deps installed yet | OPEN |
| R-OSS-003 | Incomparable metrics (each framework's native PF/Sharpe) | High | Independent `CanonicalMetrics` over BenchmarkTradeRecord | MITIGATED (scaffold) |
| R-OSS-004 | Dataset divergence (downloads, timezone, fill gaps) | High | DatasetManifest pin to Phase-1 frozen corpus | MITIGATED (schema) |
| R-OSS-005 | Lookahead accepted on documentation claims | High | Future-mutation probe protocol | DESIGNED |
| R-OSS-006 | Nautilus LGPL-3.0 obligations violated | High | LEGAL_REVIEW_REQUIRED gate before integration | OPEN |
| R-OSS-007 | FinRL published returns treated as edge | High | RESEARCH_ONLY; independent reproduction required | OPEN |
| R-OSS-008 | Cost/slippage models incomparable across engines | Medium | Declared cost_mode + fill_model + separate gross/net components | DESIGNED |
| R-OSS-009 | Simulated latency mixed with real broker latency | Medium | Latency fields require clock/source; NOT_APPLICABLE for offline | MITIGATED (contract) |
| R-OSS-010 | Reproducibility claimed without triple-run hash proof | Medium | RunManifest + triple_run scenario flag | DESIGNED |
| R-OSS-011 | Research EdgeAggregator vs spine BacktestMetrics conflation | Medium | Explicit quarantine notes; separate lab metrics path | MITIGATED (docs) |
| R-OSS-012 | Semantic OS overclaiming OSS capability as runtime truth | Medium | Semantic OS remains advisory; UNKNOWN policy | DESIGNED |
| R-OSS-013 | Codebase-Memory becomes de-facto Semantic OS | High | Forbidden surfaces on semantic_os + structural-vs-meaning split; StructuralFactRecord only | OPEN |
| R-OSS-014 | Dual adoption of Codebase-Memory + Infigraph without H2H | Medium | Single evaluation queue + BM-SCENARIO-REPO-INTEL-H2H | OPEN |
| R-OSS-015 | LEAN strategy architecture imported into Tradelatest | High | T3 adapter-only; forbidden_surfaces include strategies/core/governance | OPEN |
| R-OSS-016 | VectorBT Commons Clause commercial restriction | High | decision=DEFERRED; LEGAL_REVIEW_REQUIRED | OPEN |
| R-OSS-017 | Published RIG/Codebase-Memory gains treated as local ROI | Medium | REFERENCE_ONLY / reproduce-before-finding rule | OPEN |
| R-OSS-018 | Codebase-Memory filesystem read + agent config writes | High | ASSESSED_RISK; source audit + SLSA/Sigstore before binary trust | OPEN |
