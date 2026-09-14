# -*- coding: utf-8 -*-
"""S2-DETAIL (Schritt 3b) -- H2-Einzeltrades, AUG-Ursachenisolation, Oeffnung.

Drei Teile, read-only, Engine-SHA unveraendert:

A  AUG-2x2-Ursachenisolation der Fidelity-Abweichung
   (KantenSicht kausal vs. Engine-Lookahead) x (Niveau-Override 69.87 ja/nein)
   gegen den arretierten P4-Messwert Z2 = 17 Trades / +65.504879 R.

B  S2-H2-Einzeltrades BASE vs. VD_K408_409 (bar-scharf, tp2/sl/entry/r).
   Nur H2 (``entry_bar >= 17692``) -- H1 ist in allen V-D-Laeufen identisch,
   weil ``start_scope_bar = SPLIT``.

C  Endogene Oeffnungsbars im H2: ``aufloese_reclaim_at_opening`` (Sleep-Bypass
   der Erfolgsfamilie) ueber den S2-Katalog -- ohne August-Literal.

Ausfuehren:  .venv\\Scripts\\python.exe test/_tmp_s2_vd_detail.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import pickle
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
VD_P = ROOT / "test" / "_tmp_vd_vertrag_entwurf.py"
RENDERER_P = ROOT / "test" / "tmp_png_aug_sichttest.py"
PKL_S2 = ROOT / "test" / "_tmp_s2_scan_cache.pkl"
OUT = ROOT / "test" / "_tmp_s2_vd_detail_out.txt"
NAME = "tmp_kanten_engine_replay"
SPLIT = 17692
AUG_Z2 = (17, 65.504879)

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
    ADAPTER_V015, Hook2Ergebnis, Hook2ZielModus, PhasenRegimeAdapter,
)

KS, KR, RM, GW = vd.KantenSicht, vd.KantenRolle, vd.RangModus, vd.GegenkantenWahl
KT, SEG, AD = vd.KantenReferenz, vd.SegmentVD, vd.VDAdapterEntwurf

P9 = ADAPTER_V015.segmente[0]
AD_P9 = PhasenRegimeAdapter(start_scope_bar=848, segmente=(P9,))

_lines = RENDERER_P.read_text(encoding="utf-8").splitlines()
_ns: Dict = {"P": ENGINE_P, "ast": __import__("ast"), "copy": copy,
             "Hook2ZielModus": Hook2ZielModus, "_Hook2ZielModus": Hook2ZielModus,
             "engine": eng}
exec(compile("\n".join(_lines[540:660]), "<patch_slice>", "exec"), _ns)
PATCHED: str = _ns["patched_src"]

cfg = eng.StraightEdgeHarnessKonfiguration()

out("=" * 104)
out("S2-DETAIL -- H2-Einzeltrades / AUG-Ursachenisolation / Oeffnungsbars")
out("=" * 104)
out(f"Engine-SHA : {ENGINE_SHA}  (arretiert)")
out(f"VD-Entwurf : {hashlib.sha256(VD_P.read_bytes()).hexdigest()}")
out("")


def lauf(ad, scan) -> Tuple[list, Dict, float]:
    ns = dict(eng.__dict__)
    ns["_Hook2ZielModus"] = Hook2ZielModus
    ns["_hook"] = ad
    exec(compile(PATCHED, f"<{getattr(ad, 'name', 'ad')}>", "exec"), ns)
    t0 = time.time()
    s, st = ns["_se_trades"](copy.deepcopy(scan), cfg)
    return s, st, time.time() - t0


# ===================================================================== A
scan_aug = eng._se_scan("AUG", cfg)
_n_aug = scan_aug["n"]
scan_aug["box_end_bar"] = _n_aug
alle_aug = list(scan_aug["edges"]) + list(scan_aug["seeds"])
by_kid_aug = {e.kid: e for e in alle_aug}
_d_aug = scan_aug["d"]
_hi_a = _d_aug["high"].to_numpy(dtype=float)
_lo_a = _d_aug["low"].to_numpy(dtype=float)


class L2AUG:
    """Zielmechanismus SEG_BODEN (P9) mit zwei Schaltern."""

    def __init__(self, name: str, kausal: bool, override: bool):
        self.name = name
        self.kausal = kausal
        self.override = override
        self.start_scope_bar = 848
        self.segmente = (P9,)
        self.log: List[str] = []

    def _seg_bei(self, k):
        return P9 if k >= 848 else None

    def aktive_phase_bei(self, k):
        return self._seg_bei(k)

    def niveau_override_bei(self, k, kid):
        if not self.override:
            return None
        return AD_P9.niveau_override_bei(k, kid)

    def angewandte_basis(self, k, kid, basis_engine):
        ov = self.niveau_override_bei(k, kid)
        return float(ov) if ov is not None else float(basis_engine)

    def hook_1_freigabe_kid(self, k, sweep_px, richtung, kanten):
        return None

    def hook_2_ziel(self, k, richtung):
        seg = self._seg_bei(k)
        if seg is None:
            return Hook2Ergebnis(Hook2ZielModus.MAKRO, None)
        kid = seg.boden.kid if richtung == "SHORT" else seg.decke.kid
        e = by_kid_aug.get(kid)
        if e is None:
            return Hook2Ergebnis(Hook2ZielModus.BLOCKIERT, None)
        if self.kausal and not (e.erster_pivot_bar + 2 <= k + 1):
            return Hook2Ergebnis(Hook2ZielModus.BLOCKIERT, None)
        b = self.angewandte_basis(k, kid, e.basis_bei(k))
        return Hook2Ergebnis(Hook2ZielModus.PHASE, b)

    def hook_3_boden_reclaim(self, k):
        return AD_P9.hook_3_boden_reclaim(k) if self._seg_bei(k) else None


out("A  AUG-URSACHENISOLATION (Z2 = 17 / +65.504879 R arretiert)")
out("-" * 104)
out(f"{'Lauf':<26}{'Trd':>5}{'R':>14}   {'Kante':<10}")
for nm, kau, ov in (("Z2-Repro kausal=F ov=F", False, False),
                    ("kausal=F ov=T", False, True),
                    ("kausal=T ov=F", True, False),
                    ("kausal=T ov=T", True, True)):
    s, st, dt = lauf(L2AUG(nm, kau, ov), scan_aug)
    out(f"{nm:<26}{len(s):>5}{sum(t.r for t in s):>+14.6f}   ({dt:.1f} s)")
out("")
out("Hinweis: 'kausal=T' gemaess KantenSicht.basis_kausal (Pivot+2<=k+1).")
out("K77 (boden, SHORT-Ziel) hat Pivot 934 -> Geburt 991; SHORT-Bars")
out("903/980/981 sind damit strukturell blockiert (E-17).")
out("")

# ===================================================================== B
scan = pickle.loads(PKL_S2.read_bytes())
n = scan["n"]
scan["box_end_bar"] = n
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
alle = list(scan["edges"]) + list(scan["seeds"])


def _sich_s2(k: int):
    return [KS(e.kid, e.seite, e.basis_bei(k), e.erster_pivot_bar,
               (e.wicks[0][0] if e.wicks else None),
               (e.wicks[0][1] if e.wicks else None)) for e in alle]


class L2S2:
    def __init__(self, name, seg, ziel="VD"):
        self.name = name
        self.seg = seg
        self.ziel = ziel
        self.start_scope_bar = SPLIT
        self.segmente = (seg,) if seg else ()
        self.ad = AD(start_scope_bar=SPLIT, segmente=(seg,)) if seg else None
        self._cache: Dict[int, list] = {}
        self.log: List[str] = []

    def _sichten(self, k):
        c = self._cache.get(k)
        if c is None:
            c = _sich_s2(k)
            self._cache[k] = c
        return c

    def aktive_phase_bei(self, k):
        return self.seg if (self.seg is not None and k >= SPLIT) else None

    def niveau_override_bei(self, k, kid):
        return None

    def angewandte_basis(self, k, kid, basis_engine):
        return float(basis_engine)

    def hook_1_freigabe_kid(self, k, sweep_px, richtung, kanten):
        return None

    def hook_2_ziel(self, k, richtung):
        if self.ziel == "MAKRO" or self.seg is None or k < SPLIT:
            return Hook2Ergebnis(Hook2ZielModus.MAKRO, None)
        sw = float(hi[k]) if richtung == "SHORT" else float(lo[k])
        z = self.ad.ziel_preis_kausal(self.seg, richtung, self._sichten(k), k, sw)
        if z is None:
            return Hook2Ergebnis(Hook2ZielModus.BLOCKIERT, None)
        return Hook2Ergebnis(Hook2ZielModus.PHASE, z)

    def hook_3_boden_reclaim(self, k):
        return None


SEG_K408_409 = SEG("P_K408_409", KT(kind="kid", kid=408),
                   KT(kind="kid", kid=409), rang_modus=RM.NAEHE)

out("B  S2-H2-EINZELTRADES (entry_bar >= 17692)")
out("-" * 104)
rennen: Dict[str, list] = {}
for nm, ad in (("BASE(MAKRO)", L2S2("BASE", None, "MAKRO")),
               ("VD_K408_409", L2S2("VD_K408_409", SEG_K408_409, "VD"))):
    s, st, dt = lauf(ad, scan)
    rennen[nm] = s
    h2 = sorted([t for t in s if t.entry_bar >= SPLIT], key=lambda x: x.entry_bar)
    out(f"{nm}: gesamt {len(s)} / {sum(t.r for t in s):+.6f} R | "
        f"H2 {len(h2)} / {sum(t.r for t in h2):+.6f} R  ({dt:.1f} s)")
out("")

_b = {(t.entry_bar, t.richtung): t for t in rennen["BASE(MAKRO)"] if t.entry_bar >= SPLIT}
_v = {(t.entry_bar, t.richtung): t for t in rennen["VD_K408_409"] if t.entry_bar >= SPLIT}
out(f"{'entry':>6} {'bar':>6} {'ri':<5} {'kid':>4} | "
    f"{'tp2_base':>9} {'R_base':>10} | {'tp2_vd':>9} {'R_vd':>10} | dR")
for key in sorted(set(_b) | set(_v), key=lambda t: (t[0], t[1])):
    tb = _b.get(key)
    tv = _v.get(key)
    eb = key[0]
    bar = (tv or tb).bar
    ri = (tv or tb).richtung
    kid = (tv or tb).kid
    out(f"{eb:>6} {bar:>6} {ri:<5} K{kid:<3} | "
        f"{(tb.tp2 if tb else float('nan')):>9.4f} "
        f"{(tb.r if tb else float('nan')):>+10.6f} | "
        f"{(tv.tp2 if tv else float('nan')):>9.4f} "
        f"{(tv.r if tv else float('nan')):>+10.6f} | "
        f"{((tv.r if tv else 0.0) - (tb.r if tb else 0.0)):>+8.4f}")
out("")

# ===================================================================== C
out("C  ENDOGENE OEFFNUNGSBARS IM H2 (Sleep-Bypass der Erfolgsfamilie)")
out("-" * 104)
markt = {"high": hi, "low": lo, "close": cl}
ZAHL: Dict[int, int] = {}
ERSTE: Dict[int, int] = {}
letzte: Dict[int, int] = {}
for k in range(SPLIT, n):
    sich = _sich_s2(k)
    ev = AD.aufloese_reclaim_at_opening(k, markt, sich, {
        "sweep_mindestdurchstich_pct": cfg.sweep_mindestdurchstich_pct,
        "max_sweep_ueberdehnung_pct": cfg.max_sweep_ueberdehnung_pct})
    if ev is None:
        continue
    kid, basis, seite, stufe = ev
    ZAHL[kid] = ZAHL.get(kid, 0) + 1
    ERSTE.setdefault(kid, k)
    letzte[kid] = k
    if k - ERSTE[kid] > 1:
        pass
out(f"{'kid':>5} {'Seite':>6} {'Anz':>5} {'erster':>8} {'letzter':>8} "
    f"{'Basis':>9}")
_kinder = {e.kid: e for e in alle}
for kid, anz in sorted(ZAHL.items(), key=lambda t: t[1], reverse=True)[:15]:
    e = _kinder[kid]
    out(f"K{kid:<4} {e.seite:>6} {anz:>5} {ERSTE[kid]:>8} {letzte[kid]:>8} "
        f"{e.basis_bei(ERSTE[kid]):>9.4f}")
out("")
out(f"K408 (Kandidatendecke) Oeffnungs-Reclaims: {ZAHL.get(408, 0)}")
out(f"K409 (Kandidatenboden) Oeffnungs-Reclaims: {ZAHL.get(409, 0)}")
out("")

out("=" * 104)
out("Engine-SHA nach Lauf: " + hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
    + ("  UNVERAENDERT" if hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
       == ENGINE_SHA else "  DRIFT"))
out("=" * 104)

rep = "\n".join(BUF)
OUT.write_text(rep, encoding="utf-8")
print("geschrieben: " + str(OUT))
