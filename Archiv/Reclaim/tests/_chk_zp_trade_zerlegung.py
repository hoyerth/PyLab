# -*- coding: utf-8 -*-
"""READ-ONLY: Zerlegung der 23 V1_kausal-Trades in native vs. ZP-Injektion.

Frage: Woraus besteht der V019-Live-Anker (23 Trades / +85,577150 R)?
  * V0        -> nativ, ohne Patchset        (Soll: 14 / +42,450970)
  * V1_basis  -> Basis-Patches, 1 Segment    (Soll: 14 / +47,815697)
  * V1_kausal -> Basis + ZP, 3 Segmente      (Soll: 23 / +85,577150)
Der ZP-Beitrag ist V1_kausal - V1_basis (Soll: 9).

Vorgehen: Der ARRETIERTE Renderer ist die SSoT der Patchmechanik. Er wird im
Zero-Trust-Probe-Modus geladen (--probe-praefix), damit die versiegelten
aug_sichttest_v019_*-Artefakte unberuehrt bleiben. Keine Engine-/Adapter-
Mutation.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
RENDERER = ROOT / "test" / "tmp_png_aug_sichttest.py"
RENDERER_SHA_SOLL = (
    "500b55762001d6667af3d977324c81eb4ecbceacc2fa0d8b62c36c7e383250e0")
ENGINE_SHA_SOLL = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
PROBE_PRAEFIX = "probe_zp_"
JOURNAL = "test/_tmp_zp_renderer_journal.txt"                 # Renderer-Journal
PROTOKOLL = ROOT / "test" / "_chk_zp_trade_zerlegung_out.txt"  # Analysebeleg
ZZ_START, ZZ_ENDE = 1033, 1287      # ZP-4-Fenster (_zv)
P9_START, P9_ENDE = 848, 1020       # P9 (ZP-4 ausgenommen)

assert hashlib.sha256(RENDERER.read_bytes()).hexdigest() == RENDERER_SHA_SOLL, \
    "Fremder Renderer"
assert hashlib.sha256(
    (ROOT / "test" / "tmp_kanten_engine_replay.py").read_bytes()
).hexdigest() == ENGINE_SHA_SOLL, "Fremde Engine"


def _lade_renderer_probe():
    """Laedt den Renderer im Probe-Modus (schreibt nur probe_zp_*-Artefakte)."""
    _argv = sys.argv
    sys.argv = ["zp_zerlegung", "--mode", "V019",
                "--probe-praefix", PROBE_PRAEFIX,
                "--protokoll-nach", JOURNAL]
    try:
        spec = importlib.util.spec_from_loader("png_probe_zp", loader=None)
        mod = importlib.util.module_from_spec(spec)
        mod.__file__ = str(RENDERER)
        sys.modules["png_probe_zp"] = mod
        exec(compile(RENDERER.read_text(encoding="utf-8"), str(RENDERER),
                     "exec"), mod.__dict__)
    finally:
        sys.argv = _argv
    return mod


def _key(t) -> Tuple[int, int]:
    """Schluessel (bar, kid) -- identisch zur Renderer-Konvention."""
    return (int(t.bar), int(t.kid))


def _idx(ts) -> Dict[Tuple[int, int], object]:
    return {_key(t): t for t in ts}


class _Tee:
    """Schreibt jeden Ausgabestring auf Terminal UND in einen Puffer."""

    def __init__(self, real) -> None:
        self._real = real
        self.buf: List[str] = []

    def write(self, s: str) -> int:
        self.buf.append(s)
        return self._real.write(s)

    def flush(self) -> None:
        self._real.flush()


def main() -> None:
    _stdout = sys.stdout
    mod = _lade_renderer_probe()
    tee = _Tee(_stdout)
    sys.stdout = tee
    try:
        _analyse(mod)
    finally:
        sys.stdout = _stdout
    PROTOKOLL.write_text("".join(tee.buf), encoding="utf-8")
    print(f"\nProtokoll -> {PROTOKOLL}  ({PROTOKOLL.stat().st_size:,} B)")


def _analyse(mod) -> None:
    V0 = list(mod.V0)
    VB = list(mod.V1_basis)
    VK = list(mod.V1_kausal)
    box_end = int(mod.box_end)
    n = int(mod.n)

    k0, kb, kk = _idx(V0), _idx(VB), _idx(VK)
    injekt = [t for k, t in kk.items() if k not in kb]
    basis_neu = [t for k, t in kb.items() if k not in k0]
    native_weg = [t for k, t in k0.items() if k not in kk]

    def _sr(ts) -> float:
        return sum(t.r for t in ts)

    print("=" * 100)
    print(f"FENSTER AUG (n={n}, box_end={box_end})  ZP-Fenster "
          f"={ZZ_START}..{ZZ_ENDE}  P9={P9_START}..{P9_ENDE}")
    print(f"V0       : {len(V0):2d} Trades / {_sr(V0):+.6f} R")
    print(f"V1_basis : {len(VB):2d} Trades / {_sr(VB):+.6f} R")
    print(f"V1_kausal: {len(VK):2d} Trades / {_sr(VK):+.6f} R")
    print(f"ZP-Injekt (kausal - basis)  : {len(injekt):2d} / {_sr(injekt):+.6f} R")
    print(f"Basis-Neu (basis - v0)      : {len(basis_neu):2d} / "
          f"{_sr(basis_neu):+.6f} R")
    print(f"Native entfaellt (v0-kausal): {len(native_weg):2d} / "
          f"{_sr(native_weg):+.6f} R")
    print("=" * 100)
    print("TRADES V0 (native, unpatched):")
    print(f"{'#':>2} {'entry':>6} {'bar':>6} {'kid':>4} {'richtung':6} "
          f"{'R':>11} {'in_kausal':9}")
    for i, t in enumerate(sorted(V0, key=lambda x: (x.entry_bar, x.kid)), 1):
        print(f"{i:2d} {t.entry_bar:6d} {t.bar:6d} {t.kid:4d} {t.richtung:6s} "
              f"{t.r:+11.6f} {str(_key(t) in kk):9s}")
    print("=" * 100)
    print("TRADES V1_kausal (Basis + ZP):")
    print(f"{'#':>2} {'entry':>6} {'bar':>6} {'kid':>4} {'richtung':6} "
          f"{'R':>11} {'in_V0':5} {'in_basis':8} {'im_ZP-Fenster':13} "
          f"{'status':12}")
    for i, t in enumerate(sorted(VK, key=lambda x: (x.entry_bar, x.kid)), 1):
        k = _key(t)
        im_zp = (ZZ_START <= int(t.entry_bar) <= ZZ_ENDE
                 or ZZ_START <= int(t.bar) <= ZZ_ENDE)
        status = ("ZP-INJEKT" if k not in kb
                  else ("BASIS-NEU" if k not in k0 else "NATIV"))
        print(f"{i:2d} {t.entry_bar:6d} {t.bar:6d} {t.kid:4d} {t.richtung:6s} "
              f"{t.r:+11.6f} {str(k in k0):5s} {str(k in kb):8s} "
              f"{str(im_zp):13s} {status:12s}")
    print("=" * 100)
    print("R-Delta (V1_kausal - V0) fuer gemeinsame Schluessel:")
    for k in sorted(set(k0) & set(kk), key=lambda x: (x[0], x[1])):
        d = kk[k].r - k0[k].r
        flag = "  <== geaendert" if abs(d) > 1e-9 else ""
        print(f"  bar {k[0]:5d} K{k[1]:<4d} {kk[k].richtung:6s} "
              f"V0 {k0[k].r:+11.6f} -> V019 {kk[k].r:+11.6f}  "
              f"delta {d:+11.6f}{flag}")
    print("=" * 100)
    print("RICHTUNGSBILANZ")
    for label, ts in (("V0", V0), ("V1_basis", VB), ("V1_kausal", VK),
                      ("ZP-Injekt", injekt)):
        nl = sum(1 for t in ts if t.richtung == "LONG")
        ns = sum(1 for t in ts if t.richtung == "SHORT")
        rl = sum(t.r for t in ts if t.richtung == "LONG")
        rs = sum(t.r for t in ts if t.richtung == "SHORT")
        print(f"  {label:10s}: LONG {nl:2d} / {rl:+10.6f} R  |  "
              f"SHORT {ns:2d} / {rs:+10.6f} R")

    pngs = sorted((ROOT / "test").glob(f"{PROBE_PRAEFIX}*.png"))
    for p in pngs:
        p.unlink()
    print("=" * 100)
    print(f"Probe-PNGs entfernt: {len(pngs)} | Protokoll: {PROTOKOLL}")
    print("ARRETIERTE SATZ-DATEIEN UNBERUEHRT: aug_sichttest_v019_*")


if __name__ == "__main__":
    main()
