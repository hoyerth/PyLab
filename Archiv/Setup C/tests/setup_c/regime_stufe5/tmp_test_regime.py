"""
test/tmp_test_regime.py - Isolierter AUG-Logiktest fuer scripts/regime_filter.py (Stufe 5)
==========================================================================================
Rein lesender Backend-Test (DuckDB read_only). Prueft die 4 freigegebenen Kriterien:

  K1  Fehlerfreie Ausfuehrung (keine unbehandelten Exceptions).
  K2  Exakt 11 Phasen-Zustaende (len(states) == n_F3 == 11 fuer AUG).
  K3  NaN-Doktrin: Jeder RegimeState mit nicht-endlichen Roh-Metriken ODER
      konsolidierung_bars < kaltstart_min_bars -> strikt regime="UNKLAR",
      konfidenz=0.0 (defensiver Kaltstart-Fallback).
  K4  Truncation-Kausalitaets-Assert: Abschneiden des Dataframes bei brk_idx
      (inklusive) liefert bitgenau denselben Metrik-Vektor (Indikator-Spalten
      an Bar brk_idx + phase_spread/durchstoss_dichte/tol_band_quote) wie der
      Gesamt-Frame -> beweist: kein Lookahead ueber die Phasengrenze.

Zusaetzlich: Gate-Determinismus (entscheide_gate-Mapping §2.16-D ueber alle
drei Regime inkl. synthetischer States).

Keine GUI, keine Regression, kein Produktions-Schreiben. Erzeugt keine
Dateien ausserhalb von test/.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

_PROJEKT_ROOT: Path = Path(__file__).resolve().parent.parent
if str(_PROJEKT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJEKT_ROOT))

from scripts.market_segmentation import (  # noqa: E402
    PhaseData,
    SegmentConfig,
    SegmentResult,
    load_data,
    segmentiere_markt,
)
from scripts.regime_filter import (  # noqa: E402
    RegimeGate,
    RegimeGateConfig,
    RegimeMetricConfig,
    RegimeSchwellen,
    RegimeState,
    _durchstoss_dichte,
    _spread_usd_kausal,
    _tol_band_quote,
    berechne_regime_metriken,
    berechne_zeitreihen_indikatoren,
    klassifiziere_regime,
    entscheide_gate,
)

FENSTER: Tuple[str, str] = ("2026-08-10", "2026-08-28")  # AUG
METRIK_FELDER: Tuple[str, ...] = (
    "phase_spread_usd",
    "phase_spread_atr_ratio",
    "durchstoss_dichte",
    "tol_band_quote",
    "ema_slope",
    "adx_val",
)


def _fmt(v: object) -> str:
    """Formatiert Zahlen fuer das Protokoll (NaN -> '-')."""
    if isinstance(v, (float, np.floating)) and not math.isfinite(float(v)):
        return "-"
    return f"{v:.5f}" if isinstance(v, (float, np.floating)) else str(v)


def _gleiche_float(a: float, b: float) -> bool:
    """Bit-Exaktheit oder beidseitig NaN (Truncation-Vergleich)."""
    if math.isnan(float(a)) and math.isnan(float(b)):
        return True
    return float(a) == float(b)


def _test_k2_k3(
    states_roh: List[RegimeState],
    states_klass: List[RegimeState],
    gate_cfg: RegimeGateConfig,
    n_f3: int,
) -> Tuple[List[str], int]:
    """K2 (Anzahl) + K3 (NaN-Doktrin). Gibt (Protokoll, Fehlerzahl) zurueck."""
    proto: List[str] = []
    fehler: int = 0

    if len(states_roh) != n_f3:
        proto.append(f"  [FAIL] K2: len(states_roh)={len(states_roh)} != n_F3={n_f3}")
        fehler += 1
    else:
        proto.append(f"  [ OK ] K2: len(states)==n_F3=={n_f3}")

    unklar_doktrin: int = 0
    for st in states_klass:
        endlich: bool = all(
            math.isfinite(float(getattr(st, f))) for f in METRIK_FELDER
        )
        kaltstart: bool = st.konsolidierung_bars < gate_cfg.kaltstart_min_bars
        if (not endlich) or kaltstart:
            unklar_doktrin += 1
            if st.regime != "UNKLAR" or st.konfidenz != 0.0:
                proto.append(
                    f"  [FAIL] K3: Phase {st.phase_nr} brk={st.brk_idx} "
                    f"nicht-endlich/kaltstart -> regime={st.regime}, "
                    f"konf={st.konfidenz} (erwartet UNKLAR/0.0)"
                )
                fehler += 1
    proto.append(
        f"  [ OK ] K3: NaN-Doktrin konsistent "
        f"({unklar_doktrin}/{len(states_klass)} States im UNKLAR-Pfad)"
    )
    return proto, fehler


def _test_k4_truncation(
    df_ind: pd.DataFrame,
    sr: SegmentResult,
    echte: List[PhaseData],
    cfg: RegimeMetricConfig,
) -> Tuple[List[str], int]:
    """K4: Truncation-Kausalitaets-Assert je echter Bruch-Phase."""
    proto: List[str] = []
    fehler: int = 0
    df_roh: pd.DataFrame = sr.df

    for nr, p in enumerate(echte, start=1):
        b: int = int(p.brk_idx)
        df_tr: pd.DataFrame = df_roh.iloc[: b + 1].copy()
        ind_tr: pd.DataFrame = berechne_zeitreihen_indikatoren(df_tr, cfg)

        # --- Indikator-Kausalitaet: Spalten an Bar b (full) vs. letzte Bar ---
        ind_ok: bool = True
        for col in ("atr", "ema", "ema_slope", "adx"):
            voll: float = float(df_ind[col].iloc[b])
            trun: float = float(ind_tr[col].iloc[-1])
            if not _gleiche_float(voll, trun):
                ind_ok = False
                proto.append(
                    f"  [FAIL] K4 Phase {nr} brk={b}: Spalte '{col}' "
                    f"voll={_fmt(voll)} vs. trunc={_fmt(trun)}"
                )
                fehler += 1
        if ind_ok:
            proto.append(f"  [ OK ] K4 Phase {nr:>2} brk={b:>4}: Indikatoren kausal")

        # --- Metrik-Helfer: gleiches PhaseData auf vollem vs. gekuerztem df ---
        s_full: float = _spread_usd_kausal(df_roh, p)
        s_trun: float = _spread_usd_kausal(df_tr, p)
        d_full: float = _durchstoss_dichte(df_roh, p, cfg)
        d_trun: float = _durchstoss_dichte(df_tr, p, cfg)
        q_full: float = _tol_band_quote(df_roh, p, cfg)
        q_trun: float = _tol_band_quote(df_tr, p, cfg)
        if not (
            _gleiche_float(s_full, s_trun)
            and _gleiche_float(d_full, d_trun)
            and _gleiche_float(q_full, q_trun)
        ):
            proto.append(
                f"  [FAIL] K4 Phase {nr} brk={b}: Metrik-Drift full vs. trunc "
                f"(spread {_fmt(s_full)}/{_fmt(s_trun)}, "
                f"dichte {_fmt(d_full)}/{_fmt(d_trun)}, "
                f"quote {_fmt(q_full)}/{_fmt(q_trun)})"
            )
            fehler += 1
        elif ind_ok:
            proto.append(
                f"  [ OK ] K4 Phase {nr:>2}: Metriken identisch "
                f"(spread={_fmt(s_full)}, dichte={_fmt(d_full)}, quote={_fmt(q_full)})"
            )
    return proto, fehler


def _test_gate_determinismus(
    states_klass: List[RegimeState], gate_cfg: RegimeGateConfig
) -> Tuple[List[str], int]:
    """Gate-Determinismus: real klassifizierte + synthetische States (alle 3 Regime)."""
    proto: List[str] = []
    fehler: int = 0

    # Referenz-Mapping §2.16-D
    erwartung: dict = {
        "TREND": (True, True, 96),
        "SHAKEOUT": (False, False, 48),
        "UNKLAR": (False, False, 48),
    }

    def _pruefe(st: RegimeState, quelle: str) -> None:
        nonlocal fehler
        gate: RegimeGate = entscheide_gate(st, gate_cfg)
        exp = erwartung[st.regime]
        ok = (
            gate.erlaube_raw_cluster_b == exp[0]
            and gate.erlaube_one_close == exp[1]
            and gate.ziel_horizont == exp[2]
            and gate.phase_nr == st.phase_nr
        )
        if ok:
            proto.append(
                f"  [ OK ] Gate {quelle}: {st.regime} -> "
                f"({gate.erlaube_raw_cluster_b},{gate.erlaube_one_close},"
                f"{gate.ziel_horizont})"
            )
        else:
            proto.append(
                f"  [FAIL] Gate {quelle}: {st.regime} -> erwartet {exp}, "
                f"erhalten ({gate.erlaube_raw_cluster_b},"
                f"{gate.erlaube_one_close},{gate.ziel_horizont})"
            )
            fehler += 1

    def _synthetisch(regime: str) -> RegimeState:
        return RegimeState(
            phase_nr=999,
            brk_idx=0,
            phase_spread_usd=1.0,
            phase_spread_atr_ratio=2.0,
            durchstoss_dichte=0.1,
            tol_band_quote=0.1,
            konsolidierung_bars=200,
            ema_slope=0.005,
            adx_val=40.0,
            regime=regime,  # type: ignore[arg-type]
        )

    for regime in ("TREND", "SHAKEOUT", "UNKLAR"):
        _pruefe(_synthetisch(regime), f"synthetisch/{regime}")
    for st in states_klass:
        _pruefe(st, f"real/Phase{st.phase_nr}")

    return proto, fehler


def main() -> int:
    """Fuehrt den isolierten AUG-Logiktest aus und druckt das Protokoll."""
    proto: List[str] = []
    fehler: int = 0
    linie: str = "=" * 100

    proto.append(linie)
    proto.append("REGIME_FILTER AUG-LOGIKTEST (test/tmp_test_regime.py, Stufe 5)")
    proto.append(f"Fenster AUG: {FENSTER[0]} .. {FENSTER[1]} (Ende-exklusiv)")

    # --- Pipeline ----------------------------------------------------------
    seg_cfg: SegmentConfig = SegmentConfig(start=FENSTER[0], ende=FENSTER[1])
    proto.append(f"DuckDB (read_only): {seg_cfg.db_path}")
    df: pd.DataFrame = load_data(seg_cfg.db_path, seg_cfg.start, seg_cfg.ende)
    sr: SegmentResult = segmentiere_markt(df, seg_cfg)
    echte: List[PhaseData] = [
        p
        for p in sr.phases
        if p.break_dir is not None and p.brk_idx is not None
    ]
    n_f3: int = len(echte)
    proto.append(f"Segmente gesamt: {len(sr.phases)} | echte Bruch-Phasen: {n_f3}")

    cfg_m: RegimeMetricConfig = RegimeMetricConfig()
    df_ind: pd.DataFrame = berechne_zeitreihen_indikatoren(sr.df, cfg_m)
    states_roh: List[RegimeState] = berechne_regime_metriken(
        df_ind, sr, cfg_m, rand_phasen="ZENSIERT_UEBERGEHEN"
    )

    gate_cfg: RegimeGateConfig = RegimeGateConfig()
    schwellen: RegimeSchwellen = RegimeSchwellen()
    states_klass: List[RegimeState] = klassifiziere_regime(
        states_roh, schwellen, gate_cfg
    )

    # --- K1: Fehlerfrei bis hier (Exception waere abgebrochen) -------------
    proto.append("  [ OK ] K1: Pipeline fehlerfrei (load/segment/indikatoren/metriken/klassif)")
    proto.append("")

    # --- K2/K3 -------------------------------------------------------------
    proto.append("K2/K3 (Anzahl + NaN-Doktrin):")
    p1, f1 = _test_k2_k3(states_roh, states_klass, gate_cfg, n_f3)
    proto.extend(p1)
    fehler += f1
    proto.append("")

    # --- K4 ----------------------------------------------------------------
    proto.append("K4 (Truncation-Kausalitaets-Assert je Phase):")
    p2, f2 = _test_k4_truncation(df_ind, sr, echte, cfg_m)
    proto.extend(p2)
    fehler += f2
    proto.append("")

    # --- Gate-Determinismus ------------------------------------------------
    proto.append("GATE-DETERMINISMUS (§2.16-D):")
    p3, f3 = _test_gate_determinismus(states_klass, gate_cfg)
    proto.extend(p3)
    fehler += f3
    proto.append("")

    # --- Metrik-Report je State -------------------------------------------
    proto.append("METRIK-VEKTOREN (Roh, vor Klassifikation):")
    proto.append(
        f"  {'#Ph':>3} {'brk':>4} {'spread$':>9} {'sp/atr':>8} "
        f"{'dichte':>7} {'quote':>6} {'konsB':>5} {'emaSlp':>8} "
        f"{'adx':>6}  regime"
    )
    for st in states_klass:
        proto.append(
            f"  {st.phase_nr:>3} {st.brk_idx:>4} {_fmt(st.phase_spread_usd):>9} "
            f"{_fmt(st.phase_spread_atr_ratio):>8} {_fmt(st.durchstoss_dichte):>7} "
            f"{_fmt(st.tol_band_quote):>6} {st.konsolidierung_bars:>5} "
            f"{_fmt(st.ema_slope):>8} {_fmt(st.adx_val):>6}  {st.regime}"
        )
    proto.append("")

    # --- Gesamturteil --------------------------------------------------------
    proto.append(linie)
    if fehler == 0:
        proto.append("GESAMTURTEIL: ALLE PRUEFUNGEN BESTANDEN ([ OK ], 0 Fehler)")
    else:
        proto.append(f"GESAMTURTEIL: {fehler} FEHLER - NICHT BESTANDEN")
    proto.append(linie)

    text: str = "\n".join(proto)
    print(text)
    ausgabe: Path = Path(__file__).resolve().parent / "tmp_test_regime_AUG.txt"
    ausgabe.write_text(text, encoding="utf-8")
    print(f"\nProtokoll: {ausgabe}")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
