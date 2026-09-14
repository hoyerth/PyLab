# -*- coding: utf-8 -*-
"""S2-STRESSTEST (Schritt 3) -- V-D-Schleife gegen die S2-Baseline.

Read-only. Nutzt den arretierten S2-Pickle-Cache und den V-D-Entwurf
(``_tmp_vd_vertrag_entwurf.py``). Engine-SHA bleibt
``4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a``:
die V-D-Regeln werden ueber den bereits im Renderer benutzten RAM-Patch
(``patched_src``) eingebunden -- kein Projektdatei-Eingriff.

Zwei Buecher, strikt getrennt (analog ``_tmp_s2_baseline_ref.py``):

* ``box_end`` (Partition)     = 17.692  -> H1/H2-Statistik.
* ``scan['box_end_bar']``     = 21.624  -> Laufgrenze der Engine.

Auflage 3: **ausschliesslich relative Logik** -- kein August-Literal
(67.6355 / 68.3700 / 69.8700 / 69.9140). Segmentgrenzen werden per
SEMANTISCHER ROLLE oder per ``kid`` aus dem S2-Scan selbst aufgeloest.

Gemessen werden (je Lauf getrennt nach H1/H2):

  BASE              ungepatchte Engine (Referenz, == -186.055940 R)
  MAKRO             gepatcht, hook_2 -> MAKRO_ENGINE (Selbstkontrolle == BASE)
  VD_AUSSEN_ABSOLUT Rollen AUSSEN_* unter RangModus.ABSOLUT (Riesenband)
  VD_NAEHE_ENVELOPE Rollen AUSSEN_* unter RangModus.NAEHE (naechste Wand)
  VD_K408_409       kid-Referenzen K408/K409 (Split-Konsolidierung)
  VD_K408_409_HALF  wie oben, ziel_anteil = 0.5

Zuvor laeuft ein AUG-FIDELITY-Selbstcheck (VD_K67_77 @ 848) gegen den
arretierten P4-Messwert ``Z2 = 17 Trades / +65.504879 R``.

Ausfuehren:  .venv\\Scripts\\python.exe test/_tmp_s2_vd_stresstest.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import pickle
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
VD_P = ROOT / "test" / "_tmp_vd_vertrag_entwurf.py"
RENDERER_P = ROOT / "test" / "tmp_png_aug_sichttest.py"
PKL_S2 = ROOT / "test" / "_tmp_s2_scan_cache.pkl"
OUT = ROOT / "test" / "_tmp_s2_vd_stresstest_out.txt"
NAME = "tmp_kanten_engine_replay"
SPLIT = 17692
AUG_LITERALE = (67.6355, 68.3700, 69.8700, 69.9140)
AUG_Z2 = (17, 65.504879)       # arretierter P4-Messwert (SEG_BODEN kausal)

BUF: List[str] = []


def out(s: str = "") -> None:
    BUF.append(s)
    print(s, flush=True)


def lade(name: str, pfad: Path):
    spec = importlib.util.spec_from_file_location(name, pfad)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ENGINE_SHA = hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
eng = lade(NAME, ENGINE_P)
vd = lade("_tmp_vd_vertrag_entwurf", VD_P)

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    Hook2Ergebnis, Hook2ZielModus,
)

KS, KR, RM, GW = vd.KantenSicht, vd.KantenRolle, vd.RangModus, vd.GegenkantenWahl
KT, SEG, AD = vd.KantenReferenz, vd.SegmentVD, vd.VDAdapterEntwurf

# --------------------------------------------------- RAM-Patch aus Renderer
_lines = RENDERER_P.read_text(encoding="utf-8").splitlines()
_ns: Dict = {"P": ENGINE_P, "ast": __import__("ast"), "copy": copy,
             "Hook2ZielModus": Hook2ZielModus, "_Hook2ZielModus": Hook2ZielModus,
             "engine": eng}
exec(compile("\n".join(_lines[540:660]), "<patch_slice>", "exec"), _ns)
PATCHED: str = _ns["patched_src"]

out("=" * 104)
out("S2-STRESSTEST -- V-D-Schleife (PHASE_EIGEN / NAEHE / KantenSicht)")
out("=" * 104)
out(f"Engine-SHA  : {ENGINE_SHA}  (arretiert)")
out(f"VD-Entwurf  : {hashlib.sha256(VD_P.read_bytes()).hexdigest()}")
out(f"Renderer    : {hashlib.sha256(RENDERER_P.read_bytes()).hexdigest()}")
out(f"PATCHED     : {len(PATCHED)} Zeichen aus tmp_png_aug_sichttest.py")
out("")

# ======================================================= AUG-Fidelity-Check
cfg = eng.StraightEdgeHarnessKonfiguration()
scan_aug = eng._se_scan("AUG", cfg)
_n_aug = scan_aug["n"]
scan_aug["box_end_bar"] = _n_aug          # Voll-Lauf, wie P4-Probe
_alle_aug = list(scan_aug["edges"]) + list(scan_aug["seeds"])


def _sich_aug(k: int):
    return [KS(e.kid, e.seite, e.basis_bei(k), e.erster_pivot_bar,
               (e.wicks[0][0] if e.wicks else None),
               (e.wicks[0][1] if e.wicks else None)) for e in _alle_aug]


class L2VD:
    """Zeitfenster-Adapter: S2/S1 endogen, AUG-Fidelity per kid."""

    def __init__(self, name: str, seg, start: int, scan, sichter, ziel: str):
        self.name = name
        self.seg = seg
        self.start_scope_bar = start
        self.segmente = (seg,) if seg is not None else ()
        self.scan = scan
        self.sichter = sichter
        self.ziel = ziel
        self._cache: Dict[int, list] = {}
        if seg is not None:
            self.ad = AD(start_scope_bar=start, segmente=(seg,))
        self.log: List[str] = []

    def _sichten(self, k: int):
        c = self._cache.get(k)
        if c is None:
            c = self.sichter(k)
            self._cache[k] = c
        return c

    # --- Rueckgrat -------------------------------------------------------
    def aktive_phase_bei(self, k: int):
        return self.seg if (self.seg is not None
                            and k >= self.start_scope_bar) else None

    def niveau_override_bei(self, k: int, kid: int):
        return None

    def angewandte_basis(self, k: int, kid: int, basis_engine: float) -> float:
        return float(basis_engine)

    def hook_1_freigabe_kid(self, k, sweep_px, richtung, kanten):
        return None

    def hook_2_ziel(self, k: int, richtung: str) -> Hook2Ergebnis:
        if self.ziel == "MAKRO":
            return Hook2Ergebnis(Hook2ZielModus.MAKRO, None)
        if self.seg is None or k < self.start_scope_bar:
            return Hook2Ergebnis(Hook2ZielModus.MAKRO, None)
        sw = float(self._hi[k]) if richtung == "SHORT" else float(self._lo[k])
        z = self.ad.ziel_preis_kausal(self.seg, richtung,
                                      self._sichten(k), k, sw)
        if z is None:
            return Hook2Ergebnis(Hook2ZielModus.BLOCKIERT, None)
        return Hook2Ergebnis(Hook2ZielModus.PHASE, z)

    def hook_3_boden_reclaim(self, k: int):
        return None

    # --- Marktdaten-Anbindung -------------------------------------------
    def binde_markt(self, scan) -> None:
        d = scan["d"]
        self._hi = d["high"].to_numpy(dtype=float)
        self._lo = d["low"].to_numpy(dtype=float)


def lauf(ad: L2VD, scan) -> Tuple[list, Dict, float]:
    ns = dict(eng.__dict__)
    ns["_Hook2ZielModus"] = Hook2ZielModus
    ns["_hook"] = ad
    exec(compile(PATCHED, f"<{ad.name}>", "exec"), ns)
    t0 = time.time()
    s, st = ns["_se_trades"](copy.deepcopy(scan), cfg)
    return s, st, time.time() - t0


def kurz(st: Dict) -> Dict:
    return {k: v for k, v in st.items() if isinstance(v, int)}


def zeilen(tag: str, s: list, scan, split: Optional[int]) -> None:
    summe = sum(t.r for t in s)
    out(f"--- {tag}: {len(s)} Trades / {summe:+.6f} R ---")
    if split is None:
        for t in sorted(s, key=lambda x: x.bar):
            out(f"      bar {t.bar:>6} entry {t.entry_bar:>6} {t.richtung:<5} "
                f"K{t.kid:<4} R {t.r:>+10.6f}  tp2 {t.tp2:>9.4f}  sl {t.sl:>9.4f}")
        return
    h1 = [t for t in s if t.entry_bar < split]
    h2 = [t for t in s if t.entry_bar >= split]
    out(f"      H1 {len(h1):>3} / {sum(t.r for t in h1):+12.6f} R   |   "
        f"H2 {len(h2):>3} / {sum(t.r for t in h2):+12.6f} R")
    pos_h2 = [t for t in h2 if t.r > 0]
    out(f"      H2 positiv: {len(pos_h2)}  |  H2 tp2-Werte: "
        f"{sorted({round(t.tp2, 4) for t in h2})[:8]}")


# --- AUG-Selbstcheck (Fidelity) -----------------------------------------
out("A  AUG-FIDELITY-SELBSTCHECK (VD_K67_77 @ start 848)")
out("-" * 104)
seg_aug = SEG(phasen_id="P9_FIDELITY",
              decke=KT(kind="kid", kid=67),
              boden=KT(kind="kid", kid=77),
              gegenkante_wahl=GW.PHASE_EIGEN,
              rang_modus=RM.NAEHE)
ad_aug = L2VD("AUG_VD_K67_77", seg_aug, 848, scan_aug, _sich_aug, "VD")
ad_aug.binde_markt(scan_aug)
ad_aug.ad.verifiziere([(e.kid, e.seite, e.basis_bei(848)) for e in _alle_aug])
s_aug, st_aug, dt_aug = lauf(ad_aug, scan_aug)
out(f"Soll (P4/Z2, SEG_BODEN kausal) : {AUG_Z2[0]} Trades / {AUG_Z2[1]:+.6f} R")
zeilen(f"AUG_VD_K67_77 ({dt_aug:.1f} s)", s_aug, scan_aug, None)
_ist = (len(s_aug), round(sum(t.r for t in s_aug), 6))
out(f"FIDELITY: {'OK' if _ist == (AUG_Z2[0], round(AUG_Z2[1], 6)) else 'ABWEICHUNG'}"
    f"   ist={_ist}")
out(f"stats: {kurz(st_aug)}")
out("")

# ------------------------------------------------------------- S2-Varianten
scan = pickle.loads(PKL_S2.read_bytes())
n = scan["n"]
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
ts = d["ts"].to_numpy()
scan["box_end_bar"] = n                   # Laufgrenze (VOLL)
alle = list(scan["edges"]) + list(scan["seeds"])


def _sich_s2(k: int):
    return [KS(e.kid, e.seite, e.basis_bei(k), e.erster_pivot_bar,
               (e.wicks[0][0] if e.wicks else None),
               (e.wicks[0][1] if e.wicks else None)) for e in alle]


out("B  S2-KONTEXT")
out("-" * 104)
out(f"box_end (Partition) = {SPLIT}   scan['box_end_bar'] (Laufgrenze) = {n}")
out(f"close[Split] = {cl[SPLIT]:.4f}   H1 {SPLIT} Bars / H2 {n - SPLIT} Bars")
out(f"August-Literale {AUG_LITERALE} -- alle oberhalb S2-Max "
    f"{hi.max():.4f}? {all(x > hi.max() for x in AUG_LITERALE)}")
out("")

# BASE (ungepatcht)
t0 = time.time()
base, st_base = eng._se_trades(copy.deepcopy(scan), cfg)
dt_base = time.time() - t0
out("C  LAEUFE")
out("-" * 104)
zeilen(f"BASE ungepatcht ({dt_base:.1f} s)", base, scan, SPLIT)
out(f"   stats: {kurz(st_base)}")
out("")

# Segmente
SEG_AUSSEN_ABS = SEG("P_AUSSEN_ABS",
                     KT(kind="rolle", rolle=KR.AUSSEN_OBEN),
                     KT(kind="rolle", rolle=KR.AUSSEN_UNTEN),
                     rang_modus=RM.ABSOLUT)
SEG_AUSSEN_NAEHE = SEG("P_AUSSEN_NAEHE",
                       KT(kind="rolle", rolle=KR.AUSSEN_OBEN),
                       KT(kind="rolle", rolle=KR.AUSSEN_UNTEN),
                       rang_modus=RM.NAEHE)
SEG_K408_409 = SEG("P_K408_409", KT(kind="kid", kid=408),
                   KT(kind="kid", kid=409), rang_modus=RM.NAEHE)
SEG_K408_409_H = SEG("P_K408_409_HALF", KT(kind="kid", kid=408),
                     KT(kind="kid", kid=409), ziel_anteil=0.5)

VARIANTEN = [
    ("MAKRO         ", None, "MAKRO"),
    ("VD_AUSSEN_ABS ", SEG_AUSSEN_ABS, "VD"),
    ("VD_NAEHE_ENV  ", SEG_AUSSEN_NAEHE, "VD"),
    ("VD_K408_409   ", SEG_K408_409, "VD"),
    ("VD_K408_409_H ", SEG_K408_409_H, "VD"),
]

ERGEBNIS: Dict[str, list] = {"BASE": base}
for tag, seg, ziel in VARIANTEN:
    ad = L2VD(tag.strip(), seg, SPLIT, scan, _sich_s2, ziel)
    ad.binde_markt(scan)
    if seg is not None:
        ad.ad.verifiziere([(e.kid, e.seite, e.basis_bei(SPLIT)) for e in alle])
    s, st, dt = lauf(ad, scan)
    ERGEBNIS[tag.strip()] = s
    zeilen(f"{tag} ({dt:.1f} s)", s, scan, SPLIT)
    out(f"   stats: {kurz(st)}")
    out("")

out("D  GEGENUEBERSTELLUNG (V-D vs. Baseline, H1/H2 getrennt)")
out("-" * 104)
out(f"{'Lauf':<16}{'Trd':>5}{'R gesamt':>14}{'H1 Trd':>8}{'H1 R':>14}"
    f"{'H2 Trd':>8}{'H2 R':>14}{'H2+':>5}")
b = ERGEBNIS["BASE"]
_out = []
for name, s in ERGEBNIS.items():
    h1 = [t for t in s if t.entry_bar < SPLIT]
    h2 = [t for t in s if t.entry_bar >= SPLIT]
    out(f"{name:<16}{len(s):>5}{sum(t.r for t in s):>+14.6f}"
        f"{len(h1):>8}{sum(t.r for t in h1):>+14.6f}"
        f"{len(h2):>8}{sum(t.r for t in h2):>+14.6f}"
        f"{sum(1 for t in h2 if t.r > 0):>5}")
out("")
out(f"Delta gesamt gegen BASE ({sum(t.r for t in b):+.6f} R):")
for name, s in ERGEBNIS.items():
    if name == "BASE":
        continue
    out(f"   {name:<16} {sum(t.r for t in s) - sum(t.r for t in b):>+14.6f} R")
out("")

out("=" * 104)
out("Engine-SHA nach Lauf: " + hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
    + ("  UNVERAENDERT" if hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
       == ENGINE_SHA else "  DRIFT"))
out("=" * 104)

rep = "\n".join(BUF)
OUT.write_text(rep, encoding="utf-8")
print("geschrieben: " + str(OUT))
