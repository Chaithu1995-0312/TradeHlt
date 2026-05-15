// Tiny inline-SVG sparkline. Renders a 80×24 polyline + filled area.
function Sparkline({ points, color }) {
  if (!points || points.length < 2) return null;
  const w = 80, h = 24, pad = 2;
  const xs = points.map(p => p.t);
  const ys = points.map(p => p.v);
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const yMin = Math.min(...ys), yMax = Math.max(...ys);
  const xRange = xMax - xMin || 1;
  const yRange = yMax - yMin || 1;
  const fx = (x) => pad + ((x - xMin) / xRange) * (w - pad * 2);
  const fy = (y) => h - pad - ((y - yMin) / yRange) * (h - pad * 2);
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${fx(p.t).toFixed(1)},${fy(p.v).toFixed(1)}`).join(" ");
  const area = `${path} L${fx(xMax).toFixed(1)},${h - pad} L${fx(xMin).toFixed(1)},${h - pad} Z`;
  const c = color || "#0ea5a3";
  const last = points[points.length - 1];
  return (
    <svg width={w} height={h} style={{ display: "block" }} viewBox={`0 0 ${w} ${h}`}>
      <path d={area} fill={c} opacity="0.12" />
      <path d={path} fill="none" stroke={c} strokeWidth="1.25" />
      <circle cx={fx(last.t)} cy={fy(last.v)} r="1.6" fill={c} />
    </svg>
  );
}
window.Sparkline = Sparkline;
