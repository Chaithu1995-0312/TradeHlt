function App() {
  const [, force] = useState(0);
  useEffect(() => mockApi.subscribe(() => force(x => x + 1)), []);

  const [view, setView] = useState("runs");
  const [tourOpen, setTourOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [latestRunId, setLatestRunId] = useState(null);
  const [completed, setCompleted] = useState({});

  const data = mockApi.commands();
  const runs = mockApi.listRuns(search).runs;
  const dashEntries = mockApi.dashboard().commands;

  const selectedRun = selectedRunId ? mockApi.getRun(selectedRunId).run : null;
  const logs = selectedRunId ? mockApi.logs(selectedRunId) : null;
  const arts = selectedRunId ? mockApi.artifacts(selectedRunId) : null;
  const mons = selectedRunId ? mockApi.monitors(selectedRunId) : { fields: [] };

  const onRun = (cmd, args, cmdline) => {
    const { run } = mockApi.createRun(cmd.id, args, cmdline);
    setLatestRunId(run.run_id);
    setSelectedRunId(run.run_id);
  };
  const onStop = () => { if (latestRunId) mockApi.stop(latestRunId); };
  const onJump = (id) => { /* no-op stub: would scroll launcher */ };

  return (
    <div style={{ minHeight: "100vh", background: "linear-gradient(120deg,#0f1724,#1a2438)", color: "#e6edf7", fontFamily: '"Segoe UI", system-ui, Arial, sans-serif', fontSize: 13 }}>
      <Header view={view} onToggleView={() => setView(v => v === "dashboard" ? "runs" : "dashboard")} onHelp={() => setTourOpen(true)} />
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
            onInspect={setSelectedRunId}
            selectedRunId={selectedRunId}
            onCommandComplete={(id) => setCompleted(c => ({ ...c, [id]: true }))}
          />
          <InspectorPanel run={selectedRun} logs={logs?.logs} artifacts={arts} monitors={mons} />
        </main>
      ) : (
        <main style={{ padding: 14 }}>
          <DashboardView entries={dashEntries} commands={data.commands} />
        </main>
      )}
      <Tour open={tourOpen} onClose={() => setTourOpen(false)} />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
