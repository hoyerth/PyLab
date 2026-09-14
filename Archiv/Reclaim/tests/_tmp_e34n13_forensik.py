# -*- coding: utf-8 -*-
"""E-34n/13-Forensik (READ-ONLY): offene Haelften + Concurrency im V019-Lauf.

Kein Code-Eingriff: nutzt den Varianten-Harness (AST-Extraktion + Patches),
rekonstruiert die beiden unabhaengigen Haelften je Trade ueber
``_c_loese_trade`` (die ``_SESetup``-Felder r1/r2/grund2 werden nicht
gespeichert) und vermisst:
  (1) Haelften, die am Fensterende als "ENDE" (close[-1]) geschlossen wurden,
  (2) die bereinigte Performance R_realisiert (drei Definitionen),
  (3) die Gleichzeitigkeit offener Trades (global und je Richtung).
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V015, ADAPTER_V019, DEFAULT_ADAPTER, Hook2ZielModus,
)

ENG = ROOT / "test" / "tmp_kanten_engine_replay.py"
REN = ROOT / "test" / "tmp_png_aug_sichttest.py"

ren_txt = REN.read_text(encoding="utf-8")
RENNS: dict = {}
for _n in ast.parse(ren_txt).body:
    if isinstance(_n, ast.Assign) and len(_n.targets) == 1 \
            and isinstance(_n.targets[0], ast.Name) \
            and _n.targets[0].id.startswith("A_"):
        exec(compile(ast.get_source_segment(ren_txt, _n), "<a_>", "exec"),
             RENNS)
    if isinstance(_n, ast.FunctionDef) \
            and _n.name == "_wende_zielzonen_patches_v019":
        exec(compile(ast.get_source_segment(ren_txt, _n), "<zp4>", "exec"),
             RENNS)

src_datei = ENG.read_text(encoding="utf-8")
_node = next(x for x in ast.parse(src_datei).body
             if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src = ast.get_source_segment(src_datei, _node)
_ORDER = ("A_KANTEN", "A_LOOP", "A_POOL", "A_DIST", "A_M6_BASIS_K",
          "A_M6_BASIS", "A_M6_RET", "A_M6_SORT", "A_M6_SORT2", "A_M6_OBEN",
          "A_M6_UNTEN", "A_TP2", "A_KBASIS")
patched = src
for _nm in _ORDER:
    patched = patched.replace(RENNS[_nm], RENNS[_nm + "_NEW"])
patched = RENNS["_wende_zielzonen_patches_v019"](patched)

spec = importlib.util.spec_from_loader("ke_e34n13f", loader=None)
eng = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
eng.__file__ = str(ENG)
sys.modules["ke_e34n13f"] = eng
exec(compile(src_datei, str(ENG), "exec"), eng.__dict__)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
BOX_END = int(scan["box_end_bar"])
scan["box_end_bar"] = scan["n"]
N = int(scan["n"])
hi = scan["d"]["high"].to_numpy(dtype=float)
lo = scan["d"]["low"].to_numpy(dtype=float)
cl = scan["d"]["close"].to_numpy(dtype=float)
ts = scan["d"]["ts"]
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


def _lauf(quelle: str, hook):
    _ns = dict(ns)
    _ns["_hook"] = hook
    _HOOK[0] = hook
    exec(compile(quelle, "<se>", "exec"), _ns)
    eng._se_trades = _ns["_se_trades"]
    try:
        _sc = copy.deepcopy(scan)
        res = eng._se_trades(_sc, cfg)
    finally:
        eng._se_trades = ORIG
    return res[0], _sc


def _zerlege(t):
    """Rekonstruiert beide Haelften (r1/r2/grund2 werden nicht gespeichert)."""
    tr = eng._c_loese_trade(hi, lo, cl, int(t.entry_bar), float(t.entry),
                            t.richtung, float(t.sl), float(t.poc),
                            float(t.tp2), cfg.tp1_anteil_pct)
    assert abs((0.5 * tr.r1 + 0.5 * tr.r2) - float(t.r)) < 1e-9, (t.bar, t.r)
    assert tr.grund1 == t.grund1, (t.bar, tr.grund1, t.grund1)
    assert int(tr.exit1_bar) == int(t.exit1_bar), t.bar
    assert int(tr.exit2_bar) == int(t.exit2_bar), t.bar
    return tr


def _fmt_dt(b: int) -> str:
    return ts.iloc[b].strftime("%d.%m. %H:%M") if 0 <= b < N else "------ --:--"


def _analyse(name: str, trades, out) -> None:
    w = 0.5
    print("=" * 118, file=out)
    print(f"  MODUS {name}  (n={N}, box_end={BOX_END}, FENSTERENDE Bar {N - 1})",
          file=out)
    print("=" * 118, file=out)
    print(f"  {'bar':>5} {'zeit':>12} {'kid':>4} {'ri':<5} {'e_bar':>5} "
          f"{'x1':>5} {'g1':<5} {'r1':>9} {'x2':>5} {'g2':<5} {'r2':>9} "
          f"{'r_gew':>10} {'offen':<6}", file=out)
    offene: list = []
    for t in sorted(trades, key=lambda x: int(x.bar)):
        tr = _zerlege(t)
        off1 = tr.grund1 == "ENDE"
        off2 = tr.grund2 == "ENDE"
        tag = ("BEIDE" if (off1 and off2) else
               ("h1" if off1 else ("h2" if off2 else "")))
        if tag:
            offene.append((t, tr, tag))
        print(f"  {int(t.bar):>5} {_fmt_dt(int(t.bar)):>12} "
              f"K{int(t.kid):<3} {t.richtung:<5} {int(t.entry_bar):>5} "
              f"{int(tr.exit1_bar):>5} {tr.grund1:<5} {tr.r1:>+9.4f} "
              f"{int(tr.exit2_bar):>5} {tr.grund2:<5} {tr.r2:>+9.4f} "
              f"{float(t.r):>+10.6f} {tag:<6}", file=out)
    r_brutto = sum(float(t.r) for t in trades)
    r_per_half = 0.0
    r_excl_trade = 0.0
    r_excl_only_open_half = 0.0
    for t in trades:
        tr = _zerlege(t)
        off1 = tr.grund1 == "ENDE"
        off2 = tr.grund2 == "ENDE"
        r_per_half += (0.0 if off1 else w * tr.r1) + \
                      (0.0 if off2 else w * tr.r2)
        if not (off1 or off2):
            r_excl_trade += float(t.r)
        if not off2:
            r_excl_only_open_half += float(t.r)
    print("-" * 118, file=out)
    print(f"  Trades gesamt            : {len(trades)}", file=out)
    print(f"  R_brutto (Mark-to-Market): {r_brutto:+.6f}   <-- aktueller Sollwert",
          file=out)
    print(f"  R_realisiert (a) Trade mit offener Haelfte voll ausgeschlossen: "
          f"{r_excl_trade:+.6f}  ({len(trades) - len(offene)} vollstaendige "
          f"Trades)", file=out)
    print(f"  R_realisiert (b) nur geschlossene Haelften (offene = 0, gewichtet): "
          f"{r_per_half:+.6f}", file=out)
    print(f"  R_realisiert (c) offene Haelfte h1 ignoriert (h2 zaehlt voll): "
          f"{r_excl_only_open_half:+.6f}", file=out)
    print(file=out)
    print(f"  OFFENE HAELFTEN ({len(offene)} Trades):", file=out)
    for t, tr, tag in offene:
        print(f"    bar {int(t.bar):>4} {_fmt_dt(int(t.bar))} K{int(t.kid):<3} "
              f"{t.richtung:<5} e_bar={int(t.entry_bar):>4} [{tag}] "
              f"r1={tr.r1:+.4f} (x{int(tr.exit1_bar)}/{tr.grund1}) "
              f"r2={tr.r2:+.4f} (x{int(tr.exit2_bar)}/{tr.grund2}) "
              f"r_gew={float(t.r):+.6f}", file=out)
    print(file=out)


def _concurrency(name: str, trades, out) -> None:
    """Max. gleichzeitig offene Trades global und je Richtung (Bar-genau)."""
    iv = []
    for t in trades:
        tr = _zerlege(t)
        a = int(t.entry_bar)
        b = max(int(tr.exit1_bar), int(tr.exit2_bar))
        iv.append((a, b, t.richtung, int(t.bar), int(t.kid)))
    maxg = 0
    maxd = {"LONG": 0, "SHORT": 0}
    argmaxg = None
    for k in range(N):
        aktiv = [x for x in iv if x[0] <= k <= x[1]]
        if len(aktiv) > maxg:
            maxg = len(aktiv)
            argmaxg = (k, aktiv)
        for d in ("LONG", "SHORT"):
            c = sum(1 for x in aktiv if x[2] == d)
            if c > maxd[d]:
                maxd[d] = c
    print("=" * 118, file=out)
    print(f"  CONCURRENCY {name}: max gleichzeitig offen = {maxg} "
          f"(LONG max {maxd['LONG']}, SHORT max {maxd['SHORT']})", file=out)
    if argmaxg is not None:
        b, akt = argmaxg
        print(f"  Peak bei Bar {b} ({_fmt_dt(b)}): "
              f"{sum(1 for x in akt if x[2] == 'LONG')} LONG / "
              f"{sum(1 for x in akt if x[2] == 'SHORT')} SHORT", file=out)
        for x in sorted(akt, key=lambda y: y[0]):
            print(f"    {x[2]:<5} K{x[4]:<3} bar {x[3]:>4} "
                  f"Intervall [{x[0]}..{x[1]}]  "
                  f"({_fmt_dt(x[0])} .. {_fmt_dt(x[1])})", file=out)
    # Paarweise Ueberlappung mit Ueberlappungsbars
    print("  Ueberlappende Paare (gleiche Richtung):", file=out)
    gef = 0
    for i in range(len(iv)):
        for j in range(i + 1, len(iv)):
            if iv[i][2] != iv[j][2]:
                continue
            a = max(iv[i][0], iv[j][0])
            b = min(iv[i][1], iv[j][1])
            if b >= a:
                gef += 1
                print(f"    {iv[i][2]:<5} K{iv[i][4]} bar{iv[i][3]} "
                      f"[{iv[i][0]}..{iv[i][1]}]  X  "
                      f"K{iv[j][4]} bar{iv[j][3]} [{iv[j][0]}..{iv[j][1]}]  "
                      f"-> Ueberlappung Bars {a}..{b} ({b - a + 1})", file=out)
    print(f"    Summe ueberlappender gleichgerichteter Paare: {gef}", file=out)
    print(file=out)


def _cap_sim(name: str, trades, out) -> None:
    """First-Order-Schaetzung einer Concurrency-Schranke (KEIN echter Re-Run).

    Greedy in Einstiegsreihenfolge: ein Trade wird verworfen, sobald zum
    Einstiegs-Bar bereits N gleichgerichtete (bzw. gleichkantige) akzeptierte
    Trades laufen. NICHT kausal identisch mit einem Gate in ``_se_trades``
    (dort beeinflussen verworfene Trades ``letzter_trade``/Zyklus) -- dient
    nur der Groessenordnung und der Invarianz-Frage.
    """
    iv = []
    for t in trades:
        tr = _zerlege(t)
        iv.append({"bar": int(t.bar), "a": int(t.entry_bar),
                   "b": max(int(tr.exit1_bar), int(tr.exit2_bar)),
                   "d": t.richtung, "kid": int(t.kid), "r": float(t.r)})
    iv.sort(key=lambda x: (x["a"], x["bar"]))

    def _sim(schluessel, Nmax):
        acc: list = []
        for x in iv:
            c = sum(1 for y in acc
                    if y["a"] <= x["a"] <= y["b"]
                    and y[schluessel] == x[schluessel])
            if c >= Nmax:
                continue
            acc.append(x)
        return acc

    print("=" * 118, file=out)
    print(f"  CAP-SIMULATION {name} (First-Order, Einstiegs-Reihenfolge)",
          file=out)
    for lbl, sch, nmax in (("global max 2 je Richtung", "d", 2),
                           ("global max 1 je Richtung", "d", 1),
                           ("je Kante max 1", "kid", 1)):
        acc = _sim(sch, nmax)
        weg = [x for x in iv if x not in acc]
        h1 = sum(x["r"] for x in acc if x["a"] < BOX_END)
        h1n = sum(1 for x in acc if x["a"] < BOX_END)
        v18_flag = "V018-INVARIANT" if not any(
            x["a"] < BOX_END for x in weg) else "H1 BETROFFEN"
        print(f"    {lbl:<28}: {len(acc):>2} Trades / "
              f"{sum(x['r'] for x in acc):+.6f} R  "
              f"| H1 {h1n}/{h1:+.6f}  [{v18_flag}]", file=out)
        for x in sorted(weg, key=lambda y: y["bar"]):
            print(f"        WEG  bar {x['bar']:>4} K{x['kid']:<3} {x['d']:<5} "
                  f"e_bar={x['a']:>4} r={x['r']:+.6f}", file=out)
    print(file=out)


with open(ROOT / "test" / "_tmp_e34n13_forensik_out.txt", "w",
          encoding="utf-8") as out:
    tr19, _ = _lauf(patched, ADAPTER_V019)
    _analyse("V019 (ZP-5(D), arretiert)", tr19, out)
    _concurrency("V019", tr19, out)
    _cap_sim("V019", tr19, out)

    tr18, _ = _lauf(patched, ADAPTER_V015)
    _analyse("V018 (Gegenprobe)", tr18, out)
    _concurrency("V018", tr18, out)
    _cap_sim("V018", tr18, out)

    print("ENDE E-34n/13-Forensik", file=out)

print("geschrieben:", ROOT / "test" / "_tmp_e34n13_forensik_out.txt")
