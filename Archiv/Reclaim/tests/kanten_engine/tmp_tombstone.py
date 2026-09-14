# -*- coding: utf-8 -*-
"""READ-ONLY: Wiedergeburt-Analyse + TOMBSTONE-Regel (R20) -- AUG komplett.

Hypothese: Die Loeschung einer Zwischenkante (R18) macht den Weg frei fuer
eine NEUE Kante im gleichen Preisband (Wiedergeburt), die dann als Folgekante
andere Trades erzeugt. Gegenmittel: Tombstone -- das geloeschte Band wird fuer
X Bars fuer Neugeburten gesperrt.
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

# --- Anker: Ende der k-Schleife in _se_scan --------------------------------
A = ("                if aussen and e.status == \"AKTIV\":\r\n"
     "                    e.status = \"SCHLAFEND\"\r\n"
     "                    e.schlaf_windows.append((k, None))\r\n")
assert SRC.count(A) == 1

PRUNE = (
    A +
    "\r\n"
    "        # --- PRUNING (kausal bis Bar k) -------------------------------\r\n"
    "        if RULE_MODE:\r\n"
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
    "                        TOMB.append((k, _e.seite, _e.basis))\r\n"
    "                    else:\r\n"
    "                        _keep.append(_e)\r\n"
    "                cluster[_seite] = _keep\r\n"
)
patched = SRC.replace(A, PRUNE, 1)
patched = patched.replace(
    "MAX_SIGNAL_ZEILEN: int = 60",
    "MAX_SIGNAL_ZEILEN: int = 60\r\n"
    "RULE_MODE: str = \"\"\r\nPRUNE_LOG: List[Tuple] = []\r\n"
    "WAR_AUSSEN: set = set()\r\nTOMB: List[Tuple] = []\r\n"
    "BIRTH_LOG: List[Tuple] = []\r\n"
    "TOMB_MODE: bool = False\r\nTOMB_BAND: float = 0.30\r\n"
    "TOMB_FENSTER: int = 10 ** 9", 1)
A2 = "    for k in range(n):\r\n        mbar = k - 2\r\n"
assert patched.count(A2) == 1
patched = patched.replace(
    A2,
    "    def _lebt_scan(e: _SEEdgeH, kk: int) -> bool:\r\n"
    "        _b = [b for b, _ in e.wicks if b <= kk]\r\n"
    "        return bool(_b) and max(_b) >= kk - cfg.wall_live_bars\r\n"
    "\r\n" + A2, 1)

# --- Geburts-Pfad: Logging + Tombstone-Sperre ------------------------------
A5 = ("                    e = _SEEdgeH(kid=kid_next, seite=seite, basis=px,"
      "\r\n"
      "                                 geburts_bar=mbar, erster_pivot_bar=mbar)"
      "\r\n")
assert patched.count(A5) == 1
GUARD = (
    "                    BIRTH_LOG.append((mbar, seite, round(px, 3)))\r\n"
    "                    if TOMB_MODE and TOMB:\r\n"
    "                        _sp = False\r\n"
    "                        for _tk, _ts, _tp in TOMB:\r\n"
    "                            if (_ts == seite\r\n"
    "                                    and mbar - _tk <= TOMB_FENSTER\r\n"
    "                                    and abs(px - _tp) / _tp * 100.0\r\n"
    "                                    <= TOMB_BAND):\r\n"
    "                                _sp = True\r\n"
    "                                break\r\n"
    "                        if _sp:\r\n"
    "                            BIRTH_BLOCK.append((mbar, seite, round(px, 3)))\r\n"
    "                            continue\r\n")
patched = patched.replace(A5, GUARD + A5, 1)
patched = patched.replace("BIRTH_LOG: List[Tuple] = []",
                          "BIRTH_LOG: List[Tuple] = []\r\n"
                          "BIRTH_BLOCK: List[Tuple] = []", 1)

base = load("ke_b", SRC)
cfg = base.StraightEdgeHarnessKonfiguration()
scan0 = base._se_scan("AUG", cfg)
n = len(scan0["d"])
scan0["box_end_bar"] = n
tr0, _ = base._se_trades(scan0, cfg)
orig_sig = [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in tr0]
orig_sigs = {(e.seite, e.wicks[0][0], round(e.wicks[0][1], 3))
             for e in list(scan0["edges"]) + list(scan0["seeds"])}

mod = load("ke_t", patched)
out("#" * 118)
out("# TOMBSTONE-TEST (READ-ONLY) -- AUG komplett")
out(f"# n={n} | Original: Kanten {len(orig_sigs)} | Trades {len(tr0)} / "
    f"{sum(t.r for t in tr0):+.2f} R")
out("#" * 118)
out("")
out("Regel R18 (Baseline): Singleton (<2 Touches) nach 96 Bars, nur wenn die")
out("Linie nie eine lebende Aussenlinie war (WAR_AUSSEN-Schutz).")
out("R20 = R18 + Tombstone: geloeschtes Preisband wird fuer Neugeburten gesperrt")
out("      (Band-Toleranz und Sperr-Fenster werden variiert).")
out("")


def lauf(label: str, tomb: bool, band: float, fenster: int) -> Dict:
    mod.RULE_MODE = "R18"
    mod.PRUNE_LOG = []
    mod.WAR_AUSSEN = set()
    mod.TOMB = []
    mod.BIRTH_LOG = []
    mod.BIRTH_BLOCK = []
    mod.TOMB_MODE = tomb
    mod.TOMB_BAND = band
    mod.TOMB_FENSTER = fenster
    sc = mod._se_scan("AUG", cfg)
    sc["box_end_bar"] = n
    tr, st = mod._se_trades(sc, cfg)
    alle = list(sc["edges"]) + list(sc["seeds"])
    sig = {(e.seite, e.wicks[0][0], round(e.wicks[0][1], 3)) for e in alle}
    trs = [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in tr]
    res = {
        "label": label, "geloescht": len(mod.PRUNE_LOG), "kanten": len(alle),
        "birth_block": len(mod.BIRTH_BLOCK), "trades": trs,
        "netto": sum(t.r for t in tr),
        "ident": trs == orig_sig, "folge": sorted(sig - orig_sigs,
                                                 key=lambda x: (x[1], x[2])),
    }
    out("-" * 118)
    out(f"{label}: geloescht {res['geloescht']} | Geburten gesperrt "
        f"{res['birth_block']} | Kanten {res['kanten']} (orig {len(orig_sigs)})")
    out(f"  Trades {len(trs)} (orig {len(orig_sig)}) | Netto-R {res['netto']:+.2f} "
        f"(orig {sum(t.r for t in tr0):+.2f}) | Signatur "
        f"{'IDENTISCH' if res['ident'] else 'ABWEICHEND'}")
    if not res["ident"]:
        for a, b in zip(orig_sig, trs):
            out(f"      orig {a} vs neu {b}{'' if a == b else '   <<<'}")
        if len(trs) != len(orig_sig):
            out(f"      Anzahl: orig {len(orig_sig)} vs neu {len(trs)}")
    out(f"  FOLGEKANTEN: {len(res['folge'])}")
    for s in res["folge"]:
        out(f"      neu: {s[0]:5s} pivot_bar={s[1]:4d} px={s[2]:.3f}")
    return res


base18 = lauf("R18 (Baseline)", False, 0.30, 10 ** 9)
# Wiedergeburt-Diagnose: liegt jede Folgekante in einem geloeschten Band?
out("")
out("=" * 118)
out("WIEDERGEBURT-DIAGNOSE: Folgekanten vs. geloeschte Baender (R18)")
out("=" * 118)
for seite, pbar, px in base18["folge"]:
    treffer = []
    for tk, ts, tp in mod.TOMB:
        if ts == seite and abs(px - tp) / tp * 100.0 <= 0.30:
            treffer.append((tk, round(tp, 3)))
    out(f"  {seite:5s} pivot_bar={pbar:4d} px={px:8.3f} | "
        f"Tombstone-Treffer (<=0.30%): {len(treffer)} "
        f"{('-> ' + str(treffer[:3])) if treffer else ''}")

for band, fenster in ((0.30, 10 ** 9), (0.30, 192), (0.30, 96),
                      (0.60, 10 ** 9), (1.00, 10 ** 9), (0.10, 10 ** 9)):
    lauf(f"R20 band={band:.2f}% fenster={fenster}", True, band, fenster)

txt = "\n".join(L)
print(txt)
with open(ROOT / "test" / "tmp_tombstone.txt", "w", encoding="utf-8") as f:
    f.write(txt + "\n")
