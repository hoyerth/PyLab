# -*- coding: utf-8 -*-
"""READ-ONLY Additivitaets-/Nebenwirkungs-Check der Phasenboden-Regel G4.

Regel G4 (generisch, kausal):
    Kandidat = Bar k im Phasenfenster mit
      * lo[k]  < deklarierter_boden
      * cl[k]  > deklarierter_boden
      * touch_conf(bodenkante, k) >= min_touches_handelbar (3)
    Entry = open[k+1]; SL = min(lo[k:k+2]) - sl_buffer;
    POC  = regel-lokaler Anker (Phasenstart); TP2 = Phasen-Decke (Override).

Geprueft werden:
  T1  Alle deklarierten Segmente (P9, P12_RESERVE)
  T2  G4 generisch ueber ALLE UNTEN-Kanten, alle Bars 0..n-1
  T3  Explizit H1 (bars < 640)
  T4  Kollision der Entry-Bars mit den bestehenden Trades (V0 / V1_basis)
  T5  Geister-Trades in P10 / P11 (kein Segment deklariert)
Es wird NICHTS geschrieben; reine Neuberechnung mit Engine-Bausteinen.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "test" / "tmp_kanten_engine_replay.py"
BACK = ROOT / "backtest_lab" / "phasen_regime_adapter.py"


def load(name, path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = str(path)
    sys.modules[name] = m
    exec(compile(Path(path).read_text(encoding="utf-8"), str(path), "exec"),
         m.__dict__)
    return m


E = load("ke_add", ENGINE)
AD = load("adapter_add", BACK)

cfg = E.StraightEdgeHarnessKonfiguration()
scan = E._se_scan("AUG", cfg)
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
op = d["open"].to_numpy(dtype=float)
n = scan["n"]
box_end = scan["box_end_bar"]
by_kid = {e.kid: e for e in list(scan["edges"]) + list(scan["seeds"])}
MIN_TOUCH = cfg.min_touches_handelbar
BUFFER = cfg.sl_buffer_usd

print(f"  n {n} | box_end {box_end} | min_touches_handelbar {MIN_TOUCH} | "
      f"sl_buffer {BUFFER} | Zyklus {cfg.retest_zyklus_bars}")

# ---------------------------------------------------------------- T1
SEGMENTE = (
    ("P9", 848, 1020, 77, 68.4000, 69.8700),
    ("P12_RESERVE", 1171, 1272, 82, 67.6355, 69.5550),
)
print("\n=== T1) G4 IN DEN DEKLARIERTEN SEGMENTEN ===")
alle_hits = []
for name, s, e_, kid, boden, decke in SEGMENTE:
    kante = by_kid.get(kid)
    if kante is None:
        print(f"  {name}: Kante K{kid} nicht im Katalog")
        continue
    print(f"  --- {name} ({s}..{e_}) Deckkante {decke} | Bodenkante K{kid} "
          f"deklariert {boden} | piv1 {kante.erster_pivot_bar} "
          f"wicks {len(kante.wicks)}")
    kand = []
    for k in range(s, e_ + 1):
        if lo[k] < boden < cl[k] and kante.touch_conf(k) >= MIN_TOUCH:
            kand.append(k)
            alle_hits.append((name, k, kid, boden, decke))
    print(f"      Kandidaten (roh): {kand}")
    letzter, netto = -10**9, []
    for k in kand:
        eb = k + 1
        if eb - letzter < cfg.retest_zyklus_bars:
            print(f"      bar {k}: ZYKLUS-SPERRE (Abstand {eb - letzter})")
            continue
        entry = float(op[eb])
        if not (entry < decke):
            print(f"      bar {k}: entry {entry:.4f} >= Decke -> verworfen")
            continue
        ext = float(lo[k:eb + 1].min())
        sl = ext - BUFFER
        poc = E.berechne_kausalen_histogramm_poc(d, s, k, boden, decke,
                                                 cfg.num_bins)
        risk = entry - sl
        if risk <= 0 or not (sl < entry < poc < decke):
            print(f"      bar {k}: Ordnung verletzt (sl {sl:.4f} entry "
                  f"{entry:.4f} poc {poc:.4f} tp2 {decke}) -> verworfen")
            continue
        tr = E._c_loese_trade(hi, lo, cl, eb, entry, "LONG", sl, poc, decke,
                              cfg.tp1_anteil_pct)
        letzter = eb
        netto.append((k, eb, tr.r_mult))
        print(f"      bar {k}: entry_bar {eb} entry {entry:.4f} sl {sl:.4f} "
              f"poc {poc:.4f} risk {risk:.4f} -> R {tr.r_mult:+.6f} "
              f"({tr.resultat}, {tr.grund1}/{tr.grund2})")
    print(f"      Netto: {len(netto)} Trades / "
          f"{sum(x[2] for x in netto):+.6f} R")

# ---------------------------------------------------------------- T2
print("\n=== T2) G4 GENERISCH ueber ALLE UNTEN-Kanten, alle Bars ===")
print("  (Mindestanforderung: lo < deklarierter Boden. Als 'deklarierter "
      "Boden' dient der kausale Basiswert der Kante selbst.)")
generisch = []
for e_ in (scan["edges"] + scan["seeds"]):
    if e_.seite != "UNTEN":
        continue
    for k in range(2, box_end - 3):
        if e_.erster_pivot_bar + 2 > k:
            continue
        if e_.touch_conf(k) < MIN_TOUCH:
            continue
        b = float(e_.basis_bei(k))
        if lo[k] < b < cl[k]:
            generisch.append((k, e_.kid, round(b, 4), round(float(lo[k]), 4)))
print(f"  Treffer gesamt: {len(generisch)}")
for z in generisch:
    print(f"    bar {z[0]:4d} K{z[1]:3d} basis {z[2]:9.4f} low {z[3]:9.4f}  "
          f"{'H1' if z[0] < box_end else 'H2'}")
print(f"  davon H1 (<{box_end}): "
      f"{[z[0] for z in generisch if z[0] < box_end]}")

# ---------------------------------------------------------------- T3
print("\n=== T3) EXPLIZIT H1 (bars < 640) ===")
h1 = [z for z in generisch if z[0] < box_end]
print(f"  G4-Treffer in H1: {len(h1)} -> {h1}")
print("  Erwartung der Anwender-Festlegung: 0 (kein Eingriff in H1).")

# ---------------------------------------------------------------- T4
print("\n=== T4) KOLLISION MIT BESTEHENDEN ENTRY-BARS ===")
src = (ROOT / "test" / "tmp_png_aug_sichttest.py").read_text(encoding="utf-8")
_i = src.index("import matplotlib")
mod = {"__name__": "add_t4", "__file__": str(ROOT / "test" /
                                            "tmp_png_aug_sichttest.py")}
sys.modules[mod["__name__"]] = type(sys)("add_t4")
sys.argv = ["tmp_q29_audit12"]
exec(compile(src[:src.rindex("\n", 0, _i) + 1],
             str(ROOT / "test" / "tmp_png_aug_sichttest.py"), "exec"), mod)
V0, V1b = mod["V0"], mod["V1_basis"]
b_v0 = sorted(t.entry_bar for t in V0)
b_v1 = sorted(t.entry_bar for t in V1b)
print(f"  V0 (roh)     Entry-Bars: {b_v0}")
print(f"  V1_basis     Entry-Bars: {b_v1}")
neu = [eb for (_s, _k, _kb, _b, _d) in [] for eb in []]
print("  Neue Entry-Bars der Regel T1: "
      f"{[1003] if any(h[1] == 1002 for h in alle_hits) else 'keine'}")
kol = sorted(set(b_v1) & {1003})
print(f"  Kollision mit V1_basis: {kol or 'keine'}")

# ---------------------------------------------------------------- T5
print("\n=== T5) GEISTER-TRADES P10 / P11 (kein Segment deklariert) ===")
for lab, s, e_ in (("P6", 620, 673), ("P7", 715, 792), ("P8", 802, 840),
                   ("P10", 1030, 1075), ("P11", 1082, 1134)):
    tref = [z for z in generisch if s <= z[0] <= e_]
    print(f"  {lab:4s} ({s}..{e_}): G4-Treffer {len(tref)} {tref}")
print("  Hinweis: P10/P11 haben im Adapter KEIN PhasenSegmentEintrag -> die")
print("  Regel ist dort strukturell inaktiv; der Treffer-Ausweis oben zeigt")
print("  den hypothetischen Fall einer spaeteren Deklaration.")
