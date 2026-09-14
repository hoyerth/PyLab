# -*- coding: utf-8 -*-
"""S2-SEGMENTKANDIDATEN -- kausale Konsolidierungsgrenzen am Split Bar 17.692.

Read-only. Laedt den arretierten Pickle-Cache (`_tmp_s2_scan_cache.pkl`,
SHA a86ad180...) und ermittelt -- OHNE jeden Blick in die Zukunft --
welche Kanten als `decke` / `boden` einer S2-Konsolidierung taugen.

Kernfrage (Anwender, 2026-09-11): `AUSSEN_*` ueber das GESAMTE Jahresfenster
ergaebe ein ~28-USD-Riesenband (2025-Spanne 28,2860..56,5250) und damit
denselben Fehler wie die Makrowand in August. Gesucht ist die **lokale**
Konsolidierung, in die der Split faellt.

Verfahren (alles kausal, nur Bars <= 17.692):
  1. Lookback-Fenster L: hi/lo der letzten L Bars.
  2. Kandidatenkanten = kausal existent UND lebend (`letzter Docht <= 96`)
     UND Basis innerhalb des Lookback-Fensters.
  3. decke = aeusserste OBEN-Kante, boden = aeusserste UNTEN-Kante.
  4. Bewertung der Kandidaten im H2-Fenster (Bars > 17.692): wie oft wird die
     Wand beruehrt (ein respektierter Konsolidierungsrand wird wiederholt
     getestet) -- das ist ein MASS, keine Definition.

Kalibrierung: dasselbe Verfahren an den arretierten AUG-Bars 644 / 848, gegen
die Sollwerte P9 (K67 69,9140 / K77 68,3700).

Ausfuehren:  .venv\\Scripts\\python.exe test/_tmp_s2_segment_kandidaten.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import pickle
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
PKL_S2 = ROOT / "test" / "_tmp_s2_scan_cache.pkl"
OUT = ROOT / "test" / "_tmp_s2_segment_kandidaten_out.txt"
NAME = "tmp_kanten_engine_replay"
SPLIT_S2 = 17692           # 2025-10-01T00:00 BKZ (aus _tmp_s2_scan_pipeline.py)
BUF: List[str] = []


def out(s: str = "") -> None:
    BUF.append(s)


def lade(name: str, pfad: Path):
    spec = importlib.util.spec_from_file_location(name, pfad)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ENGINE_SHA = hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
eng = lade(NAME, ENGINE_P)
cfg = eng.StraightEdgeHarnessKonfiguration()

def trage(d: Dict, key: str, e, k: int, px: float) -> None:
    """Kandidat aufnehmen, falls er weiter aussen liegt als der Bestand.

    OBEN: hoechste Basis gewinnt. UNTEN: tiefste Basis gewinnt.

    Args:
        d: Ergebnisdict der Restriktion (``"OBEN"``/``"UNTEN"``).
        key: Seitenachse.
        e: Kandidatenkante.
        k: Bar, an dem ``e.basis`` gilt (Bar-Schnappschuss).
        px: Basiswert zum Zeitpunkt k.
    """
    if key not in d:
        d[key] = (e, k, px)
        return
    alt = d[key]
    weiter_aussen = (e.basis > alt[0].basis) if e.seite == "OBEN" \
        else (e.basis < alt[0].basis)
    if weiter_aussen:
        d[key] = (e, k, px)


def kandidaten(scan: Dict, alle: List, k: int,
               lookbacks: Tuple[int, ...]) -> Dict[str, Dict]:
    """Ermittelt Kandidatengrenzen unter mehreren lokalen Restriktionen.

    Kausalitaetsgrenze ist EXAKT ``_se_trades::_gegenkante`` (Q5/Q14):
    ``erster_pivot_bar + 2 <= k + 1`` -- SCHLAFENDE Kanten sind zulaessig,
    der Schlafstatus ist fuer die Grenzwahl unerheblich.

    Args:
        scan: Scan-Dict (``d``, ``n``).
        alle: ``edges + seeds``.
        k: Auswertungs-Bar (Split).
        lookbacks: Lookback-Laengen in Bars.

    Returns:
        ``{"restriktionen": {name: {"OBEN"/"UNTEN": (e, k, px), "_h", "_l"}},
        "kausal": [...], "lebend": [(e, last_bar), ...]}``.
    """
    d = scan["d"]
    hi = d["high"].to_numpy(float)
    lo = d["low"].to_numpy(float)
    cl = d["close"].to_numpy(float)
    kausal = [e for e in alle if e.erster_pivot_bar + 2 <= k + 1]
    lebend = []
    for e in kausal:
        bars = [b for b, _ in e.wicks if b <= k]
        if bars and max(bars) >= k - cfg.wall_live_bars:
            lebend.append((e, max(bars)))

    res: Dict[str, Dict] = {f"L{L}": {} for L in lookbacks}
    res["JAHR"] = {}
    res["PREISNAH"] = {}
    for L in lookbacks:
        a = max(0, k - L + 1)
        h_L = float(hi[a:k + 1].max())
        l_L = float(lo[a:k + 1].min())
        res[f"L{L}"]["_h"] = h_L
        res[f"L{L}"]["_l"] = l_L
        for e, _last in lebend:
            if l_L <= e.basis <= h_L:
                trage(res[f"L{L}"], e.seite, e, k, e.basis)
    # Jahresfenster = alle kausal existenten (unabhaengig von Liveness)
    res["JAHR"]["_h"] = float(hi[:k + 1].max())
    res["JAHR"]["_l"] = float(lo[:k + 1].min())
    for e in kausal:
        trage(res["JAHR"], e.seite, e, k, e.basis)
    # Nur lebende, unbeschraenkt
    res["PREISNAH"]["_h"] = float(hi[:k + 1].max())
    res["PREISNAH"]["_l"] = float(lo[:k + 1].min())
    for e, _last in lebend:
        trage(res["PREISNAH"], e.seite, e, k, e.basis)
    return {"restriktionen": res, "kausal": kausal, "lebend": lebend,
            "hi": hi, "lo": lo, "cl": cl}


def wand_statistik(e, hi: np.ndarray, lo: np.ndarray, a: int, b: int
                   ) -> Tuple[int, int]:
    """Beruehrungen der WAND im Fenster [a, b) -- kausal je Bar via basis_bei."""
    nah, durch = 0, 0
    for k in range(a, b):
        bs = e.basis_bei(k)
        if e.seite == "OBEN":
            if hi[k] >= bs:
                durch += 1
                if abs(hi[k] - bs) / bs * 100.0 <= 0.25:
                    nah += 1
        else:
            if lo[k] <= bs:
                durch += 1
                if abs(lo[k] - bs) / bs * 100.0 <= 0.25:
                    nah += 1
    return nah, durch


# ========================================================== S2
scan = pickle.loads(PKL_S2.read_bytes())
n = scan["n"]
d = scan["d"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
cl = d["close"].to_numpy(float)
ts = d["ts"].astype("datetime64[ns]").to_numpy()
alle = list(scan["edges"]) + list(scan["seeds"])
K = SPLIT_S2
H2 = n - K

out("=" * 108)
out("S2-SEGMENTKANDIDATEN -- kausale Konsolidierungsgrenzen am Split")
out("=" * 108)
out(f"Engine-SHA : {ENGINE_SHA}")
out(f"Cache      : _tmp_s2_scan_cache.pkl "
    f"{hashlib.sha256(PKL_S2.read_bytes()).hexdigest()[:24]}...  "
    f"({PKL_S2.stat().st_size} B)")
out(f"Split      : Bar {K} = {np.datetime64(ts[K], 'm')} BKZ  |  "
    f"n {n}  |  H1 {K}  H2 {H2} Bars")
out(f"close[K]   : {cl[K]:.4f}   (letzte Kerze VOR dem H2-Fenster)")
out("")

# ---------------------------------------------------- A Marktkontext
out("A  MARKTKONTEXT (kausal: nur Bars <= Split)")
out(f"   {'Fenster':<10} {'von Bar':>8} {'bis':>8}  {'Tief':>8} {'Hoch':>8} "
    f"{'Breite USD':>10} {'%':>6}")
for L in (96, 240, 480, 960, 1920, 3840, 7680, 17693):
    a = max(0, K - L + 1)
    h = float(hi[a:K + 1].max())
    l = float(lo[a:K + 1].min())
    out(f"   L={L:<7} {a:>9} {K:>8}  {l:>8.4f} {h:>8.4f} "
        f"{h - l:>10.4f} {(h - l) / l * 100:>5.1f}%")
h_j, l_j = float(hi[:K + 1].max()), float(lo[:K + 1].min())
out(f"   {'JAHR':<10} {0:>9} {K:>8}  {l_j:>8.4f} {h_j:>8.4f} "
    f"{h_j - l_j:>10.4f} {(h_j - l_j) / l_j * 100:>5.1f}%  <-- Riesenband")
out("")
out("   Tageskerzen der letzten 12 Kalendertage vor dem Split:")
_tage: Dict[str, List[float]] = {}
for i in range(max(0, K - 1920), K + 1):
    dd = str(np.datetime64(ts[i], "D"))
    _tage.setdefault(dd, [float(hi[i]), float(lo[i])])
for dd in sorted(_tage)[-12:]:
    h, l = _tage[dd]
    out(f"      {dd}  H {h:>8.4f}  L {l:>8.4f}  Range {h - l:>7.4f}")
out("")

# ---------------------------------------------------- B Kantenlage
kb = kandidaten(scan, alle, K, (96, 240, 480, 960, 1920, 3840))
kausal, lebend = kb["kausal"], kb["lebend"]
out("B  KANTENLAGE AM SPLIT")
out(f"   kausal existent (Pivot+2 <= K+1) : {len(kausal)}")
out(f"   davon LEBEND (letzter Docht>K-96): {len(lebend)}")
_set = {id(e) for e, _ in lebend}
out(f"   Kanten im Scan gesamt            : {len(alle)} "
    f"(edges {len(scan['edges'])} + seeds {len(scan['seeds'])})")
out("")
auf = sorted(kausal, key=lambda e: -e.basis)
ab_ = sorted(kausal, key=lambda e: e.basis)
out("   aeusserste KAUSALE Kanten (die 6 hoechsten / 6 tiefsten):")
for tag, lst in (("OBEN", auf[:6]), ("UNTEN", ab_[:6])):
    for e in lst:
        bars = [b for b, _ in e.wicks if b <= K]
        last = max(bars) if bars else -1
        out(f"      {tag:<5} K{e.kid:<4} basis {e.basis:>8.4f}  "
            f"pivot {e.erster_pivot_bar:>6}  letzter Docht {last:>6}  "
            f"{'LEBEND' if id(e) in _set else 'dormant':<8} "
            f"status {e.status:<9} touches {e.touch_anzahl}  "
            f"Abstand {abs(e.basis - cl[K]):>7.4f} USD")
out("")

# ---------------------------------------------------- C Kandidaten
out("C  KANDIDATEN-SEGMENTGRENZEN")
out(f"   {'Restriktion':<12} {'decke':>18} {'boden':>18} "
    f"{'Band USD':>9} {'%':>6}  Position zu close {cl[K]:.4f}")
zeilen: List[Tuple[str, int, float, int, float, float]] = []
for name, r in kb["restriktionen"].items():
    d_o = r.get("OBEN")
    d_u = r.get("UNTEN")
    if d_o is None or d_u is None:
        out(f"   {name:<12} {'-- nicht besetzt --':>40}")
        continue
    bo, bu = d_o[0].basis, d_u[0].basis
    band = bo - bu
    out(f"   {name:<12} K{d_o[0].kid:<4} {bo:>10.4f}   "
        f"K{d_u[0].kid:<4} {bu:>10.4f}  {band:>9.4f} "
        f"{band / bu * 100:>5.1f}%  "
        f"{'INNEN' if bu < cl[K] < bo else 'AUSSERHALB'}")
    zeilen.append((name, d_o[0].kid, bo, d_u[0].kid, bu, band))
out("")
out("   Lookback-Fenster der Restriktionen (Grundlage der Auswahl):")
for name, r in kb["restriktionen"].items():
    out(f"      {name:<12} Fenster {r['_l']:.4f} .. {r['_h']:.4f}")
out("")

# ---------------------------------------------------- D Wand-Resonanz
out("D  WAND-RESONANZ IM H2-FENSTER (Mass, keine Definition)")
out("   'nah' = Docht innerhalb 0,25 % der Wand (Beruehrung).")
out("   'durch' = Docht jenseits der Wand (Durchstich).")
out(f"   {'Restriktion':<12} {'Seite':<6} {'Kante':>6} {'Basis@K':>9} "
    f"{'nah':>6} {'durch':>6} {'von':>6}  {'% nah':>6}")
for name, r in kb["restriktionen"].items():
    for seite in ("OBEN", "UNTEN"):
        if seite not in r:
            continue
        e = r[seite][0]
        nah, durch = wand_statistik(e, hi, lo, K, n)
        out(f"   {name:<12} {seite:<6} K{e.kid:<5} {e.basis:>9.4f} "
            f"{nah:>6} {durch:>6} {H2:>6}  {nah / H2 * 100:>5.1f}%")
out("")

# ---------------------------------------------------- E Referenz AUG
out("E  KALIBRIERUNG AN AUG (gleiches Verfahren, Sollwerte P9)")
out("   Soll: P9 decke K67 69,9140 / boden K77 68,3700  (Band 1,5440 USD)")
try:
    scan_a = eng._se_scan("AUG", cfg)
    scan_a["box_end_bar"] = scan_a["n"]
    alle_a = list(scan_a["edges"]) + list(scan_a["seeds"])
    for k_a in (644, 848, 1020):
        ka = kandidaten(scan_a, alle_a, k_a, (96, 240, 480, 960))
        out(f"   --- AUG-Bar {k_a} ---")
        for name, r in ka["restriktionen"].items():
            if "OBEN" not in r or "UNTEN" not in r:
                continue
            bo, bu = r["OBEN"][0].basis, r["UNTEN"][0].basis
            out(f"      {name:<8} K{r['OBEN'][0].kid:<4} {bo:>8.4f} / "
                f"K{r['UNTEN'][0].kid:<4} {bu:>8.4f}  "
                f"Band {bo - bu:>7.4f}")
        out(f"      kausal existent {len(ka['kausal'])} | "
            f"lebend {len(ka['lebend'])}")
except Exception as exc:                      # noqa: BLE001
    out(f"   AUG-Kalibrierung fehlgeschlagen: {exc!r}")
out("")

# ---------------------------------------------------- F H2-Struktur
out("F  H2-STRUKTUR (Wohin laeuft der Markt nach dem Split?)")
hi2, lo2 = hi[K:], lo[K:]
i_hi, i_lo = int(np.argmax(hi2)), int(np.argmin(lo2))
out(f"   H2-Hoch   {hi[K + i_hi]:.4f} @ Bar {K + i_hi} "
    f"({np.datetime64(ts[K + i_hi], 'm')})")
out(f"   H2-Tief   {lo[K + i_lo]:.4f} @ Bar {K + i_lo} "
    f"({np.datetime64(ts[K + i_lo], 'm')})")
out(f"   Spanne    {hi[K + i_hi] - lo[K + i_lo]:.4f} USD "
    f"({(hi[K + i_hi] - lo[K + i_lo]) / lo[K + i_lo] * 100:.1f}%)")
out(f"   Position des Splits im H2-Korridor: close {cl[K]:.4f} "
    f"-> {100 * (cl[K] - lo[K + i_lo]) / (hi[K + i_hi] - lo[K + i_lo]):.1f}% "
    f"vom H2-Tief")
out("")
out("   Quartalsbloecke in H2 (je ~983 Bars):")
_q = 983
for i in range(0, H2, _q):
    a, b = K + i, min(K + i + _q, n)
    out(f"      Bar {a:>6}..{b - 1:<6} ({np.datetime64(ts[a], 'D')}.."
        f"{np.datetime64(ts[b - 1], 'D')})  "
        f"Tief {lo[a:b].min():>8.4f}  Hoch {hi[a:b].max():>8.4f}  "
        f"Breite {hi[a:b].max() - lo[a:b].min():>7.4f}  "
        f"close {cl[b - 1]:>8.4f}")
out("")
out("   Laufende 96-Bar-Range in H2 -- die 5 engsten Fenster "
    "(Konsolidierungs-Kandidaten):")
_rng = []
for i in range(0, H2 - 96, 24):
    a, b = K + i, K + i + 96
    _rng.append((float(hi[a:b].max() - lo[a:b].min()), a, b,
                 float(lo[a:b].min()), float(hi[a:b].max())))
for w, a, b, ll, hh in sorted(_rng)[:5]:
    out(f"      Bar {a:>6}..{b:<6} ({np.datetime64(ts[a], 'D')}.."
        f"{np.datetime64(ts[b - 1], 'D')})  "
        f"{ll:>8.4f} .. {hh:>8.4f}  Breite {w:>7.4f}")
out("")
out("   Neu-Aufloesung der lokalen Grenzen im H2-Verlauf "
    "(gleiches Verfahren, Lookback 960):")
out(f"      {'Bar':>7} {'Datum':<12} {'decke':>18} {'boden':>18} "
    f"{'Band':>8}  {'close':>8}")
for _k in (K, K + 480, K + 960, K + 1920, K + 2880, n - 1):
    if _k >= n:
        continue
    _ka = kandidaten(scan, alle, _k, (960,))
    _r = _ka["restriktionen"]["L960"]
    if "OBEN" not in _r or "UNTEN" not in _r:
        out(f"      {_k:>7} {str(np.datetime64(ts[_k], 'D')):<12} "
            f"{'-- nicht besetzt --':>38}")
        continue
    _bo, _bu = _r["OBEN"][0].basis, _r["UNTEN"][0].basis
    out(f"      {_k:>7} {str(np.datetime64(ts[_k], 'D')):<12} "
        f"K{_r['OBEN'][0].kid:<4} {_bo:>10.4f}  "
        f"K{_r['UNTEN'][0].kid:<4} {_bu:>10.4f}  "
        f"{_bo - _bu:>8.4f}  {cl[_k]:>8.4f}")
out("")

out("=" * 108)
out("Engine-SHA nach Lauf: " + hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
    + ("  UNVERAENDERT" if hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
       == ENGINE_SHA else "  DRIFT"))
out("=" * 108)

rep = "\n".join(BUF)
OUT.write_text(rep, encoding="utf-8")
print(rep)
