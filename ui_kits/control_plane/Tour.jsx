const TOUR_STEPS = [
  { title: "Category", text: "Choose workflow category first." },
  { title: "Command", text: "Pick command inside selected category." },
  { title: "Arguments", text: "Fill dynamic arguments for the command." },
  { title: "Preview", text: "Check exact CLI command before running." },
  { title: "Run", text: "Run command and monitor status." },
  { title: "History", text: "Use run history to inspect previous executions." },
  { title: "Inspector", text: "Read stdout, stderr, and artifacts." },
  { title: "Playbook", text: "Use playbook for guided workflow navigation." },
];

function Tour({ open, onClose }) {
  const [idx, setIdx] = useState(0);
  if (!open) return null;
  const step = TOUR_STEPS[idx];
  return (
    <React.Fragment>
      <div style={{ position: "fixed", inset: 0, background: "rgba(3,8,15,.64)", zIndex: 999 }} />
      <div style={{ position: "fixed", right: 20, bottom: 20, width: 340, background: "#0f1b2e", border: "1px solid #23364e", borderRadius: 12, padding: 12, zIndex: 1000 }}>
        <h3 style={{ margin: "0 0 6px 0", fontSize: 14, fontWeight: 600 }}>Step {idx + 1}/{TOUR_STEPS.length}: {step.title}</h3>
        <p style={{ margin: "0 0 8px 0", fontSize: 12, color: "#9fb0c8" }}>{step.text}</p>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6 }}>
          <Button autoWidth variant="ghost" onClick={() => setIdx(Math.max(0, idx - 1))} style={{ opacity: idx === 0 ? 0.5 : 1 }}>Back</Button>
          <Button autoWidth onClick={() => { if (idx === TOUR_STEPS.length - 1) { onClose(); setIdx(0); } else setIdx(idx + 1); }}>{idx === TOUR_STEPS.length - 1 ? "Finish" : "Next"}</Button>
          <Button autoWidth variant="ghost" onClick={() => { onClose(); setIdx(0); }}>Skip</Button>
        </div>
      </div>
    </React.Fragment>
  );
}
window.Tour = Tour;
