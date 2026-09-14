# test/reclaim_generation_audit.py
"""Generation-Grenzziehungs-Audit (REINE DIAGNOSE - kein Live-Code-Eingriff).

Mentor-Review 02.09. (Schritt 1 vor GenerationState-Einbau): Quantifizieren,
wie oft die drei Reset-Modelle der Range-Generation real divergieren, BEVOR
die Resonanz-Definition verdrahtet wird.

Drei Modelle fuer gen_start(k) (k = Auswerte-Bar mit 2-seitigem Korridor),
alle kausal ueber sleep-EVENTS (iter <= k, Preis = Bruchzeit-Preis t["price"]):
  M1 Kanten-Anker : max(anchor(up), anchor(dn)),
                    anchor(lev) = max(birth_bar, letzter sleep_bar <= k)
  M2 Spannen-Reset: max(iter <= k ueber ALLE sleep-Events mit Event-Preis in
                    der aktuellen Spanne [dn_px[k], up_px[k]]);
                    Fallback = max(birth_up, birth_dn)
  M3 Echte Grenze : max(iter <= k ueber sleep-Events, deren Level zum
                    Bruch-Zeitpunkt (Zustand nach iter-2) die Korridor-
                    Grenze up/dn war, UND Event-Preis in der aktuellen
                    Spanne); Fallback = max(birth_up, birth_dn)

Wichtig (Kausalitaet): M2 NICHT ueber das Endzustands-Feld last_sleep_bar
ableiten - ein Level, das NACH k erneut bricht, haette im Endzustand einen
last_sleep_bar > k und fiele fälschlich aus der Menge. Daher zaehlen beide
Modelle ueber die transitions (sleep-Events mit iter <= k).

Break-Event-Klassifikation (je sleep-Event bei iter k):
  Referenz-Zustand = nach Bar k-2 (letzter Close <= Level-Preis bei UPPER
  bzw. >= bei LOWER - der Bruch beginnt exakt mit Close k-1). Da der Korridor
  das naechste aktive Level ueber/unter dem Close ist, kann ein Nicht-Grenz-
  Level nur AUSSERHALB der damaligen Spanne liegen (pass_through) oder ein
  candidate sein (inner_bruch, noch nie Korridor-Grenze).

  grenz_bruch_up/dn : Level war nach k-2 die obere/untere Korridor-Grenze
  pass_through_oben : Level lag ueber der damaligen up-Grenze (Preis lief
                      durch die Grenze und brach die naechste aeussere Kante)
  pass_through_unten: analog unter der damaligen dn-Grenze
  inner_bruch        : Level lag INNERHALB der damaligen Spanne (candidate)
  kein_korridor      : ref < 0 oder damals keine 2-seitige Spanne

An S3-v1-Signal-Bars wird je Modell gen_start, gen_touches beider Seiten
und die Sweet-Spot-Klassifikation (4 <= combined < 12, Illustration auf
Basis der Baseline-DNA) berechnet -> Divergenz-Metriken + Summe-R-Wirkung.

Kausalitaet: Level-Events nur mit iter <= k; Touches nur mit bar <= k-2
(Pivot-Lag); last_sleep nur wenn <= k. Post-hoc-Endzustaende (store.levels)
werden entsprechend gefiltert.

Aufruf:  python test/reclaim_generation_audit.py
"""
from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reclaim_edge_store as res  # noqa: E402
import reclaim_s3_signals as s3  # noqa: E402

WINDOWS: List[Tuple[str, str, str]] = [
    ("S1", "2026-02-05", "2026-08-28"),
    ("S2", "2025-01-01", "2025-12-01"),
]

# Illustration Sweet Spot (Baseline-DNA combined 6-11 -> mit Puffer 4<=x<12;
# Store-Kalibrierung bleibt S3-v3 vorbehalten)
SS_LO, SS_HI = 4, 12

EVENT_CLASSES: List[str] = [
    "grenz_bruch_up", "grenz_bruch_dn", "pass_through_oben",
    "pass_through_unten", "inner_bruch", "kein_korridor",
]


def track_corridor(df: pd.DataFrame) -> Tuple[res.EdgeStore, Dict[str, np.ndarray]]:
    """Store-Build; je Bar k (Zustand NACH k) up/dn-Korridor erfassen."""
    n = len(df)
    up_id = np.full(n, -1, dtype=np.int64)
    up_px = np.full(n, np.nan)
    dn_id = np.full(n, -1, dtype=np.int64)
    dn_px = np.full(n, np.nan)
    close = df["close"].values.astype(float)

    def hook(k: int, store: res.EdgeStore) -> None:
        up, dn = store.corridor(close[k])
        if up is not None:
            up_id[k], up_px[k] = up.edge_id, up.price
        if dn is not None:
            dn_id[k], dn_px[k] = dn.edge_id, dn.price

    store = res.EdgeStore().build(df, on_bar=hook)
    return store, {
        "up_id": up_id, "up_px": up_px, "dn_id": dn_id, "dn_px": dn_px,
    }


def classify_event(k: int, eid: int, price: float, track: Dict[str, np.ndarray]
                   ) -> str:
    """Sleep-Event bei iter k: war das Level nach k-2 die Korridor-Grenze?"""
    ref = k - 2
    if ref < 0:
        return "kein_korridor"
    if int(track["up_id"][ref]) == eid:
        return "grenz_bruch_up"
    if int(track["dn_id"][ref]) == eid:
        return "grenz_bruch_dn"
    up_px, dn_px = track["up_px"][ref], track["dn_px"][ref]
    if np.isnan(up_px) or np.isnan(dn_px):
        return "kein_korridor"
    if price > up_px:
        return "pass_through_oben"
    if price < dn_px:
        return "pass_through_unten"
    return "inner_bruch"


def gen1_anchor(lev: res.EdgeLevel, k: int) -> int:
    ls = lev.last_sleep_bar
    if ls < 0 or ls > k:          # nie gebrochen oder erst nach k gebrochen
        ls = -10**9
    return int(max(lev.birth_bar, ls))


def analyze(name: str, start: str, ende: str) -> None:
    t0 = time.time()
    df = res.load_data(res.DB_PATH, start, ende)
    cl = df["close"].values.astype(float)
    print(f"\n{'#' * 100}\n# GENERATION-AUDIT {name} ({start} - {ende}, "
          f"{len(df)} Bars)\n{'#' * 100}")

    # S3-v1-Signale (Referenz-Kandidaten) + separater Track-Build
    sigs, _store_sig, _blk = s3.simulate(df, use_gate_a=False, use_gate_b=False)
    store, track = track_corridor(df)
    levels: Dict[int, res.EdgeLevel] = {lv.edge_id: lv for lv in store.levels}
    t_sim = time.time() - t0
    print(f"v1-Signale {len(sigs)} | Store-Level {len(store.levels)} | "
          f"{t_sim:.1f}s")

    # ---------- 1) Break-Event-Klassifikation (ganzes Fenster) ----------
    sleep_events = [t for t in store.transitions if t["event"] == "sleep"]
    classes: Counter = Counter()
    # (iter, eid, event_price, klasse) - event_price = Bruchzeit-Preis (kausal)
    events: List[Tuple[int, int, float, str]] = []
    for t in sleep_events:
        k = int(t["iter"])
        eid = int(t["edge_id"])
        price = float(t["price"])
        cls = classify_event(k, eid, price, track)
        classes[cls] += 1
        events.append((k, eid, price, cls))

    print(f"\n[1] Break-Events: {len(sleep_events)} gesamt")
    for c in EVENT_CLASSES:
        n_c = classes.get(c, 0)
        print(f"    {c:20s}: n={n_c:4d} ({100.0 * n_c / len(sleep_events):4.1f}%)")

    # ---------- 2) gen_start-Divergenz an S3-v1-Signal-Bars ----------
    print(f"\n[2] gen_start-Divergenz an {len(sigs)} S3-v1-Signal-Bars")
    rows: List[dict] = []
    for s in sigs:
        k = s.bar
        up_id, dn_id = int(track["up_id"][k]), int(track["dn_id"][k])
        if up_id < 0 or dn_id < 0:
            continue  # 1-seitig: keine Generation definierbar
        up, dn = levels[up_id], levels[dn_id]
        up_px, dn_px = float(track["up_px"][k]), float(track["dn_px"][k])
        # M1: Kanten-Anker
        g1 = max(gen1_anchor(up, k), gen1_anchor(dn, k))
        # M2: Spannen-Reset = max iter ueber ALLE sleep-Events (iter <= k)
        #     mit Event-Preis in der aktuellen Spanne nach k.
        cand2 = [it for it, _eid, px, _cls in events
                 if it <= k and dn_px <= px <= up_px]
        g2 = max(cand2) if cand2 else max(up.birth_bar, dn.birth_bar)
        # M3: Echte Grenze = max iter ueber grenz_bruch-Events (iter <= k)
        #     mit Event-Preis in der aktuellen Spanne nach k.
        cand3 = [it for it, _eid, px, cls in events
                 if it <= k and cls in ("grenz_bruch_up", "grenz_bruch_dn")
                 and dn_px <= px <= up_px]
        g3 = max(cand3) if cand3 else max(up.birth_bar, dn.birth_bar)

        def _gen_touches(lev: res.EdgeLevel, gen: int, kk: int) -> int:
            return int(sum(1 for t in lev.touches
                           if t.bar >= gen and t.bar <= kk - 2))

        def _ss(gen: int) -> Tuple[int, int, bool]:
            tu = _gen_touches(up, gen, k)
            td = _gen_touches(dn, gen, k)
            return tu, td, SS_LO <= (tu + td) < SS_HI

        res_m = {}
        for label, g in (("M1", g1), ("M2", g2), ("M3", g3)):
            tu, td, ss = _ss(g)
            res_m[label] = (g, tu, td, ss)
        rows.append({
            "bar": k, "typ": s.typ, "r": s.trade.r_mult,
            "g1": g1, "g2": g2, "g3": g3,
            "ss1": res_m["M1"][3], "ss2": res_m["M2"][3], "ss3": res_m["M3"][3],
            "c1": res_m["M1"][1] + res_m["M1"][2],
            "c2": res_m["M2"][1] + res_m["M2"][2],
            "c3": res_m["M3"][1] + res_m["M3"][2],
        })

    if not rows:
        print("    keine 2-seitigen Signal-Bars")
        return
    d = pd.DataFrame(rows)
    n_r = len(d)
    gcol = {"M1": "g1", "M2": "g2", "M3": "g3"}
    for a, b in (("M1", "M2"), ("M2", "M3"), ("M1", "M3")):
        ga, gb = gcol[a], gcol[b]
        diff = d[ga] != d[gb]
        ad = (d[ga] - d[gb]).abs()
        print(f"    {a} vs {b}: abweichend {int(diff.sum()):4d} "
              f"({100.0 * diff.mean():4.1f}%) | median |dG| "
              f"{ad.median():6.0f} Bars | p90 {ad.quantile(0.9):6.0f}")
    # Richtung (grosserer gen_start = naeher an k = JUENGERE Generation)
    print(f"    M2-Generation juenger als M1 (g2>g1): {int((d.g2 > d.g1).sum()):4d} | "
          f"aelter (g2<g1): {int((d.g2 < d.g1).sum()):4d}")
    print(f"    M3-Generation juenger als M1 (g3>g1): {int((d.g3 > d.g1).sum()):4d} | "
          f"aelter (g3<g1): {int((d.g3 < d.g1).sum()):4d}")
    print(f"    M3-Generation juenger als M2 (g3>g2): {int((d.g3 > d.g2).sum()):4d} | "
          f"aelter (g3<g2): {int((d.g3 < d.g2).sum()):4d}")

    # ---------- 3) Sweet-Spot-Wirkung je Modell ----------
    print(f"\n[3] Sweet-Spot {SS_LO}<=combined<{SS_HI} je Modell "
          f"(Illustration, Baseline-DNA)")
    print(f"    {'Modell':6s} | {'im SS':>5s} {'SummeR':>8s} {'WR':>4s} | "
          f"{'blockiert':>9s} {'entg. R':>9s}")
    scol = {"M1": "ss1", "M2": "ss2", "M3": "ss3"}
    ccol = {"M1": "c1", "M2": "c2", "M3": "c3"}
    for m in ("M1", "M2", "M3"):
        ins = d[d[scol[m]]]
        out = d[~d[scol[m]]]
        w = (ins.r > 0).sum()
        wr = 100.0 * w / len(ins) if len(ins) else 0.0
        print(f"    {m:6s} | {len(ins):5d} {ins.r.sum():+8.2f} {wr:3.0f}% | "
              f"{len(out):9d} {out.r.sum():+9.2f}")
    # v1-Gesamt
    print(f"    v1-Gesamt: {len(d):5d} {d.r.sum():+8.2f}")

    # SS-Klassifikations-Wechsel zwischen M2 und M3
    wechsel = (d[scol["M2"]] != d[scol["M3"]]).sum()
    print(f"\n    Sweet-Spot-Klassifikations-Wechsel M2 vs M3: "
          f"{wechsel}/{len(d)}")
    # combined-Verteilung je Modell (Korrelation)
    for m in ("M2", "M3"):
        corr = d[ccol[m]].corr(d["r"])
        print(f"    combined[{m}] vs R: Pearson {corr:+.3f} | "
              f"Median combined {d[ccol[m]].median():.0f} | "
              f"p25 {d[ccol[m]].quantile(0.25):.0f} | "
              f"p75 {d[ccol[m]].quantile(0.75):.0f}")
    print(f"    Zeit gesamt: {time.time() - t0:.1f}s")


def main() -> None:
    for name, start, ende in WINDOWS:
        analyze(name, start, ende)


if __name__ == "__main__":
    main()
