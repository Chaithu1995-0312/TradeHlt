// Reusable primitives matching control-plane styling exactly.
const { useState, useEffect, useRef, useMemo } = React;

function Panel({ title, children, id, style }) {
  return (
    <section id={id} style={{ background: "#122033", border: "1px solid #23364e", borderRadius: 12, overflow: "hidden", display: "flex", flexDirection: "column", ...style }}>
      {title && <h2 style={{ fontSize: 14, margin: 0, padding: "10px 12px", borderBottom: "1px solid #23364e", fontWeight: 600 }}>{title}</h2>}
      <div style={{ padding: "10px 12px", overflow: "auto", flex: 1 }}>{children}</div>
    </section>
  );
}

function StatusPill({ status }) {
  const map = {
    running:   { color: "#f59e0b" },
    succeeded: { color: "#22c55e" },
    failed:    { color: "#ef4444" },
    stopped:   { color: "#ef4444" },
    queued:    { color: "#9fb0c8" },
  };
  const c = map[status] || map.queued;
  return <span style={{ fontSize: 12, padding: "2px 9px", borderRadius: 20, border: `1px solid ${c.color}`, color: c.color }}>{status || "—"}</span>;
}

function Chip({ children, completed }) {
  const color = completed ? "#22c55e" : "#9fb0c8";
  return <span style={{ fontSize: 11, border: `1px solid ${color}`, borderRadius: 16, padding: "1px 8px", color, marginLeft: 6 }}>{children}</span>;
}

function Helper({ title, children }) {
  return (
    <div style={{ border: "1px dashed #23364e", borderRadius: 8, padding: 8, marginTop: 8 }}>
      <strong style={{ display: "block", fontSize: 12, marginBottom: 4, color: "#e6edf7", fontWeight: 600 }}>{title}</strong>
      <div style={{ fontSize: 12, color: "#9fb0c8" }}>{children}</div>
    </div>
  );
}

function Pre({ children, style }) {
  return (
    <pre style={{ background: "#091121", border: "1px solid #23364e", padding: 8, borderRadius: 8, maxHeight: 260, overflow: "auto", whiteSpace: "pre-wrap", margin: 0, fontFamily: "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace", fontSize: 12, color: "#9fb0c8", ...style }}>
      {children}
    </pre>
  );
}

function Label({ children }) {
  return <label style={{ display: "block", fontSize: 12, color: "#9fb0c8", marginTop: 8, marginBottom: 4 }}>{children}</label>;
}

function Input(props) {
  return <input {...props} style={{ width: "100%", padding: "8px 10px", borderRadius: 8, border: "1px solid #23364e", background: "#0d1626", color: "#e6edf7", fontFamily: "inherit", fontSize: 13, boxSizing: "border-box", ...props.style }} />;
}
function Select(props) {
  return <select {...props} style={{ width: "100%", padding: "8px 10px", borderRadius: 8, border: "1px solid #23364e", background: "#0d1626", color: "#e6edf7", fontFamily: "inherit", fontSize: 13, boxSizing: "border-box", ...props.style }}>{props.children}</select>;
}
function Button({ children, onClick, variant, style, autoWidth }) {
  const base = { cursor: "pointer", padding: "8px 12px", borderRadius: 8, color: "#e6edf7", fontFamily: "inherit", fontSize: 13, width: autoWidth ? "auto" : "100%", boxSizing: "border-box" };
  const variants = {
    primary: { background: "#0c3342", border: "1px solid #15607d" },
    ghost:   { background: "transparent", border: "1px solid #23364e", color: "#9fb0c8" },
    danger:  { background: "#2a0f12", border: "1px solid #ef4444", color: "#ef4444" },
  };
  return <button onClick={onClick} style={{ ...base, ...(variants[variant || "primary"]), ...style }} onMouseEnter={e => e.currentTarget.style.filter = "brightness(1.12)"} onMouseLeave={e => e.currentTarget.style.filter = ""}>{children}</button>;
}

Object.assign(window, { Panel, StatusPill, Chip, Helper, Pre, Label, Input, Select, Button });
