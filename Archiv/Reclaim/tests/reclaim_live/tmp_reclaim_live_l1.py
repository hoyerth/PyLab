# -*- coding: utf-8 -*-
"""test/tmp_reclaim_live_l1.py -- L1-Test des Reclaim-Live-Kernels (E6, K3, K9).

Verifiziert, dass ``scripts/reclaim_live_kernel.py`` bitgenau zur frozen
Pipeline ``scripts/phasen_volumen_profil.py`` rechnet:

  1. Frozen-Referenz im SUBPROZESS (runpy via tmp_reclaim_live_frozen_runner)
     auf dem AUG-Fenster (2026-08-10 .. 2026-08-28, SILVER M15).
  2. Kernel-Digest auf identischem df (Konstanten-Identitaet, Phasen-Struktur:
     Anzahl/i_start/i_ende/brk_idx/U_final/L_final je Phase, Signale: alle
     Felder + Trade-R-Multiples).
  3. Regressionstor: 27 Signale, Summe R = +24,97 (AUG-Reclaim-Baseline).
  4. Artefakt-Bereinigung der frozen Pipeline (scripts/ + test/).

Ausfuehrung (Projekt-Root):
    .venv\\Scripts\\python.exe test/tmp_reclaim_live_l1.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import reclaim_live_kernel as kl  # noqa: E402

DB_PATH = ROOT / "data" / "market_data.duckdb"
START = "2026-08-10"
ENDE = "2026-08-28"

_KONSTANTEN = [
    "TOL", "TOL_TOUCH", "MIN_TOUCHES", "MIN_CANDLES", "MIN_PHASE_CANDLES",
    "MIN_CLUSTER", "MIN_ESTABLISH", "DENSITY_BAND", "MIN_SPREAD_PCT",
    "ERWEITERUNG_PCT", "SHIFT_TOL", "GRENZ_KONTAKT_TOL", "FENSTER_PIVOTS",
    "PIVOT_LOOKBACK", "VA_PCT", "NUM_BINS", "SMOOTH_WIN", "VALLEY_REL",
    "MIN_MOUNTAIN_PCT", "MIN_RECLAIM_CANDLES", "MIN_RECLAIM_BOUNCE",
    "MIN_RECLAIM_CRV", "MIN_SIGNAL_ABSTAND_BARS", "SL_PCT",
    "TP2_PUFFER_PCT", "ANTEIL_TP1", "TRAILING_PCT",
]

_ARTEFAKTE = [
    ROOT / "scripts" / "phasen_volumen_profil.png",
    ROOT / "scripts" / "phasen_volumen_profil.txt",
    ROOT / "test" / "stats_trades_AUG.txt",
    ROOT / "test" / "phasen_volumen_profil_AUG.png",
    ROOT / "test" / "phasen_volumen_profil_AUG.txt",
]


def _load_aug() -> pd.DataFrame:
    """Exakt wie frozen load_data (Z. 320-335): ts tz-naiv, idx=np.arange."""
    con = duckdb.connect(str(DB_PATH), read_only=True)
    d = con.execute(f"""
        SELECT time AT TIME ZONE 'UTC' AS ts, open, high, low, close, tick_volume
        FROM ohlcv_bars
        WHERE symbol='SILVER' AND timeframe='M15'
          AND time AT TIME ZONE 'UTC' >= DATE '{START}'
          AND time AT TIME ZONE 'UTC' <  DATE '{ENDE}'
        ORDER BY time
    """).fetchdf()
    con.close()
    d["ts"] = pd.to_datetime(d["ts"], utc=True).dt.tz_localize(None)
    d["idx"] = np.arange(len(d))
    return d


def _f(x: Any) -> Any:
    if x is None:
        return None
    v = float(x)
    return None if np.isnan(v) else v


def _b(x: Any) -> bool:
    return bool(x)


def _phasen_digest(phasen: List[Any]) -> List[Dict[str, Any]]:
    out = []
    for p in phasen:
        out.append({
            "start": str(p.start),
            "ende": str(p.ende),
            "i_start": int(p.i_start),
            "i_ende": int(p.i_ende),
            "brk_idx": None if p.brk_idx is None else int(p.brk_idx),
            "break_dir": p.break_dir,
            "U_final": _f(p.U_final),
            "L_final": _f(p.L_final),
            "handelbar": _b(p.handelbar),
            "n_candles": int(p.n_candles),
            "touches_h": int(p.touches_h),
            "touches_l": int(p.touches_l),
            "close_h": int(p.close_h),
            "close_l": int(p.close_l),
            "spread_pct": _f(p.spread_pct),
        })
    return out


def _signal_digest(signals: List[Any]) -> List[Dict[str, Any]]:
    out = []
    for s in signals:
        t = s.trade
        assert t is not None
        out.append({
            "ts": str(s.ts),
            "typ": s.typ,
            "reclaim": s.reclaim,
            "bar": int(s.bar),
            "einstieg_bar": int(s.einstieg_bar),
            "einstieg_preis": _f(s.einstieg_preis),
            "sl": _f(s.sl),
            "tp1": _f(s.tp1),
            "tp2": _f(s.tp2),
            "crv": _f(s.crv),
            "crv2": _f(s.crv2),
            "bounce_nr": int(s.bounce_nr),
            "phase": int(s.phase),
            "U_laufend": _f(s.U_laufend),
            "L_laufend": _f(s.L_laufend),
            "POC": _f(s.POC),
            "r_mult": _f(t.r_mult),
            "resultat": t.resultat,
            "grund1": t.grund1,
            "grund2": t.grund2,
            "tp1_hit": _b(t.tp1_hit),
            "tp2_hit": _b(t.tp2_hit),
            "exit1": _f(t.exit1),
            "exit2": _f(t.exit2),
        })
    return out


def main() -> None:
    # --- 1) Frozen-Referenz im Subprozess -----------------------------------
    digest_out = ROOT / "test" / "tmp_frozen_digest.json"
    if digest_out.exists():
        digest_out.unlink()
    env = os.environ.copy()
    env["FROZEN_DIGEST_OUT"] = str(digest_out)
    runner = ROOT / "test" / "tmp_reclaim_live_frozen_runner.py"
    try:
        r = subprocess.run(
            [sys.executable, str(runner)],
            cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=600,
        )
    finally:
        pass
    assert r.returncode == 0, (
        f"Frozen-Subprozess fehlgeschlagen (rc={r.returncode})\n"
        f"STDOUT:\n{r.stdout[-3000:]}\nSTDERR:\n{r.stderr[-3000:]}"
    )
    assert digest_out.exists(), "Frozen-Digest wurde nicht geschrieben"
    frozen = json.loads(digest_out.read_text(encoding="utf-8"))

    # --- 2) Kernel auf identischem df ---------------------------------------
    df = _load_aug()
    erg = kl.berechne_reclaim_signale(df)
    k_phasen = _phasen_digest(erg.phasen)
    k_signale = _signal_digest(erg.signale)

    # --- 3) Bitgenauer Abgleich ----------------------------------------------
    assert k_phasen == frozen["phasen"], (
        "PHASEN-ABWEICHUNG Kernel vs. frozen!\n"
        f"Kernel: {len(k_phasen)} Phasen | frozen: {len(frozen['phasen'])}"
    )
    assert k_signale == frozen["signale"], (
        "SIGNAL-ABWEICHUNG Kernel vs. frozen!\n"
        f"Kernel: {len(k_signale)} | frozen: {len(frozen['signale'])}"
    )
    for name in _KONSTANTEN:
        assert getattr(kl, name) == frozen["konstanten"][name], (
            f"Konstanten-Abweichung: {name} "
            f"Kernel={getattr(kl, name)} frozen={frozen['konstanten'][name]}"
        )
    assert frozen["anzahl_signale"] == len(erg.signale)

    # --- 4) Regressionstor (AUG-Reclaim-Baseline) ----------------------------
    assert len(erg.signale) == 27, f"AUG-Referenz: erwartet 27 Signale, erhalten {len(erg.signale)}"
    sum_r = sum(s.trade.r_mult for s in erg.signale if s.trade)
    assert abs(sum_r - 24.97) < 0.01, f"AUG-Referenz: Summe R {sum_r:+.2f} != +24.97"

    # --- 5) Artefakt-Bereinigung ----------------------------------------------
    for path in _ARTEFAKTE:
        if path.exists():
            path.unlink()
    if digest_out.exists():
        digest_out.unlink()

    print("L1 OK: Kernel bitgenau zur frozen Pipeline")
    print(f"  Phasen: {len(k_phasen)} | Signale: {len(k_signale)} "
          f"| Summe R: {sum_r:+.2f} (Referenz +24.97)")
    print(f"  Konstanten-Identitaet: {len(_KONSTANTEN)}/27 geprueft")


if __name__ == "__main__":
    main()
