"""
SETUP C - SCHRITT 4a: ZEIT-EXIT-MATRIX MIT RECHTS-ZENSIERUNG (test/tmp_setup_c_zeitexit.py)
============================================================================================
Status: ENTWURF ZUR DURCHSICHT (05.09.2026) - KEINE Ausfuehrung/Kompilierung.
Doku: docs/setup_c_experiment.md (Schritt 4a: E1-E5 + Datenvertrag in §2.8).
Baseline: scripts/phasen_volumen_profil.py (v0.4.0-frozen) - UNVERAENDERT.
Arbeitsmodus: isoliertes, rein lesendes Replay (DuckDB read_only via
      tmp_setup_c_audit.py), keine Produktions-Integration, keine Charts.

Zweck
-----
Bereinigt das 274R-Mess-Artefakt aus Schritt 3 (C1/C2, Befund in §2.7): Der
unendliche DATEN_ENDE-Benchmark von KEIN_TRAILING (S2 +274,48R aus Laeufern mit
Haltedauer bis >1000 Bars) wird durch eine feste Horizont-Matrix N in {24,48,96}
M15-Bars als TERMINALE EXIT-REGEL ersetzt. Rechts-zensierte Signale werden strikt
aus der Performance-Berechnung isoliert. Arm 1 (RAW) wird nach Vorlauf-Cluster
getrennt ausgewertet (Cluster A <= 1 Bar vs. Cluster B > 1 Bar).

Arretierte Beschluesse (Doku §2.8, E1-E5)
-----------------------------------------
E1  Horizont-Matrix N in {24,48,96} als terminale Exit-Regel (Close der
    Exit-Bar e+N). 24 = S1-Reversal-Faenger; 48 = Primaeranker (kompatibel zur
    MFE@48-Matrix aus Schritt 1/2); 96 = S2-Trend-Raum ohne endloses Mitschleppen.
E2  Rechts-Zensierung: exit_bar = entry_idx + N existiert nicht in den Daten
    (entry_idx + N > n-1) UND der Trade ueberlebt bis zum Datenende ->
    Status RECHTS_ZENSIERT, r_f4/r_ref = NaN, strikt aus Performance isoliert,
    separat ausgewiesen. VORHER regulaer aufgeloeste Trades (Stop) zaehlen
    normal mit ihrem realisierten R - auch wenn die Exit-Bar jenseits des
    Datensatzendes gelegen haette (Mentor-Urteil Punkt 2).
E3  RAW-Cluster: Cluster A (vorlauf_bars <= cluster_a_max_vorlauf=1) = frische
    Ausbrueche an der Kante; Cluster B (vorlauf_bars > 1) = Range-Akkumulation
    (separate Population). Getrennte Auswertung, keine Vermischung.
E4  Arm-Fokus: RAW primaer (Cluster A/B getrennt); CONFIRMED (Negativ-Kontrolle
    fuer C4) und RETEST (Zeit-Exit als Cap) als Referenz.
E5  Exit-Matrix {24,48,96} x {KEIN_TRAILING, VAR_A_FIXED}: F4-Initial-Stop
    INTRABAR (F11 unveraendert); VAR_A-FIXED-Trailing CLOSE-basiert (C5);
    Puffer fixed_buffer = 0.15 USD. KEIN_TRAILING + Zeit-Exit = produktionsnahes
    Pendant zum 274R-DATEN_ENDE-Benchmark.

Exit-Prioritaet (Mentor-Urteil vor Code-Erstellung)
---------------------------------------------------
1. An der exakten Bar entry_idx + N hat der aktive STOP IMMER VORRANG vor dem
   Zeit-Exit: Wer intrabar sein Stop-Level beruehrt (F4: low <= stop / high >=
   stop), ist ausgestoppt, bevor die Kerze zum Zeit-Exit schliessen kann.
2. Zeit-Exit greift ausschliesslich am SCHLUSSKURS (close) der Exit-Bar, sofern
   zuvor kein Stop ausgeloest wurde.
3. Kausalitaet der Trailing-Ratsche identisch zu Schritt 3 (DV2): Pivot bei Bar
   p nach Close von p+2 bestaetigt; Stop-Aenderung wirksam ab Bar p+3
   (Exit-Check von k=p+2 zuerst, neuer Stop ab k+1).

Wiederverwendung (keine Duplizierung)
-------------------------------------
- Signal-Erfassung + F4-Stop: importiert aus tmp_setup_c_audit.py
  (resegmentiere, erfasse_confirmed, erfasse_raw, erfasse_retest).
- Pivot-Stufen + ATR-Semantik der Ratsche: importiert aus tmp_setup_c_trailing.py
  (_pivot_stufen) - Referenz-Simulationslogik aus Schritt 3.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

TEST_DIR: Path = Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

import tmp_setup_c_audit as audit  # noqa: E402  (Signalerfassung, F4-Stop)
import tmp_setup_c_trailing as trailing  # noqa: E402  (_pivot_stufen, Ratsche-Referenz)

# ==============================================================================
# 1) TYPALIASSE & DATENVERTRAEGE (Doku §2.8 - freigegeben)
# ==============================================================================

ArmName = Literal["RAW", "CONFIRMED", "RETEST"]
RawCluster = Literal["CLUSTER_A_ENG", "CLUSTER_B_WEIT", "NICHT_RAW"]
DirName = Literal["up", "down"]
TrailingModus = Literal["KEIN_TRAILING", "VAR_A_FIXED"]
ExitGrund = Literal[
    "INITIAL_SL_INTRABAR",   # F11: F4-Stop intrabar beruehrt (Vorrang vor Zeit-Exit)
    "TRAILING_SL_CLOSE",     # E5/C5: Trailing-Stufe, Close jenseits des Stops
    "ZEIT_EXIT_CLOSE",       # E1: Horizont N erreicht, Close der Exit-Bar e+N
    "RECHTS_ZENSIERT",       # E2: bis Datenende ueberlebt, Horizont nicht abgelaufen
]

# Lauf-Reihenfolge in Report & Matrix
MODI: Tuple[TrailingModus, ...] = ("KEIN_TRAILING", "VAR_A_FIXED")
# Ausgabe-Reihenfolge der Gruppen (RAW_A/RAW_B zusaetzlich zu RAW-GESAMT)
GRUPPEN_REPORT: Tuple[str, ...] = (
    "CONFIRMED", "RAW-CLUSTER-A", "RAW-CLUSTER-B", "RAW-GESAMT", "RETEST", "GESAMT",
)
# Vergleichs-Spalten ohne RAW-GESAMT (vermeidet Doppelzaehlung in Summen)
GRUPPEN_MATRIX: Tuple[str, ...] = ("CONFIRMED", "RAW_A", "RAW_B", "RETEST", "GESAMT")
# Zuordnung Report-Anzeigename -> Matrix-Key (fuer die Detailbloecke)
REPORT_GRUPPE_KEY: Dict[str, str] = {
    "CONFIRMED": "CONFIRMED",
    "RAW-CLUSTER-A": "RAW_A",
    "RAW-CLUSTER-B": "RAW_B",
    "RETEST": "RETEST",
}


@dataclass(frozen=True, slots=True)
class ZeitexitConfig:
    """Konfiguration fuer den Zeit-Exit-Vergleich (Setup C Schritt 4a, E1-E5).

    Defaults = arretierte Beschluesse; Aenderungen nur als dokumentierte
    Sensitivitaeten (nicht fuer den Freigabe-Lauf).
    """

    fenster: Literal["AUG", "S1", "S2"] = "AUG"
    symbol: str = "SILVER"
    timeframe: str = "M15"

    # E1: Horizont-Matrix (terminale Exit-Regel, Close der Exit-Bar e+N)
    zeit_horizonte: Tuple[int, ...] = (24, 48, 96)
    # E3: Cluster-A-Schwelle (RAW-Vorlauf <= 1 Bar vor dem 2-Close-Bruch)
    cluster_a_max_vorlauf: int = 1

    # E5: Stop-/Trailing-Parameter (F4 unveraendert, VAR_A close-basiert)
    pivot_lookback: int = 2                  # Baseline find_pivots (DV2)
    fixed_buffer: float = 0.15               # USD: F4-Puffer & VAR_A-Trailing-Puffer
    sl_pct_ref: float = 0.45                 # 0.45%-Referenz (r_ref-Basis)


@dataclass(slots=True)
class ZeitexitResult:
    """Simulationsergebnis fuer ein Signal unter Zeit-Exit (Doku §2.8).

    Fuer RECHTS_ZENSIERT sind r_f4 und r_ref NaN (E2); exit_idx/exit_ts/
    exit_preis/haltezeit_bars dokumentieren dann das Datenende transparenzhalber.
    """

    arm: ArmName
    raw_cluster: RawCluster
    phase: int
    dir: DirName
    horizont_bars: int
    modus: TrailingModus

    entry_idx: int
    entry_ts: pd.Timestamp
    entry_preis: float
    f4_initial_stop: float
    sl_usd: float

    exit_idx: int
    exit_ts: pd.Timestamp
    exit_preis: float
    exit_grund: ExitGrund
    haltezeit_bars: int

    # R-Multiples (NaN bei RECHTS_ZENSIERT)
    r_f4: float
    r_ref: float


# ==============================================================================
# 2) HILFSFUNKTIONEN (Signal-Erfassung, Cluster, Gruppen)
# ==============================================================================


def _signale_fenster(fenster: str) -> Tuple[pd.DataFrame, List[audit.AuditSignal]]:
    """Erfasst alle SIGNAL-Signale eines Fensters ueber die Schritt-2-Routinen.

    Args:
        fenster: AUG | S1 | S2.

    Returns:
        Tuple aus (df, Liste der AuditSignale mit status SIGNAL, sl_usd > 0).
        RAW-Signale tragen vorlauf_bars (brk_idx - trigger_idx) fuer E3.
    """
    cfg = audit.AuditConfig(fenster=fenster)
    start, ende = audit.FENSTER_DEFS[fenster]
    sr = audit.resegmentiere(start, ende)
    df: pd.DataFrame = sr.df
    min_phase_candles: int = int(sr.ns["MIN_PHASE_CANDLES"])
    vol_bed, vol_ref = audit._volumen_bestaetigt(df, cfg)
    echte = [p for p in sr.phases if p.break_dir is not None and p.brk_idx is not None]
    alle: List[audit.AuditSignal] = []
    for nr, p in enumerate(echte, start=1):
        alle.append(audit.erfasse_confirmed(df, p, nr, cfg))
        alle.extend(audit.erfasse_raw(df, p, nr, cfg, vol_bed, vol_ref, min_phase_candles))
        alle.append(audit.erfasse_retest(df, p, nr, cfg))
    sigs = [s for s in alle
            if s.status == "SIGNAL" and s.entry_idx >= 0
            and np.isfinite(s.sl_usd) and s.sl_usd > 0.0]
    return df, sigs


def _raw_cluster(sig: audit.AuditSignal, cfg: ZeitexitConfig) -> RawCluster:
    """Ordnet ein Signal dem RAW-Cluster A/B zu (E3).

    Args:
        sig: AuditSignal (RAW-Signale tragen vorlauf_bars).
        cfg: ZeitexitConfig (cluster_a_max_vorlauf).

    Returns:
        CLUSTER_A_ENG (vorlauf <= 1), CLUSTER_B_WEIT (> 1) oder NICHT_RAW.
    """
    if sig.arm != "RAW" or sig.vorlauf_bars is None:
        return "NICHT_RAW"
    return "CLUSTER_A_ENG" if sig.vorlauf_bars <= cfg.cluster_a_max_vorlauf else "CLUSTER_B_WEIT"


def _gruppen_schluessel(cluster: RawCluster, arm: ArmName) -> str:
    """Interne Matrix-Gruppe eines Ergebnisses (CONFIRMED/RAW_A/RAW_B/RETEST).

    Args:
        cluster: RawCluster des Signals.
        arm: Arm des Signals.

    Returns:
        Gruppenname (CONFIRMED | RAW_A | RAW_B | RETEST).
    """
    if arm == "RAW":
        return "RAW_A" if cluster == "CLUSTER_A_ENG" else "RAW_B"
    return arm  # CONFIRMED | RETEST


# ==============================================================================
# 3) SIMULATIONSKERN (zustandsbehaftete Ratsche + terminaler Zeit-Exit, kausal)
# ==============================================================================


def simuliere_zeitexit(
    df: pd.DataFrame,
    sig: audit.AuditSignal,
    cfg: ZeitexitConfig,
    modus: TrailingModus,
    horizont: int,
    pivot_hi: np.ndarray,
    pivot_lo: np.ndarray,
) -> ZeitexitResult:
    """Simuliert ein Signal unter terminalem Zeit-Exit (E1-E5).

    Zustandsbehaftete Ratsche (wie Schritt 3) mit harter Zeitschranke: Bar fuer
    Bar ab dem Einstieg bis min(entry+N, Datenende). Reihenfolge je Bar:
      1) Exit gegen den aktiven Stop (F4 intrabar / Trailing close) - hat
         VORRANG vor dem Zeit-Exit (Mentor-Urteil Punkt 1).
      2) Zeit-Exit am Close, sobald k == entry_idx + N (nur falls kein Stop).
      3) Pivot-Bestaetigung an Bar k = p + lookback verarbeiten (neuer Stop ab
         k+1, DV2) - nur fuer modus VAR_A_FIXED und k < Exit-Bar.
    Ueberlebt der Trade das Datenende ohne Stop und ohne erreichten Horizont
    (entry+N > n-1), gilt er als RECHTS_ZENSIERT (E2, r = NaN).

    Args:
        df: OHLCV-DataFrame.
        sig: AuditSignal (status SIGNAL, sl_usd > 0).
        cfg: ZeitexitConfig.
        modus: KEIN_TRAILING (nur F4) oder VAR_A_FIXED (Pivot-Stufen-Trailing).
        horizont: Zeit-Horizont N in Bars (24/48/96).
        pivot_hi: Pivot-Hoch-Array (NaN ausserhalb).
        pivot_lo: Pivot-Tief-Array (NaN ausserhalb).

    Returns:
        ZeitexitResult.
    """
    n: int = len(df)
    e: int = int(sig.entry_idx)
    up: bool = sig.dir == "up"
    entry: float = float(df["open"].values[e])
    f4_stop: float = float(sig.stop_level)
    sl_usd: float = float(sig.sl_usd)
    high: np.ndarray = df["high"].values.astype(float)
    low: np.ndarray = df["low"].values.astype(float)
    close: np.ndarray = df["close"].values.astype(float)
    lb: int = cfg.pivot_lookback
    cluster: RawCluster = _raw_cluster(sig, cfg)

    ziel_bar: int = e + horizont          # Exit-Bar (Close), E1
    letzte_bar: int = n - 1
    loop_ende: int = min(ziel_bar, letzte_bar)

    stop: float = f4_stop
    stop_art: Literal["INITIAL", "TRAILING"] = "INITIAL"
    exit_grund: ExitGrund = "RECHTS_ZENSIERT"   # Default, falls Loop ohne Break endet
    exit_idx: int = letzte_bar
    exit_preis: float = float(close[letzte_bar])

    for k in range(e, loop_ende + 1):
        # --- 1) Exit gegen den aktiven Stop (VORRANG vor Zeit-Exit) ----------
        if stop_art == "INITIAL":
            # F11: F4-Initial-Stop intrabar wirksam
            if (up and low[k] <= stop) or ((not up) and high[k] >= stop):
                exit_preis, exit_idx, exit_grund = float(stop), k, "INITIAL_SL_INTRABAR"
                break
        else:
            # E5/C5: Trailing-Stufe close-basiert
            if (up and close[k] < stop) or ((not up) and close[k] > stop):
                exit_preis, exit_idx, exit_grund = float(close[k]), k, "TRAILING_SL_CLOSE"
                break

        # --- 2) Terminaler Zeit-Exit am Close der Exit-Bar --------------------
        if k == ziel_bar:
            exit_preis, exit_idx, exit_grund = float(close[k]), k, "ZEIT_EXIT_CLOSE"
            break

        # --- 3) Trailing-Ratsche (nur VAR_A_FIXED, Stop ab k+1 wirksam) ------
        if modus == "KEIN_TRAILING":
            continue
        p: int = k - lb
        if p >= e:
            if up:
                pv: float = float(pivot_lo[p]) if not np.isnan(pivot_lo[p]) else float("nan")
                if np.isfinite(pv):
                    stufe: float = pv - cfg.fixed_buffer
                    if stop_art == "INITIAL":
                        # F9/DV1: Aktivierung erst wenn Stufe > Entry (nach Puffer)
                        if stufe > entry:
                            stop_art = "TRAILING"
                            stop = stufe
                    else:
                        if stufe > stop:
                            stop = stufe
            else:
                pv = float(pivot_hi[p]) if not np.isnan(pivot_hi[p]) else float("nan")
                if np.isfinite(pv):
                    stufe = pv + cfg.fixed_buffer
                    if stop_art == "INITIAL":
                        if stufe < entry:
                            stop_art = "TRAILING"
                            stop = stufe
                    else:
                        if stufe < stop:
                            stop = stufe

    # --- R-Multiples (E2: NaN bei RECHTS_ZENSIERT) ----------------------------
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
        r_ref_base: float = entry * cfg.sl_pct_ref / 100.0
        r_ref = (exit_preis - entry) / r_ref_base if up else (entry - exit_preis) / r_ref_base

    return ZeitexitResult(
        arm=sig.arm, raw_cluster=cluster, phase=sig.phase, dir=sig.dir,
        horizont_bars=horizont, modus=modus,
        entry_idx=e, entry_ts=df["ts"].iloc[e], entry_preis=entry,
        f4_initial_stop=f4_stop, sl_usd=sl_usd,
        exit_idx=exit_idx, exit_ts=df["ts"].iloc[exit_idx],
        exit_preis=float(exit_preis), exit_grund=exit_grund,
        haltezeit_bars=haltezeit,
        r_f4=float(r_f4), r_ref=float(r_ref),
    )


# ==============================================================================
# 4) AGGREGATION & REPORT
# ==============================================================================


def _agg_block(results: Sequence[ZeitexitResult]) -> Dict[str, Any]:
    """Aggregiert ZeitexitResults (zensierte werden strikt isoliert, E2)."""
    out: Dict[str, Any] = {
        "n_total": len(results),
        "n_zensiert": 0,
        "n_gewertet": 0,
        "sum_r_f4": 0.0, "mean_r_f4": float("nan"), "median_r_f4": float("nan"),
        "wr": float("nan"), "pf": float("inf"),
        "sum_r_ref": 0.0,
        "n_init": 0, "n_trail": 0, "n_zeit": 0,
        "mean_offset": float("nan"),
    }
    if not results:
        return out
    rs: List[float] = []
    offsets: List[int] = []
    for r in results:
        if r.exit_grund == "RECHTS_ZENSIERT":
            out["n_zensiert"] += 1
            continue  # E2: strikt aus Performance-Berechnung isoliert
        if r.exit_grund == "INITIAL_SL_INTRABAR":
            out["n_init"] += 1
        elif r.exit_grund == "TRAILING_SL_CLOSE":
            out["n_trail"] += 1
        else:
            out["n_zeit"] += 1
        rs.append(float(r.r_f4))
        out["sum_r_ref"] += float(r.r_ref)
        offsets.append(r.haltezeit_bars)
    n_gew: int = len(rs)
    out["n_gewertet"] = n_gew
    if not n_gew:
        return out
    arr: np.ndarray = np.array(rs, dtype=float)
    out["sum_r_f4"] = float(arr.sum())
    out["mean_r_f4"] = float(arr.mean())
    out["median_r_f4"] = float(np.median(arr))
    out["wr"] = float(np.mean(arr > 0.0) * 100.0)
    pos: float = float(arr[arr > 0.0].sum())
    neg: float = float(-arr[arr < 0.0].sum())
    out["pf"] = pos / neg if neg > 0.0 else float("inf")
    out["mean_offset"] = float(np.mean(offsets)) if offsets else float("nan")
    return out


def _fmt(v: Any, fmt: str = ".2f") -> str:
    """Formatiert Zahlen (NaN/None -> '-')."""
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "-"
    return f"{v:{fmt}}"


def _block_text(titel: str, agg: Dict[str, Any]) -> List[str]:
    """Formatiert einen Aggregationsblock fuer eine Gruppe."""
    t = f"{titel}  (n={agg['n_total']}, zensiert={agg['n_zensiert']}, gewertet={agg['n_gewertet']})"
    lines: List[str] = [t, "  " + "-" * max(2, len(t) - 2)]
    if not agg["n_gewertet"]:
        lines.append("  (keine gewerteten Trades - nur RECHTS_ZENSIERT)")
        return lines
    lines.append(
        f"  sum r_f4={agg['sum_r_f4']:>9.2f}  mean r_f4={_fmt(agg['mean_r_f4']):>7}  "
        f"median={_fmt(agg['median_r_f4']):>7}  WR={_fmt(agg['wr'], '.1f')}%  "
        f"PF={_fmt(agg['pf'])}"
    )
    lines.append(f"  sum r_ref (0.45%-Basis) = {agg['sum_r_ref']:.2f}")
    lines.append(
        f"  Exit: INITIAL_SL_INTRABAR={agg['n_init']} | TRAILING_SL_CLOSE={agg['n_trail']} "
        f"| ZEIT_EXIT_CLOSE={agg['n_zeit']} | RECHTS_ZENSIERT={agg['n_zensiert']}"
    )
    lines.append(f"  mittl. Haltedauer (gewertet) = {_fmt(agg['mean_offset'], '.0f')} Bars")
    return lines


def _bericht_fenster(fenster: str) -> str:
    """Baut den Report fuer ein Fenster (alle Horizonte x Modi)."""
    df, sigs = _signale_fenster(fenster)
    pivot_hi, pivot_lo = trailing._pivot_stufen(df, 2)
    cfg = ZeitexitConfig(fenster=fenster)

    # Cluster-Zaehlung fuer den Kopf (E3)
    n_raw_a = sum(1 for s in sigs if _raw_cluster(s, cfg) == "CLUSTER_A_ENG")
    n_raw_b = sum(1 for s in sigs if _raw_cluster(s, cfg) == "CLUSTER_B_WEIT")

    # Alle Laeufe vorab berechnen: laeufe[(N, modus)][Gruppe] = List[ZeitexitResult]
    laeufe: Dict[Tuple[int, TrailingModus], Dict[str, List[ZeitexitResult]]] = {}
    for horizont in cfg.zeit_horizonte:
        for modus in MODI:
            gruppen: Dict[str, List[ZeitexitResult]] = {k: [] for k in GRUPPEN_MATRIX}
            for s in sigs:
                res = simuliere_zeitexit(df, s, cfg, modus, horizont, pivot_hi, pivot_lo)
                gruppen["GESAMT"].append(res)
                gruppen[_gruppen_schluessel(res.raw_cluster, res.arm)].append(res)
            laeufe[(horizont, modus)] = gruppen

    linie = "=" * 120
    txt: List[str] = [
        linie,
        "SETUP C - SCHRITT 4a: ZEIT-EXIT-MATRIX (tmp_setup_c_zeitexit.py)",
        f"Fenster: {fenster} | Symbol: {cfg.symbol} {cfg.timeframe} | Datum: 2026-09-05 | Baseline: {audit.BASELINE_REF}",
        "E1 Horizonte 24/48/96 (Close e+N) | E2 RECHTS_ZENSIERT isoliert | E3 RAW-Cluster A<=1/B>1 | "
        "E5 F4 intrabar / VAR_A close / Zeit-Exit close",
        linie,
        f"df-Bars: {len(df)} | SIGNAL-Signale: CONFIRMED="
        f"{sum(1 for s in sigs if s.arm=='CONFIRMED')} RAW="
        f"{sum(1 for s in sigs if s.arm=='RAW')} (CLUSTER_A={n_raw_a}, CLUSTER_B={n_raw_b}) "
        f"RETEST={sum(1 for s in sigs if s.arm=='RETEST')}",
        "",
    ]

    # --- Detailbloecke je Horizont x Modus -----------------------------------
    for horizont in cfg.zeit_horizonte:
        txt.append(linie)
        txt.append(f"HORIZONT N = {horizont}  ({horizont} M15-Bars; Exit am Close der Bar entry+{horizont})")
        txt.append("")
        for modus in MODI:
            gruppen = laeufe[(horizont, modus)]
            txt.append(linie)
            txt.append(f"  LAUF: modus={modus}  |  F4 intrabar | ZEIT_EXIT close "
                       f"{'| VAR_A close (0.15 USD)' if modus == 'VAR_A_FIXED' else '| kein Trailing'}")
            for grp_name in GRUPPEN_REPORT:
                if grp_name == "RAW-GESAMT":
                    # RAW-GESAMT = RAW_A + RAW_B (identische Populationen)
                    ges_raw: List[ZeitexitResult] = (
                        gruppen["RAW_A"] + gruppen["RAW_B"]
                    )
                    txt.extend(_block_text(f"    {grp_name}", _agg_block(ges_raw)))
                    continue
                if grp_name == "GESAMT":
                    txt.extend(_block_text(f"    {grp_name}", _agg_block(gruppen["GESAMT"])))
                    continue
                key: str = REPORT_GRUPPE_KEY[grp_name]
                txt.extend(_block_text(f"    {grp_name}", _agg_block(gruppen[key])))
            txt.append("")

    # --- Vergleichstabellen je Horizont ---------------------------------------
    txt.append(linie)
    txt.append("VERGLEICH je Horizont  (sum r_f4 je Gruppe; zensiert in Klammern)")
    for horizont in cfg.zeit_horizonte:
        txt.append("")
        txt.append(f"  N = {horizont}:")
        txt.append(f"    {'Lauf':<14} {'CONFIRMED':>14} {'RAW_A':>12} {'RAW_B':>12} "
                   f"{'RETEST':>12} {'GESAMT':>16}")
        for modus in MODI:
            gruppen = laeufe[(horizont, modus)]
            zellen: List[str] = []
            for grp in GRUPPEN_MATRIX:
                agg = _agg_block(gruppen[grp])
                z = "keine" if not agg["n_gewertet"] else f"{agg['sum_r_f4']:.2f}"
                zell_text: str = f"{z} ({agg['n_zensiert']})"
                zellen.append(f"{zell_text:>14}")
            txt.append(f"    {modus:<14} {'  '.join(zellen)}")
    txt.append(linie)

    # --- Gesamtmatrix N x Modus -----------------------------------------------
    txt.append(linie)
    txt.append("GESAMT-UEBERSICHT  (sum r_f4; n_zensiert/n_gewertet)")
    txt.append(f"    {'N':<3} {'Lauf':<14} {'CONFIRMED':>14} {'RAW_A':>12} {'RAW_B':>12} "
               f"{'RETEST':>12} {'GESAMT':>16}")
    for horizont in cfg.zeit_horizonte:
        for modus in MODI:
            gruppen = laeufe[(horizont, modus)]
            zellen = []
            for grp in GRUPPEN_MATRIX:
                agg = _agg_block(gruppen[grp])
                z = "keine" if not agg["n_gewertet"] else f"{agg['sum_r_f4']:.2f}"
                zell_text = f"{z} ({agg['n_zensiert']}/{agg['n_gewertet']})"
                zellen.append(f"{zell_text:>14}")
            txt.append(f"    {horizont:<3} {modus:<14} {'  '.join(zellen)}")
    txt.append(linie)

    text: str = "\n".join(txt)
    out: Path = TEST_DIR / f"tmp_setup_c_zeitexit_{fenster}.txt"
    out.write_text(text, encoding="utf-8")
    return text


# ==============================================================================
# 5) MAIN
# ==============================================================================


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI-Einstieg: fuehrt den Zeit-Exit-Vergleich fuer Fenster aus.

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
    for f in fenster_list:
        text = _bericht_fenster(f)
        print(text)
        print(f"\nReport geschrieben: {TEST_DIR / f'tmp_setup_c_zeitexit_{f}.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
