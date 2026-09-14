# -*- coding: utf-8 -*-
"""E-34n/1 — Nur-Lese-Forensik: Geometrie der V019-Trades, K82-Audit,
Datenkanten-Pruefung und Gate-Listen an den vom Anwender genannten BKZ-Zeiten.

WICHTIG: importiert den Renderer NICHT (der wuerde den kompletten PNG-Satz
fahren). Die Basis-13-Literale und die ZP-4-Funktion werden per AST gezielt
aus der Datei geholt und ausgefuehrt.

Kein Schreiben in Adapter/Engine; Ausgabe nur stdout + test/_tmp_e34n1_out.txt.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import importlib.util
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V015, ADAPTER_V019, DEFAULT_ADAPTER, Hook2ZielModus,
)

ENG = ROOT / "test" / "tmp_kanten_engine_replay.py"
REN = ROOT / "test" / "tmp_png_aug_sichttest.py"
OUT = ROOT / "test" / "_tmp_e34n1_out.txt"
_FH = OUT.open("w", encoding="utf-8", newline="\n")


class _Tee:
    def write(self, s: str) -> int:
        _FH.write(s)
        _FH.flush()
        return sys.__stdout__.write(s)

    def flush(self) -> None:
        _FH.flush()
        sys.__stdout__.flush()


sys.stdout = _Tee()  # type: ignore[assignment]

# ------------------------------------------------- Renderer-Regeln per AST
ren_txt = REN.read_text(encoding="utf-8")
ren_tree = ast.parse(ren_txt)
RENNS: dict = {}
for _n in ren_tree.body:
    if isinstance(_n, ast.Assign) and len(_n.targets) == 1 \
            and isinstance(_n.targets[0], ast.Name) \
            and _n.targets[0].id.startswith("A_"):
        exec(compile(ast.get_source_segment(ren_txt, _n), "<a_>", "exec"),  # noqa: S102
             RENNS)
    if isinstance(_n, ast.FunctionDef) \
            and _n.name == "_wende_zielzonen_patches_v019":
        exec(compile(ast.get_source_segment(ren_txt, _n), "<zp4>", "exec"),  # noqa: S102
             RENNS)
assert "_wende_zielzonen_patches_v019" in RENNS, "ZP-4-Funktion nicht gefunden"

# ---------------------------------------------------------------- Engine
src_datei = ENG.read_text(encoding="utf-8")
tree = ast.parse(src_datei)
node = next(x for x in tree.body
            if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src = ast.get_source_segment(src_datei, node)
assert src is not None


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


print("=" * 118)
print("E-34n/1  GEOMETRIE-FORENSIK V019 (read-only)")
print("=" * 118)
print(f"Engine {ENG.name} SHA "
      f"{hashlib.sha256(ENG.read_bytes()).hexdigest()[:24]}...")
print(f"Renderer SHA {hashlib.sha256(REN.read_bytes()).hexdigest()[:24]}...")

eng = load("ke_e34n1", ENG)
cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
n = scan["n"]
d = scan["d"]
ts = d["ts"]
op = d["open"].to_numpy(dtype=float)
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)

print(f"n={n} | box_end(raw)={scan['box_end_bar']}")
scan["box_end_bar"] = n

_ORDER = ("A_KANTEN", "A_LOOP", "A_POOL", "A_DIST", "A_M6_BASIS_K",
          "A_M6_BASIS", "A_M6_RET", "A_M6_SORT", "A_M6_SORT2", "A_M6_OBEN",
          "A_M6_UNTEN", "A_TP2", "A_KBASIS")
patched = src
for _nm in _ORDER:
    _s, _new = RENNS[_nm], RENNS[_nm + "_NEW"]
    assert patched.count(_s) == 1, (_nm, patched.count(_s))
    patched = patched.replace(_s, _new)
patched = RENNS["_wende_zielzonen_patches_v019"](patched)

SEG = ADAPTER_V019.segmente
AUTO_A, AUTO_B = SEG[1].start_bar, SEG[-1].end_bar
P9A, P9B = SEG[0].start_bar, SEG[0].end_bar
_HOOK = [DEFAULT_ADAPTER]


def _zv(kk: int) -> bool:
    return (len(_HOOK[0].segmente) > 1
            and AUTO_A <= kk <= AUTO_B and not (P9A <= kk <= P9B))


def _ueb(kk: int) -> float:
    return 0.80 if _zv(kk) else cfg.max_sweep_ueberdehnung_pct


_RS = eng._reclaim_stufe


def _rs_lok(seite, kk, basis, h, l, c, cc):
    if _zv(kk):
        cc = dataclasses.replace(cc, max_sweep_ueberdehnung_pct=0.80)
    return _RS(seite, kk, basis, h, l, c, cc)


ORIG = eng._se_trades
ns = dict(eng.__dict__)
ns["_Hook2ZielModus"] = Hook2ZielModus
ns["_zv"] = _zv
ns["_ueb"] = _ueb
ns["_reclaim_stufe"] = _rs_lok


def _lauf(hook):
    ns["_hook"] = hook
    _HOOK[0] = hook
    exec(compile(patched, "<se_e34n1>", "exec"), ns)
    eng._se_trades = ns["_se_trades"]
    try:
        return eng._se_trades(copy.deepcopy(scan), cfg)
    finally:
        eng._se_trades = ORIG


V19, st = _lauf(ADAPTER_V019)
V18, st18 = _lauf(ADAPTER_V015)
print(f"V19: {len(V19)} Trades / {sum(t.r for t in V19):+.6f} R  |  "
      f"V18: {len(V18)} Trades / {sum(t.r for t in V18):+.6f} R")
W = cfg.tp1_anteil_pct / 100.0
print(f"R-Gewichtung: TP1(poc) {W:.2f} / TP2(gegen) {1 - W:.2f} "
      f"(cfg.tp1_anteil_pct={cfg.tp1_anteil_pct})")


def _seg_of(k: int):
    for s in SEG:
        if s.start_bar <= k <= s.end_bar:
            return s
    return None


def _zerlege(t):
    e = t.entry_bar
    hh, ll, cc = hi[e:], lo[e:], cl[e:]
    nb = len(hh)
    risk = abs(t.sl - t.entry) or 1e-9

    def first(mask):
        return int(np.argmax(mask)) if mask.any() else nb

    if t.richtung == "SHORT":
        t1, t2, tsl = first(ll <= t.poc), first(ll <= t.tp2), first(hh >= t.sl)

        def rr(px):
            return (t.entry - px) / risk
    else:
        t1, t2, tsl = first(hh >= t.poc), first(hh >= t.tp2), first(ll <= t.sl)

        def rr(px):
            return (px - t.entry) / risk
    if t1 < tsl:
        r1, g1, b1 = rr(t.poc), "TP1", e + t1
    elif tsl < nb:
        r1, g1, b1 = -1.0, "SL", e + tsl
    else:
        r1, g1, b1 = rr(float(cc[-1])), "ENDE", e + nb - 1
    if t2 < tsl:
        r2, g2, b2 = rr(t.tp2), "TP2", e + t2
    elif tsl < nb:
        r2, g2, b2 = -1.0, "SL", e + tsl
    else:
        r2, g2, b2 = rr(float(cc[-1])), "ENDE", e + nb - 1
    return r1, r2, g1, g2, b1, b2, tsl, t1, t2, nb


print("\n" + "=" * 118)
print("A) ALLE V019-TRADES MIT GEOMETRIE (Marker an t.bar = Signalbar)")
print("=" * 118)
hdr = (f"{'bar':>5} {'BKZ sig':>12} {'kid':>4} {'rich':>5} {'basis':>8} "
       f"{'entry':>8} {'sl':>8} {'poc1':>8} {'tp2':>8} {'r':>9} {'r1':>7} "
       f"{'r2':>7} {'g1':>5} {'g2':>5} {'e_bar':>6} {'rest':>4} {'seg':>12}")
print(hdr)
for t in sorted(V19, key=lambda x: x.bar):
    r1, r2, g1, g2, b1, b2, tsl, t1, t2, nb = _zerlege(t)
    s = _seg_of(t.bar)
    print(f"{t.bar:>5} {ts.iloc[t.bar].strftime('%d.%m. %H:%M'):>12} "
          f"{t.kid:>4} {t.richtung:>5} {t.basis:>8.4f} {t.entry:>8.4f} "
          f"{t.sl:>8.4f} {t.poc:>8.4f} {t.tp2:>8.4f} {t.r:>+9.4f} "
          f"{r1:>+7.3f} {r2:>+7.3f} {g1:>5} {g2:>5} {t.entry_bar:>6} "
          f"{nb:>4} {('-' if s is None else s.phasen_id):>12}")

print("\n" + "=" * 118)
print("B) HERKUNFT tp2: natural vs. PHASE-Ziel des Adapters")
print("=" * 118)
print(f"{'bar':>5} {'kid':>4} {'rich':>5} {'tp2':>9} {'segziel':>9}  PHASE?")
for t in sorted(V19, key=lambda x: x.bar):
    s = _seg_of(t.bar)
    z = None if s is None else (s.ziel_preis_short if t.richtung == "SHORT"
                                else s.ziel_preis_long)
    ph = z is not None and abs(t.tp2 - z) < 1e-9
    print(f"{t.bar:>5} {t.kid:>4} {t.richtung:>5} {t.tp2:>9.4f} "
          f"{(float('nan') if z is None else z):>9.4f}  {ph}")

print("\n" + "=" * 118)
print("C) DATENKANTEN-PRUEFUNG (Restbars nach Entry / ENDE-Exits)")
print("=" * 118)
print(f"{'bar':>5} {'BKZ sig':>12} {'kid':>4} {'e_bar':>6} {'rest':>5} "
      f"{'g1':>5} {'g2':>5} {'r':>9}  Flag")
for t in sorted(V19, key=lambda x: x.bar):
    r1, r2, g1, g2, b1, b2, tsl, t1, t2, nb = _zerlege(t)
    flag = []
    if g1 == "ENDE" or g2 == "ENDE":
        flag.append("ENDE")
    if nb <= 12:
        flag.append(f"nur {nb} Bars")
    print(f"{t.bar:>5} {ts.iloc[t.bar].strftime('%d.%m. %H:%M'):>12} "
          f"{t.kid:>4} {t.entry_bar:>6} {nb:>5} {g1:>5} {g2:>5} {t.r:>+9.4f}  "
          f"{' | '.join(flag)}")

print("\n" + "=" * 118)
print("D) DIE NEUEN ZIELZONEN-TRADES: Pfad nach dem Entry")
print("=" * 118)
_v18k = {(t.bar, t.kid) for t in V18}
for t in sorted(V19, key=lambda x: x.bar):
    if (t.bar, t.kid) in _v18k:
        continue
    r1, r2, g1, g2, b1, b2, tsl, t1, t2, nb = _zerlege(t)
    print(f"\n--- bar {t.bar} ({ts.iloc[t.bar].strftime('%d.%m. %H:%M')} BKZ) "
          f"K{t.kid} {t.richtung}  r={t.r:+.6f} ---")
    print(f"    basis={t.basis:.4f} entry={t.entry:.4f} sl={t.sl:.4f} "
          f"risk={abs(t.sl - t.entry):.4f} poc1={t.poc:.4f} "
          f"tp2={t.tp2:.4f} stufe={t.stufe}")
    print(f"    Restbars {nb} | Exit1 {g1}@bar{b1} r1={r1:+.4f} | "
          f"Exit2 {g2}@bar{b2} r2={r2:+.4f}")
    print(f"    Pfad: low_min={float(np.min(lo[t.entry_bar:])):.4f} "
          f"high_max={float(np.max(hi[t.entry_bar:])):.4f}")
    _z = []
    for j in range(min(nb, 12)):
        b = t.entry_bar + j
        _z.append(f"{b}[{ts.iloc[b].strftime('%d.%m %H:%M')}]"
                  f"H{hi[b]:.3f}L{lo[b]:.3f}C{cl[b]:.3f}")
    print("    " + " ".join(_z))

print("\n" + "=" * 118)
print("E) K82-AUDIT")
print("=" * 118)
_k82 = next((e for e in list(scan["edges"]) + list(scan["seeds"])
             if int(e.kid) == 82), None)
print(f"K82 im Katalog: {_k82 is not None}")
if _k82 is not None:
    print(f"  seite={_k82.seite} erster_pivot_bar={_k82.erster_pivot_bar} "
          f"ist_prim_anker={_k82.ist_prim_anker} "
          f"promoviert_ab={getattr(_k82, 'promoviert_ab_bar', None)} "
          f"basis/VWAP={_k82.basis:.4f} n_wicks={len(_k82.wicks)} "
          f"touch_conf(n-1)={_k82.touch_conf(n - 1)}")
    print("  Wicks (bar, BKZ, preis):")
    for _b, _p in _k82.wicks:
        print(f"    bar {_b:>5} ({ts.iloc[_b].strftime('%d.%m. %H:%M')}) "
              f"{_p:.4f}")
    print("  Verlauf in der Zielzone (jeder 8. Bar):"
          if False else "  Aktivierung/Status an ausgewaehlten Bars:")
    for _b in (1033, 1075, 1099, 1140, 1174, 1211, 1245, 1268, 1272, 1280,
               1287):
        print(f"    bar {_b:>5} ({ts.iloc[_b].strftime('%d.%m. %H:%M')}) "
              f"basis_bei={_k82.basis_bei(_b):.4f} "
              f"existiert={_k82.erster_pivot_bar + 2 <= _b} "
              f"touch_conf={_k82.touch_conf(_b)} "
              f"ist_aktiv={_k82.ist_aktiv_bei(_b)}")

print("\n" + "=" * 118)
print("F) ANWENDER-ZEITEN: Bar-Aufloesung + Gate-Listen + K82-Status")
print("=" * 118)
_tskey = {ts.iloc[i].strftime("%d.%m. %H:%M"): i for i in range(n)}
ZIELE = (("25.08. 04:45", "Lower3 Touch 1"),
         ("25.08. 11:00", "Lower3 Touch 2"),
         ("25.08. 15:00", "Lower3 Touch 3"),
         ("26.08. 17:00", "Lower3 Touch 4 (auf Kante)"),
         ("27.08. 15:45", "Lower3 Touch 5 (67.6)"),
         ("27.08. 17:45", "Frontrunner"))
for _txt, _lbl in ZIELE:
    print(f"\n  {_txt} BKZ  ->  {_lbl}")
    _b = _tskey.get(_txt)
    if _b is None:
        print("    KEIN Bar mit diesem Zeitstempel (Kalenderluecke?)")
        continue
    print(f"    bar {_b}  O{op[_b]:.4f} H{hi[_b]:.4f} L{lo[_b]:.4f} "
          f"C{cl[_b]:.4f}")
    if _k82 is not None:
        print(f"    K82 basis_bei={_k82.basis_bei(_b):.4f} "
              f"existiert={_k82.erster_pivot_bar + 2 <= _b} "
              f"touch_conf={_k82.touch_conf(_b)} "
              f"ist_aktiv={_k82.ist_aktiv_bei(_b)}")
    for _name in ("quartil_liste", "blocker_liste", "zyklus_liste",
                  "f3_liste"):
        _l = st.get(_name)
        if not isinstance(_l, (list, tuple)):
            continue
        for _z in _l:
            if f"bar {_b:4d}" in _z:
                print(f"    [{_name}] {_z}")

print("\n" + "=" * 118)
print("G) stats-Schluessel (Laengen und Zaehler)")
print("=" * 118)
for _k in sorted(st):
    _v = st[_k]
    print(f"  {_k:<24} "
          f"{('len=' + str(len(_v))) if isinstance(_v, (list, tuple)) else _v}")

print("\nENDE E-34n/1")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
