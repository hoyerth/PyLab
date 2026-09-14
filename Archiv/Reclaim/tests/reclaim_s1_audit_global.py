# test/reclaim_s1_audit_global.py
"""Globaler Lookahead-Check ueber ALLE 27 Baseline-Referenz-Signal-Bars (AUG).

Fuer jede Bar k mit Snapshot: Liegt der letzte Status-Wechsel des jeweiligen
Korridor-Levels mehr als PIVOT_LOOKBACK Bars vor k? (Level muss schon aktiv
gewesen sein, als der Preis es gepierct hat - nicht erst am Close von k.)
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

src = SRC.read_text(encoding="utf-8")
cut = src.index("reclaim_signals: List[ReclaimSignal] = []")
mod_name = "_phasen_volumen_profil_audit_g"
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

df = res.load_data(res.DB_PATH, START, ENDE)
ts_to_idx = {t: i for i, t in enumerate(df["ts"])}
record_bars = {ts_to_idx[s.ts] for s in ref_signals if s.ts in ts_to_idx}
store = res.EdgeStore().build(df, record_bars=record_bars)
PL = store.pivot_lookback

print(f"Referenz-Signale: {len(ref_signals)} | Snapshots: {len(store.snapshots)}")
bad = []
for s in ref_signals:
    k = ts_to_idx.get(s.ts)
    if k is None or k not in store.snapshots:
        continue
    snap = store.snapshots[k]
    edge = snap[0] if s.typ == "SHORT" else snap[1]
    if not edge:  # keine aktive Kante -> Signal waere im Store-Modell eh nicht da
        continue
    _, n_t, st, eid = edge
    evs = [t for t in store.transitions if t["edge_id"] == eid and t["iter"] <= k]
    last_iter = evs[-1]["iter"] if evs else -1
    gap = k - last_iter
    if st != "active" or gap <= PL:
        bad.append((s.ts, s.typ, eid, st, gap))

n_active = 0
n_edge = 0
for s in ref_signals:
    k = ts_to_idx.get(s.ts)
    if k is None or k not in store.snapshots:
        continue
    edge = store.snapshots[k][0] if s.typ == "SHORT" else store.snapshots[k][1]
    if edge:
        n_edge += 1
        if edge[2] == "active":
            n_active += 1
print(f"Snapshots mit Korridor-Level: {n_edge} | davon active: {n_active}")
print(f"LOOKAHEAD-VERDACHT (letzter Wechsel <= {PL} Bars vor Signal-Bar): {len(bad)}")
for ts, typ, eid, st, gap in bad:
    print(f"  {ts:%d.%m %H:%M} {typ:5s} edge={eid} status={st} gap={gap}")
if not bad:
    print("\n=> KEIN Lookahead: Alle aktiven Korridor-Level waren bereits > PIVOT_LOOKBACK")
    print("   Bars vor der Signal-Bar aktiv (kein 'Aufwecken' am Close der Signal-Bar).")
