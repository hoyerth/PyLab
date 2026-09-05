"""
REGIME-FILTER - Stufe-5-Modul (scripts/regime_filter.py)
========================================================
Isoliertes Modul zur Berechnung von Marktregime-Zustaenden
(``RegimeState``) pro abgeschlossener Konsolidierungsphase auf Basis
des arretierten Vertrags §2.16 des Lastenhefts
``docs/setup_c_experiment.md``.

ARCHITEKTUR (Doktrin §2.16-A)
-----------------------------
Drei-Schichten-Trennung:
  1. Zustands-Schaetzer  -> ``berechne_regime_metriken``
     (roher, typisierter Metrik-Vektor je Phase; regime=UNKLAR-Default)
  2. Entscheidungs-Gate  -> ``klassifiziere_regime`` + ``entscheide_gate``
     (Hysterese/Totzone; deklaratives Mapping auf Freigaben)
  3. Validierung         -> NICHT hier (OOS-Laeufe in test/, §2.16-B)

Modul-Isolation (§2.16-A.4): ``scripts/setup_c_profil.py`` bleibt byte-identisch
unberuehrt; Integration erst nach bestandenem Gate-Test als optionaler
Parameter (Default ``None`` = identischer Phase-1-Pfad).

KERN-PRINZIPIEN
---------------
- Einmalige Vektorisierung: ATR/EMA/EMA-Slope/ADX sind fortlaufende
  Zeitreihen ueber den GESAMTEN Dataframe (``berechne_zeitreihen_indikatoren``)
  und werden genau EINMAL berechnet. Ein Sweep (``RegimeSweepConfig``)
  laedt NIE Daten neu und berechnet NIE Indikatoren redundant; er wertet
  ausschliesslich die vorberechneten ``RegimeState``-Vektoren deklarativ aus.
- Kausalitaet (§2.16-A.5 + Formel-Spezifikation 05.09.2026): Strukturmetriken
  sind zum Zeitpunkt des Phasenendes (``p.brk_idx``) feststehend. Kanten
  werden ausschliesslich ueber die Stufenfunktion aus ``U_hist``/``L_hist``
  rekonstruiert (D4-Mechanik, ``np.searchsorted(..., side='right') - 1``) -
  NIE ueber die post-hoc finalen ``U_final``/``L_final`` (Regel-7-Finalize
  waere Lookahead ersten Grades).
- Randphasen (kein ``brk_idx``) werden NIE als Regime-Zustand gewertet
  (``rand_phasen``-Schalter; E2-konsistent).
- NaN-Doktrin: Jede am ``brk_idx`` nicht definierte Metrik ist NaN und fuehrt
  strikt in ``regime='UNKLAR'``, ``konfidenz=0.0`` (Kaltstart-Garantie).

KLASSIFIKATIONS-STATUS (wichtig fuer Review)
--------------------------------------------
``klassifiziere_regime`` implementiert eine TRANSPARENTE ARBEITSHYPOTHESE
(gewichtete additive Scores + Totzone, s. Funktions-Docstring). Die
arretierte Logik ist ausschliesslich das Gate-Mapping in ``entscheide_gate``
(§2.16-D). Die Schwellenwerte und die Gewichte sind NICHT arretiert; die
Gewichte sind als transparente Modul-Konstanten fixiert (Mentor-Beschluss
05.09.2026, kein Gewichte-Sweep), die Schwellen werden gemaess
Plateau-Doktrin (§2.16-A.1) im In-Sample-Sweep kalibriert.

Ueberarbeitung 05.09.2026 (Diagnose-Ergebnis, q_kompression-Totcode,
min()-Dominanz, Latch-Effekt):
- Ersatz der harten ``min()``-Aggregation durch gewichtete additive Scores.
- ``q_kompression`` (phase_spread_atr_ratio < 1.20) aus der Shake-Marge
  entfernt (Schwelle bei Medianen 4.6/9.2 unerreichbar).
- ``durchstoss_dichte`` aus der Shake-Marge entfernt (trennt S1/S2 nicht).
- ``konsolidierung_bars``-Semantik revidiert: LANGE Konsolidierung stuetzt
  TREND (Wyckoff-Akkumulation, S2-Median 139 vs. S1 69) - NICHT Shakeout.
- Null-Evidenz (beide Scores 0) -> strikt UNKLAR, kein Vorregime-Latch.
- Konfliktzone (beide Evidenzen aktiv, |s| < buffer) -> UNKLAR
  (Konten-Schutz, Mentor-Beschluss E-3).

V2-Bereinigung 05.09.2026 (Mentor-Beschluss, Occam's Razor nach
Sweep-Response): ``spread_atr_min`` und ``konsolidierung_min`` sind
ersatzlos aus dem TREND-Score entfernt. Beide Schwellen lagen im
gesamten sinnvollen Wertebereich zu ~95% im Saettigungsbereich
(S1/S2-Spread- und Konsolidierungs-Mindestgroessen) und zeigten im
1D-Sweep KEINE Response (Spanne < 1.0R in beiden Fenstern) - kein
Informationswert, nur papierene Komplexitaet. Die Roh-Metriken
``phase_spread_atr_ratio`` und ``konsolidierung_bars`` bleiben im
``RegimeState`` erhalten (NaN-Doktrin bzw. Kaltstart-Grenze
``kaltstart_min_bars``); nur ihre Schwellen-Scores entfallen.
Endgueltige Klassifikations-Formel (Gewichte summieren je Score auf 1.0):

  t = 0.65*S_oben(ema_slope, ema_slope_min, 0.20)
    + 0.35*S_oben(adx_val,   adx_schwelle_min, 20.0)
  k = 0.70*S_unten(ema_slope,     ema_slope_max,     0.20)
    + 0.30*S_oben(tol_band_quote, tol_band_quote_max, 0.50)

Kalibrierbar sind damit exakt 4 Schwellen (ema_slope_min, ema_slope_max,
adx_schwelle_min, tol_band_quote_max) ueber die 4 Spannen von
``RegimeSweepConfig``.

Datenherkunft: KEIN DuckDB-Zugriff in diesem Modul. ``df`` wird vom
Aufrufer geliefert (reiner Funktionskern, testbar).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import List, Literal, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from scripts.market_segmentation import PhaseData, SegmentResult

__all__ = [
    "RegimeName",
    "FensterName",
    "RandPhasenModus",
    "RegimeMetricConfig",
    "RegimeSweepConfig",
    "RegimeGateConfig",
    "RegimeSchwellen",
    "RegimeState",
    "RegimeGate",
    "berechne_zeitreihen_indikatoren",
    "berechne_regime_metriken",
    "klassifiziere_regime",
    "entscheide_gate",
]

# =============================================================================
# 1) TYP-ALIASE & DATENVERTRAEGE (verbatim §2.16-C + freigegebene Zusatzfelder)
# =============================================================================

RegimeName = Literal["TREND", "SHAKEOUT", "UNKLAR"]
FensterName = Literal["AUG", "S1", "S2"]
RandPhasenModus = Literal["ZENSIERT_UEBERGEHEN", "FEHLER"]


@dataclass(frozen=True, slots=True)
class RegimeMetricConfig:
    """Feste mathematische Lookbacks/Perioden der Regime-Messung (B primaer).

    Traegt ausschliesslich Berechnungs-Parameter. Schwellenwerte leben NICHT
    hier, sondern in RegimeSweepConfig (nicht-arretierte Sweep-Spannen).

    Freigegebene Zusatzfelder (Spec-Abgleich 05.09.2026):
    - ``tol``: 2-Close-Toleranz der tol_band_quote-Messung. MUSS mit
      ``SegmentConfig.tol`` der erzeugenden Segmentierung identisch sein
      (Default 0.34) - sonst misst die Fakeout-Quote ein anderes Band als
      die Ausbruchslogik der Baseline.
    - ``ema_slope_lookback``: Slope-Differenzfenster m (magische Zahl 5 ist
      damit eliminiert).
    """

    # Struktur-/Volatilitaetsmetriken (Option B - Primaer)
    konsolidierung_min_bars: int = 46  # Untergrenze (deckungsgleich MIN_PHASE_CANDLES)
    tol_band_messfenster_bars: int = 16  # TOLBAND-Quote-Fenster (F7-Semantik)
    atr_periode: int = 14  # ATR-Basis fuer Spread-Normalisierung
    durchstoss_fenster_bars: int = 46  # Dichte-Fenster
    tol: float = 0.34  # 2-Close-Toleranz (muss == SegmentConfig.tol sein)

    # Benchmark-Arm (Option A - vergleichend)
    ema_periode: int = 20
    adx_periode: int = 14
    ema_slope_lookback: int = 5  # Slope-Differenz ueber m Bars (m * ATR_k-Norm)


@dataclass(frozen=True, slots=True)
class RegimeSweepConfig:
    """Sweep-Spannen (min, max, step) fuer Response-Kurven (Plateau-Doktrin).

    Explizit KEINE arretierten Schwellen: Jede Schwelle wird ueber die volle
    Spanne gesweept; robust ist nur ein breites Plateau. Die Defaults sind
    Hypothesen-Startwerte aus der Quantil-Diagnose 05.09.2026 (ema_slope und
    adx trennen S1/S2; tol_band_quote stuetzt SHAKEOUT).

    Stand 05.09.2026 (V2-Bereinigung): Nur die 4 nachweislich responsiven
    Parameter werden gesweept. ``spread_atr`` und ``konsolidierung_bars``
    sind ersatzlos entfernt (keine 1D-Response im Sweep -> tote Schwellen).
    """

    ema_slope: Tuple[float, float, float] = (0.02, 0.12, 0.01)      # TREND-Momentum
    ema_slope_max: Tuple[float, float, float] = (-0.08, 0.02, 0.01)  # SHAKE-Kollaps
    adx_schwelle: Tuple[float, float, float] = (15.0, 35.0, 2.5)    # TREND-Staerke
    tol_band_quote: Tuple[float, float, float] = (0.40, 0.80, 0.05) # SHAKE-Stuetze


@dataclass(frozen=True, slots=True)
class RegimeGateConfig:
    """Hysterese- und Fallback-Parameter des Entscheidungs-Gates (Option C)."""

    hysterese_puffer: float = 0.05  # relative Hysterese um Regime-Grenze
    kaltstart_min_bars: int = 46  # unterhalb: immer UNKLAR (Kaltstart)
    fallback_horizont: int = 48  # UNKLAR/Kaltstart -> strikt N=48
    fallback_nur_raw_a: bool = True  # UNKLAR/Kaltstart -> nur RAW-Cluster A


@dataclass(frozen=True, slots=True)
class RegimeSchwellen:
    """VERSIEGELTE Schwellen (Freeze 05.09.2026, Plateau-Zentrum, nie Peak).

    ``RegimeSweepConfig`` traegt Spannen-Tupel (Generator-Spezifikation);
    ``RegimeSchwellen`` ist der konkret instanziierte, skalare Parameter-
    vektor EINES Sweep-Punkts. Ein Sweep iteriert ueber die Spannen,
    instantiiert je Kombination EIN Objekt und wertet alle vorberechneten
    ``RegimeState``-Vektoren identisch aus (Plateau-Doktrin).

    Die vier Zentren wurden ueber den In-Sample-Sweep (S1+S2, 1D-Response,
    Plateau-Doktrin §2.16-A.1) kalibriert und kryptografisch versiegelt
    (test/regime_schwellen_freezed.json + sha256 der S1/S2-Roh-Zustaende).
    Die Klassen-Defaults wurden am 05.09.2026 nachtraeglich auf die
    Siegel-Werte korrigiert (0.05->0.07, -0.02->-0.03): Zuvor standen hier
    die Vor-Freeze-Arbeitshypothesen, was gegenueber dem abgenommenen
    OOS-Portfolio (§2.16-F, +18,34R) stillen Model Drift erzeugt haette.
    Felder (Stand 05.09.2026, nach Diagnose UND V2-Bereinigung - nur die
    4 responsiven Schwellen):
      ema_slope_min       TREND: Momentum klar positiv (> Schwelle)
      ema_slope_max       SHAKE: Momentum-Kollaps (Wert <= Schwelle)
      adx_schwelle_min    TREND: Richtungsstaerke
      tol_band_quote_max  SHAKE: Fakeout-Stuetze (Quote > Schwelle)
    """

    ema_slope_min: float = 0.07            # VERSIEGELT 05.09.2026 (Plateau-Zentrum, nie Peak)
    ema_slope_max: float = -0.03           # VERSIEGELT 05.09.2026 (Plateau-Zentrum, nie Peak)
    adx_schwelle_min: float = 25.0         # TREND-Staerke
    tol_band_quote_max: float = 0.60       # SHAKE-Stuetze (vorher 0.50)


@dataclass(slots=True)
class RegimeState:
    """Vollstaendiger, typisierter Metrik-Vektor einer Phase.

    Kein untypisiertes Auffangbecken (details:str entfaellt ersatzlos). Alle
    Rohwerte werden typisiert gefuehrt, damit Sweeps deterministisch und ohne
    String-Parsing auswertbar sind. regime/konfidenz sind abgeleitete Felder
    mit defensivem Default (UNKLAR = Konto-Verteidigung).

    Kausalitaet: Der Vektor ist zum Zeitpunkt ``brk_idx`` (2-Close-Bruch der
    Phase) vollstaendig feststehend - kein Lookahead ueber die Phasengrenze,
    keine Referenz auf ``len(df)-1``.

    Attributes:
        phase_nr: 1-basierte Phasennummer NUR ueber Phasen mit echtem Bruch
            (deckungsgleich mit ``SetupCSignal.phase``/``KernelTrade.phase``
            aus ``setup_c_profil.py`` - Join-Schluessel).
        brk_idx: Bar-Index des 2-Close-Bruchs in ``df`` (Zeitanker).
    """

    phase_nr: int
    brk_idx: int
    phase_spread_usd: float  # U_brk - L_brk (kausal, USD)
    phase_spread_atr_ratio: float  # Spread / ATR[brk_idx] (dimensionslos)
    durchstoss_dichte: float  # Kanten-Kontakt-Bars / N (0..1, ohne Volumen)
    tol_band_quote: float  # Fakeout-Rate im 16-Bar-Fenster (0..1)
    konsolidierung_bars: int  # brk_idx - start_idx (Konsolidierungsdauer)

    # Benchmark-Arm (Option A - vergleichend)
    ema_slope: float  # (EMA_k - EMA_{k-m}) / (m * ATR_k), dimensionslos
    adx_val: float  # ADX(adx_periode), kausal

    # Abgeleitete Klassifikation (Default: defensiv)
    regime: RegimeName = "UNKLAR"
    konfidenz: float = 0.0  # 0..1, Abstand zur Regime-Grenze (Hysterese)


@dataclass(slots=True)
class RegimeGate:
    """Aus RegimeState abgeleitete Freigaben (Laufzeit-Objekt, nicht frozen).

    Mapping (arretierte Logik §2.13-C / §2.16-D):
      TREND    -> RAW-Cluster B + 1-Close freigegeben, Ziel-Horizont 96
      SHAKEOUT -> nur RAW-A, Ziel-Horizont 48
      UNKLAR (inkl. Kaltstart) -> strikt N=48 und nur RAW-A (Konto-Verteidigung)
    """

    phase_nr: int
    regime: RegimeName
    erlaube_raw_cluster_b: bool
    erlaube_one_close: bool
    ziel_horizont: int


# =============================================================================
# 2) EINMALIGE ZEITREIHEN-INDIKATOREN (vektorisiert, ueber den GESAMTEN df)
# =============================================================================


def _wilder_glaettung(werte: np.ndarray, n: int) -> np.ndarray:
    """Wilder-Glaettung als rekursives EMA (alpha=1/n), rein vektorisiert.

    Kausal (nutzt nur Vergangenheit). Hinweis: Die ersten ``n`` Werte sind
    Anlaufwerte (kein SMA-Seed, wie in der Wilder-Originaldefinition);
    fuer die Regime-Klassifikation zweitrangig (Schwellen werden gesweept).
    Aufrufer maskieren die Warmup-Zone separat mit NaN.

    Args:
        werte: Eindimensionales float-Array (NaN-frei).
        n: Glaettungsperiode (alpha = 1/n).

    Returns:
        Geglaettetes float-Array gleicher Laenge (beschreibbare Kopie).
    """
    return (
        pd.Series(werte)
        .ewm(alpha=1.0 / n, adjust=False)
        .mean()
        .to_numpy(copy=True)
    )


def berechne_zeitreihen_indikatoren(
    df: pd.DataFrame,
    cfg: RegimeMetricConfig,
) -> pd.DataFrame:
    """Berechnet ATR/EMA/EMA-Slope/ADX einmalig ueber den gesamten Frame.

    Rein vektorisiert (rolling/ewm/diff), keinerlei Schleifen. Alle Spalten
    sind strikt kausal: Wert an Bar ``k`` nutzt ausschliesslich Bars ``<= k``
    (kein centered rolling, kein shift(-n) mit negativem n). Der Frame wird
    defensiv kopiert, nicht mutiert.

    Spalten-Definitionen:
      atr:       SMA(TR, atr_periode), DV2-Semantik (min_periods=Periode)
      ema:       EMA(close, ema_periode), ewm(adjust=False)
      ema_slope: (EMA_k - EMA_{k-m}) / (m * ATR_k), m=ema_slope_lookback;
                 ATR-normalisiert (dimensionslos, ueber Preisniveaus
                 vergleichbar; NaN wenn ATR_k nicht endlich/<= 0).
      adx:       Wilder-ADX(adx_periode), kausal; Warmup-Zone (erste
                 ``adx_periode`` Bars) ist NaN.

    Args:
        df: OHLCV-Bars (Spalten ``ts/open/high/low/close/tick_volume/idx``,
            aufsteigend sortiert).
        cfg: RegimeMetricConfig (atr_periode, ema_periode,
            ema_slope_lookback, adx_periode).

    Returns:
        Defensive Kopie von ``df`` zusaetzlich mit float-Spalten ``atr``,
        ``ema``, ``ema_slope``, ``adx`` (NaN in der jeweiligen Warmup-Zone).
    """
    out: pd.DataFrame = df.copy()
    high: pd.Series = out["high"]
    low: pd.Series = out["low"]
    close: pd.Series = out["close"]

    # --- ATR (DV2: SMA des True Range, min_periods=Periode) ------------------
    prev_close: pd.Series = close.shift(1)
    tr: pd.Series = pd.Series(
        np.maximum(
            high - low,
            np.maximum(
                (high - prev_close).abs(), (low - prev_close).abs()
            ),
        ),
        index=df.index,
    )
    atr: pd.Series = tr.rolling(
        cfg.atr_periode, min_periods=cfg.atr_periode
    ).mean()

    # --- EMA ----------------------------------------------------------------
    ema: pd.Series = close.ewm(
        span=cfg.ema_periode, adjust=False, min_periods=cfg.ema_periode
    ).mean()

    # --- EMA-Slope (kausal, ATR-normalisiert) --------------------------------
    m: int = cfg.ema_slope_lookback
    slope: np.ndarray = (ema.diff(m) / (m * atr)).to_numpy(dtype=float)
    slope = np.where(np.isfinite(slope), slope, np.nan)

    # --- ADX (Wilder, kausal) ------------------------------------------------
    n_adx: int = cfg.adx_periode
    alpha: float = 1.0 / n_adx
    up_move: np.ndarray = high.diff().fillna(0.0).to_numpy(dtype=float)
    down_move: np.ndarray = (-low.diff()).fillna(0.0).to_numpy(dtype=float)
    plus_dm: np.ndarray = np.where(
        (up_move > down_move) & (up_move > 0.0), up_move, 0.0
    )
    minus_dm: np.ndarray = np.where(
        (down_move > up_move) & (down_move > 0.0), down_move, 0.0
    )
    tr_arr: np.ndarray = tr.fillna(0.0).to_numpy(dtype=float)
    atr_w: np.ndarray = _wilder_glaettung(tr_arr, n_adx)
    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di: np.ndarray = 100.0 * _wilder_glaettung(plus_dm, n_adx) / atr_w
        minus_di: np.ndarray = 100.0 * _wilder_glaettung(minus_dm, n_adx) / atr_w
        dx: np.ndarray = 100.0 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    dx = np.where(np.isfinite(dx), dx, 0.0)
    adx_arr: np.ndarray = _wilder_glaettung(dx, n_adx)
    adx_arr[:n_adx] = np.nan  # Warmup: Wilder-Anlauf nicht definiert
    adx: pd.Series = pd.Series(adx_arr, index=df.index)

    out["atr"] = atr
    out["ema"] = ema
    out["ema_slope"] = slope
    out["adx"] = adx
    return out


# =============================================================================
# 3) PHASEN-METRIKEN (Zustands-Schaetzer: kausal am brk_idx)
# =============================================================================


def _kanten_werte(
    ts_arr: np.ndarray, hist: Sequence[Tuple[pd.Timestamp, float]]
) -> np.ndarray:
    """Kausal gueltige Kante je Zeitstempel (D4-Stufenfunktion).

    Mechanik identisch zu ``_kanten_reihe`` in ``setup_c_profil.py``:
    ``np.searchsorted(hist_ts, ts, side='right') - 1``. Ein hist-Eintrag mit
    Zeitstempel <= Zielzeitpunkt ist bekannt; spaetere Eintraege sind es
    nicht. Existiert zum Zielzeitpunkt noch KEIN Eintrag, ist die Kante
    NaN (keine Kante - kein Kreuz-Fallback, D4).

    Args:
        ts_arr: datetime64-Array der Ziel-Zeitstempel (beliebige Einheit,
            wird intern auf ns normalisiert).
        hist: U_hist/L_hist der Phase [(ts, value), ...] - aufsteigend.

    Returns:
        float-Array der Kantenwerte je Zeitstempel (NaN wo unbekannt).
    """
    if not hist:
        return np.full(len(ts_arr), np.nan, dtype=float)
    # Einheiten-Falle: df["ts"].values kann datetime64[us] sein (DuckDB/
    # pandas >= 2.x), pd.Timestamp.value ist IMMER ns. Beide Seiten muessen
    # vor dem searchsorted auf ns normalisiert werden, sonst sind alle
    # Positionen -1 -> Kanten faelschlich NaN.
    hist_ts: np.ndarray = np.array([t.value for t, _ in hist], dtype="int64")
    hist_val: np.ndarray = np.array([v for _, v in hist], dtype=float)
    ts_ns: np.ndarray = (
        ts_arr.astype("datetime64[ns]").astype("int64")
    )
    pos: np.ndarray = (
        np.searchsorted(hist_ts, ts_ns, side="right") - 1
    )
    out: np.ndarray = np.where(
        pos >= 0, hist_val[np.clip(pos, 0, len(hist_val) - 1)], np.nan
    )
    return out.astype(float)


def _phase_start_idx(df: pd.DataFrame, p: PhaseData) -> int:
    """Positions-Index des Phasenstart-Zeitstempels in df.

    Args:
        df: OHLCV-DataFrame (ts aufsteigend sortiert).
        p: PhaseData.

    Returns:
        Zeilen-Index (positional) des Phasenbeginns.
    """
    return int(
        np.searchsorted(
            df["ts"].values, np.datetime64(p.start), side="left"
        )
    )


def _spread_usd_kausal(df: pd.DataFrame, p: PhaseData) -> float:
    """Kausaler Phasen-Spread U_brk - L_brk am brk_idx (Stufenfunktion).

    Args:
        df: OHLCV-DataFrame.
        p: PhaseData (echter Bruch vorausgesetzt).

    Returns:
        Spread in USD; NaN wenn eine Seite keine Kante hat (Ein-Kanten-
        Kompression) oder der Spread <= 0 ist (invertierte Kanten).
    """
    b: int = int(p.brk_idx)
    ts_brk: np.ndarray = df["ts"].values[b : b + 1]
    u_brk: float = float(_kanten_werte(ts_brk, p.U_hist)[0])
    l_brk: float = float(_kanten_werte(ts_brk, p.L_hist)[0])
    if not (np.isfinite(u_brk) and np.isfinite(l_brk)):
        return float("nan")
    spread: float = u_brk - l_brk
    return float(spread) if spread > 0.0 else float("nan")


def _durchstoss_dichte(df: pd.DataFrame, p: PhaseData, cfg: RegimeMetricConfig) -> float:
    """Kausale Kanten-Kontakt-Dichte ueber das N=46-Fenster (ohne Volumen).

    Zaehlt je Bar im inklusiven Fenster ``[brk_idx - N + 1, brk_idx]``
    (rechtsbuendig, N = durchstoss_fenster_bars), ob die Kante der up-
    oder down-Richtung beruehrt wurde (OR pro Bar, keine Doppelzaehlung):
    ``high_k >= K_up(ts_k)`` bzw. ``low_k <= K_lo(ts_k)``, nur wo die
    jeweilige Kante zu ``ts_k`` bereits existiert (sonst 0). Ergebnis = Anzahl
    Kontakt-Bars / N in [0, 1]. Bewusst OHNE Volumen-Bedingung (F5 lebt im
    Einstiegs-Arm; hier zaehlt die Adjazenz-/Antast-Frequenz).

    Args:
        df: OHLCV-DataFrame.
        p: PhaseData (echter Bruch vorausgesetzt).
        cfg: RegimeMetricConfig (durchstoss_fenster_bars).

    Returns:
        Dichte in [0, 1].
    """
    b: int = int(p.brk_idx)
    n_fenster: int = cfg.durchstoss_fenster_bars
    lo: int = max(0, b - n_fenster + 1)
    idxs: np.ndarray = np.arange(lo, b + 1)
    ts_w: np.ndarray = df["ts"].values[idxs]
    up_e: np.ndarray = _kanten_werte(ts_w, p.U_hist)
    lo_e: np.ndarray = _kanten_werte(ts_w, p.L_hist)
    high: np.ndarray = df["high"].values[idxs]
    low: np.ndarray = df["low"].values[idxs]
    up_fin: np.ndarray = np.isfinite(up_e)
    lo_fin: np.ndarray = np.isfinite(lo_e)
    kontakt: np.ndarray = np.zeros(len(idxs), dtype=bool)
    kontakt |= up_fin & (high >= up_e)
    kontakt |= lo_fin & (low <= lo_e)
    return float(int(kontakt.sum())) / float(n_fenster)


def _tol_band_quote(df: pd.DataFrame, p: PhaseData, cfg: RegimeMetricConfig) -> float:
    """Kausale Fakeout-Rate im 16-Bar-Fenster vor/bis brk_idx (§2.12-Semantik).

    Fenster ``W = [brk_idx - M + 1, brk_idx]``, M = tol_band_messfenster_bars.
    Versuch (Nenner) je Richtung und Bar mit endlicher Kante: up
    ``high_k >= K_up(ts_k)``, down ``low_k <= K_lo(ts_k)``. Die Bar
    ``brk_idx`` selbst zaehlt als Versuch, aber NIE als Fakeout (ihr Bruch ist
    per Definition echt; garantiert echter Nenner-Beitrag).

    Fakeout (Zaehler) fuer Versuche bei ``k <= brk_idx - 1``, up:
      close_k <= K_up(ts_k) + TOL            (Eigen-Close scheitert an TOL)
      ODER close_k > K_up(ts_k) + TOL UND close_{k+1} <= K_up(ts_k) + TOL
      (Eigen-Close bestaetigt, Folge-Close faellt zurueck - der 1-Close-
      Whipsaw aus §2.12, gemessen an der Kante von Bar k; k+1 <= brk_idx,
      also kausal legal am Gegenwarts-Bar).
    down gespiegelt (< K_lo - TOL bzw. Folge-Close >= K_lo(ts_k) - TOL).

    Nenner = 0 (ruhige Phase, kein Durchstich) -> Quote = 0.0 (Mentor-
    Entscheidung, kein NaN). Ergebnis in [0, 1].

    Args:
        df: OHLCV-DataFrame.
        p: PhaseData (echter Bruch vorausgesetzt).
        cfg: RegimeMetricConfig (tol_band_messfenster_bars, tol).

    Returns:
        Fakeout-Quote in [0, 1]; 0.0 bei leerem Nenner.
    """
    b: int = int(p.brk_idx)
    m_fenster: int = cfg.tol_band_messfenster_bars
    tol: float = cfg.tol
    lo: int = max(0, b - m_fenster + 1)
    idxs: np.ndarray = np.arange(lo, b + 1)
    ts_w: np.ndarray = df["ts"].values[idxs]
    up_e: np.ndarray = _kanten_werte(ts_w, p.U_hist)
    lo_e: np.ndarray = _kanten_werte(ts_w, p.L_hist)
    high: np.ndarray = df["high"].values[idxs]
    low: np.ndarray = df["low"].values[idxs]
    close: np.ndarray = df["close"].values[idxs]

    up_fin: np.ndarray = np.isfinite(up_e)
    lo_fin: np.ndarray = np.isfinite(lo_e)
    up_versuch: np.ndarray = up_fin & (high >= up_e)
    lo_versuch: np.ndarray = lo_fin & (low <= lo_e)
    n_versuche: int = int(up_versuch.sum()) + int(lo_versuch.sum())

    # Fakeout-Pruefung nur fuer k <= brk_idx-1 (letzte Fensterbar = brk_idx
    # wird nie auf einen Folge-Close geprueft: k+1 duerfte brk_idx+1 sein).
    c0: np.ndarray = close[:-1]
    c1: np.ndarray = close[1:]  # close_{k+1} <= close_{brk_idx}: kausal legal

    up_vor: np.ndarray = up_versuch[:-1]
    up_e_vor: np.ndarray = up_e[:-1]
    up_fake: np.ndarray = up_vor & (
        (c0 <= up_e_vor + tol)
        | ((c0 > up_e_vor + tol) & (c1 <= up_e_vor + tol))
    )

    lo_vor: np.ndarray = lo_versuch[:-1]
    lo_e_vor: np.ndarray = lo_e[:-1]
    lo_fake: np.ndarray = lo_vor & (
        (c0 >= lo_e_vor - tol)
        | ((c0 < lo_e_vor - tol) & (c1 >= lo_e_vor - tol))
    )

    n_fake: int = int(up_fake.sum()) + int(lo_fake.sum())
    if n_versuche <= 0:
        return 0.0
    return float(n_fake) / float(n_versuche)


def berechne_regime_metriken(
    df_indikatoren: pd.DataFrame,
    sr: SegmentResult,
    cfg: RegimeMetricConfig,
    rand_phasen: RandPhasenModus = "ZENSIERT_UEBERGEHEN",
) -> List[RegimeState]:
    """Extrahiert den kausalen Metrik-Vektor je Phase am Bruch-Zeitpunkt.

    Verarbeitet ausschliesslich Phasen mit echtem 2-Close-Bruch
    (``break_dir`` und ``brk_idx`` sind gesetzt). ``phase_nr`` zaehlt genau
    diese Phasen 1-basiert (deckungsgleich zu ``setup_c_profil._erfasse_signale``).
    Unvollendete Rand-Phasen (kein Bruch) werden gemaess ``rand_phasen``
    uebergangen (Default) oder loesen einen ValueError aus (``FEHLER``).

    Alle Metriken sind zum Zeitpunkt ``brk_idx`` kausal feststehend
    (Kanten aus ``U_hist``/``L_hist`` per Stufenfunktion, Indikator-Abgriff
    an Bar ``brk_idx``). Der Rueckgabe-``RegimeState`` traegt den
    Roh-Vektor mit defensivem Default ``regime='UNKLAR'``/``konfidenz=0.0``;
    die Klassifikation erfolgt separat in ``klassifiziere_regime``.

    Args:
        df_indikatoren: Ausgabe von ``berechne_zeitreihen_indikatoren``
            (OHLCV + Spalten atr/ema/ema_slope/adx).
        sr: SegmentResult aus ``market_segmentation.segmentiere_markt``.
        cfg: RegimeMetricConfig.
        rand_phasen: Verhalten bei unvollendeten Rand-Phasen.

    Returns:
        Chronologische ``RegimeState``-Liste (eine je echter Bruch-Phase).

    Raises:
        ValueError: Wenn ``rand_phasen == "FEHLER"`` und unvollendete
            Rand-Phasen existieren.
    """
    df: pd.DataFrame = df_indikatoren
    echte: List[PhaseData] = [
        p
        for p in sr.phases
        if p.break_dir is not None and p.brk_idx is not None
    ]
    rand: List[PhaseData] = [
        p
        for p in sr.phases
        if p.break_dir is None or p.brk_idx is None
    ]
    if rand and rand_phasen == "FEHLER":
        raise ValueError(
            f"Unvollendete Rand-Phasen im Analysefenster: {len(rand)} "
            "(kein brk_idx) - FEHLER-Modus aktiv."
        )

    states: List[RegimeState] = []
    for nr, p in enumerate(echte, start=1):
        b: int = int(p.brk_idx)
        start_idx: int = _phase_start_idx(df, p)
        konsolidierung_bars: int = b - start_idx

        spread_usd: float = _spread_usd_kausal(df, p)
        atr_b: float = float(df["atr"].iloc[b])
        if np.isfinite(spread_usd) and np.isfinite(atr_b) and atr_b > 0.0:
            spread_atr_ratio: float = spread_usd / atr_b
        else:
            spread_atr_ratio = float("nan")

        dichte: float = _durchstoss_dichte(df, p, cfg)
        quote: float = _tol_band_quote(df, p, cfg)
        ema_slope_b: float = float(df["ema_slope"].iloc[b])
        adx_b: float = float(df["adx"].iloc[b])

        states.append(
            RegimeState(
                phase_nr=nr,
                brk_idx=b,
                phase_spread_usd=spread_usd,
                phase_spread_atr_ratio=spread_atr_ratio,
                durchstoss_dichte=dichte,
                tol_band_quote=quote,
                konsolidierung_bars=konsolidierung_bars,
                ema_slope=ema_slope_b,
                adx_val=adx_b,
            )
        )
    return states


# =============================================================================
# 4) KLASSIFIKATION & ENTSCHEIDUNGS-GATE (Option C mit Hysterese/Totzone)
# =============================================================================

# Klassifikations-Gewichte (feste Modul-Konstanten, Mentor-Beschluss
# 05.09.2026 E-2 + V2: KEIN Gewichte-Sweep; nur Schwellen werden
# kalibriert). Je Score summieren die Gewichte auf 1.0 -> t/k in [0, 1].
# Stand V2-Bereinigung: spread_atr/konsolidierung ersatzlos entfernt,
# Gewichte auf die beiden echten Alpha-Treiber umverteilt (0.65/0.35).
_GEW_TREND_EMA_SLOPE: float = 0.65   # Momentum klar positiv (Hauptsignal)
_GEW_TREND_ADX: float = 0.35         # Richtungsstaerke
_GEW_SHAKE_EMA_SLOPE: float = 0.70   # Momentum-Kollaps (Hauptsignal)
_GEW_SHAKE_TOLBAND: float = 0.30     # Fakeout-Stuetze

# Numerische Null-Grenze (Evidenz == 0 gilt nur unterhalb EPS)
_EPS: float = 1e-9


def _clip01(x: float) -> float:
    """Klemmt einen Wert auf [0, 1].

    Args:
        x: Wert.

    Returns:
        Geklemmter Wert.
    """
    return float(min(1.0, max(0.0, x)))


def _score_oben(wert: float, schwelle: float, spanne: float) -> float:
    """S_oben: linearer Erfuellungsgrad oberhalb einer Schwelle.

    ``S_oben = clip01((wert - schwelle) / spanne)``. Wert bei/unter der
    Schwelle -> 0.0; Wert bei schwelle + spanne -> 1.0. Nicht endliche
    Werte oder spanne <= 0 -> 0.0 (kein Evidenz-Beitrag).

    Args:
        wert: Messwert.
        schwelle: Schwelle, ab der Evidenz beginnt.
        spanne: Normalisierungsspanne fuer die volle Evidenz (1.0).

    Returns:
        Score in [0, 1].
    """
    if not np.isfinite(wert) or spanne <= 0.0:
        return 0.0
    return _clip01((wert - schwelle) / spanne)


def _score_unten(wert: float, schwelle: float, spanne: float) -> float:
    """S_unten: linearer Erfuellungsgrad unterhalb einer Schwelle.

    ``S_unten = clip01((schwelle - wert) / spanne)``. Wert bei/ueber der
    Schwelle -> 0.0; Wert bei schwelle - spanne -> 1.0. Nicht endliche
    Werte oder spanne <= 0 -> 0.0 (kein Evidenz-Beitrag).

    Args:
        wert: Messwert.
        schwelle: Schwelle, ab der Evidenz beginnt.
        spanne: Normalisierungsspanne fuer die volle Evidenz (1.0).

    Returns:
        Score in [0, 1].
    """
    if not np.isfinite(wert) or spanne <= 0.0:
        return 0.0
    return _clip01((schwelle - wert) / spanne)


def _score_trend(st: RegimeState, schw: RegimeSchwellen) -> float:
    """Gewichtete additive TREND-Evidenz (V2-Bereinigung 05.09.2026).

    Formel (Gewichte -> Summe 1.0):
      t = 0.65*S_oben(ema_slope, ema_slope_min,   0.20)
        + 0.35*S_oben(adx_val,   adx_schwelle_min, 20.0)

    Gegenueber dem Diagnose-Zwischenstand (4 Terme) sind
    ``spread_atr_min`` und ``konsolidierung_min`` ersatzlos entfernt
    (Mentor-Beschluss V2): Beide Schwellen lagen im gesamten sinnvollen
    Wertebereich im Saettigungsbereich und zeigten im 1D-Sweep keine
    Response. Der Score stuetzt sich damit ausschliesslich auf die beiden
    nachweislich trennscharfen Alpha-Treiber (ema_slope-Gewicht 0.65 als
    Hauptsignal; adx 0.35 als Richtungsstaerke).

    Args:
        st: Kausal vollstaendiger RegimeState (endliche Rohwerte erwartet).
        schw: Skalare Schwellen des Sweep-Punkts.

    Returns:
        Trend-Score t in [0, 1].
    """
    return (
        _GEW_TREND_EMA_SLOPE
        * _score_oben(st.ema_slope, schw.ema_slope_min, 0.20)
        + _GEW_TREND_ADX
        * _score_oben(st.adx_val, schw.adx_schwelle_min, 20.0)
    )


def _score_shake(st: RegimeState, schw: RegimeSchwellen) -> float:
    """Gewichtete additive SHAKEOUT-Evidenz (Diagnose-Umbau 05.09.2026).

    Formel (Gewichte -> Summe 1.0):
      k = 0.70*S_unten(ema_slope,       ema_slope_max,     0.20)
        + 0.30*S_oben(tol_band_quote,   tol_band_quote_max, 0.50)

    Hauptsignal ist der Momentum-Kollaps (``ema_slope <= ema_slope_max``,
    Diagnose: trennt S1/S2 am staerksten); ``tol_band_quote`` stuetzt als
    Fakeout-Mass. ``q_kompression`` (spread_atr < 1.20) und
    ``durchstoss_dichte`` sind ersatzlos entfernt (Befund B, Totcode).

    Args:
        st: Kausal vollstaendiger RegimeState (endliche Rohwerte erwartet).
        schw: Skalare Schwellen des Sweep-Punkts.

    Returns:
        Shakeout-Score k in [0, 1].
    """
    return (
        _GEW_SHAKE_EMA_SLOPE
        * _score_unten(st.ema_slope, schw.ema_slope_max, 0.20)
        + _GEW_SHAKE_TOLBAND
        * _score_oben(st.tol_band_quote, schw.tol_band_quote_max, 0.50)
    )


def _metriken_endlich(st: RegimeState) -> bool:
    """Prueft, ob alle Roh-Metriken eines RegimeState endlich sind.

    Args:
        st: RegimeState.

    Returns:
        True wenn alle Metrik-Felder endlich (kein NaN/inf).
    """
    werte: Tuple[float, ...] = (
        st.phase_spread_usd,
        st.phase_spread_atr_ratio,
        st.durchstoss_dichte,
        st.tol_band_quote,
        st.ema_slope,
        st.adx_val,
    )
    return all(np.isfinite(float(w)) for w in werte)


def klassifiziere_regime(
    states: Sequence[RegimeState],
    schwellen: RegimeSchwellen,
    gate_cfg: RegimeGateConfig,
) -> List[RegimeState]:
    """Weist jedem RegimeState ein Regime zu (gewichtete Scores + Totzone).

    KLASSIFIKATIONS-REGEL (Arbeitshypothese nach Diagnose-Umbau 05.09.2026,
    NICHT arretiert; Kalibrierung ueber ``RegimeSweepConfig``-Spannen im
    In-Sample-Sweep, Plateau-Doktrin §2.16-A.1):

      1. Kaltstart/NaN (Garantie, §2.16-D): ``konsolidierung_bars <
         kaltstart_min_bars`` ODER irgendeine Roh-Metrik nicht endlich
         -> strikt ``UNKLAR``, ``konfidenz=0.0``.
      2. Evidenz-Scores (gewichtet additiv statt ``min()``, Summe der
         Gewichte = 1.0 -> t, k in [0, 1]):
           t = _score_trend(...)   (ema_slope/adx, V2-Bereinigung)
           k = _score_shake(...)   (ema_slope-Kollaps + tol_band_quote)
      3. Null-Evidenz: ``t <= EPS`` UND ``k <= EPS`` -> ``UNKLAR``
         (kein Vorregime-Latch; Mentor-Beschluss Q2).
      4. Entscheidung ueber ``s = t - k`` (Konten-Schutz: SHAKEOUT hat
         strukturell Vorrang, da k nur bei kollabiertem Momentum > 0):
           s >= +buffer            -> TREND    (konfidenz = t)
           s <= -buffer            -> SHAKEOUT (konfidenz = k)
           |s| < buffer: Konfliktzone, wenn t > EPS UND k > EPS -> UNKLAR
           (Mentor-Beschluss E-3: beide Evidenzen aktiv, keine Entscheidung
           -> Konto-Verteidigung, KEIN Halten).
           Sonst (nur EINE Evidenz positiv) Totzone-Halten NUR bei positiver
           Eigen-Evidenz des VORREGIMES (chronologische Reihenfolge):
           letztes == "TREND" und t > EPS    -> TREND    (konfidenz = t)
           letztes == "SHAKEOUT" und k > EPS -> SHAKEOUT (konfidenz = k)
           sonst                             -> UNKLAR.

    Die Schwellenwerte in ``schwellen`` sind Startwerte; die Regel ist
    bewusst einfach und deterministisch (keine diskontinuierlichen
    Wenn-Dann-Kaskaden), damit Sweeps glatte Response-Kurven erzeugen.

    Args:
        states: Chronologische RegimeState-Liste aus
            ``berechne_regime_metriken`` (Roh-Vektoren).
        schwellen: Skalare Schwellen EINES Sweep-Punkts.
        gate_cfg: RegimeGateConfig (hysterese_puffer, kaltstart_min_bars).

    Returns:
        Neue Liste mit befuellten Feldern ``regime``/``konfidenz``
        (Original-Objekte bleiben unveraendert).
    """
    buffer: float = max(0.0, gate_cfg.hysterese_puffer)
    letztes: RegimeName = "UNKLAR"
    ergebnis: List[RegimeState] = []

    for st in states:
        # --- Kaltstart/NaN-Garantie --------------------------------------
        if (
            st.konsolidierung_bars < gate_cfg.kaltstart_min_bars
            or not _metriken_endlich(st)
        ):
            neu: RegimeState = replace(st, regime="UNKLAR", konfidenz=0.0)
            letztes = "UNKLAR"
            ergebnis.append(neu)
            continue

        # --- Evidenz-Scores (gewichtet additiv, Diagnose-Umbau 05.09.2026) ---
        t: float = _score_trend(st, schwellen)
        k: float = _score_shake(st, schwellen)
        s: float = t - k

        regime: RegimeName
        konfidenz: float
        if t <= _EPS and k <= _EPS:
            # Null-Evidenz: kein Latch auf ein Vorregime
            regime, konfidenz = "UNKLAR", 0.0
        elif s >= buffer:
            regime, konfidenz = "TREND", _clip01(t)
        elif s <= -buffer:
            regime, konfidenz = "SHAKEOUT", _clip01(k)
        elif t > _EPS and k > _EPS:
            # Konfliktzone: beide Evidenzen aktiv, |s| < buffer
            # -> strikt UNKLAR (Konten-Schutz, Mentor-Beschluss E-3)
            regime, konfidenz = "UNKLAR", 0.0
        elif letztes == "TREND" and t > _EPS:
            # Totzone: Vorregime TREND halten (eigen-evident, kein Flattern)
            regime, konfidenz = "TREND", _clip01(t)
        elif letztes == "SHAKEOUT" and k > _EPS:
            # Totzone: Vorregime SHAKEOUT halten (eigen-evident)
            regime, konfidenz = "SHAKEOUT", _clip01(k)
        else:
            regime, konfidenz = "UNKLAR", 0.0
        letztes = regime
        ergebnis.append(replace(st, regime=regime, konfidenz=konfidenz))
    return ergebnis


def entscheide_gate(state: RegimeState, gate_cfg: RegimeGateConfig) -> RegimeGate:
    """Uebersetzt RegimeState deterministisch in Handelsfreigaben (§2.16-D).

    Arretiertes Mapping:
      TREND    -> RAW-Cluster B + 1-Close erlaubt, Ziel-Horizont 96
      SHAKEOUT -> nur RAW-A, Ziel-Horizont 48
      UNKLAR   -> nur RAW-A (``fallback_nur_raw_a``), Ziel-Horizont
                  ``fallback_horizont`` (Default 48)

    Args:
        state: Klassifizierter RegimeState.
        gate_cfg: RegimeGateConfig (fallback_horizont, fallback_nur_raw_a).

    Returns:
        RegimeGate (Freigaben fuer die Integration in setup_c_profil.py).
    """
    if state.regime == "TREND":
        return RegimeGate(
            phase_nr=state.phase_nr,
            regime="TREND",
            erlaube_raw_cluster_b=True,
            erlaube_one_close=True,
            ziel_horizont=96,
        )
    if state.regime == "SHAKEOUT":
        return RegimeGate(
            phase_nr=state.phase_nr,
            regime="SHAKEOUT",
            erlaube_raw_cluster_b=False,
            erlaube_one_close=False,
            ziel_horizont=48,
        )
    # UNKLAR (inkl. Kaltstart): Konto-Verteidigung, kein Experiment
    return RegimeGate(
        phase_nr=state.phase_nr,
        regime="UNKLAR",
        erlaube_raw_cluster_b=not gate_cfg.fallback_nur_raw_a,
        erlaube_one_close=False,
        ziel_horizont=gate_cfg.fallback_horizont,
    )
