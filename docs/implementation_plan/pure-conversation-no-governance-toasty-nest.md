# Export model_runners adapter table to Excel

## Context
This session is pure conversation (no governance/docs updates, per user's opening instruction) — we've been discussing `src/research/model_runners/` (built this session), an offline OBSERVATION_ONLY harness with one adapter per Stage-1/2/3 model (rr, gaussian, gaussian_ml, zone_gate, crt_score, crt_state_machine, fusion_compute, bitnet, tradenet, rr_trained, envelope), all invoked via `scripts/research/run_model_offline.py --model-id <id>`. I already read every adapter's source and built a verified table (model id | intent | invoking script | input | output) in-chat. The user now wants that table exported as a standalone Excel file — a small deliverable action requiring a file write, which needs to exit plan mode.

## Approach
Generate a single `.xlsx` with one sheet, 5 columns (Model id, Model Intent, Script, Input, Output), 11 data rows — content taken directly from the already-verified adapter source (no new research needed). Use openpyxl via a short Python script (repo has no existing xlsx-export utility to reuse; this is a one-off deliverable, not a codebase change — nothing under `src/`, `configs/`, or `docs/` is touched).

- Output file: `model_runners_adapters.xlsx`, written to the session scratchpad directory (`C:\Users\Hi\AppData\Local\Temp\claude\D--Tradelatest\d950b934-56b9-405f-9da0-fb3831c58c38\scratchpad\`) — this is a chat deliverable, not a repo artifact, so it does not belong under version control.
- Formatting: bold header row, column widths sized to content, wrap text on Input/Output columns for readability.
- Deliver the file to the user via `SendUserFile` once written.

## Verification
Open the generated `.xlsx` (or re-read it back with openpyxl) to confirm all 11 rows + header are present and no cell content was truncated/corrupted, then send it to the user.
