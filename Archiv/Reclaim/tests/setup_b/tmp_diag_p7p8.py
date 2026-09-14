# test/tmp_diag_p7p8.py
"""Diagnose: Phasen P6-P9 Details (Pivots, Zonen) fuer die P7/P8-Fragen."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "tmp_phasen_volumen_profil.py"

src = SRC.read_text(encoding="utf-8")
cut = src.index("reclaim_signals = []")
ns = {"__file__": str(SRC), "__name__": "diag"}
exec(compile(src[:cut], str(SRC), "exec"), ns)

phases = ns["phases"]
df = ns["df"]
level_schnittmenge = ns["level_schnittmenge"]

for i, P in enumerate(phases, 1):
    if i not in (6, 7, 8, 9):
        continue
    h = P.get("h_prices", P.get("h", []))
    l = P.get("l_prices", P.get("l", []))
    ht = P.get("h_ts", [])
    lt = P.get("l_ts", [])
    print(f"P{i}: {P['start']:%d.%m %H:%M}-{P['ende']:%d.%m %H:%M}")
    print(f"  H-Pivots: {[(f'{t:%d.%m %H:%M}', round(float(p),3)) for p,t in zip(h,ht)]}")
    print(f"  L-Pivots: {[(f'{t:%d.%m %H:%M}', round(float(p),3)) for p,t in zip(l,lt)]}")

# alte B2 (P2-P5) obere Kante
h_all, l_all = [], []
for P in phases[1:5]:
    h_all += list(P.get("h_prices", []))
    l_all += list(P.get("l_prices", []))
u_alt = level_schnittmenge(h_all, "H")
l_alt = level_schnittmenge(l_all, "L")
print(f"\nAlte P2-P5 Box (Schnittmenge): OBEN {u_alt:.3f} / UNTEN {l_alt:.3f}")

# Preisverlauf im Fenster 19.08-21.08 (Tag-High/Low)
fenster = df[(df["ts"] >= "2026-08-19 17:00") & (df["ts"] <= "2026-08-21 05:00")]
for ts, hi, lo in zip(fenster["ts"], fenster["high"], fenster["low"]):
    print(f"  {ts:%d.%m %H:%M}  H {hi:.3f}  L {lo:.3f}")
