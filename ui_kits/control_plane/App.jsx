function App() {
  const [, force] = useState(0);
  useEffect(() => mockApi.subscribe(() => force(x => x + 1)), []);

  const [view, setView] = useState("runs");
  const [tourOpen, setTourOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [latestRunId, setLatestRunId] = useState(null);
  const [completed, setCompleted] = useState({});
  const [contextRunId, setContextRunId] = useState(null);
  const [contextCommandId, setContextCommandId] = useState(null);
  const [exploreFlow, setExploreFlow] = useState(null);

  // Closure deep-link: /ui_kits/control_plane/?run={run_id}
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const rid = params.get("run");
      if (rid) {
        setView("runs");
        setSelectedRunId(rid);
        mockApi.getRun(rid);
      }
    } catch (_) { /* noop */ }
  }, []);

  const selectRun = (runId) => {
    setSelectedRunId(runId);
    try {
      const url = new URL(window.location.href);
      if (runId) url.searchParams.set("run", runId);
      else url.searchParams.delete("run");
      window.history.replaceState({}, "", url.pathname + url.search + url.hash);
    } catch (_) { /* noop */ }
  };

  const data = mockApi.commands();
  const runs = mockApi.listRuns(search).runs;
  const dashEntries = mockApi.dashboard().commands;

  const selectedRun = selectedRunId ? mockApi.getRun(selectedRunId).run : null;
  const arts = selectedRunId ? mockApi.artifacts(selectedRunId) : null;
  const mons = selectedRunId ? mockApi.monitors(selectedRunId) : { fields: [] };

  const onReport = (runId) => {
    window.open(`http://localhost:8787/runs/${runId}/report/excel`, "_blank");
  };
  const onContext = (runId) => {
    setContextRunId(runId);
  };

  const onRun = (cmd, args, cmdline) => {
    const { run } = mockApi.createRun(cmd.id, args, cmdline);
    setLatestRunId(run.run_id);
    selectRun(run.run_id);
  };
  const onStop = () => { if (latestRunId) mockApi.stop(latestRunId); };
  const onJump = (id) => { /* no-op stub: would scroll launcher */ };

  return (
    <div style={{ minHeight: "100vh", background: "linear-gradient(120deg,#0f1724,#1a2438)", color: "#e6edf7", fontFamily: '"Segoe UI", system-ui, Arial, sans-serif', fontSize: 13 }}>
      <Header view={view} setView={setView} onHelp={() => setTourOpen(true)} />
      {view === "runs" ? (
        <main style={{ display: "grid", gridTemplateColumns: "310px 380px 1fr", gap: 14, padding: 14, minHeight: "calc(100vh - 56px)", boxSizing: "border-box" }}>
          <PlaybookPanel
            commands={data.commands}
            stages={data.workflow_stages}
            completedMap={completed}
            onJump={onJump}
            onToggle={(id) => setCompleted(c => ({ ...c, [id]: !c[id] }))}
          />
          <LauncherPanel
            commands={data.commands}
            categories={data.categories}
            runs={runs}
            search={search}
            setSearch={setSearch}
            onRun={onRun}
            onStop={onStop}
            onInspect={selectRun}
            selectedRunId={selectedRunId}
            onCommandComplete={(id) => setCompleted(c => ({ ...c, [id]: true }))}
            onReport={onReport}
            onContext={onContext}
          />
          <InspectorPanel run={selectedRun} artifacts={arts} monitors={mons} onReport={onReport} onContext={onContext} commands={data.commands} />
        </main>
      ) : view === "dashboard" ? (
        <main style={{ padding: 14 }}>
          <DashboardView entries={dashEntries} commands={data.commands} />
        </main>
      ) : view === "workflow" ? (
        <WorkflowPanel
          onNode={setContextCommandId}
          onFlow={(flow) => { setExploreFlow(flow); setView("explore"); }}
        />
      ) : view === "explore" ? (
        <ExplorerPanel initialFlow={exploreFlow} />
      ) : (
        <AgentPanel />
      )}
      <Tour open={tourOpen} onClose={() => setTourOpen(false)} />
      {contextRunId && (
        <ContextModal
          runId={contextRunId}
          run={mockApi.getRun(contextRunId)?.run || null}
          onClose={() => setContextRunId(null)}
        />
      )}
      {contextCommandId && (
        <NodeContextDrawer
          commandId={contextCommandId}
          onClose={() => setContextCommandId(null)}
          onOpenRun={(runId) => { setContextCommandId(null); setContextRunId(runId); }}
        />
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
