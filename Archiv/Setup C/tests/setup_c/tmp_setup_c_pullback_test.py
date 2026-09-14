"""
SETUP C - PULLBACK-RE-ENTRY-ZWISCHENTEST (test/tmp_setup_c_pullback_test.py)
============================================================================
Status: ISOLIERTER EXPLORATIONS-TEST (AUG) - keine Produktions-Aenderung.
Baseline: scripts/setup_c_profil.py / scripts/market_segmentation.py /
      scripts/setup_c_chart.py - BYTE-IDENTISCH UNANGETASTET (nur lesende
      Importe aus market_segmentation + setup_c_profil).

Zweck
-----
Diagnostischer, prozyklischer Zusatz-Arm PULLBACK_REENTRY (Arretierung
E-1..E-5, Freigabe-Gate Schritt 5): Schliessen des Einstiegs-Bottlenecks
von Setup C durch trendbegleitende Re-Entries an zwei kausal gestaffelten
Zonen im phasenlosen/Expansions-Raum NACH einem echten 2-Close-Bruch.

Zonen (E-2, klare Trennung, Z1 vor Z2):
  Zone 1 (ZONE_1_KANTE)   - struktureller Kanten-Retest: Long-Kontakt bei
      low[k]  in [brk_kante - band, brk_kante + band] (S/R-Flip, inkl.
      Stop-Fishing-Pierce), Short gespiegelt mit high[k].
  Zone 2 (ZONE_2_EMA20)   - dynamischer EMA-20-Pullback: echtes
      EMA-Containment  low[k] <= EMA20[k] <= high[k]  (beide Richtungen).
  Praezedenz: Bar in beiden Baendern -> ZONE_1_KANTE (struktureller Anker).

Fenster-Grenze (Anker-Phase p_i, Fenster-Grenze verifiziert):
  Scan-Fenster = [p_i.brk_idx + 1, p_{i+1}.brk_idx)  (halboffen).  Die im
  Segmentierer unmittelbar folgende Phase p_{i+1} startet lueckenlos bei
  p_i.brk_idx; sobald p_{i+1} selbst bricht, uebernimmt deren brk_kante die
  Anker-Rolle. Fuer die finale ungebrochene Phase laeuft das Fenster bis
  Datenende (n-1). Spaete "Gift"-Kontakte nach ~100 Bars fallen damit in
  die Anker-Phase des Folge-Bruchs bzw. werden vom Slope-Hartfilter
  kassiert.

Trigger (E-4, striktes Next-Bar-Re-Arming; KEIN Multi-Bar-Lookback):
  Zonen-Kontakt an Bar k  ->  Status BERUEHRT (intern). Einstieg erst nach
  bestaetigtem Rejection-Close an der UNMITTELBAREN Folge-Bar k+1:
      Long : close[k+1] > high[k]   UND  kausal slope20[k+1] > 0.0
      Short: close[k+1] < low[k]    UND  kausal slope20[k+1] < 0.0
  Verweilt der Markt an der Zone, armiert jede weitere Kontakt-Bar j ihre
  EIGENE Folge-Bar-Bestaetigung j+1 (Per-Bar-Re-Arming). Bleibt die
  Bestaetigung aus, verfaellt der Trigger ersatzlos.

Struktur-Stop (Q1-Antwort, _stop_f4-Paritaet ueber Zwei-Bar-Spanne [k,k+1]):
      Long Z1: min(low[k], low[k+1], brk_kante) - stop_puffer
      Long Z2: min(low[k], low[k+1])            - stop_puffer
      Short   gespiegelt mit max()/high[] und + stop_puffer.
  KEIN kuenstlicher Stop-Cap (max_sl_kanten_mult gestrichen). Zone-1-Floor
  = brk_kante garantiert, dass der S/R-Flip die Invalidierung bleibt.

Ausfuehrung & Trade-Management:
  - Ausfuehrung strikt bei open[k+2] (Signal existiert erst bei close[k+1]).
    Fehlt Bar k+2 am Datenende -> DATEN_ENDE (kein Glattstellen). Oeffnet
    Bar k+2 bereits jenseits des Stops (Gap) -> SL_UEBERSCHRITTEN.
  - Sequentielle F3-Suppression (E-3): Key = (Anker-Phase, Richtung),
    max. EINE offene Position je Bucket; Re-Entry erst nach Exit des
    Bucket-Vorgaengers (Semantik identisch zu _kern_lauefe).
  - Exit-Management: 1:1-Nutzung der arretierten Variante-B-Ratchet
    (_simuliere_kern_ema_trailing, STOP_AUF_EXTREMUM,
    mindest_gewinn_r = 0.0, notfall_horizont_bars = 300) auf demselben
    kausal berechneten Slope-Vektor. Initial-Stop = Struktur-Stop (oben).
  - RECHTS_ZENSIERT (E2): Trade ueberlebt bis Datenende -> strikt isoliert.

Messung:
  r_f4  = P&L / (entry - stop)  (echter Struktur-Stop-Abstand)
  r_ref = P&L / (entry * sl_pct_ref)  (0.45 %-Referenz, neutral)

Ausgabe (reports/setup_c/, deterministisch reproduzierbar):
    setup_c_pullback_AUG.txt    Statistik + Kandidaten/Trade-Detail
    setup_c_pullback_trades_AUG.tsv   Trade-Block (maschinenlesbar)
    setup_c_pullback_AUG.png    300 dpi (Preis+EMA+Zonen-Marker+Equity)

Aufruf (Projekt-Root):
    python test/tmp_setup_c_pullback_test.py [--fenster=AUG] [--dpi=300]
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

from scripts.market_segmentation import (  # noqa: E402
    PhaseData,
    SegmentConfig,
    SegmentResult,
    load_data,
    segmentiere_markt,
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
_COL_Z1: str = "#b8860b"    # Zone 1 (Kanten-Retest)
_COL_Z2: str = "#9467bd"    # Zone 2 (EMA-20-Pullback)
_COL_STOP: str = "#8e44ad"
_COL_FLIP: str = "#999999"


# =============================================================================
# 1) DATENVERTRAG (freigegebenes Gate Schritt 5 - Felder exakt wie arretiert)
# =============================================================================

PullbackDir = Literal["up", "down"]
PullbackZone = Literal["ZONE_1_KANTE", "ZONE_2_EMA20"]

PullbackStatus = Literal[
    "SIGNAL",
    "KEIN_ZONEN_KONTAKT",
    "KEINE_REJECTION_BESTAETIGUNG",
    "SLOPE_INVALIDE",
    "SL_UEBERSCHRITTEN",
    "DATEN_ENDE",
]


@dataclass(frozen=True, slots=True)
class PullbackConfig:
    """Konfiguration fuer prozyklische Pullback-Re-Entries (§5.4)."""

    ema_periode: int = 20
    kanten_retest_band: float = 0.15   # USD: Toleranzband um brk_kante (Zone 1)
    rejection_lookback_bars: int = 1   # Striktes Next-Bar-Re-Arming (fix = 1)
    stop_puffer: float = 0.15          # USD: Puffer unter/ueber Struktur
    sl_pct_ref: float = 0.45           # Neutrale 0.45 %-SL-Referenzwaehrung
    # Trade-Management (arretierte Variante-B-Ratchet, §5.2)
    mindest_gewinn_r: float = 0.0
    notfall_horizont_bars: int = 300


@dataclass(slots=True)
class PullbackKandidat:
    """Typisierter Datenvertrag fuer ein Pullback-Re-Entry-Signal."""

    arm: Literal["PULLBACK_REENTRY"]
    phase: int                       # 1-basiert ueber echte Bruch-Phasen
    dir: PullbackDir                 # Identisch zur Bruchrichtung (prozyklisch)
    zone: PullbackZone               # ZONE_1_KANTE vor ZONE_2_EMA20
    brk_idx: int                     # Basis-Bruchanker
    kontakt_idx: int                 # Bar k: Zonenberuehrung
    rejection_idx: int               # Bar k+1: Bestaetigungs-Close
    entry_idx: int                   # Bar k+2: Ausfuehrung am Open
    entry_ts: Optional[pd.Timestamp]
    entry_preis: float
    stop_level: float                # Struktureller Stop ueber [k, k+1]
    sl_usd: float
    status: PullbackStatus


# =============================================================================
# 2) KANDIDATEN-ERFASSUNG (voll vektorisiert je Anker-Fenster)
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


def _erfasse_pullback_kandidaten(
    df: pd.DataFrame,
    sr: SegmentResult,
    cfg: PullbackConfig,
) -> Tuple[List[PullbackKandidat], Dict[int, Tuple[PhaseData, pd.Timestamp, int]]]:
    """Erfasst alle Pullback-Kandidaten ueber die Anker-Fenster (vektorisiert).

    Args:
        df: OHLCV-DataFrame (ts/open/high/low/close/idx, aufsteigend).
        sr: SegmentResult (segmentierte Phasen/Moves).
        cfg: PullbackConfig.

    Returns:
        (kandidaten, meta): kandidaten = alle Kontakt-Kandidaten
        chronologisch (je Kontakt-Bar genau ein Objekt, Status gesetzt);
        meta = {phase_nr: (anchor_phase, fenster_ende_ts, brk_kante)} fuer
        die Report-/Chart-Ausgabe.
    """
    n: int = len(df)
    ema_arr, slope_arr = berechne_ema_slope_vektoren(df, cfg.ema_periode)
    high: np.ndarray = df["high"].values.astype(float)
    low: np.ndarray = df["low"].values.astype(float)
    close: np.ndarray = df["close"].values.astype(float)
    opens: np.ndarray = df["open"].values.astype(float)
    ts: pd.Series = df["ts"]
    band: float = cfg.kanten_retest_band
    puf: float = cfg.stop_puffer

    phasen: List[PhaseData] = sr.phases
    kandidaten: List[PullbackKandidat] = []
    meta: Dict[int, Tuple[PhaseData, pd.Timestamp, int]] = {}

    for nr, p in _echte_phasen(sr):
        b: int = int(p.brk_idx)
        kante: float = float(p.brk_kante)
        up: bool = p.break_dir == "up"
        # Fenster-Ende: brk_idx der unmittelbar folgenden Phase, sonst Datenende
        idx_p: int = phasen.index(p)
        folge: Optional[PhaseData] = phasen[idx_p + 1] if idx_p + 1 < len(phasen) else None
        if folge is not None and folge.brk_idx is not None:
            wend: int = int(folge.brk_idx)
        else:
            wend = n
        meta[nr] = (p, df["ts"].iloc[wend - 1] if wend > 0 else df["ts"].iloc[0], kante)

        # k-Vektor: Kontakt an k, Rejection an k+1 MUSS im Fenster liegen
        # (k+1 < wend) und k+1 < n (close existiert).
        k_start: int = b + 1
        k_stop: int = min(wend, n) - 1  # exklusiv: k <= k_stop-1 = wend-2
        if k_stop - k_start <= 0:
            continue
        kvec: np.ndarray = np.arange(k_start, k_stop)
        if len(kvec) == 0:
            continue

        # Zone 1 / Zone 2 (vektorisiert, Z1-Praezedenz)
        if up:
            z1: np.ndarray = (low[kvec] >= kante - band) & (low[kvec] <= kante + band)
        else:
            z1 = (high[kvec] >= kante - band) & (high[kvec] <= kante + band)
        z2: np.ndarray = (low[kvec] <= ema_arr[kvec]) & (ema_arr[kvec] <= high[kvec])
        zone_kind: np.ndarray = np.where(z1, 1, np.where(z2, 2, 0)).astype(np.int8)

        # Rejection-Close + Slope an k+1
        if up:
            rej: np.ndarray = close[kvec + 1] > high[kvec]
            slope_ok: np.ndarray = slope_arr[kvec + 1] > 0.0
        else:
            rej = close[kvec + 1] < low[kvec]
            slope_ok = slope_arr[kvec + 1] < 0.0

        # Struktur-Stop ueber Zwei-Bar-Spanne [k, k+1] (vektorisiert)
        if up:
            roh: np.ndarray = np.minimum(low[kvec], low[kvec + 1])
            stop_v: np.ndarray = np.where(
                z1, np.minimum(roh, kante) - puf, roh - puf
            )
        else:
            roh = np.maximum(high[kvec], high[kvec + 1])
            stop_v = np.where(
                z1, np.maximum(roh, kante) + puf, roh + puf
            )

        # Je Kontakt-Bar genau ein Kandidaten-Objekt (Per-Bar-Re-Arming)
        for j in np.flatnonzero(zone_kind != 0):
            k: int = int(kvec[j])
            z: PullbackZone = "ZONE_1_KANTE" if int(zone_kind[j]) == 1 else "ZONE_2_EMA20"
            d: PullbackDir = "up" if up else "down"
            entry_idx: int = k + 2

            if not bool(rej[j]):
                status: PullbackStatus = "KEINE_REJECTION_BESTAETIGUNG"
                stop_lvl: float = float(stop_v[j])
                kandidaten.append(
                    PullbackKandidat(
                        arm="PULLBACK_REENTRY", phase=nr, dir=d, zone=z,
                        brk_idx=b, kontakt_idx=k, rejection_idx=k + 1,
                        entry_idx=-1, entry_ts=None, entry_preis=float("nan"),
                        stop_level=stop_lvl, sl_usd=float("nan"), status=status,
                    )
                )
                continue
            if not bool(slope_ok[j]):
                status = "SLOPE_INVALIDE"
                kandidaten.append(
                    PullbackKandidat(
                        arm="PULLBACK_REENTRY", phase=nr, dir=d, zone=z,
                        brk_idx=b, kontakt_idx=k, rejection_idx=k + 1,
                        entry_idx=-1, entry_ts=None, entry_preis=float("nan"),
                        stop_level=float(stop_v[j]), sl_usd=float("nan"),
                        status=status,
                    )
                )
                continue
            if entry_idx >= n:
                status = "DATEN_ENDE"
                kandidaten.append(
                    PullbackKandidat(
                        arm="PULLBACK_REENTRY", phase=nr, dir=d, zone=z,
                        brk_idx=b, kontakt_idx=k, rejection_idx=k + 1,
                        entry_idx=-1, entry_ts=None, entry_preis=float("nan"),
                        stop_level=float(stop_v[j]), sl_usd=float("nan"),
                        status=status,
                    )
                )
                continue
            stop_lvl = float(stop_v[j])
            e_preis: float = float(opens[entry_idx])
            # Gap: oeffnet die Entry-Bar jenseits des Stops -> ungueltig
            if (up and e_preis <= stop_lvl) or ((not up) and e_preis >= stop_lvl):
                status = "SL_UEBERSCHRITTEN"
                kandidaten.append(
                    PullbackKandidat(
                        arm="PULLBACK_REENTRY", phase=nr, dir=d, zone=z,
                        brk_idx=b, kontakt_idx=k, rejection_idx=k + 1,
                        entry_idx=entry_idx, entry_ts=ts.iloc[entry_idx],
                        entry_preis=e_preis, stop_level=stop_lvl,
                        sl_usd=float("nan"), status=status,
                    )
                )
                continue
            sl_usd: float = abs(e_preis - stop_lvl)
            kandidaten.append(
                PullbackKandidat(
                    arm="PULLBACK_REENTRY", phase=nr, dir=d, zone=z,
                    brk_idx=b, kontakt_idx=k, rejection_idx=k + 1,
                    entry_idx=entry_idx, entry_ts=ts.iloc[entry_idx],
                    entry_preis=e_preis, stop_level=stop_lvl,
                    sl_usd=sl_usd, status="SIGNAL",
                )
            )
    return kandidaten, meta


# =============================================================================
# 3) SIMULATION (1:1 Variante-B-Reuse + F3-Suppression, _kern_lauefe-Paritaet)
# =============================================================================


def _trade_zu_signal(k: PullbackKandidat, cfg: PullbackConfig) -> SetupCSignal:
    """Baut aus einem SIGNAL-Kandidaten ein SetupCSignal (Reuse-Schnittstelle).

    Die 1:1-Nutzung von ``_simuliere_kern_ema_trailing`` erfordert einen
    ``SetupCSignal``-Datenvertrag. ``arm`` ist fuer die Trailing-Simulation
    bedeutungslos (nur Gate-Metadaten); gewaehlt wird "RETEST" als naechster
    Produktions-Verwandter (Kanten-Retest-Semantik).
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


def _simuliere_pullback(
    df: pd.DataFrame,
    cfg: PullbackConfig,
    kandidaten: Sequence[PullbackKandidat],
) -> Tuple[List[Tuple[PullbackKandidat, "KernelTradeLike"]], List[PullbackKandidat], int]:
    """Simuliert die SIGNAL-Kandidaten mit F3-Suppression + Variante B.

    Args:
        df: OHLCV-DataFrame.
        cfg: PullbackConfig.
        kandidaten: Bereits erfasste Pullback-Kandidaten (deterministisch;
            vermeidet doppelte EMA-/Slope-Berechnung im Runner).

    Returns:
        (trades, suppressed, n_signal_total): trades = Liste (kandidat,
        KernelTrade) der aktivierten, simulierten Trades; suppressed =
        SIGNAL-Kandidaten, die an der F3-Bucket-Suppression scheitern;
        n_signal_total = Anzahl SIGNAL vor Suppression.
    """
    ema_arr, slope_arr = berechne_ema_slope_vektoren(df, cfg.ema_periode)
    trend_cfg: TrendConfig = TrendConfig(fenster="AUG")
    trailing_cfg: EMASlopeTrailingConfig = EMASlopeTrailingConfig(
        aktiviert=True,
        ema_periode=cfg.ema_periode,
        modus="STOP_AUF_EXTREMUM",
        mindest_gewinn_r=cfg.mindest_gewinn_r,
        notfall_horizont_bars=cfg.notfall_horizont_bars,
    )

    signale: List[PullbackKandidat] = [
        k for k in kandidaten if k.status == "SIGNAL"
    ]
    signale.sort(key=lambda k: (k.phase, k.dir, k.entry_idx))
    n_signal_total: int = len(signale)

    trades: List[Tuple[PullbackKandidat, object]] = []
    suppressed: List[PullbackKandidat] = []
    offen_bis: Dict[Tuple[int, str], int] = {}
    for k in signale:
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
    return trades, suppressed, n_signal_total


# KernelTradeLike nur fuer Typ-Doku (Import bleibt lesend); das echte Objekt
# liefert _simuliere_kern_ema_trailing (scripts.setup_c_profil.KernelTrade).
KernelTradeLike = object


# =============================================================================
# 4) AGGREGATION / REPORT
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


def _bericht_text(
    cfg: PullbackConfig,
    df: pd.DataFrame,
    sr: SegmentResult,
    kandidaten: List[PullbackKandidat],
    trades: List[Tuple[PullbackKandidat, object]],
    suppressed: List[PullbackKandidat],
    n_signal_total: int,
) -> str:
    """Baut den Textreport (realisierte Statistik + Kandidaten-/Trade-Detail)."""
    start, ende = FENSTER_DEFS["AUG"]
    linie: str = "=" * 120

    # Realisiert vs. zensiert (E2-Isolation)
    realisiert: List[Tuple[PullbackKandidat, object]] = [
        (k, t) for k, t in trades if str(getattr(t, "exit_grund")) != "RECHTS_ZENSIERT"
    ]
    zensiert: List[Tuple[PullbackKandidat, object]] = [
        (k, t) for k, t in trades if str(getattr(t, "exit_grund")) == "RECHTS_ZENSIERT"
    ]
    r_f4_vals: List[float] = [float(getattr(t, "r_f4")) for _, t in realisiert]
    holds: List[int] = [int(getattr(t, "haltezeit_bars")) for _, t in realisiert]
    agg = _aggregiere_realisiert(r_f4_vals, holds)

    # Status-Zaehler je Kandidat
    status_cnt: Dict[str, int] = {}
    zone_cnt: Dict[str, int] = {}
    for k in kandidaten:
        status_cnt[k.status] = status_cnt.get(k.status, 0) + 1
        zone_cnt[k.zone] = zone_cnt.get(k.zone, 0) + 1

    txt: List[str] = [
        linie,
        "SETUP C - PULLBACK-RE-ENTRY-ZWISCHENTEST (test/tmp_setup_c_pullback_test.py)",
        f"Fenster: AUG | SILVER M15 | {start} .. {ende} (ende-exkl.) | df-Bars: {len(df)}",
        "Arm: PULLBACK_REENTRY (prozyklisch, Zone 1 Kante / Zone 2 EMA20)",
        f"Config: ema_periode={cfg.ema_periode}  kanten_retest_band={cfg.kanten_retest_band}  "
        f"stop_puffer={cfg.stop_puffer}  rejection_lookback_bars={cfg.rejection_lookback_bars}",
        "Trigger: Rejection-Close an k+1 (close>high[k] Long / close<low[k] Short)",
        "         + kausaler Slope20(k+1); Ausfuehrung open[k+2]; Per-Bar-Re-Arming",
        "Stop: Struktur-Stop ueber [k,k+1] (_stop_f4-Paritaet), Zone-1-Kanten-Floor, KEIN Cap",
        "Management: F3-Bucket-Suppression (Phase,Dir) + Variante-B-Ratchet 1:1 "
        "(mindest_gewinn_r=0.0, notfall=300)",
        linie,
        "",
        f"ECHTER 2-CLOSE-BRUCH-PHASEN (Anker): {len([p for p in sr.phases if p.break_dir])}",
        f"Kandidaten (Kontakt-Bars gesamt): {len(kandidaten)}",
        "  Status-Verteilung: "
        + "  ".join(f"{s}={status_cnt.get(s, 0)}" for s in (
            "SIGNAL", "KEIN_ZONEN_KONTAKT", "KEINE_REJECTION_BESTAETIGUNG",
            "SLOPE_INVALIDE", "SL_UEBERSCHRITTEN", "DATEN_ENDE"))
        + f"   (Summe: {sum(status_cnt.values())})",
        f"  Zonen: ZONE_1_KANTE={zone_cnt.get('ZONE_1_KANTE', 0)}  "
        f"ZONE_2_EMA20={zone_cnt.get('ZONE_2_EMA20', 0)}",
        f"SIGNAL vor F3-Suppression: {n_signal_total}  "
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
        z_sum: float = 0.0
        for k, t in zensiert:
            z_sum += float(getattr(t, "r_ref"))
        txt.append("")
        txt.append(
            f"RECHTS_ZENSIERT (E2-Isolation, MtM zum letzten Close): "
            f"n={len(zensiert)}  sum r_ref(MtM) = {z_sum:+.2f}  "
            "(nicht in realisierter Statistik)"
        )
    txt.append("")
    txt.append(linie)
    txt.append("TRADE-DETAIL (realisiert, chronologisch):")
    txt.append(
        "  " + f"{'Nr':>3} {'Ph':>3} {'Dir':<5} {'Zone':<14} {'Kontakt':>7} "
        f"{'Rej':>4} {'EntryIdx':>8} {'Entry':>8} {'Stop':>8} {'ExitIdx':>7} "
        f"{'Exit':>8} {'Hold':>4} {'Grund':<20} {'r_f4':>7} {'kum':>8}"
    )
    kum: float = 0.0
    for i, (k, t) in enumerate(realisiert, start=1):
        kum += float(getattr(t, "r_f4"))
        txt.append(
            "  "
            + f"{i:>3} {k.phase:>3} {str(k.dir):<5} {str(k.zone):<14} "
            f"{k.kontakt_idx:>7} {k.rejection_idx:>4} {k.entry_idx:>8} "
            f"{k.entry_preis:>8.3f} {k.stop_level:>8.3f} "
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
                + f"Z{i:>2} {k.phase:>3} {str(k.dir):<5} {str(k.zone):<14} "
                f"{k.kontakt_idx:>7} {k.rejection_idx:>4} {k.entry_idx:>8} "
                f"{k.entry_preis:>8.3f} {k.stop_level:>8.3f} "
                f"{int(getattr(t, 'exit_idx')):>7} {float(getattr(t, 'exit_preis')):>8.3f} "
                f"{int(getattr(t, 'haltezeit_bars')):>4} "
                f"{str(getattr(t, 'exit_grund')):<20} {float(getattr(t, 'r_ref')):>+7.2f} "
                "(r_ref/MtM)"
            )
    txt.append(linie)
    return "\n".join(txt)


def _trades_tsv(
    trades: List[Tuple[PullbackKandidat, object]],
) -> str:
    """TSV-Block (aktivierte Trades inkl. RECHTS_ZENSIERT-Kennzeichnung)."""
    kopf: List[str] = [
        "# setup_c PULLBACK_REENTRY - Fenster: AUG",
        "# r_f4 = P&L / (entry - stop); r_ref = P&L / (entry * 0.45%)",
        "# zensiert=1: RECHTS_ZENSIERT am Datenende (r_ref = MtM, strikt isoliert)",
    ]
    header: str = (
        "nr\tphase\tdir\tzone\tbrk_idx\tkontakt_idx\trejection_idx\tentry_idx\t"
        "entry_ts\tentry_preis\tstop_level\tsl_usd\texit_idx\texit_ts\texit_preis\t"
        "exit_grund\thaltezeit_bars\tr_f4\tr_ref\tzensiert"
    )
    zeilen: List[str] = [*kopf, header]
    for i, (k, t) in enumerate(trades, start=1):
        zens: bool = str(getattr(t, "exit_grund")) == "RECHTS_ZENSIERT"
        zeilen.append(
            f"{i}\t{k.phase}\t{k.dir}\t{k.zone}\t{k.brk_idx}\t{k.kontakt_idx}\t"
            f"{k.rejection_idx}\t{k.entry_idx}\t{k.entry_ts}\t{k.entry_preis:.5f}\t"
            f"{k.stop_level:.5f}\t{k.sl_usd:.5f}\t{int(getattr(t, 'exit_idx'))}\t"
            f"{getattr(t, 'exit_ts')}\t{float(getattr(t, 'exit_preis')):.5f}\t"
            f"{getattr(t, 'exit_grund')}\t{int(getattr(t, 'haltezeit_bars'))}\t"
            f"{float(getattr(t, 'r_f4')):.5f}\t{float(getattr(t, 'r_ref')):.5f}\t"
            f"{1 if zens else 0}"
        )
    return "\n".join(zeilen)


# =============================================================================
# 5) CHART (300 dpi): Preis + EMA + Zonen-Marker + Trades + Equity
# =============================================================================


def _zeichne_pullback(
    cfg: PullbackConfig,
    df: pd.DataFrame,
    sr: SegmentResult,
    kandidaten: List[PullbackKandidat],
    trades: List[Tuple[PullbackKandidat, object]],
    out_png: Path,
    dpi: int,
) -> None:
    """Rendert Preis/EMA/Trades (oben) und kumulierte r_f4 (unten)."""
    realisiert: List[Tuple[PullbackKandidat, object]] = [
        (k, t) for k, t in trades
        if str(getattr(t, "exit_grund")) != "RECHTS_ZENSIERT"
    ]
    zensiert: List[Tuple[PullbackKandidat, object]] = [
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

    # Anker-Fenster + Bruchkanten-Schattierung (up gruen / down rot)
    for p in sr.phases:
        if p.break_dir is None or p.brk_idx is None or p.brk_kante is None:
            continue
        b: int = int(p.brk_idx)
        ax1.axvline(b, color=_COL_UP if p.break_dir == "up" else _COL_DOWN,
                    lw=0.5, ls=":", alpha=0.4, zorder=1)
        ax1.axhline(float(p.brk_kante), color=_COL_UP if p.break_dir == "up"
                    else _COL_DOWN, lw=0.5, alpha=0.35, zorder=1)

    # Kandidaten-Marker (SIGNAL-faehig: Zone am Kontaktpunkt)
    for k in kandidaten:
        if k.status != "SIGNAL" and k.status != "DATEN_ENDE":
            continue
        y_k: float = low[k.kontakt_idx] if k.dir == "up" else high[k.kontakt_idx]
        col_z: str = _COL_Z1 if k.zone == "ZONE_1_KANTE" else _COL_Z2
        ax1.scatter(k.kontakt_idx, y_k, marker="o", s=30, facecolor="none",
                    edgecolor=col_z, zorder=5)
    # Trades (realisiert): Entry + Exit
    for k, t in realisiert:
        col: str = _COL_UP if k.dir == "up" else _COL_DOWN
        ex_i: int = int(getattr(t, "exit_idx"))
        ax1.plot([k.entry_idx, ex_i], [k.entry_preis, float(getattr(t, "exit_preis"))],
                 color=col, lw=0.9, alpha=0.6, zorder=2)
        ax1.scatter(k.entry_idx, k.entry_preis, marker="^" if k.dir == "up" else "v",
                    s=65, color=col, edgecolor="w", linewidths=0.4, zorder=6)
        g: str = str(getattr(t, "exit_grund"))
        if g.startswith("TRAILING") or g.startswith("INITIAL"):
            ax1.scatter(ex_i, float(getattr(t, "exit_preis")), marker="s", s=40,
                        color=_COL_STOP, edgecolor="w", linewidths=0.4, zorder=6)
        else:
            ax1.scatter(ex_i, float(getattr(t, "exit_preis")), marker="x", s=40,
                        color=_COL_FLIP, zorder=6)
    for k, t in zensiert:
        col = _COL_UP if k.dir == "up" else _COL_DOWN
        ax1.scatter(k.entry_idx, k.entry_preis, marker="^" if k.dir == "up" else "v",
                    s=65, color=col, edgecolor="k", linewidths=0.7, zorder=6)

    step: int = max(16, n // 14)
    ticks: np.ndarray = np.arange(0, n, step)
    ax1.set_xticks(ticks)
    ax1.set_ylabel("USD")
    ax1.set_title(
        f"SETUP C | AUG | PULLBACK-RE-ENTRY (Z1 Kante={_COL_Z1}, Z2 EMA20) | "
        f"{FENSTER_DEFS['AUG'][0]} .. {FENSTER_DEFS['AUG'][1]} (ende-exkl.)"
    )
    ax1.grid(alpha=0.3)
    ax1.legend(loc="upper left", fontsize=8, framealpha=0.9, ncol=4)

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
            for k, t in zensiert:
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
        Line2D([0], [0], marker="o", color="w", markerfacecolor=_COL_Z1, ms=6,
               label="Zone 1 Kontakt"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=_COL_Z2, ms=6,
               label="Zone 2 Kontakt"),
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
# 6) RUNNER / MAIN
# =============================================================================


def run_pullback_test(fenster: str = "AUG", dpi: int = 300) -> str:
    """Fuehrt den PULLBACK-RE-ENTRY-Zwischentest (AUG) aus."""
    if fenster != "AUG":
        raise SystemExit(f"Scope strikt auf AUG begrenzt; ungueltig: {fenster}")
    start, ende = FENSTER_DEFS[fenster]
    seg_cfg: SegmentConfig = SegmentConfig(start=start, ende=ende)
    df: pd.DataFrame = load_data(seg_cfg.db_path, seg_cfg.start, seg_cfg.ende)
    sr: SegmentResult = segmentiere_markt(df, seg_cfg)
    cfg: PullbackConfig = PullbackConfig()

    kandidaten_all, meta = _erfasse_pullback_kandidaten(df, sr, cfg)
    trades, suppressed, n_signal_total = _simuliere_pullback(df, cfg, kandidaten_all)

    text: str = _bericht_text(cfg, df, sr, kandidaten_all, trades, suppressed,
                              n_signal_total)
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_txt: Path = _REPORT_DIR / f"setup_c_pullback_{fenster}.txt"
    out_txt.write_text(text, encoding="utf-8")
    out_tsv: Path = _REPORT_DIR / f"setup_c_pullback_trades_{fenster}.tsv"
    out_tsv.write_text(_trades_tsv(trades), encoding="utf-8")
    out_png: Path = _REPORT_DIR / f"setup_c_pullback_{fenster}.png"
    _zeichne_pullback(cfg, df, sr, kandidaten_all, trades, out_png, dpi)
    return text


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI-Einstieg: fuehrt den PULLBACK-RE-ENTRY-Zwischentest (AUG) aus."""
    args = list(sys.argv[1:] if argv is None else argv)
    fenster: str = "AUG"
    dpi: int = 300
    for a in args:
        if a.startswith("--fenster="):
            fenster = a.split("=", 1)[1].upper()
        elif a.startswith("--dpi="):
            dpi = int(a.split("=", 1)[1])
    text = run_pullback_test(fenster, dpi)
    print(text)
    print(
        f"\nReport: {_REPORT_DIR / f'setup_c_pullback_{fenster}.txt'}\n"
        f"TSV:    {_REPORT_DIR / f'setup_c_pullback_trades_{fenster}.tsv'}\n"
        f"PNG:    {_REPORT_DIR / f'setup_c_pullback_{fenster}.png'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
