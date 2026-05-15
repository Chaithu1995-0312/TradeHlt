from __future__ import annotations

import json
import socket
import threading
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from src.control_plane.jobs import JobManager
from src.control_plane.registry import REPO_ROOT, command_spec_to_json, workflow_stage_order
from src.control_plane.dashboard_api import TradingDashboardAPI
from src.control_plane.report_api import RunReportAPI


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2).encode("utf-8")


class ControlPlaneAPI:
    def __init__(self, manager: JobManager) -> None:
        self.manager = manager

    def commands_payload(self) -> dict[str, Any]:
        commands = [command_spec_to_json(spec) for spec in self.manager.list_commands()]
        categories = sorted({cmd["category"] for cmd in commands})
        return {
            "commands": commands,
            "categories": categories,
            "workflow_stages": list(workflow_stage_order()),
        }

    def runs_payload(self, query: str = "") -> dict[str, Any]:
        runs = [self.manager.snapshot(run) for run in self.manager.list_runs(query=query)]
        return {"runs": runs}

    def create_run_payload(self, command_id: str, args: dict[str, Any]) -> dict[str, Any]:
        run = self.manager.create_run(command_id=command_id, user_args=args)
        return {"run": self.manager.snapshot(run)}

    def run_payload(self, run_id: str) -> dict[str, Any]:
        run = self.manager.get_run(run_id)
        if not run:
            raise KeyError(f"Run not found: {run_id}")
        return {"run": self.manager.snapshot(run)}

    def stop_payload(self, run_id: str) -> dict[str, Any]:
        run = self.manager.stop_run(run_id)
        return {"run": self.manager.snapshot(run)}

    def logs_payload(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "logs": self.manager.read_logs(run_id)}

    def artifacts_payload(self, run_id: str) -> dict[str, Any]:
        run = self.manager.get_run(run_id)
        if not run:
            raise KeyError(f"Run not found: {run_id}")
        artifacts: list[dict[str, Any]] = []
        for path in run.artifact_paths:
            p = Path(path)
            artifacts.append(
                {
                    "path": str(p),
                    "exists": p.exists(),
                    "size": p.stat().st_size if p.exists() and p.is_file() else None,
                }
            )
        return {"run_id": run_id, "artifacts": artifacts}

    def monitors_payload(self, run_id: str) -> dict[str, Any]:
        run = self.manager.get_run(run_id)
        if not run:
            raise KeyError(f"Run not found: {run_id}")
        fields = self.manager.live_monitors(run_id)
        return {
            "run_id": run_id,
            "command_id": run.command_id,
            "status": run.status,
            "fields": fields,
        }

    def dashboard_payload(self) -> dict[str, Any]:
        return {"commands": self.manager.dashboard_snapshot()}

    def files_payload(self, glob_pattern: str) -> dict[str, Any]:
        if not glob_pattern:
            return {"files": []}
        matches = sorted(
            p.relative_to(REPO_ROOT).as_posix()
            for p in REPO_ROOT.glob(glob_pattern)
            if p.is_file()
        )
        return {"files": matches}

    def monitor_history_payload(self, command_id: str, limit: int = 50) -> dict[str, Any]:
        return {
            "command_id": command_id,
            "history": self.manager.monitor_history(command_id, limit=limit),
        }

    def ui_html(self) -> str:
        return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CRT Control Plane</title>
  <style>
    :root{
      --bg:#0f1724;--panel:#122033;--line:#23364e;--text:#e6edf7;--muted:#9fb0c8;
      --accent:#0ea5a3;--warn:#f59e0b;--ok:#22c55e;--bad:#ef4444
    }
    .dash-link{font-size:13px;color:var(--accent);text-decoration:none;padding:5px 10px;border:1px solid var(--accent);border-radius:6px}
    .dash-link:hover{background:rgba(14,165,163,.12)}
    *{box-sizing:border-box}
    body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:linear-gradient(120deg,#0f1724,#1a2438);color:var(--text)}
    header{padding:14px 18px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;background:rgba(0,0,0,.18)}
    h1{font-size:18px;margin:0}
    .top-controls{display:flex;gap:8px;align-items:center}
    .wrap{display:grid;grid-template-columns:310px 380px 1fr;gap:14px;padding:14px;min-height:calc(100vh - 56px)}
    .panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
    .panel h2{font-size:14px;margin:0;padding:10px 12px;border-bottom:1px solid var(--line)}
    .body{padding:10px 12px}
    .small{font-size:12px;color:var(--muted)}
    .helper{border:1px dashed var(--line);border-radius:8px;padding:8px;margin-top:8px}
    .helper strong{display:block;font-size:12px;margin-bottom:4px}
    label{display:block;font-size:12px;color:var(--muted);margin-top:8px}
    input,select,textarea,button{width:100%;padding:8px 10px;border-radius:8px;border:1px solid var(--line);background:#0d1626;color:var(--text)}
    button{cursor:pointer;background:#0c3342;border-color:#15607d}
    button:hover{filter:brightness(1.12)}
    .grid2{display:grid;grid-template-columns:1fr 1fr;gap:8px}
    .status{font-size:12px;padding:2px 7px;border-radius:20px;border:1px solid}
    .st-running{color:var(--warn);border-color:var(--warn)}
    .st-succeeded{color:var(--ok);border-color:var(--ok)}
    .st-failed,.st-stopped{color:var(--bad);border-color:var(--bad)}
    .st-queued{color:var(--muted);border-color:var(--muted)}
    .hist{max-height:330px;overflow:auto}
    table{width:100%;border-collapse:collapse}
    th,td{border-bottom:1px solid var(--line);padding:6px 4px;font-size:12px;text-align:left}
    pre{background:#091121;border:1px solid var(--line);padding:8px;border-radius:8px;max-height:260px;overflow:auto;white-space:pre-wrap}
    .artifact{display:flex;justify-content:space-between;gap:8px;font-size:12px;padding:5px 0;border-bottom:1px dashed var(--line)}
    .stage{border:1px solid var(--line);border-radius:8px;padding:8px;margin-bottom:8px}
    .stage h3{font-size:13px;margin:0 0 6px 0}
    .stage-item{font-size:12px;margin:4px 0;padding:6px;background:#0f1b2e;border:1px solid var(--line);border-radius:6px}
    .stage-item .actions{display:flex;gap:6px;margin-top:5px}
    .chip{font-size:11px;border:1px solid var(--line);border-radius:16px;padding:1px 8px;color:var(--muted)}
    .completed{color:var(--ok);border-color:var(--ok)}
    #playbookPanel{max-height:calc(100vh - 120px);overflow:auto}
    #tourOverlay{position:fixed;inset:0;background:rgba(3,8,15,.64);display:none;z-index:999}
    #tourCard{position:fixed;right:20px;bottom:20px;width:380px;background:#0f1b2e;border:1px solid var(--line);border-radius:12px;padding:14px;z-index:1000;display:none}
    #tourCard h3{margin:0 0 6px 0;font-size:14px}
    #tourCard p{margin:0 0 8px 0;font-size:12px;color:var(--muted);line-height:1.5}
    #tourStage{display:inline-block;font-size:10px;padding:2px 8px;border-radius:12px;background:rgba(14,165,163,.15);color:var(--accent);border:1px solid var(--accent);margin-bottom:6px}
    #tourProgress{height:3px;background:var(--line);border-radius:3px;margin-bottom:8px}
    #tourProgressBar{height:100%;background:var(--accent);border-radius:3px;transition:width .3s}
    #tourLoadBtn{background:rgba(14,165,163,.12);border:1px solid var(--accent);color:var(--accent);font-size:11px;margin-bottom:8px;width:100%;padding:6px 10px;border-radius:8px;cursor:pointer}
    #tourLoadBtn:hover{background:rgba(14,165,163,.28)}
    .tour-nav{display:flex;gap:6px;align-items:center}
    #tourSkipBtn{font-size:10px;color:var(--muted);background:transparent;border:none;flex:0 0 auto;width:auto;padding:2px 4px;cursor:pointer;text-decoration:underline}
    .tour-target{outline:2px solid var(--accent);outline-offset:2px;border-radius:8px}
    .report-btn{font-size:10px;padding:2px 7px;width:auto;background:rgba(14,165,163,.10);border:1px solid var(--accent);color:var(--accent);border-radius:4px;cursor:pointer;white-space:nowrap}
    .report-btn:hover{background:rgba(14,165,163,.25)}
    #reportModal{display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:24px;width:560px;max-width:95vw;max-height:82vh;overflow-y:auto;z-index:201}
    #reportOverlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:200}
    #reportLlmOut{display:none;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:12px;font-size:12px;white-space:pre-wrap;line-height:1.55;max-height:340px;overflow-y:auto;margin-top:10px}
    @media (max-width: 1100px){
      .wrap{grid-template-columns:1fr}
      #playbookPanel{max-height:none}
    }
    .dash-card{border:1px solid var(--line);border-radius:10px;padding:10px;background:#0f1b2e}
    .dash-card h3{font-size:13px;margin:0 0 6px 0;display:flex;justify-content:space-between;align-items:center;gap:8px}
    .dash-empty{color:var(--muted);font-size:12px;padding:4px}
    .dash-field-err{color:var(--bad);font-size:11px}
    #monitorsTable{margin-top:4px}
    #monitorsTable td:last-child{font-family:monospace;color:var(--accent)}
  </style>
</head>
<body>
  <header>
    <h1>CRT Web Control Plane</h1>
    <div class="top-controls">
      <span class="small">Data Prep → Tuning → Validation/Promotion → Replay/Backtest → Live Runner</span>
      <button id="dashboardBtn" style="width:auto">Dashboard</button>
      <button id="helpBtn" style="width:auto">Help / Start Tour</button>
    </div>
  </header>
  <main class="wrap">
    <section class="panel" id="playbookPanel">
      <h2>Tutorial / Playbook</h2>
      <div class="body">
        <div class="small">Workflow checklist and command navigation.</div>
        <div id="playbookStages" style="margin-top:8px"></div>
      </div>
    </section>
    <section class="panel" id="launcherPanel">
      <h2>Command Launcher</h2>
      <div class="body">
        <label>Category</label>
        <select id="category"></select>
        <label>Command</label>
        <select id="command"></select>
        <div id="desc" class="small" style="margin-top:6px"></div>
        <div class="helper"><strong>When to run this</strong><div id="helperWhen" class="small"></div></div>
        <div class="helper"><strong>Minimum required fields</strong><div id="helperMinFields" class="small"></div></div>
        <div class="helper"><strong>What artifacts to check next</strong><div id="helperArtifacts" class="small"></div></div>
        <div id="formArea"></div>
        <label>Resolved CLI Preview</label>
        <pre id="preview"></pre>
        <div class="grid2">
          <button id="runBtn">Run Command</button>
          <button id="stopBtn">Stop Latest Run</button>
        </div>
      </div>
      <h2>Run History</h2>
      <div class="body" id="historyPanel">
        <input id="search" placeholder="Search by run id / command / args" />
        <div class="hist">
          <table>
            <thead><tr><th>Run</th><th>Command</th><th>Status</th><th>Report</th></tr></thead>
            <tbody id="history"></tbody>
          </table>
        </div>
      </div>
    </section>
    <section class="panel" id="inspectorPanel">
      <h2>Run Inspector</h2>
      <div class="body">
        <div id="runMeta" class="small"></div>
        <h3 style="font-size:13px;margin:8px 0">Monitored Fields</h3>
        <div id="monitorsHint" class="small"></div>
        <table id="monitorsTable" style="display:none">
          <thead><tr><th>Field</th><th>Value</th></tr></thead>
          <tbody id="monitorsBody"></tbody>
        </table>
        <h3 style="font-size:13px;margin:8px 0">Stdout</h3>
        <pre id="stdout"></pre>
        <h3 style="font-size:13px;margin:8px 0">Stderr</h3>
        <pre id="stderr"></pre>
        <h3 style="font-size:13px;margin:8px 0">Artifacts</h3>
        <div id="artifacts"></div>
      </div>
    </section>
  </main>

  <main class="wrap dashboard" id="dashboardWrap" style="display:none;grid-template-columns:1fr">
    <section class="panel">
      <h2>Monitoring Dashboard — latest per command</h2>
      <div class="body">
        <div class="small" style="margin-bottom:8px">Most recent run per monitored command. Auto-refreshes every 2 s for running jobs.</div>
        <div id="dashboardGrid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px"></div>
      </div>
    </section>
  </main>

  <div id="tourOverlay"></div>
  <div id="tourCard">
    <span id="tourStage"></span>
    <div id="tourProgress"><div id="tourProgressBar" style="width:0%"></div></div>
    <h3 id="tourTitle">Tour</h3>
    <p id="tourText"></p>
    <button id="tourLoadBtn" style="display:none">Load Command →</button>
    <div class="tour-nav">
      <button id="tourBackBtn" style="flex:1">← Back</button>
      <button id="tourNextBtn" style="flex:1">Next →</button>
      <button id="tourSkipBtn">skip</button>
    </div>
  </div>

  <!-- Run Report Modal -->
  <div id="reportOverlay" onclick="closeReport()"></div>
  <div id="reportModal">
    <h3 style="margin:0 0 14px;font-size:15px;color:var(--text)">📋 Run Report &mdash; <span id="reportRunId" style="font-family:monospace;color:var(--accent)"></span></h3>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <button id="reportExcelBtn" onclick="downloadExcel()">📊 Download Excel</button>
      <button id="reportLlmBtn" onclick="runLlmAnalysis()">🤖 LLM Analysis</button>
    </div>
    <div id="reportLlmOut"></div>
    <div style="text-align:right;margin-top:14px">
      <button onclick="closeReport()" style="background:transparent;border:1px solid var(--line);color:var(--muted);width:auto;padding:4px 14px">✕ Close</button>
    </div>
  </div>

  <script>
    let data={commands:[],categories:[],workflow_stages:[]};
    let latestRunId=null;
    let selectedRunId=null;
    let currentView="runs";
    let monitorsPollTimer=null;
    const el = (id)=>document.getElementById(id);
    const TUTORIAL_VERSION="v2";
    const LS_TUTORIAL_SEEN="tutorial_seen";
    const LS_TUTORIAL_DISMISSED="tutorial_dismissed_version";
    const LS_PLAYBOOK_COMPLETED="playbook_completed";
    const LS_TOUR_PROGRESS="tutorial_progress";

    const TOUR_STEPS = [
      { title:"Pipeline Overview", stage:"", commandId:null, target:"#playbookPanel",
        text:"CRT Control Plane orchestrates 5 stages: Data Prep → Tuning → Validation & Promotion → Replay & Backtest → Live Runner. The Playbook panel (left) tracks your progress through each stage." },
      { title:"Prepare Data", stage:"Data Prep", commandId:"data.prepare_data", target:"#launcherPanel",
        text:"Download and validate M15 OHLCV CSVs per instrument. Run this first before any tuning. Output: data/*.csv" },
      { title:"Build Dataset", stage:"Data Prep", commandId:"data.unified_data_builder", target:"#formArea",
        text:"Merges multi-instrument CSVs and applies feature engineering. Output feeds the tuner. Run after Prepare Data." },
      { title:"Tune Parameters", stage:"Tuning", commandId:"tuning.auto_tuner_multi", target:"#formArea",
        text:"Searches the parameter space across all instruments. Output: results/tuner/checkpoint_multi.json — required input for Promotion Manager." },
      { title:"Validate Config", stage:"Validation & Promotion", commandId:"validation.config_validator", target:"#formArea",
        text:"Hard gates: min 10 trades, max 35% drawdown, min fitness 0.15. Soft gates: win rate, expectancy, cross-instrument variance. Returns a ValidationReport — required for promotion." },
      { title:"Promote Config", stage:"Validation & Promotion", commandId:"promotion.manager", target:"#formArea",
        text:"The only path to production. Requires an approved ValidationReport. SHA-256 hashes the config, appends to promotion_log.jsonl, archives the previous version." },
      { title:"Governance", stage:"Validation & Promotion", commandId:"governance.orchestrator", target:"#formArea",
        text:"LLM-driven reflection on live logs after promotion. Detects drift, flags anomalies, suggests hyperparameter tuning. Use --compressed-summary for faster processing." },
      { title:"Capture Baseline", stage:"Replay & Backtest", commandId:"baseline.capture", target:"#formArea",
        text:"Snapshot current state: schema hash, model registry, config SHA-256, validation metrics. Label with --label so you can compare before/after a promotion." },
      { title:"Backtest v2", stage:"Replay & Backtest", commandId:"backtest.v2", target:"#formArea",
        text:"Full CRT backtest candle-by-candle through 4 engines (CRT → Gaussian → Zone Gate → RR). Gaussian scorer loads dynamically from active model registry. No lookahead — deterministic." },
      { title:"BitNet Gate", stage:"Replay & Backtest", commandId:"backtest.bitnet", target:"#formArea",
        text:"BitNet 3B gate overlay. Runs a 3-bit quantised LLM as a tie-breaker filter on top of the 4-engine fusion score. Test gate behaviour before live deployment." },
      { title:"Unified Replay", stage:"Replay & Backtest", commandId:"replay.unified", target:"#formArea",
        text:"Replay a historical run with the current config on identical data. Compare before/after a promotion without running a full new backtest." },
      { title:"Go Live", stage:"Live Runner", commandId:"live.inout_runner", target:"#formArea",
        text:"INOUT Live Runner connects to the live feed. Start only after Config Validator → Promotion → Baseline check all pass. Monitor stdout/stderr live in the Inspector." },
      { title:"Trading Dashboard", stage:"", commandId:null, target:"#dashboardBtn",
        text:"Click Dashboard for the live trading view: active model health, kill switch, 24h trade count, opportunity win rates by session, equity curve, and calibration history." }
    ];
    let tourIndex=0;

    function getCompletedState(){
      try { return JSON.parse(localStorage.getItem(LS_PLAYBOOK_COMPLETED) || "{}"); }
      catch(_) { return {}; }
    }
    function setCompletedState(state){
      localStorage.setItem(LS_PLAYBOOK_COMPLETED, JSON.stringify(state));
    }
    function setCompleted(commandId, value){
      const state=getCompletedState();
      state[commandId]=!!value;
      setCompletedState(state);
      renderPlaybook();
    }

    function groupByCategory(category){
      return data.commands.filter(c=>c.category===category);
    }
    function statusClass(status){
      return "status st-"+status;
    }
    function validateArg(id, minVal, maxVal){
      const node=el(id);
      const errNode=el("err_"+id);
      if(!node||!errNode){return true;}
      if(node.value.trim()===""){errNode.style.display="none";node.style.borderColor="";return true;}
      const v=parseFloat(node.value);
      if(isNaN(v)){
        errNode.textContent="Must be a number";errNode.style.display="";
        node.style.borderColor="var(--bad)";return false;
      }
      if(minVal!==null&&minVal!==undefined&&v<minVal){
        errNode.textContent=`Min: ${minVal}`;errNode.style.display="";
        node.style.borderColor="var(--bad)";return false;
      }
      if(maxVal!==null&&maxVal!==undefined&&v>maxVal){
        errNode.textContent=`Max: ${maxVal}`;errNode.style.display="";
        node.style.borderColor="var(--bad)";return false;
      }
      errNode.style.display="none";node.style.borderColor="";return true;
    }

    function inferInstrument(filePath){
      if(!filePath){return "";}
      const base=filePath.split("/").pop().replace(/[.]csv$/i,"");
      const parts=base.split("_");
      return parts[0]||"";
    }

    function onFilePickerChange(selectId, instrumentArgKey){
      const sel=el(selectId);
      if(!sel){return;}
      const instr=el("arg_"+instrumentArgKey);
      if(instr){
        const inferred=inferInstrument(sel.value).toUpperCase();
        if(inferred) instr.value=inferred;
      }
      updatePreview();
    }

    async function populateFilePicker(id, glob){
      const sel=el(id);
      if(!sel){return;}
      try{
        const resp=await fetch(`/files?glob=${encodeURIComponent(glob)}`);
        const payload=await resp.json();
        const files=payload.files||[];
        const placeholder=sel.getAttribute("data-required")==="true"?
          `<option value="">— select a file —</option>`:
          `<option value="">— none (use data_dir) —</option>`;
        sel.innerHTML=placeholder+files.map(f=>`<option value="${f}">${f}</option>`).join("");
      }catch(_){
        sel.innerHTML=`<option value="">Error loading files</option>`;
      }
      sel.dispatchEvent(new Event("change"));
    }

    function argInputHtml(arg){
      const id="arg_"+arg.key;
      const reqMark=arg.required?` <span style="color:var(--bad)">*</span>`:"";
      const helpHtml=arg.help?`<div class="small" style="color:var(--muted);margin-top:2px">${arg.help}</div>`:"";
      let inner;
      if(arg.kind==="bool"){
        inner=`<label><input id="${id}" type="checkbox" ${arg.default?"checked":""}/> ${arg.key}</label>${helpHtml}`;
      } else if(arg.kind==="choice"){
        const opts=(arg.choices||[]).map(c=>`<option value="${c}" ${arg.default===c?"selected":""}>${c}</option>`).join("");
        inner=`<label>${arg.key}${reqMark}</label><select id="${id}">${opts}</select>${helpHtml}`;
      } else if(arg.kind==="file"){
        const glob=arg.file_glob||"data/*.csv";
        inner=`<label>${arg.key}${reqMark}</label><select id="${id}" data-glob="${glob}" data-required="${arg.required}"><option value="">Loading...</option></select>${helpHtml}`;
      } else if(arg.kind==="file-multi"){
        const glob=arg.file_glob||"logs/*.jsonl";
        inner=`<label>${arg.key}${reqMark}</label><select id="${id}" multiple size="5" data-glob="${glob}" data-kind="file-multi" style="height:auto;min-height:90px;padding:4px;border-radius:6px"><option value="" disabled>Loading…</option></select><div class="small" style="color:var(--muted);margin-top:3px">Hold Ctrl / ⌘ to select multiple files</div>${helpHtml}`;
      } else {
        let val=(arg.default===null||arg.default===undefined)?"":String(arg.default);
        if(!val&&arg.auto_default==="date_version"){
          const _d=new Date();
          val=`v5_auto_${_d.getFullYear()}_${String(_d.getMonth()+1).padStart(2,"0")}`;
        }
        if(arg.kind==="int"||arg.kind==="float"){
          const minAttr=(arg.min_val!==null&&arg.min_val!==undefined)?` min="${arg.min_val}"`:"";
          const maxAttr=(arg.max_val!==null&&arg.max_val!==undefined)?` max="${arg.max_val}"`:"";
          const stepAttr=arg.kind==="float"?` step="any"`:` step="1"`;
          const placeholder=(arg.min_val!==null&&arg.min_val!==undefined&&arg.max_val!==null&&arg.max_val!==undefined)?`${arg.min_val} – ${arg.max_val}`:"";
          const oninput=`oninput="validateArg('${id}',${arg.min_val===null||arg.min_val===undefined?'null':arg.min_val},${arg.max_val===null||arg.max_val===undefined?'null':arg.max_val})"`;
          inner=`<label>${arg.key}${reqMark}</label><input id="${id}" type="number" value="${val}"${minAttr}${maxAttr}${stepAttr} placeholder="${placeholder}" ${oninput} />${helpHtml}<div id="err_${id}" class="small" style="color:var(--bad);display:none"></div>`;
        } else {
          inner=`<label>${arg.key}${reqMark}</label><input id="${id}" type="text" value="${val}" placeholder="${arg.kind==='list'?'comma,separated,values':''}" />${helpHtml}`;
        }
      }
      return `<div id="wrapper_arg_${arg.key}">${inner}</div>`;
    }

    function selectedCommand(){
      const id=el("command").value;
      return data.commands.find(c=>c.id===id);
    }
    function selectCommandById(commandId){
      const cmd=data.commands.find(c=>c.id===commandId);
      if(!cmd){return;}
      el("category").value=cmd.category;
      const cmds=groupByCategory(cmd.category);
      el("command").innerHTML=cmds.map(c=>`<option value="${c.id}">${c.title}</option>`).join("");
      el("command").value=commandId;
      renderForm(cmd);
    }

    function renderHelpers(cmd){
      const notes=(cmd.quickstart_notes||[]);
      el("helperWhen").textContent = notes.length ? notes[0] : "No quickstart note available.";
      const required = (cmd.args_schema||[]).filter(a=>a.required).map(a=>a.flag?`${a.flag}`:a.key);
      el("helperMinFields").textContent = required.length ? required.join(", ") : "No mandatory flags for default command mode.";
      const art=(cmd.artifacts||[]);
      el("helperArtifacts").textContent = art.length ? art.join(", ") : "No explicit artifact pattern declared.";
    }

    function renderForm(cmd){
      el("desc").textContent=cmd.description;
      renderHelpers(cmd);
      const html=(cmd.args_schema||[]).map(arg=>argInputHtml(arg)).join("");
      el("formArea").innerHTML=html;
      // Find sibling instrument arg key (if any) relative to each file picker
      const instrArg=(cmd.args_schema||[]).find(a=>a.key==="instrument");
      const instrKey=instrArg?instrArg.key:null;
      const hasFilePicker=(cmd.args_schema||[]).some(a=>a.kind==="file");
      // Make instrument INPUT read-only when a file picker drives it (leave SELECT dropdowns interactive)
      if(hasFilePicker&&instrKey){
        const instrEl=el("arg_"+instrKey);
        if(instrEl&&instrEl.tagName==="INPUT"){instrEl.readOnly=true;instrEl.style.opacity="0.7";instrEl.title="Auto-filled from CSV selection";}
      }
      (cmd.args_schema||[]).forEach(arg=>{
        if(arg.kind==="file"){
          const selEl=el("arg_"+arg.key);
          if(!selEl){return;}
          // Wire instrument auto-fill on change
          if(instrKey){
            selEl.onchange=()=>onFilePickerChange("arg_"+arg.key, instrKey);
          } else {
            selEl.onchange=updatePreview;
          }
          // Populate options from server
          populateFilePicker("arg_"+arg.key, arg.file_glob||"data/*.csv");
        }
      });
      // Populate file-multi pickers
      (cmd.args_schema||[]).forEach(arg=>{
        if(arg.kind==="file-multi"){
          populateFilePicker("arg_"+arg.key, arg.file_glob||"logs/*.jsonl");
          const sel=el("arg_"+arg.key);
          if(sel) sel.addEventListener("change", updatePreview);
        }
      });
      // compress_logs: auto-derive output path from selected log file
      const logsArgDef=(cmd.args_schema||[]).find(a=>a.key==="logs"&&a.kind==="file-multi");
      const outArgDef=(cmd.args_schema||[]).find(a=>a.auto_default==="compressed_from_logs");
      if(logsArgDef&&outArgDef){
        const logsSel=el("arg_logs");
        const outEl=el("arg_output");
        if(logsSel&&outEl){
          logsSel.addEventListener("change",()=>{
            const first=Array.from(logsSel.selectedOptions).map(o=>o.value)[0]||"";
            if(first){
              const base=first.split("/").pop().replace(/^opportunities_/,"").replace(/[.]jsonl$/,"");
              outEl.value=`logs/compressed_${base}.json`;
            }
            updatePreview();
          });
        }
      }
      // ── applies_to conditional visibility ─────────────────────────────
      const subArgDef=(cmd.args_schema||[]).find(a=>a.positional&&a.kind==="choice");
      if(subArgDef){
        const subEl=el("arg_"+subArgDef.key);
        function applyConditionalVisibility(){
          const val=subEl?subEl.value:"";
          (cmd.args_schema||[]).forEach(arg=>{
            if(!arg.applies_to||!arg.applies_to.length) return;
            const wrapper=el("wrapper_arg_"+arg.key);
            if(wrapper){ wrapper.style.display=arg.applies_to.includes(val)?"":"none"; }
          });
          updatePreview();
        }
        if(subEl) subEl.addEventListener("change",applyConditionalVisibility);
        applyConditionalVisibility();
      }
      updatePreview();
    }

    function collectArgs(cmd){
      const args={};
      const subArg=(cmd.args_schema||[]).find(a=>a.key==="subcommand");
      const selectedSub=subArg?(() => {
        const n=el("arg_subcommand");
        return n ? n.value : (subArg.default||null);
      })():null;
      (cmd.args_schema||[]).forEach(arg=>{
        if((arg.applies_to||[]).length && selectedSub && !arg.applies_to.includes(selectedSub)){ return; }
        const node=el("arg_"+arg.key);
        if(!node){return;}
        if(arg.kind==="bool"){ args[arg.key]=!!node.checked; return; }
        if(arg.kind==="file-multi"){ args[arg.key]=Array.from(node.selectedOptions).map(o=>o.value).filter(Boolean); return; }
        const raw=(node.value||"").trim();
        if(raw===""){ if(arg.required){ args[arg.key]=null; } return; }
        if(arg.kind==="int"){ args[arg.key]=parseInt(raw,10); return; }
        if(arg.kind==="float"){ args[arg.key]=parseFloat(raw); return; }
        if(arg.kind==="list"){ args[arg.key]=raw.split(",").map(v=>v.trim()).filter(Boolean); return; }
        args[arg.key]=raw;
      });
      return args;
    }

    function updatePreview(){
      const cmd=selectedCommand();
      if(!cmd){return;}
      const args=collectArgs(cmd);
      const selectedSub=args.subcommand || null;
      let preview=`${cmd.mode==='module'?'python -m '+cmd.script:'python '+cmd.script}`;
      (cmd.args_schema||[]).forEach(arg=>{
        if((arg.applies_to||[]).length && selectedSub && !arg.applies_to.includes(selectedSub)){ return; }
        const v=args[arg.key];
        if(v===undefined||v===null||v===""){ return; }
        if(arg.positional){ preview+=` ${v}`; return; }
        if(arg.kind==="bool"){ if(v){ preview+=` ${arg.flag}`; } return; }
        if(arg.kind==="list"){ if(v.length){ preview+=` ${arg.flag} ${v.join(" ")}`; } return; }
        if(arg.kind==="file-multi"){ if(v&&v.length){ preview+=` ${arg.flag} ${v.join(" ")}`; } return; }
        preview+=` ${arg.flag} ${v}`;
      });
      el("preview").textContent=preview;
    }

    function renderPlaybook(){
      const completeState=getCompletedState();
      const stages=data.workflow_stages||[];
      const byStage=(stage)=>data.commands.filter(c=>(c.workflow_stage||c.category)===stage);
      const html=stages.map(stage=>{
        const items=byStage(stage).map(cmd=>{
          const completed=!!completeState[cmd.id];
          const next=(cmd.recommended_next_command_ids||[]).join(", ");
          return `<div class="stage-item">
            <div><strong>${cmd.title}</strong> <span class="chip ${completed?"completed":""}">${completed?"Completed":"Pending"}</span></div>
            <div class="small">${cmd.description}</div>
            <div class="small">${next?`Suggested next: ${next}`:"Suggested next: -"}</div>
            <div class="actions">
              <button style="width:auto" data-jump="${cmd.id}">Jump</button>
              <button style="width:auto" data-toggle="${cmd.id}">${completed?"Mark pending":"Mark complete"}</button>
            </div>
          </div>`;
        }).join("");
        return `<div class="stage"><h3>${stage}</h3>${items || '<div class="small">No commands</div>'}</div>`;
      }).join("");
      el("playbookStages").innerHTML=html;
      el("playbookStages").querySelectorAll("[data-jump]").forEach(btn=>{
        btn.onclick=()=>selectCommandById(btn.getAttribute("data-jump"));
      });
      el("playbookStages").querySelectorAll("[data-toggle]").forEach(btn=>{
        const id=btn.getAttribute("data-toggle");
        btn.onclick=()=>setCompleted(id, !getCompletedState()[id]);
      });
    }

    async function refreshCommands(){
      const resp=await fetch("/commands");
      data=await resp.json();
      const catSel=el("category");
      catSel.innerHTML=data.categories.map(c=>`<option value="${c}">${c}</option>`).join("");
      catSel.onchange=()=>{
        const cmds=groupByCategory(catSel.value);
        el("command").innerHTML=cmds.map(c=>`<option value="${c.id}">${c.title}</option>`).join("");
        renderForm(selectedCommand());
      };
      catSel.dispatchEvent(new Event("change"));
      el("command").onchange=()=>renderForm(selectedCommand());
      renderPlaybook();
    }

    function fmtMonitorValue(f){
      if(f.error){ return `<span class="dash-field-err" title="${f.error.replace(/"/g,'&quot;')}">err</span>`; }
      const v=f.value;
      if(v===null||v===undefined){ return "—"; }
      const unit=f.unit?` ${f.unit}`:"";
      if(f.format==="float"&&typeof v==="number"){ return `${v.toFixed(4)}${unit}`; }
      if(f.format==="timestamp"&&typeof v==="string"){ return v.replace("T"," ").replace(/[.][^Z]*/,"")+" UTC"; }
      return `${v}${unit}`;
    }

    async function refreshMonitors(runId){
      try{
        const resp=await fetch(`/runs/${runId}/monitors`);
        const payload=await resp.json();
        const tbody=el("monitorsBody");
        const hint=el("monitorsHint");
        const tbl=el("monitorsTable");
        const fields=payload.fields||[];
        if(!fields.length){
          tbl.style.display="none";
          hint.textContent="No tracked fields configured for this command.";
          return;
        }
        hint.textContent="";
        tbl.style.display="";
        tbody.innerHTML=fields.map(f=>`<tr><td>${f.label}</td><td>${fmtMonitorValue(f)}</td></tr>`).join("");
      }catch(_){}
    }

    function startMonitorsPoll(runId, status){
      if(monitorsPollTimer){ clearInterval(monitorsPollTimer); monitorsPollTimer=null; }
      refreshMonitors(runId);
      if(status==="running"||status==="queued"){
        monitorsPollTimer=setInterval(()=>refreshMonitors(runId),2000);
      }
    }

    async function refreshDashboard(){
      if(currentView!=="dashboard"){ return; }
      try{
        const resp=await fetch("/monitors/dashboard");
        const payload=await resp.json();
        const cmdMeta={};
        (data.commands||[]).forEach(c=>{ cmdMeta[c.id]=c; });
        const grid=el("dashboardGrid");
        const cmds=payload.commands||[];
        if(!cmds.length){
          grid.innerHTML=`<div class="dash-empty">No monitored commands configured. Add entries to configs/control_plane/monitors.json.</div>`;
          return;
        }
        grid.innerHTML=cmds.map(entry=>{
          const cmd=cmdMeta[entry.command_id]||{title:entry.command_id};
          const statusCls=entry.status?`st-${entry.status}`:"st-queued";
          const runLabel=entry.run_id?entry.run_id.slice(0,8):"—";
          const tsLabel=entry.started_at?(entry.started_at.replace("T"," ").replace(/[.][^Z]*/,"")+" UTC"):"no runs yet";
          const rows=(entry.fields||[]).map(f=>`<tr><td>${f.label}</td><td>${fmtMonitorValue(f)}</td></tr>`).join("")
            ||`<tr><td colspan="2" class="dash-empty">No data yet — run this command first.</td></tr>`;
          return `<div class="dash-card">
            <h3><span>${cmd.title}</span><span class="status ${statusCls}">${entry.status||"no runs"}</span></h3>
            <div class="small" style="margin-bottom:4px">Run ${runLabel} &bull; ${tsLabel}</div>
            <table><tbody>${rows}</tbody></table>
          </div>`;
        }).join("");
      }catch(_){}
    }

    function setView(view){
      currentView=view;
      document.querySelector("main.wrap:not(.dashboard)").style.display=(view==="runs")?"grid":"none";
      el("dashboardWrap").style.display=(view==="dashboard")?"grid":"none";
      el("dashboardBtn").textContent=(view==="dashboard")?"← Back to Runs":"Dashboard";
      if(view==="dashboard"){ refreshDashboard(); }
    }

    async function refreshRuns(){
      const q=encodeURIComponent((el("search").value||"").trim());
      const resp=await fetch(`/runs?q=${q}`);
      const payload=await resp.json();
      el("history").innerHTML=payload.runs.map(r=>`<tr onclick="inspectRun('${r.run_id}')"><td>${r.run_id.slice(0,8)}</td><td>${r.command_id}</td><td><span class="${statusClass(r.status)}">${r.status}</span></td><td><button class="report-btn" onclick="event.stopPropagation();showReport('${r.run_id}')">📋 Report</button></td></tr>`).join("");
      if(selectedRunId){
        const present=payload.runs.find(r=>r.run_id===selectedRunId);
        if(present){ inspectRun(selectedRunId, false); }
      }
    }
    async function inspectRun(runId, updateSelection=true){
      if(updateSelection){ selectedRunId=runId; }
      const runResp=await fetch(`/runs/${runId}`);
      const runPayload=await runResp.json();
      const run=runPayload.run;
      el("runMeta").textContent=`${run.command_id} | status=${run.status} | exit=${run.exit_code} | started=${run.started_at||'-'} | ended=${run.ended_at||'-'}`;
      startMonitorsPoll(runId, run.status);
      const logsResp=await fetch(`/runs/${runId}/logs`);
      const logs=await logsResp.json();
      el("stdout").textContent=logs.logs.stdout||"";
      el("stderr").textContent=logs.logs.stderr||"";
      const artResp=await fetch(`/runs/${runId}/artifacts`);
      const arts=await artResp.json();
      el("artifacts").innerHTML=(arts.artifacts||[]).map(a=>`<div class="artifact"><span>${a.path}</span><span>${a.exists?'exists':'missing'}</span></div>`).join("");
    }
    async function runCommand(){
      const cmd=selectedCommand();
      let valid=true;
      (cmd.args_schema||[]).forEach(arg=>{
        if(arg.kind==="int"||arg.kind==="float"){
          if(!validateArg("arg_"+arg.key,
              (arg.min_val===null||arg.min_val===undefined)?null:arg.min_val,
              (arg.max_val===null||arg.max_val===undefined)?null:arg.max_val)){valid=false;}
        }
        if(arg.required){
          const node=el("arg_"+arg.key);
          if(node&&node.type!=="checkbox"&&!node.value.trim()){
            const errNode=el("err_arg_"+arg.key);
            if(errNode){errNode.textContent="Required";errNode.style.display="";}
            node.style.borderColor="var(--bad)";valid=false;
          }
        }
      });
      if(!valid){return;}
      const args=collectArgs(cmd);
      const resp=await fetch(`/commands/${cmd.id}/runs`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({args})});
      const payload=await resp.json();
      latestRunId=payload.run.run_id;
      selectedRunId=latestRunId;
      await refreshRuns();
      await inspectRun(latestRunId);
      setCompleted(cmd.id, true);
    }
    async function stopLatest(){
      if(!latestRunId){ return; }
      await fetch(`/runs/${latestRunId}/stop`, {method:"POST"});
      await refreshRuns();
      await inspectRun(latestRunId);
    }

    function clearTourTarget(){
      document.querySelectorAll(".tour-target").forEach(n=>n.classList.remove("tour-target"));
    }
    function showTourStep(idx){
      if(idx<0||idx>=TOUR_STEPS.length){ endTour(true); return; }
      tourIndex=idx;
      const step=TOUR_STEPS[idx];
      localStorage.setItem(LS_TOUR_PROGRESS, String(idx));
      const pct=Math.round((idx/(TOUR_STEPS.length-1))*100);
      el("tourProgressBar").style.width=pct+"%";
      const badge=el("tourStage");
      if(step.stage){ badge.textContent=step.stage; badge.style.display="inline-block"; }
      else { badge.style.display="none"; }
      el("tourTitle").textContent=`Step ${idx+1}/${TOUR_STEPS.length}: ${step.title}`;
      el("tourText").textContent=step.text;
      const loadBtn=el("tourLoadBtn");
      if(step.commandId){ loadBtn.style.display="block"; loadBtn.textContent=`Load: ${step.title} →`; }
      else { loadBtn.style.display="none"; }
      clearTourTarget();
      const node=document.querySelector(step.target);
      if(node){ node.classList.add("tour-target"); node.scrollIntoView({behavior:"smooth",block:"center"}); }
      el("tourOverlay").style.display="block";
      el("tourCard").style.display="block";
      el("tourBackBtn").disabled=idx===0;
      el("tourNextBtn").textContent=idx===TOUR_STEPS.length-1?"✓ Finish":"Next →";
    }
    function startTour(force=false){
      const seen=localStorage.getItem(LS_TUTORIAL_SEEN)==="1";
      const dismissed=localStorage.getItem(LS_TUTORIAL_DISMISSED)===(TUTORIAL_VERSION);
      if(!force && (seen || dismissed)){ return; }
      const saved=Number(localStorage.getItem(LS_TOUR_PROGRESS) || "0");
      showTourStep(Number.isFinite(saved)?saved:0);
    }
    function endTour(markSeen){
      clearTourTarget();
      el("tourOverlay").style.display="none";
      el("tourCard").style.display="none";
      if(markSeen){
        localStorage.setItem(LS_TUTORIAL_SEEN, "1");
        localStorage.removeItem(LS_TOUR_PROGRESS);
      }
    }
    function skipTour(){
      localStorage.setItem(LS_TUTORIAL_DISMISSED, TUTORIAL_VERSION);
      endTour(true);
    }

    el("runBtn").onclick=runCommand;
    el("stopBtn").onclick=stopLatest;
    el("search").oninput=refreshRuns;
    el("dashboardBtn").onclick=()=>setView(currentView==="dashboard"?"runs":"dashboard");
    setInterval(refreshDashboard, 2000);
    el("helpBtn").onclick=()=>{
      localStorage.removeItem(LS_TUTORIAL_SEEN);
      localStorage.removeItem(LS_TUTORIAL_DISMISSED);
      localStorage.setItem(LS_TOUR_PROGRESS, "0");
      startTour(true);
    };
    el("tourNextBtn").onclick=()=>{ if(tourIndex===TOUR_STEPS.length-1){ endTour(true); } else { showTourStep(tourIndex+1); } };
    el("tourBackBtn").onclick=()=>showTourStep(Math.max(0,tourIndex-1));
    el("tourSkipBtn").onclick=skipTour;
    el("tourLoadBtn").onclick=()=>{ const s=TOUR_STEPS[tourIndex]; if(s&&s.commandId) selectCommandById(s.commandId); };

    document.addEventListener("input", (evt)=>{ if(evt.target.id && evt.target.id.startsWith("arg_")) updatePreview(); });
    refreshCommands().then(async ()=>{
      await refreshRuns();
      startTour(false);
    });
    setInterval(refreshRuns, 2000);

    // ── Run Report Modal ─────────────────────────────────────────────
    let _reportRunId = null;

    function showReport(runId){
      _reportRunId = runId;
      el("reportRunId").textContent = runId.slice(0, 8);
      el("reportLlmOut").style.display = "none";
      el("reportLlmOut").textContent = "";
      el("reportLlmBtn").disabled = false;
      el("reportLlmBtn").textContent = "🤖 LLM Analysis";
      el("reportExcelBtn").disabled = false;
      el("reportOverlay").style.display = "block";
      el("reportModal").style.display = "block";
    }

    function closeReport(){
      el("reportOverlay").style.display = "none";
      el("reportModal").style.display = "none";
      _reportRunId = null;
    }

    async function downloadExcel(){
      if(!_reportRunId) return;
      const btn = el("reportExcelBtn");
      const out = el("reportLlmOut");
      btn.disabled = true;
      btn.textContent = "⏳ Building…";
      try {
        const resp = await fetch(`/runs/${_reportRunId}/report/excel`);
        if(!resp.ok){
          // Server returned an error — show message in output area
          let errText = "";
          try { const j=await resp.json(); errText=j.error||JSON.stringify(j); } catch(_){ errText=await resp.text(); }
          out.style.display = "block";
          out.textContent = "Excel error (" + resp.status + "): " + errText;
          btn.disabled = false;
          btn.textContent = "📊 Download Excel";
          return;
        }
        const blob = await resp.blob();
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement("a");
        a.href     = url;
        a.download = `run_${_reportRunId.slice(0,8)}_report.xlsx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        btn.textContent = "✓ Downloaded";
        setTimeout(()=>{ btn.textContent="📊 Download Excel"; btn.disabled=false; }, 2000);
      } catch(e){
        out.style.display = "block";
        out.textContent = "Network error: " + e.message;
        btn.disabled = false;
        btn.textContent = "📊 Download Excel";
      }
    }

    async function runLlmAnalysis(){
      if(!_reportRunId) return;
      const btn = el("reportLlmBtn");
      const out = el("reportLlmOut");
      btn.disabled = true;
      btn.textContent = "⏳ Analysing…";
      out.style.display = "block";
      out.textContent = "Calling Groq API — this may take up to 30 s…";
      try {
        const resp = await fetch(`/runs/${_reportRunId}/report/llm`, {method:"POST"});
        const data = await resp.json();
        if(data.ok){
          // Render bullet lines: lines starting with • get a styled div
          const lines = data.analysis.split("\\n");
          out.innerHTML = lines.map(l=>{
            const t = l.trim();
            if(!t) return "";
            if(t.startsWith("•")){
              return `<div style="margin:4px 0;padding-left:14px;text-indent:-14px">${t}</div>`;
            }
            return `<div style="margin:2px 0;color:var(--muted)">${t}</div>`;
          }).filter(Boolean).join("");
          btn.textContent = "✓ Done";
        } else {
          out.textContent = "Error: " + (data.error || "unknown error");
          btn.disabled = false;
          btn.textContent = "🤖 Retry";
        }
      } catch(e){
        out.textContent = "Network error: " + e.message;
        btn.disabled = false;
        btn.textContent = "🤖 Retry";
      }
    }
  </script>
</body>
</html>
"""

    def trading_dashboard_html(self) -> str:  # noqa: C901  (long but self-contained)
        return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>CRT Trading Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root{--bg:#0f1724;--panel:#122033;--line:#23364e;--text:#e6edf7;
      --muted:#9fb0c8;--accent:#0ea5a3;--warn:#f59e0b;--ok:#22c55e;--bad:#ef4444}
    *{box-sizing:border-box}
    body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:var(--bg);color:var(--text);font-size:14px}
    a{color:var(--accent)}
    header{padding:12px 18px;border-bottom:1px solid var(--line);display:flex;
      justify-content:space-between;align-items:center;background:rgba(0,0,0,.2)}
    header h1{margin:0;font-size:17px}
    .back{font-size:13px;color:var(--accent);text-decoration:none;
      padding:5px 10px;border:1px solid var(--accent);border-radius:6px}
    .back:hover{background:rgba(14,165,163,.12)}
    nav.tabs{display:flex;gap:0;border-bottom:1px solid var(--line);
      padding:0 18px;background:rgba(0,0,0,.1)}
    nav.tabs button{background:none;border:none;color:var(--muted);padding:10px 16px;
      cursor:pointer;font-size:13px;border-bottom:2px solid transparent;margin-bottom:-1px}
    nav.tabs button.active{color:var(--accent);border-bottom-color:var(--accent)}
    nav.tabs button:hover{color:var(--text)}
    .tab-content{display:none;padding:18px}
    .tab-content.active{display:block}
    .card{background:var(--panel);border:1px solid var(--line);border-radius:10px;
      padding:16px;margin-bottom:14px}
    .card h3{margin:0 0 12px;font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
    .stat-row{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:14px}
    .stat{background:var(--panel);border:1px solid var(--line);border-radius:8px;
      padding:10px 16px;min-width:160px}
    .stat .label{font-size:11px;color:var(--muted);margin-bottom:4px}
    .stat .value{font-size:18px;font-weight:600}
    .stat-sub{font-size:10px;color:var(--muted);margin-top:3px}
    .badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600}
    .badge.ok{background:rgba(34,197,94,.15);color:var(--ok)}
    .badge.bad{background:rgba(239,68,68,.15);color:var(--bad)}
    .badge.warn{background:rgba(245,158,11,.15);color:var(--warn)}
    table{width:100%;border-collapse:collapse;font-size:13px}
    th{text-align:left;padding:8px 10px;color:var(--muted);font-weight:500;
      border-bottom:1px solid var(--line);font-size:12px}
    td{padding:7px 10px;border-bottom:1px solid rgba(35,54,78,.5)}
    tr:hover td{background:rgba(14,165,163,.04)}
    tr.active-row td{background:rgba(14,165,163,.08);border-left:3px solid var(--accent)}
    .corr-ok{color:var(--ok)} .corr-warn{color:var(--warn)} .corr-bad{color:var(--bad)}
    .pnl-pos{color:var(--ok)} .pnl-neg{color:var(--bad)}
    .verdict-ok{color:var(--ok)} .verdict-warn{color:var(--warn)} .verdict-bad{color:var(--bad)}
    .btn{padding:4px 10px;background:var(--accent);color:#000;border:none;border-radius:5px;
      cursor:pointer;font-size:12px;font-weight:600}
    .btn:hover{opacity:.85} .btn:disabled{opacity:.4;cursor:default}
    .btn-sm{padding:3px 8px;background:rgba(14,165,163,.15);color:var(--accent);
      border:1px solid var(--accent);border-radius:5px;cursor:pointer;font-size:12px}
    .btn-sm:hover{background:rgba(14,165,163,.28)} .btn-sm:disabled{opacity:.4;cursor:default}
    .filters{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
    .filters select,.filters input{background:var(--panel);border:1px solid var(--line);
      color:var(--text);padding:5px 8px;border-radius:6px;font-size:13px}
    .pagination{display:flex;gap:6px;align-items:center;margin-top:10px;font-size:13px}
    .pagination span{color:var(--muted)}
    .chart-wrap{position:relative;height:240px;margin-top:16px}
    .error-banner{background:rgba(239,68,68,.12);border:1px solid var(--bad);
      color:var(--bad);padding:8px 12px;border-radius:6px;margin-bottom:12px;font-size:13px}
    .loading{color:var(--muted);font-size:13px;padding:16px 0}
  </style>
</head>
<body>
<header>
  <h1>CRT Trading Dashboard</h1>
  <a href="/" class="back">&#8592; Control Plane</a>
</header>

<nav class="tabs">
  <button class="tab active" data-tab="status">Status</button>
  <button class="tab" data-tab="models">Models</button>
  <button class="tab" data-tab="opportunities">Opportunities</button>
  <button class="tab" data-tab="trades">Trades</button>
  <button class="tab" data-tab="backtests">Backtests</button>
</nav>

<!-- ═══════════════════════ STATUS TAB ═══════════════════════ -->
<div id="tab-status" class="tab-content active">
  <div id="status-error"></div>
  <div class="stat-row" id="status-stats">
    <div class="stat"><div class="label">Active Config</div><div class="value" id="s-config" style="font-size:13px">…</div></div>
    <div class="stat"><div class="label">Active Model</div><div class="value" id="s-model" style="font-size:14px">…</div></div>
    <div class="stat"><div class="label">Model Corr</div><div class="value" id="s-corr">…</div></div>
    <div class="stat"><div class="label">Kill Switch</div><div class="value" id="s-ks">…</div></div>
    <div class="stat"><div class="label">Trades (24h)</div><div class="value" id="s-trades">…</div></div>
  </div>
  <!-- ── Active Model Versions ──────────────────────────────── -->
  <div style="margin:16px 0 8px;font-size:11px;font-weight:600;color:var(--muted);
              text-transform:uppercase;letter-spacing:.08em">
    Active Model Versions (used in backtest)
  </div>
  <div id="mv-grid" style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:18px">
    <div class="stat" id="mv-gaussian">
      <div class="label">Gaussian</div>
      <div class="value" id="mv-g-version" style="font-size:14px">…</div>
      <div class="stat-sub" id="mv-g-meta"></div>
    </div>
    <div class="stat" id="mv-zonegate">
      <div class="label">Zone Gate</div>
      <div class="value" id="mv-z-version" style="font-size:14px">…</div>
      <div class="stat-sub" id="mv-z-meta"></div>
    </div>
    <div class="stat" id="mv-rr">
      <div class="label">RR Miner</div>
      <div class="value" id="mv-r-version" style="font-size:14px">…</div>
      <div class="stat-sub" id="mv-r-meta"></div>
    </div>
    <div class="stat" id="mv-tradenet">
      <div class="label">TradeNet</div>
      <div class="value" id="mv-t-version" style="font-size:14px">…</div>
      <div class="stat-sub" id="mv-t-meta"></div>
    </div>
  </div>
  <div class="stat-row">
    <div class="stat" style="cursor:pointer" onclick="switchTab('models')">
      <div class="label">&#8594; Model Registry</div>
      <div class="value" style="font-size:13px;color:var(--accent)">View all models</div>
    </div>
    <div class="stat" style="cursor:pointer" onclick="switchTab('opportunities')">
      <div class="label">&#8594; Opportunity Explorer</div>
      <div class="value" style="font-size:13px;color:var(--accent)">Browse signals</div>
    </div>
    <div class="stat" style="cursor:pointer" onclick="switchTab('trades')">
      <div class="label">&#8594; Trade Journal</div>
      <div class="value" style="font-size:13px;color:var(--accent)">View closed trades</div>
    </div>
  </div>
</div>

<!-- ═══════════════════════ MODELS TAB ══════════════════════ -->
<div id="tab-models" class="tab-content">
  <div id="models-error"></div>
  <div class="card">
    <h3>Gaussian Model Registry</h3>
    <div id="models-loading" class="loading">Loading…</div>
    <table id="models-table" style="display:none">
      <thead><tr>
        <th>Version</th><th>Corr</th><th>Cal.Error</th>
        <th>Train Samples</th><th>Trained At</th><th>Active</th><th>Action</th>
      </tr></thead>
      <tbody id="models-body"></tbody>
    </table>
  </div>
</div>

<!-- ═════════════════════ OPPORTUNITIES TAB ═════════════════ -->
<div id="tab-opportunities" class="tab-content">
  <div id="opp-error"></div>
  <div class="filters">
    <label style="color:var(--muted);font-size:12px">Instrument</label>
    <select id="opp-inst"></select>
    <label style="color:var(--muted);font-size:12px">Direction</label>
    <select id="opp-dir">
      <option value="">All</option><option value="long">Long</option><option value="short">Short</option>
    </select>
    <label style="color:var(--muted);font-size:12px">Outcome</label>
    <select id="opp-outcome">
      <option value="">All</option><option value="TP_HIT">TP Hit</option>
      <option value="SL_HIT">SL Hit</option><option value="TIMEOUT">Timeout</option>
    </select>
    <button class="btn-sm" onclick="loadOpportunities(1)">Apply</button>
  </div>
  <div class="card">
    <h3>Win Rate by Session</h3>
    <div class="chart-wrap"><canvas id="opp-chart"></canvas></div>
  </div>
  <div class="card">
    <h3>Opportunity Records</h3>
    <div id="opp-loading" class="loading">Loading…</div>
    <table id="opp-table" style="display:none">
      <thead><tr>
        <th>Timestamp</th><th>Direction</th><th>Outcome</th>
        <th>RR Achieved</th><th>Duration (c)</th><th>MFE</th><th>MAE</th>
      </tr></thead>
      <tbody id="opp-body"></tbody>
    </table>
    <div class="pagination">
      <button class="btn-sm" id="opp-prev" onclick="oppPage(-1)">&#8592; Prev</button>
      <span id="opp-page-info">–</span>
      <button class="btn-sm" id="opp-next" onclick="oppPage(1)">Next &#8594;</button>
    </div>
  </div>
</div>

<!-- ═══════════════════════ TRADES TAB ══════════════════════ -->
<div id="tab-trades" class="tab-content">
  <div id="trades-error"></div>
  <div class="filters">
    <label style="color:var(--muted);font-size:12px">Instrument</label>
    <select id="trades-inst"></select>
    <button class="btn-sm" onclick="loadTrades(1)">Apply</button>
  </div>
  <div class="card">
    <h3>Equity Curve</h3>
    <div class="chart-wrap" style="height:260px"><canvas id="equity-chart"></canvas></div>
  </div>
  <div class="card">
    <h3>Trade Journal</h3>
    <div id="trades-loading" class="loading">Loading…</div>
    <table id="trades-table" style="display:none">
      <thead><tr>
        <th>Trade ID</th><th>Opened At</th><th>Direction</th>
        <th>PnL (RR)</th><th>Exit Reason</th><th>Session</th><th>Capital After</th>
      </tr></thead>
      <tbody id="trades-body"></tbody>
    </table>
    <div class="pagination">
      <button class="btn-sm" id="trades-prev" onclick="tradesPage(-1)">&#8592; Prev</button>
      <span id="trades-page-info">–</span>
      <button class="btn-sm" id="trades-next" onclick="tradesPage(1)">Next &#8594;</button>
    </div>
  </div>
</div>

<!-- ══════════════════════ BACKTESTS TAB ════════════════════ -->
<div id="tab-backtests" class="tab-content">
  <div id="bt-error"></div>
  <div class="card">
    <h3>Phase-5 Calibration History</h3>
    <div id="bt-loading" class="loading">Loading…</div>
    <table id="bt-table" style="display:none">
      <thead><tr>
        <th>Version</th><th>N Samples</th><th>Corr</th><th>Cal.Error</th>
        <th>Verdict</th><th>Approved</th><th>Trained At</th>
      </tr></thead>
      <tbody id="bt-body"></tbody>
    </table>
  </div>
</div>

<script>
// ─── State ────────────────────────────────────────────────────────────────────
var oppPage_n = 1, trPage_n = 1;
var oppChartInst = null, eqChartInst = null;
var tabLoaded = {};
var SESSION_LABELS = {"1.0":"Asian","2.0":"London","3.0":"New York"};

// ─── Tab switching ────────────────────────────────────────────────────────────
function switchTab(name){
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.querySelector('.tab[data-tab="'+name+'"]').classList.add('active');
  document.getElementById('tab-'+name).classList.add('active');
  if(!tabLoaded[name]){
    tabLoaded[name] = true;
    if(name==='models')      loadModels();
    if(name==='opportunities'){ loadInstruments('opp-inst', ()=>{ loadOppStats(); loadOpportunities(1); }); }
    if(name==='trades')      { loadInstruments('trades-inst', ()=>loadTrades(1)); }
    if(name==='backtests')   loadBacktests();
  }
}
document.querySelectorAll('.tab').forEach(b=>{
  b.onclick = ()=>switchTab(b.dataset.tab);
});

// ─── Helpers ──────────────────────────────────────────────────────────────────
function fmtFloat(v,d){ return (v==null)?'—':Number(v).toFixed(d||4); }
function fmtInt(v){ return (v==null)?'—':Number(v).toLocaleString(); }
function showError(id, msg){ var el=document.getElementById(id);
  if(el) el.innerHTML='<div class="error-banner">'+msg+'</div>'; }
function clearError(id){ var el=document.getElementById(id); if(el) el.innerHTML=''; }

function corrClass(v){
  if(v==null) return '';
  return v>=0.05?'corr-ok':v>=0.01?'corr-warn':'corr-bad';
}
function calClass(v){
  if(v==null) return '';
  return v<0.02?'corr-ok':v<0.05?'corr-warn':'corr-bad';
}
function verdictClass(s){
  if(!s) return '';
  s=s.toUpperCase();
  if(s.includes('APPROVED')||s.includes('PASS')) return 'verdict-ok';
  if(s.includes('REJECT')||s.includes('FAIL')) return 'verdict-bad';
  return 'verdict-warn';
}

// ─── Instruments ──────────────────────────────────────────────────────────────
function loadInstruments(selId, cb){
  fetch('/api/instruments').then(r=>r.json()).then(d=>{
    var sel=document.getElementById(selId);
    sel.innerHTML='';
    (d.instruments||['EURUSD']).forEach(i=>{
      var o=document.createElement('option'); o.value=i; o.textContent=i; sel.appendChild(o);
    });
    if(cb) cb();
  }).catch(e=>{ console.warn('instruments',e); if(cb) cb(); });
}

// ─── Status ───────────────────────────────────────────────────────────────────
function loadStatus(){
  clearError('status-error');
  fetch('/api/status').then(r=>r.json()).then(d=>{
    document.getElementById('s-config').textContent = d.active_config||'—';
    document.getElementById('s-model').textContent  = d.active_model_version||'none';
    document.getElementById('s-corr').textContent   = fmtFloat(d.active_model_corr);
    document.getElementById('s-trades').textContent = d.trades_last_24h||0;
    var ks=d.kill_switch||{};
    var ksEl=document.getElementById('s-ks');
    if(ks.tripped){
      ksEl.innerHTML='<span class="badge bad">TRIPPED ('+ks.trip_reason+')</span>';
    } else {
      ksEl.innerHTML='<span class="badge ok">SAFE</span>';
    }
  }).catch(e=>showError('status-error','Status fetch failed: '+e));
  loadModelVersions();
}

// ─── Model Versions (all 4) ───────────────────────────────────────────────────
function loadModelVersions(){
  fetch('/api/model_versions').then(r=>r.json()).then(d=>{
    var g=d.gaussian||{}, z=d.zone_gate||{}, r=d.rr_model||{}, t=d.tradenet||{};

    // Gaussian
    document.getElementById('mv-g-version').textContent = g.version||'—';
    document.getElementById('mv-g-meta').textContent    =
      g.corr!=null ? 'corr '+Number(g.corr).toFixed(4) : (g.status||'');
    _mvStatus('mv-gaussian', g.status);

    // Zone Gate — prefer named version from registry; fallback to zone count
    document.getElementById('mv-z-version').textContent =
      z.version || (z.zone_count!=null ? z.zone_count+' zone'+(z.zone_count!==1?'s':'') : '—');
    document.getElementById('mv-z-meta').textContent =
      (z.zone_count!=null ? z.zone_count+' zones' : (z.schema_version||'')) +
      (z.total_versions>1 ? ' · '+z.total_versions+' ver' : '') +
      (z.trained_at ? ' · '+z.trained_at : (z.updated_at ? ' · '+z.updated_at : ''));
    _mvStatus('mv-zonegate', z.status);

    // RR Miner — prefer named version; fallback to sample count
    document.getElementById('mv-r-version').textContent =
      r.version || (r.n_samples!=null ? r.n_samples+' samples' : '—');
    document.getElementById('mv-r-meta').textContent =
      (r.n_samples!=null ? r.n_samples+' samples' : '') +
      (r.total_versions>1 ? ' · '+r.total_versions+' ver' : '') +
      (r.model_exists ? ' · model ok' : ' · no model');
    _mvStatus('mv-rr', r.status);

    // TradeNet
    document.getElementById('mv-t-version').textContent = t.version||'—';
    document.getElementById('mv-t-meta').textContent =
      (t.trained_at||'') +
      (t.total_versions ? ' · '+t.total_versions+' ver' : (t.count ? ' · '+t.count+' files' : ''));
    _mvStatus('mv-tradenet', t.status);
  }).catch(e=>console.warn('model_versions fetch failed:', e));
}

function _mvStatus(id, status){
  var el=document.getElementById(id); if(!el) return;
  el.style.borderLeft = (status==='active'||status==='ok')   ? '3px solid var(--ok)'   :
                        (status==='no-model'||status==='missing'||status==='empty') ?
                                                                '3px solid var(--warn)' :
                                                                '3px solid var(--line)';
}

// ─── Models ───────────────────────────────────────────────────────────────────
function loadModels(){
  clearError('models-error');
  document.getElementById('models-loading').style.display='block';
  document.getElementById('models-table').style.display='none';
  fetch('/api/models').then(r=>r.json()).then(d=>{
    document.getElementById('models-loading').style.display='none';
    if(d.error){ showError('models-error',d.error); return; }
    var tbody=document.getElementById('models-body');
    tbody.innerHTML='';
    (d.models||[]).forEach(m=>{
      var tr=document.createElement('tr');
      if(m.active) tr.classList.add('active-row');
      var corr=fmtFloat(m.corr_expected_rr);
      var cal=fmtFloat(m.calibration_error);
      var date=(m.trained_at||'').slice(0,10)||'—';
      var activeBadge=m.active?'<span class="badge ok">&#10003; Active</span>':'';
      var promoteBtn=m.active?
        '<button class="btn-sm" disabled>Active</button>':
        `<button class="btn-sm" onclick="promoteModel('${m.version}')">Promote</button>`;
      tr.innerHTML='<td>'+m.version+'</td>'+
        '<td class="'+corrClass(m.corr_expected_rr)+'">'+corr+'</td>'+
        '<td class="'+calClass(m.calibration_error)+'">'+cal+'</td>'+
        '<td>'+fmtInt(m.n_train)+'</td>'+
        '<td>'+date+'</td>'+
        '<td>'+activeBadge+'</td>'+
        '<td>'+promoteBtn+'</td>';
      tbody.appendChild(tr);
    });
    document.getElementById('models-table').style.display='';
  }).catch(e=>{
    document.getElementById('models-loading').style.display='none';
    showError('models-error','Models fetch failed: '+e);
  });
}

function promoteModel(version){
  if(!confirm('Promote model "'+version+'" as active?')) return;
  fetch('/api/promote_model',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({version:version})
  }).then(r=>r.json()).then(d=>{
    if(d.ok){ loadModels(); loadStatus(); }
    else alert('Promote failed: '+d.reason);
  }).catch(e=>alert('Error: '+e));
}

// ─── Opportunities ────────────────────────────────────────────────────────────
function loadOppStats(){
  var inst=document.getElementById('opp-inst').value||'EURUSD';
  fetch('/api/opportunity_stats?instrument='+inst).then(r=>r.json()).then(d=>{
    var labels=[], data=[];
    Object.entries(d.win_rate_by_session||{}).sort().forEach(([k,v])=>{
      labels.push(SESSION_LABELS[k]||('Sess '+k));
      data.push(Math.round(v*1000)/10);
    });
    if(oppChartInst){ oppChartInst.destroy(); oppChartInst=null; }
    var ctx=document.getElementById('opp-chart').getContext('2d');
    oppChartInst=new Chart(ctx,{
      type:'bar',
      data:{labels:labels,datasets:[{
        label:'Win Rate (%)',data:data,
        backgroundColor:'rgba(14,165,163,0.55)',borderColor:'rgba(14,165,163,1)',borderWidth:1
      }]},
      options:{responsive:true,maintainAspectRatio:false,
        plugins:{legend:{display:false}},
        scales:{y:{beginAtZero:true,max:60,ticks:{callback:v=>v+'%'},
          grid:{color:'rgba(35,54,78,.5)'},
          ticks:{color:'#9fb0c8'}},
          x:{grid:{color:'rgba(35,54,78,.5)'},ticks:{color:'#9fb0c8'}}}}
    });
  }).catch(e=>console.warn('opp stats',e));
}

function loadOpportunities(page){
  clearError('opp-error');
  oppPage_n=page;
  var inst=document.getElementById('opp-inst').value||'EURUSD';
  var dir =document.getElementById('opp-dir').value||'';
  var oc  =document.getElementById('opp-outcome').value||'';
  var url ='/api/opportunities?instrument='+inst+'&page='+page+'&per_page=20&direction='+dir+'&outcome='+oc;
  document.getElementById('opp-loading').style.display='block';
  document.getElementById('opp-table').style.display='none';
  fetch(url).then(r=>r.json()).then(d=>{
    document.getElementById('opp-loading').style.display='none';
    if(d.error){ showError('opp-error',d.error); return; }
    var tbody=document.getElementById('opp-body');
    tbody.innerHTML='';
    (d.records||[]).forEach(r=>{
      var tr=document.createElement('tr');
      var rr=r.rr_achieved!=null?Number(r.rr_achieved).toFixed(3):'—';
      var dirBadge=r.direction==='long'?
        '<span class="badge ok">L</span>':'<span class="badge bad">S</span>';
      var ocBadge=r.outcome==='TP_HIT'?
        '<span class="badge ok">TP</span>':
        r.outcome==='SL_HIT'?'<span class="badge bad">SL</span>':
        '<span class="badge warn">TMO</span>';
      tr.innerHTML='<td>'+(r.timestamp||'').slice(0,16)+'</td>'+
        '<td>'+dirBadge+'</td>'+
        '<td>'+ocBadge+'</td>'+
        '<td>'+rr+'</td>'+
        '<td>'+(r.duration_candles||'—')+'</td>'+
        '<td>'+fmtFloat(r.mfe,4)+'</td>'+
        '<td>'+fmtFloat(r.mae,4)+'</td>';
      tbody.appendChild(tr);
    });
    document.getElementById('opp-table').style.display='';
    var est=d.total_count_estimate||0;
    var total_pages=est>0?Math.ceil(est/20):'?';
    document.getElementById('opp-page-info').textContent=
      'Page '+page+' / ~'+total_pages+' (est. '+est.toLocaleString()+' records)';
    document.getElementById('opp-prev').disabled=(page<=1);
    document.getElementById('opp-next').disabled=!d.has_more;
  }).catch(e=>{
    document.getElementById('opp-loading').style.display='none';
    showError('opp-error','Opportunities fetch failed: '+e);
  });
}
function oppPage(delta){ loadOpportunities(Math.max(1,oppPage_n+delta)); }

// ─── Trades + Equity ──────────────────────────────────────────────────────────
function loadEquityCurve(){
  var inst=document.getElementById('trades-inst').value||'EURUSD';
  fetch('/api/equity_curve?instrument='+inst).then(r=>r.json()).then(d=>{
    var curve=d.curve||[];
    var labels=curve.map(p=>p.date);
    var pnl   =curve.map(p=>p.cumulative_pnl_rr);
    var cap   =curve.map(p=>p.capital);
    if(eqChartInst){ eqChartInst.destroy(); eqChartInst=null; }
    var ctx=document.getElementById('equity-chart').getContext('2d');
    eqChartInst=new Chart(ctx,{
      type:'line',
      data:{labels:labels,datasets:[
        {label:'Cumulative PnL (R)',data:pnl,borderColor:'#0ea5a3',
          tension:0.1,fill:false,pointRadius:0,yAxisID:'y'},
        {label:'Capital',data:cap,borderColor:'#f59e0b',
          tension:0.1,fill:false,pointRadius:0,yAxisID:'y1'}
      ]},
      options:{responsive:true,maintainAspectRatio:false,
        plugins:{legend:{labels:{color:'#9fb0c8'}}},
        scales:{
          y:{position:'left',grid:{color:'rgba(35,54,78,.5)'},ticks:{color:'#9fb0c8'}},
          y1:{position:'right',grid:{drawOnChartArea:false},ticks:{color:'#f59e0b'}},
          x:{ticks:{color:'#9fb0c8',maxTicksLimit:10},grid:{color:'rgba(35,54,78,.5)'}}
        }
      }
    });
  }).catch(e=>console.warn('equity',e));
}

function loadTrades(page){
  clearError('trades-error');
  trPage_n=page;
  var inst=document.getElementById('trades-inst').value||'EURUSD';
  var url='/api/trades?instrument='+inst+'&page='+page+'&per_page=50';
  document.getElementById('trades-loading').style.display='block';
  document.getElementById('trades-table').style.display='none';
  fetch(url).then(r=>r.json()).then(d=>{
    document.getElementById('trades-loading').style.display='none';
    if(d.error){ showError('trades-error',d.error); return; }
    var tbody=document.getElementById('trades-body');
    tbody.innerHTML='';
    (d.records||[]).forEach(r=>{
      var tr=document.createElement('tr');
      var pnl=r.pnl_rr_net!=null?Number(r.pnl_rr_net).toFixed(3):'—';
      var pnlClass=r.pnl_rr_net>0?'pnl-pos':r.pnl_rr_net<0?'pnl-neg':'';
      var cap=r.capital_after!=null?Number(r.capital_after).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}):'—';
      var sessLabel=SESSION_LABELS[String(r.session)]||r.session||'—';
      tr.innerHTML='<td>'+r.trade_id+'</td>'+
        '<td>'+(r.opened_at||'').slice(0,16)+'</td>'+
        '<td>'+r.direction+'</td>'+
        '<td class="'+pnlClass+'">'+pnl+'</td>'+
        '<td>'+r.exit_reason+'</td>'+
        '<td>'+sessLabel+'</td>'+
        '<td>'+cap+'</td>';
      tbody.appendChild(tr);
    });
    document.getElementById('trades-table').style.display='';
    var total=d.total_count||0;
    var total_pages=Math.max(1,Math.ceil(total/50));
    document.getElementById('trades-page-info').textContent=
      'Page '+page+' / '+total_pages+' ('+total+' trades)';
    document.getElementById('trades-prev').disabled=(page<=1);
    document.getElementById('trades-next').disabled=(page>=total_pages);
  }).catch(e=>{
    document.getElementById('trades-loading').style.display='none';
    showError('trades-error','Trades fetch failed: '+e);
  });
  loadEquityCurve();
}
function tradesPage(delta){ loadTrades(Math.max(1,trPage_n+delta)); }

// ─── Backtests ────────────────────────────────────────────────────────────────
function loadBacktests(){
  clearError('bt-error');
  document.getElementById('bt-loading').style.display='block';
  document.getElementById('bt-table').style.display='none';
  fetch('/api/backtest_history').then(r=>r.json()).then(d=>{
    document.getElementById('bt-loading').style.display='none';
    var tbody=document.getElementById('bt-body');
    tbody.innerHTML='';
    (d.backtests||[]).forEach(b=>{
      if(b.error){ return; }  // skip corrupt entries
      var tr=document.createElement('tr');
      var approvedBadge=b.integration_approved?
        '<span class="badge ok">&#10003;</span>':
        '<span class="badge bad">&#10007;</span>';
      var verdict=(b.verdict||'').slice(0,60)+(b.verdict&&b.verdict.length>60?'…':'');
      var vClass=verdictClass(b.verdict||'');
      tr.innerHTML='<td>'+b.version+'</td>'+
        '<td>'+fmtInt(b.n_samples)+'</td>'+
        '<td class="'+corrClass(b.corr_expected_rr)+'">'+fmtFloat(b.corr_expected_rr)+'</td>'+
        '<td class="'+calClass(b.calibration_error)+'">'+fmtFloat(b.calibration_error)+'</td>'+
        '<td class="'+vClass+'" title="'+(b.verdict||'')+'">'+verdict+'</td>'+
        '<td>'+approvedBadge+'</td>'+
        '<td>'+(b.trained_at||'').slice(0,10)||'—'+'</td>';
      tbody.appendChild(tr);
    });
    document.getElementById('bt-table').style.display='';
  }).catch(e=>{
    document.getElementById('bt-loading').style.display='none';
    showError('bt-error','Backtests fetch failed: '+e);
  });
}

// ─── Init ─────────────────────────────────────────────────────────────────────
loadStatus();
setInterval(loadStatus, 10000);
</script>
</body>
</html>
"""


def create_handler(api: ControlPlaneAPI, dash_api: TradingDashboardAPI, report_api: RunReportAPI | None = None):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CRTControlPlane/1.0"

        def _send_json(self, code: int, payload: dict[str, Any]) -> None:
            body = _json_bytes(payload)
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, code: int, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_bytes(
            self,
            code: int,
            data: bytes,
            content_type: str,
            filename: str | None = None,
        ) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            if filename:
                self.send_header(
                    "Content-Disposition",
                    f'attachment; filename="{filename}"',
                )
            self.end_headers()
            self.wfile.write(data)

        def _read_json_body(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0:
                return {}
            payload = self.rfile.read(content_length).decode("utf-8")
            if not payload:
                return {}
            loaded = json.loads(payload)
            if isinstance(loaded, dict):
                return loaded
            raise ValueError("Expected JSON object body.")

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            query = urllib.parse.parse_qs(parsed.query)
            try:
                # ── Trading Dashboard routes (/dashboard and /api/*) ──────────
                if path == "/dashboard":
                    self._send_html(HTTPStatus.OK, api.trading_dashboard_html())
                    return
                if path == "/api/model_versions":
                    self._send_json(HTTPStatus.OK, dash_api.model_versions_payload())
                    return
                if path == "/api/status":
                    self._send_json(HTTPStatus.OK, dash_api.status_payload())
                    return
                if path == "/api/models":
                    self._send_json(HTTPStatus.OK, dash_api.models_payload())
                    return
                if path == "/api/zone_gate_models":
                    self._send_json(HTTPStatus.OK, dash_api.zone_gate_models_payload())
                    return
                if path == "/api/rr_models":
                    self._send_json(HTTPStatus.OK, dash_api.rr_models_payload())
                    return
                if path == "/api/tradenet_models":
                    self._send_json(HTTPStatus.OK, dash_api.tradenet_models_payload())
                    return
                if path == "/api/instruments":
                    self._send_json(HTTPStatus.OK, dash_api.instruments_payload())
                    return
                if path == "/api/opportunities":
                    try:
                        page     = int(query.get("page",     ["1"])[0])
                        per_page = int(query.get("per_page", ["20"])[0])
                        per_page = min(max(per_page, 1), 500)
                    except (ValueError, IndexError):
                        page, per_page = 1, 20
                    instrument = query.get("instrument", ["EURUSD"])[0]
                    direction  = query.get("direction",  [""])[0]
                    outcome    = query.get("outcome",    [""])[0]
                    self._send_json(HTTPStatus.OK, dash_api.opportunities_payload(
                        instrument, page, per_page, direction, outcome))
                    return
                if path == "/api/opportunity_stats":
                    instrument = query.get("instrument", ["EURUSD"])[0]
                    self._send_json(HTTPStatus.OK, dash_api.opportunity_stats_payload(instrument))
                    return
                if path == "/api/trades":
                    try:
                        page     = int(query.get("page",     ["1"])[0])
                        per_page = int(query.get("per_page", ["50"])[0])
                        per_page = min(max(per_page, 1), 200)
                    except (ValueError, IndexError):
                        page, per_page = 1, 50
                    instrument = query.get("instrument", ["EURUSD"])[0]
                    self._send_json(HTTPStatus.OK, dash_api.trades_payload(
                        instrument, page, per_page))
                    return
                if path == "/api/equity_curve":
                    instrument = query.get("instrument", ["EURUSD"])[0]
                    self._send_json(HTTPStatus.OK, dash_api.equity_curve_payload(instrument))
                    return
                if path == "/api/backtest_history":
                    self._send_json(HTTPStatus.OK, dash_api.backtest_history_payload())
                    return
                # ── ui_kits/ static file serving (React UI kits) ─────────────
                if path.startswith("/ui_kits/"):
                    _MIME = {
                        ".html": "text/html; charset=utf-8",
                        ".js":   "application/javascript; charset=utf-8",
                        ".jsx":  "application/javascript; charset=utf-8",
                        ".css":  "text/css; charset=utf-8",
                        ".json": "application/json; charset=utf-8",
                        ".png":  "image/png",
                        ".jpg":  "image/jpeg",
                        ".svg":  "image/svg+xml",
                        ".md":   "text/plain; charset=utf-8",
                    }
                    _fp = REPO_ROOT / path.lstrip("/")
                    # Trailing slash or directory → serve index.html
                    if _fp.is_dir():
                        _fp = _fp / "index.html"
                    if not _fp.exists() or not _fp.is_file():
                        self._send_json(HTTPStatus.NOT_FOUND, {"error": f"Not found: {path}"})
                        return
                    _ct   = _MIME.get(_fp.suffix.lower(), "application/octet-stream")
                    _body = _fp.read_bytes()
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", _ct)
                    self.send_header("Content-Length", str(len(_body)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(_body)
                    return
                # ── Existing Control Plane routes ─────────────────────────────
                if path == "/":
                    self._send_html(HTTPStatus.OK, api.ui_html())
                    return
                if path == "/commands":
                    self._send_json(HTTPStatus.OK, api.commands_payload())
                    return
                if path == "/files":
                    glob_pattern = query.get("glob", [""])[0]
                    self._send_json(HTTPStatus.OK, api.files_payload(glob_pattern))
                    return
                if path == "/runs":
                    self._send_json(HTTPStatus.OK, api.runs_payload(query.get("q", [""])[0]))
                    return
                if path.startswith("/runs/") and path.endswith("/report/excel"):
                    run_id   = path.split("/")[2]
                    run_snap = api.run_payload(run_id)["run"]
                    logs     = api.logs_payload(run_id)["logs"]
                    arts     = api.artifacts_payload(run_id)["artifacts"]
                    if report_api is None:
                        self._send_json(HTTPStatus.SERVICE_UNAVAILABLE,
                                        {"error": "RunReportAPI not initialised"})
                        return
                    xlsx  = report_api.excel_bytes(run_snap, logs, arts)
                    fname = f"run_{run_id[:8]}_report.xlsx"
                    self._send_bytes(
                        HTTPStatus.OK, xlsx,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        filename=fname,
                    )
                    return
                if path.startswith("/runs/") and path.endswith("/logs"):
                    run_id = path.split("/")[2]
                    self._send_json(HTTPStatus.OK, api.logs_payload(run_id))
                    return
                if path.startswith("/runs/") and path.endswith("/artifacts"):
                    run_id = path.split("/")[2]
                    self._send_json(HTTPStatus.OK, api.artifacts_payload(run_id))
                    return
                if path.startswith("/runs/") and path.endswith("/monitors"):
                    run_id = path.split("/")[2]
                    self._send_json(HTTPStatus.OK, api.monitors_payload(run_id))
                    return
                if path == "/monitors/dashboard":
                    self._send_json(HTTPStatus.OK, api.dashboard_payload())
                    return
                if path.startswith("/monitors/history/"):
                    command_id = path[len("/monitors/history/"):]
                    try:
                        limit = int(query.get("limit", ["50"])[0])
                    except (ValueError, IndexError):
                        limit = 50
                    self._send_json(HTTPStatus.OK, api.monitor_history_payload(command_id, limit=limit))
                    return
                if path.startswith("/runs/"):
                    run_id = path.split("/")[2]
                    self._send_json(HTTPStatus.OK, api.run_payload(run_id))
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"error": f"Unknown route: {path}"})
            except KeyError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except Exception as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        def do_OPTIONS(self) -> None:
            """CORS preflight — allows ui_kits pages served via file:// to call the API."""
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            try:
                # ── Dashboard POST routes ─────────────────────────────────────
                if path == "/api/promote_model":
                    body    = self._read_json_body()
                    version = body.get("version", "")
                    if not version:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "version required"})
                        return
                    force  = bool(body.get("force", False))
                    result = dash_api.promote_model_payload(version, force)
                    code   = HTTPStatus.OK if result["ok"] else HTTPStatus.BAD_REQUEST
                    self._send_json(code, result)
                    return
                if path == "/api/promote_zone_gate":
                    body   = self._read_json_body()
                    result = dash_api.promote_zone_gate_payload(body.get("version", ""))
                    self._send_json(HTTPStatus.OK if result["ok"] else HTTPStatus.BAD_REQUEST, result)
                    return
                if path == "/api/promote_rr":
                    body   = self._read_json_body()
                    result = dash_api.promote_rr_payload(body.get("version", ""))
                    self._send_json(HTTPStatus.OK if result["ok"] else HTTPStatus.BAD_REQUEST, result)
                    return
                if path == "/api/promote_tradenet":
                    body   = self._read_json_body()
                    result = dash_api.promote_tradenet_payload(body.get("version", ""))
                    self._send_json(HTTPStatus.OK if result["ok"] else HTTPStatus.BAD_REQUEST, result)
                    return
                # ── Report LLM route ─────────────────────────────────────────
                if path.startswith("/runs/") and path.endswith("/report/llm"):
                    run_id   = path.split("/")[2]
                    run_snap = api.run_payload(run_id)["run"]
                    logs     = api.logs_payload(run_id)["logs"]
                    arts     = api.artifacts_payload(run_id)["artifacts"]
                    if report_api is None:
                        self._send_json(HTTPStatus.SERVICE_UNAVAILABLE,
                                        {"error": "RunReportAPI not initialised"})
                        return
                    result = report_api.llm_analysis(run_snap, logs, arts)
                    code   = HTTPStatus.OK if result["ok"] else HTTPStatus.BAD_GATEWAY
                    self._send_json(code, result)
                    return
                # ── Existing routes ───────────────────────────────────────────
                if path.startswith("/commands/") and path.endswith("/runs"):
                    command_id = path[len("/commands/") : -len("/runs")]
                    payload = self._read_json_body()
                    args = payload.get("args", {})
                    if not isinstance(args, dict):
                        raise ValueError("args must be an object.")
                    self._send_json(HTTPStatus.CREATED, api.create_run_payload(command_id=command_id, args=args))
                    return
                if path.startswith("/runs/") and path.endswith("/stop"):
                    run_id = path.split("/")[2]
                    self._send_json(HTTPStatus.OK, api.stop_payload(run_id))
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"error": f"Unknown route: {path}"})
            except KeyError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except Exception as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        def log_message(self, fmt: str, *args: Any) -> None:
            import sys
            print(f"[CRT] {self.address_string()} {fmt % args}", file=sys.stderr, flush=True)

    return Handler


class ControlPlaneServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8787, manager: JobManager | None = None) -> None:
        self._host = host
        self._port = port
        self._manager = manager or JobManager()
        self._api = ControlPlaneAPI(self._manager)
        self._dash_api = TradingDashboardAPI()
        self._report_api = RunReportAPI()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def manager(self) -> JobManager:
        return self._manager

    @property
    def api(self) -> ControlPlaneAPI:
        return self._api

    @property
    def base_url(self) -> str:
        if self._httpd is None:
            return f"http://{self._host}:{self._port}"
        return f"http://{self._host}:{self._httpd.server_address[1]}"

    def start(self) -> None:
        if self._httpd is not None:
            return
        handler = create_handler(self._api, self._dash_api, self._report_api)
        self._httpd = ThreadingHTTPServer((self._host, self._port), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        self._httpd = None
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None


def find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def run_server(host: str = "127.0.0.1", port: int = 8787) -> None:
    server = ControlPlaneServer(host=host, port=port)
    server.start()
    print(f"CRT Control Plane running at {server.base_url}")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            threading.Event().wait(3600)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CRT Control Plane HTTP server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)
