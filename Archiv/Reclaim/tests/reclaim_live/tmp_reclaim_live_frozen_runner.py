# -*- coding: utf-8 -*-
"""test/tmp_reclaim_live_frozen_runner.py -- L1-Hilfs-Subprozess (K3).

Fuehrt die frozen Pipeline ``scripts/phasen_volumen_profil.py`` per
``runpy`` in einem EIGENEN Prozess aus (kein Import in den L1-Prozess!)
und schreibt den Referenz-Digest (Konstanten + Phasen + Signale) als JSON
nach ``$FROZEN_DIGEST_OUT``.

Der L1-Aufrufer (tmp_reclaim_live_l1.py) vergleicht diesen Digest bitgenau
mit dem Kernel-Digest und bereinigt danach die Artefakte der frozen Pipeline
(scripts/phasen_volumen_profil.png/.txt, test/stats_trades_AUG.txt,
test/phasen_volumen_profil_AUG.png/.txt).
"""
from __future__ import annotations

import json
import os
import runpy
from pathlib import Path
from typing import Any, Dict, List

_FROZEN = Path(__file__).resolve().parent.parent / "scripts" / "phasen_volumen_profil.py"


def _f(x: Any) -> Any:
    """float-Konvertierung (None bleibt None; nan -> None fuer JSON)."""
    if x is None:
        return None
    import math
    v = float(x)
    return None if math.isnan(v) else v


def _b(x: Any) -> Any:
    """bool-Konvertierung (np.bool_-sicher)."""
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
    out_path = Path(os.environ["FROZEN_DIGEST_OUT"])
    ns = runpy.run_path(str(_FROZEN), run_name="__main__")

    # AUG-Default-Lauf verifizieren (ohne argv-Overrides)
    assert ns["START"] == "2026-08-10"
    assert ns["ENDE"] == "2026-08-28"

    _KONSTANTEN = [
        "TOL", "TOL_TOUCH", "MIN_TOUCHES", "MIN_CANDLES", "MIN_PHASE_CANDLES",
        "MIN_CLUSTER", "MIN_ESTABLISH", "DENSITY_BAND", "MIN_SPREAD_PCT",
        "ERWEITERUNG_PCT", "SHIFT_TOL", "GRENZ_KONTAKT_TOL", "FENSTER_PIVOTS",
        "PIVOT_LOOKBACK", "VA_PCT", "NUM_BINS", "SMOOTH_WIN", "VALLEY_REL",
        "MIN_MOUNTAIN_PCT", "MIN_RECLAIM_CANDLES", "MIN_RECLAIM_BOUNCE",
        "MIN_RECLAIM_CRV", "MIN_SIGNAL_ABSTAND_BARS", "SL_PCT",
        "TP2_PUFFER_PCT", "ANTEIL_TP1", "TRAILING_PCT",
    ]
    konstanten = {name: ns[name] for name in _KONSTANTEN}

    phases = ns["phases"]
    signals = ns["reclaim_signals"]
    sum_r = sum(s.trade.r_mult for s in signals if s.trade) if signals else 0.0

    data = {
        "konstanten": konstanten,
        "phasen": _phasen_digest(phases),
        "signale": _signal_digest(signals),
        "anzahl_signale": len(signals),
        "summe_r": _f(sum_r),
    }
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[frozen-runner] Digest geschrieben: {out_path} "
          f"| Phasen {len(phases)} | Signale {len(signals)} | Summe R {sum_r:+.2f}")


if __name__ == "__main__":
    main()
