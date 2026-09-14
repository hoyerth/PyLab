# -*- coding: utf-8 -*-
"""PHASE 1/3 (read-only) -- GEGENKANTEN-WAHL + RECLAIM_AT_OPENING-Verifikation.

Zentrale These der Mentor-Kritik: ``GEGENKANTE_RELATIV`` scheiterte nicht am
Prinzip, sondern an der WAHL der Gegenkante. Die Engine waehlt die AEUSSERSTE
Makrowand (``_gegenkante``, Q5/Q14) -> K48 (62.5770). Die PHASE meint aber ihre
EIGENE Gegenkante -- und genau das tut P9 bereits: ``ziel_preis_short`` (68.3700)
== ``boden.provenienz_basis`` == K77!

Gemessen werden daher vier Zielmechanismen bei konstanter kid-Bindung:
  Z0  PHASE fix            (Bestand: 68.3700 / 69.9140 [Override 69.87])
  Z1  MAKRO (Engine)       (_gegenkante = aeusserste Makrowand, K48)
  Z2  SEG-BODEN dynamisch  (``basis_bei(k)`` der phasen-eigenen Gegenkante)
  Z3  INNEN_UNTEN_1        (zweit-tiefste existierende UNTEN-Kante)

Zusaetzlich: Verifikation von ``RECLAIM_AT_OPENING`` an Bar 1002 (G4-Reclaim)
und an Bar 1075 (P10-Oeffnung).

Ausfuehren:  .venv\\Scripts\\python.exe test/_tmp_gegenkante_probe.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from collections import Counter
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


spec = importlib.util.spec_from_file_location(
    "tmp_kanten_engine_replay", ENGINE_P)
eng = importlib.util.module_from_spec(spec)
sys.modules["tmp_kanten_engine_replay"] = eng
spec.loader.exec_module(eng)

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V015, BodenReclaimSpec, Hook2Ergebnis, Hook2ZielModus,
    PhasenRegimeAdapter,
)

ENGINE_SHA = hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
n = scan["n"]
BOX = scan["box_end_bar"]
scan["box_end_bar"] = n
d = scan["d"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
cl = d["close"].to_numpy(float)
op = d["open"].to_numpy(float)
ts = d["ts"].to_numpy()
alle = list(scan["edges"]) + list(scan["seeds"])
by_kid = {e.kid: e for e in alle}
seite_edges = {"OBEN": [e for e in alle if e.seite == "OBEN"],
               "UNTEN": [e for e in alle if e.seite == "UNTEN"]}


def exists(e, k):
    return e.ist_aktiv_bei(k) and e.erster_pivot_bar + 2 <= k + 1


P9 = ADAPTER_V015.segmente[0]
AD_P9 = PhasenRegimeAdapter(start_scope_bar=848, segmente=(P9,))
P10_START, P10_END = 1021, n - 1

# =========================================================== A  Verifikation
out("=" * 104)
out("A  RECLAIM_AT_OPENING -- VERIFIKATION (Ereignisfamilie)")
out("=" * 104)
out("")
out("A.1  Bar 1002 (P9-Suedschenkel / G4-Reclaim) -- Marktdaten")
for k in (1002, 1075):
    out(f"   bar {k}  ts={np.datetime64(ts[k], 'm')}  "
        f"O={op[k]:.4f} H={hi[k]:.4f} L={lo[k]:.4f} C={cl[k]:.4f}")
out("")
out("   G4-Bedingung (Adapter-Literal 68.4000): lo[k] < 68.4000 < cl[k]")
for k in range(848, n):
    if lo[k] < 68.40 < cl[k]:
        e77 = by_kid[77]
        out(f"      bar {k}: lo={lo[k]:.4f} < 68.4000 < cl={cl[k]:.4f}  "
            f"| K77.touch_conf={e77.touch_conf(k)} "
            f"(>= {cfg.min_touches_handelbar}? "
            f"{e77.touch_conf(k) >= cfg.min_touches_handelbar})")
out("")
out("A.2  Ereignis-Aufloesung: welche UNTEN-Kante reclaimt an welchem Bar?")
out("     (je Kante ihre EIGENE kausale Basis, >= Stufe 1)")
for k in (1002, 1075):
    treffer = []
    for e in seite_edges["UNTEN"]:
        if not exists(e, k):
            continue
        st, nm = eng._reclaim_stufe("UNTEN", k, e.basis_bei(k), hi, lo, cl, cfg)
        if st >= 1:
            treffer.append((e.kid, e.basis_bei(k), st, str(nm)))
    treffer.sort(key=lambda t: t[1], reverse=True)
    out(f"   bar {k}: {len(treffer)} Kante(n) mit Reclaim >= 1")
    for (kid, b, st, nm) in treffer:
        out(f"      K{kid:<4} basis={b:>8.4f} stufe={st} ({nm})")
out("")
out("A.3  Oeffnungs-Trigger (P10): erster Bar >= 1021 mit Reclaim >= 1")
out("     gegen die DEKLARIERTE Grenzkante")
for kid, seite in ((82, "UNTEN"), (67, "OBEN")):
    e = by_kid[kid]
    for k in range(1021, n):
        st, nm = eng._reclaim_stufe(seite, k, e.basis_bei(k), hi, lo, cl, cfg)
        if st >= 1:
            out(f"      K{kid} ({seite}): erster Reclaim >= 1 bei bar {k} "
                f"stufe={st} ({nm})")
            break
    else:
        out(f"      K{kid} ({seite}): kein Reclaim >= 1 in [1021, {n})")
out("")

# =================================================== B  Gegenkanten-Analyse
out("=" * 104)
out("B  GEGENKANTEN-WAHL -- welche Kante ist TP2-Anker?")
out("=" * 104)
out("")
out("B.1  P9-Arretierung: wohin zeigt 'ziel_preis_short'?")
out(f"   P9.boden.kid            = K{P9.boden.kid}")
out(f"   P9.boden.provenienz     = {P9.boden.provenienz_basis:.4f}")
out(f"   P9.ziel_preis_short     = {P9.ziel_preis_short:.4f}")
out(f"   >> IDENTISCH: {abs(P9.boden.provenienz_basis - P9.ziel_preis_short) < 1e-12}")
out(f"   P9.decke.kid            = K{P9.decke.kid}  "
    f"(Override {P9.decke.niveau_override})  "
    f"ziel_preis_long={P9.ziel_preis_long:.4f}")
out("")
out("   >> Der PHASE-Zielpreis ist bereits die phaseneigene Gegenkante!")
out("")

ZEILEN = [(903, 905, "SHORT", 67), (980, 981, "SHORT", 67),
          (981, 982, "SHORT", 73), (1002, 1003, "LONG", 77),
          (1020, 1021, "SHORT", 67)]
out("B.2  Kausale Basen der Kandidaten-Gegenkanten an den Signal-Bars")
out(f"{'bar':>5} {'ri':>5} {'kid':>4} {'seg.boden basis':>16} "
    f"{'K77.basis':>10} {'K48.basis':>10} {'INNEN_U1':>9} {'sweep/H/L':>10}")
for (k, eb, ri, kid) in ZEILEN:
    seg = P9 if k <= 1020 else None
    b_seg = (by_kid[P9.boden.kid].basis_bei(k) if seg else float('nan'))
    b77 = by_kid[77].basis_bei(k)
    b48 = by_kid[48].basis_bei(k) if 48 in by_kid else float('nan')
    un = sorted([e for e in seite_edges["UNTEN"] if exists(e, k)],
                key=lambda e: e.basis_bei(k))
    b_in1 = un[1].basis_bei(k) if len(un) > 1 else float('nan')
    px = hi[k] if ri == "SHORT" else lo[k]
    out(f"{k:>5} {ri:>5} K{kid:<3} {b_seg:>16.4f} {b77:>10.4f} "
        f"{b48:>10.4f} {b_in1:>9.4f} {px:>10.4f}")
out("")
out("B.3  Rang der Kandidaten im UNTEN-Pool (existierende Kanten)")
for k in (903, 980, 1002, 1020):
    un = sorted([e for e in seite_edges["UNTEN"] if exists(e, k)],
                key=lambda e: e.basis_bei(k))
    out(f"   bar {k}: Pool({len(un)}) = "
        f"{[(f'K{e.kid}', round(e.basis_bei(k), 3)) for e in un[:6]]}")
out("")

# ==================================================== C  Zielmechanismen
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
PATCHED = _base_ns["patched_src"]


class L2Adapter:
    """P9 arrestiert; P10 dynamisch; Zielmechanismus waehlbar."""

    def __init__(self, ziel: str) -> None:
        self.start_scope_bar = 848
        self.segmente = (P9,)
        self.ziel = ziel
        self.log: List = []

    def _seg_bei(self, k):
        if k < 848:
            return None
        if 848 <= k <= 1020:
            return P9
        return None

    def aktive_phase_bei(self, k):
        return self._seg_bei(k)

    def niveau_override_bei(self, k, kid):
        return AD_P9.niveau_override_bei(k, kid)

    def angewandte_basis(self, k, kid, basis_engine):
        ov = self.niveau_override_bei(k, kid)
        return float(ov) if ov is not None else float(basis_engine)

    def hook_1_freigabe_kid(self, k, sweep_px, richtung, kanten):
        seg = self._seg_bei(k)
        if seg is None:
            return None
        seite_kid = seg.decke.kid if richtung == "SHORT" else seg.boden.kid
        g = []
        for kid, bk in kanten:
            if kid != seite_kid or bk <= 0.0:
                continue
            if richtung == "SHORT" and sweep_px >= bk:
                continue
            if richtung == "LONG" and sweep_px <= bk:
                continue
            if abs(sweep_px - bk) <= bk * 0.0012:
                g.append((abs(sweep_px - bk), kid))
        if not g:
            return None
        g.sort(key=lambda t: t[0])
        return g[0][1]

    def _in1_basis(self, k, richtung):
        seite = "UNTEN" if richtung == "SHORT" else "OBEN"
        pool = sorted([e for e in seite_edges[seite] if exists(e, k)],
                      key=lambda e: e.basis_bei(k),
                      reverse=(seite == "OBEN"))
        return pool[1].basis_bei(k) if len(pool) > 1 else None

    def hook_2_ziel(self, k, richtung):
        if k < 848:
            return Hook2Ergebnis(Hook2ZielModus.MAKRO, None)
        seg = self._seg_bei(k)
        if seg is None:
            return Hook2Ergebnis(Hook2ZielModus.BLOCKIERT, None)
        if self.ziel == "PHASE":
            z = (seg.ziel_preis_short if richtung == "SHORT"
                 else seg.ziel_preis_long)
            return Hook2Ergebnis(Hook2ZielModus.PHASE, z)
        if self.ziel == "MAKRO":
            return Hook2Ergebnis(Hook2ZielModus.MAKRO, None)
        if self.ziel == "SEG_BODEN":
            kid = seg.boden.kid if richtung == "SHORT" else seg.decke.kid
            if kid not in by_kid:
                return Hook2Ergebnis(Hook2ZielModus.PHASE, None)
            return Hook2Ergebnis(
                Hook2ZielModus.PHASE,
                self.angewandte_basis(k, kid, by_kid[kid].basis_bei(k)))
        if self.ziel == "INNEN1":
            b = self._in1_basis(k, richtung)
            return Hook2Ergebnis(Hook2ZielModus.PHASE, b)
        raise ValueError(self.ziel)

    def hook_3_boden_reclaim(self, k):
        seg = self._seg_bei(k)
        return AD_P9.hook_3_boden_reclaim(k) if seg is P9 else None


def lauf(name, ad):
    ns = dict(eng.__dict__)
    ns["_Hook2ZielModus"] = Hook2ZielModus
    ns["_hook"] = ad
    ns["_DIAG"] = []
    exec(compile(PATCHED, f"<{name}>", "exec"), ns)
    s, st = ns["_se_trades"](copy.deepcopy(scan), cfg)
    return s


out("=" * 104)
out("C  ZIELMECHANISMEN -- Wirkung auf die P9-H2-Trades (kid-Bindung konstant)")
out("=" * 104)
res = {}
for z in ("PHASE", "MAKRO", "SEG_BODEN", "INNEN1"):
    s = lauf(z, L2Adapter(z))
    h2 = [t for t in s if t.entry_bar >= BOX and t.bar >= 848]
    res[z] = s
    out(f"   {z:<10} gesamt {len(s):>2} Trades / "
        f"{sum(t.r for t in s):>+11.6f} R | P9-Segment-Trades:")
    for t in sorted([t for t in s if t.bar >= 848], key=lambda t: t.bar):
        out(f"        bar {t.bar:>4} {t.richtung:<5} K{t.kid:<3} "
            f"R {t.r:>+10.6f} tp2 {t.tp2:>8.4f}")
    out("")

out("Engine-SHA: " + hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
    + ("  UNVERAENDERT" if hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
       == ENGINE_SHA else "  DRIFT"))

rep = "\n".join(BUF)
(ROOT / "test" / "_tmp_gegenkante_probe_out.txt").write_text(rep,
                                                             encoding="utf-8")
print(rep)
