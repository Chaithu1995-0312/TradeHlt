#!/usr/bin/env python
"""initiate_plan.py — Initiate a Research Lane plan package for one LLM model.

Does NOT call any LLM API. Prepares:
  - curated CONTEXT_BUNDLE.md (from context_manifest.json — no full-repo scan)
  - model-separated PROPOSAL.md
  - PROMPT_FOR_<MODEL>.md ready to paste into that model
  - optional ledger line (PROPOSAL PROPOSED)

Usage:
  PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model grok
  PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model deepseek --cycle RC-001
  PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model claude --focus "P1 harness"
  PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model all --cycle RC-001

Models: deepseek | grok | gemini | claude | chatgpt

Additive flags (all default to the historical behaviour):
  --manifest <path>   use a cycle-scoped context manifest instead of context_manifest.json
  --kind <KIND>       PROPOSAL (default) | CRITIQUE | DECISION — stub read from templates/<KIND>.md
  --prompt <path>     use a bespoke role prompt instead of prompts/PLAN_DESIGN_PROMPT.md
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LANE = REPO / "multi_llm" / "research_lane"
MANIFEST = LANE / "context_manifest.json"
PROMPT_MASTER = LANE / "prompts" / "PLAN_DESIGN_PROMPT.md"
LEDGER = LANE / "research_cycle_ledger.jsonl"
PROPOSALS_ROOT = LANE / "proposals"
TEMPLATES = LANE / "templates"

KINDS = ("PROPOSAL", "CRITIQUE", "DECISION")
_KIND_ABBR = {"PROPOSAL": "PROP", "CRITIQUE": "CRIT", "DECISION": "DEC"}

MODELS: dict[str, dict[str, str]] = {
    "deepseek": {
        "role": "technical_critic",
        "author_role": "technical_critic",
        "task_hint": (
            "Default: if a PROPOSAL already exists for this cycle from another model, "
            "produce a CRITIQUE-oriented plan of attacks (still fill PROPOSAL only if none exists; "
            "otherwise write your output into PROPOSAL as 'critic plan package' and note CRITIQUE next). "
            "Prefer finding leakage, H1/H2/H3, multiple-testing, and freeze defects."
        ),
    },
    "grok": {
        "role": "hypothesis_diversity",
        "author_role": "hypothesis_diversity",
        "task_hint": (
            "Generate outside-view next steps and alternative hypotheses consistent with "
            "D-16 (no dead OHLCV archaeology). Prefer new info families and H_tool integrity first."
        ),
    },
    "gemini": {
        "role": "impl_navigator_or_quant_critique",
        "author_role": "architect",
        "task_hint": (
            "Lane-I style navigator for research: gaps, sequencing, quant risks. "
            "Keep wealth language at PL-0 unless context says higher."
        ),
    },
    "claude": {
        "role": "executor_plan_only",
        "author_role": "executor",
        "task_hint": (
            "Plan implementation steps for the next granted phase (default P1 harness). "
            "Do NOT implement in this turn of the human chat unless owner already granted; "
            "output an executable work-package list Claude can run after FREEZE DECISION."
        ),
    },
    "chatgpt": {
        "role": "architect",
        "author_role": "architect",
        "task_hint": (
            "Architect the next research cycle: prioritize phases, freeze criteria, "
            "and what to send critic/executor. No code."
        ),
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_manifest(manifest_path: Path | None = None) -> dict:
    path = manifest_path or MANIFEST
    if not path.is_file():
        raise FileNotFoundError(f"Missing context manifest: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_capped(path: Path, max_chars: int) -> tuple[str, bool]:
    if not path.is_file():
        return f"\n<!-- MISSING: {path} -->\n", True
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + f"\n\n<!-- TRUNCATED at {max_chars} chars: {path} -->\n", True
    return text, False


def build_context_bundle(
    out_dir: Path,
    max_chars: int | None = None,
    manifest_path: Path | None = None,
) -> dict:
    man = _load_manifest(manifest_path)
    used_manifest = manifest_path or MANIFEST
    default_cap = int(man.get("max_chars_per_file_default", 120000))
    cap = max_chars if max_chars is not None else default_cap
    docs = sorted(man.get("docs", []), key=lambda d: int(d.get("priority", 99)))

    index_lines = [
        "# CONTEXT_INDEX — "
        + str(man.get("description", "curated docs (no full-repo scan)")),
        "",
        f"Generated: {_utc_now()}",
        f"Manifest: `{used_manifest.relative_to(REPO).as_posix()}`",
        "",
        "| # | path | role | status |",
        "|---|---|---|---|",
    ]
    bundle_parts = [
        f"# CONTEXT_BUNDLE\n\nGenerated: {_utc_now()}\n\n"
        "Use ONLY this bundle + PROMPT. Do not invent repo files not listed.\n"
    ]
    missing = 0
    truncated = 0
    for i, doc in enumerate(docs, 1):
        rel = doc["path"]
        role = doc.get("role", "")
        path = REPO / rel
        body, was_trunc = _read_capped(path, cap)
        if body.startswith("\n<!-- MISSING"):
            missing += 1
            status = "MISSING"
        elif was_trunc:
            truncated += 1
            status = "TRUNCATED"
        else:
            status = "OK"
        index_lines.append(f"| {i} | `{rel}` | {role} | {status} |")
        bundle_parts.append(f"\n\n{'='*72}\n# SOURCE: {rel}\n# ROLE: {role}\n{'='*72}\n\n")
        bundle_parts.append(body)

    index_path = out_dir / "CONTEXT_INDEX.md"
    bundle_path = out_dir / "CONTEXT_BUNDLE.md"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    bundle_path.write_text("".join(bundle_parts), encoding="utf-8")
    return {
        "index_path": index_path,
        "bundle_path": bundle_path,
        "n_docs": len(docs),
        "missing": missing,
        "truncated": truncated,
    }


def _proposal_stub(model: str, cycle_id: str, focus: str, meta: dict) -> str:
    pid = f"{cycle_id}-PROP-{model.upper()}"
    return f"""# PROPOSAL — {model}

```yaml
schema_version: "1.0"
package_id: {pid}
kind: PROPOSAL
cycle_id: {cycle_id}
created_at: {_utc_now()}
author_role: {meta['author_role']}
author_model: {model}
claim_type: process
status: PROPOSED
promise_rung_max_claim: PL-0
```

## Summary
<!-- {model}: fill after reading CONTEXT_BUNDLE + PROMPT -->
_INITIATED empty — model must complete this section._

## Binds
- entrypoint: (TBD by model)
- lens: n/a
- ACTIVE_VERSION: (from context if stated)
- instruments: []
- phase: P1
- focus: {focus or "default next phase from phased plan"}

## Why it might work
-

## Why it might fail
-

## Falsifier
-

## H1 / H2 / H3 risks
-

## Controls / gates
-

## Stop condition
-

## Work packages (ordered)
1.

## Out of scope
-
"""


def _stub_for_kind(model: str, cycle_id: str, focus: str, meta: dict, kind: str) -> str:
    """PROPOSAL keeps the historical inline stub; other kinds read templates/<KIND>.md."""
    if kind == "PROPOSAL":
        return _proposal_stub(model, cycle_id, focus, meta)
    tpl = TEMPLATES / (kind + ".md")
    if not tpl.is_file():
        raise FileNotFoundError(f"Missing package template: {tpl}")
    nl = chr(10)
    header = (
        "<!-- INITIATED  model={m}  cycle={c}  kind={k}  at {t}" + nl
        + "     focus: {f}" + nl
        + "     Fill every section from the model reply; keep the yaml block. -->" + nl + nl
    ).format(m=model, c=cycle_id, k=kind, t=_utc_now(), f=focus or "(none)")
    return header + tpl.read_text(encoding="utf-8")


def _role_block(model: str, meta: dict) -> str:
    return (
        f"**Model:** `{model}`\n"
        f"**Research role:** `{meta['role']}`\n"
        f"**author_role:** `{meta['author_role']}`\n\n"
        f"**Role-specific instruction:**\n{meta['task_hint']}\n"
    )


def write_prompt(
    out_dir: Path,
    model: str,
    cycle_id: str,
    focus: str,
    proposal_rel: str,
    meta: dict,
    prompt_path: Path | None = None,
) -> Path:
    src = prompt_path or PROMPT_MASTER
    master = src.read_text(encoding="utf-8") if src.is_file() else (
        "Design a PROPOSAL using the CONTEXT_BUNDLE. Role: {{ROLE_BLOCK}}\n"
    )
    text = master
    text = text.replace("{{ROLE_BLOCK}}", _role_block(model, meta))
    text = text.replace("{{CYCLE_ID}}", cycle_id)
    text = text.replace("{{FOCUS}}", focus or "(none — use phased plan next grant)")
    text = text.replace("{{PROPOSAL_PATH}}", proposal_rel)
    text = text.replace("{{MODEL}}", model)

    header = (
        f"# PROMPT_FOR_{model.upper()}\n\n"
        f"Cycle: `{cycle_id}` · Generated: {_utc_now()}\n\n"
        f"**Paste this prompt + CONTEXT_BUNDLE.md into {model}.**\n\n"
        f"Output must update `{proposal_rel}` content (return full filled PROPOSAL markdown).\n\n"
        "---\n\n"
    )
    path = out_dir / f"PROMPT_FOR_{model.upper()}.md"
    path.write_text(header + text, encoding="utf-8")
    return path


def append_ledger(
    model: str, cycle_id: str, proposal_rel: str, out_dir_rel: str, kind: str = "PROPOSAL"
) -> None:
    line = {
        "schema_version": "1.0",
        "package_id": f"{cycle_id}-{_KIND_ABBR[kind]}-{model.upper()}-INIT",
        "kind": kind,
        "cycle_id": cycle_id,
        "created_at": _utc_now(),
        "author_role": "system",
        "author_model": "initiate_plan.py",
        "claim_type": "process",
        "summary": f"Initiated plan package for model={model}; {kind} stub awaiting model fill.",
        "binds": {
            "phase": "P0/P6.A",
            "promise_rung_max_claim": "PL-0",
            "entrypoint": "scripts/multi_llm/initiate_plan.py",
        },
        "artifact_paths": [proposal_rel, out_dir_rel],
        "status": "PROPOSED",
        "notes": f"model={model} kind={kind}",
    }
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def initiate_one(
    model: str,
    cycle_id: str,
    focus: str,
    *,
    no_ledger: bool,
    max_chars: int | None,
    manifest_path: Path | None = None,
    kind: str = "PROPOSAL",
    prompt_path: Path | None = None,
) -> Path:
    if model not in MODELS:
        raise SystemExit(f"Unknown model '{model}'. Choose: {', '.join(MODELS)}")
    meta = MODELS[model]
    out_dir = PROPOSALS_ROOT / model / cycle_id
    out_dir.mkdir(parents=True, exist_ok=True)

    ctx = build_context_bundle(out_dir, max_chars=max_chars, manifest_path=manifest_path)
    proposal_path = out_dir / (kind + ".md")
    proposal_path.write_text(
        _stub_for_kind(model, cycle_id, focus, meta, kind), encoding="utf-8"
    )
    proposal_rel = proposal_path.relative_to(REPO).as_posix()
    write_prompt(
        out_dir, model, cycle_id, focus, proposal_rel, meta, prompt_path=prompt_path
    )

    readme = out_dir / "README.md"
    readme.write_text(
        f"""# Plan initiation — `{model}` / `{cycle_id}`

## How to use
1. Open `PROMPT_FOR_{model.upper()}.md`
2. Attach or paste `CONTEXT_BUNDLE.md` (curated docs only)
3. Send to **{model}**
4. Replace `{kind}.md` with the model's filled {kind}
5. Optional: run critic model with a new `--model deepseek` package, or fill CRITIQUE template

## Files
- `CONTEXT_INDEX.md` — doc list ({ctx['n_docs']} entries; missing={ctx['missing']}, truncated={ctx['truncated']})
- `CONTEXT_BUNDLE.md` — concatenated context
- `PROMPT_FOR_{model.upper()}.md` — plan design prompt
- `{kind}.md` — model-separated {kind} package (fill)

## Commands
```bash
PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model {model} --cycle {cycle_id} --kind {kind}
```
""",
        encoding="utf-8",
    )

    if not no_ledger:
        append_ledger(
            model,
            cycle_id,
            proposal_rel,
            out_dir.relative_to(REPO).as_posix(),
            kind=kind,
        )

    return out_dir


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Initiate Research Lane plan package for one LLM (no API call)."
    )
    p.add_argument(
        "--model",
        "-m",
        required=True,
        help="deepseek | grok | gemini | claude | chatgpt | all",
    )
    p.add_argument("--cycle", "-c", default=None, help="Cycle id (default RC-YYYYmmdd-HHMM)")
    p.add_argument("--focus", "-f", default="", help="Optional focus string for the plan")
    p.add_argument("--no-ledger", action="store_true", help="Do not append research_cycle_ledger.jsonl")
    p.add_argument("--manifest", default=None, help="Cycle-scoped context manifest (default: context_manifest.json)")
    p.add_argument("--kind", default="PROPOSAL", choices=list(KINDS), help="Package kind (default PROPOSAL)")
    p.add_argument("--prompt", default=None, help="Bespoke role prompt (default: prompts/PLAN_DESIGN_PROMPT.md)")
    p.add_argument(
        "--max-chars-per-file",
        type=int,
        default=None,
        help="Cap each context file (default from manifest)",
    )
    args = p.parse_args(argv)

    cycle_id = args.cycle or datetime.now(timezone.utc).strftime("RC-%Y%m%d-%H%M")
    models = list(MODELS) if args.model.lower() == "all" else [args.model.lower()]

    print(f"cycle_id={cycle_id}")
    for m in models:
        out = initiate_one(
            m,
            cycle_id,
            args.focus,
            no_ledger=args.no_ledger,
            max_chars=args.max_chars_per_file,
            manifest_path=Path(args.manifest).resolve() if args.manifest else None,
            kind=args.kind,
            prompt_path=Path(args.prompt).resolve() if args.prompt else None,
        )
        rel = out.relative_to(REPO).as_posix()
        print(f"  [{m}] -> {rel}/")
        print(f"       PROMPT: {rel}/PROMPT_FOR_{m.upper()}.md")
        print(f"       PACKAGE:  {rel}/{args.kind}.md")
        print(f"       CONTEXT: {rel}/CONTEXT_BUNDLE.md")
    print("Done. Paste PROMPT + CONTEXT_BUNDLE into the chosen model; do not full-repo scan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
