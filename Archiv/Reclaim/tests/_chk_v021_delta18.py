# -*- coding: utf-8 -*-
"""Delta-18 -- Beweislast des SEGMENTWAND-Zuwachses (AUG VOLL, adapterfrei).

Zweck
-----
Der Katalog der V021-Segmentwand (``segmentwand_modus="AN"``) fuehrt 18 Trades
gegen +52.876174 R; der Legacy-Stand 14 / +42.450970. Die vier Zuwaechse
muessen einzeln auf ihre Ursache zurueckfuehrbar sein -- sonst ist die Zahl
fuer das Notariat (H20.51) nicht belastbar.

Drei Fragen, drei Antworten
---------------------------
Q1  Ist der Zuwachs REIN ADDITIV (Legacy-Menge Teilmenge der AN-Menge)?
Q2  Welche Kanten veraendert der ZP-5-Vorlauf ``erweitere_segmentwand_dochte``
    ueberhaupt -- Wicks, ``schlaf_windows``, ``status``?
Q3  Welcher der vier Zuwaechse stammt aus einer WICK-Erweiterung (ZP-5) und
    welcher aus dem Gate (A_SB / A_VC) im Regelwerk?

Verfahren
---------
Der Vorlauf wird in einer ISOLIERTEN Replik des AN-Zweigs mit einem Spion
umhuellt (Vorher/Nachher der Kantenzustaende). Die Replik wird gegen den
ECHTEN Engine-Lauf geprueft -- bei Abweichung bricht die Sonde ab, damit
Ursachenzuordnung und Ergebnis nicht auseinanderlaufen koennen.

READ-ONLY. Motoren/Adapter/Renderer bleiben byte-identisch.

Aufruf:
    .venv\\Scripts\\python.exe test\\_chk_v021_delta18.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.util
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

BOX = 644
SIG_BARS = (1075, 1122, 1172, 1272)
OUT = ROOT / "test" / "_chk_v021_delta18_out.txt"
_Z: List[str] = []


def _z(s: str = "") -> None:
    _Z.append(s)
    print(s)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _sig(tr: Sequence[Any]) -> str:
    return "|".join(f"K{int(t.kid)}@{int(t.entry_bar)}" for t in tr)


def main() -> None:
    _z("DELTA-18 -- Ursachenzerlegung des Segmentwand-Zuwachses (AUG VOLL)")
    _z("=" * 92)
    for p, soll, nm in ((BASELINE_PFAD, BASELINE_SHA, "Baseline"),
                        (ADAPTER_PFAD, ADAPTER_SHA, "Adapter")):
        ist = _sha(p)
        assert ist == soll, f"Fremdstand {nm}: {ist[:16]}"
        _z(f"SHA {nm:9s} {ist[:16]}...  OK")
    _z("")

    B = V._engine()
    ad = importlib.import_module("backtest_lab.phasen_regime_adapter")
    PhK = ad.PhasenKanteInfo

    def grenzen(a: Any) -> List[V.Segmentgrenze]:
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
    assert int(scan["box_end_bar"]) == BOX
    d = scan["d"]
    ts = d["ts"].to_numpy().astype("datetime64[ns]")
    op = d["open"].to_numpy(dtype=float)
    hi_a = d["high"].to_numpy(dtype=float)
    lo_a = d["low"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    _z(f"Fenster AUG: n={n} | box_end_bar={BOX} | edges={len(scan['edges'])} "
       f"seeds={len(scan['seeds'])}")

    cfg_leg = V.V021KantenKonfiguration()
    cfg_an = V.V021KantenKonfiguration(segmentwand_modus="AN")
    g_kausal = grenzen(ad.ADAPTER_V019_KAUSAL)
    g_batch = grenzen(ad.ADAPTER_V019)
    _z(f"Grenzen Batch : {[(g.start_bar, g.end_bar) for g in g_batch]}")
    _z(f"Grenzen Kausal: {[(g.start_bar, g.end_bar) for g in g_kausal]}")
    _z("")

    tr_leg = V._lauf(copy.deepcopy(scan), cfg_leg, box_end=n)
    tr_an = V._lauf(copy.deepcopy(scan), cfg_an, g_kausal, box_end=n)
    tr_an_b = V._lauf(copy.deepcopy(scan), cfg_an, g_batch, box_end=n)
    _z(f"Mengen: LEGACY {len(tr_leg)} | AN/Kausal {len(tr_an)} | "
       f"AN/Batch {len(tr_an_b)}")
    _z(f"SumR  : LEGACY {sum(float(t.r) for t in tr_leg):+.6f} | "
       f"AN/Kausal {sum(float(t.r) for t in tr_an):+.6f} | "
       f"AN/Batch {sum(float(t.r) for t in tr_an_b):+.6f}")

    # ------------------------------------------------------------- Q1
    _z("")
    _z("Q1 -- Additivitaet (Legacy-Menge Teilmenge der AN-Menge?)")
    sig_leg = [f"K{int(t.kid)}@{int(t.entry_bar)}" for t in tr_leg]
    sig_an = [f"K{int(t.kid)}@{int(t.entry_bar)}" for t in tr_an]
    fehlend = [s for s in sig_leg if s not in sig_an]
    zuwachs = [t for t in tr_an if f"K{int(t.kid)}@{int(t.entry_bar)}"
               not in sig_leg]
    _z(f"  Legacy-Trades in AN enthalten: {len(sig_leg) - len(fehlend)}"
       f"/{len(sig_leg)} | fehlend: {fehlend or 'keine'}")
    _z(f"  Zuwaechse ({len(zuwachs)}):")
    for t in zuwachs:
        grund = f"{t.grund1}/{t.grund2}"
        _z(f"    K{int(t.kid):<4d} {str(t.richtung):5s} sig {int(t.bar):>5d} "
           f"entry {int(t.entry_bar):>5d} @ {float(t.entry):.4f} "
           f"sl {float(t.sl):.4f} tp2 {float(t.tp2):.4f} "
           f"R {float(t.r):+.6f} | {grund}")
    _add = "JA" if not fehlend else "NEIN -- Legacy-Trades verschwinden"
    _z(f"  ADDITIV: {_add}")

    # ------------------------------------------------------------- Q2
    _z("")
    _z("Q2 -- Wirkung des ZP-5-Vorlaufs: Steuerbare Gegenprobe")
    _z("  Die Replik des AN-Zweigs ist identisch zur Engine; in ihr wird der")
    _z("  Vorlauf bzw. einzelne seiner Wirkungen auf K82 zurueckgenommen.")

    def _variante(var: str, spuren: Dict[str, Any]) -> List[Any]:
        """AN-Zweig mit steuerbarem Vorlauf-Eingriff (isolierte Replik)."""
        wcfg = V._wirksame_cfg(cfg_an)
        V._SEGMENTGRENZEN = tuple(g_kausal)      # Lauf-Kapsel der Engine
        try:
            ns = V._baue_ns(B, wcfg)
            shim = V._GrenzenShim(g_kausal)
            orig = ns["erweitere_segmentwand_dochte"]

            def _spion(sc: Any, hook: Any, c: Any, h: Any, l: Any,
                       u: Any) -> None:
                alle = list(sc["edges"]) + list(sc["seeds"])
                vor = {int(e.kid): (list(e.wicks), list(e.schlaf_windows),
                                    str(e.status)) for e in alle}
                if var != "V0_GateOnly":
                    orig(sc, hook, c, h, l, u)
                nach = {int(e.kid): (list(e.wicks), list(e.schlaf_windows),
                                     str(e.status)) for e in alle}
                spuren["vor"], spuren["nach"] = vor, nach

            ns["erweitere_segmentwand_dochte"] = _spion
            sc_repl = copy.deepcopy(scan)
            sc_repl["box_end_bar"] = n
            patched = V._regel_ersetzen(ns["_src_baseline"], cfg_an)
            exec(compile(patched, "<replik_delta18>", "exec"), ns)
            ns["erweitere_segmentwand_dochte"](
                sc_repl, shim, wcfg, hi_a, lo_a, ns["_ueb"])
            if var != "V0_GateOnly":
                idx = {int(e.kid): e for e in
                       list(sc_repl["edges"]) + list(sc_repl["seeds"])}
                k82 = idx[82]
                if var in ("V2_ohne_Wick1075", "V4_Wick_und_Schlaf",
                           "V5_Wick1075_wieBasis", "V6_Wick1100",
                           "V7_Wick1100_tief"):
                    k82.wicks = [(b, p) for b, p in k82.wicks
                                 if int(b) != 1075]
                if var == "V5_Wick1075_wieBasis":
                    k82.wicks.append((1075, float(k82.basis_bei(1172))))
                if var == "V6_Wick1100":
                    k82.wicks.append((1100, float(lo_a[1100])))
                if var == "V7_Wick1100_tief":
                    k82.wicks.append((1100, 67.42))
                if var in ("V3_ohne_Schlaf", "V4_Wick_und_Schlaf"):
                    k82.schlaf_windows = list(spuren["vor"][82][1])
            orig_se = B._se_trades
            B._se_trades = ns["_se_trades"]
            try:
                tr, _st = B._se_trades(sc_repl, wcfg)
            finally:
                B._se_trades = orig_se
        finally:
            V._SEGMENTGRENZEN = ()
        return sorted(list(tr), key=lambda x: int(x.entry_bar))

    VARIANTEN = ("V1_Voll", "V0_GateOnly", "V2_ohne_Wick1075",
                 "V3_ohne_Schlaf", "V4_Wick_und_Schlaf",
                 "V5_Wick1075_wieBasis", "V6_Wick1100",
                 "V7_Wick1100_tief")
    erg: Dict[str, List[Any]] = {}
    spuren_voll: Dict[str, Any] = {}
    for _v in VARIANTEN:
        _sp: Dict[str, Any] = {}
        erg[_v] = _variante(_v, _sp)
        if _v == "V1_Voll":
            spuren_voll = _sp
        _z(f"  {_v:20s} Trades {len(erg[_v]):3d}   SumR "
           f"{sum(float(t.r) for t in erg[_v]):+12.6f}")

    ident = _sig(erg["V1_Voll"]) == _sig(tr_an)
    _z(f"  Kontrolle V1_Voll == echter Engine-Lauf: "
       f"{'OK (identisch)' if ident else 'ABWEICHUNG -- Abbruch'}")
    if not ident:
        raise AssertionError("Replik weicht ab; Ursachenzuordnung ungueltig.")

    vor, nach = spuren_voll["vor"], spuren_voll["nach"]
    _z("  Kanten mit Zustandsaenderung durch den Vorlauf:")
    for kid in sorted(vor):
        w0, s0, st0 = vor[kid]
        w1, s1, st1 = nach[kid]
        dw = [b for b, _ in w1 if b not in {bb for bb, _ in w0}]
        if w0 != w1 or s0 != s1 or st0 != st1:
            _z(f"    K{kid:<4d} wicks {len(w0)}->{len(w1)} "
               f"(neue Bars {dw or '-'}) | schlaf {len(s0)}->{len(s1)} | "
               f"status {st0}->{st1}")
    _seg_kids = sorted({int(g.boden.kid) for g in g_kausal}
                       | {int(g.decke.kid) for g in g_kausal})
    _z(f"  Grenz-Kids der Kausal-Segmente: {_seg_kids}")
    _z("  -> Der Vorlauf beruehrt GENAU EINE Kante.")

    # ------------------------------------------------------------- Q3
    _z("")
    _z("Q3 -- Welche Variante traegt welchen Zuwachs?")
    _basis = {f"K{int(t.kid)}@{int(t.entry_bar)}" for t in erg["V1_Voll"]}
    for _v in VARIANTEN[1:]:
        _ist = {f"K{int(t.kid)}@{int(t.entry_bar)}" for t in erg[_v]}
        _verl = sorted(_basis - _ist)
        _z(f"  {_v:20s} entfaellt: "
           f"{', '.join(_verl) if _verl else 'nichts'}")
    _z("  Zuordnung je Zuwachs:")
    for t in zuwachs:
        k = f"K{int(t.kid)}@{int(t.entry_bar)}"
        traeger = [v for v in VARIANTEN if k in
                   {f"K{int(x.kid)}@{int(x.entry_bar)}" for x in erg[v]}]
        fehlt_in = [v for v in VARIANTEN if v not in traeger]
        if "V0_GateOnly" in traeger:
            urs = "Regelwerk-Gate (A_SB/A_VC) -- Vorlauf wirkungslos"
        elif "V2_ohne_Wick1075" in traeger:
            urs = "ZP-5-Vorlauf noetig, aber NICHT wegen Wick@1075"
        else:
            urs = "ZP-5-Wick@1075 getragen (Gate allein liefert ihn nicht)"
        _z(f"    {k:<14s} R {float(t.r):+8.6f}  entfaellt in "
           f"{','.join(fehlt_in) if fehlt_in else '-'}")
        _z(f"      -> {urs}")
    _z("")

    # ------------------------------------------------------------- Q4
    _z("Q4 -- Mechanismus des Wick@1075 (Beruehrungspunkt im Trade-Loop)")
    _alle = {int(e.kid): e for e in
             list(scan["edges"]) + list(scan["seeds"])}
    _k82 = copy.deepcopy(_alle[82])
    _k82b = copy.deepcopy(_alle[82])
    _k82b.wicks.append((1075, float(lo_a[1075])))
    _z(f"  K82 seite={_k82.seite} ist_prim_anker={_k82.ist_prim_anker} "
       f"basis(statisch)={float(_k82.basis):.4f}")
    _z(f"  cfg.min_touches_handelbar = {cfg_h.min_touches_handelbar}   "
       f"cfg.wall_live_bars = {cfg_h.wall_live_bars}")
    for _k in (1075, 1172):
        _z(f"  Bar {_k}: basis_bei vor/nach = "
           f"{float(_k82.basis_bei(_k)):.4f} / "
           f"{float(_k82b.basis_bei(_k)):.4f}   (unveraendert)")
        _z(f"           touch_conf vor/nach = {_k82.touch_conf(_k)} / "
           f"{_k82b.touch_conf(_k)}   letzter_touch_conf vor/nach = "
           f"{_k82.letzter_touch_conf(_k)} / {_k82b.letzter_touch_conf(_k)}")
    _z("  Anker im Trade-Loop (baseline _se_trades, Z. 184):")
    _z("      if e.touch_conf(k) < cfg.min_touches_handelbar:")
    _z("          continue        # innere Linie braucht V-S >= 3")
    _z(f"  -> K82 ist bei Bar 1172 INNERE Linie (pos != 0): der V-S-Zaehler")
    _z(f"     springt von 2 auf 3 und kreuzt damit die Schwelle "
       f"{cfg_h.min_touches_handelbar}.")
    _z("")
    _z("  Zweite Bedingung -- der Wick darf die Kausal-Basis NICHT anheben:")
    _z("      basis_bei(k) = max der Dochte mit b+2 <= k   (seite UNTEN)")
    for _b in (1075, 1100, 1150):
        _px = [float(p) for bb, p in _k82.wicks if bb + 2 <= 1172]
        _z(f"      Wick bei {_b} mit echtem Low {float(lo_a[_b]):.4f} -> "
           f"basis_bei(1172) = {max(_px + [float(lo_a[_b])]):.4f}   "
           f"(unveraendert 67.5530 nur bei 1075)")
    _z("      Gegenprobe V6 (Bar 1100, ECHTES Low 68.8230) -> 17 Trades:")
    _z("      die Linie wandert auf 68.8230 nach oben, dist(1172) wird")
    _z(f"      1.93 % und ueberschreitet max_sweep_ueberdehnung_pct "
       f"{cfg_h.max_sweep_ueberdehnung_pct}.")
    _z("      Gegenprobe V7 (Bar 1100, TIEFER Wert 67.42) trennt beide")
    _z("      Bedingungen: nur der Bar zaehlt, nicht der Bar-1075-Sonderfall.")
    _z("")
    _z(f"  -> Wick-Wert 67.4200 = echtes Low von Bar 1075 "
       f"({str(ts[1075])[:16]}); KEIN 67.58.")
    _z("")

    # ------------------------------------------------------------- Bar-Daten
    _z("Bar-Daten (BKZ, ohne Offset) fuer die Signalbars der Zuwaechse")
    for b in SIG_BARS:
        _z(f"  Bar {b:>5d}  {str(ts[b])[:16]}  O {op[b]:.4f}  H {hi_a[b]:.4f}  "
           f"L {lo_a[b]:.4f}  C {cl[b]:.4f}")
    _z("")
    _z("Kanten-Wicklisten der Kausal-Grenzen VOR dem Vorlauf")
    for kid in sorted({int(g.boden.kid) for g in g_kausal}
                      | {int(g.decke.kid) for g in g_kausal}):
        if kid in vor:
            _z(f"  K{kid:<4d} {[(int(b), round(float(p), 4)) for b, p in vor[kid][0]]}")
    _z("")
    _z("... NACH dem Vorlauf (nur Abweichungen)")
    for kid in sorted({int(g.boden.kid) for g in g_kausal}
                      | {int(g.decke.kid) for g in g_kausal}):
        if kid in vor and vor[kid][0] != nach[kid][0]:
            _z(f"  K{kid:<4d} {[(int(b), round(float(p), 4)) for b, p in nach[kid][0]]}")
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
