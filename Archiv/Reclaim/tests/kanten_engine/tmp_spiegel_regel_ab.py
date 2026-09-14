# -*- coding: utf-8 -*-
"""READ-ONLY SPIEGELUNG Regel (A) + (B) -- kein Engine-Patch auf Platte.

Regel (A)  Wand-Docht-Exception: ist der Sweep ein akzeptierter Docht der
           Wand SELBST, gilt die Wand als ERREICHT (Liquiditaet geliefert)
           -> sie faellt aus dem Kandidaten-Pool und ist kein M6-Blocker.
           (Semantik identisch zu M6 `b <= sweep_px -> continue`.)
Regel (B)  TP-Ziel: NUR im H2-Bereich (k >= box_end) = phasen-lokale
           Gegenwand (Boden/Decke der aktiven Phase) statt aeusserste Kante.
           H1 (< box_end) bleibt unveraendert.

Die Patches werden per AST-Segment + String-Ersatz NUR IM SPEICHER
angewandt (Quelldatei bleibt unberuehrt).
"""
from __future__ import annotations

import ast
import importlib.util
import io
import sys
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


engine = load("ke_sp", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan0 = engine._se_scan("AUG", cfg)
n = len(scan0["d"])
box_end = scan0["box_end_bar"]
scan0["box_end_bar"] = n
d = scan0["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
op = d["open"].to_numpy(dtype=float)
ts = d["ts"]

# ------------------------------------------------------------------ Phasen
PHASEN = {
    "P9":  (848, 1020, 69.9140, 68.3700),
    "P10": (1030, 1075, 68.2200, 67.5440),
    "P11": (1082, 1134, 69.3435, 68.5250),
    "P12": (1171, 1272, 69.5550, 67.6355),
}
ZIEL_MODUS = {"wert": "L_FINAL"}          # L_FINAL | MENTOR_68_40 | WAND_BASIS
MENTOR_ZIEL = 68.4000


def _phasen_ziel(k: int, richtung: str):
    """Phasen-lokale Gegenwand im H2-Bereich; None in H1/ausserhalb."""
    if k < box_end:
        return None
    for pid, (bs, be, u, l) in PHASEN.items():
        if bs <= k <= be:
            if ZIEL_MODUS["wert"] == "L_FINAL":
                return l if richtung == "SHORT" else u
            if ZIEL_MODUS["wert"] == "MENTOR_68_40":
                return MENTOR_ZIEL
            if ZIEL_MODUS["wert"] == "WAND_BASIS":
                return None      # wird ausserhalb ueber die Wand-Linie gesetzt
    return None


def _wand_docht(e, k: int, sweep_px: float) -> bool:
    """Sweep-Docht ist ein akzeptierter Docht DIESER Kante (Bar k)."""
    return any(b == k and abs(px - sweep_px) < 1e-9 for b, px in e.wicks)


A_SCOPE = {"wert": "H2"}          # H2 | GLOBAL


def _wand_docht_aktiv(e, k: int, sweep_px: float) -> bool:
    """Regel (A) mit Scoping: H2 = nur ab box_end (H1 bleibt unberuehrt)."""
    if A_SCOPE["wert"] == "H2" and k < box_end:
        return False
    return _wand_docht(e, k, sweep_px)


engine._phasen_ziel = _phasen_ziel
engine._wand_docht = _wand_docht
engine._wand_docht_aktiv = _wand_docht_aktiv

# --------------------------------------------------- Quelltext-Patch (RAM)
src_datei = P.read_text(encoding="utf-8")
tree = ast.parse(src_datei)
node = next(x for x in tree.body
            if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src = ast.get_source_segment(src_datei, node)
assert src is not None

R1_OLD = ('        if not pool:\n            return None\n'
          '        pool.sort(key=lambda e: e.basis_bei(k), '
          'reverse=(seite == "OBEN"))')
R1_NEW = (R1_OLD + '\n        # --- Regel (A): Wand-Docht-Exception ------'
          '--------------------\n'
          '        pool = [e for e in pool\n'
          '                if not _wand_docht_aktiv(e, k, sweep_px)]')
assert src.count(R1_OLD) == 1
src = src.replace(R1_OLD, R1_NEW)

R2_OLD = ('            if seite == "OBEN":\n'
          '                if b <= sweep_px:\n'
          '                    continue                    '
          '# erreicht -> kein Blocker\n')
R2_NEW = (R2_OLD +
          '                if _wand_docht_aktiv(e, k, sweep_px):\n'
          '                    continue                    '
          '# Regel (A): Wand lieferte selbst\n')
assert src.count(R2_OLD) == 1
src = src.replace(R2_OLD, R2_NEW)

R3_OLD = '            gegen_basis = geg.basis_bei(k)\n'
R3_NEW = (R3_OLD +
          '            _pz = _phasen_ziel(k, richtung)\n'
          '            if _pz is not None:\n'
          '                gegen_basis = _pz          '
          '# Regel (B): phasen-lokale Gegenwand (H2)\n')
assert src.count(R3_OLD) == 1
src = src.replace(R3_OLD, R3_NEW)

ns = engine.__dict__
ORIG = engine._se_trades          # WICHTIG: VOR dem exec sichern
exec(compile(src, "<se_trades_patched>", "exec"), ns)
PATCHED = ns["_se_trades"]


def run(regel_a: bool, regel_b: bool, a_scope: str = "H2"):
    ZIEL_MODUS["wert"] = "L_FINAL" if regel_b else "AUS"
    A_SCOPE["wert"] = a_scope
    if regel_a:
        engine._se_trades = PATCHED
    else:
        engine._se_trades = ORIG
    try:
        import copy
        sc = copy.deepcopy(scan0)
        setups, stats = engine._se_trades(sc, cfg)
    finally:
        engine._se_trades = ORIG
    return setups, stats


def _s(ss):
    return float(sum(t.r for t in ss))


V0, _ = run(False, False)
VA_G, _ = run(True, False, "GLOBAL")
VA_H2, _ = run(True, False, "H2")
VAB_H2, _ = run(True, True, "H2")

print("=" * 126)
print("A) REGRESSIONS-CHECK H1 (Box: entry_bar < 640) -- arretierte Referenz "
      "= 8 Trades / +38.964262 R")
print("=" * 126)
for name, ss in (("V0 Referenz", V0), ("VA global (A)", VA_G),
                 ("VA H2-only (A)", VA_H2), ("VAB H2 (A)+(B)", VAB_H2)):
    b = [t for t in ss if t.entry_bar < 640]
    h = [t for t in ss if t.entry_bar >= 640]
    print(f"  {name:18s} H1: {len(b):2d} Trades / {_s(b):+9.4f} R | "
          f"H2: {len(h):2d} Trades / {_s(h):+8.4f} R | "
          f"gesamt {len(ss):2d} / {_s(ss):+9.4f} R")

h1_ref = {(t.kid, t.bar): t.r for t in V0 if t.entry_bar < 640}
for name, ss in (("VA global", VA_G), ("VA H2-only", VA_H2),
                 ("VAB H2", VAB_H2)):
    h1 = {(t.kid, t.bar): t.r for t in ss if t.entry_bar < 640}
    neu = set(h1) - set(h1_ref)
    weg = set(h1_ref) - set(h1)
    diff = [k for k in set(h1) & set(h1_ref)
            if abs(h1[k] - h1_ref[k]) > 1e-9]
    ok = not neu and not weg and not diff
    print(f"  {name:12s}: H1 {'IDENTISCH (Regression = 0)' if ok else 'VERAENDERT'} "
          f"| neu={sorted(neu) or '-'} weg={sorted(weg) or '-'} "
          f"R-Diff={[(k, round(h1_ref[k], 4), round(h1[k], 4)) for k in diff] or '-'}")

VAB = VAB_H2

print("\n" + "=" * 126)
print("B) H2-TRADES unter Regel (A)+(B)")
print("=" * 126)
print(f"  {'sig':>4s} {'Zeit':13s} {'kid':>4s} {'stufe':16s} {'entry':>9s} "
      f"{'sl':>9s} {'tp2':>9s} {'poc':>9s} {'risk':>7s} {'R':>8s} "
      f"{'resultat':9s} {'grund1':6s}")
for t in sorted([x for x in VAB if x.entry_bar >= 640], key=lambda x: x.bar):
    print(f"  {t.bar:4d} {ts.iloc[t.bar].strftime('%d.%m. %H:%M'):13s} "
          f"{t.kid:4d} {t.stufe:16s} {t.entry:9.4f} {t.sl:9.4f} "
          f"{t.tp2:9.4f} {t.poc:9.4f} {abs(t.sl - t.entry):7.4f} "
          f"{t.r:+8.4f} {t.resultat:9s} {t.grund1:6s}")

print("\n" + "=" * 126)
print("C) BENCHMARK-ABGLEICH (K73 @ 980 / 1020)")
print("=" * 126)
for sig_bar, soll_r in ((980, 2.3821), (1020, 2.9747)):
    tr = [t for t in VAB if t.kid == 73 and t.bar == sig_bar]
    if not tr:
        print(f"  bar {sig_bar}: KEIN TRADE erzeugt")
        continue
    t = tr[0]
    print(f"  bar {sig_bar}: kid=K{t.kid} entry_bar={t.entry_bar} "
          f"({ts.iloc[t.entry_bar].strftime('%d.%m. %H:%M')}) "
          f"entry={t.entry} sl={t.sl} tp2={t.tp2} risk={abs(t.sl - t.entry):.4f} "
          f"R={t.r:+.4f} (Soll {soll_r:+.4f}, delta {t.r - soll_r:+.4f}) "
          f"resultat={t.resultat} grund1={t.grund1}")

print("\n" + "=" * 126)
print("D) ZIEL-VARIANTEN (Sensitivitaet der Regel (B))")
print("=" * 126)
for modus, ziel in (("L_FINAL", 68.3700), ("MENTOR_68_40", 68.4000)):
    ZIEL_MODUS["wert"] = modus
    engine._se_trades = PATCHED
    try:
        import copy
        sc = copy.deepcopy(scan0)
        ss, _ = engine._se_trades(sc, cfg)
    finally:
        engine._se_trades = ORIG
    tr = [t for t in ss if t.kid == 73 and t.bar in (980, 1020)]
    print(f"  Modus {modus:12s} (Ziel {ziel:.4f}): "
          + ("; ".join(f"bar {t.bar} R={t.r:+.4f}" for t in tr) or "keine")
          + f" | Summe {_s(tr):+.4f} R | H1 {_s([t for t in ss if t.entry_bar < 640]):+9.4f} R")

print("\n" + "=" * 126)
print("F) NEBENWIRKUNG von Regel (B) in H2 + TRANSITION-PARK (bars 640..847)")
print("=" * 126)
h2a = sorted([t for t in VA_H2 if t.entry_bar >= 640], key=lambda x: x.bar)
h2b = sorted([t for t in VAB_H2 if t.entry_bar >= 640], key=lambda x: x.bar)
ka = {(t.kid, t.bar): t for t in h2a}
kb = {(t.kid, t.bar): t for t in h2b}
print(f"  VA H2 ({len(h2a)}): " + ", ".join(
    f"K{t.kid}@{t.bar}({t.r:+.2f})" for t in h2a))
print(f"  VAB H2 ({len(h2b)}): " + ", ".join(
    f"K{t.kid}@{t.bar}({t.r:+.2f})" for t in h2b))
print(f"  (B) entfernt: {sorted(set(ka) - set(kb)) or '-'}")
print(f"  (B) hinzu   : {sorted(set(kb) - set(ka)) or '-'}")
for key in sorted(set(ka) & set(kb)):
    if abs(ka[key].r - kb[key].r) > 1e-9:
        print(f"  (B) R-Aenderung {key}: {ka[key].r:+.4f} -> {kb[key].r:+.4f} "
              f"(tp2 {ka[key].tp2:.4f} -> {kb[key].tp2:.4f})")
park = [t for t in h2b if 640 <= t.entry_bar <= 847]
rest = [t for t in h2b if t.entry_bar > 847]
print(f"\n  Transition-Park (640..847): {len(park)} Trades / "
      f"{_s(park):+.4f} R entfernt -> "
      + ", ".join(f"K{t.kid}@{t.bar}" for t in park))
print(f"  VERBLEIBEND in H2: {len(rest)} Trades / {_s(rest):+.4f} R "
      + " | ".join(f"K{t.kid}@{t.bar} entry {t.entry_bar} R={t.r:+.4f}"
                   for t in rest))
print(f"  Zielvorgabe-Band: {_s(rest):+.4f} R (Ziel = v0.4 L_final 68.370) | "
      f"+5.2817 R (Ziel = gerundet 68.400) | +5.3568 R (Mentor-Rechnung "
      f"100% TP2, ohne POC-Split)")

print("\n" + "=" * 126)
print("G) STATS-DIFF VA_H2 -> VAB_H2 (Blockade-Gruende)")
print("=" * 126)
_, sa = run(True, False, "H2")
_, sb = run(True, True, "H2")
for key in sorted(set(sa) & set(sb)):
    if isinstance(sa[key], int) and sa[key] != sb[key]:
        print(f"  {key:22s} VA={sa[key]:6d} VAB={sb[key]:6d} "
              f"delta={sb[key] - sa[key]:+6d}")

print("\n" + "=" * 126)
print("E) ZIEL-TREFFER-BARS je Zielpreis (Rohdaten)")
print("=" * 126)
for ziel in (68.3427, 68.3700, 68.3920, 68.4000):
    hit980 = next((b for b in range(982, 1100) if lo[b] <= ziel), -1)
    hit1020 = next((b for b in range(1021, 1100) if lo[b] <= ziel), -1)
    r1 = (op[982] - ziel) / (69.949 - op[982]) if hit980 > 0 else 0.0
    r2 = (op[1021] - ziel) / (69.974 - op[1021]) if hit1020 > 0 else 0.0
    print(f"  Ziel {ziel:.4f}: T1 hit bar {hit980} R={r1:+.4f} | "
          f"T2 hit bar {hit1020} R={r2:+.4f} | Summe {r1 + r2:+.4f}")
