"""
test/tmp_anchored_vwap_l1.py - L1-Verifikation scripts/anchored_vwap.py
========================================================================
Status: ISOLIERTER LOGIK-TEST (test/) - kein Produktionszugriff.

Zweck
-----
Bitgenaue Verifikation der vektorisierten AVWAP-Berechnung gegen eine
unabhaengige, naive Schleifen-Referenz (gleiche IEEE-754-Operationsfolge:
sequenzielle float64-Akkumulation, eine Division je Bar).

Pruefmatrix
-----------
  1. Real-Daten (AUG, SILVER M15): Anker an allen 11 Bruch-Indizes + Randfaelle
     (b=0, b=n-1, b>=n) x preis_modus {"typisch","close","open"}.
  2. Synthetische Kantenfaelle:
       - Null-Volumen-Block direkt nach dem Anker (Kette initialisiert erst
         bei erster positiver Volumen-Bar; danach unverseucht weiter).
       - NaN-Volumen-Bar (darf nicht vergiften).
       - Negatives Volumen (wird wie 0 behandelt).
       - b<0 (Klemmen auf 0), leeres df (Laenge 0), anchor_idx>=n (All-NaN).
       - Kontinuitaet: Bar mit V_k==0 zwischen positiven Bars veraendert
         das Verhaeltnis nicht (gleicher Wert wie Vorgaenger-Bar).
Bitgenauigkeit: ``np.testing.assert_array_equal`` (kein ``allclose``).

Aufruf (Projekt-Root):
    python test/tmp_anchored_vwap_l1.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
import pandas as pd

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))  # noqa: E402

from scripts.anchored_vwap import _preis_vektor, berechne_avwap_vektor  # noqa: E402
from scripts.market_segmentation import SegmentConfig, load_data  # noqa: E402
from scripts.setup_c_profil import FENSTER_DEFS  # noqa: E402


# =============================================================================
# 1) UNABHAENGIGE SCHLEIFEN-REFERENZ (bewusst naiv, langsam, lesbar)
# =============================================================================


def _referenz_schleife(
    df: pd.DataFrame,
    anchor_idx: int,
    preis_modus: str = "typisch",
    volumen_spalte: str = "tick_volume",
) -> np.ndarray:
    """Naive AVWAP-Referenz (identische Semantik, sequenzielle float64-Summen).

    Args:
        df: OHLCV-Frame.
        anchor_idx: Inklusiver Start-Index.
        preis_modus: "typisch"/"close"/"open".
        volumen_spalte: Volumen-Spaltenname.

    Returns:
        float64-Vektor (NaN vor Anker/bei Nenner <= 0).
    """
    n: int = len(df)
    preis: np.ndarray = _preis_vektor(df, preis_modus)  # noqa: SLF001 - Testnutzung
    vol: np.ndarray = df[volumen_spalte].to_numpy(dtype=float)
    out: np.ndarray = np.full(n, np.nan, dtype=np.float64)
    s: float = 0.0
    d: float = 0.0
    for k in range(n):
        if k >= anchor_idx:
            v: float = float(vol[k])
            if np.isfinite(v) and v > 0.0:
                s += float(preis[k]) * v
                d += v
        if d > 0.0:
            out[k] = s / d
    return out


# =============================================================================
# 2) PRUEFUNGEN
# =============================================================================


def _synthetisch_volumen() -> pd.DataFrame:
    """Frame mit gezielten Volumen-Kantenfaellen (Preis linear aufsteigend)."""
    n: int = 14
    close: np.ndarray = np.arange(1, n + 1, dtype=float)
    df: pd.DataFrame = pd.DataFrame(
        {
            "ts": pd.date_range("2026-08-10", periods=n, freq="15min"),
            "open": close - 0.1,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "tick_volume": [10.0, 0.0, np.nan, -5.0, 20.0, 0.0, 30.0,
                            0.0, 0.0, 40.0, 50.0, 0.0, 60.0, 70.0],
            "idx": np.arange(n),
        }
    )
    return df


def _synthetisch_leer() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": pd.Series(dtype="datetime64[ns]"),
            "open": pd.Series(dtype=float),
            "high": pd.Series(dtype=float),
            "low": pd.Series(dtype=float),
            "close": pd.Series(dtype=float),
            "tick_volume": pd.Series(dtype=float),
        }
    )


def _kontinuitaets_probe() -> None:
    """V_k==0 zwischen positiven Bars: Verhaeltnis bleibt identisch."""
    close: np.ndarray = np.array([10.0, 11.0, 12.0], dtype=float)
    df: pd.DataFrame = pd.DataFrame(
        {
            "ts": pd.date_range("2026-08-10", periods=3, freq="15min"),
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "tick_volume": np.array([100.0, 0.0, 100.0], dtype=float),
            "idx": np.arange(3),
        }
    )
    v: np.ndarray = berechne_avwap_vektor(df, 0)
    assert np.isfinite(v[0]) and np.isfinite(v[1]) and np.isfinite(v[2])
    assert abs(v[1] - v[0]) < 1e-12, f"V=0-Bar veraendert Verhaeltnis: {v}"
    # Bar 2: (typ*100_0 + typ*100_2)/200
    exp: float = (12.0 * 100.0 + 10.0 * 100.0) / 200.0
    assert abs(v[2] - exp) < 1e-12


def _kontinuitaets_probe2() -> None:
    """NaN-Volumen direkt nach Anker: Kette startet bei erster pos. Bar."""
    df: pd.DataFrame = pd.DataFrame(
        {
            "ts": pd.date_range("2026-08-10", periods=4, freq="15min"),
            "open": [1.0, 2.0, 3.0, 4.0],
            "high": [1.5, 2.5, 3.5, 4.5],
            "low": [0.5, 1.5, 2.5, 3.5],
            "close": [1.0, 2.0, 3.0, 4.0],
            "tick_volume": [np.nan, 0.0, np.nan, 50.0],
            "idx": [0, 1, 2, 3],
        }
    )
    v: np.ndarray = berechne_avwap_vektor(df, 0)
    assert np.isnan(v[0]) and np.isnan(v[1]) and np.isnan(v[2])
    # Bar 3: einziger Beitrag -> typischer Preis der Bar 3
    assert abs(v[3] - 4.0) < 1e-12, f"erwartet 4.0, ist {v[3]}"


def _real_proben() -> List[Dict]:
    """Real-Daten-Proben ueber alle AUG-Bruchanker + Randfaelle (AUG)."""
    start, ende = FENSTER_DEFS["AUG"]
    seg_cfg: SegmentConfig = SegmentConfig(start=start, ende=ende)
    df: pd.DataFrame = load_data(seg_cfg.db_path, seg_cfg.start, seg_cfg.ende)
    brks: Sequence[int] = [66, 121, 218, 380, 620, 715, 802, 848, 1030, 1082, 1171]
    anker: List[int] = list(brks) + [0, len(df) - 1, len(df), len(df) + 5, -3]
    proben: List[Dict] = []
    for b in anker:
        for pm in ("typisch", "close", "open"):
            proben.append({"df": df, "b": b, "pm": pm})
    return proben


def _main() -> int:
    fehler: int = 0
    geprueft: int = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal fehler
        if not ok:
            fehler += 1
        print(f"  [{('OK ' if ok else 'FEHLER')}] {name}: {detail}")

    print("=" * 100)
    print("L1-VERIFIKATION scripts/anchored_vwap.py (bitgenau vs. Schleife)")
    print("=" * 100)

    # --- A) Real-Daten AUG, alle Anker x Preis-Modi -------------------------
    print("\nA) REAL-DATEN (AUG SILVER M15): Vektor == Schleife (assert_array_equal)")
    for probe in _real_proben():
        df, b, pm = probe["df"], int(probe["b"]), str(probe["pm"])
        b_eff: int = max(0, min(b, len(df)))
        vec: np.ndarray = berechne_avwap_vektor(df, b, pm)
        ref: np.ndarray = _referenz_schleife(df, b, pm)
        try:
            np.testing.assert_array_equal(vec, ref)
            ok = True
            detail = f"b={b} (geklemmt {b_eff}) pm={pm} n={len(df)} identisch"
        except AssertionError as exc:
            ok = False
            detail = f"b={b} pm={pm}: {str(exc).splitlines()[0]}"
        geprueft += 1
        check(f"Real b={b} pm={pm}", ok, detail)
        # Naive Struktur-Sanity: NaN vor Anker
        nan_vorher: bool = bool(np.isnan(vec[:b_eff]).all()) if b_eff > 0 else True
        geprueft += 1
        check(f"Real b={b} pm={pm} NaN-Doktrin vor Anker", nan_vorher,
              f"erste {b_eff} Bars NaN")

    # --- B) Synthetische Kantenfaelle ---------------------------------------
    print("\nB) SYNTHETISCHE KANTENFAELLE")
    syn: pd.DataFrame = _synthetisch_volumen()
    for b in (0, 2, 6, 13, 20, -1):
        vec = berechne_avwap_vektor(syn, b)
        ref = _referenz_schleife(syn, b)
        b_eff = max(0, min(b, len(syn)))
        try:
            np.testing.assert_array_equal(vec, ref)
            ok = True
            detail = f"b={b} (geklemmt {b_eff}) identisch"
        except AssertionError as exc:
            ok = False
            detail = f"b={b}: {str(exc).splitlines()[0]}"
        geprueft += 1
        check(f"Synth b={b}", ok, detail)

    # Null-/NaN-/Negativ-Volumen ab Anker: Kette startet an Bar 0 (V=10),
    # Bars 1-3 (V=0/NaN/-5) veraendern das Verhaeltnis nicht.
    vec0: np.ndarray = berechne_avwap_vektor(syn, 0)
    typ0: float = (float(syn["high"].iloc[0]) + float(syn["low"].iloc[0])
                   + float(syn["close"].iloc[0])) / 3.0
    typ4: float = (float(syn["high"].iloc[4]) + float(syn["low"].iloc[4])
                   + float(syn["close"].iloc[4])) / 3.0
    assert np.isfinite(vec0[0]), "Bar 0 (V=10) muss die Kette starten"
    assert abs(vec0[0] - typ0) < 1e-12, f"Bar0 AVWAP {vec0[0]} != typ {typ0}"
    assert abs(vec0[1] - vec0[0]) < 1e-12, "Bar 1 (V=0) unveraendert"
    assert abs(vec0[2] - vec0[0]) < 1e-12, "Bar 2 (V=NaN) unvergiftet"
    assert abs(vec0[3] - vec0[0]) < 1e-12, "Bar 3 (V=-5) wie 0 behandelt"
    exp4: float = (typ0 * 10.0 + typ4 * 20.0) / 30.0
    assert abs(vec0[4] - exp4) < 1e-12, f"Bar4 AVWAP {vec0[4]} != {exp4}"
    geprueft += 1
    check("Synth Null-/NaN-/Negativ-Volumen ab Anker", True,
          "Start Bar 0, Bars 1-3 identisch, Bar 4 gewichtet (10/20)")

    # --- C) Randfaelle -------------------------------------------------------
    print("\nC) RANDFAELLE")
    vec_leer: np.ndarray = berechne_avwap_vektor(_synthetisch_leer(), 0)
    geprueft += 1
    check("Leeres df", vec_leer.size == 0 and vec_leer.dtype == np.float64,
          f"shape={vec_leer.shape} dtype={vec_leer.dtype}")

    vec_allnan: np.ndarray = berechne_avwap_vektor(syn, 99)
    geprueft += 1
    check("anchor_idx >= n -> All-NaN", bool(np.isnan(vec_allnan).all()),
          "n=14, b=99")

    _kontinuitaets_probe()
    _kontinuitaets_probe2()
    geprueft += 1
    check("Kontinuitaet V=0 / NaN-Start", True, "keine Verhaeltnis-Änderung")

    # --- Ergebnis -------------------------------------------------------------
    print("\n" + "=" * 100)
    print(f"L1-ERGEBNIS: {'ALLE PRUEFUNGEN BESTANDEN' if fehler == 0 else f'{fehler} FEHLER'}"
          f" ({geprueft} Vergleiche/Asserts)")
    print("=" * 100)
    return 0 if fehler == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_main())
