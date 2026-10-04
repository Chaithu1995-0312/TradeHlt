# MSIP-1 Verification Package

Frozen multi-LLM verification corpus for the Market-State Interpretation Program.

- **Generated:** 2026-07-14T07:08:43Z
- **Git commit:** `b48d4d9a7abfb429f2a17c790d4b32083da5dd92`
- **Branch:** `feature/truth-registry-v2`
- **Production code mutated by packaging:** NO

## Start here

1. Read `00_manifest/MSIP-1_VERIFICATION_PROMPT.md`
2. Read `00_manifest/AUTHORITY_FRESHNESS.md`
3. Read `00_manifest/MSIP-1_DESIGN_CONTRACT.md`
4. Verify file hashes in `00_manifest/MSIP-1_SOURCE_MANIFEST.json`

## Verdict storage

Place each LLM response under `07_llm_responses/` without editing.

Final adjudication (ChatGPT or human) builds a cross-LLM claim matrix and
rechecks material disputes against this package only.
