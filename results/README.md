# results/ — LOCAL_RUN (INV-052)

Backtest, tuner, and validation output. **Not in git.** See
[`docs/governance/GITIGNORE_SCHEMA.md`](../docs/governance/GITIGNORE_SCHEMA.md).

Sealed measurement evidence that a finding may cite lives under
`docs/research-readiness/`, which **is** tracked. Do not write `Evidence:`
paths into this tree (findings gate reads `git ls-files`; F-071).

**2026-10-01 archive.** Top-level entries whose newest file was before
2026-09-01, and the same cut inside `research/` except `bar_matrix`, were
packed to `D:\Tradelatest-archives\2026-10-01\` (`results_before_2026-09.tar.gz`,
`results_research_before_2026-09.tar.gz`) and removed here. September runs,
`layer_trace`, `bar_matrix`, and `research/_spine_entries` stayed. Manifest:
`MANIFEST.jsonl` beside the packs.
