# -*- coding: utf-8 -*-
"""S3.3 -- Byte-exakter Renderer-Patch (V018-Registrierung + Zeitbasis-Nomenklatur).

Arbeitet auf BYTE-Ebene: die Datei ``test/tmp_png_aug_sichttest.py`` ist LF-kodiert
(kein CRLF) -- das wird vor und nach dem Patch verifiziert, damit keine
Zeilendenen-Korruption entsteht (Lehre aus S3.2, wo die Engine CRLF ist).

Regeln:
  * Jede Ersetzung muss EXAKT EINMAL vorkommen (sonst Abbruch -> Fail-Loud).
  * V01..V017-Ausgabetexte bleiben byte-identisch: V017-Zweige behalten ihren
    Literaltext; V018 bekommt eigene Zweige ueber die Diskriminatoren
    ``_NEU`` (V017 oder V018) und ``_VTAG`` ("V017"/"V018").
  Niederschreiben: ``test/_tmp_s3_renderer_patch.py`` (Artefakt, test/ ist
  gitignored -> Arretierung urkundlich per SHA256).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_png_aug_sichttest.py"

# ------------------------------------------------------------------ Textblöcke
OLD_V018_DOC = """    End-Mittel). Satz ``aug_sichttest_v017_01..05.png``, Protokoll
    ``..._v017_out.txt``.
  Alle Modi teilen denselben Code und denselben RAM-Patch; umgeschaltet wird"""

NEW_V018_DOC = """    End-Mittel). Satz ``aug_sichttest_v017_01..05.png``, Protokoll
    ``..._v017_out.txt``.
  * ``KONFIGURATION_V018`` -- v0.23: S3-Zeitbasis-Kanon (Weg A). Identische
    Motordrehungen wie V017, aber die Engine-SQL rechnet auf der
    Broker-Kerzen-Zeit (BKZ = ``time AT TIME ZONE 'UTC'``) statt der
    Berlin-Projektion. Die Kalenderkante ``box_end`` wird dadurch dynamisch
    neu abgeleitet (AUG: 644 statt 640); der Grenztrade K1@640 (r = -1.000000)
    kippt von H2 nach H1 (H1 7 -> 8 Trades, H2 10 -> 9). Satz
    ``aug_sichttest_v018_01..05.png``, Protokoll ``..._v018_out.txt``.
  Alle Modi teilen denselben Code und denselben RAM-Patch; umgeschaltet wird"""

REPLACEMENTS: list[tuple[str, str]] = [
    # --- Kopf-Docstring: Zeitbasis-Kanon (BKZ statt "Wanduhr") -------------
    (
        """  * Zeitachse = BAR-ZEIT (Engine-Wanduhr d["ts"]). Sie entspricht exakt den
    Bar-Zeitstempeln der Trades/Tabellen (DB-Spalte `time`, Anzeige +02:00)
    und dem M15-Chart. KEIN Offset (AXIS_TZ_OFFSET_H = 0). Der Bar-Index
    bleibt Primaerschluessel.""",
        """  * Zeitachse = BAR-ZEIT (Broker-Kerzen-Zeit/BKZ, d["ts"] = `time AT TIME
    ZONE 'UTC'`, docs/ZEITBASIS_KANON.md). Sie entspricht exakt den
    Bar-Zeitstempeln der Trades/Tabellen und dem M15-Chart. KEIN Offset
    (AXIS_TZ_OFFSET_H = 0). Der Bar-Index bleibt Primaerschluessel.""",
    ),
    (OLD_V018_DOC, NEW_V018_DOC),
    # --- Kopf-Docstring: Satz-Zeile ---------------------------------------
    (
        "  02_h1_box      Bars 0..660    H1-Box (V01..V016: 8 | V017: 7 Trades)",
        "  02_h1_box      Bars 0..box_end+20  H1-Box (V01..V016: 8 | "
        "V017: 7 | V018: 8)",
    ),
    # --- Kopf-Docstring: Abschnitt S3 anhaengen ---------------------------
    (
        "  * ZAEHLER (§72.8): ``niveauwechsel_gesamt`` ist ein Fail-Loud-Sollwert.",
        "  * ZAEHLER (§72.8): ``niveauwechsel_gesamt`` ist ein Fail-Loud-Sollwert.\n"
        "\n"
        "Abschnitt S3 (Zeitbasis-Kanon, Modus V018 -- docs/ZEITBASIS_KANON.md):\n"
        "  * BKZ = ``time AT TIME ZONE 'UTC'`` ist die EINZIGE Rechenbasis. Die\n"
        "    frueher genutzte Berlin-Projektion entfaellt ersatzlos (Weg A).\n"
        "  * ``box_end`` ist KEINE Bar-Konstante mehr, sondern die dynamische\n"
        "    Kalenderkante ``searchsorted(ts_bkz, \"2026-08-19\")`` (AUG = 644).\n"
        "  * V018 arretiert neu: H1 (8 / +38.919584 R), H2 (9 / +26.915992 R),\n"
        "    R1 (17 / +65.835576 R). Der Grenztrade K1@640 (r = -1.000000) kippt\n"
        "    von H2 nach H1 -- alle uebrigen 16 Trades partitionieren wie V017.",
    ),
    # --- AdapterMode-Literal ----------------------------------------------
    (
        'AdapterMode = Literal["V01", "V014", "V015", "V016", "V017"]',
        'AdapterMode = Literal["V01", "V014", "V015", "V016", "V017", "V018"]',
    ),
    # --- Docstrings --------------------------------------------------------
    (
        "            ``pivot_bar + 2``). V016 = 205, V017 = 66 (§72.8).",
        "            ``pivot_bar + 2``). V016 = 205, V017/V018 = 66 (§72.8).",
    ),
    (
        "    # Defaults reproduzieren V01..V016 unveraendert; nur V017 setzt sie um.",
        "    # Defaults reproduzieren V01..V016 unveraendert; V017/V018 setzen sie um.",
    ),
    # --- KONFIGURATION_V018 + Registrierung -------------------------------
    (
        """    niveauwechsel_gesamt=66,
    niveauwechsel_baseline=205,
)

_KONFIGURATIONEN = {"V01": KONFIGURATION_V01, "V014": KONFIGURATION_V014,
                    "V015": KONFIGURATION_V015, "V016": KONFIGURATION_V016,
                    "V017": KONFIGURATION_V017}""",
        """    niveauwechsel_gesamt=66,
    niveauwechsel_baseline=205,
)

# V018 = S3-Zeitbasis-Kanon (Weg A). Identische Motordrehungen wie V017; die
# Engine-SQL rechnet auf BKZ (UTC) statt der Berlin-Projektion. Dadurch wandert
# box_end dynamisch auf 644 (searchsorted-Kalenderkante) und der Grenztrade
# K1@640 (r = -1.000000) kippt von H2 nach H1. Eigener Praefix: der arretierte
# v017-Satz bleibt unberuehrt. Reproduktion von V017 erfordert zwingend
# ``--engine test/_tmp_backup_engine_pre_v018.py`` (Fail-Loud-Guard unten).
KONFIGURATION_V018: Final[RendererKonfiguration] = RendererKonfiguration(
    mode="V018",
    ausgabe_praefix="aug_sichttest_v018_",
    protokoll_datei="test/tmp_png_aug_sichttest_v018_out.txt",
    ziel_trades_gesamt=17,
    ziel_r_gesamt=65.835576,
    ziel_r_h1=38.919584,
    ziel_r_h2=26.915992,
    ziel_p9_beitrag=23.435111,
    k67_override_aktiv=True,
    niveau_override_wert=K67_OVERRIDE_69_87,
    alt_trades_einblenden=True,
    quartett_bars=QUARTETT_V014_BARS,
    g4_aktiv=True,
    auflagen_aktiv=True,
    # --- §72/S3: neu arretierte Sollwerte der Engine-Generation V018 --------
    # V0 und R_B sind zeitbasis-invariant (identisch zu V017); H1/H2 kippen um
    # den Grenztrade K1@640 (-1.000000 R): H1 7 -> 8, H2 10 -> 9.
    ziel_v0_r=42.450970,
    ziel_v1_basis_trades=14,
    ziel_v1_basis_r=47.815697,
    ziel_h1_trades=8,
    ziel_delta_rb=18.019879,
    # (1002, 77) liefert die G4-Regel; Altsatz-Garantie wie V017 geoeffnet.
    neu_basis_soll=((903, 67), (980, 67), (981, 73), (1002, 77)),
    referenz_soll=((980, 73),),
    quartett_r_soll=((903, 4.119775), (980, 9.987676), (981, 2.695488),
                     (1020, 3.003157)),
    quartett_r_summe_soll=19.806095,
    niveauwechsel_gesamt=66,
    niveauwechsel_baseline=205,
)

_KONFIGURATIONEN = {"V01": KONFIGURATION_V01, "V014": KONFIGURATION_V014,
                    "V015": KONFIGURATION_V015, "V016": KONFIGURATION_V016,
                    "V017": KONFIGURATION_V017, "V018": KONFIGURATION_V018}""",
    ),
    # --- Generations-Diskriminatoren --------------------------------------
    (
        """# ------------------------------- V017: eigene Engine-Generation (§72) -----
# Eigener Diskriminator -- NICHT an _AUFL haengen: V016 traegt dieselben
# Auflagen und muss byte-identisch reproduzierbar bleiben (arretierter Satz).
_V17: Final[bool] = KONF.mode == "V017"
# Versionslabel (Adapter + Engine-Generation) fuer Titel und Protokoll.
# In V01..V016 exakt der bisherige Wortlaut -> Bytes unveraendert.
_VER_TEXT: Final[str] = ("v0.17 (Kanten-Extremum + M6-Heilung)" if _V17
                         else ("v0.16 (G4 + A-1..A-4)" if _AUFL
                               else ("v0.15 G4" if KONF.g4_aktiv
                                     else ("v0.14" if KONF.k67_override_aktiv
                                           else "v0.1"))))""",
        """# -------------------- V017/V018: eigene Engine-Generation (§72 / S3) -------
# Eigener Diskriminator -- NICHT an _AUFL haengen: V016 traegt dieselben
# Auflagen und muss byte-identisch reproduzierbar bleiben (arretierter Satz).
# V017 und V018 teilen die Motordrehungen (Kanten-Extremum + M6-Heilung) und
# unterscheiden sich AUSSCHLIESSLICH in der Zeitbasis (S3: BKZ/UTC statt
# Berlin) und den daraus folgenden Sollwerten. Alle Text-/Verhaltenszweige der
# Generation haengen deshalb an _NEU.
_V17: Final[bool] = KONF.mode == "V017"
_V18: Final[bool] = KONF.mode == "V018"
_NEU: Final[bool] = _V17 or _V18
# Versionskuerzel fuer Titel/Annotationen (V017 bzw. V018).
_VTAG: Final[str] = "V018" if _V18 else "V017"
# Versionslabel (Adapter + Engine-Generation) fuer Titel und Protokoll.
# In V01..V016 exakt der bisherige Wortlaut -> Bytes unveraendert.
_VER_TEXT: Final[str] = (
    "v0.18 (BKZ/UTC + Kanten-Extremum + M6-Heilung)" if _V18
    else ("v0.17 (Kanten-Extremum + M6-Heilung)" if _V17
          else ("v0.16 (G4 + A-1..A-4)" if _AUFL
                else ("v0.15 G4" if KONF.g4_aktiv
                      else ("v0.14" if KONF.k67_override_aktiv
                            else "v0.1")))))""",
    ),
    # --- Fail-Loud-Guard der Generationen (nach box_end) ------------------
    (
        """box_end = scan["box_end_bar"]
scan["box_end_bar"] = n                       # Voll-Lauf (arretierte Basis)""",
        """box_end = scan["box_end_bar"]
# ---- Fail-Loud-Guard der Generationen (§72.1 Zero-Trust, S3) --------------
# V017 ist an die V017-Engine (box_end == 640) gebunden; die V018-Engine
# liefert box_end == 644 und liesse V017 sonst in einem kryptischen Folge-
# Assert brechen. Hier ein klarer Abbruch mit Rueckweg.
if KONF.mode == "V017" and box_end != 640:
    raise SystemExit(
        f"Modus V017 erfordert die V017-Engine (box_end 640), geladen wurde "
        f"box_end={box_end} ({ENGINE_NAME} {ENGINE_SHA[:16]}...). "
        "Rueckweg/Gegenprobe: --engine test/_tmp_backup_engine_pre_v018.py")
if KONF.mode == "V018" and box_end != 644:
    raise SystemExit(
        f"Modus V018 erfordert die V018-Engine (BKZ/UTC, box_end 644), "
        f"geladen wurde box_end={box_end} ({ENGINE_NAME} "
        f"{ENGINE_SHA[:16]}...).")
scan["box_end_bar"] = n                       # Voll-Lauf (arretierte Basis)""",
    ),
    # --- Zeitachsen-Kommentar (Render) ------------------------------------
    (
        """# Zeitbasis der Achsen (lesend, Engine-unberuehrt):
# Die DB-Spalte `time` (timestamptz) zeigt die Bar-Zeit als Wanduhr mit
# +02:00-Anzeige (Europe/Berlin) -- genau diese Bar-Zeitstempel fuehren die
# Trade-Tabellen UND der M15-Chart. Die Engine-SQL (Zeile 600) liefert
# denselben Wert als naives ts. Deshalb wird die Achse OHNE Offset
# gezeichnet, damit sie zu den Bar-Zeitstempeln passt.""",
        """# Zeitbasis der Achsen (lesend, Engine-unberuehrt):
# Die Engine-SQL liefert mit ``time AT TIME ZONE 'UTC'`` die Broker-Kerzen-
# Zeit (BKZ, docs/ZEITBASIS_KANON.md) als naives ts -- exakt die Bar-
# Zeitstempel, die auch die Trade-Tabellen UND der M15-Chart fuehren.
# Deshalb wird die Achse OHNE Offset gezeichnet.""",
    ),
    (
        '    """Zeitachse = Bar-Zeit (Wanduhr, ohne Offset); Bar-Index primaer.',
        '    """Zeitachse = Bar-Zeit (BKZ, ohne Offset); Bar-Index primaer.',
    ),
    (
        '    ax.set_xlabel("Bar-Zeit (Engine-Wanduhr, M15) | Bar-Index primaer",',
        '    ax.set_xlabel("Bar-Zeit (BKZ, M15) | Bar-Index primaer",',
    ),
    # --- Niveauwechsel-Kennzahl -------------------------------------------
    (
        """# §72.8: Fail-Loud-Kennzahl -- V016 = 205, V017 = 66.""",
        """# §72.8: Fail-Loud-Kennzahl -- V016 = 205, V017/V018 = 66.""",
    ),
    (
        """# §72.8: Protokollzeile der Niveauwechsel-Kennzahl. Nur in V017 wird der
# Wortlaut erweitert; V01..V016 behalten ihre Zeile (Byte-Identitaet).""",
        """# §72.8: Protokollzeile der Niveauwechsel-Kennzahl. Ab V017/V018 wird der
# Wortlaut erweitert; V01..V016 behalten ihre Zeile (Byte-Identitaet).""",
    ),
    (
        """    f"(Baseline {KONF.niveauwechsel_baseline})" if _V17 else
    f"Preiswechsel-Linien (Label 'v0 -> v1 *'): {len(WECHSEL)}")""",
        """    f"(Baseline {KONF.niveauwechsel_baseline})" if _NEU else
    f"Preiswechsel-Linien (Label 'v0 -> v1 *'): {len(WECHSEL)}")""",
    ),
    # --- _zeilen_extra -----------------------------------------------------
    (
        """    Ab Modus V017 kommt eine Zeile zur Engine-Generation hinzu (§72.4/§72.8).""",
        """    Ab V017/V018 kommt eine Zeile zur Engine-Generation hinzu (§72.4/§72.8).""",
    ),
    (
        """        f"H1 {len(h1_1)} Trades / {sum(t.r for t in h1_1):+.6f} R "
        f"(vorher 8 / +38.964262 R)",
    ] if _V17 else []) + G4_ZEILEN""",
        """        f"H1 {len(h1_1)} Trades / {sum(t.r for t in h1_1):+.6f} R "
        f"(vorher {7 if _V18 else 8} / "
        f"{'+39.919584' if _V18 else '+38.964262'} R)",
    ] if _NEU else []) + G4_ZEILEN""",
    ),
    # --- Panel 01: Adapter-Titel ------------------------------------------
    (
        """    _ad = ("Engine V017 (Kanten-Extremum + M6-Heilung): P9-Override + Regel"
           if _V17 else""",
        """    _ad = (f"Engine {_VTAG} (Kanten-Extremum + M6-Heilung): "
           f"P9-Override + Regel" if _NEU else""",
    ),
    (
        """    # §72.8: Niveauwechsel-Kennzahl. Wortlaut nur in V017 neu -- V01..V016
    # behalten exakt ihre bisherige Zeile (Byte-Identitaet).
    _h1_mark = ("<- SOLL V017 (neu arretiert, Engine-Extremum)" if _V17
                else "<- arretierte Baseline (bit-identisch)")""",
        """    # §72.8: Niveauwechsel-Kennzahl. Wortlaut nur ab V017 neu -- V01..V016
    # behalten exakt ihre bisherige Zeile (Byte-Identitaet).
    _h1_mark = (f"<- SOLL {_VTAG} (neu arretiert, Engine-Extremum)" if _NEU
                else "<- arretierte Baseline (bit-identisch)")""",
    ),
    (
        """               f"(Baseline {KONF.niveauwechsel_baseline})" if _V17
               else f"Preiswechsel-Linien (*): {len(WECHSEL)}")""",
        """               f"(Baseline {KONF.niveauwechsel_baseline})" if _NEU
               else f"Preiswechsel-Linien (*): {len(WECHSEL)}")""",
    ),
    # --- Panel 02 ----------------------------------------------------------
    (
        """    # §72.5: H1 ist in V017 NEU arretiert (7 Trades). Wortlaut nur dort neu.
    _p02_note = ("Engine V017 (Kanten-Extremum, H1 neu arretiert)" if _V17
                 else "arretierte Baseline")
    _h1_soll = ("<- SOLL V017 (neu arretiert)" if _V17
                else "<- SOLL arretiert (bit-identisch)")""",
        """    # §72.5: H1 ist ab V017 NEU arretiert. Wortlaut nur dort neu.
    _p02_note = (f"Engine {_VTAG} (Kanten-Extremum, H1 neu arretiert)"
                 if _NEU else "arretierte Baseline")
    _h1_soll = (f"<- SOLL {_VTAG} (neu arretiert)" if _NEU
                else "<- SOLL arretiert (bit-identisch)")""",
    ),
    (
        """        + ("" if not _V17 else
           " In V017 wandert H1 dennoch, weil die KANTENFORMEL selbst im"
           " Motor liegt (§72.5) -- der Adapter bleibt MAKRO."),""",
        """        + ("" if not _NEU else
           f" In {_VTAG} wandert H1 dennoch, weil die KANTENFORMEL selbst im"
           " Motor liegt (§72.5) -- der Adapter bleibt MAKRO."),""",
    ),
    # --- Panel 03: P9-Benchmark-Zeile + Transition-Park -------------------
    (
        """        _p9z = (("P9-Benchmark v0.17 (Engine-Extremum): " if _V17 else
                 ("P9-Benchmark v0.15 G4: " if KONF.g4_aktiv
                  else "P9-Benchmark v0.14 (Quartett): ")) + " | ".join(""",
        """        _p9z = (("P9-Benchmark v0.18 (BKZ/UTC, Engine-Extremum): "
                 if _V18 else
                 "P9-Benchmark v0.17 (Engine-Extremum): " if _V17 else
                 ("P9-Benchmark v0.15 G4: " if KONF.g4_aktiv
                  else "P9-Benchmark v0.14 (Quartett): ")) + " | ".join(""",
    ),
    (
        """        # §72.5: Der Transition-Park wandert in V017 mit (K16@715 -> @714).""",
        """        # §72.5: Der Transition-Park wandert ab V017 mit (K16@715 -> @714).""",
    ),
    (
        """        (("Transition-Park 640-847 (MAKRO, gegenueber Adapter unberuehrt): "
          + ", ".join(f"K{t.kid}@{t.bar}" for t in sorted(
              (x for x in h2_1 if x.bar <= 847), key=lambda x: x.bar))
          + " = " + f"{len([x for x in h2_1 if x.bar <= 847])} / "
          + f"{sum(x.r for x in h2_1 if x.bar <= 847):+.4f} R") if _V17 else""",
        """        ((f"Transition-Park {box_end}-847 (MAKRO, gegenueber Adapter "
          "unberuehrt): "
          + ", ".join(f"K{t.kid}@{t.bar}" for t in sorted(
              (x for x in h2_1 if x.bar <= 847), key=lambda x: x.bar))
          + " = " + f"{len([x for x in h2_1 if x.bar <= 847])} / "
          + f"{sum(x.r for x in h2_1 if x.bar <= 847):+.4f} R") if _NEU else""",
    ),
    # --- Panel 04 ----------------------------------------------------------
    (
        """        _v04 = ("Engine V017 (Kanten-Extremum + M6-Heilung): P9 mit "
                "K67-Override + Boden" if _V17 else""",
        """        _v04 = (f"Engine {_VTAG} (Kanten-Extremum + M6-Heilung): P9 mit "
                f"K67-Override + Boden" if _NEU else""",
    ),
    (
        """        # §72.2: K67 traegt in V017 das kausale Extremum -- die beiden""",
        """        # §72.2: K67 traegt ab V017 das kausale Extremum -- die beiden""",
    ),
    (
        """                  f"Hook 1 wird gegenstandslos" if _V17 else""",
        """                  f"Hook 1 wird gegenstandslos" if _NEU else""",
    ),
    (
        """                   f"Grenzlinien 848 / 1021 (Regel 15)" if _V17 else""",
        """                   f"Grenzlinien 848 / 1021 (Regel 15)" if _NEU else""",
    ),
    (
        """                   f"(§72.6) | K59@853 entfaellt" if _V17 else""",
        """                   f"(§72.6) | K59@853 entfaellt" if _NEU else""",
    ),
    # --- Protokoll-Kopf ----------------------------------------------------
    (
        """# §72.4: urkundliche Kennung der geladenen Engine (auch im Probe-Lauf).
# Beschluss P-2: die beiden Kennungs-Zeilen erscheinen AUSSCHLIESSLICH im
# Modus V017 -- V01..V016 behalten ihr arretiertes Protokoll
# (tmp_png_aug_sichttest_v016_out.txt, 5.520 B / 2969723c...).
if _V17:""",
        """# §72.4: urkundliche Kennung der geladenen Engine (auch im Probe-Lauf).
# Beschluss P-2: die Kennungs-Zeilen erscheinen NUR in der Engine-Generation
# (V017/V018) -- V01..V016 behalten ihr arretiertes Protokoll
# (tmp_png_aug_sichttest_v016_out.txt, 5.520 B / 2969723c...).
if _NEU:""",
    ),
]


def main() -> int:
    raw = P.read_bytes()
    assert raw.count(b"\r\n") == 0, "Renderer ist nicht LF-kodiert -- Abbruch."
    text = raw.decode("utf-8")
    for i, (old, new) in enumerate(REPLACEMENTS, 1):
        n = text.count(old)
        assert n == 1, f"Ersetzung {i}: {n} Treffer statt 1 fuer:\n{old[:80]!r}"
        assert old != new, f"Ersetzung {i}: old == new."
        text = text.replace(old, new)
    out = text.encode("utf-8")
    P.write_bytes(out)
    assert P.read_bytes().count(b"\r\n") == 0, "CRLF nach Patch!"
    # Resttreffer-Kontrolle: kein konsumierbares _V17 im Renderer-Text mehr,
    # das nicht bewusst V017-spezifisch ist (nur _V17 selbst + _NEU-Def).
    rest = text.count("_V17")
    print(f"OK -- {len(REPLACEMENTS)} Ersetzungen, {len(out):,} B, "
          f"_V17-Resttreffer: {rest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
