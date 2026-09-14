# -*- coding: utf-8 -*-
"""PHASE 3.0 (read-only) -- Symmetrie-Vorprobe M6 <-> Hook-1.

Zweck: die Bandbreiten-Schere quantifizieren, BEVOR ein V-D-Entwurf
formuliert wird. Keine Engine-Aenderung, kein Adapter-Eingriff.

Ausfuehren:  .venv\\Scripts\\python.exe test/_tmp_explo_v018_phase3a.py
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
spec = importlib.util.spec_from_file_location("_e3a", ENGINE_P)
eng = importlib.util.module_from_spec(spec)          # type: ignore[arg-type]
sys.modules["_e3a"] = eng
spec.loader.exec_module(eng)                          # type: ignore[union-attr]

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V015, Hook2ZielModus, PhasenKanteInfo, PhasenRegimeAdapter,
    PhasenSegmentEintrag,
)

BUF = []
def out(s: str = "") -> None:
    BUF.append(s)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
BOX = scan["box_end_bar"]
scan["box_end_bar"] = scan["n"]
n = scan["n"]
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
op = d["open"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
ts = d["ts"].to_numpy()
alle = list(scan["edges"]) + list(scan["seeds"])
by_kid = {e.kid: e for e in alle}

P9 = ADAPTER_V015.segmente[0]
P10 = PhasenSegmentEintrag(
    phasen_id="P10_HYP", start_bar=1021, end_bar=n - 1,
    decke=PhasenKanteInfo(kid=67, provenienz_basis=69.9140),
    boden=PhasenKanteInfo(kid=82, provenienz_basis=67.6355),
    ziel_preis_short=67.6355, ziel_preis_long=69.9140)
AD = PhasenRegimeAdapter(start_scope_bar=848, segmente=(P9, P10))

TOL_LO = cfg.touch_band_pct / 100.0          # 0.0012
TOL_HI = cfg.max_seed_distanz_pct / 100.0    # 0.0075

out("=" * 104)
out("PHASE 3.0 / SYMMETRIE-VORPROBE M6 <-> HOOK-1  (read-only, Generation V018/BKZ)")
out("=" * 104)
out(f"n={n} | Kalendergrenze (H1/H2-Split)={BOX} | Fenster 848..{n - 1}")
out(f"touch_band_pct={cfg.touch_band_pct} %  |  max_seed_distanz_pct={cfg.max_seed_distanz_pct} %"
    f"  |  max_sweep_ueberdehnung_pct={cfg.max_sweep_ueberdehnung_pct} %"
    f"  |  wall_live_bars={cfg.wall_live_bars}")
out("")
out("-- Metrik-Vergleich (KEINE 1:1-Symmetrie!) --")
out("   M6   dist = |basis(aussen) - basis(kd)| / basis(kd) * 100   [Kante <-> Kante]"
    f"   Schwelle {cfg.max_seed_distanz_pct} %")
out("   Hook1 diff = |sweep_px - basis(seite_kid)| / basis(seite_kid) * 100   "
    f"[Docht <-> Kante]   Schwelle {cfg.touch_band_pct} %")
out("")

# ---------------------------------------------------------------- Kennzahlen
def lebt(e, k: int) -> bool:
    bars = [b for b, _ in e.wicks if b <= k]
    return bool(bars) and max(bars) >= k - cfg.wall_live_bars


M6_BARS = (1122, 1123, 1272)
out("-- Die DREI M6-Sperr-Bars in P10_HYP (K67 als Sperr-Wand) --")
out(f"{'bar':>5} {'sweep_px':>10} {'K67.basis':>10} {'diff%':>8} {'0.12%?':>7} "
    f"{'0.75%?':>7} {'K73.basis':>10} {'M6dist%':>8} {'K67.lebt':>9}")
for k in M6_BARS:
    e67 = by_kid[67]
    b67 = e67.basis_bei(k)
    sweep = float(hi[k])
    diff = abs(sweep - b67) / b67 * 100.0
    e73 = by_kid.get(73)
    b73 = e73.basis_bei(k) if e73 else float("nan")
    m6 = abs(b67 - b73) / b73 * 100.0
    out(f"{k:>5} {sweep:>10.4f} {b67:>10.4f} {diff:>8.4f} "
        f"{str(diff <= cfg.touch_band_pct):>7} "
        f"{str(diff <= cfg.max_seed_distanz_pct):>7} "
        f"{b73:>10.4f} {m6:>8.4f} {str(lebt(e67, k)):>9}")
out("")

# ------------------------------------------------- Weite der Bandaufweitung
out("-- Weite des Hebels: Bars mit K67-DOCHT-DEFIZIT im Band --")
out("   (deficit = hi[k] < K67.basis_bei(k), nur SHORT; dormante UND lebende K67)")
out(f"{'Band':>18} {'Bars 848..1287':>14} {'davon dormant':>14} "
    f"{'Bars 1021..1287':>16} {'davon dormant':>14}")
for label, tol in (("0.12 % (IST)", TOL_LO), ("0.75 % (M6)", TOL_HI)):
    ges = dor = ges2 = dor2 = 0
    for k in range(848, n):
        e67 = by_kid[67]
        if not e67.ist_aktiv_bei(k) or k < e67.erster_pivot_bar + 1:
            continue
        b67 = e67.basis_bei(k)
        if b67 <= 0.0:
            continue
        if float(hi[k]) >= b67:
            continue
        if abs(float(hi[k]) - b67) / b67 > tol:
            continue
        ges += 1
        dor += 0 if lebt(e67, k) else 1
        if k >= 1021:
            ges2 += 1
            dor2 += 0 if lebt(e67, k) else 1
    out(f"{label:>18} {ges:>14} {dor:>14} {ges2:>16} {dor2:>14}")
out("")

# ------------------------------------------- H1-Strukturimmunitaet (Beweis)
out("-- H1-Strukturimmunitaet der Adapter-seitigen Aufweitung --")
h1_bars = [t for t in (848,) if t < 848]
out(f"   hook_1_freigabe_kid: erste Zeile = aktive_phase_bei(bar_idx); "
    f"start_scope_bar={AD.start_scope_bar}")
out(f"   Fuer bar_idx < {AD.start_scope_bar} -> seg is None -> return None "
    f"(keine Freigabe moeglich).")
out(f"   H1 = entry_bar < {BOX}  =>  Signal-Bar k <= {BOX - 1} < {AD.start_scope_bar}"
    f"  =>  H1 strukturell unberuehrbar.")
out(f"   (Gegenprobe Phase 2: punktuelle _FORCE-Freigabe liess H1 bei "
    f"8/+38.919584 R.)")
out("")

# ------------------------------------------------ Restrisiko: andere Blocker
out("-- Restrisiko: M6-Blocker != seite_kid (Bandaufweitung wirkungslos) --")
out("   M6 bestimmt die AEUSSERSTE nicht erreichte Linie, nicht die Segmentkante.")
out("   Die Aufweitung greift nur, wenn der M6-Blocker == seite_kid ist")
out("   (in P10_HYP: K67). Andernfalls bleibt die Sperre bestehen.")
out("")
for k in (1122, 1272):
    e67, e73 = by_kid[67], by_kid[73]
    out(f"   bar {k}: seite_kid=K67 | Blocker=K67 | "
        f"aussen(OBEN, nicht erreicht) K67 {e67.basis_bei(k):.4f} "
        f"(erreicht? {float(hi[k]) >= e67.basis_bei(k)})")
out("")

# ------------------------------------------------------- Abwaertsstrecke
out("-- Harte Randbedingung 'Abwaertsstrecke 1023..1031 bleibt gesperrt' --")
out(f"{'bar':>5} {'O':>9} {'H':>9} {'L':>9} {'C':>9} | LONG-Kandidat-Kontext")
e82 = by_kid[82]
for k in range(1023, 1032):
    b82 = e82.basis_bei(k)
    dist = (float(lo[k]) - b82) / b82 * 100.0
    inband = 0.0 < dist <= cfg.max_seed_distanz_pct
    out(f"{k:>5} {op[k]:>9.4f} {hi[k]:>9.4f} {lo[k]:>9.4f} {cl[k]:>9.4f} | "
        f"K82@L {b82:.4f} dist {dist:+.4f} % | deficit(L>K82)="
        f"{str(float(lo[k]) > b82):<5} 0.75-Band={inband}")
out("")
out("   Befund Phase 2: alle drei Bars wurden von Q29 (25 %-Quartil) gestoppt;")
out("   Q29 liegt HINTER M6 und bleibt von einer K67-Aufweitung unberuehrt.")
out("")

out("-- SHA-Kontrolle --")
import hashlib  # noqa: E402
out(f"   Engine {hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()}")
out("")
out("ENDE PHASE 3.0")

rep = "\n".join(BUF)
(ROOT / "test" / "_tmp_explo_v018_phase3a_out.txt").write_text(
    rep, encoding="utf-8")
print(rep)
