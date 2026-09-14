# -*- coding: utf-8 -*-
"""READ-ONLY: NEUER PNG-Satz fuer den Sichttest ueber AUG KOMPLETT.

Erzeugt 5 Grafiken (Bars 0..1287) mit dem H2-Phasen-Regime-Adapter und der
arretierten Baseline als Referenz. Die Engine-Datei bleibt unberuehrt; der
Adapter wird per Namens-Injektion in den RAM-Patch gebunden.

SECHS MODI (ein Vertrag, sechs Instanzen -- Spiegelspez Abschnitt 66.5,
§70, §72 und E-34):
  * ``KONFIGURATION_V01``  -- Adapter v0.1 (K73-Umweg, arretierte Baseline).
    Satz ``aug_sichttest_01..05.png``, Protokoll ``..._out.txt``.
  * ``KONFIGURATION_V014`` -- P9 mit K67-Niveau-Override 69.8700.
    Satz ``aug_sichttest_v014_01..05.png``, Protokoll ``..._v014_out.txt``.
  * ``KONFIGURATION_V015`` -- v0.20: P9-Override UND generische
    Phasenboden-Regel G4 (§69.8), engine-nativ (Route A). Satz
    ``aug_sichttest_v015_01..05.png``, Protokoll ``..._v015_out.txt``.
  * ``KONFIGURATION_V016`` -- v0.21: wie V015, zusaetzlich bereinigt um
    die Auflagen A-1..A-4 (Diamond-Marker, 25er-Raster P04,
    K67-Annotations-Offsets, Rand-Abstand der Zonenlabels). Satz
    ``aug_sichttest_v016_01..05.png``, Protokoll ``..._v016_out.txt``.
  * ``KONFIGURATION_V017`` -- v0.22: neue ENGINE-Generation (§72). Die
    kausale Kantenlinie ist das EXTREMUM der bestaetigten Dochte (OBEN =
    tiefstes Hoch, UNTEN = hoechstes Tief) statt des Mittelwerts, und der
    M6-Kausalitaetspfad ist geheilt (Rueckfall auf den ersten Docht statt
    End-Mittel). Satz ``aug_sichttest_v017_01..05.png``, Protokoll
    ``..._v017_out.txt``.
  * ``KONFIGURATION_V018`` -- v0.23: S3-Zeitbasis-Kanon (Weg A). Identische
    Motordrehungen wie V017, aber die Engine-SQL rechnet auf der
    Broker-Kerzen-Zeit (BKZ = ``time AT TIME ZONE 'UTC'``) statt der
    Berlin-Projektion. Die Kalenderkante ``box_end`` wird dadurch dynamisch
    neu abgeleitet (AUG: 644 statt 640); der Grenztrade K1@640 (r = -1.000000)
    kippt von H2 nach H1 (H1 7 -> 8 Trades, H2 10 -> 9). Satz
    ``aug_sichttest_v018_01..05.png``, Protokoll ``..._v018_out.txt``.
  * ``KONFIGURATION_V019`` -- v0.24: endogene Segmentbildung (E-34..E-34i).
    Die Zielzone A1/A2 wird nicht mehr hart verdrahtet, sondern aus der
    kausalen Regel abgeleitet (Plateau [41; 114], Referenz 77). Neben dem
    Adapter ``ADAPTER_V019`` (P9 + A1 + A2) greift ausschliesslich in diesem
    Modus das Zielzonen-Patchset ZP-4 (A_UEB1/A_VC/A_M6L/A_SB) in der
    Engine. Satz ``aug_sichttest_v019_01..05.png``, Protokoll
    ``..._v019_out.txt``.
  Alle Modi teilen denselben Code und denselben RAM-Patch; umgeschaltet wird
  ausschliesslich die gebundene ``PhasenRegimeAdapter``-Instanz. Die Asserts
  ziehen die Sollwerte aus der aktiven Konfiguration mit (FAIL-LOUD, es gibt
  keinen Abschalter).

Konvention (verankert 2026-09-09, erweitert 2026-09-10 und 2026-09-10,
FIX fuer alle Sichtpruefungs-Grafiken -- Spiegelspez:
reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md Abschnitt 54
plus Abschnitt 66):
  * Statistik MITTIG im unteren Panel.
  * Legende OBEN LINKS im Chart.
  * Alle Panels in KERZEN (keine Close-Linie).
  * Zeitachse = BAR-ZEIT (Broker-Kerzen-Zeit/BKZ, d["ts"] = `time AT TIME
    ZONE 'UTC'`, docs/ZEITBASIS_KANON.md). Sie entspricht exakt den
    Bar-Zeitstempeln der Trades/Tabellen und dem M15-Chart. KEIN Offset
    (AXIS_TZ_OFFSET_H = 0). Der Bar-Index bleibt Primaerschluessel.
  * Trade-Kreise sind IMMER farbig gefuellt (rot=SHORT, gruen=LONG);
    H1 = kleiner/duenner Rand, H2 = groesser/dicker Rand.
  * Kantenlinien werden KAUSAL gezeichnet: basis_bei(k) je Bar (Stufe),
    maskiert vor Pivot + 2. Die statische Provenienz-Basis e.basis wird
    NICHT mehr als Linienniveau verwendet (nur noch als Auditzitat).
  * K-NAME TRAEGT DEN PREIS: an jeder Kante steht "K<kid> <preis>".
  * PREISAENDERUNG IST PFLICHTKENNZEICHNUNG: aendert sich der kausale Preis
    entlang der Linie, wird das Label zu "K<kid> <v_start> -> <v_ende> *"
    (fett, Rahmen in C_CHG) und jeder Wechselpunkt erhaelt seinen Preis als
    Kleintext. Die Anzahl markierter Linien steht im Statistikblock.
  * Sperr-Marker (violett): x = Q29-Quartil, ^ = M6-Aussenwand.
  * Titel fuehren die Bar-Grenzen als "Bars 0..1287" (n - 1).

Abschnitt 66 (Amendment v0.16, nur Modus V014):
  * PLATEAU-SYNTAX (§66.2): Kanten mit niveau_override tragen
    "K<kid> <native_start> -> <override> (<phase>-Override) -> <native_ende> *"
    (der *-Marker ist dort verpflichtend), gefolgt vom Norm-Zitat.
  * OVERRIDE-ZONEN (§66.3, neue Regel 15): Grenzlinien bei start_bar und
    end_bar + 1 in C_CHG mit Kleintext -- KEIN ueberlagerndes axvspan.
  * REFERENZ-TRADES (§66.4, Ausnahme zu Regel 10): die im V014-Lauf
    entfallenen V01-Trades (Mengendifferenz V1_basis \\ V1_aktiv) werden
    gestrichelt, mfc="none", grau, alpha 0.45 gezeichnet. Handelnde Trades
    beider Modi bleiben farbig gefuellt (mfc=col).
  * NORM-QUELLE (§66.1, F1): der deklarierte Gesamtbestand
    (P9 + P12_RESERVE) -- nicht nur die aktiven Segmente.

Abschnitt 72 (Generationswechsel V017, Modus V017):
  * KANTEN-EXTREMUM (§72.2): ``basis_bei(k)`` liefert OBEN das Minimum und
    UNTEN das Maximum der bestaetigten Dochte -- die institutionelle
    Liquiditaetsgrenze, nicht den Schwerpunkt. Gegenueber V016 sinken die
    sichtbaren Niveauwechsel von 205 auf 66.
  * M6-HEILUNG (§72.3): der Look-ahead-Rueckfall vor dem ersten bestaetigten
    Docht entfaellt; ``basis_bei`` gibt dann den ersten bekannten Docht zurueck.
  * NEU ARRETIERT (§72.5/§72.6): V0, R_B, H1 (7 Trades / +39.919584 R),
    R1 (17 / +65.835576 R) und die Altsatz-Garantie. Der v0.1-Referenz-Trade
    K73@1020 entfaellt. V015/V016 bleiben unberuehrt.
  * ZAEHLER (§72.8): ``niveauwechsel_gesamt`` ist ein Fail-Loud-Sollwert.

Abschnitt S3 (Zeitbasis-Kanon, Modus V018 -- docs/ZEITBASIS_KANON.md):
  * BKZ = ``time AT TIME ZONE 'UTC'`` ist die EINZIGE Rechenbasis. Die
    frueher genutzte Berlin-Projektion entfaellt ersatzlos (Weg A).
  * ``box_end`` ist KEINE Bar-Konstante mehr, sondern die dynamische
    Kalenderkante ``searchsorted(ts_bkz, "2026-08-19")`` (AUG = 644).
  * V018 arretiert neu: H1 (8 / +38.919584 R), H2 (9 / +26.915992 R),
    R1 (17 / +65.835576 R). Der Grenztrade K1@640 (r = -1.000000) kippt
    von H2 nach H1 -- alle uebrigen 16 Trades partitionieren wie V017.

Satz (Dateinamen = <ausgabe_praefix> + Nummer + Rolle):
  01_gesamt      Bars 0..n      Kerzen, alle Trades (V01: 15 | V014: 17)
  02_h1_box      Bars 0..box_end+20  H1-Box (V01..V016: 8 | V017: 7 | V018: 8)
  03_h2_phasen   Bars 620..n    H2, Regime-Zonen (V01: 7 | V014: 9 Trades)
  04_p9_regime   Bars 820..1045 P9-Detail, Kanten + Override
  05_kantenkarte Bars 0..n      Kerzen + Kanten-Landkarte

Aufruf (V014 ist der Default; Modus per CLI):
  .venv\\Scripts\\python.exe test\\tmp_png_aug_sichttest.py
  .venv\\Scripts\\python.exe test\\tmp_png_aug_sichttest.py --mode V01
  .venv\\Scripts\\python.exe test\\tmp_png_aug_sichttest.py --probe-praefix probe_v01_

Gegenprobe mit einer WEGWERF-Engine (§72.1, Zero-Trust-Ablauf): ``--engine``
bindet eine alternative Engine-Datei. Default ist die arretierte Engine; mit
``--probe-praefix`` bleibt der versiegelte Satz unberuehrt.
  .venv\\Scripts\\python.exe test\\tmp_png_aug_sichttest.py --mode V017 ^
      --engine test/_tmp_engine_v017cand.py --probe-praefix probe_v017_ ^
      --protokoll-nach test/_tmp_probe_v017_out.txt
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import importlib.util
import io
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Optional, Sequence, Tuple, Union

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
OUTDIR = ROOT / "test"

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V014, ADAPTER_V015, ADAPTER_V019, BASELINE_V01_H2_R,
    BENCHMARK_V014_DELTA_R,
    BENCHMARK_V014_GESAMT_R, BENCHMARK_V014_H2_R, DEFAULT_ADAPTER,
    K67_OVERRIDE_69_87, P9, P9_BODEN_RECLAIM, P12_RESERVE,
    QUARTETT_V014_BARS,
    Hook2ZielModus, PhasenRegimeAdapter,
)

# ------------------------------------------------- Renderer-Konfiguration
# Spiegelspez Abschnitt 66.5 / §70 / §72: EIN Vertrag, SECHS Instanzen. Die
# Sollwerte sind zugleich der Fail-Loud-Assert-Katalog -- es gibt bewusst
# KEINEN Schalter "Asserts aus" (Abschnitt 66.5 / E4).
AdapterMode = Literal["V01", "V014", "V015", "V016", "V017", "V018", "V019"]


@dataclass(frozen=True, slots=True)
class RendererKonfiguration:
    """Sollwerte und Ausgabeorte eines Renderer-Modus.

    Args:
        mode: ``"V01"`` (arretierte Baseline) oder ``"V014"`` (K67-Override).
        ausgabe_praefix: Praefix der PNG-Dateinamen.
        protokoll_datei: Pfad des Lauf-Protokolls (relativ zur Repo-Wurzel).
        ziel_trades_gesamt: Soll-Trades des Adapter-Laufs.
        ziel_r_gesamt: Soll-R des Adapter-Laufs.
        ziel_r_h1: Soll-R der H1-Box (in beiden Modi bit-identisch).
        ziel_r_h2: Soll-R des H2-Bereichs.
        ziel_p9_beitrag: Soll-R des P9-Beitrags (V01: K73-Paar, V014: Quartett).
        k67_override_aktiv: True gdw. der K67-Niveau-Override greift.
        niveau_override_wert: Override-Preis oder None.
        alt_trades_einblenden: True gdw. entfallene V01-Trades als blasse
            Referenzmarker gezeichnet werden (Spez Abschnitt 66.4).
        quartett_bars: Mitarretiertes Trade-Quartett (nur V014).
        g4_aktiv: True gdw. die generische Phasenboden-Regel G4 (§69.8)
            engine-nativ greift (Route A, v0.20). Steuert ausschliesslich
            Kennzeichnung und Anzeige -- die Exekution liegt in der Engine.
        auflagen_aktiv: True gdw. die kosmetischen Auflagen A-1..A-4
            (Diamond-Marker statt rotem Sweep-Kreuz, 25er-Raster P04,
            K67-Annotations-Offsets, Rand-Abstand der Zonenlabels)
            angewendet werden (v0.21 / Modus V016). Bewusst getrennt von
            ``g4_aktiv``: V015 traegt ``False`` und bleibt damit
            bit-identisch reproduzierbar (Beschluss E8/E11).
        ziel_v0_r: Soll-R des ungepatchten Engine-Referenzlaufs ``V0``.
            Die Kantenformel liegt im Motor, deshalb wandert auch V0 mit
            (§72.5) -- V01..V016 behalten ihren historischen Wert.
        ziel_v1_basis_trades: Soll-Trades des v0.1-Referenzlaufs.
        ziel_v1_basis_r: Soll-R des v0.1-Referenzlaufs (``R_B``).
        ziel_h1_trades: Soll-Trades der H1-Box.
        ziel_delta_rb: Soll-Delta ``R1 - R_B``. Greift nur bei
            ``g4_aktiv``; V014 zieht weiter ``BENCHMARK_V014_DELTA_R``.
        neu_basis_soll: Soll-Menge der Neuzugaenge ohne den G4-Zusatz.
            ``(1002, 77)`` wird bei ``g4_aktiv`` automatisch ergaenzt.
        referenz_soll: Soll-Menge der entfallenen v0.1-Trades
            (Mengendifferenz ``V1_basis \\ V1_aktiv``, Abschnitt 66.4).
        quartett_r_soll: Soll-R je Quartett-Bar als ``((bar, r), ...)``.
        niveauwechsel_gesamt: Fail-Loud-Sollwert der sichtbaren
            Niveauwechsel der kausalen Kantenlinie (maskiert vor
            ``pivot_bar + 2``). V016 = 205, V017/V018 = 66 (§72.8).
        niveauwechsel_baseline: dokumentierter Vergleichswert im
            Statistikblock (V016-Baseline).
        netto_preiswechsel_baseline: dokumentierter Vergleichswert der
            Linien mit NETTO-Preiswechsel (Beschluss P-3: eigene
            Nomenklatur, V016-Baseline = 54, V017 = 41).
    """

    mode: AdapterMode
    ausgabe_praefix: str
    protokoll_datei: str
    ziel_trades_gesamt: int
    ziel_r_gesamt: float
    ziel_r_h1: float
    ziel_r_h2: float
    ziel_p9_beitrag: float
    k67_override_aktiv: bool
    niveau_override_wert: Optional[float]
    alt_trades_einblenden: bool
    quartett_bars: Tuple[int, ...]
    g4_aktiv: bool
    auflagen_aktiv: bool
    # --- §72: Sollwerte, die die Kantenformel des Motors beruehren ---------
    # Defaults reproduzieren V01..V016 unveraendert; V017/V018 setzen sie um.
    ziel_v0_r: float = 40.445143
    ziel_v1_basis_trades: int = 15
    ziel_v1_basis_r: float = 46.866348
    ziel_h1_trades: int = 8
    ziel_delta_rb: float = 18.012732
    neu_basis_soll: Tuple[Tuple[int, int], ...] = (
        (903, 67), (980, 67), (981, 73), (1020, 67))
    referenz_soll: Tuple[Tuple[int, int], ...] = ((980, 73), (1020, 73))
    quartett_r_soll: Tuple[Tuple[int, float], ...] = (
        (903, 4.1198), (980, 9.9877), (981, 2.6943), (1020, 3.0032))
    quartett_r_summe_soll: float = 19.804922
    niveauwechsel_gesamt: int = 205
    niveauwechsel_baseline: int = 205
    netto_preiswechsel_baseline: int = 54


KONFIGURATION_V01: Final[RendererKonfiguration] = RendererKonfiguration(
    mode="V01",
    ausgabe_praefix="aug_sichttest_",
    protokoll_datei="test/tmp_png_aug_sichttest_out.txt",
    ziel_trades_gesamt=15,
    ziel_r_gesamt=46.866348,
    ziel_r_h1=38.964262,
    ziel_r_h2=BASELINE_V01_H2_R,
    ziel_p9_beitrag=5.4212,
    k67_override_aktiv=False,
    niveau_override_wert=None,
    alt_trades_einblenden=False,
    quartett_bars=(),
    g4_aktiv=False,
    auflagen_aktiv=False,
)

KONFIGURATION_V014: Final[RendererKonfiguration] = RendererKonfiguration(
    mode="V014",
    ausgabe_praefix="aug_sichttest_v014_",
    protokoll_datei="test/tmp_png_aug_sichttest_v014_out.txt",
    ziel_trades_gesamt=17,
    ziel_r_gesamt=BENCHMARK_V014_GESAMT_R,
    ziel_r_h1=38.964262,
    ziel_r_h2=BENCHMARK_V014_H2_R,
    ziel_p9_beitrag=19.804922,
    k67_override_aktiv=True,
    niveau_override_wert=K67_OVERRIDE_69_87,
    alt_trades_einblenden=True,
    quartett_bars=QUARTETT_V014_BARS,
    g4_aktiv=False,
    auflagen_aktiv=False,
)

KONFIGURATION_V015: Final[RendererKonfiguration] = RendererKonfiguration(
    mode="V015",
    # Praefix UEBERNOMMEN von §68.5: der native Lauf loest den Staging-Satz ab.
    ausgabe_praefix="aug_sichttest_v015_",
    protokoll_datei="test/tmp_png_aug_sichttest_v015_out.txt",
    ziel_trades_gesamt=18,
    ziel_r_gesamt=64.879080,
    ziel_r_h1=38.964262,          # unveraendert (H1-Box arretiert)
    ziel_r_h2=25.914818,
    ziel_p9_beitrag=23.433938,
    k67_override_aktiv=True,
    niveau_override_wert=K67_OVERRIDE_69_87,
    alt_trades_einblenden=True,
    quartett_bars=QUARTETT_V014_BARS,
    g4_aktiv=True,
    auflagen_aktiv=False,        # V015 = arretierter G4-Beweis (§70.7)
)

# V016 = bereinigter Endstand (Auflagen A-1..A-4). Eigener Praefix, damit
# der arretierte v015-Satz nicht stillschweigend ueberschrieben wird
# (Beschluss E8).
KONFIGURATION_V016: Final[RendererKonfiguration] = RendererKonfiguration(
    mode="V016",
    ausgabe_praefix="aug_sichttest_v016_",
    protokoll_datei="test/tmp_png_aug_sichttest_v016_out.txt",
    ziel_trades_gesamt=18,
    ziel_r_gesamt=64.879080,
    ziel_r_h1=38.964262,          # unveraendert (H1-Box arretiert)
    ziel_r_h2=25.914818,
    ziel_p9_beitrag=23.433938,
    k67_override_aktiv=True,
    niveau_override_wert=K67_OVERRIDE_69_87,
    alt_trades_einblenden=True,
    quartett_bars=QUARTETT_V014_BARS,
    g4_aktiv=True,
    auflagen_aktiv=True,
)

# V017 = neue ENGINE-Generation (§72). Eigener Praefix, damit der arretierte
# v016-Satz nicht stillschweigend ueberschrieben wird. Der Adapter bleibt
# unveraendert (ADAPTER_V015); es wandert ausschliesslich die Kantenformel
# im Motor -- deshalb sind V0, R_B und H1 ebenfalls neu arretiert.
KONFIGURATION_V017: Final[RendererKonfiguration] = RendererKonfiguration(
    mode="V017",
    ausgabe_praefix="aug_sichttest_v017_",
    protokoll_datei="test/tmp_png_aug_sichttest_v017_out.txt",
    ziel_trades_gesamt=17,
    ziel_r_gesamt=65.835576,
    ziel_r_h1=39.919584,          # NEU arretiert (H1 wandert mit dem Motor)
    ziel_r_h2=25.915992,
    ziel_p9_beitrag=23.435111,
    k67_override_aktiv=True,
    niveau_override_wert=K67_OVERRIDE_69_87,
    alt_trades_einblenden=True,
    quartett_bars=QUARTETT_V014_BARS,
    g4_aktiv=True,
    auflagen_aktiv=True,
    # --- §72: neu arretierte Sollwerte der Engine-Generation V017 ----------
    # Kantenlinie = Extremum der bestaetigten Dochte; inkl. der M6-Heilung
    # (beide in-memory gemessen, §72.3/§72.5). H1 wanderte von 8 auf 7 Trades.
    ziel_v0_r=42.450970,
    ziel_v1_basis_trades=14,
    ziel_v1_basis_r=47.815697,
    ziel_h1_trades=7,
    ziel_delta_rb=18.019879,
    # K73@1020 existiert schon im v0.1-Referenzlauf nicht mehr -> die
    # Altsatz-Garantie ist geoeffnet (Erratum E-5 -> E-13, §72.6).
    neu_basis_soll=((903, 67), (980, 67), (981, 73)),
    referenz_soll=((980, 73),),
    quartett_r_soll=((903, 4.1198), (980, 9.9877), (981, 2.6955),
                     (1020, 3.0032)),
    quartett_r_summe_soll=19.806095,
    niveauwechsel_gesamt=66,
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

# V019 = endogene Segmentbildung (E-34..E-34i). Eigener Praefix: die
# arretierten Saetze V01..V018 bleiben unberuehrt. Engine-Generation =
# V018-Engine (BKZ/UTC, box_end 644); zusaetzlich greift das Zielzonen-
# Patchset ZP-4 (nur in diesem Modus).
KONFIGURATION_V019: Final[RendererKonfiguration] = RendererKonfiguration(
    mode="V019",
    ausgabe_praefix="aug_sichttest_v019_",
    protokoll_datei="test/tmp_png_aug_sichttest_v019_out.txt",
    ziel_trades_gesamt=23,
    ziel_r_gesamt=82.614385,
    ziel_r_h1=38.919584,          # Invariante (bit-identisch V017/V018)
    ziel_r_h2=43.694801,
    ziel_p9_beitrag=23.435111,    # P9 arretiert, unveraendert
    k67_override_aktiv=True,
    niveau_override_wert=K67_OVERRIDE_69_87,
    alt_trades_einblenden=True,
    quartett_bars=QUARTETT_V014_BARS,
    g4_aktiv=True,
    auflagen_aktiv=True,
    # --- Engine-Generation unveraendert (V018-Engine, BKZ/UTC) ------------
    ziel_v0_r=42.450970,
    ziel_v1_basis_trades=14,
    ziel_v1_basis_r=47.815697,
    ziel_h1_trades=8,
    ziel_delta_rb=34.798688,      # = 82.614385 - 47.815697
    # --- adapter-abhaengige Sollwerte (E-34i/3, MESSUNG) ------------------
    neu_basis_soll=((903, 67), (980, 67), (981, 73), (1075, 62), (1122, 73),
                    (1211, 76), (1268, 76), (1272, 73), (1280, 76)),
    referenz_soll=((980, 73),),
    quartett_r_soll=((903, 4.119775), (980, 9.987676), (981, 2.695488),
                     (1020, 3.003157)),
    quartett_r_summe_soll=19.806095,
    niveauwechsel_gesamt=66,
    niveauwechsel_baseline=205,
)

_KONFIGURATIONEN = {"V01": KONFIGURATION_V01, "V014": KONFIGURATION_V014,
                    "V015": KONFIGURATION_V015, "V016": KONFIGURATION_V016,
                    "V017": KONFIGURATION_V017, "V018": KONFIGURATION_V018,
                    "V019": KONFIGURATION_V019}


def _cli() -> Tuple[RendererKonfiguration, str, str, str]:
    """Liest Modus, Probe-Praefix, Protokollziel und Engine-Datei.

    Returns:
        ``(Konfiguration, Probe-Praefix, Protokoll-Override,
        Engine-Datei-Override)``. Die letzten beiden sind ``None``, wenn die
        arretierten Vorgaben gelten.
    """
    import argparse

    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--mode", choices=sorted(_KONFIGURATIONEN), default="V014",
                    help="Adapter-Modus (Default: V014).")
    ap.add_argument("--probe-praefix", default=None,
                    help="ERSETZT das Ausgabe-Praefix (Beschluss P-1); das "
                         "arretierte Artefakt bleibt unberuehrt.")
    ap.add_argument("--protokoll-nach", default=None,
                    help="Override der Protokolldatei (nur fuer Gegenproben).")
    ap.add_argument("--engine", default=None,
                    help="Alternative Engine-Datei (relativ zur Repo-Wurzel) "
                         "fuer den Zero-Trust-Probe-Lauf (§72.1). Default: "
                         "die arretierte Engine.")
    a = ap.parse_args()
    return (_KONFIGURATIONEN[a.mode], a.probe_praefix, a.protokoll_nach,
            a.engine)


KONF, PROBE_PRAEFIX, PROTOKOLL_NACH, ENGINE_OVERRIDE = _cli()
if ENGINE_OVERRIDE:
    # Nur fuer Gegenproben: die arretierte Engine bleibt unberuehrt.
    P = (ROOT / ENGINE_OVERRIDE).resolve()
    assert P.is_file(), f"Engine-Override nicht gefunden: {P}"
    assert P.parent == (ROOT / "test").resolve(), (
        "Engine-Override muss in test/ liegen", P)
# Beschluss P-1: ``--probe-praefix`` ERSETZT das Ausgabe-Praefix (es wird
# NICHT vorangestellt). Ohne Override bleibt der arretierte Satz unberuehrt.
PRAEFIX: Final[str] = PROBE_PRAEFIX or KONF.ausgabe_praefix
PROTOKOLL_DATEI: Final[str] = PROTOKOLL_NACH or KONF.protokoll_datei

# Urkundliche Kennung der geladenen Engine (Protokoll, §72.4).
ENGINE_NAME: Final[str] = P.name
ENGINE_SHA: Final[str] = hashlib.sha256(P.read_bytes()).hexdigest()
adapter: PhasenRegimeAdapter = (
    ADAPTER_V019 if KONF.mode == "V019"
    else (ADAPTER_V015 if KONF.g4_aktiv
          else (ADAPTER_V014 if KONF.k67_override_aktiv
                else DEFAULT_ADAPTER)))

# -------------------------------------- Auflagen A-1..A-4 (Spiegelspez §71)
# Eigener Diskriminator -- NICHT KONF.g4_aktiv: V015 und V016 teilen
# g4_aktiv, aber nur V016 traegt die kosmetischen Auflagen. So bleibt der
# arretierte V015-Satz (§70.7) bit-identisch reproduzierbar (E8/E11).
_AUFL: Final[bool] = KONF.auflagen_aktiv
# A-2: rotes Sweep-Kreuz (Altzitat §32) weicht dem Diamond; das violette
# Q29-'x' (§54.2 R7 / A11) bleibt unveraendert.
SWEEP_MARKER: Final[str] = "d" if _AUFL else "x"
SWEEP_MARKER_MS: Final[float] = 7.5 if _AUFL else 7.0
# Die Panels 03/04 zeichnen den Sweep-Marker historisch groesser (ms=8).
SWEEP_MARKER_MS_GROSS: Final[float] = 8.5 if _AUFL else 8.0
# Panel 02 ist eingefroren (Ausnahme analog A-5) -> eigener Marker.
SWEEP_MARKER_P02: Final[str] = "x"
# A-1: 25er-Raster der Panel-04-X-Achse (8 Ticks inkl. Randtick 1025).
TICKS_P04: Final[Tuple[int, ...]] = tuple(range(850, 1050, 25))
# A-3: Kollisions-Offsets (bar, kid) -> (dx, dy) in Punkt (E5). Leer in
# V01/V014/V015 -> es gilt unveraendert die Bestandsformel.
ANNOT_OFFSET: Final[dict] = ({(1020, 67): (0, -18), (980, 67): (0, 22)}
                             if _AUFL else {})
# A-4: Zonenlabel als Achsen-Anteil statt Daten-y.
ZONEN_LABEL_Y: Final[float] = 0.92

# -------------------- V017/V018: eigene Engine-Generation (§72 / S3) -------
# Eigener Diskriminator -- NICHT an _AUFL haengen: V016 traegt dieselben
# Auflagen und muss byte-identisch reproduzierbar bleiben (arretierter Satz).
# V017 und V018 teilen die Motordrehungen (Kanten-Extremum + M6-Heilung) und
# unterscheiden sich AUSSCHLIESSLICH in der Zeitbasis (S3: BKZ/UTC statt
# Berlin) und den daraus folgenden Sollwerten. Alle Text-/Verhaltenszweige der
# Generation haengen deshalb an _NEU.
_V17: Final[bool] = KONF.mode == "V017"
_V18: Final[bool] = KONF.mode == "V018"
_V19: Final[bool] = KONF.mode == "V019"
_NEU: Final[bool] = _V17 or _V18 or _V19
# Versionskuerzel fuer Titel/Annotationen (V017 bzw. V018 bzw. V019).
_VTAG: Final[str] = "V019" if _V19 else ("V018" if _V18 else "V017")
# Versionslabel (Adapter + Engine-Generation) fuer Titel und Protokoll.
# In V01..V016 exakt der bisherige Wortlaut -> Bytes unveraendert.
_VER_TEXT: Final[str] = (
    "v0.24 (endogene Segmente A1/A2 + Zielzonen-Patchset ZP-4)" if _V19
    else ("v0.18 (BKZ/UTC + Kanten-Extremum + M6-Heilung)" if _V18
          else ("v0.17 (Kanten-Extremum + M6-Heilung)" if _V17
                else ("v0.16 (G4 + A-1..A-4)" if _AUFL
                      else ("v0.15 G4" if KONF.g4_aktiv
                            else ("v0.14" if KONF.k67_override_aktiv
                                  else "v0.1"))))))

# ---------------------------------------------------------------- Engine
def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


engine = load("ke_pngset", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
box_end = scan["box_end_bar"]
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
if KONF.mode == "V019" and box_end != 644:
    raise SystemExit(
        f"Modus V019 erfordert die V018-Engine (BKZ/UTC, box_end 644), "
        f"geladen wurde box_end={box_end} ({ENGINE_NAME} "
        f"{ENGINE_SHA[:16]}...).")
scan["box_end_bar"] = n                       # Voll-Lauf (arretierte Basis)


def _niveauwechsel_sichtbar(sc) -> int:
    """Sichtbare Niveauwechsel der kausalen Kantenlinie (maskiert).

    Gezaehlt wird ueber alle Linien an jedem Bar, an dem die Linie schon
    bestaetigt ist (``pivot_bar + 2 <= k``) -- exakt die Maskierung, die
    ``_kanten_y_engine`` beim Zeichnen anwendet. Der Bar davor wird NICHT
    als Wechsel gezaehlt: sonst entstuende je Linie ein Phantom-Sprung und
    die Kennzahl laege bei 259 statt bei den sichtbaren 205.

    Args:
        sc: Scan-Ergebnis aus ``_se_scan``.

    Returns:
        Anzahl der Preiswechsel ueber alle Kanten und Seeds.
    """
    ges = 0
    for _e in list(sc["edges"]) + list(sc["seeds"]):
        _prev = None
        for _k in range(sc["n"]):
            if not any(_b + 2 <= _k for _b, _ in _e.wicks):
                continue
            _v = float(_e.basis_bei(_k))
            if _prev is not None and abs(_v - _prev) > 1e-12:
                ges += 1
            _prev = _v
    return ges


# §72.8: Fail-Loud-Kennzahl -- V016 = 205, V017/V018 = 66.
NIVEAUWECHSEL: Final[int] = _niveauwechsel_sichtbar(scan)

# ------------------------------------------------- RAM-Patch (Adapter)
src_datei = P.read_text(encoding="utf-8")
tree = ast.parse(src_datei)
node = next(x for x in tree.body
            if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src = ast.get_source_segment(src_datei, node)
assert src is not None

A_KANTEN = '''        return max(bars) >= k - cfg.wall_live_bars

    def _im_aussenquartil('''
A_KANTEN_NEW = '''        return max(bars) >= k - cfg.wall_live_bars

    def _basis_wirksam(e: _SEEdgeH, k: int) -> float:
        return _hook.angewandte_basis(k, e.kid, e.basis_bei(k))

    def _seite_kanten(k: int, seite: KantenSeite) -> List[Tuple[int, float]]:
        return [(e.kid, _basis_wirksam(e, k)) for e in seite_edges[seite]
                if _existiert(e, k)]

    _freigabe_kid: Optional[int] = None

    def _im_aussenquartil('''
A_LOOP = '''            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])
            kd = _kandidat(richtung, k, sweep_px)'''
A_LOOP_NEW = '''            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])
            _seite: KantenSeite = ("OBEN" if richtung == "SHORT" else "UNTEN")
            _freigabe_kid = _hook.hook_1_freigabe_kid(
                k, sweep_px, richtung, _seite_kanten(k, _seite))
            kd = _kandidat(richtung, k, sweep_px)'''
A_POOL = '''        if not pool:
            return None
        pool.sort(key=lambda e: e.basis_bei(k), reverse=(seite == "OBEN"))'''
A_POOL_NEW = '''        if not pool:
            return None
        pool.sort(key=lambda e: _basis_wirksam(e, k),
                  reverse=(seite == "OBEN"))
        if _freigabe_kid is not None:
            pool = [e for e in pool if e.kid != _freigabe_kid]'''
A_DIST = '''        def _dist(e: _SEEdgeH) -> float:
            basis = e.basis_bei(k)'''
A_DIST_NEW = '''        def _dist(e: _SEEdgeH) -> float:
            basis = _basis_wirksam(e, k)'''
A_M6_OBEN = '''            if seite == "OBEN":
                if b <= sweep_px:'''
A_M6_OBEN_NEW = '''            if seite == "OBEN":
                if _freigabe_kid is not None and e.kid == _freigabe_kid:
                    continue
                if b <= sweep_px:'''
A_M6_UNTEN = '''            else:
                if b >= sweep_px:'''
A_M6_UNTEN_NEW = '''            else:
                if _freigabe_kid is not None and e.kid == _freigabe_kid:
                    continue
                if b >= sweep_px:'''
A_M6_BASIS = '''            b = e.basis_bei(k)
            if seite == "OBEN":'''
A_M6_BASIS_NEW = '''            b = _basis_wirksam(e, k)
            if seite == "OBEN":'''
A_M6_BASIS_K = '        basis_k = kd.basis_bei(k)'
A_M6_BASIS_K_NEW = '        basis_k = _basis_wirksam(kd, k)'
A_M6_RET = '''        b = aussen.basis_bei(k)
        dist = ((b - basis_k) if seite == "OBEN"'''
A_M6_RET_NEW = '''        b = _basis_wirksam(aussen, k)
        dist = ((b - basis_k) if seite == "OBEN"'''
A_M6_SORT = '                if aussen is None or b > aussen.basis_bei(k):'
A_M6_SORT_NEW = ('                if aussen is None '
                 'or b > _basis_wirksam(aussen, k):')
A_M6_SORT2 = '                if aussen is None or b < aussen.basis_bei(k):'
A_M6_SORT2_NEW = ('                if aussen is None '
                  'or b < _basis_wirksam(aussen, k):')
A_TP2 = '            gegen_basis = geg.basis_bei(k)\n'
A_TP2_NEW = A_TP2 + '''            _h2 = _hook.hook_2_ziel(k, richtung)
            if _h2.modus is _Hook2ZielModus.BLOCKIERT:
                stats["kein_raum"] += 1
                continue
            if _h2.modus is _Hook2ZielModus.PHASE:
                gegen_basis = _h2.ziel_preis
'''
A_KBASIS = '            basis = kd.basis_bei(k)\n'
A_KBASIS_NEW = '            basis = _basis_wirksam(kd, k)\n'
for _name, _s in (("A_KANTEN", A_KANTEN), ("A_LOOP", A_LOOP),
                  ("A_POOL", A_POOL), ("A_DIST", A_DIST),
                  ("A_M6_OBEN", A_M6_OBEN), ("A_M6_UNTEN", A_M6_UNTEN),
                  ("A_M6_BASIS", A_M6_BASIS), ("A_M6_BASIS_K", A_M6_BASIS_K),
                  ("A_M6_RET", A_M6_RET), ("A_M6_SORT", A_M6_SORT),
                  ("A_M6_SORT2", A_M6_SORT2), ("A_TP2", A_TP2),
                  ("A_KBASIS", A_KBASIS)):
    assert src.count(_s) == 1, (_name, src.count(_s))
patched_src = (src.replace(A_KANTEN, A_KANTEN_NEW)
               .replace(A_LOOP, A_LOOP_NEW)
               .replace(A_POOL, A_POOL_NEW)
               .replace(A_DIST, A_DIST_NEW)
               .replace(A_M6_BASIS_K, A_M6_BASIS_K_NEW)
               .replace(A_M6_BASIS, A_M6_BASIS_NEW)
               .replace(A_M6_RET, A_M6_RET_NEW)
               .replace(A_M6_SORT, A_M6_SORT_NEW)
               .replace(A_M6_SORT2, A_M6_SORT2_NEW)
               .replace(A_M6_OBEN, A_M6_OBEN_NEW)
               .replace(A_M6_UNTEN, A_M6_UNTEN_NEW)
               .replace(A_TP2, A_TP2_NEW)
               .replace(A_KBASIS, A_KBASIS_NEW))

# ------------------------------- Zielzonen-Patchset ZP-4 (nur Modus V019)
# Herkunft: test/_tmp_e34_auto.py (E-34..E-34i). Die vier Regeln sind
# KOPPLUNGSPHYSIK, kein Datensatz: ohne sie ist die Zielzone inert (ZIEL 0).
#
# ZWEISTUFIGES GATING:
#   (1) Quelltext: diese Funktion wird NUR bei mode == "V019" aufgerufen
#       -> V01..V018 behalten ihren Quelltext byte-identisch.
#   (2) Laufzeit: die injizierte ``_zv(k)`` prueft den GEBUNDENEN Adapter
#       (ns["_hook"]), nicht den Modus -> V0/V1_basis (DEFAULT_ADAPTER,
#       1 Segment) bleiben unberuehrt.
def _wende_zielzonen_patches_v019(src: str) -> str:
    """Webt die vier Zielzonen-Engine-Regeln in den ``_se_trades``-Quelltext.

    Args:
        src: Quelltextsegment der Funktion ``_se_trades`` (bereits mit den
            13 Bestands-Patches des Renderers).

    Returns:
        Quelltext mit ZP-4 (Ueberdehnung, Quartil-Reset, M6-Schlaf-Filter,
        Sweep-Basis-Aktivierung).

    Raises:
        AssertionError: ein Anker kommt nicht genau einmal vor (Fail-Loud).
    """
    paare = (
        # (1) Ueberdehnungsschranke segment-lokal 0.80
        ("A_UEB1",
         "            if dist > cfg.max_sweep_ueberdehnung_pct:",
         "            if dist > _ueb(k):"),
        # (2) Quartil-Extremum ab Segmentstart statt global
        ("A_VC",
         "        ex_hi = float(np.max(hi[:k + 1]))\n"
         "        ex_lo = float(np.min(lo[:k + 1]))",
         "        _q0 = 0\n"
         "        if _zv(k):\n"
         "            _sq = _hook.aktive_phase_bei(k)\n"
         "            if _sq is not None:\n"
         "                _q0 = int(_sq.start_bar)\n"
         "        ex_hi = float(np.max(hi[_q0:k + 1]))\n"
         "        ex_lo = float(np.min(lo[_q0:k + 1]))"),
        # (3) M6-Blocker ueberspringt schlafende Linien in der Zone
        ("A_M6L",
         "            if e is kd or not _existiert(e, k):\n"
         "                continue",
         "            if e is kd or not _existiert(e, k) or (\n"
         "                    _zv(k) and not _lebt(e, k)):\n"
         "                continue"),
        # (4) gesweepte Linie zaehlt in der Zone als aktiv
        ("A_SB",
         "        if not e.ist_aktiv_bei(k):\n"
         "            return False\n"
         "        return e.erster_pivot_bar + 2 <= k + 1",
         "        if not e.ist_aktiv_bei(k):\n"
         "            _ev = ((hi[k] > e.basis_bei(k)) if e.seite == \"OBEN\"\n"
         "                   else (lo[k] < e.basis_bei(k)))\n"
         "            if not (_zv(k) and _ev):\n"
         "                return False\n"
         "        return e.erster_pivot_bar + 2 <= k + 1"),
    )
    for _nm, _alt, _neu in paare:
        assert src.count(_alt) == 1, (_nm, src.count(_alt))
        src = src.replace(_alt, _neu)
    return src


if KONF.mode == "V019":
    patched_src = _wende_zielzonen_patches_v019(patched_src)

ORIG = engine._se_trades
ns = dict(engine.__dict__)
ns["_Hook2ZielModus"] = Hook2ZielModus

# --- ZP-4 Laufzeit-Gate (nur wirksam, wenn der gebundene Adapter V019 ist)
# Fenster aus dem Adapter abgeleitet - kein Bar-Literal.
_ZZ_START: Final[int] = ADAPTER_V019.segmente[1].start_bar
_ZZ_ENDE: Final[int] = ADAPTER_V019.segmente[-1].end_bar
_P9_START: Final[int] = ADAPTER_V019.segmente[0].start_bar
_P9_ENDE: Final[int] = ADAPTER_V019.segmente[0].end_bar


def _zv(kk: int) -> bool:
    """Zielzonen-Fenster -- NUR wenn der GEBUNDENE Adapter mehrsegments ist.

    Damit schuetzt das Gate die drei Laeufe desselben Prozesses: V0 und
    V1_basis (DEFAULT_ADAPTER, 1 Segment) bleiben unberuehrt, nur V1_aktiv
    (ADAPTER_V019, 3 Segmente) erhaelt die ZP-4-Regeln.
    """
    _hk = ns.get("_hook")
    return (KONF.mode == "V019" and _hk is not None
            and len(_hk.segmente) > 1
            and _ZZ_START <= kk <= _ZZ_ENDE
            and not (_P9_START <= kk <= _P9_ENDE))


def _ueb(kk: int) -> float:
    """Ueberdehnungs-Schranke: 0.80 segment-lokal, sonst arretierte cfg."""
    return 0.80 if _zv(kk) else cfg.max_sweep_ueberdehnung_pct


_RS_ORIG = engine._reclaim_stufe


def _reclaim_stufe_lok(seite, kk, basis, hi, lo, cl, c):
    """Wrapper: Schranke 0.80 segment-lokal (sonst arretierte cfg)."""
    if _zv(kk):
        c = dataclasses.replace(c, max_sweep_ueberdehnung_pct=0.80)
    return _RS_ORIG(seite, kk, basis, hi, lo, cl, c)


ns["_zv"] = _zv
ns["_ueb"] = _ueb
ns["_reclaim_stufe"] = _reclaim_stufe_lok


def _lauf(hook: PhasenRegimeAdapter, mit_patch: bool):
    """Ein Engine-Lauf mit gebundenem Adapter (Engine-Klasse bleibt sauber)."""
    ns["_hook"] = hook
    exec(compile(patched_src, "<se_trades_sichttest>", "exec"), ns)
    if not mit_patch:
        return ORIG(copy.deepcopy(scan), cfg)
    engine._se_trades = ns["_se_trades"]
    try:
        return engine._se_trades(copy.deepcopy(scan), cfg)
    finally:
        engine._se_trades = ORIG


# Drei Laeufe: V0 (unpatch, Referenz) | V1_basis (v0.1) | V1_aktiv (Modus).
V0, _ = _lauf(DEFAULT_ADAPTER, False)
V1_basis, st_basis = _lauf(DEFAULT_ADAPTER, True)
V1_aktiv, st_aktiv = _lauf(adapter, True)


def _key(t) -> Tuple[int, int]:
    """Schluessel (bar, kid) einer Trade-Zeile.

    Die Mengendifferenz wird ueber den Schluessel gebildet, nicht ueber
    ``set(...)``: ``_SESetup`` ist zwar hashbar, ein Set wuerde aber
    feldgleiche Zeilen stillschweigend kollabieren lassen.
    """
    return (int(t.bar), int(t.kid))


_AKTIV_KEYS = {_key(t) for t in V1_aktiv}
_BASIS_KEYS = {_key(t) for t in V1_basis}
REFERENZ = [t for t in V1_basis if _key(t) not in _AKTIV_KEYS]
NEU = [t for t in V1_aktiv if _key(t) not in _BASIS_KEYS]

V1, st1 = V1_aktiv, st_aktiv

R0 = sum(t.r for t in V0)
R1 = sum(t.r for t in V1)
RB = sum(t.r for t in V1_basis)
h1_0 = [t for t in V0 if t.entry_bar < box_end]
h2_0 = [t for t in V0 if t.entry_bar >= box_end]
h1_1 = [t for t in V1 if t.entry_bar < box_end]
h2_1 = [t for t in V1 if t.entry_bar >= box_end]
P9_BEITRAG = sum(t.r for t in V1 if 848 <= t.bar <= 1020)

# --- v0.20 G4 (Route A): Kennzeichnung aus dem ENGINE-nativen Trade --------
# Segment und Trade werden ausschliesslich aus adapter.segmente / V1
# abgeleitet -- kein Bar- oder kid-Literal. In V01/V014 liefert die Suche
# None, weil dort kein Segment ein deklariertes Boden-Literal traegt.
G4_SEG = next((s for s in adapter.segmente
               if s.boden_deklariert_literal is not None), None)
G4_TRADES = ([t for t in V1
              if t.kid == G4_SEG.boden.kid and t.bar >= G4_SEG.start_bar]
             if G4_SEG is not None else [])
G4_MARKE = frozenset((int(t.bar), int(t.kid)) for t in G4_TRADES)
# Quartett-Summe getrennt vom P9-Regimebeitrag: in V015 sind beide NICHT mehr
# identisch (Residuum 3 des §68.5-Stagings -- hier an der Wurzel behoben).
QUARTETT_R = sum(t.r for t in V1 if t.bar in KONF.quartett_bars)
G4_ZEILEN = ([
    f"G4-PHASENBODEN (§69.8): K{G4_SEG.boden.kid}@{t.bar} "
    f"entry {t.entry:.4f} sl {t.sl:.4f} tp2 {t.tp2:.4f} | R {t.r:+.6f} | "
    f"literaler Boden {G4_SEG.boden_deklariert_literal:.4f} | {t.richtung}"
    for t in G4_TRADES] if G4_SEG is not None else [])

# ------------------------------------------------------- FAIL-LOUD-Asserts
# §72.5: Die Sollwerte kommen aus KONF. Die Kantenformel liegt im MOTOR,
# deshalb wandert auch der ungepatchte Referenzlauf V0 und die v0.1-Basis
# R_B mit der Generation. V01..V016 tragen ihre historischen Literale als
# Default (Byte-Identitaet der arretierten Saetze bleibt erhalten).
assert len(V0) == 14 and abs(R0 - KONF.ziel_v0_r) < 1e-5, (len(V0), R0)
assert (len(V1_basis) == KONF.ziel_v1_basis_trades
        and abs(RB - KONF.ziel_v1_basis_r) < 1e-5), (len(V1_basis), RB)
assert len(V1) == KONF.ziel_trades_gesamt, (KONF.mode, len(V1))
assert abs(R1 - KONF.ziel_r_gesamt) < 1e-4, (KONF.mode, R1)
assert len(h1_1) == KONF.ziel_h1_trades, (KONF.mode, len(h1_1))
assert abs(sum(t.r for t in h1_1) - KONF.ziel_r_h1) < 1e-6, sum(
    t.r for t in h1_1)
assert abs(sum(t.r for t in h2_1) - KONF.ziel_r_h2) < 1e-4, sum(
    t.r for t in h2_1)
assert abs(P9_BEITRAG - KONF.ziel_p9_beitrag) < 1e-4, P9_BEITRAG
# §72.8: Die Niveauwechsel sind ein HARTES Literal -- der kosmetische Text
# im Bild schuetzt vor keiner Regression, dieser Assert schon (205 -> 66).
assert NIVEAUWECHSEL == KONF.niveauwechsel_gesamt, (
    KONF.mode, NIVEAUWECHSEL, KONF.niveauwechsel_gesamt)
if not KONF.k67_override_aktiv:
    assert abs(P9_BEITRAG - 5.4212) < 1e-3
    assert abs(sum(t.r for t in V1 if t.kid == 73) - 5.4212) < 1e-3
    assert not REFERENZ and not NEU
else:
    assert KONF.niveau_override_wert == 69.87, KONF.niveau_override_wert
    if KONF.mode == "V019":
        # E-34i: 23 - 14 = 9 (Zielzone A1/A2 traegt 6, G4 1, Quartett 2).
        assert len(V1) - len(V1_basis) == 9, len(V1) - len(V1_basis)
    else:
        assert len(V1) - len(V1_basis) in (2, 3), len(V1) - len(V1_basis)
    _dsoll = KONF.ziel_delta_rb if KONF.g4_aktiv else BENCHMARK_V014_DELTA_R
    assert abs((R1 - RB) - _dsoll) < 1e-4, R1 - RB
    # v0.20: Regel G4 fail-loud -- genau EIN Reclaim-Trade, ausschliesslich
    # im Modus V015 und ausschliesslich ausserhalb der H1-Box.
    if KONF.g4_aktiv:
        assert len(G4_TRADES) == 1, G4_TRADES
        assert (1002, 77) in G4_MARKE, G4_MARKE
        assert all(t.entry_bar >= box_end for t in G4_TRADES), "G4 in H1!"
    else:
        assert not G4_TRADES, G4_TRADES
    _q = {t.bar: t for t in V1 if t.bar in KONF.quartett_bars}
    assert sorted(_q) == list(KONF.quartett_bars), sorted(_q)
    for _b, _soll in KONF.quartett_r_soll:
        assert abs(_q[_b].r - _soll) < 1e-4, (_b, _q[_b].r)
    assert abs(sum(t.r for t in _q.values())
               - KONF.quartett_r_summe_soll) < 1e-4, sum(
        t.r for t in _q.values())
    assert ((_q[903].kid, _q[980].kid, _q[981].kid, _q[1020].kid)
            == (67, 67, 73, 67))
    # §72.6: Altsatz-Garantie geoeffnet -- in V017 entfaellt K73@1020
    # schon im v0.1-Referenzlauf (Erratum E-5 -> E-13).
    assert [_key(t) for t in sorted(REFERENZ, key=lambda x: x.bar)] == list(
        KONF.referenz_soll), [_key(t) for t in REFERENZ]
    _neu_soll = sorted(KONF.neu_basis_soll)
    if KONF.g4_aktiv:
        _neu_soll = sorted(set(_neu_soll) | {(1002, 77)})
    assert sorted(_key(t) for t in NEU) == _neu_soll, sorted(
        _key(t) for t in NEU)
    assert abs(sum(t.r for t in V1 if t.kid == 67 and t.bar in
                   KONF.quartett_bars) - 17.1107) < 1e-3

# ---------------------------------------------------------------- Plot
import matplotlib                                    # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                      # noqa: E402
import numpy as np                                   # noqa: E402
import pandas as pd                                  # noqa: E402
from matplotlib.lines import Line2D                  # noqa: E402
from matplotlib.patches import Rectangle             # noqa: E402

d = scan["d"]
# Zeitbasis der Achsen (lesend, Engine-unberuehrt):
# Die Engine-SQL liefert mit ``time AT TIME ZONE 'UTC'`` die Broker-Kerzen-
# Zeit (BKZ, docs/ZEITBASIS_KANON.md) als naives ts -- exakt die Bar-
# Zeitstempel, die auch die Trade-Tabellen UND der M15-Chart fuehren.
# Deshalb wird die Achse OHNE Offset gezeichnet.
# ts wird ausschliesslich in time_axis() fuer Tick-Labels genutzt und nie
# in die Trade-Logik eingespeist -> Engine-SHA und Trades bleiben identisch.
AXIS_TZ_OFFSET_H = 0
ts = pd.to_datetime(d["ts"]) + pd.Timedelta(hours=AXIS_TZ_OFFSET_H)
op = d["open"].to_numpy(dtype=float)
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
idx = np.arange(n)

C_UP, C_DN = "#a8d5ba", "#f2a5a5"
C_OBEN, C_UNTEN = "#d62728", "#2ca02c"
C_SHORT, C_LONG = "#d62728", "#2ca02c"
C_REGIME, C_GAP, C_RESERVE = "#2ca02c", "#d62728", "#7f7f7f"
C_GATE = "#8e44ad"                    # Sperr-Marker (Q29 x / M6 ^)
C_CHG = "#b8860b"                     # Preiswechsel-Markierung (Label)
KANTEN_COL = {"OBEN": C_OBEN, "UNTEN": C_UNTEN}
GEAENDERT: dict = {}                  # kid -> (v_start, v_ende, n_stufen)

# v0.4-Provenienz-Normen der Phasen-Grenzkanten (Quelle: Adapter).
# Sie sind dokumentarisch (Spez Abschnitt 37.4) und werden am Label als
# "Norm <wert>" mitgefuehrt, wenn der kausale Preis abweicht.
NORM = {
    P9.decke.kid: P9.decke.provenienz_basis,
    P9.boden.kid: P9.boden.provenienz_basis,
    P12_RESERVE.decke.kid: P12_RESERVE.decke.provenienz_basis,
    P12_RESERVE.boden.kid: P12_RESERVE.boden.provenienz_basis,
}
NORM_KIDS = frozenset(NORM)


def _override_info(kid: int) -> Optional[Tuple[float, str, int, int]]:
    """Niveau-Override einer Kante: ``(preis, phase, start_bar, end_bar)``.

    Quelle ist ausschliesslich der gebundene Adapter (Spez Abschnitt 66.2/66.3).
    Im Modus V01 ist die Antwort stets ``None`` -> keine Grenzlinien und kein
    Plateau-Label, der Bildsatz bleibt unveraendert.

    Args:
        kid: Kanten-ID.

    Returns:
        Tupel oder None, wenn kein Override fuer diese Kante existiert.
    """
    for _seg in adapter.segmente:
        for _kante in (_seg.decke, _seg.boden):
            if _kante.kid == int(kid) and _kante.hat_override():
                return (float(_kante.niveau_override), str(_seg.phasen_id),
                        int(_seg.start_bar), int(_seg.end_bar))
    return None


# kid -> (preis, phase, start_bar, end_bar); im Modus V01 leer.
OVERRIDE_INFO: dict = {
    _e.kid: _override_info(_e.kid)
    for _e in list(scan["edges"]) + list(scan["seeds"])
    if _override_info(_e.kid) is not None
}

PHASEN = {
    "P6": (620, 673, 65.490, 62.649),
    "P7": (715, 792, 67.201, 65.604),
    "P8": (802, 840, 68.320, 67.897),
    "P9": (848, 1020, 69.9140, 68.3700),
    "P10": (1030, 1075, 68.2200, 67.5440),
    "P11": (1082, 1134, 69.3435, 68.5250),
    "P12": (1171, 1272, 69.5550, 67.6355),
}
LECKEN = [(641, 847), (1021, 1029), (1076, 1081), (1135, 1170), (1273, n - 1)]


def draw_candles(ax, x0: int, x1: int, mode: str = "candle") -> None:
    """Kerzen (mode='candle') oder Close-Linie (mode='line') im Fenster."""
    x = idx[x0:x1 + 1]
    if mode == "line":
        ax.plot(x, cl[x0:x1 + 1], color="#1f3b57", lw=0.9, alpha=0.95,
                zorder=3, label=None)
        ax.vlines(x, lo[x0:x1 + 1], hi[x0:x1 + 1], color="#1f3b57", lw=0.25,
                  alpha=0.35, zorder=2)
        return
    up = cl[x0:x1 + 1] >= op[x0:x1 + 1]
    ax.vlines(x, lo[x0:x1 + 1], hi[x0:x1 + 1],
              color=np.where(up, "#3d8f6d", "#c05656"), lw=0.6, zorder=2)
    body_lo = np.minimum(op[x0:x1 + 1], cl[x0:x1 + 1])
    body_h = np.abs(cl[x0:x1 + 1] - op[x0:x1 + 1])
    body_h = np.where(body_h < 1e-9, 0.004, body_h)
    for xi, b0, bh, u in zip(x, body_lo, body_h, up):
        ax.add_patch(Rectangle((xi - 0.32, b0), 0.64, bh,
                               facecolor=C_UP if u else C_DN,
                               edgecolor="#3d8f6d" if u else "#c05656",
                               lw=0.4, zorder=3))


def shade_phases(ax, y0: float, y1: float, x0: int, x1: int,
                 aktiv: str = "P9") -> None:
    """Regime-Zonen: aktiv = gruen, Reserve = grau, Luecken = rot schraffiert."""
    # Auflage A-4: als Achsen-Anteil, damit Abstand zum oberen Rand
    # entsteht. In V01/V014/V015 bleibt es beim Daten-y (transData ist
    # der Matplotlib-Default -> Bytes unveraendert).
    _lbl_y, _lbl_tr = ((ZONEN_LABEL_Y, ax.get_xaxis_transform())
                       if _AUFL else (y1, ax.transData))
    for pid, (bs, be, _u, _l) in PHASEN.items():
        if be < x0 or bs > x1:
            continue
        a, b = max(bs, x0), min(be, x1)
        if pid == aktiv:
            ax.axvspan(a, b, color=C_REGIME, alpha=0.13, zorder=0)
            ax.text((a + b) / 2, _lbl_y, f"{pid} AKTIV", fontsize=9,
                    ha="center", va="top", color="#1b6b3a", weight="bold",
                    zorder=11, transform=_lbl_tr)
        elif pid == "P12":
            ax.axvspan(a, b, color=C_RESERVE, alpha=0.10, zorder=0)
            ax.text((a + b) / 2, _lbl_y, f"{pid} RESERVE", fontsize=8.5,
                    ha="center", va="top", color="#555555", zorder=11,
                    transform=_lbl_tr)
        else:
            ax.axvspan(a, b, color="#1f77b4", alpha=0.05, zorder=0)
    for gs, ge in LECKEN:
        if ge < x0 or gs > x1:
            continue
        a, b = max(gs, x0), min(ge, x1)
        ax.axvspan(a, b, facecolor=C_GAP, alpha=0.07, hatch="//",
                   edgecolor=C_GAP, lw=0.0, zorder=0)


def mark_trades(ax, trades, filled_h1: bool = True, fs: float = 8.0,
                stil: str = "voll") -> None:
    """Trade-Kreise zeichnen.

    Args:
        ax: Zielachse.
        trades: ``_SESetup``-Liste.
        filled_h1: Historisch; die Trennung laeuft ueber Groesse und Rand.
        fs: Schriftgroesse der Beschriftung.
        stil: ``"voll"`` -- handelnder Trade, farbig gefuellt (``mfc=col``),
            Regel 10 des Abschnitts 54. ``"referenz"`` -- im V014-Lauf
            entfallener V01-Trade: gestrichelt, ``mfc="none"``, grau,
            ``alpha=0.45`` (deklarierte Ausnahme, Abschnitt 66.4).
    """
    ref = stil == "referenz"
    for t in trades:
        col = "#7f7f7f" if ref else (C_SHORT if t.richtung == "SHORT"
                                     else C_LONG)
        in_h1 = t.entry_bar < box_end
        # Immer farbig gefuellt (Richtung = Farbe). H1/H2 werden NICHT mehr
        # ueber die Fuellung, sondern ueber Groesse + Randstaerke getrennt.
        # Ausnahme: entfallene V01-Referenz-Trades (Abschnitt 66.4).
        ax.plot(t.bar, t.basis, "o", ms=9.0 if in_h1 else 10.5, color=col,
                zorder=9, mec=col if ref else "#1a1a1a",
                mew=0.9 if ref else (0.7 if in_h1 else 1.6),
                mfc="none" if ref else col, alpha=0.45 if ref else None)
        # v0.20 (Route A): G4-Reclaim am ENGINE-berechneten Trade markieren.
        # Wirkt nur im Modus V015; Panel 02 (H1) enthaelt keinen G4-Trade,
        # die Byte-Invariante d9f35876... ist damit strukturell gesichert.
        if not ref and (int(t.bar), int(t.kid)) in G4_MARKE:
            ax.plot(t.bar, t.basis, "o", ms=17.5, color=C_CHG, mfc="none",
                    mew=2.2, zorder=13)
            ax.annotate("G4 RECLAIM", (t.bar, t.basis),
                        textcoords="offset points", xytext=(0, 44),
                        ha="center", fontsize=fs + 0.5, color=C_CHG,
                        weight="bold", zorder=14,
                        bbox=dict(boxstyle="round,pad=0.22", fc="#fdf6e3",
                                  ec=C_CHG, lw=0.9))
        ax.plot([t.bar, t.bar], [t.tp2, t.sl], color=col, lw=1.1,
                alpha=0.25 if ref else 0.45, ls="--" if ref else ":",
                zorder=6)
        if ref:
            ax.annotate(f"K{t.kid} {t.r:+.2f}R bar {t.bar} (V01 entfaellt)",
                        (t.bar, t.basis), textcoords="offset points",
                        xytext=(0, -30), ha="center", fontsize=fs - 0.5,
                        color="#666666", zorder=10,
                        bbox=dict(boxstyle="round,pad=0.18", fc="white",
                                  alpha=0.55, ec=col, lw=0.5, ls="--"))
        else:
            # Auflage A-3: Kollisions-Offsets fuer das K67-Cluster;
            # ausserhalb der Tabelle gilt unveraendert die Bestandsformel.
            _xy = ANNOT_OFFSET.get((int(t.bar), int(t.kid)),
                                   (0, 16 if t.richtung == "SHORT"
                                    else -25))
            ax.annotate(f"K{t.kid} {t.r:+.2f}R\nbar {t.bar}",
                        (t.bar, t.basis), textcoords="offset points",
                        xytext=_xy,
                        ha="center", fontsize=fs, color=col, zorder=10,
                        bbox=dict(boxstyle="round,pad=0.18", fc="white",
                                  alpha=0.82, ec=col, lw=0.5))


def _kanten_y_engine(e, xs) -> np.ndarray:
    """Engine-Linie OHNE Override (Referenz fuer den verdraengten Wert).

    Vor dem ersten bestaetigten Touch (``pivot_bar + 2 <= k``) ist die Linie
    maskiert (NaN); promovierte Primaer-Anker sind eingefroren (flach).
    """
    if e.ist_prim_anker:
        return np.full(len(xs), float(e.basis), dtype=float)
    ys = np.full(len(xs), np.nan, dtype=float)
    for i, k in enumerate(xs):
        if any(b + 2 <= k for b, _ in e.wicks):
            ys[i] = float(e.basis_bei(k))
    return ys


def kanten_y(e, xs) -> np.ndarray:
    """WIRKSAME Kantenlinie je Bar (Stufe).

    Grundlage sind die kausalen ``basis_bei(k)``; liegt fuer (Phase, Kante) ein
    Niveau-Override vor, wird an dessen Stelle der phasen-lokale Preis
    gezeichnet (Spez Abschnitt 66.2). Ohne Override -- also im gesamten Modus
    V01 -- liefert die Funktion exakt ``basis_bei(k)``.
    """
    ys = _kanten_y_engine(e, xs)
    if not OVERRIDE_INFO:
        return ys
    out = ys.copy()
    for i, k in enumerate(xs):
        if np.isnan(ys[i]):
            continue
        out[i] = adapter.angewandte_basis(int(k), int(e.kid), float(ys[i]))
    return out


def kanten_verlauf(e, xs):
    """Kausaler Verlauf: (ys, stufen) mit stufen = [(bar, preis)] je Wechsel.

    ``ys`` ist die gezeichnete Linie (``basis_bei(k)`` je Bar, NaN vor der
    Bestaetigung). ``stufen`` enthaelt den ersten bestaetigten Wert und
    danach jeden Bar, an dem sich der Preis aendert.
    """
    ys = kanten_y(e, xs)
    stufen = []
    prev = None
    for k, v in zip(xs, ys):
        if v is None or np.isnan(v):
            continue
        v = float(v)
        if prev is None or abs(v - prev) > 1e-12:
            stufen.append((int(k), v))
            prev = v
    return ys, stufen


def _plateau_label(e, xs, prefix: str) -> Optional[Tuple[str, float, float]]:
    """Label einer Override-Linie (Spez Abschnitt 66.2, Plateau-Syntax).

    Syntax: ``<prefix><kid> <native_start> -> <override> (<phase>-Override)
    -> <native_ende> *``. ``native_start``/``native_ende`` sind die vom
    Override **verdraengten** bzw. nach Verlassen des Fensters geltenden
    kausalen Werte -- nicht die gezeichneten Plateaupreise.

    Args:
        e: Kante.
        xs: Bar-Fenster der Zeichnung.
        prefix: ``"K"`` oder ``"s"``.

    Returns:
        ``(text, v0_wirksam, v_ende)`` oder None, wenn kein Override vorliegt.
    """
    info = _override_info(e.kid)
    if info is None:
        return None
    _preis, _phase, _start, _ende = info
    nat = _kanten_y_engine(e, xs)
    wirk = kanten_y(e, xs)
    mask = ~np.isnan(wirk)
    if not mask.any():
        return None
    pos = np.flatnonzero(mask)
    i0, i1 = int(pos[0]), int(pos[-1])
    n_start = (float(nat[i0]) if not np.isnan(nat[i0])
               else float(wirk[i0]))
    if int(xs[i1]) <= _ende:
        n_ende, _rest = float(_preis), " (Plateau bis Fensterende)"
    else:
        n_ende, _rest = (float(nat[i1]) if not np.isnan(nat[i1])
                         else float(wirk[i1])), ""
    txt = (f"{prefix}{e.kid} {n_start:.3f} -> {_preis:.3f} "
           f"({_phase}-Override) -> {n_ende:.3f} *{_rest}")
    return txt, float(wirk[i0]), n_ende


def kanten_label(e, xs, prefix: str = "K") -> tuple:
    """(text, geaendert, v0, v1, norm_abweichung) fuer das K-Label mit Preis.

    Regel (Spez Abschnitt 54):
    * Der K-Name traegt den kausalen Preis: ``K<kid> <preis>``.
    * Aendert sich der Preis entlang der Linie, wird der Verlauf
      ``v_start -> v_ende`` ausgegeben und mit ``*`` markiert.
    * Ist fuer die Kante eine v0.4-Provenienz-Norm hinterlegt und weicht der
      kausale Endwert davon ab, wird ``Norm <wert>`` angehaengt (Option (b),
      Abschnitt 37.4: Norm bleibt Zitat, der kausale Wert operiert).
    * Override-Linien nutzen die Plateau-Syntax nach Abschnitt 66.2; der
      ``*``-Marker ist dort verpflichtend.
    """
    _ys, stufen = kanten_verlauf(e, xs)
    if prefix == "K":
        _pl = _plateau_label(e, xs, prefix)
        if _pl is not None:
            _ptxt, _pv0, _pv1 = _pl
            norm = NORM.get(e.kid)
            norm_ab = bool(norm is not None
                           and abs(_basis_von(e.kid) - norm) > 1e-9)
            if norm_ab:
                _ptxt += f"  Norm {norm:.4f}"
            GEAENDERT[e.kid] = (_pv0, _pv1, len(stufen))
            return _ptxt, True, _pv0, _pv1, norm_ab
    if not stufen:
        return f"{prefix}{e.kid} --", False, None, None, False
    v0, v1 = stufen[0][1], stufen[-1][1]
    geaendert = len(stufen) > 1 and abs(v1 - v0) > 1e-12
    if geaendert:
        GEAENDERT[e.kid] = (v0, v1, len(stufen))
    norm = NORM.get(e.kid) if prefix == "K" else None
    # Norm-Vergleich auf dem VOLLEN Verlauf (Referenz-Bar 1259), nicht auf dem
    # ggf. beschnittenen Zeichenfenster - sonst kippt die Aussage je Panel.
    norm_ab = bool(norm is not None
                   and abs(_basis_von(e.kid) - norm) > 1e-9)
    txt = (f"{prefix}{e.kid} " + (f"{v0:.3f} -> {v1:.3f} *" if geaendert
                                  else f"{v1:.3f}"))
    if norm_ab:
        txt += f"  Norm {norm:.4f}"
    return txt, geaendert, v0, v1, norm_ab


def zeichne_kanten_label(ax, e, xs, fs: float, prio: bool = False,
                         zorder: int = 7, max_stufen: int = 10,
                         prefix: str = "K", stufen_texte: bool = False) -> bool:
    """Schreibt das K-Label mit Preis an die Linie und markiert Wechselpunkte.

    Args:
        stufen_texte: Zusaetzlich an jedem Preiswechsel den Wert als Kleintext
            schreiben (nur fuer Grenzkanten, sonst zu unruhig).

    Returns:
        True, wenn der Preis entlang der Linie gewechselt hat.
    """
    col = KANTEN_COL.get(e.seite, "#333333")
    txt, geaendert, v0, _v1, norm_ab = kanten_label(e, xs, prefix)
    if v0 is None:
        return False
    _ys, stufen = kanten_verlauf(e, xs)
    xtex = stufen[0][0] + 1
    herv = bool(prio or geaendert or norm_ab)
    ax.text(xtex, v0, txt, fontsize=fs, color=col, va="center", zorder=zorder,
            weight="bold" if herv else "normal",
            bbox=(dict(boxstyle="round,pad=0.12", fc="white", alpha=0.75,
                       ec=C_CHG, lw=0.6) if norm_ab or geaendert else None))
    if stufen_texte and len(stufen) <= max_stufen:
        for k, v in stufen[1:]:
            ax.text(k + 1, v, f"{v:.3f}", fontsize=max(4.6, fs - 1.8),
                    color=col, alpha=0.9, va="bottom", zorder=zorder,
                    bbox=dict(boxstyle="round,pad=0.05", fc="white",
                              alpha=0.55, ec="none"))
    return geaendert


_GATE_RE = re.compile(r"bar\s+(\d+)\s+(SHORT|LONG)\s+K\s*(\d+)\s+"
                      r"basis=[\d.]+\s+sweep=([\d.]+)")


def _gate_punkte(liste) -> list:
    """[(bar, sweep_px, kid, richtung)] aus den Engine-Sperrlisten."""
    out = []
    for s in liste:
        m = _GATE_RE.search(s)
        if m:
            out.append((int(m.group(1)), float(m.group(4)), int(m.group(3)),
                        m.group(2)))
    return out


GATE_Q29 = _gate_punkte(st1.get("quartil_liste") or [])
GATE_M6 = _gate_punkte(st1.get("blocker_liste") or [])


def mark_gates(ax, x0: int, x1: int) -> None:
    """Sperr-Marker je Bar: x = Q29 (Quartil), ^ = M6 (Aussenwand)."""
    for b, px, _kid, _r in GATE_Q29:
        if x0 <= b <= x1:
            ax.plot(b, px, "x", ms=7, color=C_GATE, zorder=8,
                    mec="black", mew=0.3)
    for b, px, _kid, _r in GATE_M6:
        if x0 <= b <= x1:
            ax.plot(b, px, "^", ms=7, color=C_GATE, zorder=8,
                    mec="black", mew=0.3)


def mark_override_grenzen(ax, x0: int, x1: int, y_oben: float) -> None:
    """Override-Zone als Grenzlinien markieren (Spez Abschnitt 66.3, Regel 15).

    Bewusst KEIN ``axvspan``: die Flaeche kollidiert farblich mit der
    Regime-Zone und dem Preiswechsel-Rahmen des Labels. Die Grenzlinien
    trennen Regime-Gueltigkeit (``start_bar``) von Kanten-Existenz
    (``pivot_bar + 2``) und Austritt (``end_bar + 1``).

    Args:
        ax: Zielachse.
        x0: Linke Fenstergrenze.
        x1: Rechte Fenstergrenze.
        y_oben: y-Wert fuer die Kleintexte.
    """
    for _kid, (_preis, _phase, _start, _ende) in sorted(OVERRIDE_INFO.items()):
        for _bar, _txt in ((_start, f"Override {_phase} {_preis:.4f} "
                                    f"ab Bar {_start}"),
                           (_ende + 1, f"{_phase}-Override endet Bar {_ende}")):
            if not (x0 <= _bar <= x1):
                continue
            ax.axvline(_bar, color=C_CHG, lw=1.1, ls="--", alpha=0.80,
                       zorder=5)
            ax.text(_bar + 2, y_oben, _txt, fontsize=7.5, color=C_CHG,
                    va="top", ha="left", zorder=11,
                    bbox=dict(boxstyle="round,pad=0.10", fc="white",
                              alpha=0.72, ec=C_CHG, lw=0.4))


def time_axis(ax, x0: int, x1: int,
              ticks: Union[int, Sequence[int]] = 13) -> None:
    """Zeitachse = Bar-Zeit (BKZ, ohne Offset); Bar-Index primaer.

    Args:
        ticks: Anzahl der Ticks (Bestandsverhalten) oder explizite
            Bar-Positionen (Auflage A-1, nur Modus V016: 25er-Raster).
    """
    tk = (np.linspace(x0, x1, ticks).astype(int)
          if isinstance(ticks, int) else np.asarray(ticks, dtype=int))
    ax.set_xticks(tk)
    ax.set_xticklabels([ts.iloc[i].strftime("%d.%m %H:%M") for i in tk],
                       fontsize=8)
    ax.set_xlim(x0 - 4, x1 + 4)
    ax.grid(alpha=0.15, ls=":")
    ax.set_xlabel("Bar-Zeit (BKZ, M15) | Bar-Index primaer",
                  fontsize=8.5, color="#555555")


def stats_panel(axs, zeilen) -> None:
    """Sichtpruefungs-Konvention: Statistik mittig im Panel."""
    axs.axis("off")
    axs.text(0.5, 0.97, "\n".join(zeilen), fontsize=10.5, va="top",
             ha="center", family="monospace", transform=axs.transAxes)


def legend(ax, handles, ncol: int = 2, fs: float = 9.0) -> None:
    """Sichtpruefungs-Konvention: Legende oben links."""
    ax.legend(handles=handles, loc="upper left", fontsize=fs, ncol=ncol,
              framealpha=0.92)


LEG_BASIS = [
    Line2D([0], [0], color=C_OBEN, lw=1.7, label="OBEN-Kante (SE)"),
    Line2D([0], [0], color=C_UNTEN, ls="--", lw=1.7, label="UNTEN-Kante (SE)"),
    Line2D([0], [0], marker="o", color="w", mfc=C_SHORT, ms=8,
           label="SHORT-Trade (H1 klein / H2 gross, gefuellt)"),
    Line2D([0], [0], marker="o", color="w", mfc=C_LONG, ms=8,
           label="LONG-Trade (H1 klein / H2 gross, gefuellt)"),
    Line2D([0], [0], marker="^", color="w", mfc="#ff7f0e", ms=7,
           label="H2-Neugeburt (Staffel)"),
    Line2D([0], [0], marker="x", color="w", mfc="red", ms=7,
           label="Sweep-Sperre"),
    Line2D([0], [0], marker="x", color="w", mfc=C_GATE, ms=7,
           label="Sperre Q29 (Quartil)"),
    Line2D([0], [0], marker="^", color="w", mfc=C_GATE, ms=7,
           label="Sperre M6 (Aussenwand)"),
    Line2D([0], [0], marker="*", color="w", mfc=C_CHG, ms=11,
           label="Preiswechsel (Label: v0 -> v1 *)"),
]


def _leg_basis_sweep() -> list:
    """LEG_BASIS fuer Panels 01/03/05 mit bereinigtem Sweep-Marker.

    Auflage A-2 (§71): nur im Modus V016 wird das rote Sweep-Kreuz durch
    den Diamond ersetzt. Panel 02 fuehrt unveraendert ``LEG_BASIS`` --
    der H1-Regressionsanker ``d9f35876...`` / 899.249 B bleibt
    byte-identisch (Ausnahme analog A-5, §66.5-Entscheid).

    Returns:
        Legenden-Handles; in V01/V014/V015 ist es ``LEG_BASIS`` selbst.
    """
    if not _AUFL:
        return LEG_BASIS
    return [Line2D([0], [0], marker=SWEEP_MARKER, color="w", mfc="red",
                   ms=SWEEP_MARKER_MS, label="Sweep-Sperre")
            if h.get_label() == "Sweep-Sperre" else h
            for h in LEG_BASIS]

# Zusatz-Legende nur im Override-Modus; im Modus V01 bleibt die Legende
# unveraendert (Byte-Identitaet des arretierten Satzes).
LEG_MODUS: list = [] if not KONF.k67_override_aktiv else [
    Line2D([0], [0], marker="o", color="w", mfc="none", mec="#7f7f7f",
           ms=9, label="v0.1-Referenz-Trade (im V014-Lauf entfallen)"),
    Line2D([0], [0], color=C_CHG, ls="--", lw=1.1,
           label=f"Override-Grenze {KONF.niveau_override_wert:.4f} "
                 f"(P9 848 / 1020)"),
    Line2D([0], [0], marker="*", color="w", mfc=C_CHG, ms=11,
           label="Plateau-Label: native -> Override -> native *"),
] + ([
    Line2D([0], [0], marker="o", color="w", mfc="none", mec=C_CHG, ms=11,
           mew=2.2, label="G4-Phasenboden-Reclaim (Hook 3, §69.8)"),
] if KONF.g4_aktiv else [])

geb_h2 = [e for e in list(scan["edges"]) + list(scan["seeds"])
          if e.geburts_bar >= box_end]
tombs = scan.get("tombstones") or []
r21 = scan.get("r21_geloescht") or []
r21_gel = [r for r in r21 if r[1] >= 0]
r21_ges = [r for r in r21 if r[1] < 0]
geschrieben = []


def _prepass_wechsel() -> dict:
    """Alle Kanten mit Preiswechsel ueber die VOLLE Spanne (fensterunabhaengig).

    Returns:
        ``{kid: (v_start, v_ende, n_stufen)}`` - Grundlage der Pflichtangabe
        ``K<kid> <preis>`` bzw. ``K<kid> <v0> -> <v1> *`` (Spez Abschnitt 54).
    """
    chg = {}
    voll = np.arange(0, n)
    for e in list(scan["edges"]) + list(scan["seeds"]):
        _ys, stufen = kanten_verlauf(e, voll)
        if len(stufen) > 1 and abs(stufen[-1][1] - stufen[0][1]) > 1e-12:
            chg[e.kid] = (stufen[0][1], stufen[-1][1], len(stufen))
    return chg


WECHSEL = _prepass_wechsel()

# §72.8: Protokollzeile der Niveauwechsel-Kennzahl. Ab V017/V018 wird der
# Wortlaut erweitert; V01..V016 behalten ihre Zeile (Byte-Identitaet).
_NW_LOG: Final[str] = (
    f"Linien mit Netto-Preiswechsel: {len(WECHSEL)} "
    f"(Baseline {KONF.netto_preiswechsel_baseline}) | "
    f"Niveauwechsel gesamt: {NIVEAUWECHSEL} "
    f"(Baseline {KONF.niveauwechsel_baseline})" if _NEU else
    f"Preiswechsel-Linien (Label 'v0 -> v1 *'): {len(WECHSEL)}")

_BY_KID: dict = {}
for _e in list(scan["edges"]) + list(scan["seeds"]):
    _BY_KID[_e.kid] = _e
NORM_REF_BAR = 1259                  # Referenz-Bar der Reserve-Auditierung


def _basis_von(kid: int, ref_bar: int = NORM_REF_BAR) -> float:
    """Kausale Basis ``basis_bei(ref_bar)`` der Kante ``kid``.

    Args:
        kid: Kanten-ID.
        ref_bar: Referenz-Bar (Default 1259).

    Returns:
        Basis als float oder NaN, wenn die Kante nicht im Katalog liegt.
    """
    e = _BY_KID.get(kid)
    return float(e.basis_bei(ref_bar)) if e is not None else float("nan")


def _zeile_kopf() -> str:
    """Kopfzeile des Statistikblocks (modusabhaengig, Abschnitt 66.5/§70)."""
    _ver = ("ADAPTER v0.16 (G4 + A-1..A-4)" if _AUFL
            else "ADAPTER v0.15 G4")
    if KONF.g4_aktiv:
        return (f"{_ver}  P9 (848-1020) | Decke K67 mit "
                f"Niveau-Override {KONF.niveau_override_wert:.4f} / "
                f"Boden K77 deklariert "
                f"{P9_BODEN_RECLAIM.boden_deklariert_literal:.4f} | "
                f"Regel §69.8 aktiv (Hook 3) | P12 = RESERVE (inaktiv)")
    if KONF.k67_override_aktiv:
        return (f"ADAPTER v0.14  P9 (848-1020) | Decke K67 mit "
                f"Niveau-Override {KONF.niveau_override_wert:.4f} / "
                f"Boden K77 | ziel_preis_short 68.3700 | touch_band 0.12 % | "
                f"P12 = RESERVE (inaktiv) | Luecken = BLOCKIERT")
    return (f"ADAPTER v0.1  P9 (848-1020) | Decke K67 / Boden K77 | "
            f"ziel_preis_short 68.3700 | touch_band 0.12 % | "
            f"P12 = RESERVE (inaktiv) | Luecken = BLOCKIERT")


def _zeile_beitrag(p9: list) -> str:
    """Beitragszeile des P9-Fensters (modusabhaengig, Abschnitt 66.5)."""
    if KONF.k67_override_aktiv:
        return ("REGIME-BEITRAG : "
                + " + ".join(f"K{t.kid}@{t.bar} {t.r:+.4f}" for t in p9)
                + f" = {sum(t.r for t in p9):+.4f} R   |   "
                  "v0.1-Referenz: K73@980 +2.4119 + K73@1020 +3.0093 "
                  "= +5.4212 R (entfaellt)")
    return (f"REGIME-BEITRAG : K73@980 "
            f"{[t.r for t in p9 if t.kid == 73 and t.bar == 980][0]:+.4f} R"
            f" + K73@1020 "
            f"{[t.r for t in p9 if t.kid == 73 and t.bar == 1020][0]:+.4f} R"
            f" = {sum(t.r for t in p9 if t.kid == 73):+.4f} R   |   "
            f"K59@853 entfaellt (Baseline-Trade)")


def _zeilen_extra() -> list:
    """Zusatzzeilen nur im Override-Modus (leer im Modus V01).

    Ab V017/V018 kommt eine Zeile zur Engine-Generation hinzu (§72.4/§72.8).
    V01..V016 bleiben wortgleich -> Byte-Identitaet der arretierten Saetze.
    """
    if not KONF.k67_override_aktiv:
        return []
    return [
        f"OVERRIDE (Abschnitt 66): K67 = {KONF.niveau_override_wert:.4f} "
        f"nur in P9 (848-1020) | Grenzlinien 848 / 1021 | "
        f"Quartett {list(KONF.quartett_bars)} = {QUARTETT_R:+.6f} R",
        "REFERENZ-MARKER (66.4): " + (", ".join(
            f"K{t.kid}@{t.bar} {t.r:+.4f}"
            for t in sorted(REFERENZ, key=lambda x: x.bar)) or "keine")
        + " (im V014-Lauf entfallen)",
    ] + ([
        f"ENGINE §72: Kanten-Extremum (OBEN min / UNTEN max) + "
        f"M6-Kausalitaetsheilung | {ENGINE_NAME} {ENGINE_SHA[:16]}... | "
        f"Linien mit Netto-Preiswechsel {len(WECHSEL)} "
        f"(Baseline {KONF.netto_preiswechsel_baseline}) | "
        f"Niveauwechsel gesamt {NIVEAUWECHSEL} "
        f"(Baseline {KONF.niveauwechsel_baseline}) | "
        f"H1 {len(h1_1)} Trades / {sum(t.r for t in h1_1):+.6f} R "
        f"(vorher {7 if _V18 else 8} / "
        f"{'+39.919584' if _V18 else '+38.964262'} R)",
    ] if _NEU else []) + G4_ZEILEN


# =========================================================== 01 GESAMT
def png_01_gesamt():
    fig, (ax1, axs) = plt.subplots(
        2, 1, figsize=(22, 13),
        gridspec_kw={"height_ratios": [4.2, 1.25], "hspace": 0.09})
    y0, y1 = float(lo.min()), float(hi.max())
    shade_phases(ax1, y0, y1, 0, n - 1)
    ax1.axvspan(0, box_end, color="gray", alpha=0.10, zorder=0)
    ax1.axvline(box_end, color="black", lw=1.6, ls=":", alpha=0.9, zorder=4)
    ax1.text(6, y1, f"H1 BOX (bars < {box_end})", fontsize=11, va="top",
             color="#444444", zorder=11)
    ax1.text(n - 8, y1, f"H2 EXPANSION (bars >= {box_end})", fontsize=11,
             va="top", ha="right", color="#1f77b4", zorder=11)
    draw_candles(ax1, 0, n - 1, "candle")
    for tk, _s, tp in tombs:
        ax1.plot([tk, n - 1], [tp, tp], color="gray", lw=0.8, ls=":",
                 alpha=0.30, zorder=1)
    for e in sorted(scan["edges"], key=lambda x: (x.seite, x.basis)):
        col = C_OBEN if e.seite == "OBEN" else C_UNTEN
        ls = "-" if e.seite == "OBEN" else "--"
        bf = min(b for b, _ in e.wicks)
        bl = max(b for b, _ in e.wicks)
        x0, x1 = max(0, bf - 20), min(n - 1, bl + 20)
        if x1 <= x0:
            continue
        _xs = np.arange(x0, x1 + 1)
        ax1.plot(_xs, kanten_y(e, _xs),
                 color=col, lw=0.9, ls=ls, alpha=0.40, zorder=4)
        zeichne_kanten_label(ax1, e, _xs, fs=6.2,
                             stufen_texte=(e.kid in NORM_KIDS))
    for e in geb_h2:
        ax1.plot(e.geburts_bar, e.basis, "^", ms=5.5, color="#ff7f0e",
                 zorder=7, mec="black", mew=0.3)
    for (b, _se, px, _ref, _dd) in scan["sweep_sperren"]:
        ax1.plot(b, px, SWEEP_MARKER, ms=SWEEP_MARKER_MS, color="red",
                 zorder=6, mec="black", mew=0.3)
    mark_gates(ax1, 0, n - 1)
    if KONF.alt_trades_einblenden:
        mark_trades(ax1, REFERENZ, fs=7.5, stil="referenz")
    mark_trades(ax1, V1, fs=7.5)
    mark_override_grenzen(ax1, 0, n - 1, y1)
    time_axis(ax1, 0, n - 1)
    _ad = (f"Engine {_VTAG} (Kanten-Extremum + M6-Heilung): "
           f"P9-Override + Regel" if _NEU else
           ("Adapter v0.16 (G4 + Auflagen A-1..A-4): P9-Override + Regel"
            if _AUFL else
            ("Adapter v0.15 G4: P9-Override + Phasenboden-Regel"
             if KONF.g4_aktiv else
             ("Adapter v0.14: P9 mit K67-Override"
              if KONF.k67_override_aktiv
              else "Adapter v0.1: P9 aktiv (848-1020)"))))
    ax1.set_title(
        f"AUG SICHTTEST 01/05 -- GESAMT (Bars 0..{n - 1}) | {_ad} | "
        f"{len(V1)} Trades / {R1:+.4f} R | "
        f"Baseline-Referenz {len(V0)} / {R0:+.4f} R", fontsize=12.5)
    _kopf = _zeile_kopf()
    _p9 = sorted((t for t in V1 if 848 <= t.bar <= 1020),
                 key=lambda x: x.bar)
    _beitrag = _zeile_beitrag(_p9)
    # §72.8: Niveauwechsel-Kennzahl. Wortlaut nur ab V017 neu -- V01..V016
    # behalten exakt ihre bisherige Zeile (Byte-Identitaet).
    _h1_mark = (f"<- SOLL {_VTAG} (neu arretiert, Engine-Extremum)" if _NEU
                else "<- arretierte Baseline (bit-identisch)")
    _nw_txt = (f"Linien mit Netto-Preiswechsel: {len(WECHSEL)} "
               f"(Baseline {KONF.netto_preiswechsel_baseline}) | "
               f"Niveauwechsel gesamt: {NIVEAUWECHSEL} "
               f"(Baseline {KONF.niveauwechsel_baseline})" if _NEU
               else f"Preiswechsel-Linien (*): {len(WECHSEL)}")
    stats_panel(axs, [
        _kopf,
        f"H1 BOX  (entry_bar < {box_end}): {len(h1_1):2d} Trades / "
        f"{sum(t.r for t in h1_1):+9.6f} R   {_h1_mark}",
        f"H2 EXP  (entry_bar >= {box_end}): {len(h2_1):2d} Trades / "
        f"{sum(t.r for t in h2_1):+9.4f} R   "
        f"SHORT {sum(1 for t in h2_1 if t.richtung == 'SHORT')}/"
        f"{sum(t.r for t in h2_1 if t.richtung == 'SHORT'):+.2f} | "
        f"LONG {sum(1 for t in h2_1 if t.richtung == 'LONG')}/"
        f"{sum(t.r for t in h2_1 if t.richtung == 'LONG'):+.2f}",
        f"GESAMT ADAPTER : {len(V1):2d} Trades / {R1:+9.4f} R   |   "
        f"BASELINE V0: {len(V0)} / {R0:+.4f} R   |   "
        f"Delta {R1 - R0:+.4f} R",
        _beitrag,
        f"KANTEN: {len(scan['edges'])} edges + {len(scan['seeds'])} seeds | "
        f"R21 {len(r21_gel)} geloescht / {len(r21_ges)} Geburten gesperrt | "
        f"{len(tombs)} Tombstones | H2-Neugeburten {len(geb_h2)} | "
        f"Promotionen {st1.get('promotionen')}",
        f"STATS V1: blocker {st1.get('blocker')} | quartil "
        f"{st1.get('quartil_blockiert')} | zyklus {st1.get('zyklus_blockiert')}"
        f" | kein_raum {st1.get('kein_raum')} | V-S {st1.get('v_s')}",
        f"SPERR-MARKER (violett): x = Q29-Quartil {len(GATE_Q29)} | "
        f"^ = M6-Aussenwand {len(GATE_M6)} | Zyklus-Sperren "
        f"{st1.get('zyklus_blockiert')} (nicht markiert)",
        f"PREIS AN DER LINIE (Pflicht): jedes K-Label traegt den kausalen "
        f"Preis | {_nw_txt} | "
        f"Norm-Abweichung (Option b, Norm als Zitat mitgefuehrt): "
        f"{sum(1 for k in NORM if abs(_basis_von(k) - NORM[k]) > 1e-9)} "
        f"von {len(NORM)} Grenzkanten {sorted(NORM)}",
    ] + _zeilen_extra())
    legend(ax1, _leg_basis_sweep() + [
        Line2D([0], [0], color="gray", ls=":", lw=1.0,
               label="Tombstone-Band (R21)"),
    ] + LEG_MODUS)
    fig.subplots_adjust(left=0.04, right=0.995, top=0.955, bottom=0.065)
    out = OUTDIR / f"{PRAEFIX}01_gesamt.png"
    fig.savefig(out, dpi=300)
    plt.close(fig)
    return out


# =========================================================== 02 H1 BOX
def png_02_h1_box():
    X1 = box_end + 20
    fig, (ax1, axs) = plt.subplots(
        2, 1, figsize=(20, 12),
        gridspec_kw={"height_ratios": [4.2, 1.25], "hspace": 0.10})
    y0, y1 = float(lo[:X1].min()), float(hi[:X1].max())
    ax1.axvspan(0, box_end, color="gray", alpha=0.10, zorder=0)
    ax1.axvline(box_end, color="black", lw=1.6, ls=":", alpha=0.9, zorder=4)
    ax1.text(6, y1, "H1 BOX 10.08.-18.08. (arretiert)", fontsize=11,
             va="top", color="#444444", zorder=11)
    draw_candles(ax1, 0, X1, "candle")
    for e in sorted(scan["edges"], key=lambda x: (x.seite, x.basis)):
        col = C_OBEN if e.seite == "OBEN" else C_UNTEN
        ls = "-" if e.seite == "OBEN" else "--"
        bf = min(b for b, _ in e.wicks)
        bl = max(b for b, _ in e.wicks)
        if bf > X1:
            continue
        x0, x1 = max(0, bf - 15), min(X1, bl + 15)
        if x1 <= x0:
            continue
        _xs = np.arange(x0, x1 + 1)
        ax1.plot(_xs, kanten_y(e, _xs),
                 color=col, lw=1.0, ls=ls, alpha=0.45, zorder=4)
        zeichne_kanten_label(ax1, e, _xs, fs=7.0,
                             stufen_texte=(e.kid in NORM_KIDS))
    for (b, _se, px, _ref, _dd) in scan["sweep_sperren"]:
        if b <= X1:
            ax1.plot(b, px, "x", ms=8, color="red", zorder=6, mec="black",
                     mew=0.3)
    mark_gates(ax1, 0, X1)
    mark_trades(ax1, h1_1, fs=8.0)
    time_axis(ax1, 0, X1, 12)
    # §72.5: H1 ist ab V017 NEU arretiert. Wortlaut nur dort neu.
    _p02_note = (f"Engine {_VTAG} (Kanten-Extremum, H1 neu arretiert)"
                 if _NEU else "arretierte Baseline")
    _h1_soll = (f"<- SOLL {_VTAG} (neu arretiert)" if _NEU
                else "<- SOLL arretiert (bit-identisch)")
    ax1.set_title(
        f"AUG SICHTTEST 02/05 -- H1 BOX (Bars 0..{X1}) | {_p02_note} "
        f"| {len(h1_1)} Trades / {sum(t.r for t in h1_1):+.6f} R", fontsize=12.5)
    stats_panel(axs, [
        f"H1 BOX (entry_bar < {box_end}): {len(h1_1)} Trades / "
        f"{sum(t.r for t in h1_1):+.6f} R   {_h1_soll}",
        f"SHORT {sum(1 for t in h1_1 if t.richtung == 'SHORT')} / "
        f"{sum(t.r for t in h1_1 if t.richtung == 'SHORT'):+.4f} R   |   "
        f"LONG {sum(1 for t in h1_1 if t.richtung == 'LONG')} / "
        f"{sum(t.r for t in h1_1 if t.richtung == 'LONG'):+.4f} R",
        "Trade-Detail: " + " | ".join(
            f"K{t.kid}@{t.bar} {t.r:+.2f}" for t in sorted(h1_1,
                                                           key=lambda x: x.bar)),
        f"Der Adapter greift ausschliesslich ab bar >= {adapter.start_scope_bar}"
        f" -> H1 ist strukturell unberuehrbar (MAKRO)."
        + ("" if not _NEU else
           f" In {_VTAG} wandert H1 dennoch, weil die KANTENFORMEL selbst im"
           " Motor liegt (§72.5) -- der Adapter bleibt MAKRO."),
    ])
    legend(ax1, LEG_BASIS)
    fig.subplots_adjust(left=0.045, right=0.995, top=0.955, bottom=0.07)
    out = OUTDIR / f"{PRAEFIX}02_h1_box.png"
    fig.savefig(out, dpi=300)
    plt.close(fig)
    return out


# =========================================================== 03 H2 PHASEN
def png_03_h2_phasen():
    X0 = 620
    fig, (ax1, axs) = plt.subplots(
        2, 1, figsize=(22, 12),
        gridspec_kw={"height_ratios": [4.2, 1.25], "hspace": 0.10})
    y0, y1 = float(lo[X0:].min()), float(hi[X0:].max())
    shade_phases(ax1, y0, y1, X0, n - 1)
    ax1.axvline(box_end, color="black", lw=1.6, ls=":", alpha=0.9, zorder=4)
    draw_candles(ax1, X0, n - 1, "candle")
    for tk, _s, tp in tombs:
        if tk >= X0:
            ax1.plot([X0, n - 1], [tp, tp], color="gray", lw=0.8, ls=":",
                     alpha=0.35, zorder=1)
    for e in sorted(scan["edges"], key=lambda x: (x.seite, x.basis)):
        if max(b for b, _ in e.wicks) < X0:
            continue
        col = C_OBEN if e.seite == "OBEN" else C_UNTEN
        ls = "-" if e.seite == "OBEN" else "--"
        bf = min(b for b, _ in e.wicks)
        bl = max(b for b, _ in e.wicks)
        x0, x1 = max(X0, bf - 20), min(n - 1, bl + 20)
        if x1 <= x0:
            continue
        _xs = np.arange(x0, x1 + 1)
        ax1.plot(_xs, kanten_y(e, _xs),
                 color=col, lw=1.0, ls=ls, alpha=0.45, zorder=4)
        zeichne_kanten_label(ax1, e, _xs, fs=6.8,
                             stufen_texte=(e.kid in NORM_KIDS))
    for e in geb_h2:
        ax1.plot(e.geburts_bar, e.basis, "^", ms=6, color="#ff7f0e",
                 zorder=7, mec="black", mew=0.35)
    for (b, _se, px, _ref, _dd) in scan["sweep_sperren"]:
        if b >= X0:
            ax1.plot(b, px, SWEEP_MARKER, ms=SWEEP_MARKER_MS_GROSS,
                     color="red", zorder=6, mec="black", mew=0.3)
    mark_gates(ax1, X0, n - 1)
    if KONF.alt_trades_einblenden:
        mark_trades(ax1, [t for t in REFERENZ if t.bar >= X0], fs=7.5,
                    stil="referenz")
    mark_trades(ax1, h2_1, fs=7.5)
    mark_override_grenzen(ax1, X0, n - 1, y1)
    time_axis(ax1, X0, n - 1, 14)
    ax1.set_title(
        f"AUG SICHTTEST 03/05 -- H2 + PHASEN (Bars {X0}..{n - 1}) | "
        f"gruen = P9 AKTIV, grau = P12 RESERVE, rot schraffiert = Luecke "
        f"(BLOCKIERT) | {len(h2_1)} Trades / {sum(t.r for t in h2_1):+.4f} R",
        fontsize=12.5)
    if KONF.k67_override_aktiv:
        _p9z = (("P9-Benchmark v0.18 (BKZ/UTC, Engine-Extremum): "
                 if _V18 else
                 "P9-Benchmark v0.17 (Engine-Extremum): " if _V17 else
                 ("P9-Benchmark v0.15 G4: " if KONF.g4_aktiv
                  else "P9-Benchmark v0.14 (Quartett): ")) + " | ".join(
            f"K{t.kid}@{t.bar} {t.r:+.4f} R ({t.stufe})"
            for t in sorted((x for x in V1 if 848 <= x.bar <= 1020),
                            key=lambda x: x.bar))
            + f" | QUARTETT {QUARTETT_R:+.4f} R   ||   "
              f"P9-REGIME-BEITRAG {P9_BEITRAG:+.4f} R   ||   "
              "v0.1-Referenz entfaellt: K73@980 +2.4119, K73@1020 +3.0093")
    else:
        _p9z = (f"P9-Benchmark: K73@980 +2.4119 R (STUFE_2_KERZE_2, "
                f"entry 69.4910) | K73@1020 +3.0093 R (STUFE_1_IN_BAR, "
                f"entry 69.5780) | Summe +5.4212 R")
    stats_panel(axs, [
        f"H2 (entry_bar >= {box_end}): {len(h2_1)} Trades / "
        f"{sum(t.r for t in h2_1):+.4f} R   |   "
        f"Baseline V0 H2: {len(h2_0)} / {sum(t.r for t in h2_0):+.4f} R   |   "
        f"Delta {sum(t.r for t in h2_1) - sum(t.r for t in h2_0):+.4f} R",
        "H2-Trades: " + " | ".join(
            f"K{t.kid}@{t.bar} {t.r:+.2f}" for t in sorted(h2_1,
                                                           key=lambda x: x.bar)),
        f"Regime-Fenster: P9 848-1020 (aktiv, Ziel 68.3700) | P10 1030-1075, "
        f"P11 1082-1134, P12 1171-1272 (nicht aktiv) | "
        f"Luecken 641-847, 1021-1029, 1076-1081, 1135-1170, 1273-{n - 1}",
        _p9z,
        # §72.5: Der Transition-Park wandert ab V017 mit (K16@715 -> @714).
        # Wortlaut/Betrag nur dort neu berechnet; V01..V016 behalten das
        # historische Literal (Byte-Identitaet).
        ((f"Transition-Park {box_end}-847 (MAKRO, gegenueber Adapter "
          "unberuehrt): "
          + ", ".join(f"K{t.kid}@{t.bar}" for t in sorted(
              (x for x in h2_1 if x.bar <= 847), key=lambda x: x.bar))
          + " = " + f"{len([x for x in h2_1 if x.bar <= 847])} / "
          + f"{sum(x.r for x in h2_1 if x.bar <= 847):+.4f} R") if _NEU else
         "Transition-Park 640-847 (MAKRO, unberuehrt): K1@639, K3@650, "
         "K45@679, K16@715, K51@760 = 5 / +2.4809 R"),
    ] + _zeilen_extra())
    legend(ax1, _leg_basis_sweep() + [
        Line2D([0], [0], color="gray", ls=":", lw=1.0,
               label="Tombstone-Band (R21)"),
    ] + LEG_MODUS)
    fig.subplots_adjust(left=0.04, right=0.995, top=0.955, bottom=0.07)
    out = OUTDIR / f"{PRAEFIX}03_h2_phasen.png"
    fig.savefig(out, dpi=300)
    plt.close(fig)
    return out


# =========================================================== 04 P9 REGIME
def png_04_p9_regime():
    X0, X1 = 820, 1045
    fig, (ax1, axs) = plt.subplots(
        2, 1, figsize=(21, 12),
        gridspec_kw={"height_ratios": [4.2, 1.25], "hspace": 0.10})
    y0, y1 = float(lo[X0:X1].min()), float(hi[X0:X1].max())
    ax1.axvspan(P9.start_bar, P9.end_bar, color=C_REGIME, alpha=0.13,
                zorder=0)
    for gs, ge in ((1021, 1029),):
        ax1.axvspan(max(gs, X0), min(ge, X1), facecolor=C_GAP, alpha=0.09,
                    hatch="//", edgecolor=C_GAP, lw=0.0, zorder=0)
    # Auflage A-4 (nur V016): aus dem Legendenbereich nach oben rechts.
    # 'Luecke BLOCKIERT' bleibt bewusst auf dem Bestandsplatz (E10).
    ax1.text(0.82 if _AUFL else P9.start_bar + 4, 0.94 if _AUFL else y1,
             "P9 AKTIV 848-1020", fontsize=10.5, va="top",
             ha="center" if _AUFL else "left", color="#1b6b3a",
             weight="bold", zorder=11,
             transform=ax1.transAxes if _AUFL else ax1.transData)
    ax1.text(1032, y1, "Luecke BLOCKIERT", fontsize=9, va="top",
             color=C_GAP, zorder=11)
    draw_candles(ax1, X0, X1, "candle")
    kids_prio = {67, 73, 76, 77, 82}
    for e in sorted(scan["edges"], key=lambda x: (x.seite, x.basis)):
        if max(b for b, _ in e.wicks) < X0 or min(b for b, _ in e.wicks) > X1:
            continue
        col = C_OBEN if e.seite == "OBEN" else C_UNTEN
        ls = "-" if e.seite == "OBEN" else "--"
        prio = e.kid in kids_prio
        bf = min(b for b, _ in e.wicks)
        bl = max(b for b, _ in e.wicks)
        x0, x1 = max(X0, bf - 25), min(X1, bl + 25)
        if x1 <= x0:
            continue
        _xs = np.arange(x0, x1 + 1)
        ax1.plot(_xs, kanten_y(e, _xs),
                 color=col, lw=2.2 if prio else 1.0, ls=ls,
                 alpha=0.90 if prio else 0.40, zorder=4)
        ax1.plot([b for b, _ in e.wicks], [p for _, p in e.wicks], ".",
                 ms=3.5, color=col, alpha=0.8, zorder=5)
        zeichne_kanten_label(ax1, e, _xs, fs=8.5 if prio else 6.8,
                             prio=prio, zorder=8,
                             stufen_texte=(prio or e.kid in NORM_KIDS))
    # Phasengrenzen
    ax1.axhline(P9.decke.provenienz_basis, color=C_OBEN, lw=1.0, ls="-.",
                alpha=0.55, zorder=5)
    ax1.text(X0 + 2, P9.decke.provenienz_basis,
             f"U_final {P9.decke.provenienz_basis:.4f}", fontsize=7.5,
             color=C_OBEN, va="bottom", zorder=8)
    ax1.axhline(P9.boden.provenienz_basis, color=C_UNTEN, lw=1.0, ls="-.",
                alpha=0.55, zorder=5)
    ax1.text(X0 + 2, P9.boden.provenienz_basis,
             f"L_final {P9.boden.provenienz_basis:.4f} (Ziel)", fontsize=7.5,
             color=C_UNTEN, va="top", zorder=8)
    if KONF.k67_override_aktiv:
        ax1.axhline(KONF.niveau_override_wert, color=C_CHG, lw=1.5, ls="--",
                    alpha=0.9, zorder=6)
        ax1.text(X0 + 2, KONF.niveau_override_wert,
                 f"Niveau-Override {KONF.niveau_override_wert:.4f} "
                 f"(P9, anwender-gesetzt) -- Abschnitt 66.2", fontsize=7.5,
                 color=C_CHG, va="bottom", zorder=8)
    for (b, _se, px, _ref, _dd) in scan["sweep_sperren"]:
        if X0 <= b <= X1:
            ax1.plot(b, px, SWEEP_MARKER, ms=SWEEP_MARKER_MS_GROSS,
                     color="red", zorder=6, mec="black", mew=0.3)
    mark_gates(ax1, X0, X1)
    if KONF.alt_trades_einblenden:
        mark_trades(ax1, [t for t in REFERENZ if X0 <= t.bar <= X1], fs=9.0,
                    stil="referenz")
    mark_trades(ax1, [t for t in h2_1 if X0 <= t.bar <= X1], fs=9.5)
    mark_override_grenzen(ax1, X0, X1, y1)
    if KONF.k67_override_aktiv:
        for _b in sorted(x.bar for x in V1 if x.bar in KONF.quartett_bars):
            _tr = [x for x in V1 if x.bar == _b]
            if not _tr:
                continue
            _t = _tr[0]
            ax1.annotate(f"Override {KONF.niveau_override_wert:.4f} | "
                         f"K{_t.kid} {_t.stufe}\ndist > 0 -> Hook 1 inaktiv",
                         (_b, hi[_b]), textcoords="offset points",
                         xytext=(0, 46), ha="center", fontsize=8.0,
                         color=C_CHG, zorder=12,
                         arrowprops=dict(arrowstyle="->", color=C_CHG,
                                         lw=1.1),
                         bbox=dict(boxstyle="round,pad=0.25", fc="#fdf6e3",
                                   ec=C_CHG, lw=0.6, alpha=0.95))
    else:
        # Hook-Annotation an den zwei Benchmark-Bars
        for bar in (980, 1020):
            tr = [t for t in h2_1 if t.kid == 73 and t.bar == bar]
            if not tr:
                continue
            t = tr[0]
            ax1.annotate("Hook 1: K67 freigegeben\n(M-Band, dist<0) | "
                         "Hook 2: PHASE",
                         (bar, hi[bar]), textcoords="offset points",
                         xytext=(0, 46), ha="center", fontsize=8.5,
                         color="#1b6b3a", zorder=12,
                         arrowprops=dict(arrowstyle="->", color="#1b6b3a",
                                         lw=1.1),
                         bbox=dict(boxstyle="round,pad=0.25", fc="#eaf7ef",
                                   ec="#1b6b3a", lw=0.6, alpha=0.95))
    time_axis(ax1, X0, X1, TICKS_P04 if _AUFL else 12)
    if KONF.g4_aktiv:
        _v04 = (f"Engine {_VTAG} (Kanten-Extremum + M6-Heilung): P9 mit "
                f"K67-Override + Boden" if _NEU else
                ("Adapter v0.16 (G4 + A-1..A-4): P9 mit K67-Override "
                 "+ Boden" if _AUFL else
                 "Adapter v0.15 G4: P9 mit K67-Override + G4-Boden"))
        ax1.set_title(
            f"AUG SICHTTEST 04/05 -- P9-REGIME (Bars {X0}..{X1}) | "
            f"{_v04} | "
            f"Niveau-Override {KONF.niveau_override_wert:.4f} / "
            f"Boden K77 deklariert "
            f"{P9_BODEN_RECLAIM.boden_deklariert_literal:.4f} | "
            f"Ziel {P9.ziel_preis_short:.4f}", fontsize=12.5)
    elif KONF.k67_override_aktiv:
        ax1.set_title(
            f"AUG SICHTTEST 04/05 -- P9-REGIME (Bars {X0}..{X1}) | "
            f"Decke K67 mit Niveau-Override {KONF.niveau_override_wert:.4f} / "
            f"Boden K77 | Direktauslösung K67 (Quartett) | "
            f"Ziel {P9.ziel_preis_short:.4f}", fontsize=12.5)
    else:
        ax1.set_title(
            f"AUG SICHTTEST 04/05 -- P9-REGIME (Bars {X0}..{X1}) | "
            f"Decke K67 / Boden K77 | Sweeps 980 + 1020 an K73 | "
            f"Ziel {P9.ziel_preis_short:.4f}", fontsize=12.5)
    if KONF.k67_override_aktiv:
        _quart = sorted((x for x in V1 if x.bar in KONF.quartett_bars),
                        key=lambda x: x.bar)
        # §72.2: K67 traegt ab V017 das kausale Extremum -- die beiden
        # Native-Werte der Hook-1-Annotation werden dort berechnet, nicht
        # zitiert. V01..V016 behalten das historische Literal.
        _k67 = _BY_KID[67]
        _z4_ov = (f"Override statt Hook 1 (Abschnitt 66.2): basis_bei(980) = "
                  f"{_k67.basis_bei(980):.4f} bzw. {_k67.basis_bei(1020):.4f} "
                  f"wird P9-lokal durch {KONF.niveau_override_wert:.4f} "
                  f"ersetzt -> dist > 0, K67 handelt DIREKT (STUFE_1_IN_BAR); "
                  f"Hook 1 wird gegenstandslos" if _NEU else
                  "Override statt Hook 1 (Abschnitt 66.2): basis_bei(980) = "
                  "69.9687 bzw. 69.9513 wird P9-lokal durch 69.8700 ersetzt "
                  "-> dist > 0, K67 handelt DIREKT (STUFE_1_IN_BAR); "
                  "Hook 1 wird gegenstandslos")
        _z4_aus = (f"Austritt: Bar 1021 zurueck auf basis_bei = "
                   f"{_k67.basis_bei(1021):.4f}, ab Bar 1022 "
                   f"{_k67.basis_bei(1022):.4f} "
                   f"({_k67.touch_conf(1022)} bestaetigte Wicks) | "
                   f"Grenzlinien 848 / 1021 (Regel 15)" if _NEU else
                   "Austritt: Bar 1021 zurueck auf basis_bei = 69.9513, ab "
                   "Bar 1022 69.9458 (alle 5 Wicks) | Grenzlinien 848 / 1021 "
                   "(Regel 15)")
        _z4_sum = (f"SUMME Quartett-Beitrag: {P9_BEITRAG:+.6f} R | "
                   f"v0.1-Referenz: nur noch K73@980 +2.4119 = +2.4119 R -- "
                   f"K73@1020 +3.0093 R entfaellt bereits im v0.1-Lauf "
                   f"(§72.6) | K59@853 entfaellt" if _NEU else
                   f"SUMME Quartett-Beitrag: {P9_BEITRAG:+.6f} R | "
                   f"v0.1-Referenz K73@980 +2.4119 + K73@1020 +3.0093 "
                   f"= +5.4212 R (entfaellt) | K59@853 entfaellt")
        _z4 = [
            f"P9 (848-1020): Decke K67 provenienz "
            f"{P9.decke.provenienz_basis:.4f} mit Niveau-Override "
            f"{KONF.niveau_override_wert:.4f} | Boden K77 provenienz "
            f"{P9.boden.provenienz_basis:.4f} | ziel_preis_short "
            f"{P9.ziel_preis_short:.4f} | touch_band {P9.touch_band_pct:.2f} %",
            _z4_ov,
            _z4_aus,
            "Quartett: " + " | ".join(
                f"K{t.kid}@{t.bar} {t.stufe} entry {t.entry:.4f} "
                f"sl {t.sl:.4f}" for t in _quart),
            "Quartett R: " + " | ".join(
                f"K{t.kid}@{t.bar} {t.r:+.4f}" for t in _quart),
            _z4_sum,
        ]
    else:
        _z4 = [
            f"P9 (848-1020): Decke K67 provenienz "
            f"{P9.decke.provenienz_basis:.4f} | "
            f"Boden K77 provenienz {P9.boden.provenienz_basis:.4f} | "
            f"ziel_preis_short {P9.ziel_preis_short:.4f} | touch_band "
            f"{P9.touch_band_pct:.2f} %",
            "Hook 1 (ZWEI Konsumstellen, eine Auswertung): Pool-Filter in "
            "_kandidat + continue in _blockiert_durch_aussenkante | "
            "greift nur bei dist < 0 (Q1-Schutz)",
            f"K67 bei Bar 980: basis_bei(980) = 69.9687 vs. Sweep 69.8990 "
            f"(dist -0.0996 %, im 0.12-%-Band) -> Freigabe | "
            f"Bar 1020: 69.9513 vs. 69.9240 (-0.0390 %) -> Freigabe",
            f"K73@980 : STUFE_2_KERZE_2 entry 69.4910 sl 69.9490 tp2 68.3700 "
            f"R +2.4119 | K73@1020: STUFE_1_IN_BAR entry 69.5780 sl 69.9740 "
            f"tp2 68.3700 R +3.0093",
            f"SUMME Regime-Beitrag: +5.4212 R (Zielband Mentor "
            f"[+5.28 .. +5.42 R]) | K59@853 entfaellt",
        ]
    stats_panel(axs, _z4 + _zeilen_extra())
    legend(ax1, [
        Line2D([0], [0], color=C_OBEN, lw=1.7, label="OBEN-Kante (SE)"),
        Line2D([0], [0], color=C_UNTEN, ls="--", lw=1.7,
               label="UNTEN-Kante (SE)"),
        Line2D([0], [0], color=C_OBEN, ls="-.", lw=1.0,
               label="U_final (Phasengrenze)"),
        Line2D([0], [0], color=C_UNTEN, ls="-.", lw=1.0,
               label="L_final / Ziel"),
        Line2D([0], [0], marker="o", color="w", mfc=C_SHORT, ms=8,
               label="SHORT-Trade (H2, gefuellt)"),
        Line2D([0], [0], marker=SWEEP_MARKER, color="w", mfc="red",
               ms=SWEEP_MARKER_MS, label="Sweep-Sperre"),
        Line2D([0], [0], marker="x", color="w", mfc=C_GATE, ms=7,
               label="Sperre Q29 (Quartil)"),
        Line2D([0], [0], marker="^", color="w", mfc=C_GATE, ms=7,
               label="Sperre M6 (Aussenwand)"),
    ] + LEG_MODUS)
    fig.subplots_adjust(left=0.045, right=0.995, top=0.955, bottom=0.07)
    out = OUTDIR / f"{PRAEFIX}04_p9_regime.png"
    fig.savefig(out, dpi=300)
    plt.close(fig)
    return out


# =========================================================== 05 KANTENKARTE
def png_05_kantenkarte():
    fig, (ax1, axs) = plt.subplots(
        2, 1, figsize=(22, 13),
        gridspec_kw={"height_ratios": [4.2, 1.25], "hspace": 0.09})
    y0, y1 = float(lo.min()), float(hi.max())
    shade_phases(ax1, y0, y1, 0, n - 1)
    ax1.axvspan(0, box_end, color="gray", alpha=0.10, zorder=0)
    ax1.axvline(box_end, color="black", lw=1.6, ls=":", alpha=0.9, zorder=4)
    ax1.text(6, y1, "H1 BOX", fontsize=11, va="top", color="#444444",
             zorder=11)
    ax1.text(n - 8, y1, "H2 EXPANSION", fontsize=11, va="top", ha="right",
             color="#1f77b4", zorder=11)
    draw_candles(ax1, 0, n - 1, "candle")
    for tk, _s, tp in tombs:
        ax1.plot([tk, n - 1], [tp, tp], color="gray", lw=0.9, ls=":",
                 alpha=0.40, zorder=1)
    for e in sorted(scan["edges"], key=lambda x: (x.seite, x.basis)):
        col = C_OBEN if e.seite == "OBEN" else C_UNTEN
        ls = "-" if e.seite == "OBEN" else "--"
        bf = min(b for b, _ in e.wicks)
        bl = max(b for b, _ in e.wicks)
        x0, x1 = max(0, bf - 20), min(n - 1, bl + 20)
        if x1 <= x0:
            continue
        _xs = np.arange(x0, x1 + 1)
        ax1.plot(_xs, kanten_y(e, _xs),
                 color=col, lw=1.1, ls=ls, alpha=0.55, zorder=4)
        ax1.plot([b for b, _ in e.wicks], [p for _, p in e.wicks], ".",
                 ms=3.0, color=col, alpha=0.8, zorder=5)
        zeichne_kanten_label(ax1, e, _xs, fs=6.2,
                             stufen_texte=(e.kid in NORM_KIDS))
    for e in scan["seeds"]:
        col = C_OBEN if e.seite == "OBEN" else C_UNTEN
        ax1.plot([b for b, _ in e.wicks], [p for _, p in e.wicks], "x",
                 ms=5, color=col, alpha=0.6, zorder=5)
        _bs = np.arange(max(0, e.wicks[0][0] - 20), n)
        zeichne_kanten_label(ax1, e, _bs, fs=5.8, prefix="s")
    for e in geb_h2:
        ax1.plot(e.geburts_bar, e.basis, "^", ms=5.5, color="#ff7f0e",
                 zorder=7, mec="black", mew=0.3)
    for (b, _se, px, _ref, _dd) in scan["sweep_sperren"]:
        ax1.plot(b, px, SWEEP_MARKER, ms=SWEEP_MARKER_MS, color="red",
                 zorder=6, mec="black", mew=0.3)
    mark_gates(ax1, 0, n - 1)
    if KONF.alt_trades_einblenden:
        mark_trades(ax1, REFERENZ, fs=7.0, stil="referenz")
    mark_trades(ax1, V1, fs=7.0)
    mark_override_grenzen(ax1, 0, n - 1, y1)
    time_axis(ax1, 0, n - 1)
    ax1.set_title(
        f"AUG SICHTTEST 05/05 -- KANTEN-LANDKARTE (Bars 0..{n - 1}) | "
        f"{len(scan['edges'])} Kanten + {len(scan['seeds'])} Seeds | "
        f"geloeschte R21-Kanten unsichtbar (nur Tombstone-Baender)",
        fontsize=12.5)
    stats_panel(axs, [
        f"Kanten: {len(scan['edges'])} edges + {len(scan['seeds'])} seeds "
        f"= {len(scan['edges']) + len(scan['seeds'])} lebend | "
        f"R21: {len(r21_gel)} geloescht / {len(r21_ges)} Geburten gesperrt | "
        f"{len(tombs)} Tombstones (gepunktet, keine Linie)",
        f"OBEN {sum(1 for e in scan['edges'] if e.seite == 'OBEN')} / "
        f"UNTEN {sum(1 for e in scan['edges'] if e.seite == 'UNTEN')} | "
        f"Sweep-Sperren {len(scan['sweep_sperren'])} | "
        f"H2-Neugeburten {len(geb_h2)} (Dreiecke) | "
        f"Promovierte Primaer-Anker {st1.get('promotionen')}",
        f"H1 BOX: {len(h1_1)} Trades / {sum(t.r for t in h1_1):+.6f} R  |  "
        f"H2 EXP: {len(h2_1)} Trades / {sum(t.r for t in h2_1):+.4f} R  |  "
        f"GESAMT: {len(V1)} / {R1:+.4f} R",
        "Lesart: K67 (OBEN, Provenienz 69.9140 / kausal 69.9458 @1259) und "
        "K73 (OBEN, Provenienz 69.5550 / kausal 69.6714 @1259) tragen das "
        "P9-Regime; K77 (UNTEN) ist der Boden. R21-geloeschte Kanten sind "
        "bewusst unsichtbar. Linien sind KAUSAL (basis_bei(k)) gezeichnet; "
        "Wechsler tragen v0 -> v1 *.",
    ] + _zeilen_extra())
    legend(ax1, _leg_basis_sweep() + [
        Line2D([0], [0], color="gray", ls=":", lw=1.0,
               label="Tombstone-Band (R21)"),
        Line2D([0], [0], marker="x", color="w", mfc="gray", ms=6,
               label="Seed (< 2 Touches)"),
    ] + LEG_MODUS)
    fig.subplots_adjust(left=0.04, right=0.995, top=0.955, bottom=0.065)
    out = OUTDIR / f"{PRAEFIX}05_kantenkarte.png"
    fig.savefig(out, dpi=300)
    plt.close(fig)
    return out


# ---------------------------------------------------------------- Lauf
class _Protokoll:
    """Tee: schreibt gleichzeitig auf stdout und in den Protokollpuffer."""

    def __init__(self) -> None:
        self.zeilen: list = []

    def __call__(self, msg: str = "") -> None:
        print(msg)
        self.zeilen.append(msg)

    def schreibe(self, ziel: Path) -> None:
        """Persistiert das Protokoll als UTF-8 ohne BOM (LF)."""
        ziel.write_text("\n".join(self.zeilen) + "\n", encoding="utf-8",
                        newline="\n")


log = _Protokoll()
log("=" * 110)
log(f"AUG-SICHTTEST -- PNG-SATZ (Modus {KONF.mode}, "
    f"Adapter {_VER_TEXT})")
log("=" * 110)
# §72.4: urkundliche Kennung der geladenen Engine (auch im Probe-Lauf).
# Beschluss P-2: die Kennungs-Zeilen erscheinen NUR in der Engine-Generation
# (V017/V018) -- V01..V016 behalten ihr arretiertes Protokoll
# (tmp_png_aug_sichttest_v016_out.txt, 5.520 B / 2969723c...).
if _NEU:
    log(f"  ENGINE         : {ENGINE_NAME}  SHA256 {ENGINE_SHA}")
    log(f"  Sichtbare Niveauwechsel (maskiert, §72.8): {NIVEAUWECHSEL} "
        f"(Baseline {KONF.niveauwechsel_baseline})")
log(f"  n={n} | box_end={box_end} | Kanten {len(scan['edges'])} edges + "
    f"{len(scan['seeds'])} seeds")
log(f"  Baseline V0    : {len(V0):2d} Trades / {R0:+.6f} R  "
    f"(H1 {len(h1_0)}/{sum(t.r for t in h1_0):+.6f} | "
    f"H2 {len(h2_0)}/{sum(t.r for t in h2_0):+.6f})")
log(f"  V1_basis (v0.1): {len(V1_basis):2d} Trades / {RB:+.6f} R")
log(f"  V1_aktiv ({KONF.mode}) : {len(V1):2d} Trades / {R1:+.6f} R  "
    f"(H1 {len(h1_1)}/{sum(t.r for t in h1_1):+.6f} | "
    f"H2 {len(h2_1)}/{sum(t.r for t in h2_1):+.6f})")
if KONF.k67_override_aktiv:
    log(f"  Quartett       : " + " | ".join(
        f"K{t.kid}@{t.bar} {t.r:+.4f}" for t in sorted(
            (x for x in V1 if x.bar in KONF.quartett_bars),
            key=lambda x: x.bar)) + f" | QUARTETT {QUARTETT_R:+.6f} R")
    for _z in G4_ZEILEN:
        log("  " + _z)
    log(f"  Delta {KONF.mode}-v0.1: {R1 - RB:+.6f} R  (Soll "
        f"{_dsoll:+.6f})")
    log(f"  Referenz-Marker (entfallene V01-Trades): " + (", ".join(
        f"K{t.kid}@{t.bar} {t.r:+.4f}" for t in sorted(
            REFERENZ, key=lambda x: x.bar)) or "keine"))
    log(f"  Neu im {KONF.mode}-Lauf: " + (", ".join(
        f"K{t.kid}@{t.bar} {t.r:+.4f}" for t in sorted(
            NEU, key=lambda x: x.bar)) or "keine"))
else:
    log(f"  Regime         : K73@980 +2.4119 | K73@1020 +3.0093 | "
        f"Summe {sum(t.r for t in V1 if t.kid == 73):+.4f} R")
log(f"  Override-Info  : {OVERRIDE_INFO or 'keine (Modus ohne Override)'}")
log(f"  Sperr-Marker: Q29 x {len(GATE_Q29)} | M6 ^ {len(GATE_M6)}")
log(f"    Q29-Bars (H2) = "
    f"{[b for b, _p, _k, _r in GATE_Q29 if b >= box_end]}")
log(f"    M6-Bars  (H2) = "
    f"{[b for b, _p, _k, _r in GATE_M6 if b >= box_end]}")
log(f"  {_NW_LOG}")
for _kid in sorted(WECHSEL):
    _v0, _v1, _ns = WECHSEL[_kid]
    log(f"    K{_kid:<4} {_v0:.4f} -> {_v1:.4f}  "
        f"(delta {_v1 - _v0:+.4f}, {_ns} Stufen)")
log(f"  Norm-Vergleich (Option b, Referenz-Bar {NORM_REF_BAR}, "
    f"Quelle Gesamtbestand P9 + P12_RESERVE):")
for _kid in sorted(NORM):
    _c = _basis_von(_kid)
    _n = NORM[_kid]
    log(f"    K{_kid:<4} kausal {_c:.4f} vs Norm {_n:.4f}  "
        f"delta {_c - _n:+.4f}  "
        f"{'ABWEICHUNG (Label traegt Norm)' if abs(_c - _n) > 1e-9 else 'konform'}")
if KONF.k67_override_aktiv:
    _pl = kanten_label(_BY_KID[67], np.arange(0, n), "K")
    log(f"  Plateau-Label K67 (gerendert): {_pl[0]}")

for fn in (png_01_gesamt, png_02_h1_box, png_03_h2_phasen, png_04_p9_regime,
           png_05_kantenkarte):
    p = fn()
    geschrieben.append(p)
    log(f"  PNG -> {p.name}  ({p.stat().st_size:,} B)")

log("\nSatz vollstaendig: " + ", ".join(p.name for p in geschrieben))
_PFAD = ROOT / PROTOKOLL_DATEI
_PFAD.parent.mkdir(parents=True, exist_ok=True)
log.schreibe(_PFAD)
print(f"\nProtokoll -> {_PFAD.relative_to(ROOT)}  "
      f"({_PFAD.stat().st_size:,} B)")
