# -*- coding: utf-8 -*-
"""READ-ONLY: Vollstaendige Sollwert-Inventur fuer KONFIGURATION_V017.

Kandidat = Variante F + M6-Heilung (Rueckfall auf den ersten Docht) -- beides
in-memory. Gemessen wird der komplette Adapter-Satz (Hooks 1/2/3, K67-Override,
G4, Quartett) plus die sichtbaren Niveauwechsel (Renderer-Maskierung).

Keine Datei wird veraendert; die Engine-Kopie ist eine Wegwerfdatei.
"""
from __future__ import annotations

import pathlib
import sys
import types
from typing import Dict, List

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
RENDERER = ROOT / "test" / "tmp_png_aug_sichttest.py"
CAND = ROOT / "test" / "_tmp_engine_v017cand.py"

B_BASIS = """        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        return float(np.mean(px)) if px else self.basis"""
V017 = """        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        if px:
            return float(min(px) if self.seite == "OBEN" else max(px))
        return float(self.wicks[0][1])"""

src = P.read_text(encoding="utf-8")
assert src.count(B_BASIS) == 1
CAND.write_text(src.replace(B_BASIS, V017), encoding="utf-8", newline="")

R_SRC = RENDERER.read_text(encoding="utf-8")
MARKER = "# ---------------------------------------------------------------- Plot"
HEAD = R_SRC.split(MARKER)[0]
_HOLD: List[object] = []


def run(engine_path: pathlib.Path) -> Dict:
    src_head = HEAD.replace('P = ROOT / "test" / "tmp_kanten_engine_replay.py"',
                            f'P = Path(r"{engine_path}")')
    mod = types.ModuleType("inv_" + engine_path.stem)
    mod.__file__ = str(RENDERER)
    sys.modules[mod.__name__] = mod
    ns: Dict = mod.__dict__
    old_argv, old_out = sys.argv, sys.stdout
    sys.argv = ["t", "--mode", "V016", "--probe-praefix", "probe_",
                "--protokoll-nach", "test/_tmp_probeV017.txt"]
    try:
        exec(compile(src_head, "<head>", "exec", optimize=1), ns)
    finally:
        _HOLD.append(sys.stdout)
        sys.stdout = old_out
        sys.argv = old_argv
    return ns


def sichtwechsel(scan) -> int:
    """Niveauwechsel, die der Renderer wirklich zeichnet (maskiert vor Pivot+2)."""
    n = scan["n"]
    g = 0
    for e in list(scan["edges"]) + list(scan["seeds"]):
        prev = None
        for k in range(n):
            if not any(b + 2 <= k for b, _ in e.wicks):
                continue
            v = e.basis_bei(k)
            if prev is not None and abs(v - prev) > 1e-12:
                g += 1
            prev = v
    return g


def bericht(lbl: str, ns: Dict) -> None:
    V0, VB, V1 = ns["V0"], ns["V1_basis"], ns["V1"]
    h1, h2 = ns["h1_1"], ns["h2_1"]
    print(f"########## {lbl} ##########")
    print(f"  V0  (Engine roh)  : {len(V0):2d} / {sum(t.r for t in V0):+.6f} R")
    print(f"  V1_basis (v0.1)   : {len(VB):2d} / {sum(t.r for t in VB):+.6f} R"
          f"   <- RB")
    print(f"  V1_aktiv (Modus)  : {len(V1):2d} / {sum(t.r for t in V1):+.6f} R"
          f"   <- R1")
    print(f"  H1   : {len(h1)} / {sum(t.r for t in h1):+.6f} R"
          f"   entries {sorted(t.entry_bar for t in h1)}")
    print(f"  H2   : {len(h2)} / {sum(t.r for t in h2):+.6f} R")
    print(f"  P9_BEITRAG {ns['P9_BEITRAG']:+.6f}   QUARTETT_R {ns['QUARTETT_R']:+.6f}")
    print(f"  DELTA (R1-RB) {sum(t.r for t in V1) - sum(t.r for t in VB):+.6f}")
    print(f"  G4_TRADES: {[(t.bar, t.kid, round(t.r, 6)) for t in ns['G4_TRADES']]}")
    q = {t.bar: t for t in V1 if t.bar in ns["KONF"].quartett_bars}
    print("  Quartett: " + " | ".join(
        f"{b}: K{q[b].kid} {q[b].r:+.4f}" for b in sorted(q)))
    print(f"  K67-Quartett-Summe: "
          f"{sum(t.r for t in V1 if t.kid == 67 and t.bar in ns['KONF'].quartett_bars):+.4f}")
    print(f"  REFERENZ: {[(t.bar, t.kid) for t in sorted(ns['REFERENZ'], key=lambda x: x.bar)]}")
    print(f"  NEU     : {[(t.bar, t.kid) for t in sorted(ns['NEU'], key=lambda x: x.bar)]}")
    print(f"  Niveauwechsel sichtbar: {sichtwechsel(ns['scan'])}")
    kk = {e.kid: e for e in ns["scan"]["edges"] + ns["scan"]["seeds"]}
    n = ns["n"]
    print(f"  Niveaus: K67={kk[67].basis_bei(n-1):.4f} K73={kk[73].basis_bei(n-1):.4f} "
          f"K77={kk[77].basis_bei(n-1):.4f} K82={kk[82].basis_bei(n-1):.4f}")
    print()


bericht("BASELINE (arretierte Engine, V016)", run(P))
bericht("KANDIDAT V017 (F + M6-Heilung)", run(CAND))
CAND.unlink(missing_ok=True)
sys.exit(0)
