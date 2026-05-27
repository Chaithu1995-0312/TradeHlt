// CRT Dashboard chart primitives — all inline SVG, no deps.

function DonutChart({ segments, size = 150, thickness = 22, centerLabel, centerSub }) {
  const total = segments.reduce((a, s) => a + s.value, 0);
  const r = size / 2 - thickness / 2;
  const cx = size / 2, cy = size / 2;
  const C = 2 * Math.PI * r;
  let offset = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1e2a44" strokeWidth={thickness} />
      {segments.map((s, i) => {
        const frac = total === 0 ? 0 : s.value / total;
        const len = C * frac;
        const dash = `${len} ${C - len}`;
        const el = (
          <circle key={i}
            cx={cx} cy={cy} r={r} fill="none"
            stroke={s.color} strokeWidth={thickness}
            strokeDasharray={dash}
            strokeDashoffset={-offset}
            transform={`rotate(-90 ${cx} ${cy})`}
          />
        );
        offset += len;
        return el;
      })}
      {centerLabel && (
        <text x={cx} y={cy - 2} textAnchor="middle" fontSize="22" fontWeight="800" fill="#e6edf7" fontFamily="Inter, system-ui">
          {centerLabel}
        </text>
      )}
      {centerSub && (
        <text x={cx} y={cy + 16} textAnchor="middle" fontSize="10" fill="#7f8da6">
          {centerSub}
        </text>
      )}
    </svg>
  );
}

function LineChart({ values, data, width = 380, height = 150, color = "#22d3ee", areaFill = "#22d3ee", padding = { l: 28, r: 12, t: 8, b: 22 }, yTicks = 4, xLabels = [], showYAxis = true, showGrid = true }) {
  // Accept either `values` or `data` prop for backward-compat
  const pts = (values || data || []);
  if (!pts.length) return <svg width="100%" height={height} />;
  const { l, r, t, b } = padding;
  const innerW = width - l - r;
  const innerH = height - t - b;
  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const yMin = min - (max - min) * 0.08;
  const yMax = max + (max - min) * 0.08;
  const fx = (i) => l + (i / (pts.length - 1)) * innerW;
  const fy = (v) => t + (1 - (v - yMin) / (yMax - yMin)) * innerH;
  const path = pts.map((v, i) => `${i === 0 ? "M" : "L"}${fx(i).toFixed(1)},${fy(v).toFixed(1)}`).join(" ");
  const area = `${path} L${fx(pts.length - 1).toFixed(1)},${t + innerH} L${fx(0).toFixed(1)},${t + innerH} Z`;
  // y ticks
  const ticks = [];
  for (let i = 0; i <= yTicks; i++) {
    const v = yMin + (i / yTicks) * (yMax - yMin);
    ticks.push({ v, y: fy(v) });
  }
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      {showGrid && ticks.map((tk, i) => (
        <line key={i} x1={l} x2={l + innerW} y1={tk.y} y2={tk.y} stroke="#1e2a44" strokeDasharray="2 3" />
      ))}
      <defs>
        <linearGradient id={`lg-${color.replace("#","")}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={areaFill} stopOpacity="0.30" />
          <stop offset="100%" stopColor={areaFill} stopOpacity="0.00" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#lg-${color.replace("#","")})`} />
      <path d={path} fill="none" stroke={color} strokeWidth="1.6" />
      {showYAxis && ticks.map((tk, i) => (
        <text key={i} x={l - 4} y={tk.y + 3} textAnchor="end" fontSize="10" fill="#7f8da6">
          {Number.isInteger(tk.v) ? tk.v : tk.v.toFixed(1)}
        </text>
      ))}
      {xLabels.map((lab, i) => {
        const x = l + (i / (xLabels.length - 1)) * innerW;
        return <text key={i} x={x} y={height - 4} textAnchor="middle" fontSize="10" fill="#7f8da6">{lab}</text>;
      })}
    </svg>
  );
}

function DrawdownChart({ values, width = 380, height = 150, color = "#ef4444", padding = { l: 28, r: 12, t: 8, b: 22 } }) {
  const { l, r, t, b } = padding;
  const innerW = width - l - r;
  const innerH = height - t - b;
  const min = Math.min(...values, -1);
  const fx = (i) => l + (i / (values.length - 1)) * innerW;
  const fy = (v) => t + (1 - (v - min) / (0 - min)) * innerH;
  const path = values.map((v, i) => `${i === 0 ? "M" : "L"}${fx(i).toFixed(1)},${fy(v).toFixed(1)}`).join(" ");
  const area = `${path} L${fx(values.length - 1).toFixed(1)},${fy(0).toFixed(1)} L${fx(0).toFixed(1)},${fy(0).toFixed(1)} Z`;
  const ticks = 4;
  const tickLines = [];
  for (let i = 0; i <= ticks; i++) {
    const v = min + (i / ticks) * (0 - min);
    tickLines.push({ v, y: fy(v) });
  }
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      {tickLines.map((tk, i) => (
        <line key={i} x1={l} x2={l + innerW} y1={tk.y} y2={tk.y} stroke="#1e2a44" strokeDasharray="2 3" />
      ))}
      <defs>
        <linearGradient id="dd-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={color} stopOpacity="0.10" />
          <stop offset="100%" stopColor={color} stopOpacity="0.45" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#dd-grad)" />
      <path d={path} fill="none" stroke={color} strokeWidth="1.5" />
      {tickLines.map((tk, i) => (
        <text key={i} x={l - 4} y={tk.y + 3} textAnchor="end" fontSize="10" fill="#7f8da6">{Math.round(tk.v)}</text>
      ))}
    </svg>
  );
}

function StackedBarChart({ data, colors, width = 520, height = 170, padding = { l: 32, r: 8, t: 8, b: 22 }, xLabels = [], yTicks = 5 }) {
  const { l, r, t, b } = padding;
  const innerW = width - l - r;
  const innerH = height - t - b;
  const totals = data.map(d => (d.tp || 0) + (d.sl || 0) + (d.to || 0));
  const yMax = Math.max(...totals) * 1.08;
  const barGap = 2;
  const barW = (innerW / data.length) - barGap;
  const ticks = [];
  for (let i = 0; i <= yTicks; i++) {
    const v = (i / yTicks) * yMax;
    const y = t + (1 - v / yMax) * innerH;
    ticks.push({ v, y });
  }
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      {ticks.map((tk, i) => (
        <line key={i} x1={l} x2={l + innerW} y1={tk.y} y2={tk.y} stroke="#1e2a44" strokeDasharray="2 3" />
      ))}
      {data.map((d, i) => {
        const x = l + i * (barW + barGap);
        let yCursor = t + innerH;
        const segs = [
          { v: d.tp, c: colors.tp },
          { v: d.sl, c: colors.sl },
          { v: d.to, c: colors.to },
        ];
        return segs.map((s, j) => {
          const h = (s.v / yMax) * innerH;
          yCursor -= h;
          return <rect key={`${i}-${j}`} x={x.toFixed(1)} y={yCursor.toFixed(1)} width={barW.toFixed(1)} height={h.toFixed(1)} fill={s.c} />;
        });
      })}
      {ticks.map((tk, i) => (
        <text key={i} x={l - 4} y={tk.y + 3} textAnchor="end" fontSize="10" fill="#7f8da6">
          {tk.v >= 1000 ? `${Math.round(tk.v / 1000)}K` : Math.round(tk.v)}
        </text>
      ))}
      {xLabels.map((lab, i) => {
        const idx = Math.floor((i / (xLabels.length - 1)) * (data.length - 1));
        const x = l + idx * (barW + barGap) + barW / 2;
        return <text key={i} x={x} y={height - 4} textAnchor="middle" fontSize="10" fill="#7f8da6">{lab}</text>;
      })}
    </svg>
  );
}

function VerticalBars({ items, data, maxVal, width = 380, height = 200, padding = { l: 26, r: 8, t: 24, b: 22 } }) {
  // Accept either `items` or `data` prop for backward-compat with callers using `data=`
  const rows = items || data || [];
  const { l, r, t, b } = padding;
  const innerW = width - l - r;
  const innerH = height - t - b;
  // Accept optional `maxVal` override; otherwise derive from data
  const max = maxVal != null
    ? maxVal
    : rows.length ? Math.max(...rows.map(it => Math.abs(it.value || 0))) * 1.1 : 100;
  const safeMax = max || 100;  // guard against zero
  const barW = rows.length ? (innerW / rows.length) * 0.55 : 20;
  const gap  = rows.length ? (innerW / rows.length) * 0.45 : 10;
  // Derive 4 evenly-spaced tick values from the actual max
  const tickVals = [0.25, 0.5, 0.75, 1.0].map(f => Math.round(safeMax * f));
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      {tickVals.map((v, i) => {
        const y = t + (1 - v / safeMax) * innerH;
        return (
          <g key={i}>
            <line x1={l} x2={l + innerW} y1={y} y2={y} stroke="#1e2a44" strokeDasharray="2 3" />
            <text x={l - 4} y={y + 3} textAnchor="end" fontSize="10" fill="#7f8da6">
              {v >= 1000 ? `${(v/1000).toFixed(1)}K` : v}
            </text>
          </g>
        );
      })}
      {rows.map((it, i) => {
        const x = l + i * (barW + gap) + gap / 2;
        const h = Math.max(1, (Math.abs(it.value || 0) / safeMax) * innerH);
        const y = t + innerH - h;
        return (
          <g key={i}>
            <rect x={x} y={y} width={barW} height={h} fill={it.color} rx="2" />
            <text x={x + barW / 2} y={y - 6} textAnchor="middle" fontSize="11" fontWeight="700" fill={it.color}>
              {(it.value || 0) > 0 ? "+" : ""}{(+(it.value || 0)).toFixed(it.value >= 10 ? 0 : 2)}
            </text>
            <text x={x + barW / 2} y={height - 4} textAnchor="middle" fontSize="11" fill="#7f8da6">{it.label}</text>
          </g>
        );
      })}
    </svg>
  );
}

function Scatter({ points, width = 380, height = 190, xDomain = [0, 300], yDomain = [0, 180] }) {
  const fx = (x) => 8 + ((x - xDomain[0]) / (xDomain[1] - xDomain[0])) * (width - 16);
  const fy = (y) => 8 + ((y - yDomain[0]) / (yDomain[1] - yDomain[0])) * (height - 16);
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      {points.map((p, i) => (
        <circle key={i} cx={fx(p.x).toFixed(1)} cy={fy(p.y).toFixed(1)} r="2.2" fill={p.color} opacity="0.78" />
      ))}
    </svg>
  );
}

function Heatmap({ rows, colLabels, width = 460, height = 180, cellGap = 2 }) {
  const cellW = (width - 36) / colLabels.length - cellGap;
  const cellH = (height - 22) / rows.length - cellGap;
  // Color: red below 0, green above 0, intensity scaled by abs(v)/maxAbs
  const maxAbs = Math.max(...rows.flatMap(r => r.cells.map(c => Math.abs(c))));
  const cellColor = (v) => {
    const t = Math.min(1, Math.abs(v) / maxAbs);
    if (v > 0) {
      // green scale
      const a = 0.18 + t * 0.65;
      return `rgba(34,197,94,${a.toFixed(2)})`;
    }
    const a = 0.18 + t * 0.65;
    return `rgba(239,68,68,${a.toFixed(2)})`;
  };
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      {colLabels.map((lab, ci) => (
        <text key={ci} x={36 + ci * (cellW + cellGap) + cellW / 2} y={12} textAnchor="middle" fontSize="10" fill="#7f8da6">{lab}</text>
      ))}
      {rows.map((row, ri) => (
        <g key={ri}>
          <text x={32} y={22 + ri * (cellH + cellGap) + cellH / 2 + 3} textAnchor="end" fontSize="10" fill="#7f8da6">{row.year}</text>
          {row.cells.map((c, ci) => {
            const x = 36 + ci * (cellW + cellGap);
            const y = 22 + ri * (cellH + cellGap);
            return (
              <g key={ci}>
                <rect x={x} y={y} width={cellW} height={cellH} fill={cellColor(c)} rx="2" />
                <text x={x + cellW / 2} y={y + cellH / 2 + 3} textAnchor="middle" fontSize="9" fill="#e6edf7" fontWeight="600">
                  {c >= 0 ? `+${c.toFixed(1)}` : c.toFixed(1)}
                </text>
              </g>
            );
          })}
        </g>
      ))}
    </svg>
  );
}

Object.assign(window, { DonutChart, LineChart, DrawdownChart, StackedBarChart, VerticalBars, Scatter, Heatmap });
