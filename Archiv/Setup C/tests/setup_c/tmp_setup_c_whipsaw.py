"""
SETUP C - SCHRITT 4b STUFE 2: WHIPSAW-SCAN & NETTO-GEGENRECHNUNG (test/tmp_setup_c_whipsaw.py)
===============================================================================================
Status: ENTWURF ZUR DURCHSICHT (05.09.2026) - KEINE Ausfuehrung/Kompilierung.
Doku: docs/setup_c_experiment.md (Schritt 4b: G5 in §2.10, H1-H4 in §2.11).
Baseline: scripts/phasen_volumen_profil.py (v0.4.0-frozen) - UNVERAENDERT.
Arbeitsmodus: isoliertes, rein lesendes Replay (DuckDB read_only via
      tmp_setup_c_audit.py), keine Produktions-Integration, keine Charts.

Zweck
-----
G5-Stufe-2 (Eintrittsbedingung aus H4 erfuellt): Gegenrechnen der
1-Close-Fehlausbrueche (Whipsaws), die in der Stufe-1-Stichprobe (nur echte
2-Close-Brueche = F3) fehlen -> Survivorship-Korrektur der 1-Close-Kante.
Netto = Stufe-1-Summe + Summe der Whipsaw-Trades. Urteil: Ueberlebt der
1-Close-Vorteil (H3: 6/6 Zellen, S1 Delta r_ref bis +52R) die Gegenrechnung?

Ratifizierte Beschluesse (05.09.2026, Mentor-Urteil + Antworten F1-F3)
----------------------------------------------------------------------
F1  Whipsaw-Definition (Negativ-Spiegel des Baseline-Compilers): Innen-Bar
    j < brk_idx einer F3-Phase mit 1-Close-Trigger
        up:   close[j] >  kante(j) + TOL
        down: close[j] <  kante(j) - TOL
    und fehlender 2-Close-Bestaetigung an j+1 GEGEN DIESELBE Kante:
        up:   close[j+1] <= kante(j) + TOL   (sonst waere j der Bruch)
        down: close[j+1] >= kante(j) - TOL
    Keine kuenstliche Verschaerfung "zurueck in die Range" (Retail-Optimismus).
    Sub-Typen diagnostisch: RETRACE (close[j+1] <= kante(j)  bzw. >= kante(j))
    vs. TOL_BAND (nur an der TOL-Grenze gescheitert).
    Kante(j) = kausal rekonstruierte Kante aus U_hist/L_hist (audit._kanten_reihe,
    D4-Doktrin). KEIN U_final/L_final-Lookahead, KEIN Kreuz-Fallback.
F2  Abwicklung: KEIN pauschales -1R. Jeder Whipsaw laeuft durch den regulären
    Simulationskern zeitexit.simuliere_zeitexit(modus="KEIN_TRAILING",
    N in {48,96}) mit G2-kausalem Stop (nur Triggerkerze j) und Rechts-
    Zensierung E2. Ein Whipsaw kann den spaeteren echten Bruch ueberleben und
    als frueher Einstieg positiv enden; pauschal -1R wuerde das Setup
    verstaemmeln, pauschal 0 die echten Trap-Kosten unterschlagen.
F3  Mehrfach-Trigger: Default Open-Position-Suppression (kein Folge-Entry
    derselben Richtung derselben Phase, solange eine akzeptierte Whipsaw-
    Position offen ist; e <= exit_idx der offenen Position -> supprimiert).
    KEIN fester N-Bar-Cooldown (Willkuer). Sensitivitaet "ohne Suppression"
    als Kontrollspalte (alle Kandidaten unabhaengig).
    Stufe-1-Einstiege (open[b+1] am echten Bruch) sind NICHT Teil der
    Suppression: Das Netto ist additiv auf Event-Basis (Stufe-1-Trades werden
    nicht neu simuliert, sondern aus dem identischen 1close-Codepfad bezogen).
Scope (bestätigt): Strikt die F3-Bruchphasen der Stufe-1-Population
    (AUG=11, S1=138, S2=61). Nur die BRUCH-RICHTUNG wird gescannt (Spiegel
    der Stufe-1-Einstiege). Gegenrichtungs-Piercings gehoeren zu einem anderen
    (Fading-)Setup und wuerden Populationen mischen (kein Apfel-mit-Birnen).
    Nicht-Bruch-Phasen (DATEN_ENDE) bleiben außen vor.

Wiederverwendung (keine Duplizierung)
-------------------------------------
- Segmentierung + F3-Phasen: audit.resegmentiere (exec-Slice, bitgenau).
- Stufe-1-Referenz (1-Close + 2-Close): tmp_setup_c_1close._paar_fenster /
  _simuliere_paare / _agg_block / _block_text / _fmt - IDENTISCHER Codepfad
  zum Schritt-4b-Stufe-1-Report (kein Drift). Die Phasenmenge des Whipsaw-
  Scans wird auf die Phasen-Nummern der 1close-Paare eingeschraenkt
  (deckungsgleich per Konstruktion).
- Kausale Kantenreihe: audit._kanten_reihe (D4-Doktrin, hist-Stufenfunktion).
- F4-Stop: audit._stop_f4 (G2-kausal: lo_struktur=hi_struktur=Triggerkerze).
- Exit-Simulation: zeitexit.simuliere_zeitexit (KEIN_TRAILING, E2-Zensierung).
- Pivot-Arrays (sim-Kompatibilitaet): trailing._pivot_stufen(df, 2).

Bekannte, dokumentierte Grenzfaelle (kein Fix, da selten und konservativ)
-------------------------------------------------------------------------
1) Kanten-Shift zwischen j und j+1 > TOL (Range-Expansion innerhalb des
   Piercing-Paares): Der Negativ-Test nutzt die Kante der Trigger-Bar j
   (F1-ratifiziert). Ein Trigger, dessen Folge-Close die ALTE Kante ueber-
   schreitet, aber gegen die NEUE (hoehere) Kante scheitert, wird NICHT als
   Whipsaw gezaehlt (bleibt der Stufe-1-Bruchbar-Konvention ueberlassen).
   Erfordert einen Kanten-Shift > TOL zwischen zwei Bars - selten.
2) Kantenrekonstruktion mit SHIFT_TOL-Granularitaet (0.05 USD): Die hist-
   Stufenfunktion weicht gegenueber der Baseline-Inline-Kante (U_j live) um
   maximal SHIFT_TOL ab - identische Naherung wie in Schritt 2/4a (RAW, D4).
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

import tmp_setup_c_audit as audit  # noqa: E402  (Segmentierung, _kanten_reihe, _stop_f4, _phase_start_idx)
import tmp_setup_c_trailing as trailing  # noqa: E402  (_pivot_stufen fuer sim-Kompatibilitaet)
import tmp_setup_c_zeitexit as zeitexit  # noqa: E402  (simuliere_zeitexit, KEIN_TRAILING, E2)
import tmp_setup_c_1close as oneclose  # noqa: E402  (Stufe-1-Referenz, identischer Codepfad)

# ==============================================================================
# 1) TYPALIASSE & DATENVERTRAEGE (freigegeben, 05.09.2026)
# ==============================================================================

WhipsawTyp = Literal["RETRACE", "TOL_BAND"]
DirName = Literal["up", "down"]
ExitGrund = Literal[
    "INITIAL_SL_INTRABAR",   # F4/G2: Stop intrabar beruehrt (Vorrang vor Zeit-Exit)
    "ZEIT_EXIT_CLOSE",       # E1/G3: Horizont N erreicht, Close der Exit-Bar e+N
    "RECHTS_ZENSIERT",       # E2: bis Datenende ueberlebt, Horizont nicht abgelaufen
]


@dataclass(frozen=True, slots=True)
class WhipsawConfig:
    """Konfiguration fuer den Whipsaw-Scan (Setup C Schritt 4b Stufe 2).

    Defaults = arretierte Beschluesse (F1-F3 + Scope). Aenderungen nur als
    dokumentierte Sensitivitaeten (nicht fuer den Freigabe-Lauf).
    """

    fenster: Literal["AUG", "S1", "S2"] = "AUG"
    symbol: str = "SILVER"
    timeframe: str = "M15"

    # G3: Exit-Horizonte (Best-Practice aus D2, identisch zu Stufe 1)
    zeit_horizonte: Tuple[int, ...] = (48, 96)
    # G2/F4: Puffer unter Struktur/Kante (USD) - identisch zu OneCloseConfig
    fixed_buffer: float = 0.15
    # G4: Neutrale 0.45%-Referenz (stop-unabhaengige Dollar-Benchmark)
    sl_pct_ref: float = 0.45
    # F3: Default Open-Position-Suppression (True); False = Sensitivitaetslauf
    suppression_aktiv: bool = True


@dataclass(slots=True)
class WhipsawResult:
    """Simulationsergebnis fuer einen Whipsaw-Trade (Doku F1-F3).

    Fuer RECHTS_ZENSIERT sind r_f4 und r_ref NaN (E2); exit_idx/exit_ts/
    exit_preis/haltezeit_bars dokumentieren das Datenende transparenzhalber.
    whipsaw_typ klassifiziert den Fehlausbruch (RETRACE vs. TOL_BAND).
    """

    phase: int
    dir: DirName
    whipsaw_typ: WhipsawTyp
    horizont_bars: int

    trigger_idx: int                 # Bar j (Piercing-Close, 1-Close-Trigger)
    entry_idx: int                   # Bar j+1 (open[j+1])
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


@dataclass(slots=True)
class _Kandidat:
    """Interner Whipsaw-Kandidat (vor der Suppression/Simulation)."""

    sig: audit.AuditSignal
    typ: WhipsawTyp


# ==============================================================================
# 2) WHIPSAW-SCAN (F1: Negativ-Spiegel des Baseline-Compilers, BRUCH-RICHTUNG)
# ==============================================================================


def _whipsaw_kandidaten(
    df: pd.DataFrame,
    p: Any,
    nr: int,
    acfg: audit.AuditConfig,
    min_phase_candles: int,
    tol: float,
) -> List[_Kandidat]:
    """Scannt eine F3-Phase auf 1-Close-Fehlausbrueche in Bruchrichtung (F1).

    Fuer jede Innen-Bar j in [Phasenstart+MIN_PHASE_CANDLES, brk_idx) wird
    geprueft, ob der 1-Close-Trigger (erster Close jenseits kante(j)+TOL bzw.
    kante(j)-TOL) feuerte, ohne dass Bar j+1 gegen DIESELBE kante(j) die
    2-Close-Bestaetigung lieferte. Da die Phase erst bei brk_idx bricht, ist
    jede solche Bar automatisch ein Fehlausbruch (Whipsaw). Sub-Typ:
    RETRACE (Folge-Close vollstaendig zurueck in die Range) vs. TOL_BAND.

    Args:
        df: OHLCV-DataFrame.
        p: PhaseData-Objekt (echter 2-Close-Bruch, break_dir == Bruchrichtung).
        nr: Phasennummer (1-basiert, deckungsgleich zu Stufe-1-Nummerierung).
        acfg: AuditConfig (stop_puffer = fixed_buffer fuer den F4-Stop).
        min_phase_candles: MIN_PHASE_CANDLES der Baseline (untere Scan-Grenze).
        tol: TOL der Baseline (Bruchschwelle, bitgenau aus sr.ns["TOL"]).

    Returns:
        Liste der Whipsaw-Kandidaten (aufsteigend nach trigger_idx sortiert).
    """
    b: int = int(p.brk_idx)
    dir: DirName = p.break_dir  # nach Filter in _whipsaw_fenster: up|down
    start_idx: int = audit._phase_start_idx(df, p)
    # Nur die Bruchrichtung hat in Stufe 1 Einstiege (Scope-Beschluss).
    hist: Sequence[Tuple[pd.Timestamp, float]] = (
        list(p.U_hist) if dir == "up" else list(p.L_hist)
    )
    if not hist:
        # Keine etablierte Kante dieser Richtung vor dem Bruch -> kein Trigger
        # moeglich (identische Logik zu erfasse_raw / KEINE_KANTE).
        return []
    scan_lo: int = start_idx + min_phase_candles
    erster_hist_idx: int = int(np.searchsorted(
        df["ts"].values, np.datetime64(hist[0][0]), side="left"
    ))
    scan_lo = max(scan_lo, erster_hist_idx)
    if scan_lo >= b:
        return []  # kein Innen-Fenster (Phase zu kurz bzw. Kante erst am Bruch)
    rng: np.ndarray = np.arange(scan_lo, b)  # j in [scan_lo, brk_idx) - strikt < b
    ts_rng: np.ndarray = df["ts"].values[rng]
    kanten: np.ndarray = audit._kanten_reihe(ts_rng, hist, float(hist[0][1]))
    closes: np.ndarray = df["close"].values.astype(float)
    c0: np.ndarray = closes[rng]
    c1: np.ndarray = closes[rng + 1]  # j+1 < b+1 <= n-1 (b+1 < n garantiert)

    if dir == "up":
        trig: np.ndarray = c0 > kanten + tol
        no_confirm: np.ndarray = c1 <= kanten + tol          # F1-Negativ-Spiegel
        typ_arr: np.ndarray = np.where(c1 <= kanten, "RETRACE", "TOL_BAND")
    else:
        trig = c0 < kanten - tol
        no_confirm = c1 >= kanten - tol
        typ_arr = np.where(c1 >= kanten, "RETRACE", "TOL_BAND")

    out: List[_Kandidat] = []
    for pos in np.flatnonzero(trig & no_confirm):
        j: int = int(rng[pos])
        kante_j: float = float(kanten[pos])
        e: int = j + 1
        # G2-kausaler Stop: NUR die Triggerkerze j (low[j+1] existiert am
        # Entscheidungszeitpunkt open[j+1] noch nicht - kein Lookahead).
        stop: float = audit._stop_f4(df, j, j, kante_j, dir, acfg)
        entry: float = float(df["open"].values[e])
        sl_usd: float = entry - stop if dir == "up" else stop - entry
        if not (np.isfinite(sl_usd) and sl_usd > 0.0):
            continue
        s = audit.AuditSignal(
            arm="CONFIRMED", fenster=acfg.fenster, phase=nr,
            dir=dir, kante=kante_j, brk_idx=b, trigger_idx=j,
            entry_idx=e, status="SIGNAL",
        )
        s.entry_ts = df["ts"].iloc[e]
        s.entry_preis = entry
        s.stop_level = stop
        s.sl_usd = float(sl_usd)
        out.append(_Kandidat(sig=s, typ=str(typ_arr[pos])))  # type: ignore[arg-type]
    return out


# ==============================================================================
# 3) SUPPRESSION & SIMULATION (F2/F3: regulaerer Kern, E2-Zensierung)
# ==============================================================================


def _whipsaw_result(
    zr: zeitexit.ZeitexitResult,
    typ: WhipsawTyp,
    trigger_idx: int,
) -> WhipsawResult:
    """Mappt ein ZeitexitResult (KEIN_TRAILING) auf das WhipsawResult.

    Args:
        zr: Ergebnis aus zeitexit.simuliere_zeitexit (modus KEIN_TRAILING).
        typ: Whipsaw-Sub-Typ (RETRACE/TOL_BAND) aus der F1-Klassifikation.
        trigger_idx: Bar j des Piercing-Closes (nicht in ZeitexitResult).

    Returns:
        WhipsawResult mit uebernommenen Feldern.
    """
    return WhipsawResult(
        phase=zr.phase, dir=zr.dir, whipsaw_typ=typ,
        horizont_bars=zr.horizont_bars,
        trigger_idx=trigger_idx,
        entry_idx=zr.entry_idx, entry_ts=zr.entry_ts, entry_preis=zr.entry_preis,
        f4_initial_stop=zr.f4_initial_stop, sl_usd=zr.sl_usd,
        exit_idx=zr.exit_idx, exit_ts=zr.exit_ts, exit_preis=zr.exit_preis,
        exit_grund=zr.exit_grund, haltezeit_bars=zr.haltezeit_bars,
        r_f4=zr.r_f4, r_ref=zr.r_ref,
    )


def _simuliere_whipsaws(
    df: pd.DataFrame,
    kandidaten: Sequence[_Kandidat],
    cfg: WhipsawConfig,
    horizont: int,
    pivot_hi: np.ndarray,
    pivot_lo: np.ndarray,
) -> Tuple[List[WhipsawResult], int]:
    """Simuliert Whipsaw-Kandidaten unter F3-Suppression (Default).

    Kandidaten sind aufsteigend nach (phase, trigger_idx) sortiert.
    F3-Suppression (ratifiziert: NUR derselben Phase): Ein Kandidat mit
    Einstiegs-Bar e wird verworfen, solange eine akzeptierte Whipsaw-Position
    DERSELBEN Phase noch offen ist (e <= exit_idx der offenen Position). Beim
    Phasenwechsel wird der Suppressions-Zustand zurueckgesetzt - Positionen
    verschiedener Phasen duerfen ueberlappen (konsistent zur Event-Basis, in
    der auch Stufe-1-Trades phasenuebergreifend ueberlappen duerfen). Nach dem
    Exit (Stop/Zeit-Exit/Zensur) sind spaetere Trigger derselben Phase wieder
    zulaessig. Stufe-1-Einstiege (Bruchbar b) sind NICHT Teil dieser
    Suppression (additive Event-Basis, siehe Modul-Docstring).

    Args:
        df: OHLCV-DataFrame.
        kandidaten: Whipsaw-Kandidaten aller Stufe-1-Phasen (sortiert).
        cfg: WhipsawConfig (suppression_aktiv).
        horizont: Zeit-Horizont N (48/96).
        pivot_hi: Pivot-Hoch-Array (sim-Kompatibilitaet, KEIN_TRAILING ungenutzt).
        pivot_lo: Pivot-Tief-Array (dito).

    Returns:
        Tuple aus (akzeptierte WhipsawResult-Liste, Anzahl Supprimierter).
    """
    zcfg = zeitexit.ZeitexitConfig(
        fenster=cfg.fenster, fixed_buffer=cfg.fixed_buffer, sl_pct_ref=cfg.sl_pct_ref
    )
    ergebnis: List[WhipsawResult] = []
    n_supprimiert: int = 0
    offen_bis: int = -1  # exit_idx der offenen Whipsaw-Position derselben Phase
    letzte_phase: Optional[int] = None
    for kand in kandidaten:
        phase: int = int(kand.sig.phase)
        if letzte_phase is not None and phase != letzte_phase:
            offen_bis = -1  # Suppression ist phasenlokal (F3-Beschluss)
        letzte_phase = phase
        e: int = int(kand.sig.entry_idx)
        if cfg.suppression_aktiv and e <= offen_bis:
            n_supprimiert += 1
            continue
        zr = zeitexit.simuliere_zeitexit(
            df, kand.sig, zcfg, "KEIN_TRAILING", horizont, pivot_hi, pivot_lo
        )
        offen_bis = int(zr.exit_idx)
        ergebnis.append(_whipsaw_result(zr, kand.typ, int(kand.sig.trigger_idx)))
    return ergebnis, n_supprimiert


# ==============================================================================
# 4) AGGREGATION & REPORT
# ==============================================================================


def _agg_whipsaw(
    results: Sequence[WhipsawResult],
    n_kandidaten: int,
    n_supprimiert: int,
) -> Dict[str, Any]:
    """Aggregiert WhipsawResults (zensierte strikt isoliert, E2/G3).

    Args:
        results: Akzeptierte Whipsaw-Ergebnisse (nach F3-Suppression).
        n_kandidaten: Roh-Trigger vor Suppression (Diagnose).
        n_supprimiert: Durch F3-Suppression verworfen (Diagnose).

    Returns:
        Dict mit Summen/Verteilungen inkl. Sub-Typ-Split (RETRACE/TOL_BAND).
    """
    out: Dict[str, Any] = {
        "n_kandidaten": n_kandidaten,
        "n_supprimiert": n_supprimiert,
        "n_total": len(results),
        "n_zensiert": 0,
        "n_gewertet": 0,
        "sum_r_f4": 0.0, "mean_r_f4": float("nan"), "median_r_f4": float("nan"),
        "wr": float("nan"), "pf": float("inf"),
        "sum_r_ref": 0.0,
        "n_init": 0, "n_zeit": 0,
        "mean_offset": float("nan"),
        "n_retrace": 0, "n_tolband": 0,
        "sum_r_f4_retrace": 0.0, "sum_r_f4_tolband": 0.0,
    }
    if not results:
        return out
    rs: List[float] = []
    offsets: List[int] = []
    for r in results:
        if r.whipsaw_typ == "RETRACE":
            out["n_retrace"] += 1
        else:
            out["n_tolband"] += 1
        if r.exit_grund == "RECHTS_ZENSIERT":
            out["n_zensiert"] += 1
            continue  # E2: strikt aus Performance-Berechnung isoliert
        if r.exit_grund == "INITIAL_SL_INTRABAR":
            out["n_init"] += 1
        else:
            out["n_zeit"] += 1
        rs.append(float(r.r_f4))
        out["sum_r_ref"] += float(r.r_ref)
        offsets.append(r.haltezeit_bars)
        if r.whipsaw_typ == "RETRACE":
            out["sum_r_f4_retrace"] += float(r.r_f4)
        else:
            out["sum_r_f4_tolband"] += float(r.r_f4)
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


def _whipsaw_block_text(titel: str, agg: Dict[str, Any]) -> List[str]:
    """Formatiert einen Whipsaw-Aggregationsblock (inkl. Suppression/Subtypen)."""
    t = (
        f"{titel}  (Kand.={agg['n_kandidaten']}, suppr.={agg['n_supprimiert']}, "
        f"akzeptiert={agg['n_total']}, zensiert={agg['n_zensiert']}, "
        f"gewertet={agg['n_gewertet']})"
    )
    lines: List[str] = [t, "  " + "-" * max(2, len(t) - 2)]
    if not agg["n_gewertet"]:
        lines.append("  (keine gewerteten Trades - nur RECHTS_ZENSIERT)")
        return lines
    lines.append(
        f"  sum r_f4={agg['sum_r_f4']:>9.2f}  mean r_f4={oneclose._fmt(agg['mean_r_f4']):>7}  "
        f"median={oneclose._fmt(agg['median_r_f4']):>7}  WR={oneclose._fmt(agg['wr'], '.1f')}%  "
        f"PF={oneclose._fmt(agg['pf'])}"
    )
    lines.append(f"  sum r_ref (0.45%-Basis) = {agg['sum_r_ref']:.2f}")
    lines.append(
        f"  Exit: INITIAL_SL_INTRABAR={agg['n_init']} | ZEIT_EXIT_CLOSE={agg['n_zeit']} "
        f"| RECHTS_ZENSIERT={agg['n_zensiert']}"
    )
    lines.append(
        f"  Subtypen (akzeptiert): RETRACE n={agg['n_retrace']} "
        f"(sum r_f4 {agg['sum_r_f4_retrace']:.2f}, gewertet) | "
        f"TOL_BAND n={agg['n_tolband']} (sum r_f4 {agg['sum_r_f4_tolband']:.2f}, gewertet)"
    )
    lines.append(f"  mittl. Haltedauer (gewertet) = {oneclose._fmt(agg['mean_offset'], '.0f')} Bars")
    return lines


def _netto_text(stufe_agg: Dict[str, Any], whip_agg: Dict[str, Any]) -> List[str]:
    """Netto-Zeilen (Stufe-1 + Whipsaws, additive Event-Basis, nur gewertet)."""
    n_gew: int = int(stufe_agg["n_gewertet"]) + int(whip_agg["n_gewertet"])
    s4: float = float(stufe_agg["sum_r_f4"]) + float(whip_agg["sum_r_f4"])
    sr: float = float(stufe_agg["sum_r_ref"]) + float(whip_agg["sum_r_ref"])
    return [
        f"  NETTO sum r_f4 = {s4:>9.2f}   (Stufe-1 {stufe_agg['sum_r_f4']:>7.2f} "
        f"+ Whipsaw {whip_agg['sum_r_f4']:>7.2f})",
        f"  NETTO sum r_ref = {sr:>8.2f}   (Stufe-1 {stufe_agg['sum_r_ref']:>7.2f} "
        f"+ Whipsaw {whip_agg['sum_r_ref']:>7.2f})",
        f"  NETTO n_gewertet = {n_gew}   (Stufe-1 {stufe_agg['n_gewertet']} "
        f"+ Whipsaw {whip_agg['n_gewertet']}; zensiert Stufe-1 "
        f"{stufe_agg['n_zensiert']} + Whipsaw {whip_agg['n_zensiert']})",
    ]


def _bericht_fenster(fenster: str) -> str:
    """Baut den Whipsaw-Report fuer ein Fenster (Horizonte 48/96).

    Ablauf:
      1) Stufe-1-Referenz (Paare + Simulation) ueber den identischen 1close-
         Codepfad - df/sig1/sig2 stammen aus oneclose._paar_fenster.
      2) Eigene Segmentierung NUR fuer die PhaseData-Objekte (U_hist/L_hist)
         des Whipsaw-Scans. Die Scan-Phasenmenge wird auf die Phasen-Nummern
         der Stufe-1-Paare eingeschraenkt (deckungsgleich per Konstruktion).
      3) Whipsaw-Kandidaten je Phase (F1), Suppression + Simulation je
         Horizont (F2/F3), Netto = Stufe-1 + Whipsaws, Sensitivitaet
         "ohne Suppression" als Kontrollspalte.

    Args:
        fenster: AUG | S1 | S2.

    Returns:
        Report-Text (wird nach test/tmp_setup_c_whipsaw_{fenster}.txt geschrieben).
    """
    # --- 1) Stufe-1-Referenz (identischer Codepfad zu Schritt 4b Stufe 1) -----
    df, sig2, sig1 = oneclose._paar_fenster(fenster)
    pivot_hi, pivot_lo = trailing._pivot_stufen(df, 2)
    cfg = WhipsawConfig(fenster=fenster)
    acfg = audit.AuditConfig(fenster=fenster, stop_puffer=cfg.fixed_buffer)
    stufe_phasen: List[int] = sorted({int(s.phase) for s in sig1})

    # --- 2) Segmentierung fuer die PhaseData-Objekte (U_hist/L_hist) ----------
    start, ende = audit.FENSTER_DEFS[fenster]
    sr = audit.resegmentiere(start, ende)
    min_phase_candles: int = int(sr.ns["MIN_PHASE_CANDLES"])
    tol: float = float(sr.ns["TOL"])
    echte = [p for p in sr.phases if p.break_dir is not None and p.brk_idx is not None]
    phasen_set: set = set(stufe_phasen)

    # --- 3) Whipsaw-Kandidaten je Stufe-1-Phase (Bruchrichtung) ---------------
    kandidaten: List[_Kandidat] = []
    n_phasen_scan: int = 0
    for nr, p in enumerate(echte, start=1):
        if nr not in phasen_set:
            continue  # nur exakt die Stufe-1-Population (Scope, inkl. DATEN_ENDE-Ausschluss)
        n_phasen_scan += 1
        kandidaten.extend(_whipsaw_kandidaten(df, p, nr, acfg, min_phase_candles, tol))
    kandidaten.sort(key=lambda k: (int(k.sig.phase), int(k.sig.trigger_idx)))

    # --- 4) Report-Text --------------------------------------------------------
    linie = "=" * 120
    txt: List[str] = [
        linie,
        "SETUP C - SCHRITT 4b STUFE 2: WHIPSAW-SCAN & NETTO-GEGENRECHNUNG "
        "(tmp_setup_c_whipsaw.py)",
        f"Fenster: {fenster} | Symbol: {cfg.symbol} {cfg.timeframe} | Datum: 2026-09-05 | "
        f"Baseline: {audit.BASELINE_REF}",
        "F1 Negativ-Spiegel close[j+1]<=kante+TOL | F2 volle Simulation "
        "KEIN_TRAILING 48/96 (E2) | F3 Suppression (Default) + Sensitivitaet | "
        "Scope: F3-Bruchphasen der Stufe-1-Population, Bruchrichtung",
        linie,
        f"df-Bars: {len(df)} | Stufe-1-Population (Paare): {len(sig1)} | "
        f"gescannte F3-Phasen: {n_phasen_scan} | Whipsaw-Kandidaten (Roh, "
        f"beide Horizonte): {len(kandidaten)}",
        "",
    ]

    # Stufe-1-Referenz-Bloecke je Horizont simulieren (res1=1-Close, res2=2-Close)
    laeufe: Dict[int, Tuple[List[oneclose.OneCloseResult], List[oneclose.OneCloseResult]]] = {}
    for horizont in cfg.zeit_horizonte:
        r1, r2 = oneclose._simuliere_paare(df, sig1, sig2, oneclose.OneCloseConfig(fenster=fenster),
                                           horizont, pivot_hi, pivot_lo)
        laeufe[horizont] = (r1, r2)

    for horizont in cfg.zeit_horizonte:
        r1, r2 = laeufe[horizont]
        txt.append(linie)
        txt.append(f"HORIZONT N = {horizont}  ({horizont} M15-Bars; Exit am Close der "
                   f"Bar entry+{horizont}; Stop-Vorrang intrabar)")
        txt.append("")

        # --- Stufe-1-Referenz (1-Close) --------------------------------------
        agg_stufe = oneclose._agg_block(r1)
        agg_ref2 = oneclose._agg_block(r2)
        txt.extend(oneclose._block_text("  STUFE-1 CONFIRMED_1CLOSE (Referenz, ohne Whipsaws)", agg_stufe))
        txt.append("")
        txt.extend(oneclose._block_text("  STUFE-1 CONFIRMED_2CLOSE (Referenz)", agg_ref2))
        txt.append("")

        # --- Whipsaw-Scan (Suppression Default) -------------------------------
        res_whip, n_suppr = _simuliere_whipsaws(df, kandidaten, cfg, horizont, pivot_hi, pivot_lo)
        agg_whip = _agg_whipsaw(res_whip, len(kandidaten), n_suppr)
        txt.extend(_whipsaw_block_text("  WHIPSAW-SCAN (F3-Suppression AKTIV)", agg_whip))
        txt.append("")
        txt.extend(_netto_text(agg_stufe, agg_whip))
        txt.append("")

        # --- Sensitivitaet: ohne Suppression ----------------------------------
        cfg_nos = WhipsawConfig(fenster=cfg.fenster, fixed_buffer=cfg.fixed_buffer,
                                sl_pct_ref=cfg.sl_pct_ref, suppression_aktiv=False)
        res_nos, n_suppr_nos = _simuliere_whipsaws(df, kandidaten, cfg_nos, horizont, pivot_hi, pivot_lo)
        agg_nos = _agg_whipsaw(res_nos, len(kandidaten), n_suppr_nos)
        txt.extend(_whipsaw_block_text("  SENS: WHIPSAW ohne Suppression (alle Kandidaten)", agg_nos))
        txt.append("")
        txt.extend(_netto_text(agg_stufe, agg_nos))
        txt.append("")

    # --- Vergleichstabelle (sum r_f4 und sum r_ref) ---------------------------
    txt.append(linie)
    txt.append("VERGLEICH  (sum r_f4 | sum r_ref; gewertet, zensiert isoliert E2)")
    txt.append(
        f"    {'N':<4} {'Stufe1_1c':>18} {'Whipsaw_suppr':>20} {'NETTO_1c':>18} "
        f"{'2Close_Ref':>18} {'Whipsaw_ohne':>20} {'NETTO_ohne':>18}"
    )
    for horizont in cfg.zeit_horizonte:
        r1, r2 = laeufe[horizont]
        agg_stufe = oneclose._agg_block(r1)
        agg_ref2 = oneclose._agg_block(r2)
        res_whip, n_suppr = _simuliere_whipsaws(df, kandidaten, cfg, horizont, pivot_hi, pivot_lo)
        agg_whip = _agg_whipsaw(res_whip, len(kandidaten), n_suppr)
        cfg_nos = WhipsawConfig(fenster=cfg.fenster, fixed_buffer=cfg.fixed_buffer,
                                sl_pct_ref=cfg.sl_pct_ref, suppression_aktiv=False)
        res_nos, _ = _simuliere_whipsaws(df, kandidaten, cfg_nos, horizont, pivot_hi, pivot_lo)
        agg_nos = _agg_whipsaw(res_nos, len(kandidaten), 0)
        netto = float(agg_stufe["sum_r_f4"]) + float(agg_whip["sum_r_f4"])
        netto_ref = float(agg_stufe["sum_r_ref"]) + float(agg_whip["sum_r_ref"])
        netto_nos = float(agg_stufe["sum_r_f4"]) + float(agg_nos["sum_r_f4"])
        netto_nos_ref = float(agg_stufe["sum_r_ref"]) + float(agg_nos["sum_r_ref"])
        txt.append(
            f"    {horizont:<4} "
            f"{agg_stufe['sum_r_f4']:>8.2f}|{agg_stufe['sum_r_ref']:>8.2f} "
            f"{agg_whip['sum_r_f4']:>9.2f}|{agg_whip['sum_r_ref']:>9.2f} "
            f"{netto:>8.2f}|{netto_ref:>8.2f} "
            f"{agg_ref2['sum_r_f4']:>8.2f}|{agg_ref2['sum_r_ref']:>8.2f} "
            f"{agg_nos['sum_r_f4']:>9.2f}|{agg_nos['sum_r_ref']:>9.2f} "
            f"{netto_nos:>8.2f}|{netto_nos_ref:>8.2f}"
        )
    txt.append(linie)

    # --- Verifikationsanker ---------------------------------------------------
    ok_phasen: str = "OK" if n_phasen_scan == len(sig1) == len(stufe_phasen) else "FEHLER"
    txt.append(linie)
    txt.append(
        f"VERIFIKATIONSANKER: gescannte F3-Phasen == Stufe-1-Population "
        f"(AUG=11, S1=138, S2=61) -> {n_phasen_scan} == {len(sig1)}  [{ok_phasen}]"
    )
    txt.append(linie)

    text: str = "\n".join(txt)
    out: Path = TEST_DIR / f"tmp_setup_c_whipsaw_{fenster}.txt"
    out.write_text(text, encoding="utf-8")
    return text


# ==============================================================================
# 5) MAIN
# ==============================================================================


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI-Einstieg: fuehrt den Whipsaw-Scan fuer Fenster aus.

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
        print(f"\nReport geschrieben: {TEST_DIR / f'tmp_setup_c_whipsaw_{f}.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
