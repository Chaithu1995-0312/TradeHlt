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
from src.control_plane.registry import command_spec_to_json, workflow_stage_order


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
    #tourCard{position:fixed;right:20px;bottom:20px;width:340px;background:#0f1b2e;border:1px solid var(--line);border-radius:12px;padding:12px;z-index:1000;display:none}
    #tourCard h3{margin:0 0 6px 0;font-size:14px}
    #tourCard p{margin:0 0 8px 0;font-size:12px;color:var(--muted)}
    .tour-actions{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px}
    .tour-target{outline:2px solid var(--accent);outline-offset:2px;border-radius:8px}
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
            <thead><tr><th>Run</th><th>Command</th><th>Status</th></tr></thead>
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
    <h3 id="tourTitle">Tour</h3>
    <p id="tourText"></p>
    <div class="tour-actions">
      <button id="tourBackBtn">Back</button>
      <button id="tourNextBtn">Next</button>
      <button id="tourSkipBtn">Skip</button>
    </div>
  </div>

  <script>
    let data={commands:[],categories:[],workflow_stages:[]};
    let latestRunId=null;
    let selectedRunId=null;
    let currentView="runs";
    let monitorsPollTimer=null;
    const el = (id)=>document.getElementById(id);
    const TUTORIAL_VERSION="v1";
    const LS_TUTORIAL_SEEN="tutorial_seen";
    const LS_TUTORIAL_DISMISSED="tutorial_dismissed_version";
    const LS_PLAYBOOK_COMPLETED="playbook_completed";
    const LS_TOUR_PROGRESS="tutorial_progress";

    const TOUR_STEPS = [
      { title:"Category", text:"Choose workflow category first.", target:"#category" },
      { title:"Command", text:"Pick command inside selected category.", target:"#command" },
      { title:"Arguments", text:"Fill dynamic arguments for the command.", target:"#formArea" },
      { title:"Preview", text:"Check exact CLI command before running.", target:"#preview" },
      { title:"Run", text:"Run command and monitor status.", target:"#runBtn" },
      { title:"History", text:"Use run history to inspect previous executions.", target:"#historyPanel" },
      { title:"Inspector", text:"Read stdout, stderr, and artifacts.", target:"#inspectorPanel" },
      { title:"Playbook", text:"Use playbook for guided workflow navigation.", target:"#playbookPanel" }
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
    function argInputHtml(arg){
      const id="arg_"+arg.key;
      let inputType="text";
      if(arg.kind==="int"||arg.kind==="float"){inputType="number";}
      if(arg.kind==="bool"){return `<label><input id="${id}" type="checkbox" ${arg.default?"checked":""}/> ${arg.key}</label>`;}
      if(arg.kind==="choice"){
        const opts=(arg.choices||[]).map(c=>`<option value="${c}" ${arg.default===c?"selected":""}>${c}</option>`).join("");
        return `<label>${arg.key}</label><select id="${id}">${opts}</select>`;
      }
      const val=(arg.default===null||arg.default===undefined)?"":String(arg.default);
      return `<label>${arg.key}</label><input id="${id}" type="${inputType}" value="${val}" placeholder="${arg.kind==='list'?'comma,separated,values':''}" />`;
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
      el("history").innerHTML=payload.runs.map(r=>`<tr onclick="inspectRun('${r.run_id}')"><td>${r.run_id.slice(0,8)}</td><td>${r.command_id}</td><td><span class="${statusClass(r.status)}">${r.status}</span></td></tr>`).join("");
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
      if(idx < 0 || idx >= TOUR_STEPS.length){ endTour(true); return; }
      tourIndex=idx;
      const step=TOUR_STEPS[idx];
      localStorage.setItem(LS_TOUR_PROGRESS, String(idx));
      el("tourTitle").textContent=`Step ${idx+1}/${TOUR_STEPS.length}: ${step.title}`;
      el("tourText").textContent=step.text;
      clearTourTarget();
      const node=document.querySelector(step.target);
      if(node){ node.classList.add("tour-target"); node.scrollIntoView({behavior:"smooth", block:"center"}); }
      el("tourOverlay").style.display="block";
      el("tourCard").style.display="block";
      el("tourBackBtn").disabled = idx===0;
      el("tourNextBtn").textContent = idx===TOUR_STEPS.length-1 ? "Finish" : "Next";
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

    document.addEventListener("input", (evt)=>{ if(evt.target.id && evt.target.id.startsWith("arg_")) updatePreview(); });
    refreshCommands().then(async ()=>{
      await refreshRuns();
      startTour(false);
    });
    setInterval(refreshRuns, 2000);
  </script>
</body>
</html>
"""


def create_handler(api: ControlPlaneAPI):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CRTControlPlane/1.0"

        def _send_json(self, code: int, payload: dict[str, Any]) -> None:
            body = _json_bytes(payload)
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, code: int, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

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
                if path == "/":
                    self._send_html(HTTPStatus.OK, api.ui_html())
                    return
                if path == "/commands":
                    self._send_json(HTTPStatus.OK, api.commands_payload())
                    return
                if path == "/runs":
                    self._send_json(HTTPStatus.OK, api.runs_payload(query.get("q", [""])[0]))
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

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            try:
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
            return

    return Handler


class ControlPlaneServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8787, manager: JobManager | None = None) -> None:
        self._host = host
        self._port = port
        self._manager = manager or JobManager()
        self._api = ControlPlaneAPI(self._manager)
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
        handler = create_handler(self._api)
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
