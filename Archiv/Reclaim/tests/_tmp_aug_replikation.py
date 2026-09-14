# -*- coding: utf-8 -*-
"""PHASE 2/3 (read-only) -- VOLLSTAENDIGER AUGUST-REPLIKATIONSBEWEIS (Ebene 2).

Vier Laeufe trennen die zwei Fragen, die bisher vermischt wurden:

  R0  Ebene 1, kid-Bindung, Ziel = PROVENIENZ (PHASE)   -> arretierte Referenz
  R1  Ebene 2, ROLLEN-Bindung (AUSSEN_OBEN/RECLAIM),    -> RESOLVER-BEWEIS
      Ziel = PROVENIENZ (PHASE)                            (Ziel unveraendert!)
  R2  Ebene 1, kid-Bindung, Ziel = GEGENKANTE_RELATIV   -> Preis des Niveaus
  R3  Ebene 2, ROLLEN-Bindung, Ziel = GEGENKANTE_RELATIV-> Kombination

Kernaussage-Design: R1 isoliert den Resolver, indem das Zielmechanisma
konstant gehalten wird. R2/R3 messen den Effekt des Niveauwechsels.

Sollwert Ebene 1: 17 Trades / +65.835576 R (H1 8/+38.919584 | H2 9/+26.915992).

Ausfuehren:  .venv\\Scripts\\python.exe test/_tmp_aug_replikation.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
BUF: List[str] = []


def out(s: str = "") -> None:
    BUF.append(s)


def load_engine(name: str):
    spec = importlib.util.spec_from_file_location(name, ENGINE_P)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# LOADER-NAME FIXIERT (Auflage 4): identisch fuer dump und load.
ENGINE_MODNAME = "tmp_kanten_engine_replay"
eng = load_engine(ENGINE_MODNAME)

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V015, BodenReclaimSpec, Hook2Ergebnis, Hook2ZielModus,
    PhasenRegimeAdapter,
)

# Entwurf (Ebene 2) laden -- reine Wertedomaene, kein Engine-Import.
_vd_spec = importlib.util.spec_from_file_location(
    "_vd_contract", ROOT / "test" / "_tmp_vd_vertrag_entwurf.py")
_vd = importlib.util.module_from_spec(_vd_spec)
sys.modules["_vd_contract"] = _vd
_vd_spec.loader.exec_module(_vd)
KantenReferenz = _vd.KantenReferenz
KantenRolle = _vd.KantenRolle
NiveauModus = _vd.NiveauModus
VDAdapterEntwurf = _vd.VDAdapterEntwurf

ENGINE_SHA = hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
n = scan["n"]
BOX = scan["box_end_bar"]
scan["box_end_bar"] = n
SOLL = (17, 65.835576, 8, 38.919584, 9, 26.915992)

d = scan["d"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
op = d["open"].to_numpy(float)
cl = d["close"].to_numpy(float)
alle = list(scan["edges"]) + list(scan["seeds"])
by_kid = {e.kid: e for e in alle}
seite_edges = {"OBEN": [e for e in alle if e.seite == "OBEN"],
               "UNTEN": [e for e in alle if e.seite == "UNTEN"]}


def exists(e, k: int) -> bool:
    return e.ist_aktiv_bei(k) and e.erster_pivot_bar + 2 <= k + 1


# ---- P9 bleibt ARRETIERT (Ebene 1, inkl. G4-Literal und K67-Override) ------
P9 = ADAPTER_V015.segmente[0]
AD_P9 = PhasenRegimeAdapter(start_scope_bar=848, segmente=(P9,))

# ---- P10 (Ebene 2) als reine Wertedomaene ---------------------------------
P10_START, P10_END = 1021, n - 1
OFFEN_BAR = 1075          # gemessen (Phase 3.1): K82 STUFE_1_IN_BAR


@dataclass(frozen=True)
class P10Local:
    """Minimaler Traeger der P10-Daten (Ebene 2)."""

    start_bar: int
    end_bar: int
    decke: object
    boden: object
    ziel_short: float
    ziel_long: float
    touch_band_pct: float = 0.12


def baue_p10(rollen: bool, band: float = 0.12) -> P10Local:
    if rollen:
        decke = KantenReferenz(kind="rolle", rolle=KantenRolle.AUSSEN_OBEN)
        boden = KantenReferenz(kind="rolle",
                               rolle=KantenRolle.RECLAIM_AT_OPENING)
    else:
        decke = KantenReferenz(kind="kid", kid=67, provenienz_basis=69.9140)
        boden = KantenReferenz(kind="kid", kid=82, provenienz_basis=67.6355)
    return P10Local(P10_START, P10_END, decke, boden,
                    ziel_short=67.6355, ziel_long=69.9140,
                    touch_band_pct=band)


class L2Adapter:
    """Ebene-1/2-Adapter: P9 arrestiert, P10 dynamisch.

    Args:
        p10: P10-Traeger (Rollen- oder Kid-Bindung).
        ziel_modus: ``"PHASE"`` (Provenienz-Ziel) oder ``"MAKRO"``
            (Engine-Gegenkante = GEGENKANTE_RELATIV).
    """

    def __init__(self, p10: P10Local, ziel_modus: str) -> None:
        self.start_scope_bar = 848
        self.segmente = (P9, p10)
        self.p10 = p10
        self.ziel_modus = ziel_modus
        self.log: List[Tuple[int, str, str]] = []
        self._opening_kid: Dict[str, int] = {}

    # ------------------------------------------------------------- Segmente
    def _seg_bei(self, k: int) -> Optional[object]:
        if k < self.start_scope_bar:
            return None
        if self.p10.start_bar <= k <= self.p10.end_bar:
            return self.p10
        if P9.start_bar <= k <= P9.end_bar:
            return P9
        return None

    def aktive_phase_bei(self, k: int) -> Optional[object]:
        return self._seg_bei(k)

    # -------------------------------------------------------------- Basis
    def niveau_override_bei(self, k: int, kid: int) -> Optional[float]:
        if self._seg_bei(k) is P9:
            return AD_P9.niveau_override_bei(k, kid)
        return None

    def angewandte_basis(self, k: int, kid: int, basis_engine: float) -> float:
        ov = self.niveau_override_bei(k, kid)
        return float(ov) if ov is not None else float(basis_engine)

    # ------------------------------------------------------------ Hook 1
    def _seite_kid(self, k: int, richtung: str,
                   kanten) -> Optional[int]:
        seg = self._seg_bei(k)
        if seg is None:
            return None
        ref = seg.decke if richtung == "SHORT" else seg.boden
        if getattr(ref, "ist_rolle", None) and ref.ist_rolle():
            rolle = ref.rolle
            if rolle is None:
                return None
            if not rolle.ist_rang:
                # Ereignisfamilie: braucht den Oeffnungs-Bar (hook_4).
                kid = self._opening_kid.get(richtung)
                if kid is None:
                    self.log.append((k, richtung, "EVENT_ROLE_UNRESOLVED"))
                return kid
            seite = rolle.seite
            rang = rolle.rang
            assert rang is not None
            sortiert = sorted(kanten, key=lambda t: t[1],
                              reverse=(seite == "OBEN"))
            if len(sortiert) <= rang:
                return None
            return sortiert[rang][0]
        return getattr(ref, "kid", None)

    def hook_1_freigabe_kid(self, k: int, sweep_px: float, richtung: str,
                            kanten) -> Optional[int]:
        seg = self._seg_bei(k)
        if seg is None:
            return None
        seite_kid = self._seite_kid(k, richtung, kanten)
        if seite_kid is None:
            return None
        band = getattr(seg, "touch_band_pct", 0.12)
        gueltige: List[Tuple[float, int]] = []
        for kid, basis_k in kanten:
            if kid != seite_kid or basis_k <= 0.0:
                continue
            if richtung == "SHORT" and sweep_px >= basis_k:
                continue
            if richtung == "LONG" and sweep_px <= basis_k:
                continue
            tol = basis_k * (band / 100.0)
            if abs(sweep_px - basis_k) <= tol:
                gueltige.append((abs(sweep_px - basis_k), kid))
        if not gueltige:
            return None
        gueltige.sort(key=lambda t: t[0])
        return gueltige[0][1]

    # ------------------------------------------------------------ Hook 2
    def hook_2_ziel(self, k: int, richtung: str) -> Hook2Ergebnis:
        if k < self.start_scope_bar:
            return Hook2Ergebnis(Hook2ZielModus.MAKRO, None)
        seg = self._seg_bei(k)
        if seg is None:
            return Hook2Ergebnis(Hook2ZielModus.BLOCKIERT, None)
        if seg is not self.p10 or self.ziel_modus == "MAKRO":
            if seg is P9 and self.ziel_modus != "MAKRO":
                ziel = (P9.ziel_preis_short if richtung == "SHORT"
                        else P9.ziel_preis_long)
                return Hook2Ergebnis(Hook2ZielModus.PHASE, ziel)
            return Hook2Ergebnis(Hook2ZielModus.MAKRO, None)
        ziel = (self.p10.ziel_short if richtung == "SHORT"
                else self.p10.ziel_long)
        return Hook2Ergebnis(Hook2ZielModus.PHASE, ziel)

    # ------------------------------------------------------------ Hook 3
    def hook_3_boden_reclaim(self, k: int) -> Optional[BodenReclaimSpec]:
        if self._seg_bei(k) is P9:
            return AD_P9.hook_3_boden_reclaim(k)
        return None


# ----------------------------------------------------- Renderer-Patch-Slice
_lines = (ROOT / "test" / "tmp_png_aug_sichttest.py").read_text(
    encoding="utf-8").splitlines()
_base_ns: Dict = {
    "P": ENGINE_P, "ast": __import__("ast"), "copy": copy,
    "Hook2ZielModus": Hook2ZielModus, "_Hook2ZielModus": Hook2ZielModus,
    "PhasenRegimeAdapter": PhasenRegimeAdapter,
    "engine": eng, "cfg": cfg, "scan": scan,
    "DEFAULT_ADAPTER": ADAPTER_V015, "ADAPTER_V015": ADAPTER_V015,
    "adapter": ADAPTER_V015,
}
exec(compile("\n".join(_lines[540:660]), "<patch_slice>", "exec"), _base_ns)
PATCHED: str = _base_ns["patched_src"]

_ANCHORS = [
    ('            if kd is None:\n                continue',
     '            if kd is None:\n'
     '                _DIAG.append((k, richtung, "KANDIDAT_NONE"))\n'
     '                continue'),
    ('            if blk is not None:\n                stats["blocker"] += 1',
     '            if blk is not None:\n'
     '                _DIAG.append((k, richtung, f"M6(K{blk.kid})"))\n'
     '                stats["blocker"] += 1'),
    ('            if not _im_aussenquartil(richtung, k, sweep_px):',
     '            if not _im_aussenquartil(richtung, k, sweep_px):\n'
     '                _DIAG.append((k, richtung, "Q29"))\n'),
    ('            if stufe_n == 0:\n                continue',
     '            if stufe_n == 0:\n'
     '                _DIAG.append((k, richtung, "STUFE0"))\n'
     '                continue'),
]


def build_src() -> str:
    o = PATCHED
    for old, new in _ANCHORS:
        assert o.count(old) == 1, (old[:40], o.count(old))
        o = o.replace(old, new)
    o = o.replace('stats["kein_raum"] += 1',
                  '_DIAG.append((k, richtung, "RAUM")); '
                  'stats["kein_raum"] += 1')
    return o


SRC = build_src()


def lauf(name: str, adapter: L2Adapter):
    ns = dict(eng.__dict__)
    ns["_Hook2ZielModus"] = Hook2ZielModus
    ns["_hook"] = adapter
    ns["_DIAG"] = []
    exec(compile(SRC, f"<{name}>", "exec"), ns)
    setups, stats = ns["_se_trades"](copy.deepcopy(scan), cfg)
    return setups, stats


def summ(name: str, setups):
    h1 = [t for t in setups if t.entry_bar < BOX]
    h2 = [t for t in setups if t.entry_bar >= BOX]
    return {
        "name": name, "n": len(setups), "r": sum(t.r for t in setups),
        "h1n": len(h1), "h1r": round(sum(t.r for t in h1), 6),
        "h2n": len(h2), "h2r": round(sum(t.r for t in h2), 6),
        "keys": sorted((t.bar, t.kid) for t in setups),
        "obj": setups,
    }


# ------------------------------------------------------------------ Laeufe
LAEUFE = []
for nm, rollen, zmod in (
        ("R0  kid  + PROVENIENZ (PHASE)", False, "PHASE"),
        ("R1  ROLLE+ PROVENIENZ (PHASE)", True, "PHASE"),
        ("R2  kid  + GEGENKANTE (MAKRO)", False, "MAKRO"),
        ("R3  ROLLE+ GEGENKANTE (MAKRO)", True, "MAKRO")):
    ad = L2Adapter(baue_p10(rollen), zmod)
    ad._opening_kid = {"LONG": 82}
    s, _st = lauf(nm, ad)
    res = summ(nm, s)
    res["log"] = ad.log
    LAEUFE.append(res)

R = {x["name"].split()[0]: x for x in LAEUFE}

# ================================================================== Report
out("=" * 108)
out("AUGUST-REPLIKATIONSBEWEIS EBENE 2 -- read-only, Generation V018 (BKZ)")
out("=" * 108)
out(f"Engine  : {ENGINE_P.name}  SHA256 {ENGINE_SHA}")
out(f"Loader  : sys.modules['{ENGINE_MODNAME}']  (fixiert, Pickle-tauglich)")
out(f"Adapter : backtest_lab/phasen_regime_adapter.py UNVERAENDERT")
out(f"Entwurf : test/_tmp_vd_vertrag_entwurf.py (Ebene-2-Vertrag)")
out(f"n={n} | box_end(H1/H2-Split)={BOX} | H2 ab Bar {BOX}")
out(f"SOLL Ebene 1: {SOLL[0]} Trades / {SOLL[1]:+.6f} R "
    f"(H1 {SOLL[2]}/{SOLL[3]:+.6f} | H2 {SOLL[4]}/{SOLL[5]:+.6f})")
out("")
out(f"{'Lauf':<34} {'Trd':>3} {'R gesamt':>12} | {'H1':>19} | {'H2':>19} | Bewertung")
for x in LAEUFE:
    ok = (x["n"], round(x["r"], 6), x["h1n"], x["h1r"]) == \
        (SOLL[0], round(SOLL[1], 6), SOLL[2], SOLL[3])
    out(f"{x['name']:<34} {x['n']:>3} {x['r']:>+12.6f} | "
        f"H1 {x['h1n']:>2}/{x['h1r']:>+10.6f} | "
        f"H2 {x['h2n']:>2}/{x['h2r']:>+10.6f} | "
        f"{'BIT-IDENTISCH' if ok else 'ABWEICHUNG'}")
out("")

out("-" * 108)
out("BEWEIS 1 -- RESOLVER (R0 vs R1, Zielmechanisma KONSTANT = PHASE)")
out("-" * 108)
out(f"   R0 kid   : {R['R0']['n']:>3} / {R['R0']['r']:>+12.6f} R")
out(f"   R1 Rolle : {R['R1']['n']:>3} / {R['R1']['r']:>+12.6f} R")
ident = R["R0"]["keys"] == R["R1"]["keys"] and \
    abs(R["R0"]["r"] - R["R1"]["r"]) < 1e-9
out(f"   Delta    : {R['R1']['n'] - R['R0']['n']:+d} Trades / "
    f"{R['R1']['r'] - R['R0']['r']:+.9f} R")
out(f"   Keys identisch: {R['R0']['keys'] == R['R1']['keys']}")
out(f"   >> RESOLVER-BEWEIS: {'BESTANDEN' if ident else '*** GESCHEITERT ***'}")
out(f"   (AUSSEN_OBEN loest exakt wie kid=67 auf; Sollwert "
    f"{SOLL[0]}/{SOLL[1]:+.6f} getroffen: "
    f"{(R['R1']['n'], round(R['R1']['r'], 6)) == (SOLL[0], round(SOLL[1], 6))})")
out("")

out("-" * 108)
out("BEWEIS 2 -- NIVEAU (R0 vs R2, kid-Bindung KONSTANT)")
out("-" * 108)
out(f"   R0 kid + PROVENIENZ (PHASE)  : {R['R0']['n']:>3} Trades / "
    f"{R['R0']['r']:>+12.6f} R | H2 {R['R0']['h2n']}/{R['R0']['h2r']:+.6f}")
out(f"   R2 kid + GEGENKANTE (MAKRO)  : {R['R2']['n']:>3} Trades / "
    f"{R['R2']['r']:>+12.6f} R | H2 {R['R2']['h2n']}/{R['R2']['h2r']:+.6f}")
out(f"   Delta R gesamt : {R['R2']['r'] - R['R0']['r']:+.6f}")
out(f"   Delta H2       : {R['R2']['h2r'] - R['R0']['h2r']:+.6f}")
out(f"   Keys verloren  : {[k for k in R['R0']['keys'] if k not in R['R2']['keys']]}")
out(f"   Keys gewonnen  : {[k for k in R['R2']['keys'] if k not in R['R0']['keys']]}")
out("")
out("   Trades R0 mit bar/Kid/R  (H2-Bereich):")
for t in sorted([t for t in R["R0"]["obj"] if t.bar >= 848], key=lambda t: t.bar):
    out(f"      bar {t.bar:>4} entry {t.entry_bar:>4} {t.richtung:<5} "
        f"K{t.kid:<3} R {t.r:>+10.6f} tp2 {t.tp2:.4f}")
out("   Trades R2 mit bar/Kid/R  (H2-Bereich):")
for t in sorted([t for t in R["R2"]["obj"] if t.bar >= 848], key=lambda t: t.bar):
    out(f"      bar {t.bar:>4} entry {t.entry_bar:>4} {t.richtung:<5} "
        f"K{t.kid:<3} R {t.r:>+10.6f} tp2 {t.tp2:.4f}")
out("")

out("-" * 108)
out("BEWEIS 3 -- KOMBINATION (R3)")
out("-" * 108)
out(f"   R3 ROLLE+ GEGENKANTE : {R['R3']['n']:>3} / {R['R3']['r']:>+12.6f} R | "
    f"H1 {R['R3']['h1n']}/{R['R3']['h1r']:+.6f} | H2 {R['R3']['h2n']}/{R['R3']['h2r']:+.6f}")
out(f"   == R2? {R['R3']['keys'] == R['R2']['keys']}  "
    f"(Rolle und kid liefern bei MAKRO dasselbe)")
out("")

out("-" * 108)
out("RESOLVER-LOG (EVENT_ROLE_UNRESOLVED = hook_4 fehlt)")
out("-" * 108)
for x in LAEUFE:
    lg = x.get("log", [])
    if not lg:
        continue
    from collections import Counter
    c = Counter(t for (_k, _r, t) in lg)
    out(f"   {x['name']:<34} {dict(c)}  erste Bars: "
        f"{[k for (k, _r, _t) in lg[:5]]}")
out("")
sha = hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
out(f"Engine-SHA Kontrolle: {sha}  "
    f"{'UNVERAENDERT' if sha == ENGINE_SHA else 'DRIFT'}")
out("")
out("ENDE AUGUST-REPLIKATIONSBEWEIS")

rep = "\n".join(BUF)
(ROOT / "test" / "_tmp_aug_replikation_out.txt").write_text(rep, encoding="utf-8")
print(rep)
