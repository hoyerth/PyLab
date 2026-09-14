# -*- coding: utf-8 -*-
"""PHASE 1 (read-only) -- H2-Marktanalyse 1021..1287 auf BKZ / Generation V018.

Stufen 1.1 (Kanten-Status-Matrix), 1.2 (Pivot-Chronologie Monatstief),
1.3 (Gate-Barriere-Protokoll). Reine Diagnose: die Engine-Datei wird NICHT
veraendert; Instrumentierung erfolgt ausschliesslich im RAM (exec eines
Quelltext-Klons), exakt wie der Renderer-RAM-Patch.

Zeitbasis: BKZ = ``time AT TIME ZONE 'UTC'`` (docs/ZEITBASIS_KANON.md).
Kalendergrenzen dynamisch (searchsorted), kein Bar-Literal.

Ausfuehren:  .venv\\Scripts\\python.exe test/_tmp_explo_v018_phase1.py
Ausgabe:     test/_tmp_explo_v018_phase1_out.txt
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
    spec = importlib.util.spec_from_file_location("_v018_engine", ENGINE_P)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["_v018_engine"] = mod          # Pflicht fuer @dataclass
    spec.loader.exec_module(mod)               # type: ignore[union-attr]
    return mod


eng = load_engine()
from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V015, DEFAULT_ADAPTER, Hook2ZielModus, PhasenRegimeAdapter,
)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
op = d["open"].to_numpy(dtype=float)
ts = d["ts"].to_numpy()
n = scan["n"]
# WICHTIG: Der Renderer ueberschreibt ``scan["box_end_bar"] = n`` (Voll-Lauf,
# tmp_png_aug_sichttest.py Z. 507) und teilt H1/H2 erst NACH dem Lauf ueber die
# Kalendergrenze. Die 644 ist also NUR Split-Grenze, nicht Laufgrenze.
box_end = scan["box_end_bar"]          # Kalendergrenze (644) -> H1/H2-Split
scan["box_end_bar"] = n                # Renderer-Voll-Lauf (Z. 507)
alle = list(scan["edges"]) + list(scan["seeds"])
by_kid = {e.kid: e for e in alle}
seite_edges: Dict[str, List] = {
    "OBEN": [e for e in alle if e.seite == "OBEN"],
    "UNTEN": [e for e in alle if e.seite == "UNTEN"],
}

ENGINE_SHA = hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
adapter: PhasenRegimeAdapter = ADAPTER_V015
K0, K1 = 1021, n - 1                       # 1021..1287
FOKUS = [67, 73, 76, 77, 82, 85]

# ------------------------------------------------------------------ Helpers
def exists(e, k: int) -> bool:
    """1:1-Transkription ``_se_trades::_existiert`` (Engine Z. 2401-2411)."""
    if not e.ist_aktiv_bei(k):
        return False
    return e.erster_pivot_bar + 2 <= k + 1


def lebt(e, k: int) -> bool:
    """1:1-Transkription ``_se_trades::_lebt`` (Engine Z. 2413-2424)."""
    bars = [b for b, _ in e.wicks if b <= k]
    return bool(bars) and max(bars) >= k - cfg.wall_live_bars


def etabliert(e, k: int) -> bool:
    return k - e.erster_pivot_bar >= cfg.min_wall_alter_bars


def im_aussenquartil(richtung: str, k: int, sweep_px: float) -> bool:
    """1:1-Transkription ``_im_aussenquartil`` (Engine Z. 2426-2441)."""
    ex_hi = float(np.max(hi[:k + 1]))
    ex_lo = float(np.min(lo[:k + 1]))
    spanne = ex_hi - ex_lo
    if spanne <= 0.0:
        return True
    dist = ((ex_hi - sweep_px) if richtung == "SHORT"
            else (sweep_px - ex_lo)) / spanne * 100.0
    return dist <= cfg.quartil_distanz_pct


def kandidat_diag(richtung: str, k: int, sweep_px: float):
    """1:1-Transkription ``_kandidat`` (Engine Z. 2486-2546) + Grund."""
    seite = "OBEN" if richtung == "SHORT" else "UNTEN"

    def _dist(e) -> float:
        basis = e.basis_bei(k)
        if richtung == "SHORT":
            return (sweep_px - basis) / basis * 100.0
        return (basis - sweep_px) / basis * 100.0

    pool = []
    n_zu_jung = 0
    for e in seite_edges[seite]:
        if not exists(e, k):
            continue
        if not ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                or e.touch_conf(k) >= 2):
            continue
        if not etabliert(e, k):
            n_zu_jung += 1
            continue
        pool.append(e)
    for e in seite_edges[seite]:
        if e in pool or not exists(e, k) or e.ist_prim_anker:
            continue
        if e.touch_conf(k) >= 2 or not etabliert(e, k):
            continue
        dd = _dist(e)
        if cfg.sweep_mindestdurchstich_pct < dd <= cfg.max_sweep_ueberdehnung_pct:
            pool.append(e)
    if not pool:
        return None, f"KEIN_POOL(zu_jung={n_zu_jung})"
    pool.sort(key=lambda e: e.basis_bei(k), reverse=(seite == "OBEN"))
    for pos, e in enumerate(pool):
        dist = _dist(e)
        if dist < 0.0:
            if lebt(e, k):
                return None, f"WAND_LEBT_UNERREICHT(K{e.kid})"
            continue
        if dist > cfg.max_sweep_ueberdehnung_pct:
            return None, "UEBERDEHNUNG"
        if dist <= cfg.sweep_mindestdurchstich_pct:
            continue
        if pos == 0:
            return e, "WAND"
        if e.touch_conf(k) < cfg.min_touches_handelbar:
            continue
        return e, "INNEN"
    return None, "POOL_ERSCHOEPFT"


def m6_diag(richtung: str, k: int, kd, sweep_px: float):
    """1:1-Transkription ``_blockiert_durch_aussenkante`` (Z. 2443-2477)."""
    seite = "OBEN" if richtung == "SHORT" else "UNTEN"
    basis_k = kd.basis_bei(k)
    aussen = None
    for e in seite_edges[seite]:
        if e is kd or not exists(e, k):
            continue
        b = e.basis_bei(k)
        if seite == "OBEN":
            if b <= sweep_px:
                continue
            if aussen is None or b > aussen.basis_bei(k):
                aussen = e
        else:
            if b >= sweep_px:
                continue
            if aussen is None or b < aussen.basis_bei(k):
                aussen = e
    if aussen is None:
        return None
    b = aussen.basis_bei(k)
    dist = ((b - basis_k) if seite == "OBEN" else (basis_k - b)) / basis_k * 100.0
    return aussen if 0.0 < dist <= cfg.max_seed_distanz_pct else None


def pool_dump(richtung: str, k: int, sweep_px: float):
    """Roh-Pool in Iterationsreihenfolge (aussen -> innen) mit Position."""
    seite = "OBEN" if richtung == "SHORT" else "UNTEN"

    def _dist(e) -> float:
        basis = e.basis_bei(k)
        if richtung == "SHORT":
            return (sweep_px - basis) / basis * 100.0
        return (basis - sweep_px) / basis * 100.0

    pool = []
    for e in seite_edges[seite]:
        if not exists(e, k):
            continue
        if not ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                or e.touch_conf(k) >= 2):
            continue
        if not etabliert(e, k):
            continue
        pool.append(e)
    for e in seite_edges[seite]:
        if e in pool or not exists(e, k) or e.ist_prim_anker:
            continue
        if e.touch_conf(k) >= 2 or not etabliert(e, k):
            continue
        dd = _dist(e)
        if cfg.sweep_mindestdurchstich_pct < dd <= cfg.max_sweep_ueberdehnung_pct:
            pool.append(e)
    pool.sort(key=lambda e: e.basis_bei(k), reverse=(seite == "OBEN"))
    return [(pos, e.kid, _dist(e), lebt(e, k)) for pos, e in enumerate(pool)]


def gegenkante(richtung: str, k: int):
    """1:1-Transkription ``_gegenkante`` (Engine Z. 2548-2562)."""
    gegenseite = "UNTEN" if richtung == "SHORT" else "OBEN"
    pool = [e for e in seite_edges[gegenseite]
            if e.erster_pivot_bar + 2 <= k + 1
            and ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                 or e.touch_conf(k) >= 2)]
    if not pool:
        return None
    if gegenseite == "OBEN":
        return max(pool, key=lambda e: e.basis_bei(k))
    return min(pool, key=lambda e: e.basis_bei(k))


def aussen_decke(k: int):
    """Aeusserste EXISTIERENDE OBEN-Linie bei k (bzw. None)."""
    c = [e for e in seite_edges["OBEN"] if exists(e, k)]
    return max(c, key=lambda e: e.basis_bei(k)) if c else None


def aussen_boden(k: int):
    c = [e for e in seite_edges["UNTEN"] if exists(e, k)]
    return min(c, key=lambda e: e.basis_bei(k)) if c else None


# ------------------------------------------------------ RAM-Instrumentierung
_slice_src = (ROOT / "test" / "tmp_png_aug_sichttest.py").read_text(encoding="utf-8")
_slice_lines = _slice_src.splitlines()
# Renderer Z. 541..660: RAM-Patch-Aufbau + ``_lauf`` (bewusst ohne PNG-Teil).
_patch_block = "\n".join(_slice_lines[540:660])
_ns_slice: Dict = {
    "P": ENGINE_P, "ast": __import__("ast"), "copy": copy,
    "Hook2ZielModus": Hook2ZielModus, "_Hook2ZielModus": Hook2ZielModus,
    "engine": eng, "cfg": cfg, "scan": scan,
    "DEFAULT_ADAPTER": DEFAULT_ADAPTER, "ADAPTER_V015": ADAPTER_V015,
    "adapter": ADAPTER_V015,
}
exec(compile(_patch_block, "<renderer_patch_slice>", "exec"), _ns_slice)
_patched_src: str = _ns_slice["patched_src"]

_ANCHORS: List[Tuple[str, str]] = [
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
    ('            if k <= kd.letzter_sweep_bar:\n                stats["f3"] += 1',
     '            if k <= kd.letzter_sweep_bar:\n'
     '                _DIAG.append((k, richtung, "F3"))\n'
     '                stats["f3"] += 1'),
    ('                stats["zyklus_blockiert"] += 1',
     '                _DIAG.append((k, richtung, "ZYKLUS"))\n'
     '                stats["zyklus_blockiert"] += 1'),
    ('            if geg is None:\n                stats["kein_gegner"] += 1',
     '            if geg is None:\n'
     '                _DIAG.append((k, richtung, "KEIN_GEGNER"))\n'
     '                stats["kein_gegner"] += 1'),
]


def inject(src: str) -> str:
    """Fuegt je Barriere einen ``_DIAG``-Eintrag ein (RAM, fail-loud)."""
    out_src = src
    for old, new in _ANCHORS:
        if old == new:
            continue
        assert out_src.count(old) == 1, (old[:50], out_src.count(old))
        out_src = out_src.replace(old, new)
    # Sammel-Marker (mehrfach): Raum-Ablehnungen.
    out_src = out_src.replace(
        'stats["kein_raum"] += 1',
        '_DIAG.append((k, richtung, "RAUM")); stats["kein_raum"] += 1')
    if "_Hook2ZielModus.BLOCKIERT" in out_src:
        # Nach der Sammel-Ersetzung steht in der hook_2-Weiche der RAUM-Marker;
        # der spezifischere HOOK2_BLOCKIERT-Marker wird davorgesetzt.
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
    if "getradete_entry_bars:   # B23-3: Dedup" in out_src:
        old_dd = '            if entry_bar in getradete_entry_bars:   # B23-3: Dedup\n                continue'
        assert out_src.count(old_dd) == 1, out_src.count(old_dd)
        out_src = out_src.replace(
            old_dd,
            '            if entry_bar in getradete_entry_bars:   # B23-3: Dedup\n'
            '                _DIAG.append((k, richtung, "DEDUP"))\n'
            '                continue')
    return out_src


def lauf_diag(mit_patch: bool, hook: PhasenRegimeAdapter):
    """Instrumentierter Lauf; Rueckgabe (setups, stats, diag)."""
    src = inject(_patched_src if mit_patch else _src_orig)
    ns = dict(eng.__dict__)
    ns["_Hook2ZielModus"] = Hook2ZielModus
    ns["_DIAG"] = []
    ns["_hook"] = hook
    exec(compile(src, "<se_trades_diag>", "exec"), ns)
    setups, stats = ns["_se_trades"](copy.deepcopy(scan), cfg)
    return setups, stats, list(ns["_DIAG"])


_src_orig = __import__("ast").get_source_segment(
    ENGINE_P.read_text(encoding="utf-8"),
    next(x for x in __import__("ast").parse(
        ENGINE_P.read_text(encoding="utf-8")).body
        if isinstance(x, __import__("ast").FunctionDef) and x.name == "_se_trades"))

# Engine-eigene Referenzlaeufe (uninstrumentiert) fuer Sollwert-Abgleich.
V0_soll, _ = eng._se_trades(copy.deepcopy(scan), cfg)
ORIG_TRADES = eng._se_trades
V1_soll, st_soll = None, None

# Instrumentierte Laeufe.
V0_list, V0_stats, V0_diag = lauf_diag(False, DEFAULT_ADAPTER)
V1_list, V1_stats, V1_diag = lauf_diag(True, adapter)

# ---------------------------------------------------- Validierung (fail-loud)
assert len(V0_list) == len(V0_soll), (len(V0_list), len(V0_soll))
assert {(t.bar, t.kid) for t in V0_list} == {(t.bar, t.kid) for t in V0_soll}
assert abs(sum(t.r for t in V0_list) - sum(t.r for t in V0_soll)) < 1e-9
assert len(V1_list) == 17, len(V1_list)
assert abs(sum(t.r for t in V1_list) - 65.835576) < 1e-5, sum(t.r for t in V1_list)
h1 = [t for t in V1_list if t.entry_bar < box_end]
h2 = [t for t in V1_list if t.entry_bar >= box_end]
assert (len(h1), round(sum(t.r for t in h1), 6)) == (8, 38.919584)
assert (len(h2), round(sum(t.r for t in h2), 6)) == (9, 26.915992)


def first_gate(diag, k, richtung):
    for (dk, dr, tag) in diag:
        if dk == k and dr == richtung:
            return tag
    return "PASS"           # kein Gate-Eintrag -> Trade genommen oder kein Kandidat? s.u.


# Kreuzvalidierung der 1:1-Transkriptionen gegen den instrumentierten
# Engine-Lauf (nur iterierte Bars: range(2, box_end-1-3)).
_diag_by: Dict[Tuple[int, str], List[str]] = {}
for (_dk, _dr, _tag) in V1_diag:
    _diag_by.setdefault((_dk, _dr), []).append(_tag)
_mm_k = _mm_m6 = _mm_q29 = []
for k in range(K0, n - 3):
    for richtung in ("SHORT", "LONG"):
        sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])
        kd, _why = kandidat_diag(richtung, k, sweep_px)
        tags = _diag_by.get((k, richtung), [])
        eng_none = "KANDIDAT_NONE" in tags
        if (kd is None) != eng_none:
            _mm_k.append((k, richtung, kd is None, eng_none))
        if kd is not None:
            blk = m6_diag(richtung, k, kd, sweep_px)
            eng_m6 = [t for t in tags if t.startswith("M6(")]
            if bool(blk) != bool(eng_m6):
                _mm_m6.append((k, richtung, blk and blk.kid, eng_m6))
            elif blk and eng_m6 and f"K{blk.kid}" not in eng_m6[0]:
                _mm_m6.append((k, richtung, blk.kid, eng_m6))
            eng_q29 = "Q29" in tags
            if (not im_aussenquartil(richtung, k, sweep_px)) != eng_q29:
                _mm_q29.append((k, richtung))
assert not _mm_k, _mm_k[:5]
assert not _mm_m6, _mm_m6[:5]
assert not _mm_q29, _mm_q29[:5]


# ----------------------------------------------------------------- Header
out("=" * 100)
out("PHASE 1 / H2-MARKTANALYSE 1021..1287 -- READ-ONLY, Generation V018 (BKZ)")
out("=" * 100)
out(f"Engine   : {ENGINE_P.name}  SHA256 {ENGINE_SHA}")
out(f"Zeitbasis: BKZ = \"time\" AT TIME ZONE 'UTC' (docs/ZEITBASIS_KANON.md)")
out(f"n={n} | box_end_bar=644 (Kalendergrenze, H1/H2-Split) | "
    f"Renderer-Voll-Lauf: scan['box_end_bar']:=n (Z. 507)")
out(f"Analysefenster: Bars {K0}..{K1} | Lookback ab 848 (Adapter-Scope)")
out(f"Adapter  : ADAPTER_V015 (V018-Modus) | segmente="
    f"{[(s.phasen_id, s.start_bar, s.end_bar) for s in adapter.segmente]}")
out(f"           start_scope_bar={adapter.start_scope_bar} | "
    f"aktive_phase_bei(1021)={adapter.aktive_phase_bei(1021)}")
out(f"cfg      : band={cfg.touch_band_pct}% | V-S>={cfg.min_touches_handelbar} | "
    f"max_sweep={cfg.max_sweep_ueberdehnung_pct}% | Q29={cfg.quartil_distanz_pct}% | "
    f"M6 max_seed_dist={cfg.max_seed_distanz_pct}% | wall_live={cfg.wall_live_bars}")
out(f"Validierung: V0={len(V0_list)} Trades (SOLL {len(V0_soll)}), "
    f"V1_aktiv={len(V1_list)} Trades / {sum(t.r for t in V1_list):+.6f} R "
    f"(SOLL 17 / +65.835576)")
out(f"            H1={len(h1)}/{sum(t.r for t in h1):+.6f} | "
    f"H2={len(h2)}/{sum(t.r for t in h2):+.6f}")
out("")

# =================================================== 1.1 Kanten-Status-Matrix
out("#" * 100)
out("# 1.1 KANTEN-STATUS-MATRIX (Fokus-Sextett + dynamische Aussenkanten)")
out("#" * 100)
out("")
out("-- Kantenkatalog (alle Kanten, die im Analysefenster existieren) --")
out(f"{'kid':>4} {'seite':>5} {'basis':>9} {'touches':>7} {'erster_piv':>10} "
    f"{'geburts':>7} {'anker':>5} {'promov':>7} {'letzter_wick':>12}")
for e in sorted(alle, key=lambda e: (e.seite, e.kid)):
    if not any(exists(e, k) for k in range(K0, K1 + 1)):
        continue
    wb = max((b for b, _ in e.wicks), default=-1)
    out(f"{e.kid:>4} {e.seite:>5} {e.basis:>9.4f} {e.touch_anzahl:>7} "
        f"{e.erster_pivot_bar:>10} {e.geburts_bar:>7} "
        f"{str(e.ist_prim_anker):>5} {e.promoviert_ab_bar:>7} {wb:>12}")
out("")
out("-- Fokus-Sextett: Statuswechsel-Timeline (nur Aenderungen) --")
out(f"{'bar':>5} {'kid':>4} {'exists':>6} {'lebt':>5} {'aktiv':>5} {'t_conf':>6} "
    f"{'basis_bei':>9} {'letzter_piv':>11}")
for kid in FOKUS:
    e = by_kid.get(kid)
    if e is None:
        out(f"  K{kid}: NICHT VORHANDEN im Scan-Katalog")
        continue
    prev = None
    for k in range(K0, K1 + 1):
        cur = (exists(e, k), lebt(e, k), e.ist_aktiv_bei(k),
               e.touch_conf(k), round(e.basis_bei(k), 4),
               e.letzter_touch_conf(k))
        if cur != prev:
            out(f"{k:>5} {kid:>4} {str(cur[0]):>6} {str(cur[1]):>5} "
                f"{str(cur[2]):>5} {cur[3]:>6} {cur[4]:>9.4f} {cur[5]:>11}")
            prev = cur
out("")
out("-- Dynamische Aussenkanten (existierende OBEN-Decke / UNTEN-Boden) --")
out("   (nur Wechsel; 'erreicht' = Docht-Extremum von k beruehrt/ueberschreitet)")
out(f"{'bar':>5} {'decke_kid':>9} {'decke':>9} {'decke_lebt':>10} "
    f"{'boden_kid':>9} {'boden':>9} {'boden_lebt':>10}")
prev = None
for k in range(K0, K1 + 1):
    dc = aussen_decke(k)
    bd = aussen_boden(k)
    cur = (dc.kid if dc else None, round(dc.basis_bei(k), 4) if dc else None,
           lebt(dc, k) if dc else None,
           bd.kid if bd else None, round(bd.basis_bei(k), 4) if bd else None,
           lebt(bd, k) if bd else None)
    if cur != prev:
        out(f"{k:>5} {str(cur[0]):>9} "
            f"{(f'{cur[1]:.4f}' if cur[1] is not None else '-'):>9} "
            f"{str(cur[2]):>10} {str(cur[3]):>9} "
            f"{(f'{cur[4]:.4f}' if cur[4] is not None else '-'):>9} "
            f"{str(cur[5]):>10}")
        prev = cur
out("")

# ==================================================== 1.2 Pivot-Chronologie
out("#" * 100)
out("# 1.2 PIVOT-CHRONOLOGIE & 2-BAR-BESTAETIGUNG (Monatstief-Bereich)")
out("#" * 100)
out("")
lo_min = float(np.min(lo[K0:K1 + 1]))
lo_arg = int(K0 + np.argmin(lo[K0:K1 + 1]))
hi_max = float(np.max(hi[K0:K1 + 1]))
hi_arg = int(K0 + np.argmax(hi[K0:K1 + 1]))
out(f"Fenster-Extrema: Tief {lo_min:.4f} @ Bar {lo_arg} | "
    f"Hoch {hi_max:.4f} @ Bar {hi_arg}")
out(f"Bestaetigungslauf: L-Pivot an Bar m wird erst bei m+2 wirksam "
    f"(mbar=k-2; _pivot_dual prueft +-2).")
out("")
out("-- Pivots (mbar) im Bereich 1040..1140 mit Wick-Aufnahme --")
out(f"{'mbar':>5} {'typ':>3} {'preis':>9} {'bestaetigt_ab_bar':>17} "
    f"{'aufgenommen_von':>20} {'dist_%':>8}")
for mbar in range(1040, 1141):
    if mbar < 2 or mbar + 2 >= n:
        continue
    for typ in eng._pivot_dual(hi, lo, mbar):
        px = float(hi[mbar]) if typ == "H" else float(lo[mbar])
        seite = "OBEN" if typ == "H" else "UNTEN"
        treffer = None
        for e in alle:
            if e.seite != seite:
                continue
            for (b, p) in e.wicks:
                if b == mbar and abs(p - px) < 1e-9:
                    treffer = e
        if treffer is None:
            out(f"{mbar:>5} {typ:>3} {px:>9.4f} {mbar + 2:>17} "
                f"{'<neu/Sweep-Sperre>':>20} {'-':>8}")
            continue
        dist = abs(px - treffer.basis) / treffer.basis * 100.0
        out(f"{mbar:>5} {typ:>3} {px:>9.4f} {mbar + 2:>17} "
            f"{('K' + str(treffer.kid)):>20} {dist:>8.4f}")
out("")
out("-- Extremum 1075 im Detail --")
out(f"lo[{lo_arg}]={lo[lo_arg]:.4f} hi[{lo_arg}]={hi[lo_arg]:.4f} "
    f"cl[{lo_arg}]={cl[lo_arg]:.4f} ts={np.datetime64(ts[lo_arg], 'm')}")
out(f"Pivots @ {lo_arg}: {eng._pivot_dual(hi, lo, lo_arg)}")
for e in sorted(alle, key=lambda e: e.kid):
    w = [b for b, _ in e.wicks if abs(b - lo_arg) <= 5]
    if w:
        out(f"   K{e.kid:<3} seite={e.seite:<5} basis={e.basis:.4f} "
            f"touches={e.touch_anzahl} erster_pivot={e.erster_pivot_bar} "
            f"anker={e.ist_prim_anker} wicks@+-5={w}")
out("")

# ================================================== 1.3 Gate-Barriere-Protokoll
out("#" * 100)
out("# 1.3 GATE-BARRIERE-PROTOKOLL 1021..1287 (kausale Kaskade je Bar x Richtung)")
out("#" * 100)
out("")
out("Reihenfolge der Gates (Engine-Z. 2564 ff.):")
out("  KANDIDAT_NONE -> M6(aussenkante) -> Q29(Quartil) -> STUFE0 -> F3 -> "
    "ZYKLUS -> KEIN_GEGNER -> HOOK2_BLOCKIERT/RAUM -> DEDUP -> TRADE")
out("")

zeilen = []
for k in range(K0, K1 + 1):
    for richtung in ("SHORT", "LONG"):
        sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])
        kd, why = kandidat_diag(richtung, k, sweep_px)
        tag = first_gate(V1_diag, k, richtung)
        zeilen.append((k, richtung, kd, why, tag, sweep_px))

from collections import Counter
cnt = Counter(z[4] for z in zeilen)
out("-- Barriere-Histogramm (erstes schlagendes Gate, V1_aktiv/ADAPTER_V015) --")
out(f"   (534 = 267 Bars x 2 Richtungen; Engine-Laufgrenze: "
    f"range(2, box_end-3) -> Bars {K1 - 2}..{K1} werden NICHT iteriert)")
for tag, c in cnt.most_common():
    out(f"   {tag:>28}: {c:>4}")
out("")
out("-- KANDIDAT_NONE: Grund-Histogramm (alle 267 Bars x 2 Richtungen; "
    "inkl. der 6 nicht iterierten Bars) --")
rc = Counter(z[3] for z in zeilen if z[2] is None)
for why, c in rc.most_common():
    out(f"   {why:>28}: {c:>4}")
out("")
out("-- WAND_LEBT_UNERREICHT: blockierende lebende Aussenwand je Kante --")
wb = Counter(z[3] for z in zeilen if z[3].startswith("WAND_LEBT"))
for why, c in wb.most_common():
    out(f"   {why:>28}: {c:>4}")
out("")

out("-- Alle Bars mit EXISTIERENDEM Kandidaten (Kaskade laeuft weiter) --")
out(f"{'bar':>5} {'richtung':>6} {'kd':>5} {'warum':>24} {'dist_%':>8} "
    f"{'M6':>6} {'Q29':>4} {'stufe':>6} {'erstes_gate':>28} {'sweep':>9}")
for (k, richtung, kd, why, tag, sweep_px) in zeilen:
    if kd is None:
        continue
    basis = kd.basis_bei(k)
    dist = ((sweep_px - basis) if richtung == "SHORT"
            else (basis - sweep_px)) / basis * 100.0
    blk = m6_diag(richtung, k, kd, sweep_px)
    q29 = im_aussenquartil(richtung, k, sweep_px)
    seite = "OBEN" if richtung == "SHORT" else "UNTEN"
    stufe, _nm = eng._reclaim_stufe(seite, k, basis, hi, lo, cl, cfg)
    out(f"{k:>5} {richtung:>6} {'K' + str(kd.kid):>5} {why:>24} {dist:>8.4f} "
        f"{(f'K{blk.kid}' if blk else '-'):>6} {str(q29):>4} {stufe:>6} "
        f"{tag:>28} {sweep_px:>9.4f}")
out("")

out("-- Kandidaten-Katalog: welche Kante stellt wann die aeusserste Wand? --")
per_kd: Dict[int, List[str]] = {}
for (k, richtung, kd, why, tag, sweep_px) in zeilen:
    if kd is None:
        continue
    per_kd.setdefault(kd.kid, []).append(
        f"{k}/{richtung[0]}:{tag.split('(')[0]}")
for kid in sorted(per_kd):
    vals = per_kd[kid]
    out(f"   K{kid}: {len(vals)} Bars -> " + ", ".join(vals[:40])
        + (" ..." if len(vals) > 40 else ""))
out("")

out("-- PRUEFSTEINE (avisiert) im Detail --")
for (pbar, pri, pname) in [(1122, "SHORT", "K73 Short 1122"),
                           (1072, "LONG", "K82 Long 1072"),
                           (1172, "LONG", "K82 Long 1172"),
                           (1259, "LONG", "K82 Long 1259")]:
    out(f"   [{pname}] bar={pbar} {pri}  ts={np.datetime64(ts[pbar], 'm')} "
        f"O={op[pbar]:.4f} H={hi[pbar]:.4f} L={lo[pbar]:.4f} C={cl[pbar]:.4f}")
    # Kaskade im Detail
    sweep_px = float(hi[pbar]) if pri == "SHORT" else float(lo[pbar])
    kd, why = kandidat_diag(pri, pbar, sweep_px)
    out(f"     sweep_px={sweep_px:.4f} | _kandidat -> "
        f"{(f'K{kd.kid} ({why})' if kd else why)}")
    if kd is not None:
        blk = m6_diag(pri, pbar, kd, sweep_px)
        out(f"     M6 -> {(f'BLOCKER K{blk.kid} {blk.basis_bei(pbar):.4f}' if blk else 'frei')}")
        out(f"     Q29 -> {im_aussenquartil(pri, pbar, sweep_px)} "
            f"(Quartil-Grenze {cfg.quartil_distanz_pct}%)")
        seite = "OBEN" if pri == "SHORT" else "UNTEN"
        st, nm = eng._reclaim_stufe(seite, pbar, kd.basis_bei(pbar), hi, lo, cl, cfg)
        out(f"     _reclaim_stufe -> {st} ({nm})")
        geg = gegenkante(pri, pbar)
        out(f"     _gegenkante -> {(f'K{geg.kid} {geg.basis_bei(pbar):.4f}' if geg else None)}")
    h2z = adapter.hook_2_ziel(pbar, pri)
    out(f"     hook_2_ziel -> {h2z.modus.name} "
        f"({'vacuum: kein Segment deckt den Bar' if h2z.modus is Hook2ZielModus.BLOCKIERT else h2z.ziel_preis})")
    out(f"     erstes_gate (instrumentiert) -> {first_gate(V1_diag, pbar, pri)}")
    out("     Roh-Pool (aussen->innen; pos | kid | dist_% | lebt) -- "
        "'pos' zaehlt AUCH dormante Linien:")
    for (pos, kid, dist, lb) in pool_dump(pri, pbar, sweep_px):
        mark = "  <-- Kandidat" if (kd is not None and kid == kd.kid) else ""
        out(f"        pos {pos:>2} | K{kid:<3} | {dist:>+8.4f} | "
            f"lebt={str(lb):<5}{mark}")
    # Gate-Kette der Aussenkanten
    dc = aussen_decke(pbar); bd = aussen_boden(pbar)
    out(f"     Aussen: Decke K{dc.kid} {dc.basis_bei(pbar):.4f} "
        f"(lebt={lebt(dc, pbar)}) | Boden K{bd.kid} {bd.basis_bei(pbar):.4f} "
        f"(lebt={lebt(bd, pbar)})")
    for kid in FOKUS:
        e = by_kid.get(kid)
        if e is None:
            out(f"     K{kid}: nicht vorhanden")
            continue
        out(f"     K{kid:<3} exists={str(exists(e, pbar)):<5} lebt={str(lebt(e, pbar)):<5} "
            f"aktiv={str(e.ist_aktiv_bei(pbar)):<5} V-S={e.touch_conf(pbar)} "
            f"basis_bei={e.basis_bei(pbar):.4f} erster_pivot={e.erster_pivot_bar}")
    out("")

out("-- Trades im Analysefenster (V0 / ungepatcht) --")
for t in V0_list:
    if t.bar >= K0:
        out(f"   bar {t.bar} entry {t.entry_bar} {t.richtung} K{t.kid} "
            f"R {t.r:+.6f}")
out("-- Trades im Analysefenster (V1_aktiv / ADAPTER_V015) --")
for t in V1_list:
    if t.bar >= K0:
        out(f"   bar {t.bar} entry {t.entry_bar} {t.richtung} K{t.kid} "
            f"R {t.r:+.6f}")
out("")
out("-- V1_aktiv: alle 17 Trades (Kontext) --")
for t in sorted(V1_list, key=lambda t: t.bar):
    out(f"   bar {t.bar:>4} entry {t.entry_bar:>4} {'H1' if t.entry_bar < box_end else 'H2'} "
        f"{t.richtung:<5} K{t.kid:<3} R {t.r:+.6f} {t.stufe}")
out("")
out("-- Gate-Barrieren V1_aktiv (vollstaendige Rohliste, Bars >= 1021) --")
for (dk, dr, tag) in V1_diag:
    if dk >= K0:
        out(f"   bar {dk:>4} {dr:<5} {tag}")
out("")
out("ENDE PHASE 1")

report = "\n".join(BUF)
(ROOT / "test" / "_tmp_explo_v018_phase1_out.txt").write_text(
    report, encoding="utf-8")
print(report)
