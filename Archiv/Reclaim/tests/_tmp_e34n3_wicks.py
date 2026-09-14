# -*- coding: utf-8 -*-
"""E-34n/3 — Plateau-/Mehrfach-Beruehrungs-Audit (read-only).

Anwender-Befund: an mehreren Stellen beruehren MEHRERE aufeinanderfolgende
Bars ein Level, ohne dass ein einzelner Pivot-Docht entsteht (P1 verlangt
STRENG isolierte Extrema beidseitig). Die Treffer sind trotzdem real.

Dieses Skript:
  A) Katalog aller Kanten/Seeds (kid, seite, basis, erster_pivot_bar, wicks).
  B) Fuer jedes Level: alle Laeufe aufeinanderfolgender Bars, die den
     Level durchstossen haben (lo < basis bei UNTEN, hi > basis bei OBEN),
     mit Kennzeichnung, ob im Lauf ein Docht akzeptiert wurde.
     -> Laeufe >= 2 Bars OHNE akzeptierten Docht = der Anwender-Befund.
  C) Detail-Fenster 1055..1090: OHLC, Pivot-Typ, je Kante Durchstich/akzeptiert.
  D) Gesamtzahlen.

Kein Schreiben in Adapter/Engine; Ausgabe stdout + test/_tmp_e34n3_out.txt.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENG = ROOT / "test" / "tmp_kanten_engine_replay.py"
OUT = ROOT / "test" / "_tmp_e34n3_out.txt"
_FH = OUT.open("w", encoding="utf-8", newline="\n")


class _Tee:
    def write(self, s: str) -> int:
        _FH.write(s)
        _FH.flush()
        return sys.__stdout__.write(s)

    def flush(self) -> None:
        _FH.flush()
        sys.__stdout__.flush()


sys.stdout = _Tee()  # type: ignore[assignment]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


print("=" * 118)
print("E-34n/3  PLATEAU-/MEHRFACH-BERUEHRUNGS-AUDIT (read-only)")
print("=" * 118)
print(f"Engine SHA {hashlib.sha256(ENG.read_bytes()).hexdigest()[:24]}...")

eng = load("ke_e34n3", ENG)
cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
n = scan["n"]
d = scan["d"]
ts = d["ts"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
alle = list(scan["edges"]) + list(scan["seeds"])
print(f"n={n} | Kanten {len(scan['edges'])} | Seeds {len(scan['seeds'])} | "
      f"touch_band_pct={cfg.touch_band_pct} | "
      f"MIN_TOUCH_ABSTAND={eng.SE_HARNESS_MIN_TOUCH_ABSTAND}")


def _zeit(k: int) -> str:
    return ts.iloc[k].strftime("%d.%m. %H:%M")


print("\n" + "=" * 118)
print("A) KATALOG aller Kanten/Seeds im Preisband 66.5..70.5")
print("=" * 118)
print(f"{'kid':>4} {'seite':>6} {'basis':>9} {'pivot':>6} {'n_w':>4} "
      f"{'anker':>6}  Wicks (bar@preis)")
_kat = {}
for e in sorted(alle, key=lambda x: int(x.kid)):
    if not (66.5 <= float(e.basis) <= 70.5):
        continue
    _kat[int(e.kid)] = e
    _w = " ".join(f"{b}@{p:.4f}" for b, p in e.wicks)
    print(f"{int(e.kid):>4} {e.seite:>6} {float(e.basis):>9.4f} "
          f"{int(e.erster_pivot_bar):>6} {len(e.wicks):>4} "
          f"{str(bool(e.ist_prim_anker)):>6}  {_w}")

print("\n" + "=" * 118)
print("B) DURCHSTOSS-LAEUFE ohne akzeptierten Docht (Lauf >= 2 Bars)")
print("=" * 118)
print("Definition Durchstoss: UNTEN lo[k] < basis, OBEN hi[k] > basis "
      "(strikt). Lauf = zusammenhaengende Bars.")


def _laeufe(e) -> list:
    """Zusammenhaengende Durchstoss-Laeufe einer Kante."""
    kind = "UNTEN" if e.seite == "UNTEN" else "OBEN"
    basis = float(e.basis)
    ins = (lo < basis) if kind == "UNTEN" else (hi > basis)
    out = []
    k = 0
    while k < n:
        if not ins[k]:
            k += 1
            continue
        s = k
        while k + 1 < n and ins[k + 1]:
            k += 1
        out.append((s, k))
        k += 1
    return out


_verdacht = []
for e in sorted(alle, key=lambda x: int(x.kid)):
    if not (66.5 <= float(e.basis) <= 70.5):
        continue
    _wb = {b for b, _ in e.wicks}
    for (s, t) in _laeufe(e):
        if t - s + 1 < 2:
            continue
        _hat = [b for b in range(s, t + 1) if b in _wb]
        if _hat:
            continue
        # Extrem des Laufs
        _ext = (float(np.min(lo[s:t + 1])) if e.seite == "UNTEN"
                else float(np.max(hi[s:t + 1])))
        _verdacht.append((int(e.kid), e.seite, float(e.basis), s, t, _ext,
                          len(e.wicks)))

print(f"\n  {len(_verdacht)} Laeufe ohne Docht:")
print(f"  {'kid':>4} {'seite':>6} {'basis':>9} {'von':>5} {'bis':>5} "
      f"{'n':>3} {'von(BKZ)':>12} {'bis(BKZ)':>12} {'extrem':>9} {'w_ge':>5}")
for (kid, seite, basis, s, t, ext, nw) in sorted(_verdacht,
                                                 key=lambda x: x[3]):
    print(f"  {kid:>4} {seite:>6} {basis:>9.4f} {s:>5} {t:>5} {t - s + 1:>3} "
          f"{_zeit(s):>12} {_zeit(t):>12} {ext:>9.4f} {nw:>5}")

print("\n" + "=" * 118)
print("B2) PRAEZISER FALL: Lauf-EINSTIEG im touch_band, aber KEIN Docht akzeptiert")
print("=" * 118)
print(f"touch_band_pct={cfg.touch_band_pct} | Filter: k >= erster_pivot_bar+2 "
      f"| Lauf >= 2 Bars | mind. 1 Durchstoss-Bar im Band")
_b2 = []
for e in sorted(alle, key=lambda x: int(x.kid)):
    if not (66.5 <= float(e.basis) <= 70.5):
        continue
    basis = float(e.basis)
    _wb = {b for b, _ in e.wicks}
    for (s, t) in _laeufe(e):
        if t - s + 1 < 2 or s < int(e.erster_pivot_bar) + 2:
            continue
        if any(b in _wb for b in range(s, t + 1)):
            continue
        _in_band = [b for b in range(s, t + 1)
                    if abs((lo[b] if e.seite == "UNTEN" else hi[b]) - basis)
                    / basis * 100.0 <= cfg.touch_band_pct]
        if not _in_band:
            continue
        _ext_b = (s + int(np.argmin(lo[s:t + 1])) if e.seite == "UNTEN"
                  else s + int(np.argmax(hi[s:t + 1])))
        _ext_p = float(lo[_ext_b]) if e.seite == "UNTEN" else float(hi[_ext_b])
        _d_ext = abs(_ext_p - basis) / basis * 100.0
        _b2.append((int(e.kid), e.seite, basis, s, t, _ext_b, _ext_p, _d_ext,
                    len(_in_band), len(e.wicks)))
print(f"\n  {len(_b2)} Faelle:")
print(f"  {'kid':>4} {'seite':>6} {'basis':>9} {'von':>5} {'bis':>5} {'n':>3} "
      f"{'ext_bar':>7} {'ext_preis':>9} {'d_ext%':>7} {'imBand':>6} {'w_ge':>5}  BKZ")
for (kid, seite, basis, s, t, eb, ep, de, nb, nw) in sorted(_b2,
                                                            key=lambda x: x[3]):
    print(f"  {kid:>4} {seite:>6} {basis:>9.4f} {s:>5} {t:>5} {t - s + 1:>3} "
          f"{eb:>7} {ep:>9.4f} {de:>7.3f} {nb:>6} {nw:>5}  {_zeit(s)}")

print("\n" + "=" * 118)
print("C) DETAIL-FENSTER 1055..1090")
print("=" * 118)
print(f"{'bar':>5} {'BKZ':>12} {'O':>8} {'H':>8} {'L':>8} {'C':>8} "
      f"{'piv':>3}  Durchstiche (kid:seite:basis@dist% -> akz?)")
for k in range(1055, 1091):
    piv = "".join(eng._pivot_dual(hi, lo, k))
    zeile = []
    for e in sorted(alle, key=lambda x: int(x.kid)):
        if not (66.6 <= float(e.basis) <= 70.0):
            continue
        basis = float(e.basis)
        if e.seite == "UNTEN":
            if lo[k] >= basis:
                continue
            dist = (basis - lo[k]) / basis * 100.0
        else:
            if hi[k] <= basis:
                continue
            dist = (hi[k] - basis) / basis * 100.0
        akz = any(b == k for b, _ in e.wicks)
        zeile.append(f"K{int(e.kid)}:{e.seite[0]}:{basis:.4f}"
                     f"@{dist:.3f}->{'JA' if akz else 'nein'}")
    print(f"{k:>5} {_zeit(k):>12} {hi[k]:>8.4f} "
          f"{hi[k]:>8.4f} {lo[k]:>8.4f} {cl[k]:>8.4f} "
          f"{piv if piv else '-':>3}  {' | '.join(zeile)}")

print("\n" + "=" * 118)
print("D) GESAMTZAHLEN")
print("=" * 118)
_alle_laeufe = 0
_ohne = 0
for e in alle:
    if not (66.5 <= float(e.basis) <= 70.5):
        continue
    _wb = {b for b, _ in e.wicks}
    for (s, t) in _laeufe(e):
        _alle_laeufe += 1
        if not any(b in _wb for b in range(s, t + 1)):
            _ohne += 1
print(f"  Durchstoss-Laeufe (Band 66.5..70.5): {_alle_laeufe} | "
      f"davon OHNE Docht: {_ohne} "
      f"({100.0 * _ohne / max(1, _alle_laeufe):.1f} %)")
print(f"  Summe akzeptierter Dochte (Band): "
      f"{sum(len(e.wicks) for e in alle if 66.5 <= float(e.basis) <= 70.5)}")
print("\nENDE E-34n/3")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
