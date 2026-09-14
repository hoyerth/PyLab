# -*- coding: utf-8 -*-
"""READ-ONLY: Variante F gegen den VOLLSTAENDIGEN V016-Satz (Adapter inkl.).

Baut den Renderer-Lauf (tmp_png_aug_sichttest.py) zweimal nach -- einmal mit
der arretierten Engine (Baseline) und einmal mit in-memory gepatchtem
``basis_bei`` (F = Extremum der bestaetigten Dochte) -- und vergleicht die
Adapter-Trades (Hooks 1/2/3, K67-Override, G4, Quartett).

Keine Engine-/Adapter-Datei wird veraendert; der F-Lauf nutzt eine
Wegwerf-Kopie ``test/_tmp_engine_F.py`` (gitignored).
"""
from __future__ import annotations

import pathlib
import sys
from typing import Dict, List, Tuple

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
RENDERER = ROOT / "test" / "tmp_png_aug_sichttest.py"
PF = ROOT / "test" / "_tmp_engine_F.py"

B_BASIS = """        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        return float(np.mean(px)) if px else self.basis"""
F = """        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        if not px:
            return self.basis
        return float(min(px) if self.seite == "OBEN" else max(px))"""

src_orig = P.read_text(encoding="utf-8")
assert src_orig.count(B_BASIS) == 1
PF.write_text(src_orig.replace(B_BASIS, F), encoding="utf-8", newline="")

R_SRC = RENDERER.read_text(encoding="utf-8")
MARKER = "# ---------------------------------------------------------------- Plot"
assert MARKER in R_SRC
HEAD = R_SRC.split(MARKER)[0]

_HOLDER: List[object] = []


def run(engine_path: pathlib.Path) -> Dict:
    """Renderer-Kopf (bis vor dem Plot-Teil) scharf ausfuehren.

    ``optimize=1`` entfernt die FAIL-LOUD-Asserts -- die Sollwerte gelten fuer
    die arretierte V016-Baseline, nicht fuer die Probe.
    """
    src = HEAD.replace('P = ROOT / "test" / "tmp_kanten_engine_replay.py"',
                       f'P = Path(r"{engine_path}")')
    assert f'Path(r"{engine_path}")' in src
    import types
    mod = types.ModuleType("probe_" + engine_path.stem)
    mod.__file__ = str(RENDERER)
    sys.modules[mod.__name__] = mod            # exec-Falle: @dataclass braucht
    ns: Dict = mod.__dict__                    # den Modul-Eintrag in sys.modules
    old_argv, old_out = sys.argv, sys.stdout
    sys.argv = ["sichttest", "--mode", "V016", "--probe-praefix", "probe_",
                "--protokoll-nach", "test/_tmp_probeF.txt"]
    try:
        exec(compile(src, "<renderer_head>", "exec", optimize=1), ns)
    finally:
        _HOLDER.append(sys.stdout)      # Wrapper am Leben halten (Buffer!)
        sys.stdout = old_out
        sys.argv = old_argv
    return ns


def bericht(lbl: str, ns: Dict) -> Tuple:
    V1 = ns["V1"]
    h1, h2 = ns["h1_1"], ns["h2_1"]
    print(f"=== {lbl} ===")
    print(f"  Trades {len(V1)} / {sum(t.r for t in V1):+.6f} R")
    print(f"  H1 {len(h1)} / {sum(t.r for t in h1):+.6f} R")
    print(f"  H2 {len(h2)} / {sum(t.r for t in h2):+.6f} R")
    print(f"  P9-Beitrag {ns['P9_BEITRAG']:+.6f} R   "
          f"Quartett {ns['QUARTETT_R']:+.6f} R")
    g4 = ns["G4_TRADES"]
    print(f"  G4: {[f'K{t.kid}@{t.bar} {t.r:+.6f}' for t in g4]}"
          if g4 else "  G4: -- (kein Trade)")
    print("  Trades:")
    for t in sorted(V1, key=lambda x: (x.bar, x.kid)):
        print(f"    bar {t.bar:4d} K{t.kid:3d} {t.richtung:5s} r={t.r:+9.6f} "
              f"entry_bar={t.entry_bar:4d} entry={t.entry:.4f} tp2={t.tp2:.4f}")
    print(f"  REFERENZ (entfallen): "
          f"{[(t.bar, t.kid) for t in sorted(ns['REFERENZ'], key=lambda x: x.bar)]}")
    print(f"  NEU (hinzu)        : "
          f"{[(t.bar, t.kid) for t in sorted(ns['NEU'], key=lambda x: x.bar)]}")
    print()
    return {(t.bar, t.kid): t.r for t in V1}


b = run(P)
f = run(PF)
mb = b["V1"]
ra = bericht("BASELINE (arretierte Engine)", b)
rb = bericht("F = Extremum der bestaetigten Dochte", f)

print("=== DIFF ===")
ka = dict(ra)
kb = dict(rb)
print(f"  Kids identisch: {sorted(x.kid for x in mb) == sorted(x.kid for x in f['V1'])}")
nur_b = sorted(set(ka) - set(kb))
nur_f = sorted(set(kb) - set(ka))
print(f"  nur BASELINE: {[(k, round(ka[k], 6)) for k in nur_b]}")
print(f"  nur F       : {[(k, round(kb[k], 6)) for k in nur_f]}")
geaendert = [(k, round(ka[k], 6), round(kb[k], 6)) for k in sorted(set(ka) & set(kb))
             if abs(ka[k] - kb[k]) > 1e-9]
print(f"  R geaendert : {geaendert if geaendert else 'KEINE'}")
print()
print("=== KANTEN-NIVEAUS (Adapter-Sicht, basis_bei(1287)) ===")
for lbl, src in (("BASE", b), ("F   ", f)):
    e = next((x for x in src["scan"]["edges"] + src["scan"]["seeds"] if x.kid == 73), None)
    g = next((x for x in src["scan"]["edges"] + src["scan"]["seeds"] if x.kid == 82), None)
    k = next((x for x in src["scan"]["edges"] + src["scan"]["seeds"] if x.kid == 77), None)
    ch = next((x for x in src["scan"]["edges"] + src["scan"]["seeds"] if x.kid == 67), None)
    print(f"  {lbl} K73={e.basis_bei(src['n'] - 1):.4f} "
          f"K82={g.basis_bei(src['n'] - 1):.4f} "
          f"K77={k.basis_bei(src['n'] - 1):.4f} "
          f"K67={ch.basis_bei(src['n'] - 1):.4f}")
PF.unlink(missing_ok=True)
sys.exit(0)
