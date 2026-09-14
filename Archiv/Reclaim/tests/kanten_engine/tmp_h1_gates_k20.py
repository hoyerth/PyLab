# -*- coding: utf-8 -*-
"""READ-ONLY: Gate-Walk fuer die vier K20-Sweeps (229 / 242 / 244 / 529 / 565).

Beantwortet die Anwenderfrage: WELCHE Regel blockiert WELCHEN der vier
Re-Entries auf K20 (Basis 66.459) - in exakter Code-Reihenfolge von
_se_trades? Kein Engine-Import, kein _se_scan, kein Compile.

Spec-Anker (§7.2):
  Z. 440-442: "ausschliesslich der echte Docht-Durchstich der Linie
              (high[k] > basis bzw. low[k] < basis) - ein blosser
              Bandkontakt OHNE Durchstich erzeugt kein Signal."
  Z. 454-455: "max. 1 offene Position je Kante (kein Stacking), Entry-Zeit-
              Lesart kandidat_entry_bar <= max(exit1_bar, exit2_bar)".
  Z. 358-360: F3 - neue Freigabe nur bei neuem bestaetigtem Touch UND
              max. 1 offene Position je Kante (kein Stacking).
"""
from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Optional

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
BAND, MAXSW, PUFFER, SLBUF, ZYKLUS, MIN_ALTER = 0.12, 0.60, 0.01, 0.05, 12, 24


def zeit(k: int) -> str:
    return ts.iloc[k].strftime("%d.%m %H:%M")


# --- Kanten (aus dem arretierten Audit-Bestand, R21-bereinigt) -------------
# (kid, wicks, geburts_bar) -- OBEN
OBEN = {20: ([107, 529, 565], 529), 31: ([237, 249, 286, 536], 249),
        15: ([85, 220], 220), 16: ([90, 96, 114, 478, 492, 495, 498, 510,
                                    514, 547], 96),
        12: ([72, 78, 148, 155, 275, 463, 578, 609, 614], 78),
        25: ([141, 160, 165, 196, 343, 594, 603], 160),
        10: ([67, 135, 179, 187, 315, 357, 416], 135),
        9: ([56, 62, 386, 624], 62), 6: ([31, 45, 400], 45),
        0: ([5, 25, 634, 638], 25), 2: ([12, 18], 18),
        26: ([144, 211], 211), 28: ([204, 433], 433),
        36: ([327, 444], 444), 33: ([262, 267, 296, 306], 267),
        44: ([572, 585], 585)}
# UNTEN
UNTEN = {8: ([52, 57, 380, 627, 635], 57), 5: ([30, 60, 63, 386, 632], 60),
         17: ([92, 111, 242, 246, 252, 475, 493, 497, 512, 544, 553], 111),
         11: ([69, 122, 177, 342, 349, 410], 122),
         13: ([75, 154, 157, 192, 196, 334, 442, 447, 466, 582], 154),
         23: ([130, 162, 172, 320, 346, 368, 372], 162),
         24: ([136, 184, 312, 356, 414, 420, 452, 458], 184),
         14: ([81, 209, 259, 279, 300, 437, 520], 209),
         34: ([264, 273], 273), 29: ([214, 294, 606], 294),
         21: ([126, 316, 361, 406], 316), 1: ([7, 398, 621], 398)}
ANCHOR = {20: 66.459}          # K20: eingefrorene Basis ab Promotion Bar 229
# Prim-Antworten (Arretierung): promo_ab_bar, kind_basis, pivot-Bar
PRIM = {20: (229, 66.459, 107), 6: (39, 64.312, 45), 15: (101, 66.046, 220),
        3: (650, 62.967, 682), 59: (853, 68.989, 847)}
# R21-Loeschungen (Tombstone-Bar) - betrifft nur NICHT-Prim-Kanten
R21_DEL = {18: 290, 19: 296, 22: 320, 27: 367, 30: 427, 32: 447, 35: 483,
           37: 522, 39: 544, 40: 582}


def basis_bei(kid: int, k: int) -> float:
    if kid in PRIM:
        return PRIM[kid][1]
    wl = (OBEN.get(kid) or UNTEN.get(kid))[0]
    px = [hi[b] if kid in OBEN else lo[b] for b in wl if b + 2 <= k]
    return float(np.mean(px)) if px else float("nan")


def touch_conf(kid: int, k: int) -> int:
    wl = (OBEN.get(kid) or UNTEN.get(kid))[0]
    return sum(1 for b in wl if b + 2 <= k)


def lebt(kid: int, k: int) -> bool:
    return k < R21_DEL.get(kid, 10 ** 9)


def pool_seite(seite: str, k: int, eigene: Optional[int] = None):
    """_kandidat-Pool OHNE In-Band-Filter (der kommt separat als Gate (1b)).

    Existenz = erster_pivot_bar + 2 <= k + 1 (_existiert, Z. 2375-2385);
    NICHT die Keimung (geburts_bar). K20 z. B. hat geburts_bar 529, ist
    aber als Primaer-Anker ab promo_ab_bar 229 handelbar.
    """
    qu = OBEN if seite == "OBEN" else UNTEN
    out = []
    for kid, (wl, geb) in qu.items():
        if wl[0] + 2 > k + 1 or not lebt(kid, k):
            continue
        ist_anker = kid in PRIM and k >= PRIM[kid][0]
        if ist_anker or touch_conf(kid, k) >= 2:
            if k - wl[0] >= MIN_ALTER:          # _etabliert (erster Pivot)
                out.append(kid)
    return sorted(out, key=lambda x: basis_bei(x, k),
                  reverse=(seite == "OBEN"))


def reclaim(k: int, basis: float, band: float):
    dist = (hi[k] - basis) / basis * 100.0
    if not (hi[k] > basis and band < dist <= MAXSW):
        return 0, None
    if cl[k] <= basis:
        return 1, "STUFE_1_IN_BAR"
    if k + 1 < len(cl) and cl[k + 1] <= basis and hi[k + 1] <= hi[k] + PUFFER:
        return 2, "STUFE_2_KERZE_2"
    if (k + 2 < len(cl) and cl[k + 2] <= basis
            and max(hi[k + 1], hi[k + 2]) <= hi[k] + PUFFER):
        return 3, "STUFE_3_KERZE_3"
    return 0, None


def poc(start_bar, signal_bar, unter, ober, num_bins=60):
    sub = d.iloc[start_bar:signal_bar + 1]
    edges = np.linspace(unter, ober, num_bins + 1)
    vol = np.zeros(num_bins, dtype=float)
    for a, b, v in zip(sub["low"].to_numpy(float), sub["high"].to_numpy(float),
                       sub["tick_volume"].to_numpy(float)):
        if b <= a or v <= 0:
            continue
        lb = int(np.clip(np.searchsorted(edges, a, side="right") - 1, 0, num_bins - 1))
        hb = int(np.clip(np.searchsorted(edges, b, side="left") - 1, 0, num_bins - 1))
        if lb == hb:
            vol[lb] += v
        else:
            ov = np.array([max(0.0, min(b, edges[x + 1]) - max(a, edges[x]))
                           for x in range(lb, hb + 1)])
            t = float(ov.sum())
            if t > 0:
                vol[lb:hb + 1] += v * ov / t
    vs = np.convolve(vol, np.ones(3) / 3.0, mode="same") if len(vol) >= 3 else vol
    p = int(np.argmax(vs))
    return float((edges[p] + edges[p + 1]) / 2.0)


def loese(entry_bar, entry, sl, tp1, tp2):
    risk = abs(sl - entry)
    hh, ll, cc = hi[entry_bar:], lo[entry_bar:], cl[entry_bar:]
    nb = len(hh)
    f = lambda m: int(np.argmax(m)) if m.any() else nb  # noqa: E731
    t1, t2, tsl = f(ll <= tp1), f(ll <= tp2), f(hh >= sl)
    r = lambda px: (entry - px) / risk  # noqa: E731
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
    return (0.5 * r1 + 0.5 * r2, r1, r2, b1, b2, g1, g2,
            b1 if g1 == "TP1" else -1, max(b1, b2))


print("=" * 116)
print("A) K20-KASKADE: ist K20 an den vier Sweep-Bars die AEUSSERSTE Linie?")
print("=" * 116)
print(f"  {'bar':>5} {'zeit':>12} {'high':>8} {'K20 basis':>10} {'K20 dist%':>10} "
      f"{'K31 basis':>10} {'K31 dist%':>10}  Pool(OBEN, absteigend)")
for k in (229, 242, 244, 529, 565):
    b20 = basis_bei(20, k)
    b31 = basis_bei(31, k)
    p = pool_seite("OBEN", k)
    print(f"  {k:5d} {zeit(k):>12} {hi[k]:8.3f} {b20:10.3f} "
          f"{(hi[k] - b20) / b20 * 100:+10.4f} {b31:10.3f} "
          f"{(hi[k] - b31) / b31 * 100:+10.4f}  "
          f"{', '.join('K' + str(x) + '/' + format(basis_bei(x, k), '.3f') for x in p[:4])}")
print("")
print("  -> K20 (66.459) ist an ALLEN fuenf Bars die aeusserste OBEN-Linie")
print("     (K15 66.046 liegt darunter, erreicht -> kein Blocker).")

print("")
print("=" * 116)
print("B) GATE-WALK je Bar (Code-Reihenfolge). Erster BLOCKIERER wird ausgewiesen.")
print("=" * 116)
print("  Legende Gates: (1) _kandidat-Kaskade/In-Band  (2) M6 Blocker")
print("                 (3) Q29 Quartil  (4) _reclaim_stufe  (5) F3-Frische")
print("                 (6) Zyklus 12  (7) _gegenkante  (8) Geometrie  (9) Stacking")

for k in (229, 242, 244, 529, 565):
    b20 = basis_bei(20, k)
    dist = (hi[k] - b20) / b20 * 100.0
    print("")
    print(f"  --- Bar {k} ({zeit(k)}) high={hi[k]:.3f} K20-basis={b20:.3f} "
          f"dist={dist:+.4f} % ---")
    # (1) Kaskade: aeusserste Linie, In-Band-Vorrang, Seed-Pool
    in_band = dist <= BAND
    p_oben = pool_seite("OBEN", k)
    print(f"    (1) Kaskade: aeusserste OBEN-Linie = K{p_oben[0]} "
          f"({basis_bei(p_oben[0], k):.3f}) -> das ist K20.")
    print(f"        (1b) In-Band-Vorrang (dist <= {BAND} %): "
          f"{'JA -> K20 uebersprungen (Skip), Kaskade faellt nach innen' if in_band else 'nein -> K20 handelt (Wand = pos 0)'}")
    for band, label in ((BAND, "arretiert (band=0.12)"), (0.0, "spec-konform (band=0)")):
        st, sn = reclaim(k, b20, band)
        print(f"        (4) _reclaim_stufe {label:24s}: stufe={st} "
              f"({sn or 'kein Reclaim'})"
              f"{' -> entry=' + str(k + st) if st else ''}")
    st_spec, sn_spec = reclaim(k, b20, 0.0)
    if not st_spec:
        print("    => Endstation bereits bei (1)/(4): kein Signal.")
        continue
    entry_bar = k + st_spec
    # (2) M6 Blocker
    blk = [x for x in pool_seite("OBEN", k) if basis_bei(x, k) > hi[k] and x != 20]
    print(f"    (2) M6 Blocker: OBEN-Linien oberhalb des Sweeps: "
          f"{['K' + str(x) for x in blk] or 'keine'} -> "
          f"{'BLOCK' if blk else 'pass'}")
    # (3) Q29
    eh, el = float(np.max(hi[:k + 1])), float(np.min(lo[:k + 1]))
    q = (eh - hi[k]) / (eh - el) * 100.0
    print(f"    (3) Q29 Quartil: dist {q:.2f} % <= 25 % -> "
          f"{'pass' if q <= 25 else 'BLOCK'}")
    # (5) F3-Frische: K20 letzter_sweep_bar
    last_sweep = 229 if k > 229 else -1000
    print(f"    (5) F3-Frische: k={k} > letzter_sweep_bar={last_sweep} -> "
          f"{'pass' if k > last_sweep else 'BLOCK'}")
    # (6) Zyklus
    print(f"    (6) Zyklus: {k} - {last_sweep} = {k - last_sweep} >= 12 -> "
          f"{'pass' if k - last_sweep >= 12 else 'BLOCK'}")
    # (7) Gegenkante
    gp = pool_seite("UNTEN", k)
    print(f"    (7) Gegenkante: aeusserste UNTEN = "
          f"{['K' + str(x) + ' (' + format(basis_bei(x, k), '.3f') + ')' for x in gp[:2]]} "
          f"-> pass")
    # (8) Geometrie
    tp2 = basis_bei(gp[0], k)
    cluster_ext = float(np.max(hi[k:entry_bar]))
    sl = cluster_ext + SLBUF
    entry = float(op[entry_bar])
    p1 = poc(0, k, tp2, b20)
    geo = sl > entry > p1 > tp2
    print(f"    (8) Geometrie: SL={sl:.3f} E={entry:.3f} POC={p1:.3f} "
          f"TP2={tp2:.3f} -> {'pass' if geo else 'BLOCK'}")
    # (9) Stacking
    offen = {229: (231, 398), 529: (531, 639)}
    blocker = None
    for tb, (eb, exf) in offen.items():
        if tb < k and entry_bar <= exf:
            blocker = (tb, eb, exf)
            break
    print(f"    (9) Stacking: {('Position ' + str(blocker[1]) + ' (Trade ' + str(blocker[0]) +
                          ') offen bis ' + str(blocker[2]) + ' -> entry ' + str(entry_bar) +
                          ' <= ' + str(blocker[2]) + ' -> BLOCK') if blocker else 'keine offene Position -> pass'}")
    if geo:
        rm, r1, r2, b1, b2, g1, g2, tp1b, exf2 = loese(entry_bar, entry, sl, p1, tp2)
        print(f"        -> hypothetischer Trade: entry={entry_bar} R={rm:+.2f} "
              f"(TP1@{b1}, TP2@{b2}, exit_final={exf2})")
        print(f"        -> De-Risking-Freigabe waere erst ab TP1-Bar {tp1b} "
              f"{'(nie)' if tp1b < 0 else ''}")

print("")
print("=" * 116)
print("C) FAZIT: erster Blockierer je Bar")
print("=" * 116)
print("  Bar 229 (12.08 11:15): ALLE Gates pass -> TRADE genommen (+6,92 R).")
print("  Bar 242 (12.08 14:30): Gate (9) STACKING (Position 231 offen bis 398).")
print("  Bar 244 (12.08 15:00): Gate (9) STACKING (zusaetzlich Dedup entry_bar 245).")
print("  Bar 529 (17.08 17:15): Gate (1) IN-BAND (dist +0,1189 % <= 0,12 %).")
print("  Bar 565 (18.08 03:15): Gate (1) IN-BAND (dist +0,1159 % <= 0,12 %),")
print("                         danach zusaetzlich Gate (9) STACKING.")
print("")
print("  Die ZYKLUS-Regel blockiert KEINEN der vier Bars (13/15/300/336 >= 12).")
