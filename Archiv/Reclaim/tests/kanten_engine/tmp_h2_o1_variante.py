# -*- coding: utf-8 -*-
"""READ-ONLY: Wirkung der O1-Akkumulationsschranke (Alter >= 96) -- AUG.

Befund-Verdacht: Der _p8-Prune akkumuliert WAR_AUSSEN_IDS nur innerhalb des
Zweigs `_alt >= wall_live_bars`. Eine Linie, die in ihren ersten 96 Bars
aeusserste lebende Linie war, wird nie als solche registriert und ist damit
spaeter loeschbar (Schutz-Luecke).

V0 = Ist-Stand (_p8 arretiert)
V1 = O1-Akkumulation fuer ALLE Altersstufen (separater Pre-Pass je Bar k)
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, src: str):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(P)
    sys.modules[name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


with open(P, encoding="utf-8", newline="") as f:
    SRC = f.read()

A = ("                    if (_alt >= cfg.wall_live_bars\r\n"
     "                            and not _e.ist_prim_anker):\r\n"
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
     "                        if _ist_aussen:\r\n"
     "                            WAR_AUSSEN_IDS.add(_e.kid)   # O1 arretiert\r\n")
assert SRC.count(A) == 1, SRC.count(A)

B = ("        # --- §7.2 Teil 5: R21-Bereinigung (kausal bei Bar k, in-place) --\r\n"
     "        if cfg.r21_loeschung_aktiv:\r\n")
assert SRC.count(B) == 1, SRC.count(B)

PREPASS = (
    "        # VARIANTE V1: O1-Aussenrolle fuer ALLE Altersstufen akkumulieren\r\n"
    "        if cfg.r21_loeschung_aktiv:\r\n"
    "            for _seite in (\"OBEN\", \"UNTEN\"):\r\n"
    "                _lb = [r for r in cluster[_seite]\r\n"
    "                       if _lebt_scan(r, k)]\r\n"
    "                if _lb:\r\n"
    "                    _mx = max(r.basis for r in _lb)\r\n"
    "                    _mn = min(r.basis for r in _lb)\r\n"
    "                    for _e in cluster[_seite]:\r\n"
    "                        if _seite == \"OBEN\":\r\n"
    "                            if _e.basis >= _mx:\r\n"
    "                                WAR_AUSSEN_IDS.add(_e.kid)\r\n"
    "                        else:\r\n"
    "                            if _e.basis <= _mn:\r\n"
    "                                WAR_AUSSEN_IDS.add(_e.kid)\r\n"
    "\r\n")
V1 = SRC.replace(A, "", 1).replace(B, PREPASS + B, 1)
assert V1 != SRC

base = load("ke_v0", SRC)
alt = load("ke_v1", V1)
cfg = base.StraightEdgeHarnessKonfiguration()

print("=" * 112)
print("O1-AKKUMULATIONSSCHRANKE (Alter >= 96) -- READ-ONLY, AUG n=1288")
print("=" * 112)
for label, mod in (("V0 (arretiert, Alter >= 96)", base),
                   ("V1 (alle Altersstufen)", alt)):
    sc = mod._se_scan("AUG", cfg)
    n = sc["n"]
    sc["box_end_bar"] = n
    tr, st = mod._se_trades(sc, cfg)
    r21 = sc.get("r21_geloescht") or []
    gel = [r for r in r21 if r[1] >= 0]
    gesp = [r for r in r21 if r[1] < 0]
    sig = [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in tr]
    print("")
    print(f"{label}:")
    print(f"  Kanten        : {len(sc['edges']) + len(sc['seeds'])} "
          f"(edges {len(sc['edges'])} / seeds {len(sc['seeds'])})")
    print(f"  R21 geloescht : {len(gel)} | Geburten gesperrt: {len(gesp)}")
    print(f"  WAR_AUSSEN    : {len(mod.WAR_AUSSEN_IDS)} IDs")
    print(f"  Trades        : {len(tr)} | Netto-R {sum(t.r for t in tr):+.2f}")
    print(f"  Stacking      : {st.get('stacking_blockiert')} | "
          f"Zyklus {st.get('zyklus_blockiert')}")
    print(f"  Signaturen    : {sig}")
    print(f"  geloeschte K  : {sorted(r[1] for r in gel)}")

# Direktvergleich
sc0 = base._se_scan("AUG", cfg)
sc0["box_end_bar"] = sc0["n"]
tr0, _ = base._se_trades(sc0, cfg)
sc1 = alt._se_scan("AUG", cfg)
sc1["box_end_bar"] = sc1["n"]
tr1, _ = alt._se_trades(sc1, cfg)
g0 = {r[1] for r in (sc0.get("r21_geloescht") or []) if r[1] >= 0}
g1 = {r[1] for r in (sc1.get("r21_geloescht") or []) if r[1] >= 0}
s0 = [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in tr0]
s1 = [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in tr1]
print("")
print("=" * 112)
print("DIREKTVERGLEICH")
print("=" * 112)
print(f"  Trade-Signatur : {'IDENTISCH' if s0 == s1 else 'ABWEICHEND'}")
print(f"  Netto-R        : V0 {sum(t.r for t in tr0):+.2f} | "
      f"V1 {sum(t.r for t in tr1):+.2f}")
print(f"  geloescht V0   : {sorted(g0)}")
print(f"  geloescht V1   : {sorted(g1)}")
print(f"  Differenz      : V1 loescht weniger: {sorted(g0 - g1)}")
