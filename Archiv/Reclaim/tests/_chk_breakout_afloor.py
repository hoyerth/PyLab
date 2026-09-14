# -*- coding: utf-8 -*-
"""READ-ONLY Boden-Treppe A-Umfeld + Reclaim-Check."""
from __future__ import annotations
import hashlib, importlib.util, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
EP = ROOT / "test" / "tmp_kanten_engine_replay.py"
assert hashlib.sha256(EP.read_bytes()).hexdigest() == \
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"
s = importlib.util.spec_from_file_location("efl", EP)
e = importlib.util.module_from_spec(s)
sys.modules["efl"] = e
s.loader.exec_module(e)  # type: ignore[union-attr]
e.FENSTER["EXT"] = ("2026-08-03", "2026-09-12")  # type: ignore[index]
cfg = e.StraightEdgeHarnessKonfiguration()
sc = e._se_scan("EXT", cfg)  # type: ignore[arg-type]
d = sc["d"]; ts = list(d["ts"])
c = d["close"].to_numpy(float); l = d["low"].to_numpy(float)
E = list(sc["edges"]); LIVE = int(cfg.wall_live_bars)


def lebt(x: object, k: int) -> bool:
    b = [bb for bb, _ in x.wicks if bb <= k]  # type: ignore[attr-defined]
    return bool(b) and max(b) >= k - LIVE


def bas(x: object, k: int) -> float:
    return float(x.basis_bei(k))  # type: ignore[attr-defined]


def floor(k: int):
    u = [bas(x, k) for x in E if x.seite == "UNTEN" and int(x.geburts_bar) <= k and lebt(x, k)]  # type: ignore[attr-defined]
    return min(u) if u else None


print("BODEN-TREPPE A-Umfeld (Bars 800..1000), nur Aenderungen:")
last = None
for k in range(800, 1001):
    f = floor(k)
    if f is None:
        continue
    if last is None or abs(f - last) > 1e-9:
        dlt = f"({f-last:+.4f})" if last is not None else ""
        print(f"  Bar {k:>4} {str(ts[k]):<20} Boden {f:>8.4f}  Close {c[k]:>8.4f}  {dlt}")
        last = f

w = floor(835)
print(f"\nReclaim-Check A: gebrochene Wand @835 = {w:.4f}")
hits = [k for k in range(836, 1000) if c[k] > w]
print("  erster Close > Wand nach Bruch:",
      (hits[0], str(ts[hits[0]])) if hits else "KEINER")
for k in (858, 864, 880, 900, 920, 950, 1000):
    print(f"  Close@{k} ({ts[k]}): {c[k]:.4f}  Low {l[k]:.4f}  "
          f"{'ueber' if c[k] > w else 'unter'} Wand  Boden={floor(k)}")
