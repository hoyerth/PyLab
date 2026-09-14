# -*- coding: utf-8 -*-
"""S2-BASELINE-REFERENZ (V0/MAKRO) -- der Maßstab fuer den V-D-Stresstest.

Read-only, nutzt den arretierten Pickle-Cache. Zwei Buecher muessen getrennt
bleiben (analog Renderer V018, Z. 492 vs. 507):

* ``box_end``  = 17.692  -> H1/H2-PARTITION der Statistik.
* ``scan["box_end_bar"]`` = n = 21.624 -> LAUFGRENZE der Engine
  (``_se_trades`` iteriert ``range(2, box_end - 3)``).

Setzt man ``scan["box_end_bar"]`` auf den Split, laeuft die Engine nur ueber
H1 und liefert **keinen** H2-Trade. Genau dieser Fehler ist hier zu vermeiden.

Ausfuehren:  .venv\\Scripts\\python.exe test/_tmp_s2_baseline_ref.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import pickle
import sys
import time
from pathlib import Path
from typing import Dict, List

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
PKL_S2 = ROOT / "test" / "_tmp_s2_scan_cache.pkl"
OUT = ROOT / "test" / "_tmp_s2_baseline_ref_out.txt"
SPLIT = 17692
BUF: List[str] = []


def out(s: str = "") -> None:
    BUF.append(s)


spec = importlib.util.spec_from_file_location(
    "tmp_kanten_engine_replay", ENGINE_P)
eng = importlib.util.module_from_spec(spec)
sys.modules["tmp_kanten_engine_replay"] = eng
spec.loader.exec_module(eng)

ENGINE_SHA = hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
cfg = eng.StraightEdgeHarnessKonfiguration()
scan = pickle.loads(PKL_S2.read_bytes())
n = scan["n"]

out("=" * 104)
out("S2-BASELINE-REFERENZ (V0/MAKRO, Engine unveraendert)")
out("=" * 104)
out(f"Engine-SHA : {ENGINE_SHA}")
out(f"box_end (Partition) = {SPLIT}   scan['box_end_bar'] (Laufgrenze) = {n}")
out("")
out(f"walk_live_bars={cfg.wall_live_bars}  touch_band={cfg.touch_band_pct}  "
    f"M6={cfg.max_seed_distanz_pct}  Q29={cfg.quartil_distanz_pct}  "
    f"V-S-min={cfg.min_touches_handelbar}  Q24={cfg.min_wall_alter_bars}")
out("")

_lauf: Dict[str, Dict] = {}
for tag, bx in (("H1 (bars < 17.692)", SPLIT), ("VOLL (bis n)", n)):
    s = copy.deepcopy(scan)
    s["box_end_bar"] = bx
    t0 = time.time()
    setups, stats = eng._se_trades(s, cfg)
    dt = time.time() - t0
    _lauf[tag] = {"setups": setups, "stats": stats, "dt": dt,
                  "summe": sum(t.r for t in setups)}
    out(f"--- Lauf {tag}: box_end_bar={bx}  ({dt:.1f} s) ---")
    out(f"    Trades {len(setups)} / Summe {_lauf[tag]['summe']:+.6f} R")
    out(f"    stats  {stats}")
    out("")

setups = _lauf["VOLL (bis n)"]["setups"]
h1 = [t for t in setups if t.entry_bar < SPLIT]
h2 = [t for t in setups if t.entry_bar >= SPLIT]
out("PARTITIONIERUNG des Voll-Laufs bei entry_bar <>= 17.692")
out(f"    H1 : {len(h1):>3} Trades / {sum(t.r for t in h1):+.6f} R")
out(f"    H2 : {len(h2):>3} Trades / {sum(t.r for t in h2):+.6f} R")
out(f"    ges: {len(setups):>3} Trades / {sum(t.r for t in setups):+.6f} R")
out("")
out("    H2-Trades im Detail (entry_bar >= 17.692):")
if not h2:
    out("       -- KEINE --")
for t in sorted(h2, key=lambda x: x.entry_bar):
    out(f"       bar {t.bar:>6} entry {t.entry_bar:>6} {t.richtung:<5} "
        f"K{t.kid:<4} R {t.r:>+10.6f}  tp2 {t.tp2:>8.4f}  sl {t.sl:>8.4f}")
out("")
out("    Letzte 10 H1-Trades (Grenzbereich):")
for t in sorted(h1, key=lambda x: x.entry_bar)[-10:]:
    out(f"       bar {t.bar:>6} entry {t.entry_bar:>6} {t.richtung:<5} "
        f"K{t.kid:<4} R {t.r:>+10.6f}  tp2 {t.tp2:>8.4f}")
out("")

# Wie haeufig blockiert der MAKRO-Gegner den H2-Bereich?
out("MAKRO-GEGENKANTE UND RAUM-PRUEFUNG (Diagnose)")
out(f"    stats['kein_gegner']={_lauf['VOLL (bis n)']['stats'].get('kein_gegner')}"
    f"  stats['kein_raum']={_lauf['VOLL (bis n)']['stats'].get('kein_raum')}")
out("    Referenz: 2025-Spanne 28,2860 .. 56,5250 (Band 28,2390 USD).")
out("")

out("=" * 104)
out("Engine-SHA nach Lauf: " + hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
    + ("  UNVERAENDERT" if hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
       == ENGINE_SHA else "  DRIFT"))
out("=" * 104)

rep = "\n".join(BUF)
OUT.write_text(rep, encoding="utf-8")
print(rep)
