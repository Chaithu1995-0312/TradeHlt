# Full-suite conditioned reds (named in advance)

| Test | Baseline | After A | Class |
|---|---|---|---|
| provenance fingerprint / compare_surfaces (x2) | green | red | expected-caused-by-A (ADDENDUM) |
| completeness census total/complete (x2) | red | red | pre-existing (DRIFT-PARAM-CENSUS-01) |
| reachability field coverage | red | red | pre-existing (DRIFT-PARAM-REACHABILITY-01) |

**Diff mechanics:** Pre-existing reds do not appear in the diff; only the two provenance transitions are expected. They are filtered by construction (same red state before and after), not by manual skip. Any other before/after delta is signal.
