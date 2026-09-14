# -*- coding: utf-8 -*-
"""E-34n — Typisierter Datenvertrag der MANUELLEN Sichtpruefung (Modus V019).

STATUS: ENTWURF / Dokumentation. Diese Datei wird NICHT ausgefuehrt; sie ist
der Pruefbogen fuer die visuelle Abnahme des v019-PNG-Satzes durch den
Anwender. Der Algorithmus gilt erst als markttauglich, wenn der menschliche
Blick die Reclaims bestaetigt (Mentor-Regel).

Anker (bit-verankert):
  Renderer   test/tmp_png_aug_sichttest.py
             SHA256 eccc4d77536ac1f8dc068ea2637ed7c2db99f49edee359a407cece4796285148
  Adapter    backtest_lab/phasen_regime_adapter.py
             SHA256 4f50b6b0829ad031613acb9edcfd79c6316a2082cda35152821bf010cb861e83
  Engine     test/tmp_kanten_engine_replay.py
             SHA256 4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a
  Protokoll  test/tmp_png_aug_sichttest_v019_out.txt
  Handoff    test/SESSION_HANDOFF.md (Commit a1ffe7d, §E-34m)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

StatusSichtpruefung = Literal["OFFEN", "BESTAETIGT", "BEANSTANDET"]
Richtung = Literal["LONG", "SHORT"]

RENDERER_SHA: Final[str] = (
    "eccc4d77536ac1f8dc068ea2637ed7c2db99f49edee359a407cece4796285148")
ADAPTER_SHA: Final[str] = (
    "4f50b6b0829ad031613acb9edcfd79c6316a2082cda35152821bf010cb861e83")
ENGINE_SHA: Final[str] = (
    "4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a")
HANDOFF_COMMIT: Final[str] = "a1ffe7d"
PROTOKOLL: Final[str] = "test/tmp_png_aug_sichttest_v019_out.txt"

# --- Sollwerte des Laufs (Protokoll; zugleich die 14 Fail-Loud-Asserts) ----
SOLL_GESAMT_TRADES: Final[int] = 23
SOLL_GESAMT_R: Final[float] = 82.614385
SOLL_H1: Final[tuple[int, float]] = (8, 38.919584)
SOLL_H2_TRADES: Final[int] = 15
SOLL_H2_R: Final[float] = 43.694801
SOLL_P9_R: Final[float] = 23.435111
SOLL_DELTA_RB: Final[float] = 34.798688
SOLL_NIVEAUWECHSEL: Final[int] = 66
SOLL_REFERENZ: Final[tuple[tuple[int, int], ...]] = ((980, 73),)

# --- Die 6 Zielzonen-Neuzugaenge (E-34k §B; Bars = Primaerschluessel) ------
# (signal_bar, kid, richtung, sig_bkz, entry_bkz, r)
#
# ACHTUNG Zeitbasis-Kanon: der BAR-INDEX ist der Primaerschluessel, die
# BKZ-Zeit ist sekundaer. Ein entry_bar wird hier BEWUSST nicht gefuehrt:
# AUG enthaelt Kalenderluecken (Wochenende 22./23.08.), daher ist entry_bar
# NICHT als bar + konstanter Zeitschritt ableitbar.
# Der Marker wird an t.bar (SIGNALBAR) gezeichnet; das Bildlabel lautet
# exakt "K<kid> <r>R\nbar <signal_bar>".
ZIELZONEN_TRADES: Final[tuple[
    tuple[int, int, Richtung, str, str, float], ...]] = (
    (1075, 62, "LONG", "25.08. 15:45", "25.08. 16:15", +1.475768),
    (1122, 73, "SHORT", "26.08. 04:30", "26.08. 04:45", +10.752473),
    (1211, 76, "SHORT", "27.08. 03:45", "27.08. 04:30", +2.539476),
    (1268, 76, "SHORT", "27.08. 18:00", "27.08. 18:15", -1.000000),
    (1272, 73, "SHORT", "27.08. 19:00", "27.08. 19:15", +1.254682),
    (1280, 76, "SHORT", "27.08. 21:00", "27.08. 21:15", +1.756410),
)


@dataclass(frozen=True, slots=True)
class PngSichtpruefungEintrag:
    """Freigabestatus eines generierten Chart-Bildes (manuelle Abnahme).

    Args:
        dateiname: Ausgabename im Ordner ``test/`` (praefix + Rolle).
        rolle: Panel-Rolle laut Renderer-Docstring.
        groesse_bytes: Erwartete Dateigroesse (Fingerabdruck des Satzes).
        fenster: Sichtbares Bar-Fenster des Panels.
        fokus: Was dieses Bild beweisen soll (Pruefauftrag).
        pruefpunkte: Konkrete Einzelchecks (fail-loud im Kopf des Pruefers).
        status: ``OFFEN`` / ``BESTAETIGT`` / ``BEANSTANDET``.
        bemerkung: Freitext des Anwenders (Befund, Abweichung, Bildstelle).
    """

    dateiname: str
    rolle: str
    groesse_bytes: int
    fenster: str
    fokus: str
    pruefpunkte: tuple[str, ...] = ()
    status: StatusSichtpruefung = "OFFEN"
    bemerkung: str = ""


# Reihenfolge = Satz 01..05. Groessen sind zugleich der Datei-Fingerabdruck.
SICHTPRUEFUNG_PNGS: Final[tuple[PngSichtpruefungEintrag, ...]] = (
    PngSichtpruefungEintrag(
        dateiname="aug_sichttest_v019_01_gesamt.png",
        rolle="01/05 GESAMT",
        groesse_bytes=2_140_255,
        fenster="Bars 0..1287",
        fokus="Gesamtbild; ALLE 23 Trades inkl. der 6 Zielzonen-Neuzugaenge; "
              "Referenz-Marker K73@980 (blass, gestrichelt, mfc=none).",
        pruefpunkte=(
            "Titel: '23 Trades / +82.6144 R | Baseline-Referenz 14 / +42.4510 R'.",
            "6 neue Kreise im Fenster 1075..1280 sind farbig GEFUELLT "
            "(gruen=LONG K62@1075; rot=SHORT K73@1122 und die vier K76/K73 "
            "vom 27.08.).",
            "Genau EIN blasser Referenz-Kreis bei Bar 980 (K73, grau, "
            "gestrichelt, mfc='none') -- nicht gefuellt.",
            "Genau EIN goldener G4-Ring (K77@1002) mit Label 'G4 RECLAIM'.",
            "K67-Label lautet 'K67 69.975 -> 69.870 (P9-Override) -> 69.899 *"
            "  Norm 69.9140' (fett, Rahmen #b8860b).",
            "X-Achse = Bar-Zeit BKZ OHNE Offset; Titel 'Bars 0..1287'.",
        ),
    ),
    PngSichtpruefungEintrag(
        dateiname="aug_sichttest_v019_02_h1_box.png",
        rolle="02/05 H1 BOX",
        groesse_bytes=896_312,
        fenster="Bars 0..664",
        fokus="H1-Invariante: 8 Trades / +38.919584 R -- identisch zu V018. "
              "Der Adapter greift erst ab Bar 848.",
        pruefpunkte=(
            "Titel: '8 Trades / +38.919584 R'.",
            "Letzter H1-Trade: K1@639 LONG (Grenztrade an der BKZ-Kalender-"
            "kante), entry 640 = 18.08. 22:00 BKZ, r = -1.000000.",
            "KEIN Zielzonen-Trade (alle 6 liegen bei bar >= 1075).",
            "Gegen V018 darf sich AUSSER dem Versionskuerzel 'V019' im Titel "
            "NICHTS unterscheiden (Dateigroesse +461 B = reiner Textdelta).",
        ),
    ),
    PngSichtpruefungEintrag(
        dateiname="aug_sichttest_v019_03_h2_phasen.png",
        rolle="03/05 H2 + PHASEN",
        groesse_bytes=1_778_529,
        fenster="Bars 620..1287",
        fokus="Die Zielzone: 15 H2-Trades / +43.6948 R. Traegt die 6 neuen "
              "Einstiege und das 27.08.-Cluster.",
        pruefpunkte=(
            "Titel: '15 Trades / +43.6948 R'.",
            "K62@1075 (gruen, LONG) links; K73@1122 (rot, SHORT) mit "
            "r +10.7525 -- der groesste Neuzugang.",
            "Cluster rechts: K76@1211 +2.54, K76@1268 -1.00, K73@1272 +1.25, "
            "K76@1280 +1.76 (vier Kreise dicht beieinander).",
            "Hintergrund-Zonen bleiben die HISTORISCHEN P6..P12 -- NICHT A1/A2 "
            "(siehe BEFUND_KOSMETIK 1).",
            "Letzte Statistikzeile aufklappen: 'Engine §72 ... H1 8 Trades / "
            "+38.919584 R (vorher 8 / +38.964262 R)'.",
        ),
    ),
    PngSichtpruefungEintrag(
        dateiname="aug_sichttest_v019_04_p9_regime.png",
        rolle="04/05 P9-REGIME",
        groesse_bytes=1_195_846,
        fenster="Bars 820..1045",
        fokus="P9-Detail: Override 69.8700 nur in 848..1020, Quartett, "
              "Grenzlinien 848/1021. Enthaelt KEINEN Zielzonen-Trade.",
        pruefpunkte=(
            "Titel: 'Niveau-Override 69.8700 / Boden K77 deklariert 68.4000 | "
            "Ziel 68.3700'.",
            "Vier Quartett-Kreise: K67@903, K67@980, K73@981, K67@1020 -- "
            "Summe +19.806095 R in der Statistik.",
            "G4-Ring K77@1002 gold.",
            "Rote Zielzone 1033+ liegt nur ANGESCHNITTEN am rechten Rand "
            "(Fenster endet 1045) -- dort ist KEIN Neuzugang zu erwarten.",
        ),
    ),
    PngSichtpruefungEintrag(
        dateiname="aug_sichttest_v019_05_kantenkarte.png",
        rolle="05/05 KANTEN-LANDKARTE",
        groesse_bytes=2_135_870,
        fenster="Bars 0..1287",
        fokus="Kantenlandkarte: 59 Kanten + 14 Seeds, kausale Linien "
              "(basis_bei(k)) und Preis-Labels.",
        pruefpunkte=(
            "Titel: '59 Kanten + 14 Seeds'.",
            "Preis an der Linie (Pflicht): jedes K-Label traegt den kausalen "
            "Preis; Wechsler 'v0 -> v1 *' (41 Linien, Protokoll).",
            "Seeds mit 's<kid> <preis>' (Kreuzmarker, kleiner).",
            "Norm-Zitat: K67 / K73 / K77 / K82 tragen 'Norm <wert>' NUR als "
            "Zitat (Option b) -- K82 zeigt 'Norm 67.6355' bei kausal 67.5530.",
            "15 Trade-Kreise (H2) + 8 (H1) = 23 farbig gefuellt.",
        ),
    ),
)

# --- Bekannte kosmetische Befunde -- VOR der Abnahme zu lesen ---------------
BEFUND_KOSMETIK: Final[tuple[str, ...]] = (
    "1. ZONEN-WIDERSPRUCH (kosmetisch, KEIN Logikfehler): shade_phases "
    "zeichnet die HISTORISCHEN Zonen P6..P12 aus dem Literal-Dict PHASEN "
    "(Z. 1012..1020) und die Luecken aus LECKEN (Z. 1021) -- NICHT die "
    "V019-Segmente A1 (1033..1173) / A2 (1174..1287). Folge: die neuen "
    "Trades liegen optisch teils in rot schraffierten 'Luecke (BLOCKIERT)'-"
    "Baendern (LECKEN 1135..1170 in A1; 1273..1287 in A2) bzw. in blass-blauen "
    "'nicht aktiv'-Zonen (P10 1030..1075, P11 1082..1134). Die Bildunterschrift "
    "beschreibt damit den ALTEN Vertrag. Sichturteil: nur die Trade-Geometrie "
    "und die Kantenlinien bewerten, NICHT die Zonenfarbe.",
    "2. K82-DOPPELROLLE (dokumentiert, korrekt): K82 ist Boden in A1 UND A2 "
    "mit zwei Provenienzen (67.5350 / 67.5530), traegt aber die P12-RESERVE-"
    "Norm 67.6355. Das Label 'Norm 67.6355' ist Zitat und daher richtig, wirkt "
    "aber neben dem kausalen 67.5530 wie ein Widerspruch.",
    "3. LABEL-DICHTE 27.08.: ANNOT_OFFSET deckt nur (1020,67)/(980,67) ab. "
    "Die vier Kreise 1211/1268/1272/1280 liegen innerhalb von 4 Bars Abstand "
    "-- ueberlappende Textboxen sind erwartbar und kein Fehler.",
    "4. PANEL 02 BYTE-DELTA: V018 895.851 B -> V019 896.312 B (+461 B) stammt "
    "ausschliesslich aus dem Versionskuerzel 'V018'->'V019' im Titel/Statistik-"
    "text (laenger). Die H1-Werte sind unveraendert. Groessere Abweichungen "
    "waeren ein Regressionsbefund.",
    "5. PANEL 04 OHNE ZIELZONE: Das Fenster 820..1045 enthaelt keinen der 6 "
    "Neuzugaenge (alle >= 1075). Erwartungsfalle -- hier NICHTS Neues suchen.",
)


@dataclass(frozen=True, slots=True)
class KennzahlenSichtpruefung:
    """Gesamtbilanz der visuellen Abnahme (Abschluss-Urkunde E-34n)."""

    pngs: tuple[PngSichtpruefungEintrag, ...] = SICHTPRUEFUNG_PNGS
    kennzahlen_bestaetigt: bool = False
    kosmetik_akzeptiert: bool = False
    gesamtsieg: Literal["OFFEN", "JA", "NEIN"] = "OFFEN"
    anwender: str = ""
    datum: str = ""


if __name__ == "__main__":  # pragma: no cover -- reine Anzeige, kein Lauf
    print(f"Renderer {RENDERER_SHA[:16]}...  (Commit {HANDOFF_COMMIT})")
    for _e in SICHTPRUEFUNG_PNGS:
        print(f"  [{_e.status:<11}] {_e.dateiname}  {_e.groesse_bytes:,} B"
              f"  {_e.fenster}  -- {_e.rolle}")
    print("\nKosmetische Befunde:")
    for _z in BEFUND_KOSMETIK:
        print(f"  {_z}")
