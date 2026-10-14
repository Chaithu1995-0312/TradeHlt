"""Full divergence-branch report (trunk | branches) for trend, volatility, momentum and volume on XAUUSD H4."""
import json, html, os

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
D = json.load(open(os.path.join(ROOT, "results", "divergence_h4.json"), encoding="utf-8"))
OUT = os.path.join(ROOT, "results", "branch_mockup_rsi.html")    # same file -> same artifact URL
esc = html.escape
W = D["window"]; NB = len(W["c"]); F = D["features"]; NE = D["rows"]
GROUPS = [("trend", "Trend / EMA"), ("volatility", "Volatility"), ("momentum", "Momentum"), ("volume", "Volume"),
          ("session", "Session / time"), ("structure", "Sweeps / structure"), ("displacement", "Displacement / retest"), ("liquidity", "Liquidity"), ("smc", "SMC zones"), ("rejection", "Rejection blocks"), ("ohlcv", "Raw OHLCV"), ("crt", "CRT state resolver")]
FLAGS01 = {"swing_high", "swing_low", "higher_high", "lower_low", "higher_low", "lower_high", "sideways", "sweep_detected", "double_sweep",
           "order_block_present", "fvg_present", "breaker_present", "mitigation_block_present", "eqh_present", "eql_present",
           "rejection_bull_present", "rejection_bear_present"}
SIGNED = {"break_of_structure", "liquidity_sweep", "change_of_character"}
DISCRETE = {"trend_bias", "volatility_regime", "volume_spike", "hour_of_day", "session", "candles_since_sweep", "crt_state_resolved"} | FLAGS01 | SIGNED
CRT_NAMES = D.get("state_orders", {}).get("crt_state_resolved", [])
SESSION_NAMES = {0: "ASIA", 1: "LONDON", 2: "NY", 3: "OVERLAP", 4: "CLOSED"}
KIND_LABEL = {"definition": "Definition", "implementation": "Implementation", "data": "Data"}

def fmtv(v):
    if v is None or v != v: return "–"
    a = abs(v)
    if a >= 1000: return f"{v:,.0f}"
    if a >= 100: return f"{v:,.1f}"
    if a >= 1: return f"{v:.2f}"
    if a >= 0.01: return f"{v:.3f}"
    if a == 0: return "0"
    return f"{v:.2e}"

def agrees(m, p, col):
    if m is None or p is None or m != m or p != p: return False
    return m == p if col in DISCRETE else abs(m - p) <= max(1e-6 * abs(p), 1e-6)
assert not agrees(1.0001, 1.0, "atr") and agrees(1.0, 1.0, "atr")      # the checklist can fail

def chart(col, lines, dots=None, mask=None, candles=True, label=""):
    Wd = 340; top_h = 86 if candles else 0; gap = 8 if candles else 4; bot_h = 104; lab = 15
    H = top_h + gap + bot_h + lab
    x0, x1 = 6, Wd - (58 if col == "session" else 76 if col == "crt_state_resolved" else 40); step = (x1 - x0) / NB
    xs = [x0 + step * (i + 0.5) for i in range(NB)]
    out = []
    if candles:
        hi, lo = max(W["h"]), min(W["l"]); yp = lambda p: 4 + (hi - p) / (hi - lo) * (top_h - 8)
        for i in range(NB):
            o, h, l, c = W["o"][i], W["h"][i], W["l"][i], W["c"][i]; k = "up" if c >= o else "dn"
            t, b = yp(max(o, c)), yp(min(o, c))
            out.append(f'<line x1="{xs[i]:.1f}" y1="{yp(h):.1f}" x2="{xs[i]:.1f}" y2="{yp(l):.1f}" class="wk {k}"/>'
                       f'<rect x="{xs[i]-step*0.32:.1f}" y="{t:.1f}" width="{step*0.64:.1f}" height="{max(b-t,0.8):.1f}" class="bd {k}"/>')
    vals = [v for s, _ in lines for v in s if v == v] + ([v for v in dots if v == v] if dots else [])
    vmin, vmax = (min(vals), max(vals)) if vals else (0, 1)
    guides = []
    if col == "rsi_14": vmin, vmax, guides = 0.0, 100.0, [30.0, 70.0]
    elif col in ("volatility_regime",): vmin, vmax, guides = -0.3, 2.3, [0.0, 1.0, 2.0]
    elif col in ("trend_bias",): vmin, vmax, guides = -1.3, 1.3, [-1.0, 0.0, 1.0]
    elif col == "volume_spike" or col in FLAGS01: vmin, vmax, guides = -0.2, 1.2, [0.0, 1.0]
    elif col in SIGNED: vmin, vmax, guides = -1.3, 1.3, [-1.0, 0.0, 1.0]
    elif col == "session": vmin, vmax, guides = -0.4, 4.4, [0.0, 1.0, 2.0, 3.0, 4.0]
    elif col == "hour_of_day": vmin, vmax, guides = -1.0, 24.0, [0.0, 6.0, 12.0, 18.0]
    elif col == "crt_state_resolved":
        used = sorted({int(v) for s, _ in lines for v in s if v == v})
        vmin, vmax, guides = min(used) - 0.4, max(used) + 0.4, [float(u) for u in used]
    else:
        pad = (vmax - vmin) * 0.08 or 1.0; vmin, vmax = vmin - pad, vmax + pad
        if vmin < 0 < vmax: guides = [0.0]
        if col == "volatility_ratio" and vmin < 1 < vmax: guides.append(1.0)
    by = top_h + gap; yv = lambda v: by + (vmax - v) / (vmax - vmin) * bot_h
    out.append(f'<rect x="{x0}" y="{by}" width="{x1-x0}" height="{bot_h}" class="panel"/>')
    if mask:
        for i, m in enumerate(mask):
            if m: out.append(f'<rect x="{xs[i]-step/2:.1f}" y="{by}" width="{step:.1f}" height="{bot_h}" class="zdiff"><title>{esc(W["ts"][i][:16])}: decision reading differs</title></rect>')
    for g in guides:
        lab = (SESSION_NAMES.get(int(g), "") if col == "session" else f"{int(g):02d}h" if col == "hour_of_day"
               else CRT_NAMES[int(g)] if col == "crt_state_resolved" and int(g) < len(CRT_NAMES) else fmtv(g))
        out.append(f'<line x1="{x0}" y1="{yv(g):.1f}" x2="{x1}" y2="{yv(g):.1f}" class="guide"/><text x="{x1+4}" y="{yv(g)+3:.1f}" class="ax">{esc(lab)}</text>')
    if not guides or col not in ({"rsi_14", "volatility_regime", "trend_bias", "volume_spike", "session", "hour_of_day", "crt_state_resolved"} | FLAGS01 | SIGNED):
        out.append(f'<text x="{x1+4}" y="{by+9}" class="ax">{fmtv(vmax)}</text><text x="{x1+4}" y="{by+bot_h}" class="ax">{fmtv(vmin)}</text>')
    step_kind = col in DISCRETE
    for series, cls in lines:
        if step_kind:
            pts = " ".join(f"{xs[i]-step/2:.1f},{yv(v):.1f} {xs[i]+step/2:.1f},{yv(v):.1f}" for i, v in enumerate(series) if v == v)
        else:
            pts = " ".join(f"{xs[i]:.1f},{yv(v):.1f}" for i, v in enumerate(series) if v == v)
        out.append(f'<polyline points="{pts}" class="{cls}"/>')
    if dots:
        out += [f'<circle cx="{xs[i]:.1f}" cy="{yv(v):.1f}" r="1.5" class="dot"/>' for i, v in enumerate(dots) if v == v]
    out.append(f'<text x="{x0}" y="{H-3}" class="ax">{esc(W["ts"][0][:10])}</text><text x="{x1}" y="{H-3}" class="ax" text-anchor="end">{esc(W["ts"][-1][:16])}</text>')
    return f'<svg viewBox="0 0 {Wd} {H}" class="chart" role="img" aria-label="{esc(label)}">{"".join(out)}</svg>'

def checklist(col, f):
    rows = []
    for i in range(NB - 1, -1, -1):
        m, p = f["window_mine"][i], f["window_pipe"][i]; ok = agrees(m, p, col)
        d = "" if (m != m or p != p) else (str(int(m != p)) if col in DISCRETE else f"{abs(m-p):.1e}")
        rows.append(f'<tr class="{"" if ok else "badrow"}"><th scope="row">{esc(W["ts"][i][:16])}</th><td>{fmtv(m)}</td><td>{fmtv(p)}</td><td>{d}</td><td class="{"ok" if ok else "bad"}">{"✓" if ok else "✗"}</td></tr>')
    t = f["trunk"]; nbad = t["mismatch_count"]
    first = ""
    if nbad:
        first = ("<p class='warn'>First mismatching bars across all " + f"{NE:,}:</p><div class='tw'><table><tbody>" +
                 "".join(f'<tr class="badrow"><th scope="row">{esc(x["ts"][:16])}</th><td>{fmtv(x["mine"])}</td><td>{fmtv(x["pipe"])}</td><td class="bad">✗</td></tr>' for x in t["mismatch_first"][:10]) +
                 "</tbody></table></div>")
    win_ok = sum(agrees(f["window_mine"][i], f["window_pipe"][i], col) for i in range(NB))
    return (f'<details><summary>Per-bar checklist: {win_ok} of {NB} drawn bars ✓ · {nbad:,} of {NE:,} differ</summary>{first}'
            f'<div class="tw"><table><thead><tr><th>bar</th><th>recompute</th><th>pipeline</th><th>diff</th><th></th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></details>')

def refs_html(f):
    r = f["refs"]
    if not r: return '<p class="refs">No other source file references this column.</p>'
    return (f'<details class="refs"><summary>Referenced by {len(r)} source files (grep for the column name; use not traced)</summary>'
            f'<p>{", ".join(f"<code>{esc(x)}</code>" for x in r)}</p></details>')

def decision_panel(b):
    if b.get("follows"):
        return (f'<div class="decision follow" data-follows="{esc(b["follows"])}"><strong>Decision</strong>'
                f'<p class="current" data-current-for="{esc(b["follows"])}">Decided with <code>{esc(b["follows"])}</code>: loading…</p></div>')
    bid = esc(b["id"]); kind = b["kind"]
    names = {"definition": ("Keep registered", "Adopt branch", "Needs research"),
             "implementation": ("Accept as is", "Fix implementation", "Needs research"),
             "data": ("Accept caveat", "Fix the data", "Needs research")}[kind]
    opts = "".join(f'<label><input type="radio" name="c-{bid}" value="{v}"><span>{esc(t)}</span></label>'
                   for v, t in zip(("keep_trunk", "adopt_branch", "research"), names))
    return (f'<div class="decision" data-branch="{bid}" data-kind="{kind}" aria-live="polite"><strong>Decision for {bid}</strong>'
            f'<p class="current" data-current-for="{bid}">Loading the saved decision…</p>'
            f'<div class="choices" role="radiogroup" aria-label="Decision for {bid}">{opts}</div>'
            f'<label class="status" for="n-{bid}">Reason (saved with your pick)</label>'
            f'<textarea id="n-{bid}" maxlength="1000" placeholder="Why this choice?"></textarea>'
            f'<div class="row"><button type="button" class="save" disabled>Save decision</button><span class="status msg"></span></div>'
            f'<details><summary>Decision history</summary><ul class="hist"><li class="meta">No decisions recorded yet.</li></ul></details></div>')

def branch_panel(col, f, b):
    lines = [(f["window_pipe"], "trunk faint")]
    if b.get("window"): lines.append((b["window"], "branch"))
    ch = chart(col, lines, mask=b.get("window_mask"), candles=False, label=f"{col}: trunk and branch {b['id']}") if b.get("window") else ""
    stats = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in b["stats"].items())
    key = ('<div class="keyrow"><span><i class="kl brl"></i>branch</span><span><i class="kl trl"></i>registered</span>'
           '<span><i class="kl zl"></i>decision reading differs</span></div>') if b.get("window") else ""
    return (f'<div class="col branch-col k-{b["kind"]}"><span class="coltag">Branch · {KIND_LABEL[b["kind"]]} · {esc(b["title"])}</span>'
            f'<code class="formula">{esc(b["formula"])}</code>{ch}{key}<dl class="facts">{stats}</dl>'
            f'{f"<p class=note>{esc(b["note"])}</p>" if b.get("note") else ""}{decision_panel(b)}</div>')

def trunk_status(col, f):
    t = f["trunk"]
    if t["mismatch_count"] == 0:
        return f'<span class="ok">✓</span> {NE:,} of {NE:,} bars, largest difference {fmtv(t["max_abs_diff"])}'
    return (f'<span class="bad">✗</span> {t["mismatch_count"]:,} of {NE:,} bars outside 1-in-a-million, largest difference '
            f'{fmtv(t["max_abs_diff"])}. See the implementation branch below.')

def feature_block(col):
    f = F[col]
    trunk = (f'<div class="col trunk-col"><span class="coltag">Trunk · registered</span>'
             f'<code class="formula">{esc(f["registered"] or "")}</code><p class="plain">{esc(f["plain"])}</p>'
             f'{chart(col, [(f["window_pipe"], "trunk")], dots=f["window_mine"], label=col + " pipeline line and recompute dots")}'
             f'<div class="keyrow"><span><i class="kl trl2"></i>pipeline</span><span><i class="dk"></i>recompute from OHLC</span></div>'
             f'<dl class="facts"><dt>Pipeline vs recompute</dt><dd>{trunk_status(col, f)}</dd></dl>{checklist(col, f)}{refs_html(f)}</div>')
    opened = [b for b in f["branches"] if b["open"]]
    closed = [b for b in f["branches"] if not b["open"]]
    def closed_head(b):
        if b.get("resolved"):
            return f'<span class="chip c-decided">resolved</span> {KIND_LABEL[b["kind"]]} · {esc(b["title"])} ({esc(b["decision_label"])})'
        return f'<span class="chip c-closed">closed</span> {KIND_LABEL[b["kind"]]} · {esc(b["title"])}: 0 bars change ({esc(b["decision_label"])})'
    closed_html = "".join(
        f'<details class="closed"><summary>{closed_head(b)}</summary>'
        f'<code class="formula">{esc(b["formula"])}</code><dl class="facts">{"".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in b["stats"].items())}</dl>'
        f'{f"<p class=note>{esc(b["note"])}</p>" if b.get("note") else ""}</details>' for b in closed)
    branches = "".join(branch_panel(col, f, b) for b in opened)
    wide = "cols" if opened else "cols single"
    return (f'<section class="feature" id="{esc(f["fm"])}"><div class="fhead"><span class="fmid">{esc(f["fm"])}</span><h3>{esc(col)}</h3>'
            f'{"".join(f"<span class=\"chip c-{b["kind"]}\">{KIND_LABEL[b["kind"]]} branch open</span>" for b in opened)}</div>'
            f'<div class="{wide}">{trunk}{"<div class=bstack>" + branches + "</div>" if opened else ""}</div>{closed_html}</section>')

# summary table
srows = []
for g, _ in GROUPS:
    for col, f in F.items():
        if f["group"] != g: continue
        opened = [b for b in f["branches"] if b["open"]]
        chips = "".join(f'<span class="chip c-{b["kind"]}">{esc(b["id"])}</span>' for b in opened) or '<span class="muted">none</span>'
        decs = " ".join(f'<span class="chip c-open" data-sum-for="{esc(b.get("follows") or b["id"])}">…</span>' for b in opened) or '<span class="muted">–</span>'
        t = f["trunk"]
        tr = f'<span class="ok">✓</span> {NE:,}' if t["mismatch_count"] == 0 else f'<span class="bad">✗</span> {t["mismatch_count"]:,} differ'
        srows.append(f'<tr><td><a href="#{esc(f["fm"])}">{esc(f["fm"])}</a></td><td><code>{esc(col)}</code></td><td>{esc(g)}</td><td>{tr}</td><td>{chips}</td><td>{decs}</td></tr>')

n_open = sum(1 for f in F.values() for b in f["branches"] if b["open"] and not b.get("follows"))
n_follow = sum(1 for f in F.values() for b in f["branches"] if b["open"] and b.get("follows"))
n_closed = sum(1 for f in F.values() for b in f["branches"] if not b["open"])
PB = D["page_data_branch"]
pbs = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in PB["stats"].items())
sections = "".join(
    f'<h2 id="g-{g}">{esc(title)}</h2>' + "".join(feature_block(col) for col, f in F.items() if f["group"] == g) for g, title in GROUPS)
docgaps = "".join(f'<li><code>{esc(x["where"])}</code>: {esc(x["text"])}</li>' for x in D["doc_gaps"])

def pattern_chart(CW, p):
    """Month of candles; filled dot above = registered rule fires, ring below = card rule fires, band = they differ."""
    nb = len(CW["c"]); Wd, H = 680, 170; x0, x1 = 6, Wd - 6; step = (x1 - x0) / nb
    xs = [x0 + step * (i + 0.5) for i in range(nb)]
    hi, lo = max(CW["h"]), min(CW["l"]); yp = lambda v: 14 + (hi - v) / (hi - lo) * (H - 44)
    out = []
    for i in range(nb):
        r, k_ = p["repo_mask"][i], p["card_mask"][i]
        if r != k_: out.append(f'<rect x="{xs[i]-step/2:.1f}" y="4" width="{step:.1f}" height="{H-26}" class="zdiff"><title>{esc(CW["ts"][i])}: registered {int(r)}, card {int(k_)}</title></rect>')
    for i in range(nb):
        o, h, l, c = CW["o"][i], CW["h"][i], CW["l"][i], CW["c"][i]; k = "up" if c >= o else "dn"
        t, b = yp(max(o, c)), yp(min(o, c))
        out.append(f'<line x1="{xs[i]:.1f}" y1="{yp(h):.1f}" x2="{xs[i]:.1f}" y2="{yp(l):.1f}" class="wk {k}"/>'
                   f'<rect x="{xs[i]-step*0.32:.1f}" y="{t:.1f}" width="{step*0.64:.1f}" height="{max(b-t,0.8):.1f}" class="bd {k}"/>')
        if p["repo_mask"][i]: out.append(f'<circle cx="{xs[i]:.1f}" cy="{yp(h)-5:.1f}" r="2.6" class="mk-repo"><title>{esc(CW["ts"][i])}: registered rule</title></circle>')
        if p["card_mask"][i]: out.append(f'<circle cx="{xs[i]:.1f}" cy="{yp(l)+5:.1f}" r="2.6" class="mk-card"><title>{esc(CW["ts"][i])}: card rule</title></circle>')
    out.append(f'<text x="{x0}" y="{H-4}" class="ax">{esc(CW["ts"][0])}</text><text x="{x1}" y="{H-4}" class="ax" text-anchor="end">{esc(CW["ts"][-1])} UTC</text>')
    return f'<svg viewBox="0 0 {Wd} {H}" class="chart" role="img" aria-label="{esc(p["title"])}: registered vs card hits">{"".join(out)}</svg>'

def candle_images_section():
    CI = D.get("candle_images")
    if not CI: return ""
    CW = CI["window"]; blocks = []; srow = []
    for p in CI["patterns"]:
        tr = (f'<span class="ok">✓</span> recompute = pipeline on {CI["bars"]} of {CI["bars"]} month bars and {p["trunk_all_bars"]:,} of {p["trunk_all_bars"]:,} in the file'
              if p["trunk_month_mismatch"] == 0 and p["trunk_all_mismatch"] == 0 else f'<span class="bad">✗</span> {p["trunk_month_mismatch"]} month bars differ')
        facts = (f"<dt>Registered fires</dt><dd>{p['repo_hits']} bars</dd><dt>Card rule fires</dt><dd>{p['card_hits']} bars</dd>"
                 f"<dt>Both</dt><dd>{p['both']}</dd><dt>Registered only</dt><dd>{p['repo_only']}</dd><dt>Card only</dt><dd>{p['card_only']}</dd>"
                 f"<dt>Whole file ({p['trunk_all_bars']:,} bars)</dt><dd>registered {p['all_repo_hits']}, card {p['all_card_hits']}, differ on {p['all_diff']}</dd>")
        diffs = "".join(f'<tr><th scope="row">{esc(x["ts"])}</th><td>{x["repo"]}</td><td>{x["card"]}</td></tr>' for x in p["diff_bars"])
        dtab = (f'<details><summary>{len(p["diff_bars"])} bars where they differ this month</summary><div class="tw"><table><thead><tr><th>bar (UTC)</th><th>registered</th><th>card</th></tr></thead><tbody>{diffs}</tbody></table></div></details>'
                if p["diff_bars"] else "")
        bid = f'card-{p["col"]}'
        dec = decision_panel({"id": bid, "kind": "definition"}) if p["open"] else '<p class="note">Same bars fire under both rules this month: nothing to decide.</p>'
        blocks.append(
            f'<section class="feature" id="ci-{esc(p["col"])}"><div class="fhead"><span class="fmid">{esc(p["fm"])}</span><h3>{esc(p["title"])}</h3>'
            f'<span class="chip c-data">card {esc(p["card"])}</span>{"<span class=\"chip c-definition\">Definition branch open</span>" if p["open"] else "<span class=\"chip c-closed\">same bars</span>"}</div>'
            f'{pattern_chart(CW, p)}<div class="keyrow"><span><i class="dk"></i>registered rule fires (above)</span><span><i class="kl brl"></i>card rule fires (ring below)</span><span><i class="kl zl"></i>they differ</span></div>'
            f'<div class="cols"><div class="col trunk-col"><span class="coltag">Trunk · registered {esc(p["fm"])}</span><code class="formula">{esc(p["registered"] or "")}</code>'
            f'<dl class="facts"><dt>Pipeline vs recompute</dt><dd>{tr}</dd></dl></div>'
            f'<div class="bstack"><div class="col branch-col k-definition"><span class="coltag">Branch · Candle Images workflow · card {esc(p["card"])}</span>'
            f'<code class="formula">{esc(p["card_rule"])}</code><p class="note">{esc(p["card_change"])}</p><dl class="facts">{facts}</dl>{dtab}{dec}</div></div></div></section>')
        srow.append(f'<tr><td><a href="#ci-{esc(p["col"])}">{esc(p["fm"])}</a></td><td>{esc(p["title"])}</td><td>{esc(p["card"])}</td><td>{p["repo_hits"]}</td><td>{p["card_hits"]}</td><td>{p["repo_only"]}</td><td>{p["card_only"]}</td></tr>')
    return (f'<h2 id="g-candle-images">Candle Images workflow</h2>'
            f'<p class="lede">A parallel branch built from the study cards in <code>docs/reference/candle_theory/</code>. Each card rule is put beside the registered pattern on the last month of H4 bars, {esc(CI["from"])} to {esc(CI["to"])} UTC ({CI["bars"]} bars). The cards give no numbers, so a card rule keeps the registered thresholds and changes only what the card draws or says. "Downtrend" / "uptrend" = the previous close is below / above the close {CI["lookback"]} bars earlier (the registered swing lookback). The cards are teaching material: a pick here chooses a definition, not a trade.</p>'
            f'<div class="summary"><table><thead><tr><th>FM</th><th>Pattern</th><th>Card</th><th>Registered</th><th>Card rule</th><th>Registered only</th><th>Card only</th></tr></thead><tbody>{"".join(srow)}</tbody></table></div>'
            + "".join(blocks))

CSS = open(os.path.join(_HERE, "divergence.css"), encoding="utf-8").read() + \
    "\n.mk-repo{fill:var(--accent)} .mk-card{fill:none;stroke:var(--branch);stroke-width:1.6}\n"
JS = open(os.path.join(_HERE, "divergence.js"), encoding="utf-8").read()

page = f"""<title>Divergence Branches</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@600;700&family=Source+Sans+3:wght@400;600&family=JetBrains+Mono:wght@400;500&display=swap">
<style>{CSS}</style>
<div class="wrap">
  <header style="display:grid;gap:8px">
    <div class="eyebrow">Tradelatest · feature audit · XAUUSD H4</div>
    <h1>Divergence Branches</h1>
    <p class="lede">Each feature has a <b>trunk</b>: its registered formula, recomputed independently from OHLC and compared with the feature pipeline on all {NE:,} bars. A <b>branch</b> opens beside it when a different definition, the implementation, or the data would change something a decision reads: a zone, flag, regime, sign or threshold class. Audit both and record a pick. A pick changes no code; each adopted branch becomes its own approved change.</p>
  </header>

  <div class="tiles">
    <div><b>{len(F)}</b><span>features checked ({", ".join(t for g, t in GROUPS if any(f["group"] == g for f in F.values()))})</span></div>
    <div><b>{n_open}</b><span>branches open for a decision</span></div>
    <div><b>{n_follow}</b><span>open branches that follow the ATR decision</span></div>
    <div><b>{n_closed}</b><span>branches closed: no decision reading changes</span></div>
  </div>

  <div class="kinds" aria-label="Branch kinds">
    <div class="kind k-implementation"><b>Implementation</b>The pipeline does not equal its own registered formula. A bug candidate.</div>
    <div class="kind k-definition"><b>Definition</b>The registered formula differs from a textbook or TradingView definition. A choice.</div>
    <div class="kind k-data"><b>Data</b>The input data, not the formula: clock, source, meaning.</div>
  </div>

  <section class="feature k-data-row" id="h4-clock">
    <div class="fhead"><span class="chip c-data">Data branch · whole page</span><h3>{esc(PB["title"])}</h3></div>
    <div class="cols"><div class="col"><dl class="facts">{pbs}</dl><p class="note">{esc(PB["options"])}</p></div>
    <div class="bstack"><div class="col branch-col k-data">{decision_panel({"id": PB["id"], "kind": "data"})}</div></div></div>
  </section>

  <section style="display:grid;gap:8px">
    <h2>Summary</h2>
    <div class="summary"><table>
      <thead><tr><th>FM</th><th>Feature</th><th>Group</th><th>Trunk</th><th>Open branches</th><th>Decision</th></tr></thead>
      <tbody>{"".join(srows)}</tbody></table></div>
    <p class="note">Documentation gaps found on the way (no decision needed, fix with the next change to that file): </p><ul class="note">{docgaps}</ul>
  </section>

  {candle_images_section()}

  {sections}

  <footer>Data: <code>data/mt5/XAUUSD_H4.csv</code>, times converted to UTC through its declared clock (<code>mt5_icmarkets_xau</code>), then <code>FeaturePipeline(timeframe="H4")</code>, active config <code>{esc(D.get("active_version", "?"))}</code> (from <code>configs/production/ACTIVE_VERSION</code>). The pipeline's windows are bar counts tuned for M15, so on H4 they span about four times as long. Charts show the 60 bars ending {esc(W["ts"][-1][:16])} UTC; counts cover all {NE:,} bars. Charts are inline SVG generated by script from these numbers, not images. Reviewed by Claude (claude-opus-5-5), 2026-10-14.</footer>
</div>
<script>{JS}</script>
"""
open(OUT, "w", encoding="utf-8").write(page)
print("wrote", OUT, len(page), "open", n_open, "follow", n_follow, "closed", n_closed)
