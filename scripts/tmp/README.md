# scripts/tmp/

Scratch / throwaway scripts (local experiments). Same SITS rules as `scripts/probes/`.

- Prefer this directory over repo-root `_*.py`
- Expect lifecycle `EPHEMERAL`; close with `CLOSED_EPHEMERAL` + archive when done
- Always re-run census `--write-stubs` before commit if you add a `.py` here
