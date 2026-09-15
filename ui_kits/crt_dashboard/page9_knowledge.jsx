// page9_knowledge.jsx — Truth-tier Knowledge retrieval UI.
// Renders tier partitions + divergence flags as first-class (never a flat blend).

function KnowledgePage() {
  const [q, setQ] = React.useState("why is rr_fusion disabled");
  const [loading, setLoading] = React.useState(false);
  const [err, setErr] = React.useState("");
  const [result, setResult] = React.useState(null);
  const [status, setStatus] = React.useState(null);

  React.useEffect(() => {
    if (window.ApiClient && window.ApiClient.fetchKnowledgeStatus) {
      window.ApiClient.fetchKnowledgeStatus()
        .then(setStatus)
        .catch(() => setStatus({ ok: false }));
    }
  }, []);

  function runSearch(e) {
    if (e) e.preventDefault();
    setLoading(true);
    setErr("");
    window.ApiClient.fetchKnowledgeSearch(q, { top_k: 12, explain: false })
      .then((data) => {
        setResult(data);
        setLoading(false);
      })
      .catch((ex) => {
        setErr(String(ex && ex.message ? ex.message : ex));
        setLoading(false);
      });
  }

  const order = ["CURRENT", "RECORDED", "INTENDED", "REFERENCE", "HISTORICAL"];
  const classes = result && result.by_truth_class
    ? order.filter((tc) => result.by_truth_class[tc]).concat(
        Object.keys(result.by_truth_class).filter((tc) => order.indexOf(tc) < 0)
      )
    : [];

  return (
    <div className="page knowledge-page" style={{ padding: 16 }}>
      <h2 style={{ marginTop: 0 }}>Knowledge (truth-tier RAG)</h2>
      <p style={{ color: "#7f8da6", maxWidth: 720 }}>
        Divergence-surfacing retrieval — verbatim spans partitioned by truth class.
        The retriever never blends CURRENT / INTENDED / RECORDED and never picks a winner.
      </p>

      {status && (
        <div style={{ marginBottom: 12, fontSize: 12, color: status.ok ? "#34d399" : "#f87171" }}>
          Index: {status.ok ? "ready" : "missing"}{" "}
          {status.manifest ? `· chunks=${status.manifest.chunks || "?"} records=${status.manifest.records || "?"}` : ""}
        </div>
      )}

      <form onSubmit={runSearch} style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Ask about code, findings, configs…"
          style={{ flex: 1, padding: "8px 12px", borderRadius: 6, border: "1px solid #334155", background: "#0b1220", color: "#e2e8f0" }}
        />
        <button type="submit" disabled={loading} style={{ padding: "8px 16px", borderRadius: 6 }}>
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {err && <div style={{ color: "#f87171", marginBottom: 12 }}>{err}</div>}

      {result && result.ok && (
        <div>
          <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 12 }}>
            {result.total_spans} spans · {result.retrieval_time_ms}ms · classes: {(result.truth_classes || []).join(", ")}
          </div>

          {(result.divergence_flags || []).length > 0 && (
            <div style={{ marginBottom: 16, padding: 12, border: "1px solid #b45309", borderRadius: 8, background: "#1c1408" }}>
              <div style={{ fontWeight: 700, color: "#fbbf24", marginBottom: 8 }}>Divergence flags</div>
              {(result.divergence_flags || []).map((f, i) => (
                <div key={i} style={{ fontSize: 13, marginBottom: 4 }}>
                  <span style={{ color: "#fbbf24" }}>[{f.kind}]</span> {f.detail || f.symbol_or_id}
                  {f.truth_classes && f.truth_classes.length ? ` · ${f.truth_classes.join(" / ")}` : ""}
                </div>
              ))}
            </div>
          )}

          {classes.map((tc) => (
            <div key={tc} style={{ marginBottom: 20 }}>
              <h3 style={{ color: "#38bdf8", borderBottom: "1px solid #1e293b", paddingBottom: 4 }}>{tc}</h3>
              {(result.by_truth_class[tc] || []).map((c) => (
                <div key={c.chunk_id} style={{ marginBottom: 12, padding: 10, background: "#0b1220", borderRadius: 8, border: "1px solid #1e293b" }}>
                  <div style={{ fontSize: 13 }}>
                    <code>{c.filepath}</code> · L{c.start_line}–{c.end_line}
                    {c.lifecycle_status && c.lifecycle_status !== "LIVE" ? (
                      <span style={{ color: "#f87171", marginLeft: 8 }}>[{c.lifecycle_status}]</span>
                    ) : null}
                    <span style={{ color: "#64748b", marginLeft: 8 }}>score {Number(c.score).toFixed(3)}</span>
                  </div>
                  {c.heading ? <div style={{ fontSize: 12, color: "#94a3b8" }}>{c.heading}</div> : null}
                  <pre style={{ whiteSpace: "pre-wrap", fontSize: 12, marginTop: 8, color: "#cbd5e1" }}>{c.text}</pre>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {result && !result.ok && (
        <div style={{ color: "#f87171" }}>{result.error || "search failed"}</div>
      )}
    </div>
  );
}

Object.assign(window, { KnowledgePage });
