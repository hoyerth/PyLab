# -*- coding: utf-8 -*-
"""STATISCHE Vorpruefung der Budgetidentitaet (I) -- reiner AST-Check.

Struktur der Baseline::

    for k in range(2, box_end - 3):
        for richtung in ("SHORT", "LONG"):
            <Body mit genau EINEM Ausgang je (k, richtung)>

Jedes ``continue`` im Body der ``richtung``-Schleife verlaesst EINE
(k, richtung)-Einheit. Verlaesst eine Einheit den Body ohne Zaehler, bricht
Identitaet (I) (``eintritt == Summe der Ausgaenge``).

Geprueft wird: jeder Ausgang, dessen naechste umschliessende Schleife die
``richtung``-Schleife (oder die ``k``-Schleife selbst) ist, hat im
instrumentierten Text unmittelbar davor einen ``_c(...)``-Aufruf.
"""
from __future__ import annotations

import ast
import pathlib
from typing import Dict, List, Tuple

SEGMENT_QUELLE = pathlib.Path("test/tmp_kanten_engine_replay.py").read_text(
    encoding="utf-8")


def _instrumentiere(src: str) -> str:
    import sys
    root = pathlib.Path(__file__).resolve().parent.parent
    for p in (str(root), str(root / "test")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import _chk_zulassung_funnel as F
    assert F._pruefe_anker(src) == []
    return F._instrumentiere(src)


def _funktion(que: str) -> ast.FunctionDef:
    return next(n for n in ast.parse(que).body
                if isinstance(n, ast.FunctionDef) and n.name == "_se_trades")


def _funktion_baum(tree: ast.Module) -> ast.FunctionDef:
    return next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "_se_trades")


def _k_schleife(fn: ast.FunctionDef) -> ast.For:
    for n in fn.body:
        if (isinstance(n, ast.For) and isinstance(n.target, ast.Name)
                and n.target.id == "k"):
            return n
    raise RuntimeError("k-Schleife nicht gefunden.")


def _richtung_schleife(k: ast.For) -> ast.For:
    for n in k.body:
        if isinstance(n, ast.For):
            return n
    raise RuntimeError("richtung-Schleife nicht gefunden.")


def _elternbau(fn: ast.AST) -> Dict[ast.AST, ast.AST]:
    eltern: Dict[ast.AST, ast.AST] = {}
    for x in ast.walk(fn):
        for y in ast.iter_child_nodes(x):
            eltern[y] = x
    return eltern


def _ausgaenge(fn: ast.AST) -> List[Tuple[ast.AST, str, ast.AST]]:
    """(Knoten, Art, naechste umschliessende Schleife) -- objektbasiert."""
    out: List[Tuple[ast.AST, str, ast.AST]] = []

    def gehe(n: ast.AST, stapel: List[ast.AST]) -> None:
        for kind in ast.iter_child_nodes(n):
            if isinstance(kind, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.Lambda)):
                continue
            if isinstance(kind, (ast.For, ast.While, ast.AsyncFor)):
                gehe(kind, stapel + [kind])
                continue
            if isinstance(kind, (ast.Continue, ast.Break)):
                out.append((kind, type(kind).__name__.lower(),
                            stapel[-1] if stapel else None))
                continue
            if isinstance(kind, ast.Return) and kind.value is not None:
                out.append((kind, "return", stapel[-1] if stapel else None))
                continue
            gehe(kind, stapel)

    gehe(fn, [])
    return sorted(out, key=lambda t: t[0].lineno)


def _zaehler_davor(eltern: Dict[ast.AST, ast.AST], ziel: ast.AST
                   ) -> Tuple[bool, str]:
    """Steht im SELBEN Body VOR ``ziel`` genau ein ``_c(...)``?

    Nicht "unmittelbar davor": die Anker setzen den Zaehler mal VOR, mal NACH
    die ``stats[...] += 1``-Zeile; dazwischen koennen Listen-Appends liegen.
    Entscheidend ist, dass der Zaehler im selben Block unbedingt vor dem
    Ausgang steht (direkte Anweisung, nicht in einem Unterblock).
    """
    p = eltern.get(ziel)
    if p is None or not hasattr(p, "body"):
        return False, "kein Elternbody"
    body = list(getattr(p, "body"))
    try:
        i = body.index(ziel)
    except ValueError:
        return False, "nicht im Elternbody"
    treffer: List[str] = []
    for v in body[:i]:
        if (isinstance(v, ast.Expr) and isinstance(v.value, ast.Call)
                and isinstance(v.value.func, ast.Name)
                and v.value.func.id == "_c"):
            treffer.append(str(v.value.args[0].value))
        if isinstance(v, (ast.Continue, ast.Break, ast.Return)):
            return False, f"anderer Ausgang ({type(v).__name__}) davor"
    if len(treffer) == 1:
        return True, treffer[0]
    return False, (f"{len(treffer)} Zaehler davor" if treffer
                   else f"kein Zaehler (davor: {type(body[i-1]).__name__})")


def _pruefe(label: str, baum: ast.Module) -> int:
    fn = _funktion_baum(baum)
    k = _k_schleife(fn)
    rs = _richtung_schleife(k)
    eltern = _elternbau(fn)
    alle = _ausgaenge(fn)
    budget = [t for t in alle if t[2] is rs or t[2] is k]
    aussen = [t for t in alle if t[2] is not rs and t[2] is not k]

    print(f"### {label}: _se_trades ab Z{fn.lineno}, k-Schleife Z{k.lineno}, "
          f"richtung-Schleife Z{rs.lineno}")
    print(f"    Ausgaenge gesamt {len(alle)} | Budgetausgaenge {len(budget)} "
          f"| ausserhalb {len(aussen)}")
    for knoten, art, _ in budget:
        ok, info = _zaehler_davor(eltern, knoten)
        print(f"    Z{knoten.lineno:>5d} {art:<8s} "
              f"{'-> _c(\"' + info + '\", ...)' if ok else '-> KEIN Zaehler (' + info + ')'}")
    print("    ausserhalb:")
    for knoten, art, schleife in aussen:
        print(f"    Z{knoten.lineno:>5d} {art:<8s} Schleife "
              f"Z{schleife.lineno if schleife else None}")
    return len(budget)


def _kandidat_pfade() -> None:
    """Zweite Risikostelle: liefert ``_kandidat`` AUSSCHLIESSLICH an den 4
    instrumentierten Stellen ``None``?  Sonst bricht Identitaet (III)."""
    fn = next(n for n in ast.walk(ast.parse(SEGMENT_QUELLE))
              if isinstance(n, ast.FunctionDef) and n.name == "_kandidat")
    print(f"### _kandidat ab Z{fn.lineno} -- alle Wert-Rueckgaben:")
    for n in ast.walk(fn):
        if isinstance(n, ast.Return):
            if n.value is None:
                wert = "None"
            elif isinstance(n.value, ast.Name):
                wert = n.value.id
            else:
                wert = type(n.value).__name__
            print(f"    Z{n.lineno:>5d} return {wert}")


def _bodies(label: str, baum: ast.Module) -> None:
    """Top-Level-Kette des richtung-Bodys (letzter Ausgang? Fallthrough?)."""
    fn = _funktion_baum(baum)
    k = _k_schleife(fn)
    rs = _richtung_schleife(k)
    print(f"### {label} -- Top-Level-Kette des richtung-Bodys "
          f"({len(rs.body)} Anweisungen):")
    for st in rs.body:
        print(f"    Z{st.lineno:>5d} {type(st).__name__:<12s} "
              f"{ast.dump(st, annotate_fields=False)[:110]}")


def main() -> None:
    _bodies("BASELINE", ast.parse(SEGMENT_QUELLE))
    _kandidat_pfade()
    print()
    alt = _pruefe("BASELINE", ast.parse(SEGMENT_QUELLE))
    inst = _instrumentiere(SEGMENT_QUELLE)
    neu = _pruefe("INSTRUMENTIERT", ast.parse(inst))
    assert alt == neu, f"Budgetausgangszahl {alt} -> {neu}"
    print(f"\nBudgetausgaenge unveraendert: {alt}")


if __name__ == "__main__":
    main()
