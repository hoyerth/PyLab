# -*- coding: utf-8 -*-
"""test/tmp_kanten_engine_replay.py -- Schritt-0-Replay-Harness (Setup B, SILVER M15).

Kausal-sequentieller Replay-Harness fuer die Standalone-Kanten-Engine gemaess
``docs/reclaim_kanten_engine_spez.md`` (Commit c66457b, §§ 3/5/6/7/8) und den
drei bindenden User-Praezisierungen (POC-Seiten-Gate + CRV, Gegenkanten-Paarung,
Volumen-Basis VWAP). Strukturvorlage: test/tmp_reclaim_snapshot_replay.py.

ABGRENZUNG (Spez §1.1): Reine OHLCV-Rohdaten - KEINE Phasen-Segmentierung,
KEIN finales Zonen-Screening, KEIN Phasen-Ende-Wissen. Kanten entstehen kausal
und sequenziell aus bestaetigten Pivots (2-Bar-Puffer, gueltig_ab_bar = m+2).

LAUF-REIHENFOLGE (Freigabe):
    Schritt A: AUG-Smoke (max_tage=60)  -> Mechanik-Verifikation an Einzelfaellen
    Schritt B: Sensitivitaetsmatrix max_tage in {1, 5, 20, 60} auf S1 und S2
               gegen das Gate (PF >= 1.30 & Summe R > 0 je Fenster)

IMPLEMENTIERUNGS-PRAEZISIERUNGEN (Spez-mehrdeutige Stellen, fuer den Harness
fixiert; im Smoke-Review durch den User abnehmbar):

  P1 (Pivot-Definition, kausal): H-Pivot bei Bar m  <=>  high[m] strikt groesser
     als alle 4 Nachbarn high[m-2..m+2] ausser m; L symmetrisch. Bestaetigt ab Bar
     m+2 (= Iteration k, in der m = k-2 verarbeitet wird). Strikte Variante
     verhindert Doppel-Pivots an flachen Spitzen; die Kernel-Baseline erlaubt
     >= fuer die +/-1-Nachbarn - bewusste Abweichung, dokumentiert.
     Randfall: H und L gleichzeitig erfuellt (extreme Umkehrbar) -> H gewinnt.

  P2 (SwingFilter, finale Semantik): Amplitude amp = |p - p_gegen| / p_gegen
     relativ zum LETZTEN bestaetigten gegensaetzlichen PIVOT (auch wenn dieser
     verworfen wurde). Gegenkanten-Ursprung = der letzte gegensaetzliche Pivot
     war ein Kanten-Ereignis (Touch an bestehender Kante ODER Geburt).
       (a) kein Gegner-Referenz-Pivot  -> Pivot zaehlt
       (b) amp >= MIN_SWING_PCT (1.0)  -> Pivot zaehlt (Touch-Zuordnung ODER Geburt)
       (c) amp <  1.0 UND Gegenkanten-Ursprung -> zaehlt NUR als Touch an
           bestehender Kante im +/-0.15-Band; KEINE Geburt (kein Over-Segmenting
           in Korridor-Mitte)
       (d) sonst -> Zwischenwelle, verworfen (kein Zaehler, keine Verschiebung)
     Jeder bestaetigte Pivot aktualisiert die Referenz seiner Seite
     (kanten_ereignis=True bei Touch/Geburt, False bei Verwerfung).

  P3 (Touch-Zuordnung): Pivot -> Kante gleicher Seite (AKTIV oder SCHLAFEND,
     nicht VERFALLEN) mit geringster |preis - balance| <= DENSITY_BAND (0.15).
     Keine Zuordnung + Fall (b) -> Geburt einer neuen Kante (basis = Dochtpreis).

  P4 (Balance-Update, Praezisierung 3): VWAP = Sum(P*V)/Sum(V) ueber die
     bestaetigten Touches, deren Extremum im +/-0.15-Band der Balance VOR dem
     Update liegt. volumen_im_band = Summe der tick_volume dieser Touches.

  P5 (Einstiegs-Kante, Signal-Scan): Pro Richtung wird nur die A5-Kante
     geprueft: hoechste (SHORT) bzw. tiefste (LONG) aktive Typ-B-Kante, deren
     Balance durchstochen wurde (balance < high[k] bzw. > low[k]).

  P6 (next_bar-Erkennung): Sweep an Bar k ohne in_bar-Reclaim wird gemerkt und
     bei Bar k+1 gegen die DANN aktuelle Balance geprueft (high[k] > balance
     UND close[k+1] <= balance fuer SHORT). Entry open[k+2] == open[(k+1)+1].

  P7 (Cooldown): strikt je Kante (cooldown_bis_bar = signal_bar + 12), nicht
     global. in_bar-Scan (S4) laeuft vor dem next_bar-Abgleich (S5) -> bei
     Konflikt gewinnt das frische in_bar-Ereignis (Cooldown blockiert S5).

  P8 (Trade-Aufloesung): Exakter Port der Baseline-``_aufloesen``-Semantik
     (reclaim_live_kernel): SL 0.45%, TP1 25%/TP2 75%, unabhaengige Haelften,
     kein Nachzug, kein Trailing; offene Trades laufen bis Fensterende
     (close[-1], Grund ENDE).

Datenvertrag: df-Spalten ts (tz-naiv)/open/high/low/close/tick_volume, geladen
mit ``time AT TIME ZONE 'UTC'`` (BKZ-Kanon, `docs/ZEITBASIS_KANON.md`).
Fenster exakt wie frozen:
AUG 2026-08-10..08-28, S1 2026-02-05..08-28, S2 2025-01-01..12-01.

Aufruf:
    .venv\\Scripts\\python.exe test/tmp_kanten_engine_replay.py                 # AUG-Smoke, max_tage=60
    .venv\\Scripts\\python.exe test/tmp_kanten_engine_replay.py --fenster S1 --max-tage 5
    .venv\\Scripts\\python.exe test/tmp_kanten_engine_replay.py --matrix        # Smoke + S1/S2 x {1,5,20,60}
    .venv\\Scripts\\python.exe test/tmp_kanten_engine_replay.py --dpi 300       # PNG-Aufloesung (Default 300)

Report:   Konsole + test/stats_kanten_engine_replay.txt (bei --matrix frisch).
PNG (je Lauf, 300 dpi): test/kanten_engine_trades_{FENSTER}_mt{max_tage}.png
    * Chart oben: Close + Trades mit START (Entry ^/v, LONG gruen / SHORT rot),
      ENDE je Haelfte (o = 25%-Haelfte, s = 75%-Haelfte; Farbe nach Grund:
      TP1/TP2 gruen, SL rot, Zeitende/ENDE grau); Linie Entry -> Exit je Haelfte.
      Text am Trade-Ende: CRV-Wert + R-Ergebnis (bei > 80 Trades nur R-Kurzform).
      Prio-Kanten (an Signalen beteiligte Typ-B-Kanten) als Balance-Linien:
      OBEN-Kanten durchgezogen, UNTEN-Kanten gestrichelt; Einstiegs-Kanten
      dicker, reine Gegenkanten dezent; kleine Punkte = Touch-Eichpunkte;
      Linie bis Verfall (letzter Touch + max_tage) bzw. Fensterende.
    * Ax_stat unten: Statistik-Text; CRV-Statistik zentral (Spalte Mitte);
      Anzahl Prio-Kanten.
    * Legende oben links; 300 dpi. KEINE Summierungs-/Equity-Grafik.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, Set, Tuple

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH: Path = ROOT / "data" / "market_data.duckdb"
REPORT_TXT: Path = ROOT / "test" / "stats_kanten_engine_replay.txt"

# ==============================================================================
# MODULKONSTANTEN (Spez §4; Werte der arretierten Baseline)
# ==============================================================================

PIVOT_LOOKBACK: int = 2            # Spez §4: Pivot-Lookback / 2-Bar-Puffer
DENSITY_BAND: float = 0.15         # Spez §4: Touch-Band (+/- 0.15 USD)
MIN_SWING_PCT: float = 1.0         # Spez §4: SwingFilter-Amplitude (%)
MIN_TOUCHES_B: int = 3             # Spez §4: Typ B ab 3 bestaetigten Touches
SCHLAFEND_BODIES: int = 2          # Spez §4: 2 konsekutive Koerper jenseits
COOLDOWN_BARS: int = 12            # Spez §4: Cooldown je Kante
ANTEIL_TP1: float = 25.0           # Baseline: 25%-Split auf TP1 (TP2 75%)
MAX_SIGNAL_ZEILEN: int = 60        # Report-Kappung der Signalliste

# --- V2 / Modus B (Spez §4.1, Commit f75f6d0) --------------------------------
RATCHET_TOL_PCT: float = 0.10      # Spez §4.1: Admission-Toleranz (%)
CLUSTER_DISTANZ_USD: float = 0.30  # Spez §4.1: Cluster-Distanz (USD)
GRACE_PERIODE_BARS: int = 96       # Spez §4.1: rollierende Grace-Periode
ZWISCHENSCHWUNG_PCT: float = 1.5   # Spez §4.1: max. Zwischenschwung (%)
MAX_DIAGNOSE_ZEILEN: int = 40      # Report-Kappung der B-Diagnose

# --- V3 / Modus C (Spez §7.1/§8.4, arretiert 2026-09-08, E1-E5/F1-F3/U1) ----
V3_TOUCH_BAND_PCT: float = 0.23        # relatives Touchband (F2, ~0.15 USD)
V3_GEBURTS_SPERR_PCT: float = 0.50     # asymmetrische Geburts-Sperre (F)
V3_MIN_TOUCH_BAR_ABSTAND: int = 3      # Touch-Mindestabstand (A)
V3_MIN_SIGNAL_BAR_ABSTAND: int = 3     # Diagnose (aktive Bremse ist F3)
V3_TP_MINDIST_PCT: float = 1.5         # Mindest-Raum Basis-zu-Basis (C/D)
V3_SL_BUFFER_USD: float = 0.05         # struktureller SL-Puffer (B)
V3_TP1_ANTEIL_PCT: float = 50.0        # Zwei-Stufen-Split 50/50 (D)
V3_ERLAUBE_NEXT_BAR: bool = True       # next_bar nur als separater Split (G2)

EngineModus = Literal["A", "B", "C"]

FensterTyp = Literal["AUG", "S1", "S2"]
FENSTER: Dict[FensterTyp, Tuple[str, str]] = {
    "AUG": ("2026-08-10", "2026-08-28"),  # nur Referenz (S1 enthaelt AUG)
    "S1": ("2026-02-05", "2026-08-28"),
    "S2": ("2025-01-01", "2025-12-01"),
}

# ==============================================================================
# USER-DATENVERTRAEGE (bindend, Freigabe-Nachricht)
# ==============================================================================


@dataclass(frozen=True, slots=True)
class HarnessKonfiguration:
    max_tage: int
    sl_pct: float = 0.45
    min_spread_pct: float = 1.5
    tp2_puffer_pct: float = 0.20
    crv_min_tp1: float = 1.0
    # --- V2 / Modus B (Spez §4.1/§8.1; Defaults = Modus-A-Verhalten) ---
    modus: EngineModus = "A"
    toleranz_ratchet_pct: float = RATCHET_TOL_PCT
    cluster_distanz_usd: float = CLUSTER_DISTANZ_USD
    grace_periode_bars: int = GRACE_PERIODE_BARS
    max_zwischenschwung_pct: float = ZWISCHENSCHWUNG_PCT
    touch_band_usd: float = DENSITY_BAND
    pruefe_trigger_an_extremum: bool = True   # B: Trigger an anker_extremum
    body_reclaim_reaktivierung: bool = True   # B: SCHLAFEND->AKTIV per Close


@dataclass(frozen=True, slots=True)
class FensterErgebnis:
    fenster_name: str
    max_tage: int
    trades_gesamt: int
    in_bar_trades: int
    next_bar_trades: int
    win_rate_pct: float
    summe_r: float
    profit_factor: float
    low_n_warnung: bool
    gate_bestanden: bool


# ==============================================================================
# V3-DATENVERTRAEGE / MODUS C (Spez §7.1, arretiert 2026-09-08; F1-F3/U1/U2)
# Autarker Zusatzblock - die A/B-Vertraege oben bleiben unangetastet.
# ==============================================================================

KantenStatusC = Literal["AKTIV", "SCHLAFEND"]   # kein VERFALLEN/Zeitverfall


@dataclass(frozen=True, slots=True)
class ModusCKonfiguration:
    """Bindende V3-Defaults (Spez §7.1, arretiert; §8.4 C-Gate ohne Grid)."""
    touch_band_pct: float = V3_TOUCH_BAND_PCT
    min_touch_bar_abstand: int = V3_MIN_TOUCH_BAR_ABSTAND
    min_signal_bar_abstand: int = V3_MIN_SIGNAL_BAR_ABSTAND
    tp_mindist_pct: float = V3_TP_MINDIST_PCT
    sl_buffer_usd: float = V3_SL_BUFFER_USD
    tp1_anteil_pct: float = V3_TP1_ANTEIL_PCT
    erlaube_next_bar: bool = V3_ERLAUBE_NEXT_BAR


@dataclass(slots=True)
class StatischeKanteC:
    """V3-Kante (User-Freigabe 2026-09-08, Spez §7.1).

    basis_preis ist der einzige, unverrueckbare Anker. Status nur AKTIV/
    SCHLAFEND (kein VERFALLEN, kein Zeitverfall). Touch = bestaetigter Pivot-
    Docht im touch_band_pct-Band (0,23 %); SCHLAFEND = 2 konsekutive Koerper
    vollstaendig jenseits basis_preis; Reaktivierung per Docht-Touch im Band.
    letzter_signal_bar sperrt Re-Trigger ohne neuen Touch (F3).
    """

    kanten_id: int
    seite: KantenSeite
    basis_preis: float          # Unverrueckbarer Fixpreis
    geburts_bar: int
    letzter_touch_bar: int = -1000
    letzter_signal_bar: int = -1000
    touch_bars: List[int] = field(default_factory=list)
    outside_body_count: int = 0
    status: KantenStatusC = "AKTIV"

    @property
    def touch_anzahl(self) -> int:
        return len(self.touch_bars)

    @property
    def neuester_touch_bar(self) -> int:
        """Hoechste pivot_bar aller bestaetigten Touches (-1000 wenn keine)."""
        return self.touch_bars[-1] if self.touch_bars else -1000

    @property
    def ist_handelbar_typ_b(self) -> bool:
        """Zwingend >= 3 Touches fuer den Einstieg (nur AKTIV)."""
        return self.touch_anzahl >= 3 and self.status == "AKTIV"

    @property
    def ist_gueltiges_kursziel_typ_a(self) -> bool:
        """Mindestens 2 Touches als passives Kursziel (auch SCHLAFEND)."""
        return self.touch_anzahl >= 2

    def ist_im_touch_band(self, extremum_preis: float,
                          cfg: ModusCKonfiguration) -> bool:
        """Relatives Touch-Band: |p - basis| / basis * 100 <= touch_band_pct."""
        diff_pct = (abs(extremum_preis - self.basis_preis)
                    / self.basis_preis * 100.0)
        return diff_pct <= cfg.touch_band_pct


@dataclass(frozen=True, slots=True)
class ModusCSignal:
    """V3-Signal-Vertrag (User-Fassung, Spez §7.1 V3-Datenvertraege)."""

    bar_index: int              # Entscheidungs-Bar k (Reclaim in Bar k)
    zeitstempel: pd.Timestamp
    kanten_id: int
    richtung: SignalRichtung
    basis_preis: float
    sweep_preis: float          # high[k] bzw. low[k] (Docht-Durchstich)
    trigger_preis: float        # close[k] (Reclaim-Schluss)
    entry_preis: float          # open[k+1] (in_bar) bzw. open[k+2] (next_bar)
    stop_loss: float            # Sweep-Docht +/- sl_buffer_usd (strukturell)
    tp1_preis: float            # Naechste Gegenkante >= tp_mindist_pct
    tp2_preis: Optional[float]  # Uebergeordnete Kante dahinter
    tp1_anteil_pct: float = V3_TP1_ANTEIL_PCT


@dataclass(frozen=True, slots=True)
class AsymmetrischeGeneseRegeln:
    """Asymmetrische Geburts-Sperre + Touchband der V3-Genese (Spez §7.1 F)."""
    touch_band_pct: float = V3_TOUCH_BAND_PCT
    geburts_sperr_pct: float = V3_GEBURTS_SPERR_PCT
    min_bar_abstand: int = V3_MIN_TOUCH_BAR_ABSTAND


def darf_kante_geboren_werden(
    seite: KantenSeite,
    neuer_preis: float,
    bestehende_kanten: List["StatischeKanteC"],
    regeln: AsymmetrischeGeneseRegeln,
) -> bool:
    """Asymmetrisch (Spez §7.1 F): aeusseres Extremum darf immer gebaeren;
    innere Pivots innerhalb geburts_sperr_pct werden geblockt (Zwischenwelle)."""
    for kante in bestehende_kanten:
        if kante.seite != seite:
            continue
        dist_pct = (abs(neuer_preis - kante.basis_preis)
                    / kante.basis_preis * 100.0)
        if dist_pct <= regeln.geburts_sperr_pct:
            if seite == "OBEN" and neuer_preis <= kante.basis_preis:
                return False   # innerer Pivot unter bestehender Kante
            if seite == "UNTEN" and neuer_preis >= kante.basis_preis:
                return False   # innerer Pivot ueber bestehender Kante
    return True


@dataclass(frozen=True, slots=True)
class KantenDominanzVergleich:
    """Dominanz-Matching mit U1-Fix (Spez §7.1 F, Commit 61a0c29).

    Etablierte Kante gewinnt; bei Gleichstand stets das aeussere Extremum
    (OBEN: hoehere Basis; UNTEN: tiefere Basis) - kein Retail-FIFO.
    """

    seite: KantenSeite

    def waehle_dominante_kante(
        self,
        kante_a_basis: float,
        kante_a_touches: int,
        kante_b_basis: float,
        kante_b_touches: int,
    ) -> Literal["A", "B"]:
        """Etablierte Kante gewinnt; bei Gleichstand stets das aeussere Extremum."""
        if kante_a_touches != kante_b_touches:
            return "A" if kante_a_touches > kante_b_touches else "B"
        if self.seite == "OBEN":
            return "A" if kante_a_basis > kante_b_basis else "B"
        return "A" if kante_a_basis < kante_b_basis else "B"


# --- Interne C-Laufzeit-Typen (Replay-Buchhaltung, analog _Signal) ----------


@dataclass(slots=True)
class _CTradeResult:
    r_mult: float
    resultat: Literal["GEWONNEN", "VERLOREN", "NEUTRAL"]
    grund1: str                 # TP1 / TP2 / SL / ENDE (Haelfte 1)
    grund2: str                 # TP1 / TP2 / SL / ENDE (Haelfte 2)
    exit1: float
    exit2: float
    r1: float = 0.0
    r2: float = 0.0
    exit1_bar: int = -1
    exit2_bar: int = -1


@dataclass(slots=True)
class _CSignal:
    signal_bar: int             # Entscheidungs-Bar k (Reclaim in Bar k)
    sweep_bar: int              # Sweep-Bar (k bei in_bar, k-1 bei next_bar)
    ts: pd.Timestamp
    richtung: SignalRichtung
    semantik: SignalSemantik
    kanten_id: int
    basis_preis: float
    sweep_preis: float          # Docht-Durchstich des Sweep-Bars
    trigger_preis: float        # close[k] (Reclaim-Schluss)
    entry_bar: int              # k + 1 (open[k+1])
    entry_preis: float
    sl_preis: float             # struktureller SL
    tp1_preis: float
    tp2_preis: Optional[float]
    dist_gegen_pct: float       # Distanz Basis-zu-Basis zur naechsten Kante
    touch_anzahl: int
    trade: Optional[_CTradeResult] = None


@dataclass(slots=True)
class _CZustand:
    """Laufender C-Zustand (F3 / max. 1 offene Position je Kante)."""
    offen_bis: Dict[int, int] = field(default_factory=dict)  # kid -> letzter Exit


@dataclass(slots=True)
class _ReplayErgebnisC:
    fenster: FensterTyp
    cfg: ModusCKonfiguration
    n_bars: int
    laufzeit_s: float
    kanten: Dict[int, StatischeKanteC] = field(default_factory=dict)
    signale: List[_CSignal] = field(default_factory=list)
    ablehnung: Dict[str, int] = field(default_factory=dict)
    sweeps_ohne_reclaim: int = 0
    nextbar_reclaim_ok: int = 0
    nextbar_abgelehnt: int = 0


# ==============================================================================
# INTERNE VERTRAEGE (Spez §5 angelehnt + Replay-Erweiterungen)
# ==============================================================================

KantenSeite = Literal["OBEN", "UNTEN"]
KantenZustand = Literal["AKTIV", "SCHLAFEND", "VERFALLEN"]
SignalRichtung = Literal["SHORT", "LONG"]
SignalSemantik = Literal["in_bar", "next_bar"]
ReclaimStufe = Literal["STUFE_1_IN_BAR", "STUFE_2_KERZE_2",
                       "STUFE_3_KERZE_3"]  # D2 (Freigabe 2026-09-08)


@dataclass(slots=True)
class _KantenTouch:
    pivot_bar: int              # Pivot-Bar m
    ts: pd.Timestamp
    preis: float                # high[m] bzw. low[m] (Docht-Extremum)
    volumen: float              # tick_volume[m]
    gueltig_ab_bar: int         # m + PIVOT_LOOKBACK
    amplitude_pct: float
    gegenkanten_ursprung: bool


@dataclass(slots=True)
class _Kante:
    kanten_id: int
    seite: KantenSeite
    geburts_bar: int            # Pivot-Bar der Geburt
    geburts_ts: pd.Timestamp
    basis_preis: float          # 1. Touch: Docht-Extremum (unveraendert)
    balance_preis: float        # VWAP der im-Band-Touches (KantenBalancierung)
    volumen_im_band: float      # Summe tick_volume der im-Band-Touches
    zustand: KantenZustand = "AKTIV"
    cooldown_bis_bar: int = -10**9
    touche: List[_KantenTouch] = field(default_factory=list)
    letzter_touch_bar: int = -1
    letzter_touch_ts: Optional[pd.Timestamp] = None
    # V2 / Modus B: laufendes Extremum (Ratchet; 0.0 = inaktiv im Modus A)
    anker_extremum: float = 0.0

    @property
    def touch_anzahl(self) -> int:
        return len(self.touche)

    @property
    def ist_typ_b(self) -> bool:
        return self.touch_anzahl >= MIN_TOUCHES_B

    @property
    def ist_handelbar(self) -> bool:
        return self.ist_typ_b and self.zustand == "AKTIV"


def _ref_preis(k2: "_Kante", nutze_anker: bool) -> float:
    """Modus-abhaengige Trigger-/Admissions-Referenz der Kante.

    Modus B (nutze_anker=True): anker_extremum (Ratchet-Extremum).
    Modus A (False): balance_preis (VWAP).
    """
    if nutze_anker and k2.anker_extremum > 0.0:
        return k2.anker_extremum
    return k2.balance_preis


@dataclass(slots=True)
class _ZonenMerkposten:
    """Unbestaetigte Cluster-Akkumulation (herrenlose Zone, Spez §5.1).

    Wird beim 1. Zonen-Retest ohne Kante im Band angelegt (nur bei
    Gegenkanten-Ursprung); Geburt am 2. Retest innerhalb der Grace-Periode
    und unterhalb der Schwung-Huerde (kausale Cluster-Geburt, §4.1).
    """

    seite: KantenSeite
    erst_bar: int
    letzter_bar: int
    anker_extremum: float          # laufendes Extremum (Ratchet: nach aussen)
    retest_bars: List[int] = field(default_factory=list)
    retest_preise: List[float] = field(default_factory=list)
    retest_volumina: List[float] = field(default_factory=list)
    retest_amps: List[float] = field(default_factory=list)
    retest_herkunft: List[bool] = field(default_factory=list)

    def ist_abgelaufen(self, aktueller_bar: int, grace_bars: int) -> bool:
        return (aktueller_bar - self.letzter_bar) > grace_bars

    def schwung_ok(self, m: int, hi: np.ndarray, lo: np.ndarray,
                   max_schwung_pct: float) -> bool:
        """Zwischenschwung seit dem letzten Retest <= Schwelle (Spez §4.1)."""
        lo_bar = self.letzter_bar + 1
        if m <= self.letzter_bar:
            return True
        a = self.anker_extremum
        if self.seite == "UNTEN":
            swing = float(np.max(hi[lo_bar:m + 1]))
            pct = (swing - a) / a * 100.0
        else:
            swing = float(np.min(lo[lo_bar:m + 1]))
            pct = (a - swing) / a * 100.0
        return pct <= max_schwung_pct


@dataclass(slots=True)
class _TradeResult:
    r_mult: float
    resultat: Literal["GEWONNEN", "VERLOREN", "NEUTRAL"]
    grund1: str
    grund2: str
    exit1: float
    exit2: float
    r1: float = 0.0              # R der 25%-Haelfte (TP1/SL/ENDE)
    r2: float = 0.0              # R der 75%-Haelfte (TP2/SL/ENDE)
    exit1_bar: int = -1          # absolute Bar des 1. Exits (Haelfte 1)
    exit2_bar: int = -1          # absolute Bar des 2. Exits (Haelfte 2)


@dataclass(slots=True)
class _Signal:
    signal_bar: int             # Entscheidungs-Bar k (nach close[k])
    sweep_bar: int              # Sweep-Bar (k bei in_bar, k-1 bei next_bar)
    ts: pd.Timestamp
    richtung: SignalRichtung
    semantik: SignalSemantik
    kanten_id: int
    kanten_id_gegen: int
    kanten_alter_bars: int      # k - geburts_bar (seit Geburts-Pivot)
    kanten_touch_anzahl: int
    entry_bar: int              # k + 1 (open[k+1])
    entry_preis: float
    sl_preis: float
    tp1_poc_preis: float
    tp2_preis: float
    crv_tp1: float
    spread_pct: float
    trade: Optional[_TradeResult] = None


@dataclass(slots=True)
class _ReplayErgebnis:
    fenster: FensterTyp
    cfg: HarnessKonfiguration
    n_bars: int
    laufzeit_s: float
    kanten_geboren: int = 0
    kanten_oben: int = 0
    kanten_unten: int = 0
    kanten_typ_b: int = 0
    kanten_verfallen: int = 0
    signale: List[_Signal] = field(default_factory=list)
    # Diagnose next_bar-Mechanik (P6): Sweeps ohne in_bar-Reclaim -> Kandidaten
    sweeps_ohne_reclaim: int = 0     # S6: pending-Eintraege (Sweep ohne Reclaim)
    nextbar_reclaim_ok: int = 0      # S5: Reclaim in Folge-Bar bestaetigt
    nextbar_gate_abgelehnt: int = 0  # S5: Reclaim ok, aber Gates abgelehnt
    nextbar_ablehnung: Dict[str, int] = field(default_factory=dict)
    # Kanten-Speicher (nur fuer Chart-Diagnose: Balance-Linien der Prio-Kanten)
    kanten: Dict[int, "_Kante"] = field(default_factory=dict)
    # Modus-B-Diagnose (Spez §8.1)
    diagnose: List[str] = field(default_factory=list)
    cluster_geburten: int = 0
    swing_geburten: int = 0
    neue_merkposten: int = 0
    merkposten_verfallen_zeit: int = 0
    merkposten_verfallen_schwung: int = 0
    ratchet_abgelehnt: int = 0
    body_reclaims: int = 0

    def fenster_ergebnis(self) -> FensterErgebnis:
        """Aggregation auf den bindenden User-Vertrag FensterErgebnis."""
        trades = [s for s in self.signale if s.trade is not None]
        n_in = sum(1 for s in trades if s.semantik == "in_bar")
        n_next = sum(1 for s in trades if s.semantik == "next_bar")
        gew = sum(1 for s in trades if s.trade is not None and s.trade.resultat == "GEWONNEN")
        verl = sum(1 for s in trades if s.trade is not None and s.trade.resultat == "VERLOREN")
        entschieden = gew + verl
        sum_r = sum(s.trade.r_mult for s in trades if s.trade is not None)
        sum_pos = sum(s.trade.r_mult for s in trades
                      if s.trade is not None and s.trade.r_mult > 1e-9)
        sum_neg = sum(-s.trade.r_mult for s in trades
                      if s.trade is not None and s.trade.r_mult < -1e-9)
        if entschieden == 0:
            pf = 0.0
        elif sum_neg <= 0.0:
            pf = float("inf")
        else:
            pf = sum_pos / sum_neg
        winrate = 100.0 * gew / entschieden if entschieden else 0.0
        low_n = entschieden < 20
        gate = entschieden > 0 and sum_r > 0 and pf >= 1.30
        return FensterErgebnis(
            fenster_name=self.fenster,
            max_tage=self.cfg.max_tage,
            trades_gesamt=len(trades),
            in_bar_trades=n_in,
            next_bar_trades=n_next,
            win_rate_pct=winrate,
            summe_r=sum_r,
            profit_factor=pf,
            low_n_warnung=low_n,
            gate_bestanden=gate,
        )


# ==============================================================================
# DATEN-LADUNG (BKZ-Kanon: AT TIME ZONE 'UTC')
# ==============================================================================


def _lade_fenster(fenster: FensterTyp) -> pd.DataFrame:
    """OHLCV-Fenster tz-naiv (time AT TIME ZONE 'UTC' = BKZ).

    Zeitbasis-Kanon K1/K4 (`docs/ZEITBASIS_KANON.md`): Rechenbasis ist
    ausschliesslich die Broker-Kerzen-Zeit (BKZ) = ``time AT TIME ZONE
    'UTC'``. Regionale Projektionen (`Europe/Berlin`/`Europe/Budapest`)
    sind reine Anzeige-Dubletten und werden hier nicht verwendet.

    Returns:
        DataFrame mit ``ts`` (BKZ, tz-naiv) sowie open/high/low/close/
        tick_volume, aufsteigend nach ``ts``.
    """
    start, ende = FENSTER[fenster]
    con = duckdb.connect(str(DB_PATH), read_only=True)
    d = con.execute(f"""
        -- Zeitbasis-Kanon K1/K4 (docs/ZEITBASIS_KANON.md):
        -- SELECT und WHERE nutzen dieselbe Basis (BKZ = AT TIME ZONE 'UTC').
        -- Die frueher verwendete Berlin-Projektion erzeugte einen
        -- DST-abhaengigen Offset (+1 h Winter / +2 h Sommer) und verschob
        -- Kalendergrenzen um 4 bzw. 8 Bars.
        -- Migration V017 -> V018: box_end_bar 640 -> 644.
        SELECT time AT TIME ZONE 'UTC' AS ts, open, high,
               low, close, tick_volume
        FROM ohlcv_bars
        WHERE symbol='SILVER' AND timeframe='M15'
          AND time AT TIME ZONE 'UTC' >= DATE '{start}'
          AND time AT TIME ZONE 'UTC' <  DATE '{ende}'
        ORDER BY time
    """).fetchdf()
    con.close()
    if d["ts"].dt.tz is not None:
        d["ts"] = pd.to_datetime(d["ts"], utc=True).dt.tz_localize(None)
    return d.sort_values("ts").reset_index(drop=True)


# ==============================================================================
# PIVOT-DETEKTION (kausal, P1)
# ==============================================================================


def _pivot_typ(hi: np.ndarray, lo: np.ndarray, m: int) -> Optional[Literal["H", "L"]]:
    """Kausale Pivot-Pruefung fuer Bar m (Daten bis m+2 bekannt).

    H: high[m] strikt groesser als high[m-2], high[m-1], high[m+1], high[m+2].
    L: low[m]  strikt kleiner  als low[m-2],  low[m-1],  low[m+1],  low[m+2].
    Randfall H==L gleichzeitig (extreme Umkehrbar): H gewinnt (P1).

    Args:
        hi: high-Array.
        lo: low-Array.
        m: Kandidaten-Bar (m >= 2, m+2 <= len-1).

    Returns:
        "H", "L" oder None (kein Pivot).
    """
    if hi[m] > hi[m - 1] and hi[m] > hi[m - 2] and hi[m] > hi[m + 1] and hi[m] > hi[m + 2]:
        return "H"
    if lo[m] < lo[m - 1] and lo[m] < lo[m - 2] and lo[m] < lo[m + 1] and lo[m] < lo[m + 2]:
        return "L"
    return None


# ==============================================================================
# KANTEN-VERWALTUNG (KantenSpeicher / KantenBalancierung / SwingFilter)
# ==============================================================================


def _update_balance(kante: _Kante) -> None:
    """Balance = VWAP ueber Touches im +/-DENSITY_BAND der alten Balance (P4).

    volumen_im_band = Summe der tick_volume dieser Touches. Fallback auf alle
    Touches, falls durch Balance-Drift keiner mehr im Band liegt.
    """
    bal = kante.balance_preis
    relevante = [t for t in kante.touche if abs(t.preis - bal) <= DENSITY_BAND]
    if not relevante:
        relevante = list(kante.touche)
    v_sum = sum(t.volumen for t in relevante)
    if v_sum > 0:
        kante.balance_preis = float(sum(t.preis * t.volumen for t in relevante) / v_sum)
    else:
        kante.balance_preis = float(sum(t.preis for t in relevante) / len(relevante))
    kante.volumen_im_band = float(v_sum)


def _finde_kante_im_band(
    kanten: Dict[int, _Kante], seite: KantenSeite, preis: float,
    nutze_anker: bool = False,
) -> Optional[_Kante]:
    """Kante der Seite mit geringster |preis - referenz| <= DENSITY_BAND (P3).

    Modus A: Referenz = balance_preis. Modus B: Referenz = anker_extremum.
    """
    best: Optional[_Kante] = None
    best_dist = float("inf")
    for k2 in kanten.values():
        if k2.seite != seite or k2.zustand == "VERFALLEN":
            continue
        ref = _ref_preis(k2, nutze_anker)
        dist = abs(preis - ref)
        if dist <= DENSITY_BAND and dist < best_dist:
            best, best_dist = k2, dist
    return best


def _verarbeite_pivot(
    m: int,
    typ: Literal["H", "L"],
    hi: np.ndarray,
    lo: np.ndarray,
    vol: np.ndarray,
    ts_vals: np.ndarray,
    kanten: Dict[int, _Kante],
    last_ref: Dict[str, Dict],
) -> None:
    """SwingFilter + Touch-Zuordnung/Geburt fuer einen bestaetigten Pivot (P2/P3).

    Args:
        m: Pivot-Bar (bestätigt ab m+2, Daten bis m+2 vorhanden).
        typ: "H" (obere Kante) oder "L" (untere Kante).
        hi/lo/vol/ts_vals: Arrays des Fensters.
        kanten: Kanten-Speicher (Mutation).
        last_ref: Referenz-Pivots {"H": {...}, "L": {...}} je Gegenseite
            (Mutation: bar/preis/kanten_ereignis).
    """
    seite: KantenSeite = "OBEN" if typ == "H" else "UNTEN"
    preis = float(hi[m]) if typ == "H" else float(lo[m])
    volumen = float(vol[m])
    ref = last_ref["L" if typ == "H" else "H"]  # letzter gegensaetzlicher Pivot

    if ref["bar"] < 0:
        amp = float("inf")
        herkunft = False
    else:
        amp = abs(preis - ref["preis"]) / ref["preis"] * 100.0
        herkunft = bool(ref["kanten_ereignis"])

    # Fall (d): Zwischenwelle (keine Amplitude, kein Gegenkanten-Ursprung)
    if ref["bar"] >= 0 and amp < MIN_SWING_PCT and not herkunft:
        ref_typ = "H" if typ == "H" else "L"
        last_ref[ref_typ] = {"bar": m, "preis": preis, "kanten_ereignis": False}
        return

    touch = _KantenTouch(
        pivot_bar=m,
        ts=pd.Timestamp(ts_vals[m]),
        preis=preis,
        volumen=volumen,
        gueltig_ab_bar=m + PIVOT_LOOKBACK,
        amplitude_pct=amp,
        gegenkanten_ursprung=herkunft,
    )

    kante = _finde_kante_im_band(kanten, seite, preis)
    if kante is not None:
        # Touch an bestehender Kante (Reaktivierung bei SCHLAFEND)
        kante.zustand = "AKTIV"
        kante.touche.append(touch)
        kante.letzter_touch_bar = m
        kante.letzter_touch_ts = pd.Timestamp(ts_vals[m])
        _update_balance(kante)
        ereignis = True
    elif amp >= MIN_SWING_PCT:
        # Fall (b) ohne Zuordnung: Geburt einer neuen Kante (Docht-Extremum)
        neue_id = max(kanten.keys(), default=-1) + 1
        kanten[neue_id] = _Kante(
            kanten_id=neue_id,
            seite=seite,
            geburts_bar=m,
            geburts_ts=pd.Timestamp(ts_vals[m]),
            basis_preis=preis,
            balance_preis=preis,
            volumen_im_band=volumen,
            touche=[touch],
            letzter_touch_bar=m,
            letzter_touch_ts=pd.Timestamp(ts_vals[m]),
        )
        ereignis = True
    else:
        # Fall (c): Gegenkanten-Ursprung, aber keine Kante im Band -> verworfen
        ereignis = False

    ref_typ = "H" if typ == "H" else "L"
    last_ref[ref_typ] = {"bar": m, "preis": preis, "kanten_ereignis": ereignis}


def _body_bruch(
    kanten: Dict[int, _Kante], k: int, op: np.ndarray, cl: np.ndarray,
    nutze_anker: bool = False,
) -> None:
    """2 konsekutive Koerper (k-1, k) jenseits der Kante -> SCHLAFEND.

    OBEN: min(open, close) > referenz; UNTEN: max(open, close) < referenz.
    Modus A: referenz = balance_preis; Modus B: referenz = anker_extremum.
    Stateless gegen die aktuelle Referenz (nach Touch-Updates von Iteration k).
    """
    if k < 1:
        return
    for kante in kanten.values():
        if kante.zustand != "AKTIV":
            continue
        ref = _ref_preis(kante, nutze_anker)
        if kante.seite == "OBEN":
            if min(op[k - 1], cl[k - 1]) > ref and min(op[k], cl[k]) > ref:
                kante.zustand = "SCHLAFEND"
        else:
            if max(op[k - 1], cl[k - 1]) < ref and max(op[k], cl[k]) < ref:
                kante.zustand = "SCHLAFEND"


def _verfall(kanten: Dict[int, _Kante], ts_k: pd.Timestamp, max_tage: int) -> None:
    """Rollierende Lebensdauer: > max_tage Kalendertage ohne Touch -> VERFALLEN."""
    if max_tage <= 0:
        return
    grenze = pd.Timedelta(days=max_tage)
    for kante in kanten.values():
        if kante.zustand == "VERFALLEN" or kante.letzter_touch_ts is None:
            continue
        if ts_k - kante.letzter_touch_ts > grenze:
            kante.zustand = "VERFALLEN"


# ==============================================================================
# SIGNAL-SCAN (ReclaimEngine)
# ==============================================================================


def _waehle_einstiegskante(
    kanten: Dict[int, _Kante], richtung: SignalRichtung, sweep_preis: float
) -> Optional[_Kante]:
    """A5-Einstiegs-Kante: hoechste (SHORT) / tiefste (LONG) aktive Typ-B-Kante,
    deren Balance durchstochen wurde (balance < sweep_preis bzw. > sweep_preis)."""
    seite: KantenSeite = "OBEN" if richtung == "SHORT" else "UNTEN"
    best: Optional[_Kante] = None
    for k2 in kanten.values():
        if k2.seite != seite or not k2.ist_handelbar:
            continue
        if richtung == "SHORT":
            if k2.balance_preis < sweep_preis and (
                best is None or k2.balance_preis > best.balance_preis
            ):
                best = k2
        else:
            if k2.balance_preis > sweep_preis and (
                best is None or k2.balance_preis < best.balance_preis
            ):
                best = k2
    return best


def _loese_trade(
    hi: np.ndarray,
    lo: np.ndarray,
    cl: np.ndarray,
    e_bar: int,
    entry: float,
    richtung: SignalRichtung,
    sl: float,
    tp1: float,
    tp2: float,
) -> _TradeResult:
    """Aufloesung exakt in Baseline-_aufloesen-Semantik (P8, ohne Trailing).

    Zwei unabhaengige Haelften ab e_bar: Haelfte 1 (25%) bis TP1 oder SL,
    Haelfte 2 (75%) bis TP2 oder SL; offen am Fensterende -> close[-1] (ENDE).
    """
    n = len(hi)
    risk = abs(sl - entry)
    if risk <= 0:
        risk = 1e-9
    hh = hi[e_bar:]
    ll = lo[e_bar:]
    cc = cl[e_bar:]
    nb = len(hh)

    def _first(mask: np.ndarray) -> int:
        return int(np.argmax(mask)) if mask.any() else nb

    if richtung == "SHORT":
        t1 = _first(ll <= tp1)
        t2 = _first(ll <= tp2)
        t_sl = _first(hh >= sl)
    else:
        t1 = _first(hh >= tp1)
        t2 = _first(hh >= tp2)
        t_sl = _first(ll <= sl)

    def _r(px: float) -> float:
        if richtung == "SHORT":
            return (entry - px) / risk
        return (px - entry) / risk

    # Haelfte 1: TP1 (25%)
    if t1 < t_sl:
        r1, ex1, g1, ex1_bar = _r(tp1), tp1, "TP1", e_bar + t1
    elif t_sl < t1:
        r1, ex1, g1, ex1_bar = -1.0, float(sl), "SL", e_bar + t_sl
    elif t_sl < nb:
        r1, ex1, g1, ex1_bar = -1.0, float(sl), "SL", e_bar + t_sl
    else:
        r1, ex1, g1, ex1_bar = _r(float(cc[-1])), float(cc[-1]), "ENDE", e_bar + nb - 1
    # Haelfte 2: TP2 (75%)
    if t2 < t_sl:
        r2, ex2, g2, ex2_bar = _r(tp2), tp2, "TP2", e_bar + t2
    elif t_sl < nb:
        r2, ex2, g2, ex2_bar = -1.0, float(sl), "SL", e_bar + t_sl
    else:
        r2, ex2, g2, ex2_bar = _r(float(cc[-1])), float(cc[-1]), "ENDE", e_bar + nb - 1

    w1 = ANTEIL_TP1 / 100.0
    w2 = 1.0 - w1
    rm = w1 * r1 + w2 * r2
    resultat: Literal["GEWONNEN", "VERLOREN", "NEUTRAL"] = (
        "GEWONNEN" if rm > 1e-9 else ("VERLOREN" if rm < -1e-9 else "NEUTRAL")
    )
    return _TradeResult(r_mult=rm, resultat=resultat, grund1=g1, grund2=g2,
                        exit1=ex1, exit2=ex2,
                        r1=r1, r2=r2, exit1_bar=ex1_bar, exit2_bar=ex2_bar)


def _pruefe_und_erzeuge(
    d: pd.DataFrame,
    kanten: Dict[int, _Kante],
    k: int,
    kante: _Kante,
    richtung: SignalRichtung,
    sweep_bar: int,
    cfg: HarnessKonfiguration,
    ablehnung: Optional[Dict[str, int]] = None,
) -> Optional[_Signal]:
    """Gates (Cooldown, Gegenkante+Spread, POC-Seite+CRV) und Signal-Erzeugung.

    Entry = open[k+1]. Gegenkante = aktive Typ-B-Kante der Gegenseite mit
    geringster Balance-Distanz (Praezisierung 2); Abstand >= min_spread_pct.
    TP1 = POC = kombinierter Kanten-VWAP beider Korridor-Kanten (Praezisierung 1);
    TP2 = Gegenkanten-Balance +/- Innen-Puffer (SHORT: b_gegen*1.002,
    LONG: b_gegen*0.998). Cooldown wird erst NACH allen Gates gesetzt (P7).

    Args:
        d: Fenster-DataFrame.
        kanten: Kanten-Speicher.
        k: Entscheidungs-Bar.
        kante: Einstiegs-Kante.
        richtung: SHORT/LONG.
        sweep_bar: Sweep-Bar (k bei in_bar, k-1 bei next_bar).
        cfg: Harness-Konfiguration.
        ablehnung: Optionales Zaehler-Dict fuer Ablehnungsgruende (Diagnose).

    Returns:
        _Signal oder None (Gate abgelehnt).
    """
    n = len(d)

    def _z(grund: str) -> None:
        if ablehnung is not None:
            ablehnung[grund] = ablehnung.get(grund, 0) + 1

    if k >= n - 1:
        _z("kein_platz")
        return None  # kein Platz fuer Entry open[k+1]
    if k < kante.cooldown_bis_bar:
        _z("cooldown")
        return None
    entry_bar = k + 1
    entry = float(d["open"].iloc[entry_bar])
    bal = kante.balance_preis

    gegen_seite: KantenSeite = "UNTEN" if richtung == "SHORT" else "OBEN"
    gegen: Optional[_Kante] = None
    gegen_dist = float("inf")
    for k2 in kanten.values():
        if k2.seite != gegen_seite or not k2.ist_handelbar:
            continue
        dist = abs(bal - k2.balance_preis) / k2.balance_preis * 100.0
        if dist < gegen_dist:
            gegen, gegen_dist = k2, dist
    if gegen is None:
        _z("keine_gegenkante")
        return None
    if gegen_dist < cfg.min_spread_pct:
        _z("spread_zu_eng")
        return None

    v_ein = kante.volumen_im_band
    v_geg = gegen.volumen_im_band
    v_sum = v_ein + v_geg
    if v_sum > 0:
        poc = (bal * v_ein + gegen.balance_preis * v_geg) / v_sum
    else:
        poc = (bal + gegen.balance_preis) / 2.0

    risk_pct = cfg.sl_pct / 100.0
    if richtung == "SHORT":
        sl = entry * (1.0 + risk_pct)
        tp2 = gegen.balance_preis * (1.0 + cfg.tp2_puffer_pct / 100.0)
        if not (entry > poc):
            _z("poc_seite")
            return None
        crv = (entry - poc) / (entry * risk_pct)
    else:
        sl = entry * (1.0 - risk_pct)
        tp2 = gegen.balance_preis * (1.0 - cfg.tp2_puffer_pct / 100.0)
        if not (entry < poc):
            _z("poc_seite")
            return None
        crv = (poc - entry) / (entry * risk_pct)
    if crv < cfg.crv_min_tp1:
        _z("crv")
        return None

    # Alle Gates bestanden -> Signal (Cooldown je Kante setzen)
    kante.cooldown_bis_bar = k + COOLDOWN_BARS
    trade = _loese_trade(
        d["high"].to_numpy(dtype=float),
        d["low"].to_numpy(dtype=float),
        d["close"].to_numpy(dtype=float),
        entry_bar, entry, richtung, sl, poc, tp2,
    )
    semantik: SignalSemantik = "next_bar" if sweep_bar < k else "in_bar"
    return _Signal(
        signal_bar=k,
        sweep_bar=sweep_bar,
        ts=pd.Timestamp(d["ts"].iloc[k]),
        richtung=richtung,
        semantik=semantik,
        kanten_id=kante.kanten_id,
        kanten_id_gegen=gegen.kanten_id,
        kanten_alter_bars=k - kante.geburts_bar,
        kanten_touch_anzahl=kante.touch_anzahl,
        entry_bar=entry_bar,
        entry_preis=entry,
        sl_preis=sl,
        tp1_poc_preis=poc,
        tp2_preis=tp2,
        crv_tp1=crv,
        spread_pct=gegen_dist,
        trade=trade,
    )


# ==============================================================================
# MODUS B / V2 (Spez §4.1/§5.1/§6.1, Commit f75f6d0) -- isolierter Block.
# Modus-A-Pfad bleibt oben unveraendert (Regressions-Anker §8.3).
# ==============================================================================


def _b_ratchet_erlaubt(kante: _Kante, preis: float, tol_pct: float) -> bool:
    """Admission (Ratchet, §4.1): Pivot muss am/ausserhalb des Extremums liegen.

    OBEN: preis >= anker*(1 - tol) ; UNTEN: preis <= anker*(1 + tol).
    Innen-Pivots (unterhalb der Toleranz) werden verworfen: kein Touch, kein
    Lebensdauer-Reset, keine Reaktivierung.
    """
    a = kante.anker_extremum
    if a <= 0.0:
        return True
    tol = a * tol_pct / 100.0
    if kante.seite == "OBEN":
        return preis >= a - tol
    return preis <= a + tol


def _b_update_balance_vwap(kante: _Kante) -> None:
    """Modus B: balance_preis = VWAP ueber ALLE akzeptierten Touches (§4.1)."""
    v = [t.volumen for t in kante.touche]
    s = sum(v)
    if s > 0:
        kante.balance_preis = float(
            sum(t.preis * t.volumen for t in kante.touche) / s)
    else:
        kante.balance_preis = float(
            sum(t.preis for t in kante.touche) / len(kante.touche))
    kante.volumen_im_band = float(s)


def _b_finde_merkposten(
    merkposten: List["_ZonenMerkposten"], seite: KantenSeite, preis: float,
    m: int, cfg: HarnessKonfiguration,
) -> Optional["_ZonenMerkposten"]:
    """Naechster offener Merkposten gleicher Seite (Distanz + Grace, §4.1)."""
    best: Optional[_ZonenMerkposten] = None
    best_dist = float("inf")
    for seed in merkposten:
        if seed.seite != seite:
            continue
        if seed.ist_abgelaufen(m, cfg.grace_periode_bars):
            continue
        dist = abs(preis - seed.anker_extremum)
        if dist <= cfg.cluster_distanz_usd and dist < best_dist:
            best, best_dist = seed, dist
    return best


def _b_kante_geburt(
    kanten: Dict[int, _Kante], m: int, ts_vals: np.ndarray,
    seite: KantenSeite, anker: float, vol: np.ndarray,
    retests: Optional[List[Tuple[int, float, float, float, bool]]] = None,
) -> int:
    """Erzeugt eine Modus-B-Kante (anker = Extremum; balance_preis = VWAP).

    retests = Liste (bar, preis, volumen, amp, herkunft) bei Cluster-Geburt
    (§4.1); None = Swing-Geburt (ein Touch, Geburt am Docht-Extremum).
    """
    neue_id = max(kanten.keys(), default=-1) + 1
    if retests is None:
        liste: List[Tuple[int, float, float, float, bool]] = [
            (m, anker, float(vol[m]), 0.0, False)]
    else:
        liste = retests
    touche: List[_KantenTouch] = []
    for (b_, p_, v_, amp_, herk_) in liste:
        touche.append(_KantenTouch(
            pivot_bar=b_,
            ts=pd.Timestamp(ts_vals[b_]),
            preis=p_,
            volumen=v_,
            gueltig_ab_bar=b_ + PIVOT_LOOKBACK,
            amplitude_pct=amp_,
            gegenkanten_ursprung=herk_,
        ))
    v_sum = sum(t.volumen for t in touche)
    balance = (float(sum(t.preis * t.volumen for t in touche) / v_sum)
               if v_sum > 0 else anker)
    letzte_bar = int(liste[-1][0])
    kanten[neue_id] = _Kante(
        kanten_id=neue_id,
        seite=seite,
        geburts_bar=letzte_bar,
        geburts_ts=pd.Timestamp(ts_vals[letzte_bar]),
        basis_preis=anker,
        balance_preis=balance,
        volumen_im_band=float(v_sum),
        touche=touche,
        letzter_touch_bar=letzte_bar,
        letzter_touch_ts=pd.Timestamp(ts_vals[letzte_bar]),
        anker_extremum=anker,
    )
    return neue_id


def _b_verarbeite_pivot(
    m: int,
    typ: Literal["H", "L"],
    hi: np.ndarray,
    lo: np.ndarray,
    vol: np.ndarray,
    ts_vals: np.ndarray,
    kanten: Dict[int, _Kante],
    merkposten: List["_ZonenMerkposten"],
    last_ref: Dict[str, Dict],
    cfg: HarnessKonfiguration,
    stat: Dict[str, int],
    diagnose: List[str],
) -> None:
    """Modus-B-Pipeline (§4.1): 1 Ratchet+Touch-Mapping -> 2 Cluster ->
    3 Swing-Geburt/neuer Merkposten. Touch-Zuordnung VOR SwingFilter."""
    seite: KantenSeite = "OBEN" if typ == "H" else "UNTEN"
    preis = float(hi[m]) if typ == "H" else float(lo[m])
    volumen = float(vol[m])
    ref = last_ref["L" if typ == "H" else "H"]
    if ref["bar"] < 0:
        amp = float("inf")
        herkunft = False
    else:
        amp = abs(preis - ref["preis"]) / ref["preis"] * 100.0
        herkunft = bool(ref["kanten_ereignis"])
    ref_typ = "H" if typ == "H" else "L"
    ts_m = pd.Timestamp(ts_vals[m])

    # --- 1) Ratchet-Admission + Touch-Mapping an existierende Kante ---------
    kante = _finde_kante_im_band(kanten, seite, preis, nutze_anker=True)
    if kante is not None:
        if not _b_ratchet_erlaubt(kante, preis, cfg.toleranz_ratchet_pct):
            stat["ratchet_abgelehnt"] = stat.get("ratchet_abgelehnt", 0) + 1
            if len(diagnose) < 600:
                diagnose.append(
                    f"{ts_m:%m-%d %H:%M} ABGELEHNT_RATCHET_INNEN bar {m:4d} "
                    f"{seite} p={preis:8.3f} anker={kante.anker_extremum:8.3f}")
            last_ref[ref_typ] = {"bar": m, "preis": preis,
                                 "kanten_ereignis": False}
            return
        # Admission bestanden -> Touch (reaktiviert SCHLAFEND mit)
        kante.zustand = "AKTIV"
        kante.touche.append(_KantenTouch(
            pivot_bar=m, ts=ts_m, preis=preis, volumen=volumen,
            gueltig_ab_bar=m + PIVOT_LOOKBACK, amplitude_pct=amp,
            gegenkanten_ursprung=herkunft,
        ))
        kante.letzter_touch_bar = m
        kante.letzter_touch_ts = ts_m
        if seite == "OBEN":
            kante.anker_extremum = max(kante.anker_extremum, preis)
        else:
            kante.anker_extremum = min(kante.anker_extremum, preis)
        _b_update_balance_vwap(kante)
        stat["touches"] = stat.get("touches", 0) + 1
        last_ref[ref_typ] = {"bar": m, "preis": preis, "kanten_ereignis": True}
        return

    # --- 2) Cluster-Merkposten (herrenlose Zone) -----------------------------
    seed = _b_finde_merkposten(merkposten, seite, preis, m, cfg)
    if seed is not None and not seed.schwung_ok(
            m, hi, lo, cfg.max_zwischenschwung_pct):
        merkposten.remove(seed)
        stat["merkposten_verfallen_schwung"] = stat.get(
            "merkposten_verfallen_schwung", 0) + 1
        if len(diagnose) < 600:
            diagnose.append(
                f"{ts_m:%m-%d %H:%M} MERKPOSTEN_VERFALLEN_SCHWUNG bar {m:4d} "
                f"{seite} seed_anker={seed.anker_extremum:8.3f}")
        seed = None
    if seed is not None:
        seed.retest_bars.append(m)
        seed.retest_preise.append(preis)
        seed.retest_volumina.append(volumen)
        seed.retest_amps.append(amp)
        seed.retest_herkunft.append(herkunft)
        if seite == "OBEN":
            seed.anker_extremum = max(seed.anker_extremum, preis)
        else:
            seed.anker_extremum = min(seed.anker_extremum, preis)
        seed.letzter_bar = m
        if len(seed.retest_bars) >= 2:
            retests = list(zip(
                seed.retest_bars, seed.retest_preise, seed.retest_volumina,
                seed.retest_amps, seed.retest_herkunft))
            kid = _b_kante_geburt(
                kanten, m, ts_vals, seite, seed.anker_extremum, vol, retests)
            stat["cluster_geburten"] = stat.get("cluster_geburten", 0) + 1
            if len(diagnose) < 600:
                diagnose.append(
                    f"{ts_m:%m-%d %H:%M} MERKPOSTEN_BESTAETIGT->GEBURT bar {m:4d} "
                    f"{seite} K{kid:2d} anker={seed.anker_extremum:8.3f} "
                    f"retests={len(seed.retest_bars)}")
            merkposten.remove(seed)
        last_ref[ref_typ] = {"bar": m, "preis": preis,
                             "kanten_ereignis": True}
        return

    # --- 3) Swing-Geburt / neuer Merkposten (SwingFilter nur hier) ----------
    if ref["bar"] >= 0 and amp < MIN_SWING_PCT:
        if herkunft:
            seed2 = _ZonenMerkposten(seite=seite, erst_bar=m, letzter_bar=m,
                                     anker_extremum=preis)
            seed2.retest_bars = [m]
            seed2.retest_preise = [preis]
            seed2.retest_volumina = [volumen]
            seed2.retest_amps = [amp]
            seed2.retest_herkunft = [herkunft]
            merkposten.append(seed2)
            stat["neue_merkposten"] = stat.get("neue_merkposten", 0) + 1
            if len(diagnose) < 600:
                diagnose.append(
                    f"{ts_m:%m-%d %H:%M} NEUER_MERKPOSTEN bar {m:4d} {seite} "
                    f"anker={preis:8.3f}")
            ereignis = True
        else:
            ereignis = False
    else:
        kid = _b_kante_geburt(kanten, m, ts_vals, seite, preis, vol, None)
        stat["swing_geburten"] = stat.get("swing_geburten", 0) + 1
        if len(diagnose) < 600:
            diagnose.append(
                f"{ts_m:%m-%d %H:%M} KANTEN_GEBURT_SWING bar {m:4d} {seite} "
                f"K{kid:2d} anker={preis:8.3f}")
        ereignis = True
    last_ref[ref_typ] = {"bar": m, "preis": preis, "kanten_ereignis": ereignis}


def _b_body_reclaim(kanten: Dict[int, _Kante], k: int,
                    cl: np.ndarray) -> int:
    """SCHLAFEND -> AKTIV per Close-Reclaim ohne Docht-Zwang (§4.1/§6.1).

    OBEN (gebrochen nach oben): close[k] < anker; UNTEN: close[k] > anker.
    Eine Kerze genuegt (Kante war bereits Typ-B-etabliert).
    """
    n = 0
    for kante in kanten.values():
        if kante.zustand != "SCHLAFEND":
            continue
        a = kante.anker_extremum
        if a <= 0.0:
            continue
        if kante.seite == "OBEN" and cl[k] < a:
            kante.zustand = "AKTIV"
            n += 1
        elif kante.seite == "UNTEN" and cl[k] > a:
            kante.zustand = "AKTIV"
            n += 1
    return n


def _b_waehle_einstiegskante(
    kanten: Dict[int, _Kante], richtung: SignalRichtung, sweep_preis: float
) -> Optional[_Kante]:
    """A5-Einstiegs-Kante (Modus B): aussenste aktive Typ-B-Kante, deren
    anker_extremum durchstochen wurde (anker < high[k] bzw. > low[k])."""
    seite: KantenSeite = "OBEN" if richtung == "SHORT" else "UNTEN"
    best: Optional[_Kante] = None
    best_ref = 0.0
    for k2 in kanten.values():
        if k2.seite != seite or not k2.ist_handelbar:
            continue
        a = k2.anker_extremum
        if a <= 0.0:
            continue
        if richtung == "SHORT":
            if a < sweep_preis and (best is None or a > best_ref):
                best, best_ref = k2, a
        else:
            if a > sweep_preis and (best is None or a < best_ref):
                best, best_ref = k2, a
    return best


def _b_pruefe_und_erzeuge(
    d: pd.DataFrame,
    kanten: Dict[int, _Kante],
    k: int,
    kante: _Kante,
    richtung: SignalRichtung,
    sweep_bar: int,
    cfg: HarnessKonfiguration,
    ablehnung: Optional[Dict[str, int]] = None,
) -> Optional[_Signal]:
    """Gates + Signal-Erzeugung (Modus B, §6.1).

    Referenz = anker_extremum. TP1 = balance_preis der Einstiegs-Kante
    (Richtwert). TP2 = Gegenkanten-balance +/- Innen-Puffer (wie V1).
    KEIN crv/poc_seite-Gate in Modus B (crv wird nur berichtet).
    """
    n = len(d)

    def _z(grund: str) -> None:
        if ablehnung is not None:
            ablehnung[grund] = ablehnung.get(grund, 0) + 1

    if k >= n - 1:
        _z("kein_platz")
        return None
    if k < kante.cooldown_bis_bar:
        _z("cooldown")
        return None
    entry_bar = k + 1
    entry = float(d["open"].iloc[entry_bar])
    a = kante.anker_extremum
    if a <= 0.0:
        _z("kein_anker")
        return None

    gegen_seite: KantenSeite = "UNTEN" if richtung == "SHORT" else "OBEN"
    gegen: Optional[_Kante] = None
    gegen_dist = float("inf")
    for k2 in kanten.values():
        if k2.seite != gegen_seite or not k2.ist_handelbar:
            continue
        a2 = k2.anker_extremum
        if a2 <= 0.0:
            continue
        dist = abs(a - a2) / a2 * 100.0
        if dist < gegen_dist:
            gegen, gegen_dist = k2, dist
    if gegen is None:
        _z("keine_gegenkante")
        return None
    if gegen_dist < cfg.min_spread_pct:
        _z("spread_zu_eng")
        return None

    risk_pct = cfg.sl_pct / 100.0
    tp1 = kante.balance_preis  # TP1-Richtwert (balance_vwap)
    if richtung == "SHORT":
        sl = entry * (1.0 + risk_pct)
        tp2 = gegen.balance_preis * (1.0 + cfg.tp2_puffer_pct / 100.0)
        crv = (entry - tp1) / (entry * risk_pct)
    else:
        sl = entry * (1.0 - risk_pct)
        tp2 = gegen.balance_preis * (1.0 - cfg.tp2_puffer_pct / 100.0)
        crv = (tp1 - entry) / (entry * risk_pct)

    kante.cooldown_bis_bar = k + COOLDOWN_BARS
    trade = _loese_trade(
        d["high"].to_numpy(dtype=float),
        d["low"].to_numpy(dtype=float),
        d["close"].to_numpy(dtype=float),
        entry_bar, entry, richtung, sl, tp1, tp2,
    )
    semantik: SignalSemantik = "next_bar" if sweep_bar < k else "in_bar"
    return _Signal(
        signal_bar=k,
        sweep_bar=sweep_bar,
        ts=pd.Timestamp(d["ts"].iloc[k]),
        richtung=richtung,
        semantik=semantik,
        kanten_id=kante.kanten_id,
        kanten_id_gegen=gegen.kanten_id,
        kanten_alter_bars=k - kante.geburts_bar,
        kanten_touch_anzahl=kante.touch_anzahl,
        entry_bar=entry_bar,
        entry_preis=entry,
        sl_preis=sl,
        tp1_poc_preis=tp1,
        tp2_preis=tp2,
        crv_tp1=crv,
        spread_pct=gegen_dist,
        trade=trade,
    )


# ==============================================================================
# MODUS C / V3 (Spez §7.1/§8.4, arretiert 2026-09-08) -- isolierter Block.
# A/B-Pfade bleiben oben unveraendert (Regressions-Anker §8.3).
# ==============================================================================


def _pivot_dual(hi: np.ndarray, lo: np.ndarray,
                m: int) -> List[Literal["H", "L"]]:
    """F1-Doppel-Pivot (arretiert): H und L unabhaengig pruefen.

    H==L-Umkehrbar (z. B. Bar 386 am 14.08.) liefert ["H", "L"] (beidseitig).
    Die A/B-P1-Regel "H gewinnt bei H==L" bleibt fuer A/B unangetastet.
    """
    out: List[Literal["H", "L"]] = []
    if (hi[m] > hi[m - 1] and hi[m] > hi[m - 2]
            and hi[m] > hi[m + 1] and hi[m] > hi[m + 2]):
        out.append("H")
    if (lo[m] < lo[m - 1] and lo[m] < lo[m - 2]
            and lo[m] < lo[m + 1] and lo[m] < lo[m + 2]):
        out.append("L")
    return out


def _c_dominante(kandidaten: List[StatischeKanteC],
                 seite: KantenSeite) -> StatischeKanteC:
    """U1-Dominanz-Matching: hoechste touch_anzahl, Tie-Break aeusseres Extrem."""
    vergleich = KantenDominanzVergleich(seite)
    best = kandidaten[0]
    for k2 in kandidaten[1:]:
        w = vergleich.waehle_dominante_kante(
            k2.basis_preis, k2.touch_anzahl,
            best.basis_preis, best.touch_anzahl,
        )
        if w == "A":
            best = k2
    return best


def _c_verarbeite_pivot(
    m: int,
    typ: Literal["H", "L"],
    hi: np.ndarray,
    lo: np.ndarray,
    kanten: Dict[int, StatischeKanteC],
    cfg: ModusCKonfiguration,
    regeln: AsymmetrischeGeneseRegeln,
    ablehnung: Dict[str, int],
) -> None:
    """V3-Genese (Spez §7.1 F): Touch-Matching (U1-Dominanz) -> asym. Geburt.

    Ein bestaetigter Pivot-Docht im 0,23-%-Band einer Kante gleicher Seite ist
    ein Touch an der dominanten Kante (Mindestabstand 3, Reaktivierung
    SCHLAFEND->AKTIV). Ohne Band-Kandidat: asymmetrische Geburts-Sperre -
    innerer Pivot im 0,50-%-Nahbereich = Zwischenwelle (Ring, verworfen);
    aeusseres Extrem / ausserhalb 0,50 % = Geburt (Geburts-Touch).
    """
    seite: KantenSeite = "OBEN" if typ == "H" else "UNTEN"
    preis = float(hi[m]) if typ == "H" else float(lo[m])

    def _z(grund: str) -> None:
        ablehnung[grund] = ablehnung.get(grund, 0) + 1

    kandidaten = [k2 for k2 in kanten.values()
                  if k2.seite == seite and k2.ist_im_touch_band(preis, cfg)]
    if kandidaten:
        gewinner = _c_dominante(kandidaten, seite)
        if m - gewinner.letzter_touch_bar >= regeln.min_bar_abstand:
            gewinner.touch_bars.append(m)
            gewinner.letzter_touch_bar = m
            if gewinner.status == "SCHLAFEND":
                gewinner.status = "AKTIV"
            gewinner.outside_body_count = 0
        else:
            _z("band_abstand_verworfen")   # gleiche Bewegung (kein Touch/Geburt)
        return
    if darf_kante_geboren_werden(seite, preis, list(kanten.values()), regeln):
        neue_id = max(kanten.keys(), default=-1) + 1
        kanten[neue_id] = StatischeKanteC(
            kanten_id=neue_id,
            seite=seite,
            basis_preis=preis,
            geburts_bar=m,
            letzter_touch_bar=m,
            touch_bars=[m],
        )
    else:
        _z("ring_zwischenwelle")   # 0,23-0,50-%-Ring: weder Touch noch Geburt


def _c_aktualisiere_zustaende(kanten: Dict[int, StatischeKanteC], k: int,
                              op: np.ndarray, cl: np.ndarray) -> None:
    """2-Body-Bruch gegen das FIXE basis_preis (Spez §7.1 A).

    Zwei konsekutive Kerzenkoerper (k-1, k) vollstaendig jenseits basis ->
    SCHLAFEND. Kein Zeitverfall; Reaktivierung nur per Docht-Touch im Band.
    """
    if k < 1:
        return
    for k2 in kanten.values():
        if k2.seite == "OBEN":
            aussen = (min(op[k - 1], cl[k - 1]) > k2.basis_preis and
                      min(op[k], cl[k]) > k2.basis_preis)
        else:
            aussen = (max(op[k - 1], cl[k - 1]) < k2.basis_preis and
                      max(op[k], cl[k]) < k2.basis_preis)
        if aussen:
            k2.outside_body_count = 2
            if k2.status == "AKTIV":
                k2.status = "SCHLAFEND"
        else:
            k2.outside_body_count = 0


def _c_waehle_einstiegskante(
    kanten: Dict[int, StatischeKanteC], richtung: SignalRichtung,
    sweep_preis: float,
) -> Optional[StatischeKanteC]:
    """Einstiegs-Kante (V3): beste AKTIVE Typ-B-Kante, deren basis durchstochen.

    SHORT: hoechste OBEN-Basis < high[k]; LONG: tiefste UNTEN-Basis > low[k].
    Nur der echte Docht-Durchstich zaehlt (F2) - kein blosser Bandkontakt.
    """
    seite: KantenSeite = "OBEN" if richtung == "SHORT" else "UNTEN"
    best: Optional[StatischeKanteC] = None
    for k2 in kanten.values():
        if k2.seite != seite or not k2.ist_handelbar_typ_b:
            continue
        if richtung == "SHORT":
            if k2.basis_preis < sweep_preis and (
                    best is None or k2.basis_preis > best.basis_preis):
                best = k2
        else:
            if k2.basis_preis > sweep_preis and (
                    best is None or k2.basis_preis < best.basis_preis):
                best = k2
    return best


def _c_waehle_kursziele(
    kanten: Dict[int, StatischeKanteC], richtung: SignalRichtung,
    basis_ein: float, cfg: ModusCKonfiguration,
) -> Tuple[Optional[float], Optional[float], float]:
    """Passive Gegenkanten (Spez §7.1 C/D): >= 2 Touches, Raum >= tp_mindist.

    Distanz Basis-zu-Basis relativ zur Einstiegs-Basis (konsistent zu den
    Spez-Beispielen 66.46 -> 64.20 = 3,4 %). TP1 = naechstgelegene Kante,
    TP2 = dahinterliegende (SHORT: absteigende Basis; LONG: aufsteigende).
    SCHLAFEND vollwertig zulaessig; AKTIV-vor-SCHLAFEND bei identischer Basis.
    Nur eine qualifizierte -> TP2 = None (100 % auf TP1); keine -> (None, None).
    """
    gegen_seite: KantenSeite = "UNTEN" if richtung == "SHORT" else "OBEN"
    qual: List[Tuple[float, int, float]] = []   # (distanz_pct, aktiv_prio, basis)
    for k2 in kanten.values():
        if k2.seite != gegen_seite or not k2.ist_gueltiges_kursziel_typ_a:
            continue
        basis = k2.basis_preis
        if richtung == "SHORT" and basis >= basis_ein:
            continue
        if richtung == "LONG" and basis <= basis_ein:
            continue
        dist = abs(basis_ein - basis) / basis_ein * 100.0
        if dist < cfg.tp_mindist_pct:
            continue
        aktiv_prio = 0 if k2.status == "AKTIV" else 1
        qual.append((dist, aktiv_prio, basis))
    if not qual:
        return None, None, 0.0
    # naechstgelegene zuerst; bei identischer Basis AKTIV vor SCHLAFEND
    if richtung == "SHORT":
        qual.sort(key=lambda q: (-q[2], q[1]))
    else:
        qual.sort(key=lambda q: (q[2], q[1]))
    tp1 = qual[0][2]
    tp2 = qual[1][2] if len(qual) >= 2 else None
    return tp1, tp2, qual[0][0]


def _c_loese_trade(
    hi: np.ndarray,
    lo: np.ndarray,
    cl: np.ndarray,
    e_bar: int,
    entry: float,
    richtung: SignalRichtung,
    sl: float,
    tp1: float,
    tp2: Optional[float],
    tp1_anteil_pct: float,
) -> _CTradeResult:
    """Zwei unabhaengige Haelften (tp1_anteil / Rest) gegen TP/SL (Spez §7.1 D).

    Haelfte 1 (Standard 50 %) bis TP1 oder SL; Haelfte 2 bis TP2 oder SL;
    tp2 = None -> beide Haelften auf TP1 (100 %-Fallback). Offene Haelften am
    Fensterende -> close[-1] (Grund ENDE). SL = struktureller Stop.
    """
    n = len(hi)
    risk = abs(sl - entry)
    if risk <= 0:
        risk = 1e-9
    hh = hi[e_bar:]
    ll = lo[e_bar:]
    cc = cl[e_bar:]
    nb = len(hh)

    def _first(mask: np.ndarray) -> int:
        return int(np.argmax(mask)) if mask.any() else nb

    ziel2 = tp2 if tp2 is not None else tp1
    grund2 = "TP2" if tp2 is not None else "TP1"
    if richtung == "SHORT":
        t1 = _first(ll <= tp1)
        t2 = _first(ll <= ziel2)
        t_sl = _first(hh >= sl)
    else:
        t1 = _first(hh >= tp1)
        t2 = _first(hh >= ziel2)
        t_sl = _first(ll <= sl)

    def _r(px: float) -> float:
        if richtung == "SHORT":
            return (entry - px) / risk
        return (px - entry) / risk

    # Haelfte 1 (tp1_anteil_pct %)
    if t1 < t_sl:
        r1, ex1, g1, ex1_bar = _r(tp1), tp1, "TP1", e_bar + t1
    elif t_sl < nb:
        r1, ex1, g1, ex1_bar = -1.0, float(sl), "SL", e_bar + t_sl
    else:
        r1, ex1, g1, ex1_bar = _r(float(cc[-1])), float(cc[-1]), "ENDE", e_bar + nb - 1
    # Haelfte 2 (Rest)
    if t2 < t_sl:
        r2, ex2, g2, ex2_bar = _r(ziel2), ziel2, grund2, e_bar + t2
    elif t_sl < nb:
        r2, ex2, g2, ex2_bar = -1.0, float(sl), "SL", e_bar + t_sl
    else:
        r2, ex2, g2, ex2_bar = _r(float(cc[-1])), float(cc[-1]), "ENDE", e_bar + nb - 1

    w1 = tp1_anteil_pct / 100.0
    w2 = 1.0 - w1
    rm = w1 * r1 + w2 * r2
    resultat: Literal["GEWONNEN", "VERLOREN", "NEUTRAL"] = (
        "GEWONNEN" if rm > 1e-9 else ("VERLOREN" if rm < -1e-9 else "NEUTRAL")
    )
    return _CTradeResult(r_mult=rm, resultat=resultat, grund1=g1, grund2=g2,
                         exit1=ex1, exit2=ex2,
                         r1=r1, r2=r2, exit1_bar=ex1_bar, exit2_bar=ex2_bar)


def _c_pruefe_und_erzeuge(
    hi: np.ndarray,
    lo: np.ndarray,
    cl: np.ndarray,
    op: np.ndarray,
    ts_vals: np.ndarray,
    kanten: Dict[int, StatischeKanteC],
    k: int,
    kante: StatischeKanteC,
    richtung: SignalRichtung,
    sweep_bar: int,
    cfg: ModusCKonfiguration,
    zustand: _CZustand,
    ablehnung: Optional[Dict[str, int]] = None,
) -> Optional[_CSignal]:
    """V3-Gates + Signal-Erzeugung (Spez §7.1 B/E).

    Entry = open[k+1]. SL strukturell = Sweep-Extremum +/- sl_buffer_usd.
    F3-Freigabe: neuester bestaetigter Touch mit pivot_bar > letzter_signal_bar
    UND max. 1 offene Position je Kante (kein Stacking). Kursziele nach C/D
    (>= 2 Touches, Distanz >= tp_mindist_pct, SCHLAFEND zulaessig).
    """
    n = len(hi)

    def _z(grund: str) -> None:
        if ablehnung is not None:
            ablehnung[grund] = ablehnung.get(grund, 0) + 1

    if k >= n - 1:
        _z("kein_platz")
        return None
    if not (kante.neuester_touch_bar > kante.letzter_signal_bar):
        _z("f3_kein_neuer_touch")
        return None
    if zustand.offen_bis.get(kante.kanten_id, -1) >= k + 1:
        _z("position_offen")
        return None

    entry_bar = k + 1
    entry = float(op[entry_bar])
    basis = kante.basis_preis
    if richtung == "SHORT":
        sweep_preis = float(hi[sweep_bar])
        sl = sweep_preis + cfg.sl_buffer_usd
        if not sl > entry:
            _z("sl_unmoeglich")
            return None
    else:
        sweep_preis = float(lo[sweep_bar])
        sl = sweep_preis - cfg.sl_buffer_usd
        if not sl < entry:
            _z("sl_unmoeglich")
            return None

    tp1, tp2, dist_gegen = _c_waehle_kursziele(kanten, richtung, basis, cfg)
    if tp1 is None:
        _z("kein_ziel_raum")
        return None

    trade = _c_loese_trade(hi, lo, cl, entry_bar, entry, richtung, sl, tp1,
                           tp2, cfg.tp1_anteil_pct)
    semantik: SignalSemantik = "next_bar" if sweep_bar < k else "in_bar"
    kante.letzter_signal_bar = k
    zustand.offen_bis[kante.kanten_id] = max(trade.exit1_bar, trade.exit2_bar)
    return _CSignal(
        signal_bar=k,
        sweep_bar=sweep_bar,
        ts=pd.Timestamp(ts_vals[k]),
        richtung=richtung,
        semantik=semantik,
        kanten_id=kante.kanten_id,
        basis_preis=basis,
        sweep_preis=sweep_preis,
        trigger_preis=float(cl[k]),
        entry_bar=entry_bar,
        entry_preis=entry,
        sl_preis=sl,
        tp1_preis=tp1,
        tp2_preis=tp2,
        dist_gegen_pct=dist_gegen,
        touch_anzahl=kante.touch_anzahl,
        trade=trade,
    )


def _replay_c(fenster: FensterTyp,
              cfg: ModusCKonfiguration) -> _ReplayErgebnisC:
    """V3-Einzellauf (Modus C, Spez §8.4): je Fenster genau 1 Durchlauf.

    Kausale Schleife (Entscheidungsstand nach close[k]):
      C1 Pivot m=k-2 (F1-Doppel-Pivot) -> Touch/Geburt (U1-Dominanz, Abstand 3)
      C2 2-Body-Bruch gegen fixes basis_preis (AKTIV -> SCHLAFEND)
      C3 in_bar-Scan (Docht-Durchstich + Reclaim-Close; F3-Freigabe)
      C4 next_bar (nur als separater Split, Sweep von k-1 reclaimt in k)
    Kein Zeitverfall, kein max_tage-Grid.
    """
    t0 = time.perf_counter()
    d = _lade_fenster(fenster)
    n = len(d)
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    op = d["open"].to_numpy(dtype=float)
    ts_vals = d["ts"].to_numpy()

    kanten: Dict[int, StatischeKanteC] = {}
    signale: List[_CSignal] = []
    pending: List[Tuple[int, SignalRichtung, int]] = []  # (sweep_bar, richtung, kid)
    zustand = _CZustand()
    ablehnung: Dict[str, int] = {}
    regeln = AsymmetrischeGeneseRegeln(
        touch_band_pct=cfg.touch_band_pct,
        geburts_sperr_pct=V3_GEBURTS_SPERR_PCT,
        min_bar_abstand=cfg.min_touch_bar_abstand,
    )
    sweeps_ohne_reclaim = 0
    nextbar_reclaim_ok = 0
    nextbar_abgelehnt = 0

    for k in range(n):
        # --- C1: Pivot von m = k-2 (2-Bar-Puffer, F1 dual) ---
        m = k - PIVOT_LOOKBACK
        if m >= 2:
            for typ in _pivot_dual(hi, lo, m):
                _c_verarbeite_pivot(m, typ, hi, lo, kanten, cfg, regeln,
                                    ablehnung)

        # --- C2: 2-Body-Bruch gegen fixes basis_preis ---
        _c_aktualisiere_zustaende(kanten, k, op, cl)

        if k > n - 2:
            continue  # kein Entry open[k+1] mehr moeglich

        # --- C3: in_bar-Scan (Sweep + Reclaim in Bar k) ---
        ks = _c_waehle_einstiegskante(kanten, "SHORT", hi[k])
        if ks is not None and cl[k] <= ks.basis_preis:
            sig = _c_pruefe_und_erzeuge(hi, lo, cl, op, ts_vals, kanten, k, ks,
                                        "SHORT", k, cfg, zustand, ablehnung)
            if sig is not None:
                signale.append(sig)
        kl_ = _c_waehle_einstiegskante(kanten, "LONG", lo[k])
        if kl_ is not None and cl[k] >= kl_.basis_preis:
            sig = _c_pruefe_und_erzeuge(hi, lo, cl, op, ts_vals, kanten, k, kl_,
                                        "LONG", k, cfg, zustand, ablehnung)
            if sig is not None:
                signale.append(sig)

        if not cfg.erlaube_next_bar:
            continue  # next_bar-Split deaktiviert (G2)

        # --- C4: next_bar-Abgleich (pending stammt von Bar k-1) ---
        for sweep_bar, richtung, kid in pending:
            kante = kanten.get(kid)
            if kante is None or not kante.ist_handelbar_typ_b:
                continue
            basis = kante.basis_preis
            if richtung == "SHORT":
                ok = hi[sweep_bar] > basis and cl[k] <= basis
            else:
                ok = lo[sweep_bar] < basis and cl[k] >= basis
            if ok:
                nextbar_reclaim_ok += 1
                sig = _c_pruefe_und_erzeuge(
                    hi, lo, cl, op, ts_vals, kanten, k, kante, richtung,
                    sweep_bar, cfg, zustand, ablehnung,
                )
                if sig is not None:
                    signale.append(sig)
                else:
                    nextbar_abgelehnt += 1
        pending.clear()

        # --- Sweeps ohne in_bar-Reclaim merken (fuer Abgleich bei k+1) ---
        ks = _c_waehle_einstiegskante(kanten, "SHORT", hi[k])
        if ks is not None and cl[k] > ks.basis_preis:
            pending.append((k, "SHORT", ks.kanten_id))
            sweeps_ohne_reclaim += 1
        kl_ = _c_waehle_einstiegskante(kanten, "LONG", lo[k])
        if kl_ is not None and cl[k] < kl_.basis_preis:
            pending.append((k, "LONG", kl_.kanten_id))
            sweeps_ohne_reclaim += 1

    signale.sort(key=lambda s: (s.ts, s.richtung))
    laufzeit = time.perf_counter() - t0
    return _ReplayErgebnisC(
        fenster=fenster,
        cfg=cfg,
        n_bars=n,
        laufzeit_s=laufzeit,
        kanten=kanten,
        signale=signale,
        ablehnung=ablehnung,
        sweeps_ohne_reclaim=sweeps_ohne_reclaim,
        nextbar_reclaim_ok=nextbar_reclaim_ok,
        nextbar_abgelehnt=nextbar_abgelehnt,
    )


# ==============================================================================
# V3-STRAIGHT-EDGE-ENGINE (Spez §7.2 arretiert, Commit a771e04; Schritt B/C)
# ==============================================================================
# Additiver Zusatzblock - die A/B- und Alt-C-Strukturen oben bleiben unangetastet.
# Die arretierte Straight-Edge-Revision (§7.2-Nachtrag Sweep-Immunitaet):
#   * Keimung  >= 2 bestaetigte Pivot-Dochte im SE-Band 0.12 %
#     (Seed = 1. Docht; erst der 2. Docht im Band laesst die Kante keimen).
#   * Basis = MITTEL der akzeptierten Cluster-Dochte (selbst-lokalisierend,
#     kausal; laeuft mit jedem Touch deterministisch mit).
#   * SWEEP-IMMUNITAET: Reclaim-Dochte der aeussersten Referenz der Seite
#     (INKL. Singleton-Seeds) bilden NIE neue Linien (K33/K36 eliminiert).
#   * Regel 2: Einstiege NUR an der aeussersten AKTIVEN reifen Kante der Seite
#     (Rolle RANGE_AUSSENGRENZE, V-S: >= min_touches_handelbar Touches);
#     innere ZWISCHEN_LEVEL bleiben stumm.
#   * TP1 = kausaler Histogramm-POC (60 Bins) im Preisraum Einstiegskante <->
#     Gegenkante; TP2 = aeussere Gegenkante; Split 50/50; SL = Sweep-Extremum
#     +/- sl_buffer_usd (0.05).
# Ausgabe (Schritt C): Terminal-Report + test/kanten_engine_trades_AUG_mC.png
# (300 dpi) + test/tmp_v3_straight_edge_harness_AUG.txt.

SE_HARNESS_BAND_PCT: float = 0.12      # arretiert (Audit: einzige 5/5-Stufe)
SE_HARNESS_MIN_TOUCH_ABSTAND: int = 3  # Regel 1: Touch-Mindestabstand
SE_HARNESS_R21_RUHEZEIT: int = 192     # §7.2 Teil 5: 48 h
SE_HARNESS_TOMBSTONE_PCT: float = 0.30  # §7.2 Teil 5: eigenstaendig
WAR_AUSSEN_IDS: Set[int] = set()       # O1-Semantik (arretiert)
TOMBSTEINE: List[Tuple[int, str, float]] = []
R21_LOG: List[Tuple[int, int, str, float, int, int]] = []
SE_HARNESS_TP_RAUM_PCT: float = 0.0    # keine Mindest-Distanz (POC-Raum)


@dataclass(frozen=True, slots=True)
class StraightEdgeHarnessKonfiguration:
    """Arretierte SE-Harness-Konfiguration (Commit a771e04, Freigabe Schritt B).

    touch_band_pct = SE_BAND_PCT 0.12 (arretiert; einzige Stufe mit UPPER 5/5
    und ist_perfekt=True im Audit).
    """
    touch_band_pct: float = SE_HARNESS_BAND_PCT
    min_touches_handelbar: int = 3      # V-S strikt: Erst ab 3 Touches
    max_sweep_ueberdehnung_pct: float = 0.60  # Korridor [0.478; 0.625]%
    reclaim_grace_bars: int = 2          # Schluss innerhalb k..k+2
    sl_buffer_usd: float = 0.05          # Sweep-Extremum +/- 0.05 USD
    tp1_anteil_pct: float = 50.0         # 50/50 Zwei-Stufen-TP
    num_bins: int = 60                   # Binned-POC Aufloesung
    # --- D1-D5 (Freigabe 2026-09-08) -------------------------------------
    max_seed_distanz_pct: float = 0.75   # Q9b: Sicherheitsnetz Promotion
    min_wall_alter_bars: int = 24        # Q24: Erst-Durchstich erst ab Alter
    wall_live_bars: int = 96             # Q25: Liveness dormanter Aussenlinien
    doppeltop_puffer_usd: float = 0.01   # Q17: Non-Expansion-Puffer
    # --- Block 2/3 (Freigabe 2026-09-08, Teil 2) ------------------------
    retest_zyklus_bars: int = 12          # Q21: Liquiditaetszyklus (3 h, Teil 3)
    # --- Teil 7 (Arretierung 2026-09-09): B2 + Sweep-Entkopplung -------
    retest_zyklus_referenz: str = "ENTRY"   # B2: Entry-Bar statt Sweep
    stacking_gate_aktiv: bool = False       # §7.1 B revoziert (Teil 7)
    sweep_mindestdurchstich_pct: float = 0.0  # Barriere 1 entkoppelt
    quartil_distanz_pct: float = 25.0     # Q29: nur aeusseres Quartil handelt
    # --- Teil 5 (Arretierung 2026-09-09): R21 + Tombstone ---------------
    r21_loeschung_aktiv: bool = True      # §7.2 Teil 5 arretiert
    ruhezeit_roher_touch_bars: int = 192  # 48 h institutioneller Standard
    tombstone_band_pct: float = 0.30      # eigenstaendig (+/-0.30 %)
    erlaube_loeschung_fuer_prim_anker: bool = False
    # --- Stufe 3 (E-34n/17): Kalenderkante parametrisiert --------------
    # Die box_end-Kante war bis V019 ein Datums-Literal in ``_se_scan``
    # und damit ein reines AUG-Artefakt. Sie ist jetzt ein Konfigurations-
    # feld; der Default haelt jeden historischen Aufruf byte-identisch
    # (AUG = 644). ISO-8601 (``YYYY-MM-DD``); ``np.datetime64`` parst den
    # Wert in ``_se_scan``.
    box_end_datum: str = "2026-08-19"
    # --- Stufe 4b (E-34n/17): Concurrency-Schranke ----------------------
    # Hoechstzahl GLEICHZEITIG offener Positionen je Richtung. AUG
    # erreicht hoechstens 3 gleichzeitige SHORTs (K67@903 / K67@980 /
    # K73@981, alle Exit 991) -> Cap 3 ist auf dem arretierten Fenster
    # inert; die bindende Wirkung ist erst im Zweitfenster belegbar
    # (Bindetest: test/_chk_v019_cap_bindetest.py). 0 = Schranke aus.
    max_gleichzeitig_je_richtung: int = 3


def berechne_kausalen_histogramm_poc(
    df_bars: pd.DataFrame,
    start_bar: int,
    signal_bar: int,
    untergrenze: float,
    obergrenze: float,
    num_bins: int = 60,
) -> float:
    """Ermittelt den echten Point of Control (POC) kausal bis signal_bar.

    Gleiche Binned-Logik wie die Baseline (phasen_volumen_profil.py,
    Commit v0.4.0-DNA): np.linspace-Bins, volumengewichtete Ueberlapp-
    Verteilung (Anteil der Bar-Range je Bin), Glättung win=3, POC = Mitte
    des Max-Bins. Kausal: nur Bars start_bar..signal_bar (t <= k).

    Args:
        df_bars: OHLCV-Fenster (ts/open/high/low/close/tick_volume).
        start_bar: Balance-Beginn (erste Bar des Histogramm-Fensters).
        signal_bar: Entscheidungs-Bar k (histogramm t <= k).
        untergrenze: untere Preisgrenze (Gegenkante bzw. Einstiegskante).
        obergrenze: obere Preisgrenze (Einstiegskante bzw. Gegenkante).
        num_bins: Anzahl der Bins (Default 60).

    Returns:
        POC-Preis (Bin-Mitte des Max-Bins nach Glättung); bei leerem
        Teilfenster der Mittelwert der Preisgrenzen.
    """
    sub: pd.DataFrame = df_bars.iloc[start_bar:signal_bar + 1]
    if sub.empty:
        return (untergrenze + obergrenze) / 2.0

    edges: np.ndarray = np.linspace(untergrenze, obergrenze, num_bins + 1)
    vol: np.ndarray = np.zeros(num_bins, dtype=float)

    lows: np.ndarray = sub["low"].to_numpy(dtype=float)
    highs: np.ndarray = sub["high"].to_numpy(dtype=float)
    vols: np.ndarray = sub["tick_volume"].to_numpy(dtype=float)

    for lo, hi, v in zip(lows, highs, vols):
        if hi <= lo or v <= 0:
            continue
        lo_b: int = int(
            np.clip(np.searchsorted(edges, lo, side="right") - 1, 0, num_bins - 1)
        )
        hi_b: int = int(
            np.clip(np.searchsorted(edges, hi, side="left") - 1, 0, num_bins - 1)
        )
        if lo_b == hi_b:
            vol[lo_b] += v
        else:
            ov: np.ndarray = np.array([
                max(0.0, min(hi, edges[b + 1]) - max(lo, edges[b]))
                for b in range(lo_b, hi_b + 1)
            ])
            tot: float = float(ov.sum())
            if tot > 0:
                vol[lo_b:hi_b + 1] += v * ov / tot

    # Glaettung wie Baseline v0.4.0 (win=3)
    if len(vol) >= 3:
        vol_s: np.ndarray = np.convolve(vol, np.ones(3) / 3.0, mode="same")
    else:
        vol_s = vol

    p_idx: int = int(np.argmax(vol_s))
    poc_preis: float = float((edges[p_idx] + edges[p_idx + 1]) / 2.0)
    return poc_preis


def ist_sweep_einer_bestehenden_referenz_se(
    seite: KantenSeite,
    bar_k: int,
    pivot_preis: float,
    cl: np.ndarray,
    aeusserste_referenz_basis: Optional[float],
    cfg: StraightEdgeHarnessKonfiguration,
) -> bool:
    """Arretierte Sweep-Pruefung (Commit a771e04, spiegelbildlich zur Spez).

    1) In-Band-Vorrang: dist_pct <= touch_band_pct -> False (der Docht
       gehoert zur Referenz, ist kein Sweep).
    2) OBEN: pivot > basis & dist <= max_sweep_ueberdehnung; Reclaim =
       IRGENDEIN Close im Fenster [bar_k, bar_k + reclaim_grace_bars]
       <= basis -> True. UNTEN symmetrisch. any-Semantik kalibriert an
       Bar 229 (Reclaim in 230) und Bar 242 (Reclaim in 244).
    """
    if aeusserste_referenz_basis is None:
        return False
    if bar_k + cfg.reclaim_grace_bars + 1 > len(cl):
        return False
    basis = float(aeusserste_referenz_basis)
    dist_pct = abs(pivot_preis - basis) / basis * 100.0
    if dist_pct <= cfg.touch_band_pct:
        return False
    if dist_pct > cfg.max_sweep_ueberdehnung_pct:
        return False
    fenster = cl[bar_k:bar_k + cfg.reclaim_grace_bars + 1]
    if seite == "OBEN":
        if pivot_preis <= basis:
            return False
        return bool(np.any(fenster <= basis))
    if pivot_preis >= basis:
        return False
    return bool(np.any(fenster >= basis))


def _reclaim_stufe(seite: KantenSeite, k: int, basis: float,
                   hi: np.ndarray, lo: np.ndarray, cl: np.ndarray,
                   cfg: StraightEdgeHarnessKonfiguration
                   ) -> Tuple[int, Optional[ReclaimStufe]]:
    """D2 (Freigabe 2026-09-08): dreistufige Reclaim-Hierarchie, kausal.

    Q2: Signal verlangt echten Durchstich jenseits der Basis UND jenseits
    des Touch-Bands (kein Blind-Fading im Band).
    Q3/Q17: Non-Expansion mit 1-Cent-Puffer (Doppeltop/Linienlaeufer).
    Rueckgabe: (0, None) = kein Reclaim; sonst (stufe_n, ReclaimStufe).
    """
    n = len(cl)
    if k < 0 or k >= n:
        return 0, None
    puffer = cfg.doppeltop_puffer_usd
    band = cfg.touch_band_pct
    if seite == "OBEN":
        dist_o = (hi[k] - basis) / basis * 100.0
        if not (hi[k] > basis
                and cfg.sweep_mindestdurchstich_pct < dist_o
                <= cfg.max_sweep_ueberdehnung_pct):
            return 0, None
        if cl[k] <= basis:
            return 1, "STUFE_1_IN_BAR"
        if (k + 1 < n and cl[k + 1] <= basis
                and hi[k + 1] <= hi[k] + puffer):
            return 2, "STUFE_2_KERZE_2"
        if (k + 2 < n and cl[k + 2] <= basis
                and max(hi[k + 1], hi[k + 2]) <= hi[k] + puffer):
            return 3, "STUFE_3_KERZE_3"
        return 0, None
    dist_u = (basis - lo[k]) / basis * 100.0
    if not (lo[k] < basis
            and cfg.sweep_mindestdurchstich_pct < dist_u
            <= cfg.max_sweep_ueberdehnung_pct):
        return 0, None
    if cl[k] >= basis:
        return 1, "STUFE_1_IN_BAR"
    if (k + 1 < n and cl[k + 1] >= basis
            and lo[k + 1] >= lo[k] - puffer):
        return 2, "STUFE_2_KERZE_2"
    if (k + 2 < n and cl[k + 2] >= basis
            and min(lo[k + 1], lo[k + 2]) >= lo[k] - puffer):
        return 3, "STUFE_3_KERZE_3"
    return 0, None


def _finde_kante(kanten: List[_SEEdgeH],
                 basis: float) -> Optional[_SEEdgeH]:
    """Q9b: Kante/Seed zur Basis der aeussersten Referenz (Toleranz 1e-6)."""
    best: Optional[_SEEdgeH] = None
    best_d = 1e18
    for e in kanten:
        d = abs(e.basis - basis)
        if d < best_d:
            best, best_d = e, d
    return best if best is not None and best_d <= 1e-6 else None


def _promo_erlaubt(seed: _SEEdgeH, kanten: List[_SEEdgeH],
                   cfg: StraightEdgeHarnessKonfiguration,
                   k: int = 10 ** 9) -> bool:
    """Q9b: Sicherheitsnetz — Abstand zur naechsten Linie derselben Seite
    <= max_seed_distanz_pct (0.75 %). Nur Linien mit geburts_bar <= k
    (Bar-Kausalitaet, kein Blick auf spaeter entstandene Linien).
    """
    for e in kanten:
        if e is seed or e.seite != seed.seite or e.geburts_bar > k:
            continue
        dist = abs(seed.basis - e.basis) / e.basis * 100.0
        if dist <= cfg.max_seed_distanz_pct:
            return True
    return False


@dataclass(slots=True)
class _SEEdgeH:
    """SE-Kante des Harness (Regel 1, selbst-lokalisierende Mittel-Basis).

    basis = laufendes Mittel aller akzeptierten Dochte (kausal). Schlaf-
    Fenster wie im Audit; Touch = bestaetigter Pivot-Docht im SE-Band.
    """

    kid: int
    seite: KantenSeite
    basis: float
    geburts_bar: int                    # Pivot-Bar des 2. Dochts (Keimung)
    wicks: List[Tuple[int, float]] = field(default_factory=list)
    status: str = "AKTIV"
    letzter_bar: int = -1000
    schlaf_windows: List[Tuple[int, Optional[int]]] = field(default_factory=list)
    letzter_signal_bar: int = -1000
    # --- D1 (Freigabe 2026-09-08): Primär-Anker / Promotion / Cluster -----
    ist_prim_anker: bool = False        # Q13: eingefrorene Grundlinie
    erster_pivot_bar: int = -1          # level-definierender Pivot (unveraenderlich)
    promoviert_ab_bar: int = -1         # Q9b: Bar des bestaetigten Reclaims
    letzter_sweep_bar: int = -1000      # Q4: F3-Frische-Referenz
    cluster_hoch: float = 0.0           # Q6/Q8: Cluster-Extremum (SHORT)
    cluster_tief: float = 0.0           # Q6/Q8: Cluster-Extremum (LONG)

    @property
    def touch_anzahl(self) -> int:
        return len(self.wicks)

    def basis_bei(self, k: int) -> float:
        """Kausale Basis bei Bar k = Mittel der Dochte (p+2<=k).

        Q13: Nur der promovierte Primär-Anker friert auf seiner Grundlinie
        ein; alle anderen Linien behalten die arretierte Mittel-Basis
        (Spez §7.1).
        """
        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        if px:
            return float(min(px) if self.seite == "OBEN" else max(px))
        return float(self.wicks[0][1])

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


def _se_scan(fenster: FensterTyp,
             cfg: StraightEdgeHarnessKonfiguration) -> Dict:
    """Kausaler SE-Scan ueber ein Fenster (Regel 1 + Sweep-Immunitaet + 2-Body).

    Rueckgabe: edges (gekeimt >= 2), seeds (Singletons am Fensterende),
    sweep_sperren (blockierte Seed-Geburten), ueberlapp, n, box_end_bar, d,
    band_pct. Identische Kausalitaet wie der reine Audit-Scan (Schritt B:
    die auditierte Referenz wird hier in den Harness gehoben).
    """
    # §7.2 Teil 5: Lauf-Idempotenz -- Container je Scan frisch (kein State-Leak)
    WAR_AUSSEN_IDS.clear()
    TOMBSTEINE.clear()
    R21_LOG.clear()

    def _lebt_scan(e: _SEEdgeH, kk: int) -> bool:
        _b = [b for b, _ in e.wicks if b <= kk]
        return bool(_b) and max(_b) >= kk - cfg.wall_live_bars

    def _r21_loeschen(e: _SEEdgeH, kk: int,
                      c: StraightEdgeHarnessKonfiguration) -> bool:
        if e.ist_prim_anker and not c.erlaube_loeschung_fuer_prim_anker:
            return False
        if e.kid in WAR_AUSSEN_IDS:
            return False
        if kk - e.erster_pivot_bar < c.wall_live_bars:
            return False
        if sum(1 for b, _ in e.wicks if b + 2 <= kk) >= 2:
            return False
        _roh = [b for b, _ in e.wicks if b <= kk]
        if not _roh:
            return False
        return (kk - max(_roh)) >= c.ruhezeit_roher_touch_bars

    def _tombstone_sperrt(seite: str, px: float,
                          c: StraightEdgeHarnessKonfiguration) -> bool:
        for _tk, _ts, _tp in TOMBSTEINE:
            if (_ts == seite
                    and abs(px - _tp) / _tp * 100.0 <= c.tombstone_band_pct):
                return True
        return False

    d = _lade_fenster(fenster)
    n = len(d)
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    op = d["open"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    ts_arr = d["ts"].to_numpy().astype("datetime64[ns]")
    box_end_bar = int(np.searchsorted(ts_arr, np.datetime64(cfg.box_end_datum)))

    cluster: Dict[KantenSeite, List[_SEEdgeH]] = {"OBEN": [], "UNTEN": []}
    ueberlapp: List[Tuple[int, str, float, List[Tuple[int, float, int]]]] = []
    sweep_sperren: List[Tuple[int, str, float, float, float]] = []
    kid_next = 0

    def _ist_im_band(px: float, basis: float) -> bool:
        return abs(px - basis) / basis * 100.0 <= cfg.touch_band_pct

    def _akzeptiere(e: _SEEdgeH, bar: int, px: float) -> None:
        if len(e.wicks) == 1:
            e.geburts_bar = bar
        e.wicks.append((bar, px))
        e.letzter_bar = bar
        if not e.ist_prim_anker:            # Q13: Anker friert ein
            e.basis = float(np.mean([p for _, p in e.wicks]))
        if e.status == "SCHLAFEND":
            e.status = "AKTIV"
            if e.schlaf_windows:
                start, _end = e.schlaf_windows[-1]
                e.schlaf_windows[-1] = (start, bar + 2)

    for k in range(n):
        mbar = k - 2
        if mbar >= 2:
            for typ in _pivot_dual(hi, lo, mbar):
                seite: KantenSeite = "OBEN" if typ == "H" else "UNTEN"
                px = float(hi[mbar]) if typ == "H" else float(lo[mbar])
                cand = [c for c in cluster[seite]
                        if _ist_im_band(px, c.basis)
                        and mbar - c.letzter_bar >= SE_HARNESS_MIN_TOUCH_ABSTAND]
                if cand:
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
                    refs = cluster[seite]
                    aeus_ref = None
                    if refs:
                        aeus_ref = (max(r.basis for r in refs)
                                    if seite == "OBEN"
                                    else min(r.basis for r in refs))
                    if ist_sweep_einer_bestehenden_referenz_se(
                            seite, mbar, px, cl, aeus_ref, cfg):
                        dist_pct = abs(px - aeus_ref) / aeus_ref * 100.0
                        sweep_sperren.append((mbar, seite, px, aeus_ref,
                                              dist_pct))
                        # D3/Q9b: ereignisgetriebene Promotion des Seeds
                        ref = _finde_kante(cluster[seite], aeus_ref)
                        if ref is not None and not ref.ist_prim_anker:
                            st, _nm = _reclaim_stufe(seite, mbar, aeus_ref,
                                                     hi, lo, cl, cfg)
                            if (st
                                    and _promo_erlaubt(ref, cluster[seite],
                                                       cfg, mbar)):
                                ref.ist_prim_anker = True
                                ref.basis = float(aeus_ref)
                                ref.promoviert_ab_bar = mbar
                        continue
                    if cfg.r21_loeschung_aktiv and _tombstone_sperrt(
                            seite, px, cfg):
                        R21_LOG.append((mbar, -1, seite, round(px, 3),
                                        -1, -1))
                        continue
                    e = _SEEdgeH(kid=kid_next, seite=seite, basis=px,
                                 geburts_bar=mbar, erster_pivot_bar=mbar)
                    kid_next += 1
                    e.wicks.append((mbar, px))
                    e.letzter_bar = mbar
                    cluster[seite].append(e)

        # 2-Body-Bruch gegen die laufende Basis (nur gekeimte Kanten)
        for seite in ("OBEN", "UNTEN"):
            for e in cluster[seite]:
                if (e.touch_anzahl < 2 and not e.ist_prim_anker) or k < 1:
                    continue
                if seite == "OBEN":
                    aussen = (min(op[k - 1], cl[k - 1]) > e.basis
                              and min(op[k], cl[k]) > e.basis)
                else:
                    aussen = (max(op[k - 1], cl[k - 1]) < e.basis
                              and max(op[k], cl[k]) < e.basis)
                if aussen and e.status == "AKTIV":
                    e.status = "SCHLAFEND"
                    e.schlaf_windows.append((k, None))

        # --- §7.2 Teil 5: R21-Bereinigung (kausal bei Bar k, in-place) --
        if cfg.r21_loeschung_aktiv:
            for _seite in ("OBEN", "UNTEN"):
                _keep = []
                for _e in cluster[_seite]:
                    _alt = k - _e.erster_pivot_bar
                    if (_alt >= cfg.wall_live_bars
                            and not _e.ist_prim_anker):
                        _lb = [r for r in cluster[_seite]
                               if _lebt_scan(r, k)]
                        _ist_aussen = True
                        if _lb:
                            if _seite == "OBEN":
                                _ist_aussen = _e.basis >= max(
                                    r.basis for r in _lb)
                            else:
                                _ist_aussen = _e.basis <= min(
                                    r.basis for r in _lb)
                        if _ist_aussen:
                            WAR_AUSSEN_IDS.add(_e.kid)   # O1 arretiert
                    if _r21_loeschen(_e, k, cfg):
                        R21_LOG.append((k, _e.kid, _e.seite,
                                        round(_e.basis, 3),
                                        _e.erster_pivot_bar, _alt))
                        TOMBSTEINE.append((k, _e.seite, _e.basis))
                    else:
                        _keep.append(_e)
                cluster[_seite] = _keep

    edges = [e for lst in cluster.values() for e in lst
             if e.touch_anzahl >= 2]
    seeds = [e for lst in cluster.values() for e in lst
             if e.touch_anzahl < 2]
    edges.sort(key=lambda e: (e.seite, e.basis))
    seeds.sort(key=lambda e: e.basis)
    return dict(edges=edges, seeds=seeds, ueberlapp=ueberlapp,
                sweep_sperren=sweep_sperren, n=n, box_end_bar=box_end_bar, d=d,
                band_pct=cfg.touch_band_pct,
                r21_geloescht=list(R21_LOG),
                tombstones=list(TOMBSTEINE))


@dataclass(frozen=True, slots=True)
class _SESetup:
    bar: int
    richtung: SignalRichtung
    kid: int
    basis: float
    sweep: float
    trigger_close: float
    touch_n: int
    poc: float
    tp2: float
    sl: float
    entry: float
    r: float
    resultat: str
    # --- D4/D5 (Freigabe 2026-09-08) -------------------------------------
    stufe: ReclaimStufe = "STUFE_1_IN_BAR"
    reclaim_bar: int = -1
    entry_bar: int = -1
    ist_prim_anker: bool = False
    grund1: str = ""
    exit1_bar: int = -1
    exit2_bar: int = -1
    # --- Stufe 4a (E-34n/17): Schenkel-Durchreichung ---------------------
    # ``_c_loese_trade`` berechnet r1/r2/grund1/grund2 bereits vollstaendig;
    # bis Stufe 4a wurden grund2/r1/r2 bei der _SESetup-Instanziierung
    # verworfen. Die Durchreichung ist rein additiv (Defaults = inert).
    grund2: str = ""
    r1: float = 0.0
    r2: float = 0.0


def _konkurrenz_aktiv(
    setups: List["_SESetup"],
    richtung: SignalRichtung,
    entry_bar: int,
    exit1_bar: int,
    exit2_bar: int,
) -> int:
    """Gleichzeitig offene Positionen DERSELBEN Richtung (inkl. Kandidat).

    Eine Position ist von ``entry_bar`` bis ``max(exit1_bar, exit2_bar)``
    offen (Haltedauer inklusiv; ein Exit-Bar < Entry gilt als Entry-Bar).
    Gemessen wird der Ueberlapp mit dem Kandidaten; dieser zaehlt selbst
    mit (Rueckgabe >= 1).
    """
    neu_von = int(entry_bar)
    neu_bis = max(int(exit1_bar), int(exit2_bar), neu_von)
    anzahl = 1
    for s in setups:
        if s.richtung != richtung:
            continue
        von = int(s.entry_bar)
        bis = max(int(s.exit1_bar), int(s.exit2_bar), von)
        if von <= neu_bis and neu_von <= bis:
            anzahl += 1
    return anzahl


def _se_trades(scan: Dict, cfg: StraightEdgeHarnessKonfiguration
               ) -> Tuple[List[_SESetup], Dict[str, int]]:
    """Regel-2-Trades an der aeussersten AKTIVEN Kante (D4, 2026-09-08).

    Q1: Die aeusserste Linie handelt ohne V-S >= 3 — die Reclaim-Abweisung
    IST die operative Reife; V-S >= 3 bleibt Schutz innerer (stummer) Linien.
    Q9b/Q13: promovierte Primaer-Anker sind handelbar, Basis eingefroren.
    Q2/Q3/Q17: echter Durchstich + Stufen 1/2/3 (Non-Expansion mit Puffer).
    Q4: F3-Frische referenziert den Sweep-Bar.
    Q6/Q10: SL = Cluster-Extremum (kausal bis Reclaim-Bar) + Puffer.
    Q11/Q16: F2 — Einstieg nur ohne offene Position ODER nach De-Risking
    (Haelfte 1 = TP1). Q8: gleicher Schwung sperrt im Vollrisiko.
    Q5/Q14: TP2 = aeusserste Gegenkante (>= 2 Touches, >= 1.5 %, SCHLAFEND ok).
    Nur in der Box (bars < box_end_bar).
    """
    d = scan["d"]
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    op = d["open"].to_numpy(dtype=float)
    alle: List[_SEEdgeH] = list(scan["edges"]) + list(scan["seeds"])
    seite_edges: Dict[KantenSeite, List[_SEEdgeH]] = {
        "OBEN": [e for e in alle if e.seite == "OBEN"],
        "UNTEN": [e for e in alle if e.seite == "UNTEN"]}
    setups: List[_SESetup] = []
    box_end = scan["box_end_bar"]
    stats: Dict[str, int] = {"v_s": 0, "kein_gegner": 0, "f3": 0,
                             "kein_raum": 0, "zyklus_blockiert": 0,
                             "quartil_blockiert": 0, "blocker": 0,
                             "promotionen": 0,
                             "stacking_blockiert": 0,
                             "frisch_blockiert": 0,
                             "concurrency_blockiert": 0}
    poc_start = 0                       # Balance-Beginn (Box-Beginn)
    letzter_trade: Dict[int, _SESetup] = {}
    getradete_entry_bars: set[int] = set()   # B23-3: Dedup je Entry-Bar
    stacking_liste: List[str] = []        # §7.1 B (Teil 4)
    zyklus_liste: List[str] = []
    quartil_liste: List[str] = []
    blocker_liste: List[str] = []

    def _existiert(e: _SEEdgeH, k: int) -> bool:
        """Linie existiert, sobald ihr level-definierender Pivot bestaetigt ist.

        Bestaetigung = Pivot-Bar + 2 (P1). Fuer den fruehestmoeglichen Entry
        (k+1) bedeutet das: erster_pivot_bar + 2 <= k + 1. Die Keimung
        (>= 2 Touches) ist KEINE Existenzbedingung — sie bestimmt nur die
        ZWISCHEN_LEVEL-Rolle.
        """
        if not e.ist_aktiv_bei(k):
            return False
        return e.erster_pivot_bar + 2 <= k + 1

    def _lebt(e: _SEEdgeH, k: int) -> bool:
        """Q25: Linie ist am Markt praesent (letzter Kontakt <= wall_live_bars).

        Dormante Crash-Extreme (K3 62.967/Bar 14, K4 63.252/Bar 20) sind keine
        Begrenzung der aktuellen Balance und duerfen die Unterseite nicht
        lahmlegen; eine LEBENDE, nicht erreichte Aussenlinie sperrt dagegen
        jeden Einstieg weiter innen.
        """
        bars = [b for b, _ in e.wicks if b <= k]
        if not bars:
            return False
        return max(bars) >= k - cfg.wall_live_bars

    def _im_aussenquartil(richtung: SignalRichtung, k: int,
                          sweep_px: float) -> bool:
        """Q29: Einstieg nur an der aeusseren lebenden Wand.

        Distanz des Sweep-Extremums zum laufenden Range-Extrem,
        normiert auf die kausale Spanne 0..k. Aeusseres Quartil =
        <= quartil_distanz_pct (Default 25 %).
        """
        ex_hi = float(np.max(hi[:k + 1]))
        ex_lo = float(np.min(lo[:k + 1]))
        spanne = ex_hi - ex_lo
        if spanne <= 0.0:
            return True
        distanz = ((ex_hi - sweep_px) if richtung == "SHORT"
                   else (sweep_px - ex_lo)) / spanne * 100.0
        return distanz <= cfg.quartil_distanz_pct

    def _blockiert_durch_aussenkante(richtung: SignalRichtung, k: int,
                                     kd: _SEEdgeH,
                                     sweep_px: float) -> Optional[_SEEdgeH]:
        """M6: Innenlevel-Blocker (kein Fade unter einer Aussenwand).

        Blocker ist die AEUSSERSTE existierende Linie derselben Seite, die
        vom Sweep-Extremum NICHT erreicht wurde (jenseits des Sweeps liegt)
        und deren Abstand zur Kandidatenbasis <= max_seed_distanz_pct
        (0.75 %) ist. Nur _existiert-Linien (AKTIV) wirken als Blocker (F3).
        Die AEUSSERSTE Linie ist entscheidend: eine naehere Innenlinie darf
        die Sperre nicht ausloesen, wenn die Aussenwand selbst erreicht wurde.
        """
        seite: KantenSeite = "OBEN" if richtung == "SHORT" else "UNTEN"
        basis_k = kd.basis_bei(k)
        aussen: Optional[_SEEdgeH] = None
        for e in seite_edges[seite]:
            if e is kd or not _existiert(e, k):
                continue
            b = e.basis_bei(k)
            if seite == "OBEN":
                if b <= sweep_px:
                    continue                    # erreicht -> kein Blocker
                if aussen is None or b > aussen.basis_bei(k):
                    aussen = e
            else:
                if b >= sweep_px:
                    continue
                if aussen is None or b < aussen.basis_bei(k):
                    aussen = e
        if aussen is None:
            return None
        b = aussen.basis_bei(k)
        dist = ((b - basis_k) if seite == "OBEN"
                else (basis_k - b)) / basis_k * 100.0
        return aussen if 0.0 < dist <= cfg.max_seed_distanz_pct else None

    def _etabliert(e: _SEEdgeH, k: int) -> bool:
        """Q24: Linie ist etabliert, wenn ihr level-definierender Pivot
        mindestens min_wall_alter_bars zurueckliegt (kein Fade des ersten
        Ausbruchsversuchs einer frischen Linie).
        """
        return k - e.erster_pivot_bar >= cfg.min_wall_alter_bars

    def _kandidat(richtung: SignalRichtung, k: int,
                  sweep_px: float) -> Optional[_SEEdgeH]:
        """Kaskade von aussen nach innen ueber EXISTIERENDE Linien (Regel 2).

        - top = hoechste/tiefste existierende Linie.
        - dist(top) <= 0            -> kein Trade (kein Fading unter der Wand)
        - dist(top) > touch_band    -> top handelt (Q1: Reclaim = Reife)
        - dist(top) <= touch_band   -> in-band beruehrt (kein Sweep) ->
          naechste Linie nach innen; innere Linien brauchen V-S >= 3
        - dist > max_sweep          -> Ueberdehnung, kein Trade
        """
        seite: KantenSeite = "OBEN" if richtung == "SHORT" else "UNTEN"

        def _dist(e: _SEEdgeH) -> float:
            basis = e.basis_bei(k)
            if richtung == "SHORT":
                return (sweep_px - basis) / basis * 100.0
            return (basis - sweep_px) / basis * 100.0

        pool: List[_SEEdgeH] = []
        for e in seite_edges[seite]:
            if not _existiert(e, k):
                continue
            # B23-2: Anker wirkt erst ab seiner Promotions-Bar (kausal).
            if not ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                    or e.touch_conf(k) >= 2):
                continue                        # Seeds nur ereignisgetrieben
            if not _etabliert(e, k):
                if _dist(e) > cfg.touch_band_pct:
                    stats["frisch_blockiert"] += 1
                continue                        # Q24: Linie noch zu jung
            pool.append(e)
        # Q9b: ein Seed zaehlt NUR, wenn dieser Bar ihn tatsaechlich
        # durchsticht (K3/K4 werden in der Box nie unterschritten).
        for e in seite_edges[seite]:
            if e in pool or not _existiert(e, k) or e.ist_prim_anker:
                continue
            if e.touch_conf(k) >= 2 or not _etabliert(e, k):
                continue
            d = _dist(e)
            if cfg.sweep_mindestdurchstich_pct < d <= cfg.max_sweep_ueberdehnung_pct:
                pool.append(e)
        if not pool:
            return None
        pool.sort(key=lambda e: e.basis_bei(k), reverse=(seite == "OBEN"))
        for pos, e in enumerate(pool):
            dist = _dist(e)
            if dist < 0.0:
                if _lebt(e, k):
                    return None                 # lebende Wand nicht erreicht
                continue                        # dormante Linie ignorieren
            if dist > cfg.max_sweep_ueberdehnung_pct:
                return None                     # Ueberdehnung, kein Reclaim
            if dist <= cfg.sweep_mindestdurchstich_pct:
                continue                        # nur Durchstich zaehlt (Teil 7)
            if pos == 0:
                return e                        # Q1: Wand handelt (Reclaim=Reife)
            if e.touch_conf(k) < cfg.min_touches_handelbar:
                continue                        # innere Linie braucht V-S >= 3
            return e
        return None

    def _gegenkante(richtung: SignalRichtung, k: int) -> Optional[_SEEdgeH]:
        """Q5/Q14: aeusserste Gegenkante (>= 2 Touches, SCHLAFEND zulaessig)."""
        gegenseite: KantenSeite = "UNTEN" if richtung == "SHORT" else "OBEN"
        # Block2/Q30: identische Existenz-Semantik wie _kandidat (Pivot+2),
        # bewusst OHNE AKTIV-Gate (Q5/Q14: SCHLAFENDE Gegenkanten erlaubt).
        # Q18/Q30: promovierte Primaer-Anker ohne 2-Touch-Gate.
        pool = [e for e in seite_edges[gegenseite]
                if e.erster_pivot_bar + 2 <= k + 1
                and ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                     or e.touch_conf(k) >= 2)]
        if not pool:
            return None
        if gegenseite == "OBEN":
            return max(pool, key=lambda e: e.basis_bei(k))
        return min(pool, key=lambda e: e.basis_bei(k))

    for k in range(2, box_end - 3):
        for richtung in ("SHORT", "LONG"):
            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])
            kd = _kandidat(richtung, k, sweep_px)
            if kd is None:
                continue
            # --- M6: Innenlevel-Blocker (unerreichte Aussenwand) ---------------
            blk = _blockiert_durch_aussenkante(richtung, k, kd, sweep_px)
            if blk is not None:
                stats["blocker"] += 1
                blocker_liste.append(
                    f"bar {k:4d} {richtung:5s} K{kd.kid:3d} "
                    f"basis={kd.basis_bei(k):.3f} sweep={sweep_px:.3f} "
                    f"-> BLOCKER-SPERRE (unerreichte Aussenwand K{blk.kid} "
                    f"{blk.basis_bei(k):.3f})")
                continue
            # --- Q29: Niemandsland-Sperre (aeusseres Quartil) ----------
            if not _im_aussenquartil(richtung, k, sweep_px):
                stats["quartil_blockiert"] += 1
                quartil_liste.append(
                    f"bar {k:4d} {richtung:5s} K{kd.kid:3d} "
                    f"basis={kd.basis_bei(k):.3f} sweep={sweep_px:.3f} "
                    f"-> QUARTIL-SPERRE (Mitte der Range)")
                continue
            seite: KantenSeite = "OBEN" if richtung == "SHORT" else "UNTEN"
            basis = kd.basis_bei(k)
            stufe_n, stufe_name = _reclaim_stufe(seite, k, basis, hi, lo, cl,
                                                 cfg)
            if stufe_n == 0:
                continue
            entry_bar = k + stufe_n
            reclaim_bar = entry_bar - 1
            # --- Q4: F3-Frische (Sweep-Bar-Referenz) --------------------------
            if k <= kd.letzter_sweep_bar:
                stats["f3"] += 1
                continue
            # --- Q6/Q10: Cluster-Extremum kausal bis Reclaim-Bar --------------
            if richtung == "SHORT":
                cluster_ext = float(np.max(hi[k:reclaim_bar + 1]))
                sl = cluster_ext + cfg.sl_buffer_usd
            else:
                cluster_ext = float(np.min(lo[k:reclaim_bar + 1]))
                sl = cluster_ext - cfg.sl_buffer_usd
            # --- Q21/B23: Retest-Zyklus (ersetzt F2-Vollrisiko + Q8) ----------
            # B23-5: letzter_sweep_bar wird NUR bei tatsaechlich genommenem
            # Trade fortgeschrieben (siehe unten) -- ein abgewiesener Kontakt
            # setzt die Uhr nicht zurueck.
            _vor_zeit = letzter_trade.get(kd.kid)
            if (_vor_zeit is not None
                    and entry_bar - _vor_zeit.entry_bar
                    < cfg.retest_zyklus_bars):
                stats["zyklus_blockiert"] += 1
                zyklus_liste.append(
                    f"bar {k:4d} {richtung:5s} K{kd.kid:3d} "
                    f"basis={kd.basis_bei(k):.3f} -> ZYKLUS-SPERRE "
                    f"(letzter Sweep Bar {kd.letzter_sweep_bar}, "
                    f"Abstand {k - kd.letzter_sweep_bar} "
                    f"< {cfg.retest_zyklus_bars})")
                continue
            geg = _gegenkante(richtung, k)
            if geg is None:
                stats["kein_gegner"] += 1
                continue
            gegen_basis = geg.basis_bei(k)
            if richtung == "SHORT":
                if not (gegen_basis < basis):
                    stats["kein_raum"] += 1
                    continue
                if abs(basis - gegen_basis) / basis * 100.0 < V3_TP_MINDIST_PCT:
                    stats["kein_raum"] += 1
                    continue
                unter, ober = gegen_basis, basis
            else:
                if not (gegen_basis > basis):
                    stats["kein_raum"] += 1
                    continue
                if abs(gegen_basis - basis) / basis * 100.0 < V3_TP_MINDIST_PCT:
                    stats["kein_raum"] += 1
                    continue
                unter, ober = basis, gegen_basis
            poc = berechne_kausalen_histogramm_poc(
                d, poc_start, k, unter, ober, cfg.num_bins)
            if not (unter < poc < ober):
                stats["kein_raum"] += 1
                continue
            entry = float(op[entry_bar])
            tp2 = gegen_basis
            if richtung == "SHORT":
                if not (sl > entry > poc > tp2):
                    stats["kein_raum"] += 1
                    continue
            else:
                if not (sl < entry < poc < tp2):
                    stats["kein_raum"] += 1
                    continue
            risk = abs(sl - entry)
            if risk <= 0:
                stats["kein_raum"] += 1
                continue
            # --- §7.1 B REVOZIERT (Teil 7): kein Stacking-Gate ----------
            # Der Schutz gegen Re-Entry-Spamming liegt beim 12-Bar-
            # Entry-Mindestabstand (B2, Zyklus-Check unten).
            trade = _c_loese_trade(
                hi, lo, cl, entry_bar, entry, richtung, sl, poc, tp2,
                cfg.tp1_anteil_pct)
            # --- Stufe 4b (E-34n/17): Concurrency-Schranke (Klumpenrisiko) -
            # Schutz gegen ungedecktes paralleles Engagement in EINER
            # Richtung. Auf AUG hoechstens 3 gleichzeitig -> inert; die
            # Wirkung ist maschinell im Bindetest nachgewiesen.
            if cfg.max_gleichzeitig_je_richtung > 0:
                _offen = _konkurrenz_aktiv(
                    setups, richtung, entry_bar,
                    trade.exit1_bar, trade.exit2_bar)
                if _offen > cfg.max_gleichzeitig_je_richtung:
                    stats["concurrency_blockiert"] += 1
                    continue
            if entry_bar in getradete_entry_bars:   # B23-3: Dedup
                continue
            getradete_entry_bars.add(entry_bar)
            kd.letzter_signal_bar = k
            kd.letzter_sweep_bar = k
            # Strenge Regel: keine Seed-Promotion fuer Trades (V-S >= 3).
            if richtung == "SHORT":
                kd.cluster_hoch = max(kd.cluster_hoch, cluster_ext)
            else:
                kd.cluster_tief = (cluster_ext if kd.cluster_tief <= 0.0
                                   else min(kd.cluster_tief, cluster_ext))
            setup = _SESetup(
                bar=k, richtung=richtung, kid=kd.kid, basis=basis,
                sweep=sweep_px, trigger_close=float(cl[k]),
                touch_n=kd.touch_conf(k), poc=poc, tp2=tp2, sl=sl,
                entry=entry, r=trade.r_mult, resultat=trade.resultat,
                stufe=stufe_name or "STUFE_1_IN_BAR", reclaim_bar=reclaim_bar,
                entry_bar=entry_bar, ist_prim_anker=kd.ist_prim_anker,
                grund1=trade.grund1, exit1_bar=trade.exit1_bar,
                exit2_bar=trade.exit2_bar,
                grund2=trade.grund2, r1=trade.r1, r2=trade.r2)
            letzter_trade[kd.kid] = setup
            setups.append(setup)

    # --- v0.20: Phasenboden-Regel G4 (generischer Hook-3-Konsum) -----------
    # Route A: Der Adapter AUTORISIERT, die Engine exekutiert. Der Guard ist
    # ZWINGEND, weil ``_hook`` im Standalone-Harness und im V0-Referenzlauf
    # des Renderers (``ORIG``, ``__globals__ == engine.__dict__``) NICHT
    # definiert ist. Ohne Guard: NameError. Inertheit ist zweistufig:
    #   (a) keine gebundene ``hook_3_boden_reclaim`` -> kein Block,
    #   (b) ``boden_deklariert_literal is None`` -> Segment uebersprungen.
    # Damit bleiben P9 / P9_DIRECT_69_87 / DEFAULT_ADAPTER / ADAPTER_V014
    # exakt auf Baseline (17 Trades); V01/V014-Bildsaetze byte-identisch.
    _hk_g4 = globals().get("_hook")
    _bspec_g4 = getattr(_hk_g4, "hook_3_boden_reclaim", None)
    if _bspec_g4 is not None:
        _kid_g4 = {e.kid: e for e in alle}
        for _seg_g4 in getattr(_hk_g4, "segmente", ()):
            _lit_g4 = getattr(_seg_g4, "boden_deklariert_literal", None)
            if _lit_g4 is None:
                continue
            # Fensterzugang aus dem Adapter: H1 (bars < 640) wird nicht
            # einmal iteriert - die Regressionsfreiheit ist strukturell.
            for _k_g4 in range(int(_seg_g4.start_bar),
                               int(_seg_g4.end_bar) + 1):
                # (1)+(2) Durchstich unter den deklarierten Boden + Reclaim.
                if not (lo[_k_g4] < _lit_g4 < cl[_k_g4]):
                    continue
                _spec_g4 = _bspec_g4(_k_g4)
                if _spec_g4 is None:
                    continue
                # Keine zweite Wahrheit: Spec-Literal == Segment-Literal.
                assert abs(float(_spec_g4.deklarierter_boden_literal)
                           - float(_lit_g4)) < 1e-12, _spec_g4
                _kante_g4 = _kid_g4.get(int(_spec_g4.boden_kid))
                if _kante_g4 is None:
                    continue
                # (3) V-S >= 3: kausale Touch-Bestaetigung der Bodenkante.
                if _kante_g4.touch_conf(_k_g4) < cfg.min_touches_handelbar:
                    continue
                _eb_g4 = _k_g4 + 1
                if _eb_g4 in getradete_entry_bars:      # B23-3: Dedup
                    continue
                _entry_g4 = float(op[_eb_g4])
                # Deklarierte Regel min(lo[k:k+2]) - Puffer; NICHT das
                # Nachbar-Idiom lo[k:reclaim_bar+1] (hier numerisch identisch,
                # aber bewusst die strengere Regelform).
                _sl_g4 = (float(lo[_k_g4:_eb_g4 + 1].min())
                          - cfg.sl_buffer_usd)
                # POC regel-lokal: Anker = PHASENSTART (nicht poc_start = 0).
                _poc_g4 = berechne_kausalen_histogramm_poc(
                    d, int(_seg_g4.start_bar), _k_g4, float(_lit_g4),
                    float(_spec_g4.tp2), cfg.num_bins)
                if not (_sl_g4 < _entry_g4 < _poc_g4 < _spec_g4.tp2):
                    continue
                _tr_g4 = _c_loese_trade(
                    hi, lo, cl, _eb_g4, _entry_g4, "LONG", _sl_g4,
                    _poc_g4, float(_spec_g4.tp2), cfg.tp1_anteil_pct)
                # --- Stufe 4b-Nachtrag (E-34n/17): KEIN Sonderweg ------
                # Der G4-Reclaim hing bis hier direkt an ``setups`` und
                # umging die Concurrency-Schranke. Auf AUG folgenlos
                # (einzelner LONG in P9), aber ein Risikomodul kennt
                # keine unkontrollierten Nebenwege -> Guard identisch
                # zum Regel-Loop.
                if cfg.max_gleichzeitig_je_richtung > 0:
                    _offen_g4 = _konkurrenz_aktiv(
                        setups, "LONG", _eb_g4,
                        _tr_g4.exit1_bar, _tr_g4.exit2_bar)
                    if _offen_g4 > cfg.max_gleichzeitig_je_richtung:
                        stats["concurrency_blockiert"] += 1
                        continue
                getradete_entry_bars.add(_eb_g4)
                # Stufe-1-In-Bar bindet Signal-Ausfuehrung an den
                # Entry-Bar-Trigger: ``reclaim_bar = entry_bar`` (V015-Staging,
                # byte-reproduzierend zu §68.5).
                setups.append(_SESetup(
                    bar=_k_g4, richtung="LONG",
                    kid=int(_spec_g4.boden_kid),
                    basis=float(_kante_g4.basis_bei(_k_g4)),
                    sweep=float(lo[_k_g4]), trigger_close=float(cl[_k_g4]),
                    touch_n=int(_kante_g4.touch_conf(_k_g4)),
                    poc=float(_poc_g4), tp2=float(_spec_g4.tp2),
                    sl=_sl_g4, entry=_entry_g4, r=float(_tr_g4.r_mult),
                    resultat=_tr_g4.resultat, stufe="STUFE_1_IN_BAR",
                    reclaim_bar=_eb_g4, entry_bar=_eb_g4,
                    ist_prim_anker=False, grund1=_tr_g4.grund1,
                    exit1_bar=int(_tr_g4.exit1_bar),
                    exit2_bar=int(_tr_g4.exit2_bar),
                    grund2=_tr_g4.grund2, r1=_tr_g4.r1,
                    r2=_tr_g4.r2))
    stats["promotionen"] = sum(1 for e in alle if e.ist_prim_anker)
    stats["v_s"] = len(setups)
    stats["zyklus_liste"] = zyklus_liste  # type: ignore[assignment]
    stats["quartil_liste"] = quartil_liste  # type: ignore[assignment]
    stats["blocker_liste"] = blocker_liste  # type: ignore[assignment]
    stats["stacking_liste"] = stacking_liste  # type: ignore[assignment]
    return setups, stats


def _se_report(fenster: FensterTyp, scan: Dict, setups: List[_SESetup],
               stats: Dict[str, int], nach_datei: bool = True) -> str:
    band = scan["band_pct"]
    edges = scan["edges"]
    seeds = scan["seeds"]
    box_end = scan["box_end_bar"]
    d = scan["d"]
    ts = pd.to_datetime(d["ts"])
    box_max_pivot = box_end - 3

    L = []
    L.append("=" * 118)
    L.append(f"V3-STRAIGHT-EDGE-HARNESS {fenster} | SE_BAND {band:.3f}% | "
             f"Box < 19.08 (bars < {box_end}) | arretiert a771e04")
    L.append("=" * 118)
    n_oben = sum(1 for e in edges if e.seite == "OBEN")
    n_unten = len(edges) - n_oben
    n_typ_b = sum(1 for e in edges if e.touch_anzahl >= 3)
    L.append(f"Gekeimte SE-Kanten: {len(edges)} (OBEN {n_oben}/UNTEN "
             f"{n_unten}) | >= 3 Touches: {n_typ_b} | Seeds offen: "
             f"{len(seeds)}")
    L.append("")
    L.append("-" * 118)
    L.append("SWEEP-SPERRE (blockierte Seed-Geburten):")
    L.append("-" * 118)
    if not scan["sweep_sperren"]:
        L.append("  (keine)")
    for (b, seite, px, ref, dist) in scan["sweep_sperren"]:
        mark = ""
        if seite == "OBEN" and b == 229:
            mark = "   <== K33 (Seed 229/66.776) ELIMINIERT"
        elif seite == "OBEN" and b == 242:
            mark = "   <== K36 (Seed 242/66.663) ELIMINIERT"
        L.append(f"  bar {b:4d} {seite:5s} docht={px:.3f} ref={ref:.3f} "
                 f"ueber {dist:.3f}% -> KEIN Seed{mark}")
    k33 = any(b == 229 and s == "OBEN" for b, s, *_ in scan["sweep_sperren"])
    k36 = any(b == 242 and s == "OBEN" for b, s, *_ in scan["sweep_sperren"])
    L.append(f"  -> K33 eliminiert: {k33} | K36 eliminiert: {k36}")
    L.append("")
    L.append("-" * 118)
    L.append("PROMOVIERTE PRIMAER-ANKER (Q9b: Sweep+Reclaim = ereignisgetriebene Promotion):")
    L.append("-" * 118)
    promos = [e for e in list(scan["edges"]) + list(scan["seeds"])
              if e.ist_prim_anker]
    promos.sort(key=lambda e: (e.promoviert_ab_bar, e.kid))
    if not promos:
        L.append("  (keine)")
    for e in promos:
        L.append(f"  K{e.kid:3d} {e.seite:5s} basis={e.basis:8.3f} "
                 f"geb={e.geburts_bar:4d} promo_ab={e.promoviert_ab_bar:4d} "
                 f"n={e.touch_anzahl}")
    L.append("")
    L.append("-" * 118)
    L.append("SE-KANTEN MIT BOX-DOCHT (basis = Box-Mittel):")
    L.append("-" * 118)
    box_edges = [e for e in edges if any(b <= box_end - 1 for b, _ in e.wicks)]
    box_edges.sort(key=lambda e: (e.geburts_bar, e.kid))
    for e in box_edges:
        inb = [b for b, _ in e.wicks if b <= box_end - 1]
        post = [b for b, _ in e.wicks if b > box_end - 1]
        bb = e.basis
        wick = ",".join(str(b) for b in inb)
        if post:
            wick += f" (+{len(post)} n.Box)"
        L.append(f"  K{e.kid:3d} {e.seite:5s} basis={bb:8.3f} "
                 f"geb={e.geburts_bar:4d} n={e.touch_anzahl} wicks=[{wick}]")
    L.append("")
    L.append("-" * 118)
    L.append(f"REGEL-2-TRADES (V-S >= {StraightEdgeHarnessKonfiguration().min_touches_handelbar} Touches, Stufen 1-3, De-Risk, Box): {len(setups)}")
    L.append("-" * 118)
    for s in setups:
        anker = " [PRIMAER-ANKER]" if s.ist_prim_anker else ""
        L.append(f"  {s.richtung:5s} bar {s.bar:4d} {s.stufe:15s} "
                 f"reclaim={s.reclaim_bar:4d} entry={s.entry_bar:4d} "
                 f"an K{s.kid:3d} basis={s.basis:.3f} "
                 f"sweep={s.sweep:.3f} close={s.trigger_close:.3f} | "
                 f"E={s.entry:.3f} SL={s.sl:.3f} TP1(POC)={s.poc:.3f} "
                 f"TP2={s.tp2:.3f} | H1={s.grund1:4s}@{s.exit1_bar} | "
                 f"{s.resultat:8s} {s.r:+6.2f}R{anker}")
    L.append(f"  Ablehnungen: kein_Gegner={stats['kein_gegner']} "
             f"F3={stats['f3']} Blocker={stats['blocker']} "
             f"Zyklus={stats['zyklus_blockiert']} "
             f"Quartil={stats['quartil_blockiert']} "
             f"kein_Raum={stats['kein_raum']} "
             f"Stacking={stats.get('stacking_blockiert', 0)} "
             f"R21={sum(1 for _r in (scan.get('r21_geloescht') or [])
                        if _r[1] >= 0)}")
    L.append(f"  Promovierte Primaer-Anker: {stats.get('promotionen', 0)}")
    zl = stats.get("zyklus_liste") or []
    if zl:
        L.append("")
        L.append("  ZYKLUS-GESPERRTE SETUPS (Retest < retest_zyklus_bars an derselben Kante):")
        for zeile in zl:  # type: ignore[union-attr]
            L.append(f"    {zeile}")
    ql = stats.get("quartil_liste") or []
    if ql:
        L.append("")
        L.append("  QUARTIL-GESPERRTE SETUPS (Niemandsland, ausserhalb des aeusseren Quartils):")
        for zeile in ql:  # type: ignore[union-attr]
            L.append(f"    {zeile}")
    bl = stats.get("blocker_liste") or []
    if bl:
        L.append("")
        L.append("  BLOCKER-GESPERRTE SETUPS (unerreichte Aussenwand in Schlagdistanz, <= 0.75 %):")
        for zeile in bl:  # type: ignore[union-attr]
            L.append(f"    {zeile}")
    L.append("")
    sl = stats.get("stacking_liste") or []
    if sl:
        L.append("")
        L.append("  STACKING-GESPERRTE SETUPS (§7.1 B):")
        for zeile in sl:  # type: ignore[union-attr]
            L.append(f"    {zeile}")
    _r21l = scan.get("r21_geloescht") or []
    if _r21l:
        L.append("")
        L.append("  R21-BEREINIGTE KANTEN & TOMBSTONES (§7.2 Teil 5):")
        L.append(f"    geloescht: {sum(1 for r in _r21l if r[1] >= 0)} | "
                 f"Geburten gesperrt: "
                 f"{sum(1 for r in _r21l if r[1] < 0)} | "
                 f"Tombstones: {len(scan.get('tombstones') or [])}")
        for zeile in _r21l:  # type: ignore[union-attr]
            if zeile[1] >= 0:
                L.append(f"    bar {zeile[0]:4d} K{zeile[1]:3d} "
                         f"{zeile[2]:5s} basis={zeile[3]:.3f} "
                         f"pivot={zeile[4]} alter={zeile[5]}")
            else:
                L.append(f"    bar {zeile[0]:4d} GEBURT GESPERRT "
                         f"{zeile[2]:5s} px={zeile[3]:.3f}")
    txt = "\n".join(L)
    print(txt)
    if nach_datei:
        pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            f"tmp_v3_straight_edge_harness_{fenster}.txt")
        with open(pfad, "w", encoding="utf-8") as f:
            f.write(txt + "\n")
        print(f"TXT geschrieben: {pfad}")
    return txt


def _zeichne_se_png(fenster: FensterTyp, scan: Dict, setups: List[_SESetup],
                    dpi: int = 300) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    band = scan["band_pct"]
    box_end = scan["box_end_bar"]
    d = scan["d"]
    n = scan["n"]
    ts = pd.to_datetime(d["ts"])
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    idx = np.arange(n)
    out = ROOT / "test" / f"kanten_engine_trades_{fenster}_mC.png"

    box_edges = [e for e in scan["edges"]
                 if any(b <= box_end - 1 for b, _ in e.wicks)]
    box_edges.sort(key=lambda e: e.basis)

    fig, (ax1, axs) = plt.subplots(
        2, 1, figsize=(18, 12),
        gridspec_kw={"height_ratios": [3.6, 1.6], "hspace": 0.12})

    ax1.plot(idx, cl, color="#1f77b4", lw=0.8, alpha=0.9, zorder=2)
    ax1.axvspan(0, box_end, color="gray", alpha=0.10, zorder=1)
    ax1.axvline(box_end, color="black", lw=1.2, ls=":", alpha=0.7)
    for e in box_edges:
        col = "#d62728" if e.seite == "OBEN" else "#2ca02c"
        ls = "-" if e.seite == "OBEN" else "--"
        b_first = min(b for b, _ in e.wicks if b <= box_end - 1)
        b_last = max(b for b, _ in e.wicks if b <= box_end - 1)
        x0 = max(0, b_first - 20)
        x1 = min(n - 1, b_last + 20)
        ax1.plot(np.arange(x0, x1 + 1), np.full(x1 - x0 + 1, e.basis),
                 color=col, lw=1.2, ls=ls, alpha=0.5, zorder=3)
    for (b, _se, px, _ref, _d) in scan["sweep_sperren"]:
        ax1.plot(b, px, "x", ms=8, color="red", zorder=6, mec="black", mew=0.3)
    for e in scan["seeds"]:
        if e.ist_prim_anker:
            ax1.axhline(e.basis, color="#d62728", lw=1.8, ls="-.",
                        alpha=0.85, zorder=5)
        elif e.letzter_bar <= box_end - 1:
            ax1.plot(e.letzter_bar, e.basis, "x", ms=5, color="gray", zorder=5)
    for s in setups:
        col = "#d62728" if s.richtung == "SHORT" else "#2ca02c"
        ax1.plot(s.bar, s.basis, "o", ms=7, color=col, zorder=6, mec="black",
                 mew=0.4)
        ax1.plot([s.bar, s.bar], [s.tp2, s.sl], color=col, lw=1.0, alpha=0.35,
                 ls=":", zorder=4)
    ticks = np.linspace(0, n - 1, 9).astype(int)
    ax1.set_xticks(ticks)
    ax1.set_xticklabels([ts.iloc[i].strftime("%d.%m") for i in ticks],
                        fontsize=8)
    ax1.set_title(f"V3-STRAIGHT-EDGE-HARNESS {fenster} | SE_BAND {band:.3f}% | "
                  "Box 10.08-18.08 | Sweep-Immunitaet (a771e04) | V-S-Trades "
                  "(Kreise) mit SL-TP2-Range", fontsize=11)
    ax1.set_xlim(-5, n + 5)

    axs.axis("off")
    z = []
    z.append(f"SE-Kanten {len(scan['edges'])} (OBEN "
             f"{sum(1 for e in scan['edges'] if e.seite=='OBEN')}) | "
             f"Seeds {len(scan['seeds'])} | Sweep-Sperren "
             f"{len(scan['sweep_sperren'])} | K33/K36: "
             f"{any(b==229 for b,*_ in scan['sweep_sperren'])}/"
             f"{any(b==242 for b,*_ in scan['sweep_sperren'])}")
    z.append(f"V-S-Trades (Box): {len(setups)}")
    gew = sum(1 for s in setups if s.resultat == "GEWONNEN")
    verl = sum(1 for s in setups if s.resultat == "VERLOREN")
    sum_r = sum(s.r for s in setups)
    z.append(f"GEWONNEN {gew} | VERLOREN {verl} | Summe R {sum_r:+.2f}")
    # --- SICHTPRUEFUNGS-KONVENTION (verankert 2026-09-09) -------------
    # Anwender-Vorgabe: Statistik MITTIG im Panel, Legende OBEN LINKS
    # im Chart. Gilt fuer alle Sichtpruefungs-Grafiken.
    axs.text(0.5, 0.97, "\n".join(z), fontsize=10, va="top",
             ha="center",
             family="monospace", transform=axs.transAxes)
    leg = [Line2D([0], [0], color="#d62728", lw=1.2, label="OBEN-Kante (SE)"),
           Line2D([0], [0], color="#2ca02c", ls="--", lw=1.2,
                  label="UNTEN-Kante (SE)"),
           Line2D([0], [0], marker="o", color="w", mfc="#d62728",
                  label="SHORT-Trade"),
           Line2D([0], [0], marker="o", color="w", mfc="#2ca02c",
                  label="LONG-Trade"),
           Line2D([0], [0], marker="x", color="w", mfc="red",
                  label="Sweep-Sperre"),
           Line2D([0], [0], marker="x", color="w", mfc="gray",
                  label="Singleton-Seed")]
    # Konvention: Legende OBEN LINKS (Sichtpruefung, 2026-09-09)
    ax1.legend(handles=leg, loc="upper left", fontsize=8,
               framealpha=0.92)
    fig.savefig(out, dpi=dpi)
    plt.close(fig)
    return out


def _replay_c_se_main(fenster: FensterTyp,
                      cfg: Optional[StraightEdgeHarnessKonfiguration] = None,
                      dpi: int = 300) -> Dict:
    """Orchestriert den SE-Harness-Lauf (Schritt C): Scan -> Trades -> Report.

    Fuehrt den arretierten Straight-Edge-Scan (Sweep-Immunitaet inklusive),
    die Regel-2-Trade-Pass und den Report aus; schreibt TXT + PNG
    (kanten_engine_trades_{fenster}_mC.png, 300 dpi). Rueckgabe-Dict mit
    scan/setups/stats fuer die Terminal-Zusammenfassung.
    """
    if cfg is None:
        cfg = StraightEdgeHarnessKonfiguration()
    scan = _se_scan(fenster, cfg)
    setups, stats = _se_trades(scan, cfg)
    _se_report(fenster, scan, setups, stats, nach_datei=True)
    out_png = _zeichne_se_png(fenster, scan, setups, dpi=dpi)
    print(f"PNG geschrieben: {out_png} (300 dpi)")
    return dict(scan=scan, setups=setups, stats=stats, cfg=cfg)


# _SE_CONTINUE_


# ==============================================================================
# REPLAY (kausal-sequentieller Bar-Loop)
# ==============================================================================


def _replay(fenster: FensterTyp, cfg: HarnessKonfiguration) -> _ReplayErgebnis:
    """Einzellauf eines Fensters mit gegebener Konfiguration (Schritt 0).

    Pro Iteration k (Entscheidungsstand nach close[k]):
      S1 Pivot m=k-2 bestaetigen (Touch/Geburt)   S2 2-Body-Bruch -> SCHLAFEND
      S3 Verfall (max_tage)                       S4 in_bar-Scan (Entry k+1)
      S5 next_bar-Abgleich (Sweeps von k-1)       S6 Merkliste fuer k fuellen
    """
    t0 = time.perf_counter()
    d = _lade_fenster(fenster)
    n = len(d)
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    op = d["open"].to_numpy(dtype=float)
    vol = d["tick_volume"].to_numpy(dtype=float)
    ts_vals = d["ts"].to_numpy()

    modus_b = cfg.modus == "B"
    kanten: Dict[int, _Kante] = {}
    merkposten: List[_ZonenMerkposten] = []   # nur Modus B (Cluster, §5.1)
    diagnose: List[str] = []                  # nur Modus B (Kanten-Genese)
    stat: Dict[str, int] = {}
    pending: List[Tuple[int, SignalRichtung, int]] = []  # (sweep_bar, richtung, kid)
    signale: List[_Signal] = []
    sweeps_ohne_reclaim = 0
    nextbar_reclaim_ok = 0
    nextbar_gate_abgelehnt = 0
    nextbar_ablehnung: Dict[str, int] = {}
    last_ref: Dict[str, Dict] = {
        "H": {"bar": -1, "preis": 0.0, "kanten_ereignis": False},
        "L": {"bar": -1, "preis": 0.0, "kanten_ereignis": False},
    }

    for k in range(n):
        # --- S1: Pivot von m = k-2 (2-Bar-Puffer, P1) ---
        m = k - PIVOT_LOOKBACK
        if m >= 2:
            typ = _pivot_typ(hi, lo, m)
            if typ is not None:
                if modus_b:
                    _b_verarbeite_pivot(m, typ, hi, lo, vol, ts_vals, kanten,
                                        merkposten, last_ref, cfg, stat,
                                        diagnose)
                else:
                    _verarbeite_pivot(m, typ, hi, lo, vol, ts_vals, kanten,
                                      last_ref)

        # --- S2: 2-Body-Bruch (Koerper k-1, k) + (B) Body-Reclaim ---
        if modus_b:
            _body_bruch(kanten, k, op, cl, nutze_anker=True)
            if cfg.body_reclaim_reaktivierung:
                nr = _b_body_reclaim(kanten, k, cl)
                if nr:
                    stat["body_reclaims"] = stat.get("body_reclaims", 0) + nr
        else:
            _body_bruch(kanten, k, op, cl)

        # --- S3: Verfall (max_tage ab letztem Touch) ---
        _verfall(kanten, pd.Timestamp(ts_vals[k]), cfg.max_tage)
        # --- S3b (B): Merkposten-Grace-Verfall (rollierende 96 Bars) ---
        if modus_b:
            for seed in list(merkposten):
                if seed.ist_abgelaufen(k, cfg.grace_periode_bars):
                    merkposten.remove(seed)
                    stat["merkposten_verfallen_zeit"] = stat.get(
                        "merkposten_verfallen_zeit", 0) + 1
                    if len(diagnose) < 600:
                        diagnose.append(
                            f"{pd.Timestamp(ts_vals[k]):%m-%d %H:%M} "
                            f"MERKPOSTEN_VERFALLEN_ZEIT bar {k:4d} "
                            f"{seed.seite} anker={seed.anker_extremum:8.3f}")

        if k > n - 2:
            continue  # kein Entry open[k+1] mehr moeglich

        # --- S4: in_bar-Scan (Sweep + Reclaim in Bar k) ---
        if modus_b:
            ks = _b_waehle_einstiegskante(kanten, "SHORT", hi[k])
            if ks is not None and cl[k] <= ks.anker_extremum:
                sig = _b_pruefe_und_erzeuge(d, kanten, k, ks, "SHORT", k, cfg)
                if sig is not None:
                    signale.append(sig)
            kl_ = _b_waehle_einstiegskante(kanten, "LONG", lo[k])
            if kl_ is not None and cl[k] >= kl_.anker_extremum:
                sig = _b_pruefe_und_erzeuge(d, kanten, k, kl_, "LONG", k, cfg)
                if sig is not None:
                    signale.append(sig)
        else:
            ks = _waehle_einstiegskante(kanten, "SHORT", hi[k])
            if ks is not None and cl[k] <= ks.balance_preis:
                sig = _pruefe_und_erzeuge(d, kanten, k, ks, "SHORT", k, cfg)
                if sig is not None:
                    signale.append(sig)
            kl_ = _waehle_einstiegskante(kanten, "LONG", lo[k])
            if kl_ is not None and cl[k] >= kl_.balance_preis:
                sig = _pruefe_und_erzeuge(d, kanten, k, kl_, "LONG", k, cfg)
                if sig is not None:
                    signale.append(sig)

        # --- S5: next_bar-Abgleich (pending stammt von Bar k-1) ---
        for sweep_bar, richtung, kid in pending:
            kante = kanten.get(kid)
            if kante is None or not kante.ist_handelbar:
                continue
            ref_p = (kante.anker_extremum if modus_b else kante.balance_preis)
            if richtung == "SHORT":
                ok = hi[sweep_bar] > ref_p and cl[k] <= ref_p
            else:
                ok = lo[sweep_bar] < ref_p and cl[k] >= ref_p
            if ok:
                nextbar_reclaim_ok += 1
                if modus_b:
                    sig = _b_pruefe_und_erzeuge(
                        d, kanten, k, kante, richtung, sweep_bar, cfg,
                        ablehnung=nextbar_ablehnung,
                    )
                else:
                    sig = _pruefe_und_erzeuge(
                        d, kanten, k, kante, richtung, sweep_bar, cfg,
                        ablehnung=nextbar_ablehnung,
                    )
                if sig is not None:
                    signale.append(sig)
                else:
                    nextbar_gate_abgelehnt += 1
        pending.clear()

        # --- S6: Sweeps ohne in_bar-Reclaim merken (fuer Abgleich bei k+1) ---
        if modus_b:
            ks = _b_waehle_einstiegskante(kanten, "SHORT", hi[k])
            if ks is not None and cl[k] > ks.anker_extremum:
                pending.append((k, "SHORT", ks.kanten_id))
                sweeps_ohne_reclaim += 1
            kl_ = _b_waehle_einstiegskante(kanten, "LONG", lo[k])
            if kl_ is not None and cl[k] < kl_.anker_extremum:
                pending.append((k, "LONG", kl_.kanten_id))
                sweeps_ohne_reclaim += 1
        else:
            ks = _waehle_einstiegskante(kanten, "SHORT", hi[k])
            if ks is not None and cl[k] > ks.balance_preis:
                pending.append((k, "SHORT", ks.kanten_id))
                sweeps_ohne_reclaim += 1
            kl_ = _waehle_einstiegskante(kanten, "LONG", lo[k])
            if kl_ is not None and cl[k] < kl_.balance_preis:
                pending.append((k, "LONG", kl_.kanten_id))
                sweeps_ohne_reclaim += 1

    signale.sort(key=lambda s: (s.ts, s.richtung))
    n_oben = sum(1 for k2 in kanten.values() if k2.seite == "OBEN")
    n_unten = sum(1 for k2 in kanten.values() if k2.seite == "UNTEN")
    n_typ_b = sum(1 for k2 in kanten.values() if k2.ist_typ_b)
    n_verf = sum(1 for k2 in kanten.values() if k2.zustand == "VERFALLEN")
    laufzeit = time.perf_counter() - t0
    return _ReplayErgebnis(
        fenster=fenster, cfg=cfg, n_bars=n, laufzeit_s=laufzeit,
        kanten_geboren=len(kanten), kanten_oben=n_oben, kanten_unten=n_unten,
        kanten_typ_b=n_typ_b, kanten_verfallen=n_verf, signale=signale,
        sweeps_ohne_reclaim=sweeps_ohne_reclaim,
        nextbar_reclaim_ok=nextbar_reclaim_ok,
        nextbar_gate_abgelehnt=nextbar_gate_abgelehnt,
        nextbar_ablehnung=nextbar_ablehnung,
        kanten=kanten,
        diagnose=diagnose,
        cluster_geburten=stat.get("cluster_geburten", 0),
        swing_geburten=stat.get("swing_geburten", 0),
        neue_merkposten=stat.get("neue_merkposten", 0),
        merkposten_verfallen_zeit=stat.get("merkposten_verfallen_zeit", 0),
        merkposten_verfallen_schwung=stat.get("merkposten_verfallen_schwung", 0),
        ratchet_abgelehnt=stat.get("ratchet_abgelehnt", 0),
        body_reclaims=stat.get("body_reclaims", 0),
    )


# ==============================================================================
# REPORT
# ==============================================================================


def _pf_txt(pf: float) -> str:
    if pf == float("inf"):
        return "   inf"
    return f"{pf:6.2f}"


def _report(erg: _ReplayErgebnis, nach_datei: bool = True) -> None:
    fe = erg.fenster_ergebnis()
    start, ende = FENSTER[erg.fenster]
    n_long = sum(1 for s in erg.signale if s.richtung == "LONG")
    n_short = len(erg.signale) - n_long
    neutral = sum(1 for s in erg.signale
                  if s.trade is not None and s.trade.resultat == "NEUTRAL")
    entschieden = fe.trades_gesamt - neutral
    lines: List[str] = []
    lines.append("")
    lines.append("=" * 104)
    modus_txt = "Modus A (Balance-VWAP)" if erg.cfg.modus == "A" else \
        "Modus B (Extremum-Ratchet)"
    lines.append(
        f"=== KANTEN-ENGINE-REPLAY: {erg.fenster} ({start} .. {ende}) | "
        f"max_tage={fe.max_tage} | {modus_txt} | {erg.laufzeit_s:5.1f}s ==="
    )
    lines.append("=" * 104)
    if erg.cfg.modus == "B":
        lines.append(
            f"Kanten-Genese B: Cluster-Geburten {erg.cluster_geburten} | "
            f"Swing-Geburten {erg.swing_geburten} | neue Merkposten "
            f"{erg.neue_merkposten} | Merkposten-Verfall Zeit/Schwung "
            f"{erg.merkposten_verfallen_zeit}/{erg.merkposten_verfallen_schwung} | "
            f"Ratchet abgelehnt {erg.ratchet_abgelehnt} | Body-Reclaims "
            f"{erg.body_reclaims}"
        )
    lines.append(
        f"Bars: {erg.n_bars} | Kanten geboren: {erg.kanten_geboren} "
        f"(OBEN {erg.kanten_oben} / UNTEN {erg.kanten_unten}) | "
        f"Typ B (>=3 Touches): {erg.kanten_typ_b} | verfallen: {erg.kanten_verfallen}"
    )
    lines.append(
        f"Signale: {fe.trades_gesamt} (LONG {n_long} / SHORT {n_short}) | "
        f"in_bar {fe.in_bar_trades} / next_bar {fe.next_bar_trades} | "
        f"entschieden: {entschieden} | NEUTRAL: {neutral}"
    )
    lines.append(
        f"Winrate: {fe.win_rate_pct:5.1f}% (nur entschieden) | "
        f"Summe R: {fe.summe_r:+8.2f} | PF: {_pf_txt(fe.profit_factor)}"
    )
    lines.append(
        f"next_bar-Diagnose: Sweeps ohne in_bar-Reclaim (Kandidaten) = "
        f"{erg.sweeps_ohne_reclaim} | Reclaim in Folge-Bar bestaetigt = "
        f"{erg.nextbar_reclaim_ok} | davon Gates abgelehnt = "
        f"{erg.nextbar_gate_abgelehnt}"
        + (f" | Gruende: {erg.nextbar_ablehnung}" if erg.nextbar_ablehnung else "")
    )
    gate_txt = "BESTANDEN" if fe.gate_bestanden else "NICHT BESTANDEN"
    if erg.fenster in ("S1", "S2"):
        lines.append(
            f"Gate (PF >= 1.30 & Summe R > 0): {gate_txt}"
            + (" | Low-n-Warnung (entschieden < 20)" if fe.low_n_warnung else "")
        )
    else:
        lines.append("Gate: (AUG nur Referenz, nicht gate-relevant)")
    lines.append("--- Signalliste ---")
    if erg.signale:
        for s in erg.signale[:MAX_SIGNAL_ZEILEN]:
            t = s.trade
            assert t is not None
            lines.append(
                f"  {s.ts:%m-%d %H:%M} {s.richtung:5s} {s.semantik:8s} "
                f"K{s.kanten_id:2d}>K{s.kanten_id_gegen:2d} "
                f"alt={s.kanten_alter_bars:4d}B tp={s.kanten_touch_anzahl} "
                f"E {s.entry_preis:7.3f} SL {s.sl_preis:7.3f} "
                f"TP1 {s.tp1_poc_preis:7.3f} TP2 {s.tp2_preis:7.3f} "
                f"CRV {s.crv_tp1:4.2f} spr {s.spread_pct:4.2f} | "
                f"{t.resultat:8s} {t.r_mult:+6.2f}R ({t.grund1}/{t.grund2})"
            )
        if len(erg.signale) > MAX_SIGNAL_ZEILEN:
            lines.append(f"  ... (+{len(erg.signale) - MAX_SIGNAL_ZEILEN} weitere)")
    else:
        lines.append("  (keine Signale)")
    if erg.cfg.modus == "B" and erg.diagnose:
        lines.append(f"--- Kanten-Genese-Diagnose (Modus B, max {MAX_DIAGNOSE_ZEILEN}) ---")
        for z in erg.diagnose[:MAX_DIAGNOSE_ZEILEN]:
            lines.append(f"  {z}")
        if len(erg.diagnose) > MAX_DIAGNOSE_ZEILEN:
            lines.append(f"  ... (+{len(erg.diagnose) - MAX_DIAGNOSE_ZEILEN} weitere)")
    lines.append("")

    txt = "\n".join(lines)
    print(txt)
    if nach_datei:
        with open(REPORT_TXT, "a", encoding="utf-8") as f:
            f.write(txt)


def _matrix_tabelle(ergebnisse: List[_ReplayErgebnis],
                    modus: Optional[EngineModus] = None) -> None:
    """Kompakte Gate-Uebersicht ueber alle Matrix-Laeufe."""
    lines: List[str] = []
    lines.append("")
    lines.append("=" * 104)
    modus_txt = f"Modus {modus}" if modus else "Modi gemischt"
    lines.append(
        f"=== KANTEN-ENGINE-MATRIX: GATE-UEBERSICHT ({modus_txt}, max_tage-Scan) ==="
    )
    lines.append("=" * 104)
    lines.append(
        f"{'Fenster':7s} {'mt':>3s} {'Sig':>4s} {'in_b':>4s} {'nxt':>4s} "
        f"{'LONG':>4s} {'SHORT':>5s} {'WR%':>5s} {'SummeR':>8s} {'PF':>6s}  Gate"
    )
    lines.append("-" * 104)
    for erg in ergebnisse:
        fe = erg.fenster_ergebnis()
        n_long = sum(1 for s in erg.signale if s.richtung == "LONG")
        n_short = len(erg.signale) - n_long
        gate_txt = (
            "BESTANDEN" if erg.fenster in ("S1", "S2") and fe.gate_bestanden
            else "referenz" if erg.fenster == "AUG"
            else "verfehlt"
        )
        lines.append(
            f"{erg.fenster:7s} {fe.max_tage:3d} {fe.trades_gesamt:4d} "
            f"{fe.in_bar_trades:4d} {fe.next_bar_trades:4d} {n_long:4d} "
            f"{n_short:5d} {fe.win_rate_pct:5.1f} {fe.summe_r:+8.2f} "
            f"{_pf_txt(fe.profit_factor)}  {gate_txt}"
        )
    lines.append("")
    txt = "\n".join(lines)
    print(txt)
    with open(REPORT_TXT, "a", encoding="utf-8") as f:
        f.write(txt)


def _vergleich_tabelle(erg_a: _ReplayErgebnis,
                       erg_b: _ReplayErgebnis) -> None:
    """Side-by-Side A|B|Delta je Fenster (Kernkennzahlen, §8.1).

    Wird bei --modus BEIDE direkt im Terminal ausgegeben und an den
    Report-TXT angehaengt.
    """
    fa = erg_a.fenster_ergebnis()
    fb = erg_b.fenster_ergebnis()
    n_long_a = sum(1 for s in erg_a.signale if s.richtung == "LONG")
    n_long_b = sum(1 for s in erg_b.signale if s.richtung == "LONG")

    def _gate(fe: FensterErgebnis, fenster: FensterTyp) -> str:
        if fenster in ("S1", "S2"):
            return "JA" if fe.gate_bestanden else "NEIN"
        return "ref"

    def _pf(pf: float) -> str:
        return "inf" if pf == float("inf") else f"{pf:.2f}"

    lines: List[str] = []
    lines.append("")
    lines.append("=" * 104)
    lines.append(
        f"=== A/B-VERGLEICH: {erg_a.fenster} (A = Balance-VWAP-V1 / "
        f"B = Extremum-Ratchet-V2) | mt {fa.max_tage} ==="
    )
    lines.append("=" * 104)
    lines.append(
        f"{'Kennzahl':22s} {'Modus A':>22s} {'Modus B':>22s} {'Delta':>12s}"
    )
    lines.append("-" * 104)
    rows = [
        ("Signale (trades)", f"{fa.trades_gesamt}",
         f"{fb.trades_gesamt}", fb.trades_gesamt - fa.trades_gesamt),
        ("davon in_bar", f"{fa.in_bar_trades}",
         f"{fb.in_bar_trades}", fb.in_bar_trades - fa.in_bar_trades),
        ("davon next_bar", f"{fa.next_bar_trades}",
         f"{fb.next_bar_trades}", fb.next_bar_trades - fa.next_bar_trades),
        ("LONG / SHORT", f"{n_long_a}/{fa.trades_gesamt - n_long_a}",
         f"{n_long_b}/{fb.trades_gesamt - n_long_b}", ""),
        ("Winrate %", f"{fa.win_rate_pct:5.1f}",
         f"{fb.win_rate_pct:5.1f}", fb.win_rate_pct - fa.win_rate_pct),
        ("Summe R", f"{fa.summe_r:+8.2f}", f"{fb.summe_r:+8.2f}",
         fb.summe_r - fa.summe_r),
        ("Profit Factor", f"{_pf(fa.profit_factor):>8s}",
         f"{_pf(fb.profit_factor):>8s}",
         (fb.profit_factor - fa.profit_factor
          if fa.profit_factor != float("inf")
          and fb.profit_factor != float("inf") else "")),
        ("Gate bestanden", _gate(fa, erg_a.fenster),
         _gate(fb, erg_b.fenster), ""),
    ]
    for name, va, vb, delta in rows:
        if delta == "":
            lines.append(f"{name:22s} {va:>22s} {vb:>22s} {'':>12s}")
        elif isinstance(delta, str):
            lines.append(f"{name:22s} {va:>22s} {vb:>22s} {delta:>12s}")
        elif isinstance(delta, float):
            lines.append(f"{name:22s} {va:>22s} {vb:>22s} {delta:+12.2f}")
        else:
            lines.append(f"{name:22s} {va:>22s} {vb:>22s} {delta:+12d}")
    lines.append(
        f"{'Kanten geboren':22s} {erg_a.kanten_geboren:>22d} "
        f"{erg_b.kanten_geboren:>22d} "
        f"{erg_b.kanten_geboren - erg_a.kanten_geboren:+12d}"
    )
    lines.append(
        f"{'Typ-B-Kanten':22s} {erg_a.kanten_typ_b:>22d} "
        f"{erg_b.kanten_typ_b:>22d} "
        f"{erg_b.kanten_typ_b - erg_a.kanten_typ_b:+12d}"
    )
    lines.append("")
    txt = "\n".join(lines)
    print(txt)
    with open(REPORT_TXT, "a", encoding="utf-8") as f:
        f.write(txt)


# ==============================================================================
# REPORT / MODUS C (Spez §8.4 C-Gate: je Fenster genau 1 Durchlauf, statisch)
# ==============================================================================


def _c_kennzahlen(erg_c: _ReplayErgebnisC) -> Dict[str, float]:
    """Aggregation der C-Trades (gleiche Gate-Formel wie §8.2/§8.4)."""
    trades = [s for s in erg_c.signale if s.trade is not None]
    n_in = sum(1 for s in trades if s.semantik == "in_bar")
    n_nx = len(trades) - n_in
    n_long = sum(1 for s in trades if s.richtung == "LONG")
    n_short = len(trades) - n_long
    gew = sum(1 for t in trades
              if t.trade is not None and t.trade.resultat == "GEWONNEN")
    verl = sum(1 for t in trades
               if t.trade is not None and t.trade.resultat == "VERLOREN")
    neutral = len(trades) - gew - verl
    entschieden = gew + verl
    sum_r = sum(t.trade.r_mult for t in trades if t.trade is not None)
    sum_pos = sum(t.trade.r_mult for t in trades
                  if t.trade is not None and t.trade.r_mult > 1e-9)
    sum_neg = sum(-t.trade.r_mult for t in trades
                  if t.trade is not None and t.trade.r_mult < -1e-9)
    if entschieden == 0:
        pf = 0.0
    elif sum_neg <= 0.0:
        pf = float("inf")
    else:
        pf = sum_pos / sum_neg
    wr = 100.0 * gew / entschieden if entschieden else 0.0
    low_n = entschieden < 20
    gate = entschieden > 0 and sum_r > 0 and pf >= 1.30
    return {
        "n": float(len(trades)),
        "in_bar": float(n_in),
        "next_bar": float(n_nx),
        "long": float(n_long),
        "short": float(n_short),
        "gewonnen": float(gew),
        "verloren": float(verl),
        "neutral": float(neutral),
        "entschieden": float(entschieden),
        "winrate": wr,
        "summe_r": sum_r,
        "pf": pf,
        "low_n": float(low_n),
        "gate": float(gate),
    }


def _c_kanten_zeilen(erg_c: _ReplayErgebnisC,
                     max_zeilen: int = 80) -> List[str]:
    """Kanten-Diagnose (>= 2 Touches) mit Geburt/Touch-Bars fuer den Report."""
    reif = sorted([k2 for k2 in erg_c.kanten.values()
                   if k2.touch_anzahl >= 2], key=lambda k2: (k2.seite, k2.basis_preis))
    out: List[str] = []
    for k2 in reif[:max_zeilen]:
        endstatus = k2.status
        out.append(
            f"  K{k2.kanten_id:3d} {k2.seite:5s} basis={k2.basis_preis:8.3f} "
            f"geburt={k2.geburts_bar:4d} status={endstatus:8s} "
            f"touche={k2.touch_anzahl} bars={k2.touch_bars}"
        )
    if len(reif) > max_zeilen:
        out.append(f"  ... (+{len(reif) - max_zeilen} weitere, >= 2 Touches)")
    return out


def _report_c(erg_c: _ReplayErgebnisC, nach_datei: bool = True) -> None:
    """Terminal-/Datei-Report eines Modus-C-Laufs (V3, statisch)."""
    kz = _c_kennzahlen(erg_c)
    start, ende = FENSTER[erg_c.fenster]
    cfg = erg_c.cfg
    kanten = list(erg_c.kanten.values())
    n_oben = sum(1 for k2 in kanten if k2.seite == "OBEN")
    n_unten = len(kanten) - n_oben
    n_typ_a = sum(1 for k2 in kanten if k2.ist_gueltiges_kursziel_typ_a)
    n_typ_b = sum(1 for k2 in kanten if k2.ist_handelbar_typ_b or k2.touch_anzahl >= 3)

    lines: List[str] = []
    lines.append("")
    lines.append("=" * 116)
    lines.append(
        f"=== KANTEN-ENGINE-REPLAY (Modus C / V3 statisch): {erg_c.fenster} "
        f"({start} .. {ende}) | touch_band {cfg.touch_band_pct:.2f} | "
        f"geburts_sperr {V3_GEBURTS_SPERR_PCT:.2f} | abstand "
        f"{cfg.min_touch_bar_abstand} | tp_mindist {cfg.tp_mindist_pct:.1f} | "
        f"sl_buffer {cfg.sl_buffer_usd:.2f} | split {cfg.tp1_anteil_pct:.0f}/"
        f"{100.0 - cfg.tp1_anteil_pct:.0f} | next_bar="
        f"{'an' if cfg.erlaube_next_bar else 'aus'} | {erg_c.laufzeit_s:5.1f}s ==="
    )
    lines.append("=" * 116)
    lines.append(
        f"Bars: {erg_c.n_bars} | Kanten geboren: {len(kanten)} "
        f"(OBEN {n_oben} / UNTEN {n_unten}) | Typ A (>=2 Touches): {n_typ_a} | "
        f"Typ B (>=3 Touches): {n_typ_b}"
    )
    lines.append(
        f"Genese-Verwerfungen: Ring-Zwischenwellen (0.23-0.50%) "
        f"{erg_c.ablehnung.get('ring_zwischenwelle', 0)} | "
        f"Band-Touch am Mindestabstand verworfen "
        f"{erg_c.ablehnung.get('band_abstand_verworfen', 0)}"
    )
    lines.append(
        f"Signale: {kz['n']:.0f} (LONG {kz['long']:.0f} / SHORT {kz['short']:.0f}) "
        f"| in_bar {kz['in_bar']:.0f} / next_bar {kz['next_bar']:.0f} | "
        f"GEWONNEN {kz['gewonnen']:.0f} / VERLOREN {kz['verloren']:.0f} / "
        f"NEUTRAL {kz['neutral']:.0f}"
    )
    lines.append(
        f"Winrate: {kz['winrate']:5.1f}% (nur entschieden) | "
        f"Summe R: {kz['summe_r']:+8.2f} | PF: {_pf_txt(kz['pf'])}"
    )
    if erg_c.ablehnung:
        lines.append(f"Gate-Ablehnungen (Signale): {erg_c.ablehnung}")
    if cfg.erlaube_next_bar:
        lines.append(
            f"next_bar-Diagnose: Sweeps ohne in_bar-Reclaim = "
            f"{erg_c.sweeps_ohne_reclaim} | Reclaim in Folge-Bar = "
            f"{erg_c.nextbar_reclaim_ok} | davon Gates abgelehnt = "
            f"{erg_c.nextbar_abgelehnt}"
        )
    if erg_c.fenster in ("S1", "S2"):
        gate_txt = "BESTANDEN" if kz["gate"] else "NICHT BESTANDEN"
        lines.append(
            f"C-Gate (PF >= 1.30 & Summe R > 0): {gate_txt}"
            + (f" | Low-n-Warnung (entschieden < 20)" if kz["low_n"] else "")
        )
    else:
        lines.append("C-Gate: (AUG nur Referenz, nicht gate-relevant)")

    lines.append("--- Kanten (>= 2 Touches) ---")
    kz_zeilen = _c_kanten_zeilen(erg_c)
    if kz_zeilen:
        lines.extend(kz_zeilen)
    else:
        lines.append("  (keine Kante mit >= 2 Touches)")
    lines.append("--- Signalliste ---")
    if erg_c.signale:
        for s in erg_c.signale[:MAX_SIGNAL_ZEILEN]:
            t = s.trade
            assert t is not None
            tp2_txt = f"{s.tp2_preis:7.3f}" if s.tp2_preis is not None else "    -  "
            lines.append(
                f"  {s.ts:%m-%d %H:%M} {s.richtung:5s} {s.semantik:8s} "
                f"K{s.kanten_id:2d} basis={s.basis_preis:8.3f} tp={s.touch_anzahl} "
                f"E {s.entry_preis:7.3f} SL {s.sl_preis:7.3f} "
                f"TP1 {s.tp1_preis:7.3f} TP2 {tp2_txt} "
                f"spr {s.dist_gegen_pct:4.2f} | "
                f"{t.resultat:8s} {t.r_mult:+6.2f}R ({t.grund1}/{t.grund2})"
            )
        if len(erg_c.signale) > MAX_SIGNAL_ZEILEN:
            lines.append(
                f"  ... (+{len(erg_c.signale) - MAX_SIGNAL_ZEILEN} weitere)")
    else:
        lines.append("  (keine Signale)")
    lines.append("")

    txt = "\n".join(lines)
    print(txt)
    if nach_datei:
        with open(REPORT_TXT, "a", encoding="utf-8") as f:
            f.write(txt)


def _c_gate_tabelle(ergebnisse: List[_ReplayErgebnisC]) -> None:
    """C-Gate-Uebersicht (§8.4): je Fenster 1 Durchlauf + S1/S2-Gesamturteil."""
    lines: List[str] = []
    lines.append("")
    lines.append("=" * 116)
    lines.append("=== MODUS-C-GATE (§8.4): je Fenster genau 1 Lauf (statisch, "
                 "kein max_tage-Grid) ===")
    lines.append("=" * 116)
    lines.append(
        f"{'Fenster':7s} {'Bars':>5s} {'Sig':>4s} {'in_b':>4s} {'nxt':>4s} "
        f"{'LONG':>4s} {'SHORT':>5s} {'WR%':>5s} {'SummeR':>8s} {'PF':>6s}  Gate"
    )
    lines.append("-" * 116)
    s_gate: List[str] = []
    for erg in ergebnisse:
        kz = _c_kennzahlen(erg)
        if erg.fenster in ("S1", "S2"):
            gate_txt = "BESTANDEN" if kz["gate"] else "verfehlt"
            s_gate.append(erg.fenster if kz["gate"] else f"{erg.fenster}!")
        elif erg.fenster == "AUG":
            gate_txt = "referenz"
        else:
            gate_txt = "-"
        low = " (low-n)" if kz["low_n"] else ""
        lines.append(
            f"{erg.fenster:7s} {erg.n_bars:5d} {kz['n']:4.0f} "
            f"{kz['in_bar']:4.0f} {kz['next_bar']:4.0f} {kz['long']:4.0f} "
            f"{kz['short']:5.0f} {kz['winrate']:5.1f} {kz['summe_r']:+8.2f} "
            f"{_pf_txt(kz['pf'])}  {gate_txt}{low}"
        )
    s1 = any(e.fenster == "S1" for e in ergebnisse)
    s2 = any(e.fenster == "S2" for e in ergebnisse)
    if s1 and s2:
        alle_ok = all(
            _c_kennzahlen(e)["gate"] for e in ergebnisse
            if e.fenster in ("S1", "S2")
        )
        urteil = ("V3-GATE §8.4 BESTANDEN (S1 UND S2)"
                  if alle_ok else "V3-GATE §8.4 VERFEHLT (Abbruch: kein Tuning)")
        lines.append("-" * 116)
        lines.append(f"  {urteil}")
    lines.append("")
    txt = "\n".join(lines)
    print(txt)
    with open(REPORT_TXT, "a", encoding="utf-8") as f:
        f.write(txt)


def _abc_vergleich_tabelle(list_a: List[_ReplayErgebnis],
                           list_b: List[_ReplayErgebnis],
                           list_c: List[_ReplayErgebnisC]) -> None:
    """A/B/C-Vergleich (--modus ALLE, §8.4): A mt60 / B mt60 / C statisch."""
    def _gate_txt(fenster: FensterTyp, gate: bool) -> str:
        if fenster in ("S1", "S2"):
            return "BESTANDEN" if gate else "verfehlt"
        return "referenz"

    def _pf(pf: float) -> str:
        return "inf" if pf == float("inf") else f"{pf:.2f}"

    lines: List[str] = []
    lines.append("")
    lines.append("=" * 128)
    lines.append(
        "=== A/B/C-VERGLEICH (--modus ALLE, §8.4): A = Balance-VWAP mt60 | "
        "B = Extremum-Ratchet mt60 | C = V3 statisch ==="
    )
    lines.append("=" * 128)
    for erg_a, erg_b, erg_c in zip(list_a, list_b, list_c):
        fa = erg_a.fenster_ergebnis()
        fb = erg_b.fenster_ergebnis()
        kc = _c_kennzahlen(erg_c)
        n_long_a = sum(1 for s in erg_a.signale if s.richtung == "LONG")
        n_long_b = sum(1 for s in erg_b.signale if s.richtung == "LONG")
        start, ende = FENSTER[erg_a.fenster]
        lines.append("")
        lines.append(f"--- {erg_a.fenster} ({start} .. {ende}) ---")
        lines.append(
            f"{'Kennzahl':22s} {'A (mt60)':>18s} {'B (mt60)':>18s} "
            f"{'C (statisch)':>18s}"
        )
        lines.append("-" * 128)
        rows = [
            ("Signale (trades)",
             f"{fa.trades_gesamt}", f"{fb.trades_gesamt}", f"{kc['n']:.0f}"),
            ("davon in_bar",
             f"{fa.in_bar_trades}", f"{fb.in_bar_trades}", f"{kc['in_bar']:.0f}"),
            ("davon next_bar",
             f"{fa.next_bar_trades}", f"{fb.next_bar_trades}",
             f"{kc['next_bar']:.0f}"),
            ("LONG / SHORT",
             f"{n_long_a}/{fa.trades_gesamt - n_long_a}",
             f"{n_long_b}/{fb.trades_gesamt - n_long_b}",
             f"{kc['long']:.0f}/{kc['short']:.0f}"),
            ("Winrate %",
             f"{fa.win_rate_pct:5.1f}", f"{fb.win_rate_pct:5.1f}",
             f"{kc['winrate']:5.1f}"),
            ("Summe R",
             f"{fa.summe_r:+8.2f}", f"{fb.summe_r:+8.2f}",
             f"{kc['summe_r']:+8.2f}"),
            ("Profit Factor",
             f"{_pf(fa.profit_factor):>8s}", f"{_pf(fb.profit_factor):>8s}",
             f"{_pf(kc['pf']):>8s}"),
            ("Gate bestanden",
             _gate_txt(erg_a.fenster, fa.gate_bestanden),
             _gate_txt(erg_b.fenster, fb.gate_bestanden),
             _gate_txt(erg_c.fenster, bool(kc["gate"]))),
        ]
        for name, va, vb, vc in rows:
            lines.append(f"{name:22s} {va:>18s} {vb:>18s} {vc:>18s}")
        n_typ_b_c = sum(1 for k2 in erg_c.kanten.values()
                        if k2.touch_anzahl >= 3)
        lines.append(
            f"{'Kanten geboren':22s} {erg_a.kanten_geboren:>18d} "
            f"{erg_b.kanten_geboren:>18d} {len(erg_c.kanten):>18d}"
        )
        lines.append(
            f"{'Typ-B-Kanten':22s} {erg_a.kanten_typ_b:>18d} "
            f"{erg_b.kanten_typ_b:>18d} {n_typ_b_c:>18d}"
        )
    lines.append("")
    txt = "\n".join(lines)
    print(txt)
    with open(REPORT_TXT, "a", encoding="utf-8") as f:
        f.write(txt)


# ==============================================================================
# PNG-CHART (300 dpi, je Testlauf)
# ==============================================================================

# Farbkonstanten (an Projekt-Chart-Konvention angelehnt)
_COL_UP: str = "#1a7a37"      # LONG / TP / positiv
_COL_DOWN: str = "#c0392b"    # SHORT
_COL_SL: str = "#c00000"      # Stop-Loss-Exit
_COL_ENDE: str = "#777777"    # Zeitende-Exit (grau)
_COL_CLOSE: str = "#111111"   # Close-Linie
_COL_KANTE_OBEN: str = "#e67e22"    # OBEN-Kante (Balance, durchgezogen)
_COL_KANTE_UNTEN: str = "#2980b9"   # UNTEN-Kante (Balance, gestrichelt)


def _balance_segmente(k: "_Kante",
                      nutze_anker: bool = False) -> List[Tuple[int, float]]:
    """Rekonstruiert die Referenz-Historie einer Kante (deterministisch).

    Modus A: simuliert exakt die _update_balance-Semantik des Replays ueber
    die chronologisch bestaetigten Touches (VWAP im +/-DENSITY_BAND).
    Modus B (nutze_anker=True): laufendes Extremum (Ratchet-Historie) -
    OBEN: running max, UNTEN: running min der Touch-Preise.

    Rueckgabe: Liste von (gueltig_ab_bar, referenz) - Schrittpunkte der Linie.
    """
    ts = sorted(k.touche, key=lambda t: t.pivot_bar)
    if not ts:
        return []
    if nutze_anker and k.anker_extremum > 0.0:
        # Modus B: Ratchet-Historie (nach aussen, nie nach innen)
        ext = ts[0].preis
        segmente: List[Tuple[int, float]] = [(ts[0].gueltig_ab_bar, ext)]
        for t in ts[1:]:
            if k.seite == "OBEN":
                ext = max(ext, t.preis)
            else:
                ext = min(ext, t.preis)
            segmente.append((t.gueltig_ab_bar, ext))
        return segmente
    bal = ts[0].preis
    segmente = [(ts[0].gueltig_ab_bar, bal)]
    akku: List[_KantenTouch] = [ts[0]]
    for t in ts[1:]:
        akku.append(t)
        relevant = [x for x in akku if abs(x.preis - bal) <= DENSITY_BAND]
        if not relevant:
            relevant = list(akku)
        v_sum = sum(x.volumen for x in relevant)
        if v_sum > 0:
            bal = sum(x.preis * x.volumen for x in relevant) / v_sum
        else:
            bal = sum(x.preis for x in relevant) / len(relevant)
        segmente.append((t.gueltig_ab_bar, bal))
    return segmente


def _crv_stats(erg: _ReplayErgebnis) -> Dict[str, float]:
    """CRV-Statistik ueber alle Trades (crv_tp1): n, min, p25, median, mean,
    p75, max, Anteil >= 1.0 in %."""
    crvs: List[float] = [s.crv_tp1 for s in erg.signale if s.trade is not None]
    if not crvs:
        return {"n": 0.0, "min": 0.0, "p25": 0.0, "median": 0.0, "mean": 0.0,
                "p75": 0.0, "max": 0.0, "ge_1_0_pct": 0.0}
    a = np.array(crvs)
    return {
        "n": float(len(a)),
        "min": float(a.min()),
        "p25": float(np.percentile(a, 25)),
        "median": float(np.median(a)),
        "mean": float(a.mean()),
        "p75": float(np.percentile(a, 75)),
        "max": float(a.max()),
        "ge_1_0_pct": float(100.0 * np.mean(a >= 1.0)),
    }


def _zeichne_trades_png(
    erg: _ReplayErgebnis,
    out_png: Path,
    dpi: int = 300,
) -> Path:
    """Rendert je Lauf ein PNG (300 dpi): nur Chart + Statistik (keine Equity).

    Layout (2 Panels):
      * ax1 oben   : Close + Trades: START (Entry ^/v), ENDE je Haelfte
                     (o=25%-Haelfte, s=75%-Haelfte; Farbe nach Grund
                     TP1/TP2 gruen, SL rot, Zeitende/ENDE grau); Linie
                     Entry -> Exit je Haelfte; Text am Trade-Ende:
                     CRV + R-Ergebnis. Legende oben links.
      * ax_stat    : Statistik-Text; CRV-Statistik in der MITTE.

    Args:
        erg: Replay-Ergebnis.
        out_png: Ziel-Pfad (z. B. test/kanten_engine_trades_AUG_mt60.png).
        dpi: Aufloesung (Default 300).

    Returns:
        out_png (geschrieben).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    d = _lade_fenster(erg.fenster)
    n = len(d)
    idx = np.arange(n)
    close = d["close"].to_numpy(dtype=float)
    ts = pd.to_datetime(d["ts"])

    fig, (ax1, ax_stat) = plt.subplots(
        2, 1, figsize=(18, 11),
        sharex=False,
        gridspec_kw={"height_ratios": [4.0, 1.25], "hspace": 0.18},
    )

    # ---- Ax1: Preis + Trades -----------------------------------------------
    ax1.plot(idx, close, color=_COL_CLOSE, lw=0.8, alpha=0.85, zorder=2,
             label="Close")
    trades = [s for s in erg.signale if s.trade is not None]
    for s in trades:
        t = s.trade
        assert t is not None
        col = _COL_UP if s.richtung == "LONG" else _COL_DOWN
        # Pfad Entry -> Exit je Haelfte (Haelfte 1 gestrichelt, Haelfte 2 voll)
        if t.exit1_bar >= 0 and t.exit1_bar != t.exit2_bar:
            ax1.plot([s.entry_bar, t.exit1_bar],
                     [s.entry_preis, t.exit1],
                     color=col, lw=0.7, ls=":", alpha=0.55, zorder=3)
        if t.exit2_bar >= 0:
            ax1.plot([s.entry_bar, t.exit2_bar],
                     [s.entry_preis, t.exit2],
                     color=col, lw=0.8, alpha=0.55, zorder=3)
        # START (Entry)
        ax1.scatter(s.entry_bar, s.entry_preis,
                    marker="^" if s.richtung == "LONG" else "v",
                    s=52, color=col, edgecolor="w", linewidths=0.4, zorder=6)
        # ENDE je Haelfte (Farbe nach Grund)
        for e_bar, e_preis, grund, mk in (
            (t.exit1_bar, t.exit1, t.grund1, "o"),
            (t.exit2_bar, t.exit2, t.grund2, "s"),
        ):
            if e_bar < 0:
                continue
            if grund in ("TP1", "TP2"):
                ec = _COL_UP
            elif grund == "SL":
                ec = _COL_SL
            else:
                ec = _COL_ENDE
            ax1.scatter(e_bar, e_preis, marker=mk, s=26, color=ec,
                        edgecolor="w", linewidths=0.3, zorder=6)

    # ---- Prio-Kanten (an Signalen beteiligte Typ-B-Kanten) als Balance-Linien
    # OBEN-Kanten durchgezogen, UNTEN-Kanten gestrichelt; Einstiegs-Kanten
    # dicker/volle Deckkraft, reine Gegenkanten dezent; Touch-Punkte als
    # kleine Eichpunkte; Linie laeuft bis Verfall (letzter Touch + max_tage)
    # bzw. Fensterende.
    ein_ids = {s.kanten_id for s in erg.signale}
    geg_ids = {s.kanten_id_gegen for s in erg.signale}
    ts_dt = d["ts"].to_numpy()  # datetime64[ns]
    max_tage = erg.cfg.max_tage
    prio_kanten_n = 0
    for kid, k2 in erg.kanten.items():
        if kid not in ein_ids and kid not in geg_ids:
            continue
        if not k2.ist_typ_b:
            continue
        segmente = _balance_segmente(k2, nutze_anker=(erg.cfg.modus == "B"))
        if not segmente:
            continue
        ende_bar = n - 1
        if k2.letzter_touch_ts is not None and max_tage > 0:
            verfall_ts = np.datetime64(k2.letzter_touch_ts) + np.timedelta64(max_tage, "D")
            idx = int(np.searchsorted(ts_dt, verfall_ts, side="left"))
            ende_bar = min(ende_bar, idx)
        x_st = [b for b, _ in segmente] + [ende_bar + 1]
        y_st = [b for _, b in segmente] + [segmente[-1][1]]
        col = _COL_KANTE_OBEN if k2.seite == "OBEN" else _COL_KANTE_UNTEN
        ls = "-" if k2.seite == "OBEN" else "--"
        ax1.plot(x_st, y_st, drawstyle="steps-post", color=col, ls=ls,
                 lw=1.3 if kid in ein_ids else 0.9,
                 alpha=0.85 if kid in ein_ids else 0.5, zorder=2.5)
        ax1.scatter([t.pivot_bar for t in k2.touche],
                    [t.preis for t in k2.touche],
                    s=7, color=col, alpha=0.5, edgecolors="none", zorder=2.6)
        prio_kanten_n += 1

    # Annotation am Trade-Ende (letzter Exit): CRV-Wert + R-Ergebnis
    # Bei > 80 Trades nur R-Kurzform (Lesbarkeit); Position alternierend
    # ueber/unter dem Exit-Marker; bei Exits am Fensterrand links daneben.
    annot_kurz = len(trades) > 80
    for i, s in enumerate(trades):
        t = s.trade
        assert t is not None
        e_bar = max(t.exit1_bar, t.exit2_bar)
        if e_bar < 0:
            continue
        e_pr = t.exit1 if t.exit1_bar >= t.exit2_bar else t.exit2
        txt = (f"{t.r_mult:+.2f}R" if annot_kurz
               else f"CRV{s.crv_tp1:.2f} {t.r_mult:+.2f}R")
        acol = (_COL_UP if t.r_mult > 1e-9
                else (_COL_DOWN if t.r_mult < -1e-9 else _COL_ENDE))
        dy = 5 if i % 2 == 0 else -14
        if e_bar > n - 8:
            ax1.annotate(txt, xy=(e_bar, e_pr), xytext=(-5, dy),
                         textcoords="offset points", ha="right", va="bottom",
                         fontsize=7 if not annot_kurz else 6, color=acol,
                         zorder=7, alpha=0.95)
        else:
            ax1.annotate(txt, xy=(e_bar, e_pr), xytext=(6, dy),
                         textcoords="offset points", ha="left", va="bottom",
                         fontsize=7 if not annot_kurz else 6, color=acol,
                         zorder=7, alpha=0.95)

    start, ende = FENSTER[erg.fenster]
    ref_txt = ("Balance VWAP (V1)" if erg.cfg.modus == "A"
               else "Extremum-Ratchet (V2)")
    ax1.set_title(
        f"KANTEN-ENGINE-REPLAY {erg.fenster}  |  {start} .. {ende} (ende-exkl.)  |  "
        f"max_tage={erg.cfg.max_tage}  |  {ref_txt}  |  {erg.laufzeit_s:.1f}s"
        + ("   [GATE BESTANDEN]" if erg.fenster_ergebnis().gate_bestanden else ""),
        fontsize=12,
    )
    ax1.set_ylabel("USD")
    ax1.grid(alpha=0.3)

    # ---- Ax_stat (Mitte): Statistik, CRV zentral ----------------------------
    ax_stat.axis("off")
    fe = erg.fenster_ergebnis()
    gew = sum(1 for t in trades if t.trade is not None and t.trade.resultat == "GEWONNEN")
    verl = sum(1 for t in trades if t.trade is not None and t.trade.resultat == "VERLOREN")
    neutral = sum(1 for t in trades
                  if t.trade is not None and t.trade.resultat == "NEUTRAL")
    n_long = sum(1 for s in erg.signale if s.richtung == "LONG")
    n_short = len(erg.signale) - n_long
    cs = _crv_stats(erg)
    n_tp1 = sum(1 for t in trades if t.trade is not None and t.trade.grund1 == "TP1")
    n_tp2 = sum(1 for t in trades if t.trade is not None and t.trade.grund2 == "TP2")
    n_sl = sum(1 for t in trades
               if t.trade is not None and (t.trade.grund1 == "SL" or t.trade.grund2 == "SL"))
    n_ende = sum(1 for t in trades
                 if t.trade is not None
                 and (t.trade.grund1 == "ENDE" or t.trade.grund2 == "ENDE"))

    pf = fe.profit_factor
    pf_txt = "inf" if pf == float("inf") else f"{pf:.2f}"
    links = (
        f"GESAMT (n={len(trades)})\n"
        f"  GEWONNEN {gew}  |  VERLOREN {verl}  |  NEUTRAL {neutral}\n"
        f"  Winrate {fe.win_rate_pct:.1f}%\n"
        f"  Summe R {fe.summe_r:+.2f}   PF {pf_txt}\n"
        f"  LONG {n_long}  |  SHORT {n_short}\n"
        f"  in_bar {fe.in_bar_trades}  |  next_bar {fe.next_bar_trades}\n"
        f"  Low-n-Warnung: {'JA' if fe.low_n_warnung else 'nein'}"
    )
    mitte = (
        f"CRV-STATISTIK (n={cs['n']:.0f})\n"
        f"  min {cs['min']:.2f}  |  p25 {cs['p25']:.2f}\n"
        f"  median {cs['median']:.2f}  |  mean {cs['mean']:.2f}\n"
        f"  p75 {cs['p75']:.2f}  |  max {cs['max']:.2f}\n"
        f"  Anteil >= 1.0: {cs['ge_1_0_pct']:.1f}%"
    )
    rechts = (
        f"EXITS\n"
        f"  TP1 (25%-Haelfte): {n_tp1}\n"
        f"  TP2 (75%-Haelfte): {n_tp2}\n"
        f"  SL-Anteile: {n_sl}\n"
        f"  Zeitende (ENDE): {n_ende}\n"
        f"  Text am Exit = CRV + R\n"
        f"KANTEN\n"
        f"  geboren {erg.kanten_geboren} (OBEN {erg.kanten_oben}/"
        f"UNTEN {erg.kanten_unten})\n"
        f"  Typ B {erg.kanten_typ_b} | verfallen {erg.kanten_verfallen}\n"
        f"  Prio-Kanten (Linien): {prio_kanten_n}"
    )
    ax_stat.text(0.01, 0.5, links, va="center", ha="left", fontsize=10,
                 family="monospace",
                 bbox=dict(boxstyle="round,pad=0.4", fc="#f4f4f4", ec="#999999"))
    ax_stat.text(0.40, 0.5, mitte, va="center", ha="left", fontsize=10,
                 family="monospace",
                 bbox=dict(boxstyle="round,pad=0.4", fc="#eaf2ea", ec="#1a7a37"))
    ax_stat.text(0.68, 0.5, rechts, va="center", ha="left", fontsize=10,
                 family="monospace",
                 bbox=dict(boxstyle="round,pad=0.4", fc="#f4f4f4", ec="#999999"))

    # ---- Zeitachse am Chart (unten) + Legende oben links ---------------------
    step: int = max(16, n // 14)
    ticks: np.ndarray = np.arange(0, n, step)
    ax1.set_xlim(-1, n)
    ax1.set_xticks(ticks)
    ax1.set_xticklabels(
        [ts[t].strftime("%a %d.%m %H:%M") for t in ticks],
        rotation=45, ha="right", fontsize=8,
    )

    legende_ax1: List[Line2D] = [
        Line2D([0], [0], color=_COL_CLOSE, lw=1.0, label="Close"),
        Line2D([0], [0], color=_COL_KANTE_OBEN, lw=1.4, ls="-",
               label="OBEN-Kante (durchgezogen)"),
        Line2D([0], [0], color=_COL_KANTE_UNTEN, lw=1.4, ls="--",
               label="UNTEN-Kante (gestrichelt)"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor=_COL_UP, ms=8,
               label="LONG-Entry (Start)"),
        Line2D([0], [0], marker="v", color="w", markerfacecolor=_COL_DOWN, ms=8,
               label="SHORT-Entry (Start)"),
        Line2D([0], [0], marker="o", color=_COL_UP, ms=6, ls="",
               label="Exit TP1 (25%-Haelfte)"),
        Line2D([0], [0], marker="s", color=_COL_UP, ms=5, ls="",
               label="Exit TP2 (75%-Haelfte)"),
        Line2D([0], [0], marker="o", color=_COL_SL, ms=6, ls="",
               label="Exit SL (rote Kreise)"),
        Line2D([0], [0], marker="o", color=_COL_ENDE, ms=6, ls="",
               label="Exit Zeitende / ENDE (grau)"),
    ]
    ax1.legend(handles=legende_ax1, loc="upper left", fontsize=8,
               framealpha=0.9, ncol=2)

    fig.subplots_adjust(left=0.055, right=0.985, top=0.95, bottom=0.09,
                        hspace=0.22)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=dpi)
    plt.close(fig)
    return out_png


def _png_pfad(erg: _ReplayErgebnis) -> Path:
    """PNG-Zielpfad je Lauf: test/kanten_engine_trades_{Fenster}_mt{mt}_m{Modus}.png."""
    return ROOT / "test" / (
        f"kanten_engine_trades_{erg.fenster}_mt{erg.cfg.max_tage}"
        f"_m{erg.cfg.modus}.png"
    )


def _png_pfad_c(erg_c: _ReplayErgebnisC) -> Path:
    """PNG-Zielpfad Modus C: test/kanten_engine_trades_{Fenster}_mC.png.

    Kein max_tage-Bestandteil (C-Gate §8.4: genau 1 Lauf je Fenster).
    """
    return ROOT / "test" / f"kanten_engine_trades_{erg_c.fenster}_mC.png"


# --- Kantenlisten-TXT (Dialog-Referenz, je Lauf frisch) ----------------------


def _kantenliste_c_txt(erg_c: _ReplayErgebnisC) -> Path:
    """Schreibt test/kanten_liste_{Fenster}_mC.txt (Dialog-Referenz, frisch).

    Alle Kanten (auch 1-Touch) chronologisch nach kanten_id (= Geburtsfolge)
    mit Basis, Geburts-Bar/-Zeitstempel, Touch-Bars, Status und Typ-Kennung.
    Fuer AUG zusaetzlich eine Soll-Ebenen-Zuordnung (66.46 / 63.67 / 64.20,
    Level-Aequivalenz = touch_band_pct 0,23) analog zum Genese-Audit, damit
    die K-IDs im Dialog direkt den Soll-Waenden zugeordnet werden koennen.

    Args:
        erg_c: Modus-C-Replay-Ergebnis (Kanten des Laufs).

    Returns:
        Pfad der geschriebenen TXT.
    """
    d = _lade_fenster(erg_c.fenster)
    ts_all = d["ts"]

    def _ts(b: int) -> str:
        if 0 <= b < len(ts_all):
            return f"{ts_all.iloc[b]:%d.%m %H:%M}"
        return "-"

    cfg = erg_c.cfg
    pfad = ROOT / "test" / f"kanten_liste_{erg_c.fenster}_mC.txt"
    start, ende = FENSTER[erg_c.fenster]
    kanten = sorted(erg_c.kanten.values(), key=lambda k2: k2.kanten_id)
    n_oben = sum(1 for k2 in kanten if k2.seite == "OBEN")
    n_unten = len(kanten) - n_oben
    n_typ_a = sum(1 for k2 in kanten if k2.ist_gueltiges_kursziel_typ_a)
    n_typ_b = sum(1 for k2 in kanten if k2.touch_anzahl >= 3)
    kz = _c_kennzahlen(erg_c)

    lines: List[str] = []
    lines.append("=" * 118)
    lines.append(f"KANTEN-LISTE (Modus C / V3 statisch) | Fenster {erg_c.fenster} "
                 f"({start} .. {ende})")
    lines.append("=" * 118)
    lines.append(f"Parameter: touch_band_pct {cfg.touch_band_pct:.2f} | "
                 f"geburts_sperr_pct {V3_GEBURTS_SPERR_PCT:.2f} | "
                 f"min_touch_abstand {cfg.min_touch_bar_abstand} | "
                 f"tp_mindist_pct {cfg.tp_mindist_pct:.1f} | "
                 f"sl_buffer_usd {cfg.sl_buffer_usd:.2f} | "
                 f"tp1_anteil_pct {cfg.tp1_anteil_pct:.0f} | "
                 f"next_bar-Split {'an' if cfg.erlaube_next_bar else 'aus'}")
    lines.append(f"Bars: {erg_c.n_bars} | Kanten gesamt: {len(kanten)} "
                 f"(OBEN {n_oben} / UNTEN {n_unten}) | Typ A (>=2): {n_typ_a} | "
                 f"Typ B (>=3): {n_typ_b} | Ring-Verwerfungen: "
                 f"{erg_c.ablehnung.get('ring_zwischenwelle', 0)}")
    lines.append(f"Signale: {kz['n']:.0f} (LONG {kz['long']:.0f} / "
                 f"SHORT {kz['short']:.0f}) | Summe R {kz['summe_r']:+.2f} | "
                 f"PF {_pf_txt(kz['pf'])}")
    lines.append("")
    lines.append("--- KANTEN (alle, chronologisch nach kanten_id) ---")
    for k2 in kanten:
        typ = ("B" if k2.touch_anzahl >= 3
               else ("A" if k2.touch_anzahl >= 2 else "-"))
        band = ""
        if erg_c.fenster == "AUG":
            for name, seite, soll in (
                ("UPPER 66.46", "OBEN", 66.46),
                ("LOWER-MAIN 63.67", "UNTEN", 63.67),
                ("LOWER-MINOR 64.20", "UNTEN", 64.20),
            ):
                if (k2.seite == seite
                        and abs(k2.basis_preis - soll) / soll * 100.0
                        <= cfg.touch_band_pct):
                    band += f"   <== ~{name}"
        lines.append(
            f"K{k2.kanten_id:3d} {k2.seite:5s} basis={k2.basis_preis:8.3f} "
            f"geb={k2.geburts_bar:4d} ({_ts(k2.geburts_bar)}) "
            f"status={k2.status:8s} typ={typ} touch={k2.touch_anzahl:2d} "
            f"bars={k2.touch_bars}{band}"
        )
    if erg_c.fenster == "AUG":
        lines.append("")
        lines.append("--- SOLL-EBENEN-ZUORDNUNG (AUG, Band-Aequivalenz <= "
                     f"{cfg.touch_band_pct:.2f} %) ---")
        for name, seite, soll in (
            ("UPPER 66.46", "OBEN", 66.46),
            ("LOWER-MAIN 63.67", "UNTEN", 63.67),
            ("LOWER-MINOR 64.20", "UNTEN", 64.20),
        ):
            match = [k2 for k2 in kanten if k2.seite == seite
                     and abs(k2.basis_preis - soll) / soll * 100.0
                     <= cfg.touch_band_pct]
            match.sort(key=lambda k2: (abs(k2.basis_preis - soll),
                                       k2.kanten_id))
            lines.append(f"[{name}] ({seite}, Soll-Anker {soll:.2f}) -> "
                         f"{len(match)} Kante(n) im Band:")
            for k2 in match:
                dist = abs(k2.basis_preis - soll) / soll * 100.0
                lines.append(
                    f"    K{k2.kanten_id:3d} basis={k2.basis_preis:8.3f} "
                    f"(dist {dist:5.3f}%) geb={k2.geburts_bar:4d} "
                    f"status={k2.status:8s} touch={k2.touch_anzahl:2d} "
                    f"bars={k2.touch_bars}")
    lines.append("")
    txt = "\n".join(lines)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"  Kantenliste TXT: {pfad}")
    return pfad


def _kantenliste_ab_txt(erg: _ReplayErgebnis) -> Path:
    """Schreibt test/kanten_liste_{Fenster}_mt{mt}_m{Modus}.txt (frisch).

    A/B-Variante: alle Kanten chronologisch nach kanten_id mit Geburts-Bar/-ts,
    Referenz (Modus A: balance_preis; Modus B: anker_extremum), Touch-Bars,
    Zustand und Typ-Kennung - identische Dialog-Referenz fuer A/B-Laeufe.
    """
    nutze_anker = erg.cfg.modus == "B"
    pfad = ROOT / "test" / (
        f"kanten_liste_{erg.fenster}_mt{erg.cfg.max_tage}_m{erg.cfg.modus}.txt"
    )
    start, ende = FENSTER[erg.fenster]
    kanten = sorted(erg.kanten.values(), key=lambda k2: k2.kanten_id)
    n_oben = sum(1 for k2 in kanten if k2.seite == "OBEN")
    n_unten = len(kanten) - n_oben
    n_typ_b = sum(1 for k2 in kanten if k2.ist_typ_b)

    lines: List[str] = []
    lines.append("=" * 118)
    modus_txt = ("Modus A (Balance-VWAP)" if erg.cfg.modus == "A"
                 else "Modus B (Extremum-Ratchet)")
    lines.append(f"KANTEN-LISTE ({modus_txt}) | Fenster {erg.fenster} "
                 f"({start} .. {ende}) | max_tage={erg.cfg.max_tage}")
    lines.append("=" * 118)
    lines.append(f"Bars: {erg.n_bars} | Kanten gesamt: {len(kanten)} "
                 f"(OBEN {n_oben} / UNTEN {n_unten}) | Typ B (>=3): {n_typ_b} | "
                 f"verfallen: {erg.kanten_verfallen}")
    lines.append("")
    lines.append("--- KANTEN (alle, chronologisch nach kanten_id) ---")
    for k2 in kanten:
        ref = _ref_preis(k2, nutze_anker)
        typ = "B" if k2.ist_typ_b else "-"
        ts_geb = (f"{k2.geburts_ts:%d.%m %H:%M}"
                  if k2.geburts_ts is not None else "-")
        touch_bars = [t.pivot_bar for t in k2.touche]
        ref_name = "anker" if nutze_anker else "balance"
        lines.append(
            f"K{k2.kanten_id:3d} {k2.seite:5s} basis={k2.basis_preis:8.3f} "
            f"{ref_name}={ref:8.3f} geb={k2.geburts_bar:4d} ({ts_geb}) "
            f"zustand={k2.zustand:9s} typ={typ} touch={k2.touch_anzahl:2d} "
            f"bars={touch_bars}"
        )
    lines.append("")
    txt = "\n".join(lines)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"  Kantenliste TXT: {pfad}")
    return pfad


def _zeichne_modus_c_png(
    erg_c: _ReplayErgebnisC,
    out_png: Path,
    dpi: int = 300,
) -> Path:
    """Rendert je Modus-C-Lauf ein PNG (300 dpi): nur Chart + Statistik.

    Layout (2 Panels):
      * ax1 oben   : Close + V3-Trades (Entry ^/v; Exit je Haelfte
                     o = TP1-Haelfte, s = TP2/100%-Haelfte; Farbe nach Grund
                     TP gruen, SL rot, Zeitende/ENDE grau); Kanten mit
                     >= 2 Touches als statische Level-Linien (OBEN rot
                     durchgezogen, UNTEN gruen gestrichelt) + Touch-Eichpunkte.
      * ax_stat    : C-Kennzahlen + V3-Parameter + Kanten-Statistik.

    Args:
        erg_c: Modus-C-Replay-Ergebnis.
        out_png: Ziel-Pfad (z. B. test/kanten_engine_trades_AUG_mC.png).
        dpi: Aufloesung (Default 300).

    Returns:
        out_png (geschrieben).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    _COL_C_OBEN: str = "#d62728"     # OBEN-Kante (rot, durchgezogen)
    _COL_C_UNTEN: str = "#2ca02c"    # UNTEN-Kante (gruen, gestrichelt)

    d = _lade_fenster(erg_c.fenster)
    n = len(d)
    idx = np.arange(n)
    close = d["close"].to_numpy(dtype=float)
    ts = pd.to_datetime(d["ts"])

    fig, (ax1, ax_stat) = plt.subplots(
        2, 1, figsize=(18, 11),
        sharex=False,
        gridspec_kw={"height_ratios": [4.0, 1.45], "hspace": 0.16},
    )

    # ---- Ax1: Close + Kanten-Level + Trades ---------------------------------
    ax1.plot(idx, close, color=_COL_CLOSE, lw=0.8, alpha=0.85, zorder=2,
             label="Close")
    reif = [k2 for k2 in erg_c.kanten.values() if k2.touch_anzahl >= 2]
    for k2 in reif:
        col = _COL_C_OBEN if k2.seite == "OBEN" else _COL_C_UNTEN
        ls = "-" if k2.seite == "OBEN" else "--"
        ax1.plot([k2.geburts_bar, n - 1], [k2.basis_preis, k2.basis_preis],
                 color=col, ls=ls, lw=1.0, alpha=0.45, zorder=2.5)
        ax1.scatter(k2.touch_bars,
                    [k2.basis_preis] * len(k2.touch_bars),
                    s=8, color=col, alpha=0.6, edgecolors="none", zorder=2.7)

    trades = [s for s in erg_c.signale if s.trade is not None]
    for s in trades:
        t = s.trade
        assert t is not None
        col = _COL_UP if s.richtung == "LONG" else _COL_DOWN
        if t.exit1_bar >= 0 and t.exit1_bar != t.exit2_bar:
            ax1.plot([s.entry_bar, t.exit1_bar],
                     [s.entry_preis, t.exit1],
                     color=col, lw=0.7, ls=":", alpha=0.55, zorder=3)
        if t.exit2_bar >= 0:
            ax1.plot([s.entry_bar, t.exit2_bar],
                     [s.entry_preis, t.exit2],
                     color=col, lw=0.8, alpha=0.55, zorder=3)
        ax1.scatter(s.entry_bar, s.entry_preis,
                    marker="^" if s.richtung == "LONG" else "v",
                    s=52, color=col, edgecolor="w", linewidths=0.4, zorder=6)
        for e_bar, e_preis, grund, mk in (
            (t.exit1_bar, t.exit1, t.grund1, "o"),
            (t.exit2_bar, t.exit2, t.grund2, "s"),
        ):
            if e_bar < 0:
                continue
            if grund in ("TP1", "TP2"):
                ec = _COL_UP
            elif grund == "SL":
                ec = _COL_SL
            else:
                ec = _COL_ENDE
            ax1.scatter(e_bar, e_preis, marker=mk, s=26, color=ec,
                        edgecolor="w", linewidths=0.3, zorder=6)

    annot_kurz = len(trades) > 80
    for i, s in enumerate(trades):
        t = s.trade
        assert t is not None
        e_bar = max(t.exit1_bar, t.exit2_bar)
        if e_bar < 0:
            continue
        e_pr = t.exit1 if t.exit1_bar >= t.exit2_bar else t.exit2
        txt = f"{t.r_mult:+.2f}R"
        acol = (_COL_UP if t.r_mult > 1e-9
                else (_COL_DOWN if t.r_mult < -1e-9 else _COL_ENDE))
        dy = 5 if i % 2 == 0 else -14
        if e_bar > n - 8:
            ax1.annotate(txt, xy=(e_bar, e_pr), xytext=(-5, dy),
                         textcoords="offset points", ha="right", va="bottom",
                         fontsize=7 if not annot_kurz else 6, color=acol,
                         zorder=7, alpha=0.95)
        else:
            ax1.annotate(txt, xy=(e_bar, e_pr), xytext=(6, dy),
                         textcoords="offset points", ha="left", va="bottom",
                         fontsize=7 if not annot_kurz else 6, color=acol,
                         zorder=7, alpha=0.95)

    start, ende = FENSTER[erg_c.fenster]
    cfg = erg_c.cfg
    gate_ok = bool(_c_kennzahlen(erg_c)["gate"])
    ax1.set_title(
        f"KANTEN-ENGINE-REPLAY {erg_c.fenster} (MODUS C / V3 statisch)  |  "
        f"{start} .. {ende} (ende-exkl.)  |  touch_band {cfg.touch_band_pct:.2f} "
        f"| sl_buffer {cfg.sl_buffer_usd:.2f} | split {cfg.tp1_anteil_pct:.0f}/"
        f"{100.0 - cfg.tp1_anteil_pct:.0f} | {erg_c.laufzeit_s:.1f}s"
        + ("   [GATE BESTANDEN]" if gate_ok else ""),
        fontsize=12,
    )
    ax1.set_ylabel("USD")
    ax1.grid(alpha=0.3)

    # ---- Ax_stat: C-Kennzahlen + V3-Parameter ------------------------------
    ax_stat.axis("off")
    kz = _c_kennzahlen(erg_c)
    kanten = list(erg_c.kanten.values())
    n_oben = sum(1 for k2 in kanten if k2.seite == "OBEN")
    n_unten = len(kanten) - n_oben
    n_typ_a = sum(1 for k2 in kanten if k2.ist_gueltiges_kursziel_typ_a)
    n_typ_b = sum(1 for k2 in kanten if k2.touch_anzahl >= 3)
    n_tp1 = sum(1 for t in trades if t.trade is not None and t.trade.grund1 == "TP1")
    n_tp2 = sum(1 for t in trades if t.trade is not None and t.trade.grund2 == "TP2")
    n_sl = sum(1 for t in trades
               if t.trade is not None
               and (t.trade.grund1 == "SL" or t.trade.grund2 == "SL"))
    n_ende = sum(1 for t in trades
                 if t.trade is not None
                 and (t.trade.grund1 == "ENDE" or t.trade.grund2 == "ENDE"))
    pf = kz["pf"]
    pf_txt = "inf" if pf == float("inf") else f"{pf:.2f}"
    links = (
        f"GESAMT (n={kz['n']:.0f})\n"
        f"  GEWONNEN {kz['gewonnen']:.0f} | VERLOREN {kz['verloren']:.0f} "
        f"| NEUTRAL {kz['neutral']:.0f}\n"
        f"  Winrate {kz['winrate']:.1f}%\n"
        f"  Summe R {kz['summe_r']:+.2f}   PF {pf_txt}\n"
        f"  LONG {kz['long']:.0f} | SHORT {kz['short']:.0f}\n"
        f"  in_bar {kz['in_bar']:.0f} | next_bar {kz['next_bar']:.0f}\n"
        f"  Low-n-Warnung: {'JA' if kz['low_n'] else 'nein'}\n"
        f"  Exits TP1 {n_tp1} | TP2 {n_tp2} | SL {n_sl} | ENDE {n_ende}"
    )
    mitte = (
        f"V3-PARAMETER\n"
        f"  touch_band_pct {cfg.touch_band_pct:.2f}\n"
        f"  geburts_sperr_pct {V3_GEBURTS_SPERR_PCT:.2f}\n"
        f"  min_touch_abstand {cfg.min_touch_bar_abstand}\n"
        f"  tp_mindist_pct {cfg.tp_mindist_pct:.1f}\n"
        f"  sl_buffer_usd {cfg.sl_buffer_usd:.2f}\n"
        f"  tp1_anteil_pct {cfg.tp1_anteil_pct:.0f}\n"
        f"  next_bar-Split {'an' if cfg.erlaube_next_bar else 'aus'}\n"
        f"GENESE-VERWERFUNGEN\n"
        f"  Ring (0.23-0.50%): "
        f"{erg_c.ablehnung.get('ring_zwischenwelle', 0)}\n"
        f"  Band-Mindestabstand: "
        f"{erg_c.ablehnung.get('band_abstand_verworfen', 0)}"
    )
    rechts = (
        f"KANTEN\n"
        f"  geboren {len(kanten)} (OBEN {n_oben}/UNTEN {n_unten})\n"
        f"  Typ A (>=2 T): {n_typ_a}\n"
        f"  Typ B (>=3 T): {n_typ_b}\n"
        f"  Einstiegs-Bremse F3 (kein neuer Touch): "
        f"{erg_c.ablehnung.get('f3_kein_neuer_touch', 0)}\n"
        f"  max-1-offen: {erg_c.ablehnung.get('position_offen', 0)}\n"
        f"  kein Ziel-Raum (>=1.5%): "
        f"{erg_c.ablehnung.get('kein_ziel_raum', 0)}"
    )
    ax_stat.text(0.005, 0.5, links, va="center", ha="left", fontsize=9,
                 family="monospace",
                 bbox=dict(boxstyle="round,pad=0.4", fc="#f4f4f4", ec="#999999"))
    ax_stat.text(0.36, 0.5, mitte, va="center", ha="left", fontsize=9,
                 family="monospace",
                 bbox=dict(boxstyle="round,pad=0.4", fc="#faf0f0", ec="#c0392b"))
    ax_stat.text(0.70, 0.5, rechts, va="center", ha="left", fontsize=9,
                 family="monospace",
                 bbox=dict(boxstyle="round,pad=0.4", fc="#f4f4f4", ec="#999999"))

    # ---- Zeitachse + Legende ------------------------------------------------
    step: int = max(16, n // 14)
    ticks: np.ndarray = np.arange(0, n, step)
    ax1.set_xlim(-1, n)
    ax1.set_xticks(ticks)
    ax1.set_xticklabels(
        [ts[t].strftime("%a %d.%m %H:%M") for t in ticks],
        rotation=45, ha="right", fontsize=8,
    )
    legende_ax1: List[Line2D] = [
        Line2D([0], [0], color=_COL_CLOSE, lw=1.0, label="Close"),
        Line2D([0], [0], color=_COL_C_OBEN, lw=1.2, ls="-",
               label="OBEN-Kante (>=2T, durchgezogen)"),
        Line2D([0], [0], color=_COL_C_UNTEN, lw=1.2, ls="--",
               label="UNTEN-Kante (>=2T, gestrichelt)"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor=_COL_UP, ms=8,
               label="LONG-Entry (Start)"),
        Line2D([0], [0], marker="v", color="w", markerfacecolor=_COL_DOWN, ms=8,
               label="SHORT-Entry (Start)"),
        Line2D([0], [0], marker="o", color=_COL_UP, ms=6, ls="",
               label="Exit TP (Haelfte 1)"),
        Line2D([0], [0], marker="s", color=_COL_UP, ms=5, ls="",
               label="Exit TP2/100% (Haelfte 2)"),
        Line2D([0], [0], marker="o", color=_COL_SL, ms=6, ls="",
               label="Exit SL"),
        Line2D([0], [0], marker="o", color=_COL_ENDE, ms=6, ls="",
               label="Exit Zeitende / ENDE"),
    ]
    ax1.legend(handles=legende_ax1, loc="upper left", fontsize=8,
               framealpha=0.9, ncol=2)

    fig.subplots_adjust(left=0.055, right=0.985, top=0.95, bottom=0.09,
                        hspace=0.22)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=dpi)
    plt.close(fig)
    return out_png


def main() -> None:
    parser = argparse.ArgumentParser(description="Kanten-Engine Replay (Schritt 0)")
    parser.add_argument("--fenster", default="AUG", choices=["AUG", "S1", "S2", "ALLE"])
    parser.add_argument("--max-tage", type=int, default=60)
    parser.add_argument("--modus", default="A",
                        choices=["A", "B", "BEIDE", "C", "ALLE"],
                        help="Engine-Modus A (Balance-VWAP/V1), "
                             "B (Extremum-Ratchet/V2), BEIDE (A/B-Vergleich), "
                             "C (V3 statisch, §8.4) oder ALLE (A/B/C-Vergleich)")
    parser.add_argument("--dpi", type=int, default=300,
                        help="PNG-Aufloesung (Default 300)")
    parser.add_argument("--matrix", action="store_true",
                        help="AUG-Smoke(60) + S1/S2 x max_tage {1,5,20,60} "
                             "(nur Modus A/B/BEIDE)")
    parser.add_argument("--png", action="store_true",
                        help="PNG je Lauf erzeugen (Default: an)")
    parser.set_defaults(png=True)
    args = parser.parse_args()

    png_pfade: List[Path] = []
    txt_pfade: List[Path] = []
    modus_arg = args.modus

    fenster_liste: List[FensterTyp] = (
        ["AUG", "S1", "S2"] if args.fenster == "ALLE" else [args.fenster]  # type: ignore
    )

    def _lauf_ab(fenster: FensterTyp, mt: int, modus: str) -> _ReplayErgebnis:
        """Ein A/B-Replay-Lauf: Report + optional PNG + Kantenliste-TXT."""
        erg = _replay(fenster, HarnessKonfiguration(max_tage=mt,
                                                    modus=modus))  # type: ignore[arg-type]
        _report(erg)
        try:
            txt_pfade.append(_kantenliste_ab_txt(erg))
        except Exception as _e:
            print(f"  [WARNUNG] Kantenliste-TXT nicht schreibbar: {_e}")
        if args.png:
            try:
                png_pfade.append(_zeichne_trades_png(erg, _png_pfad(erg),
                                                     dpi=args.dpi))
            except OSError as _e:
                print(f"  [WARNUNG] PNG nicht schreibbar (gesperrt?): "
                      f"{_png_pfad(erg)} -- {_e}")
        return erg

    def _lauf_c(fenster: FensterTyp) -> _ReplayErgebnisC:
        """Ein Modus-C-Lauf (V3 statisch, §8.4): Report + optional PNG +
        Kantenliste-TXT (Dialog-Referenz)."""
        erg_c = _replay_c(fenster, ModusCKonfiguration())
        _report_c(erg_c)
        try:
            txt_pfade.append(_kantenliste_c_txt(erg_c))
        except Exception as _e:
            print(f"  [WARNUNG] Kantenliste-TXT nicht schreibbar: {_e}")
        if args.png:
            try:
                png_pfade.append(_zeichne_modus_c_png(erg_c, _png_pfad_c(erg_c),
                                                      dpi=args.dpi))
            except OSError as _e:
                print(f"  [WARNUNG] PNG nicht schreibbar (gesperrt?): "
                      f"{_png_pfad_c(erg_c)} -- {_e}")
        return erg_c

    def _a_b_vergleich(erg_pro_modus: Dict[str, List[_ReplayErgebnis]]) -> None:
        """Bei BEIDE: Side-by-Side-Vergleich je (Fenster, max_tage)-Paarung."""
        if "A" in erg_pro_modus and "B" in erg_pro_modus:
            for erg_a, erg_b in zip(erg_pro_modus["A"], erg_pro_modus["B"]):
                _vergleich_tabelle(erg_a, erg_b)

    if args.matrix and modus_arg in ("C", "ALLE"):
        print("[HINWEIS] --matrix entfaellt fuer Modus C/ALLE "
              "(C-Gate §8.4: je Fenster genau 1 Durchlauf, kein max_tage-Grid).")
        args.matrix = False

    if args.matrix:
        # Nur Modus A/B/BEIDE: max_tage-Sensitivitaetsmatrix (§8.1/§8.3)
        open(REPORT_TXT, "w", encoding="utf-8").close()
        konfigurationen: List[Tuple[FensterTyp, int]] = [
            ("AUG", 60),
            *[(f, t) for f in ("S1", "S2") for t in (1, 5, 20, 60)],  # type: ignore
        ]
        modi: List[str] = (["A", "B"] if modus_arg == "BEIDE" else [modus_arg])
        ergebnis_pro_modus: Dict[str, List[_ReplayErgebnis]] = {}
        for modus in modi:
            ergebnisse: List[_ReplayErgebnis] = []
            for fenster, mt in konfigurationen:
                ergebnisse.append(_lauf_ab(fenster, mt, modus))
            _matrix_tabelle(ergebnisse, modus=modus)  # type: ignore[arg-type]
            ergebnis_pro_modus[modus] = ergebnisse
        _a_b_vergleich(ergebnis_pro_modus)
    elif modus_arg in ("A", "B", "BEIDE"):
        ergebnis_pro_modus: Dict[str, List[_ReplayErgebnis]] = {}
        modi = ["A", "B"] if modus_arg == "BEIDE" else [modus_arg]
        for modus in modi:
            ergebnisse: List[_ReplayErgebnis] = []
            for fenster in fenster_liste:
                ergebnisse.append(_lauf_ab(fenster, args.max_tage, modus))
            ergebnis_pro_modus[modus] = ergebnisse
        _a_b_vergleich(ergebnis_pro_modus)
    elif modus_arg == "C":
        # C-Gate §8.4: je Fenster genau 1 Lauf; AUG = SE-Harness
        # (arretierte Straight-Edge-Revision a771e04, Schritt B/C): Sweep-
        # Sperre, SE_BAND 0.12, Regel-2-Rollen, POC-TP1/TP2-Gegenkante,
        # Split 50/50, SL +/- 0.05 USD. Alt-C (S1/S2) bleibt Referenz.
        ergebnisse_c: List[_ReplayErgebnisC] = []
        for fenster in fenster_liste:
            if fenster == "AUG":
                _replay_c_se_main(fenster, dpi=args.dpi)
                continue
            ergebnisse_c.append(_lauf_c(fenster))
        if len(ergebnisse_c) > 1:
            _c_gate_tabelle(ergebnisse_c)
    else:  # modus_arg == "ALLE" (§8.4: A mt60 / B mt60 / C statisch)
        if args.matrix:
            open(REPORT_TXT, "w", encoding="utf-8").close()
        list_a: List[_ReplayErgebnis] = []
        list_b: List[_ReplayErgebnis] = []
        list_c: List[_ReplayErgebnisC] = []
        for fenster in fenster_liste:
            list_a.append(_lauf_ab(fenster, 60, "A"))
            list_b.append(_lauf_ab(fenster, 60, "B"))
            list_c.append(_lauf_c(fenster))
        _abc_vergleich_tabelle(list_a, list_b, list_c)

    if png_pfade:
        print("\nPNG (300 dpi):")
        for p in png_pfade:
            print(f"  {p}")
    if txt_pfade:
        print("\nKantenlisten (TXT, Dialog-Referenz):")
        for p in txt_pfade:
            print(f"  {p}")


if __name__ == "__main__":
    main()
