# -*- coding: utf-8 -*-
"""READ-ONLY: Einzel-Attribution der Loeschungen (R18) -- AUG komplett.

Fuer jede von R18 geloeschte Kante wird geprueft, ob ihre Entfernung ALLEIN
die Trade-Signatur veraendert (harmful) oder nicht (harmless). Daraus wird
die maximale harmlose Loeschmenge gebildet und erneut verifiziert.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

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

# --- R18-Scan (in-memory) zur Ermittlung der geloeschten Kanten ------------
A = ("                if aussen and e.status == \"AKTIV\":\r\n"
     "                    e.status = \"SCHLAFEND\"\r\n"
     "                    e.schlaf_windows.append((k, None))\r\n")
assert SRC.count(A) == 1
PRUNE = (
    A + "\r\n"
    "        if RULE_MODE == \"R18\":\r\n"
    "            for _seite in (\"OBEN\", \"UNTEN\"):\r\n"
    "                _keep = []\r\n"
    "                for _e in cluster[_seite]:\r\n"
    "                    _alt = k - _e.erster_pivot_bar\r\n"
    "                    _loeschen = False\r\n"
    "                    if (_alt >= cfg.wall_live_bars\r\n"
    "                            and not _e.ist_prim_anker):\r\n"
    "                        _n = _e.touch_conf(k)\r\n"
    "                        _lb = [r for r in cluster[_seite]\r\n"
    "                               if _lebt_scan(r, k)]\r\n"
    "                        _ist_aussen = True\r\n"
    "                        if _lb:\r\n"
    "                            if _seite == \"OBEN\":\r\n"
    "                                _ist_aussen = _e.basis >= max(\r\n"
    "                                    r.basis for r in _lb)\r\n"
    "                            else:\r\n"
    "                                _ist_aussen = _e.basis <= min(\r\n"
    "                                    r.basis for r in _lb)\r\n"
    "                        _geschuetzt = _e.kid in WAR_AUSSEN\r\n"
    "                        if _ist_aussen:\r\n"
    "                            WAR_AUSSEN.add(_e.kid)\r\n"
    "                        if _n < 2 and not _ist_aussen and not _geschuetzt:\r\n"
    "                            _letzter = max(b for b, _ in _e.wicks if b <= k)\r\n"
    "                            if k - _letzter >= 96:\r\n"
    "                                _loeschen = True\r\n"
    "                    if _loeschen:\r\n"
    "                        PRUNE_LOG.append((k, _e.kid, _e.seite,\r\n"
    "                                          round(_e.basis, 3), _alt))\r\n"
    "                    else:\r\n"
    "                        _keep.append(_e)\r\n"
    "                cluster[_seite] = _keep\r\n")
p18 = SRC.replace(A, PRUNE, 1)
p18 = p18.replace("MAX_SIGNAL_ZEILEN: int = 60",
                  "MAX_SIGNAL_ZEILEN: int = 60\r\n"
                  "RULE_MODE: str = \"\"\r\nPRUNE_LOG: List[Tuple] = []\r\n"
                  "WAR_AUSSEN: set = set()", 1)
A2 = "    for k in range(n):\r\n        mbar = k - 2\r\n"
assert p18.count(A2) == 1
p18 = p18.replace(
    A2,
    "    def _lebt_scan(e: _SEEdgeH, kk: int) -> bool:\r\n"
    "        _b = [b for b, _ in e.wicks if b <= kk]\r\n"
    "        return bool(_b) and max(_b) >= kk - cfg.wall_live_bars\r\n"
    "\r\n" + A2, 1)

# --- deletion-at-birth (BLACKLIST) fuer die Einzel-Attribution -------------
A5 = ("                    e = _SEEdgeH(kid=kid_next, seite=seite, basis=px,"
      "\r\n"
      "                                 geburts_bar=mbar, erster_pivot_bar=mbar)"
      "\r\n")
assert SRC.count(A5) == 1
GUARD = ("                    if (seite, mbar, round(px, 3)) in BLACKLIST:"
         "\r\n"
         "                        continue\r\n")
pdel = SRC.replace(A5, GUARD + A5, 1)
pdel = pdel.replace("MAX_SIGNAL_ZEILEN: int = 60",
                    "MAX_SIGNAL_ZEILEN: int = 60\r\nBLACKLIST: set = set()", 1)

base = load("ke_b", SRC)
cfg = base.StraightEdgeHarnessKonfiguration()
scan0 = base._se_scan("AUG", cfg)
n = len(scan0["d"])
scan0["box_end_bar"] = n
tr0, _ = base._se_trades(scan0, cfg)
orig_sig = [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in tr0]
orig_sigs = {(e.seite, e.wicks[0][0], round(e.wicks[0][1], 3))
             for e in list(scan0["edges"]) + list(scan0["seeds"])}
kid2edge = {e.kid: e for e in list(scan0["edges"]) + list(scan0["seeds"])}

m18 = load("ke_18", p18)
m18.RULE_MODE = "R18"
m18.PRUNE_LOG = []
m18.WAR_AUSSEN = set()
sc18 = m18._se_scan("AUG", cfg)
sc18["box_end_bar"] = n
tr18, _ = m18._se_trades(sc18, cfg)
trs18 = [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in tr18]
gel = sorted({p[1] for p in m18.PRUNE_LOG})

mdel = load("ke_del", pdel)


def sig_of(blacklist: Set[Tuple]) -> Tuple:
    mdel.BLACKLIST = set(blacklist)
    sc = mdel._se_scan("AUG", cfg)
    sc["box_end_bar"] = n
    tr, _ = mdel._se_trades(sc, cfg)
    return [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in tr]


out("#" * 118)
out("# EINZEL-ATTRIBUTION DER R18-LOESCHUNGEN (READ-ONLY) -- AUG komplett")
out(f"# n={n} | Original {len(tr0)} Trades / {sum(t.r for t in tr0):+.2f} R | "
    f"R18 {len(tr18)} Trades / {sum(t.r for t in tr18):+.2f} R")
out("#" * 118)
out("")
out(f"R18 loescht {len(gel)} Kanten: {gel}")
out("")

harmlos: List[int] = []
schaedlich: List[Tuple[int, List[str]]] = []
for kid in gel:
    e = kid2edge.get(kid)
    if e is None:
        out(f"  K{kid}: nicht im Original-Cluster (bereits anders entfernt)")
        continue
    sig = (e.seite, e.wicks[0][0], round(e.wicks[0][1], 3))
    got = sig_of({sig})
    if got == orig_sig:
        harmlos.append(kid)
    else:
        diffs = [f"{a}->{b}" for a, b in zip(orig_sig, got) if a != b]
        schaedlich.append((kid, diffs))
    out(f"  K{kid:3d} {e.seite:5s} pivot={e.wicks[0][0]:4d} "
        f"px={e.wicks[0][1]:8.3f} | {len(e.wicks)} Touches | "
        f"{'harmlos' if got == orig_sig else 'SCHAEDLICH'}")

out("")
out("=" * 118)
out(f"HARMLOS: {len(harmlos)} von {len(gel)} Einzel-Loeschungen")
out(f"  {sorted(harmlos)}")
out(f"SCHAEDLICH: {len(schaedlich)}")
for kid, diffs in schaedlich:
    out(f"  K{kid}: {diffs[:3]}")
out("")

# --- Sammel-Test: nur die harmlosen loeschen -------------------------------
bl_harm = {(kid2edge[k].seite, kid2edge[k].wicks[0][0],
            round(kid2edge[k].wicks[0][1], 3)) for k in harmlos}
sig_h = sig_of(bl_harm)
mdel.BLACKLIST = bl_harm
sc = mdel._se_scan("AUG", cfg)
sc["box_end_bar"] = n
alle_h = list(sc["edges"]) + list(sc["seeds"])
sig_set_h = {(e.seite, e.wicks[0][0], round(e.wicks[0][1], 3))
             for e in alle_h}
folge_h = sig_set_h - orig_sigs
out("=" * 118)
out(f"SAMMEL-TEST: alle {len(harmlos)} harmlosen Loeschungen gemeinsam")
out("=" * 118)
out(f"  Trades        : {len(sig_h)} (orig {len(orig_sig)}) | Netto-R "
    f"{sum(t[3] for t in sig_h):+.2f} (orig {sum(t.r for t in tr0):+.2f})")
out(f"  Trade-Signatur: {'IDENTISCH' if sig_h == orig_sig else 'ABWEICHEND'}")
out(f"  Kanten danach : {len(alle_h)} (orig {len(orig_sigs)}) | "
    f"FOLGEKANTEN {len(folge_h)}")
for s in sorted(folge_h, key=lambda x: (x[1], x[2])):
    out(f"      neu: {s[0]:5s} pivot_bar={s[1]:4d} px={s[2]:.3f}")

txt = "\n".join(L)
print(txt)
with open(ROOT / "test" / "tmp_deletion_attribution.txt", "w",
          encoding="utf-8") as f:
    f.write(txt + "\n")
