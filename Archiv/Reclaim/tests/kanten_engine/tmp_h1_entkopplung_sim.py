# -*- coding: utf-8 -*-
"""READ-ONLY In-Memory-Simulation der Entkopplung (Arbeitsanweisung Mentor).

Modifiziert werden NUR Kopien der Engine im RAM (exec/compile), niemals die
Datei `test/tmp_kanten_engine_replay.py` auf der Platte.

Varianten:
  V0        arretiert (Referenz)
  VA        Barriere 2: Stacking-Gate vor _c_loese_trade deaktiviert
  VB        Barriere 1: Sweep-Pruefung entkoppelt (reiner Durchstich, min=0.00)
  VB05      Barriere 1: wie VB, aber Mindest-Durchstich 0.05 % (Sensitivitaet)
  VC        Barriere 1 + 2 gemeinsam (min=0.00)
  VC05      Barriere 1 + 2 gemeinsam (min=0.05)

Je Variante: frischer Modul-Load + frischer _se_scan (Scan mutiert!).
Fenster: AUG - einmal BOX (box_end_bar = 644, arretiert) und einmal VOLL (n).
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
_ZIEL_BARS = (229, 242, 244, 529, 565)


def load(name: str, src: str):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(P)
    sys.modules[name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


with open(P, encoding="utf-8", newline="") as f:
    SRC = f.read()

# --- Anker (CRLF-exakt) ---------------------------------------------------
G3O = ("        dist_o = (hi[k] - basis) / basis * 100.0\r\n"
       "        if not (hi[k] > basis and band < dist_o\r\n"
       "                <= cfg.max_sweep_ueberdehnung_pct):\r\n")
G3U = ("    dist_u = (basis - lo[k]) / basis * 100.0\r\n"
       "    if not (lo[k] < basis and band < dist_u\r\n"
       "            <= cfg.max_sweep_ueberdehnung_pct):\r\n")
G2 = ("            if dist <= cfg.touch_band_pct:\r\n"
      "                continue                        # Beruehrung/in-band (Schatten)\r\n")
G2S = ("            if cfg.touch_band_pct < d <= cfg.max_sweep_ueberdehnung_pct:\r\n"
       "                pool.append(e)\r\n")
GSTACK_START = "            _vor = letzter_trade.get(kd.kid)"

for nm, an in (("G3O", G3O), ("G3U", G3U), ("G2", G2), ("G2S", G2S)):
    assert SRC.count(an) == 1, f"Anker {nm}: {SRC.count(an)} Treffer"
assert SRC.count(GSTACK_START) == 1, f"GSTACK: {SRC.count(GSTACK_START)} Treffer"


def _stacking_block_text(src: str) -> str:
    """Schneidet den Stacking-Gate-Block ab der Marker-Zeile bis zum `continue`."""
    start = src.index(GSTACK_START)
    zeilenende = src.index("\r\n", start) + 2
    cpos = src.index("                    continue\r\n", zeilenende)
    cende = cpos + len("                    continue\r\n")
    return src[start:cende]


def entferne_stacking(src: str) -> str:
    blk = _stacking_block_text(src)
    neu = ("            # [IN-MEMORY VARIANTE A/C] Stacking-Gate deaktiviert:\r\n"
           "            # Zeitliche Entzerrung ausschliesslich via retest_zyklus_bars.\r\n"
           "            _vor = letzter_trade.get(kd.kid)\r\n")
    return src.replace(blk, neu, 1)


def entkopple_band(src: str, sweep_min: float) -> str:
    s = src.replace(
        G3O, "        dist_o = (hi[k] - basis) / basis * 100.0\r\n"
             "        if not (hi[k] > basis and SWEEP_MIN < dist_o\r\n"
             "                <= cfg.max_sweep_ueberdehnung_pct):\r\n", 1)
    s = s.replace(
        G3U, "    dist_u = (basis - lo[k]) / basis * 100.0\r\n"
             "    if not (lo[k] < basis and SWEEP_MIN < dist_u\r\n"
             "            <= cfg.max_sweep_ueberdehnung_pct):\r\n", 1)
    s = s.replace(
        G2, "            if dist <= SWEEP_MIN:\r\n"
            "                continue                        # nur Durchstich zaehlt\r\n", 1)
    s = s.replace(
        G2S, "            if SWEEP_MIN < d <= cfg.max_sweep_ueberdehnung_pct:\r\n"
             "                pool.append(e)\r\n", 1)
    s = s.replace("V3_TP_MINDIST_PCT: float = 1.5",
                  f"V3_TP_MINDIST_PCT: float = 1.5\r\nSWEEP_MIN: float = {sweep_min}", 1)
    return s


VARIANTEN = {
    "V0   arretiert": SRC,
    "VA   Stacking-Gate AUS": entferne_stacking(SRC),
    "VB   Sweep entkoppelt 0.00": entkopple_band(SRC, 0.0),
    "VB05 Sweep entkoppelt 0.05": entkopple_band(SRC, 0.05),
    "VC   beide (0.00)": entkopple_band(entferne_stacking(SRC), 0.0),
    "VC05 beide (0.05)": entkopple_band(entferne_stacking(SRC), 0.05),
}


def lauf(src: str, name: str, box: bool):
    mod = load(name, src)
    cfg = mod.StraightEdgeHarnessKonfiguration()
    sc = mod._se_scan("AUG", cfg)
    if not box:
        sc["box_end_bar"] = sc["n"]
    tr, st = mod._se_trades(sc, cfg)
    return tr, st, sc, mod


def zeile(t, ts) -> str:
    return (f"  {t.bar:5d} {ts.iloc[t.bar].strftime('%d.%m %H:%M'):>12} "
            f"{t.richtung:5s} K{t.kid:3d} basis={t.basis:8.3f} "
            f"sweep={t.sweep:8.3f} entry={t.entry_bar:5d} E={t.entry:8.3f} "
            f"SL={t.sl:8.3f} TP1={t.poc:8.3f} TP2={t.tp2:8.3f} "
            f"exits={t.exit1_bar:4d}/{t.exit2_bar:4d} g1={t.grund1:>4s} "
            f"{t.r:+7.2f}R {t.resultat}")


print("=" * 126)
print("ENTKOPPLUNGS-SIMULATION (READ-ONLY, Engine-Datei unveraendert) - AUG")
print("=" * 126)

ergeb = {}
for label, src in VARIANTEN.items():
    for box in (True, False):
        fen = "BOX  (box_end=644)" if box else "VOLL (n=1288)"
        tr, st, sc, mod = lauf(src, f"sim_{abs(hash(label + fen)) % 10**8}", box)
        key = (label, fen)
        ergeb[key] = (tr, st, sc)
        sig = [(t.bar, t.richtung, t.kid, t.entry_bar, round(t.r, 4)) for t in tr]
        print("")
        print("-" * 126)
        print(f"{label:26s} | {fen:18s} | Kanten {len(sc['edges']):3d} | "
              f"Trades {len(tr):2d} | Netto-R {sum(t.r for t in tr):+7.2f} | "
              f"Stacking {st.get('stacking_blockiert', 0)} | "
              f"Zyklus {st.get('zyklus_blockiert', 0)}")
        print("-" * 126)
        ts = sc["d"]["ts"]
        for t in tr:
            print(zeile(t, ts))

print("")
print("=" * 126)
print("DIFF GEGEN V0 (Voll-Fenster): welche Trades kommen dazu / fallen weg")
print("=" * 126)
v0 = ergeb[("V0   arretiert", "VOLL (n=1288)")][0]
s0 = {(t.bar, t.richtung, t.kid, t.entry_bar): t.r for t in v0}
for label in VARIANTEN:
    if label.startswith("V0"):
        continue
    tr = ergeb[(label, "VOLL (n=1288)")][0]
    s1 = {(t.bar, t.richtung, t.kid, t.entry_bar): t.r for t in tr}
    neu = [k for k in s1 if k not in s0]
    weg = [k for k in s0 if k not in s1]
    print("")
    print(f"  {label}:  {len(tr)} Trades / {sum(t.r for t in tr):+.2f} R "
          f"(V0: {len(v0)} / {sum(t.r for t in v0):+.2f} R, "
          f"Delta {sum(t.r for t in tr) - sum(t.r for t in v0):+.2f} R)")
    for k in neu:
        print(f"    + NEU   bar {k[0]:4d} {k[1]:5s} K{k[2]:3d} entry {k[3]:4d} "
              f"-> {s1[k]:+7.2f} R")
    for k in weg:
        print(f"    - WEG   bar {k[0]:4d} {k[1]:5s} K{k[2]:3d} entry {k[3]:4d} "
              f"-> {s0[k]:+7.2f} R")
    for k in s0:
        if k in s1 and abs(s0[k] - s1[k]) > 1e-9:
            print(f"    ~ GEAENDERT bar {k[0]:4d} {k[1]:5s} K{k[2]:3d} "
                  f"entry {k[3]:4d} -> {s0[k]:+.2f} R  ==>  {s1[k]:+.2f} R")

print("")
print("=" * 126)
print("ZIEL-BARS 229/242/244/529/565 -- Verhalten in jeder Variante (VOLL)")
print("=" * 126)
print(f"  {'Bar':>5} " + "".join(f"{lab.split()[0]:>12s}" for lab in VARIANTEN))
for zb in _ZIEL_BARS:
    zeile_out = f"  {zb:5d} "
    for label in VARIANTEN:
        tr = ergeb[(label, "VOLL (n=1288)")][0]
        hits = [t for t in tr if t.bar == zb]
        if hits:
            t = hits[0]
            zeile_out += f"{'K' + str(t.kid):>12s}"
        else:
            zeile_out += f"{'--':>12s}"
    print(zeile_out)
print("")
print("  (Kante des Trades am jeweiligen Signal-Bar; '--' = kein Trade)")

print("")
print("=" * 126)
print("STACKING-LISTE (geblockte Setups) je Variante, VOLL")
print("=" * 126)
for label in VARIANTEN:
    tr, st, sc = ergeb[(label, "VOLL (n=1288)")]
    lst = st.get("stacking_liste") or []
    print(f"  {label:26s}: {len(lst)} Sperren")
    for z in lst:
        print(f"      {z}")
