# -*- coding: utf-8 -*-
"""SONDE Schritt 1 -- ZP-4/ZP-5-Segmentwand adapterfrei, quellentreu (read-only).

Kein Import von tmp_png_aug_sichttest.py (Modul-Level argparse -> SystemExit).
Stattdessen AST-Extraktion (B1) + synthetischer Namespace (B2) + Nullprobe
1 vs. 3 Segmente (B3). Motoren/Adapter bleiben byte-identisch; jeder Lauf auf
frischer copy.deepcopy(scan) (H20.50 Abschnitt 3).

Sollwerte (arretiert): V0 14/+42.450970 | V1_basis 14/+47.815697 (ZP inert)
| V1_aktiv 17/+65.835576 mit H1 8/+38.919584 und H2 9/+26.915992.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import importlib.util
import sys
import typing
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TEST = ROOT / "test"
sys.path.insert(0, str(ROOT))

BASELINE = TEST / "tmp_kanten_engine_replay.py"
RENDERER = TEST / "tmp_png_aug_sichttest.py"
BASELINE_SHA = ("53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
RENDERER_SHA = ("500b55762001d6667af3d977324c81eb4ecbceacc2fa0d8b62c36c7e383250e0")
BOX_AUG = 644
SOLL = {
    # (n, R, H1_n, H1_R, H2_n, H2_R) -- alle VOLL-Lauf, Split bei Kalenderkante 644
    "V0": (14, +42.450970, 8, +38.919584, 6, +3.531386),
    "V1_basis": (14, +47.815697, 8, +38.919584, 6, +8.896113),
    # ZP-5(D) eingebrannt (E-34n/13): Batch-Adapter ADAPTER_V019
    "V1_batch": (24, +88.116626, 8, +38.919584, 16, +49.197042),
    # V019-SSoT (H20.50 Abschnitt 2/6): ADAPTER_V019_KAUSAL (LIVE-Rendererpfad)
    "V1_kausal": (23, +85.577150, 8, +38.919584, 15, +46.657566),
}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load(name: str, p: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(p)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# =========================================================== 1) AST-Extraktion
def _extrahiere(quelle: str, funktionen: Sequence[str]) -> str:
    """Quelltexte der benannten Funktionen, verbatim, in Dateireihenfolge."""
    tree = ast.parse(quelle)
    treffer = {n.name: n for n in tree.body
               if isinstance(n, ast.FunctionDef) and n.name in funktionen}
    fehlend = set(funktionen) - set(treffer)
    assert not fehlend, f"AST-Anker fehlt: {sorted(fehlend)}"
    return "\n\n".join(
        ast.get_source_segment(quelle, treffer[n]) for n in funktionen)


def _extrahiere_patchbasis(quelle: str) -> str:
    """A_*-Konstanten + Guard-Loop + patched_src-Zuweisung, verbatim."""
    tree = ast.parse(quelle)
    namen = {"A_KANTEN", "A_LOOP", "A_POOL", "A_DIST", "A_M6_BASIS_K",
             "A_M6_BASIS", "A_M6_RET", "A_M6_SORT", "A_M6_SORT2",
             "A_M6_OBEN", "A_M6_UNTEN", "A_TP2", "A_KBASIS"}
    i0 = next(i for i, n in enumerate(tree.body)
              if isinstance(n, ast.Assign)
              and getattr(n.targets[0], "id", None) in namen)
    i1 = next(i for i, n in enumerate(tree.body)
              if isinstance(n, ast.Assign)
              and getattr(n.targets[0], "id", None) == "patched_src")
    assert i0 < i1, "Patchbasis-Reihenfolge verletzt"
    # get_source_segment liefert fuer ein Module-Node None -> Statements
    # einzeln segmentieren (verbatim, Reihenfolge erhalten).
    teile = [ast.get_source_segment(quelle, n) for n in tree.body[i0:i1 + 1]]
    assert all(t is not None for t in teile), "Patchbasis nicht segmentierbar"
    return "\n".join(t for t in teile if t is not None)


# ================================================ 2) Synthetischer Namespace
class _Konf:
    """Minimal-Stellvertreter der Renderer-Konfiguration (nur ``mode``)."""

    def __init__(self, mode: str = "V019") -> None:
        self.mode = mode


def _ns_bauen(engine: Any, adapter: Any,
              ueberdehnung_segment_pct: float = 0.80) -> Dict[str, Any]:
    """Namespace fuer den Patchtext.

    ``cfg`` ist eine frozen-Subklasse der Engine-Konfiguration, die den
    12. Vertragspunkt (``ueberdehnung_segment_pct``) traegt. In V021 ist ``cfg``
    direkt ``V021KantenKonfiguration``; der Patchtext ``cfg.ueberdehnung_
    segment_pct`` bleibt damit in beiden Welten wortgleich.
    """
    @dataclasses.dataclass(frozen=True, slots=True)
    class SonnenCfg(engine.StraightEdgeHarnessKonfiguration):  # type: ignore
        ueberdehnung_segment_pct: float = 0.80

    cfg = SonnenCfg(ueberdehnung_segment_pct=ueberdehnung_segment_pct)
    ns: Dict[str, Any] = dict(engine.__dict__)
    ns.update({
        "cfg": cfg,
        "engine": engine,
        "np": np,
        "copy": copy,
        "dataclasses": dataclasses,
        "KONF": _Konf("V019"),
        "Callable": typing.Callable,
        "Sequence": typing.Sequence,
        "_RS_ORIG": engine._reclaim_stufe,
        "_ZZ_START": adapter.segmente[1].start_bar,
        "_ZZ_ENDE": adapter.segmente[-1].end_bar,
        "_P9_START": adapter.segmente[0].start_bar,
        "_P9_ENDE": adapter.segmente[0].end_bar,
        "_hook": adapter,
    })
    ns["ns"] = ns                      # _zv liest ns["_hook"] (Selbstbezug)
    return ns


def _zwo_siebzig_ersetzen(text: str) -> str:
    """12. Vertragspunkt: die beiden 0.80-CODE-Literale -> cfg.ueberdehnung_segment_pct.

    Bewusster, gegengepruefter Anker-Ersatz (K-C). Ohne diese Ersetzung waere
    ``ueberdehnung_segment_pct`` ein stiller No-Op. Nicht ersetzt werden die
    drei 0.80-Nennungen in Kommentaren/Docstrings (dokumentarisch, korrekt).

    Raises:
        AssertionError: ein Code-Anker kommt nicht genau einmal vor.
    """
    anker = (
        ("_ueb-Rumpf",
         "return 0.80 if _zv(kk) else cfg.max_sweep_ueberdehnung_pct",
         "return cfg.ueberdehnung_segment_pct if _zv(kk) else "
         "cfg.max_sweep_ueberdehnung_pct"),
        ("_reclaim_stufe_lok-Rumpf",
         "max_sweep_ueberdehnung_pct=0.80)",
         "max_sweep_ueberdehnung_pct=cfg.ueberdehnung_segment_pct)"),
    )
    for _nm, _alt, _neu in anker:
        n = text.count(_alt)
        assert n == 1, f"0.80-Code-Anker '{_nm}' nicht eindeutig ({n})"
        text = text.replace(_alt, _neu)
    assert "_zv(kk) else" in text
    return text


# ============================================================== 3) Der Lauf
def _lauf(ns: Dict[str, Any], patched_src: str, scan: Dict[str, Any],
          hook: Any, mit_patch: bool) -> Tuple[List[Any], Dict[str, Any]]:
    """Ein Lauf -- exakt wie Renderer ``_lauf`` (L979-1002).

    Reihenfolge INTERN (P1/I5): deepcopy -> Segmentwand-Vorlauf -> Handel.
    """
    ns["_hook"] = hook
    exec(compile(patched_src, "<se_trades_sonde>", "exec"), ns)
    sc_copy = copy.deepcopy(scan)                       # I6: vollstaendig
    if not mit_patch:
        return ns["ORIG"](sc_copy, ns["cfg"])
    if ns["KONF"].mode == "V019" and len(getattr(hook, "segmente", ())) > 1:
        ns["erweitere_segmentwand_dochte"](
            sc_copy, hook, ns["cfg"],
            sc_copy["d"]["high"].to_numpy(dtype=float),
            sc_copy["d"]["low"].to_numpy(dtype=float),
            ns["_ueb"])
    engine = ns["engine"]
    engine._se_trades = ns["_se_trades"]
    try:
        return engine._se_trades(sc_copy, ns["cfg"])
    finally:
        engine._se_trades = ns["ORIG"]


def _ber(tr: Sequence[Any], box: int = BOX_AUG) -> Tuple[int, float,
                                                         int, float,
                                                         int, float]:
    h1 = [float(t.r) for t in tr if int(t.entry_bar) < box]
    h2 = [float(t.r) for t in tr if int(t.entry_bar) >= box]
    return (len(tr), sum(float(t.r) for t in tr),
            len(h1), sum(h1), len(h2), sum(h2))


def main() -> None:
    assert _sha(BASELINE) == BASELINE_SHA, "Baseline-Fremdstand"
    assert _sha(RENDERER) == RENDERER_SHA, "Renderer-Fremdstand"
    print("SHAs OK: Baseline 53f28e1b / Renderer 500b5576")

    quell_renderer = RENDERER.read_text(encoding="utf-8")
    quell_basis = BASELINE.read_text(encoding="utf-8")
    B = _load("basis_sonde", BASELINE)

    adapter_mod = _load("pradapter_sonde",
                        ROOT / "backtest_lab" / "phasen_regime_adapter.py")
    PhasenKanteInfo = adapter_mod.PhasenKanteInfo
    ADAPTER_V019 = adapter_mod.ADAPTER_V019
    ADAPTER_V019_KAUSAL = adapter_mod.ADAPTER_V019_KAUSAL
    DEFAULT_ADAPTER = adapter_mod.DEFAULT_ADAPTER
    print(f"Adapter: V019 segmente={len(ADAPTER_V019.segmente)} | "
          f"V019_KAUSAL segmente={len(ADAPTER_V019_KAUSAL.segmente)} | "
          f"DEFAULT segmente={len(DEFAULT_ADAPTER.segmente)} | "
          f"PhasenKanteInfo={PhasenKanteInfo.__name__} "
          f"({len(dataclasses.fields(PhasenKanteInfo))} Felder)")

    tree = ast.parse(quell_basis)
    node = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "_se_trades")
    enginesrc = ast.get_source_segment(quell_basis, node)
    assert enginesrc is not None

    zp_src = _extrahiere(quell_renderer,
                        ("_wende_zielzonen_patches_v019", "_zv", "_ueb",
                         "_reclaim_stufe_lok", "erweitere_segmentwand_dochte"))
    # 12. Vertragspunkt: die beiden 0.80-Literale sitzen in _ueb (L905) und
    # _reclaim_stufe_lok (L914) -- also im HELFER-Text, nicht im Patchtext.
    zp_src = _zwo_siebzig_ersetzen(zp_src)
    basis_src = _extrahiere_patchbasis(quell_renderer)
    print(f"AST: _se_trades {len(enginesrc)} B | ZP-Helfer {len(zp_src)} B | "
          f"Patchbasis {len(basis_src)} B")

    ns = _ns_bauen(B, ADAPTER_V019)
    ns["src"] = enginesrc
    ns["ORIG"] = B._se_trades
    # Renderer L879: der Enum wird per Namens-Injektion gebunden (A_TP2).
    ns["_Hook2ZielModus"] = adapter_mod.Hook2ZielModus
    exec(compile(basis_src, "<patchbasis>", "exec"), ns)
    exec(compile("from __future__ import annotations\n" + zp_src,
                 "<zp_helper>", "exec"), ns)
    patched = ns["_wende_zielzonen_patches_v019"](ns["patched_src"])
    assert patched.count("_ueb(k)") == 1, "ZP-A_UEB1 (Ueberdehnung) fehlt"
    # Drei ZP-4-Regeln haengen am Laufzeit-Gate _zv(k): A_VC (Quartil-Reset),
    # A_M6L (M6-Schlaf-Filter), A_SB (gesweepte Linie zaehlt als aktiv).
    assert patched.count("_zv(k)") == 3, "ZP-Gate _zv(k) unvollstaendig"
    print(f"Patchkette: 13 A_*-Patches + 4 ZP-4-Regeln -> {len(patched)} B "
          f"| _ueb(k) {patched.count('_ueb(k)')}x | _zv(k) "
          f"{patched.count('_zv(k)')}x | _lebt {patched.count('_lebt(e, k)')}x "
          f"(0.80 -> cfg.ueberdehnung_segment_pct)")

    scan = B._se_scan("AUG", ns["cfg"])
    assert int(scan["box_end_bar"]) == BOX_AUG, scan["box_end_bar"]
    # Renderer L630: Voll-Lauf (arretierte Basis) -- box_end_bar := n.
    # Die Sollwerte V0 14/+42.450970 und V1_aktiv 17/+65.835576 gelten fuer
    # den VOLL-Lauf; der H1/H2-Split bleibt bei der Kalenderkante 644.
    scan["box_end_bar"] = int(scan["n"])
    alle = list(scan["edges"]) + list(scan["seeds"])
    print(f"Scan: n={scan['n']} box=VOLL({scan['box_end_bar']}) "
          f"edges={len(scan['edges'])} seeds={len(scan['seeds'])} "
          f"| Major(>=4 Wicks)={sum(1 for e in alle if len(e.wicks) >= 4)} "
          f"SCHLAFEND={sum(1 for e in alle if e.status == 'SCHLAFEND')}")

    v0, _ = _lauf(ns, patched, scan, DEFAULT_ADAPTER, False)
    vb, _ = _lauf(ns, patched, scan, DEFAULT_ADAPTER, True)
    vbatch, _ = _lauf(ns, patched, scan, ADAPTER_V019, True)
    vkaus, _ = _lauf(ns, patched, scan, ADAPTER_V019_KAUSAL, True)

    print()
    print("=" * 92)
    ok_all = True
    for nm, tr in (("V0", v0), ("V1_basis", vb),
                   ("V1_batch", vbatch), ("V1_kausal", vkaus)):
        n, r, n1, r1, n2, r2 = _ber(tr)
        s = SOLL[nm]
        ok = (n == s[0] and abs(r - s[1]) < 1e-4)
        if s[2] is not None:
            ok = ok and n1 == s[2] and abs(r1 - s[3]) < 1e-6
            ok = ok and n2 == s[4] and abs(r2 - s[5]) < 1e-4
        ok_all = ok_all and ok
        print(f"{nm:9s} n={n:3d} R={r:+11.6f} | H1 {n1:2d}/{r1:+10.6f} | "
              f"H2 {n2:2d}/{r2:+10.6f} | {'OK' if ok else 'ABWEICHUNG'}")
    print("=" * 92)
    print("V0       Trades: " + ", ".join(
        f"K{int(t.kid)}@{int(t.entry_bar)}({float(t.r):+.1f})" for t in v0))
    print("V1_batch Trades: " + ", ".join(
        f"K{int(t.kid)}@{int(t.entry_bar)}({float(t.r):+.1f})" for t in vbatch))
    print("V1_kausal Trades: " + ", ".join(
        f"K{int(t.kid)}@{int(t.entry_bar)}({float(t.r):+.1f})" for t in vkaus))

    # -- B3 Tracebarkeit: Wirkung 1..4 des segmentwand-Gates -------------
    print()
    print("=" * 92)
    for nm, hook, mz in (("AUS (1 Segment)", DEFAULT_ADAPTER, False),
                         ("AN  (Batch)", ADAPTER_V019, True),
                         ("AN  (Kausal)", ADAPTER_V019_KAUSAL, True)):
        sc = copy.deepcopy(scan)
        vor = [len(e.wicks) for e in list(sc["edges"]) + list(sc["seeds"])]
        if mz:
            ns["_hook"] = hook
            ns["erweitere_segmentwand_dochte"](
                sc, hook, ns["cfg"],
                sc["d"]["high"].to_numpy(dtype=float),
                sc["d"]["low"].to_numpy(dtype=float), ns["_ueb"])
        nach = [len(e.wicks) for e in list(sc["edges"]) + list(sc["seeds"])]
        neu = sum(1 for a, b in zip(vor, nach) if b > a)
        a = list(sc["edges"]) + list(sc["seeds"])
        print(f"{nm:17s} Dochte +{sum(nach) - sum(vor):3d} auf {neu:2d} Kanten"
              f" | schlafend {sum(1 for e in a if e.schlaf_windows):2d}"
              f" | AKTIV {sum(1 for e in a if e.status == 'AKTIV'):2d}"
              f" | Major-schlafend "
              f"{sum(1 for e in a if len(e.wicks) >= 4 and e.status == 'SCHLAFEND'):2d}")

    # -- Idempotenzprobe (scan_readonly / Nicht-Idempotenz H20.50) -------
    n_roh = len(list(scan["edges"]) + list(scan["seeds"]))
    w_roh = sum(len(e.wicks) for e in list(scan["edges"]) + list(scan["seeds"]))
    _lauf(ns, patched, scan, ADAPTER_V019, True)
    n_nach = len(list(scan["edges"]) + list(scan["seeds"]))
    w_nach = sum(len(e.wicks) for e in list(scan["edges"]) + list(scan["seeds"]))
    print()
    print(f"Read-only-Probe Master-Scan: Kanten {n_roh}->{n_nach} | "
          f"Wicks {w_roh}->{w_nach} | "
          f"{'OK (unberuehrt)' if (n_roh, w_roh) == (n_nach, w_nach) else 'MUTIERT'}")
    print(f"GESAMT: {'ALLE SOLLWERTE OK' if ok_all else 'ABWEICHUNGEN -- siehe oben'}")


if __name__ == "__main__":
    main()
