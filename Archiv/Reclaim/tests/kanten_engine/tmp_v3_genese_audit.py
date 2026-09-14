# -*- coding: utf-8 -*-
"""V3-Genese-Audit Phase 0b (rein lesend; schreibt nur das Diagnose-PNG).

Prueft die ARRETIERTE V3-Kanten-Genese (Spez §7.1 F, Commit 515d0c9) ueber das
AUG-Fenster, OHNE Signal-/Trade-/Kursziel-Logik:

  * Dualer Pivot (F1): H und L unabhaengig; H==L-Umkehrbar -> BEIDE Seiten.
  * Asymmetrische Geburts-Sperre (geburts_sperr_pct = 0.50):
      - aeusseres Extremum (OBEN: preis > basis_best; UNTEN: preis < basis_best)
        darf IMMER gebaeren (Range-Expansion, K20 trotz K18)
      - innerer Pivot im 0,50-%-Nahbereich = Zwischenwelle (kein Touch, keine
        Geburt), AUSSER er liegt im 0,23-%-Touchband einer Kante -> Touch
  * Touch-Matching per Dominanz: Kandidaten gleicher Seite im 0,23-%-Band;
    Gewinner = hoechste touch_anzahl, Tie-Break aeltere (kleinere kid).
  * Touch-Mindestabstand min_touch_bar_abstand = 3.
  * 2-Body-Bruch -> SCHLAFEND gegen das FIXE basis_preis; Reaktivierung per
    Docht-Touch im Band.
  * Ring-Ereignis-Reporting: verworfene innere Pivots im Ring (0,23..0,50 %)
    werden je Soll-Ebene separat ausgewiesen (Restpunkt 5 der Spez).

Ausgabe: Terminal-Report + PNG test/kanten_engine_genese_AUG.png (D1).
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tmp_kanten_engine_replay as m  # noqa: E402

TOUCH_BAND_PCT: float = 0.23        # V3: relatives Touch-Band (F2)
GEBURTS_SPERR_PCT: float = 0.50     # V3: Geburts-Sperre fuer innere Sub-Level
MIN_TOUCH_ABSTAND: int = 3          # V3: Touch-Mindestabstand
PNG_OUT: str = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "kanten_engine_genese_AUG.png")

SOLL = [
    dict(name="UPPER 66.46", seite="OBEN", basis=66.46,
         von="2026-08-11 03:45", bis="2026-08-18 03:00", soll=5,
         mensch=[107, 237, 249, 529, 536]),
    dict(name="LOWER-MAIN 63.67", seite="UNTEN", basis=63.67,
         von="2026-08-10 07:30", bis="2026-08-18 17:30", soll=7,
         mensch=[30, 52, 57, 60, 63, 380, 386]),
    dict(name="LOWER-MINOR 64.20", seite="UNTEN", basis=64.20,
         von="2026-08-11 08:30", bis="2026-08-14 02:30", soll=4,
         mensch=[126, 316, 320, 361]),
]


class _KanteC:
    """Minimal-Kante des Genese-Audits (nur Geometrie, kein Signal)."""

    __slots__ = ("kid", "seite", "basis", "geburts_bar", "letzter_touch",
                 "touch_bars", "aussen_count", "status", "schlaf_ab")

    def __init__(self, kid: int, seite: str, basis: float, geburts_bar: int):
        self.kid = kid
        self.seite = seite
        self.basis = basis
        self.geburts_bar = geburts_bar
        self.letzter_touch = -1000
        self.touch_bars: list = []
        self.aussen_count = 0
        self.status = "AKTIV"
        self.schlaf_ab: list = []

    def ist_im_band(self, extremum: float) -> bool:
        return (abs(extremum - self.basis) / self.basis * 100.0
                <= TOUCH_BAND_PCT)

    def dist_pct(self, px: float) -> float:
        return abs(px - self.basis) / self.basis * 100.0

    @property
    def touch_anzahl(self) -> int:
        return len(self.touch_bars)

    def touch(self, bar: int) -> None:
        self.touch_bars.append(bar)
        self.letzter_touch = bar
        self.aussen_count = 0
        if self.status == "SCHLAFEND":
            self.status = "AKTIV"


def _pivot_dual(hi: np.ndarray, lo: np.ndarray, m: int) -> list:
    out: list = []
    if hi[m] > hi[m - 1] and hi[m] > hi[m - 2] and \
            hi[m] > hi[m + 1] and hi[m] > hi[m + 2]:
        out.append("H")
    if lo[m] < lo[m - 1] and lo[m] < lo[m - 2] and \
            lo[m] < lo[m + 1] and lo[m] < lo[m + 2]:
        out.append("L")
    return out


def main() -> None:
    d = m._lade_fenster("AUG")
    n = len(d)
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    op = d["open"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    ts_arr = d["ts"].to_numpy().astype("datetime64[ns]")
    ts = pd.to_datetime(d["ts"])

    def _ts(b: int) -> str:
        return ts.iloc[b].strftime("%d.%m %H:%M")

    for s in SOLL:
        s["von_bar"] = int(np.searchsorted(ts_arr, np.datetime64(s["von"])))
        s["bis_bar"] = int(np.searchsorted(
            ts_arr, np.datetime64(s["bis"]), side="right")) - 1

    kanten: list = []
    ring: list = []          # (bar, seite, px, near_kid, dist_pct)
    kid_next = 0

    for k in range(n):
        mbar = k - 2
        if mbar >= 2:
            for typ in _pivot_dual(hi, lo, mbar):
                seite = "OBEN" if typ == "H" else "UNTEN"
                px = float(hi[mbar]) if typ == "H" else float(lo[mbar])
                # 1) Touch-Matching (Dominanz) im 0,23-%-Band
                cand = [e for e in kanten if e.seite == seite
                        and e.ist_im_band(px)]
                if cand:
                    best = max(cand, key=lambda e: (e.touch_anzahl, -e.kid))
                    if mbar - best.letzter_touch >= MIN_TOUCH_ABSTAND:
                        best.touch(mbar)
                    continue
                # 2) Geburts-Sperre asymmetrisch
                blocked = False
                near = None
                for e in kanten:
                    if e.seite != seite:
                        continue
                    dd = e.dist_pct(px)
                    if dd <= GEBURTS_SPERR_PCT:
                        inner = ((seite == "OBEN" and px <= e.basis) or
                                 (seite == "UNTEN" and px >= e.basis))
                        if inner:
                            blocked = True
                            if near is None or dd < near[0]:
                                near = (dd, e.kid, e.basis)
                if blocked:
                    ring.append((mbar, seite, px, near[1], near[0]))
                    continue
                # 3) Geburt (aeusseres Extrem oder ausserhalb 0,50 %)
                e = _KanteC(kid_next, seite, px, mbar)
                kid_next += 1
                e.touch(mbar)
                kanten.append(e)

        # 2-Body-Bruch gegen FIXES basis
        if k >= 1:
            for e in kanten:
                if e.seite == "OBEN":
                    aussen = (min(op[k - 1], cl[k - 1]) > e.basis and
                              min(op[k], cl[k]) > e.basis)
                else:
                    aussen = (max(op[k - 1], cl[k - 1]) < e.basis and
                              max(op[k], cl[k]) < e.basis)
                if aussen:
                    e.aussen_count = 2
                    if e.status == "AKTIV":
                        e.status = "SCHLAFEND"
                        e.schlaf_ab.append(k)
                else:
                    e.aussen_count = 0

    # --- Globale Statistik ------------------------------------------------
    n_oben = sum(1 for e in kanten if e.seite == "OBEN")
    n_unten = sum(1 for e in kanten if e.seite == "UNTEN")
    n_typ_b = sum(1 for e in kanten if len(e.touch_bars) >= 3)
    print("=" * 116)
    print("V3-GENESE-AUDIT 0b AUG | asym. Geburts-Sperre 0.50 | "
          "Dominanz-Matching | touch_band 0.23 | min_abstand 3")
    print("=" * 116)
    print(f"Geborene Kanten gesamt: {len(kanten)} "
          f"(OBEN {n_oben}, UNTEN {n_unten}) | >= 3 Touches (Typ B): {n_typ_b} "
          f"| verworfene Ring-Pivots (0.23-0.50%): {len(ring)}")

    reif = [e for e in kanten if len(e.touch_bars) >= 2]
    reif.sort(key=lambda e: e.basis)
    print(f"Kanten mit >= 2 Touches (Typ A): {len(reif)}")
    for e in reif:
        band = ""
        for s in SOLL:
            if s["seite"] == e.seite and abs(e.basis - s["basis"]) / \
                    s["basis"] * 100.0 <= TOUCH_BAND_PCT:
                band += f"   <== ~{s['name'].split()[0]} {s['name'].split()[1]}"
        print(f"  K{e.kid:3d} {e.seite:5s} basis={e.basis:8.3f} "
              f"geburt={e.geburts_bar:4d} touche={len(e.touch_bars)} "
              f"bars={e.touch_bars}  {band}")

    # --- Soll/Ist-Abgleich ------------------------------------------------
    print("\n" + "#" * 116)
    print("# SOLL/IST-ABGLEICH (Level-Aequivalenz = touch_band_pct)")
    print("#" * 116)
    tabellen_zeilen = []
    for s in SOLL:
        match = [e for e in kanten if e.seite == s["seite"] and
                 abs(e.basis - s["basis"]) / s["basis"] * 100.0
                 <= TOUCH_BAND_PCT]
        match.sort(key=lambda e: (abs(e.basis - s["basis"]), e.kid))
        print(f"\n[{s['name']}] ({s['seite']}, Soll-Anker {s['basis']:.2f}) "
              f"Zeitfenster {s['von'][5:]}..{s['bis'][5:]} "
              f"(bars {s['von_bar']}..{s['bis_bar']}) | Soll {s['soll']} "
              f"| gematchte Kanten im Band: {len(match)}")
        # Ring-Ereignisse nahe dieser Soll-Ebene (Seite + Basis im Ring)
        ring_s = []
        for (b, seite, px, nk, dp) in ring:
            if seite != s["seite"]:
                continue
            if abs(px - s["basis"]) / s["basis"] * 100.0 <= GEBURTS_SPERR_PCT:
                ring_s.append((b, px, nk, dp))
        ring_s.sort()
        for e in match:
            fenster_t = [b for b in e.touch_bars
                         if s["von_bar"] <= b <= s["bis_bar"]]
            dist = abs(e.basis - s["basis"]) / s["basis"] * 100.0
            print(f"  K{e.kid:3d} basis={e.basis:8.3f} (dist {dist:5.3f}%) "
                  f"geburt={e.geburts_bar:4d} endstatus={e.status} "
                  f"touche_gesamt={len(e.touch_bars)} "
                  f"touche_im_fenster={len(fenster_t)}")
            for b in fenster_t:
                mark = "   <== menschl. Soll-Touch" if b in s["mensch"] else ""
                print(f"        bar {b:4d} ({_ts(b)}){mark}")
        # Ring-Ereignisse im Soll-Fenster
        ring_fenster = [r for r in ring_s
                        if s["von_bar"] <= r[0] <= s["bis_bar"]]
        if ring_fenster:
            print(f"  RING-Ereignisse im Fenster (verworfen, 0.23-0.50%): "
                  f"{len(ring_fenster)}")
            for (b, px, nk, dp) in ring_fenster:
                mark = "   <== menschl. Soll-Touch liegt im RING" \
                    if b in s["mensch"] else ""
                print(f"        bar {b:4d} ({_ts(b)}) px={px:8.3f} "
                      f"(dist zu K{nk} {dp:5.3f}%){mark}")
        if match:
            dom = match[0]
            ist = [b for b in dom.touch_bars if s["von_bar"] <= b <= s["bis_bar"]]
            ring_mensch = [r for r in ring_fenster if r[0] in s["mensch"]]
            status = "OK " if len(ist) == s["soll"] else "ABWEICHUNG"
            fehl = [b for b in s["mensch"] if b not in ist
                    and b not in [r[0] for r in ring_mensch]]
            in_ring = [b for b in s["mensch"] if b not in ist
                       and b in [r[0] for r in ring_mensch]]
            extra = [b for b in ist if b not in s["mensch"]]
            print(f"  -> IST (dominante Kante K{dom.kid}): {len(ist)} | "
                  f"Soll {s['soll']} | {status}")
            if in_ring:
                print(f"     im Ring verworfen (menschl. zaehlt sie): {in_ring}")
            if fehl:
                print(f"     fehlend (weder Touch noch Ring): {fehl}")
            if extra:
                print(f"     zusaetzlich gegen menschl. Zaehlung: {extra}")
            tabellen_zeilen.append((s["name"], s["soll"], len(ist),
                                    len(in_ring), status))

    # --- PNG (D1) ----------------------------------------------------------
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.lines import Line2D

        idx = np.arange(n)
        close = d["close"].to_numpy(dtype=float)
        fig, (ax1, axs) = plt.subplots(
            2, 1, figsize=(18, 11), gridspec_kw={
                "height_ratios": [4.0, 1.4], "hspace": 0.15})
        ax1.plot(idx, close, color="#1f77b4", lw=0.9, alpha=0.9, zorder=2,
                 label="Close")
        # Soll-Ebenen + Zeitfenster
        for s in SOLL:
            seg = np.full(n, np.nan)
            seg[s["von_bar"]:s["bis_bar"] + 1] = s["basis"]
            ax1.plot(idx, seg, color="black", lw=1.6, ls="--", alpha=0.8,
                     zorder=4)
            ax1.text(idx[s["bis_bar"]] + 4, s["basis"],
                     f"{s['basis']:.2f} (Soll {s['soll']})", fontsize=8,
                     color="black", va="center")
        # Geborene Kanten >= 2 Touches
        for e in reif:
            col = "#d62728" if e.seite == "OBEN" else "#2ca02c"
            ls = "-" if e.seite == "OBEN" else "--"
            ax1.plot(idx, np.full(n, e.basis), color=col, lw=1.1, ls=ls,
                     alpha=0.55, zorder=3)
            for tb in e.touch_bars:
                tpx = e.basis if e.seite == "OBEN" else e.basis
                ax1.plot(tb, tpx, "o", ms=3.0, color=col, alpha=0.85,
                         zorder=5)
        # Box + Doppel-Pivot Bar 386
        ax1.axvspan(0, 551, color="gray", alpha=0.06, zorder=1)
        ax1.axvline(386, color="purple", lw=1.2, ls=":", alpha=0.8)
        ax1.text(386, ax1.get_ylim()[0], " Doppel-Pivot 386 (F1)", fontsize=8,
                 color="purple", rotation=90, va="bottom")
        # x-Achse Datums-Labels
        ticks = np.linspace(0, n - 1, 9).astype(int)
        ax1.set_xticks(ticks)
        ax1.set_xticklabels([ts.iloc[i].strftime("%d.%m %H:%M") for i in ticks],
                            rotation=0, fontsize=8)
        ax1.set_title("V3-Genese-Audit 0b AUG | asym. Geburts-Sperre 0.50 | "
                      "Dominanz-Matching | touch_band 0.23", fontsize=12)
        leg = [Line2D([0], [0], color="black", ls="--", lw=1.6,
                      label="Soll-Ebenen"),
               Line2D([0], [0], color="#d62728", lw=1.1,
                      label="OBEN-Kanten (>=2T)"),
               Line2D([0], [0], color="#2ca02c", ls="--", lw=1.1,
                      label="UNTEN-Kanten (>=2T)"),
               Line2D([0], [0], marker="o", color="w", mfc="#2ca02c",
                      label="Touch"),]
        ax1.legend(handles=leg, loc="upper left", fontsize=8)
        # Statistik-Panel
        axs.axis("off")
        z = []
        for (nm, soll, ist, ring_, st) in tabellen_zeilen:
            z.append(f"{nm}: Soll {soll} | IST {ist} | Ring-Soll {ring_} | "
                     f"{st}")
        z.insert(0, f"Kanten gesamt: {len(kanten)} (OBEN {n_oben}, "
                    f"UNTEN {n_unten}) | Typ B: {n_typ_b} | "
                    f"Ring-Pivots verworfen: {len(ring)}")
        axs.text(0.01, 0.95, "\n".join(z), fontsize=11, va="top",
                 family="monospace", transform=axs.transAxes)
        fig.savefig(PNG_OUT, dpi=300)
        plt.close(fig)
        print(f"\nPNG geschrieben: {PNG_OUT}")
    except Exception as e:  # pragma: no cover
        print(f"\n[WARNUNG] PNG nicht erzeugt: {e}")

    print("-" * 116)
    print("Annahmen: (1) Freie Genese ab Fensterbeginn AUG; (2) asym. "
          "Geburts-Sperre 0.50% (aeusseres Extrem immer Geburt);")
    print("(3) Dominanz-Matching (max touch_anzahl, Tie aeltere); (4) Ring = "
          "Zwischenwelle ohne Touch (Restpunkt 5);")
    print("(5) 2-Body-Bruch gegen fixes basis_preis; kein Zeitverfall; "
          "(6) KEINE Signal-/Trade-/Kursziel-Logik.")


if __name__ == "__main__":
    main()
