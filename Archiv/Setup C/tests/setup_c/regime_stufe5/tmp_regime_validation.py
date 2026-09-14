"""
test/setup_c/regime_stufe5/tmp_regime_validation.py
=============================================================================
Stufe-5-Validierung scripts/regime_filter.py
Dreistufige Validierung des Regime-Filters gemaess §2.16 (Doktrin/OOS-Zonen)
und der arretierten Validierungs-Matrix (05.09.2026):

  --stufe=sweep   In-Sample-1D-Response-Kurven auf S1+S2 (Plateau-Doktrin).
                  Report: test/tmp_regime_sweep.txt
  --stufe=freeze  Versiegelt die Freeze-Kandidaten (Plateau-Zentrum, nie
                  Peak) aus dem Sweep-Artefakt in
                  test/regime_schwellen_freezed.json (+ sha256 der
                  Roh-Zustaende S1/S2 als forensische Haertung, S4).
  --stufe=oos     One-Shot-Blindtest: liest NUR das Freeze-JSON, oeffnet
                  die freigegebene Zone (--zone=stress; 2024 ist versiegelt,
                  §2.16-F.2). Report: test/tmp_regime_oos_stress.txt

ARRETIERTE RAHMENBEDINGUNGEN (vorab registriert, unveraenderlich)
------------------------------------------------------------------
- Portfolio-Konvention (E1, revidiert 05.09.2026 - Befund D): max. 1 Trade
  je (phase, dir), disjunkt. Der 1-Close-Pfad (oc96) ist ersatzlos ENTFERNT:
  Der S2-Mehrertrag der alten Logik ruhte fast vollstaendig auf dem
  ungefilterten 1-Close-Trade; der echte Hebel-Nachweis des Regime-Filters
  erfolgt ausschliesslich ueber den TREND-Pfad in OOS 2024.
  TREND    -> RAW-A @96 falls vorhanden (beide Richtungen unabhaengig),
              sonst (nur Bruchrichtung) RAW-B @96.
  SHAKEOUT -> strikt nur RAW-A @48 (Konto-Verteidigung, = B48).
  UNKLAR   -> strikt nur RAW-A @48 (fallback_horizont 48).
- Ungated-Baseline (E2): B48 = RAW-A @48, alle Phasen, beide Richtungen.
  Sekundaer: B96 = RAW-A @96 (statischer 96er-Lauf) wird mitgefuehrt.
- Klassifikations-Struktur (B1) und Gate-Mapping (B2, §2.16-D) sind fix;
  frei kalibrierbar sind ausschliesslich die 4 Skalarfelder von
  RegimeSchwellen (B3) ueber die Spannen von RegimeSweepConfig (B4).
  Stand V2-Bereinigung 05.09.2026: spread_atr_min und konsolidierung_min
  sind ersatzlos entfernt (keine 1D-Response -> tote Schwellen, Occam).
- RAW-B (S2): ausschliesslich in Bruchrichtung.
- In-Sample-Gueltigkeit je Sweep-Punkt (revidiert 05.09.2026, E-1):
  S1-Delta >= -0.5R UND S2-Delta >= -0.5R UND S2-Trend-Anteil > 50%.
  Der S2-Trend-Anteil ist der Anti-Total-Filter: In der Trend-Zone muss die
  Mehrheit der Phasen als TREND klassifiziert sein, sonst waere ein
  triviales Alles-UNKLAR-Plateau gueltig (Dauer-Sperre statt Hebel).
- Mindest-Response (revidiert 05.09.2026, Befund B/C): Ein Parameter mit
  Delta-Spanne < 1.0R in BEIDEN Fenstern ueber die volle Sweep-Spanne ist
  tot (flache Kurve != Plateau) und kann kein Plateau bestehen.
- Abschnitts-Definition (S3): chronologische Regime-Bloecke; UNKLAR bildet
  einen eigenen Abschnitt. Drawdown-Schranke: kumuliertes Netto-Delta
  (gated - B48) je Abschnitt >= -5.0R (OOS-Kriterium c).
- Integrity (S4): sha256 ueber die Roh-RegimeState-Vektoren S1/S2 im
  Freeze-JSON; die OOS-Stufe bricht bei Abweichung hart ab.

REINHEIT & HYGIENE
------------------
- DuckDB strikt read_only; keinerlei Schreibzugriff ausserhalb test/.
- scripts/setup_c_profil.py und scripts/regime_filter.py werden NUR
  importiert (Funktions-Importe), niemals modifiziert.
- Determinismus: keine Zufallsquellen, keine Systemzeit in Ergebnissen.
- ASCII-Konsole (cp1252-sicher); Dateien UTF-8.
- Aufruf: python test/setup_c/regime_stufe5/tmp_regime_validation.py --stufe=sweep
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


def _finde_projekt_root(datei: Path) -> Path:
    """Projekt-Wurzel = naechstes Verzeichnis mit ``.git`` (umzugsrobust).

    Der Report-/Testordner liegt inzwischen verschachtelt
    (``test/setup_c/regime_stufe5/``); eine feste ``parent.parent``-Kette
    wuerde danach auf ``test/setup_c`` zeigen und den DB-Pfad brechen.

    Args:
        datei: Pfad dieser Datei (``__file__``).

    Returns:
        Projekt-Wurzel (Verzeichnis mit ``.git``); Fallback = vier Ebenen
        ueber der Datei.
    """
    basis: Path = datei.resolve().parent
    for kandidat in (basis, *basis.parents):
        if (kandidat / ".git").exists():
            return kandidat
    return datei.resolve().parents[3]


_PROJEKT_ROOT: Path = _finde_projekt_root(Path(__file__))
if str(_PROJEKT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJEKT_ROOT))

import scripts.regime_filter as rf  # noqa: E402
import scripts.setup_c_profil as scp  # noqa: E402
from scripts.market_segmentation import (  # noqa: E402
    PhaseData,
    SegmentConfig,
    SegmentResult,
    load_data,
    segmentiere_markt,
)
from scripts.regime_filter import (  # noqa: E402
    RegimeGateConfig,
    RegimeMetricConfig,
    RegimeSchwellen,
    RegimeState,
)
from scripts.setup_c_profil import (  # noqa: E402
    KernelTrade,
    SetupCSignal,
    TrendConfig,
)

# ---------------------------------------------------------------------------
# 1) KONSTANTEN
# ---------------------------------------------------------------------------

_DB_PATH: Path = _PROJEKT_ROOT / "data" / "market_data.duckdb"
_REPORT_DIR: Path = Path(__file__).resolve().parent

# (start, ende) - ende exklusiv (load_data-Konvention, §2.16-B)
_WINDOWS: Dict[str, Tuple[str, str]] = {
    "S1": ("2026-02-05", "2026-08-28"),      # In-Sample: Shakeout
    "S2": ("2025-01-01", "2025-12-01"),      # In-Sample: Trend
    "Z2024": ("2024-01-01", "2024-12-31"),   # Makro-Holdout (abgenommen & versiegelt, §2.16-F; Lauf gesperrt)
    "ZSTRESS": ("2025-12-01", "2026-02-05"), # Stress-Holdout (arretiert)
}

# RegimeSchwellen-Feld -> RegimeSweepConfig-Feld (Sweep-Spanne)
# Stand 05.09.2026 (V2-Bereinigung): exakt 4 Felder, deckungsgleich mit den
# RegimeSchwellen/RegimeSweepConfig-Dataclasses in regime_filter.py.
# spread_atr_min/konsolidierung_min sind ersatzlos entfernt (tote Schwellen).
_PARAM_SWEEP: Dict[str, str] = {
    "ema_slope_min": "ema_slope",            # TREND-Momentum
    "ema_slope_max": "ema_slope_max",        # SHAKE-Kollaps
    "adx_schwelle_min": "adx_schwelle",      # TREND-Staerke
    "tol_band_quote_max": "tol_band_quote",  # SHAKE-Stuetze
}

# Bestehensgrenzen In-Sample (Plateau, revidiert 05.09.2026, E-1):
# S1 und S2 je >= -0.5R (Schutz; der S2-Mehrertrag ruhte vorher auf dem
# entfernten 1-Close-Traeger - der Hebel-Nachweis liegt in OOS 2024).
_GRENZE_S1: float = -0.5   # Schutz: gated nicht schlechter als B48
_GRENZE_S2: float = -0.5   # Toleranz (identische Schwelle, E-1 revidiert)
# Anti-Total-Filter: In der Trend-Zone S2 muss die Mehrheit der Phasen als
# TREND klassifiziert sein, sonst ist ein Alles-UNKLAR-Plateau trivial.
_TREND_ANTEIL_MIN_S2: float = 0.50  # Anteil TREND an allen S2-Phasen
# Mindest-Response (Befund B/C): flache Kurve in beiden Fenstern ist KEIN
# Plateau (toter Parameter); Spanne ueber die volle Sweep-Sweite.
_RESPONSE_MIN_R: float = 1.0

# Freeze-JSON-Name (versiegelt, von OOS gelesen)
_FREEZE_JSON: Path = _REPORT_DIR / "regime_schwellen_freezed.json"

# ---------------------------------------------------------------------------
# 2) TYPISIERTE DATENKLASSEN
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class FensterCache:
    """Einmalig je Window aufgebaute, schwellen-unabhaengige Basis.

    Alle Trades sind je (phase, dir) gecacht; die Klassifikation ist
    Sweep-abhaengig und wird NICHT hier gespeichert.
    """

    key: str
    n_phasen: int
    echte: List[PhaseData]                       # chronologisch, echte Brueche
    states_roh: List[RegimeState]                # unklassifiziert (regime=UNKLAR)
    a48: Dict[Tuple[int, str], KernelTrade]      # RAW-A @48, beide Richtungen
    a96: Dict[Tuple[int, str], KernelTrade]      # RAW-A @96, beide Richtungen
    b96: Dict[Tuple[int, str], KernelTrade]      # RAW-B @96, nur Bruchrichtung


@dataclass(frozen=True, slots=True)
class FensterAgg:
    """Aggregierte Kennzahlen EINES Sweep-Punkts fuer EIN Fenster."""

    delta_b48: float            # Primaer: sum_f4_gated - sum_f4_b48
    sum_f4_gated: float
    sum_ref_gated: float
    sum_f4_b48: float
    sum_ref_b48: float
    sum_f4_b96: float           # Sekundaer-Baseline (statischer 96er)
    n_gewertet_gated: int
    n_zensiert_gated: int
    n_init_gated: int
    n_zeit_gated: int
    hd_gated: float
    n_trend: int
    n_shakeout: int
    n_unklar: int


@dataclass(frozen=True, slots=True)
class PlateauBefund:
    """Ergebnis der Plateau-Pruefung fuer EINEN Parameter (S1 UND S2)."""

    param_name: str
    punkte: Tuple[float, ...]
    delta_s1: Tuple[float, ...]
    delta_s2: Tuple[float, ...]
    bestanden: bool
    freez_wert: Optional[float]
    seq_start: int               # Start-Index der gewaehlten Plateau-Sequenz
    seq_laenge: int              # Laenge der Sequenz (>= 3 bei Bestehen)
    grund: str                   # Befund-Text (Klippe/CoV/keine Sequenz)


# ---------------------------------------------------------------------------
# 3) HILFSFUNKTIONEN
# ---------------------------------------------------------------------------


def _sum_f4(trades: Sequence[KernelTrade]) -> float:
    """Summe r_f4 ueber Trades; RECHTS_ZENSIERT strikt isoliert (E2)."""
    s: float = 0.0
    for t in trades:
        if t.exit_grund != "RECHTS_ZENSIERT" and np.isfinite(t.r_f4):
            s += float(t.r_f4)
    return s


def _sum_ref(trades: Sequence[KernelTrade]) -> float:
    """Summe r_ref ueber Trades; RECHTS_ZENSIERT strikt isoliert (E2)."""
    s: float = 0.0
    for t in trades:
        if t.exit_grund != "RECHTS_ZENSIERT" and np.isfinite(t.r_ref):
            s += float(t.r_ref)
    return s


def _agg_merkmale(trades: Sequence[KernelTrade]) -> Tuple[int, int, int, int, float]:
    """(n_gewertet, n_zensiert, n_init, n_zeit, mittlere Haltedauer)."""
    n_zens: int = 0
    n_init: int = 0
    n_zeit: int = 0
    hd: List[int] = []
    for t in trades:
        if t.exit_grund == "RECHTS_ZENSIERT":
            n_zens += 1
        else:
            if t.exit_grund == "INITIAL_SL_INTRABAR":
                n_init += 1
            else:
                n_zeit += 1
            hd.append(t.haltezeit_bars)
    n_gew: int = len(hd)
    hd_mean: float = float(np.mean(hd)) if hd else float("nan")
    return n_gew, n_zens, n_init, n_zeit, hd_mean


def _spanne(tup: Tuple[float, float, float]) -> List[float]:
    """Erzeugt die Sweep-Punkte aus einem (min, max, step)-Tupel."""
    lo, hi, step = tup
    if isinstance(lo, int):
        return [float(x) for x in range(int(lo), int(hi) + 1, int(step))]
    n: int = int(round((hi - lo) / step)) + 1
    return [round(lo + i * step, 10) for i in range(n)]


def _states_hash(states: Sequence[RegimeState]) -> str:
    """sha256 ueber die kanonische Serialisierung der Roh-Zustaende (S4)."""
    h: "hashlib._Hash" = hashlib.sha256()
    for st in states:
        zeile: str = "|".join(
            [
                str(st.phase_nr),
                str(st.brk_idx),
                repr(st.phase_spread_usd),
                repr(st.phase_spread_atr_ratio),
                repr(st.durchstoss_dichte),
                repr(st.tol_band_quote),
                str(st.konsolidierung_bars),
                repr(st.ema_slope),
                repr(st.adx_val),
            ]
        )
        h.update(zeile.encode("utf-8"))
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 4) CACHE-AUFBAU (einmalig je Fenster)
# ---------------------------------------------------------------------------


def _baue_cache(key: str) -> FensterCache:
    """Laedt das Fenster und simuliert alle Pfade je Phase/Richtung einmalig.

    Rein lesend (DuckDB read_only). Verwendet ausschliesslich unveraenderte
    Funktionen aus scripts/setup_c_profil (Import) - kein Produktiv-Eingriff.
    """
    start, ende = _WINDOWS[key]
    cfg: TrendConfig = TrendConfig()
    seg_cfg: SegmentConfig = replace(
        cfg.segment, db_path=_DB_PATH, start=start, ende=ende
    )
    df: pd.DataFrame = load_data(seg_cfg.db_path, seg_cfg.start, seg_cfg.ende)
    sr: SegmentResult = segmentiere_markt(df, seg_cfg)

    # Zeitreihen-Indikatoren + Roh-Zustaende (regime_filter, kausal)
    df_ind: pd.DataFrame = rf.berechne_zeitreihen_indikatoren(
        df, RegimeMetricConfig()
    )
    echte: List[PhaseData] = [
        p
        for p in sr.phases
        if p.break_dir is not None and p.brk_idx is not None
    ]
    states_roh: List[RegimeState] = rf.berechne_regime_metriken(
        df_ind, sr, RegimeMetricConfig(), rand_phasen="ZENSIERT_UEBERGEHEN"
    )
    if len(states_roh) != len(echte):
        raise RuntimeError(
            f"{key}: states_roh ({len(states_roh)}) != echte Phasen "
            f"({len(echte)}) - Join-Schluessel inkonsistent."
        )

    # Signale (Phase-1-Kern) fuer RAW-A/B-Pfade
    signale: List[SetupCSignal] = scp._erfasse_signale(sr, cfg)

    # RAW-A @48 und @96 via _kern_lauefe (exakt Phase-1-Semantik, No-op-Suppr.)
    a48: Dict[Tuple[int, str], KernelTrade] = {}
    a96: Dict[Tuple[int, str], KernelTrade] = {}
    for h, ziel in ((48, a48), (96, a96)):
        trades, _n_supp = scp._kern_lauefe(df, signale, cfg, h)
        if _n_supp != 0:
            raise RuntimeError(f"{key}: RAW-A-Suppression nicht No-op ({_n_supp})")
        for t in trades:
            ziel[(int(t.phase), str(t.dir))] = t

    # RAW-B @96: nur Bruchrichtung, vorlauf > cluster_a_max_vorlauf (1)
    b96: Dict[Tuple[int, str], KernelTrade] = {}
    brk_dir: Dict[int, str] = {}
    for nr, p in enumerate(echte, start=1):
        assert p.break_dir is not None and p.brk_idx is not None
        brk_dir[nr] = str(p.break_dir)
    for sig in signale:
        if (
            sig.arm == "RAW"
            and sig.status == "SIGNAL"
            and sig.entry_idx >= 0
            and np.isfinite(sig.sl_usd)
            and sig.sl_usd > 0.0
            and sig.vorlauf_bars is not None
            and sig.vorlauf_bars > cfg.cluster_a_max_vorlauf
        ):
            nr = int(sig.phase)
            if str(sig.dir) != brk_dir.get(nr):
                continue
            if (nr, str(sig.dir)) in a48 or (nr, str(sig.dir)) in a96:
                continue  # Sicherheit: disjunkt (darf nicht auftreten)
            b96[(nr, str(sig.dir))] = scp._simuliere_kern(df, sig, cfg, 96)

    return FensterCache(
        key=key,
        n_phasen=len(echte),
        echte=echte,
        states_roh=states_roh,
        a48=a48,
        a96=a96,
        b96=b96,
    )


# ---------------------------------------------------------------------------
# 5) PORTFOLIO-ASSEMBLIERUNG (E1/E2: disjunkt, max. 1 Trade je (phase, dir))
# ---------------------------------------------------------------------------


def _gated_trades_fuer_phase(
    cache: FensterCache, nr: int, regime: str
) -> List[KernelTrade]:
    """Waehlt die gated-Trades EINER Phase gemaess Regime (E1)."""
    out: List[KernelTrade] = []
    if regime != "TREND":
        # SHAKEOUT/UNKLAR: strikt RAW-A @48 (= B48-Beitrag, Delta = 0)
        for d in ("up", "down"):
            t: Optional[KernelTrade] = cache.a48.get((nr, d))
            if t is not None:
                out.append(t)
        return out
    # TREND: RAW-A @96 (beide Richtungen); sonst B nur Bruchrichtung
    bdir: str = cache.echte[nr - 1].break_dir or "up"
    for d in ("up", "down"):
        t = cache.a96.get((nr, d))
        if t is None and d == bdir:
            t = cache.b96.get((nr, d))
        if t is not None:
            out.append(t)
    return out


def _klassifiziere(
    cache: FensterCache, schwellen: RegimeSchwellen, gate_cfg: RegimeGateConfig
) -> List[RegimeState]:
    """Klassifiziert die Roh-Zustaende eines Caches (Sweep-abhaengig)."""
    return rf.klassifiziere_regime(cache.states_roh, schwellen, gate_cfg)


def _berechne_punkt(cache: FensterCache, klass: Sequence[RegimeState]) -> FensterAgg:
    """Aggregiert gated/B48/B96 fuer einen klassifizierten Cache (E2)."""
    b48_trades: List[KernelTrade] = list(cache.a48.values())
    b96_trades: List[KernelTrade] = list(cache.a96.values())
    gated: List[KernelTrade] = []
    n_trend = n_shake = n_unklar = 0
    for nr, st in enumerate(klass, start=1):
        r: str = str(st.regime)
        if r == "TREND":
            n_trend += 1
        elif r == "SHAKEOUT":
            n_shake += 1
        else:
            n_unklar += 1
        gated.extend(_gated_trades_fuer_phase(cache, nr, r))
    n_gew, n_zens, n_init, n_zeit, hd = _agg_merkmale(gated)
    return FensterAgg(
        delta_b48=_sum_f4(gated) - _sum_f4(b48_trades),
        sum_f4_gated=_sum_f4(gated),
        sum_ref_gated=_sum_ref(gated),
        sum_f4_b48=_sum_f4(b48_trades),
        sum_ref_b48=_sum_ref(b48_trades),
        sum_f4_b96=_sum_f4(b96_trades),
        n_gewertet_gated=n_gew,
        n_zensiert_gated=n_zens,
        n_init_gated=n_init,
        n_zeit_gated=n_zeit,
        hd_gated=hd,
        n_trend=n_trend,
        n_shakeout=n_shake,
        n_unklar=n_unklar,
    )


# ---------------------------------------------------------------------------
# 6) PLATEAU-ALGORITHMUS (S1 UND S2 getrennt; gemeinsame Freeze-Sequenz)
# ---------------------------------------------------------------------------


def _laengste_seq(gueltig: Sequence[bool]) -> Tuple[int, int]:
    """Laengste zusammenhlaengende Sequenz von True. (start, laenge)."""
    best_start: int = -1
    best_len: int = 0
    i: int = 0
    g: List[bool] = list(gueltig)
    while i < len(g):
        if g[i]:
            j: int = i
            while j < len(g) and g[j]:
                j += 1
            if j - i > best_len:
                best_len = j - i
                best_start = i
            i = j
        else:
            i += 1
    return best_start, best_len


def _plateau_befund(
    param_name: str,
    punkte: Sequence[float],
    delta_s1: Sequence[float],
    delta_s2: Sequence[float],
    anteil_s2: Sequence[float],
) -> PlateauBefund:
    """Prueft das Plateau fuer einen Parameter (beide Fenster gemeinsam).

    Regeln (arretiert, revidiert 05.09.2026 E-1/B/C):
      - Response: Mindestens EIN Fenster muss ueber die volle Sweep-Spanne
        eine Delta-Spanne >= _RESPONSE_MIN_R aufweisen (flach = toter
        Parameter, kein Plateau).
      - gueltig je Punkt: S1 delta >= _GRENZE_S1 UND S2 delta >= _GRENZE_S2
        UND S2-Trend-Anteil > _TREND_ANTEIL_MIN_S2 (Anti-Total-Filter)
      - Sequenz: laengste zusammenhlaengende gueltige Sequenz, Laenge >= 3
      - Klippen-Regel: kein benachbarter Schritt in der Sequenz mit Abfall
        > 30 % des lokalen Niveaus (Floor 0.5R)
      - CoV-Regel je Fenster: (max-min)/|median| <= 0.5 ueber die Sequenz
      - Freeze = Plateau-Zentrum (mittlerer Punkt der Sequenz; bei gerader
        Laenge der linke der beiden mittleren = konservativ), NIE der Peak.
    """
    ds1: List[float] = list(delta_s1)
    ds2: List[float] = list(delta_s2)
    an2: List[float] = list(anteil_s2)
    pts: List[float] = list(punkte)
    n_p: int = len(pts)
    if len(an2) != n_p:
        raise ValueError("anteil_s2 muss je Sweep-Punkt vorliegen.")

    # --- Mindest-Response (Befund B/C: flache Kurve != Plateau) -----------
    resp_s1: float = max(ds1) - min(ds1)
    resp_s2: float = max(ds2) - min(ds2)
    if resp_s1 < _RESPONSE_MIN_R and resp_s2 < _RESPONSE_MIN_R:
        return PlateauBefund(
            param_name=param_name,
            punkte=tuple(pts),
            delta_s1=tuple(ds1),
            delta_s2=tuple(ds2),
            bestanden=False,
            freez_wert=None,
            seq_start=-1,
            seq_laenge=0,
            grund=(
                f"keine Response: Spanne S1 {resp_s1:.2f}R, S2 {resp_s2:.2f}R "
                f"< {_RESPONSE_MIN_R:.1f}R in beiden Fenstern (toter Parameter)"
            ),
        )

    gueltig: List[bool] = [
        (
            ds1[i] >= _GRENZE_S1
            and ds2[i] >= _GRENZE_S2
            and an2[i] > _TREND_ANTEIL_MIN_S2
        )
        for i in range(n_p)
    ]
    start, laenge = _laengste_seq(gueltig)
    if laenge < 3:
        return PlateauBefund(
            param_name=param_name,
            punkte=tuple(pts),
            delta_s1=tuple(ds1),
            delta_s2=tuple(ds2),
            bestanden=False,
            freez_wert=None,
            seq_start=start,
            seq_laenge=laenge,
            grund=f"keine gueltige Sequenz >= 3 (beste Sequenz: {laenge})",
        )
    # Klippen-Regel innerhalb der Sequenz (beide Fenster)
    for i in range(start, start + laenge - 1):
        for d in (ds1, ds2):
            abfall: float = d[i] - d[i + 1]
            boden: float = 0.5
            if abfall > 0.30 * max(abs(d[i]), abs(d[i + 1]), boden):
                return PlateauBefund(
                    param_name=param_name,
                    punkte=tuple(pts),
                    delta_s1=tuple(ds1),
                    delta_s2=tuple(ds2),
                    bestanden=False,
                    freez_wert=None,
                    seq_start=start,
                    seq_laenge=laenge,
                    grund=(
                        f"Klippen-Regel verletzt bei Index {i}->{i + 1} "
                        f"(Abfall {abfall:.2f}R)"
                    ),
                )
    # CoV-Regel je Fenster ueber die Sequenz
    for name, d in (("S1", ds1), ("S2", ds2)):
        seg: List[float] = d[start : start + laenge]
        med: float = float(np.median(seg))
        if med == 0.0:
            return PlateauBefund(
                param_name=param_name, punkte=tuple(pts),
                delta_s1=tuple(ds1), delta_s2=tuple(ds2),
                bestanden=False, freez_wert=None,
                seq_start=start, seq_laenge=laenge,
                grund=f"CoV nicht definiert (Median=0) in {name}",
            )
        cov: float = (max(seg) - min(seg)) / abs(med)
        if cov > 0.5:
            return PlateauBefund(
                param_name=param_name, punkte=tuple(pts),
                delta_s1=tuple(ds1), delta_s2=tuple(ds2),
                bestanden=False, freez_wert=None,
                seq_start=start, seq_laenge=laenge,
                grund=f"CoV {cov:.2f} > 0.5 in {name}",
            )
    freez_idx: int = start + (laenge - 1) // 2  # Plateau-Zentrum (konservativ)
    return PlateauBefund(
        param_name=param_name,
        punkte=tuple(pts),
        delta_s1=tuple(ds1),
        delta_s2=tuple(ds2),
        bestanden=True,
        freez_wert=float(pts[freez_idx]),
        seq_start=start,
        seq_laenge=laenge,
        grund=(
            f"Plateau OK: Sequenz [{start}..{start + laenge - 1}] "
            f"(n={laenge}), Freeze={pts[freez_idx]} (Plateau-Zentrum)"
        ),
    )


# ---------------------------------------------------------------------------
# 7) STUFE 1 - SWEEP
# ---------------------------------------------------------------------------


def _sweep_param(
    cache_s1: FensterCache,
    cache_s2: FensterCache,
    param: str,
    gate_cfg: RegimeGateConfig,
) -> PlateauBefund:
    """Fuehrt die 1D-Response-Kurve fuer EINEN Parameter aus."""
    sweep_feld: str = _PARAM_SWEEP[param]
    spanne: Tuple[float, float, float] = tuple(
        getattr(rf.RegimeSweepConfig(), sweep_feld)  # type: ignore[arg-type]
    )  # type: ignore[assignment]
    punkte: List[float] = _spanne(spanne)
    ds1: List[float] = []
    ds2: List[float] = []
    an2: List[float] = []  # S2-Trend-Anteil je Punkt (Anti-Total-Filter)
    for w in punkte:
        schw: RegimeSchwellen = replace(rf.RegimeSchwellen(), **{param: w})
        k1: List[RegimeState] = _klassifiziere(cache_s1, schw, gate_cfg)
        k2: List[RegimeState] = _klassifiziere(cache_s2, schw, gate_cfg)
        a1: FensterAgg = _berechne_punkt(cache_s1, k1)
        a2: FensterAgg = _berechne_punkt(cache_s2, k2)
        ds1.append(a1.delta_b48)
        ds2.append(a2.delta_b48)
        an2.append(float(a2.n_trend) / float(cache_s2.n_phasen))
    return _plateau_befund(param, punkte, ds1, ds2, an2)


def _stufe_sweep(fenster_liste: Sequence[str]) -> int:
    """--stufe=sweep: 1D-Response-Kurven + Plateau-Befunde (S1/S2)."""
    linie: str = "=" * 118
    gate_cfg: RegimeGateConfig = rf.RegimeGateConfig()
    caches: Dict[str, FensterCache] = {}
    for key in fenster_liste:
        caches[key] = _baue_cache(key)

    proto: List[str] = [
        linie,
        "STUFE-5-VALIDIERUNG: IN-SAMPLE-SWEEP (Plateau-Doktrin, 1D-Response)",
        "Quelle: scripts/regime_filter.py (V2, 4-Parameter: 0.65/0.35-"
        "Trendscore, 05.09.2026) | setup_c_profil.py (Commit 29e7d03, "
        "unveraendert)",
        f"Gate: {gate_cfg}",
        f"Gueltigkeit je Punkt: S1 >= {_GRENZE_S1}R | S2 >= {_GRENZE_S2}R | "
        f"S2-Trend-Anteil > {_TREND_ANTEIL_MIN_S2:.0%}",
        f"Response >= {_RESPONSE_MIN_R}R (mind. 1 Fenster) | Klippe > 30% | "
        "CoV <= 0.5 | Sequenz >= 3 | Freeze = Plateau-Zentrum",
        linie,
    ]
    # Verifikationsanker: B48/B96 muessen die Phase-1-L2 reproduzieren
    for key in fenster_liste:
        c: FensterCache = caches[key]
        proto.append(
            f"VERIFIKATION {key}: B48 sum_r_f4 = {_sum_f4(list(c.a48.values())):.2f} "
            f"(Phase-1 Soll S1=22.81/S2=0.31) | B96 = "
            f"{_sum_f4(list(c.a96.values())):.2f} (Soll S1=27.87/S2=0.98) | "
            f"Phasen {c.n_phasen} | A48-Trades {len(c.a48)} A96 {len(c.a96)} "
            f"B96 {len(c.b96)}"
        )

    ergebnisse: List[PlateauBefund] = []
    for param in _PARAM_SWEEP:
        bef: PlateauBefund = _sweep_param(caches["S1"], caches["S2"], param, gate_cfg)
        ergebnisse.append(bef)
        proto.append("")
        proto.append(linie)
        proto.append(f"PARAMETER: {param}  (Spanne "
                     f"{tuple(getattr(rf.RegimeSweepConfig(), _PARAM_SWEEP[param]))})")
        n2: int = caches["S2"].n_phasen
        proto.append(
            f"  {'idx':>3} {'wert':>10} | {'delta_S1':>8} {'delta_S2':>8} | "
            f"{'g_S1':>8} {'g_S2':>8} | {'T/S/U S1':>17} {'T/S/U S2':>17} | "
            f"{'trendS2':>7}"
        )
        # Aggregat je Punkt fuer die Tabelle (erneut, deterministisch)
        sweep_feld: str = _PARAM_SWEEP[param]
        spanne: Tuple = tuple(getattr(rf.RegimeSweepConfig(), sweep_feld))
        punkte: List[float] = _spanne(spanne)  # type: ignore[arg-type]
        for i, w in enumerate(punkte):
            schw = replace(rf.RegimeSchwellen(), **{param: w})
            k1 = _klassifiziere(caches["S1"], schw, gate_cfg)
            k2 = _klassifiziere(caches["S2"], schw, gate_cfg)
            a1: FensterAgg = _berechne_punkt(caches["S1"], k1)
            a2: FensterAgg = _berechne_punkt(caches["S2"], k2)
            an2: float = float(a2.n_trend) / float(n2)
            gueltig_punkt: bool = (
                a1.delta_b48 >= _GRENZE_S1
                and a2.delta_b48 >= _GRENZE_S2
                and an2 > _TREND_ANTEIL_MIN_S2
            )
            mark: str = "  "
            if (
                bef.bestanden
                and bef.seq_start <= i < bef.seq_start + bef.seq_laenge
            ):
                mark = " *"
            elif gueltig_punkt:
                mark = " ."
            ts1: str = f"{a1.n_trend}/{a1.n_shakeout}/{a1.n_unklar}"
            ts2: str = f"{a2.n_trend}/{a2.n_shakeout}/{a2.n_unklar}"
            proto.append(
                f"{i:>3} {w:>10.4f} | {a1.delta_b48:>+8.2f} {a2.delta_b48:>+8.2f} | "
                f"{a1.sum_f4_gated:>8.2f} {a2.sum_f4_gated:>8.2f} | "
                f"{ts1:>17} {ts2:>17} | {100.0 * an2:>6.1f}%{mark}"
            )
        proto.append(f"  BEFUND: {'BESTANDEN' if bef.bestanden else 'NICHT BESTANDEN'} "
                     f"| {bef.grund}")
        if bef.freez_wert is not None:
            proto.append(f"  FREEZE-KANDIDAT: {bef.freez_wert:.6f}")

    proto.append("")
    proto.append(linie)
    proto.append("ZUSAMMENFASSUNG FREEZE-KANDIDATEN (je Parameter):")
    for bef in ergebnisse:
        status: str = f"{bef.freez_wert:.6f}" if bef.freez_wert is not None else "---"
        proto.append(f"  {bef.param_name:<26} bestanden={str(bef.bestanden):<5} "
                     f"freeze={status}")

    # Zwischen-Artefakt fuer --stufe=freeze (nur bestandene Kandidaten)
    freez_map: Dict[str, Optional[float]] = {
        b.param_name: b.freez_wert for b in ergebnisse
    }
    artefakt: Path = _REPORT_DIR / "tmp_regime_sweep_freez_kandidaten.json"
    artefakt.write_text(
        json.dumps(
            {
                "version": 1,
                "bestanden": {b.param_name: b.bestanden for b in ergebnisse},
                "freez_kandidaten": freez_map,
                "grund": {b.param_name: b.grund for b in ergebnisse},
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    text: str = "\n".join(proto)
    ausgabe: Path = _REPORT_DIR / "tmp_regime_sweep.txt"
    ausgabe.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"\nProtokoll: {ausgabe}")
    print(f"Freeze-Zwischenstand: {artefakt}")
    return 0


# ---------------------------------------------------------------------------
# 8) STUFE 2 - FREEZE (Versiegelung)
# ---------------------------------------------------------------------------


def _stufe_freeze() -> int:
    """--stufe=freeze: konsolidiert und versiegelt die Freeze-Kandidaten.

    Liest das Sweep-Zwischenartefakt; nur Parameter mit bestandenem Plateau
    gehen in das Siegel-JSON. Fehlt ein Parameter, wird KEIN Siegel erzeugt
    (blockiert die OOS-Stufe konstruktiv).
    """
    artefakt: Path = _REPORT_DIR / "tmp_regime_sweep_freez_kandidaten.json"
    if not artefakt.exists():
        print("FEHLER: Sweep-Zwischenstand fehlt - zuerst --stufe=sweep ausfuehren.")
        return 1
    daten: Dict = json.loads(artefakt.read_text(encoding="utf-8"))
    bestanden: Dict[str, bool] = daten["bestanden"]
    kandidaten: Dict[str, Optional[float]] = daten["freez_kandidaten"]
    if not all(bestanden.values()):
        print("FEHLER: Nicht alle Parameter haben ein Plateau bestanden:")
        for p, ok in bestanden.items():
            if not ok:
                print(f"  {p}: {daten['grund'][p]}")
        print("Kein Siegel erzeugt (One-Shot-Haertung).")
        return 1

    # Roh-Zustaende S1/S2 neu aufbauen (fuer den forensischen Hash, S4)
    gate_cfg: RegimeGateConfig = rf.RegimeGateConfig()
    c1: FensterCache = _baue_cache("S1")
    c2: FensterCache = _baue_cache("S2")
    h1: str = _states_hash(c1.states_roh)
    h2: str = _states_hash(c2.states_roh)

    schwellen_werte: Dict[str, float] = {
        p: float(v) for p, v in kandidaten.items() if v is not None
    }
    if len(schwellen_werte) != len(_PARAM_SWEEP):
        print("FEHLER: Unvollstaendige Schwellen-Menge.")
        return 1
    # Konsistenz: aus den Werten muss ein RegimeSchwellen-Objekt baubar sein
    test_obj: RegimeSchwellen = replace(rf.RegimeSchwellen(), **schwellen_werte)
    json_inhalt: Dict = {
        "version": 1,
        "datum": "2026-09-05",
        "quelle_fenster": ["S1", "S2"],
        "regel": (
            "Plateau-Zentrum (konservativster Punkt, nie Peak); "
            "Sequenz >= 3; +/-10%-Umgebung abgedeckt durch Grid-Schritte; "
            "Klippen-Regel >30% verboten; CoV <= 0.5 je Fenster; "
            "Response >= 1.0R in mind. einem Fenster; "
            "S1 >= -0.5R und S2 >= -0.5R und S2-Trend-Anteil > 50% je Punkt; "
            "beide Fenster separat; V2-Bereinigung: 4 Parameter "
            "(revidiert 05.09.2026, E-1/B/C)"
        ),
        "schwellen": schwellen_werte,
        "historie_defaults": {
            f: float(getattr(rf.RegimeSchwellen(), f))
            for f in _PARAM_SWEEP
        },
        "metrik_config": {
            f: float(getattr(rf.RegimeMetricConfig(), f))
            for f in (
                "tol",
                "ema_slope_lookback",
                "atr_periode",
                "ema_periode",
                "adx_periode",
                "tol_band_messfenster_bars",
                "durchstoss_fenster_bars",
                "konsolidierung_min_bars",
            )
        },
        "gate_config": {
            "hysterese_puffer": gate_cfg.hysterese_puffer,
            "kaltstart_min_bars": gate_cfg.kaltstart_min_bars,
            "fallback_horizont": gate_cfg.fallback_horizont,
            "fallback_nur_raw_a": gate_cfg.fallback_nur_raw_a,
        },
        "sha256_states_s1": h1,
        "sha256_states_s2": h2,
        "schwellen_obj_repr": repr(test_obj),
    }
    _FREEZE_JSON.write_text(
        json.dumps(json_inhalt, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    menschen: Path = _REPORT_DIR / "tmp_regime_freezed.txt"
    zeilen: List[str] = [
        "REGIME-SCHWELLEN - VERSIEGELT (Freeze, Plateau-Zentrum)",
        f"Datei: {_FREEZE_JSON.name}",
        f"sha256_states_s1: {h1}",
        f"sha256_states_s2: {h2}",
        "",
    ]
    for p, w in schwellen_werte.items():
        zeilen.append(f"  {p:<26} = {w:.6f}")
    menschen.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    print("\n".join(zeilen))
    print(f"\nSiegel geschrieben: {_FREEZE_JSON}")
    print(f"Uebersicht: {menschen}")
    return 0


# ---------------------------------------------------------------------------
# 9) STUFE 3 - OOS (One-Shot, sequenziell; liest NUR das Siegel-JSON)
# ---------------------------------------------------------------------------


def _abschnitte(
    cache: FensterCache, klass: Sequence[RegimeState]
) -> List[Tuple[str, int, int, float, float, float]]:
    """Zusammenhlaengende Regime-Abschnitte mit kumuliertem Netto-Delta.

    Rueckgabe je Abschnitt:
      (regime, phasen_von, phasen_bis, sum_f4_gated, sum_f4_b48,
       delta_kumuliert)
    UNKLAR bildet einen eigenen Abschnitt (S3).
    """
    if not klass:
        return []
    out: List[Tuple[str, int, int, float, float, float]] = []
    akt_regime: str = str(klass[0].regime)
    akt_start: int = 1
    g_sum: float = 0.0
    b_sum: float = 0.0
    for nr, st in enumerate(klass, start=1):
        r: str = str(st.regime)
        gt: List[KernelTrade] = _gated_trades_fuer_phase(cache, nr, r)
        bt: List[KernelTrade] = [
            t for d in ("up", "down") if (t := cache.a48.get((nr, d))) is not None
        ]
        g_phase: float = _sum_f4(gt)
        b_phase: float = _sum_f4(bt)
        if r == akt_regime:
            g_sum += g_phase
            b_sum += b_phase
            continue
        out.append((akt_regime, akt_start, nr - 1, g_sum, b_sum, g_sum - b_sum))
        akt_regime = r
        akt_start = nr
        g_sum = g_phase
        b_sum = b_phase
    out.append((akt_regime, akt_start, len(klass), g_sum, b_sum, g_sum - b_sum))
    return out


def _stufe_oos(zone: str) -> int:
    """--stufe=oos: One-Shot-Blindtest auf genau einer Zone.

    Bestehenskriterien (arretiert, duale Ausweisung):
      Fassung 1 (Audit-Historie; fuer Zone 2024 versiegelt, §2.16-F.2):
        (a) SHAKEOUT/UNKLAR-Abschnitte: Delta = gated - B48 >= -0.5R
        (b) TREND-Abschnitte: Delta > 0.0R (je Block)
        (c) Drawdown-Schranke: kumuliertes Netto-Delta je Abschnitt >= -5.0R
      Fassung 2 (bindend ab ZSTRESS, §2.16-F.4):
        (a) unveraendert
        (b') Sigma-Delta-TREND >= 0.0R (Roh-Float-Summe ueber TREND-Bloecke;
             == Primaer-Delta wegen No-Harm-Identitaet; bei 0 TREND-Bloecken
             vakuum-erfuellt)
        (c) unveraendert
    """
    if zone == "2024":
        raise ValueError(
            "Zone 2024 ist verbraucht und versiegelt (§2.16-F.2). "
            "Ein erneuter Lauf wuerde das historische Audit-Artefakt "
            "(test/tmp_regime_oos_2024.txt) ueberschreiben."
        )
    if zone != "stress":
        print("FEHLER: --zone muss 'stress' sein (2024 versiegelt).")
        return 1
    if not _FREEZE_JSON.exists():
        print("FEHLER: Kein Siegel-JSON - zuerst --stufe=freeze ausfuehren "
              "(One-Shot-Haertung).")
        return 1
    siegel: Dict = json.loads(_FREEZE_JSON.read_text(encoding="utf-8"))
    schwellen_map: Dict[str, float] = siegel["schwellen"]
    schw: RegimeSchwellen = replace(rf.RegimeSchwellen(), **schwellen_map)
    gate_cfg: RegimeGateConfig = rf.RegimeGateConfig(
        hysterese_puffer=float(siegel["gate_config"]["hysterese_puffer"]),
        kaltstart_min_bars=int(siegel["gate_config"]["kaltstart_min_bars"]),
        fallback_horizont=int(siegel["gate_config"]["fallback_horizont"]),
        fallback_nur_raw_a=bool(siegel["gate_config"]["fallback_nur_raw_a"]),
    )

    # Einzige freigegebene OOS-Zone ist ZSTRESS (2024 durch ValueError oben
    # versiegelt); _WINDOWS["Z2024"] bleibt als inerte Doku des abgenommenen
    # Makro-Holdouts (One-Shot verbraucht, kein erneuter Lauf moeglich).
    key: str = "ZSTRESS"
    cache: FensterCache = _baue_cache(key)
    # Forensische Hash-Pruefung ist nur fuer S1/S2 definiert (Siegel-Bezug);
    # die OOS-Zone hat keinen Soll-Hash - die Roh-Zustaende der Zone werden
    # im Report dokumentiert (kein Kalibrier-Pfad existiert).
    h_zone: str = _states_hash(cache.states_roh)
    klass: List[RegimeState] = _klassifiziere(cache, schw, gate_cfg)
    agg: FensterAgg = _berechne_punkt(cache, klass)
    abschnitte: List[Tuple[str, int, int, float, float, float]] = _abschnitte(
        cache, klass
    )

    linie: str = "=" * 118
    proto: List[str] = [
        linie,
        f"STUFE-5-OOS: ONE-SHOT-BLINDTEST ZONE {key} "
        f"({_WINDOWS[key][0]} .. {_WINDOWS[key][1]}, ende-exklusiv)",
        f"Siegel-Hash S1: {siegel.get('sha256_states_s1', '-')[:16]}...",
        f"Siegel-Hash S2: {siegel.get('sha256_states_s2', '-')[:16]}...",
        f"Zonen-Hash     : {h_zone[:16]}... (nur Doku, kein Soll)",
        f"Freeze-Schwellen: {schwellen_map}",
        f"Klassifikation : TREND {agg.n_trend} | SHAKEOUT {agg.n_shakeout} | "
        f"UNKLAR {agg.n_unklar} (von {cache.n_phasen} Phasen)",
        f"Gated: sum_f4={agg.sum_f4_gated:.2f} sum_ref={agg.sum_ref_gated:.2f} "
        f"(n_gewertet={agg.n_gewertet_gated}, zensiert={agg.n_zensiert_gated}, "
        f"init={agg.n_init_gated}, zeit={agg.n_zeit_gated}, hd={agg.hd_gated:.0f})",
        f"B48  : sum_f4={agg.sum_f4_b48:.2f} sum_ref={agg.sum_ref_b48:.2f}",
        f"B96  : sum_f4={agg.sum_f4_b96:.2f} (Sekundaer-Baseline)",
        f"PRIMAER-DELTA (gated - B48): {agg.delta_b48:+.2f}R",
        linie,
        "",
        "ABSCHNITTE (chronologisch, UNKLAR eigenstaendig):",
        f"  {'Regime':<10} {'Phasen':>10} | {'sum_f4_gated':>12} "
        f"{'sum_f4_b48':>10} {'delta':>8} | Befund (Fassung 1)",
    ]
    kriterien: Dict[str, bool] = {"a": True, "b": True, "c": True}
    for regime, von, bis, gs, bs, dk in abschnitte:
        befund: str = ""
        if regime in ("SHAKEOUT", "UNKLAR"):
            ok: bool = dk >= -0.5
            kriterien["a"] = kriterien["a"] and ok
            befund = "OK" if ok else "VERLETZT (a): delta < -0.5R"
        elif regime == "TREND":
            ok = dk > 0.0
            kriterien["b"] = kriterien["b"] and ok
            befund = "OK" if ok else "VERLETZT (b): delta <= 0"
        if dk < -5.0:
            kriterien["c"] = False
            befund += " | VERLETZT (c): delta < -5.0R"
        if not befund:
            befund = "OK"
        proto.append(
            f"  {regime:<10} {von:>4}-{bis:<4} | {gs:>12.2f} {bs:>10.2f} "
            f"{dk:>+8.2f} | {befund}"
        )
    # --- Duale Auswertung: Fassung 1 (Audit) vs. Fassung 2 (bindend) ------
    # Sigma-Delta-TREND aus Roh-Floats (b[5] = delta_kumuliert je Block).
    # Da SHAKEOUT/UNKLAR-Bloecke konstruktionsbedingt Delta = 0.00 beitragen
    # (No-Harm-Identitaet, §2.16-F.2), muss Sigma exakt dem Primaer-Delta
    # entsprechen - der Check faengt Rundungsfehler/Lecks mathematisch ab.
    trend_bloecke: List[Tuple[str, int, int, float, float, float]] = [
        b for b in abschnitte if b[0] == "TREND"
    ]
    sigma_trend_roh: float = sum(b[5] for b in trend_bloecke)
    id_ok: bool = abs(sigma_trend_roh - float(agg.delta_b48)) < 1e-6
    # Fassung 1: (a) UND (b) UND (c) - je Block (historischer Massstab)
    urteil_f1: bool = bool(kriterien["a"] and kriterien["b"] and kriterien["c"])
    # Fassung 2: (a) UND (b') UND (c) - zonen-kumulativ (bindend ab ZSTRESS)
    b2_ok: bool = sigma_trend_roh >= 0.0
    urteil_f2: bool = bool(kriterien["a"] and b2_ok and kriterien["c"])

    proto.append("")
    proto.append("HINWEIS (a): No-Harm-Identitaet - in SHAKEOUT/UNKLAR waehlt")
    proto.append("das Gate exakt die B48-Baseline (Delta = 0.00 je Block,")
    proto.append("konstruktionsbedingt, §2.16-F.2).")
    proto.append("FASSUNG-2-SUMMARY (bindend ab ZSTRESS, §2.16-F.4):")
    proto.append(
        f"  TREND-Bloecke: {len(trend_bloecke)} | "
        f"Sigma-Delta-TREND (roh): {sigma_trend_roh:+.2f}R | "
        f"Primaer-Delta: {agg.delta_b48:+.2f}R | "
        f"Identitaets-Check |diff|<1e-6: {id_ok}"
    )
    proto.append(f"URTEIL FASSUNG 1 (Audit-Historie): a={kriterien['a']} "
                 f"b={kriterien['b']} c={kriterien['c']} -> "
                 f"{'BESTANDEN' if urteil_f1 else 'NICHT BESTANDEN'}")
    proto.append(f"GESAMTURTEIL FASSUNG 2 (Bindend ab ZSTRESS): "
                 f"a={kriterien['a']} b'={b2_ok} c={kriterien['c']} -> "
                 f"{'BESTANDEN' if urteil_f2 else 'NICHT BESTANDEN'}")
    proto.append(linie)
    text: str = "\n".join(proto)
    # Zone ist hier zwingend ZSTRESS (2024 durch ValueError oben versiegelt);
    # die Z2024-Report-Datei bleibt byte-identisch eingefroren (§2.16-F.2).
    ausgabe: Path = _REPORT_DIR / "tmp_regime_oos_stress.txt"
    ausgabe.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"\nProtokoll: {ausgabe}")
    return 0


# ---------------------------------------------------------------------------
# 10) MAIN
# ---------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI-Einstieg (--stufe=sweep|freeze|oos [--zone=stress])."""
    args: List[str] = list(sys.argv[1:] if argv is None else argv)
    stufe: str = ""
    zone: str = ""
    fenster: List[str] = ["S1", "S2"]
    for a in args:
        if a.startswith("--stufe="):
            stufe = a.split("=", 1)[1].lower()
        elif a.startswith("--zone="):
            zone = a.split("=", 1)[1].lower()
        elif a.startswith("--fenster="):
            fw: str = a.split("=", 1)[1].upper()
            fenster = [x for x in fw.split(",") if x in _WINDOWS]
    if stufe == "sweep":
        # Plateau-Validierung erfordert zwingend S1 UND S2 (getrennte Fenster)
        return _stufe_sweep(["S1", "S2"])
    if stufe == "freeze":
        return _stufe_freeze()
    if stufe == "oos":
        return _stufe_oos(zone)
    raise SystemExit(
        "Unbekannte Stufe: --stufe=sweep|freeze|oos [--zone=stress]"
    )


if __name__ == "__main__":
    raise SystemExit(main())
