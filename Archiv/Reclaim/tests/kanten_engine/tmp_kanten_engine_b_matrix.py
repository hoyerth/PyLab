# -*- coding: utf-8 -*-
"""Modus-B-Sensitivitaetsmatrix ueber S1/S2 (4 Ein-Faktor-Saetze um Default).

Saetze (Ratchet %, Zwischenschwung %):
  S1: 0.10/1.5 (arretierter Default)  S2: 0.05/1.5  S3: 0.15/1.5  S4: 0.10/2.0

Je Satz: AUG60 (Referenz) + S1/S2 x max_tage {1,5,20,60}.
Detail-Reports (Modus B) gehen in REPORT_TXT (stdout unterdrueckt); Terminal
zeigt je Satz die kompakte Matrix sowie A/B-Side-by-Side (Satz 1 vs Modus A,
nur S1/S2-Zellen) und eine Gesamt-Gate-UEbersicht ueber alle Saetze.

Rein lesend; schreibt nur test/stats_kanten_engine_replay.txt (append).
"""
import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tmp_kanten_engine_replay as m  # noqa: E402

SAETZE = [
    ("S1_R0.10_S1.5_arretiert", 0.10, 1.5),
    ("S2_R0.05_S1.5", 0.05, 1.5),
    ("S3_R0.15_S1.5", 0.15, 1.5),
    ("S4_R0.10_S2.0", 0.10, 2.0),
]
KONFIG: list = [("AUG", 60)] + [(f, t) for f in ("S1", "S2") for t in (1, 5, 20, 60)]


def _lauf(fenster, mt, modus, ratchet=None, schwung=None):
    cfg = m.HarnessKonfiguration(
        max_tage=mt, modus=modus,
        toleranz_ratchet_pct=ratchet if ratchet is not None else 0.10,
        max_zwischenschwung_pct=schwung if schwung is not None else 1.5,
    )
    return m._replay(fenster, cfg)


def main() -> None:
    out = io.StringIO()
    with open(m.REPORT_TXT, "a", encoding="utf-8") as f:
        f.write("\n\n" + "=" * 104 + "\n")
        f.write("SENSITIVITAETSMATRIX MODUS B (4 Saetze; Ratchet%/Schwung%)\n")
        f.write("=" * 104 + "\n")

    # --- Modus-A-Referenz (fuer Side-by-Side, Regression bereits bewiesen) ---
    print("Lade Modus-A-Referenz (9 Laeufe)...")
    erg_a = {f"{w}_mt{t}": _lauf(w, t, "A") for w, t in KONFIG}

    gesamt_zeilen = []
    for satz_label, ratchet, schwung in SAETZE:
        print("\n" + "#" * 104)
        print(f"# PARAM-SATZ {satz_label}  (Ratchet {ratchet}% / Zwischenschwung {schwung}%)")
        print("#" * 104)
        with open(m.REPORT_TXT, "a", encoding="utf-8") as f:
            f.write("\n" + "#" * 104 + f"\n# PARAM-SATZ {satz_label} "
                    f"(Ratchet {ratchet}% / Zwischenschwung {schwung}%)\n" + "#" * 104 + "\n")
        ergebnisse = []
        for fenster, mt in KONFIG:
            erg = _lauf(fenster, mt, "B", ratchet, schwung)
            ergebnisse.append(erg)
            # Detail-Report nur in REPORT_TXT (stdout unterdrueckt)
            with contextlib.redirect_stdout(out):
                m._report(erg, nach_datei=True)
            if fenster in ("S1", "S2") and satz_label.startswith("S1_"):
                # A/B-Side-by-Side (Satz 1) ins Terminal + Datei
                m._vergleich_tabelle(erg_a[f"{fenster}_mt{mt}"], erg)
        m._matrix_tabelle(ergebnisse, modus="B")
        # Aggregat ueber die 8 S1/S2-Zellen
        s1z = [e for e in ergebnisse if e.fenster == "S1"]
        s2z = [e for e in ergebnisse if e.fenster == "S2"]
        alle = s1z + s2z
        best_s1 = sum(1 for e in s1z if e.fenster_ergebnis().gate_bestanden)
        best_s2 = sum(1 for e in s2z if e.fenster_ergebnis().gate_bestanden)
        paar = 0
        for mt in (1, 5, 20, 60):
            g1 = [e for e in s1z if e.cfg.max_tage == mt][0].fenster_ergebnis().gate_bestanden
            g2 = [e for e in s2z if e.cfg.max_tage == mt][0].fenster_ergebnis().gate_bestanden
            if g1 and g2:
                paar += 1
        sig_sum = sum(e.fenster_ergebnis().trades_gesamt for e in alle)
        lown = sum(1 for e in alle if e.fenster_ergebnis().low_n_warnung)
        ratchet_abg = sum(getattr(e, "ratchet_abgelehnt", 0) for e in alle)
        cluster = sum(getattr(e, "cluster_geburten", 0) for e in alle)
        swing = sum(getattr(e, "swing_geburten", 0) for e in alle)
        merk = sum(getattr(e, "neue_merkposten", 0) for e in alle)
        reclaims = sum(getattr(e, "body_reclaims", 0) for e in alle)
        gesamt_zeilen.append((satz_label, best_s1, best_s2, paar, sig_sum,
                              lown, ratchet_abg, cluster, swing, merk, reclaims))
        zeile = (f"{satz_label:26s} S1-best {best_s1}/4 | S2-best {best_s2}/4 | "
                 f"S1&S2-Kanal-Paare {paar}/4 | Signale(S1+S2) {sig_sum:4d} | "
                 f"low-n {lown}/8 | Ratchet-Abgelehnt {ratchet_abg:5d} | "
                 f"Cluster-Geb. {cluster:4d} | Swing-Geb. {swing:4d} | "
                 f"Merkposten {merk:4d} | Reclaims {reclaims:5d}")
        print(zeile)
        with open(m.REPORT_TXT, "a", encoding="utf-8") as f:
            f.write(zeile + "\n")

    # --- Gesamt-Gate-UEbersicht (alle Saetze) ---
    print("\n" + "=" * 120)
    print("GESAMT-GATE-UEBERSICHT MODUS B (Gate je Zelle: PF>=1.30 & SummeR>0 "
          "& entschieden>0; Kanal-Paar = S1 UND S2 im selben mt bestanden)")
    print("=" * 120)
    print(f"{'Satz':26s} {'S1-best':>8s} {'S2-best':>8s} {'Paare':>6s} "
          f"{'SigSum':>7s} {'low-n':>6s} {'RatchetAbg':>10s} {'Cluster':>7s} "
          f"{'Swing':>6s} {'Merk':>5s} {'Reclaim':>8s}")
    for z in gesamt_zeilen:
        print(f"{z[0]:26s} {z[1]:>8d} {z[2]:>8d} {z[3]:>6d} {z[4]:>7d} "
              f"{z[5]:>6d} {z[6]:>10d} {z[7]:>7d} {z[8]:>6d} {z[9]:>5d} {z[10]:>8d}")
    with open(m.REPORT_TXT, "a", encoding="utf-8") as f:
        f.write("\nGESAMT-GATE-UEBERSICHT MODUS B (Satz, S1-best, S2-best, "
                "Paare, SigSum, low-n, RatchetAbg, Cluster, Swing, Merk, Reclaim)\n")
        for z in gesamt_zeilen:
            f.write(",".join(str(x) for x in z) + "\n")

    keine_paare = all(z[3] == 0 for z in gesamt_zeilen)
    print("\n" + "-" * 120)
    if keine_paare:
        print("URTEIL: KEIN Parametersatz erreicht ein (S1&S2)-Kanal-Paar. "
              "-> Null-Befund-Arretierung fuer Modus B pruefen (s8.2/s8.3).")
    else:
        print("URTEIL: Mindestens ein Parametersatz erreicht ein (S1&S2)-"
              "Kanal-Paar -> formale Gate-Pruefung durch den Anwender.")
    print("-" * 120)


if __name__ == "__main__":
    main()
