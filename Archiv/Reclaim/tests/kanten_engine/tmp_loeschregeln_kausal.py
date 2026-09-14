# -*- coding: utf-8 -*-
"""READ-ONLY: KAUSALE Loeschregeln (Timeout) fuer Zwischenkanten -- AUG komplett.

Getestet werden Regeln, die ausschliesslich Informationen bis Bar k nutzen
(kein Look-ahead). Geprueft wird je Regel: Folgekanten (neue Geburten) und
Trade-Signatur gegen den Original-Lauf.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
L: List[str] = []


def out(s: str = "") -> None:
    L.append(s)


def load(name: str, src: str):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(P)
    sys.modules[name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


with open(P, encoding="utf-8", newline="") as f:
    SRC = f.read()

# --- Anker: Ende der k-Schleife in _se_scan (2-Body-Bruch-Block) ------------
A = ("                if aussen and e.status == \"AKTIV\":\r\n"
     "                    e.status = \"SCHLAFEND\"\r\n"
     "                    e.schlaf_windows.append((k, None))\r\n")
assert SRC.count(A) == 1, SRC.count(A)

PRUNE = (
    "                if aussen and e.status == \"AKTIV\":\r\n"
    "                    e.status = \"SCHLAFEND\"\r\n"
    "                    e.schlaf_windows.append((k, None))\r\n"
    "\r\n"
    "        # --- PRUNING (in-memory Regel-Test, kausal bis Bar k) ---------\r\n"
    "        if RULE_MODE:\r\n"
    "            for _seite in (\"OBEN\", \"UNTEN\"):\r\n"
    "                _keep = []\r\n"
    "                for _e in cluster[_seite]:\r\n"
    "                    _alt = k - _e.erster_pivot_bar\r\n"
    "                    _loeschen = False\r\n"
    "                    if (_alt >= cfg.wall_live_bars\r\n"
    "                            and not _e.ist_prim_anker):\r\n"
    "                        _n = _e.touch_conf(k)\r\n"
    "                        if RULE_MODE in (\"R8\", \"R10\") and _n < 2:\r\n"
    "                            _loeschen = True          # Singleton-Timeout\r\n"
    "                        if not _loeschen and RULE_MODE in (\"R9\", \"R10\"):\r\n"
    "                            _lb = [r for r in cluster[_seite]\r\n"
    "                                   if _lebt_scan(r, k)]\r\n"
    "                            if _lb:\r\n"
    "                                _au = ((max(r.basis for r in _lb))\r\n"
    "                                       if _seite == \"OBEN\"\r\n"
    "                                       else (min(r.basis for r in _lb)))\r\n"
    "                                _ist_aussen = ((_e.basis >= _au)\r\n"
    "                                               if _seite == \"OBEN\"\r\n"
    "                                               else (_e.basis <= _au))\r\n"
    "                                if not _ist_aussen:\r\n"
    "                                    _loeschen = True  # Nicht-Aussenkante\r\n"
    "                        if (not _loeschen and RULE_MODE == \"R11\"\r\n"
    "                                and _n < 3):\r\n"
    "                            _loeschen = True      # nicht handelbar\r\n"
    "                        if (not _loeschen\r\n"
    "                                and RULE_MODE in (\"R18\", \"R19\")):\r\n"
    "                            if _n < 2:\r\n"
    "                                _letzter = max(b for b, _ in _e.wicks\r\n"
    "                                               if b <= k)\r\n"
    "                                _lb = [r for r in cluster[_seite]\r\n"
    "                                       if _lebt_scan(r, k)]\r\n"
    "                                _ist_aussen = True\r\n"
    "                                if _lb:\r\n"
    "                                    if _seite == \"OBEN\":\r\n"
    "                                        _ist_aussen = _e.basis >= max(\r\n"
    "                                            r.basis for r in _lb)\r\n"
    "                                    else:\r\n"
    "                                        _ist_aussen = _e.basis <= min(\r\n"
    "                                            r.basis for r in _lb)\r\n"
    "                                _geschuetzt = _e.kid in WAR_AUSSEN\r\n"
    "                                if (RULE_MODE == \"R19\" and _ist_aussen):\r\n"
    "                                    WAR_AUSSEN.add(_e.kid)\r\n"
    "                                if (k - _letzter >= 96 and not _ist_aussen\r\n"
    "                                        and not _geschuetzt):\r\n"
    "                                    _loeschen = True\r\n"
    "                        if (not _loeschen and RULE_MODE in (\"R15\", \"R16\", \"R17\")\r\n"
    "                                and _n < (3 if RULE_MODE != \"R16\" else 99)):\r\n"
    "                            _lb = [r for r in cluster[_seite]\r\n"
    "                                   if _lebt_scan(r, k)]\r\n"
    "                            if _lb:\r\n"
    "                                if _seite == \"OBEN\":\r\n"
    "                                    _ersetzt = any(r.basis > _e.basis\r\n"
    "                                                   for r in _lb)\r\n"
    "                                else:\r\n"
    "                                    _ersetzt = any(r.basis < _e.basis\r\n"
    "                                                   for r in _lb)\r\n"
    "                                if _ersetzt:\r\n"
    "                                    _letzter = max(b for b, _ in _e.wicks\r\n"
    "                                                   if b <= k)\r\n"
    "                                    _dorm = k - _letzter\r\n"
    "                                    _lim = (192 if RULE_MODE == \"R17\"\r\n"
    "                                            else 96)\r\n"
    "                                    if _dorm >= _lim:\r\n"
    "                                        _loeschen = True\r\n"
    "                    if _loeschen:\r\n"
    "                        PRUNE_LOG.append((k, _e.kid, _e.seite,\r\n"
    "                                          round(_e.basis, 3), _alt))\r\n"
    "                    else:\r\n"
    "                        _keep.append(_e)\r\n"
    "                cluster[_seite] = _keep\r\n"
)
patched = SRC.replace(A, PRUNE, 1)
patched = patched.replace(
    "MAX_SIGNAL_ZEILEN: int = 60",
    "MAX_SIGNAL_ZEILEN: int = 60\r\n"
    "RULE_MODE: str = \"\"\r\nPRUNE_LOG: List[Tuple] = []\r\nWAR_AUSSEN: set = set()", 1)
# _lebt_scan-Helfer (identisch zu _lebt in _se_trades) vor der k-Schleife
A2 = "    for k in range(n):\r\n        mbar = k - 2\r\n"
assert patched.count(A2) == 1
patched = patched.replace(
    A2,
    "    def _lebt_scan(e: _SEEdgeH, kk: int) -> bool:\r\n"
    "        _b = [b for b, _ in e.wicks if b <= kk]\r\n"
    "        return bool(_b) and max(_b) >= kk - cfg.wall_live_bars\r\n"
    "\r\n" + A2, 1)

base = load("ke_b", SRC)
cfg = base.StraightEdgeHarnessKonfiguration()
scan0 = base._se_scan("AUG", cfg)
n = len(scan0["d"])
scan0["box_end_bar"] = n
tr0, _ = base._se_trades(scan0, cfg)
orig_sig = [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in tr0]
orig_sigs = {(e.seite, e.wicks[0][0], round(e.wicks[0][1], 3))
             for e in list(scan0["edges"]) + list(scan0["seeds"])}

mod = load("ke_p", patched)
out("#" * 118)
out("# KAUSALE LOESCHREGELN (READ-ONLY) -- AUG komplett")
out(f"# n={n} | Original: Kanten {len(scan0['edges']) + len(scan0['seeds'])} "
    f"| Trades {len(tr0)} / {sum(t.r for t in tr0):+.2f} R")
out("#" * 118)
out("")
out("Regel-Definitionen (alle kausal bis Bar k, Timeout = wall_live_bars 96):")
out("  R8  = Singleton-Timeout: < 2 Touches nach 96 Bars -> loeschen")
out("  R9  = Nicht-Aussenkante: 96 Bars lang nicht aeusserste lebende Linie")
out("  R10 = R8 + R9")
out("  R11 = nicht handelbar (< 3 Touches, kein Primaer-Anker) nach 96 Bars")
out("  R15 = ersetzt+dormant: < 3 Touches, von neuerer Aussenlinie ersetzt,")
out("        letzter Kontakt >= 96 Bars -> loeschen")
out("  R16 = wie R15 ohne Touch-Grenze (auch >= 3 Touches)")
out("  R17 = wie R15, Dormanz-Fenster 192 Bars")
out("  R18 = Singleton-Timeout + nie als lebende Aussenlinie aufgetreten")
out("  R19 = R18 + Schutz fuer Linien, die je Aussenlinie waren")
out("")

for mode in ("R18", "R19"):
    mod.RULE_MODE = mode
    mod.PRUNE_LOG = []
    mod.WAR_AUSSEN = set()
    sc = mod._se_scan("AUG", cfg)
    sc["box_end_bar"] = n
    tr, st = mod._se_trades(sc, cfg)
    alle = list(sc["edges"]) + list(sc["seeds"])
    sig = {(e.seite, e.wicks[0][0], round(e.wicks[0][1], 3)) for e in alle}
    folge = sig - orig_sigs
    trs = [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in tr]
    out("=" * 118)
    out(f"{mode}: geloeschte Kanten {len(mod.PRUNE_LOG)} | Kanten danach "
        f"{len(alle)} (orig 93) | edges {len(sc['edges'])} seeds "
        f"{len(sc['seeds'])}")
    out("=" * 118)
    out(f"  Trades        : {len(tr)} (orig {len(tr0)}) | Netto-R "
        f"{sum(t.r for t in tr):+.2f} (orig {sum(t.r for t in tr0):+.2f})")
    out(f"  Trade-Signatur: {'IDENTISCH' if trs == orig_sig else 'ABWEICHEND'}")
    if trs != orig_sig:
        for a, b in zip(orig_sig, trs):
            out(f"      orig {a} vs neu {b}{'' if a == b else '   <<<'}")
        if len(trs) != len(orig_sig):
            out(f"      Anzahl: orig {len(orig_sig)} vs neu {len(trs)}")
    out(f"  FOLGEKANTEN   : {len(folge)}")
    for s in sorted(folge, key=lambda x: (x[1], x[2])):
        out(f"      neu: {s[0]:5s} pivot_bar={s[1]:4d} px={s[2]:.3f}")
    # Loeschzeitpunkte (Alter)
    if mod.PRUNE_LOG:
        alter = [p[4] for p in mod.PRUNE_LOG]
        out(f"  Alter beim Loeschen: min={min(alter)} max={max(alter)} "
            f"median={sorted(alter)[len(alter) // 2]}")
        out(f"  geloeschte Kanten: {sorted(p[1] for p in mod.PRUNE_LOG)}")
    out("")

# ---------------------------------------------------------------------------
# R12/R13: GEBURTS-Filter (deletion at birth, kausal)
#   R12 = Geburt nur an einem NEUEN Range-Extrem (Docht = kausales Extrem)
#   R13 = Geburt nur im aeusseren Quartil der kausalen Spanne
# ---------------------------------------------------------------------------
A3 = ("                    e = _SEEdgeH(kid=kid_next, seite=seite, basis=px,"
      "\r\n"
      "                                 geburts_bar=mbar, erster_pivot_bar=mbar)"
      "\r\n")
assert SRC.count(A3) == 1
BIRTH_GUARD = (
    "                    _ok12 = True\r\n"
    "                    if RULE_MODE == \"R12\":\r\n"
    "                        if seite == \"OBEN\":\r\n"
    "                            _ok12 = px >= float(np.max(hi[:mbar + 1]))\r\n"
    "                        else:\r\n"
    "                            _ok12 = px <= float(np.min(lo[:mbar + 1]))\r\n"
    "                    if RULE_MODE == \"R13\":\r\n"
    "                        _ex_hi = float(np.max(hi[:mbar + 1]))\r\n"
    "                        _ex_lo = float(np.min(lo[:mbar + 1]))\r\n"
    "                        _sp = _ex_hi - _ex_lo\r\n"
    "                        if _sp > 0:\r\n"
    "                            _d = (((_ex_hi - px) if seite == \"OBEN\"\r\n"
    "                                   else (px - _ex_lo)) / _sp * 100.0)\r\n"
    "                            _ok12 = _d <= cfg.quartil_distanz_pct\r\n"
    "                    if not _ok12:\r\n"
    "                        PRUNE_LOG.append((mbar, -1, seite, round(px, 3), 0))\r\n"
    "                        continue\r\n")
p2 = SRC.replace(A3, BIRTH_GUARD + A3, 1)
p2 = p2.replace("MAX_SIGNAL_ZEILEN: int = 60",
                "MAX_SIGNAL_ZEILEN: int = 60\r\n"
                "RULE_MODE: str = \"\"\r\nPRUNE_LOG: List[Tuple] = []", 1)
mod2 = load("ke_p2", p2)
out("=" * 118)
out("GEBURTS-FILTER (deletion at birth, kausal bis mbar)")
out("=" * 118)
for mode in ("R12", "R13"):
    mod2.RULE_MODE = mode
    mod2.PRUNE_LOG = []
    sc = mod2._se_scan("AUG", cfg)
    sc["box_end_bar"] = n
    tr, st = mod2._se_trades(sc, cfg)
    alle = list(sc["edges"]) + list(sc["seeds"])
    sig = {(e.seite, e.wicks[0][0], round(e.wicks[0][1], 3)) for e in alle}
    folge = sig - orig_sigs
    trs = [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in tr]
    out("-" * 118)
    out(f"{mode}: unterdrueckte Geburten {len(mod2.PRUNE_LOG)} | Kanten danach "
        f"{len(alle)} (orig 93) | edges {len(sc['edges'])} seeds "
        f"{len(sc['seeds'])}")
    out(f"  Trades        : {len(tr)} (orig {len(tr0)}) | Netto-R "
        f"{sum(t.r for t in tr):+.2f} (orig {sum(t.r for t in tr0):+.2f})")
    out(f"  Trade-Signatur: {'IDENTISCH' if trs == orig_sig else 'ABWEICHEND'}")
    if trs != orig_sig:
        for a, b in zip(orig_sig, trs):
            out(f"      orig {a} vs neu {b}{'' if a == b else '   <<<'}")
        if len(trs) != len(orig_sig):
            out(f"      Anzahl: orig {len(orig_sig)} vs neu {len(trs)}")
    out(f"  FOLGEKANTEN   : {len(folge)}")
    for s in sorted(folge, key=lambda x: (x[1], x[2])):
        out(f"      neu: {s[0]:5s} pivot_bar={s[1]:4d} px={s[2]:.3f}")

txt = "\n".join(L)
print(txt)
with open(ROOT / "test" / "tmp_loeschregeln_kausal.txt", "w",
          encoding="utf-8") as f:
    f.write(txt + "\n")
