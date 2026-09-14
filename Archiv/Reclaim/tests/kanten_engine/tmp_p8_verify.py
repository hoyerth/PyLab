# -*- coding: utf-8 -*-
"""READ-ONLY Verifikation _p8 (Voll-Lauf n=1288) -- kein Engine-Eingriff.

Prueft nach dem `_p8`-Patch: Voll-Lauf (box_end_bar = n) 9 Trades / +23.02 R /
Stacking=4 sowie Idempotenz (zweifacher Scan -> identische Ergebnisse).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, src: str):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(P)
    sys.modules[name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


mod = load("ke_p8", P.read_text(encoding="utf-8"))
cfg = mod.StraightEdgeHarnessKonfiguration()

# --- Voll-Lauf (box_end_bar = n = 1288) ------------------------------------
scan = mod._se_scan("AUG", cfg)
n = len(scan["d"])
scan["box_end_bar"] = n
setups, stats = mod._se_trades(scan, cfg)
sig = [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in setups]
r21 = scan.get("r21_geloescht") or []
gel = [r for r in r21 if r[1] >= 0]
gesp = [r for r in r21 if r[1] < 0]

print("=" * 110)
print("P8-VERIFIKATION: VOLL-LAUF AUG (n=1288, box_end_bar = n)")
print("=" * 110)
print(f"  Kanten (edges+seeds) : {len(scan['edges']) + len(scan['seeds'])} "
      f"(edges {len(scan['edges'])} / seeds {len(scan['seeds'])})")
print(f"  R21 geloescht        : {len(gel)}")
print(f"  R21 Geburten gesperrt: {len(gesp)}")
print(f"  Tombstones           : {len(scan.get('tombstones') or [])}")
print(f"  Trades               : {len(setups)}")
print(f"  Netto-R              : {sum(t.r for t in setups):+.2f}")
print(f"  Stacking blockiert   : {stats.get('stacking_blockiert')}")
print(f"  Zyklus blockiert     : {stats.get('zyklus_blockiert')}")
print(f"  Quartil / Blocker / F3 / kein_Gegner: "
      f"{stats.get('quartil_blockiert')} / {stats.get('blocker')} / "
      f"{stats.get('f3')} / {stats.get('kein_gegner')}")
print("  Trades:")
for t in setups:
    box = "BOX " if t.entry_bar < 644 else "POST"
    print(f"    {box} bar {t.bar:4d} {t.richtung:5s} entry={t.entry_bar:4d} "
          f"K{t.kid:3d} {t.resultat:9s} {t.r:+6.2f}R")

# --- Zielmetriken (Vertrag P8ScharfschaltungsVertrag) ----------------------
soll = {
    "soll_trades_gesamt": 9, "soll_netto_r_gesamt": 23.02,
    "erwartete_r21_loeschungen": 17,
    "erwartete_tombstone_geburten_gesperrt": 17,
}
ist = {
    "soll_trades_gesamt": len(setups),
    "soll_netto_r_gesamt": round(sum(t.r for t in setups), 2),
    "erwartete_r21_loeschungen": len(gel),
    "erwartete_tombstone_geburten_gesperrt": len(gesp),
}
print("")
print("ZIELABGLEICH (Voll-Lauf):")
ok = True
for k, v in soll.items():
    treffer = ist[k] == v
    ok = ok and treffer
    print(f"  {k:42s} soll={v:>7} ist={ist[k]:>7} "
          f"{'OK' if treffer else 'ABWEICHUNG'}")

# --- Idempotenz-Test (zweifacher Scan, State-Reset) ------------------------
scan2 = mod._se_scan("AUG", cfg)
scan2["box_end_bar"] = n
setups2, stats2 = mod._se_trades(scan2, cfg)
sig2 = [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in setups2]
print("")
print(f"IDEMPOTENZ (2. Scan nach 1. Lauf): Signatur "
      f"{'IDENTISCH' if sig2 == sig else 'ABWEICHEND'} | "
      f"Kanten {len(scan2['edges']) + len(scan2['seeds'])} | "
      f"R21 {len(scan2.get('r21_geloescht') or [])} | "
      f"Tombstones {len(scan2.get('tombstones') or [])}")

# --- PNG-Kantenbestand (keine Schattenlinien) ------------------------------
print("")
print(f"PNG-KANTENBESTAND: {len(scan['edges'])} edges + "
      f"{len(scan['seeds'])} seeds = "
      f"{len(scan['edges']) + len(scan['seeds'])} gezeichnet "
      f"(geloeschte Kanten sind NICHT im Scan-Objekt)")
print("GESAMT:", "BESTANDEN" if ok else "ABWEICHUNG")
