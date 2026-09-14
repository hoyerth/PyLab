# test/tmp_diag_trade_p7.py
"""Debug: B3-SHORT vom 20.08 04:15 (dritter Short in P7).

Zeigt das komplette Trade-Dict + alle Bars ab Entry bis zum Exit.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "tmp_phasen_volumen_profil.py"

src = SRC.read_text(encoding="utf-8")
cut = src.index("reclaim_signals = []")
ns = {"__file__": str(SRC), "__name__": "diag"}
exec(compile(src[:cut], str(SRC), "exec"), ns)

df = ns["df"]
phases = ns["phases"]
find_signals_box = None  # wird unten aus v7-Skript geholt

# --- v7-Modul laden (find_signals_box + segmentierung) ---
import importlib.util
spec = importlib.util.spec_from_file_location("v7", ROOT / "test" / "test_diag_3eck_v7_vmove.py")
# v7 fuehrt beim Import alles aus -> stattdessen Code-Teile ueber exec:
v7_src = (ROOT / "test" / "test_diag_3eck_v7_vmove.py").read_text(encoding="utf-8")
# Nur Funktionsdefinitionen verwenden: Code ab "print" abschneiden ist unsauber.
# Stattdessen: B3 manuell aus den Phasen P7+P8 bauen (identisch zur v7-Logik).
P7 = phases[6]
P8 = phases[7]

box = {
    "i_start": P7["i_start"], "i_ende": None,
    "h": list(P7["h_prices"]) + list(P8["h_prices"]),
    "h_ts": list(P7["h_ts"]) + list(P8["h_ts"]),
    "l": list(P7["l_prices"]) + list(P8["l_prices"]),
    "l_ts": list(P7["l_ts"]) + list(P8["l_ts"]),
}
# LUEKEN-FIX wie v7: i_ende bis Ende der naechsten Phase/B3-Ende
box["i_ende"] = phases[8]["i_start"] - 1
n = len(df)
box["i_ende"] = min(box["i_ende"], n - 1)
print(f"B3 manuell: i_start={box['i_start']} ({df['ts'].iloc[box['i_start']]}) "
      f"i_ende={box['i_ende']} ({df['ts'].iloc[box['i_ende']]})")
print(f"P7: {P7['start']} - {P7['ende']} | P8: {P8['start']} - {P8['ende']}")

# find_signals_box aus v6-Skript importieren (identische Funktion)
v6_src = (ROOT / "test" / "test_diag_3eck_v6.py").read_text(encoding="utf-8")
marker = 'print("=== SEGMENTIERUNG'
v6_head = v6_src[:v6_src.index(marker)]
exec(compile(v6_head, str(ROOT / "test" / "test_diag_3eck_v6.py"), "exec"), ns)
find_signals_box = ns["find_signals_box"]

sigs = find_signals_box(ns, box)
print(f"\nSignale B3: {len(sigs)}")
for s in sigs:
    print(f"  {s['ts']:%d.%m %H:%M} {s['typ']:5s} Kante "
          f"{s['U_laufend'] if s['typ']=='SHORT' else s['L_laufend']:.3f} "
          f"| POC {s['POC']:.3f} | L {s['L_laufend']:.3f} | U {s['U_laufend']:.3f} "
          f"| Bo {s['bounce_nr']} | EntryBar {s['einstieg_bar']} | Entry {s['einstieg_preis']:.3f} "
          f"| SL {s['sl']:.3f} | TP1 {s['tp1']:.3f} | TP2 {s['tp2']:.3f} "
          f"| {s['resultat']} {s['r_mult']:+.2f}R")

# Ziel-Trade: SHORT 04:15
ziel = [s for s in sigs if s["typ"] == "SHORT" and s["ts"] == df["ts"].iloc[box["i_start"]]]
pd = ns["pd"]
for s in sigs:
    if s["ts"] <= pd.Timestamp("2026-08-20 05:00") and s["ts"] >= pd.Timestamp("2026-08-20 03:30") and s["typ"] == "SHORT":
        print("\n=== ZIEL-TRADE (alle Felder) ===")
        for k_, v in sorted(s.items()):
            print(f"  {k_}: {v}")
        # Bars ab Entry
        eb = s["einstieg_bar"]
        print(f"\nBars ab Entry-Bar {eb} ({df['ts'].iloc[eb]}):")
        for j in range(eb, min(eb + 60, n)):
            ts = df["ts"].iloc[j]
            o, h, l, c = df["open"].iloc[j], df["high"].iloc[j], df["low"].iloc[j], df["close"].iloc[j]
            mark = ""
            if s["typ"] == "SHORT":
                if l <= s["tp1"]:
                    mark = " <== TP1!"
                if l <= s["tp2"]:
                    mark = " <== TP2!"
                if h >= s["sl"]:
                    mark = " <== SL!"
            print(f"  {ts:%d.%m %H:%M} O {o:.3f} H {h:.3f} L {l:.3f} C {c:.3f}{mark}")
