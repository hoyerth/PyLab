# -*- coding: utf-8 -*-
"""Soll/Ist-Abgleich der 3 Basic-Kanten (menschliche Sicht) gegen Modus A/B.

Je Soll-Kante (Seite, Zeitraum, Level, erwartete Touches):
  1) Menschliche Sicht: alle Pivot-Extrema der Seite im Zeitraum nahe dem Level
     (Pivot-Definition wie Engine: 2-Bar-Lookback). Band +/-0.15 USD wie
     DENSITY_BAND; zusaetzlich +/-0.30 als 'weiter' markiert.
  2) Engine A: existiert eine Kante im Band? K-ID, Geburt, Zustand, registrierte
     Touches (nur die im Zeitraum), verpasste Soll-Kontakte.
  3) Engine B: dito (Anker statt Balance).

Rein lesend, Terminal-Ausgabe (kein Datei-Schreiben).
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tmp_kanten_engine_replay as m  # noqa: E402

BAND = 0.15  # wie DENSITY_BAND

SOLL = [
    dict(name="UPPER 66.46", seite="OBEN",
         von="2026-08-11 03:45", bis="2026-08-18 03:00", level=66.46, soll=5),
    dict(name="LOWER 63.67", seite="UNTEN",
         von="2026-08-10 07:30", bis="2026-08-18 17:30", level=63.67, soll=7),
    dict(name="LOWER-MINOR 64.20", seite="UNTEN",
         von="2026-08-11 08:30", bis="2026-08-14 02:30", level=64.20, soll=4),
]


def _kontakte(hi, lo, seite, i0, i1, level):
    """Pivot-Extrema der Seite in [i0, i1] nahe level (menschliche Sicht)."""
    out = []
    for mm in range(i0, i1 + 1):
        if seite == "OBEN":
            if hi[mm] > hi[mm - 1] and hi[mm] > hi[mm - 2] and \
               hi[mm] > hi[mm + 1] and hi[mm] > hi[mm + 2]:
                out.append((mm, float(hi[mm])))
        else:
            if lo[mm] < lo[mm - 1] and lo[mm] < lo[mm - 2] and \
               lo[mm] < lo[mm + 1] and lo[mm] < lo[mm + 2]:
                out.append((mm, float(lo[mm])))
    # nur nahe dem Level
    out = [(b, p) for b, p in out if abs(p - level) <= 0.30]
    return out


def _kante_im_band(erg, seite, level):
    """Beste Kante der Seite, deren Referenz(en) im +-BAND um level liegen."""
    best, best_dist = None, 1e9
    for kid, k2 in erg.kanten.items():
        if k2.seite != seite:
            continue
        for ref in (k2.basis_preis, k2.balance_preis, k2.anker_extremum):
            if ref <= 0.0:
                continue
            dist = abs(ref - level)
            if dist <= BAND and dist < best_dist:
                best, best_dist = (kid, k2), dist
    return best


def _ts(b):
    return pd.Timestamp(d["ts"].iloc[b]).strftime("%m.%d %H:%M")


def main() -> None:
    global d, hi, lo
    d = m._lade_fenster("AUG")
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    ts_arr = d["ts"].to_numpy().astype("datetime64[ns]")
    erg_a = m._replay("AUG", m.HarnessKonfiguration(max_tage=60, modus="A"))
    erg_b = m._replay("AUG", m.HarnessKonfiguration(max_tage=60, modus="B"))

    for spec in SOLL:
        i0 = int(np.searchsorted(ts_arr, np.datetime64(spec["von"])))
        i1 = int(np.searchsorted(ts_arr, np.datetime64(spec["bis"]), side="right")) - 1
        lvl = spec["level"]
        print("\n" + "=" * 104)
        print(f"SOLL-KANTE {spec['name']}  [{spec['seite']}]  level={lvl:.2f}  "
              f"Zeitraum {spec['von'][5:]}..{spec['bis'][5:]}  "
              f"(bars {i0}..{i1})  |  Soll-Touches lt. Mensch: {spec['soll']}")
        print("=" * 104)

        # --- Menschliche Sicht ---
        kontakte = _kontakte(hi, lo, spec["seite"], i0, i1, lvl)
        print(f"MENSCHLICHE SICHT (Pivot-Extrema im Zeitraum nahe level): "
              f"{len(kontakte)} Kontakte im +-0.30")
        for b, p in kontakte:
            band = "<=0.15" if abs(p - lvl) <= BAND else "<=0.30"
            print(f"    bar {b:4d} ({_ts(b)}) preis={p:8.3f}  (+-{band})")

        # --- Engine A / B ---
        for name, erg in (("MODUS A (V1)", erg_a), ("MODUS B (V2)", erg_b)):
            treffer = _kante_im_band(erg, spec["seite"], lvl)
            print(f"\n  [{name}]")
            if treffer is None:
                print("    KEINE Kante im +-0.15-Band um das Soll-Level!")
                continue
            kid, k2 = treffer
            refs = (f"basis={k2.basis_preis:.3f} bal={k2.balance_preis:.3f}"
                    + (f" anker={k2.anker_extremum:.3f}"
                       if k2.anker_extremum > 0 else ""))
            print(f"    K{kid} {k2.seite} geb_bar={k2.geburts_bar} "
                  f"({_ts(k2.geburts_bar)}) zustand={k2.zustand} "
                  f"typB={'JA' if k2.ist_typ_b else '--'} "
                  f"hand={'JA' if k2.ist_handelbar else '--'} | {refs}")
            reg = [(t.pivot_bar, t.preis) for t in k2.touche
                   if i0 <= t.pivot_bar <= i1]
            print(f"    registrierte Touches im Zeitraum: {len(reg)} "
                  f"(gesamt {k2.touch_anzahl})")
            for b, p in reg:
                print(f"      touch bar {b:4d} ({_ts(b)}) preis={p:8.3f}")
            # verpasste Soll-Kontakte (in menschl. Sicht, nicht registriert)
            regb = {b for b, _ in reg}
            verpasst = [(b, p) for b, p in kontakte
                        if b not in regb and abs(p - lvl) <= BAND]
            if verpasst:
                print(f"    VERPASSTE Soll-Kontakte (<=0.15, nicht als Touch): "
                      f"{len(verpasst)}")
                for b, p in verpasst:
                    print(f"      bar {b:4d} ({_ts(b)}) preis={p:8.3f}")
        print("-" * 104)


if __name__ == "__main__":
    main()
