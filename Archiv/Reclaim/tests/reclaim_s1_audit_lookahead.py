# test/reclaim_s1_audit_lookahead.py
"""Lookahead-Audit (User-Warnung): Wurde die 66.28-Zone an den Gewinner-Bars
(17.08 18:45 / 18.08 02:15) durch fruehere Pivots reaktiviert - oder hat der
Store an Bar k den unbestätigten Pivot der Signal-Bar selbst verwendet?

Kausalitaets-Invariante des Stores:
  - Pivot auf Bar j wird erst bei Iteration k = j + PIVOT_LOOKBACK (= j+2)
    verarbeitet (2-Close-Bestaetigung). Ein Pivot der Signal-Bar k waere also
    erst bei k+2 bekannt und KANN den Snapshot bei k nicht beeinflussen.
  - Snapshot bei k = Zustand NACH Verarbeitung von Pivot j = k-2 (bekannt am
    Close von k) = korrekter Entscheidungszeitpunkt (Entry fruehestens k+1).
  - ZUSAETZLICH hier geprueft: Liegt der letzte Status-Wechsel (activate/
    reactivate/sleep) des Korridor-Levels deutlich VOR der Signal-Bar, damit
    das Level schon aktiv war, als der Preis es gepierct hat (nicht erst am
    Close der Signal-Bar "aufgeweckt")?
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

# --- Baseline-Referenz (nur um die beiden Gewinner-Signal-Bars zu ermitteln) ---
src = SRC.read_text(encoding="utf-8")
cut = src.index("reclaim_signals: List[ReclaimSignal] = []")
mod_name = "_phasen_volumen_profil_audit"
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

ref_signals = []
for i_p, p in enumerate(phases, 1):
    for s in ns["find_reclaim_signals"](df_base, p):
        s.phase = i_p
        ref_signals.append(s)
ref_signals.sort(key=lambda s: s.ts)
winner_bars = [s for s in ref_signals
               if pd.Timestamp("2026-08-14") <= s.ts < pd.Timestamp("2026-08-19")
               and s.trade and s.trade.resultat == "GEWONNEN"]
print(f"Gewinner-Signale im P5-Fenster: {len(winner_bars)}")

# --- Store mit Snapshots + Transition-Log ---
df = res.load_data(res.DB_PATH, START, ENDE)
ts_to_idx = {t: i for i, t in enumerate(df["ts"])}
record_bars = {ts_to_idx[s.ts] for s in winner_bars}
store = res.EdgeStore().build(df, record_bars=record_bars)
PL = store.pivot_lookback

print(f"\n{'Signal-Bar':<16} {'Typ':5s} {'Korridor-Level':>14} {'EdgeId':>6} "
      f"{'nT':>2} | letzter Status-Wechsel -> WANN (iter) | Abstand zur Signal-Bar")
ok_all = True
for s in winner_bars:
    k = ts_to_idx[s.ts]
    snap = store.snapshots[k]
    if s.typ == "SHORT":
        snap_edge = snap[0] if snap else None
    else:
        snap_edge = snap[1] if snap else None
    if not snap_edge:
        print(f"{s.ts:%d.%m %H:%M}  {s.typ:5s}  KEIN aktives Korridor-Level im Snapshot")
        ok_all = False
        continue
    px, n_t, st, eid = snap_edge
    # alle Transitions dieses Levels mit iter <= k
    evs = [t for t in store.transitions
           if t["edge_id"] == eid and t["iter"] <= k]
    last_ev = evs[-1] if evs else None
    last_iter = last_ev["iter"] if last_ev else -1
    gap = k - last_iter
    status_ok = st == "active"
    gap_ok = gap > PL  # Statuswechsel liegt mehr als Pivot-Lag zurueck
    ok = status_ok and gap_ok
    ok_all = ok_all and ok
    print(f"{s.ts:%d.%m %H:%M}  {s.typ:5s}  {px:14.3f}  {eid:6d}  {n_t:2d} | "
          f"{last_ev['event'] if last_ev else '?':>18} @ iter {last_iter:4d} "
          f"({df['ts'].iloc[last_iter]:%d.%m %H:%M})  | gap {gap:3d}  {'OK' if ok else '*** PROBLEM ***'}")

# Detail-Timeline der 66.28-Zonen-Level (id 14 und 16) - alle Events mit iter
print("\n=== TRANSITION-TIMELINE Level 14 & 16 (66.2er/66.39er-Zone) ===")
for eid in (14, 16):
    lev = next((l for l in store.levels if l.edge_id == eid), None)
    if lev is None:
        continue
    print(f"\nLevel {eid}: {lev.side} px_final={lev.price:.3f} status_final={lev.status}")
    evs = [t for t in store.transitions if t["edge_id"] == eid]
    for t in sorted(evs, key=lambda x: x["iter"]):
        print(f"   iter {t['iter']:4d} ({df['ts'].iloc[t['iter']]:%d.%m %H:%M}) "
              f"{t['event']:>18} px={t['price']:.3f} "
              f"touch_bar={t['touch_bar']}")

print(f"\n=== AUDIT-ERGEBNIS: {'KEIN LOOKAHEAD (alle Gewinner-Level waren vor der Signal-Bar aktiv)' if ok_all else 'LOOKAHEAD-VERDACHT - bitte pruefen'} ===")
