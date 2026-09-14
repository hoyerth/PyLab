# -*- coding: utf-8 -*-
"""Sichtungs-Begleitprotokoll zu ``test/render_aug_v021.png`` (read-only).

Zweck
-----
Die Bildabnahme (F2, Anwender) soll nicht am Auge allein haengen. Diese Sonde
liefert die Datenseite zu den vier Zuwaechsen des 18er-Katalogs:

1. Zuordnung jeder Kante zu den ACHT Anwender-Linien (naechstgelegene Kante
   je Linie, gemessen an ``basis`` UND an ``basis_bei(entry)``).
2. Reclaim-Evidenz je Zuwachs: Bar-OHLC am Signalbars, kausale Basis,
   Durchstichweite in Prozent, Touch-Zaehler, Reclaim-Bedingung (A_SB).
3. Kennzeichnung, ob die getragene Kante UEBERHAUPT eine Anwender-Linie ist.

Keine Bewertung, keine Mutation. Motoren/Adapter/Renderer byte-identisch.

Aufruf:
    .venv\\Scripts\\python.exe test\\_chk_v021_sicht_beiwerk.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

V = importlib.import_module("tmp_kanten_engine_v021_replay")

BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
ADAPTER_PFAD = ROOT / "backtest_lab" / "phasen_regime_adapter.py"
BASELINE_SHA = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
ADAPTER_SHA = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")

PNG = ROOT / "test" / "render_aug_v021.png"
BOX = 644
ZUWAECHSE: Tuple[int, ...] = (1077, 1123, 1173, 1273)

# Anwender-Vorgaben 1:1 aus test/_render_aug_v021.py (LINIEN).
LINIEN: Tuple[Tuple[str, str, float], ...] = (
    ("upper 66.46", "OBEN", 66.46), ("lower 63.67", "UNTEN", 63.67),
    ("lower-min 64.20", "UNTEN", 64.20), ("Upper1 69.90", "OBEN", 69.90),
    ("Upper2 69.62", "OBEN", 69.62), ("Lower1 68.88", "UNTEN", 68.88),
    ("Lower2 68.40", "UNTEN", 68.40), ("Lower3 67.60", "UNTEN", 67.60),
)

OUT = ROOT / "test" / "_chk_v021_sicht_beiwerk_out.txt"
_Z: List[str] = []


def _z(s: str = "") -> None:
    _Z.append(s)
    print(s)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _png_info(p: Path) -> str:
    """Breite/Hoehe aus dem IHDR-Chunk (read-only, kein Bilddecoder)."""
    b = p.read_bytes()
    if b[:8] != b"\x89PNG\r\n\x1a\n":
        return "kein gueltiges PNG-Signatur"
    w = int.from_bytes(b[16:20], "big")
    h = int.from_bytes(b[20:24], "big")
    return f"{w} x {h} px | {len(b)} B | sha256 {hashlib.sha256(b).hexdigest()[:16]}"


def main() -> None:
    _z("SICHTUNGS-BEGLEITPROTOKOLL -- render_aug_v021.png (AUG VOLL, AN/Kausal)")
    _z("=" * 96)
    for p, soll, nm in ((BASELINE_PFAD, BASELINE_SHA, "Baseline"),
                        (ADAPTER_PFAD, ADAPTER_SHA, "Adapter")):
        ist = _sha(p)
        assert ist == soll, f"Fremdstand {nm}: {ist[:16]}"
        _z(f"SHA {nm:9s} {ist[:16]}...  OK")
    _z(f"PNG    {PNG.name:28s} {_png_info(PNG)}")
    _z("")

    B = V._engine()
    ad = importlib.import_module("backtest_lab.phasen_regime_adapter")
    PhK = ad.PhasenKanteInfo

    def grenzen(a: Any) -> List[Any]:
        return [V.Segmentgrenze(
            start_bar=int(s.start_bar), end_bar=int(s.end_bar),
            boden=PhK(kid=int(s.boden.kid),
                      provenienz_basis=float(s.boden.provenienz_basis)),
            decke=PhK(kid=int(s.decke.kid),
                      provenienz_basis=float(s.decke.provenienz_basis)),
            boden_deklariert_literal=s.boden_deklariert_literal)
            for s in a.segmente]

    cfg_h = B.StraightEdgeHarnessKonfiguration()
    scan = B._se_scan("AUG", cfg_h)
    n = int(scan["n"])
    d = scan["d"]
    ts = d["ts"].to_numpy().astype("datetime64[ns]")
    op = d["open"].to_numpy(dtype=float)
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    alle = list(scan["edges"]) + list(scan["seeds"])
    idx = {int(e.kid): e for e in alle}
    g_kausal = grenzen(ad.ADAPTER_V019_KAUSAL)

    tr = V._lauf(copy.deepcopy(scan), V.V021KantenKonfiguration(
        segmentwand_modus="AN"), g_kausal, box_end=n)
    assert len(tr) == 18, f"Trades {len(tr)} != 18"

    # ------------------------------------------------- A) Linien-Zuordnung
    _z("A) ZUORDNUNG DER ACHT ANWENDER-LINIEN ZU DEN SCAN-KANTEN")
    _z("   (naechstgelegene Kante je Linie; 'basis' = statische Provenienz)")
    _z("")
    _z(f"   {'Anwender-Linie':18s} {'Seite':6s} {'Preis':>8s}   "
       f"{'naechste Kante':>14s} {'Seite':6s} {'basis':>8s} {'dw%':>7s}  "
       f"{'Wicks':>5s}  {'prim':>4s}")
    used: Dict[int, str] = {}
    for nm, seite, px in LINIEN:
        kandidaten = [e for e in alle if str(e.seite) == seite]
        e = min(kandidaten, key=lambda x: abs(float(x.basis) - px))
        dw = (float(e.basis) - px) / px * 100.0
        used[int(e.kid)] = nm
        _z(f"   {nm:18s} {seite:6s} {px:8.2f}   K{int(e.kid):<12d} "
           f"{str(e.seite):6s} {float(e.basis):8.4f} {dw:+7.3f}  "
           f"{len(e.wicks):5d}  {'ja' if e.ist_prim_anker else 'nein':>4s}")
    _z("")
    _z(f"   Von den 8 Linien belegte Kids: "
       f"{sorted(used)}")
    _z("")

    # ------------------------------------------------- B) Zuwaechse
    _z("B) RECLAIM-EVIDENZ DER VIER ZUWAECHSE (Step-2-Kern)")
    _z("")
    for t in tr:
        if int(t.entry_bar) not in ZUWAECHSE:
            continue
        kid, sig, ent = int(t.kid), int(t.bar), int(t.entry_bar)
        e = idx[kid]
        seite = str(e.seite)
        kurz = (float(hi[sig]) if seite == "OBEN" else float(lo[sig]))
        basis = float(e.basis_bei(sig))
        dw = (kurz - basis) / basis * 100.0
        linie = used.get(kid, "-")
        # A_SB-Reclaim-Bedingung (Regel: Durchstich gegen die kausale Basis)
        if seite == "OBEN":
            reclaim = float(hi[sig]) > basis
            richtung_bedingung = f"hi[{sig}] {hi[sig]:.4f} > basis {basis:.4f}"
        else:
            reclaim = float(lo[sig]) < basis
            richtung_bedingung = f"lo[{sig}] {lo[sig]:.4f} < basis {basis:.4f}"
        _z(f"   --- Zuwachs K{kid} {str(t.richtung)} | sig {sig} -> entry {ent} "
           f"| R {float(t.r):+.6f} | Exit {t.grund1}/{t.grund2}")
        _z(f"       Anwender-Linie? {linie}   Seite {seite}   "
           f"Primaer-Anker: {'ja' if e.ist_prim_anker else 'nein'}   "
           f"erster_pivot_bar {int(e.erster_pivot_bar)}")
        _z(f"       Bar {sig} ({str(ts[sig])[:16]}): O {op[sig]:.4f} "
           f"H {hi[sig]:.4f} L {lo[sig]:.4f} C {cl[sig]:.4f}")
        _z(f"       Kausale Basis basis_bei({sig}) = {basis:.4f}   "
           f"Basis statisch = {float(e.basis):.4f}   "
           f"(Differenz {(float(e.basis) - basis):+.4f})")
        _z(f"       Durchstich: {richtung_bedingung}  ->  {dw:+.4f} %  "
           f"| A_SB-Reclaim erfuellt: {reclaim}")
        _z(f"       touch_conf({sig}) = {e.touch_conf(sig)}   "
           f"(Schwelle {cfg_h.min_touches_handelbar}, "
           f"nur bei INNERER Linie relevant)   "
           f"letzter_touch_conf = {e.letzter_touch_conf(sig)}  "
           f"(Alter {sig - e.letzter_touch_conf(sig)} / "
           f"wall_live_bars {cfg_h.wall_live_bars})")
        _z(f"       Wicks gesamt: {len(e.wicks)}  ->  "
           f"{[(int(b), round(float(p), 4)) for b, p in e.wicks]}")
        _z(f"       Entry-Preis {float(t.entry):.4f}   sl {float(t.sl):.4f}   "
           f"tp2 {float(t.tp2):.4f}   poc {float(t.poc):.4f}   "
           f"Risiko {abs(float(t.sl) - float(t.entry)):.4f} USD")
        _z(f"       Setup: basis {float(t.basis):.4f}   "
           f"sweep {float(t.sweep):.4f}   "
           f"trigger_close {float(t.trigger_close):.4f}   "
           f"touch_n {int(t.touch_n)}   stufe {t.stufe}   "
           f"reclaim_bar {int(t.reclaim_bar)}   "
           f"ist_prim_anker {bool(t.ist_prim_anker)}")
        _z(f"       Realisierung: {t.resultat}   r1 {float(t.r1):+.6f} "
           f"(exit {int(t.exit1_bar)}) / r2 {float(t.r2):+.6f} "
           f"(exit {int(t.exit2_bar)})")
        _z("")

    # ------------------------------------------------- C) Segmentgrenzen
    _z("C) SEGMENTGRENZEN IM BILD (Kausal) -- vertikale Linien im Renderer")
    for g in g_kausal:
        _z(f"   Bar {g.start_bar:>5d} .. {g.end_bar:>5d}  "
           f"({str(ts[g.start_bar])[:16]} .. {str(ts[g.end_bar])[:16]})   "
           f"boden K{int(g.boden.kid)}  decke K{int(g.decke.kid)}  "
           f"literal {g.boden_deklariert_literal}")
    _z("")
    _z("D) VERORTUNG DER ZUWAECHSE IM SEGMENTRASTER")
    for t in tr:
        if int(t.entry_bar) not in ZUWAECHSE:
            continue
        sig = int(t.bar)
        seg = [g for g in g_kausal if g.start_bar <= sig <= g.end_bar]
        _z(f"   K{int(t.kid):<4d} sig {sig:>5d}  ->  "
           f"{'Segment ' + str((seg[0].start_bar, seg[0].end_bar)) if seg else 'AUSSERHALB aller Segmente'}"
           f"   {'(Ankersegment P9)' if seg and seg[0].start_bar == g_kausal[0].start_bar else ''}")
    _z("")
    _z("E) FENSTERRAND-ANTEIL (ENDE-Glattstellung) -- Sichtungsvorbehalt")
    _z("   Der VOLL-Lauf setzt box_end_bar = n; offene Positionen werden am")
    _z("   letzten Bar (1287) zu close[-1] geschlossen und als R gebucht.")
    _z("   Im Bild sind das die MAGENTA RINGE. Anteil je Halftrade = r/2.")
    _z("")
    _z(f"   {'Kante':>6s} {'sig':>6s} {'R':>12s} {'r1':>12s} {'g1':>5s} "
       f"{'r2':>12s} {'g2':>5s} {'ENDE-R':>12s} {'markterprobt':>13s}")
    _ende_ges = 0.0
    _mark_ges = 0.0
    _ende_zuw = 0.0
    _mark_zuw = 0.0
    for t in tr:
        e_anteil = 0.0
        m_anteil = 0.0
        for _r, _g in ((float(t.r1), str(t.grund1)),
                       (float(t.r2), str(t.grund2))):
            if _g == "ENDE":
                e_anteil += 0.5 * _r
            else:
                m_anteil += 0.5 * _r
        _ende_ges += e_anteil
        _mark_ges += m_anteil
        if int(t.entry_bar) in ZUWAECHSE:
            _ende_zuw += e_anteil
            _mark_zuw += m_anteil
        _z(f"   K{int(t.kid):<5d} {int(t.bar):>6d} {float(t.r):+12.6f} "
           f"{float(t.r1):+12.6f} {str(t.grund1):>5s} "
           f"{float(t.r2):+12.6f} {str(t.grund2):>5s} "
           f"{e_anteil:+12.6f} {m_anteil:+13.6f}")
    _sum = sum(float(t.r) for t in tr)
    _z("")
    _z(f"   Gesamt-SumR (18 Trades)          : {_sum:+12.6f}")
    _z(f"   davon ENDE-Glattstellung         : {_ende_ges:+12.6f}  "
       f"({100.0 * _ende_ges / _sum:.1f} %)")
    _z(f"   davon markterprobt (TP1/TP2/SL)  : {_mark_ges:+12.6f}  "
       f"({100.0 * _mark_ges / _sum:.1f} %)")
    _z("")
    _z(f"   Zuwachs-Delta (4 Trades)         : "
       f"{_ende_zuw + _mark_zuw:+12.6f}")
    _z(f"   davon ENDE-Glattstellung         : {_ende_zuw:+12.6f}  "
       f"({100.0 * _ende_zuw / (_ende_zuw + _mark_zuw):.1f} %)")
    _z(f"   davon markterprobt (TP1/TP2/SL)  : {_mark_zuw:+12.6f}  "
       f"({100.0 * _mark_zuw / (_ende_zuw + _mark_zuw):.1f} %)")
    _z("")
    _z(f"PROTOKOLL: {OUT}")


if __name__ == "__main__":
    _fehler = False
    try:
        main()
    except BaseException as exc:                    # noqa: BLE001
        _fehler = True
        import traceback
        tb = traceback.format_exc()
        sys.stderr.write(tb)
        _Z.append(f"\nABBRUCH: {type(exc).__name__}: {exc}\n\n{tb}")
    OUT.write_text("\n".join(_Z) + "\n", encoding="utf-8", newline="\n")
    print(f"\nFehler={_fehler}")
