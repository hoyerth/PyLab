# -*- coding: utf-8 -*-
"""BLOCK E-20 (additiv, read-only) -- POC-Entkopplung vom Exit-Target.

Befund E-20: In ``_se_trades`` speist ``gegen_basis`` (das TP2-Ziel) ZUGLEICH
das POC-Fenster ``unter, ober = gegen_basis, basis``. Wird das Ziel verschoben,
wandert der POC an die Bandkante und ``tp1 = poc`` triggert nicht mehr vor dem
Stop. Das POC ist aber eine ZUSTANDSBESCHREIBUNG der Balance, das Ziel eine
HANDELSENTSCHEIDUNG -- beides darf nicht am selben Wert haengen.

Dieser Prototyp fuegt einen **additiven** Schalter hinzu (kein Kern-Eingriff):

    poc_quelle = GEGENKANTE_LEGACY   (Default -> byte-identisch zum Bestand)
               | PHASE_RANGE         (unter, ober = min/max(boden, decke) kausal)

Ratifiziert (2026-09-11): ``PHASE_RANGE`` ist der neue Standard; die harte
Zulaessigkeitsordnung ``sl > entry > poc > tp2`` (SHORT) bleibt UNVERAENDERT.

Laeufe (S2-Cache, Split-Partition bei entry_bar = 17.692):

  BASE            ungepatchte Engine (Referenz)
  LEGACY_CTRL     gepatcht, Segment K408/K409, poc_quelle = LEGACY
                  -> muss ``-19.065650 R`` (H2) reproduzieren (Harness-Kontrolle)
  PHASE_RANGE     gepatcht, Segment K408/K409, poc_quelle = PHASE_RANGE
  PR_AUSSEN_NAEHE gepatcht, Rollensegment AUSSEN_*/NAEHE, poc_quelle = PHASE_RANGE

Ausweis je Lauf und Partition: N, R, R_max, R_adj = R - R_max, Q_stop,
EV/Trade, EV_adj/Trade.

Ausfuehren:  .venv\\Scripts\\python.exe test/_tmp_s2_e20_poc.py
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
OUT = ROOT / "test" / "_tmp_s2_e20_poc_out.txt"
NAME = "tmp_kanten_engine_replay"
SPLIT = 17692
AUG_LITERALE = (67.6355, 68.3700, 69.8700, 69.9140)
STOP_EPS = 1e-9

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

# ------------------------------------------------- RAM-Patch (Renderer-Treue)
_lines = RENDERER_P.read_text(encoding="utf-8").splitlines()
_ns: Dict = {"P": ENGINE_P, "ast": __import__("ast"), "copy": copy,
             "Hook2ZielModus": Hook2ZielModus, "_Hook2ZielModus": Hook2ZielModus,
             "engine": eng}
exec(compile("\n".join(_lines[540:660]), "<patch_slice>", "exec"), _ns)
PATCHED_RENDERER: str = _ns["patched_src"]

# --- E-20-Aufsatz: POC-Fenster ueber den Hook ---------------------------------
A_POC_SHORT = "                unter, ober = gegen_basis, basis\n"
A_POC_LONG = "                unter, ober = basis, gegen_basis\n"
assert PATCHED_RENDERER.count(A_POC_SHORT) == 1, PATCHED_RENDERER.count(A_POC_SHORT)
assert PATCHED_RENDERER.count(A_POC_LONG) == 1, PATCHED_RENDERER.count(A_POC_LONG)
_POC_CALL = ("                unter, ober = _hook.poc_fenster("
             "k, richtung, gegen_basis, basis)\n")
PATCHED: str = (PATCHED_RENDERER
                .replace(A_POC_SHORT, _POC_CALL)
                .replace(A_POC_LONG, _POC_CALL))
assert PATCHED.count("_hook.poc_fenster(") == 2

cfg = eng.StraightEdgeHarnessKonfiguration()

out("=" * 108)
out("BLOCK E-20 -- POC-ENTKOPPLUNG (poc_quelle: GEGENKANTE_LEGACY vs PHASE_RANGE)")
out("=" * 108)
out(f"Engine-SHA : {ENGINE_SHA}  (arretiert)")
out(f"VD-Entwurf : {hashlib.sha256(VD_P.read_bytes()).hexdigest()}")
out(f"Renderer   : {hashlib.sha256(RENDERER_P.read_bytes()).hexdigest()}")
out(f"Patch      : Renderer-Slice ({len(PATCHED_RENDERER)} Z.) + "
    f"2 x poc_fenster-Hook ({len(PATCHED)} Z.)")
out(f"Zulaessigkeit: sl > entry > poc > tp2 (SHORT) -- UNVERAENDERT")
out("")


class BasisAdapter:
    """Traegt Rueckgrat + E-20-POC-Schalter."""

    def __init__(self, name: str, seg: Optional[SEG], poc_quelle: str,
                 start: int) -> None:
        self.name = name
        self.seg = seg
        self.poc_quelle = poc_quelle
        self.start_scope_bar = start
        self.segmente = (seg,) if seg is not None else ()
        self.ad = AD(start_scope_bar=start, segmente=(seg,)) if seg else None
        self._cache: Dict[int, list] = {}
        self._hi = np.zeros(0)
        self._lo = np.zeros(0)
        self.log: List[str] = []

    def binde_markt(self, scan) -> None:
        d = scan["d"]
        self._hi = d["high"].to_numpy(dtype=float)
        self._lo = d["low"].to_numpy(dtype=float)

    def setze_sichter(self, fn) -> None:
        self._sichter = fn

    def _sichten(self, k: int):
        c = self._cache.get(k)
        if c is None:
            c = self._sichter(k)
            self._cache[k] = c
        return c

    # ---------------------------------------------------------- Rueckgrat
    def aktive_phase_bei(self, k: int):
        return (self.seg if (self.seg is not None
                             and k >= self.start_scope_bar) else None)

    def niveau_override_bei(self, k: int, kid: int):
        return None

    def angewandte_basis(self, k: int, kid: int, basis_engine: float) -> float:
        return float(basis_engine)

    def hook_1_freigabe_kid(self, k, sweep_px, richtung, kanten):
        return None

    def hook_2_ziel(self, k: int, richtung: str) -> Hook2Ergebnis:
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

    # -------------------------------------------------------- E-20-Schalter
    def poc_fenster(self, k: int, richtung: str, gegen_basis: float,
                    basis: float) -> Tuple[float, float]:
        """Bin-Grenzen des POC-Histogramms.

        LEGACY       = ``(gegen_basis, basis)`` (Bestand, Ziel-koppelt).
        PHASE_RANGE  = ``(min(boden, decke), max(boden, decke))`` kausal.

        Ohne aktive Phase / ohne aufloesbare Grenzen: Fallback LEGACY.
        """
        if richtung == "SHORT":
            legacy = (float(gegen_basis), float(basis))
        else:
            legacy = (float(basis), float(gegen_basis))
        if self.poc_quelle != "PHASE_RANGE":
            return legacy
        akt = self.aktive_phase_bei(k)
        if akt is None:
            return legacy
        sw = float(self._hi[k]) if richtung == "SHORT" else float(self._lo[k])
        sich = self._sichten(k)
        decke = self.ad.aufloese_referenz_kausal(akt.decke, sich, k, sw,
                                                akt.rang_modus)
        boden = self.ad.aufloese_referenz_kausal(akt.boden, sich, k, sw,
                                                 akt.rang_modus)
        if decke is None or boden is None:
            return legacy
        u, o = sorted((float(boden[1]), float(decke[1])))
        if not (u < o):
            return legacy
        return (u, o)


def lauf(ad: BasisAdapter, scan) -> Tuple[list, Dict, float]:
    ns = dict(eng.__dict__)
    ns["_Hook2ZielModus"] = Hook2ZielModus
    ns["_hook"] = ad
    exec(compile(PATCHED, f"<{ad.name}>", "exec"), ns)
    t0 = time.time()
    s, st = ns["_se_trades"](copy.deepcopy(scan), cfg)
    return s, st, time.time() - t0


def metrik(s: list) -> Dict[str, float]:
    """R, R_max (nur Gewinn), R_adj, Q_stop, EV, EV_adj."""
    n = len(s)
    r = [float(t.r) for t in s]
    ges = float(sum(r))
    rmax = max([0.0] + [x for x in r if x > 0.0])
    adj = ges - rmax
    nstop = sum(1 for x in r if x <= -1.0 + STOP_EPS)
    return {"N": n, "R": ges, "R_max": rmax, "R_adj": adj,
            "N_stop": nstop, "Q_stop": (nstop / n if n else float("nan")),
            "EV": (ges / n if n else float("nan")),
            "EV_adj": (adj / n if n else float("nan"))}


def zeile(tag: str, m: Dict[str, float]) -> str:
    return (f"{tag:<16}{m['N']:>5}{m['R']:>+14.6f}{m['R_max']:>13.6f}"
            f"{m['R_adj']:>+14.6f}{m['N_stop']:>7}"
            f"{m['Q_stop']:>9.3f}{m['EV']:>+11.6f}{m['EV_adj']:>+11.6f}")


KOPF = (f"{'Lauf':<16}{'N':>5}{'R':>14}{'R_max':>13}{'R_adj':>14}"
        f"{'N_stop':>7}{'Q_stop':>9}{'EV':>11}{'EV_adj':>11}")


def block(tag: str, s: list, scan, split: int) -> None:
    h1 = [t for t in s if t.entry_bar < split]
    h2 = [t for t in s if t.entry_bar >= split]
    out(KOPF)
    out("-" * len(KOPF))
    for nm, grp in (("gesamt", s), ("H1", h1), ("H2", h2)):
        out(zeile(f"{tag} {nm}", metrik(grp)))
    out("")


# ------------------------------------------------------------------ S2-Cache
scan = pickle.loads(PKL_S2.read_bytes())
n = scan["n"]
scan["box_end_bar"] = n
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
alle = list(scan["edges"]) + list(scan["seeds"])

out("S2-KONTEXT")
out("-" * 108)
out(f"n = {n}   Split (Partition) = {SPLIT}   box_end_bar (Laufgrenze) = {n}")
out(f"H1 {SPLIT} Bars / H2 {n - SPLIT} Bars   close[Split] = {cl[SPLIT]:.4f}")
out(f"August-Literale {AUG_LITERALE} alle oberhalb von {hi.max():.4f}? "
    f"{all(x > hi.max() for x in AUG_LITERALE)}  (Auflage 3: kein Literal)")
out("")


def sichter(k: int):
    return [KS(e.kid, e.seite, e.basis_bei(k), e.erster_pivot_bar,
               (e.wicks[0][0] if e.wicks else None),
               (e.wicks[0][1] if e.wicks else None)) for e in alle]


SEG_K408_409 = SEG("P_K408_409", KT(kind="kid", kid=408),
                   KT(kind="kid", kid=409), rang_modus=RM.NAEHE)
SEG_AUSSEN_NAEHE = SEG("P_AUSSEN_NAEHE",
                       KT(kind="rolle", rolle=KR.AUSSEN_OBEN),
                       KT(kind="rolle", rolle=KR.AUSSEN_UNTEN),
                       rang_modus=RM.NAEHE)

VERLAUF: Dict[str, Dict[str, Dict[str, float]]] = {}

# ------------------------------------------------------------------- BASE
t0 = time.time()
base, st_base = eng._se_trades(copy.deepcopy(scan), cfg)
dt = time.time() - t0
out("A  LAEUFE")
out("=" * 108)
out(f"--- BASE ungepatcht ({dt:.1f} s) ---")
block("BASE", base, scan, SPLIT)
VERLAUF["BASE"] = {"gesamt": metrik(base),
                   "H1": metrik([t for t in base if t.entry_bar < SPLIT]),
                   "H2": metrik([t for t in base if t.entry_bar >= SPLIT])}

VARIANTEN = [
    ("LEGACY_CTRL", SEG_K408_409, "GEGENKANTE_LEGACY"),
    ("PHASE_RANGE", SEG_K408_409, "PHASE_RANGE"),
    ("PR_AUSSEN_NAEHE", SEG_AUSSEN_NAEHE, "PHASE_RANGE"),
]
SETUPS: Dict[str, list] = {"BASE": base}
for tag, seg, pq in VARIANTEN:
    ad = BasisAdapter(tag, seg, pq, SPLIT)
    ad.binde_markt(scan)
    ad.setze_sichter(sichter)
    ad.ad.verifiziere([(e.kid, e.seite, e.basis_bei(SPLIT)) for e in alle])
    s, st, dt = lauf(ad, scan)
    SETUPS[tag] = s
    out(f"--- {tag}  (poc_quelle={pq}, Segment {seg.phasen_id}, {dt:.1f} s) ---")
    block(tag, s, scan, SPLIT)
    VERLAUF[tag] = {"gesamt": metrik(s),
                    "H1": metrik([t for t in s if t.entry_bar < SPLIT]),
                    "H2": metrik([t for t in s if t.entry_bar >= SPLIT])}
    out("   stats: " + str({k: v for k, v in st.items()
                            if isinstance(v, int)}))
    out("")

# ------------------------------------------------------- Kontrolle LEGACY
out("B  HARNESS-KONTROLLE")
out("=" * 108)
leg = VERLAUF["LEGACY_CTRL"]["H2"]
out(f"LEGACY_CTRL H2 R = {leg['R']:+.6f}   (Soll aus _tmp_s2_vd_stresstest: "
    f"-19.065650)")
out(f"   Kontrolle: "
    f"{'OK' if abs(leg['R'] + 19.065650) < 1e-6 else 'ABWEICHUNG'}")
out(f"MAKRO-Kontrolle entfaellt hier -- BASE ist separat gemessen.")
out("")

# ------------------------------------------------------------- Vergleich
out("C  GEGENUEBERSTELLUNG (Partition H2 = Messung; H1 = Kontrolle)")
out("=" * 108)
out(KOPF)
out("-" * len(KOPF))
for tag in ("BASE", "LEGACY_CTRL", "PHASE_RANGE", "PR_AUSSEN_NAEHE"):
    out(zeile(f"{tag} H2", VERLAUF[tag]["H2"]))
out("")
out("Deltas gegen LEGACY_CTRL (H2):")
for tag in ("PHASE_RANGE", "PR_AUSSEN_NAEHE"):
    a = VERLAUF["LEGACY_CTRL"]["H2"]
    b = VERLAUF[tag]["H2"]
    out(f"   {tag:<18} dR {b['R'] - a['R']:>+12.6f}   "
        f"dR_adj {b['R_adj'] - a['R_adj']:>+12.6f}   "
        f"dQ_stop {b['Q_stop'] - a['Q_stop']:>+7.3f}   "
        f"dEV_adj {b['EV_adj'] - a['EV_adj']:>+9.6f}")
out("")

# ------------------------------------------- H2-Einzeltrades PHASE_RANGE
out("D  H2-EINZELTRADES PHASE_RANGE (Diagnose)")
out("=" * 108)
for tag in ("LEGACY_CTRL", "PHASE_RANGE"):
    h2 = sorted([t for t in SETUPS[tag] if t.entry_bar >= SPLIT],
                key=lambda x: x.entry_bar)
    out(f"{tag}: H2 {len(h2)} Trades / {sum(t.r for t in h2):+.6f} R")
    for t in h2:
        out(f"      entry {t.entry_bar:>6} bar {t.bar:>6} {t.richtung:<5} "
            f"K{t.kid:<4} R {t.r:>+10.6f}  tp2 {t.tp2:>9.4f}  poc {t.poc:>9.4f}  "
            f"sl {t.sl:>9.4f}")
    out("")

out("=" * 108)
out("Engine-SHA nach Lauf: " + hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
    + ("  UNVERAENDERT" if hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
       == ENGINE_SHA else "  DRIFT"))
out("=" * 108)

rep = "\n".join(BUF)
OUT.write_text(rep, encoding="utf-8")
print("geschrieben: " + str(OUT))
