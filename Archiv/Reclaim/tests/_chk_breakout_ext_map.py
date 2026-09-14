# -*- coding: utf-8 -*-
"""READ-ONLY Recon: Bar-Zuordnung der September-Fenster (C/D/E).

Prueft (a) Engine-SHA, (b) dass die August-Bar-Indizes durch die
Fenster-Erweiterung unveraendert bleiben, (c) BKZ-Kalendergrenzen
via searchsorted (Kanon: keine Bar-Konstante hartcodieren).

Kein Patch an Engine/Adapter/Renderer.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
EP = ROOT / "test" / "tmp_kanten_engine_replay.py"
assert hashlib.sha256(EP.read_bytes()).hexdigest() == \
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"

_s = importlib.util.spec_from_file_location("emap", EP)
engine = importlib.util.module_from_spec(_s)
sys.modules["emap"] = engine
_s.loader.exec_module(engine)  # type: ignore[union-attr]

cfg = engine.StraightEdgeHarnessKonfiguration()

# --- Basis AUG26 (Referenz-Bar-Indizes) ---
engine.FENSTER["AUG26"] = ("2026-08-03", "2026-09-01")  # type: ignore[index]
base = engine._se_scan("AUG26", cfg)  # type: ignore[arg-type]
nb = int(base["n"])
tsb = np.array(list(base["d"]["ts"]))

# --- Erweitertes Fenster (gleicher Start => Bar-Indizes der August-
#     Bereiche bleiben erhalten; September wird angehaengt) ---
engine.FENSTER["EXT"] = ("2026-08-03", "2026-09-12")  # type: ignore[index]
ext = engine._se_scan("EXT", cfg)  # type: ignore[arg-type]
ne = int(ext["n"])
tse = np.array(list(ext["d"]["ts"]))

print("=" * 100)
print("FENSTER-UEBERGANG")
print("=" * 100)
print(f"AUG26: n={nb}  [{tsb[0]} .. {tsb[-1]}]")
print(f"EXT  : n={ne}  [{tse[0]} .. {tse[-1]}]")
print(f"Praefix identisch: {bool(np.array_equal(tsb, tse[:nb]))}")
print(f"Neue Bars ab Index {nb}: {ne - nb}")

print("\nReferenz-Bars (A/B) unter EXT unveraendert?")
for k in (836, 864, 1076, 1160, 1104):
    ok = str(tsb[k]) == str(tse[k])
    print(f"  Bar {k:>4}  AUG26={tsb[k]}  EXT={tse[k]}  {'OK' if ok else 'ABWEICHUNG!'}")

# --- Kalendergrenzen dynamisch via searchsorted (Kanon) ---
tsd = np.array(tse, dtype="datetime64[ns]")

def bar_at(bkz: str) -> int:
    """Erster Bar >= BKZ-Zeitstempel (searchsorted, Kanon-Methode)."""
    return int(np.searchsorted(tsd, np.datetime64(bkz)))

WUNSCH = [
    ("C  28.08. 08:00", "2026-08-28T08:00"),
    ("C  28.08. 18:00", "2026-08-28T18:00"),
    ("D  01.09. 10:00", "2026-09-01T10:00"),
    ("D  02.09. 16:00", "2026-09-02T16:00"),
    ("E  10.09. 08:00", "2026-09-10T08:00"),
    ("E  11.09. 15:00", "2026-09-11T15:00"),
]
print("\n" + "=" * 100)
print("BAR-ZUORDNUNG GEWUENSCHTE ZEITFENSTER (BKZ)")
print("=" * 100)
print(f"{'Label':<20} {'BKZ-Wunsch':<18} {'Bar':>6} {'BKZ(ts)':<20} {'Anzeige+02:00':<22}")
for lab, w in WUNSCH:
    k = bar_at(w)
    disp = (np.datetime64(w) + np.timedelta64(2, "h")).astype(str)
    print(f"{lab:<20} {w:<18} {k:>6} {str(tse[k]):<20} {disp:<22}")

# --- Tagesabdeckung September (Bars/Tag) ---
print("\n" + "=" * 100)
print("TAGESABDECKUNG ab 2026-08-28 (BKZ, Bars je Kalendertag)")
print("=" * 100)
days: dict[str, int] = {}
for t in tse:
    d0 = str(t)[:10]
    days[d0] = days.get(d0, 0) + 1
for d0 in sorted(days):
    if d0 >= "2026-08-28":
        print(f"  {d0}: {days[d0]:>3} Bars")
