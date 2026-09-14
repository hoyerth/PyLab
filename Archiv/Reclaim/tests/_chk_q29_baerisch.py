# -*- coding: utf-8 -*-
"""READ-ONLY: Q29 im BAERISCHEN Fenster -- Spiegeltest der Asymmetrie.

These des Anwenders: Im baerischen Trend kehrt sich das Ungleichgewicht um
(LONG passiert, SHORT gesperrt) -- dieselbe Mechanik, nur gespiegelt.

Fenster B(baerisch): 2026-03-01 .. 2026-08-01
   Maerz 2026 Hoch 96.391 -> Juli 2026 Tief 54.751  (rund -43 %)
Kontrolle A(bullisch): 2026-08-03 .. 2026-09-12 (bekannt: 0 LONG / 19 SHORT)
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
ENGINE_PATH = ROOT / "test" / "tmp_kanten_engine_replay.py"
SHA_SOLL = "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"

sha = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
assert sha == SHA_SOLL, f"Fremd-Engine {sha[:16]}"
spec = importlib.util.spec_from_loader("ke_q29b", loader=None)
eng = importlib.util.module_from_spec(spec)
eng.__file__ = str(ENGINE_PATH)
sys.modules["ke_q29b"] = eng
exec(compile(ENGINE_PATH.read_text(encoding="utf-8"), str(ENGINE_PATH),
             "exec"), eng.__dict__)

cfg = eng.StraightEdgeHarnessKonfiguration()
q = float(cfg.quartil_distanz_pct)


def _messe(label: str, start: str, ende: str) -> None:
    """Scan + Trade-Lauf + Q29-Passraten fuer ein Fenster."""
    eng.FENSTER["CHK"] = (start, ende)                 # type: ignore[index]
    scan = eng._se_scan("CHK", cfg)                    # type: ignore[arg-type]
    n = int(scan["n"])
    d = scan["d"]
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    k0 = int(np.searchsorted(d["ts"].to_numpy().astype("datetime64[ns]"),
                             np.datetime64(start)))
    k1 = int(np.searchsorted(d["ts"].to_numpy().astype("datetime64[ns]"),
                             np.datetime64(ende)))
    print("=" * 74)
    print(f"{label}: {start} .. {ende}  n={n}")
    print(f"   Preis {d['close'].iloc[0]:.3f} -> {d['close'].iloc[-1]:.3f} "
          f"({(d['close'].iloc[-1]/d['close'].iloc[0]-1)*100:+.1f} %)")

    # --- Q29-Passrate (global, exakt die arretierte Formel) -------------
    ex_hi = np.maximum.accumulate(hi)
    ex_lo = np.minimum.accumulate(lo)
    spanne = ex_hi - ex_lo
    with np.errstate(divide="ignore", invalid="ignore"):
        d_short = np.where(spanne > 0, (ex_hi - hi) / spanne * 100.0, 0.0)
        d_long = np.where(spanne > 0, (lo - ex_lo) / spanne * 100.0, 0.0)
    print(f"   EX_HI={ex_hi[-1]:.3f} (Bar {int(np.argmax(ex_hi))}) | "
          f"EX_LO={ex_lo[-1]:.3f} (Bar {int(np.argmin(ex_lo))})")
    print(f"   Q29-Pass SHORT {int((d_short<=q).sum()):5d}/{n} = "
          f"{(d_short<=q).mean()*100:5.1f} %  |  "
          f"LONG {int((d_long<=q).sum()):5d}/{n} = "
          f"{(d_long<=q).mean()*100:5.1f} %")

    # --- Engine-native Trades ------------------------------------------
    scan["box_end_bar"] = n
    setups, stats = eng._se_trades(scan, cfg)          # type: ignore[arg-type]
    cnt = Counter(s.richtung for s in setups)
    for r in ("SHORT", "LONG"):
        rr = [s for s in setups if s.richtung == r]
        print(f"   TRADES {r:6s}: {cnt.get(r,0):3d} | Summe R "
              f"{sum(s.r for s in rr):+.6f}")
    for key in ("quartil_liste", "blocker_liste", "zyklus_liste"):
        lst = stats.get(key) or []

        def _dir(x: str) -> str:
            return ("LONG" if " LONG " in x
                    else ("SHORT" if " SHORT " in x else "?"))
        c = Counter(_dir(x) for x in lst)
        print(f"   {key:16s}: SHORT {c.get('SHORT',0):4d} | "
              f"LONG {c.get('LONG',0):4d}")


_messe("BULLISCH (Kontrolle)", "2026-08-03", "2026-09-12")
_messe("BAERISCH (Spiegeltest)", "2026-03-01", "2026-08-01")
print("=" * 74)
