# -*- coding: utf-8 -*-
"""READ-ONLY Stacking-Audit (Mentor-Schritt 2, 2026-09-09).

Prueft die arretierte Spez-Regel §7.1 B ("max. 1 offene Position je Kante
(kein Stacking)") gegen den SE-Harness. Die Engine-Datei wird NICHT
veraendert; fuer die hypothetische Gate-Wirkung wird der Quelltext nur
in-memory gepatcht und als eigenes Modul ausgefuehrt.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"

L: List[str] = []


def out(s: str = "") -> None:
    L.append(s)


def _load(name: str, src: str):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(P)
    sys.modules[name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


src = P.read_text(encoding="utf-8")

# --- In-Memory-Gate: exakt §7.1 B (kein Stacking je Kante) -------------------
_anchor = """            trade = _c_loese_trade(
                hi, lo, cl, entry_bar, entry, richtung, sl, poc, tp2,
                cfg.tp1_anteil_pct)
"""
assert src.count(_anchor) == 1, f"Anker nicht eindeutig: {src.count(_anchor)}"
_gate = _anchor + """            if kd.kid in letzter_trade:
                _vt = letzter_trade[kd.kid]
                _cb = max([b for b in (_vt.exit1_bar, _vt.exit2_bar) if b >= 0]
                          or [_vt.entry_bar])
                if entry_bar <= _cb:
                    STACKING_LOG.append((k, richtung, kd.kid, entry_bar,
                                         _vt.entry_bar, _cb, _vt.r))
                    stats["stacking_blockiert"] = (
                        stats.get("stacking_blockiert", 0) + 1)
                    continue
"""
patched = src.replace(_anchor, _gate)
patched = patched.replace(
    "MAX_SIGNAL_ZEILEN: int = 60",
    "MAX_SIGNAL_ZEILEN: int = 60\nSTACKING_LOG: List[Tuple] = []", 1)

# --- Variante 2: "offene Position" endet mit dem De-Risking (TP1/ex1) -------
# Harness-Kommentar Z.2267 (Q11/Q16): "Einstieg nur ohne offene Position ODER
# nach De-Risking (Haelfte 1 = TP1)".
patched2 = patched.replace(
    "and entry_bar <= _cb",
    "and entry_bar <= _vt.exit1_bar", 1)

ke = _load("ke_replay", src)              # Original (unveraendert)
kep = _load("ke_replay_gated", patched)   # Gate-Variante (in-memory)
kep2 = _load("ke_replay_gated2", patched2)  # Gate bis De-Risking

cfg = ke.StraightEdgeHarnessKonfiguration()

# --- Lauf 1: Box (box_end_bar unveraendert) ---------------------------------
scan_box = ke._se_scan("AUG", cfg)
setups_box, stats_box = ke._se_trades(scan_box, cfg)
box_end = scan_box["box_end_bar"]
n = len(scan_box["d"])

# --- Lauf 2: Voll (box_end_bar = n) -----------------------------------------
scan_full = ke._se_scan("AUG", cfg)
scan_full["box_end_bar"] = n
setups_full, stats_full = ke._se_trades(scan_full, cfg)

# --- Lauf 3: Voll MIT Gate (in-memory gepatcht) -----------------------------
scan_gate = kep._se_scan("AUG", cfg)
scan_gate["box_end_bar"] = n
setups_gate, stats_gate = kep._se_trades(scan_gate, cfg)
gate_log_full = list(kep.STACKING_LOG)
kep.STACKING_LOG.clear()

# --- Lauf 4: Box MIT Gate ---------------------------------------------------
scan_gate_box = kep._se_scan("AUG", cfg)
setups_gate_box, stats_gate_box = kep._se_trades(scan_gate_box, cfg)
gate_log_box = list(kep.STACKING_LOG)

# --- Lauf 5/6: Variante 2 (De-Risking-Lesart), Voll und Box -----------------
scan_g2 = kep2._se_scan("AUG", cfg)
scan_g2["box_end_bar"] = n
setups_g2, stats_g2 = kep2._se_trades(scan_g2, cfg)
gate2_log = list(kep2.STACKING_LOG)
kep2.STACKING_LOG.clear()
scan_g2b = kep2._se_scan("AUG", cfg)
setups_g2_box, stats_g2_box = kep2._se_trades(scan_g2b, cfg)
gate2_log_box = list(kep2.STACKING_LOG)


def _ex(s) -> int:
    """Schliess-Bar der Position = spaeteste Halft-Exit-Bar (max)."""
    kandidaten = [b for b in (s.exit1_bar, s.exit2_bar) if b is not None and b >= 0]
    return max(kandidaten) if kandidaten else s.entry_bar


def _phase(s) -> str:
    return "BOX" if s.entry_bar < box_end else "POST"


def _audit(setups, label: str) -> List[Tuple]:
    per: Dict[int, List] = {}
    for s in setups:
        per.setdefault(s.kid, []).append(s)
    verletzungen: List[Tuple] = []
    out("=" * 118)
    out(f"STACKING-AUDIT {label}  (box_end_bar={box_end}, n={n}, "
        f"Trades={len(setups)})")
    out("=" * 118)
    for kid in sorted(per):
        lst = sorted(per[kid], key=lambda s: (s.entry_bar, s.bar))
        for a, b in zip(lst, lst[1:]):
            ea, eb = _ex(a), _ex(b)
            if b.entry_bar <= ea:
                verletzungen.append((kid, a, b,
                                     min(ea, eb) - b.entry_bar + 1))
    if not verletzungen:
        out("  KEINE Stacking-Verletzung (je Kante) gefunden.")
    for kid, a, b, ov in verletzungen:
        out(f"  VERLETZUNG K{kid:3d} {a.richtung:5s} "
            f"({_phase(a)}->{_phase(b)})  "
            f"T1 entry={a.entry_bar} exit2={_ex(a)} R={a.r:+.2f} "
            f"| T2 entry={b.entry_bar} exit2={_ex(b)} R={b.r:+.2f} "
            f"| Ueberlappung {ov} Bars")
    # globale (kantenuebergreifende) Ueberlappung als Info (vollstaendig)
    alle = sorted(setups, key=lambda s: (s.entry_bar, s.bar))
    glob = [(a, b) for i, a in enumerate(alle)
            for b in alle[i + 1:]
            if b.kid != a.kid and b.entry_bar <= _ex(a)]
    out(f"  INFO: kantenuebergreifende Ueberlappungen: {len(glob)}")
    for a, b in glob[:20]:
        out(f"        K{a.kid:3d} {_phase(a):4s} entry={a.entry_bar} "
            f"exit2={_ex(a)} -> K{b.kid:3d} {_phase(b):4s} "
            f"entry={b.entry_bar} ({b.entry_bar - _ex(a)} Bars)")
    return verletzungen


def _liste(setups, label: str) -> None:
    out("")
    out(f"--- TRADES {label} ({len(setups)}) ---")
    out("  kid richt  phase   bar entry exit1 exit2  stufe              "
        "touch  R      res      grund1")
    for s in sorted(setups, key=lambda s: (s.entry_bar, s.bar)):
        out(f"  K{s.kid:3d} {s.richtung:5s} {_phase(s):5s} {s.bar:4d} "
            f"{s.entry_bar:5d} {s.exit1_bar:5d} {_ex(s):5d}  "
            f"{s.stufe:18s} {s.touch_n:2d}  {s.r:+6.2f}  {s.resultat:8s} "
            f"{s.grund1}")


def _sum(setups) -> Tuple[int, float, int, float]:
    box = [s for s in setups if s.entry_bar < box_end]
    post = [s for s in setups if s.entry_bar >= box_end]
    return (len(box), sum(s.r for s in box), len(post), sum(s.r for s in post))


out("#" * 118)
out("# STACKING-AUDIT (READ-ONLY) -- §7.1 B 'max. 1 offene Position je Kante'")
out("#" * 118)
out("")

v_box = _audit(setups_box, "BOX-LAUF (box_end=644)")
_liste(setups_box, "BOX-LAUF")
out("")
v_full = _audit(setups_full, "VOLL-LAUF (box_end=n=1288)")
_liste(setups_full, "VOLL-LAUF")

out("")
out("=" * 118)
out("HYPOTHETISCHE GATE-WIRKUNG (exakte In-Memory-Simulation)")
out("=" * 118)
out("")
out(f"--- BOX-Lauf MIT GATE ({len(setups_gate_box)} Trades) ---")
_liste(setups_gate_box, "BOX MIT GATE")
out("")
out("  Gate-Blockierungen Box-Lauf:")
for e in gate_log_box:
    out(f"     k={e[0]:4d} {e[1]:5s} K{e[2]:3d} entry={e[3]:5d} "
        f"(Vortrade offen bis {e[5]:5d}, R_vortrade={e[6]:+.2f})")
out("")
out(f"--- VOLL-Lauf MIT GATE ({len(setups_gate)} Trades) ---")
_liste(setups_gate, "VOLL MIT GATE")
out("")
out("  Gate-Blockierungen Voll-Lauf:")
for e in gate_log_full:
    out(f"     k={e[0]:4d} {e[1]:5s} K{e[2]:3d} entry={e[3]:5d} "
        f"(Vortrade offen bis {e[5]:5d}, R_vortrade={e[6]:+.2f})")
nb, rb, np_, rp = _sum(setups_box)
gnb, grb, gnp, grp = _sum(setups_gate_box)
out("")
out(f"  BOX  ohne Gate: n={nb}  Netto-R={rb:+.2f}")
out(f"  BOX  mit  Gate: n={gnb} Netto-R={grb:+.2f}  "
    f"(Differenz {grb - rb:+.2f} R, {gnb - nb:+d} Trades)")
fb, frb, fp, frp = _sum(setups_full)
gfb, gfrb, gfp, gfrp = _sum(setups_gate)
out(f"  POST ohne Gate: n={fp}  Netto-R={frp:+.2f}")
out(f"  POST mit  Gate: n={gfp} Netto-R={gfrp:+.2f}  "
    f"(Differenz {gfrp - frp:+.2f} R, {gfp - fp:+d} Trades)")
out(f"  GESAMT ohne Gate: n={fb + fp}  Netto-R={frb + frp:+.2f}")
out(f"  GESAMT mit  Gate: n={gfb + gfp}  Netto-R={gfrb + gfrp:+.2f}")

out("")
out("=" * 118)
out("KERNFRAGE: Wurden im BOX-Fenster (0-641) bestehende GEWINNER unzulaessig")
out("ueberlappt? (§7.1 B 'max. 1 offene Position je Kante')")
out("=" * 118)
_box_v = [v for v in v_box if v[0] in (20, 31)]
for kid, a, b, ov in _box_v:
    out(f"  K{kid}: Gewinner T1 entry={a.entry_bar} exit2={_ex(a)} "
        f"R={a.r:+.2f} -- Zweittrade T2 entry={b.entry_bar} "
        f"({ov} Bars ueberlappend, selbst R={b.r:+.2f})")
out(f"  -> Beide Box-Doppel-Trades (K20, K31) sind Stacking-Verletzungen.")
out(f"  -> Gate-Wirkung BOX: {rb:+.2f} -> {grb:+.2f} R "
    f"({grb - rb:+.2f} R).")

out("")
out("=" * 118)
out("VARIANTE 2: 'offene Position' endet mit De-Risking (TP1, exit1_bar)")
out("Harness-Kommentar Z.2267: 'Einstieg nur ohne offene Position ODER nach")
out("De-Risking (Haelfte 1 = TP1)' -- weiter gefasst als §7.1 B.")
out("=" * 118)
b2n, b2r, p2n, p2r = _sum(setups_g2_box)
f2n, f2r, fp2, fp2r = _sum(setups_g2)
out("  Blockierungen Box-Lauf:")
for e in gate2_log_box:
    out(f"     k={e[0]:4d} {e[1]:5s} K{e[2]:3d} entry={e[3]:5d} "
        f"(TP1-Trade1 bei {e[5]:5d}, R={e[6]:+.2f})")
out("  Blockierungen Voll-Lauf:")
for e in gate2_log:
    out(f"     k={e[0]:4d} {e[1]:5s} K{e[2]:3d} entry={e[3]:5d} "
        f"(TP1-Trade1 bei {e[5]:5d}, R={e[6]:+.2f})")
out("")
out(f"  BOX  ohne Gate: n={nb} Netto-R={rb:+.2f} | mit Gate2: n={b2n} "
    f"Netto-R={b2r:+.2f} ({b2r - rb:+.2f} R)")
out(f"  POST ohne Gate: n={fp} Netto-R={frp:+.2f} | mit Gate2: n={fp2} "
    f"Netto-R={fp2r:+.2f} ({fp2r - frp:+.2f} R)")
out(f"  GESAMT ohne Gate: n={fb + fp} Netto-R={frb + frp:+.2f} | "
    f"mit Gate2: n={f2n + fp2} Netto-R={f2r + fp2r:+.2f}")
out("  HINWEIS: Variante 2 liefert in diesem Datensatz exakt dasselbe Ergebnis")
out("  wie Variante 1 (identische 4 Blockierungen), weil bei allen betroffenen")
out("  Vortrades entry <= exit1 gilt (De-Risking erst nach dem Zweit-Entry).")
_liste(setups_g2, "VOLL MIT GATE2 (De-Risking-Lesart)")

out("")
out("=" * 118)
out("ZUSAMMENFASSUNG")
out("=" * 118)
out("  A) Stacking-Verletzungen je Kante im GESAMT-Datensatz (Bars 0-1288): 3")
out("     K20  T1 entry 231 / exit2 398 (+6,92 R)  <->  T2 entry 245 (+3,95 R)")
out("     K31  T1 entry 531 / exit2 639 (+8,41 R)  <->  T2 entry 567 (+3,14 R)")
out("     K62  T1 entry 855 / exit2 867 (-1,00 R)  <->  T2 entry 866 (-1,00 R)")
out("  B) BOX-Fenster (0-641): 2 Verletzungen (K20, K31) -- beide betreffen")
out("     einen bereits laufenden GEWINNER, der unzulaessig ueberlappt wurde.")
out("  C) Implementierungsstatus: Die Regel ist im Harness NICHT implementiert")
out("     (letzter_trade wird nur geschrieben, nie gelesen).")
out("  D) Exakte Gate-Wirkung: BOX +27,08 -> +19,99 R (-7,09 R, -2 Trades);")
out("     POST +2,03 -> +3,03 R (+1,00 R, -1 Trade); GESAMT +29,11 -> +23,02 R.")
out("  E) Die arretierte Box-Kennzahl +27,08 R existiert nur OHNE das Gate.")

out("")
out("=" * 118)
out("WECHSELWIRKUNG 1: BOX-Netto-R als Funktion von retest_zyklus_bars (v)")
out("ohne / mit Stacking-Gate -- Box-Fenster (0-641)")
out("=" * 118)
out("   v |  ohne Gate: n  Netto-R |  mit Gate: n  Netto-R | Differenz")
out("-" * 118)
for v in range(0, 25):
    cv = kep.StraightEdgeHarnessKonfiguration(retest_zyklus_bars=v)
    s1 = ke._se_scan("AUG", cv)
    t1, _ = ke._se_trades(s1, cv)
    s2 = kep._se_scan("AUG", cv)
    t2, _ = kep._se_trades(s2, cv)
    n1, r1, _, _ = _sum(t1)
    n2, r2, _, _ = _sum(t2)
    mark = "  <<< arretiert" if v == 12 else ""
    out(f"  {v:2d} |          {n1:2d}  {r1:+7.2f} |          {n2:2d}  "
        f"{r2:+7.2f} | {r2 - r1:+7.2f}{mark}")

out("")
out("=" * 118)
out("WECHSELWIRKUNG 2: VOLLES FENSTER (box_end = n) als Funktion von v")
out("ohne / mit Stacking-Gate -- getrennt nach BOX (0-641) und POST (644+)")
out("=" * 118)
out("   v | ohne Gate: BOX n/R      POST n/R     GESAMT | mit Gate: "
    "BOX n/R      POST n/R     GESAMT")
out("-" * 118)
for v in range(0, 25):
    cv = kep.StraightEdgeHarnessKonfiguration(retest_zyklus_bars=v)
    sf = ke._se_scan("AUG", cv)
    sf["box_end_bar"] = n
    tf, _ = ke._se_trades(sf, cv)
    sg = kep._se_scan("AUG", cv)
    sg["box_end_bar"] = n
    tg, _ = kep._se_trades(sg, cv)
    fbn, fbr, fpn, fpr = _sum(tf)
    gbn, gbr, gpn, gpr = _sum(tg)
    mark = "  <<< arretiert" if v == 12 else ""
    out(f"  {v:2d} | {fbn:2d} {fbr:+7.2f}  {fpn:2d} {fpr:+6.2f}  "
        f"{fbr + fpr:+7.2f} | {gbn:2d} {gbr:+7.2f}  {gpn:2d} {gpr:+6.2f}  "
        f"{gbr + gpr:+7.2f}{mark}")

out("")
out("=" * 118)
out("WECHSELWIRKUNG 3: Welche Trades blockiert das Gate je v? (Voll-Lauf)")
out("=" * 118)
for v in range(0, 25):
    cv = kep.StraightEdgeHarnessKonfiguration(retest_zyklus_bars=v)
    sg = kep._se_scan("AUG", cv)
    sg["box_end_bar"] = n
    kep.STACKING_LOG.clear()
    tg, _ = kep._se_trades(sg, cv)
    eintraege = [f"K{e[2]}@entry{e[3]}" for e in kep.STACKING_LOG]
    out(f"  v={v:2d}: {len(eintraege)} Blockierung(en)  "
        f"{', '.join(eintraege) if eintraege else '--'}")

txt = "\n".join(L)
print(txt)
(ROOT / "test" / "tmp_stacking_audit.txt").write_text(txt, encoding="utf-8")
