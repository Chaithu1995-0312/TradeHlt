"""Inspect older BNBUSDT runs to find parameters that produced more trades."""
import csv, json, os

targets = [
    r'd:\Tradelatest\results\session_sweep\_runs\run_20260601_174721_BNBUSDT',
    r'd:\Tradelatest\results\session_sweep\_runs\run_20260601_174829_BNBUSDT',
    r'd:\Tradelatest\results\detection_sweep\_runs\run_20260606_172334_BNBUSDT',
]

for base in targets:
    trades_csv = os.path.join(base, 'BNBUSDT_trades.csv')
    if os.path.exists(trades_csv):
        with open(trades_csv) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        print(f"\n=== {os.path.basename(base)} ===")
        print(f"Trades: {len(rows)}")
        if rows:
            r = rows[0]
            print(f"config_version: {r.get('config_version', 'N/A')}")
            print(f"Entry#1: {r['trade_id']} dir={r['direction']} raw={r['entry_raw']}")

    # Check report for params
    report_txt = os.path.join(base, 'BNBUSDT_report.txt')
    if os.path.exists(report_txt):
        with open(report_txt) as f:
            content = f.read()
        for line in content.split('\n'):
            if 'sweep' in line.lower() or 'decay' in line.lower() or 'threshold' in line.lower():
                print(f"  PARAM: {line.strip()}")