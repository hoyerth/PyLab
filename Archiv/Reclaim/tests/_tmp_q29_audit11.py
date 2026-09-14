# -*- coding: utf-8 -*-
"""READ-ONLY Papier-Konzept: generische Phasen-Boden-Reclaim-Regel an K77.

Frage: Wo feuert eine GENERISCHE Regel (nicht 'Bar 1002 hartkodiert')?
Varianten:
  G0  jeder Bar mit L < boden und C > boden
  G1  nur bei neuem Extremtief der Phase
  G2  nur wenn zusaetzlich K77 als ausserste Linie bestaetigt ist
  + jeweils 12-Bar-Entry-Mindestabstand (kid-gebuendelt, wie Engine)
Exit-Modell (Papier): SL = Sweep-Tief - sl_buffer, TP1 = POC(boden..decke),
                      TP2 = Decke-Override. Ein- und Ausstieg kaufmaennisch.
Keine Engine-Aenderung; reine Neuberechnung mit Engine-Bausteinen.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name, path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = str(path)
    sys.modules[name] = m
    exec(compile(Path(path).read_text(encoding="utf-8"), str(path), "exec"),
         m.__dict__)
    return m


E = load("ke_generic", P)
cfg = E.StraightEdgeHarnessKonfiguration()
scan = E._se_scan("AUG", cfg)
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
op = d["open"].to_numpy(dtype=float)
by_kid = {e.kid: e for e in list(scan["edges"]) + list(scan["seeds"])}
K77 = by_kid[77]

BODEN = 68.4000
DECKE = 69.8700
START, ENDE = 848, 1020
ENTRY_LIMIT = DECKE

print(f"  K77: piv1 {K77.erster_pivot_bar} geb {K77.geburts_bar} "
      f"wicks {[(b, round(p, 3)) for b, p in K77.wicks]}")
print(f"  Boden {BODEN} | Decke {DECKE} | Fenster {START}..{ENDE} | "
      f"sl_buffer {cfg.sl_buffer_usd} | Zyklus {cfg.retest_zyklus_bars}")

roh, neues_extrem, ausserste, v3 = [], [], [], []
lauf_min = None
for k in range(START, ENDE + 1):
    if lauf_min is None or lo[k] < lauf_min:
        lauf_min = float(lo[k])
        neu = True
    else:
        neu = False
    if lo[k] < BODEN and cl[k] > BODEN:
        roh.append(k)
        if neu:
            neues_extrem.append(k)
        if K77.touch_conf(k) >= cfg.min_touches_handelbar:
            v3.append(k)
        confirms = K77.erster_pivot_bar + 2 <= k
        _b77 = K77.basis_bei(k)
        ist_ausserste = all(
            e.basis_bei(k) > _b77
            for e in (scan["edges"] + scan["seeds"])
            if e.seite == "UNTEN" and e is not K77
            and e.erster_pivot_bar + 2 <= k)
        if neu and confirms and ist_ausserste:
            ausserste.append(k)

for lab, kand in (("G0 roh (L<boden, C>boden)", roh),
                  ("G1 + neues Extremtief", neues_extrem),
                  ("G2 + K77 bestaetigt + ausserste Wand", ausserste),
                  ("G4 + V-S>=3 der Bodenkante (kausal)", v3)):
    print(f"\n  --- {lab}: Kandidaten-Bars {kand}")
    letzter_entry = -10**9
    getroffen = []
    for k in kand:
        if k + 1 - letzter_entry < cfg.retest_zyklus_bars:
            print(f"      bar {k}: ZYKLUS-SPERRE (Abstand "
                  f"{k + 1 - letzter_entry} < {cfg.retest_zyklus_bars})")
            continue
        basis = K77.basis_bei(k)
        std = 1
        entry_bar = k + std
        entry = float(op[entry_bar])
        if entry >= ENTRY_LIMIT:
            print(f"      bar {k}: entry {entry:.4f} >= Decke -> verworfen")
            continue
        sweep_ext = float(lo[k:k + std + 1].min())
        sl = sweep_ext - cfg.sl_buffer_usd
        poc = E.berechne_kausalen_histogramm_poc(d, START, k, BODEN, DECKE,
                                                 cfg.num_bins)
        risk = entry - sl
        if risk <= 0:
            print(f"      bar {k}: risk <= 0 -> verworfen")
            continue
        tr = E._c_loese_trade(hi, lo, cl, entry_bar, entry, "LONG", sl, poc,
                              DECKE, cfg.tp1_anteil_pct)
        letzter_entry = entry_bar
        getroffen.append((k, entry_bar, entry, sl, poc, tr.r_mult,
                          tr.resultat, tr.grund1, tr.grund2,
                          tr.exit1_bar, tr.exit2_bar))
        print(f"      bar {k}: basis {basis:.4f} entry_bar {entry_bar} "
              f"entry {entry:.4f} sl {sl:.4f} poc {poc:.4f} "
              f"risk {risk:.4f} -> R {tr.r_mult:+.6f} ({tr.resultat}, "
              f"{tr.grund1}/{tr.grund2}, exits {tr.exit1_bar}/{tr.exit2_bar})")
    print(f"      Summe: {len(getroffen)} Trades / "
          f"{sum(x[5] for x in getroffen):+.6f} R")

print("\n  --- G3 FORCIERT: bar 1002 ohne Zyklussperre (Papier-Rechnung) ---")
for _k in (1002,):
    _basis = K77.basis_bei(_k)
    _eb = _k + 1
    _entry = float(op[_eb])
    _ext = float(lo[_k:_eb + 1].min())
    _sl = _ext - cfg.sl_buffer_usd
    for _ps, _lab in ((0, "poc_start 0 (IST)"), (START, "poc_start 848")):
        _poc = E.berechne_kausalen_histogramm_poc(d, _ps, _k, BODEN, DECKE,
                                                  cfg.num_bins)
        _tr = E._c_loese_trade(hi, lo, cl, _eb, _entry, "LONG", _sl, _poc,
                               DECKE, cfg.tp1_anteil_pct)
        _ok = _sl < _entry < _poc < DECKE
        print(f"      {_lab:20s} poc {_poc:.4f} ordnung-ok {_ok} -> "
              f"R {_tr.r_mult:+.6f} ({_tr.resultat}, {_tr.grund1}/"
              f"{_tr.grund2}, exits {_tr.exit1_bar}/{_tr.exit2_bar})")
    print(f"      (basis {_basis:.4f} entry_bar {_eb} entry {_entry:.4f} "
          f"SL {_sl:.4f})")

print("\n  Vergleich: Arm A0 (IST, Baseline v0.1) = 15 Trades / "
      "+46.866348 R | P9-Beitrag +5.4212 R")
print("  Eine additive Regel waere nur dann zulaessig, wenn sie mit KEINEM "
      "bestehenden Entry-Bar kollidiert (getradete_entry_bars).")
bestehend = {993, 980 + 1, 1020 + 1}
print(f"  Bekannte P9-Entry-Bars (A0/LONG/2-seitig-Varianten): "
      f"{sorted(bestehend)}")
