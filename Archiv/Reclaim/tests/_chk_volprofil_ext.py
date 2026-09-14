# -*- coding: utf-8 -*-
"""READ-ONLY Aktivitaets-Profil-Analyse  A/B/C/D  (Ausreisser vs. echte Expansion).

Vollstaendige Volumen-/Aktivitaets-Achse, die in der Bisher-Untersuchung fehlte:

  T0  Event-Anker dynamisch (Wand = min lebende UNTEN-Kante vor dem Bruch,
      Bruch-Bar, Leg-Tief)  -- edges-only.
  T1  Binned-Profil (Engine-Logik: range-ueberlapp-gewichtet, t<=k):
      POC, VA70, Konzentration, Bin-Aufloesung 30/60/120, Lookback 96/192/384/768.
  T2  Wand-Aktivitaet: ist der gebrochene Preis ein HVN oder LVN?
      (Bin-Volumen am Wandpreis / Max-Bin, Rang).
  T3  POC-Drift kausal (Bar fuer Bar) -- Balance-Migration vs. Trend.
  T4  Delta-Proxy = tick_volume * (2*(close-low)/(high-low) - 1)  (Kauf-/Verkaufsdruck-Proxy)
  T5  Volumen-Migration: VWAP des Profils und VA-Verschiebung.
  T6  Synthese + Falsifikations-Statement.

Hinweis Datenvertrag: real_volume ist ueber alle Zeilen 0 => kein echtes
Handelsvolumen. tick_volume = Tick-Aktivitaet; Gleichverteilung ueber die
Bar-Range (Engine-Konvention). Daher ueberall "Aktivitaet", nicht "Volumen".

Kein Patch. Engine-SHA hart geprueft.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
EP = ROOT / "test" / "tmp_kanten_engine_replay.py"
assert hashlib.sha256(EP.read_bytes()).hexdigest() == \
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"
_s = importlib.util.spec_from_file_location("evp", EP)
engine = importlib.util.module_from_spec(_s)
sys.modules["evp"] = engine
_s.loader.exec_module(engine)  # type: ignore[union-attr]
engine.FENSTER["EXT"] = ("2026-08-03", "2026-09-12")  # type: ignore[index]
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("EXT", cfg)  # type: ignore[arg-type]
n = int(scan["n"]); d = scan["d"]; ts = list(d["ts"])
op = d["open"].to_numpy(float); hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float); cl = d["close"].to_numpy(float)
vo = d["tick_volume"].to_numpy(float)
EDGES = list(scan["edges"])
LIVE = int(cfg.wall_live_bars)


def lebt(e: object, k: int) -> bool:
    b = [bb for bb, _ in e.wicks if bb <= k]  # type: ignore[attr-defined]
    return bool(b) and max(b) >= k - LIVE


def bas(e: object, k: int) -> float:
    return float(e.basis_bei(k))  # type: ignore[attr-defined]


def boden(k: int) -> Optional[float]:
    u = [bas(e, k) for e in EDGES
         if e.seite == "UNTEN" and int(e.geburts_bar) <= k and lebt(e, k)]  # type: ignore[attr-defined]
    return min(u) if u else None


FENSTER = {"A": (836, 864), "B": (1076, 1160), "C": (1780, 1820), "D": (1972, 2088)}

# ---------------------------------------------------------------- T0 Anker
AN: Dict[str, Dict[str, float]] = {}
print("=" * 122)
print("T0  EVENT-ANKER (dynamisch, edges-only)")
print("=" * 122)
print(f"{'Ev':<3} {'Fenster':<12} {'Wand@k0-1':>10} {'Bruch-Bar':>10} {'Bruch-Zeit':<20} "
      f"{'Tief-Bar':>9} {'Tief':>9} {'Exc%':>7} {'Leg-Bars':>8}")
for lab, (k0, k1) in FENSTER.items():
    w = boden(k0 - 1)
    if w is None:
        w = op[k0]
    brk = next((k for k in range(k0, k1 + 1) if lo[k] < w), None)
    kl = int(np.argmin(lo[k0:k1 + 1])) + k0
    kh = k0 + int(np.argmax(hi[k0:k1 + 1]))
    legs = abs(kl - kh)
    AN[lab] = {"k0": k0, "k1": k1, "wall": w, "brk": brk if brk else k0, "kl": kl,
               "kh": kh, "low": lo[kl], "exc": (w - lo[kl]) / w * 100}
    print(f"{lab:<3} {f'{k0}-{k1}':<12} {w:>10.4f} {AN[lab]['brk']:>10} "
          f"{str(ts[int(AN[lab]['brk'])]):<20} {kl:>9} {lo[kl]:>9.4f} "
          f"{(w-lo[kl])/w*100:>7.3f} {legs:>8}")


# ---------------------------------------------------------------- T1 Profil
def profil(k_start: int, k_end: int, bins: int) -> Dict[str, object]:
    """Binned-Aktivitaetsprofil (Engine-Logik: Range-Ueberlapp, keine Glaettung)."""
    pmin = float(lo[k_start:k_end + 1].min())
    pmax = float(hi[k_start:k_end + 1].max())
    if pmax <= pmin:
        return {}
    edges = np.linspace(pmin, pmax, bins + 1)
    vol = np.zeros(bins, dtype=float)
    for k in range(k_start, k_end + 1):
        l_, h_, v_ = lo[k], hi[k], vo[k]
        if h_ <= l_ or v_ <= 0:
            continue
        lb = int(np.clip(np.searchsorted(edges, l_, side="right") - 1, 0, bins - 1))
        hb = int(np.clip(np.searchsorted(edges, h_, side="left") - 1, 0, bins - 1))
        if lb == hb:
            vol[lb] += v_
        else:
            ov = np.array([max(0.0, min(h_, edges[b + 1]) - max(l_, edges[b]))
                           for b in range(lb, hb + 1)])
            tot = float(ov.sum())
            if tot > 0:
                vol[lb:hb + 1] += v_ * ov / tot
    mitte = (edges[:-1] + edges[1:]) / 2.0
    tot_v = float(vol.sum())
    p_idx = int(np.argmax(vol))
    # VA70
    order = np.argsort(vol)[::-1]
    ziel = 0.70 * tot_v
    acc = 0.0
    sel: List[int] = []
    for i in order:
        acc += vol[i]
        sel.append(int(i))
        if acc >= ziel:
            break
    vmin, vmax = float(mitte[min(sel)]), float(mitte[max(sel)])
    # Konzentration
    hhi = float(np.sum((vol / tot_v) ** 2)) if tot_v > 0 else float("nan")
    return {"pmin": pmin, "pmax": pmax, "edges": edges, "mitte": mitte, "vol": vol,
            "tot": tot_v, "poc": float(mitte[p_idx]), "poc_bin": p_idx,
            "va_lo": vmin, "va_hi": vmax, "hhi": hhi,
            "peak_share": float(vol[p_idx] / tot_v) if tot_v > 0 else float("nan"),
            "bins_belegt": int((vol > 0).sum())}


def bin_at(P: Dict[str, object], px: float) -> int:
    return int(np.clip(np.searchsorted(P["edges"], px, side="right") - 1,  # type: ignore[index]
                       0, len(P["vol"]) - 1))  # type: ignore[arg-type]


print("\n" + "=" * 122)
print("T1  BINNED-PROFIL (kausal bis Anker)   |   POC / VA70 / Konzentration")
print("=" * 122)
LOOKBACKS = [96, 192, 384, 768]
for bins in (30, 60, 120):
    print(f"\n--- Bin-Aufloesung {bins} ---")
    print(f"{'Ev':<3} {'Ende':<6} {'LB':>4} {'POC':>9} {'POC-Bin%':>9} {'VA70-lo':>9} "
          f"{'VA70-hi':>9} {'VA-Breite%':>10} {'HHI':>8} {'PeakShare':>9} {'belegt':>7}")
    for lab in FENSTER:
        A = AN[lab]
        for end_name, ke in (("brk", int(A["brk"])), ("low", int(A["kl"]))):
            for lb in LOOKBACKS:
                ks = max(0, ke - lb + 1)
                P = profil(ks, ke, bins)
                if not P:
                    continue
                breite = (P["va_hi"] - P["va_lo"]) / P["va_lo"] * 100  # type: ignore[operator]
                print(f"{lab:<3} {end_name:<6} {lb:>4} {P['poc']:>9.4f} "  # type: ignore[arg-type]
                      f"{(P['poc']-P['pmin'])/(P['pmax']-P['pmin'])*100:>9.1f} "  # type: ignore[operator]
                      f"{P['va_lo']:>9.4f} {P['va_hi']:>9.4f} {breite:>10.3f} "  # type: ignore[arg-type]
                      f"{P['hhi']:>8.4f} {P['peak_share']:>9.4f} {P['bins_belegt']:>7}")  # type: ignore[arg-type]

# ---------------------------------------------------------------- T2 Wand
print("\n" + "=" * 122)
print("T2  WAND-Aktivitaet: HVN oder LVN am gebrochenen Preis?")
print("=" * 122)
print(f"{'Ev':<3} {'LB':>4} {'Bin@Wand':>9} {'WandAkt':>9} {'MaxAkt':>9} {'Wand/Max':>9} "
      f"{'Rang':>5} {'Bins':>5} {'Z-Wert':>8}  Einordnung")
for lab in FENSTER:
    A = AN[lab]
    ke = int(A["brk"])
    for lb in LOOKBACKS:
        P = profil(max(0, ke - lb + 1), ke, 60)
        if not P:
            continue
        bi = bin_at(P, A["wall"])
        v = P["vol"][bi]  # type: ignore[index]
        vmax = float(P["vol"].max())  # type: ignore[union-attr]
        mu = float(P["vol"].mean()); sd = float(P["vol"].std())  # type: ignore[union-attr]
        rang = int((P["vol"] > v).sum()) + 1  # type: ignore[union-attr]
        z = (v - mu) / sd if sd > 0 else float("nan")
        einz = "HVN" if v > mu + sd else ("LVN" if v < mu else "neutral")
        print(f"{lab:<3} {lb:>4} {bi:>9} {v:>9.0f} {vmax:>9.0f} {v/vmax*100:>8.1f}% "
              f"{rang:>5} {len(P['vol']):>5} {z:>8.2f}  {einz}")

# ---------------------------------------------------------------- T3 POC-Drift
print("\n" + "=" * 122)
print("T3  POC-DRIFT kausal (Profil 192 Bars, Fenster [Anchor-192, k], 60 Bins)")
print("=" * 122)
for lab in FENSTER:
    A = AN[lab]
    k0, k1, kl, brk = int(A["k0"]), int(A["k1"]), int(A["kl"]), int(A["brk"])
    step = max(1, (k1 - k0) // 12)
    pts = list(range(k0, k1 + 1, step))
    if kl not in pts:
        pts.append(kl)
    poc_s: List[float] = []
    for k in pts:
        P = profil(max(0, k - 191), k, 60)
        poc_s.append(P["poc"] if P else float("nan"))  # type: ignore[arg-type]
    wand = A["wall"]
    print(f"\n{lab}: Wand={wand:.4f}  Leg {A['kh']}->{kl}  Bruch@{brk}")
    print("   Bar   Zeit                 Close    POC    POC-Wand    POC-Trend")
    prev = None
    for k, p in zip(pts, poc_s):
        if np.isnan(p):
            continue
        tr = "-" if prev is None else ("v" if p < prev else ("^" if p > prev else "="))
        print(f"   {k:>5} {str(ts[k]):<20} {cl[k]:>8.4f} {p:>8.4f} {p-wand:>+9.4f}   {tr}")
        prev = p
    # Netto-Drift
    g = [p for p in poc_s if not np.isnan(p)]
    if len(g) >= 2:
        print(f"   POC-Drift netto: {g[-1]-g[0]:+.4f} pts ({(g[-1]-g[0])/g[0]*100:+.3f}%)  "
              f"min={min(g):.4f} max={max(g):.4f}  Spanne={max(g)-min(g):.4f}")

# ---------------------------------------------------------------- T4 Delta
print("\n" + "=" * 122)
print("T4  DELTA-PROXY  (tick_volume * (2*(close-low)/(high-low) - 1))  kumuliert")
print("=" * 122)
print(f"{'Ev':<3} {'Summe+':>10} {'Summe-':>10} {'Netto':>10} {'Netto/Vol':>10} "
      f"{'Periode-Bars':>12} {'Netto/Bar':>10}  Charakter")
for lab in FENSTER:
    A = AN[lab]
    k0, k1 = int(A["k0"]), int(A["k1"])
    rng = hi[k0:k1 + 1] - lo[k0:k1 + 1]
    pos = np.where(rng > 0, (cl[k0:k1 + 1] - lo[k0:k1 + 1]) / np.where(rng > 0, rng, 1), 0.5)
    dv = vo[k0:k1 + 1] * (2 * pos - 1)
    sp = float(dv[dv > 0].sum()); sn = float(dv[dv < 0].sum())
    net = float(dv.sum()); tv = float(vo[k0:k1 + 1].sum())
    m = k1 - k0 + 1
    char = ("trendig-AB" if net / tv < -0.05 else
            "trendig-AUF" if net / tv > 0.05 else "ausgeglichen/Sweep")
    print(f"{lab:<3} {sp:>10.0f} {sn:>10.0f} {net:>10.0f} {net/tv:>10.4f} {m:>12} "
          f"{net/m:>10.1f}  {char}")

# ---------------------------------------------------------------- T5 Migration
print("\n" + "=" * 122)
print("T5  AKTIVITAETS-MIGRATION: VWAP des 192-Bar-Profils + VA70-Verschiebung")
print("=" * 122)
print(f"{'Ev':<3} {'Phase':<14} {'VWAP':>9} {'VA70-lo':>9} {'VA70-hi':>9} {'VA-Wand':>9}  Lesart")
for lab in FENSTER:
    A = AN[lab]
    for name, k in (("vor Bruch", int(A["brk"]) - 1),
                    ("bei Bruch", int(A["brk"])),
                    ("bei Tief", int(A["kl"])),
                    ("Fensterende", int(A["k1"]))):
        if k < 0:
            continue
        P = profil(max(0, k - 191), k, 60)
        if not P:
            continue
        v = P["vol"]; mt = P["mitte"]
        vwap = float((v * mt).sum() / v.sum())  # type: ignore[union-attr]
        wand = A["wall"]
        lage = ("ueber Wand" if P["va_lo"] > wand else   # type: ignore[operator]
                "unter Wand" if P["va_hi"] < wand else "um Wand")  # type: ignore[operator]
        print(f"{lab:<3} {name:<14} {vwap:>9.4f} {P['va_lo']:>9.4f} {P['va_hi']:>9.4f} "
              f"{P['va_lo']-wand:>+9.4f}  VA70 {lage}")

# ---------------------------------------------------------------- T6 Synthese
print("\n" + "=" * 122)
print("T6  SYNTHESE  A (Referenz) vs B/C/D (Ausreisser-Kandidaten)")
print("=" * 122)


def kenn(lab: str) -> Dict[str, float]:
    A = AN[lab]
    kl, brk = int(A["kl"]), int(A["brk"])
    P_low = profil(max(0, kl - 191), kl, 60)
    P_brk = profil(max(0, brk - 191), brk, 60)
    v = P_low["vol"]; mt = P_low["mitte"]  # type: ignore[index]
    vwap = float((v * mt).sum() / v.sum())  # type: ignore[union-attr]
    bi = bin_at(P_low, A["wall"])
    wand_akt = float(v[bi] / max(v.max(), 1))  # type: ignore[union-attr]
    rng = hi[brk:kl + 1] - lo[brk:kl + 1]
    pos = np.where(rng > 0, (cl[brk:kl + 1] - lo[brk:kl + 1]) / np.where(rng > 0, rng, 1), 0.5)
    dv = vo[brk:kl + 1] * (2 * pos - 1)
    return {
        "exc_pct": A["exc"],
        "leg_bars": abs(kl - int(A["kh"])),
        "poc_brk_rel": (P_brk["poc"] - A["wall"]) / A["wall"] * 100,  # type: ignore[operator]
        "poc_low_rel": (P_low["poc"] - A["wall"]) / A["wall"] * 100,  # type: ignore[operator]
        "va_breite_low_pct": (P_low["va_hi"] - P_low["va_lo"]) / A["wall"] * 100,  # type: ignore[operator]
        "hhi_low": P_low["hhi"],  # type: ignore[dict-item]
        "wand_akt_share": wand_akt,
        "vwap_rel": (vwap - A["wall"]) / A["wall"] * 100,
        "delta_netto_norm": float(dv.sum() / max(vo[brk:kl + 1].sum(), 1)),
    }


print(f"{'Kennzahl':<26} " + " ".join(f"{x:>14}" for x in ["A", "B", "C", "D"]))
K = {lab: kenn(lab) for lab in FENSTER}
for key in ["exc_pct", "leg_bars", "poc_brk_rel", "poc_low_rel", "va_breite_low_pct",
            "hhi_low", "wand_akt_share", "vwap_rel", "delta_netto_norm"]:
    print(f"{key:<26} " + " ".join(f"{K[lab][key]:>14.4f}" for lab in FENSTER))

print("\nFalsifikations-Statement:")
print("  Unterscheiden sich A und B/C/D in KEINER der obigen Profil-Dimensionen")
print("  systematisch (jeweils innerhalb der Streuung), so ist die Trennung allein")
print("  ueber die Aktivitaets-/Volumen-Achse NICHT belegbar. Die Zahlen oben sind")
print("  dann der Beleg fuer diese Nicht-Unterscheidbarkeit -- nicht die widerlegende,")
print("  sondern die stuetztragende Messung.")
