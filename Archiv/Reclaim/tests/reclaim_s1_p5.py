# test/reclaim_s1_p5.py
"""S1-Diagnose P5: Baseline-Referenzsignale (AUG) gegen EdgeStore-Korridor.

Frage: Wuerden die 5 P5-Konter-SHORTs (Trailing) entfallen und die 2 Gewinner
an 66.28 (17./18.08) im S1-Store-Modell (active-only, sleeping ohne
Reaktivierung) erhalten bleiben? Der Store wird mit kausalen Korridor-
Snapshots an den Signal-Bars gebaut (kein Lookahead auf spaetere Status).
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
TS_LO, TS_HI = pd.Timestamp("2026-08-14"), pd.Timestamp("2026-08-19")

# --- Baseline-Referenz (exec-cut, wie tmp_diag_p5_pruefung.py) ---
src = SRC.read_text(encoding="utf-8")
cut = src.index("reclaim_signals: List[ReclaimSignal] = []")
mod_name = "_phasen_volumen_profil_p5_s1"
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
print(f"Baseline-Referenz: {len(ref_signals)} Signale | {len(phases)} Phasen")

# Signal-Bars im P5-Zeitfenster merken (fuer kausale Store-Snapshots)
df = res.load_data(res.DB_PATH, START, ENDE)
ts_to_idx = {t: i for i, t in enumerate(df["ts"])}
record_bars = {
    ts_to_idx[s.ts]
    for s in ref_signals
    if TS_LO <= s.ts < TS_HI and s.ts in ts_to_idx
}

store = res.EdgeStore().build(df, record_bars=record_bars)

print("\n=== REFERENZ-SIGNALE 14.-18.08 vs. KORRIDOR (kausaler Snapshot an Signal-Bar) ===")
print("Sig | ts                | Typ  | Entry   | Res                  | U_alt(Baseline) | Store U (aktiv)  | Store D (aktiv)")
show = [s for s in ref_signals if TS_LO <= s.ts < TS_HI]
for s in show:
    k = ts_to_idx[s.ts]
    snap = store.snapshots[k]
    res_txt = f"{s.trade.resultat} {s.trade.r_mult:+.2f}R" if s.trade else "?"
    up_txt = dn_txt = "---"
    if snap:
        if snap[0]:
            up_txt = f"{snap[0][0]:.3f}(T{snap[0][1]},{snap[0][2][:3]})"
        if snap[1]:
            dn_txt = f"{snap[1][0]:.3f}(T{snap[1][1]},{snap[1][2][:3]})"
    print(f"{s.phase:2d} | {s.ts:%d.%m %H:%M} | {s.typ:5s} | {s.einstieg_preis:7.3f} | "
          f"{res_txt:20s} | U_alt={s.U_laufend:7.3f}      | U={up_txt:20s} | D={dn_txt}")

# Store-Level in der 66.0-66.8-Zone mit kausalem Stand vom 18.08 03:00
cut_ts = pd.Timestamp("2026-08-18 03:00")
k_cut = int(df.index[df["ts"] <= cut_ts][-1])
store_cut = res.EdgeStore().build(df.iloc[: k_cut + 1].copy())
print(f"\n=== LEVEL 66.0-66.8 (kausaler Stand {cut_ts:%d.%m %H:%M}) ===")
near = [lev for lev in store_cut.levels if 66.0 <= lev.price <= 66.8]
for lev in sorted(near, key=lambda x: x.price):
    ttypes = {}
    for t in lev.touches:
        ttypes[t.touch_type] = ttypes.get(t.touch_type, 0) + 1
    print(f"  id={lev.edge_id:3d} {lev.side:5s} {lev.status:9s} px={lev.price:7.3f} "
          f"T={lev.n_touches:2d} {ttypes} birth={lev.birth_ts:%d.%m %H:%M}")

# Store-Level der Zone mit kausalem Stand vom 13.08 00:00 (VOR der 66.28-Rueckkehr)
cut_ts2 = pd.Timestamp("2026-08-13 00:00")
k_cut2 = int(df.index[df["ts"] <= cut_ts2][-1])
store_cut2 = res.EdgeStore().build(df.iloc[: k_cut2 + 1].copy())
print(f"\n=== LEVEL 66.0-66.8 (kausaler Stand {cut_ts2:%d.%m %H:%M}, vor P5) ===")
for lev in sorted([lev for lev in store_cut2.levels if 66.0 <= lev.price <= 66.8],
                  key=lambda x: x.price):
    print(f"  id={lev.edge_id:3d} {lev.side:5s} {lev.status:9s} px={lev.price:7.3f} "
          f"T={lev.n_touches:2d} birth={lev.birth_ts:%d.%m %H:%M}")
