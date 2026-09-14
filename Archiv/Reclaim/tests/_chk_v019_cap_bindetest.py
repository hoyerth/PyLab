# -*- coding: utf-8 -*-
"""Stufe 4b: Bindetest der Concurrency-Schranke (Cap = 3 je Richtung).

Drei Nachweise:
  T1 EINHEIT  -- echter 4. Trade: 3 synthetisch offene + 1 Kandidat
                 -> _konkurrenz_aktiv == 4 -> vom Guard (Cap 3) blockiert.
  T2 POSITIV  -- AUG mit Default-Cap 3: 23 Trades unveraendert,
                 concurrency_blockiert == 0 (Schranke inert).
  T3 NEGATIV  -- AUG mit Cap 2 (End-to-End): der 3. gleichzeitige SHORT
                 wird blockiert -> concurrency_blockiert > 0.

Read-only; es wird keine Produktivdatei geschrieben.
"""
from __future__ import annotations

import copy
import dataclasses
import importlib.util
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import ADAPTER_V019_KAUSAL  # noqa: E402

ok = True


def _pruefe(name: str, ist, soll) -> None:
    global ok
    hit = ist == soll
    ok = ok and hit
    print(f"  [{'OK ' if hit else 'FAIL'}] {name:<52} "
          f"ist={ist}  soll={soll}")


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
        "h_cap", ROOT / "test" / "_chk_v019_kausal_vergleich.py")
    H = importlib.util.module_from_spec(_spec)
    sys.modules["h_cap"] = H
    _spec.loader.exec_module(H)  # type: ignore[union-attr]
finally:
    sys.stdout = _stdout

engine = H.engine
cfg = H.cfg

print("=" * 100)
print("STUFE 4b -- BINDETEST DER CONCURRENCY-SCHRANKE (Cap = 3 je Richtung)")
print("=" * 100)

# ---------------------------------------------------------------- T1 Einheit
print("\nT1) EINHEIT: echter 4. Trade (3 offene + 1 Kandidat)")


def _setup(bar: int, entry_bar: int, x1: int, x2: int,
           richt: str = "SHORT", kid: int = 900) -> object:
    return engine._SESetup(
        bar=bar, richtung=richt, kid=kid, basis=70.0, sweep=70.1,
        trigger_close=70.0, touch_n=3, poc=69.5, tp2=69.0, sl=70.5,
        entry=70.0, r=1.0, resultat="GEWONNEN",
        entry_bar=entry_bar, exit1_bar=x1, exit2_bar=x2,
        grund1="TP1", grund2="TP2", r1=0.5, r2=0.5)


# Drei gleichzeitig offene SHORTs [900..1000], Kandidat bei 950
_offen = [_setup(900, 905, 990, 1000, kid=901),
          _setup(910, 915, 985, 1005, kid=902),
          _setup(920, 925, 995, 1010, kid=903)]
_n4 = engine._konkurrenz_aktiv(_offen, "SHORT", 950, 990, 990)
_pruefe("_konkurrenz_aktiv(3 offen + Kandidat @950)", _n4, 4)
_pruefe("  -> Cap 3 blockiert (4 > 3)", _n4 > cfg.max_gleichzeitig_je_richtung,
        True)

# Gegenprobe: nicht ueberlappend -> 1
_weit = engine._konkurrenz_aktiv(_offen, "SHORT", 2000, 2010, 2010)
_pruefe("_konkurrenz_aktiv(kein Ueberlapp)", _weit, 1)
# Gegenprobe: andere Richtung zaehlt nicht
_andere = engine._konkurrenz_aktiv(_offen, "LONG", 950, 990, 990)
_pruefe("_konkurrenz_aktiv(andere Richtung)", _andere, 1)


# ------------------------------------------------------- Engine-Lauf-Helfer
def _lauf_mit(cfg_v, hook):
    H.ns["_hook"] = hook
    exec(compile(H.patched_src, "<cap_variante>", "exec"), H.ns)  # noqa: S102
    setups, st = H.ns["_se_trades"](copy.deepcopy(H.scan), cfg_v)
    return list(setups), dict(st)


def _kz(ss):
    return len(ss), round(sum(float(t.r) for t in ss), 6)


# ------------------------------------------------------------- T2 Positiv
print("\nT2) POSITIV: AUG mit Default-Cap 3 (muss inert sein)")
_P_SET, _P_ST = _lauf_mit(cfg, ADAPTER_V019_KAUSAL)
_pruefe("Trades unveraendert", _kz(_P_SET), (23, 85.577150))
_pruefe("concurrency_blockiert == 0 (inert)",
        int(_P_ST.get("concurrency_blockiert", -1)), 0)
_pruefe("Cap-Feld == 3", cfg.max_gleichzeitig_je_richtung, 3)

# ------------------------------------------------------------- T3 Negativ
print("\nT3) NEGATIV (End-to-End): Cap 2 -> der 3. gleichzeitige SHORT faellt")
_cfg2 = dataclasses.replace(cfg, max_gleichzeitig_je_richtung=2)
_N_SET, _N_ST = _lauf_mit(_cfg2, ADAPTER_V019_KAUSAL)
_n_block = int(_N_ST.get("concurrency_blockiert", -1))
_pruefe("concurrency_blockiert > 0", _n_block > 0, True)
_pruefe("Trades reduziert (23 -> ?)", len(_N_SET) < 23, True)
print(f"       blockiert: {_n_block} | Trades {len(_N_SET)} / "
      f"{sum(float(t.r) for t in _N_SET):+.6f} R")
_kP = {H._key(t) for t in _P_SET}
_kN = {H._key(t) for t in _N_SET}
for t in sorted([x for x in _P_SET if H._key(x) not in _kN],
                key=lambda z: int(z.bar)):
    print(f"       BLOCKIERT bar {int(t.bar):>5} entry {int(t.entry_bar):>5} "
          f"{t.richtung:<6} K{int(t.kid):<4} R {float(t.r):>+10.5f}")

print(f"\nGESAMT: {'OK' if ok else 'FEHLER'}")
raise SystemExit(0 if ok else 1)
