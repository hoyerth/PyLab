# -*- coding: utf-8 -*-
"""PHASE 2 (read-only / In-Memory) -- Isolierte Hebel-Analyse H2 ab Bar 1021.

Deckt:
  2.2.1 K67-M6-Freigabe an K73@1122/1123 isolieren (Hook-1-Scope)
  2.2.2 ``pos``-Sortierung auditieren (Zaehlung nur LEBENDER Kanten)
  2.2.3 Phasenlokales Q29 (848..1020 und 1021..1287, getrennt ausgewiesen)

Die Engine-Datei ``test/tmp_kanten_engine_replay.py`` wird NICHT veraendert
(SHA 4a576a76...  am Ende verifiziert). Alle Varianten laufen als RAM-Klon-
``exec`` mit zusaetzlichen, explizit benannten Quelltext-Transformationen
(Fail-Loud: jede Ersetzung muss GENAU EINMAL vorkommen).

H1-Invarianz-Gate: jede Variante muss H1 = 8 Trades / +38.919584 R halten
(entry_bar < 644); sonst wird sie als DISQUALIFIZIERT gemeldet.

Ausfuehren:  .venv\\Scripts\\python.exe test/_tmp_explo_v018_phase2.py
Ausgabe:     test/_tmp_explo_v018_phase2_out.txt
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
BUF: List[str] = []


def out(line: str = "") -> None:
    BUF.append(line)


def load_engine():
    spec = importlib.util.spec_from_file_location("_v018_eng2", ENGINE_P)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["_v018_eng2"] = mod
    spec.loader.exec_module(mod)               # type: ignore[union-attr]
    return mod


eng = load_engine()
from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V015, DEFAULT_ADAPTER, Hook2ZielModus, PhasenKanteInfo,
    PhasenRegimeAdapter, PhasenSegmentEintrag,
)

ENGINE_SHA = hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
n = scan["n"]
BOX = scan["box_end_bar"]                       # 644 (H1/H2-Split-Grenze)
scan["box_end_bar"] = n                         # Renderer-Voll-Lauf (Z. 507)
W0, W1 = 1021, n - 4                            # iterierte Bars (range(2, n-3))
RANGE_H1 = (8, 38.919584)

# ------------------------------------------------------------------ Adapter
P9_SEG = ADAPTER_V015.segmente[0]               # P9_BODEN_RECLAIM (G4)
P10_HYP = PhasenSegmentEintrag(
    phasen_id="P10_HYP",
    start_bar=1021,
    end_bar=n - 1,                              # 1287
    decke=PhasenKanteInfo(kid=67, provenienz_basis=69.9140),
    boden=PhasenKanteInfo(kid=82, provenienz_basis=67.6355),
    ziel_preis_short=67.6355,
    ziel_preis_long=69.9140,
)
AD_HYP = PhasenRegimeAdapter(start_scope_bar=848,
                             segmente=(P9_SEG, P10_HYP))
assert AD_HYP.aktive_phase_bei(1122) is P10_HYP
assert AD_HYP.aktive_phase_bei(1020) is P9_SEG

# ------------------------------------------- Renderer-Patch-Slice (Basis)
_lines = (ROOT / "test" / "tmp_png_aug_sichttest.py").read_text(
    encoding="utf-8").splitlines()
_base_ns: Dict = {
    "P": ENGINE_P, "ast": __import__("ast"), "copy": copy,
    "Hook2ZielModus": Hook2ZielModus, "_Hook2ZielModus": Hook2ZielModus,
    "PhasenRegimeAdapter": PhasenRegimeAdapter,
    "engine": eng, "cfg": cfg, "scan": scan,
    "DEFAULT_ADAPTER": DEFAULT_ADAPTER, "ADAPTER_V015": ADAPTER_V015,
    "adapter": ADAPTER_V015,
}
exec(compile("\n".join(_lines[540:660]), "<patch_slice>", "exec"), _base_ns)
PATCHED: str = _base_ns["patched_src"]


# ------------------------------------------- Basis-Injektion der _DIAG-Marker
# 1:1 aus Phase 1 (test/_tmp_explo_v018_phase1.py) uebernommen: die Gate-
# Barrieren werden im Quelltext-Klon um _DIAG-Eintraege erweitert (RAM).
_BASE_ANCHORS: List[Tuple[str, str]] = [
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


def inject_base(src: str) -> str:
    """Fuegt je Barriere einen _DIAG-Eintrag ein (RAM, fail-loud)."""
    out_src = src
    for old, new in _BASE_ANCHORS:
        assert out_src.count(old) == 1, (old[:50], out_src.count(old))
        out_src = out_src.replace(old, new)
    out_src = out_src.replace(
        'stats["kein_raum"] += 1',
        '_DIAG.append((k, richtung, "RAUM")); stats["kein_raum"] += 1')
    if "_Hook2ZielModus.BLOCKIERT" in out_src:
        old_h2 = ('            if _h2.modus is _Hook2ZielModus.BLOCKIERT:\n'
                  '                _DIAG.append((k, richtung, "RAUM")); '
                  'stats["kein_raum"] += 1')
        assert out_src.count(old_h2) == 1, out_src.count(old_h2)
        out_src = out_src.replace(
            old_h2,
            '            if _h2.modus is _Hook2ZielModus.BLOCKIERT:\n'
            '                _DIAG.append((k, richtung, "HOOK2_BLOCKIERT"))\n'
            '                _DIAG.append((k, richtung, "RAUM")); '
            'stats["kein_raum"] += 1')
    return out_src


# ------------------------------------------------------- Quelltext-Transforms
def tf_ident(src: str) -> str:
    return src


def tf_m6_live(src: str) -> str:
    """M6-Blocker muessen LEBEND sein (Konsistenz zu Q25 ``_lebt``)."""
    old = "            if e is kd or not _existiert(e, k):"
    new = ("            if (e is kd or not _existiert(e, k)\n"
           "                    or not _lebt(e, k)):")
    assert src.count(old) == 1, ("tf_m6_live", src.count(old))
    return src.replace(old, new)


def tf_force_freigabe(src: str) -> str:
    """Erzwingt Hook-1-Freigabe fuer ``k in _FORCE_FREI`` (kid=_FORCE_KID)."""
    old = ("            _freigabe_kid = _hook.hook_1_freigabe_kid(\n"
           "                k, sweep_px, richtung, _seite_kanten(k, _seite))")
    new = old + ("\n            if k in _FORCE_FREI:\n"
                 "                _freigabe_kid = _FORCE_KID")
    assert src.count(old) == 1, ("tf_force_freigabe", src.count(old))
    return src.replace(old, new)


def tf_pos_live(src: str) -> str:
    """``pos`` zaehlt nur noch LEBENDE Kanten (dormante verbrauchen kein pos)."""
    old_loop = "        for pos, e in enumerate(pool):"
    new_loop = ("        _outer_live = next((_e2 for _e2 in pool if _lebt(_e2, k)),\n"
                "                            None)\n"
                "        for pos, e in enumerate(pool):")
    old_pos0 = "            if pos == 0:"
    new_pos0 = "            if e is _outer_live:"
    assert src.count(old_loop) == 1, ("tf_pos_live.loop", src.count(old_loop))
    assert src.count(old_pos0) == 1, ("tf_pos_live.pos0", src.count(old_pos0))
    return src.replace(old_loop, new_loop).replace(old_pos0, new_pos0)


def tf_q29_local(src: str) -> str:
    """Phasenlokales Q29: Range-Extrema nur in [_Q29_LO, _Q29_HI]."""
    old = ("        ex_hi = float(np.max(hi[:k + 1]))\n"
           "        ex_lo = float(np.min(lo[:k + 1]))")
    new = ("        if _Q29_LO <= k <= _Q29_HI:\n"
           "            ex_hi = float(np.max(hi[_Q29_LO:k + 1]))\n"
           "            ex_lo = float(np.min(lo[_Q29_LO:k + 1]))\n"
           "        else:\n"
           "            ex_hi = float(np.max(hi[:k + 1]))\n"
           "            ex_lo = float(np.min(lo[:k + 1]))")
    assert src.count(old) == 1, ("tf_q29_local", src.count(old))
    return src.replace(old, new)


# Zusatzmarker: M6-Blocker mit Liveness + Kandidat-Kid protokollieren.
def tf_diag_m6(src: str) -> str:
    old = ('                _DIAG.append((k, richtung, f"M6(K{blk.kid})"))')
    new = ('                _DIAG.append((k, richtung,\n'
           '                             f"M6(K{blk.kid},'
           '{\'live\' if _lebt(blk, k) else \'dorm\'})"))')
    assert src.count(old) == 1, ("tf_diag_m6", src.count(old))
    return src.replace(old, new)


def tf_diag_kid(src: str) -> str:
    """Kandidat-Kid in die WAND-Marke aufnehmen."""
    old = ('            if pos == 0:\n                return e')
    new = ('            if pos == 0:\n'
           '                _DIAG.append((k, richtung, f"WAND(K{e.kid})"))\n'
           '                return e')
    if src.count(old) != 1:
        old = ('            if e is _outer_live:\n                return e')
        new = ('            if e is _outer_live:\n'
               '                _DIAG.append((k, richtung, f"WAND(K{e.kid})"))\n'
               '                return e')
    assert src.count(old) == 1, ("tf_diag_kid", src.count(old))
    return src.replace(old, new)


def tf_diag_innen(src: str) -> str:
    old = ("            if e.touch_conf(k) < cfg.min_touches_handelbar:\n"
           "                continue                        # innere Linie "
           "braucht V-S >= 3\n"
           "            return e")
    if src.count(old) == 1:
        return src.replace(
            old,
            "            if e.touch_conf(k) < cfg.min_touches_handelbar:\n"
            "                _DIAG.append((k, richtung,\n"
            "                             f\"V_S(K{e.kid},{e.touch_conf(k)})\"))\n"
            "                continue                        # innere Linie "
            "braucht V-S >= 3\n"
            "            _DIAG.append((k, richtung, f\"INNEN(K{e.kid})\"))\n"
            "            return e")
    return src


def build_src(transforms: List[Callable[[str], str]]) -> str:
    src = inject_base(PATCHED)
    src = tf_diag_m6(src)
    src = tf_diag_kid(src)
    src = tf_diag_innen(src)
    for tf in transforms:
        src = tf(src)
    return src


# ------------------------------------------------------------------ Runner
@dataclass
class Variante:
    name: str
    adapter: PhasenRegimeAdapter
    transforms: List[Callable[[str], str]]
    extra: Dict


def run(v: Variante):
    src = build_src(v.transforms)
    ns = dict(eng.__dict__)
    ns["_Hook2ZielModus"] = Hook2ZielModus
    ns["_hook"] = v.adapter
    ns["_DIAG"] = []
    ns["_FORCE_FREI"] = frozenset()
    ns["_FORCE_KID"] = -1
    ns["_Q29_LO"] = 1
    ns["_Q29_HI"] = 0
    ns.update(v.extra)
    exec(compile(src, f"<{v.name}>", "exec"), ns)
    setups, stats = ns["_se_trades"](copy.deepcopy(scan), cfg)
    return setups, stats, list(ns["_DIAG"])


def summ(name: str, setups, diag) -> Dict:
    r = sum(t.r for t in setups)
    h1 = [t for t in setups if t.entry_bar < BOX]
    h2 = [t for t in setups if t.entry_bar >= BOX]
    kn = sum(1 for (k, _ri, tag) in diag if tag == "KANDIDAT_NONE"
             and W0 <= k <= W1)
    m6 = [f"bar {k} {ri} {tag}" for (k, ri, tag) in diag
          if tag.startswith("M6(") and W0 <= k <= W1]
    return {
        "name": name, "trades": len(setups), "r": r,
        "h1n": len(h1), "h1r": round(sum(t.r for t in h1), 6),
        "h2n": len(h2), "h2r": round(sum(t.r for t in h2), 6),
        "kn": kn, "m6": m6,
        "keys": sorted((t.bar, t.kid) for t in setups),
        "h1keys": sorted((t.bar, t.kid) for t in h1),
        "setup_obj": setups,
        "diag": diag,
    }


def gate(res: Dict) -> str:
    ok = (res["h1n"], res["h1r"]) == RANGE_H1
    return "H1-HALTEN " if ok else "H1-VERLETZT"


def row(res: Dict, base: Dict) -> str:
    added = [k for k in res["keys"] if k not in base["keys"]]
    removed = [k for k in base["keys"] if k not in res["keys"]]
    return (f"{res['name']:<34} {res['trades']:>3} {res['r']:>+12.6f} | "
            f"H1 {res['h1n']:>2}/{res['h1r']:>+10.6f} [{gate(res)}] | "
            f"H2 {res['h2n']:>2}/{res['h2r']:>+10.6f} | "
            f"KN {res['kn']:>3} | +{added} -{removed}")


# ------------------------------------------------------------------ Laeufe
BASE = Variante("V015 (Baseline)", ADAPTER_V015, [tf_ident], {})
_bs, _bst, _bd = run(BASE)
b = summ("V015 (Baseline)", _bs, _bd)

VAR_M6_FORCE = Variante(
    "V015 + K67-Freigabe@1122/1123", ADAPTER_V015, [tf_force_freigabe],
    {"_FORCE_FREI": frozenset({1122, 1123}), "_FORCE_KID": 67})
VAR_M6_LIVE = Variante(
    "V015 + M6-nur-lebende", ADAPTER_V015, [tf_m6_live], {})
VAR_POS_LIVE = Variante(
    "V015 + pos-nur-lebende", ADAPTER_V015, [tf_pos_live], {})
VAR_Q29A = Variante(
    "V015 + Q29-lokal 848..1020", ADAPTER_V015, [tf_q29_local],
    {"_Q29_LO": 848, "_Q29_HI": 1020})
VAR_Q29B = Variante(
    "V015 + Q29-lokal 1021..1287", ADAPTER_V015, [tf_q29_local],
    {"_Q29_LO": 1021, "_Q29_HI": n - 1})

HYP_BASE = Variante("HYP-P10 (Baseline)", AD_HYP, [tf_ident], {})
HYP_FORCE = Variante(
    "HYP-P10 + K67-Freigabe@1122/1123", AD_HYP, [tf_force_freigabe],
    {"_FORCE_FREI": frozenset({1122, 1123}), "_FORCE_KID": 67})
HYP_M6LIVE = Variante(
    "HYP-P10 + M6-nur-lebende", AD_HYP, [tf_m6_live], {})
HYP_POS = Variante(
    "HYP-P10 + pos-nur-lebende", AD_HYP, [tf_pos_live], {})
HYP_M6LIVE_POS = Variante(
    "HYP-P10 + M6-live + pos-live", AD_HYP, [tf_m6_live, tf_pos_live], {})

alles: List[Tuple[Variante, Dict]] = []
for v in (BASE, VAR_M6_FORCE, VAR_M6_LIVE, VAR_POS_LIVE, VAR_Q29A, VAR_Q29B,
          HYP_BASE, HYP_FORCE, HYP_M6LIVE, HYP_POS, HYP_M6LIVE_POS):
    s, st, dg = run(v)
    alles.append((v, summ(v.name, s, dg)))

D = {v.name: d for (v, d) in alles}

# ------------------------------------------------------------------ Header
out("=" * 112)
out("PHASE 2 / H2-MARKTANALYSE -- ISOLIERTE HEBEL-ANALYSE (Read-Only / In-Memory)")
out("=" * 112)
out(f"Engine (Disk, unveraendert) : {ENGINE_P.name}  SHA256 {ENGINE_SHA}")
out(f"Zeitbasis                   : BKZ = \"time\" AT TIME ZONE 'UTC'")
out(f"n={n} | H1/H2-Split bei {BOX} | iteriertes Fenster {W0}..{W1}")
out(f"Adapter V015  : {[(s.phasen_id, s.start_bar, s.end_bar) for s in ADAPTER_V015.segmente]}")
out(f"Adapter HYP   : {[(s.phasen_id, s.start_bar, s.end_bar) for s in AD_HYP.segmente]}  "
    f"(P10_HYP = Hypothese, KEINE Arretierung)")
out(f"H1-Invarianz-Gate: {RANGE_H1[0]} Trades / {RANGE_H1[1]:+.6f} R (entry_bar < {BOX})")
out("")
out("-- Uebersicht aller Varianten ------------------------------------------"
    "----------------------------------------")
hdr = (f"{'Variante':<34} {'Trd':>3} {'R gesamt':>12} | {'H1':>19} | "
       f"{'H2':>19} | {'KN':>3} | Deltas (bar,kid)")
out(hdr)
out(f"{b['name']:<34} {b['trades']:>3} {b['r']:>+12.6f} | "
    f"H1 {b['h1n']:>2}/{b['h1r']:>+10.6f} [{gate(b)}] | "
    f"H2 {b['h2n']:>2}/{b['h2r']:>+10.6f} | KN {b['kn']:>3} | (Referenz)")
for (v, d) in alles:
    if v.name == b["name"]:
        continue
    out(row(d, b))
out("")

# =========================================================== 2.2.1 M6 / K67
out("#" * 112)
out("# 2.2.1  K67-M6-FREIGABE an K73@1122/1123 -- isoliert (Hook-1-Scope)")
out("#" * 112)
out("")
out("Befund vorab: K67 ist an Bar 1122 DORMANT (lebt=False, letzter Kontakt 1020).")
out("M6 prueft nur ``_existiert`` -- eine dormante Wand sperrt also den Innen-")
out("Sweep, obwohl die Engine dormante Linien in ``_kandidat`` ausdruecklich")
out("ignoriert ('dormante Linie ignorieren'). Das ist die Inkonsistenz.")
out("")
out("-- Alle M6-Blocker im Fenster (mit Liveness des Blockers) --")
for (k, ri, tag) in b["diag"]:
    if tag.startswith("M6(") and W0 <= k <= W1:
        out(f"   bar {k:>4} {ri:<5} {tag}")
out("")
out("-- Wirkung der K67-Freigabe (V015-Kontext) --")
out(row(D[VAR_M6_FORCE.name], b))
out(f"   K73@1122/1123 im Ergebnis enthalten? "
    f"{(1122, 73) in D[VAR_M6_FORCE.name]['keys'] or (1123, 73) in D[VAR_M6_FORCE.name]['keys']}")
out("   >> Grund: Hook-2 (Adapter-V015) liefert fuer 1122/1123 BLOCKIERT")
out("      (kein Segment deckt den Bar) -> der Trade ist DOPPELT gesperrt.")
out("")
out("-- Wirkung der M6-Liveness-Regel (V015-Kontext) --")
out(row(D[VAR_M6_LIVE.name], b))
out("")
out("-- Hypothesenkontext P10_HYP (1021..1287, NICHT arretiert) --")
out(row(D[HYP_BASE.name], b))
out(row(D[HYP_FORCE.name], b))
out(row(D[HYP_M6LIVE.name], b))
out("")
for nm in (HYP_BASE.name, HYP_FORCE.name, HYP_M6LIVE.name):
    d = D[nm]
    neu = [k for k in d["keys"] if k not in b["keys"]]
    h2neu = [k for k in neu if k[0] >= W0]
    out(f"   [{nm}] neue Schluessel im H2-Fenster: {h2neu}")
    for t in sorted(d["setup_obj"], key=lambda t: t.bar):
        if t.bar >= W0:
            out(f"       bar {t.bar:>4} entry {t.entry_bar:>4} {t.richtung:<5} "
                f"K{t.kid:<3} R {t.r:+.6f} {t.stufe} (tp2 {t.tp2:.4f})")
out("")

# ============================================================ 2.2.2 pos-Audit
out("#" * 112)
out("# 2.2.2  pos-SORTIERUNG -- Zaehlung nur LEBENDER Kanten (In-Memory-Gegenprobe)")
out("#" * 112)
out("")
out("Fix-Semantik: ``_outer_live`` = erste LEBENDE Linie in der aussen->innen-")
out("Sortierung; nur sie erhaelt das Q1-Privileg 'pos 0 handelt'. Dormante")
out("Aussenlinien (K48/K3/K17) verbrauchen KEIN pos mehr.")
out("")
out(f"KANDIDAT_NONE im Fenster {W0}..{W1}:  Baseline V015 = {b['kn']}")
out(f"                                  V015+pos-live = {D[VAR_POS_LIVE.name]['kn']}"
    f"   (Delta {D[VAR_POS_LIVE.name]['kn'] - b['kn']:+d})")
out(f"                                  HYP-P10       = {D[HYP_BASE.name]['kn']}")
out(f"                                  HYP+pos-live  = {D[HYP_POS.name]['kn']}"
    f"   (Delta {D[HYP_POS.name]['kn'] - D[HYP_BASE.name]['kn']:+d})")
out("")
out("-- Wirkung V015-Kontext --")
out(row(D[VAR_POS_LIVE.name], b))
out("-- Wirkung HYP-P10-Kontext --")
out(row(D[HYP_POS.name], b))
out(row(D[HYP_M6LIVE_POS.name], b))
out("")
out("-- K82@1072 LONG unter HYP+pos-live: Kaskade --")
for nm in (HYP_BASE.name, HYP_POS.name, HYP_M6LIVE_POS.name):
    d = D[nm]
    tr = [t for t in d["setup_obj"] if t.bar in (1072, 1073)]
    out(f"   [{nm}] Trades an 1072/1073: "
        f"{[(t.bar, 'K' + str(t.kid), round(t.r, 6)) for t in tr] or 'keine'}")
out("")

# ============================================================ 2.2.3 Q29-Lokal
out("#" * 112)
out("# 2.2.3  PHASENLOKALES Q29 -- Intervalle getrennt ausgewiesen")
out("#" * 112)
out("")
out("Q29 global nutzt Range-Extrema ueber ALLE kausalen Bars ``hi[:k+1]``.")
out("Phasenlokal: Extrema nur aus [_Q29_LO, k]. Wirkung ausserhalb des")
out("Intervalls bleibt unveraendert (if-Guard).")
out("")
out(f"Intervall 1 (848..1020 = P9-Struktur), arretiertes V015-Segment:")
out(row(D[VAR_Q29A.name], b))
out(f"Intervall 2 (1021..1287 = Vakuum), reiner Hypothesenlauf ohne Segment:")
out(row(D[VAR_Q29B.name], b))
out("")
out("-- Q29-Sperren im Fenster (Baseline) --")
qq = [(k, ri) for (k, ri, tag) in b["diag"] if tag == "Q29" and W0 <= k <= W1]
out(f"   Anzahl: {len(qq)}  ->  {qq}")
out("")
out("  Deutung: Eine Q29-Sperre ist NUR dann strukturell relevant, wenn der")
out("  Sweep ueberhaupt einen Kandidaten erzeugt und danach an Q29 scheitert.")
out("  Ohne Segment (V015) ist der Bar bereits durch Hook-2 BLOCKIERT; die")
out("  Q29-Sperre wirkt dann nur als vorgelagerter Zaehler.")
out("")

# ============================================================ 2.2.4 H1-Gate
out("#" * 112)
out("# 2.2.4  H1-INVARIANZ-GATE (verbindlich)")
out("#" * 112)
out("")
out(f"Soll: H1 = {RANGE_H1[0]} Trades / {RANGE_H1[1]:+.6f} R")
for (v, d) in alles:
    ok = (d["h1n"], d["h1r"]) == RANGE_H1
    out(f"   {v.name:<40} H1 {d['h1n']:>2}/{d['h1r']:>+10.6f}  "
        f"{'OK' if ok else '*** VERLETZT ***'}")
out("")
out("-- H1-Schluessel je Variante (nur bei Abweichung zur Baseline) --")
for (v, d) in alles:
    if d["h1keys"] != b["h1keys"]:
        out(f"   {v.name}: +{sorted(set(d['h1keys']) - set(b['h1keys']))} "
            f"-{sorted(set(b['h1keys']) - set(d['h1keys']))}")
out("")

out("-- SHA-Kontrolle der Engine-Datei --")
out(f"   {hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()}  "
    f"{'UNVERAENDERT' if hashlib.sha256(ENGINE_P.read_bytes()).hexdigest() == ENGINE_SHA else 'DRIFT'}")
out("")
out("ENDE PHASE 2")

report = "\n".join(BUF)
(ROOT / "test" / "_tmp_explo_v018_phase2_out.txt").write_text(
    report, encoding="utf-8")
print(report)
