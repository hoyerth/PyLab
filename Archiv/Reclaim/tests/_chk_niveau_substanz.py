# -*- coding: utf-8 -*-
"""Substanzpruefung der Kanten-Niveaus (read-only, kein Motoreingriff).

Frage: Reagiert der Preis an den vom Motor behaupteten Niveaus BESSER als an
beliebigen anderen Preisen? Wenn nein, ist die "Kante" informationstheoretisch
leer -- unabhaengig davon, wie korrekt der Motor rechnet.

Vier Tests, alle richtungsbewusst (OBEN = Widerstand, UNTEN = Stuetze):

  T1  Niveau-Verteilung: Sind die Niveau-Preise von einer Gleichverteilung
      unterscheidbar? (Spacing / Nearest-Neighbour gegen Poisson-Erwartung)
  T2  Permutationstest: Abprallquote an echten Niveaus vs. Zufallsniveaus aus
      demselben Preisbereich (M Durchlaeufe -> empirischer p-Wert).
  T3  Reaktionsamplitude: wie gross ist die Reaktion in USD / Prozent --
      verglichen mit dem Touchband.
  T4  Selektionsfrage: Sind die 12 tatsaechlich GEHANDELTEN Kanten besser als
      die uebrigen? (Wenn der Motor waehlt, muesste das sichtbar sein.)

Definitionen (provisorisch, zur Bindung durch den Anwender):
  H      = 24 Bars Vorlauf (6 h auf M15)
  X      = 0.15 USD  (Reaktionsschwelle -- Abprall)
  EPS    = 0.05 USD  (Bruchschwelle, = struktureller SL-Puffer)
  ABSTAND= 8 Bars    (Deduplizierung aufeinanderfolgender Beruehrungen)

Approximation, offengelegt: als Niveau-Preis wird die ARRETIERTE Basis am
Box-Ende (``basis_bei(box_end-3)``) verwendet, nicht die zeitvariierende
Basis. Die Sonde misst damit "ist der behauptete Preis ein Niveau?", nicht
"ist die laufende Basis ein Niveau?".
"""
from __future__ import annotations

import copy
import importlib.util
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TEST = ROOT / "test"
for p in (str(ROOT), str(TEST)):
    if p not in sys.path:
        sys.path.insert(0, p)

spec = importlib.util.spec_from_file_location(
    "v022_substanz", TEST / "tmp_kanten_engine_v022_replay.py")
V = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
sys.modules["v022_substanz"] = V
spec.loader.exec_module(V)  # type: ignore[union-attr]

B = V._engine()

H_VORLAUF = 24
X_REAKTION = 0.15
EPS_BRUCH = 0.05
ABSTAND = 8
M_PERM = 200
RNG = np.random.default_rng(20260731)

FENSTER = (("MAI", "2026-05-01", "2026-06-01"),
           ("JUN", "2026-06-01", "2026-07-01"),
           ("JUL", "2026-07-01", "2026-08-01"),
           ("AUG_BASE", "AUG", "AUG"))


def _scan(B: Any, start: str, ende: str) -> Dict[str, Any]:
    if start == "AUG":
        s = B._se_scan("AUG", B.StraightEdgeHarnessKonfiguration())
        s = copy.deepcopy(s)
        s["box_end_bar"] = int(s["n"])
        return s
    B.FENSTER["LAB"] = (start, ende)
    try:
        d = B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]
    n = int(len(d))
    orig = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        s = B._se_scan("LAB", B.StraightEdgeHarnessKonfiguration())
    finally:
        B._lade_fenster = orig  # type: ignore
    s = copy.deepcopy(s)
    s["box_end_bar"] = int(n)
    return s


def _vorlauf(hi: np.ndarray, lo: np.ndarray, cl: np.ndarray,
             h: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Sliding-Window-Extrema der jeweils naechsten ``h`` Bars (kausal korrekt)."""
    n = len(cl)
    mx = np.full(n, -np.inf)
    mn = np.full(n, np.inf)
    mxc = np.full(n, -np.inf)
    mnc = np.full(n, np.inf)
    for b in range(n):
        e = min(b + h, n - 1)
        if e > b:
            mx[b] = hi[b + 1:e + 1].max()
            mn[b] = lo[b + 1:e + 1].min()
            mxc[b] = cl[b + 1:e + 1].max()
            mnc[b] = cl[b + 1:e + 1].min()
    return mx, mn, mxc, mnc


def _touches(level: float, hi: np.ndarray, lo: np.ndarray,
             box_end: int, abstand: int) -> List[int]:
    """Beruehrungs-Bars (Range enthaelt das Niveau), dedupliziert."""
    maske = (lo[:box_end] <= level) & (hi[:box_end] >= level)
    bars = np.flatnonzero(maske)
    out: List[int] = []
    letzter = -10 ** 9
    for b in bars:
        if b - letzter >= abstand:
            out.append(int(b))
            letzter = int(b)
    return out


def _bewerte(level: float, seite: str, bars: Sequence[int],
             mx: np.ndarray, mn: np.ndarray,
             mxc: np.ndarray, mnc: np.ndarray) -> Tuple[int, int, List[float]]:
    """(Abpralle, Brueche, Amplituden) ueber alle Beruehrungen."""
    ab, br, amp = 0, 0, []
    for b in bars:
        if not np.isfinite(mx[b]):
            continue
        if seite == "OBEN":                       # Widerstand
            abprall = (mn[b] <= level - X_REAKTION) and (mxc[b] < level + EPS_BRUCH)
            bruch = mxc[b] > level + EPS_BRUCH
            if abprall and not bruch:
                ab += 1
                amp.append(level - mn[b])
            elif bruch:
                br += 1
        else:                                     # Stuetze
            abprall = (mx[b] >= level + X_REAKTION) and (mnc[b] > level - EPS_BRUCH)
            bruch = mnc[b] < level - EPS_BRUCH
            if abprall and not bruch:
                ab += 1
                amp.append(mx[b] - level)
            elif bruch:
                br += 1
    return ab, br, amp


def _quote_und_bars(levels: Sequence[Tuple[float, str]], hi, lo, cl,
                    box_end: int, mx, mn, mxc, mnc) -> Tuple[int, int, List[float]]:
    ab = br = 0
    amp: List[float] = []
    for lvl, seite in levels:
        bars = _touches(lvl, hi, lo, box_end, ABSTAND)
        a, b, am = _bewerte(lvl, seite, bars, mx, mn, mxc, mnc)
        ab += a
        br += b
        amp.extend(am)
    return ab, br, amp


def main() -> None:
    print("=" * 100)
    print("SUBSTANZPRUEFUNG DER KANTEN-NIVEAUS")
    print(f"H={H_VORLAUF} Bars  X={X_REAKTION} USD  EPS={EPS_BRUCH} USD  "
          f"Abstand={ABSTAND} Bars  Permutationen={M_PERM}")
    print("=" * 100)

    echte: List[Tuple[float, str]] = []
    gehandelt: List[Tuple[float, str]] = []
    alle_niveaus: List[float] = []
    amp_alle: List[float] = []
    fenster_daten: List[Dict[str, Any]] = []
    ab_g = br_g = 0

    for fid, start, ende in FENSTER:
        sc = _scan(B, start, ende)
        hi = sc["d"]["high"].to_numpy(dtype=float)
        lo = sc["d"]["low"].to_numpy(dtype=float)
        cl = sc["d"]["close"].to_numpy(dtype=float)
        box = int(sc["box_end_bar"])
        kbox = box - 3

        mx, mn, mxc, mnc = _vorlauf(hi, lo, cl, H_VORLAUF)

        edges: List[Any] = list(sc["edges"]) + list(sc["seeds"])
        kurz = [(float(e.basis_bei(kbox)), e.seite) for e in edges]
        kurz = [(l, s) for l, s in kurz if lo[:box].min() <= l <= hi[:box].max()]

        setups, _ = V._se_trades_v022(copy.deepcopy(sc), V.V022KantenKonfiguration())
        kids = {int(t.kid) for t in setups}
        lang = [(float(e.basis_bei(kbox)), e.seite) for e in edges
                if int(e.kid) in kids]
        lang = [(l, s) for l, s in lang if lo[:box].min() <= l <= hi[:box].max()]

        ab_e, br_e, amp_e = _quote_und_bars(kurz, hi, lo, cl, box, mx, mn, mxc, mnc)
        ab_g += ab_e
        br_g += br_e
        amp_alle.extend(amp_e)
        echte.extend(kurz)
        gehandelt.extend(lang)
        alle_niveaus.extend(l for l, _ in kurz)

        fenster_daten.append(dict(fid=fid, hi=hi, lo=lo, cl=cl, box=box,
                                  mx=mx, mn=mn, mxc=mxc, mnc=mnc,
                                  lo_preis=float(lo[:box].min()),
                                  hi_preis=float(hi[:box].max()),
                                  kurz=kurz, lang=lang,
                                  ab=ab_e, br=br_e))

        print()
        print(f"{fid}:  {len(edges)} Kanten, {len(kurz)} im Preisbereich, "
              f"{len(lang)} gehandelt   Preisbereich {lo[:box].min():.3f}.."
              f"{hi[:box].max():.3f}")
        print(f"       Beruehrungen: Abprall {ab_e}, Bruch {br_e}   "
              f"Abprallquote {ab_e / max(ab_e + br_e, 1) * 100:.1f} %")

    # ------------------------------------------------------------------ T1
    print()
    print("=" * 100)
    print("T1  NIVEAU-VERTEILUNG: unterscheidbar von Gleichverteilung?")
    print("=" * 100)
    lv = np.sort(np.array(alle_niveaus))
    spanne = float(lv.max() - lv.min())
    n_ = len(lv)
    nnd = np.diff(lv)
    print(f"    Niveaus {n_}  Bereich {lv.min():.4f}..{lv.max():.4f} "
          f"(Spanne {spanne:.4f} USD)")
    print(f"    mittlerer Abstand  IST  {spanne / (n_ - 1):.4f} USD   "
          f"(Gleichverteilung erwartet genau diesen Wert: {spanne / (n_ - 1):.4f})")
    print(f"    Nearest-Neighbour  Median IST {statistics.median(nnd):.4f} USD")
    print(f"                       Poisson-Erwartung {spanne / (2 * (n_ - 1)):.4f} USD")
    # KS-Test gegen Uniform (ohne scipy: empirisch vs. theoretisch)
    u = (lv - lv.min()) / spanne
    d_ks = float(np.max(np.abs(u - (np.arange(n_) + 0.5) / n_)))
    grenze = 1.36 / np.sqrt(n_)
    print(f"    KS-Statistik {d_ks:.4f}  (5-%-Grenze {grenze:.4f})  ->  "
          f"{'NICHT unterscheidbar von gleichverteilt' if d_ks < grenze else 'ABWEICHUNG von gleichverteilt'}")

    # ------------------------------------------------------------------ T2
    print()
    print("=" * 100)
    print("T2  PERMUTATIONSTEST: Abprallquote echte Niveaus vs. Zufallsniveaus")
    print("=" * 100)
    ist_quote = ab_g / max(ab_g + br_g, 1)
    print(f"    ECHTE Niveaus: Abprall {ab_g}, Bruch {br_g}  ->  "
          f"Quote {ist_quote * 100:.2f} %")
    null_quoten: List[float] = []
    for m in range(M_PERM):
        q_ab = q_br = 0
        for fd in fenster_daten:
            n_lvl = len(fd["kurz"])
            if n_lvl == 0:
                continue
            zufall = RNG.uniform(fd["lo_preis"], fd["hi_preis"], n_lvl)
            seiten = [s for _, s in fd["kurz"]]
            a, b, _ = _quote_und_bars(list(zip(zufall.tolist(), seiten)),
                                      fd["hi"], fd["lo"], fd["cl"], fd["box"],
                                      fd["mx"], fd["mn"], fd["mxc"], fd["mnc"])
            q_ab += a
            q_br += b
        null_quoten.append(q_ab / max(q_ab + q_br, 1))
    arr = np.array(null_quoten)
    p = float((arr >= ist_quote).mean())
    print(f"    NULL (M={M_PERM}): Mittel {arr.mean() * 100:.2f} %  "
          f"Median {np.median(arr) * 100:.2f} %  "
          f"Streuung {arr.std() * 100:.2f} %")
    print(f"    Perzentile 5/50/95: {np.percentile(arr, 5) * 100:.2f} / "
          f"{np.percentile(arr, 50) * 100:.2f} / {np.percentile(arr, 95) * 100:.2f} %")
    print(f"    p-Wert (echte >= null): {p:.4f}   ->  "
          f"{'KEIN Informationsgehalt' if p >= 0.05 else 'signifikanter Unterschied'}")

    # ------------------------------------------------------------------ T3
    print()
    print("=" * 100)
    print("T3  REAKTIONSAMPLITUDE (nur Abpralle)")
    print("=" * 100)
    if amp_alle:
        a = np.array(amp_alle)
        print(f"    N={len(a)}  Median {np.median(a):.4f} USD  "
              f"Mittel {a.mean():.4f} USD  p90 {np.percentile(a, 90):.4f} USD")
        print(f"    Touchband des Motors 0.12 % = 0.0690 USD (bei 57.46)")
        print(f"    Anteil Reaktionen < 2x Touchband (0.138 USD): "
              f"{(a < 0.138).mean() * 100:.1f} %")
        print(f"    Anteil Reaktionen < 0.25 USD: {(a < 0.25).mean() * 100:.1f} %")

    # ------------------------------------------------------------------ T4
    print()
    print("=" * 100)
    print("T4  SELEKTIONSFRAGE: sind die GEHANDELTEN Kanten besser?")
    print("=" * 100)
    for fd in fenster_daten:
        if not fd["lang"]:
            continue
        a2, b2, _ = _quote_und_bars(fd["lang"], fd["hi"], fd["lo"], fd["cl"],
                                    fd["box"], fd["mx"], fd["mn"],
                                    fd["mxc"], fd["mnc"])
        print(f"    {fd['fid']:<9s} gehandelt {len(fd['lang'])} Niveaus: "
              f"Abprall {a2}, Bruch {b2} -> Quote "
              f"{a2 / max(a2 + b2, 1) * 100:5.1f} %   "
              f"| alle {len(fd['kurz'])}: "
              f"{fd['ab'] / max(fd['ab'] + fd['br'], 1) * 100:5.1f} %")
    ab_l = br_l = 0
    for fd in fenster_daten:
        a3, b3, _ = _quote_und_bars(fd["lang"], fd["hi"], fd["lo"], fd["cl"],
                                    fd["box"], fd["mx"], fd["mn"],
                                    fd["mxc"], fd["mnc"])
        ab_l += a3
        br_l += b3
    print(f"    GESAMT gehandelt: Abprall {ab_l}, Bruch {br_l} -> "
          f"Quote {ab_l / max(ab_l + br_l, 1) * 100:.2f} %  "
          f"(alle Niveaus {ist_quote * 100:.2f} %)")
    print()
    print("=" * 100)


if __name__ == "__main__":
    main()
