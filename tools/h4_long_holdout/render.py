"""Render results/h4_long_holdout/holdout.json as a per-day / per-trade HTML ledger."""
import os, json, html
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
D = json.load(open(os.path.join(ROOT, "results", "h4_long_holdout", "holdout.json"), encoding="utf-8"))
OUT = os.path.join(ROOT, "results", "h4_long_holdout", "report.html")
esc = html.escape

def inr(v, sign=True):
    s = f"{abs(v):,.0f}"
    # Indian digit grouping
    n = f"{abs(round(v)):d}"
    if len(n) > 3:
        head, tail = n[:-3], n[-3:]
        parts = []
        while len(head) > 2: parts.insert(0, head[-2:]); head = head[:-2]
        if head: parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    else:
        s = n
    return ("−" if v < 0 else ("+" if sign and v > 0 else "")) + "₹" + s

def cls(v): return "pos" if v > 0 else ("neg" if v < 0 else "zero")

def equity_svg(acct, a):
    days = a["days"]; cap = a["capital"]
    vals = [cap] + [d["equity"] for d in days]
    W, Hh, L, R, T, B = 720, 220, 64, 12, 14, 30
    lo, hi = min(vals), max(vals); pad = (hi - lo) * 0.08 or cap * 0.02; lo -= pad; hi += pad
    x = lambda i: L + (W - L - R) * i / (len(vals) - 1)
    y = lambda v: T + (Hh - T - B) * (hi - v) / (hi - lo)
    # ticks: 5 round levels
    step = (hi - lo) / 4; out = []
    for k in range(5):
        v = lo + step * k
        out.append(f'<line x1="{L}" x2="{W-R}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/><text x="{L-6}" y="{y(v)+4:.1f}" text-anchor="end" class="tick">{esc(inr(v, False))}</text>')
    out.append(f'<line x1="{L}" x2="{W-R}" y1="{y(cap):.1f}" y2="{y(cap):.1f}" class="base"/>')
    # span gap marker
    for i, d in enumerate(days, start=1):
        if d["span"] == "2" and days[i - 2]["span"] != "2":
            out.append(f'<line x1="{x(i)-0.5:.1f}" x2="{x(i)-0.5:.1f}" y1="{T}" y2="{Hh-B}" class="split"/><text x="{x(i)+4:.1f}" y="{T+10}" class="tick">Aug 8</text>')
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
    area = f"{x(0):.1f},{y(cap):.1f} " + pts + f" {x(len(vals)-1):.1f},{y(cap):.1f}"
    out.append(f'<polygon points="{area}" class="area"/><polyline points="{pts}" class="line"/>')
    for i, d in enumerate(days, start=1):
        if d["closed"]:
            out.append(f'<circle cx="{x(i):.1f}" cy="{y(d["equity"]):.1f}" r="2.6" class="{cls(d["pnl"])}dot"><title>{d["date"]}: {inr(d["pnl"])} → {inr(d["equity"], False)}</title></circle>')
    end = vals[-1]
    out.append(f'<circle cx="{x(len(vals)-1):.1f}" cy="{y(end):.1f}" r="4" class="enddot"/>')
    out.append(f'<text x="{L}" y="{Hh-8}" class="tick">{days[0]["date"]}</text><text x="{W-R}" y="{Hh-8}" text-anchor="end" class="tick">{days[-1]["date"]}</text>')
    return f'<svg viewBox="0 0 {W} {Hh}" role="img" aria-label="Account {acct} closing equity by day">{"".join(out)}</svg>'

def account_panel(acct, a, ctrl):
    s = a["summary"]; cap = a["capital"]
    tiles = [("Net result", inr(s["net"]), cls(s["net"]), f'{s["net"]/cap:+.1%} of {inr(cap, False)}'),
             ("Trades", f'{s["trades"]}', "", f'{s["wins"]} won · {s["trades"]-s["wins"]} lost ({s["wins"]/s["trades"]:.0%})'),
             ("Average trade", f'{s["mean_r"]:+.2f} R', cls(s["mean_r"]), f'risk {inr(a["budget"], False)} per trade'),
             ("Worst drop", f'{s["max_dd"]:.1%}', "neg", "from the highest closing equity"),
             ("Trading days", f'{s["green_days"]} up · {s["red_days"]} down', "", f'{s["days_traded"]} days with a closed trade'),
             ("Funding paid", inr(s["funding"]), cls(s["funding"]), "overnight swap on longs")]
    tiles_html = "".join(f'<div class="tile"><span class="lab">{esc(t)}</span><b class="{c}">{esc(v)}</b><span class="sub">{esc(sub)}</span></div>' for t, v, c, sub in tiles)
    comp = (f'<p class="note">Comparison, long on every H4 candle with the same entry, stop and target: {ctrl["trades"]} trades, '
            f'<span class="{cls(ctrl["net"])}">{inr(ctrl["net"])}</span>, worst drop {ctrl["max_dd"]:.1%}.</p>')
    rows = []
    for d in a["days"]:
        active = bool(d["opened"] or d["closed"])
        link = lambda ids: " ".join(f'<a href="#{i.lower()}">{i}</a>' for i in ids) or '<span class="mut">–</span>'
        wl = f'{d["wins"]}W {d["losses"]}L' if d["closed"] else '<span class="mut">–</span>'
        pnl = f'<span class="{cls(d["pnl"])}">{inr(d["pnl"])}</span>' if d["closed"] else '<span class="mut">–</span>'
        pos = '<span class="chip on">holding</span>' if d["in_position"] else '<span class="chip">flat</span>'
        rows.append(f'<tr class="{"act" if active else "quiet"}"><td class="mono">{d["date"]}</td><td>{d["weekday"]}</td><td>{pos}</td>'
                    f'<td class="mono">{link(d["opened"])}</td><td class="mono">{link(d["closed"])}</td><td>{wl}</td><td class="num">{pnl}</td>'
                    f'<td class="num">{inr(d["equity"], False)}</td><td class="num {"neg" if d["drawdown"] > 0 else "mut"}">{d["drawdown"]:.1%}</td></tr>')
    trows = []
    for t in a["trades"]:
        trows.append(f'<tr id="{t["id"].lower()}"><td class="mono b">{t["id"]}</td>'
                     f'<td class="mono">{t["signal"]}<span class="ist">{t["signal_ist"]} IST</span></td>'
                     f'<td class="mono">{t["entry_at"]}<span class="ist">{t["entry_ist"]} IST</span></td>'
                     f'<td class="num">{t["entry"]:,.2f}</td><td class="num">{t["stop"]:,.2f}</td><td class="num">{t["target"]:,.2f}</td><td class="num">{t["lots"]:.2f}</td>'
                     f'<td class="mono">{t["exit_at"]}<span class="ist">{t["exit_ist"]} IST</span></td>'
                     f'<td><span class="chip {"win" if t["kind"]=="Target" else "loss"}">{esc(t["kind"])}</span></td><td class="num">{t["exit_fill"]:,.2f}</td>'
                     f'<td class="num">{t["hold_h"]:.1f} h</td><td class="num">{t["nights"]}</td><td class="num {cls(t["funding_inr"])}">{inr(t["funding_inr"])}</td>'
                     f'<td class="num {cls(t["r"])}">{t["r"]:+.2f}</td><td class="num {cls(t["inr"])}">{inr(t["inr"])}</td><td class="num">{inr(t["equity"], False)}</td></tr>')
    op = a["open"]
    open_html = (f'<p class="note">Still open when the data ends (2026-10-06 19:45 broker): <b>{op["id"]}</b>, entered {op["entry_at"]} broker '
                 f'({op["entry_ist"]} IST) at {op["entry"]:,.2f}, stop {op["stop"]:,.2f}, target {op["target"]:,.2f}, {op["lots"]:.2f} lots. '
                 f'Not counted in the cash above.</p>') if op else ""
    sk = a["skipped"]; busy = sum(x["reason"] == "position already open" for x in sk); minlot = len(sk) - busy
    skip_html = f'<p class="note">Signals not taken: {busy} because a trade was already open, {minlot} because the position would be below 0.01 lot.</p>'
    return (f'<section class="acct" id="acct-{acct.lower()}" data-acct="{acct}">'
            f'<div class="tiles">{tiles_html}</div>{comp}'
            f'<figure class="chart"><figcaption>Closing equity by day · dots mark days a trade closed (green up, red down)</figcaption>{equity_svg(acct, a)}</figure>'
            f'<h2>Day by day</h2><p class="note">Every trading day in the two test windows, plus any day a trade closed after a window ended. Day P&amp;L is booked when a trade closes.</p>'
            f'<div class="tw"><table class="days"><thead><tr><th>Date (broker)</th><th>Day</th><th>Position</th><th>Opened</th><th>Closed</th><th>W / L</th><th class="num">Day P&amp;L</th><th class="num">Equity</th><th class="num">Drawdown</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            f'<h2>Every trade</h2><p class="note">Times are the MT5 broker clock, with India time under each. Prices in USD per ounce.</p>'
            f'<div class="tw"><table class="trades"><thead><tr><th>ID</th><th>Signal candle</th><th>Entry</th><th class="num">Entry</th><th class="num">Stop</th><th class="num">Target</th><th class="num">Lots</th><th>Exit</th><th>Result</th><th class="num">Exit fill</th><th class="num">Held</th><th class="num">Nights</th><th class="num">Funding</th><th class="num">R</th><th class="num">P&amp;L</th><th class="num">Equity</th></tr></thead><tbody>{"".join(trows)}</tbody></table></div>'
            f'{open_html}{skip_html}</section>')

A, B = D["accounts"]["A"], D["accounts"]["B"]; g = D["gold"]; dec = D["declaration"]
WR = json.load(open(os.path.join(ROOT, "results", "h4_long_holdout", "web_regime.json"), encoding="utf-8"))

def regime_section():
    acct_by_span = {}
    for t in A["trades"]:
        k = "1" if t["entry_at"] < "2026-07-06" else "2"
        acct_by_span.setdefault(k, []).append(t["inr"])
    res = {"1": acct_by_span.get("1", []), "2": acct_by_span.get("2", [])}
    cards = []
    for r in WR["regimes"]:
        k = "1" if "window 1" in r["window"] else ("2" if "window 2" in r["window"] else None)
        a_line = (f'<p class="res">Account A here: {len(res[k])} trades, <span class="{cls(sum(res[k]))}">{inr(sum(res[k]))}</span></p>' if k else
                  '<p class="res">Not tested: the rule was built on this stretch.</p>')
        cards.append(f'<article class="reg"><span class="lab">{esc(r["window"])}</span><h3>{esc(r["label"])}</h3>'
                     f'<dl class="facts"><dt>Websites say</dt><dd>{esc(r["web"])}</dd><dt>MT5 file shows</dt><dd>{esc(r["mt5"])}</dd>'
                     f'<dt>Agree?</dt><dd>{esc(r["agrees"])}</dd></dl>{a_line}</article>')
    src = "".join(f'<li><a href="{esc(s["url"])}" rel="noopener" target="_blank">{esc(s["name"])}</a></li>' for s in WR["sources"])
    return (f'<section class="regime"><h2>Market regime: web check</h2><p class="note">Gold\'s backdrop in each window, from public web pages scraped on {WR["scraped_on"]}, '
            f'set beside the MT5 data this test used. {esc(WR["note"])}</p><div class="regs">{"".join(cards)}</div>'
            f'<details><summary>Sources</summary><ul class="src">{src}</ul></details></section>')
CSS = """
/* Ledger layout: one column, account switch, summary tiles, equity chart, then day and trade tables. */
:root{
  --bg:#f4f6f5; --surface:#ffffff; --ink:#15201d; --ink-2:#4b5a55; --ink-3:#7a8984; --rule:#d9e0dd;
  --accent:#1d5c63; --pos:#1c7c45; --neg:#b4372a; --pos-bg:#e3f2e8; --neg-bg:#f8e4e0; --hold:#e6eef0;
  --f-display:"Archivo","Arial Narrow",system-ui,sans-serif; --f-body:"Source Sans 3","Segoe UI",system-ui,sans-serif; --f-mono:"IBM Plex Mono",ui-monospace,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#0f1514;--surface:#17201e;--ink:#e9f0ed;--ink-2:#b0bfba;--ink-3:#84948f;--rule:#2a3633;--accent:#6fb8bf;--pos:#4cc77f;--neg:#f07a69;--pos-bg:#173326;--neg-bg:#3a1e1a;--hold:#1d2b2d;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0f1514;--surface:#17201e;--ink:#e9f0ed;--ink-2:#b0bfba;--ink-3:#84948f;--rule:#2a3633;--accent:#6fb8bf;--pos:#4cc77f;--neg:#f07a69;--pos-bg:#173326;--neg-bg:#3a1e1a;--hold:#1d2b2d;color-scheme:dark}
body{background:var(--bg);color:var(--ink);font:15px/1.5 var(--f-body)}
.wrap{max-width:1180px;margin:0 auto;padding-inline:16px;padding-block:24px 48px;display:grid;gap:18px}
h1,h2{font-family:var(--f-display);margin:0;text-wrap:balance;letter-spacing:-.01em}
h1{font-size:30px;font-weight:700} h2{font-size:20px;font-weight:600;margin-top:10px}
.eyebrow{font:600 12px/1 var(--f-display);text-transform:uppercase;letter-spacing:.1em;color:var(--accent)}
.lede{color:var(--ink-2);max-width:72ch;margin:0}
.verdict{display:flex;flex-wrap:wrap;gap:10px;align-items:center;background:var(--neg-bg);border:1px solid color-mix(in srgb,var(--neg) 35%,transparent);border-radius:10px;padding:12px 14px}
.verdict b{font-family:var(--f-display);color:var(--neg);font-size:18px;letter-spacing:.04em}
.verdict span{color:var(--ink-2);min-width:0}
.switch{display:flex;gap:6px;flex-wrap:wrap}
.switch button{font:600 14px var(--f-body);padding:8px 14px;border-radius:8px;border:1px solid var(--rule);background:var(--surface);color:var(--ink-2);cursor:pointer}
.switch button[aria-selected="true"]{background:var(--accent);border-color:var(--accent);color:var(--bg)}
.switch button:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.acct{display:grid;gap:14px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}
.tile{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:10px 12px;display:grid;gap:2px;min-width:0}
.tile .lab{font-size:12px;color:var(--ink-3);text-transform:uppercase;letter-spacing:.06em}
.tile b{font:600 22px/1.2 var(--f-display);font-variant-numeric:tabular-nums}
.tile .sub{font-size:12.5px;color:var(--ink-2)}
.chart{margin:0;background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:12px;display:grid;gap:6px}
.chart figcaption{font-size:13px;color:var(--ink-2)}
.chart svg{width:100%;height:auto;display:block}
.grid{stroke:var(--rule);stroke-width:1} .base{stroke:var(--ink-3);stroke-dasharray:3 3} .split{stroke:var(--ink-3);stroke-dasharray:2 4}
.tick{fill:var(--ink-3);font:11px var(--f-mono)}
.line{fill:none;stroke:var(--accent);stroke-width:2} .area{fill:color-mix(in srgb,var(--accent) 12%,transparent)}
.posdot{fill:var(--pos)} .negdot{fill:var(--neg)} .zerodot{fill:var(--ink-3)} .enddot{fill:var(--accent);stroke:var(--surface);stroke-width:2}
.note{color:var(--ink-2);margin:0;max-width:90ch;font-size:14px}
.tw{overflow-x:auto;background:var(--surface);border:1px solid var(--rule);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:6px 10px;border-bottom:1px solid var(--rule);text-align:left;white-space:nowrap;vertical-align:top}
thead th{position:sticky;top:0;background:var(--surface);font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--ink-3);font-weight:600}
.num{text-align:right;font-variant-numeric:tabular-nums}
.mono{font-family:var(--f-mono);font-size:12.5px}
.b{font-weight:600}
.ist{display:block;color:var(--ink-3);font-size:11.5px}
tr.quiet td{color:var(--ink-3)} tr.act td:first-child{border-left:3px solid var(--accent)} tr.quiet td:first-child{border-left:3px solid transparent}
tr:target td{background:var(--hold)}
.pos{color:var(--pos)} .neg{color:var(--neg)} .zero,.mut{color:var(--ink-3)}
.chip{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:999px;background:var(--bg);color:var(--ink-3)}
.chip.on{background:var(--hold);color:var(--accent)} .chip.win{background:var(--pos-bg);color:var(--pos)} .chip.loss{background:var(--neg-bg);color:var(--neg)}
a{color:var(--accent)}
details{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:10px 14px}
details summary{cursor:pointer;font-weight:600}
dl.facts{display:grid;grid-template-columns:minmax(120px,max-content) 1fr;gap:4px 14px;margin:10px 0 0;font-size:14px}
dl.facts dt{color:var(--ink-3)} dl.facts dd{margin:0;min-width:0;overflow-wrap:anywhere}
.regime{display:grid;gap:10px}
.regs{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:10px}
.reg{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:12px 14px;display:grid;gap:4px;align-content:start;min-width:0}
.reg .lab{font-size:12px;color:var(--ink-3);text-transform:uppercase;letter-spacing:.06em}
.reg h3{font:600 18px/1.2 var(--f-display);margin:0}
.reg .res{margin:6px 0 0;font-size:14px;font-weight:600}
.src{margin:8px 0 0;padding-left:18px;font-size:14px;display:grid;gap:4px}
@media (max-width:560px){h1{font-size:24px} dl.facts{grid-template-columns:1fr} .regs{grid-template-columns:1fr}}
"""
JS = """
const btns=[...document.querySelectorAll('.switch button')],panels=[...document.querySelectorAll('.acct')];
function show(a){btns.forEach(b=>b.setAttribute('aria-selected',b.dataset.acct===a));panels.forEach(p=>p.hidden=p.dataset.acct!==a);try{localStorage.setItem('h4acct',a)}catch(e){}}
btns.forEach(b=>b.addEventListener('click',()=>show(b.dataset.acct)));
let start='A';const h=(location.hash||'').toLowerCase();
if(h.startsWith('#b')||h==='#acct-b')start='B';else if(!h){try{start=localStorage.getItem('h4acct')||'A'}catch(e){}}
show(start);
"""
facts = [("Rule", "H4 candle body at least 66% of its range → buy at the next M15 open; stop at the candle low minus 0.2 × ATR(14); target 1.5R after costs; one trade at a time."),
         ("Costs", "spread $0.09, entry slip $0.09, stop and exit slip $0.09, commission $0.08 round trip; funding −$0.5759 per ounce per night (Wednesday ×3)."),
         ("Sizing", "Account A ₹10,00,000 with ₹30,000 risk per trade; Account B ₹1,00,000 with ₹3,000 risk; lots rounded down to 0.01, minimum 0.01."),
         ("Test windows", "signals from 22 May to 5 Jul 2026 and 8 Aug to 6 Oct 2026. July 6 – August 7 is left out because the rule was built on it."),
         ("Data", f'{D["data"]["path"]}, {D["data"]["rows"]:,} M15 bars, {D["data"]["first"]} to {D["data"]["last"]}, sha256 {D["data"]["sha256"][:16]}…'),
         ("Clock", "MT5 broker time (New York time + 7 h, so UTC+3 in these months). India time = broker time + 2 h 30 min."),
         ("Declaration", f'{dec["id"]}, sha256 {D["declaration_sha256"][:16]}…, recorded in the session log before the run. Pass bar: average trade above 0 R with at least 30 trades, and better than the every-candle comparison.'),
         ("Caveats", " ".join(dec["caveats"]))]
page = f"""<title>H4 Long Holdout Ledger</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=IBM+Plex+Mono:wght@400;500&family=Source+Sans+3:wght@400;600&display=swap">
<style>{CSS}</style>
<div class="wrap">
  <header style="display:grid;gap:8px">
    <div class="eyebrow">XAUUSD · H4 long only · 1.5R target · frozen rule</div>
    <h1>H4 Long Holdout Ledger</h1>
    <p class="lede">The frozen H4 long rule run once on months it had never seen: 22 May – 5 Jul and 8 Aug – 6 Oct 2026. Gold went from {g['start']:,.2f} to {g['end']:,.2f} over these windows. Account A is the account under test; Account B is kept here for later research.</p>
  </header>
  <div class="verdict"><b>FAIL</b><span>Account A averaged {A['summary']['mean_r']:+.2f} R over {A['summary']['trades']} trades (the bar was above 0 R with at least 30 trades) and lost {inr(A['summary']['net'])}. No settings were changed after the run.</span></div>
  {regime_section()}
  <div class="switch" role="tablist" aria-label="Account">
    <button type="button" role="tab" data-acct="A" aria-selected="true">Account A · ₹10L</button>
    <button type="button" role="tab" data-acct="B" aria-selected="false">Account B · ₹1L · research</button>
  </div>
  {account_panel("A", A, D["control"]["A"])}
  {account_panel("B", B, D["control"]["B"])}
  <details><summary>How this was run</summary><dl class="facts">{"".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in facts)}</dl></details>
  <p class="note">Built from <code>tools/h4_long_holdout/build_data.py</code> and <code>render.py</code>; data in <code>results/h4_long_holdout/holdout.json</code>. Research record only, not a trading recommendation.</p>
</div>
<script>{JS}</script>
"""
open(OUT, "w", encoding="utf-8").write(page)
print("wrote", OUT, len(page))
