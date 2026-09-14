# -*- coding: utf-8 -*-
"""S2 (2025) Scan-Cache + Pickle-Roundtrip + Ebene-2-Rollenprobe (read-only).

Freigabe 2026-09-11 (Entscheidungsfrage 6, bedingt erteilt). Drei Auflagen:

1. ``scan["box_end_bar"]`` wird auf den **Split 2025-10-01** gesetzt
   (``searchsorted``, BKZ) -- nicht auf das hart verdrahtete 2026-08-19.
2. Der Loader-Name wird **fixiert** (``sys.modules["tmp_kanten_engine_replay"]``),
   damit die gepickelten ``_SEEdgeH``-Instanzen in einem frischen Prozess
   aufloesen (``type(...).__module__`` zeigt auf diesen Namen).
3. S2 wird **ausschliesslich** mit der relativen Logik (Aufloesung ueber
   kausales ``basis_bei(k)``) evaluiert -- **niemals** mit August-Literalen
   (67.6355 / 68.3700 / 69.8700 / 69.9140). B3: die S2-Spanne liegt
   vollstaendig unter allen August-Niveaus.

Arretierung: Engine ``4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a``
bleibt unveraendert; kein Projektdatei-Eingriff.

Ausfuehren:  .venv\\Scripts\\python.exe test/_tmp_s2_scan_pipeline.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import pickle
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
VD_P = ROOT / "test" / "_tmp_vd_vertrag_entwurf.py"
PKL = ROOT / "test" / "_tmp_s2_scan_cache.pkl"
OUT = ROOT / "test" / "_tmp_s2_scan_pipeline_out.txt"
NAME = "tmp_kanten_engine_replay"
SPLIT = np.datetime64("2025-10-01")
AUG_LITERALE = (67.6355, 68.3700, 69.8700, 69.9140)

BUF: List[str] = []


def out(s: str = "") -> None:
    BUF.append(s)


def lade(name: str, pfad: Path):
    """Laedt ein Modul unter FIXIERTEM Namen (Pickle-Aufloesung)."""
    spec = importlib.util.spec_from_file_location(name, pfad)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ENGINE_SHA = hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
eng = lade(NAME, ENGINE_P)
vd = lade("_tmp_vd_vertrag_entwurf", VD_P)
KS, KR, RM, GW = vd.KantenSicht, vd.KantenRolle, vd.RangModus, vd.GegenkantenWahl
KT, SEG, AD = vd.KantenReferenz, vd.SegmentVD, vd.VDAdapterEntwurf

out("=" * 104)
out("S2 (2025-01-01..2025-12-01) -- SCAN / PICKLE / EBENE-2-ROLLENPROBE")
out("=" * 104)
out(f"Engine-SHA   : {ENGINE_SHA}")
out(f"VD-Entwurf   : {hashlib.sha256(VD_P.read_bytes()).hexdigest()}")
out(f"Loader-Name  : {NAME}  (fixiert)")
out("")

# ------------------------------------------------------------------ 1  Scan
t0 = time.time()
cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("S2", cfg)
t_scan = time.time() - t0

n = scan["n"]
d = scan["d"]
ts = d["ts"].to_numpy().astype("datetime64[ns]")
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
raw_box = scan["box_end_bar"]
split_bar = int(np.searchsorted(ts, SPLIT))
scan["box_end_bar"] = split_bar

out("1  SCAN")
out(f"   _se_scan('S2') in {t_scan:.1f} s")
out(f"   n                        = {n}")
out(f"   box_end (hart 2026-08-19) = {raw_box}   (== n -> ausserhalb, B1)")
out(f"   Split 2025-10-01          = Bar {split_bar}  "
    f"({np.datetime64(ts[split_bar], 'm')})")
out(f"   >> scan['box_end_bar']   = {scan['box_end_bar']}")
out(f"   H1 (bars <  {split_bar:>6}) = {split_bar:>6} Bars")
out(f"   H2 (bars >= {split_bar:>6}) = {n - split_bar:>6} Bars")
out(f"   edges={len(scan['edges'])} seeds={len(scan['seeds'])}")
alle = list(scan["edges"]) + list(scan["seeds"])
kids = sorted(e.kid for e in alle)
out(f"   kid-Bereich              = {kids[0]}..{kids[-1]}  "
    f"({len(kids)} Kanten, fensterlokal -> B4)")
out(f"   Preisspanne S2           = {lo.min():.4f} .. {hi.max():.4f}  "
    f"(mean close {cl.mean():.4f})")
out(f"   August-Literale {AUG_LITERALE}")
out(f"   >> alle Literale oberhalb des S2-Maximums? "
    f"{all(x > hi.max() for x in AUG_LITERALE)}  (B3)")
out("")

# ------------------------------------------------------------- 2  Pickle
blob = pickle.dumps(scan, protocol=pickle.HIGHEST_PROTOCOL)
PKL.write_bytes(blob)
out("2  PICKLE")
out(f"   Datei  : {PKL.name}")
out(f"   Bytes  : {len(blob)}")
out(f"   SHA256 : {hashlib.sha256(blob).hexdigest()}")
out(f"   Klasse : {type(alle[0]).__module__}.{type(alle[0]).__name__}")
out("")

# --- Frisch-Prozess-Simulation: Modul neu laden (fixierter Name), dann laden.
del sys.modules[NAME]
eng2 = lade(NAME, ENGINE_P)
with PKL.open("rb") as fh:
    scan_r = pickle.load(fh)

gleiche_keys = sorted(scan.keys()) == sorted(scan_r.keys())
out("3  ROUNDTRIP")
out(f"   Keys identisch           : {gleiche_keys}")
out(f"   box_end_bar (reload)     : {scan_r['box_end_bar']}  "
    f"(erwartet {split_bar})")
out(f"   n (reload)               : {scan_r['n']}")
out(f"   Kanten (reload)          : {len(scan_r['edges'])} edges + "
    f"{len(scan_r['seeds'])} seeds")
out("")

# Bounded Fidelity-Lauf (box_end_bar=3000) -- voller S2-Lauf waere unnoetig lang.
_bx = 3000
s_a = copy.deepcopy(scan)
s_a["box_end_bar"] = _bx
s_b = copy.deepcopy(scan_r)
s_b["box_end_bar"] = _bx
t0 = time.time()
setups_a, stats_a = eng2._se_trades(s_a, cfg)
setups_b, stats_b = eng2._se_trades(s_b, cfg)
t_tr = time.time() - t0
ka = [(t.bar, t.kid, round(t.r, 9)) for t in setups_a]
kb = [(t.bar, t.kid, round(t.r, 9)) for t in setups_b]
out(f"   Fidelity-Lauf box_end= {_bx} in {t_tr:.1f} s")
out(f"   Trades/Summe (Original)  : {len(setups_a)} / "
    f"{sum(t.r for t in setups_a):+.6f}")
out(f"   Trades/Summe (reload)    : {len(setups_b)} / "
    f"{sum(t.r for t in setups_b):+.6f}")
out(f"   bit-identisch            : {ka == kb and stats_a == stats_b}")
out("")

# ------------------------------------------- 4  Ebene-2-Rollenprobe (relativ)
out("4  EBENE-2-ROLLENPROBE im H2-Fenster (relativ, KEIN August-Literal)")
out("   Rollen werden je Bar kausal aus dem Scan aufgeloest:")
out("   decke = AUSSEN_OBEN (Rang 0), boden = AUSSEN_UNTEN (Rang 0);")
out("   Gegenkante = PHASE_EIGEN; Innenrang = RangModus.NAEHE.")
out("")

t0 = time.time()
zaehler: Dict[str, int] = {"bars": 0, "kein_pool": 0,
                           "aussen_oben": 0, "aussen_unten": 0,
                           "phase_eigen_kurz": 0, "phase_eigen_lang": 0,
                           "ereignis": 0}
ereignis_kids: Dict[int, int] = {}
rollen_beispiel: List[str] = []
for k in range(split_bar, n, 3):                 # Stride 3 (Kostenbindung)
    sichten = [KS(e.kid, e.seite, e.basis_bei(k), e.erster_pivot_bar)
               for e in alle]
    zaehler["bars"] += 1
    if not AD.filtere_kausal(sichten, k):
        zaehler["kein_pool"] += 1
        continue
    seg = SEG(phasen_id="P_DYN",
              decke=KT(kind="rolle", rolle=KR.AUSSEN_OBEN),
              boden=KT(kind="rolle", rolle=KR.AUSSEN_UNTEN))
    ad = AD(start_scope_bar=split_bar, segmente=(seg,))
    d_o = ad.aufloese_rolle_kausal(KR.AUSSEN_OBEN, sichten, k, float(hi[k]))
    d_u = ad.aufloese_rolle_kausal(KR.AUSSEN_UNTEN, sichten, k, float(lo[k]))
    if d_o is None:
        continue
    zaehler["aussen_oben"] += 1
    if d_u is None:
        continue
    zaehler["aussen_unten"] += 1
    g_s = ad.gegenkante_basis(seg, "SHORT", sichten, k, float(hi[k]))
    g_l = ad.gegenkante_basis(seg, "LONG", sichten, k, float(lo[k]))
    if g_s is not None:
        zaehler["phase_eigen_kurz"] += 1
    if g_l is not None:
        zaehler["phase_eigen_lang"] += 1
    ev = AD.aufloese_reclaim_at_opening(
        k, {"high": hi, "low": lo, "close": cl}, sichten)
    if ev is not None:
        zaehler["ereignis"] += 1
        ereignis_kids[ev[0]] = ereignis_kids.get(ev[0], 0) + 1
        if len(rollen_beispiel) < 8:
            rollen_beispiel.append(
                f"bar {k:>6} ({np.datetime64(ts[k], 'm')}) "
                f"K{ev[0]} {ev[2]} basis={ev[1]:.4f} "
                f"({ev[3]}) decke={d_o[0]} boden={d_u[0]} "
                f"ziel_short={g_s if g_s is None else round(g_s, 4)}")
t_probe = time.time() - t0
out(f"   geprueft (Stride 3)      : {zaehler['bars']} Bars in {t_probe:.1f} s"
    f"  (H2 gesamt {n - split_bar})")
out(f"   leerer kausaler Pool     : {zaehler['kein_pool']}")
out(f"   AUSSEN_OBEN aufloesbar   : {zaehler['aussen_oben']}")
out(f"   AUSSEN_UNTEN aufloesbar  : {zaehler['aussen_unten']}")
out(f"   PHASE_EIGEN SHORT/LONG   : {zaehler['phase_eigen_kurz']} / "
    f"{zaehler['phase_eigen_lang']}")
out(f"   RECLAIM_AT_OPENING       : {zaehler['ereignis']}  "
    f"(Kids {dict(sorted(ereignis_kids.items()))})")
out("")
for z in rollen_beispiel:
    out("      " + z)
out("")
out("   >> Alle Groessen sind AUGUST-FREI (reine Scan-/Marktwerte).")
out("")

out("=" * 104)
out("Engine-SHA nach Lauf: " + hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
    + ("  UNVERAENDERT" if hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
       == ENGINE_SHA else "  DRIFT"))
out("=" * 104)

rep = "\n".join(BUF)
OUT.write_text(rep, encoding="utf-8")
print(rep)
