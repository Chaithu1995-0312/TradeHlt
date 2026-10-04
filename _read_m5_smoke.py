import json
from pathlib import Path

m = json.loads(Path("results/research/m5_mtf/_smoke_stage1/m5_mtf_information.json").read_text(encoding="utf-8"))
print("universe_complete", m.get("universe_complete"))
print("exclusions", list((m.get("universe_exclusions") or {}).keys()))
print("crypto_loaded", m.get("crypto_symbols_loaded"))
print("fx_loaded", m.get("fx_symbols_loaded"))
print("cross", m.get("cross_market"))
print()
for grp in ("crypto", "fx"):
    print("== pooled", grp)
    for prog, b in (m.get("pooled") or {}).get(grp, {}).items():
        print(
            f"  {prog} verdict={b.get('verdict')} gate_a={b.get('gate_a_pass')} "
            f"n={b.get('n_decision')} p={b.get('decision_p_value')} inc_p={b.get('incremental_p_value')}"
        )
        print(f"    half={b.get('half_life')}")
        print(f"    stab={b.get('stability')}")
        print(f"    ig={b.get('ig_curve')}")
print()
print("== per-instrument (p ignored at n_perm=2)")
for sym, rec in (m.get("per_instrument") or {}).items():
    for prog, b in (rec.get("programs") or {}).items():
        hl = b.get("half_life") or {}
        st = b.get("stability") or {}
        print(
            f"  {sym:8s} {prog:22s} n={b.get('n_decision')} "
            f"half_ok={hl.get('passed')} half_bars={hl.get('half_life_bars')} "
            f"stab_ok={st.get('passed')} ret={st.get('retention')} ig={b.get('ig_curve')}"
        )
