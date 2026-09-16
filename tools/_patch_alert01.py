from pathlib import Path
p = Path("scripts/research/live_alert_resolver.py")
text = p.read_text(encoding="utf-8")
old = '''        if et != "STATE_TRANSITION":
            # RESET during expansion = orange death candidate
            if et == "RESET" and phase == "E":
                alerts.append(
                    mint(
                        "EXPANSION_ORANGE_DEATH",
                        "watch",
                        ev,
                        f"Expansion died via RESET after {exp_bars} bars (before RETEST)",
                        expansion_bars=exp_bars,
                        expansion_start=exp_start_ts,
                        reason=ev.get("reason"),
                        direction=last_direction,
                    )
                )
                phase = "idle"
                exp_bars = 0
            continue'''
new = '''        if et != "STATE_TRANSITION":
            # REM-ALERT-01: any RESET breaks the costume. During E => orange death
            # with dwell from candle_index delta (not transition count).
            if et == "RESET":
                if phase == "E":
                    if exp_start_idx is not None and ev.get("candle_index") is not None:
                        exp_bars = max(1, int(ev["candle_index"]) - int(exp_start_idx))
                    alerts.append(
                        mint(
                            "EXPANSION_ORANGE_DEATH",
                            "watch",
                            ev,
                            f"Expansion died via RESET after {exp_bars} bars (before RETEST)",
                            expansion_bars=exp_bars,
                            expansion_start=exp_start_ts,
                            reason=ev.get("reason"),
                            direction=last_direction,
                            continuous=False,
                        )
                    )
                # S/D or post-death: hard idle (HTF/session kill)
                phase = "idle"
                exp_bars = 0
                exp_start_idx = None
                exp_start_ts = None
                sweep_ts = None
            continue'''
if old not in text:
    raise SystemExit("RESET block not found")
# Also refuse EXPANSION entry from idle without recent S/D — require phase D (or S) only
old2 = '''        elif to == "EXPANSION" and phase in ("D", "S", "E", "idle"):'''
new2 = '''        elif to == "EXPANSION" and phase in ("D", "S", "E"):'''
if old2 not in text:
    raise SystemExit("EXPANSION phase gate not found")
text = text.replace(old, new, 1).replace(old2, new2, 1)
# Cap absurd dwell: if exp_bars > 200 at RETEST, treat as broken continuity (info near-miss)
old3 = '''            if exp_bars >= expansion_min:
                alerts.append(
                    mint(
                        "A_SETUP_CANDIDATE",
                        "action",
                        ev,'''
new3 = '''            if exp_bars > 200:
                alerts.append(
                    mint(
                        "A_SETUP_CANDIDATE",
                        "info",
                        ev,
                        f"Retest after non-continuous expansion span ({exp_bars} bars) — discarded",
                        expansion_bars=exp_bars,
                        expansion_start=exp_start_ts,
                        direction=last_direction,
                        near_miss=True,
                        noncontinuous=True,
                    )
                )
            elif exp_bars >= expansion_min:
                alerts.append(
                    mint(
                        "A_SETUP_CANDIDATE",
                        "action",
                        ev,'''
if old3 not in text:
    raise SystemExit("A_SETUP action block not found")
text = text.replace(old3, new3, 1)
p.write_text(text, encoding="utf-8")
print("REM-ALERT-01 patched")
