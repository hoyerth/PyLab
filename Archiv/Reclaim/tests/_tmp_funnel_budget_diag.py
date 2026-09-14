# -*- coding: utf-8 -*-
"""DIAGNOSE-WRAPPER (read-only, kein Motor-Eingriff) -- E2.

Anlass: ``main()`` der Sonde bricht bei einer Budgetverletzung VOR dem
Schreiben des Protokolls ab (Beschluss O4: kein Protokoll bei Verletzung).
Damit gehen die bereits berechneten Verletzungszeilen verloren.

Dieser Wrapper aendert NICHTS an der Sonde und NICHTS am Motor. Er
importiert die Sonde als Modul und faengt jede von ihr erzeugte
``TelemetrieBudget``-Instanz ab (Registry). Nach dem Abbruch werden die
Budgetzeilen, die Trichter und die Hypothesensignaturen ausgegeben -- die
Zaehler ``F.ZAHL`` sind nach dem Abbruch unveraendert gueltig, weil der
Abbruch erst NACH dem Durchlauf aller fuenf Fenster erfolgt.
"""
from __future__ import annotations

import pathlib
import sys
import traceback
from typing import Any, List

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

import _chk_zulassung_funnel as F  # noqa: E402

OUT = ROOT / "test" / "_tmp_funnel_budget_diag_out.txt"

REGI: List[Any] = []


class _Rec(F.TelemetrieBudget):  # type: ignore[misc]
    """Aufzeichnende Huelle (nur __init__ -- keine Semantik-Aenderung)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        REGI.append(self)


def main() -> None:
    z: List[str] = []
    z.append("DIAGNOSE-WRAPPER ZUR ZULASSUNGS-FUNNEL-SONDE (E2)")
    z.append("=" * 96)
    z.append("Die Sonde laeuft UNVERAENDERT. Erfasst werden nur die bereits")
    z.append("erzeugten TelemetrieBudget-Instanzen + die Zaehlerstaende.")
    z.append("")

    F.TelemetrieBudget = _Rec  # type: ignore[assignment]
    _abgebrochen: str = ""
    try:
        F.main()
        z.append("main() lief ohne Abbruch durch (kein Fehlerfall).")
    except BaseException as exc:                        # noqa: BLE001
        _abgebrochen = f"{type(exc).__name__}: {exc}"
        z.append(f"ABBRUCH: {_abgebrochen}")
        z.append("")
        z.append(traceback.format_exc())
    z.append("")

    # ---------------------------------------------------- Budgettabelle
    z.append("=" * 96)
    z.append("BUDGETTABELLE (aus den erfassten Instanzen)")
    z.append("=" * 96)
    for b in REGI:
        if b.richtung == "TOTAL":
            z.append(
                f"  {b.fenster:<9s} TOTAL   box_end {b.box_end:>5d}  "
                f"eintritt {b.eintritt_ist:>6d} / Soll {b.eintritt_soll:>6d}"
                f"   kein_raum stats {b.kein_raum_summe:>6d} / "
                f"Zerlegung {b.kein_raum_details:>6d}   "
                f"{'OK' if b.ist_valide else 'VERLETZT'}")
        else:
            z.append(
                f"  {b.fenster:<9s} {b.richtung:<5s}   box_end {b.box_end:>5d}"
                f"  eintritt {b.eintritt_ist:>6d} / Soll {b.eintritt_soll:>6d}"
                f" = Ausgaenge {b.summe_ausgaenge:>6d}"
                f"   kand_none {b.kand_none_summe:>4d} = Details "
                f"{b.kand_none_details:>4d}   "
                f"{'OK' if b.ist_valide else 'VERLETZT'}")
        if not b.ist_valide:
            for x in b.verletzungen:
                z.append(f"        VERLETZUNG ({b.fenster}/{b.richtung}): {x}")

    verletzt = [b for b in REGI if not b.ist_valide]
    z.append("")
    z.append(f"  Verletzte Budgets: {len(verletzt)} von {len(REGI)}")

    # ------------------------------------------------- Zaehler-Rohstand
    z.append("")
    z.append("=" * 96)
    z.append("ZAEHLER-ROHSTAND (F.ZAHL, nach dem Abbruch)")
    z.append("=" * 96)
    z.append(f"  Schluessel gesamt: {len(F.ZAHL)}")
    for fenster, *_ in F.FENSTER:
        z.append(f"  --- {fenster} ---")
        for site in (["eintritt"] + list(F.SITES_KAND)
                     + list(F.SITES_KAND_FILTER) + list(F.SITES_TERMINAL)
                     + list(F.SITES_RAUM) + list(F.SITES_G4)):
            a = F._n(fenster, site, "LONG")
            b = F._n(fenster, site, "SHORT")
            if a or b:
                z.append(f"      {site:<22s} L {a:>6d}  S {b:>6d}")
    # ------------------------------------------------------- Trichter
    z.append("")
    for fenster, *_ in F.FENSTER:
        z.append("=" * 96)
        z.append(f"TRICHTER {fenster}")
        z.append("=" * 96)
        z.extend(F._trichter(fenster))
        z.extend([""] + F._signaturen(fenster))
        z.append("")

    OUT.write_text("\n".join(z) + "\n", encoding="utf-8", newline="\n")
    print(f"ABBRUCH={_abgebrochen}")
    print(f"VERLETZT={len(verletzt)}/{len(REGI)}")
    print(f"DIAGNOSE-PROTOKOLL: {OUT}")


if __name__ == "__main__":
    main()
