# -*- coding: utf-8 -*-
"""READ-ONLY Grenzkarte retest_zyklus_bars = 0..24 UNTER DEM NEUEN REGIME.

Regime: Stacking-Gate entfernt (Barriere 2), Sweep-Bandbreite entkoppelt
(Barriere 1, touch_band_pct bleibt reine Touch-Erkennung). Verglichen werden
zwei Zaehlungs-Referenzen der Zyklus-Uhr:

  SWEEP-Ref (Code heute):  k - letzter_sweep_bar < v
  ENTRY-Ref (Variante B):  entry_bar - letzter_sweep_bar(=entry) < v

Kein File-Overwrite, keine Engine-Aenderung auf der Platte: exec(compile())
in eine isolierte Modulkopie, modifiziert wird nur der RAM-Text.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, src: str):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(P)
    sys.modules[name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


with open(P, encoding="utf-8", newline="") as f:
    SRC = f.read()

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
GSTACK = "            _vor = letzter_trade.get(kd.kid)"
GSET = "            kd.letzter_sweep_bar = k\r\n"
GF3 = "            if k <= kd.letzter_sweep_bar:\r\n"
GF3B = "            if entry_bar <= kd.letzter_sweep_bar:\r\n"
for nm, an in (("G3O", G3O), ("G3U", G3U), ("G2", G2), ("G2S", G2S),
               ("GSET", GSET), ("GF3", GF3)):
    assert SRC.count(an) == 1, f"Anker {nm}: {SRC.count(an)} Treffer"
assert SRC.count(GSTACK) == 1


def entferne_stacking(src: str) -> str:
    start = src.index(GSTACK)
    zeilenende = src.index("\r\n", start) + 2
    cpos = src.index("                    continue\r\n", zeilenende)
    cende = cpos + len("                    continue\r\n")
    blk = src[start:cende]
    return src.replace(blk,
                       "            # [RAM] Stacking-Gate deaktiviert\r\n"
                       "            _vor = letzter_trade.get(kd.kid)\r\n", 1)


def entkopple_band(src: str) -> str:
    s = src.replace(
        G3O, "        dist_o = (hi[k] - basis) / basis * 100.0\r\n"
             "        if not (hi[k] > basis and 0.0 < dist_o\r\n"
             "                <= cfg.max_sweep_ueberdehnung_pct):\r\n", 1)
    s = s.replace(
        G3U, "    dist_u = (basis - lo[k]) / basis * 100.0\r\n"
             "    if not (lo[k] < basis and 0.0 < dist_u\r\n"
             "            <= cfg.max_sweep_ueberdehnung_pct):\r\n", 1)
    s = s.replace(
        G2, "            if dist <= 0.0:\r\n"
            "                continue                        # nur Durchstich zaehlt\r\n", 1)
    s = s.replace(
        G2S, "            if 0.0 < d <= cfg.max_sweep_ueberdehnung_pct:\r\n"
             "                pool.append(e)\r\n", 1)
    return s


def auf_entry_referenz(src: str) -> str:
    s = src.replace(GSET, "            kd.letzter_sweep_bar = entry_bar\r\n", 1)
    s = s.replace(GF3, GF3B, 1)
    return s


def mit_zyklus(src: str, v: int) -> str:
    return src.replace("retest_zyklus_bars: int = 12",
                       f"retest_zyklus_bars: int = {v}", 1)


BASIS = entferne_stacking(entkopple_band(SRC))


def lauf(src: str, name: str):
    mod = load(name, src)
    cfg = mod.StraightEdgeHarnessKonfiguration()
    sc = mod._se_scan("AUG", cfg)
    sc["box_end_bar"] = sc["n"]
    tr, st = mod._se_trades(sc, cfg)
    return tr, st, sc


print("=" * 132)
print("GRENZKARTE retest_zyklus_bars = 0..24 -- REGIME: Stacking AUS + Sweep-Band entkoppelt")
print("Basis: AUG Voll-Fenster n=1288, read-only RAM-Kopien, je Variante frischer _se_scan")
print("=" * 132)
kopf = (f"  {'v':>3} | {'Trades':>6} | {'Netto-R':>8} | {'Zyklus-Sperren':>14} | "
        f"{'K20-Setups 12.08. (bar->entry/R)':52s} | {'Verluste':>8}")
print("")
print("  SWEEP-Ref  (Code heute: k - letzter_sweep_bar < v)")
print("-" * 132)
print(kopf)
for v in range(0, 25):
    tr, st, sc = lauf(mit_zyklus(BASIS, v), f"gz_s_{v}")
    k20 = [t for t in tr if t.kid == 20 and 200 < t.bar < 300]
    k20s = ("kein K20-Setup" if not k20 else " | ".join(
        f"{t.bar}->{t.entry_bar} {t.r:+.2f}R" for t in k20))
    verl = sum(1 for t in tr if t.r < 0)
    print(f"  {v:3d} | {len(tr):6d} | {sum(t.r for t in tr):+8.2f} | "
          f"{st.get('zyklus_blockiert', 0):14d} | {k20s:52s} | {verl:8d}")

print("")
print("  ENTRY-Ref  (Variante B: entry_bar - letzter_entry_bar < v)")
print("-" * 132)
print(kopf)
for v in range(0, 25):
    tr, st, sc = lauf(auf_entry_referenz(mit_zyklus(BASIS, v)), f"gz_e_{v}")
    k20 = [t for t in tr if t.kid == 20 and 200 < t.bar < 300]
    k20s = ("kein K20-Setup" if not k20 else " | ".join(
        f"{t.bar}->{t.entry_bar} {t.r:+.2f}R" for t in k20))
    verl = sum(1 for t in tr if t.r < 0)
    print(f"  {v:3d} | {len(tr):6d} | {sum(t.r for t in tr):+8.2f} | "
          f"{st.get('zyklus_blockiert', 0):14d} | {k20s:52s} | {verl:8d}")

print("")
print("=" * 132)
print("TRADE-LISTEN DER VIER KANDIDATEN")
print("=" * 132)
for label, src in (
        ("SWEEP-Ref v=12", mit_zyklus(BASIS, 12)),
        ("SWEEP-Ref v=13", mit_zyklus(BASIS, 13)),
        ("ENTRY-Ref v=11", auf_entry_referenz(mit_zyklus(BASIS, 11))),
        ("ENTRY-Ref v=12", auf_entry_referenz(mit_zyklus(BASIS, 12)))):
    tr, st, sc = lauf(src, f"lst_{abs(hash(label)) % 10**8}")
    print("")
    print("-" * 132)
    print(f"{label:16s} | Trades {len(tr):2d} | Netto-R {sum(t.r for t in tr):+7.2f} | "
          f"Zyklus-Sperren {st.get('zyklus_blockiert', 0):2d}")
    print("-" * 132)
    ts = sc["d"]["ts"]
    for t in tr:
        print(f"  {t.bar:5d} {ts.iloc[t.bar].strftime('%d.%m %H:%M'):>12} "
              f"{t.richtung:5s} K{t.kid:3d} basis={t.basis:8.3f} entry={t.entry_bar:5d} "
              f"E={t.entry:8.3f} SL={t.sl:8.3f} TP1={t.poc:8.3f} TP2={t.tp2:8.3f} "
              f"exits={t.exit1_bar:4d}/{t.exit2_bar:4d} {t.r:+7.2f}R {t.resultat}")
