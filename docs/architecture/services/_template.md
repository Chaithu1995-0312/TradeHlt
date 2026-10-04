# Service: <NAME>

> **Loadable context unit.** This doc is written so an LLM (or human) can understand
> this service — and safely change it — **without loading the rest of the codebase**.
> Keep it to ins → flow → outs. If you need more, link, don't inline.
>
> Status: <current monolith module(s) | extracted service>. Anchored to `<config version>`.

## Purpose
<One sentence. What this service is responsible for.>

## Inputs (what crosses the boundary inward)
- **Data:** <shapes / dataclasses / dict keys>
- **Config:** <which `get_prod_section` keys, injected how>
- **Contracts in:** <upstream events/calls it consumes>

## Internal flow (plain English)
<The happy path in 3–7 steps. Then the key branches / failure modes. Reference the
controlling `file:line` for each step. No code dumps.>

## Outputs (what crosses the boundary outward)
- **Data:** <return shape / dataclass>
- **Contracts out:** <events emitted, downstream calls>

## Events emitted
- <EventType → sink (JSONL path), with the payload fields that matter>

## Replay notes
- <Deterministic? Any seeds? Any wall-clock or lookahead risk? What must NOT change to
  keep runs comparable.>

## Upstream / downstream services
- **Upstream:** <who calls in>
- **Downstream:** <who it calls / emits to>

## Decomposition blockers (if any)
- <Tier 1–3 coupling that stops clean extraction, with file:line.>
