# -*- coding: utf-8 -*-
"""Stufe 4a: End-to-End-Nachweis der Schenkel-Durchreichung (R_realisiert).

Liest grund2/r1/r2 direkt aus den _SESetup-Objekten (jetzt durchgereicht)
und rechnet die drei Metriken OHNE Instrumentierung nach.

Read-only; keine Produktivdatei wird geschrieben.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import ADAPTER_V019_KAUSAL  # noqa: E402

ok = True


def _pruefe(name: str, ist, soll, tol: float = 0.0) -> None:
    global ok
    hit = abs(float(ist) - float(soll)) < tol if tol > 0 else ist == soll
    ok = ok and hit
    print(f"  [{'OK ' if hit else 'FAIL'}] {name:<50} ist={ist}  soll={soll}")


class _Quiet:
    def __init__(self) -> None:
        self.puffer: List[str] = []

    def write(self, s: str) -> int:
        self.puffer.append(s)
        return len(s)

    def writelines(self, lines) -> None:
        self.puffer.extend(lines)

    def flush(self) -> None:
        return None

    def reconfigure(self, *args, **kwargs) -> None:
        return None


_stdout = sys.stdout
_quiet = _Quiet()
try:
    sys.stdout = _quiet
    _spec = importlib.util.spec_from_file_location(
        "h_rreal", ROOT / "test" / "_chk_v019_kausal_vergleich.py")
    H = importlib.util.module_from_spec(_spec)
    sys.modules["h_rreal"] = H
    _spec.loader.exec_module(H)  # type: ignore[union-attr]
finally:
    sys.stdout = _stdout

cfg = H.cfg
W = cfg.tp1_anteil_pct / 100.0

print("=" * 100)
print("STUFE 4a -- R_REALISIERT (Schenkel aus _SESetup, ohne Instrumentierung)")
print("=" * 100)

S, ST = H._lauf(ADAPTER_V019_KAUSAL)
print(f"\nKausaler Satz: {len(S)} Setups / {sum(float(t.r) for t in S):+.6f} R")

# Schenkel-Felder muessen jetzt gefuellt sein (Stufe 4a)
_leer = [t for t in S if not getattr(t, "grund2", "")]
_pruefe("alle Setups tragen grund2", len(_leer), 0)
_pruefe("alle Setups tragen r1/r2 (nicht alle 0.0)",
        any(abs(float(t.r1)) > 0.0 for t in S), True)

_brutto = sum(float(t.r) for t in S)
_b = sum((0.0 if t.grund1 == "ENDE" else W * float(t.r1))
         + (0.0 if t.grund2 == "ENDE" else (1.0 - W) * float(t.r2))
         for t in S)
_a_set = [t for t in S if t.grund1 != "ENDE" and t.grund2 != "ENDE"]
_a = sum(W * float(t.r1) + (1.0 - W) * float(t.r2) for t in _a_set)

_pruefe("R_brutto", round(_brutto, 6), 85.577150, tol=1e-6)
_pruefe("R_realisiert (b)", round(_b, 6), 75.677008, tol=1e-6)
_pruefe("R_untergrenze (a)", round(_a, 6), 75.588050, tol=1e-6)
_pruefe("(a)-Menge ohne ENDE", len(_a_set), 19)
_pruefe("ENDE-Trades", sum(1 for t in S if "ENDE" in (t.grund1, t.grund2)), 4)

print("\n  ENDE-Trades (Schenkel direkt aus _SESetup):")
print(f"  {'Bar':>5} {'Entry':>6} {'Kante':>6} {'Richt':>6} "
      f"{'grund1':>7} {'r1':>10} {'grund2':>7} {'r2':>10} {'r':>11}")
for t in sorted([x for x in S if "ENDE" in (x.grund1, x.grund2)],
                key=lambda z: int(z.bar)):
    print(f"  {int(t.bar):>5} {int(t.entry_bar):>6} {'K%d' % int(t.kid):>6} "
          f"{t.richtung:>6} {t.grund1:>7} {float(t.r1):>+10.5f} "
          f"{t.grund2:>7} {float(t.r2):>+10.5f} {float(t.r):>+11.5f}")

print(f"\n  concurrency_blockiert = "
      f"{int(ST.get('concurrency_blockiert', -1))} (Cap 3 inert)")

print(f"\nGESAMT: {'OK' if ok else 'FEHLER'}")
raise SystemExit(0 if ok else 1)
