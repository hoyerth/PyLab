# -*- coding: utf-8 -*-
"""GEGENUEBERSTELLUNG `_p9` (Schritt 5) -- pre_p9 vs. post_p9.

Read-only. Vier Messungen je Stand, jeweils mit FRISCHEM Scan:
  A) offizieller Lauf: box_end_bar = scan["box_end_bar"] (= 644, Box < 19.08)
  B) Voll-Lauf (Kennzahl-Basis der Arretierung): box_end_bar = n = 1288
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
PRE = ROOT / "test" / "tmp_kanten_engine_replay_pre_p9.py"
POST = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


def messe(mod, voll: bool):
    cfg = mod.StraightEdgeHarnessKonfiguration()
    sc = mod._se_scan("AUG", cfg)
    box = sc["box_end_bar"]
    sc["box_end_bar"] = sc["n"] if voll else box
    tr, st = mod._se_trades(sc, cfg)
    return tr, st, box, sc["n"]


def main() -> int:
    pre = load("p9_pre", PRE)
    post = load("p9_post", POST)
    print("=" * 104)
    print("GEGENUEBERSTELLUNG `_p9` (Schritt 5) | pre_p9 vs. post_p9 | AUG")
    print("=" * 104)
    for p in (PRE, POST):
        b = p.read_bytes()
        print(f"  {p.name:42s} {len(b):9d} B  CRLF {b.count(b'\r\n'):5d}  "
              f"SHA256 {hashlib.sha256(b).hexdigest()[:16]}")

    zeilen = []
    for label, voll in (("BOX-LAUF  (offiziell, box_end_bar = 644)", False),
                        ("VOLL-LAUF (Arretierungs-Kennzahl, n = 1288)", True)):
        print("")
        print("-" * 104)
        print(f"  {label}")
        print("-" * 104)
        print(f"  {'Stand':10s} {'n':>4s} {'Summe R':>9s} {'dR':>8s} "
              f"{'Stacking':>9s} {'Zyklus':>7s} {'R21':>5s}")
        basis = None
        for nm, mod in (("pre_p9", pre), ("post_p9", post)):
            tr, st, box, n = messe(mod, voll)
            r = sum(t.r for t in tr)
            if basis is None:
                basis = (len(tr), r)
            dr = r - basis[1]
            print(f"  {nm:10s} {len(tr):4d} {r:+9.2f} {dr:+8.2f} "
                  f"{st.get('stacking_blockiert', 0):9d} "
                  f"{st.get('zyklus_blockiert', 0):7d} "
                  f"{st.get('r21_blockiert', 0):5d}")
            zeilen.append((label, nm, len(tr), r, dr))

    print("")
    print("-" * 104)
    print("  ZIELWERT-GATE (Datenvertrag `P9ScharfschaltungsSoll`)")
    print("-" * 104)
    tr_v, st_v, _, n = messe(post, True)
    r_v = sum(t.r for t in tr_v)
    soll = (len(tr_v) == 14 and round(r_v, 2) == 40.45
            and st_v.get("stacking_blockiert", 0) == 0)
    print(f"  Voll-Lauf : {len(tr_v)} Trades / {r_v:+.2f} R / "
          f"Stacking {st_v.get('stacking_blockiert', 0)} -> "
          f"{'ERREICHT' if soll else 'ABWEICHUNG'}")
    tr_b, st_b, _, _ = messe(post, False)
    r_b = sum(t.r for t in tr_b)
    print(f"  Box-Lauf  : {len(tr_b)} Trades / {r_b:+.2f} R / "
          f"Stacking {st_b.get('stacking_blockiert', 0)} "
          f"(offizieller Lauf, Box < 19.08)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
