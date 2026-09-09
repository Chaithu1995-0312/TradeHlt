let meta = #{
    name: "claude-ritual",
    description: "Run one CLAUDE.md turn: Orient, Map, Classify, Execute, Validate, Drift, Log. Trigger-routed. Grants no new authority.",
    when_to_use: "Any Tradelatest turn that must follow CLAUDE.md: Orient, Continue, Next step, Validate, Implement, Map, Audit, Plan, Log, Compile.",
    phases: [
        #{ title: "Orient", detail: "subsystem + memory doc + ORIENT_RUNTIME" },
        #{ title: "Map", detail: "landing layer, callers, flow citation" },
        #{ title: "Classify", detail: "construction protocol + task class; STOP on UNKNOWN" },
        #{ title: "Execute", detail: "trigger-specific work; write only when authorized" },
        #{ title: "Validate", detail: "pytest + Five Questions; read-only" },
        #{ title: "Drift", detail: "documentation-truth decision" },
        #{ title: "Log", detail: "SESSION LOG ENTRY to assistant_project.md" },
    ],
};

let orient_schema = #{
    "type": "object",
    "required": ["in_scope", "domain", "memory_doc", "active_version", "orient_runtime_ran", "schema_mismatch", "stop_reason"],
    "properties": #{
        "in_scope": #{ "type": "string" },
        "domain": #{ "type": "string" },
        "memory_doc": #{ "type": "string" },
        "active_version": #{ "type": "string" },
        "orient_runtime_ran": #{ "type": "boolean" },
        "schema_mismatch": #{ "type": "boolean" },
        "recent_log_conflict": #{ "type": "string" },
        "stop_reason": #{ "type": "string" },
        "companion_docs": #{ "type": "array", "items": #{ "type": "string" } },
    },
};

let map_schema = #{
    "type": "object",
    "required": ["landing_layer", "flow_citation", "new_abstraction"],
    "properties": #{
        "landing_layer": #{ "type": "string" },
        "callers": #{ "type": "array", "items": #{ "type": "string" } },
        "dependents": #{ "type": "array", "items": #{ "type": "string" } },
        "flow_citation": #{ "type": "string" },
        "new_abstraction": #{ "type": "boolean" },
        "convention_conflict": #{ "type": "string" },
        "notes": #{ "type": "string" },
    },
};

let classify_schema = #{
    "type": "object",
    "required": ["task_class", "change_contract", "blocking_unknown", "needs_user_approval", "formula_math", "writes_repo"],
    "properties": #{
        "task_class": #{ "type": "string" },
        "change_contract": #{ "type": "string" },
        "blocking_unknown": #{ "type": "boolean" },
        "needs_user_approval": #{ "type": "boolean" },
        "approval_reason": #{ "type": "string" },
        "formula_math": #{ "type": "boolean" },
        "writes_repo": #{ "type": "boolean" },
        "production_behavior": #{ "type": "boolean" },
        "notes": #{ "type": "string" },
    },
};

let execute_schema = #{
    "type": "object",
    "required": ["status", "summary"],
    "properties": #{
        "status": #{ "type": "string" },
        "summary": #{ "type": "string" },
        "files_touched": #{ "type": "array", "items": #{ "type": "string" } },
        "tests_run": #{ "type": "string" },
        "blocked_reason": #{ "type": "string" },
        "unknown_tags": #{ "type": "string" },
        "handoff_required": #{ "type": "boolean" },
    },
};

let validate_schema = #{
    "type": "object",
    "required": ["passed", "summary", "five_questions"],
    "properties": #{
        "passed": #{ "type": "boolean" },
        "summary": #{ "type": "string" },
        "tests_run": #{ "type": "string" },
        "five_questions": #{ "type": "string" },
        "determinism_check": #{ "type": "string" },
        "blocked_reason": #{ "type": "string" },
    },
};

let drift_schema = #{
    "type": "object",
    "required": ["drift_class", "log_file"],
    "properties": #{
        "drift_class": #{ "type": "string" },
        "findings_action": #{ "type": "string" },
        "topic_sync": #{ "type": "boolean" },
        "citation_sync": #{ "type": "boolean" },
        "truth_conflict": #{ "type": "string" },
        "log_file": #{ "type": "string" },
        "notes": #{ "type": "string" },
    },
};

let log_schema = #{
    "type": "object",
    "required": ["appended", "log_file", "topic", "decision", "belief_update", "open_questions", "next_step"],
    "properties": #{
        "appended": #{ "type": "boolean" },
        "log_file": #{ "type": "string" },
        "topic": #{ "type": "string" },
        "decision": #{ "type": "string" },
        "belief_update": #{ "type": "string" },
        "open_questions": #{ "type": "string" },
        "next_step": #{ "type": "string" },
        "entry": #{ "type": "string" },
    },
};

fn nonempty(s) {
    if type_of(s) != "string" { return false; }
    let t = s;
    t.trim();
    t != ""
}

fn agent_ok(r) {
    r != () && r.success && r.output != ()
}

fn doctrine() {
    let d = "";
    d += "SOURCE OF RULES: CLAUDE.md only. Do not invent F-ids, FM-ids, SEM ids, or CC-* ids. ";
    d += "Source code always wins on conflict with docs. ";
    d += "Triggers are advisory orchestration and grant NO new authority: never bypass write-authority, path-guard, y/N confirm, or APPROVE promotion. ";
    d += "Evidence has no authority; only demonstrated G001 improvement grants production authority. ";
    d += "Information != value != authority != architecture. ";
    d += "Never read, print, or copy .env. ";
    d += "Never put production logic in scripts/. Never local formula math — ontology then registry then implementations. ";
    d += "No silent config defaults. No lookahead in backtests. Four engines are mandatory. ";
    d += "Never hand-edit GENERATED artifacts under data/*.jsonl. ";
    d += "If Semantic OS grounding is not GROUNDED, do not introduce the noun/join/symbol/finding — say the status. ";
    d += "Use tools (read_file, grep, run_terminal_command). Do not answer from memory. ";
    d += "A valid empty field requires you to have inspected the cited file first.\n";
    d
}

if args == () {
    pause("verification", "Pass args.trigger (orient|continue|next-step|next-plan|validate|implement|map|audit|plan|log|compile) and args.task.");
}

let trigger = args.trigger;
let task = args.task;
if trigger == () || !nonempty(trigger) {
    pause("verification", "Pass args.trigger: orient | continue | next-step | next-plan | validate | implement | map | audit | plan | log | compile.");
}
if task == () || !nonempty(task) {
    pause("verification", "Pass args.task — the user request this turn is serving.");
}

let ts = "UNSPECIFIED";
if args.timestamp != () && nonempty(args.timestamp) { ts = args.timestamp; }

let domain_hint = "";
if args.domain != () && nonempty(args.domain) { domain_hint = args.domain; }

let task_json = json_encode(task);
let trigger_json = json_encode(trigger);
let domain_json = json_encode(domain_hint);
let ts_json = json_encode(ts);

let do_orient = trigger != "log";
let do_map = trigger == "continue" || trigger == "next-step" || trigger == "next-plan" || trigger == "implement" || trigger == "map" || trigger == "plan" || trigger == "audit";
let do_classify = trigger == "continue" || trigger == "next-step" || trigger == "next-plan" || trigger == "implement" || trigger == "plan";
let do_execute = trigger == "continue" || trigger == "next-step" || trigger == "next-plan" || trigger == "implement" || trigger == "validate" || trigger == "audit" || trigger == "plan" || trigger == "compile" || trigger == "map";
let do_validate_gate = trigger == "continue" || trigger == "next-plan" || trigger == "implement" || trigger == "validate";
let do_drift = trigger == "implement" || trigger == "audit" || trigger == "next-step" || trigger == "continue";

let in_scope = "";
let domain_found = domain_hint;
let memory_doc = "";
let active_version = "";
let schema_mismatch = false;
let orient_stop = "";
let map_notes = "";
let task_class = "OBSERVATION_ONLY";
let writes_repo = false;
let blocking_unknown = false;
let needs_user_approval = false;
let approval_reason = "";
let formula_math = false;
let exec_status = "SKIPPED";
let exec_summary = "";
let files_touched = [];
let val_passed = true;
let val_summary = "not run";
let five_q = "";
let drift_class = "NOT_APPLICABLE";
let truth_conflict = "";
let log_file = "assistant_project.md";

// ---------------------------------------------------------------------------
phase("Orient");
if do_orient {
    let op = "";
    op += doctrine();
    op += "TRIGGER=" + trigger_json + " TASK=" + task_json + " DOMAIN_HINT=" + domain_json + " TIMESTAMP=" + ts_json + "\n";
    op += "You are the ORIENT agent (CLAUDE.md §0, §4.0, §7.1). Read-only. One-sentence scope. No fluff.\n";
    op += "STEPS (use tools; inspect files; do not guess):\n";
    op += "1. Identify the subsystem for TASK. Domain table (CLAUDE.md §0): ";
    op += "agent -> docs/memory/agent-memory.md; runtime/backtest/live -> docs/memory/runtime-memory.md; ";
    op += "features/schema/pipeline -> docs/memory/feature-memory.md; engines/scoring -> docs/memory/engine-memory.md; ";
    op += "governance/promotion -> docs/memory/governance-memory.md; cross-cutting architecture -> docs/memory/architecture-memory.md. ";
    op += "Load ONLY that memory doc. Follow its Reading order into source. Do not load all companions.\n";
    op += "2. ORIENT_RUNTIME is mandatory before planning, backtest, promotion, forensic, or config reasoning ";
    op += "(CLAUDE.md §4.0): (A) read configs/production/ACTIVE_VERSION; (B) load that config; ";
    op += "(C) verify keys exist in CRTConfig / ConfigBuilder; (D) record ACTIVE_VERSION; (E) only then plan. ";
    op += "If the config carries keys absent from CRTConfig, set schema_mismatch=true, stop_reason='schema/version mismatch', do NOT migrate or execute. ";
    op += "Runtime truth precedence: Tier0 ACTIVE_VERSION > Tier1 in-code schema > Tier2 promotion_log.jsonl > Tier3 session log/findings > Tier4 LLM memory.\n";
    op += "3. Read the end of assistant_project.md. Do not reopen a resolved thread (CLAUDE.md §3.4 item 7).\n";
    op += "4. Companion docs (CLAUDE.md §2) — name only those the TASK actually touches. Do not dump architecture.\n";
    op += "5. domain must be one of: agent, runtime, features, engines, governance, architecture, unknown.\n";
    op += "OUTPUT: in_scope = one sentence. stop_reason empty string if OK. recent_log_conflict empty if none.\n";
    let o = agent(op, #{
        label: "orient",
        capability_mode: "read-only",
        output_schema: orient_schema,
    });
    if agent_ok(o) {
        if o.output.in_scope != () { in_scope = o.output.in_scope; }
        if o.output.domain != () { domain_found = o.output.domain; }
        if o.output.memory_doc != () { memory_doc = o.output.memory_doc; }
        if o.output.active_version != () { active_version = o.output.active_version; }
        if o.output.schema_mismatch == true { schema_mismatch = true; }
        if o.output.stop_reason != () { orient_stop = o.output.stop_reason; }
        log("ORIENT domain=" + domain_found + " ACTIVE_VERSION=" + active_version);
    } else {
        orient_stop = "ORIENT agent failed; fail-closed.";
        log("ORIENT failed");
    }
}

if schema_mismatch || nonempty(orient_stop) {
    log("STOP after Orient: " + orient_stop);
}

// ---------------------------------------------------------------------------
phase("Map");
if do_map && !schema_mismatch && !nonempty(orient_stop) {
    let base = "";
    base += doctrine();
    base += "TRIGGER=" + trigger_json + " TASK=" + task_json + " IN_SCOPE=" + json_encode(in_scope) + " DOMAIN=" + json_encode(domain_found) + "\n";
    base += "You are a MAP agent (CLAUDE.md §7.2, §10, §12 Map). Read-only. Locate where the change lands. Cite graph.dot nodes as ModuleA -> FunctionB -> ClassC.\n";

    let p_spine = base;
    p_spine += "SPINE MAP. Read docs/architecture/signal-flow.md and src/core/engine_runner.py. ";
    p_spine += "Report landing_layer, callers, dependents, flow_citation (EngineRunner -> ... form), new_abstraction (true only if TASK invents a new pattern not in conventions), convention_conflict.\n";

    let p_conv = base;
    p_conv += "CONVENTION MAP. Read docs/reference/conventions.md and docs/reference/example-service.py. ";
    p_conv += "Flag magic numbers, skipped gates, partial fusion, lookahead, stringly-typed enums, API-wrapper around stdlib HTTP, production logic in scripts/. ";
    p_conv += "landing_layer = the folder CLAUDE.md §3.1 would pick. new_abstraction=true only if TASK invents a pattern not already there.\n";

    let p_log = base;
    p_log += "SESSION-LOG MAP. Read the end of assistant_project.md. ";
    p_log += "landing_layer='session-log'. flow_citation = any prior entry that already decided this TASK. ";
    p_log += "If a resolved thread would be reopened, put that in convention_conflict and notes. new_abstraction=false.\n";

    let maps = parallel([
        #{ prompt: p_spine, label: "map-spine", capability_mode: "read-only", output_schema: map_schema },
        #{ prompt: p_conv, label: "map-conventions", capability_mode: "read-only", output_schema: map_schema },
        #{ prompt: p_log, label: "map-session-log", capability_mode: "read-only", output_schema: map_schema },
    ]);
    let mi = 0;
    for m in maps {
        if agent_ok(m) {
            if nonempty(m.output.flow_citation) { map_notes += m.output.flow_citation + " | "; }
            if nonempty(m.output.convention_conflict) { map_notes += "CONFLICT:" + m.output.convention_conflict + " | "; }
            if m.output.notes != () && nonempty(m.output.notes) { map_notes += m.output.notes + " | "; }
        }
        mi += 1;
    }
    log("MAP notes length=" + map_notes.len().to_string());
}

// ---------------------------------------------------------------------------
phase("Classify");
if do_classify && !schema_mismatch && !nonempty(orient_stop) {
    let cp = "";
    cp += doctrine();
    cp += "TRIGGER=" + trigger_json + " TASK=" + task_json + " IN_SCOPE=" + json_encode(in_scope) + " MAP=" + json_encode(map_notes) + "\n";
    cp += "You are the CLASSIFY agent (CLAUDE.md §3.3b Construction Protocol + TASK_CLASSIFICATION_BEHAVIOR_POLICY).\n";
    cp += "Read docs/governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md and docs/governance/change_contracts.json. Use tools.\n";
    cp += "Classify TASK against change_contracts.json. blocking_unknown=true if the change contract is UNKNOWN — that is STOP.\n";
    cp += "task_class must be exactly one of: OBSERVATION_ONLY, BEHAVIOR_CHANGE_AUTHORIZED, EXPLORATORY_RESEARCH, UNKNOWN.\n";
    cp += "writes_repo=true if this trigger will edit the repository. formula_math=true if TASK introduces a quantity — then ontology -> registry -> implementations, never local formula math.\n";
    cp += "needs_user_approval=true for AMBIGUOUS/split-brain, any change that downgrades/reverses a finding, or edits to an active config / ACTIVE_VERSION (CLAUDE.md §6.2 gate calibration).\n";
    cp += "production_behavior=true if ACTIVE_VERSION behavior would change.\n";
    cp += "Do not implement. Do not edit. Classification only.\n";
    let c = agent(cp, #{
        label: "classify",
        capability_mode: "read-only",
        output_schema: classify_schema,
    });
    if agent_ok(c) {
        if c.output.task_class != () { task_class = c.output.task_class; }
        if c.output.blocking_unknown == true { blocking_unknown = true; }
        if c.output.needs_user_approval == true { needs_user_approval = true; }
        if c.output.approval_reason != () { approval_reason = c.output.approval_reason; }
        if c.output.formula_math == true { formula_math = true; }
        if c.output.writes_repo == true { writes_repo = true; }
        log("CLASSIFY class=" + task_class + " unknown=" + blocking_unknown.to_string() + " approval=" + needs_user_approval.to_string());
    } else {
        blocking_unknown = true;
        task_class = "UNKNOWN";
        log("CLASSIFY failed; fail-closed UNKNOWN");
    }
}

if blocking_unknown {
    log("STOP: construction protocol blocking UNKNOWN");
}

if needs_user_approval && !blocking_unknown && !schema_mismatch {
    await_user("user", "CLAUDE.md §6.2 requires user approval before continuing. Reason: " + approval_reason + " Task class: " + task_class + ". Resume to authorize, or stop.");
}

// ---------------------------------------------------------------------------
phase("Execute");
let skip_execute = schema_mismatch || nonempty(orient_stop) || blocking_unknown;
if do_execute && !skip_execute {
    let write_ok = trigger == "implement" || trigger == "continue" || trigger == "next-step" || trigger == "next-plan" || trigger == "audit" || trigger == "plan" || trigger == "compile";
    let cap = "read-only";
    if write_ok && writes_repo { cap = "all"; }
    if trigger == "audit" { cap = "read-write"; }
    if trigger == "plan" { cap = "read-write"; }
    if trigger == "compile" { cap = "execute"; }
    if trigger == "validate" || trigger == "map" { cap = "read-only"; }

    let ep = "";
    ep += doctrine();
    ep += "TRIGGER=" + trigger_json + " TASK=" + task_json + " CLASS=" + json_encode(task_class) + "\n";
    ep += "IN_SCOPE=" + json_encode(in_scope) + " MEMORY_DOC=" + json_encode(memory_doc) + " ACTIVE_VERSION=" + json_encode(active_version) + "\n";
    ep += "MAP=" + json_encode(map_notes) + " FORMULA_MATH=" + formula_math.to_string() + "\n";
    ep += "You are the EXECUTE agent (CLAUDE.md §7.3, §12, §3). Be concrete. Cite real paths, classes, signatures. Minimal diffs. Follow existing patterns; if a pattern is not in conventions.md or example-service.py, do not invent — set status=BLOCKED and say so.\n";
    ep += "Before touching code, the §3.4 checklist is: CLAUDE.md, the active production config, docs/reference/architecture.md §3, src/core/engine_runner.py, src/config_layer/config_validator.py, src/governance/promotion_manager.py, assistant_project.md, graph.dot if present.\n";
    ep += "TRIGGER LAW:\n";
    ep += "- orient/map/validate: read-only. Produce the report. Do not edit.\n";
    ep += "- continue: resume active work from latest docs/implementation_plan/*.md + SESSION LOG. Then the next discrete step.\n";
    ep += "- next-step: one discrete step inside the current milestone only.\n";
    ep += "- next-plan: do not jump ahead; leave Validate to the Validate phase, then draft/enter the next milestone plan under docs/implementation_plan/.\n";
    ep += "- implement: surgical additive code per CLAUDE.md §3. Copy example-service.py structure for new modules. New scripts must SITS-register the same turn. New tunables go in production config with _require(); then python scripts/maintenance/_compute_hash.py if params change. Wire into orchestrator. Write pytest (APPROVE path, hard-failure branches, circuit-breaker open, optional-dep absent). After writes, the Validate phase runs — do not skip it.\n";
    ep += "- audit: re-verify architecture doc file:line citations vs code; additive doc-only fixes. Do not edit production code, active config, production tests, or xfails.\n";
    ep += "- plan: write docs/implementation_plan/ ; do not implement.\n";
    ep += "- compile: run python scripts/context/build_context.py. context/*.md are generated derived views; never hand-edit them.\n";
    ep += "- validate: do not change code; gather what Validate must run.\n";
    ep += "If TASK touches multi_llm/ or build_queue.jsonl, set handoff_required=true (CLAUDE.md §13.7).\n";
    ep += "status must be one of: DONE, BLOCKED, UNKNOWN, NEEDS_REVISION. If unsure, write UNKNOWN in unknown_tags — never invent.\n";
    ep += "Construction: python scripts/governance/construction_protocol.py validate-completion <manifest> after a classified modification. One-command floor: construction_protocol.py check.\n";
    if trigger == "audit" || trigger == "implement" || trigger == "plan" {
        ep += "Semantic review close (if you judge meaning): exactly one of CONFIRMED DEFECT, INTENTIONAL SEMANTIC SEPARATION, STALE / LEGACY ARTIFACT, COMPATIBILITY ARTIFACT, DEFENSE-IN-DEPTH OPPORTUNITY, TEST / CONTRACT GAP, DOCUMENTATION GAP, DORMANT BUT VALID, INSUFFICIENT EVIDENCE, USER AUTHORIZATION REQUIRED. different != wrong. Do not silently remediate during review.\n";
    }
    let e = agent(ep, #{
        label: "execute:" + trigger,
        capability_mode: cap,
        output_schema: execute_schema,
    });
    if agent_ok(e) {
        if e.output.status != () { exec_status = e.output.status; }
        if e.output.summary != () { exec_summary = e.output.summary; }
        if e.output.files_touched != () { files_touched = e.output.files_touched; }
        if e.output.blocked_reason != () && nonempty(e.output.blocked_reason) {
            log("EXECUTE blocked: " + e.output.blocked_reason);
        }
        log("EXECUTE status=" + exec_status);
    } else {
        exec_status = "BLOCKED";
        exec_summary = "EXECUTE agent failed; fail-closed.";
        log("EXECUTE failed");
    }
}

// ---------------------------------------------------------------------------
phase("Validate");
if do_validate_gate && !skip_execute && exec_status != "BLOCKED" {
    let vp = "";
    vp += doctrine();
    vp += "TRIGGER=" + trigger_json + " TASK=" + task_json + " EXECUTE_STATUS=" + json_encode(exec_status) + " EXECUTE_SUMMARY=" + json_encode(exec_summary) + " FILES=" + json_encode(files_touched) + "\n";
    vp += "You are the VALIDATE agent (CLAUDE.md §12 Validate). READ-ONLY. Do not edit the repo.\n";
    vp += "Run the verification gate: pytest per docs/reference/testing.md (scope to tests this TASK actually touches; do not invent a full-suite requirement if a focused file is named), plus determinism/replay check if the TASK claims byte-identity, plus the Five Governance Questions from docs/architecture/goal.md.\n";
    vp += "Read docs/architecture/goal.md for the five questions and 8 invariants (invariant 8 = RECOMPUTE != RECOVER). Score the change. Do not grant production authority.\n";
    vp += "passed=true only with command evidence you ran. If you could not run tests, passed=false and blocked_reason says why.\n";
    vp += "five_questions = short answers, not a skip.\n";
    let v = agent(vp, #{
        label: "validate",
        capability_mode: "read-only",
        output_schema: validate_schema,
    });
    if agent_ok(v) {
        if v.output.passed == false { val_passed = false; }
        if v.output.summary != () { val_summary = v.output.summary; }
        if v.output.five_questions != () { five_q = v.output.five_questions; }
        log("VALIDATE passed=" + val_passed.to_string());
    } else {
        val_passed = false;
        val_summary = "VALIDATE agent failed; fail-closed.";
        log("VALIDATE failed");
    }
}

if do_validate_gate && exec_status != "BLOCKED" && !val_passed {
    log("Validate did not pass; Drift still runs if writes occurred, then Log.");
}

// ---------------------------------------------------------------------------
phase("Drift");
if do_drift && !skip_execute && writes_repo {
    let dp = "";
    dp += doctrine();
    dp += "TRIGGER=" + trigger_json + " TASK=" + task_json + " FILES=" + json_encode(files_touched) + " VALIDATE=" + json_encode(val_summary) + "\n";
    dp += "You are the DRIFT agent (CLAUDE.md §6.2 / §6.3 / §6.4). Every code/config/runtime-truth change triggers a documentation-truth decision. Reporting a discrepancy is not sufficient.\n";
    dp += "5 steps: classify (ALIGNED / DOC_DRIFT / CODE_DRIFT / AMBIGUOUS) -> present impact -> gate -> synchronize -> audit-trail.\n";
    dp += "Auto-fix unambiguous DOC_DRIFT/CODE_DRIFT that changes no registered conclusion. Require user approval (do not apply) for AMBIGUOUS, finding downgrade/reversal, or ACTIVE_VERSION edits — put that in truth_conflict.\n";
    dp += "Existing-doc-first. Never delete truth; mark SUPERSEDED / INVALIDATED_BY / BRANCH_SPECIFIC.\n";
    dp += "If you validated or overturned a conclusion, findings_action describes the same-turn edit to docs/current-findings.md (add/flip; never delete). Run the E-001 six questions before any finding. Mandatory phrase if you overclaimed: Caught me overclaiming; I owe you a correction. Correction = fix the SOURCE, not just chat.\n";
    dp += "Citation sync: path:line Symbol moves update docs the same turn (tests/test_doc_citations.py).\n";
    dp += "Topic sync: update only the one docs/topics/ file the code belongs to; bump Updated:; append Discussion.\n";
    dp += "log_file: assistant_project.md for codebase/research; llm_project_assistant.md for multi-LLM workflow-only; primary + one-line cross-link if both. Never duplicate full entries.\n";
    dp += "drift_class exactly one of: ALIGNED, DOC_DRIFT, CODE_DRIFT, AMBIGUOUS, NOT_APPLICABLE.\n";
    dp += "If AMBIGUOUS, do not silently resolve — fill truth_conflict as TruthConflict (source A, source B, evidence, impact, recommendation).\n";
    let dcap = "read-write";
    if trigger == "continue" && !writes_repo { dcap = "read-only"; }
    let d = agent(dp, #{
        label: "drift",
        capability_mode: dcap,
        output_schema: drift_schema,
    });
    if agent_ok(d) {
        if d.output.drift_class != () { drift_class = d.output.drift_class; }
        if d.output.truth_conflict != () { truth_conflict = d.output.truth_conflict; }
        if d.output.log_file != () && nonempty(d.output.log_file) { log_file = d.output.log_file; }
        log("DRIFT class=" + drift_class);
    } else {
        drift_class = "AMBIGUOUS";
        truth_conflict = "Drift agent failed; treat as unresolved TruthConflict.";
        log("DRIFT failed; fail-closed AMBIGUOUS");
    }
}

if nonempty(truth_conflict) {
    await_user("user", "CLAUDE.md §6.2 TruthConflict — do not silently resolve. " + truth_conflict);
}

// ---------------------------------------------------------------------------
phase("Log");
let lp = "";
lp += doctrine();
lp += "TIMESTAMP=" + ts_json + " TRIGGER=" + trigger_json + " TASK=" + task_json + "\n";
lp += "IN_SCOPE=" + json_encode(in_scope) + " DOMAIN=" + json_encode(domain_found) + " ACTIVE_VERSION=" + json_encode(active_version) + "\n";
lp += "CLASS=" + json_encode(task_class) + " EXECUTE=" + json_encode(exec_status) + " / " + json_encode(exec_summary) + "\n";
lp += "VALIDATE_PASSED=" + val_passed.to_string() + " VALIDATE=" + json_encode(val_summary) + " FIVE_Q=" + json_encode(five_q) + "\n";
lp += "DRIFT=" + json_encode(drift_class) + " STOP=" + json_encode(orient_stop) + " UNKNOWN=" + blocking_unknown.to_string() + "\n";
lp += "You are the LOG agent (CLAUDE.md §6 + §7.4). Non-optional. Never defer. Do not skip for short replies.\n";
lp += "Append the EXACT block below to " + log_file + " at repo root (create the file if missing). Also return it in entry.\n";
lp += "Route: assistant_project.md = codebase/research (code, config, findings, backtests, tooling including multi_llm/ layer builds). ";
lp += "llm_project_assistant.md = workflow-only (handoff cycles, protocol/role/queue). Tie-breaker: governed code/config/findings -> assistant_project.md.\n";
lp += "Read the end of the target file and APPEND. Do not rewrite the file. Do not delete prior entries.\n";
lp += "Block format:\n";
lp += "---\n";
lp += "SESSION LOG ENTRY\n";
lp += "Date: {timestamp}\n";
lp += "Topic: {1-line summary}\n";
lp += "Decision/Output: {key content}\n";
lp += "Belief Update / ROI / Goal: {Goal: ... Belief: ... Knowledge ROI: ... Action: ...}  (or none if pure mechanics)\n";
lp += "Open Questions: {unresolved}\n";
lp += "Next Step: {what should happen next}\n";
lp += "---\n";
lp += "Use the literal header with the memo emoji if the file already uses it; otherwise match the existing file's SESSION LOG ENTRY header exactly.\n";
lp += "Belief Update operationalizes CLAUDE.md §6.1: Goal -> Belief -> ROI -> Action. Intelligence is an ROI-weighted belief change, not accumulated data.\n";
lp += "appended=true only after you actually wrote the file. next_step must be concrete.\n";

let l = agent(lp, #{
    label: "session-log",
    capability_mode: "read-write",
    output_schema: log_schema,
});

let appended = false;
let topic = "claude-ritual " + trigger;
let decision = exec_summary;
let belief = "none";
let open_q = "";
let next_step = "";
let entry = "";
if agent_ok(l) {
    if l.output.appended == true { appended = true; }
    if l.output.topic != () { topic = l.output.topic; }
    if l.output.decision != () { decision = l.output.decision; }
    if l.output.belief_update != () { belief = l.output.belief_update; }
    if l.output.open_questions != () { open_q = l.output.open_questions; }
    if l.output.next_step != () { next_step = l.output.next_step; }
    if l.output.entry != () { entry = l.output.entry; }
    if l.output.log_file != () && nonempty(l.output.log_file) { log_file = l.output.log_file; }
}

if !appended {
    log("SESSION LOG was not appended — ritual incomplete per CLAUDE.md §6.");
}

let report = "";
report += "# claude-ritual result\n\n";
report += "- trigger: " + trigger + "\n";
report += "- in_scope: " + in_scope + "\n";
report += "- domain: " + domain_found + "\n";
report += "- memory_doc: " + memory_doc + "\n";
report += "- ACTIVE_VERSION: " + active_version + "\n";
report += "- schema_mismatch: " + schema_mismatch.to_string() + "\n";
report += "- stop_reason: " + orient_stop + "\n";
report += "- task_class: " + task_class + "\n";
report += "- blocking_unknown: " + blocking_unknown.to_string() + "\n";
report += "- execute: " + exec_status + " — " + exec_summary + "\n";
report += "- validate_passed: " + val_passed.to_string() + " — " + val_summary + "\n";
report += "- drift_class: " + drift_class + "\n";
report += "- session_log_appended: " + appended.to_string() + " -> " + log_file + "\n";
report += "- next_step: " + next_step + "\n";
if nonempty(entry) {
    report += "\n## SESSION LOG ENTRY\n\n";
    report += entry;
    report += "\n";
}
let report_path = write_scratch_file("claude-ritual-report.md", report);

let final_status = "DONE";
if schema_mismatch || nonempty(orient_stop) || blocking_unknown { final_status = "BLOCKED"; }
if exec_status == "BLOCKED" || exec_status == "UNKNOWN" || exec_status == "NEEDS_REVISION" { final_status = exec_status; }
if do_validate_gate && !val_passed && final_status == "DONE" { final_status = "NEEDS_REVISION"; }
if !appended && final_status == "DONE" { final_status = "NEEDS_REVISION"; }

complete(#{
    status: final_status,
    trigger: trigger,
    in_scope: in_scope,
    domain: domain_found,
    active_version: active_version,
    task_class: task_class,
    execute: exec_status,
    validate_passed: val_passed,
    drift_class: drift_class,
    session_log_appended: appended,
    log_file: log_file,
    next_step: next_step,
    topic: topic,
    decision: decision,
    belief_update: belief,
    open_questions: open_q,
    report_path: report_path,
});
