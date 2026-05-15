// Shared monitor-value formatter matching server.py's fmtMonitorValue() exactly,
// plus support for `duration` and `int` formats.

function fmtMonitorValue(f) {
  if (!f) return "—";
  if (f.error) return React.createElement("span", { title: f.error, style: { color: "#ef4444", fontSize: 11 } }, "err");
  const v = f.value;
  if (v === null || v === undefined) return "—";
  const unit = f.unit ? ` ${f.unit}` : "";
  if (f.format === "float" && typeof v === "number") return `${v.toFixed(4)}${unit}`;
  if (f.format === "int" && typeof v === "number") return `${v.toLocaleString()}${unit}`;
  if (f.format === "duration" && typeof v === "number") {
    const s = Math.max(0, Math.floor(v));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    if (h > 0) return `${h}h ${m}m ${sec}s`;
    if (m > 0) return `${m}m ${sec}s`;
    return `${sec}s`;
  }
  if (f.format === "timestamp" && typeof v === "string") {
    return v.replace("T", " ").replace(/\..*/, "") + " UTC";
  }
  return `${v}${unit}`;
}

window.fmtMonitorValue = fmtMonitorValue;
