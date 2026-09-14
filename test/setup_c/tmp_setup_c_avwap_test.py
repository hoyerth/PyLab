"""
SETUP C - AVWAP-PULLBACK-ZWISCHENTEST (test/tmp_setup_c_avwap_test.py)
======================================================================
Status: ISOLIERTER EXPLORATIONS-TEST (AUG) - keine Produktions-Aenderung.
Baseline: scripts/setup_c_profil.py / scripts/market_segmentation.py /
      scripts/regime_filter.py / scripts/anchored_vwap.py - Produktions-
      Module BYTE-IDENTISCH UNANGETASTET (nur lesende Importe). Neu ist
      ausschliesslich scripts/anchored_vwap.py (Freigabe-Gate 06.09.2026,
      L1 bitgenau bestanden: test/tmp_anchored_vwap_l1.py).

Zweck
-----
Pfad-A-Spezifikation (AVWAP_PULLBACK, §5.6-Kandidat): Schliessen des
Einstiegs-Bottlenecks von Setup C durch trendbegleitende Pullback-Entries
an der AVWAP-Linie NACH einem echten 2-Close-Bruch. Das Exit-Management
ist arretiert (Variante-B-Ratchet, Commit e5f24d2, §5.2.1); getestet wird
ausschliesslich das Einstiegs-Konzept im TREND-Regime.

Regeln (freigegebener Spezifikationstext, Schritt 3/4):
  Anker:    b = brk_idx der echten Bruch-Phase; AVWAP ab b INKLUSIVE
            (Anker-Bar gehoert zur neuen Positionierung).
  Fenster:  Scan-Fenster = [b + 1, brk_idx der Folge-Phase)  (halboffen);
            finale ungebrochene Phase laeuft bis Datenende (n-1).
  Kontakt:  AVWAP kausal an Bar k:  low[k] <= avwap[k] <= high[k].
  Trigger:  Bestaetigungs-Close an der unmittelbaren Folge-Bar k+1:
              Long : close[k+1] > high[k]   UND  slope20[k+1] > 0.0
              Short: close[k+1] < low[k]    UND  slope20[k+1] < 0.0
            Per-Bar-Re-Arming (jede Kontakt-Bar armiert ihre eigene
            Folge-Bar-Bestaetigung); ohne Bestaetigung verfaellt der
            Trigger ersatzlos.
  Stop:     Struktur-Stop ueber Zwei-Bar-Spanne [k, k+1]:
              Long : min(low[k], low[k+1]) - stop_puffer
              Short: max(high[k], high[k+1]) + stop_puffer
            KEIN kuenstlicher Cap (SL-Abstand = echter Struktur-Abstand).
  Ausfuehrung: strikt open[k+2]; fehlt Bar k+2 -> DATEN_ENDE; oeffnet die
            Entry-Bar jenseits des Stops (Gap) -> SL_UEBERSCHRITTEN.
  Regime:   TREND-only-Gate als Pflicht (erfordere_trend_regime=True).
            Klassifikation mit den VERSIEGELTEN Defaults des Moduls
            scripts/regime_filter.py (RegimeSchwellen()/RegimeGateConfig()/
            RegimeMetricConfig() = Freeze 05.09.2026). AUG-Erwartung laut
            Reconnaissance: TREND-Phasen = [6, 7, 8].
  Management: F3-Bucket-Suppression Key = (Anker-Phase, Richtung) +
            1:1-Variante-B-Ratchet (_simuliere_kern_ema_trailing,
            STOP_AUF_EXTREMUM, mindest_gewinn_r=0.0, notfall=300).
  Zensur:   RECHTS_ZENSIERT (Trade ueberlebt bis Datenende) strikt isoliert.

Messung:
  r_f4  = P&L / (entry - stop)  (echter Struktur-Stop-Abstand)
  r_ref = P&L / (entry * sl_pct_ref)  (0.45 %-Referenz, neutral)

Erfolgskriterium (Spezifikation, AUG):
  PF >= 1.50 UND Summe r_f4 > 0 UND Erfassung der Ph-6/7-Expansions-
  Gewinner. Sonst: sofortiger Null-Befund §5.6 (scripts/anchored_vwap.py
  verbleibt als utilitaristisches Hilfsmodul).

Ausgabe (reports/setup_c/, deterministisch reproduzierbar):
    setup_c_avwap_AUG.txt                Statistik + Kandidaten/Trade-Detail
    setup_c_avwap_trades_AUG.tsv         Trade-Block (maschinenlesbar)
    setup_c_avwap_AUG.png                300 dpi (Preis+EMA+AVWAP+Equity)

Aufruf (Projekt-Root):
    python test/tmp_setup_c_avwap_test.py [--fenster=AUG] [--dpi=300]
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))  # noqa: E402

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from scripts.anchored_vwap import berechne_avwap_vektor  # noqa: E402
from scripts.market_segmentation import (  # noqa: E402
    PhaseData,
    SegmentConfig,
    SegmentResult,
    load_data,
    segmentiere_markt,
)
from scripts.regime_filter import (  # noqa: E402 - versiegelte Defaults (Freeze 05.09.2026)
    RegimeGateConfig,
    RegimeMetricConfig,
    RegimeSchwellen,
    berechne_regime_metriken,
    berechne_zeitreihen_indikatoren,
    klassifiziere_regime,
)
from scripts.setup_c_profil import (  # noqa: E402 - NUR lesende Importe
    FENSTER_DEFS,
    EMASlopeTrailingConfig,
    SetupCSignal,
    TrendConfig,
    _simuliere_kern_ema_trailing,
    berechne_ema_slope_vektoren,
)

_REPORT_DIR: Path = PROJECT_ROOT / "reports" / "setup_c"

# Farben (konsistent zur Projekt-Chart-Palette)
_COL_EMA: str = "#1565c0"
_COL_UP: str = "#1a7d1a"
_COL_DOWN: str = "#c00000"
_COL_AVWAP: str = "#b8860b"
_COL_STOP: str = "#8e44ad"
_COL_FLIP: str = "#999999"
_COL_BLOCK: str = "#bbbbbb"


# =============================================================================
# 1) DATENVERTRAG (freigegebene Pfad-A-Spezifikation)
# =============================================================================

AavwapDir = Literal["up", "down"]

AavwapStatus = Literal[
    "SIGNAL",
    "KEIN_KONTAKT",
    "KEINE_REJECTION",
    "SLOPE_INVALIDE",
    "REGIME_BLOCKIERT",
    "SL_UEBERSCHRITTEN",
    "DATEN_ENDE",
]


@dataclass(frozen=True, slots=True)
class AavwapConfig:
    """Konfiguration fuer AVWAP-Pullback-Entries (§5.6, Pfad A)."""

    ema_periode: int = 20
    stop_puffer: float = 0.15          # USD: Puffer unter/ueber Struktur
    sl_pct_ref: float = 0.45           # Neutrale 0.45 %-SL-Referenzwaehrung
    erfordere_trend_regime: bool = True  # TREND-only-Gate (Pflicht)
    # Trade-Management (arretierte Variante-B-Ratchet, §5.2)
    mindest_gewinn_r: float = 0.0
    notfall_horizont_bars: int = 300


@dataclass(slots=True)
class AavwapKandidat:
    """Typisierter Datenvertrag fuer ein AVWAP-Pullback-Signal."""

    arm: Literal["AVWAP_PULLBACK"]
    phase: int                       # 1-basiert ueber echte Bruch-Phasen
    dir: AavwapDir                   # Identisch zur Bruchrichtung (prozyklisch)
    brk_idx: int                     # Basis-Bruchanker (AVWAP-Start, inklusiv)
    kontakt_idx: int                 # Bar k: AVWAP-Kontakt
    rejection_idx: int               # Bar k+1: Bestaetigungs-Close
    entry_idx: int                   # Bar k+2: Ausfuehrung am Open
    entry_ts: Optional[pd.Timestamp]
    entry_preis: float
    avwap_wert: float                # avwap[k] am Kontakt
    stop_level: float                # Struktureller Stop ueber [k, k+1]
    sl_usd: float
    status: AavwapStatus


# =============================================================================
# 2) REGIME-GATE (versiegelte Defaults, Freeze 05.09.2026)
# =============================================================================


def _regime_je_phase(
    df: pd.DataFrame,
    sr: SegmentResult,
) -> Dict[int, str]:
    """Klassifiziert jede echte Bruch-Phase mit den VERSIEGELTEN Defaults.

    Nutzt ausschliesslich die Modul-Defaults von ``scripts.regime_filter``
    (``RegimeSchwellen()``/``RegimeGateConfig()``/``RegimeMetricConfig()``),
    die seit dem Freeze 05.09.2026 die Soll-Freeze-Werte tragen
    (ema_slope_min=0.07, ema_slope_max=-0.03, adx_schwelle_min=25.0,
    tol_band_quote_max=0.60). Keine Kalibrier-/Sweep-Pfade, kein OOS.

    Args:
        df: OHLCV-Frame (AUG).
        sr: SegmentResult.

    Returns:
        ``{phase_nr: regime}`` fuer alle echten Bruch-Phasen
        (``regime`` in {"TREND", "SHAKEOUT", "UNKLAR"}).
    """
    metric_cfg: RegimeMetricConfig = RegimeMetricConfig()
    states = berechne_regime_metriken(
        berechne_zeitreihen_indikatoren(df, metric_cfg),
        sr,
        metric_cfg,
        rand_phasen="ZENSIERT_UEBERGEHEN",
    )
    states = klassifiziere_regime(states, RegimeSchwellen(), RegimeGateConfig())
    return {int(st.phase_nr): str(st.regime) for st in states}


# =============================================================================
# 3) KANDIDATEN-ERFASSUNG (voll vektorisiert je Anker-Fenster)
# =============================================================================


def _echte_phasen(sr: SegmentResult) -> List[Tuple[int, PhaseData]]:
    """1-basierte Nummerierung der echten Bruch-Phasen (wie _erfasse_signale)."""
    return [
        (nr, p)
        for nr, p in enumerate(
            (p for p in sr.phases if p.break_dir is not None and p.brk_idx is not None),
            start=1,
        )
    ]


def _erfasse_avwap_kandidaten(
    df: pd.DataFrame,
    sr: SegmentResult,
    cfg: AavwapConfig,
    regime_map: Dict[int, str],
) -> Tuple[List[AavwapKandidat], Dict[int, Tuple[PhaseData, pd.Timestamp, str]]]:
    """Erfasst AVWAP-Pullback-Kandidaten ueber die Anker-Fenster (vektorisiert).

    Args:
        df: OHLCV-DataFrame (ts/open/high/low/close/tick_volume/idx).
        sr: SegmentResult.
        cfg: AavwapConfig.
        regime_map: ``{phase_nr: regime}`` aus ``_regime_je_phase``.

    Returns:
        (kandidaten, meta): kandidaten = Kontakt-Kandidaten chronologisch
        (je Kontakt-Bar genau ein Objekt, natuerlicher Status); meta =
        {phase_nr: (anchor_phase, fenster_ende_ts, regime)} fuer den
        Report/Chart.
    """
    n: int = len(df)
    _, slope_arr = berechne_ema_slope_vektoren(df, cfg.ema_periode)
    high: np.ndarray = df["high"].values.astype(float)
    low: np.ndarray = df["low"].values.astype(float)
    close: np.ndarray = df["close"].values.astype(float)
    opens: np.ndarray = df["open"].values.astype(float)
    ts: pd.Series = df["ts"]
    puf: float = cfg.stop_puffer

    phasen: List[PhaseData] = sr.phases
    kandidaten: List[AavwapKandidat] = []
    meta: Dict[int, Tuple[PhaseData, pd.Timestamp, str]] = {}
    kontakt_phasen: List[int] = []

    for nr, p in _echte_phasen(sr):
        b: int = int(p.brk_idx)
        up: bool = p.break_dir == "up"
        regime: str = regime_map.get(nr, "UNKLAR")
        # Fenster-Ende: brk_idx der unmittelbar folgenden Phase, sonst Datenende
        idx_p: int = phasen.index(p)
        folge: Optional[PhaseData] = phasen[idx_p + 1] if idx_p + 1 < len(phasen) else None
        if folge is not None and folge.brk_idx is not None:
            wend: int = int(folge.brk_idx)
        else:
            wend = n
        meta[nr] = (p, df["ts"].iloc[wend - 1] if wend > 0 else df["ts"].iloc[0], regime)

        # AVWAP ab Anker b INKLUSIVE (Anker-Bar gehoert zur Positionierung).
        avwap_vec: np.ndarray = berechne_avwap_vektor(
            df, b, preis_modus="typisch", volumen_spalte="tick_volume"
        )

        # k-Vektor: Kontakt an k, Rejection an k+1 MUSS im Fenster liegen
        # (k+1 < wend) und k+1 < n (close existiert).
        k_start: int = b + 1
        k_stop: int = min(wend, n) - 1  # exklusiv: k <= k_stop-1 = wend-2
        if k_stop - k_start <= 0:
            continue
        kvec: np.ndarray = np.arange(k_start, k_stop)
        if len(kvec) == 0:
            continue

        av: np.ndarray = avwap_vec[kvec]
        # AVWAP-Kontakt: Bar umschliesst die AVWAP-Linie (richtungsoffen).
        kontakt: np.ndarray = (low[kvec] <= av) & (av <= high[kvec]) & np.isfinite(av)

        if up:
            rej: np.ndarray = close[kvec + 1] > high[kvec]
            slope_ok: np.ndarray = slope_arr[kvec + 1] > 0.0
            roh: np.ndarray = np.minimum(low[kvec], low[kvec + 1])
            stop_v: np.ndarray = roh - puf
        else:
            rej = close[kvec + 1] < low[kvec]
            slope_ok = slope_arr[kvec + 1] < 0.0
            roh = np.maximum(high[kvec], high[kvec + 1])
            stop_v = roh + puf

        if kontakt.any():
            kontakt_phasen.append(nr)
        # Je Kontakt-Bar genau ein Kandidaten-Objekt (Per-Bar-Re-Arming)
        for j in np.flatnonzero(kontakt):
            k: int = int(kvec[j])
            d: AavwapDir = "up" if up else "down"
            av_w: float = float(av[j])
            entry_idx: int = k + 2

            if not bool(rej[j]):
                status: AavwapStatus = "KEINE_REJECTION"
                kandidaten.append(
                    AavwapKandidat(
                        arm="AVWAP_PULLBACK", phase=nr, dir=d,
                        brk_idx=b, kontakt_idx=k, rejection_idx=k + 1,
                        entry_idx=-1, entry_ts=None, entry_preis=float("nan"),
                        avwap_wert=av_w, stop_level=float(stop_v[j]),
                        sl_usd=float("nan"), status=status,
                    )
                )
                continue
            if not bool(slope_ok[j]):
                status = "SLOPE_INVALIDE"
                kandidaten.append(
                    AavwapKandidat(
                        arm="AVWAP_PULLBACK", phase=nr, dir=d,
                        brk_idx=b, kontakt_idx=k, rejection_idx=k + 1,
                        entry_idx=-1, entry_ts=None, entry_preis=float("nan"),
                        avwap_wert=av_w, stop_level=float(stop_v[j]),
                        sl_usd=float("nan"), status=status,
                    )
                )
                continue
            if entry_idx >= n:
                status = "DATEN_ENDE"
                kandidaten.append(
                    AavwapKandidat(
                        arm="AVWAP_PULLBACK", phase=nr, dir=d,
                        brk_idx=b, kontakt_idx=k, rejection_idx=k + 1,
                        entry_idx=-1, entry_ts=None, entry_preis=float("nan"),
                        avwap_wert=av_w, stop_level=float(stop_v[j]),
                        sl_usd=float("nan"), status=status,
                    )
                )
                continue
            e_preis: float = float(opens[entry_idx])
            stop_lvl: float = float(stop_v[j])
            # Gap: oeffnet die Entry-Bar jenseits des Stops -> ungueltig
            if (up and e_preis <= stop_lvl) or ((not up) and e_preis >= stop_lvl):
                status = "SL_UEBERSCHRITTEN"
                kandidaten.append(
                    AavwapKandidat(
                        arm="AVWAP_PULLBACK", phase=nr, dir=d,
                        brk_idx=b, kontakt_idx=k, rejection_idx=k + 1,
                        entry_idx=entry_idx, entry_ts=ts.iloc[entry_idx],
                        entry_preis=e_preis, avwap_wert=av_w,
                        stop_level=stop_lvl, sl_usd=float("nan"),
                        status=status,
                    )
                )
                continue
            sl_usd: float = abs(e_preis - stop_lvl)
            kandidaten.append(
                AavwapKandidat(
                    arm="AVWAP_PULLBACK", phase=nr, dir=d,
                    brk_idx=b, kontakt_idx=k, rejection_idx=k + 1,
                    entry_idx=entry_idx, entry_ts=ts.iloc[entry_idx],
                    entry_preis=e_preis, avwap_wert=av_w,
                    stop_level=stop_lvl, sl_usd=sl_usd, status="SIGNAL",
                )
            )
    return kandidaten, meta


# =============================================================================
# 4) SIMULATION (TREND-only-Gate + F3-Suppression + Variante-B-Reuse)
# =============================================================================


def _trade_zu_signal(k: AavwapKandidat, cfg: AavwapConfig) -> SetupCSignal:
    """Baut aus einem SIGNAL-Kandidaten ein SetupCSignal (Reuse-Schnittstelle).

    Die 1:1-Nutzung von ``_simuliere_kern_ema_trailing`` erfordert einen
    ``SetupCSignal``-Datenvertrag. ``arm`` ist fuer die Trailing-Simulation
    bedeutungslos (nur Gate-Metadaten); gewaehlt wird "RETEST" (naechster
    Produktions-Verwandter, Pullback-/Retest-Semantik).
    """
    return SetupCSignal(
        arm="RETEST",
        phase=k.phase,
        dir=k.dir,  # type: ignore[arg-type]
        kante=float("nan"),  # im Trailing ungenutzt
        brk_idx=k.brk_idx,
        trigger_idx=k.kontakt_idx,
        entry_idx=k.entry_idx,
        entry_ts=k.entry_ts,
        entry_preis=k.entry_preis,
        stop_level=k.stop_level,
        sl_usd=k.sl_usd,
        vorlauf_bars=None,
        vol_bestaetigt=None,
        status="SIGNAL",  # type: ignore[arg-type]
    )


def _simuliere_avwap(
    df: pd.DataFrame,
    cfg: AavwapConfig,
    kandidaten: Sequence[AavwapKandidat],
    regime_map: Dict[int, str],
) -> Tuple[
    List[Tuple[AavwapKandidat, object]],
    List[AavwapKandidat],
    List[AavwapKandidat],
    int,
    int,
]:
    """Simuliert TREND-gegatete SIGNAL-Kandidaten (F3 + Variante B).

    Args:
        df: OHLCV-DataFrame.
        cfg: AavwapConfig.
        kandidaten: Erfasste AVWAP-Kandidaten (deterministisch).
        regime_map: ``{phase_nr: regime}``.

    Returns:
        (trades, suppressed, blockiert, n_gate, n_signal):
        trades = (kandidat, KernelTrade) der aktivierten Trades; suppressed
        = SIGNAL im TREND-Gate, die an der F3-Suppression scheitern;
        blockiert = SIGNAL in Nicht-TREND-Phasen (REGIME_BLOCKIERT);
        n_gate = SIGNAL im TREND-Gate vor F3; n_signal = SIGNAL gesamt.
    """
    trend_cfg: TrendConfig = TrendConfig(fenster="AUG")
    trailing_cfg: EMASlopeTrailingConfig = EMASlopeTrailingConfig(
        aktiviert=True,
        ema_periode=cfg.ema_periode,
        modus="STOP_AUF_EXTREMUM",
        mindest_gewinn_r=cfg.mindest_gewinn_r,
        notfall_horizont_bars=cfg.notfall_horizont_bars,
    )
    ema_arr, slope_arr = berechne_ema_slope_vektoren(df, cfg.ema_periode)

    signale_all: List[AavwapKandidat] = [k for k in kandidaten if k.status == "SIGNAL"]
    signale_all.sort(key=lambda k: (k.phase, k.dir, k.entry_idx))
    n_signal: int = len(signale_all)

    if cfg.erfordere_trend_regime:
        gated: List[AavwapKandidat] = [
            k for k in signale_all if regime_map.get(k.phase) == "TREND"
        ]
        blockiert: List[AavwapKandidat] = [
            k for k in signale_all if regime_map.get(k.phase) != "TREND"
        ]
    else:
        gated = list(signale_all)
        blockiert = []
    n_gate: int = len(gated)

    trades: List[Tuple[AavwapKandidat, object]] = []
    suppressed: List[AavwapKandidat] = []
    offen_bis: Dict[Tuple[int, str], int] = {}
    for k in gated:
        key: Tuple[int, str] = (k.phase, k.dir)
        if k.entry_idx <= offen_bis.get(key, -1):
            suppressed.append(k)
            continue
        trade = _simuliere_kern_ema_trailing(
            df, _trade_zu_signal(k, cfg), trend_cfg,
            ema_arr, slope_arr, trailing_cfg,
        )
        trades.append((k, trade))
        offen_bis[key] = int(trade.exit_idx)
    return trades, suppressed, blockiert, n_gate, n_signal


# KernelTradeLike nur fuer Typ-Doku (Import bleibt lesend); das echte Objekt
# liefert _simuliere_kern_ema_trailing (scripts.setup_c_profil.KernelTrade).
KernelTradeLike = object


# =============================================================================
# 5) AGGREGATION / REPORT
# =============================================================================


def _fmt(v: object, f: str = ".2f") -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(float(v))):
        return "-"
    return f"{v:{f}}"


def _aggregiere_realisiert(werte_f4: List[float], holds: List[int]) -> dict:
    rs: np.ndarray = np.array(werte_f4, dtype=float)
    out: dict = {
        "n": len(rs),
        "sum_r_f4": float(rs.sum()) if len(rs) else 0.0,
        "mean": float(rs.mean()) if len(rs) else float("nan"),
        "median": float(np.median(rs)) if len(rs) else float("nan"),
        "wr": float(np.mean(rs > 0.0) * 100.0) if len(rs) else float("nan"),
        "pf": float("inf"),
        "bester": float(rs.max()) if len(rs) else float("nan"),
        "schlechtester": float(rs.min()) if len(rs) else float("nan"),
        "mean_hold": float(np.mean(holds)) if holds else float("nan"),
    }
    if len(rs):
        pos: float = float(rs[rs > 0.0].sum())
        neg: float = float(-rs[rs < 0.0].sum())
        out["pf"] = pos / neg if neg > 0.0 else float("inf")
    return out


def _urteil(
    agg: dict,
    trades: List[Tuple[AavwapKandidat, object]],
) -> Tuple[bool, List[str]]:
    """Erfolgskriterium: PF>=1.50, SumR>0, Ph-6/7-Gewinner erfasst (AUG)."""
    zeilen: List[str] = []
    ok_pf: bool = float(agg["pf"]) >= 1.50
    ok_r: bool = float(agg["sum_r_f4"]) > 0.0
    ph67: List[Tuple[AavwapKandidat, object]] = [
        (k, t) for k, t in trades if k.phase in (6, 7)
        and str(getattr(t, "exit_grund")) != "RECHTS_ZENSIERT"
    ]
    ok_67: bool = bool(ph67) and sum(float(getattr(t, "r_f4")) for _, t in ph67) > 0.0
    zeilen.append(f"  Kriterium PF  >= 1.50 : {'ERFUELLT' if ok_pf else 'VERFEHLT'} "
                  f"(PF = {_fmt(agg['pf'])})")
    zeilen.append(f"  Kriterium SumR > 0.0  : {'ERFUELLT' if ok_r else 'VERFEHLT'} "
                  f"(sum r_f4 = {agg['sum_r_f4']:+.2f}R)")
    zeilen.append(f"  Kriterium Ph6/7 Gewinn: {'ERFUELLT' if ok_67 else 'VERFEHLT'} "
                  f"(realisierte Trades n={len(ph67)}, sum r_f4 = "
                  f"{sum(float(getattr(t, 'r_f4')) for _, t in ph67):+.2f}R)")
    bestanden: bool = ok_pf and ok_r and ok_67
    urteil_text: str = (
        "BESTANDEN (Kandidat fuer Setup-C-Pfad-A)"
        if bestanden
        else "NULL-BEFUND (§5.6-Arretierung vorgesehen)"
    )
    zeilen.append(f"  GESAMTURTEIL: {urteil_text}")
    return bestanden, zeilen


def _bericht_text(
    cfg: AavwapConfig,
    df: pd.DataFrame,
    sr: SegmentResult,
    kandidaten: List[AavwapKandidat],
    trades: List[Tuple[AavwapKandidat, object]],
    suppressed: List[AavwapKandidat],
    blockiert: List[AavwapKandidat],
    n_gate: int,
    n_signal: int,
    regime_map: Dict[int, str],
    meta: Dict[int, Tuple[PhaseData, pd.Timestamp, str]],
) -> str:
    """Baut den Textreport (realisiert + Kandidaten-/Phasen-Detail)."""
    start, ende = FENSTER_DEFS["AUG"]
    linie: str = "=" * 120

    realisiert: List[Tuple[AavwapKandidat, object]] = [
        (k, t) for k, t in trades if str(getattr(t, "exit_grund")) != "RECHTS_ZENSIERT"
    ]
    zensiert: List[Tuple[AavwapKandidat, object]] = [
        (k, t) for k, t in trades if str(getattr(t, "exit_grund")) == "RECHTS_ZENSIERT"
    ]
    r_f4_vals: List[float] = [float(getattr(t, "r_f4")) for _, t in realisiert]
    holds: List[int] = [int(getattr(t, "haltezeit_bars")) for _, t in realisiert]
    agg = _aggregiere_realisiert(r_f4_vals, holds)
    bestanden, urteil = _urteil(agg, trades)

    status_cnt: Dict[str, int] = {}
    for k in kandidaten:
        status_cnt[k.status] = status_cnt.get(k.status, 0) + 1
    # REGIME_BLOCKIERT = SIGNAL in Nicht-TREND-Phasen
    n_blocked_signal: int = len(blockiert)

    txt: List[str] = [
        linie,
        "SETUP C - AVWAP-PULLBACK-ZWISCHENTEST (test/tmp_setup_c_avwap_test.py)",
        f"Fenster: AUG | SILVER M15 | {start} .. {ende} (ende-exkl.) | df-Bars: {len(df)}",
        "Arm: AVWAP_PULLBACK (Pfad A, AVWAP-Kontakt ab phasen-bruch-inklusivem Anker)",
        f"Config: ema_periode={cfg.ema_periode}  stop_puffer={cfg.stop_puffer}  "
        f"sl_pct_ref={cfg.sl_pct_ref}  erfordere_trend_regime={cfg.erfordere_trend_regime}",
        "Trigger: AVWAP-Kontakt an k, Rejection-Close an k+1 "
        "(close>high[k] Long / close<low[k] Short)",
        "         + kausaler Slope20(k+1); Ausfuehrung open[k+2]; Per-Bar-Re-Arming",
        "Stop: Struktur-Stop ueber [k,k+1] min/max(low/high) +- stop_puffer, KEIN Cap",
        "Regime: versiegelte Freeze-Defaults 05.09.2026 (RegimeSchwellen()/Gate()/Metric())",
        "Management: TREND-only-Gate + F3-Bucket-Suppression (Phase,Dir) + "
        "Variante-B-Ratchet 1:1 (mindest_gewinn_r=0.0, notfall=300)",
        linie,
        "",
    ]

    # Per-Phasen-Tabelle (Kontakte / Rej+Slope / SIGNAL / Regime)
    txt.append("PHASEN-TABELLE (echte Bruch-Phasen, Anker b = brk_idx):")
    txt.append(
        "  " + f"{'Ph':>3} {'Dir':<5} {'Regime':<9} {'brk':>5} {'Kontakte':>8} "
        f"{'Rej+Slope':>9} {'SIGNAL':>7} {'Gate':>6}"
    )
    ph_nummern: List[int] = [nr for nr, _ in _echte_phasen(sr)]
    for nr, p in _echte_phasen(sr):
        ph_k: List[AavwapKandidat] = [k for k in kandidaten if k.phase == nr]
        n_kontakt: int = len(ph_k)
        n_rs: int = sum(1 for k in ph_k if k.status in ("SIGNAL", "DATEN_ENDE",
                                                        "SL_UEBERSCHRITTEN"))
        n_sig: int = sum(1 for k in ph_k if k.status == "SIGNAL")
        reg: str = regime_map.get(nr, "?")
        in_gate: bool = reg == "TREND" and cfg.erfordere_trend_regime
        txt.append(
            "  " + f"{nr:>3} {str(p.break_dir):<5} {reg:<9} {int(p.brk_idx):>5} "
            f"{n_kontakt:>8} {n_rs:>9} {n_sig:>7} "
            f"{('TREND' if in_gate else 'blockiert'):>6}"
        )
    txt.append("")
    txt.append(
        "TREND-Phasen (Gate): "
        + ", ".join(str(nr) for nr in ph_nummern if regime_map.get(nr) == "TREND")
        or "-"
    )
    txt.append("")

    txt += [
        f"Kandidaten (Kontakt-Bars gesamt): {len(kandidaten)}",
        "  Status-Verteilung (natuerlich vor Gate): "
        + "  ".join(f"{s}={status_cnt.get(s, 0)}" for s in (
            "SIGNAL", "KEINE_REJECTION", "SLOPE_INVALIDE",
            "SL_UEBERSCHRITTEN", "DATEN_ENDE"))
        + f"   (Summe: {sum(status_cnt.values())})",
        f"SIGNAL gesamt: {n_signal}  "
        f"| davon REGIME_BLOCKIERT: {n_blocked_signal}  "
        f"| TREND-Gate vor F3: {n_gate}  "
        f"| F3-supprimiert: {len(suppressed)}  | aktiviert/simuliert: {len(trades)}",
        "",
    ]
    if agg["n"]:
        txt += [
            "STATISTIK REALISIERT (r_f4 = P&L / Struktur-Stop-Abstand):",
            f"  n = {agg['n']}   sum r_f4 = {agg['sum_r_f4']:+.2f}R",
            f"  mean = {_fmt(agg['mean']):>7}   median = {_fmt(agg['median']):>7}   "
            f"WR = {_fmt(agg['wr'], '.1f')}%   PF = {_fmt(agg['pf'])}",
            f"  bester = {agg['bester']:+.2f}   schlechtester = "
            f"{agg['schlechtester']:+.2f}   mittl. Haltedauer = "
            f"{_fmt(agg['mean_hold'], '.0f')} Bars",
        ]
        l_vals: List[float] = [float(getattr(t, "r_f4")) for k, t in realisiert if k.dir == "up"]
        s_vals: List[float] = [float(getattr(t, "r_f4")) for k, t in realisiert if k.dir == "down"]
        if l_vals:
            txt.append(f"  LONG : n={len(l_vals):>3}  sum r_f4 = {sum(l_vals):+.2f}")
        if s_vals:
            txt.append(f"  SHORT: n={len(s_vals):>3}  sum r_f4 = {sum(s_vals):+.2f}")
        txt.append("  Exit-Verteilung (realisiert):")
        for g in ("INITIAL_SL_INTRABAR", "TRAILING_SL_INTRABAR", "CRASH_HORIZONT_CLOSE"):
            cnt = sum(1 for _, t in realisiert if getattr(t, "exit_grund") == g)
            txt.append(f"    {g}: {cnt}")
    else:
        txt.append("STATISTIK REALISIERT: (keine realisierten Trades)")
    if zensiert:
        z_sum: float = sum(float(getattr(t, "r_ref")) for _, t in zensiert)
        txt.append("")
        txt.append(
            f"RECHTS_ZENSIERT (MtM zum letzten Close): n={len(zensiert)}  "
            f"sum r_ref(MtM) = {z_sum:+.2f}  (nicht in realisierter Statistik)"
        )
    txt.append("")
    txt.append(linie)
    txt.append("ERFOLGSKRITERIUM (Spezifikation, AUG):")
    txt += urteil
    txt.append(linie)
    txt.append("TRADE-DETAIL (realisiert, chronologisch):")
    txt.append(
        "  " + f"{'Nr':>3} {'Ph':>3} {'Dir':<5} {'Kontakt':>7} {'Rej':>4} "
        f"{'EntryIdx':>8} {'Entry':>8} {'Stop':>8} {'AVWAP':>8} {'ExitIdx':>7} "
        f"{'Exit':>8} {'Hold':>4} {'Grund':<20} {'r_f4':>7} {'kum':>8}"
    )
    kum: float = 0.0
    for i, (k, t) in enumerate(realisiert, start=1):
        kum += float(getattr(t, "r_f4"))
        txt.append(
            "  "
            + f"{i:>3} {k.phase:>3} {str(k.dir):<5} {k.kontakt_idx:>7} "
            f"{k.rejection_idx:>4} {k.entry_idx:>8} {k.entry_preis:>8.3f} "
            f"{k.stop_level:>8.3f} {k.avwap_wert:>8.3f} "
            f"{int(getattr(t, 'exit_idx')):>7} {float(getattr(t, 'exit_preis')):>8.3f} "
            f"{int(getattr(t, 'haltezeit_bars')):>4} "
            f"{str(getattr(t, 'exit_grund')):<20} {float(getattr(t, 'r_f4')):>+7.2f} "
            f"{kum:>+8.2f}"
        )
    if zensiert:
        txt.append("  RECHTS_ZENSIERT (isoliert):")
        for i, (k, t) in enumerate(zensiert, start=1):
            txt.append(
                "  "
                + f"Z{i:>2} {k.phase:>3} {str(k.dir):<5} {k.kontakt_idx:>7} "
                f"{k.rejection_idx:>4} {k.entry_idx:>8} {k.entry_preis:>8.3f} "
                f"{k.stop_level:>8.3f} {k.avwap_wert:>8.3f} "
                f"{int(getattr(t, 'exit_idx')):>7} {float(getattr(t, 'exit_preis')):>8.3f} "
                f"{int(getattr(t, 'haltezeit_bars')):>4} "
                f"{str(getattr(t, 'exit_grund')):<20} {float(getattr(t, 'r_ref')):>+7.2f} "
                "(r_ref/MtM)"
            )
    if suppressed:
        txt.append("  F3-SUPPRIMIERT (TREND-Gate):")
        for i, k in enumerate(suppressed, start=1):
            txt.append(
                "  "
                + f"S{i:>2} {k.phase:>3} {str(k.dir):<5} {k.kontakt_idx:>7} "
                f"{k.rejection_idx:>4} {k.entry_idx:>8} {k.entry_preis:>8.3f} "
                f"{k.stop_level:>8.3f} {k.avwap_wert:>8.3f} (F3-Bucket belegt)"
            )
    if blockiert:
        txt.append("  REGIME_BLOCKIERT (Nicht-TREND-Phase, nur Info):")
        for i, k in enumerate(blockiert, start=1):
            txt.append(
                "  "
                + f"B{i:>2} {k.phase:>3} {str(k.dir):<5} {k.kontakt_idx:>7} "
                f"{k.rejection_idx:>4} {k.entry_idx:>8} {k.entry_preis:>8.3f} "
                f"{k.stop_level:>8.3f} {k.avwap_wert:>8.3f} "
                f"(Regime={regime_map.get(k.phase)})"
            )
    txt.append(linie)
    return "\n".join(txt)


def _trades_tsv(
    trades: List[Tuple[AavwapKandidat, object]],
) -> str:
    """TSV-Block (aktivierte Trades inkl. RECHTS_ZENSIERT-Kennzeichnung)."""
    kopf: List[str] = [
        "# setup_c AVWAP_PULLBACK - Fenster: AUG (TREND-only-Gate)",
        "# r_f4 = P&L / (entry - stop); r_ref = P&L / (entry * 0.45%)",
        "# zensiert=1: RECHTS_ZENSIERT am Datenende (r_ref = MtM, strikt isoliert)",
    ]
    header: str = (
        "nr\tphase\tdir\tbrk_idx\tkontakt_idx\trejection_idx\tentry_idx\t"
        "entry_ts\tentry_preis\tavwap_wert\tstop_level\tsl_usd\texit_idx\texit_ts\t"
        "exit_preis\texit_grund\thaltezeit_bars\tr_f4\tr_ref\tzensiert"
    )
    zeilen: List[str] = [*kopf, header]
    for i, (k, t) in enumerate(trades, start=1):
        zens: bool = str(getattr(t, "exit_grund")) == "RECHTS_ZENSIERT"
        zeilen.append(
            f"{i}\t{k.phase}\t{k.dir}\t{k.brk_idx}\t{k.kontakt_idx}\t"
            f"{k.rejection_idx}\t{k.entry_idx}\t{k.entry_ts}\t{k.entry_preis:.5f}\t"
            f"{k.avwap_wert:.5f}\t{k.stop_level:.5f}\t{k.sl_usd:.5f}\t"
            f"{int(getattr(t, 'exit_idx'))}\t{getattr(t, 'exit_ts')}\t"
            f"{float(getattr(t, 'exit_preis')):.5f}\t{getattr(t, 'exit_grund')}\t"
            f"{int(getattr(t, 'haltezeit_bars'))}\t{float(getattr(t, 'r_f4')):.5f}\t"
            f"{float(getattr(t, 'r_ref')):.5f}\t{1 if zens else 0}"
        )
    return "\n".join(zeilen)


# =============================================================================
# 6) CHART (300 dpi): Preis + EMA + AVWAP-Segmente + Trades + Equity
# =============================================================================


def _zeichne_avwap(
    cfg: AavwapConfig,
    df: pd.DataFrame,
    sr: SegmentResult,
    kandidaten: List[AavwapKandidat],
    trades: List[Tuple[AavwapKandidat, object]],
    regime_map: Dict[int, str],
    meta: Dict[int, Tuple[PhaseData, pd.Timestamp, str]],
    out_png: Path,
    dpi: int,
) -> None:
    """Rendert Preis/EMA/AVWAP/Trades (oben) und kumulierte r_f4 (unten)."""
    realisiert: List[Tuple[AavwapKandidat, object]] = [
        (k, t) for k, t in trades
        if str(getattr(t, "exit_grund")) != "RECHTS_ZENSIERT"
    ]
    zensiert: List[Tuple[AavwapKandidat, object]] = [
        (k, t) for k, t in trades
        if str(getattr(t, "exit_grund")) == "RECHTS_ZENSIERT"
    ]
    idx: np.ndarray = df["idx"].values.astype(int)
    n: int = len(df)
    ema_s: pd.Series = df["close"].astype(float).ewm(
        span=cfg.ema_periode, adjust=False
    ).mean()
    high: np.ndarray = df["high"].values.astype(float)
    low: np.ndarray = df["low"].values.astype(float)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(17, 11), sharex=True,
        gridspec_kw={"height_ratios": [3.2, 1.0], "hspace": 0.08},
    )

    ax1.plot(idx, df["close"].values.astype(float), color="#000000", lw=0.9,
             zorder=3, label="Close")
    ax1.plot(idx, ema_s.to_numpy(dtype=float), color=_COL_EMA, lw=1.1,
             zorder=4, label=f"EMA({cfg.ema_periode})")

    # AVWAP-Segmente je TREND-Phase (Anker b inklusiv, bis Fenster-Ende)
    phasen: List[PhaseData] = sr.phases
    for nr, p in _echte_phasen(sr):
        if regime_map.get(nr) != "TREND":
            continue
        b: int = int(p.brk_idx)
        idx_p: int = phasen.index(p)
        folge = phasen[idx_p + 1] if idx_p + 1 < len(phasen) else None
        wend: int = int(folge.brk_idx) if folge is not None and folge.brk_idx is not None else n
        av: np.ndarray = berechne_avwap_vektor(
            df, b, preis_modus="typisch", volumen_spalte="tick_volume"
        )
        seg_idx: np.ndarray = np.arange(b, min(wend, n))
        ax1.plot(seg_idx, av[seg_idx], color=_COL_AVWAP, lw=1.4, ls="--",
                 alpha=0.9, zorder=2,
                 label=f"AVWAP Ph{nr} (b={b})")

    # Bruchanker-Schattierung (alle Phasen) + TREND-Hervorhebung
    for p in sr.phases:
        if p.break_dir is None or p.brk_idx is None or p.brk_kante is None:
            continue
        b = int(p.brk_idx)
        ax1.axvline(b, color=_COL_UP if p.break_dir == "up" else _COL_DOWN,
                    lw=0.5, ls=":", alpha=0.4, zorder=1)
    for nr, p in _echte_phasen(sr):
        if regime_map.get(nr) != "TREND":
            continue
        b = int(p.brk_idx)
        ax1.axvspan(b, b + 8, color=_COL_AVWAP, alpha=0.08, zorder=0)

    # Kandidaten-Kontakte (alle SIGNAL-faehigen, kleiner Ring; TREND = gefuellt)
    for c in kandidaten:
        if c.status not in ("SIGNAL", "DATEN_ENDE", "SL_UEBERSCHRITTEN"):
            continue
        if c.status == "SIGNAL":
            ist_trend: bool = regime_map.get(c.phase) == "TREND"
            col_c: str = _COL_UP if (c.dir == "up" and ist_trend) else (
                _COL_DOWN if (c.dir == "down" and ist_trend) else _COL_BLOCK)
            y_c: float = low[c.kontakt_idx] if c.dir == "up" else high[c.kontakt_idx]
            ax1.scatter(c.kontakt_idx, y_c, marker="o", s=26,
                        facecolor=col_c if ist_trend else "none",
                        edgecolor=col_c, lw=0.7, zorder=5)

    # Trades (realisiert): Entry + Exit-Pfad
    for c, t in realisiert:
        col: str = _COL_UP if c.dir == "up" else _COL_DOWN
        ex_i: int = int(getattr(t, "exit_idx"))
        ax1.plot([c.entry_idx, ex_i], [c.entry_preis, float(getattr(t, "exit_preis"))],
                 color=col, lw=0.9, alpha=0.6, zorder=2)
        ax1.scatter(c.entry_idx, c.entry_preis, marker="^" if c.dir == "up" else "v",
                    s=65, color=col, edgecolor="w", linewidths=0.4, zorder=6)
        g: str = str(getattr(t, "exit_grund"))
        if g.startswith("TRAILING") or g.startswith("INITIAL"):
            ax1.scatter(ex_i, float(getattr(t, "exit_preis")), marker="s", s=40,
                        color=_COL_STOP, edgecolor="w", linewidths=0.4, zorder=6)
        else:
            ax1.scatter(ex_i, float(getattr(t, "exit_preis")), marker="x", s=40,
                        color=_COL_FLIP, zorder=6)
    for c, t in zensiert:
        col = _COL_UP if c.dir == "up" else _COL_DOWN
        ax1.scatter(c.entry_idx, c.entry_preis, marker="^" if c.dir == "up" else "v",
                    s=65, color=col, edgecolor="k", linewidths=0.7, zorder=6)

    step: int = max(16, n // 14)
    ticks: np.ndarray = np.arange(0, n, step)
    ax1.set_xticks(ticks)
    ax1.set_ylabel("USD")
    trend_ph: str = ", ".join(
        str(nr) for nr, _ in _echte_phasen(sr) if regime_map.get(nr) == "TREND"
    )
    ax1.set_title(
        f"SETUP C | AUG | AVWAP-PULLBACK (TREND-Gate Ph {trend_ph}) | "
        f"{FENSTER_DEFS['AUG'][0]} .. {FENSTER_DEFS['AUG'][1]} (ende-exkl.)"
    )
    ax1.grid(alpha=0.3)
    ax1.legend(loc="upper left", fontsize=8, framealpha=0.9, ncol=3)

    if realisiert:
        x_exits: List[int] = [int(getattr(t, "exit_idx")) for _, t in realisiert]
        kum: np.ndarray = np.cumsum([float(getattr(t, "r_f4")) for _, t in realisiert])
        x_step: List[int] = [int(realisiert[0][0].entry_idx)] + x_exits
        y_step: List[float] = [0.0] + [float(v) for v in kum]
        ax2.plot(x_step, y_step, drawstyle="steps-post", color=_COL_UP, lw=1.3,
                 zorder=3, label="kum. r_f4 (realisiert)")
        ax2.axhline(0.0, color="#555555", lw=0.6, zorder=2)
        ax2.scatter(x_exits, kum, s=18, color=_COL_UP, zorder=4)
        if zensiert:
            z_last: float = float(kum[-1]) if len(kum) else 0.0
            for c, t in zensiert:
                z_last += float(getattr(t, "r_ref"))
            ax2.scatter(int(zensiert[-1][0].entry_idx), z_last, marker="o",
                        facecolor="none", edgecolor="#c00000", s=40, zorder=5)
            ax2.annotate(f"OFFEN MtM {z_last:+.2f}R (zensiert)",
                         (int(zensiert[-1][0].entry_idx), z_last),
                         xytext=(int(zensiert[-1][0].entry_idx) - 150, z_last),
                         fontsize=8, color="#c00000")
    ax2.set_ylabel("r_f4 (kum.)")
    ax2.grid(alpha=0.3)
    ax2.set_xlim(-1, n)
    ax2.set_xticks(ticks)
    ax2.set_xticklabels(
        [df["ts"].iloc[t].strftime("%a %d.%m %H:%M") for t in ticks],
        rotation=45, ha="right", fontsize=8,
    )
    legende: List[Line2D] = [
        Line2D([0], [0], color="#000000", lw=1.0, label="Close"),
        Line2D([0], [0], color=_COL_EMA, lw=1.5, label=f"EMA({cfg.ema_periode})"),
        Line2D([0], [0], color=_COL_AVWAP, lw=1.5, ls="--", label="AVWAP (TREND-Ph)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=_COL_UP, ms=6,
               label="Kontakt (TREND, up)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=_COL_DOWN, ms=6,
               label="Kontakt (TREND, down)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=_COL_BLOCK, ms=6,
               label="Kontakt (blockiert)"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor=_COL_UP, ms=7,
               label="LONG-Entry"),
        Line2D([0], [0], marker="v", color="w", markerfacecolor=_COL_DOWN, ms=7,
               label="SHORT-Entry"),
        Line2D([0], [0], marker="s", color=_COL_STOP, ms=5, ls="",
               label="Stop-Exit"),
        Line2D([0], [0], marker="x", color=_COL_FLIP, ms=6, ls="",
               label="Zeit-/Crash-Exit"),
        Line2D([0], [0], color=_COL_UP, lw=1.5, label="kum. r_f4 (realisiert)"),
    ]
    ax2.legend(handles=legende, loc="upper left", fontsize=7.5, framealpha=0.9)

    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=dpi)
    plt.close(fig)


# =============================================================================
# 7) RUNNER / MAIN
# =============================================================================


def run_avwap_test(fenster: str = "AUG", dpi: int = 300) -> str:
    """Fuehrt den AVWAP-PULLBACK-Zwischentest (AUG, TREND-only) aus."""
    if fenster != "AUG":
        raise SystemExit(f"Scope strikt auf AUG begrenzt; ungueltig: {fenster}")
    start, ende = FENSTER_DEFS[fenster]
    seg_cfg: SegmentConfig = SegmentConfig(start=start, ende=ende)
    df: pd.DataFrame = load_data(seg_cfg.db_path, seg_cfg.start, seg_cfg.ende)
    sr: SegmentResult = segmentiere_markt(df, seg_cfg)
    cfg: AavwapConfig = AavwapConfig()

    regime_map: Dict[int, str] = _regime_je_phase(df, sr)
    # Nummerierungs-Konsistenz: RegimeState je echter Bruch-Phase
    ph_nr: List[int] = [nr for nr, _ in _echte_phasen(sr)]
    assert set(regime_map.keys()) == set(ph_nr), (
        f"Regime-Nummerierung weicht ab: {sorted(regime_map)} vs {ph_nr}"
    )

    kandidaten, meta = _erfasse_avwap_kandidaten(df, sr, cfg, regime_map)
    trades, suppressed, blockiert, n_gate, n_signal = _simuliere_avwap(
        df, cfg, kandidaten, regime_map
    )

    text: str = _bericht_text(
        cfg, df, sr, kandidaten, trades, suppressed, blockiert,
        n_gate, n_signal, regime_map, meta,
    )
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_txt: Path = _REPORT_DIR / f"setup_c_avwap_{fenster}.txt"
    out_txt.write_text(text, encoding="utf-8")
    out_tsv: Path = _REPORT_DIR / f"setup_c_avwap_trades_{fenster}.tsv"
    out_tsv.write_text(_trades_tsv(trades), encoding="utf-8")
    out_png: Path = _REPORT_DIR / f"setup_c_avwap_{fenster}.png"
    _zeichne_avwap(cfg, df, sr, kandidaten, trades, regime_map, meta, out_png, dpi)
    return text


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI-Einstieg: fuehrt den AVWAP-PULLBACK-Zwischentest (AUG) aus."""
    args = list(sys.argv[1:] if argv is None else argv)
    fenster: str = "AUG"
    dpi: int = 300
    for a in args:
        if a.startswith("--fenster="):
            fenster = a.split("=", 1)[1].upper()
        elif a.startswith("--dpi="):
            dpi = int(a.split("=", 1)[1])
    text = run_avwap_test(fenster, dpi)
    print(text)
    print(
        f"\nReport: {_REPORT_DIR / f'setup_c_avwap_{fenster}.txt'}\n"
        f"TSV:    {_REPORT_DIR / f'setup_c_avwap_trades_{fenster}.tsv'}\n"
        f"PNG:    {_REPORT_DIR / f'setup_c_avwap_{fenster}.png'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
