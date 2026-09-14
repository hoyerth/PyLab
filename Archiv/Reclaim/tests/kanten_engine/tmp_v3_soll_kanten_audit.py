# -*- coding: utf-8 -*-
"""V3-Soll-Kanten-Audit (rein lesend, keine Datei-Schreibzugriffe).

Prueft die 3 Soll-Kanten (66.46 / 64.20 / 63.67) gegen die reinen V3-Regeln
(§7.1 der Spezifikation, Commit 37a66b4):

  * Statische Kante am fixen basis_preis (keine Drift, kein Ratchet).
  * Touch = bestaetigter Pivot (2-Bar-Puffer) mit Docht-Kontakt im
    +/-TOUCH_BAND um basis_preis; Mindestabstand MIN_BAR_ABSTAND.
  * SCHLAFEND = 2 konsekutive Kerzenkoerper vollstaendig jenseits basis_preis.
  * Reaktivierung = naechster Docht-Kontakt am fixen basis_preis.
  * Einstieg (Typ B): Kante AKTIV + >= 3 Touches; Trigger in_bar:
      OBEN (SHORT): high[k] > basis_preis UND close[k] <= basis_preis
      UNTEN (LONG): low[k]  < basis_preis UND close[k] >= basis_preis
    Entry = open[k+1].
  * Stop-Loss strukturell: SHORT high[k]+0.05, LONG low[k]-0.05.
  * Kursziel (Typ A, Gegenkante): >= 2 Touches, Gegenseite, Distanz
    basis-zu-basis >= 1.5 %; TP1 = naechste, TP2 = uebergeordnete dahinter.
    (Kandidaten-Universum = die 3 Soll-Ebenen; Annahme dokumentiert.)

Ausgabe: je Soll-Kante Touch-Liste (Soll vs. Ist), Zustandswechsel und jedes
V3-Signal mit Entry/SL/TP1/TP2. Terminal pur.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tmp_kanten_engine_replay as m  # noqa: E402

TOUCH_BAND: float = 0.15          # V3-A: Docht-Kontakt um basis_preis
MIN_BAR_ABSTAND: int = 3          # V3-A: Touch-Mindestabstand
SL_BUFFER: float = 0.05           # V3-B: struktureller SL-Puffer
TP_MINDIST_PCT: float = 1.5       # V3-C: Mindest-Raum Basis-zu-Basis
BOX_ENDE = pd.Timestamp("2026-08-18")  # Vorlage-Box 10.08..18.08

SOLL = [
    dict(name="UPPER 66.46", seite="OBEN", basis=66.46,
         von="2026-08-11 03:45", bis="2026-08-18 03:00", soll=5),
    dict(name="LOWER-MAIN 63.67", seite="UNTEN", basis=63.67,
         von="2026-08-10 07:30", bis="2026-08-18 17:30", soll=7),
    dict(name="LOWER-MINOR 64.20", seite="UNTEN", basis=64.20,
         von="2026-08-11 08:30", bis="2026-08-14 02:30", soll=4),
]


def _ts(b: int) -> str:
    return pd.Timestamp(d["ts"].iloc[b]).strftime("%d.%m %H:%M")


def _simuliere(seite: str, basis: float, von_bar: int, bis_bar: int):
    """V3-Zustandsmaschine einer statischen Kante ueber [von_bar..n).

    Rueckgabe: touche [(pivot_bar, preis)], confirm_bars, state_aktiv (np),
    running_touches (np, je Bar zaehlbar mit confirm <= bar),
    sleep_bars (np boolean: Bar, an der Kante SCHLAFEND gesetzt).
    """
    n = len(d)
    aktiv = True
    outside = 0
    touche: list = []
    confirm: list = []
    state = np.zeros(n, dtype=bool)      # AKTIV am Ende der Bar-Verarbeitung
    running = np.zeros(n, dtype=int)     # bestaetigte Touches (confirm <= bar)
    sleep_at = np.zeros(n, dtype=bool)
    last_touch_bar = -10**9

    for k in range(von_bar, n):
        # 1) Pivot von m = k-2 verarbeiten (Touch-Registrierung, kausal)
        m_bar = k - 2
        if von_bar <= m_bar <= bis_bar:
            typ = m._pivot_typ(hi, lo, m_bar)
            if typ is not None:
                seite_p = "OBEN" if typ == "H" else "UNTEN"
                if seite_p == seite:
                    px = float(hi[m_bar]) if seite == "OBEN" else float(lo[m_bar])
                    if abs(px - basis) <= TOUCH_BAND and (
                            m_bar - last_touch_bar) >= MIN_BAR_ABSTAND:
                        touche.append((m_bar, px))
                        confirm.append(m_bar + 2)
                        last_touch_bar = m_bar
                        aktiv = True            # Reaktivierung per Docht-Touch
                        outside = 0
        # 2) 2-Body-Bruch gegen FIXES basis (nicht _ref_preis!)
        if k >= von_bar + 1 and k < n:
            if seite == "OBEN":
                aussen1 = min(op[k - 1], cl[k - 1]) > basis
                aussen2 = min(op[k], cl[k]) > basis
            else:
                aussen1 = max(op[k - 1], cl[k - 1]) < basis
                aussen2 = max(op[k], cl[k]) < basis
            if aussen1 and aussen2:
                if aktiv:
                    aktiv = False
                    sleep_at[k] = True
                outside = 0
            else:
                outside = 0
        state[k] = aktiv
        running[k] = len(confirm)   # alle mit pivot+2 <= k sind drin

    # running kumulativ auf confirm-Bars (bereits korrekt via len)
    # state[k] gilt NACH Verarbeitung von Bar k (Pivot k-2 + Body k).
    return dict(touche=touche, confirm=confirm, state=state,
                running=running, sleep_at=sleep_at)


def _touch_im_fenster(touche, von_bar, bis_bar):
    return [(b, p) for b, p in touche if von_bar <= b <= bis_bar]


def main() -> None:
    global d, hi, lo, op, cl
    d = m._lade_fenster("AUG")
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    op = d["open"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    ts_arr = d["ts"].to_numpy().astype("datetime64[ns]")
    n = len(d)

    def bar_idx(ts_str: str) -> int:
        return int(np.searchsorted(ts_arr, np.datetime64(ts_str)))

    # Fenster je Soll-Kante
    for s in SOLL:
        s["von_bar"] = bar_idx(s["von"])
        s["bis_bar"] = int(np.searchsorted(
            ts_arr, np.datetime64(s["bis"]), side="right")) - 1

    # --- Simulation aller 3 Ebenen ----------------------------------------
    sims = {}
    for s in SOLL:
        sims[s["name"]] = _simuliere(s["seite"], s["basis"],
                                     s["von_bar"], s["bis_bar"])

    # --- Touch-Abgleich Soll vs. Ist --------------------------------------
    print("=" * 108)
    print("V3-SOLL-KANTEN-AUDIT AUG | Touch-Band +/-%.2f | Abstand >= %d "
          "Bars | SL-Buffer %.2f | TP-Mindest %.1f%%"
          % (TOUCH_BAND, MIN_BAR_ABSTAND, SL_BUFFER, TP_MINDIST_PCT))
    print("=" * 108)
    for s in SOLL:
        sim = sims[s["name"]]
        ist = _touch_im_fenster(sim["touche"], s["von_bar"], s["bis_bar"])
        status = "OK " if len(ist) == s["soll"] else "ABWEICHUNG"
        print(f"\n[{status}] {s['name']} ({s['seite']}, basis={s['basis']:.2f}) "
              f"Zeitraum {s['von'][5:]}..{s['bis'][5:]} "
              f"(bars {s['von_bar']}..{s['bis_bar']}): "
              f"Soll {s['soll']} Touches | Ist {len(ist)}")
        for b, p in ist:
            mark = "  <== Touch" 
            print(f"    bar {b:4d} ({_ts(b)}) preis={p:8.3f} "
                  f"(dist {abs(p - s['basis']):.3f}){mark}")
        if status == "ABWEICHUNG":
            # zusaetzliche/fehlende Kandidaten zeigen
            alle = _touch_im_fenster(sim["touche"], s["von_bar"], s["bis_bar"])
            extra = [x for x in alle]
            print(f"    (alle registrierten Touches im Fenster: {len(alle)})")

    # --- V3-Signale je Kante -----------------------------------------------
    print("\n" + "#" * 108)
    print("# V3-IN-BAR-RECLAIM-SIGNALE (Einstiegskante AKTIV & >= 3 Touches; "
          "Kursziel = Gegenkante >= 2 Touches, >= 1.5%)")
    print("#" * 108)
    gesamt = []
    for s in SOLL:
        sim = sims[s["name"]]
        basis = s["basis"]
        richtung = "SHORT" if s["seite"] == "OBEN" else "LONG"
        print(f"\n--- {s['name']} ({richtung}-Trigger an {basis:.2f}) ---")
        sig_gefunden = 0
        for k in range(s["von_bar"], n - 1):
            if not sim["state"][k]:
                continue
            if sim["running"][k] < 3:
                continue
            if richtung == "SHORT":
                sweep = hi[k] > basis and cl[k] <= basis
            else:
                sweep = lo[k] < basis and cl[k] >= basis
            if not sweep:
                continue
            # Kausal: Bar k nicht als Touch fuer >=3 zaehlen (confirm k+2)
            entry = float(d["open"].iloc[k + 1])
            sl = (hi[k] + SL_BUFFER) if richtung == "SHORT" else (lo[k] - SL_BUFFER)
            # Kursziel: Gegenkanten aus SOLL (Gegenseite, >=2 Touches, >=1.5%)
            ziele = []
            for s2 in SOLL:
                if s2["seite"] == s["seite"]:
                    continue
                sim2 = sims[s2["name"]]
                if sim2["running"][k] < 2:
                    continue
                dist = abs(basis - s2["basis"]) / s2["basis"] * 100.0
                if richtung == "SHORT":
                    ok_richtung = s2["basis"] < basis
                else:
                    ok_richtung = s2["basis"] > basis
                if ok_richtung and dist >= TP_MINDIST_PCT:
                    ziele.append((dist, s2["basis"], s2["name"]))
            ziele.sort()
            tp1 = ziele[0] if ziele else None
            tp2 = ziele[1] if len(ziele) > 1 else None
            if tp1 is None:
                # kein Ziel -> kein Trade (Raum-Mangel, V3-D)
                continue
            box = "  [BOX 10.08-18.08]" if pd.Timestamp(d["ts"].iloc[k]) < BOX_ENDE else ""
            r_tp1 = ((entry - tp1[1]) / (sl - entry)
                     if richtung == "SHORT" else (tp1[1] - entry) / (entry - sl))
            ziel_txt = f"TP1 {tp1[1]:.2f} ({tp1[2]}, {r_tp1:+.2f}R)"
            if tp2:
                r_tp2 = ((entry - tp2[1]) / (sl - entry)
                         if richtung == "SHORT" else (tp2[1] - entry) / (entry - sl))
                ziel_txt += f" | TP2 {tp2[1]:.2f} ({tp2[2]}, {r_tp2:+.2f}R)"
            sig_gefunden += 1
            gesamt.append((s["name"], k))
            print(f"  SIG {richtung:5s} bar {k:4d} ({_ts(k)}) "
                  f"nT={sim['running'][k]} sweep={hi[k] if richtung=='SHORT' else lo[k]:.3f} "
                  f"close={cl[k]:.3f} entry={entry:.3f} SL={sl:.3f} | {ziel_txt}{box}")
        if sig_gefunden == 0:
            print("  (keine V3-Signale)")

    # --- Zusammenfassung ----------------------------------------------------
    print("\n" + "-" * 108)
    print(f"GESAMT: {len(gesamt)} V3-In-Bar-Reclaim-Signale an den 3 "
          f"Soll-Ebenen (AUG, entry open[k+1], nur mit Kursziel >= 1.5%)")
    for name, k in gesamt:
        box = " [BOX]" if pd.Timestamp(d["ts"].iloc[k]) < BOX_ENDE else ""
        print(f"  {name:16s} bar {k:4d} ({_ts(k)}){box}")
    print("-" * 108)
    print("\nAnnahmen (dokumentiert): (1) Kursziel-Universum = die 3 Soll-Ebenen;")
    print("(2) Touch = Pivot-Docht im +/-Band (symmetric); (3) 2-Body-Bruch gegen")
    print("fixes basis (V3); (4) keine Cooldown-/Spread-/POC-Gates (V3-E).")


if __name__ == "__main__":
    main()
