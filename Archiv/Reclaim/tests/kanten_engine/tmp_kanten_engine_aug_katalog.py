# -*- coding: utf-8 -*-
"""AUG-Lauf (Modus A + B) mit vollstaendigem Kanten-Katalog in die Report-TXT.

Haengt je Modus den Standard-Report an und danach einen KANTEN-KATALOG:
jede Kante mit allen Daten (Geburt, Basis/Balance/Anker, Volumen, Zustand,
Cooldown, saemtliche Touche inkl. Bar/ts/Preis/Volumen/gueltig_ab/Amplitude/
Gegenkanten-Ursprung) sowie den erzeugten Signalen je Kante. Markierung der
Kanten mit Geburt im Prototyp-Box 10.08..18.08.

Terminal: kompakte Einzeiler aller Kanten je Modus (Diskussion direkt moeglich).
"""
import contextlib
import io
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tmp_kanten_engine_replay as m  # noqa: E402

BOX = pd.Timestamp("2026-08-18")  # Prototyp-Box: 10.08..18.08


def _fmt_ts(t) -> str:
    return t.strftime("%d.%m %H:%M") if hasattr(t, "strftime") else str(t)


def _katalog(erg: m._ReplayErgebnis, fh, modus_txt: str, box_bar: int) -> None:
    fe = erg.fenster_ergebnis()
    pf = fe.profit_factor
    pf_txt = "inf" if pf == float("inf") else f"{pf:.2f}"
    fh.write("\n" + "=" * 110 + "\n")
    fh.write(f"KANTEN-KATALOG AUG -- {modus_txt} | max_tage={erg.cfg.max_tage} | "
             f"Kanten {len(erg.kanten)} | Signale {fe.trades_gesamt} | "
             f"SummeR {fe.summe_r:+.2f} | PF {pf_txt}\n")
    fh.write("=" * 110 + "\n")
    fh.write(f"Box-Grenze (Geburt < 18.08.): bar {box_bar}\n\n")
    for kid, k2 in sorted(erg.kanten.items()):
        in_box = k2.geburts_bar < box_bar
        mark = "   <<< BOX 10.08-18.08" if in_box else ""
        anker_txt = (f"{k2.anker_extremum:.3f}" if k2.anker_extremum > 0.0 else "-")
        lt = (f"{k2.letzter_touch_bar} ({_fmt_ts(k2.letzter_touch_ts)})"
              if k2.letzter_touch_ts is not None else "-")
        fh.write(
            f"K{kid:2d} {k2.seite:5s} geb_bar={k2.geburts_bar:4d} "
            f"({_fmt_ts(k2.geburts_ts)}) zustand={k2.zustand:9s} "
            f"typB={'JA' if k2.ist_typ_b else '--':2s} "
            f"handelbar={'JA' if k2.ist_handelbar else '--':2s} "
            f"nT={k2.touch_anzahl:2d} letzter_touch={lt}{mark}\n"
        )
        fh.write(
            f"    basis={k2.basis_preis:.3f} balance={k2.balance_preis:.3f} "
            f"anker={anker_txt} vol_im_band={k2.volumen_im_band:.0f} "
            f"cooldown_bis_bar={k2.cooldown_bis_bar}\n"
        )
        for i, t in enumerate(k2.touche, 1):
            fh.write(
                f"    touch {i:2d}: bar={t.pivot_bar:4d} ({_fmt_ts(t.ts)}) "
                f"preis={t.preis:.3f} vol={t.volumen:.0f} "
                f"gueltig_ab={t.gueltig_ab_bar:4d} amp={t.amplitude_pct:.2f}% "
                f"gegenkanten={'ja' if t.gegenkanten_ursprung else 'nein'}\n"
            )
        for s in erg.signale:
            if s.kanten_id != kid:
                continue
            fh.write(
                f"    -> SIG {s.semantik:8s} {s.richtung:5s} "
                f"sweep_bar={s.sweep_bar:4d} entry_bar={s.entry_bar:4d} "
                f"({_fmt_ts(s.ts)}) gegen K{s.kanten_id_gegen}\n"
            )
    fh.write("\n")


def _compact(erg: m._ReplayErgebnis, box_bar: int) -> list:
    zeilen = []
    for kid, k2 in sorted(erg.kanten.items()):
        in_box = k2.geburts_bar < box_bar
        anker_txt = (f"{k2.anker_extremum:.3f}" if k2.anker_extremum > 0.0 else "-")
        zeilen.append(
            f"K{kid:2d} {k2.seite:5s} geb={k2.geburts_bar:4d} "
            f"({_fmt_ts(k2.geburts_ts)}) basis={k2.basis_preis:7.3f} "
            f"bal={k2.balance_preis:7.3f} anker={anker_txt:7s} "
            f"nT={k2.touch_anzahl:2d} typB={'JA' if k2.ist_typ_b else '--':2s} "
            f"hand={'JA' if k2.ist_handelbar else '--':2s}"
            + ("  [BOX]" if in_box else "")
        )
    return zeilen


def main() -> None:
    d = m._lade_fenster("AUG")
    box_bar = int(np.searchsorted(
        d["ts"].to_numpy().astype("datetime64[ns]"),
        np.datetime64(BOX.to_datetime64())))
    print(f"AUG: {len(d)} Bars | Box-Grenze 18.08 = bar {box_bar} "
          f"(ts={_fmt_ts(pd.Timestamp(d['ts'].iloc[box_bar]))})")

    for modus in ("A", "B"):
        modus_txt = ("Modus A (Balance-VWAP/V1)" if modus == "A"
                     else "Modus B (Extremum-Ratchet/V2)")
        cfg = m.HarnessKonfiguration(max_tage=60, modus=modus)  # type: ignore[arg-type]
        erg = m._replay("AUG", cfg)
        # Standard-Report nur in die Datei (Terminal: kompakte Kantenliste)
        with contextlib.redirect_stdout(io.StringIO()):
            m._report(erg, nach_datei=True)
        with open(m.REPORT_TXT, "a", encoding="utf-8") as fh:
            _katalog(erg, fh, modus_txt, box_bar)
        fe = erg.fenster_ergebnis()
        print("\n" + "#" * 100)
        print(f"# {modus_txt} | AUG | Kanten {len(erg.kanten)} | "
              f"Signale {fe.trades_gesamt} | SummeR {fe.summe_r:+.2f} | "
              f"PF {'inf' if fe.profit_factor == float('inf') else f'{fe.profit_factor:.2f}'}")
        print("#" * 100)
        for z in _compact(erg, box_bar):
            print("  " + z)

    print(f"\nKanten-Katalog vollstaendig angehaengt an: {m.REPORT_TXT}")


if __name__ == "__main__":
    main()
