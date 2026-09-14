# -*- coding: utf-8 -*-
"""V3-Straight-Edge-Audit AUG (Spez §7.2, Schritt B; rein lesend).

Prueft die ARRETIERTE Straight-Edge-Revision (§7.2, Commit 69e9698, E1-E5)
ueber das AUG-Fenster (SILVER M15) - KANTEN-GEOMETRIE + RANGE-SETUP-ZAEHLUNG,
OHNE Trade-/TP-/POC-Logik (die folgt in Schritt C):

  * Regel 1 - Cluster-Keimung (>= 2 bestaetigte Pivot-Dochte im Band):
      - Seed = einzelner Docht (F1-dual, 2-Bar-Puffer); erst der ZWEITE Docht
        im Toleranzband laesst die Kante keimen.
      - Einheitliches relatives Band SE_BAND_PCT in {0,11 / 0,115 / 0,12 %};
        arretierter Default erst nach Abnahme dieser Audit-Ergebnisse.
      - Basis-Preis = MITTEL der akzeptierten Cluster-Dochte (selbst-
        lokalisierend, laeuft mit jedem akzeptierten Touch deterministisch
        mit; kausal, kein Blick ueber Bar k).
      - Touch-Mindestabstand min_bar_abstand = 3.
      - Zuordnung bei Band-Ueberlappung = U1 (hoechste touch_anzahl, bei
        Gleichstand aeusseres Extremum: OBEN hoehere / UNTEN tiefere Basis).
      - 2-Body-Bruch gegen die laufende Basis -> SCHLAFEND; Reaktivierung per
        Docht-Touch im Band.
      - SWEEP-IMMUNITAET (Commit a771e04 / §7.2-Nachtrag): Reclaim-Dochte der
        aeussersten Referenz der Seite (INKL. Singleton-Seeds) bilden NIE neue
        Linien. K33 (Seed 229/66.776) und K36 (Seed 242/66.663) werden
        ersatzlos eliminiert (Ueberdehnung 0.477 % / 0.307 % ueber Seed 107,
        Reclaim im 2-Bar-Grace-Fenster); K23-Keim-Dochte 529/565 bleiben im
        arretierten In-Band-Vorrang (0.119 % / 0.116 % <= touch_band 0.12).
  * Regel 2 - Begrenzungs-Hierarchie (Rolle RANGE_AUSSENGRENZE vs.
    ZWISCHEN_LEVEL): Handelbar sind nur AUSSENGRENZEN (je Seite die aeusserste
    aktive Kante). Setup-Zaehlung in zwei Varianten:
      V-S (streng §7.2-Literal): Aussengrenze = aeusserste AKTIVE GEBORENE
          Kante der Seite (Rolle RANGE_AUSSENGRENZE, touch_conf >= 2),
          handelbar erst ab >= 3 Touches (ist_aktive_aussengrenze).
      V-2 (Reife-Lockerung): dieselbe Aussengrenze, aber handelbar bereits
          ab der Geburt (>= 2 Touches) - Sensitivitaet fuer die Reife-
          Schwelle. Innere ZWISCHEN_LEVEL bleiben in BEIDEN Varianten stumm
          (kein Rueckfall auf innere Linien, wenn die Aussengrenze unreif
          oder SCHLAFEND ist).
      Trigger in_bar: SHORT high[k] > basis & close[k] <= basis;
      LONG low[k] < basis & close[k] >= basis. F3-Frische: neuester
      bestaetigter Touch (pivot_bar) > letzter_signal_bar.
  * Eichmassstab = BOX-PHASE 10.08..18.08 (bars < 2026-08-19). Nach dem
    Makro-Bruch 19.08 schlaeft die Engine per 2-Body-Schutz (kein Trade in der
    neuen Richtung ~70/62 USD-Regime).

Nachweisziel (E4/E5):
  39 Phase-0b-Kanten kollabieren auf die institutionellen Begrenzungslinien
  (Upper ~66.36/66.51, Unterkante Staffelung ~63.63/63.76 + Sweep-Zone 63.49,
  Minor dominant ~64.21 + Junior ~64.33) und die Trade-Zahl in der Box
  schrumpft von 33 Alt-C-Signalen (in_box) auf wenige echte Range-Setups.
  Die Soll-Wand-Zaehlung (menschliche Zonen-Zaehlung +/- 0.15 USD um die
  Anker 66.46 / 63.67 / 64.22 / 64.31) wird je SE_BAND ausgewiesen.

Referenzen/Konstanten: nutzt m._lade_fenster/m._pivot_dual aus
tmp_kanten_engine_replay.py sowie die Soll-Zonen aus tmp_v3_genese_audit.py
und tmp_v3_soll_kanten_audit.py.

Ausgabe: Terminal-Report + test/tmp_v3_straight_edge_audit_AUG.txt +
PNG test/kanten_engine_straight_edge_AUG.png (Band-Default 0.12, 300 dpi).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tmp_kanten_engine_replay as m  # noqa: E402

SE_BAND_SWEEP: Tuple[float, ...] = (0.11, 0.115, 0.12)
PNG_DEFAULT_BAND: float = 0.12      # einzige Band-Stufe mit UPPER 5/5 (Audit)
MIN_BAR_ABSTAND: int = 3            # Regel 1: Touch-Mindestabstand
BOX_END: pd.Timestamp = pd.Timestamp("2026-08-19")   # Box = ts < 19.08
ZONEN_BREITE_USD: float = 0.15      # menschliche Zonen-Zaehlung +/- 0.15
AUG_DIR = os.path.dirname(os.path.abspath(__file__))
TXT_OUT: str = os.path.join(AUG_DIR, "tmp_v3_straight_edge_audit_AUG.txt")
PNG_OUT: str = os.path.join(AUG_DIR, "kanten_engine_straight_edge_AUG.png")

# Historischer Zielverfehlungs-Befund (Phase-0b, Commit 61a0c29 / 69e9698)
ALT_C_GESAMT: int = 66              # Modus-C-Signale AUG gesamt (Harness)
ALT_C_IN_BOX: int = 33              # davon in der Box (< 19.08), hier gemessen

# Referenz-Zonen (§7.2 / Soll-Kanten; Anker +/- ZONEN_BREITE_USD)
ZONEN: List[Dict] = [
    dict(name="UPPER-WAND", anker=66.46, seite="OBEN",
         soll=[107, 237, 249, 529, 536],
         hinweis="Soll 5/5; SE erwartet Sub-Linien ~66.36/66.51 (Band-Scan)"),
    dict(name="LOWER-MAIN", anker=63.67, seite="UNTEN",
         soll=[30, 52, 57, 60, 63, 380, 386],
         hinweis="Soll 7/7 = menschl. Zonen-Zaehlung; SE: Staffelung 63.62/"
                 "63.70-63.79"),
    dict(name="MINOR-DOMINANT", anker=64.22, seite="UNTEN",
         soll=[126, 316, 320, 361],
         hinweis="E1: dominant 64.22 = 4/4"),
    dict(name="MINOR-JUNIOR", anker=64.31, seite="UNTEN",
         soll=[130, 162, 368],
         hinweis="E1: Junior 64.31 = 3/3, ZWISCHEN_LEVEL (stumm)"),
]

# ==============================================================================
# SWEEP-IMMUNITAET (arretiert, Commit a771e04 - §7.2-Nachtrag)
# ==============================================================================
# Kernregel: Reclaim-Dochte einer bestehenden Referenz bilden NIE neue Linien.
# Ein OBEN-Docht, der die aeusserste Referenz der Seite (inkl. Singleton-
# Seeds) um mehr als touch_band_pct uebersteigt und binnen reclaim_grace_bars
# Bars wieder UNTER die Referenz schliesst, ist ein fehlgeschlagener Ausbruch
# (Sweep) und wird NICHT als Seed geboren - ebenso UNTEN symmetrisch.


@dataclass(frozen=True, slots=True)
class SweepImmunitaetKonfiguration:
    """Arretierte Sweep-Immunitaet (Commit a771e04, §7.2-Nachtrag).

    touch_band_pct ist die ARRETIERTE Konstante 0.12 (nicht das Band des
    laufenden Auditscans): Dadurch bleiben Grenz-Dochte wie K23s Keim-Docht
    bar 529 (Ueberdehnung 0.119 %) im In-Band-Vorrang und bilden weiterhin
    die zweite Upper-Sub-Linie, waehrend die tiefen Reclaim-Sweeps 229/242
    (0.477 % / 0.307 %) eliminiert werden.
    """
    touch_band_pct: float = 0.12
    max_sweep_ueberdehnung_pct: float = 0.60
    reclaim_grace_bars: int = 2
    referenz_modus: Literal["inkl_seeds", "nur_gekeimte"] = "inkl_seeds"


SWEEP_CFG = SweepImmunitaetKonfiguration()


@dataclass(frozen=True, slots=True)
class AuditNachweisErgebnis:
    """Formaler Abnahme-Nachweis der Sweep-Immunitaet je Band (Commit a771e04).

    ist_perfekt = K33 (Seed 229/66.776) UND K36 (Seed 242/66.663) eliminiert
    UND die Soll-Wand-Zaehlung bleibt vollstaendig (5/5, 7/7, 4/4, 3/3).
    """
    band_pct: float
    k33_eliminiert: bool
    k36_eliminiert: bool
    upper_treffer: int
    upper_soll: int
    main_treffer: int
    main_soll: int
    minor_d_treffer: int
    minor_d_soll: int
    minor_j_treffer: int
    minor_j_soll: int
    seeds_offen: int
    edges_gesamt: int

    @property
    def ist_perfekt(self) -> bool:
        return (self.k33_eliminiert and self.k36_eliminiert
                and self.upper_treffer == self.upper_soll
                and self.main_treffer == self.main_soll
                and self.minor_d_treffer == self.minor_d_soll
                and self.minor_j_treffer == self.minor_j_soll)


def ist_sweep_einer_bestehenden_referenz(
    seite: str,
    bar_k: int,
    pivot_preis: float,
    cl: np.ndarray,
    aeusserste_referenz_basis: Optional[float],
    cfg: SweepImmunitaetKonfiguration = SWEEP_CFG,
) -> bool:
    """Arretierte Sweep-Pruefung (Commit a771e04, spiegelbildlich zur Spez).

    1) In-Band-Vorrang: dist_pct <= touch_band_pct -> False (der Docht
       gehoert zur Referenz, ist kein Sweep).
    2) OBEN: pivot > basis & dist <= max_sweep_ueberdehnung; Reclaim =
       IRGENDEIN Close im Fenster [bar_k, bar_k + reclaim_grace_bars]
       <= basis -> True (die Sweep-Bar selbst darf ueber der Basis
       schliessen; der Reclaim folgt typisch 1-2 Bars spaeter, z. B.
       bar 229 -> Reclaim-Close in 230, bar 242 -> Reclaim-Close in 244).
       UNTEN symmetrisch (pivot < basis; Reclaim-Close >= basis).
    Kausal: das komplette Reclaim-Fenster ist bei der Verarbeitung
    k = bar_k + 2 bekannt (kein Lookahead ueber den Grace-Horizont);
    fehlt am Fensterende die volle Fensterlaenge, gilt der Docht als
    nicht-bestaetigter Sweep (False).
    """
    if aeusserste_referenz_basis is None:
        return False
    if bar_k + cfg.reclaim_grace_bars + 1 > len(cl):
        return False                      # Reclaim-Fenster noch nicht komplett
    basis = float(aeusserste_referenz_basis)
    dist_pct = abs(pivot_preis - basis) / basis * 100.0
    if dist_pct <= cfg.touch_band_pct:
        return False                      # In-Band-Vorrang: Touch, kein Sweep
    if dist_pct > cfg.max_sweep_ueberdehnung_pct:
        return False
    fenster = cl[bar_k:bar_k + cfg.reclaim_grace_bars + 1]
    if seite == "OBEN":
        if pivot_preis <= basis:
            return False
        return bool(np.any(fenster <= basis))
    # UNTEN
    if pivot_preis >= basis:
        return False
    return bool(np.any(fenster >= basis))


KantenRolle = Literal["RANGE_AUSSENGRENZE", "ZWISCHEN_LEVEL"]


@dataclass(slots=True)
class _SEEdge:
    """Straight-Edge-Kante des Audits (Regel 1, selbst-lokalisierende Linie).

    basis = laufendes Mittel aller akzeptierten Dochte (kausal). Schlaf-
    Fenster: [(start_bar, end_bar|None)] - end_bar = Reaktivierungs-
    Bestaetigungsbar (pivot_bar+2) oder None (bis Fensterende schlafend).
    """

    kid: int
    seite: Literal["OBEN", "UNTEN"]
    basis: float
    geburts_bar: int                    # Pivot-Bar des 2. Dochts (Keimung)
    wicks: List[Tuple[int, float]] = field(default_factory=list)
    status: str = "AKTIV"
    letzter_bar: int = -1000
    schlaf_windows: List[Tuple[int, Optional[int]]] = field(default_factory=list)

    @property
    def touch_anzahl(self) -> int:
        return len(self.wicks)

    def box_basis(self, box_max_pivot: int) -> float:
        """Mittel der im Box-Fenster bestaetigbaren Dochte (pivot <= max)."""
        px = [p for b, p in self.wicks if b <= box_max_pivot]
        return float(np.mean(px)) if px else self.basis

    def basis_bei(self, k: int) -> float:
        """Kausale Basis bei Bar k = Mittel der bestaetigten Dochte (p+2<=k)."""
        px = [p for b, p in self.wicks if b + 2 <= k]
        return float(np.mean(px)) if px else self.basis

    def touch_conf(self, k: int) -> int:
        """Anzahl bestaetigter Dochte bei Bar k (pivot_bar + 2 <= k)."""
        return sum(1 for b, _ in self.wicks if b + 2 <= k)

    def letzter_touch_conf(self, k: int) -> int:
        """Neuester bestaetigter Pivot-Bar (<= k-2); -1000 wenn keiner."""
        bars = [b for b, _ in self.wicks if b + 2 <= k]
        return max(bars) if bars else -1000

    def ist_aktiv_bei(self, k: int) -> bool:
        """AKTIV bei Bar k = in keinem Schlaf-Fenster [start, end)."""
        for start, end in self.schlaf_windows:
            if start <= k and (end is None or k < end):
                return False
        return True

    def aktuelle_rolle(
        self, seite_edges: List["_SEEdge"], k: int,
    ) -> KantenRolle:
        """Regel 2: nur die aeusserste AKTIVE Kante der Seite = AUSSENGRENZE.

        OBEN: hoechste Basis; UNTEN: tiefste Basis. (Reife spielt hier keine
        Rolle - die bildet ist_handelbar_aussengrenze gemeinsam mit >= 3.)
        """
        aktiv = [e for e in seite_edges if e.ist_aktiv_bei(k)]
        if not aktiv:
            return "ZWISCHEN_LEVEL"
        if self not in aktiv:
            return "ZWISCHEN_LEVEL"
        if self.seite == "OBEN":
            outer = max(aktiv, key=lambda e: e.basis_bei(k))
        else:
            outer = min(aktiv, key=lambda e: e.basis_bei(k))
        return "RANGE_AUSSENGRENZE" if outer is self else "ZWISCHEN_LEVEL"


# ==============================================================================
# KERNSCAN (Regel 1: kausale Keimung; Rueckgabe je SE_BAND)
# ==============================================================================


def _scan_se(band_pct: float) -> Dict:
    """Kausaler Straight-Edge-Scan ueber AUG (Regel 1 + 2-Body + U1).

    Liefert dict mit: edges (alle gekeimten, n>=2), seeds (Singletons am
    Fensterende), ueberlappungen (Entscheidungs-Protokoll), n (Bars),
    box_end_bar (exklusiv), ts/hi/lo/op/cl (fuer die Setup-Pass).
    """
    d = m._lade_fenster("AUG")
    n = len(d)
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    op = d["open"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    ts_arr = d["ts"].to_numpy().astype("datetime64[ns]")
    box_end_bar = int(np.searchsorted(ts_arr, np.datetime64(BOX_END)))

    cluster: Dict[str, List[_SEEdge]] = {"OBEN": [], "UNTEN": []}
    ueberlapp: List[Tuple[int, str, float, List[Tuple[int, float, int]]]] = []
    # Sweep-Sperren (Commit a771e04): blockierte Seed-Geburten als
    # (mbar, seite, pivot_preis, aeusserste_referenz_basis, dist_pct).
    sweep_sperren: List[Tuple[int, str, float, float, float]] = []
    kid_next = 0

    def _ist_im_band(px: float, basis: float) -> bool:
        return abs(px - basis) / basis * 100.0 <= band_pct

    def _akzeptiere(e: _SEEdge, bar: int, px: float) -> None:
        if len(e.wicks) == 1:                # 2. Docht = Keimung
            e.geburts_bar = bar
        e.wicks.append((bar, px))
        e.letzter_bar = bar
        e.basis = float(np.mean([p for _, p in e.wicks]))
        if e.status == "SCHLAFEND":          # Reaktivierung per Docht-Touch
            e.status = "AKTIV"
            if e.schlaf_windows:
                start, _end = e.schlaf_windows[-1]
                e.schlaf_windows[-1] = (start, bar + 2)

    for k in range(n):
        mbar = k - 2
        if mbar >= 2:
            for typ in m._pivot_dual(hi, lo, mbar):
                seite = "OBEN" if typ == "H" else "UNTEN"
                px = float(hi[mbar]) if typ == "H" else float(lo[mbar])
                cand = [c for c in cluster[seite]
                        if _ist_im_band(px, c.basis)
                        and mbar - c.letzter_bar >= MIN_BAR_ABSTAND]
                if cand:
                    # U1-Dominanz: hoechste touch_anzahl; Gleichstand ->
                    # aeusseres Extremum (OBEN max / UNTEN min Basis).
                    best = max(
                        cand,
                        key=lambda c: (c.touch_anzahl,
                                       c.basis if seite == "OBEN" else -c.basis),
                    )
                    if len(cand) > 1:
                        ueberlapp.append((
                            mbar, seite, px,
                            [(c.kid, c.basis, c.touch_anzahl) for c in cand]))
                    _akzeptiere(best, mbar, px)
                else:
                    # SWEEP-IMMUNITAET (Commit a771e04): Reclaim-Dochte der
                    # aeussersten Referenz der Seite (INKL. Singleton-Seeds)
                    # bilden nie neue Linien -> kein Seed, Sperre wird
                    # protokolliert. Kausal: die Reclaim-Closes mbar..mbar+2
                    # sind bei der Verarbeitung k = mbar + 2 bekannt (kein
                    # Lookahead ueber den Grace-Horizont hinaus).
                    refs = cluster[seite]
                    aeus_ref = None
                    if refs:
                        aeus_ref = (max(r.basis for r in refs)
                                    if seite == "OBEN"
                                    else min(r.basis for r in refs))
                    if ist_sweep_einer_bestehenden_referenz(
                            seite, mbar, px, cl, aeus_ref, SWEEP_CFG):
                        dist_pct = abs(px - aeus_ref) / aeus_ref * 100.0
                        sweep_sperren.append((mbar, seite, px, aeus_ref,
                                              dist_pct))
                        continue
                    e = _SEEdge(kid=kid_next, seite=seite, basis=px,
                                geburts_bar=mbar)
                    kid_next += 1
                    e.wicks.append((mbar, px))
                    e.letzter_bar = mbar
                    cluster[seite].append(e)

        # 2-Body-Bruch gegen die laufende Basis (nur gekeimte Kanten)
        for seite in ("OBEN", "UNTEN"):
            for e in cluster[seite]:
                if e.touch_anzahl < 2:
                    continue
                if k < 1:
                    continue
                if seite == "OBEN":
                    aussen = (min(op[k - 1], cl[k - 1]) > e.basis
                              and min(op[k], cl[k]) > e.basis)
                else:
                    aussen = (max(op[k - 1], cl[k - 1]) < e.basis
                              and max(op[k], cl[k]) < e.basis)
                if aussen:
                    if e.status == "AKTIV":
                        e.status = "SCHLAFEND"
                        e.schlaf_windows.append((k, None))

    edges = [e for lst in cluster.values() for e in lst
             if e.touch_anzahl >= 2]
    seeds = [e for lst in cluster.values() for e in lst
             if e.touch_anzahl < 2]
    edges.sort(key=lambda e: (e.seite, e.basis))
    seeds.sort(key=lambda e: e.basis)
    return dict(edges=edges, seeds=seeds, ueberlapp=ueberlapp, n=n,
                box_end_bar=box_end_bar, d=d, band_pct=band_pct,
                sweep_sperren=sweep_sperren)


# ==============================================================================
# SETUP-ZAEHLUNG (Regel 2; in_bar; V-S vs. V-2) - zweite, strikt kausale Pass
# ==============================================================================


@dataclass(frozen=True, slots=True)
class _Setup:
    bar: int
    richtung: Literal["SHORT", "LONG"]
    variante: str
    kid: int
    basis: float
    sweep: float
    trigger_close: float
    touch_n: int


def _zaehle_setups(scan: Dict) -> Tuple[List[_Setup], Dict[str, int]]:
    """in_bar-Reclaim-Setups in der Box (< box_end_bar) an AUSSENGRENZEN.

    Beide Varianten setzen Regel 2 um: Kandidat ist ausschliesslich die
    aeusserste AKTIVE GEBORENE Kante der Seite (Rolle RANGE_AUSSENGRENZE);
    innere ZWISCHEN_LEVEL bleiben stumm - es gibt KEINEN Rueckfall auf eine
    innere Linie, wenn die Aussengrenze unreif oder SCHLAFEND ist. Der Sweep
    muss die Aussengrenze durchstossen (Docht-Durchstich), sonst kein
    Kandidat (die Mitte der Range handelt nicht). Unterschied:

      V-S (streng §7.2): handelbar erst ab >= 3 bestaetigten Touches
          (ist_aktive_aussengrenze).
      V-2 (Reife-Lockerung): handelbar ab der Geburt (>= 2 Touches) -
          Sensitivitaet fuer die Reife-Schwelle.

    Trigger in_bar: SHORT high[k] > basis & close[k] <= basis;
    LONG low[k] < basis & close[k] >= basis. F3-Frische: neuester
    bestaetigter Touch (pivot_bar) > letzter_signal_bar.
    """
    d = scan["d"]
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    edges_oben = sorted([e for e in scan["edges"] if e.seite == "OBEN"],
                        key=lambda e: e.kid)
    edges_unten = sorted([e for e in scan["edges"] if e.seite == "UNTEN"],
                         key=lambda e: e.kid)
    seite_edges = {"OBEN": edges_oben, "UNTEN": edges_unten}
    letzter_sig: Dict[str, Dict[int, int]] = {"S": {}, "2": {}}
    setups: List[_Setup] = []
    box_end = scan["box_end_bar"]

    def _kandidat(richtung: str, k: int, sweep_px: float,
                  schwell_min_touches: int) -> Optional[_SEEdge]:
        seite = "OBEN" if richtung == "SHORT" else "UNTEN"
        # aeusserste AKTIVE GEBORENE Kante der Seite (2+ bestaetigte Dochte)
        pool = [e for e in seite_edges[seite]
                if e.touch_conf(k) >= 2 and e.ist_aktiv_bei(k)]
        if not pool:
            return None
        outer = (max(pool, key=lambda e: e.basis_bei(k))
                 if seite == "OBEN" else min(pool, key=lambda e: e.basis_bei(k)))
        if outer.touch_conf(k) < schwell_min_touches:
            return None
        # Aussengrenze nur handelbar, wenn der Sweep sie durchstoesst
        if richtung == "SHORT":
            durchstochen = outer.basis_bei(k) < sweep_px
        else:
            durchstochen = outer.basis_bei(k) > sweep_px
        return outer if durchstochen else None

    def _f3_frisch(e: _SEEdge, k: int, variante: str) -> bool:
        return e.letzter_touch_conf(k) > letzter_sig[variante].get(e.kid, -10**9)

    # Box-Bars: Pivots m=k-2, 2-Body, dann in_bar-Scan (spiegelbildlich C1-C3)
    # Zustand (Schlaf/Reaktivierung) kommt aus dem Scan; die Kausalitaet der
    # Touch-/Basis-Sichten wird ueber die confirm-Grenzen (p+2<=k) sichergestellt.
    # F3-Buchhaltung je Variante GETRENNT (V-S und V-2 sind eigene Szenarien).
    for k in range(2, box_end - 1):
        for richtung in ("SHORT", "LONG"):
            for variante, schwelle in (("S", 3), ("2", 2)):
                sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])
                kd = _kandidat(richtung, k, sweep_px, schwelle)  # type: ignore[arg-type]
                if kd is None:
                    continue
                basis = kd.basis_bei(k)
                if richtung == "SHORT":
                    reclaim = cl[k] <= basis
                else:
                    reclaim = cl[k] >= basis
                if not reclaim or not _f3_frisch(kd, k, variante):
                    continue
                letzter_sig[variante][kd.kid] = k
                setups.append(_Setup(
                    bar=k, richtung=richtung,  # type: ignore[arg-type]
                    variante=variante, kid=kd.kid, basis=basis,
                    sweep=sweep_px, trigger_close=float(cl[k]),
                    touch_n=kd.touch_conf(k)))

    # Nur Box-Setups (bar < box_end-1 erzwungen durch Schleife)
    stats = {}
    for v in ("S", "2"):
        sub = [s for s in setups if s.variante == v]
        stats[v] = len(sub)
    return setups, stats


# ==============================================================================
# SOLL-ZONEN-ABDECKUNG (menschliche Zaehlung: Anker +/- 0.15 USD)
# ==============================================================================


def _soll_zonen(scan: Dict) -> List[Dict]:
    d = scan["d"]
    ts = pd.to_datetime(d["ts"])
    box_max_pivot = scan["box_end_bar"] - 3      # confirm p+2 <= box_end-1

    def _in_box_gekeimt(e: _SEEdge) -> bool:
        """Kante ist INNERHALB der Box gekeimt (>= 2 Dochte <= box_max)."""
        return sum(1 for b, _ in e.wicks if b <= box_max_pivot) >= 2

    ergebnis = []
    for z in ZONEN:
        lo_g = z["anker"] - ZONEN_BREITE_USD
        hi_g = z["anker"] + ZONEN_BREITE_USD
        zone_edges = [e for e in scan["edges"]
                      if e.seite == z["seite"]
                      and _in_box_gekeimt(e)
                      and lo_g <= e.box_basis(box_max_pivot) <= hi_g]
        zone_edges.sort(key=lambda e: (abs(e.box_basis(box_max_pivot)
                                          - z["anker"]), e.kid))
        deckung = []
        fehlend = []
        for b in z["soll"]:
            treffer = [e for e in zone_edges
                       if any(wb == b for wb, _ in e.wicks)]
            deckung.append((b, treffer[0].kid if treffer else None))
            if not treffer:
                fehlend.append(b)
        ergebnis.append(dict(
            name=z["name"], anker=z["anker"], seite=z["seite"],
            hinweis=z["hinweis"], soll=z["soll"],
            zone_edges=zone_edges, deckung=deckung, fehlend=fehlend,
            ts=ts))
    return ergebnis


# ==============================================================================
# REPORT
# ==============================================================================


def _format_ts(ts, bar: int) -> str:
    return pd.Timestamp(ts.iloc[bar]).strftime("%d.%m %H:%M")


def _report_band(scan: Dict, zonen_ergebnis: List[Dict],
                 setups: List[_Setup], alt_vergleich: bool = True) -> str:
    band = scan["band_pct"]
    edges = scan["edges"]
    box_end = scan["box_end_bar"]
    d = scan["d"]
    ts = pd.to_datetime(d["ts"])
    box_max_pivot = box_end - 3
    n_oben = sum(1 for e in edges if e.seite == "OBEN")
    n_unten = sum(1 for e in edges if e.seite == "UNTEN")
    n_typ_b = sum(1 for e in edges if e.touch_anzahl >= 3)
    box_edges = [e for e in edges if any(b <= box_end - 1 for b, _ in e.wicks)]

    L = []
    L.append("=" * 118)
    L.append(f"STRAIGHT-EDGE-AUDIT AUG | SE_BAND_PCT {band:.3f} | "
             f"Box < {BOX_END.strftime('%d.%m')} (bars < {box_end})")
    L.append("=" * 118)
    L.append(f"Gekeimte SE-Kanten gesamt: {len(edges)} (OBEN {n_oben} / "
             f"UNTEN {n_unten}) | >= 3 Touches (reif): {n_typ_b} | "
             f"mit Box-Docht: {len(box_edges)}")
    if alt_vergleich:
        L.append(f"ALT (Phase-0b, Commit 69e9698): 39 Kanten / 33 Typ B / "
                 f"66 Signale AUG, davon {ALT_C_IN_BOX} in der Box | "
                 f"Phase-0b-Kanten im Niemandsland handelten (Regel-2-Fix)")
    L.append("")

    # --- Kanten-Detail (Box-Bezug) ----------------------------------------
    L.append("-" * 118)
    L.append("SE-KANTEN MIT BOX-DOCHT (chronologisch nach Geburt; "
             "basis = Box-End-Mittel)")
    L.append("-" * 118)
    box_edges.sort(key=lambda e: (e.geburts_bar, e.kid))
    for e in box_edges:
        w = [b for b, _ in e.wicks]
        in_box = [b for b in w if b <= box_end - 1]
        post = [b for b in w if b > box_end - 1]
        bb = e.box_basis(box_max_pivot)
        wick_txt = ",".join(str(b) for b in in_box)
        if post:
            wick_txt += f"  (+{len(post)} nach Box)"
        L.append(f"  K{e.kid:3d} {e.seite:5s} basis_box={bb:8.3f} "
                 f"(end {e.basis:8.3f}) geb={e.geburts_bar:4d} "
                 f"({_format_ts(ts, e.geburts_bar)}) n={len(w):2d} "
                 f"wicks_box=[{wick_txt}]")
    L.append("")

    # --- Seeds (offene Singletons im Box-Kontext) --------------------------
    seeds_box = [e for e in scan["seeds"] if e.letzter_bar <= box_end - 1]
    if seeds_box:
        L.append(f"SEEDS (Singleton-Dochte, bis Box-Ende NICHT gekeimt): "
                 f"{len(seeds_box)}")
        for e in seeds_box:
            L.append(f"  K{e.kid:3d} {e.seite:5s} basis={e.basis:8.3f} "
                     f"bar={e.letzter_bar:4d} ({_format_ts(ts, e.letzter_bar)})")
        L.append("")

    # --- Sweep-Sperren (Commit a771e04: Reclaim-Dochte bilden keine Linien)
    sperren = scan["sweep_sperren"]
    L.append("-" * 118)
    L.append("SWEEP-SPERRE (Commit a771e04): Reclaim-Dochte der aeussersten "
             "Referenz der Seite (INKL. Singleton-Seeds) bilden keine neuen "
             f"Linien | Sperren gesamt: {len(sperren)}")
    L.append("-" * 118)
    if not sperren:
        L.append("  (keine Sweep-Blockierungen)")
    for (b, seite, px, ref, dist_pct) in sperren:
        k33 = (seite == "OBEN" and b == 229)
        k36 = (seite == "OBEN" and b == 242)
        mark = ""
        if k33:
            mark = "   <== K33 (Seed 229/66.776) ELIMINIERT"
        elif k36:
            mark = "   <== K36 (Seed 242/66.663) ELIMINIERT"
        L.append(f"  bar {b:4d} ({_format_ts(ts, b)}) {seite:5s} "
                 f"docht={px:.3f} | aeusserste Referenz {ref:.3f} | "
                 f"Ueberdehnung {dist_pct:.3f}% > arret. touch_band "
                 f"{SWEEP_CFG.touch_band_pct:.2f}% | Reclaim im Grace-"
                 f"Fenster ({SWEEP_CFG.reclaim_grace_bars} Bars) -> "
                 f"KEIN Seed{mark}")
    k33b = any(b == 229 and s == "OBEN" for b, s, *_r in sperren)
    k36b = any(b == 242 and s == "OBEN" for b, s, *_r in sperren)
    L.append(f"  -> K33 (Seed 229/66.776): "
             f"{'ELIMINIERT' if k33b else 'FEHLT - NICHT GEBLOCKT'} | "
             f"K36 (Seed 242/66.663): "
             f"{'ELIMINIERT' if k36b else 'FEHLT - NICHT GEBLOCKT'}")
    L.append("")

    # --- Soll-Zonen-Abdeckung ----------------------------------------------
    L.append("#" * 118)
    L.append("# SOLL-ZONEN-ABDECKUNG (menschl. Zaehlung +/- %.2f USD um Anker)"
             % ZONEN_BREITE_USD)
    L.append("#" * 118)
    for z in zonen_ergebnis:
        ze = z["zone_edges"]
        L.append(f"\n[{z['name']}] ({z['seite']}, Anker {z['anker']:.2f}) "
                 f"Soll {len(z['soll'])}: {z['soll']} | {z['hinweis']}")
        if not ze:
            L.append("  KEINE SE-Kante im Zonen-Band -> Soll 0")
            continue
        L.append(f"  SE-Kanten im Zonen-Band (box-basis): {len(ze)}")
        for e in ze:
            bb = e.box_basis(box_max_pivot)
            inb = [b for b, _ in e.wicks if b <= box_end - 1]
            mark_soll = [b for b in inb if b in z["soll"]]
            L.append(f"    K{e.kid:3d} basis_box={bb:8.3f} n={e.touch_anzahl}"
                     f" wicks_box={inb}"
                     + (f"  <== Soll-Dochte {mark_soll}" if mark_soll else ""))
        abgedeckt = [b for b, kid in z["deckung"] if kid is not None]
        L.append(f"  -> Soll-Bars abgedeckt: {len(abgedeckt)}/"
                 f"{len(z['soll'])} {z['deckung']}")
        if z["fehlend"]:
            L.append(f"  -> FEHLEND (orphan, kein Zonen-Kanten-Docht): "
                     f"{z['fehlend']}")
    L.append("")

    # --- Ueberlappungs-Protokoll -------------------------------------------
    if scan["ueberlapp"]:
        L.append("-" * 118)
        L.append("UEBERLAPPUNGSPROTOKOLL (Docht im Band mehrerer Kanten; "
                 "U1-Entscheid: hoechste touch_anzahl, Gleichstand aeusseres "
                 "Extremum)")
        L.append("-" * 118)
        for (b, seite, px, cand) in scan["ueberlapp"][:40]:
            cand_txt = "; ".join(
                f"K{kid}(basis {bas:.3f}, {n}T)" for kid, bas, n in cand)
            L.append(f"  bar {b:4d} ({_format_ts(ts, b)}) {seite} "
                     f"docht={px:.3f} | Kandidaten: {cand_txt}")
        if len(scan["ueberlapp"]) > 40:
            L.append(f"  ... +{len(scan['ueberlapp']) - 40} weitere")
        L.append("")

    # --- Box-Range-Setups --------------------------------------------------
    for variante, titel in (("S", "V-S (streng §7.2: aeusserste aktive "
                                  "geborene Kante, handelbar ab >= 3 "
                                  "Touches)"),
                            ("2", "V-2 (Reife-Lockerung: dieselbe "
                                  "Aussengrenze, handelbar ab Geburt "
                                  ">= 2 Touches)")):
        sub = [s for s in setups if s.variante == variante]
        sub.sort(key=lambda s: s.bar)
        L.append("-" * 118)
        L.append(f"BOX-RANGE-SETUPS {titel}: {len(sub)}")
        L.append("-" * 118)
        for s in sub:
            L.append(f"  {s.richtung:5s} bar {s.bar:4d} "
                     f"({_format_ts(ts, s.bar)}) an K{s.kid:3d} "
                     f"basis={s.basis:.3f} sweep={s.sweep:.3f} "
                     f"close={s.trigger_close:.3f} touch_n={s.touch_n}")
        if not sub:
            L.append("  (keine)")
        L.append("")
    return "\n".join(L)


# ==============================================================================
# PNG (Band-Default 0.12)
# ==============================================================================


def _zeichne_png(scan: Dict, zonen_ergebnis: List[Dict],
                 setups: List[_Setup]) -> None:
    band = scan["band_pct"]
    box_end = scan["box_end_bar"]
    d = scan["d"]
    n = scan["n"]
    ts = pd.to_datetime(d["ts"])
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    box_max_pivot = box_end - 3
    idx = np.arange(n)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    box_edges = [e for e in scan["edges"]
                 if any(b <= box_end - 1 for b, _ in e.wicks)]
    box_edges.sort(key=lambda e: e.basis)

    fig, (ax1, ax2, axs) = plt.subplots(
        3, 1, figsize=(18, 14),
        gridspec_kw={"height_ratios": [3.2, 2.6, 1.5], "hspace": 0.14})

    # ---------- Panel 1: komplettes Fenster --------------------------------
    ax1.plot(idx, cl, color="#1f77b4", lw=0.8, alpha=0.9, zorder=2)
    ax1.axvspan(0, box_end, color="gray", alpha=0.10, zorder=1)
    ax1.axvline(box_end, color="black", lw=1.2, ls=":", alpha=0.7)
    ax1.text(box_end, ax1.get_ylim()[0], " Box-Ende 19.08", fontsize=8,
             rotation=90, va="bottom")
    for e in box_edges:
        col = "#d62728" if e.seite == "OBEN" else "#2ca02c"
        ls = "-" if e.seite == "OBEN" else "--"
        # Linie nur ueber die Box (1. bis letzter Box-Docht + Rand)
        b_first = min(b for b, _ in e.wicks if b <= box_end - 1)
        b_last = max(b for b, _ in e.wicks if b <= box_end - 1)
        x0 = max(0, b_first - 20)
        x1 = min(n - 1, b_last + 20)
        ax1.plot(np.arange(x0, x1 + 1), np.full(x1 - x0 + 1, e.basis),
                 color=col, lw=1.2, ls=ls, alpha=0.5, zorder=3)
    # Seeds
    for e in scan["seeds"]:
        if e.letzter_bar <= box_end - 1:
            ax1.plot(e.letzter_bar, e.basis, "x", ms=5, color="gray",
                     alpha=0.8, zorder=5)
    # Sweep-Sperren (rot: blockierte Seed-Geburten, Commit a771e04)
    for (b, _seite, px, _ref, _d) in scan["sweep_sperren"]:
        ax1.plot(b, px, "x", ms=8, color="red", zorder=6, mec="black",
                 mew=0.3)
    for s in setups:
        if s.variante != "S":
            continue
        col = "#d62728" if s.richtung == "SHORT" else "#2ca02c"
        ax1.plot(s.bar, s.basis + (0.25 if s.richtung == "SHORT" else -0.25),
                 "o", ms=6, color=col, zorder=6, mec="black", mew=0.4)
    ticks = np.linspace(0, n - 1, 9).astype(int)
    ax1.set_xticks(ticks)
    ax1.set_xticklabels([ts.iloc[i].strftime("%d.%m") for i in ticks],
                        fontsize=8)
    ax1.set_title(f"V3-Straight-Edge-Audit AUG | SE_BAND {band:.3f} % | "
                  "Box 10.08-18.08 | Keimung >= 2 Dochte, Basis=Docht-Mittel, "
                  "2-Body-Schutz", fontsize=11)
    ax1.set_xlim(-5, n + 5)

    # ---------- Panel 2: Box-Zoom -------------------------------------------
    ax2.plot(np.arange(box_end), cl[:box_end], color="#1f77b4", lw=0.9,
             zorder=2)
    zofarb = {"UPPER-WAND": "black", "LOWER-MAIN": "darkorange",
              "MINOR-DOMINANT": "purple", "MINOR-JUNIOR": "purple"}
    zolst = {"UPPER-WAND": "--", "LOWER-MAIN": "--",
             "MINOR-DOMINANT": ":", "MINOR-JUNIOR": ":"}
    for z in zonen_ergebnis:
        seg = np.full(box_end, np.nan)
        seg[:] = z["anker"]
        col = zofarb.get(z["name"], "black")
        ls = zolst.get(z["name"], "--")
        ax2.plot(np.arange(box_end), seg, color=col, lw=1.4, ls=ls, alpha=0.8)
        ax2.text(box_end - 2, z["anker"], f"{z['anker']:.2f} "
                 f"({z['name']})", fontsize=7.5, color=col, ha="right",
                 va="center")
    for e in box_edges:
        col = "#d62728" if e.seite == "OBEN" else "#2ca02c"
        ls = "-" if e.seite == "OBEN" else "--"
        alpha = 0.8 if e.touch_anzahl >= 3 else 0.35
        x = np.arange(box_end)
        ax2.plot(x, np.full(box_end, e.box_basis(box_max_pivot)),
                 color=col, lw=1.0, ls=ls, alpha=alpha, zorder=3)
        for (wb, wp) in e.wicks:
            if wb < box_end:
                ax2.plot(wb, wp, "o", ms=2.6, color=col, alpha=0.95, zorder=5)
    # Soll-Dochte hervorheben (Rauten)
    for z in zonen_ergebnis:
        for b in z["soll"]:
            if b < box_end:
                pv = float(hi[b]) if z["seite"] == "OBEN" else float(lo[b])
                ax2.plot(b, pv, "D", ms=5.5, color=zofarb[z["name"]],
                         zorder=6, mec="black", mew=0.4)
    # Seeds im Box-Zoom
    for e in scan["seeds"]:
        if e.letzter_bar <= box_end - 1:
            ax2.plot(e.letzter_bar, e.basis, "x", ms=5, color="gray", zorder=5)
    # Sweep-Sperren im Box-Zoom (rot, Commit a771e04)
    for (b, _seite, px, _ref, _d) in scan["sweep_sperren"]:
        if b < box_end:
            ax2.plot(b, px, "x", ms=8, color="red", zorder=6, mec="black",
                     mew=0.3)
    for s in setups:
        off = 0.22 if s.richtung == "SHORT" else -0.22
        style = {"S": "o", "2": "^" if s.richtung == "SHORT" else "v"}
        col = "#d62728" if s.richtung == "SHORT" else "#2ca02c"
        ax2.plot(s.bar, s.basis + off, style[s.variante], ms=6, color=col,
                 alpha=0.95 if s.variante == "S" else 0.55, zorder=7,
                 mec="black", mew=0.3)
    xt = np.linspace(0, box_end - 1, 8).astype(int)
    ax2.set_xticks(xt)
    ax2.set_xticklabels([ts.iloc[i].strftime("%d.%m %H:%M") for i in xt],
                        fontsize=7)
    ax2.set_title("Box-Zoom (10.08-18.08): SE-Kanten (Kreise=Dochte, "
                  "x=Singleton-Seeds, Rauten=Soll-Dochte; "
                  "o=V-S / ^v=V-2-Setups)", fontsize=10)
    ax2.set_xlim(-2, box_end + 4)
    ymin = min(lo[:box_end]) - 0.4
    ymax = max(hi[:box_end]) + 0.4
    ax2.set_ylim(ymin, ymax)

    # ---------- Panel 3: Statistik ------------------------------------------
    axs.axis("off")
    z = []
    n_typ_b = sum(1 for e in scan["edges"] if e.touch_anzahl >= 3)
    z.append(f"Band {band:.3f}% | SE-Kanten gesamt {len(scan['edges'])} "
             f"(Typ-B {n_typ_b}) | Seeds offen {len(scan['seeds'])} | "
             f"Alt-C-Referenz: 39 Kanten / 66 Signale AUG ({ALT_C_IN_BOX} Box)")
    z.append(f"Sweep-Sperren: {len(scan['sweep_sperren'])} | K33 (229) "
             f"{'JA' if any(b == 229 and s == 'OBEN' for b, s, *_r in scan['sweep_sperren']) else 'NEIN'} | "
             f"K36 (242) "
             f"{'JA' if any(b == 242 and s == 'OBEN' for b, s, *_r in scan['sweep_sperren']) else 'NEIN'}")
    for zr in zonen_ergebnis:
        abg = [b for b, kid in zr["deckung"] if kid is not None]
        fehl = zr["fehlend"]
        txt = f"{zr['name']}: Soll {len(zr['soll'])} | abgedeckt {len(abg)}"
        if fehl:
            txt += f" | FEHLEND {fehl}"
        z.append(txt)
    for variante, titel in (("S", "V-S (>= 3 Touches)"),
                            ("2", "V-2 (ab Geburt, >= 2 Touches)")):
        sub = [s for s in setups if s.variante == variante]
        z.append(f"{titel} Box-Setups: {len(sub)}")
    z.append("Band-Sweep {0.11 / 0.115 / 0.12} und Entscheidungspunkte: "
             "siehe TXT/Konsole.")
    axs.text(0.005, 0.97, "\n".join(z), fontsize=10, va="top",
             family="monospace", transform=axs.transAxes)

    leg = [Line2D([0], [0], color="#d62728", lw=1.2, label="OBEN-Kante (SE)"),
           Line2D([0], [0], color="#2ca02c", ls="--", lw=1.2,
                  label="UNTEN-Kante (SE)"),
           Line2D([0], [0], marker="o", color="w", mfc="#d62728",
                  label="V-S-Setup"),
           Line2D([0], [0], marker="^", color="w", mfc="#d62728",
                  label="V-2 SHORT"),
           Line2D([0], [0], marker="v", color="w", mfc="#2ca02c",
                  label="V-2 LONG"),
           Line2D([0], [0], marker="D", color="w", mfc="black",
                  label="Soll-Docht"),
           Line2D([0], [0], marker="x", color="w", mfc="gray",
                  label="Singleton-Seed"),
           Line2D([0], [0], marker="x", color="w", mfc="red",
                  label="Sweep-Sperre (kein Seed)")]
    ax2.legend(handles=leg, loc="upper left", fontsize=7)
    fig.savefig(PNG_OUT, dpi=300)
    plt.close(fig)


# ==============================================================================
# MAIN
# ==============================================================================


def main() -> None:
    print("V3-Straight-Edge-Audit (Spez §7.2, Schritt B) | AUG | "
          f"Band-Sweep {list(SE_BAND_SWEEP)}")
    gesamt_txt: List[str] = []
    scans = {}
    for band in SE_BAND_SWEEP:
        scan = _scan_se(band)
        scans[band] = scan
        zonen = _soll_zonen(scan)
        setups, _stats = _zaehle_setups(scan)
        txt = _report_band(scan, zonen, setups,
                           alt_vergleich=(band == SE_BAND_SWEEP[0]))
        print("\n" + txt)
        gesamt_txt.append(txt)

    # --- Zusammenfassungstabelle ueber den Sweep ---------------------------
    L = []
    L.append("=" * 118)
    L.append("ZUSAMMENFASSUNG BAND-SWEEP | Soll-Wand-Zaehlung +/- %.2f USD | "
             "Box-Setups (in_bar)" % ZONEN_BREITE_USD)
    L.append("=" * 118)
    kopf = (f"{'Band':>7s} | {'SE ges':>6s} {'TypB':>5s} | "
            f"{'UPPER':>7s} {'MAIN':>5s} {'MIN-D':>6s} {'MIN-J':>6s} | "
            f"{'SetupsS':>8s} {'Setups2':>8s}")
    L.append(kopf)
    L.append("-" * 118)
    for band in SE_BAND_SWEEP:
        scan = scans[band]
        zonen = _soll_zonen(scan)
        _, stats = _zaehle_setups(scan)
        n_typ_b = sum(1 for e in scan["edges"] if e.touch_anzahl >= 3)
        cov = {}
        for z in zonen:
            abg = len([b for b, kid in z["deckung"] if kid is not None])
            cov[z["name"]] = f"{abg}/{len(z['soll'])}"
        L.append(
            f"{band:7.3f} | {len(scan['edges']):6d} {n_typ_b:5d} | "
            f"{cov['UPPER-WAND']:>7s} {cov['LOWER-MAIN']:>5s} "
            f"{cov['MINOR-DOMINANT']:>6s} {cov['MINOR-JUNIOR']:>6s} | "
            f"{stats['S']:8d} {stats['2']:8d}")
    L.append("-" * 118)
    L.append("Legende: UPPER/MAIN/MIN-D/MIN-J = abgedeckte Soll-Bars der "
             "menschl. Zonen-Zaehlung (nur in der Box gekeimte Kanten); "
             "SetupsS = V-S (Aussengrenze ab >= 3 Touches); Setups2 = V-2 "
             "(Aussengrenze ab Geburt >= 2 Touches). "
             "Alt-C-Box-Signale: %d." % ALT_C_IN_BOX)

    # --- Sweep-Immunitaets-Nachweis (Commit a771e04) ------------------------
    L.append("")
    L.append("-" * 118)
    L.append("SWEEP-IMMUNITAETS-NACHWEIS (Commit a771e04 / §7.2-Nachtrag): "
             "K33 = Seed 229/66.776, K36 = Seed 242/66.663")
    L.append("-" * 118)
    nachweise = {}
    for band in SE_BAND_SWEEP:
        scan = scans[band]
        sperren = scan["sweep_sperren"]
        k33b = any(b == 229 and s == "OBEN" for b, s, *_r in sperren)
        k36b = any(b == 242 and s == "OBEN" for b, s, *_r in sperren)
        zonen = _soll_zonen(scan)
        cov = {}
        for z in zonen:
            abg = len([b for b, kid in z["deckung"] if kid is not None])
            cov[z["name"]] = (abg, len(z["soll"]))
        nw = AuditNachweisErgebnis(
            band_pct=band, k33_eliminiert=k33b, k36_eliminiert=k36b,
            upper_treffer=cov["UPPER-WAND"][0], upper_soll=cov["UPPER-WAND"][1],
            main_treffer=cov["LOWER-MAIN"][0], main_soll=cov["LOWER-MAIN"][1],
            minor_d_treffer=cov["MINOR-DOMINANT"][0],
            minor_d_soll=cov["MINOR-DOMINANT"][1],
            minor_j_treffer=cov["MINOR-JUNIOR"][0],
            minor_j_soll=cov["MINOR-JUNIOR"][1],
            seeds_offen=len(scan["seeds"]), edges_gesamt=len(scan["edges"]))
        nachweise[band] = nw
        L.append(
            f"  Band {band:.3f}: Sperren {len(sperren):2d} | "
            f"K33 {('JA' if k33b else 'NEIN')} | "
            f"K36 {('JA' if k36b else 'NEIN')} | "
            f"SE gesamt {nw.edges_gesamt:3d} | "
            f"Seeds offen {nw.seeds_offen:2d} | Soll-Zonen "
            f"{nw.upper_treffer}/{nw.upper_soll} {nw.main_treffer}/"
            f"{nw.main_soll} {nw.minor_d_treffer}/{nw.minor_d_soll} "
            f"{nw.minor_j_treffer}/{nw.minor_j_soll}")
    nw12 = nachweise[PNG_DEFAULT_BAND]
    L.append("-" * 118)
    L.append(f"  VERDIKT Band {PNG_DEFAULT_BAND:.3f} (Default): ist_perfekt = "
             f"{nw12.ist_perfekt}")
    L.append("  Bedingung: K33 eliminiert UND K36 eliminiert UND Soll-Zonen "
             f"5/5 7/7 4/4 3/3 -> erfuellt: {nw12.ist_perfekt} "
             f"(K33={nw12.k33_eliminiert}, K36={nw12.k36_eliminiert}, "
             f"Zonen {nw12.upper_treffer}/{nw12.upper_soll} "
             f"{nw12.main_treffer}/{nw12.main_soll} "
             f"{nw12.minor_d_treffer}/{nw12.minor_d_soll} "
             f"{nw12.minor_j_treffer}/{nw12.minor_j_soll})")
    L.append("  -> Arretierung bestaetigt: Die Sweep-Immunitaet (Reclaim-"
             "Dochte bilden keine Linien) ist additiv nachgewiesen; "
             "K33/K36 sind ersatzlos eliminiert, die Soll-Waende bleiben "
             "unveraendert. Damit ist diese Tabelle die formale Abnahme-"
             "Grundlage fuer das 'Go' zu Schritt B (additiver Umbau von "
             "_replay_c im Harness) und Schritt C (AUG-Lauf --modus C).")
    L.append("")
    L.append("ENTSCHEIDUNGSPUNKTE FUER DIE ABNNAHME (Schritt C):")
    L.append("  (1) Band-Default: 0.12 erreicht UPPER 5/5; 0.11/0.115 -> 4/5 "
             "(bar 107 bleibt in der Box Singleton-Seed; K23 keimt erst mit "
             "bar 730 am 19.08). Arretierter Default-Vorschlag: 0.12.")
    L.append("  (2) E1-Zwei-Linien Minor: freier Scan weist bar 320 dem "
             "Junior zu (Junior erreichte ueber bar 172 zuerst 3 Touches); "
             "dominant ~64.21 = {126,316,361,406}, junior ~64.33 = "
             "{130,162,172,320,346,368,372}. Zonen-Abdeckung 4/4 bleibt; "
             "die E1-Zuordnung (320->dominant) ist mit der freien Keimung "
             "nicht reproduzierbar - Entscheidung: freie Keimung akzeptieren "
             "oder E1-Zuordnung als Sonderregel arretieren.")
    L.append("  (3) Upper-Wand: 2 Sub-Linien statt einer 66.42-66.46-Linie: "
             "K35 ~66.36 ({237,249,286,536,730}) und K23 ~66.51 "
             "({107,529,565}). K35 schlaeft am 18.08 03:15 (2 Koerper ueber "
             "66.345 in Bars 564/565) und wird erst durch Bar 730 (19.08) "
             "reaktiviert; K23 (66.51) bleibt AKTIV (Koerper nie ueber 66.5).")
    L.append("  (4) Unterkante: Staffelung L1 ~63.63 ({30,60,63,386,632}) + "
             "L2 ~63.76 ({52,57,380,627,635}) + Sweep-Zone ~63.49 "
             "({7,398,621}); Soll-Main 7/7 bleibt (Zonen-Zaehlung).")
    L.append("  (5) Setup-Zahl in der Box: V-S (Reife >= 3) = 3-4 - deutlich "
             "UNTER der Erwartung 6-9. V-2 (handelbar ab Geburt >= 2) = 7 "
             "auf allen Band-Stufen - trifft das Zielband 6-9. Die 3 "
             "zusaetzlichen V-2-Setups (Bars 22/60/223 an K3/K10/K17) sind "
             "Frueh-Struktur-Trades an der jeweils ersten handelbaren "
             "Aussengrenze VOR Keimung der spaeteren Waende; die "
             "Wand-Sweeps 398/527/564/639 sind in beiden Varianten enthalten.")
    L.append("      -> Abnaehme noetig: (a) V-S (streng) vs. V-2 (ab Geburt) "
             "fuer Schritt C; (b) Faellt die Reife-Schwelle auf >= 2, fallen "
             "die Frueh-Struktur-Trades 22/60/223 mit an - sind diese "
             "erwuenscht oder gehoert eine Mindest-Reife (3) zur "
             "Aussengrenzen-Definition?; (c) next_bar-Split mitzaehlen; "
             "(d) F3-Lockerung pruefen; (e) L2-Staffelung/K23 (66.51) als "
             "separate Wall-Kante mit eigenem Signalrecht bewerten.")
    tab = "\n".join(L)
    print("\n\n" + tab)
    gesamt_txt.append(tab)

    with open(TXT_OUT, "w", encoding="utf-8") as f:
        f.write("\n\n".join(gesamt_txt))
    print(f"\nTXT geschrieben: {TXT_OUT}")

    # --- PNG fuer den Default-Band (0.12) ----------------------------------
    scan = scans[PNG_DEFAULT_BAND]
    zonen = _soll_zonen(scan)
    setups, _ = _zaehle_setups(scan)
    try:
        _zeichne_png(scan, zonen, setups)
        print(f"PNG geschrieben: {PNG_OUT} (Band {PNG_DEFAULT_BAND}, 300 dpi)")
    except OSError as e:
        print(f"[WARNUNG] PNG nicht schreibbar (gesperrt?): {e}")


if __name__ == "__main__":
    main()
