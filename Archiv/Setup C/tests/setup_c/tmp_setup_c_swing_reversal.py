"""
SETUP C - SWING_REVERSAL (FADE) - ISOLIERTER AUDIT (test/tmp_setup_c_swing_reversal.py)
=========================================================================================
Status: ENTWURF ZUR DURCHSICHT (06.09.2026) - Freigabe-Gate F1-F4 erteilt.
Doku:   docs/setup_c_experiment.md (Paragraf 5.3: Phasenloser Raum &
        Counter-Trend-Reversals - Beobachtung/Status; arretierte Semantik im
        Chat-Protokoll 06.09.2026, Amendments 1-8 + Simulations-Parameter 1-3).
Baseline: scripts/setup_c_profil.py (Produktionskern) - BYTE-IDENTISCH
        UNANGETASTET (kein Import-Eingriff, kein Schreiben, kein Patch).
Arbeitsmodus: isoliertes, rein lesendes Replay (DuckDB read_only via
      scripts.market_segmentation.load_data). Keine Produktions-Integration.

Zweck
-----
Bewertet als eigenstaendiger Einstiegs-Zweig (Arbeitsstrom Setup C Evolution,
Paragraf 5.3) kontraere Fade-Entries auf den abgeschlossenen 2-Close-Bruch
einer Strukturphase: Up-Bruch -> SHORT, Down-Bruch -> LONG (NIE Sofort-
Einstieg). Der Einstieg folgt der ZWEISTUFIGEN SEQUENZ (Freigabe F-A,
Mentor-Urteil 06.09.2026; die Koinzidenz-Variante ist empirisch 0/210 -
EMA-20-Lag):
  (a) Ereignis k_exh: Sweep ueber das lokale Extremum (Ratschen-
      Nachfuehrung NACH Pruefung, strikte Ungleichheit: high > lok_extrem
      bzw. low < lok_extrem) MIT Docht-Rejection (Docht-Anteil >=
      docht_min_verhaeltnis gegen die Bewegungsrichtung; SHORT: close <
      open, LONG: close > open) = Erschoepfungs-Nachweis.
  (b) Bestaetigung k_trig >= k_exh: EMA-20-Slope kippt in die Schutz-
      richtung (SHORT: slope <= schwelle, LONG: slope >= schwelle) =
      Trigger; Entry = open[k_trig + 1]; Stop-Anker = Extremum von k_exh.
  STRENGE INVALIDIERUNG (Zusatzfrage, Mentor-Intervention): neues Extremum
  nach k_exh (high > exhaustion_high bzw. low < exhaustion_low) entwertet
  k_exh; erst eine NEUE Sweep+Docht-Kerze schaltet den Slope-Kipp wieder
  scharf (Nicht-Docht-Sweeps ratchen das Extremum weiter, Anker = None).
Der Simulationskern ist eine 1:1-Adaption der Phase-1-Kausalitaet
(E1/E2-Reihe): intrabar-Stop mit VORRANG, terminaler Zeit-Exit N=48 am Close
der Bar entry+N (ZEIT_EXIT_CLOSE), strikt kausale Rechts-Zensierung
(RECHTS_ZENSIERT, r = NaN) ausschliesslich bei entry+N > n-1. KEINE 300-Bar-
Crash-Notbremse (F3-Freigabe: N=48 terminiert ohnehin; CRASH_HORIZONT_CLOSE
wird im Reversal-Arm nicht emittiert). Variante-B-Ratchet 1:1
(mindest_gewinn_r = 0.0, Monotonie-Pflicht, Extremum der Abflachungs-Kerze).

Arretierte Datenvertraege (Amendments 1-8, Freigabe-Gate 06.09.2026)
---------------------------------------------------------------------
A1  scan_start_offset_bars = 2: Scan erst ab brk_idx + 2 (nach vollstaendiger
    2-Close-Bestaetigung; kein Fade der Bestaetigungskerze = kein Kopf-an-Kopf
    mit CONFIRMED-Long derselben Phase).
A2  lok_extrem-Initialisierung ueber [brk_idx, start_scan) =
    np.max(high[brk_idx:start_scan]) bzw. np.min(low[brk_idx:start_scan])
    (verhindert Phantom-Sweeps gegen eine leere Historie).
A3  Sweep-Bedingung strikt (high > lok_extrem bzw. low < lok_extrem;
    Ratschen-Nachfuehrung NACH Pruefung). Docht-Anteil >=
    docht_min_verhaeltnis (0.40). SHORT: close < open; LONG: close > open.
A4  Status-Trennschaerfe: hatte_erschoepfung (Sweep+Docht) -> Unterscheidung
    KEINE_EMA_ABFLACHUNG (Erschoepfung gesehen, Slope nie koinzident) vs.
    KEINE_ERSCHOEPFUNG (keine Sweep+Docht-Bar im Fenster). RANGE_DEGENERIERT
    bei fehlender/positiv-verletzter Phasenbreite; SL_UEBERSCHRITTEN bei
    sl_usd <= 0 (Entry jenseits der Stop-Kappe); DATEN_ENDE bei leerem
    Scan-Fenster (start_scan > n-1) oder Trigger auf der letzten Bar
    (kein Folge-Open).
A5  Slope-Vorzeichen-Semantik (slope <= schwelle SHORT / >= schwelle LONG;
    Default slope_schwelle = 0.0). SlopeSemantik-Literal deklariert
    (BETRAG_ATR_NORM = Backlog, ungueltige Auswahl wird abgelehnt).
A6  SwingSignalConfig-Defaults: max_suchfenster_bars=24,
    scan_start_offset_bars=2, docht_min_verhaeltnis=0.40, ema_periode=20,
    slope_schwelle=0.0, max_sl_kanten_mult=1.0, stop_puffer=0.15.
A7  SwingSignalKandidat: arm = Literal["SWING_REVERSAL"], Basis-Referenz-
    Felder (basis_brk_dir/basis_brk_idx/basis_kante), exhaustion_high/low,
    status.
A8  Doppelte-Top/Bottom-Gleichheit (high == lok_extrem bzw. low ==
    lok_extrem) -> KEIN Sweep (konsistent). sweep_toleranz = Backlog-
    Sensitivitaet (nicht implementiert).
F-A PRAEZISIERUNG (Freigabe 06.09.2026, Mentor-Urteil F-A): Die Koinzidenz
    von A3+A5 (Sweep+Docht+Slope-Kipp an DERSELBEN Bar) ist empirisch 0/210
    unproduktiv (EMA-20 = nachlaufender Tiefpass; ein frisches Extremum
    laesst den Slope erst NACH der Erschoepfungs-Kerze kippen). Neuer
    Trigger = zweistufige Sequenz: k_exh (Sweep+Docht, Nachweis) ->
    k_trig >= k_exh (Slope-Kipp, Bestaetigung); Entry = open[k_trig+1];
    Stop-Anker = Extremum von k_exh. STRENGE INVALIDIERUNG (Zusatzfrage,
    Mentor-Intervention): neues Extremum nach k_exh (high > exhaustion_high
    SHORT / low < exhaustion_low LONG) entwertet k_exh - ein neuer
    Sweep+Docht ist Voraussetzung, bevor ein Slope-Kipp scharf schaltet.
    Die Implementierung ist die EXAKTE Vektorisierung dieser State-Machine
    (kein Bar-Loop; Agenten-Regel "Vektorisierung pur").

Arretierte Simulations-Parameter (Freigabe F1-F3)
--------------------------------------------------
S1  Hard-Intrabar-Stop mit VORRANG, Exit zum Stop-Preis (Gap wie Baseline).
S2  Variante-B-Ratchet 1:1 (mindest_gewinn_r = 0.0); +0.5/+1.0R-Backlog.
S3  Terminaler Zeit-Exit N=48 (Close der Bar entry+48, ZEIT_EXIT_CLOSE);
    RECHTS_ZENSIERT strikt isoliert (r = NaN, keine Glattstellung zum letzten
    Close). KEINE Crash-Notbremse (N=48 ist die terminale Schranke).

Stop-Deckelung (strukturell, F4-Adaption)
-----------------------------------------
SHORT: stop = min(high_exh + stop_puffer, entry + max_sl_kanten_mult * Range)
LONG:  stop = max(low_exh  - stop_puffer, entry - max_sl_kanten_mult * Range)
Range = U_final - L_final der Basis-Phase (echter 2-Close-Bruch).

Ausgabe
-------
Textreport + Trade-TSV unter reports/setup_c/setup_c_swing_{FENSTER}.txt/.tsv
(andere Dateinamen als die Baseline-Artefakte setup_c_*.txt/.tsv und
setup_c_ab_trailing_* -> historische Artefakte bleiben byte-identisch
unberuehrt). Zusaetzlich Konsolenausgabe.

Aufruf (Projekt-Root):
    python test/tmp_setup_c_swing_reversal.py --fenster=AUG|S1|S2|ALLE
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
TEST_DIR: Path = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Produktions-Module NUR lesend importiert (Isolations-Garantie: kein Patch).
from scripts.market_segmentation import (  # noqa: E402
    PhaseData,
    SegmentConfig,
    SegmentResult,
    load_data,
    segmentiere_markt,
)
from scripts.setup_c_profil import (  # noqa: E402
    AggBlock,
    FENSTER_DEFS,
    ExitGrund,
    KernelTrade,
    _agg_block,
    _block_text,
    _fmt,
    berechne_ema_slope_vektoren,
)

# ==============================================================================
# 1) TYPALIASSE & ARRETIERTE KONSTANTEN
# ==============================================================================

DirName = Literal["up", "down"]
SwingArm = Literal["SWING_REVERSAL"]
SwingSignalStatus = Literal[
    "SIGNAL",
    "KEINE_ERSCHOEPFUNG",     # keine Sweep+Docht-Bar im Suchfenster
    "KEINE_EMA_ABFLACHUNG",   # Erschoepfung gesehen, Slope-Kipp nie bei
                              # gueltigem Anker (F-A-Invalidierung)
    "SL_UEBERSCHRITTEN",      # Stop-Kappe degeneriert (sl_usd <= 0)
    "RANGE_DEGENERIERT",      # Basis-Phase ohne gueltige Breite (U_final-L_final)
    "DATEN_ENDE",             # Scan-Fenster leer oder Trigger ohne Folge-Open
]
# A5: Deklariertes Semantik-Literal. BETRAG_ATR_NORM ist Backlog
# (unimplementiert); eine Auswahl wird mit NotImplementedError abgelehnt.
SlopeSemantik = Literal["VORZEICHEN", "BETRAG_ATR_NORM"]

# S3: Terminaler Zeit-Exit-Horizont (M15-Bars) - arretiert. Abweichend vom
# 300er-Trend-Kern, da der Fade ein schneller Snap-back ist.
SWING_ZEIT_HORIZONT: int = 48
# S2: Ratchet-Gewinnschwelle in R (0.0 = ab der ersten Kerze aktiv).
# +0.5/+1.0R-Sensitivitaeten sind Backlog.
SWING_MINDEST_GEWINN_R: float = 0.0
# r_ref bleibt reine 0.45%-Messung (nie Produktions-Stop; Konvention Phase 1).
SWING_SL_PCT_REF: float = 0.45


# ==============================================================================
# 2) DATENVERTRAEGE (A6/A7, freigegeben)
# ==============================================================================


@dataclass(frozen=True, slots=True)
class SwingSignalConfig:
    """Konfiguration fuer den SWING_REVERSAL-Erfassungsblock (A6).

    Defaults = arretierte Beschluesse (Amendments 1-8); Aenderungen nur als
    dokumentierte Sensitivitaeten. ``sweep_toleranz`` (A8) ist bewusst NICHT
    Teil des Vertrags (Backlog-Sensitivitaet).

    Attributes:
        max_suchfenster_bars: Scan-Fenster in Bars ab brk_idx +
            scan_start_offset_bars (24 M15-Bars = 6h).
        scan_start_offset_bars: Offset des Scan-Starts nach brk_idx
            (2 = nach vollstaendiger 2-Close-Bestaetigung, A1).
        docht_min_verhaeltnis: Mindest-Docht-Anteil der Rejection-Kerze am
            gesamten Kerzen-Range (0.40, A3).
        ema_periode: EMA-Periode des Slope-Gates (Standard 20).
        slope_schwelle: Vorzeichen-Schwelle des Slope-Gates (0.0, A5).
        max_sl_kanten_mult: Stop-Deckelung als Vielfaches der Basis-Phase-
            Breite Range = U_final - L_final (1.0 = maximal 1R Risiko).
        stop_puffer: Puffer (USD) ueber/unter dem Erschoepfungs-Extremum
            (0.15, F4-Adaption).
    """

    max_suchfenster_bars: int = 24
    scan_start_offset_bars: int = 2
    docht_min_verhaeltnis: float = 0.40
    ema_periode: int = 20
    slope_schwelle: float = 0.0
    max_sl_kanten_mult: float = 1.0
    stop_puffer: float = 0.15


@dataclass(slots=True)
class SwingSignalKandidat:
    """Erfasster SWING_REVERSAL-Kandidat einer echten Bruch-Phase (A7).

    Ein Kandidat je Phase; die Fade-Richtung ist deterministisch kontraer zum
    Bruch (Up-Bruch -> dir="down", Down-Bruch -> dir="up"). SIGNAL traegt
    entry_*/stop_level/sl_usd; Nicht-SIGNAL-Status traegt Diagnose-Felder
    (trigger_idx/exhaustion_* wo verfuegbar, sonst -1/None/nan).
    """

    arm: SwingArm
    phase: int                       # Basis-Phase (1-basiert, echte Brueche)
    dir: DirName                     # Fade-/Positionsrichtung (kontraer)
    basis_brk_dir: DirName           # Bruchrichtung der Basis-Phase
    basis_brk_idx: int               # brk_idx der Basis-Phase (erste der 2 Close)
    basis_kante: float               # brk_kante der Basis-Phase
    range_breite: float              # U_final - L_final (Stop-Deckelung)
    trigger_idx: int                 # Slope-Kipp-Bar k_trig (Bestaetigung, F-A)
    entry_idx: int                   # = trigger_idx + 1 (Open der Folge-Bar)
    entry_ts: Optional[pd.Timestamp]
    entry_preis: float
    lok_extrem_trigger: Optional[float]   # laufendes Extremum VOR k_trig
    exhaustion_high: Optional[float]      # high der k_exh (SHORT, Stop-Anker)
    exhaustion_low: Optional[float]       # low der k_exh (LONG, Stop-Anker)
    stop_level: float                     # strukturelle Stop-Kappe
    sl_usd: float
    status: SwingSignalStatus


# ==============================================================================
# 3) SIGNAL-ERFASSUNG (SWING_REVERSAL, Amendments A1-A8 + F-A-Sequenz;
#    vektorisiert, keinerlei Bar-Schleife)
# ==============================================================================


def _erfasse_swing_reversal(
    df: pd.DataFrame,
    p: PhaseData,
    nr: int,
    cfg: SwingSignalConfig,
    slope_arr: np.ndarray,
) -> SwingSignalKandidat:
    """Erfasst den SWING_REVERSAL-Kandidaten einer echten Bruch-Phase.

    Zweistufige Sequenz (Freigabe F-A, 06.09.2026): Die urspruengliche
    Koinzidenz-Anforderung (Sweep+Docht+Slope-Kipp an DERSELBEN Bar, A3/A5)
    ist empirisch 0/210 unproduktiv: Der EMA-20 ist ein nachlaufender
    Tiefpass, dessen Slope durch ein frisches Extremum erst NACH der
    Erschoepfungs-Kerze kippen kann. Institutionelle Liquiditaet formt das
    Muster in zwei Phasen:
      1) Ereignis k_exh: Sweep ueber das laufende Extremum (strikte
         Ungleichheit, A8) MIT Docht-Rejection (Anteil >=
         docht_min_verhaeltnis; SHORT: close < open, LONG: close > open)
         = Erschoepfungs-Nachweis.
      2) Bestaetigung k_trig >= k_exh: Slope-Kipp in die Schutzrichtung
         (SHORT: slope <= schwelle, LONG: slope >= schwelle, A5) =
         Trigger; Entry = open[k_trig + 1]; Stop-Anker = Extremum von
         k_exh.
    STRENGE INVALIDIERUNG (Freigabe F-A, Mentor-Intervention): Markiert
    eine Bar nach k_exh ein NEUES Extremum (high > exhaustion_high bzw.
    low < exhaustion_low), war k_exh nur eine Pause im Trend - sie wird
    entwertet; erst eine NEUE Sweep+Docht-Kerze schaltet den Slope-Kipp
    wieder scharf (Nicht-Docht-Sweeps ratchen das lokale Extremum weiter,
    halten den Zustand aber auf "kein Anker").

    Rein vektorisiert (np.maximum.accumulate/np.minimum.accumulate fuer die
    Ratschen-Historie; der Trigger-Zustand "Anker k_exh gueltig an Bar k"
    wird exakt ueber den LETZTEN Sweep-Bar <= k ausgedrueckt: k_exh ist
    genau dann gueltig, wenn dieser letzte Sweep eine Erschoepfungs-Kerze
    ist - keinerlei Bar-Schleife, aber bitgenau aequivalent zur arretierten
    State-Machine).

    Args:
        df: OHLCV-DataFrame.
        p: PhaseData-Objekt (echter 2-Close-Bruch, break_dir/brk_idx gesetzt).
        nr: Phasennummer (1-basiert, deckungsgleich _erfasse_signale/
            KernelTrade.phase).
        cfg: SwingSignalConfig.
        slope_arr: Kausaler 1-Bar-Slope-Vektor ueber df (len(df)); der EMA
            selbst wird hier nicht benoetigt (nur dessen Ableitung).

    Returns:
        SwingSignalKandidat (SIGNAL oder Diagnose-Status, A4/F-A).
    """
    assert p.break_dir is not None and p.brk_idx is not None
    assert p.brk_kante is not None
    assert p.U_final is not None and p.L_final is not None
    assert cfg.max_suchfenster_bars >= 1
    assert cfg.scan_start_offset_bars >= 1
    assert cfg.docht_min_verhaeltnis > 0.0
    assert cfg.max_sl_kanten_mult > 0.0

    n: int = len(df)
    b: int = int(p.brk_idx)
    fade: DirName = "down" if p.break_dir == "up" else "up"
    breite: float = float(p.U_final) - float(p.L_final)

    def _roh(status: SwingSignalStatus, trigger: int = -1) -> SwingSignalKandidat:
        return SwingSignalKandidat(
            arm="SWING_REVERSAL", phase=nr, dir=fade,
            basis_brk_dir=p.break_dir, basis_brk_idx=b,  # type: ignore[arg-type]
            basis_kante=float(p.brk_kante),
            range_breite=breite if np.isfinite(breite) and breite > 0.0
            else float("nan"),
            trigger_idx=trigger, entry_idx=-1, entry_ts=None,
            entry_preis=float("nan"), lok_extrem_trigger=None,
            exhaustion_high=None, exhaustion_low=None,
            stop_level=float("nan"), sl_usd=float("nan"), status=status,
        )

    # A4: RANGE_DEGENERIERT (Basis-Phase ohne gueltige Breite)
    if not (np.isfinite(breite) and breite > 0.0):
        return _roh("RANGE_DEGENERIERT")

    offset: int = cfg.scan_start_offset_bars
    start_scan: int = b + offset
    if start_scan > n - 1:
        return _roh("DATEN_ENDE")  # A4: leeres Scan-Fenster

    # A6: Scan-Fenster = max_suchfenster_bars Bars ab start_scan (bzw.
    # Datenende). fenster_voll=False => Datenende hat das Fenster gekappt
    # (A4/F-A: dann DATEN_ENDE statt KEINE_ERSCHOEPFUNG, wenn kein Docht).
    nominal_hi: int = b + offset + cfg.max_suchfenster_bars - 1
    scan_hi: int = min(nominal_hi, n - 1)
    fenster_voll: bool = scan_hi == nominal_hi

    high: np.ndarray = df["high"].values.astype(float)
    low: np.ndarray = df["low"].values.astype(float)
    opn: np.ndarray = df["open"].values.astype(float)
    cls: np.ndarray = df["close"].values.astype(float)

    W: np.ndarray = np.arange(start_scan, scan_hi + 1)
    hi_w: np.ndarray = high[W]
    lo_w: np.ndarray = low[W]
    op_w: np.ndarray = opn[W]
    cl_w: np.ndarray = cls[W]
    slp_w: np.ndarray = slope_arr[W].astype(float)

    # Ratschen-Historie (A2/A3): lok je Scan-Bar k = Extremum ueber
    # [brk_idx, k-1]; Initialisierung implizit ueber pref[0:offset-1].
    if fade == "down":
        # SHORT: laufendes Maximum der Highs
        full: np.ndarray = high[b : scan_hi + 1]
        pref: np.ndarray = np.maximum.accumulate(full)
    else:
        # LONG: laufendes Minimum der Lows
        full = low[b : scan_hi + 1]
        pref = np.minimum.accumulate(full)
    lok: np.ndarray = pref[offset - 1 : offset - 1 + len(W)]

    kerzen_range: np.ndarray = hi_w - lo_w
    with np.errstate(divide="ignore", invalid="ignore"):
        if fade == "down":
            sweep: np.ndarray = hi_w > lok      # A3/A8: strikte Ungleichheit
            docht: np.ndarray = (
                (cl_w < op_w)
                & (kerzen_range > 0.0)
                & ((hi_w - np.maximum(op_w, cl_w)) / kerzen_range
                   >= cfg.docht_min_verhaeltnis)
            )
            slope_ok: np.ndarray = slp_w <= cfg.slope_schwelle  # A5
        else:
            sweep = lo_w < lok                  # A3/A8: strikte Ungleichheit
            docht = (
                (cl_w > op_w)
                & (kerzen_range > 0.0)
                & ((np.minimum(op_w, cl_w) - lo_w) / kerzen_range
                   >= cfg.docht_min_verhaeltnis)
            )
            slope_ok = slp_w >= cfg.slope_schwelle  # A5

    erschoepfung: np.ndarray = sweep & docht

    # F-A-Trigger (exakte Vektorisierung der State-Machine): Der Anker
    # k_exh an Bar k ist der LETZTE Sweep-Bar <= k. Gueltig nur, wenn
    # dieser letzte Sweep eine Erschoepfungs-Kerze ist. Ein Nicht-Docht-
    # Sweep nach einer Erschoepfung entwertet sie (Invalidierung) und
    # haelt den Zustand "kein Anker", bis eine NEUE Sweep+Docht-Kerze
    # entsteht (strikte Invalidierung, Mentor-Intervention F-A).
    swp_bar: np.ndarray = np.where(sweep, W, -1)
    last_sweep: np.ndarray = np.maximum.accumulate(swp_bar)
    has_anchor: np.ndarray = last_sweep >= 0
    anchor_pos: np.ndarray = np.where(has_anchor, last_sweep - start_scan, 0)
    valid: np.ndarray = has_anchor & erschoepfung[anchor_pos]
    trigger_mask: np.ndarray = valid & slope_ok

    if not bool(trigger_mask.any()):
        # A4/F-A: Trennschaerfe - Erschoepfung gesehen, aber Slope-Kipp nie
        # waehrend eines gueltigen Ankers im Fenster?
        if bool(erschoepfung.any()):
            return _roh("KEINE_EMA_ABFLACHUNG")
        if not fenster_voll:
            return _roh("DATEN_ENDE")  # Fenster am Datenende gekappt
        return _roh("KEINE_ERSCHOEPFUNG")

    p_trig: int = int(np.flatnonzero(trigger_mask)[0])
    k_trig: int = int(W[p_trig])
    if k_trig + 1 >= n:
        return _roh("DATEN_ENDE", trigger=k_trig)  # A4: kein Folge-Open

    j_anchor: int = int(last_sweep[p_trig])  # = k_exh (gueltige Erschoepfung)
    e: int = k_trig + 1
    entry: float = float(opn[e])  # F4: deterministisch open[k_trig+1]
    mult: float = cfg.max_sl_kanten_mult
    if fade == "down":
        exh_high: float = float(high[j_anchor])
        stop: float = min(
            exh_high + cfg.stop_puffer, entry + mult * breite
        )
        sl_usd: float = stop - entry
    else:
        exh_low: float = float(low[j_anchor])
        stop = max(exh_low - cfg.stop_puffer, entry - mult * breite)
        sl_usd = entry - stop

    # F4-Adaption: Stop-Kappe degeneriert -> kein handelbarer Einstieg
    if not (np.isfinite(sl_usd) and sl_usd > 0.0):
        kandidat = _roh("SL_UEBERSCHRITTEN", trigger=k_trig)
        kandidat.lok_extrem_trigger = float(lok[p_trig])
        if fade == "down":
            kandidat.exhaustion_high = float(high[j_anchor])
        else:
            kandidat.exhaustion_low = float(low[j_anchor])
        return kandidat

    return SwingSignalKandidat(
        arm="SWING_REVERSAL", phase=nr, dir=fade,
        basis_brk_dir=p.break_dir, basis_brk_idx=b,  # type: ignore[arg-type]
        basis_kante=float(p.brk_kante), range_breite=breite,
        trigger_idx=k_trig, entry_idx=e, entry_ts=df["ts"].iloc[e],
        entry_preis=entry, lok_extrem_trigger=float(lok[p_trig]),
        exhaustion_high=float(high[j_anchor]) if fade == "down" else None,
        exhaustion_low=float(low[j_anchor]) if fade == "up" else None,
        stop_level=float(stop), sl_usd=float(sl_usd), status="SIGNAL",
    )


# ==============================================================================
# 4) SIMULATIONSKERN (SWING_REVERSAL; korrigierte Fassung, Freigabe F1-F4)
# ==============================================================================


def _simuliere_kern_swing_reversal(
    df: pd.DataFrame,
    sig: SwingSignalKandidat,
    ema_arr: np.ndarray,
    slope_arr: np.ndarray,
    *,
    horizont: int = SWING_ZEIT_HORIZONT,
    mindest_gewinn_r: float = SWING_MINDEST_GEWINN_R,
    slope_schwelle: float = 0.0,
    sl_pct_ref: float = SWING_SL_PCT_REF,
) -> KernelTrade:
    """Simuliert ein SWING_REVERSAL-Signal (Fade, arretiertes Modell S1-S3).

    Modell (Freigabe-Gate 06.09.2026, F1-F3):
      1) Intrabar-Stop mit VORRANG: initial = strukturelle Stop-Kappe
         (``sig.stop_level``); nach einem Ratchet gilt der nachgezogene Stop
         (TRAILING_SL_INTRABAR). Exit zum Stop-Preis (Gap wie Baseline).
      2) Variante-B-Ratchet 1:1 (mindest_gewinn_r = 0.0 = sofort aktiv):
         kippt die EMA-Steigung in die Schutzrichtung (LONG: slope <=
         schwelle, SHORT: slope >= schwelle), wird der Stop auf das
         Extremum DIESER Kerze nachgezogen (LONG: low[k], SHORT: high[k]).
         Monotonie-Pflicht: Long nur erhoehen / Short nur senken (nie
         Risiko vergroessern). +0.5/+1.0R = Backlog-Sensitivitaet.
      3) Terminaler Zeit-Exit N = horizont (48): Exit am Close der Bar
         entry+N (ZEIT_EXIT_CLOSE). Abweichend vom 300er-Trend-Kern (Fade =
         schneller Snap-back); eine separate Crash-Sicherung ist NICHT Teil
         des Swing-Modells (F3: CRASH_HORIZONT_CLOSE wird nie emittiert).
    Ueberlebt der Trade das Datenende ohne Stop und ohne erreichten Horizont
    (entry+N > n-1), gilt er als RECHTS_ZENSIERT (E2): r_f4 und r_ref = NaN,
    exit_* dokumentiert das Datenende - strikt isoliert, KEINE Glattstellung
    zum letzten Close.

    Args:
        df: OHLCV-DataFrame (open/high/low/close/ts, len > entry_idx).
        sig: SwingSignalKandidat (status SIGNAL; dir = Fade-Richtung;
            entry_idx; stop_level/sl_usd gesetzt).
        ema_arr: Kausaler Close-EMA-Vektor ueber df (len(df)).
        slope_arr: Kausaler 1-Bar-Slope-Vektor ueber df (len(df)).
        horizont: Terminaler Zeit-Exit-Horizont N (Default 48, arretiert).
        mindest_gewinn_r: Gewinnschwelle in R fuer den Ratchet (0.0).
        slope_schwelle: Vorzeichen-Schwelle des Ratchet-Triggers (0.0).
        sl_pct_ref: Referenz-SL-Prozentsatz fuer r_ref (0.45 %-Basis).

    Returns:
        KernelTrade (horizont_bars = N, arm = "SWING_REVERSAL",
        trailing_pfad = Ratchet-Pfad sofern nachgezogen, sonst None).
    """
    assert sig.status == "SIGNAL"
    assert sig.entry_idx >= 0 and np.isfinite(sig.sl_usd) and sig.sl_usd > 0.0
    n: int = len(df)
    e: int = int(sig.entry_idx)
    up: bool = sig.dir == "up"
    entry: float = float(df["open"].values[e])  # F4: deterministisch aus df
    initial_stop: float = float(sig.stop_level)
    sl_usd: float = float(sig.sl_usd)
    high: np.ndarray = df["high"].values.astype(float)
    low: np.ndarray = df["low"].values.astype(float)
    close: np.ndarray = df["close"].values.astype(float)

    ziel_bar: int = e + horizont
    letzte_bar: int = n - 1
    loop_ende: int = min(ziel_bar, letzte_bar)

    exit_grund: ExitGrund = "RECHTS_ZENSIERT"  # Default: Datenende ueberlebt
    exit_idx: int = letzte_bar
    exit_preis: float = float(close[letzte_bar])
    akt_sl: float = initial_stop
    pfad: List[Tuple[int, float]] = []

    for k in range(e, loop_ende + 1):
        # 1) Stop intrabar mit aktuellem Niveau (Vorrang vor Zeit-Exit)
        if (up and low[k] <= akt_sl) or ((not up) and high[k] >= akt_sl):
            exit_preis, exit_idx = float(akt_sl), k
            exit_grund = (
                "INITIAL_SL_INTRABAR"
                if akt_sl == initial_stop
                else "TRAILING_SL_INTRABAR"
            )
            break
        # 2) Terminaler Zeit-Exit am Close der Bar entry+N (S3)
        if k == ziel_bar:
            exit_preis, exit_idx, exit_grund = (
                float(close[k]), k, "ZEIT_EXIT_CLOSE"
            )
            break
        # 3) Variante-B-Ratchet (S2; Monotonie: nie Risiko vergroessern)
        slope_k: float = float(slope_arr[k])
        ratchet_ok: bool = mindest_gewinn_r <= 0.0
        if not ratchet_ok:
            fl_r: float = (
                (close[k] - entry) / sl_usd if up
                else (entry - close[k]) / sl_usd
            )
            ratchet_ok = fl_r >= mindest_gewinn_r
        if ratchet_ok and (
            (up and slope_k <= slope_schwelle)
            or ((not up) and slope_k >= slope_schwelle)
        ):
            neuer_sl: float = float(low[k] if up else high[k])
            if (up and neuer_sl > akt_sl) or ((not up) and neuer_sl < akt_sl):
                akt_sl = neuer_sl
                pfad.append((k, akt_sl))

    haltezeit: int = exit_idx - e
    zensiert: bool = exit_grund == "RECHTS_ZENSIERT"
    if zensiert:
        r_f4: float = float("nan")
        r_ref: float = float("nan")
    else:
        if up:
            r_f4 = (exit_preis - entry) / sl_usd
        else:
            r_f4 = (entry - exit_preis) / sl_usd
        r_ref_base: float = entry * sl_pct_ref / 100.0
        r_ref = (
            (exit_preis - entry) / r_ref_base
            if up
            else (entry - exit_preis) / r_ref_base
        )

    return KernelTrade(
        phase=sig.phase, dir=sig.dir, horizont_bars=horizont,
        entry_idx=e, entry_ts=df["ts"].iloc[e], entry_preis=entry,
        f4_initial_stop=initial_stop, sl_usd=sl_usd,
        exit_idx=exit_idx, exit_ts=df["ts"].iloc[exit_idx],
        exit_preis=float(exit_preis), exit_grund=exit_grund,
        haltezeit_bars=haltezeit, r_f4=float(r_f4), r_ref=float(r_ref),
        arm="SWING_REVERSAL",
        trailing_pfad=tuple(pfad) if pfad else None,
    )


# ==============================================================================
# 5) RUNNER & AUSWERTUNG (run_swing_audit, Schritt 2/3 des Plans)
# ==============================================================================

STATUS_REIHENFOLGE: Tuple[SwingSignalStatus, ...] = (
    "SIGNAL",
    "KEINE_ERSCHOEPFUNG",
    "KEINE_EMA_ABFLACHUNG",
    "SL_UEBERSCHRITTEN",
    "RANGE_DEGENERIERT",
    "DATEN_ENDE",
)


def _trade_zeile(t: KernelTrade) -> str:
    """Eine lesbare Trade-Zeile fuer den Textreport (forensisch)."""
    return (
        f"{t.phase:>3} {t.dir:<4} {t.entry_idx:>5} {str(t.entry_ts):>16} "
        f"{t.entry_preis:>8.3f} {t.f4_initial_stop:>8.3f} {t.sl_usd:>7.3f} "
        f"{t.exit_idx:>5} {t.exit_grund:<20} {t.haltezeit_bars:>4} "
        f"{_fmt(t.r_f4):>8}"
    )


def _swing_trade_tsv(trades: Sequence[KernelTrade], fenster: str) -> str:
    """Maschinenlesbarer Trade-Block (TSV) - Spalten identisch zum Produktions-
    TSV (setup_c_trades_*.tsv), damit bestehende Parse-Werkzeuge 1:1 greifen.

    Args:
        trades: Aktivierte SWING_REVERSAL-KernelTrades.
        fenster: Fenster-Label.

    Returns:
        TSV-Text (Kommentarzeilen + Header + Datenzeilen).
    """
    kopf: List[str] = [
        f"# setup_c SWING_REVERSAL (isolierter Audit) - Fenster: {fenster}",
        f"# Modell: Fade kontraer zum 2-Close-Bruch | Sequenz k_exh(Sweep+Docht) -> "
        f"k_trig(Slope-Kipp) | strikte Invalidierung (F-A) | "
        f"terminaler Zeit-Exit N={SWING_ZEIT_HORIZONT} | arm=SWING_REVERSAL",
        "# RECHTS_ZENSIERT: r_f4/r_ref = NaN (E2, strikt isoliert)",
    ]
    header: str = (
        "horizont\tphase\tdir\tentry_idx\tentry_ts\tentry_preis\t"
        "f4_initial_stop\tsl_usd\texit_idx\texit_ts\texit_preis\t"
        "exit_grund\thaltezeit_bars\tr_f4\tr_ref"
    )
    zeilen: List[str] = [*kopf, header]
    for t in sorted(trades, key=lambda x: (x.phase, x.entry_idx)):
        zeilen.append(
            f"{t.horizont_bars}\t{t.phase}\t{t.dir}\t{t.entry_idx}\t"
            f"{t.entry_ts}\t{t.entry_preis:.5f}\t{t.f4_initial_stop:.5f}\t"
            f"{t.sl_usd:.5f}\t{t.exit_idx}\t{t.exit_ts}\t{t.exit_preis:.5f}\t"
            f"{t.exit_grund}\t{t.haltezeit_bars}\t{_fmt(t.r_f4)}\t{_fmt(t.r_ref)}"
        )
    return "\n".join(zeilen)


def run_swing_audit(
    fenster: str, report_dir: Optional[Path] = None
) -> str:
    """Fuehrt den SWING_REVERSAL-Audit fuer ein Fenster aus (Schritt 2/3).

    Laedt das Fenster strikt lesend (DuckDB read_only via
    market_segmentation.load_data), segmentiert, erfasst je echter Bruch-Phase
    genau EINEN Swing-Kandidaten (Fade-Richtung kontraer zum Bruch) und
    simuliert alle SIGNAL-Kandidaten mit dem arretierten Kern
    (Zeit-Exit N=48, Ratchet 1:1). Auswertung: Status-Diagnose je Fenster,
    Performance (sum/mean/median r_f4, WR, PF, sum r_ref) und Exit-Verteilung
    ueber die Produktions-Aggregation (_agg_block/_block_text), damit die
    Aggregations-Semantik bitgenau der Baseline entspricht (E2 strikt isoliert).

    Args:
        fenster: AUG | S1 | S2.
        report_dir: Ausgabeordner (Default = reports/setup_c).

    Returns:
        Reporttext (wird zusaetzlich als setup_c_swing_{F}.txt/.tsv
        geschrieben; Baseline-Artefakte bleiben byte-identisch unberuehrt).
    """
    start, ende = FENSTER_DEFS[fenster]
    seg_cfg: SegmentConfig = SegmentConfig(start=start, ende=ende)
    df: pd.DataFrame = load_data(seg_cfg.db_path, seg_cfg.start, seg_cfg.ende)
    sr: SegmentResult = segmentiere_markt(df, seg_cfg)

    cfg: SwingSignalConfig = SwingSignalConfig()
    ema_arr, slope_arr = berechne_ema_slope_vektoren(
        df, cfg.ema_periode
    )
    echte: List[PhaseData] = [
        p for p in sr.phases if p.break_dir is not None and p.brk_idx is not None
    ]
    kandidaten: List[SwingSignalKandidat] = []
    for nr, p in enumerate(echte, start=1):
        kandidaten.append(
            _erfasse_swing_reversal(df, p, nr, cfg, slope_arr)
        )

    # Status-Diagnose (A4-Triage)
    status_cnt: Dict[str, int] = {s: 0 for s in STATUS_REIHENFOLGE}
    for k in kandidaten:
        status_cnt[str(k.status)] += 1

    # SIGNAL-Simulation (nur echte SIGNAL-Kandidaten; Kern laeuft bis N=48)
    trades: List[KernelTrade] = []
    for k in kandidaten:
        if k.status != "SIGNAL":
            continue
        trades.append(
            _simuliere_kern_swing_reversal(
                df, k, ema_arr, slope_arr,
                horizont=SWING_ZEIT_HORIZONT,
                mindest_gewinn_r=SWING_MINDEST_GEWINN_R,
                slope_schwelle=cfg.slope_schwelle,
                sl_pct_ref=SWING_SL_PCT_REF,
            )
        )

    agg: AggBlock = _agg_block(trades, 0)

    linie: str = "=" * 120
    txt: List[str] = [
        linie,
        "SETUP C - SWING_REVERSAL (Fade) - ISOLIERTER AUDIT "
        "(test/tmp_setup_c_swing_reversal.py)",
        f"Fenster: {fenster} | Symbol: SILVER M15 | df-Bars: {len(df)} | "
        f"Segmente: {len(sr.phases)} | echte F3-Brueche: {len(echte)}",
        f"Modell: Fade kontraer zum 2-Close-Bruch (up->SHORT / down->LONG) | "
        f"Sequenz: k_exh Sweep+Docht(>={cfg.docht_min_verhaeltnis:.2f}) -> "
        f"k_trig Slope-Kipp | strikte Invalidierung (F-A) | "
        f"Scan ab brk_idx+{cfg.scan_start_offset_bars}, "
        f"Fenster {cfg.max_suchfenster_bars} Bars",
        f"Stop-Kappe: max_sl_kanten_mult={cfg.max_sl_kanten_mult:.2f} x Range | "
        f"stop_puffer={cfg.stop_puffer} | slope_schwelle={cfg.slope_schwelle} | "
        f"EMA({cfg.ema_periode})",
        f"Kern: terminaler Zeit-Exit N={SWING_ZEIT_HORIZONT} (ZEIT_EXIT_CLOSE) | "
        f"Ratchet mindest_gewinn_r={SWING_MINDEST_GEWINN_R} | "
        f"r_ref: {SWING_SL_PCT_REF}%-SL | KEINE Crash-Notbremse (F3)",
        linie,
        "",
        "STATUS-DIAGNOSE (je echter Bruch-Phase genau 1 Kandidat):",
    ]
    for s in STATUS_REIHENFOLGE:
        txt.append(f"  {s:<24}: {status_cnt[s]:>4}")
    txt.append("")
    txt.append(linie)
    txt.append(
        f"SWING-REVERSAL-TRADES  |  Horizont N = {SWING_ZEIT_HORIZONT}  "
        "(Close der Bar entry+N) | Zeit-Exit entkoppelt (S3)"
    )
    txt.extend(_block_text("    SWING_REVERSAL", agg))
    txt.append("")

    if trades:
        txt.append(linie)
        txt.append("TRADE-DETAIL (forensisch; phase dir entry_idx entry_ts "
                   "entry stop sl_usd exit_idx exit_grund haltezeit r_f4):")
        txt.append(
            "  " + f"{'Ph':>3} {'Dir':<4} {'EIdx':>5} {'EntryTS':>16} "
            f"{'Entry':>8} {'Stop':>8} {'SL$':>7} {'XIdx':>5} "
            f"{'ExitGrund':<20} {'Hold':>4} {'r_f4':>8}"
        )
        for t in sorted(trades, key=lambda x: (x.phase, x.entry_idx)):
            txt.append("  " + _trade_zeile(t))
        txt.append("")

    txt.append(linie)

    text: str = "\n".join(txt)
    out_dir: Path = (
        report_dir if report_dir is not None
        else PROJECT_ROOT / "reports" / "setup_c"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    out_txt: Path = out_dir / f"setup_c_swing_{fenster}.txt"
    out_txt.write_text(text, encoding="utf-8")
    out_tsv: Path = out_dir / f"setup_c_swing_trades_{fenster}.tsv"
    out_tsv.write_text(_swing_trade_tsv(trades, fenster), encoding="utf-8")
    return text


# ==============================================================================
# 6) MAIN
# ==============================================================================


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI-Einstieg: fuehrt den SWING_REVERSAL-Audit fuer Fenster aus.

    Args:
        argv: Kommandozeilen-Argumente (Default: sys.argv[1:]).

    Returns:
        Exit-Code 0 bei Erfolg.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    fenster: str = "AUG"
    for a in args:
        if a.startswith("--fenster="):
            fenster = a.split("=", 1)[1].upper()
    if fenster == "ALLE":
        fenster_list: List[str] = ["AUG", "S1", "S2"]
    elif fenster in ("AUG", "S1", "S2"):
        fenster_list = [fenster]
    else:
        raise SystemExit(f"Unbekanntes Fenster: {fenster} (AUG|S1|S2|ALLE)")
    out_dir: Path = PROJECT_ROOT / "reports" / "setup_c"
    for f in fenster_list:
        text = run_swing_audit(f, report_dir=out_dir)
        print(text)
        print(
            f"\nReport geschrieben: {out_dir / f'setup_c_swing_{f}.txt'} | "
            f"{out_dir / f'setup_c_swing_trades_{f}.tsv'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
