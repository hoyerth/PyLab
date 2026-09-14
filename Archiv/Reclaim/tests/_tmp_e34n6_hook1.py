# -*- coding: utf-8 -*-
"""E-34n/6 — Hook-1-Freigabe (Segmentwand) und wirksame Basis je Bar 1072..1078."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import ADAPTER_V019  # noqa: E402

spec = importlib.util.spec_from_loader("ke_e34n6", loader=None)
eng = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
eng.__file__ = str(ROOT / "test" / "tmp_kanten_engine_replay.py")
sys.modules["ke_e34n6"] = eng
exec(compile((ROOT / "test" / "tmp_kanten_engine_replay.py").read_text(
    encoding="utf-8"), "k", "exec"), eng.__dict__)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
ts = scan["d"]["ts"]
hi = scan["d"]["high"].to_numpy(dtype=float)
lo = scan["d"]["low"].to_numpy(dtype=float)
alle = list(scan["edges"]) + list(scan["seeds"])

print("E-34n/6  Hook 1 / wirksame Basis (V019) im Fenster 1072..1078")
print("=" * 112)
for k in range(1072, 1079):
    seg = ADAPTER_V019.aktive_phase_bei(k)
    unten = [(int(e.kid), float(e.basis_bei(k)))
             for e in alle if e.seite == "UNTEN"]
    fr_l = ADAPTER_V019.hook_1_freigabe_kid(k, float(lo[k]), "LONG", unten)
    fr_s = ADAPTER_V019.hook_1_freigabe_kid(k, float(hi[k]), "SHORT", unten)
    print(f"\nbar {k} ({ts.iloc[k].strftime('%d.%m. %H:%M')}) "
          f"H{hi[k]:.4f} L{lo[k]:.4f} | Segment="
          f"{None if seg is None else seg.phasen_id} "
          f"boden={None if seg is None else seg.boden.kid}")
    print(f"   Hook1 FREIGABE  LONG={fr_l}  SHORT={fr_s}")
    for kid in (82, 62, 85, 60):
        e = next((x for x in alle if int(x.kid) == kid), None)
        if e is None:
            continue
        be = float(e.basis_bei(k))
        aw = float(ADAPTER_V019.angewandte_basis(k, kid, be))
        tc = int(e.touch_conf(k))
        d_u = (be - lo[k]) / be * 100.0
        tol = be * (seg.touch_band_pct / 100.0) if seg is not None else 0.0
        print(f"   K{kid:<3} basis_bei={be:.4f} wirksam={aw:.4f} "
              f"tc={tc} lo<base={lo[k] < be} diff={be - lo[k]:.4f} "
              f"tol={tol:.4f} imBand={abs(be - lo[k]) <= tol} "
              f"dist_u%={d_u:+.3f}")
print("\nENDE E-34n/6")
