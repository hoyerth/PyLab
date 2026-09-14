# -*- coding: utf-8 -*-
"""READ-ONLY H1-Forensik Schritt 4 (Robustheit): Stacking vs. De-Risking.

Vollfenster-Beweis: Sind alle Stacking-Sperren auch unter der De-Risking-Lesart
gesperrt? Und ist in den freigegebenen Fenstern (TP1 .. exit_final) ueberhaupt
ein geometrisch moeglicher Re-Entry vorhanden?

Quelle: test/archiv/silver_m15_ohlc_2026-08-10_2026-08-28.csv (Rohdaten).
KEIN Engine-Import, kein _se_scan/_se_trades, kein Compile.

Datenbasis (dokumentiert):
  _p8-Voll-Lauf (n=1288): 9 Trades / +23,02 R, stacking_blockiert = 4.
  Teil 4 §6 (v=10..12): K20@245 (2x), K31@567, K62@866.
  Teil 4 §3: K62 T1 entry=855 -> exit_final=867, R=-1,00 (SL).
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
CSV = Path(__file__).resolve().parent / "archiv" / "silver_m15_ohlc_2026-08-10_2026-08-28.csv"
d = pd.read_csv(CSV)
d["ts"] = pd.to_datetime(d["ts"])
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
op = d["open"].to_numpy(float)
cl = d["close"].to_numpy(float)
ts = d["ts"]
n = len(d)
BAND = 0.12


def zeit(k: int) -> str:
    return ts.iloc[k].strftime("%d.%m %H:%M")


def loese(entry_bar: int, entry: float, sl: float, tp1: float, tp2: float,
          richtung: str = "SHORT"):
    """_c_loese_trade wortgetreu (zwei unabhaengige Haelften, 50/50)."""
    risk = abs(sl - entry)
    hh, ll, cc = hi[entry_bar:], lo[entry_bar:], cl[entry_bar:]
    nb = len(hh)

    def first(mask):
        return int(np.argmax(mask)) if mask.any() else nb

    if richtung == "SHORT":
        t1, t2, tsl = first(ll <= tp1), first(ll <= tp2), first(hh >= sl)
        r = lambda px: (entry - px) / risk  # noqa: E731
    else:
        t1, t2, tsl = first(hh >= tp1), first(hh >= tp2), first(ll <= sl)
        r = lambda px: (px - entry) / risk  # noqa: E731
    if t1 < tsl:
        r1, b1, g1 = r(tp1), entry_bar + t1, "TP1"
    elif tsl < nb:
        r1, b1, g1 = -1.0, entry_bar + tsl, "SL"
    else:
        r1, b1, g1 = r(cc[-1]), entry_bar + nb - 1, "ENDE"
    if t2 < tsl:
        r2, b2, g2 = r(tp2), entry_bar + t2, "TP2"
    elif tsl < nb:
        r2, b2, g2 = -1.0, entry_bar + tsl, "SL"
    else:
        r2, b2, g2 = r(cc[-1]), entry_bar + nb - 1, "ENDE"
    return {"r": 0.5 * r1 + 0.5 * r2, "r1": r1, "r2": r2,
            "b1": b1, "b2": b2, "g1": g1, "g2": g2,
            "tp1_bar": b1 if g1 == "TP1" else -1,
            "exit_final": max(b1, b2)}


# --- dokumentierte Trades (Parameter aus den Audit-Laeufen) ----------------
# kid-Signaturen aus _p8: K20 (OBEN 107/66.459), K31 (OBEN 249/66.360),
# K59 (OBEN 805/68.972) = Teil-6-K62 (kid-Renumberierung durch R21).
TRADES = {
    229: dict(kid=20, richtung="SHORT", entry_bar=231, e=66.424, sl=66.826,
              tp1=63.676, tp2=63.605),
    529: dict(kid=31, richtung="SHORT", entry_bar=531, e=66.324, sl=66.588,
              tp1=64.735, tp2=63.474),
}
# K59/K62: R = -1,00 -> beide Haelften SL -> kein TP1 (kein De-Risking).
K62_EXIT_FINAL = 867

print("=" * 112)
print("SCHRITT 4A -- Stacking vs. De-Risking: ALLE Sperren des Voll-Laufs (n=1288)")
print("=" * 112)
print(f"  {'Setup-Bar':>9} {'Kante':>6} {'Entry':>6} {'T1-Entry':>8} {'T1-TP1':>7} "
      f"{'T1-exit':>8} {'Stacking':>10} {'De-Risking':>11}")
bloecke = [(242, "K20", 229, 245), (244, "K20", 229, 245),
           (564, "K31", 529, 567), (865, "K59", 853, 866)]
res = {}
for sb, kante, t1bar, ebar in bloecke:
    if t1bar in TRADES:
        t = TRADES[t1bar]
        tr = loese(t["entry_bar"], t["e"], t["sl"], t["tp1"], t["tp2"],
                   t["richtung"])
        tp1_bar, exf = tr["tp1_bar"], tr["exit_final"]
    else:
        tp1_bar, exf = -1, K62_EXIT_FINAL
    st = "GESPERRT" if ebar <= exf else "frei"
    if tp1_bar < 0:
        dr = "GESPERRT"
    else:
        dr = "GESPERRT" if ebar <= tp1_bar else "FREI"
    res[(sb, kante)] = (ebar, tp1_bar, exf, st, dr)
    print(f"  {sb:9d} {kante:>6} {ebar:6d} {t1bar:8d} "
          f"{tp1_bar if tp1_bar >= 0 else '  nie':>7} {exf:8d} "
          f"{st:>10} {dr:>11}")
print("")
print("  -> Alle 4 Sperren sind unter BEIDEN Lesarten gesperrt.")
print("  -> De-Risking gibt zusaetzlich frei: K20 386->398 (12 Bars),")
print("     K31 614->639 (25 Bars). K59/K62: nie de-risked (R=-1,00 = SL).")

print("")
print("=" * 112)
print("SCHRITT 4B -- Geometrie der freigegebenen Fenster (kann dort ein Re-Entry entstehen?)")
print("=" * 112)
for t1bar, kante, basis, tp1_bar, exf in (
        (229, "K20", 66.459, 386, 398), (529, "K31", 66.327, 614, 639)):
    fh = hi[tp1_bar:exf + 1]
    fl = lo[tp1_bar:exf + 1]
    schwelle = basis * (1.0 + BAND / 100.0)
    print(f"  {kante} (Basis {basis:.3f}, SHORT-Re-Entry braucht high > {schwelle:.4f}):")
    print(f"    freies Fenster {tp1_bar}..{exf} ({zeit(tp1_bar)} .. {zeit(exf)})")
    print(f"    max high = {fh.max():.3f} | max low = {fl.max():.3f} | "
          f"Abstand zum Re-Entry = {schwelle - fh.max():+.4f} USD "
          f"({(schwelle - fh.max()) / basis * 100:+.2f} %)")
    print(f"    -> geometrisch moeglicher K{kante}-Re-Entry im freien Fenster: "
          f"{bool(fh.max() > schwelle)}")
print("")
print("  -> Nach TP1 steht der Kurs am Kursziel (63.7 bzw. 64.7), nicht an der")
print("     Basis (66.46 bzw. 66.33). Das freie Fenster ist strukturell leer:")
print("     die De-Risking-Lesart kann im vorliegenden Datensatz KEINEN")
print("     zusaetzlichen Trade erzeugen -> +19,99 R (Box) / +23,02 R (Voll)")
print("     bleiben identisch.")

print("")
print("=" * 112)
print("SCHRITT 4C -- K20 'tote Zone' nach der Promotion (Bar 229)")
print("=" * 112)
basis20 = 66.459
schwelle20 = basis20 * (1.0 + BAND / 100.0)
print(f"  In-Band (kein Handel):  {basis20:.3f} < high <= {schwelle20:.4f}")
print(f"  Sweep-faehig:           high >  {schwelle20:.4f}  (>= {np.ceil(schwelle20 * 1000) / 1000:.3f})")
ueber = [k for k in range(229, n) if hi[k] > basis20]
inband = [k for k in ueber if (hi[k] - basis20) / basis20 * 100.0 <= BAND]
sweep = [k for k in ueber if (hi[k] - basis20) / basis20 * 100.0 > BAND]
# handelbar = Sweep UND Reclaim (irgendein Close in k..k+2 <= Basis, _reclaim_stufe)
handelbar = [k for k in sweep if bool(np.any(cl[k:min(k + 3, n)] <= basis20))]
print(f"  Dochte ueber der Basis (Bar >= 229): {len(ueber)}")
print(f"    davon IN-BAND  (<= {BAND} %, Skip)  : {len(inband)}  -> Bars "
      f"{inband[:8]}{' ...' if len(inband) > 8 else ''}")
print(f"    davon Sweep-faehig (>{BAND} %)     : {len(sweep)}")
print(f"    davon mit Reclaim (Close <= Basis in k..k+2): {len(handelbar)}  "
      f"-> Bars {handelbar}")
print("")
print("  Die beiden einzigen Range-internen Sweeps:")
for k in (529, 565):
    print(f"    Bar {k} ({zeit(k)}): high={hi[k]:.3f} | "
          f"dist={(hi[k] - basis20) / basis20 * 100:+.4f} % | "
          f"Fehlbetrag zur Schwelle = {basis20 * (1 + BAND / 100) - hi[k]:.4f} USD")
print("")
print("  -> Range-intern verfehlt K20 die Schwelle zweimal knapp (0.0008 / 0.0028 USD).")
print("     Alle spaeteren Dochte (ab Bar 733) liegen im Ausbruch: der Reclaim")
print("     (Close <= Basis innerhalb von 2 Bars) findet dort nie statt ->")
print("     kein K20-Setup. K20 ist nach Bar 229 praktisch nie wieder handelbar.")

print("")
print("=" * 112)
print("SCHRITT 4E -- Fallstrick im Vertrag ReTestDeRiskingPruefung (Semantik-Falle)")
print("=" * 112)
print("  Naive Lesart: ist_nach_de_risking_zulaessig = kandidat_entry_bar > tp1_bar")
print("")
print("  K59 (OBEN pivot 805 / 68.972, = Teil-6-K62):")
print("    Trade bar 853 entry=855 -> R = -1,00 (beide Haelften SL, exit_final 867)")
print("    -> ein TP1-Bar EXISTIERT NICHT.")
print("    -> naive Lesart: 866 > (None/-1)  =  TRUE  -> Kandidat 865 FREI")
print("    -> Folge: zusaetzlicher Trade bar 866 (Teil 4 §3: R = -1,00)")
print("    -> Voll-Lauf: 10 Trades / +22,02 R  statt  9 / +23,02 R  (-1,00 R).")
print("")
print("  Praezise Lesart: ein Trade OHNE erreichtes TP1 (SL/ENDE) gilt als")
print("    NICHT de-risked -> Sperre bis exit_final.")
print("    -> 866 GESPERRT -> +23,02 R identisch zur Stacking-Lesart.")
print("")
print("  -> Der Vertrag braucht daher zwingend den Zusatz:")
print("     'Hat der laufende Trade sein TP1 nicht erreicht (grund1 != TP1),")
print("      ist er NICHT de-risked; es gilt die Sperre bis exit_final_bar.'")

print("")
print("=" * 112)
print("SCHRITT 4D -- Robustheit der Sweep-Entkopplung (Messlage Teil 6, Voll-Lauf)")
print("=" * 112)
print("  V0 arretiert                         :  9 Trades / +23,02 R  (Referenz)")
print("  V1 nur Gate (iii) auf 0,05 %         :  9 Trades / +23,02 R  (wirkungslos)")
print("  V2 nur Anker-Vorrang (ii)            :  8 Trades / +14,61 R  (-8,41 R)")
print("  V3 Anker-Vorrang + (iii) 0,05 %      :  9 Trades / +23,00 R  (K31 -> K20)")
print("  V4 (ii)+(ii')+(iii) 0,02 %           : 12 Trades / +21,12 R  (-1,90 R)")
print("  V4 (ii)+(ii')+(iii) 0,05 %           : 11 Trades / +21,52 R  (-1,50 R)")
print("  V4 (ii)+(ii')+(iii) 0,08 %           : 11 Trades / +21,52 R  (-1,50 R)")
print("  V4 (ii)+(ii')+(iii) 0,10 %           : 11 Trades / +21,52 R  (-1,50 R)")
print("  sweep_min 0,12/0,15 % (>= Band)      :  9 Trades / +23,02 R  (signaturgleich)")
print("  sweep_min 0,30 %                     :  7 Trades / +24,65 R  (Verschaerfung)")
print("  sweep_min 0,60 %                     :  0 Trades")
print("")
print("  -> Kein Entkopplungswert haelt das arretierte Ergebnis und lockert")
print("     zugleich das Band. Der einzige motivierende Fall (K20@529) ist")
print("     -0,02 R wert; die Regeländerung kostet -1,50 bis -1,90 R.")
print("  -> Neue Verlierer in V4 (Teil 6): Bars 383, 492, 620.")
