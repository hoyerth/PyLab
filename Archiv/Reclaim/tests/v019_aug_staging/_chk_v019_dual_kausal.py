"""Schritt 2a-Verifikation: dualer Lauf OHNE PNG-Generierung.

Laedt den arretierten Harness (``_chk_v019_kausal_vergleich.py``) als Modul
mit unterdrueckter Ausgabe und fahrt daraus einen vierten Lauf mit dem NEUEN
Adapter ``ADAPTER_V019_KAUSAL``. Verglichen wird gegen:
  * die arretierte Batch-Kontrolle A (24 / +88.116626),
  * den Harness-eigenen kausalen Lauf B (23 / +85.577150).

Geprueft wird die ADAPTER-Ableitung (``kausale_segmentfenster``), nicht eine
Zweitimplementierung im Renderer.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V019, ADAPTER_V019_KAUSAL, AUTO_VERSCHMELZUNG_SCHWELLE,
)

ok = True


def _pruefe(name: str, ist, soll, tol: float = 0.0) -> None:
    global ok
    if tol > 0.0:
        hit = abs(float(ist) - float(soll)) < tol
    else:
        hit = ist == soll
    ok = ok and hit
    print(f"  [{'OK ' if hit else 'FAIL'}] {name:<46} ist={ist}  soll={soll}")


print("=" * 96)
print("2a  DUALER KAUSALER LAUF (adapter-getrieben, read-only, ohne PNG)")
print("=" * 96)

# --- 1) Fenster-Ableitung -------------------------------------------------
print("\n1) ADAPTER_V019_KAUSAL -> Fenster")
_w = [(s.phasen_id, s.start_bar, s.end_bar) for s in ADAPTER_V019_KAUSAL.segmente]
_b = [(s.phasen_id, s.start_bar, s.end_bar) for s in ADAPTER_V019.segmente]
print(f"  Batch : {_b}")
print(f"  Kausal: {_w}")
_pruefe("A1 endet 1249 (1174+77-1 = 1250 -> -1)", _w[1][2], 1249)
_pruefe("A2 endet 1287 (letztes Segment unveraendert)", _w[2][2], 1287)
_pruefe("Startbars unveraendert", ( _w[1][1], _w[2][1]), (1033, 1174))
_pruefe("P9-Anker unberuehrt", _w[0], ("P9", 848, 1020))
_pruefe("Kantenpaare unveraendert",
        [(s.decke.kid, s.boden.kid) for s in ADAPTER_V019_KAUSAL.segmente],
        [(s.decke.kid, s.boden.kid) for s in ADAPTER_V019.segmente])
_pruefe("Schwelle == 77 (Plateaumitte)", AUTO_VERSCHMELZUNG_SCHWELLE, 77)

# --- 2) Harness laden (Ausgabe unterdrueckt) ------------------------------
print("\n2) Harness laden (arretierte Renderer-Patches per AST)")


class _Quiet:
    """Minimaler stdout-Ersatz (der Harness ruft ``reconfigure``)."""

    def __init__(self) -> None:
        self.puffer: list = []

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
        "h_v019_kausal", ROOT / "test" / "_chk_v019_kausal_vergleich.py")
    H = importlib.util.module_from_spec(_spec)
    sys.modules["h_v019_kausal"] = H
    _spec.loader.exec_module(H)  # type: ignore[union-attr]
finally:
    sys.stdout = _stdout
print(f"  Harness geladen ({sum(len(s) for s in _quiet.puffer):,} Zeichen "
      f"Ausgabe unterdrueckt)")

A_SET, B_SET = H.A_SETUPS, H.B_SETUPS
_nA, _rA = H._kz(A_SET)
_nB, _rB = H._kz(B_SET)
_pruefe("Kontrolle A (Batch): 24 / +88.116626", (_nA, round(_rA, 6)),
        (24, 88.116626))
_pruefe("Kontrolle B (Harness-kausal): 23 / +85.577150",
        (_nB, round(_rB, 6)), (23, 85.577150))

# --- 3) ADAPTER_V019_KAUSAL fahren ---------------------------------------
print("\n3) ADAPTER_V019_KAUSAL -> Engine-Lauf")
D_SET, D_STATS = H._lauf(ADAPTER_V019_KAUSAL)
_nD, _rD = H._kz(D_SET)
_h1 = [t for t in D_SET if int(t.entry_bar) < 644]
_h2 = [t for t in D_SET if int(t.entry_bar) >= 644]
_pruefe("V1_kausal: Trades", _nD, 23)
_pruefe("V1_kausal: R", _rD, 85.577150, tol=1e-6)
_pruefe("V1_kausal: H1", (len(_h1), round(sum(t.r for t in _h1), 6)),
        (8, 38.919584))
_pruefe("V1_kausal: H2", (len(_h2), round(sum(t.r for t in _h2), 6)),
        (15, 46.657566))

# --- 4) Bit-Identitaet zum Harness-kausalen Lauf --------------------------
print("\n4) Mengenvergleich (Adapter-kausal vs. Harness-kausal)")
_kD = {H._key(t) for t in D_SET}
_kB = {H._key(t) for t in B_SET}
_ka = {H._key(t) for t in A_SET}
_pruefe("Mengengleichheit D == B", _kD == _kB, True)
_pruefe("Trade-Menge: entfernt vs. A", sorted(_ka - _kD), [(1211, 76)])
_pruefe("Kein Zusatz gegen B", sorted(_kD - _kB), [])
for _bar, _kid in sorted(_kD & _kB):
    _td = next(t for t in D_SET if H._key(t) == (_bar, _kid))
    _tb = next(t for t in B_SET if H._key(t) == (_bar, _kid))
    if abs(float(_td.r) - float(_tb.r)) > 1e-12:
        ok = False
        print(f"  [FAIL] R-Delta {_bar}/K{_kid}: {_td.r} != {_tb.r}")
print("  [OK ] alle gemeinsamen Trades R-bit-identisch"
      if ok else "  [FAIL] R-Delta gefunden")

# --- 5) H1-Invariante gegen Kontrolle ------------------------------------
_h1a = [t for t in A_SET if int(t.entry_bar) < 644]
_pruefe("H1 kausal == H1 Batch (Box etikettfrei)",
        [(t.bar, t.kid, round(float(t.r), 9)) for t in _h1],
        [(t.bar, t.kid, round(float(t.r), 9)) for t in _h1a])

print(f"\nGESAMT: {'OK' if ok else 'FEHLER'}")
raise SystemExit(0 if ok else 1)
