# -*- coding: utf-8 -*-
import sys, re
sys.stdout.reconfigure(encoding="utf-8")
# 1) TRADE-LOG-Format in stats_trades_MAKRO_S1.txt pruefen
txt = open("test/stats_trades_MAKRO_S1.txt", encoding="utf-8").read()
base = txt.split("Modus: --macro-live")[0]
lines = base.split("\n")
in_tr = False
shown = 0
for l in lines:
    if l.startswith("TRADE-LOG"):
        in_tr = True
        continue
    if in_tr and "|" in l and shown < 4:
        print("LOG:", l[:160])
        shown += 1
# 2) reclaim_signals.sort Vorkommen + was danach kommt
src = open("scripts/phasen_volumen_profil.py", encoding="utf-8").read()
sl = src.split("\n")
idxs = [i for i, l in enumerate(sl) if "reclaim_signals.sort" in l]
print("\nreclaim_signals.sort bei Zeilen:", [i+1 for i in idxs])
# 3) Kontext: ist compute_volume_zone (Z. 584) vor der Segmentierung (Z. 617)?
print("compute_volume_zone def:", 584, "| Segmentierung startet:", 617)
print("df = load_data bei Z.:", 337)
# 4) Konstanten
for i, l in enumerate(sl):
    m = re.match(r"^(NUM_BINS|SMOOTH_WIN|MIN_MOUNTAIN_PCT|VALLEY_REL|VA_PCT)\s*[:=]\s*([\d.]+)", l)
    if m:
        print(f"Konstante {m.group(1)} = {m.group(2)} (Z. {i+1})")
