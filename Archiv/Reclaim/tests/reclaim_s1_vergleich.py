# test/reclaim_s1_vergleich.py
"""Vergleichbarkeits-Check AUG: Baseline-Signale vs. Store-Korridor.

Frage: Wie viele der 27 Baseline-Signale (AUG) waeren im S1-Kantenspeicher-
Modell strukturell moeglich? Ein Baseline-Signal ist 'moeglich', wenn an der
Signal-Bar die aktive Store-Kante (naechstes aktives Level ueber/unter Close)
gepierct wurde und die Baseline-Kante in der Naehe der Store-Kante liegt.
Das zeigt, ob die Ergebnisse ueberhaupt 1:1 vergleichbar sind.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reclaim_edge_store as res  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "phasen_volumen_profil.py"
START, ENDE = "2026-08-10", "2026-08-28"

# --- Baseline-Referenz (exec-cut) ---
src = SRC.read_text(encoding="utf-8")
cut = src.index("reclaim_signals: List[ReclaimSignal] = []")
mod_name = "_phasen_volumen_profil_s1vgl"
if mod_name in sys.modules:
    mod = sys.modules[mod_name]
else:
    mod = types.ModuleType(mod_name)
    mod.__file__ = str(SRC)
    sys.modules[mod_name] = mod
sys.argv = [str(SRC), f"--start={START}", f"--ende={ENDE}"]
exec(compile(src[:cut], str(SRC), "exec"), mod.__dict__)
ns = mod.__dict__
df_base = ns["df"]
phases = ns["phases"]

ref_signals: list = []
for i_p, p in enumerate(phases, 1):
    for s in ns["find_reclaim_signals"](df_base, p):
        s.phase = i_p
        ref_signals.append(s)
ref_signals.sort(key=lambda s: s.ts)
print(f"Baseline AUG: {len(ref_signals)} Signale")

# Store mit kausalen Snapshots an allen Signal-Bars
df = res.load_data(res.DB_PATH, START, ENDE)
ts_to_idx = {t: i for i, t in enumerate(df["ts"])}
record_bars = {ts_to_idx[s.ts] for s in ref_signals if s.ts in ts_to_idx}
store = res.EdgeStore().build(df, record_bars=record_bars)

hi = df["high"].to_numpy()
lo = df["low"].to_numpy()

print(f"\n{'#':>2} {'P':>2} {'ts':<16} {'Typ':5s} {'Entry':>7} {'Res':>12} "
      f"{'Base-Kante':>10} {'Store-Kante':>11} {'Pierce':6s} {'Match?':6s} {'Bemerkung'}")
n_possible = 0
n_total = 0
rows = []
for s in ref_signals:
    k = ts_to_idx.get(s.ts)
    if k is None:
        continue
    n_total += 1
    snap = store.snapshots.get(k)
    if s.typ == "SHORT":
        base_kante = s.U_laufend
        if snap and snap[0]:
            store_kante, n_t, st, _ = snap[0]
        else:
            store_kante, n_t, st = None, 0, "?"
        pierce = bool(store_kante is not None and hi[k] > store_kante)
    else:
        base_kante = s.L_laufend
        if snap and snap[1]:
            store_kante, n_t, st, _ = snap[1]
        else:
            store_kante, n_t, st = None, 0, "?"
        pierce = bool(store_kante is not None and lo[k] < store_kante)

    dist = abs(base_kante - store_kante) if store_kante else float("nan")
    # 'Match': aktive Store-Kante gepierct UND Baseline-Kante innerhalb 2*EDGE_TOL
    match = pierce and dist <= 2 * res.EDGE_TOL
    if match:
        n_possible += 1
    res_txt = f"{s.trade.resultat} {s.trade.r_mult:+.2f}" if s.trade else "?"
    bemerkung = ""
    if store_kante is None:
        bemerkung = "keine aktive Kante"
    elif not pierce:
        bemerkung = f"kein Pierce (Bar-High {hi[k]:.2f})"
    elif not match:
        bemerkung = f"Distanz {dist:.2f} > Toleranz"
    rows.append((s, k, base_kante, store_kante, pierce, match, dist, res_txt, bemerkung))

for s, k, bk, sk, pierce, match, dist, rt, bem in rows:
    sk_str = f"{sk:.3f}" if sk is not None else "  ---  "
    print(f"{s.phase:2d} | {s.ts:%d.%m %H:%M} | {s.typ:5s} | {s.einstieg_preis:7.3f} | {rt:>12} "
          f"| {bk:10.3f} | {sk_str:>11} | {str(pierce):6s} | {str(match):6s} | {bem}")

print(f"\n=== ERGEBNIS ===")
print(f"Baseline-Signale gesamt: {n_total}")
print(f"Strukturell im Store-Modell moeglich (aktive Kante gepierct + Distanz<=2*TOL): {n_possible}")
print(f"Anteil: {100.0 * n_possible / n_total:.0f}%" if n_total else "n/a")
print(f"\n=> Ein direkter 1:1-Vergleich der Summe R ist NICHT sinnvoll, wenn der Anteil")
print(f"   deutlich unter 100% liegt: Das Store-Modell selektiert andere Kanten/Signale.")
