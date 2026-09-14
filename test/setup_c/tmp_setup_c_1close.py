"""
SETUP C - SCHRITT 4b: CONFIRMED 1-CLOSE vs 2-CLOSE A/B-TIMING-AUDIT (test/tmp_setup_c_1close.py)
=================================================================================================
Status: ENTWURF ZUR DURCHSICHT (05.09.2026) - KEINE Ausfuehrung/Kompilierung.
Doku: docs/setup_c_experiment.md (Schritt 4b: G1-G5 + Datenvertrag in §2.10).
Baseline: scripts/phasen_volumen_profil.py (v0.4.0-frozen) - UNVERAENDERT.
Arbeitsmodus: isoliertes, rein lesendes Replay (DuckDB read_only via
      tmp_setup_c_audit.py), keine Produktions-Integration, keine Charts.

Zweck
-----
Pruft die institutionelle Hypothese G1: Kauft der 2-Close-Filter am open[b+2]
die Liquiditaetserschoepfung (Retail steigt an Kerze b+1 ein, waehrend
Institutionen den Liquiditaetsabzug vollziehen), und liefert der Einstieg am
open[b+1] (= 1-Close) mit kausalem F4-Stop einen echten Timing-Vorteil?

Arretierte Beschluesse (Doku §2.10, G1-G5)
------------------------------------------
G1  1-Close-Einstieg = open[brk_idx+1] (brk_idx = j = erste Durchbruchs-Kerze).
    2-Close-Referenz = open[brk_idx+2] (bestehende erfasse_confirmed-Semantik).
    Das spart genau eine M15-Kerze gegenueber dem 2-Close-Einstieg.
G2  Kausaler Struktur-Stop fuer 1-Close: _stop_f4(df, b, b, kante, dir, cfg)
    = min(low[b], kante) - 0.15 (Long) bzw. max(high[b], kante) + 0.15 (Short).
    NUR die eine Bruchkerze j - low[j+1] existiert am Entscheidungszeitpunkt
    open[j+1] noch nicht (2-Close-F4-Konstruktion min(low[b],low[b+1]) waere
    Lookahead). 2-Close-Referenz behaelt ihren Stop _stop_f4(df, b, b+1, ...).
G3  Exit-Konstante: KEIN_TRAILING (F4 intrabar) + terminaler Zeit-Exit N in
    {48, 96}. Kein Stufen-Trailing (D2: Performanz-Bremse in 16/18 Zellen);
    N=24 gestrichen (D-Befund: Mittelmaess).
G4  Verzerrungs-Kontrolle: r_f4 ist bei 1-Close mechanisch beguenstigt (engerer
    Stop -> kleinerer Nenner sl_usd). Der Report stellt daher zwingend
    sum r_ref (0.45%-Basis, stop-unabhaengige Dollar-Benchmark) daneben und
    fuehrt eine SL-Delta-Diagnose sl_delta_ratio = sl_usd_1close/sl_usd_2close.
    Zusaetzlich paarweises Delta (1-Close - 2-Close) nur auf Phasen, in denen
    BEIDE Varianten gewertet (nicht rechts-zensiert) sind.
G5  Zweistufig: Dieser Kern (Stufe 1) testet auf der F3-Population (echte
    2-Close-Brueche). Stufe 2 (Whipsaw-Scan) NUR falls Stufe 1 in S1 positiv
    ueberrascht - Gegenrechnen der 1-Close-Fehlausbrueche (Piercings ohne
    Folge-Bestaetigung), bevor eine Produktions-Empfehlung auf 1-Close fusst.
    Ohne Stufe 2 ist die F3-Stichprobe survivorship-verzerrt.

Wiederverwendung (keine Duplizierung)
-------------------------------------
- Segmentierung + F3-Phasen: audit.resegmentiere (exec-Slice, DuckDB read_only).
- 2-Close-Signal (Referenz): audit.erfasse_confirmed (identischer Datenpfad
  zu Schritt 2/4a - kein Drift).
- F4-Stop: audit._stop_f4 (hi inklusiv; 1-Close mit lo=hi=b, RAW-analog).
- Exit-Simulation: zeitexit.simuliere_zeitexit mit modus="KEIN_TRAILING"
  (F4 intrabar mit Stop-Vorrang vor Zeit-Exit; RECHTS_ZENSIERT strikt isoliert,
  r_f4/r_ref = NaN bei Zensierung) - identische Semantik zu Schritt 4a (E2).
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

import tmp_setup_c_audit as audit  # noqa: E402  (Segmentierung, F3, erfasse_confirmed, _stop_f4)
import tmp_setup_c_trailing as trailing  # noqa: E402  (_pivot_stufen fuer sim-Kompatibilitaet)
import tmp_setup_c_zeitexit as zeitexit  # noqa: E402  (simuliere_zeitexit, KEIN_TRAILING-Semantik)

# ==============================================================================
# 1) TYPALIASSE & DATENVERTRAEGE (Doku §2.10 - freigegeben)
# ==============================================================================

EntryTyp = Literal["CONFIRMED_1CLOSE", "CONFIRMED_2CLOSE"]
DirName = Literal["up", "down"]
ExitGrund = Literal[
    "INITIAL_SL_INTRABAR",   # F11/F4: Stop intrabar beruehrt (Vorrang vor Zeit-Exit)
    "ZEIT_EXIT_CLOSE",       # E1/G3: Horizont N erreicht, Close der Exit-Bar e+N
    "RECHTS_ZENSIERT",       # E2: bis Datenende ueberlebt, Horizont nicht abgelaufen
]

# Ausgabe-Reihenfolge (1-Close zuerst = Untersuchungsgegenstand, 2-Close Referenz)
ENTRY_TYPEN: Tuple[EntryTyp, ...] = ("CONFIRMED_1CLOSE", "CONFIRMED_2CLOSE")
# Anzeigenamen fuer Report
ENTRY_LABEL: Dict[EntryTyp, str] = {
    "CONFIRMED_1CLOSE": "CONFIRMED_1CLOSE (open[b+1])",
    "CONFIRMED_2CLOSE": "CONFIRMED_2CLOSE (open[b+2], Referenz)",
}


@dataclass(frozen=True, slots=True)
class OneCloseConfig:
    """Konfiguration fuer den 1-Close vs 2-Close Vergleich (Setup C Schritt 4b).

    Defaults = arretierte Beschluesse (G1-G5). Aenderungen nur als dokumentierte
    Sensitivitaeten (nicht fuer den Freigabe-Lauf).
    """

    fenster: Literal["AUG", "S1", "S2"] = "AUG"
    symbol: str = "SILVER"
    timeframe: str = "M15"

    # G3: Exit-Parameter (Best-Practice aus Schritt 4a, D2)
    zeit_horizonte: Tuple[int, ...] = (48, 96)   # N=24 gestrichen (D-Befund)
    # G2: F4-Puffer unter Struktur/Kante (USD); identisch zu AuditConfig.stop_puffer
    fixed_buffer: float = 0.15
    # G4: Neutrale 0.45%-Referenz (stop-unabhaengige Dollar-Benchmark)
    sl_pct_ref: float = 0.45


@dataclass(slots=True)
class OneCloseResult:
    """Simulationsergebnis fuer ein Signal im A/B-Vergleich (Doku §2.10).

    Fuer RECHTS_ZENSIERT sind r_f4 und r_ref NaN (E2); exit_idx/exit_ts/
    exit_preis/haltezeit_bars dokumentieren das Datenende transparenzhalber.
    sl_delta_ratio ist NUR fuer CONFIRMED_1CLOSE befuellt (Verhaeltnis zum
    gepaarten 2-Close-Stop derselben Phase); sonst NaN (G4).
    """

    entry_typ: EntryTyp
    phase: int
    dir: DirName
    horizont_bars: int

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

    # G4: Delta-Diagnose gegenueber 2-Close (nur fuer 1-Close befuellt)
    sl_delta_ratio: float = float("nan")   # sl_usd_1close / sl_usd_2close


# ==============================================================================
# 2) SIGNAL-ERFASSUNG (gepaarte 1-Close / 2-Close je F3-Phase)
# ==============================================================================


def _paar_fenster(
    fenster: str,
) -> Tuple[pd.DataFrame, List[audit.AuditSignal], List[audit.AuditSignal]]:
    """Erfasst je F3-Phase das gepaarte 2-Close (Referenz) und 1-Close-Signal.

    Nur Phasen, in denen BEIDE Einstiege existieren (2-Close status SIGNAL und
    sl_usd > 0; 1-Close-Einstieg open[b+1] existiert dann automatisch, da
    b+1 < b+2 < n) - identische Population fuer den sauberen A/B (G4).

    Args:
        fenster: AUG | S1 | S2.

    Returns:
        Tuple aus (df, sig_2close, sig_1close) mit paarweise gleicher Laenge.
    """
    acfg = audit.AuditConfig(fenster=fenster)
    start, ende = audit.FENSTER_DEFS[fenster]
    sr = audit.resegmentiere(start, ende)
    df: pd.DataFrame = sr.df
    n: int = len(df)
    echte = [p for p in sr.phases if p.break_dir is not None and p.brk_idx is not None]
    sig2: List[audit.AuditSignal] = []
    sig1: List[audit.AuditSignal] = []
    for nr, p in enumerate(echte, start=1):
        s2 = audit.erfasse_confirmed(df, p, nr, acfg)
        if s2.status != "SIGNAL" or not (np.isfinite(s2.sl_usd) and s2.sl_usd > 0.0):
            continue
        b: int = int(p.brk_idx)
        if b + 1 >= n:
            # Kann bei s2-SIGNAL (b+2 < n) nicht auftreten - Guard fuer Robustheit
            continue
        # G1: 1-Close-Einstieg open[b+1]
        s1 = audit.AuditSignal(
            arm="CONFIRMED", fenster=fenster, phase=nr,
            dir=p.break_dir, kante=float(p.brk_kante), brk_idx=b,
            trigger_idx=b, entry_idx=b + 1, status="SIGNAL",
        )
        s1.entry_ts = df["ts"].iloc[b + 1]
        # G2: Kausaler Stop NUR mit der einen Bruchkerze b (RAW-analog)
        s1.stop_level = audit._stop_f4(df, b, b, float(p.brk_kante), s1.dir, acfg)
        if s1.dir == "up":
            s1.sl_usd = float(df["open"].values[b + 1]) - s1.stop_level
        else:
            s1.sl_usd = s1.stop_level - float(df["open"].values[b + 1])
        if not (np.isfinite(s1.sl_usd) and s1.sl_usd > 0.0):
            continue
        sig2.append(s2)
        sig1.append(s1)
    return df, sig2, sig1


# ==============================================================================
# 3) SIMULATION & ERGEBNIS-MAPPING (Wiederverwendung zeitexit.simuliere_zeitexit)
# ==============================================================================


def _oneclose_result(
    entry_typ: EntryTyp,
    zr: zeitexit.ZeitexitResult,
    sl_delta: float,
) -> OneCloseResult:
    """Mappt ein ZeitexitResult (KEIN_TRAILING) auf das 4b-OneCloseResult.

    Args:
        entry_typ: CONFIRMED_1CLOSE oder CONFIRMED_2CLOSE.
        zr: Ergebnis aus zeitexit.simuliere_zeitexit (modus KEIN_TRAILING).
        sl_delta: sl_delta_ratio (nur 1-Close befuellt, sonst NaN).

    Returns:
        OneCloseResult mit uebernommenen Feldern.
    """
    return OneCloseResult(
        entry_typ=entry_typ, phase=zr.phase, dir=zr.dir,
        horizont_bars=zr.horizont_bars,
        entry_idx=zr.entry_idx, entry_ts=zr.entry_ts, entry_preis=zr.entry_preis,
        f4_initial_stop=zr.f4_initial_stop, sl_usd=zr.sl_usd,
        exit_idx=zr.exit_idx, exit_ts=zr.exit_ts, exit_preis=zr.exit_preis,
        exit_grund=zr.exit_grund, haltezeit_bars=zr.haltezeit_bars,
        r_f4=zr.r_f4, r_ref=zr.r_ref, sl_delta_ratio=sl_delta,
    )


def _simuliere_paare(
    df: pd.DataFrame,
    sig1: Sequence[audit.AuditSignal],
    sig2: Sequence[audit.AuditSignal],
    cfg: OneCloseConfig,
    horizont: int,
    pivot_hi: np.ndarray,
    pivot_lo: np.ndarray,
) -> Tuple[List[OneCloseResult], List[OneCloseResult]]:
    """Simuliert alle Paare unter F4 + Zeit-Exit (KEIN_TRAILING).

    Args:
        df: OHLCV-DataFrame.
        sig1: 1-Close-Signale (G1/G2).
        sig2: 2-Close-Signale (Referenz, G4).
        cfg: OneCloseConfig.
        horizont: Zeit-Horizont N (48/96).
        pivot_hi: Pivot-Hoch-Array (fuer sim-Kompatibilitaet, bei KEIN_TRAILING ungenutzt).
        pivot_lo: Pivot-Tief-Array (dito).

    Returns:
        Tuple aus (res_1close, res_2close) - paarweise gleiche Laenge wie Input.
    """
    zcfg = zeitexit.ZeitexitConfig(fenster=cfg.fenster)
    res1: List[OneCloseResult] = []
    res2: List[OneCloseResult] = []
    for s1, s2 in zip(sig1, sig2):
        zr2 = zeitexit.simuliere_zeitexit(
            df, s2, zcfg, "KEIN_TRAILING", horizont, pivot_hi, pivot_lo
        )
        zr1 = zeitexit.simuliere_zeitexit(
            df, s1, zcfg, "KEIN_TRAILING", horizont, pivot_hi, pivot_lo
        )
        # G4: SL-Delta nur auf 1-Close (Verhaeltnis zum gepaarten 2-Close-Stop)
        delta: float = (
            float(s1.sl_usd / s2.sl_usd) if s2.sl_usd > 0.0 else float("nan")
        )
        res1.append(_oneclose_result("CONFIRMED_1CLOSE", zr1, delta))
        res2.append(_oneclose_result("CONFIRMED_2CLOSE", zr2, float("nan")))
    return res1, res2


# ==============================================================================
# 4) AGGREGATION & REPORT
# ==============================================================================


def _agg_block(results: Sequence[OneCloseResult]) -> Dict[str, Any]:
    """Aggregiert OneCloseResults (zensierte strikt isoliert, E2/G3)."""
    out: Dict[str, Any] = {
        "n_total": len(results),
        "n_zensiert": 0,
        "n_gewertet": 0,
        "sum_r_f4": 0.0, "mean_r_f4": float("nan"), "median_r_f4": float("nan"),
        "wr": float("nan"), "pf": float("inf"),
        "sum_r_ref": 0.0,
        "n_init": 0, "n_zeit": 0,
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


def _delta_paare(
    res1: Sequence[OneCloseResult], res2: Sequence[OneCloseResult]
) -> Dict[str, Any]:
    """Paarweises Delta (1-Close - 2-Close) nur wo BEIDE gewertet sind.

    Args:
        res1: 1-Close-Ergebnisse.
        res2: 2-Close-Ergebnisse (gleiche Phasen-Reihenfolge).

    Returns:
        Dict mit n, sum_d_r_f4, sum_d_r_ref, median_d_r_f4.
    """
    out: Dict[str, Any] = {"n": 0, "sum_d_r_f4": 0.0, "sum_d_r_ref": 0.0,
                           "median_d_r_f4": float("nan")}
    d_r4: List[float] = []
    for a, b in zip(res1, res2):
        if a.exit_grund == "RECHTS_ZENSIERT" or b.exit_grund == "RECHTS_ZENSIERT":
            continue
        d_r4.append(float(a.r_f4) - float(b.r_f4))
        out["sum_d_r_ref"] += float(a.r_ref) - float(b.r_ref)
    n: int = len(d_r4)
    out["n"] = n
    if n:
        arr: np.ndarray = np.array(d_r4, dtype=float)
        out["sum_d_r_f4"] = float(arr.sum())
        out["median_d_r_f4"] = float(np.median(arr))
    return out


def _fmt(v: Any, fmt: str = ".2f") -> str:
    """Formatiert Zahlen (NaN/None -> '-')."""
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "-"
    return f"{v:{fmt}}"


def _block_text(titel: str, agg: Dict[str, Any]) -> List[str]:
    """Formatiert einen Aggregationsblock."""
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
        f"  Exit: INITIAL_SL_INTRABAR={agg['n_init']} | ZEIT_EXIT_CLOSE={agg['n_zeit']} "
        f"| RECHTS_ZENSIERT={agg['n_zensiert']}"
    )
    lines.append(f"  mittl. Haltedauer (gewertet) = {_fmt(agg['mean_offset'], '.0f')} Bars")
    return lines


def _sl_delta_text(sig1: Sequence[audit.AuditSignal],
                   sig2: Sequence[audit.AuditSignal]) -> List[str]:
    """SL-Delta-Diagnose (G4): median sl_usd je Variante + delta_ratio."""
    lines: List[str] = ["--- SL-DELTA-DIAGNOSE (G2/G4, alle Paare, stop-unabhaengig) ---"]
    if not sig1:
        lines.append("  (keine Paare)")
        return lines
    sl1: np.ndarray = np.array([float(s.sl_usd) for s in sig1])
    sl2: np.ndarray = np.array([float(s.sl_usd) for s in sig2])
    ratio: np.ndarray = sl1 / sl2
    lines.append(f"  n_Paare = {len(sig1)}")
    lines.append(f"  sl_usd 2-Close (Referenz) : median={np.median(sl2):.4f} USD")
    lines.append(f"  sl_usd 1-Close            : median={np.median(sl1):.4f} USD")
    lines.append(
        f"  sl_delta_ratio (1c/2c)       : median={np.median(ratio):.3f}  "
        f"p25={np.percentile(ratio, 25):.3f}  p75={np.percentile(ratio, 75):.3f}"
    )
    lines.append(
        "  -> ratio < 1 bedeutet engerer 1-Close-Stop (kleinerer R-Nenner); "
        "r_f4-Delta ist dann teils mechanisch. sum r_ref bleibt die neutrale Waehrung."
    )
    return lines


def _bericht_fenster(fenster: str) -> str:
    """Baut den Report fuer ein Fenster (Horizonte 48/96, A/B 1-Close vs 2-Close)."""
    df, sig2, sig1 = _paar_fenster(fenster)
    pivot_hi, pivot_lo = trailing._pivot_stufen(df, 2)  # fuer sim-Kompatibilitaet
    cfg = OneCloseConfig(fenster=fenster)

    # Alle Laeufe simulieren: laeufe[horizont] = (res1, res2)
    laeufe: Dict[int, Tuple[List[OneCloseResult], List[OneCloseResult]]] = {}
    for horizont in cfg.zeit_horizonte:
        r1, r2 = _simuliere_paare(df, sig1, sig2, cfg, horizont, pivot_hi, pivot_lo)
        laeufe[horizont] = (r1, r2)

    linie = "=" * 120
    txt: List[str] = [
        linie,
        "SETUP C - SCHRITT 4b: CONFIRMED 1-CLOSE vs 2-CLOSE A/B-TIMING-AUDIT "
        "(tmp_setup_c_1close.py)",
        f"Fenster: {fenster} | Symbol: {cfg.symbol} {cfg.timeframe} | Datum: 2026-09-05 | "
        f"Baseline: {audit.BASELINE_REF}",
        "G1 open[b+1] | G2 Stop min(low[b],kante)-0.15 (RAW-analog) | G3 F4 intrabar + "
        "Zeit-Exit 48/96 | G4 r_ref + SL-Delta | G5 Stufe 1 (F3-Population)",
        linie,
        f"df-Bars: {len(df)} | gepaarte SIGNAL-Paare (2-Close SIGNAL, G4-Referenz): {len(sig2)}",
        "",
        * _sl_delta_text(sig1, sig2),
        "",
    ]

    # --- Detailbloecke je Horizont -------------------------------------------
    for horizont in cfg.zeit_horizonte:
        r1, r2 = laeufe[horizont]
        txt.append(linie)
        txt.append(f"HORIZONT N = {horizont}  ({horizont} M15-Bars; Exit am Close der "
                   f"Bar entry+{horizont}; Stop-Vorrang intrabar)")
        txt.append("")
        agg1 = _agg_block(r1)
        agg2 = _agg_block(r2)
        txt.extend(_block_text(f"  ENTRY {ENTRY_LABEL['CONFIRMED_1CLOSE']}", agg1))
        txt.append("")
        txt.extend(_block_text(f"  ENTRY {ENTRY_LABEL['CONFIRMED_2CLOSE']}", agg2))
        txt.append("")
        d = _delta_paare(r1, r2)
        if d["n"]:
            txt.append(
                f"  DELTA 1-Close - 2-Close (paarweise, nur wo beide gewertet, n={d['n']}):\n"
                f"    sum d_r_f4={d['sum_d_r_f4']:>9.2f}  median d_r_f4="
                f"{_fmt(d['median_d_r_f4']):>7}  sum d_r_ref (0.45%%)="
                f"{d['sum_d_r_ref']:.2f}"
            )
        else:
            txt.append("  DELTA 1-Close - 2-Close: (keine paarweise gewerteten Trades)")
        txt.append("")

    # --- Vergleichstabelle je Horizont ----------------------------------------
    txt.append(linie)
    txt.append("VERGLEICH  (sum r_f4 je EntryTyp; zensiert in Klammern)")
    txt.append(f"    {'N':<4} {'EntryTyp':<34} {'sum_r_f4':>10} {'sum_r_ref':>10} "
               f"{'n_gew':>6} {'n_zens':>7}")
    for horizont in cfg.zeit_horizonte:
        r1, r2 = laeufe[horizont]
        for label, res in ((ENTRY_LABEL["CONFIRMED_1CLOSE"], r1),
                           (ENTRY_LABEL["CONFIRMED_2CLOSE"], r2)):
            agg = _agg_block(res)
            wert: str = "keine" if not agg["n_gewertet"] else f"{agg['sum_r_f4']:.2f}"
            txt.append(
                f"    {horizont:<4} {label:<34} "
                f"{wert:>10} "
                f"{agg['sum_r_ref']:>10.2f} {agg['n_gewertet']:>6} {agg['n_zensiert']:>7}"
            )
        r1, r2 = laeufe[horizont]
        d = _delta_paare(r1, r2)
        txt.append(f"    {'':<4} {'DELTA (1c-2c, paarweise)':<34} "
                   f"{_fmt(d['sum_d_r_f4']):>10} {_fmt(d['sum_d_r_ref']):>10} "
                   f"{d['n']:>6}")
    txt.append(linie)

    # --- Verifikationsanker ---------------------------------------------------
    txt.append(linie)
    txt.append(
        "VERIFIKATIONSANKER: gepaarte Paare = CONFIRMED-SIGNAL-Zahl aus Schritt 2 "
        "(AUG=11, S1=138, S2=61, abzueglich DATEN_ENDE)"
    )
    txt.append(linie)

    text: str = "\n".join(txt)
    out: Path = TEST_DIR / f"tmp_setup_c_1close_{fenster}.txt"
    out.write_text(text, encoding="utf-8")
    return text


# ==============================================================================
# 5) MAIN
# ==============================================================================


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI-Einstieg: fuehrt das 1-Close vs 2-Close Audit fuer Fenster aus.

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
        print(f"\nReport geschrieben: {TEST_DIR / f'tmp_setup_c_1close_{f}.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
