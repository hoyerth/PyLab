"""
SETUP C - PHASE-1-PRODUKTIONSKERN (scripts/setup_c_profil.py)
================================================================
Implementiert den arretierten Phase-1-Kern aus §2.13/§2.14 des Lastenhefts
``docs/setup_c_experiment.md`` auf der Modul-Basis
``scripts/market_segmentation.py`` (KEIN ``exec()``-Slice, KEINE
Produktions-Baseline-Veränderung):

    RAW (jeder kausale Volumen-Durchstoss an der Kante)
    + F4-Stop intrabar (Puffer 0,15 USD) + terminaler Zeit-Exit 48/96
    + phasenlokale Open-Position-Suppression (Pflicht-Schutzschicht,
    §2.13-C/§2.13-1.4).

0,45 %-SL bleibt ausschliesslich r_ref-Messung, nie Produktions-Stop.

LIVE-KAUSALITAET (Hausregel, bindend - "erlaubt ist nur was live passiert")
---------------------------------------------------------------------------
Der Handelspfad enthaelt KEINEN Lookahead. Verbindlich:

  1) Der RAW-Trigger wird am Bar-Close entschieden: erster Bar mit
     ``high >= kante(b)`` (bzw. ``low <= kante``) UND F5-Volumen, Kante
     strikt kausal aus ``U_hist``/``L_hist``. Einstieg am Open der Folge-Bar.
  2) Die Scan-Obergrenze ist die LIVE bekannte Phasengrenze: bei
     bestehendem 2-Close-Bruch ``brk_idx`` (der Bruch ist bei
     ``close[brk_idx+1]`` bekannt, alle Scan-Bars liegen davor), sonst das
     Datenende. Eine noch offene Phase wird NICHT zensiert.
  3) ENTfernt (vormals Lookahead): der Auswahlfilter
     ``vorlauf_bars <= cluster_a_max_vorlauf`` ("RAW-Cluster A"). Er setzte
     ``brk_idx`` voraus und wurde in der Einstiegs-Bar entschieden, BEVOR
     ``close[j]``/``close[j+1]`` bekannt waren. Messung (Attribution ueber
     MAI26..AUG26, 2026): 10 von 23 Cluster-A-Trades mit ``vorlauf == 1``
     trugen ~100 % der Cluster-A-Summe; die uebrigen 13 mit ``vorlauf == 0``
     ergaben +0,14R (N48) bzw. -1,38R (N96). ``vorlauf_bars`` bleibt daher
     ausschliesslich DIAGNOSEFELD und ist an keiner Auswahl beteiligt.
  4) ``cluster_a_max_vorlauf`` existiert nur noch fuer die historische
     §2.16-Gate-Reproduktion (``nur_cluster_a=True``); der Gate-Report ist
     ein eingefrorener OOS-Vergleich und KEIN Handelspfad.

Historische Verifikation (§2.14/§2.15, Stand vor der Kausalitaets-Bereinigung)
------------------------------------------------------------------------------
L1  Pipeline-Anker (Populationen): CONFIRMED / RAW gesamt (A/B) / RETEST je
    Fenster AUG/S1/S2. F3/CONFIRMED/RETEST sind bitgenau invariant; der
    RAW-Split folgt der Ratchet-Korrektur (AUG 10 (2/8), S1 105 (38/67),
    S2 76 (3/73)). Die A/B-Zerlegung ist seit der Kausalitaets-Bereinigung
    nur noch diagnostisch und NICHT mehr handelbar.
L2  (vormals "RAW-Cluster A") unter Zeit-Exit N=48/N=96: Summen r_f4/r_ref,
    Exit-Verteilung, Haltedauer, Rechts-Zensierung (E2). Anlass der
    urspruenglichen Arretierung: µs/ns-Einheiten-Bug in ``_kanten_reihe``
    (statische Kante statt D4-Ratchet-Stufenfunktion), Fix dort dokumentiert.
    Die damaligen Soll-Werte gelten fuer den Cluster-A-Pfad und sind mit dem
    live-kausalen Pfad NICHT mehr vergleichbar.

Der L2-Referenzlauf der Explorationsphase war suppression-frei (Reports
``tmp_setup_c_zeitexit_*.txt``, Schritt 4a). Die Produktion schaltet die
phasenlokale Suppression als Pflicht-Schutzschicht hinzu (Whipsaw-Beschluss
F3, §2.12). ``TrendConfig.suppression_phasenlokal`` steuert beide Modi:
``False`` reproduziert die §2.14-Soll-Werte (Gate-Lauf), ``True`` ist der
Produktions-Default und weist das Delta als n_supprimiert aus (zusaetzlich
druckt der Report die suppression-freie L2-Referenzzeile).

F3-Suppression (arretierte Semantik, §2.13-C: "aktiver Trade in DERSELBEN
Richtung derselben Phase"): Der Suppression-Key ist (phase, dir). Da
``_erfasse_raw`` je (Phase, Richtung) maximal EIN Signal liefert, ist die
Suppression fuer die RAW-A-Population ein striktes No-op (n_supprimiert=0);
die Produktion reproduziert damit die arretierte L2-Referenz bitgenau.
Kein Cross-Richtungs-Eingriff (up/down derselben Phase sind unabhaengige,
gleichzeitig handelbare Setups).

Kausalitaet (unveraendert aus der Baseline/den Referenz-Reports):
- F4-Stop intrabar mit VORRANG vor dem Zeit-Exit an derselben Bar.
- Zeit-Exit ausschliesslich am Close der Exit-Bar entry+N.
- Rechts-Zensierung (E2): ueberlebt ein Trade das Datenende ohne Stop und
  ohne erreichten Horizont -> RECHTS_ZENSIERT, r = NaN, strikt isoliert.
- RAW-Kantenreferenz strikt kausal aus U_hist/L_hist (D4, kein Lookahead,
  KEINE_KANTE bei fehlender Kante, kein Kreuz-Fallback).
- F5-Volumen strikt kausal: tick_volume >= 1.5 * SMA20(tick_volume).shift(1).

Ausgabe (Phase 1 = Text-Export only, §2.14-B3): Console + ``.txt``-Report +
maschinenlesbarer Trade-Block (``.tsv``) unter ``reports/setup_c/``.
Aufruf (Projekt-Root, Namespace-Package ohne __init__.py):
    python -m scripts.setup_c_profil --fenster=AUG|S1|S2|ALLE [--ohne-suppression]
    python -m scripts.setup_c_profil --fenster=ALLE --mit-regime-gate

Beliebiger Zeitraum als Parameter (Betrieb, ohne Zusatzfreigabe):
    python -m scripts.setup_c_profil --start=2026-09-01 --ende=2026-09-11
    python -m scripts.setup_c_profil --start=2026-01-01 --ende=2026-09-11 ^
        --bezeichnung=Y2026 --mit-regime-gate
``--start`` (inklusive) und ``--ende`` (exklusiv) sind ISO-Daten (die
``load_data``-Konvention, deckungsgleich der BKZ-Zeitbasis: der Filter laeuft
ueber ``time AT TIME ZONE 'UTC'``). Beide sind zwingend gemeinsam zu setzen;
fehlt ``--bezeichnung``, wird das Label automatisch als
``<start_ohne_bindestriche>_<ende_ohne_bindestriche>`` gebildet und dient als
Report-Namensraum (``reports/setup_c/setup_c_<label>.txt``). Alle uebrigen
Schalter (--ohne-suppression, --mit-regime-gate, --ema-trailing, ...) gelten
unveraendert auch fuer freie Zeitraeume.

Anderes Instrument / Timeframe (Silber-Artefakte bleiben unberuehrt):
    python -m scripts.setup_c_profil --symbol=Brent --timeframe=M15 ^
        --start=2026-05-01 --ende=2026-06-01 --bezeichnung=MAI26_BRENT
``--symbol`` (Default ``SILVER``) waehlt das DB-Instrument; jedes andere
Symbol erhaelt einen Grossbuchstaben-Suffix am Fenster-/Report-Label
(``Brent`` -> ``_BRENT``), damit Silber- und Brent-Artefakte getrennt
bleiben. ``--timeframe`` (Default ``M15``) waehlt die Kerzen-Zeitbasis.

Gate-Modus (optional, Luecke-1-Integration; §2.16-A.4): ``--mit-regime-gate``
aktiviert das Gated-Portfolio exakt wie im OOS abgenommen (§2.16-F.1:
TREND -> RAW-A@96 + RAW-B@96 nur Bruchrichtung; SHAKEOUT/UNKLAR -> strikt
RAW-A@48 = No-Harm-Baseline). Ohne das Flag bleibt der Kern bitgenau der
Phase-1-Pfad (No-Harm-Invarianz, L2-Referenz §2.15/§2.14). Schwellen: die
versiegelten Klassen-Defaults von ``scripts.regime_filter.RegimeSchwellen``
(Freeze 05.09.2026, §2.16-C) - bewusst KEIN Zugriff auf gitignored
test-Artefakte.
"""
from __future__ import annotations

import datetime
import re
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Dict,
    List,
    Literal,
    Optional,
    Protocol,
    Sequence,
    Tuple,
)

import numpy as np
import pandas as pd

from scripts.market_segmentation import (
    PhaseData,
    SegmentConfig,
    SegmentResult,
    load_data,
    segmentiere_markt,
)

if TYPE_CHECKING:  # Nur fuer Typ-Checker; Laufzeit-Import bleibt im Gate-Pfad
    from scripts.regime_filter import RegimeState

__all__ = [
    "TrendConfig",
    "EMASlopeTrailingConfig",
    "SetupCSignal",
    "KernelTrade",
    "AggBlock",
    "berechne_ema_slope_vektoren",
    "bericht_fenster",
    "fenster_spanne",
    "loese_zeitraeume",
    "symbol_suffix",
    "haenge_symbol_suffix",
    "ist_iso_datum",
    "normiere_bezeichnung",
    "bezeichnung_aus_zeitraum",
    "main",
]

# =============================================================================
# 1a) GATE-PROVIDER (entkoppelt, §2.16-A.4: regime_filter-Import NUR im Gate-Pfad)
# =============================================================================


class IRegimeProvider(Protocol):
    """Entkoppelte Regime-Klassifikation (Luecke-1, §2.16-A.4).

    Ermoeglicht Injektion von Fakes/Alternativen im Test ohne harte
    Kopplung an ``scripts.regime_filter``. Eine Implementierung muss je
    echter 2-Close-Bruch-Phase (``phase_nr`` 1..n) genau EINEN
    klassifizierten ``RegimeState`` liefern (Join-Schluessel zu
    ``KernelTrade.phase``, deckungsgleich §2.16-C).
    """

    def klassifiziere(
        self, df: pd.DataFrame, sr: SegmentResult
    ) -> "List[RegimeState]":
        """Klassifizierte RegimeState je Phase (kausal bis brk_idx)."""
        ...


class RegimeFilterProvider:
    """Duenne Adaption der regime_filter-Free-Functions (versiegelte Defaults).

    Nutzt ausschliesslich die Klassen-Defaults von ``RegimeSchwellen``
    (= Freeze-Zentren nach Hunk-0-Bereinigung, §2.16-C) - bewusst KEIN
    Zugriff auf ``test/regime_schwellen_freezed.json`` (gitignored,
    unversioniert, nicht reproduzierbar aus dem Repo).
    """

    def klassifiziere(
        self, df: pd.DataFrame, sr: SegmentResult
    ) -> "List[RegimeState]":
        import scripts.regime_filter as rf  # Modul-Isolation: nur Gate-Pfad

        cfg_metrik = rf.RegimeMetricConfig()
        df_ind: pd.DataFrame = rf.berechne_zeitreihen_indikatoren(df, cfg_metrik)
        states_roh: "List[RegimeState]" = rf.berechne_regime_metriken(
            df_ind, sr, cfg_metrik, rand_phasen="ZENSIERT_UEBERGEHEN"
        )
        return rf.klassifiziere_regime(
            states_roh, rf.RegimeSchwellen(), rf.RegimeGateConfig()
        )


# =============================================================================
# 1) FENSTER & KONFIGURATION (Datenvertrag)
# =============================================================================

# Referenzfenster (start, ende) - Ende exklusiv (load_data-Konvention)
FENSTER_DEFS: Dict[str, Tuple[str, str]] = {
    "AUG": ("2026-08-10", "2026-08-28"),
    "S1": ("2026-02-05", "2026-08-28"),
    "S2": ("2025-01-01", "2025-12-01"),
}

# ISO-Datum der freien Zeitraum-Parameter (--start / --ende)
_ISO_DATUM_MUSTER = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def ist_iso_datum(text: str) -> bool:
    """Prueft ein ISO-Datum (YYYY-MM-DD) syntaktisch und kalendarisch.

    Args:
        text: Zu pruefender String.

    Returns:
        True, wenn ``text`` ein gueltiges ISO-Datum ist.
    """
    if not _ISO_DATUM_MUSTER.match(text):
        return False
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def normiere_bezeichnung(text: str) -> str:
    """Bildet ein dateisystem- und report-sicheres Zeitraum-Label.

    Nur ``A-Z a-z 0-9 _ . -`` bleiben erhalten; alle anderen Zeichen werden
    zu ``_`` (Report-Namensraum ``reports/setup_c/setup_c_<label>.txt``).

    Args:
        text: Rohbezeichnung (z. B. ``--bezeichnung=Y2026``).

    Returns:
        Bereinigtes Label.

    Raises:
        SystemExit: Wenn nach der Bereinigung kein Zeichen uebrig bleibt.
    """
    sauber: str = re.sub(r"[^A-Za-z0-9_.-]+", "_", text.strip()).strip("_.-")
    if not sauber:
        raise SystemExit(f"Ungueltige Bezeichnung: {text!r}")
    return sauber


def bezeichnung_aus_zeitraum(start: str, ende: str) -> str:
    """Auto-Label eines freien Zeitraums (``YYYYMMDD_YYYYMMDD``).

    Args:
        start: ISO-Datum (inklusive).
        ende: ISO-Datum (exklusiv).

    Returns:
        Label ohne Bindestriche.
    """
    return f"{start.replace('-', '')}_{ende.replace('-', '')}"


def fenster_spanne(fenster: str, cfg: "TrendConfig") -> Tuple[str, str]:
    """Loest (start, ende) aus ``cfg.start``/``cfg.ende`` oder ``FENSTER_DEFS``.

    Freier Zeitraum hat Vorrang: sind ``cfg.start`` UND ``cfg.ende`` gesetzt,
    wird dieser Zeitraum verwendet (beliebig, nicht auf AUG/S1/S2 begrenzt).
    Andernfalls greift die Alias-Aufloesung ``FENSTER_DEFS[fenster]``.

    Args:
        fenster: Fenster-Label (Alias AUG|S1|S2 oder freie Bezeichnung).
        cfg: TrendConfig mit optionalem freiem Zeitraum (start/ende).

    Returns:
        Tupel ``(start, ende)`` fuer ``load_data`` (ende exklusiv).

    Raises:
        SystemExit: Wenn nur eines von start/ende gesetzt ist, ein Datum
            ungueltig ist, start >= ende gilt oder das Label kein bekanntes
            Referenzfenster und kein freier Zeitraum ist.
    """
    frei_start: Optional[str] = getattr(cfg, "start", None)
    frei_ende: Optional[str] = getattr(cfg, "ende", None)
    if (frei_start is None) != (frei_ende is None):
        raise SystemExit(
            "Freier Zeitraum: --start und --ende nur gemeinsam "
            f"(erhalten: start={frei_start!r}, ende={frei_ende!r})."
        )
    if frei_start is not None and frei_ende is not None:
        if not ist_iso_datum(frei_start):
            raise SystemExit(f"Ungueltiges --start (ISO YYYY-MM-DD): {frei_start!r}")
        if not ist_iso_datum(frei_ende):
            raise SystemExit(f"Ungueltiges --ende (ISO YYYY-MM-DD): {frei_ende!r}")
        if frei_start >= frei_ende:
            raise SystemExit(
                f"Leerer Zeitraum: start={frei_start} muss < ende={frei_ende} sein."
            )
        return frei_start, frei_ende
    if fenster not in FENSTER_DEFS:
        raise SystemExit(
            f"Unbekanntes Fenster: {fenster} "
            f"({', '.join(sorted(FENSTER_DEFS))}|ALLE) "
            "oder freien Zeitraum via --start/--ende angeben."
        )
    return FENSTER_DEFS[fenster]


def symbol_suffix(symbol: str) -> str:
    """Label-Suffix fuer ein vom Baseline-Symbol abweichendes Instrument.

    Verhindert, dass Laeufe anderer Instrumente die Silber-Artefakte unter
    ``reports/setup_c/`` ueberschreiben (Hausregel: ein Namensraum je
    Instrument).

    Args:
        symbol: Instrumentsname (z. B. ``Brent``).

    Returns:
        ``""`` fuer ``SILVER`` (Baseline), sonst ``"_<SYMBOL>``
        (z. B. ``_BRENT``).
    """
    sym: str = str(symbol).strip().upper()
    if sym in ("", "SILVER"):
        return ""
    return "_" + re.sub(r"[^A-Z0-9]+", "", sym)


def haenge_symbol_suffix(label: str, suffix: str) -> str:
    """Haengt den Instrumenten-Suffix an - ausser er ist schon vorhanden.

    Idempotenz-Schutz gegen doppelte Kennungen (z. B. ``--bezeichnung=
    MAI26_BRENT --symbol=Brent`` darf NICHT ``MAI26_BRENT_BRENT`` ergeben).
    Fuer ``suffix == ""`` (SILVER) ist die Funktion die Identitaet - der
    Baseline-Namensraum bleibt damit bitgenau unveraendert.

    Args:
        label: Bereits normalisiertes Report-Label.
        suffix: Instrumenten-Suffix aus ``symbol_suffix`` (ggf. ``""``).

    Returns:
        Label mit genau einem Suffix.
    """
    if suffix and label.upper().endswith(suffix.upper()):
        return label
    return label + suffix


def loese_zeitraeume(
    fenster: str,
    start: Optional[str],
    ende: Optional[str],
    bezeichnung: Optional[str] = None,
    symbol: str = "SILVER",
) -> List[str]:
    """Bestimmt die abzuarbeitenden Report-Labels aus den CLI-Parametern.

    Reine Funktion (kein DB-Zugriff, keine Seiteneffekte) - damit die
    Zeitraum-Aufloesung isoliert testbar bleibt. Vorrang-Regel: ein freier
    Zeitraum (``start`` UND ``ende``) ueberschreibt das Alias-Fenster.
    Fuer ein von ``SILVER`` abweichendes ``symbol`` wird das Label um
    ``symbol_suffix(symbol)`` ergaenzt (Instrumenten-Namensraum).

    Args:
        fenster: Alias (AUG|S1|S2|ALLE) bzw. frei gewaehltes Label.
        start: ISO-Datum (inklusive) oder ``None``.
        ende: ISO-Datum (exklusiv) oder ``None``.
        bezeichnung: Optionaler Report-Namensraum.
        symbol: Instrumentsname (Default ``SILVER`` = Baseline).

    Returns:
        Liste der Fenster-/Zeitraum-Labels (inkl. Symbol-Suffix).

    Raises:
        SystemExit: Bei nur einseitig gesetztem Zeitraum, ungueltigem Datum,
            leerem Zeitraum oder unbekanntem Alias.
    """
    suffix: str = symbol_suffix(symbol)
    if (start is None) != (ende is None):
        raise SystemExit(
            "--start und --ende nur gemeinsam angeben (freier Zeitraum)."
        )
    if start is not None and ende is not None:
        # Gemeinsame Validierungsquelle (ISO-Format + start < ende)
        fenster_spanne("FREI", TrendConfig(start=start, ende=ende))
        basis: str = (
            bezeichnung if bezeichnung else bezeichnung_aus_zeitraum(start, ende)
        )
        return [haenge_symbol_suffix(normiere_bezeichnung(basis), suffix)]
    if fenster == "ALLE":
        return [haenge_symbol_suffix(f, suffix) for f in ("AUG", "S1", "S2")]
    if fenster in FENSTER_DEFS:
        basis = normiere_bezeichnung(bezeichnung) if bezeichnung else fenster
        return [haenge_symbol_suffix(basis, suffix)]
    raise SystemExit(
        f"Unbekanntes Fenster: {fenster} "
        f"({', '.join(sorted(FENSTER_DEFS))}|ALLE) - "
        "oder freien Zeitraum via --start/--ende angeben."
    )

ArmName = Literal["RAW", "CONFIRMED", "RETEST"]
DirName = Literal["up", "down"]
RawCluster = Literal["CLUSTER_A_ENG", "CLUSTER_B_WEIT", "NICHT_RAW"]
ExitGrund = Literal[
    "INITIAL_SL_INTRABAR",    # F4-Stop intrabar (Vorrang vor Zeit-Exit)
    "ZEIT_EXIT_CLOSE",        # Horizont N erreicht, Close der Exit-Bar e+N
    "RECHTS_ZENSIERT",        # E2: bis Datenende ueberlebt, Horizont nicht abgelaufen
    "TRAILING_SL_INTRABAR",   # EMA-Slope-Trailing: nachgezogener Stop intrabar
    "CRASH_HORIZONT_CLOSE",   # Notfall-Zeitschranke (Crash-Sicherung), Close
]
SignalStatus = Literal[
    "SIGNAL",
    "VERWORFEN_STOP_VERLETZT",
    "TIMEOUT",
    "KEIN_CLOSE_SCHUTZ",
    "KEIN_VOLUMEN",
    "KEIN_DURCHSTOSS",
    "KEINE_KANTE",
    "DATEN_ENDE",
]


@dataclass(frozen=True, slots=True)
class EMASlopeTrailingConfig:
    """Konfiguration fuer dynamisches Trailing via EMA-Steigung (§5.2/§5.4).

    NUR Variante B (STOP_AUF_EXTREMUM) implementiert; Variante A
    (SOFORT_EXIT) ist Backlog-Task und wird bei Aktivierung mit
    ``NotImplementedError`` abgelehnt. Defaults = deaktiviert -> der Kern
    bleibt bitgenau der Phase-1-Pfad (No-Harm-Invarianz, L2 §2.15).

    Attributes:
        aktiviert: True = Trailing-Modus aktiv (A/B-Test).
        ema_periode: EMA-Periode des Steigungs-Triggers (Standard 20).
        modus: Ausfuehrungs-Modus (Primaer: STOP_AUF_EXTREMUM = Stop-
            Nachzug auf das Extremum der Abflachungs-Kerze statt Sofort-Exit).
        mindest_gewinn_r: Gewinnschwelle in R, ab der der Nachzug greift
            (0.0 = sofort ab der ersten Kerze aktiv).
        notfall_horizont_bars: Crash-Sicherung (Notbremse) gegen Endlos-
            Laeufe; ersetzt im Trailing-Modus den terminalen Zeit-Exit.
    """

    aktiviert: bool = False
    ema_periode: int = 20
    modus: Literal["STOP_AUF_EXTREMUM", "SOFORT_EXIT"] = "STOP_AUF_EXTREMUM"
    mindest_gewinn_r: float = 0.0
    notfall_horizont_bars: int = 300


@dataclass(frozen=True, slots=True)
class TrendConfig:
    """Phase-1-Konfiguration fuer Setup C (verbindlicher Datenvertrag).

    Defaults = arretierte Beschluesse (§2.13-C, F4-F8, E1-E3/E5-KEIN_TRAILING,
    Whipsaw-F3). Aenderungen nur als dokumentierte Sensitivitaeten.

    Attributes:
        fenster: Fenster-Label. Bekannte Referenz-Aliasse (AUG|S1|S2)
            bestimmen start/ende via ``FENSTER_DEFS``; bei freien Zeitraeumen
            dient es zugleich als Report-Namensraum.
        start: Freier Zeitraum-Start (ISO-Datum, inklusive). ``None`` =
            Aufloesung ueber ``FENSTER_DEFS[fenster]``.
        ende: Freies Zeitraum-Ende (ISO-Datum, exklusiv). ``None`` =
            Aufloesung ueber ``FENSTER_DEFS[fenster]``.
        symbol: Symbol (Default ``SILVER`` wie Baseline). Wird sowohl fuer den
            Datenzugriff als auch fuer die Report-Kennzeichnung genutzt; ein
            von ``SILVER`` abweichendes Symbol erhaelt automatisch ein
            Label-Suffix (kein Ueberschreiben der Silber-Artefakte).
        timeframe: Timeframe (Default ``M15`` wie Baseline).
        db_path: DuckDB-Datei (Default = zentrale Produktions-DB).
        suppression_phasenlokal: Phasenlokale Open-Position-Suppression
            (Produktion Pflicht; Key = (phase, dir), F3). ``False`` =
            L2-Referenzmodus fuer das §2.14-Gate.
        cluster_a_max_vorlauf: HISTORISCH (nicht handelbar). Vorlauf-Schwelle
            des eingefrorenen "RAW-Cluster A" (Vorlauf <= 1 Bar vor dem
            2-Close-Bruch). Wird im Handelspfad NICHT mehr angewandt (siehe
            LIVE-KAUSALITAET im Modul-Docstring); nur noch fuer die
            §2.16-Gate-Reproduktion (``_kern_lauefe(nur_cluster_a=True)``).
        zeit_horizonte: Terminale Zeit-Exit-Horizonte (Close e+N), E1;
            Phase-1-Betrieb 48/96.
        stop_puffer: F4-Puffer unter Struktur/Kante (USD), F4.
        raw_vol_mult: F5-Volumen-Multiplikator (1.5x SMA20).
        sma_vol_period: F5-SMA-Periode (20).
        retest_band: Retest-Kontaktband um die gebrochene Kante (USD), F6.
        retest_timeout_bars: Retest-Guetigkeit nach dem 2-Close-Bruch, F7.
        sl_pct_ref: 0,45 %-Referenz-SL (ausschliesslich r_ref-Messung).
        segment: Segmentierungs-Konfiguration (Defaults = Baseline exakt);
            start/ende/db_path werden je Fenster ueberschrieben.
        ema_trailing: EMA-Slope-Trailing (optionaler A/B-Modus, §5.2/§5.4);
            Default deaktiviert = bitgenau Phase-1-Pfad.
        report_dir: Ausgabeordner (Phase 1 = Text-Export only).
    """

    fenster: str = "AUG"
    # Freier Zeitraum (Betrieb): ISO-Daten, start inklusive / ende exklusiv.
    # Beide gesetzt = beliebiger Zeitraum als Parameter (Vorrang vor
    # FENSTER_DEFS); beide None = Alias-Aufloesung ueber FENSTER_DEFS.
    start: Optional[str] = None
    ende: Optional[str] = None
    symbol: str = "SILVER"
    timeframe: str = "M15"
    db_path: Path = (
        Path(__file__).resolve().parent.parent / "data" / "market_data.duckdb"
    )

    # Produktions-Schutzschicht (Whipsaw-F3, §2.12/§2.13)
    suppression_phasenlokal: bool = True

    # Regime-Gate (optional, §2.16-A.4): False = bitgenau identischer
    # Phase-1-Pfad (No-Harm-Invarianz); True = Gated-Portfolio exakt wie
    # OOS-abgenommen (§2.16-F.1: TREND -> RAW-A@96 + RAW-B@96 nur
    # Bruchrichtung; SHAKEOUT/UNKLAR -> strikt RAW-A@48).
    mit_regime_gate: bool = False

    # E3: RAW-Cluster A (frische Ausbrueche an der Kante)
    cluster_a_max_vorlauf: int = 1

    # E1: terminale Zeit-Exit-Horizonte (Phase 1: 48 = S1/AUG, 96 = Trend)
    zeit_horizonte: Tuple[int, ...] = (48, 96)

    # F4: struktureller Stop (intrabar, Puffer USD)
    stop_puffer: float = 0.15
    # F5: Volumen-Basis RAW (strikt kausal, shift(1))
    raw_vol_mult: float = 1.5
    sma_vol_period: int = 20
    # F6/F7: Retest-Kontakt (nur L1-Population, nicht Phase-1-Produktion)
    retest_band: float = 0.15
    retest_timeout_bars: int = 16
    # 0,45 %-SL: reine r_ref-Messung (nie Produktions-Stop)
    sl_pct_ref: float = 0.45

    # Segmentierungs-Konfiguration (Baseline-Konstanten, unveraendert)
    segment: SegmentConfig = field(default_factory=SegmentConfig)

    # EMA-Slope-Trailing (optionaler A/B-Modus, §5.2/§5.4): Default
    # deaktiviert -> _simuliere_kern/_kern_lauefe bleiben bitgenau Phase-1
    # (No-Harm-Invarianz). Aktivierung nur ueber --ema-trailing (main).
    ema_trailing: EMASlopeTrailingConfig = field(
        default_factory=EMASlopeTrailingConfig
    )

    # Phase 1 = Text-Export only (§2.14-B3)
    report_dir: Path = (
        Path(__file__).resolve().parent.parent / "reports" / "setup_c"
    )


@dataclass(slots=True)
class SetupCSignal:
    """Erfasstes Signal eines Arms (F4-F8, D4) - Zwischenstand vor Simulation.

    Populationen (L1) zaehlen SIGNAL mit gueltigem SL. ``vorlauf_bars`` ist
    seit der Kausalitaets-Bereinigung ein reines DIAGNOSE-Feld (Abstand
    Trigger-Bar zum 2-Close-Bruch) und an keiner Auswahl beteiligt;
    ``brk_idx`` ist ``None``, wenn die Phase bis zum Datenende nicht
    gebrochen ist (live: Phase noch offen).
    """

    arm: ArmName
    phase: int
    dir: DirName
    kante: float
    brk_idx: Optional[int]
    trigger_idx: int
    entry_idx: int
    entry_ts: Optional[pd.Timestamp]
    entry_preis: float
    stop_level: float
    sl_usd: float
    vorlauf_bars: Optional[int]
    vol_bestaetigt: Optional[bool]
    status: SignalStatus


@dataclass(slots=True)
class KernelTrade:
    """Simulierter Phase-1-Trade (RAW-A, F4 + Zeit-Exit, KEIN_TRAILING).

    RECHTS_ZENSIERT: r_f4/r_ref = NaN (E2), exit_* dokumentiert das Datenende.
    """

    phase: int
    dir: DirName
    horizont_bars: int
    entry_idx: int
    entry_ts: pd.Timestamp
    entry_preis: float
    f4_initial_stop: float
    sl_usd: float
    exit_idx: int
    exit_ts: pd.Timestamp
    exit_preis: float
    exit_grund: ExitGrund
    haltezeit_bars: int
    r_f4: float
    r_ref: float

    # Gate-Metadaten (NUR im Gate-Modus gefuellt; Baseline: None -> No-Harm).
    # Mutation ist seiteneffektfrei: _simuliere_kern/_kern_lauefe liefern
    # frische Objekte; Aggregation/TSV lesen nur die numerischen Felder.
    regime: Optional[str] = None  # "TREND" | "SHAKEOUT" | "UNKLAR"
    arm: Optional[str] = None     # "RAW-A" | "RAW-B" (nur Bruchrichtungs-Fallback)

    # Optionaler Stop-Pfad des EMA-Slope-Trailing (Variante B, §5.2) fuer das
    # Chart-Rendering. Jedes Element = (Bar-Index, Stop-Niveau) NACH einem
    # Ratchet-Nachzug; Start ist implizit (entry_idx, f4_initial_stop).
    # NUR im Trailing-Modus gefuellt; Baseline: None -> No-Harm.
    trailing_pfad: Optional[Tuple[Tuple[int, float], ...]] = None


@dataclass(slots=True)
class AggBlock:
    """Aggregationsblock (E2: Zensierte strikt isoliert; kein dict)."""

    n_kandidaten: int = 0
    n_supprimiert: int = 0
    n_aktiv: int = 0
    n_zensiert: int = 0
    n_gewertet: int = 0
    sum_r_f4: float = 0.0
    sum_r_ref: float = 0.0
    mean_r_f4: float = float("nan")
    median_r_f4: float = float("nan")
    wr: float = float("nan")
    pf: float = float("inf")
    n_init: int = 0
    n_zeit: int = 0
    n_trailing: int = 0
    n_crash: int = 0
    mean_offset: float = float("nan")


# =============================================================================
# 2) HILFSFUNKTIONEN (verbatim aus test/tmp_setup_c_audit.py, D1/D4/F5)
# =============================================================================


def _volumen_bestaetigt(
    df: pd.DataFrame, cfg: TrendConfig
) -> Tuple[np.ndarray, np.ndarray]:
    """F5-Volumenbedingung strikt kausal (keine Selbstinklusion).

    Args:
        df: OHLCV-DataFrame (tick_volume vorhanden).
        cfg: TrendConfig (raw_vol_mult, sma_vol_period).

    Returns:
        (bool-Array Bedingung, float-Array 1.5*SMA20(shift1)).
    """
    tv: np.ndarray = df["tick_volume"].values.astype(float)
    sma: np.ndarray = (
        pd.Series(tv)
        .rolling(cfg.sma_vol_period, min_periods=cfg.sma_vol_period)
        .mean()
        .shift(1)
        .values.astype(float)
    )
    ref: np.ndarray = cfg.raw_vol_mult * sma
    bed: np.ndarray = np.where(np.isnan(ref), False, tv >= ref)
    return bed, ref


def _kanten_reihe(
    ts_arr: np.ndarray,
    hist: Sequence[Tuple[pd.Timestamp, float]],
    fallback: float,
) -> np.ndarray:
    """Zeitlich gueltige Kante je Zeitstempel (D1/D4, Stufenfunktion).

    Args:
        ts_arr: datetime64-Array der Ziel-Zeitstempel (us ODER ns; wird fuer
            den searchsorted-Vergleich einheiten-bereinigt auf ns normiert).
        hist: U_hist/L_hist der Phase [(ts, value), ...] - aufsteigend.
        fallback: Kante, falls hist vor dem Zielzeitpunkt noch leer ist.
            D4: strikt der erste hist-Wert der EIGENEN Scan-Richtung
            (nie U_final/L_final, nie die gegenueberliegende Kante).

    Returns:
        Kantenwerte je Zeitstempel.
    """
    if not hist:
        return np.full(len(ts_arr), fallback, dtype=float)
    hist_ts = np.array([t.value for t, _ in hist], dtype="int64")
    hist_val = np.array([v for _, v in hist], dtype=float)
    # Einheiten-Bereinigung D4-Ratchet: hist_ts liegt in ns
    # (pd.Timestamp.value), ts_arr aus df["ts"].values kann datetime64[us]
    # sein (DuckDB/pandas >= 2.x) -> ohne Normalisierung auf ns wuerde
    # searchsorted alle Positionen auf -1 stellen (statische Kante = erster
    # hist-Wert statt zeitlich gueltiger Ratchet-Stufenfunktion).
    ts_ns = ts_arr.astype("datetime64[ns]").astype("int64")
    pos = np.searchsorted(hist_ts, ts_ns, side="right") - 1
    out = np.where(pos >= 0, hist_val[np.clip(pos, 0, len(hist_val) - 1)], fallback)
    return out.astype(float)


def _phase_start_idx(df: pd.DataFrame, start_ts: pd.Timestamp) -> int:
    """df-Index des Phasenstart-Zeitstempels (idx-Spalte vorhanden).

    Args:
        df: OHLCV-DataFrame (ts, idx).
        start_ts: Phasenstart-Zeitstempel (``p.start``).

    Returns:
        Zeilen-Index des Phasenbeginns in df.
    """
    ts_val: np.datetime64 = np.datetime64(start_ts)
    pos: int = int(np.searchsorted(df["ts"].values, ts_val, side="left"))
    return int(df["idx"].iloc[pos])


def _stop_f4(
    df: pd.DataFrame,
    lo_struktur_idx: int,
    hi_struktur_idx: int,
    kante: float,
    dir: DirName,
    cfg: TrendConfig,
) -> float:
    """Struktureller F4-Stop aus Kerzenstruktur und Kante.

    Args:
        df: OHLCV-DataFrame.
        lo_struktur_idx: erste Struktur-Bar (niedriger Index).
        hi_struktur_idx: zweite Struktur-Bar (Arm 2: brk_idx+1).
        kante: Referenzkante.
        dir: Signalrichtung.
        cfg: TrendConfig (stop_puffer).

    Returns:
        Stop-Level (Preis).
    """
    if dir == "up":
        struktur = float(
            np.min(df["low"].values[lo_struktur_idx : hi_struktur_idx + 1])
        )
        return min(struktur, kante) - cfg.stop_puffer
    struktur = float(
        np.max(df["high"].values[lo_struktur_idx : hi_struktur_idx + 1])
    )
    return max(struktur, kante) + cfg.stop_puffer


# =============================================================================
# 3) SIGNAL-ERFASSUNG (drei Arme; verbatim Logik, L1-Populationen)
# =============================================================================


def _erfasse_confirmed(
    df: pd.DataFrame, p: PhaseData, nr: int, cfg: TrendConfig
) -> SetupCSignal:
    """Arm 2: BREAKOUT_CONFIRMED - Einstieg open[brk_idx+2] (F2/F4).

    Args:
        df: OHLCV-DataFrame.
        p: PhaseData-Objekt (echter 2-Close-Bruch).
        nr: Phasennummer (1-basiert).
        cfg: TrendConfig.

    Returns:
        SetupCSignal (SIGNAL oder DATEN_ENDE).
    """
    assert p.brk_idx is not None and p.break_dir is not None
    assert p.brk_kante is not None
    b: int = int(p.brk_idx)
    n: int = len(df)
    s = SetupCSignal(
        arm="CONFIRMED", phase=nr, dir=p.break_dir,
        kante=float(p.brk_kante), brk_idx=b, trigger_idx=b, entry_idx=-1,
        entry_ts=None, entry_preis=float("nan"),
        stop_level=float("nan"), sl_usd=float("nan"),
        vorlauf_bars=None, vol_bestaetigt=None, status="SIGNAL",
    )
    if b + 2 >= n:
        s.status = "DATEN_ENDE"
        return s
    s.entry_idx = b + 2
    s.entry_ts = df["ts"].iloc[b + 2]
    s.stop_level = _stop_f4(df, b, b + 1, s.kante, s.dir, cfg)
    s.entry_preis = float(df["open"].values[b + 2])
    if s.dir == "up":
        s.sl_usd = s.entry_preis - s.stop_level
    else:
        s.sl_usd = s.stop_level - s.entry_preis
    return s


def _erfasse_raw(
    df: pd.DataFrame,
    p: PhaseData,
    nr: int,
    cfg: TrendConfig,
    vol_bed: np.ndarray,
    min_phase_candles: int,
) -> List[SetupCSignal]:
    """Arm 1: BREAKOUT_RAW - Volumen-Durchstoss an der kausalen Kante (F5/F4).

    LIVE-KAUSAL (Pflicht): Scannt [Phasenstart + MIN_PHASE_CANDLES, scan_hi]
    nach dem ersten Kanten-Durchstoss (high >= obere / low <= untere Kante)
    mit F5-Volumen. ``scan_hi`` ist die LIVE bekannte Phasengrenze:

      * Phase mit 2-Close-Bruch: ``scan_hi = brk_idx``. Der Bruch ist bei
        ``close[brk_idx+1]`` bekannt, alle Scan-Bars liegen davor -> jeder
        Trigger ist am jeweiligen Bar-Close entscheidbar.
      * Phase ohne Bruch (Phase laeuft bis zum Datenende): ``scan_hi = n-1``.
        Die Phase ist live erkennbar noch offen und wird NICHT verworfen
        (frueherer Stand: nur Bruch-Phasen wurden gescannt = Lookahead).

    KEIN Vorlauf-Filter: ``vorlauf_bars`` ist ein reines Diagnosefeld.
    Beide Richtungen unabhaengig (D4: Kante strikt kausal aus U_hist/L_hist;
    Scan erst ab dem ersten hist-Eintrag der Richtung; leere hist =
    KEINE_KANTE, kein Kreuz-Fallback). Status-Kategorien inkl. Diagnose
    (KEINE_KANTE, KEIN_DURCHSTOSS, KEIN_VOLUMEN, DATEN_ENDE) - identisch zur
    Audit-Referenz ``tmp_setup_c_audit.erfasse_raw``.

    Args:
        df: OHLCV-DataFrame.
        p: PhaseData-Objekt (mit oder ohne 2-Close-Bruch).
        nr: Phasennummer (1-basiert).
        cfg: TrendConfig.
        vol_bed: bool-Array F5-Bedingung ueber ganz df.
        min_phase_candles: SegmentConfig.min_phase_candles (Scan-Untergrenze).

    Returns:
        Liste mit 0..2 SetupCSignal-Objekten.
    """
    n: int = len(df)
    b_opt: Optional[int] = None if p.brk_idx is None else int(p.brk_idx)
    scan_hi: int = b_opt if b_opt is not None else n - 1
    start_idx: int = _phase_start_idx(df, p.start)
    scan_lo: int = start_idx + min_phase_candles
    ergebnis: List[SetupCSignal] = []

    def _leer(status: SignalStatus, dir: DirName, kante: float) -> SetupCSignal:
        return SetupCSignal(
            arm="RAW", phase=nr, dir=dir, kante=kante,
            brk_idx=b_opt, trigger_idx=-1, entry_idx=-1,
            entry_ts=None, entry_preis=float("nan"),
            stop_level=float("nan"), sl_usd=float("nan"),
            vorlauf_bars=None, vol_bestaetigt=None, status=status,
        )

    if scan_lo > scan_hi:
        # Phase zu kurz fuer einen Scan -> in Bruchrichtung ein Diagnosesignal
        if p.break_dir is not None and p.brk_kante is not None:
            return [_leer("KEIN_DURCHSTOSS", p.break_dir, float(p.brk_kante))]
        return []

    for dir in ("up", "down"):
        hist: Sequence[Tuple[pd.Timestamp, float]] = (
            list(p.U_hist) if dir == "up" else list(p.L_hist)
        )
        if not hist:
            ergebnis.append(_leer("KEINE_KANTE", dir, float("nan")))
            continue
        erster_hist_idx: int = int(
            np.searchsorted(
                df["ts"].values, np.datetime64(hist[0][0]), side="left"
            )
        )
        scan_lo_dir: int = max(scan_lo, erster_hist_idx)
        if scan_lo_dir > scan_hi:
            ergebnis.append(_leer("KEIN_DURCHSTOSS", dir, float("nan")))
            continue
        rng_dir: np.ndarray = np.arange(scan_lo_dir, scan_hi + 1)
        ts_rng_dir: np.ndarray = df["ts"].values[rng_dir]
        kante_r: np.ndarray = _kanten_reihe(
            ts_rng_dir, hist, float(hist[0][1])
        )
        if dir == "up":
            durchstoss: np.ndarray = df["high"].values[rng_dir] >= kante_r
        else:
            durchstoss = df["low"].values[rng_dir] <= kante_r
        treffer: np.ndarray = durchstoss & vol_bed[rng_dir]
        erste: Optional[int] = None
        if treffer.any():
            erste = scan_lo_dir + int(np.flatnonzero(treffer)[0])
        s = SetupCSignal(
            arm="RAW", phase=nr, dir=dir,
            kante=float(kante_r[erste - scan_lo_dir])
            if erste is not None
            else float(hist[0][1]),
            brk_idx=b_opt, trigger_idx=erste if erste is not None else -1,
            entry_idx=-1, entry_ts=None, entry_preis=float("nan"),
            stop_level=float("nan"), sl_usd=float("nan"),
            vorlauf_bars=None, vol_bestaetigt=None, status="SIGNAL",
        )
        if erste is None:
            s.status = "KEIN_VOLUMEN" if durchstoss.any() else "KEIN_DURCHSTOSS"
            s.vol_bestaetigt = False
            ergebnis.append(s)
            continue
        s.entry_idx = erste + 1
        if s.entry_idx >= n:
            s.status = "DATEN_ENDE"
            ergebnis.append(s)
            continue
        s.entry_ts = df["ts"].iloc[s.entry_idx]
        # Diagnose only - NICHT Auswahlkriterium (Cluster-A-Filter entfernt).
        s.vorlauf_bars = (b_opt - erste) if b_opt is not None else None
        s.vol_bestaetigt = True
        s.stop_level = _stop_f4(
            df, erste, erste, float(kante_r[erste - scan_lo_dir]), dir, cfg
        )
        s.entry_preis = float(df["open"].values[s.entry_idx])
        if dir == "up":
            s.sl_usd = s.entry_preis - s.stop_level
        else:
            s.sl_usd = s.stop_level - s.entry_preis
        ergebnis.append(s)
    return ergebnis


def _erfasse_retest(
    df: pd.DataFrame, p: PhaseData, nr: int, cfg: TrendConfig
) -> SetupCSignal:
    """Arm 3: RETEST_OUTSIDE - Pullback an die gebrochene Kante (F6/F7/F8).

    Args:
        df: OHLCV-DataFrame.
        p: PhaseData-Objekt.
        nr: Phasennummer.
        cfg: TrendConfig.

    Returns:
        SetupCSignal (SIGNAL oder Status-Kategorie).
    """
    assert p.brk_idx is not None and p.break_dir is not None
    assert p.brk_kante is not None
    n: int = len(df)
    b: int = int(p.brk_idx)
    up: bool = p.break_dir == "up"
    kante: float = float(p.brk_kante)
    lo: int = b + 1
    hi: int = min(b + cfg.retest_timeout_bars, n - 2)  # k+1 muss existieren
    s = SetupCSignal(
        arm="RETEST", phase=nr, dir=p.break_dir,
        kante=kante, brk_idx=b, trigger_idx=-1, entry_idx=-1,
        entry_ts=None, entry_preis=float("nan"),
        stop_level=float("nan"), sl_usd=float("nan"),
        vorlauf_bars=None, vol_bestaetigt=None, status="SIGNAL",
    )
    if hi < lo:
        s.status = "DATEN_ENDE"
        return s
    stop: float = _stop_f4(df, b, b + 1, kante, s.dir, cfg)
    s.stop_level = stop
    high: np.ndarray = df["high"].values
    low: np.ndarray = df["low"].values
    close: np.ndarray = df["close"].values
    if up:
        run_min: np.ndarray = np.minimum.accumulate(low[lo : hi + 1])
        verletzt: np.ndarray = run_min < stop
        kontakt: np.ndarray = (low[lo : hi + 1] >= kante - cfg.retest_band) & (
            low[lo : hi + 1] <= kante + cfg.retest_band
        )
        verteidigt: np.ndarray = close[lo : hi + 1] > kante
    else:
        run_max: np.ndarray = np.maximum.accumulate(high[lo : hi + 1])
        verletzt = run_max > stop
        kontakt = (high[lo : hi + 1] >= kante - cfg.retest_band) & (
            high[lo : hi + 1] <= kante + cfg.retest_band
        )
        verteidigt = close[lo : hi + 1] < kante
    kandidaten: np.ndarray = kontakt & verteidigt
    hatte_kontakt: bool = bool(kontakt.any())
    if kandidaten.any():
        erste_k: int = lo + int(np.flatnonzero(kandidaten)[0])
        rel: int = erste_k - lo
        if verletzt[rel]:
            s.status = "VERWORFEN_STOP_VERLETZT"
            return s
        s.trigger_idx = erste_k
        s.entry_idx = erste_k + 1
        s.entry_ts = df["ts"].iloc[s.entry_idx]
        s.entry_preis = float(df["open"].values[s.entry_idx])
        if up:
            s.sl_usd = s.entry_preis - stop
        else:
            s.sl_usd = stop - s.entry_preis
        return s
    if hatte_kontakt:
        s.status = "KEIN_CLOSE_SCHUTZ"
        return s
    s.status = "VERWORFEN_STOP_VERLETZT" if bool(verletzt.any()) else "TIMEOUT"
    return s


def _erfasse_signale(
    sr: SegmentResult, cfg: TrendConfig
) -> List[SetupCSignal]:
    """Erfasst alle Signale eines Fensters ueber die drei Arme (L1).

    LIVE-KAUSAL: Es werden ALLE Phasen verarbeitet - auch die bis zum
    Datenende ungebrochene (letzte) Phase. Ein frueherer Stand zensierte sie
    (``nur echte Bruch-Phasen``), was der Live-Sicht widerspricht: eine noch
    offene, etablierte Phase ist handelbar, sobald die Kante kausal
    durchstossen wird. CONFIRMED/RETEST brauchen die Bruchkante und werden
    daher weiterhin nur fuer gebrochene Phasen erzeugt.

    Die Phasennummerierung bleibt gegenueber der Gate-/Harness-Konvention
    stabil: gebrochene Phasen erhalten 1..k in Reihenfolge; die offene
    Schlussphase (hoechstens eine) erhaelt k+1.

    Args:
        sr: SegmentResult aus market_segmentation.segmentiere_markt.
        cfg: TrendConfig.

    Returns:
        Alle SetupCSignal-Objekte je Phase.
    """
    df: pd.DataFrame = sr.df
    vol_bed, _ = _volumen_bestaetigt(df, cfg)
    min_phase_candles: int = cfg.segment.min_phase_candles
    alle: List[SetupCSignal] = []
    nr: int = 0
    for p in sr.phases:
        nr += 1
        if p.break_dir is not None and p.brk_idx is not None:
            alle.append(_erfasse_confirmed(df, p, nr, cfg))
            alle.extend(_erfasse_raw(df, p, nr, cfg, vol_bed, min_phase_candles))
            alle.append(_erfasse_retest(df, p, nr, cfg))
        else:
            # Offene Phase (kein 2-Close-Bruch bis Datenende): nur der
            # live-kausale RAW-Trigger ist definiert.
            alle.extend(_erfasse_raw(df, p, nr, cfg, vol_bed, min_phase_candles))
    return alle


def _population(
    signale: Sequence[SetupCSignal], arm: ArmName
) -> List[SetupCSignal]:
    """SIGNAL-Population eines Arms (entry_idx >= 0, sl_usd endlich > 0).

    Args:
        signale: Alle erfassten Signale.
        arm: Armname.

    Returns:
        Gueltige SIGNAL-Signale des Arms.
    """
    return [
        s
        for s in signale
        if s.arm == arm and s.status == "SIGNAL" and s.entry_idx >= 0
        and np.isfinite(s.sl_usd) and s.sl_usd > 0.0
    ]


# =============================================================================
# 4) SIMULATIONSKERN (Phase 1: F4 intrabar + terminaler Zeit-Exit, KEIN_TRAILING;
#    optional EMA-Slope-Trailing Variante B, §5.2/§5.4)
# =============================================================================


def berechne_ema_slope_vektoren(
    df: pd.DataFrame, periode: int = 20
) -> Tuple[np.ndarray, np.ndarray]:
    """Berechnet kausal den Close-EMA und dessen 1-Bar-Slope (Vektoren).

    Rein vektorisiert (ewm/diff, keinerlei Schleifen). Der Wert an Bar ``k``
    nutzt ausschliesslich Closes ``<= k`` (kein Lookahead): EMA ueber
    ``ewm(span=periode, adjust=False)``, Slope = EMA_t - EMA_{t-1}
    (§5.2: erste Ableitung). Der NaN an Position 0 wird mit 0.0 gefuellt
    (kausal neutral, identische Semantik wie der Referenz-Entwurf).

    Args:
        df: OHLCV-DataFrame (close-Spalte vorhanden).
        periode: EMA-Periode (Standard 20, Projektkonvention §2.1/§2.16).

    Returns:
        (ema_werte, slope_werte) als float64-Arrays ueber ganz df.
    """
    close_s: pd.Series = df["close"].astype(float)
    ema_s: pd.Series = close_s.ewm(span=periode, adjust=False).mean()
    slope_s: pd.Series = ema_s.diff().fillna(0.0)
    return (
        ema_s.to_numpy(dtype=float, copy=True),
        slope_s.to_numpy(dtype=float, copy=True),
    )


def _simuliere_kern(
    df: pd.DataFrame,
    sig: SetupCSignal,
    cfg: TrendConfig,
    horizont: int,
) -> KernelTrade:
    """Simuliert ein RAW-A-Signal unter F4 + Zeit-Exit (E1/E2/E5-KT).

    Bar fuer Bar ab Einstieg bis min(entry+N, Datenende). Reihenfolge je Bar:
      1) F4-Stop intrabar - VORRANG vor dem Zeit-Exit (Mentor-Urteil).
      2) Zeit-Exit am Close, sobald k == entry_idx + N.
    Ueberlebt der Trade das Datenende ohne Stop und ohne erreichten Horizont
    (entry+N > n-1), gilt er als RECHTS_ZENSIERT (E2, r = NaN).

    Args:
        df: OHLCV-DataFrame.
        sig: SetupCSignal (SIGNAL, sl_usd > 0).
        cfg: TrendConfig.
        horizont: Zeit-Horizont N in Bars (48/96).

    Returns:
        KernelTrade.
    """
    n: int = len(df)
    e: int = int(sig.entry_idx)
    up: bool = sig.dir == "up"
    entry: float = float(df["open"].values[e])
    f4_stop: float = float(sig.stop_level)
    sl_usd: float = float(sig.sl_usd)
    high: np.ndarray = df["high"].values.astype(float)
    low: np.ndarray = df["low"].values.astype(float)
    close: np.ndarray = df["close"].values.astype(float)

    ziel_bar: int = e + horizont
    letzte_bar: int = n - 1
    loop_ende: int = min(ziel_bar, letzte_bar)

    exit_grund: ExitGrund = "RECHTS_ZENSIERT"  # Default, falls Loop ohne Break
    exit_idx: int = letzte_bar
    exit_preis: float = float(close[letzte_bar])

    for k in range(e, loop_ende + 1):
        # 1) F4-Initial-Stop intrabar (Vorrang vor Zeit-Exit)
        if (up and low[k] <= f4_stop) or ((not up) and high[k] >= f4_stop):
            exit_preis, exit_idx, exit_grund = float(f4_stop), k, "INITIAL_SL_INTRABAR"
            break
        # 2) Terminaler Zeit-Exit am Close der Exit-Bar
        if k == ziel_bar:
            exit_preis, exit_idx, exit_grund = float(close[k]), k, "ZEIT_EXIT_CLOSE"
            break

    haltezeit: int = exit_idx - e
    zensiert: bool = exit_grund == "RECHTS_ZENSIERT"
    if zensiert:
        r_f4: float = float("nan")
        r_ref: float = float("nan")
    else:
        if up:
            r_f4 = (exit_preis - entry) / sl_usd
        else:
            r_f4 = (entry - exit_preis) / sl_usd
        r_ref_base: float = entry * cfg.sl_pct_ref / 100.0
        r_ref = (
            (exit_preis - entry) / r_ref_base
            if up
            else (entry - exit_preis) / r_ref_base
        )

    return KernelTrade(
        phase=sig.phase, dir=sig.dir, horizont_bars=horizont,
        entry_idx=e, entry_ts=df["ts"].iloc[e], entry_preis=entry,
        f4_initial_stop=f4_stop, sl_usd=sl_usd,
        exit_idx=exit_idx, exit_ts=df["ts"].iloc[exit_idx],
        exit_preis=float(exit_preis), exit_grund=exit_grund,
        haltezeit_bars=haltezeit, r_f4=float(r_f4), r_ref=float(r_ref),
    )


def _simuliere_kern_ema_trailing(
    df: pd.DataFrame,
    sig: SetupCSignal,
    cfg: TrendConfig,
    ema_arr: np.ndarray,
    slope_arr: np.ndarray,
    trailing_cfg: EMASlopeTrailingConfig,
) -> KernelTrade:
    """Simuliert RAW-A-Signal mit EMA-Slope-Trailing (Variante B, §5.2).

    Abweichend vom Baseline-Kern (``_simuliere_kern``) ist der terminale
    Zeit-Exit N=48/96 ENTKOPPELT (§5.1-Architektur-Entscheidung). Statt
    dessen gilt je Bar (strikt kausal, Reihenfolge wie Baseline):
      1) Stop intrabar mit dem AKTUELLEN Stop-Niveau (initial F4 oder
         nachgezogen) - VORRANG.
      2) Crash-Sicherung (Notbremse): k == entry_idx + notfall_horizont_bars
         -> Exit am Close (CRASH_HORIZONT_CLOSE).
      3) EMA-Slope-Ratchet (Variante B): Slope_t <= 0 (Long) bzw. >= 0
         (Short) -> Stop auf das Extremum der Abflachungs-Kerze nachziehen
         (Low bei Long, High bei Short). Monotonie-Pflicht: Der Stop darf
         NIE zurueckweichen (nur erhoehen bei Long / nur senken bei Short).
         Optional greift die Gewinnschwelle ``mindest_gewinn_r`` (0.0 =
         sofort ab der ersten Kerze aktiv).
    Ueberlebt der Trade das Datenende ohne Stop und ohne erreichte
    Crash-Schranke, gilt er als RECHTS_ZENSIERT (E2, r = NaN).

    Args:
        df: OHLCV-DataFrame.
        sig: SetupCSignal (SIGNAL, sl_usd > 0).
        cfg: TrendConfig (fuer sl_pct_ref/r_ref).
        ema_arr: Kausaler Close-EMA-Vektor ueber df (len(df)).
        slope_arr: Kausaler 1-Bar-Slope-Vektor ueber df (len(df)).
        trailing_cfg: EMASlopeTrailingConfig (aktiviert, STOP_AUF_EXTREMUM).

    Returns:
        KernelTrade (horizont_bars = notfall_horizont_bars).
    """
    n: int = len(df)
    e: int = int(sig.entry_idx)
    up: bool = sig.dir == "up"
    entry: float = float(df["open"].values[e])
    f4_stop: float = float(sig.stop_level)
    sl_usd: float = float(sig.sl_usd)
    high: np.ndarray = df["high"].values.astype(float)
    low: np.ndarray = df["low"].values.astype(float)
    close: np.ndarray = df["close"].values.astype(float)

    notfall: int = trailing_cfg.notfall_horizont_bars
    ziel_bar: int = e + notfall
    letzte_bar: int = n - 1
    loop_ende: int = min(ziel_bar, letzte_bar)

    exit_grund: ExitGrund = "RECHTS_ZENSIERT"  # Default, falls Loop ohne Break
    exit_idx: int = letzte_bar
    exit_preis: float = float(close[letzte_bar])
    akt_sl: float = f4_stop  # laufender Stop (initial = F4, dann Ratchet)
    pfad: List[Tuple[int, float]] = []  # Ratchet-Punkte fuer Chart-Rendering

    for k in range(e, loop_ende + 1):
        # 1) Stop intrabar mit aktuellem Niveau (Vorrang vor Crash-Schranke)
        if (up and low[k] <= akt_sl) or ((not up) and high[k] >= akt_sl):
            exit_preis = akt_sl
            exit_idx = k
            exit_grund = (
                "INITIAL_SL_INTRABAR"
                if akt_sl == f4_stop
                else "TRAILING_SL_INTRABAR"
            )
            break
        # 2) Crash-Sicherung am Close der Notfall-Bar (terminal)
        if k == ziel_bar:
            exit_preis, exit_idx, exit_grund = (
                float(close[k]), k, "CRASH_HORIZONT_CLOSE"
            )
            break
        # 3) EMA-Slope-Ratchet (Variante B): Extremum der Abflachungs-Kerze
        slope_k: float = float(slope_arr[k])
        ratchet_ok: bool = trailing_cfg.mindest_gewinn_r <= 0.0
        if not ratchet_ok:
            fl_r: float = (
                (close[k] - entry) / sl_usd if up else (entry - close[k]) / sl_usd
            )
            ratchet_ok = fl_r >= trailing_cfg.mindest_gewinn_r
        if ratchet_ok and ((up and slope_k <= 0.0) or ((not up) and slope_k >= 0.0)):
            neuer_sl: float = float(low[k] if up else high[k])
            # Monotonie: Stop darf nie zurueckweichen (nie Risiko vergroessern)
            if (up and neuer_sl > akt_sl) or ((not up) and neuer_sl < akt_sl):
                akt_sl = neuer_sl
                pfad.append((k, akt_sl))

    haltezeit: int = exit_idx - e
    zensiert: bool = exit_grund == "RECHTS_ZENSIERT"
    if zensiert:
        r_f4: float = float("nan")
        r_ref: float = float("nan")
    else:
        if up:
            r_f4 = (exit_preis - entry) / sl_usd
        else:
            r_f4 = (entry - exit_preis) / sl_usd
        r_ref_base: float = entry * cfg.sl_pct_ref / 100.0
        r_ref = (
            (exit_preis - entry) / r_ref_base
            if up
            else (entry - exit_preis) / r_ref_base
        )

    return KernelTrade(
        phase=sig.phase, dir=sig.dir, horizont_bars=notfall,
        entry_idx=e, entry_ts=df["ts"].iloc[e], entry_preis=entry,
        f4_initial_stop=f4_stop, sl_usd=sl_usd,
        exit_idx=exit_idx, exit_ts=df["ts"].iloc[exit_idx],
        exit_preis=float(exit_preis), exit_grund=exit_grund,
        haltezeit_bars=haltezeit, r_f4=float(r_f4), r_ref=float(r_ref),
        trailing_pfad=tuple(pfad) if pfad else None,
    )


def _kern_lauefe(
    df: pd.DataFrame,
    signale: Sequence[SetupCSignal],
    cfg: TrendConfig,
    horizont: int,
    nur_cluster_a: bool = False,
) -> Tuple[List[KernelTrade], int]:
    """Produktionslauf der RAW-Signale (live-kausal + F3-Suppression).

    HANDELSPFAD (Default, ``nur_cluster_a=False``): ALLE gueltigen
    RAW-Signale werden gehandelt - jedes ist am Bar-Close entschieden
    (Kanten-Durchstoss + F5-Volumen, Einstieg Open der Folge-Bar). Es gibt
    KEINEN Vorlauf-Filter; ``vorlauf_bars`` ist reine Diagnose. Damit ist der
    Pfad lookahead-frei (Hausregel).

    ``nur_cluster_a=True``: reproduziert den historischen "RAW-Cluster A"
    (``vorlauf <= cfg.cluster_a_max_vorlauf``) AUSSCHLIESSLICH fuer die
    eingefrorene §2.16-Gate-Gegenprobe. Dieser Pfad ist NICHT handelbar
    (er setzt das Bruchwissen voraus) und darf nie als Ergebnis
    praesentiert werden.

    Suppression (F3, §2.12/§2.13-C: "aktiver Trade in DERSELBEN Richtung
    derselben Phase"): Ein Kandidat wird nur dann verworfen, wenn in
    derselben (phase, dir) eine fruehere Position noch offen ist
    (entry_idx <= exit_idx). Da ``_erfasse_raw`` je (Phase, Richtung) maximal
    EIN Signal liefert, ist die Suppression ein No-op (n_supprimiert = 0).
    Kein Cross-Richtungs-Eingriff (up/down derselben Phase sind unabhaengige,
    gleichzeitig handelbare Setups).

    EMA-Slope-Trailing (optional): Ist ``cfg.ema_trailing.aktiviert``, wird
    jeder Kandidat mit ``_simuliere_kern_ema_trailing`` simuliert (Variante B,
    §5.2). Die kausalen EMA-/Slope-Vektoren werden genau einmal je Lauf
    berechnet. Das ``horizont``-Argument ist im Trailing-Modus bedeutungslos:
    die Laufzeitgrenze bestimmt ausschliesslich
    ``cfg.ema_trailing.notfall_horizont_bars`` (Crash-Sicherung).

    Args:
        df: OHLCV-DataFrame.
        signale: Alle erfassten Signale.
        cfg: TrendConfig.
        horizont: Zeit-Horizont N in Bars (nur Baseline; im Trailing-Modus
            ohne Bedeutung).
        nur_cluster_a: Historischer Gate-Vergleichspfad (NICHT handelbar).

    Returns:
        (aktivierte KernelTrades, n_supprimiert).
    """
    if cfg.ema_trailing.aktiviert:
        if cfg.ema_trailing.modus != "STOP_AUF_EXTREMUM":
            raise NotImplementedError(
                "EMA-Slope-Trailing: Modus "
                f"{cfg.ema_trailing.modus} (Variante A/SOFORT_EXIT) ist "
                "Backlog-Task §5.4 - nur STOP_AUF_EXTREMUM implementiert."
            )
        ema_arr, slope_arr = berechne_ema_slope_vektoren(
            df, cfg.ema_trailing.ema_periode
        )

        def _sim(sig: SetupCSignal) -> KernelTrade:
            return _simuliere_kern_ema_trailing(
                df, sig, cfg, ema_arr, slope_arr, cfg.ema_trailing
            )

    else:

        def _sim(sig: SetupCSignal) -> KernelTrade:
            return _simuliere_kern(df, sig, cfg, horizont)

    kandidaten: List[SetupCSignal] = [
        s
        for s in signale
        if s.arm == "RAW" and s.status == "SIGNAL" and s.entry_idx >= 0
        and np.isfinite(s.sl_usd) and s.sl_usd > 0.0
        and (
            not nur_cluster_a
            or (
                s.vorlauf_bars is not None
                and s.vorlauf_bars <= cfg.cluster_a_max_vorlauf
            )
        )
    ]
    kandidaten.sort(key=lambda s: (s.phase, s.dir, s.entry_idx))

    trades: List[KernelTrade] = []
    if not cfg.suppression_phasenlokal:
        for sig in kandidaten:
            trades.append(_sim(sig))
        return trades, 0

    n_supprimiert: int = 0
    # F3: Key = (Phase, Richtung) - explizit typisiert (kein implizites dict)
    offen_bis: Dict[Tuple[int, DirName], int] = {}
    for sig in kandidaten:
        key: Tuple[int, DirName] = (sig.phase, sig.dir)
        if sig.entry_idx <= offen_bis.get(key, -1):
            n_supprimiert += 1
            continue
        trade: KernelTrade = _sim(sig)
        trades.append(trade)
        offen_bis[key] = int(trade.exit_idx)
    return trades, n_supprimiert


def _gate_portfolio_laeufe(
    df: pd.DataFrame,
    signale: Sequence[SetupCSignal],
    cfg: TrendConfig,
    sr: SegmentResult,
    states: Sequence["RegimeState"],
) -> Tuple[
    List[KernelTrade], List[KernelTrade], List[KernelTrade], List[KernelTrade]
]:
    """Assembliert das Gated-Portfolio (1:1-Spiegel der OOS-Harness-Logik).

    Exakte Uebernahme der verifizierten Assemblierung aus
    test/tmp_regime_validation.py (``_baue_cache`` + ``_gated_trades_fuer_phase``,
    §2.16-F.1), damit die Produktion bitgenau das abgenommene Portfolio
    reproduziert:

      SHAKEOUT/UNKLAR: RAW-A @48, beide Richtungen (= B48-Beitrag, No-Harm).
      TREND:           RAW-A @96, beide Richtungen; RAW-B @96 NUR auf
                       (phase, Bruchrichtung) und NUR als Fallback, wenn dort
                       KEIN RAW-A @96 existiert. RAW-A/RAW-B sind ueber
                       ``vorlauf_bars`` disjunkt (A <= 1 XOR B > 1) -> keine
                       Kollision, keine zeitliche Merge-Ratsche.

    F3-Suppression ist fuer RAW-A ein No-op (Harness-Assert) - der Lauf
    bricht hart ab, falls die No-op-Garantie je verletzt wuerde.

    Args:
        df: OHLCV-DataFrame.
        signale: Alle erfassten Signale (unveraendert, L1-Populationen).
        cfg: TrendConfig.
        sr: SegmentResult (fuer break_dir je Phase).
        states: Klassifizierte RegimeState (len == echte Bruch-Phasen).

    Returns:
        (gated, a48, a96, b96): gated chronologisch sortiert; a48/a96/b96
        als vollstaendige Listen fuer die Breakdown-/Referenz-Zeilen.
    """
    echte: List[PhaseData] = [
        p for p in sr.phases if p.break_dir is not None and p.brk_idx is not None
    ]
    if len(states) != len(echte):
        raise RuntimeError(
            f"Gate: {len(states)} RegimeState != {len(echte)} echte Phasen "
            "(Join-Schluessel phase_nr inkonsistent)."
        )

    # RAW-A-Basen (beide Horizonte); F3-Suppression muss No-op sein.
    # WICHTIG: nur_cluster_a=True reproduziert den EINGEFRORENEN historischen
    # Cluster-A-Pfad (Lookahead) fuer den §2.16-OOS-Vergleich. Der Gate-Report
    # ist KEIN Handelspfad.
    a48, ns48 = _kern_lauefe(df, signale, cfg, 48, nur_cluster_a=True)
    a96, ns96 = _kern_lauefe(df, signale, cfg, 96, nur_cluster_a=True)
    if ns48 != 0 or ns96 != 0:
        raise RuntimeError(
            f"Gate: RAW-A-Suppression nicht No-op (n48={ns48}, n96={ns96})."
        )
    a48d: Dict[Tuple[int, str], KernelTrade] = {
        (int(t.phase), str(t.dir)): t for t in a48
    }
    a96d: Dict[Tuple[int, str], KernelTrade] = {
        (int(t.phase), str(t.dir)): t for t in a96
    }
    brk_dir: Dict[int, str] = {}
    for nr, p in enumerate(echte, start=1):
        assert p.break_dir is not None and p.brk_idx is not None
        brk_dir[nr] = str(p.break_dir)

    # RAW-B @96: vorlauf > 1, NUR Bruchrichtung, NUR wo kein RAW-A @96
    b96d: Dict[Tuple[int, str], KernelTrade] = {}
    for sig in signale:
        if (
            sig.arm == "RAW"
            and sig.status == "SIGNAL"
            and sig.entry_idx >= 0
            and np.isfinite(sig.sl_usd)
            and sig.sl_usd > 0.0
            and sig.vorlauf_bars is not None
            and sig.vorlauf_bars > cfg.cluster_a_max_vorlauf
        ):
            nr = int(sig.phase)
            d = str(sig.dir)
            if d != brk_dir.get(nr):
                continue  # nur Bruchrichtung
            if (nr, d) in a48d or (nr, d) in a96d:
                continue  # Sicherheit: disjunkt (darf nicht auftreten)
            b96d[(nr, d)] = _simuliere_kern(df, sig, cfg, 96)
    b96: List[KernelTrade] = list(b96d.values())

    # Assemblierung je Phase gemaess Regime (Harness-Semantik, 1:1)
    gated: List[KernelTrade] = []
    for st in states:
        nr = int(st.phase_nr)
        r: str = str(st.regime)
        if r == "TREND":
            bdir: str = brk_dir.get(nr) or "up"
            for d in ("up", "down"):
                key = (nr, d)
                t: Optional[KernelTrade] = a96d.get(key)
                if t is not None:
                    t.regime, t.arm = r, "RAW-A"
                elif d == bdir:
                    t = b96d.get(key)
                    if t is not None:
                        t.regime, t.arm = r, "RAW-B"
                if t is not None:
                    gated.append(t)
        else:
            # SHAKEOUT/UNKLAR: strikt RAW-A @48 (No-Harm = B48-Beitrag)
            for d in ("up", "down"):
                t = a48d.get((nr, d))
                if t is not None:
                    t.regime, t.arm = r, "RAW-A"
                    gated.append(t)
    gated.sort(key=lambda x: (x.entry_idx, x.phase, x.dir))
    return gated, a48, a96, b96


# =============================================================================
# 5) AGGREGATION (E2: Zensierte strikt isoliert)
# =============================================================================


def _agg_block(trades: Sequence[KernelTrade], n_supprimiert: int = 0) -> AggBlock:
    """Aggregiert KernelTrades (Zensierte strikt aus Performance isoliert).

    Args:
        trades: Aktivierte KernelTrades eines Laufs.
        n_supprimiert: Durch F3-Suppression verworfen (Diagnose).

    Returns:
        AggBlock.
    """
    agg: AggBlock = AggBlock(
        n_kandidaten=len(trades) + n_supprimiert,
        n_supprimiert=n_supprimiert,
        n_aktiv=len(trades),
    )
    if not trades:
        return agg
    rs: List[float] = []
    offsets: List[int] = []
    for r in trades:
        if r.exit_grund == "RECHTS_ZENSIERT":
            agg.n_zensiert += 1
            continue
        if r.exit_grund == "INITIAL_SL_INTRABAR":
            agg.n_init += 1
        elif r.exit_grund == "TRAILING_SL_INTRABAR":
            agg.n_trailing += 1
        elif r.exit_grund == "CRASH_HORIZONT_CLOSE":
            agg.n_crash += 1
        else:
            agg.n_zeit += 1
        rs.append(float(r.r_f4))
        agg.sum_r_ref += float(r.r_ref)
        offsets.append(r.haltezeit_bars)
    n_gew: int = len(rs)
    agg.n_gewertet = n_gew
    if not n_gew:
        return agg
    arr: np.ndarray = np.array(rs, dtype=float)
    agg.sum_r_f4 = float(arr.sum())
    agg.mean_r_f4 = float(arr.mean())
    agg.median_r_f4 = float(np.median(arr))
    agg.wr = float(np.mean(arr > 0.0) * 100.0)
    pos: float = float(arr[arr > 0.0].sum())
    neg: float = float(-arr[arr < 0.0].sum())
    agg.pf = pos / neg if neg > 0.0 else float("inf")
    agg.mean_offset = float(np.mean(offsets)) if offsets else float("nan")
    return agg


def _fmt(v: object, fmt: str = ".2f") -> str:
    """Formatiert Zahlen (NaN/None -> '-').

    Args:
        v: Wert.
        fmt: Format-String.

    Returns:
        Formatierter String.
    """
    if v is None:
        return "-"
    if isinstance(v, (float, np.floating)) and not np.isfinite(float(v)):
        return "-"
    return f"{v:{fmt}}"


# =============================================================================
# 6) REPORT (Text + maschinenlesbarer Trade-Block, reports/setup_c/)
# =============================================================================


def _block_text(titel: str, agg: AggBlock) -> List[str]:
    """Formatiert einen Aggregationsblock fuer eine Gruppe.

    Args:
        titel: Blocktitel.
        agg: Aggregationsergebnis.

    Returns:
        Textzeilen.
    """
    t = (
        f"{titel}  (n={agg.n_kandidaten}, supprimiert={agg.n_supprimiert}, "
        f"aktiv={agg.n_aktiv}, zensiert={agg.n_zensiert}, gewertet={agg.n_gewertet})"
    )
    lines: List[str] = [t, "  " + "-" * max(2, len(t) - 2)]
    if not agg.n_gewertet:
        lines.append("  (keine gewerteten Trades - nur RECHTS_ZENSIERT)")
        return lines
    lines.append(
        f"  sum r_f4={agg.sum_r_f4:>9.2f}  mean r_f4={_fmt(agg.mean_r_f4):>7}  "
        f"median={_fmt(agg.median_r_f4):>7}  WR={_fmt(agg.wr, '.1f')}%  "
        f"PF={_fmt(agg.pf)}"
    )
    lines.append(f"  sum r_ref (0.45%-Basis) = {agg.sum_r_ref:.2f}")
    exit_teile: List[str] = [
        f"INITIAL_SL_INTRABAR={agg.n_init}",
        f"ZEIT_EXIT_CLOSE={agg.n_zeit}",
    ]
    if agg.n_trailing:
        exit_teile.append(f"TRAILING_SL_INTRABAR={agg.n_trailing}")
    if agg.n_crash:
        exit_teile.append(f"CRASH_HORIZONT_CLOSE={agg.n_crash}")
    exit_teile.append(f"RECHTS_ZENSIERT={agg.n_zensiert}")
    lines.append("  Exit: " + " | ".join(exit_teile))
    lines.append(f"  mittl. Haltedauer (gewertet) = {_fmt(agg.mean_offset, '.0f')} Bars")
    return lines


def _trade_block_tsv(
    trades: Sequence[KernelTrade], fenster: str, cfg: TrendConfig
) -> str:
    """Maschinenlesbarer Trade-Block (TSV) je Fenster ueber alle Horizonte.

    Args:
        trades: Aktivierte RAW-A-KernelTrades (alle Horizonte).
        fenster: Fenster-Label.
        cfg: TrendConfig (fuer Metadatenzeilen).

    Returns:
        TSV-Text (Kommentarzeilen + Header + Datenzeilen).
    """
    mode_kopf: str = (
        "EMA-Slope-Trailing (Variante B)"
        if cfg.ema_trailing.aktiviert
        else "RAW live-kausal + F4 intrabar + Zeit-Exit"
    )
    kopf: List[str] = [
        f"# setup_c Phase-1-Kern ({mode_kopf}) - Fenster: {fenster} | "
        f"Symbol: {cfg.symbol} {cfg.timeframe}",
        f"# HANDELSPFAD: alle kausalen RAW-Trigger (KEIN Vorlauf-Filter) | "
        f"suppression_phasenlokal: {cfg.suppression_phasenlokal} | "
        f"stop_puffer: {cfg.stop_puffer} | sl_pct_ref: {cfg.sl_pct_ref}",
        "# vorlauf_bars ist Diagnose (nicht Auswahl); brk_idx leer = offene Phase",
        "# RECHTS_ZENSIERT: r_f4/r_ref = NaN (E2, strikt isoliert)",
    ]
    header: str = (
        "horizont\tphase\tdir\tentry_idx\tentry_ts\tentry_preis\t"
        "f4_initial_stop\tsl_usd\texit_idx\texit_ts\texit_preis\t"
        "exit_grund\thaltezeit_bars\tr_f4\tr_ref"
    )
    zeilen: List[str] = [*kopf, header]
    for t in sorted(trades, key=lambda x: (x.horizont_bars, x.phase, x.entry_idx)):
        zeilen.append(
            f"{t.horizont_bars}\t{t.phase}\t{t.dir}\t{t.entry_idx}\t"
            f"{t.entry_ts}\t{t.entry_preis:.5f}\t{t.f4_initial_stop:.5f}\t"
            f"{t.sl_usd:.5f}\t{t.exit_idx}\t{t.exit_ts}\t{t.exit_preis:.5f}\t"
            f"{t.exit_grund}\t{t.haltezeit_bars}\t{_fmt(t.r_f4)}\t{_fmt(t.r_ref)}"
        )
    return "\n".join(zeilen)


def _trade_block_gate_tsv(
    trades: Sequence[KernelTrade], fenster: str, cfg: TrendConfig
) -> str:
    """Maschinenlesbarer Gate-Trade-Block (TSV) inkl. regime/arm-Spalten."""
    kopf: List[str] = [
        f"# setup_c Gate-Modus (Gated-Portfolio, --mit-regime-gate) - Fenster: {fenster} "
        f"| Symbol: {cfg.symbol} {cfg.timeframe}",
        f"# suppression_phasenlokal: {cfg.suppression_phasenlokal} | "
        f"cluster_a_max_vorlauf: {cfg.cluster_a_max_vorlauf} | "
        f"stop_puffer: {cfg.stop_puffer} | sl_pct_ref: {cfg.sl_pct_ref}",
        "# Portfolio (§2.16-F.1): TREND -> RAW-A@96 + RAW-B@96 (Bruchrichtung) | "
        "SHAKEOUT/UNKLAR -> RAW-A@48",
        "# RECHTS_ZENSIERT: r_f4/r_ref = NaN (E2, strikt isoliert)",
    ]
    header: str = (
        "regime\tarm\thorizont\tphase\tdir\tentry_idx\tentry_ts\tentry_preis\t"
        "f4_initial_stop\tsl_usd\texit_idx\texit_ts\texit_preis\t"
        "exit_grund\thaltezeit_bars\tr_f4\tr_ref"
    )
    zeilen: List[str] = [*kopf, header]
    for t in sorted(trades, key=lambda x: (x.entry_idx, x.phase, x.dir)):
        zeilen.append(
            f"{t.regime}\t{t.arm}\t{t.horizont_bars}\t{t.phase}\t{t.dir}\t"
            f"{t.entry_idx}\t{t.entry_ts}\t{t.entry_preis:.5f}\t"
            f"{t.f4_initial_stop:.5f}\t{t.sl_usd:.5f}\t{t.exit_idx}\t"
            f"{t.exit_ts}\t{t.exit_preis:.5f}\t{t.exit_grund}\t"
            f"{t.haltezeit_bars}\t{_fmt(t.r_f4)}\t{_fmt(t.r_ref)}"
        )
    return "\n".join(zeilen)


def _bericht_gate(
    fenster: str,
    cfg: TrendConfig,
    df: pd.DataFrame,
    sr: SegmentResult,
    signale: Sequence[SetupCSignal],
    states: Sequence["RegimeState"],
) -> str:
    """Baut den Gate-Report (konsolidiert + Breakdown + No-Harm-Nachweis).

    Primaer-Sicht = Gated-Portfolio (konsolidiert, exakt OOS-vergleichbar,
    §2.16-F.6-Muster); darunter Breakdown RAW-A@48 / RAW-A@96 / RAW-B@96
    (forensisch) und die B48/B96-Referenz-Baselines mit Primaer-Delta.
    Dateien getrennt (``setup_c_gate_*``) -> historische Baseline-Artefakte
    ``setup_c_*.txt/.tsv`` bleiben byte-identisch unberuehrt.
    """
    gated, a48, a96, b96 = _gate_portfolio_laeufe(
        df, signale, cfg, sr, states
    )
    n_trend: int = sum(1 for st in states if st.regime == "TREND")
    n_shake: int = sum(1 for st in states if st.regime == "SHAKEOUT")
    n_unklar: int = sum(1 for st in states if st.regime == "UNKLAR")
    agg_g: AggBlock = _agg_block(gated)
    agg_a48: AggBlock = _agg_block(a48)   # Referenz-Baseline B48
    agg_a96: AggBlock = _agg_block(a96)   # Sekundaer-Baseline B96
    brk_48: List[KernelTrade] = [
        t for t in gated if t.arm == "RAW-A" and t.horizont_bars == 48
    ]
    brk_96: List[KernelTrade] = [
        t for t in gated if t.arm == "RAW-A" and t.horizont_bars == 96
    ]
    brk_b: List[KernelTrade] = [t for t in gated if t.arm == "RAW-B"]

    linie: str = "=" * 120
    txt: List[str] = [
        linie,
        "SETUP C - GATE-MODUS (Gated-Portfolio, --mit-regime-gate)",
        "!! KEIN HANDELSPFAD - EINGEFRORENER HISTORISCHER OOS-VERGLEICH !!",
        "   Das Portfolio selektiert 'RAW-Cluster A' (vorlauf <= 1) und setzt",
        "   damit Bruchwissen voraus, das zum Einstiegszeitpunkt nicht existiert.",
        "   Nicht als Ergebnis/Edge praesentieren (Hausregel Live-Kausalitaet).",
        f"Fenster: {fenster} | Symbol: {cfg.symbol} {cfg.timeframe} | "
        f"Segmente: {len(sr.phases)} | F3-Brueche: {len(states)}",
        "Portfolio (§2.16-F.1, OOS-abgenommen): TREND -> RAW-A@96 + RAW-B@96 "
        "(nur Bruchrichtung) | SHAKEOUT/UNKLAR -> strikt RAW-A@48",
        f"Regime: TREND {n_trend} | SHAKEOUT {n_shake} | UNKLAR {n_unklar}",
        linie,
        "",
        "GATED-PORTFOLIO (konsolidiert, Primaer-Sicht):",
    ]
    txt.extend(_block_text("    GATED", agg_g))
    txt.append("")
    txt.append("BREAKDOWN (Arm/Horizont, forensisch):")
    for titel, grp in (
        ("RAW-A@48", brk_48),
        ("RAW-A@96", brk_96),
        ("RAW-B@96", brk_b),
    ):
        if grp:
            txt.extend(_block_text(f"    {titel}", _agg_block(grp)))
        else:
            txt.append(f"    {titel}: (keine Trades)")
    txt.append("")
    txt.append("REFERENZ-BASELINES (No-Harm-Nachweis):")
    txt.extend(_block_text("    B48 (RAW-A@48, alle Phasen)", agg_a48))
    txt.extend(_block_text("    B96 (RAW-A@96, alle Phasen)", agg_a96))
    txt.append("")
    delta_b48: float = agg_g.sum_r_f4 - agg_a48.sum_r_f4
    txt.append(f"PRIMAER-DELTA (gated - B48): {delta_b48:+.2f}R")
    txt.append("HINWEIS (No-Harm-Identitaet): SHAKEOUT/UNKLAR-Phasen tragen")
    txt.append("konstruktionsbedingt Delta = 0.00R (Gate waehlt exakt B48).")
    txt.append(linie)

    cfg.report_dir.mkdir(parents=True, exist_ok=True)
    out_txt: Path = cfg.report_dir / f"setup_c_gate_{fenster}.txt"
    out_txt.write_text("\n".join(txt), encoding="utf-8")
    out_tsv: Path = cfg.report_dir / f"setup_c_gate_trades_{fenster}.tsv"
    out_tsv.write_text(
        _trade_block_gate_tsv(gated, fenster, cfg), encoding="utf-8"
    )
    return "\n".join(txt)


def _bericht_ab_trailing(
    fenster: str,
    cfg: TrendConfig,
    df: pd.DataFrame,
    sr: SegmentResult,
    signale: Sequence[SetupCSignal],
) -> str:
    """A/B-Report: Baseline (N48/N96) vs. EMA-Slope-Trailing (Variante B).

    Eigener Report (``setup_c_ab_trailing_{f}.txt``) - die historischen
    Baseline-Artefakte ``setup_c_*.txt/.tsv`` bleiben byte-identisch
    unberuehrt. Struktur: L1-Pipeline-Anker, Baseline-Bloecke N48/N96,
    Trailing-Block (Crash-Sicherung N=notfall) und A/B-Delta (r_f4).

    Args:
        fenster: AUG | S1 | S2.
        cfg: TrendConfig (ema_trailing.aktiviert = True, Modus B).
        df: OHLCV-DataFrame.
        sr: SegmentResult.
        signale: Alle erfassten Signale.

    Returns:
        Reporttext (wird zusaetzlich nach reports/setup_c/ geschrieben).
    """
    cfg_b: TrendConfig = replace(cfg, ema_trailing=EMASlopeTrailingConfig())
    tc: EMASlopeTrailingConfig = cfg.ema_trailing

    # --- L1: Pipeline-Anker (Populationen; A/B nur noch DIAGNOSE) -----------
    n_f3: int = sum(
        1 for p in sr.phases if p.break_dir is not None and p.brk_idx is not None
    )
    pop_conf: int = len(_population(signale, "CONFIRMED"))
    pop_raw: List[SetupCSignal] = _population(signale, "RAW")
    pop_a: int = sum(
        1
        for s in pop_raw
        if s.vorlauf_bars is not None
        and s.vorlauf_bars <= cfg_b.cluster_a_max_vorlauf
    )
    pop_b: int = sum(1 for s in pop_raw if s.vorlauf_bars is not None) - pop_a
    pop_offen: int = sum(1 for s in pop_raw if s.vorlauf_bars is None)
    pop_retest: int = len(_population(signale, "RETEST"))

    # --- Baseline (Trailing deaktiviert, bitgenau Phase-1-Semantik) ---------
    laeufe_b: Dict[int, Tuple[List[KernelTrade], int]] = {}
    for horizont in cfg_b.zeit_horizonte:
        laeufe_b[horizont] = _kern_lauefe(df, signale, cfg_b, horizont)

    # --- Trailing (Variante B, Crash-Sicherung als Laufzeitgrenze) ---------
    trades_t, n_supp_t = _kern_lauefe(
        df, signale, cfg, tc.notfall_horizont_bars
    )
    if n_supp_t != 0:
        raise RuntimeError(
            f"{fenster}: Trailing-Suppression nicht No-op ({n_supp_t})."
        )
    agg_t: AggBlock = _agg_block(trades_t)

    linie: str = "=" * 120
    txt: List[str] = [
        linie,
        "SETUP C - A/B: BASELINE vs. EMA-SLOPE-TRAILING (Variante B, §5.2)",
        f"Fenster: {fenster} | Symbol: {cfg.symbol} {cfg.timeframe} | "
        f"Segmente: {len(sr.phases)} | F3-Brueche: {n_f3}",
        f"Trailing: EMA({tc.ema_periode})-Slope | Modus {tc.modus} | "
        f"mindest_gewinn_r={tc.mindest_gewinn_r} | Crash-Sicherung "
        f"N={tc.notfall_horizont_bars} | Suppression={cfg.suppression_phasenlokal}",
        linie,
        "",
        "L1 PIPELINE-ANKER (Populationen, SIGNAL & sl_usd>0):",
        f"  F3-Brueche      : {n_f3}",
        f"  CONFIRMED       : {pop_conf}",
        f"  RAW gesamt      : {len(pop_raw)}",
        f"    davon offene Phase (brk_idx leer, live gehandelt): {pop_offen}",
        f"    Diagnose Vorlauf: A(<=1)={pop_a}, B(>1)={pop_b} "
        f"(NICHT Auswahl - der Handelspfad nutzt ALLE RAW)",
        f"  RETEST          : {pop_retest}",
        "",
    ]

    for horizont in cfg_b.zeit_horizonte:
        trades, n_supp = laeufe_b[horizont]
        agg = _agg_block(trades, n_supp)
        txt.append(linie)
        txt.append(
            f"BASELINE RAW (live-kausal, alle Trigger)  |  Horizont N = {horizont}  "
            f"(Close der Bar entry+{horizont})"
        )
        txt.extend(_block_text("    RAW (live)", agg))
        txt.append("")

    txt.append(linie)
    txt.append(
        "EMA-SLOPE-TRAILING (Variante B) | Zeit-Exit entkoppelt (§5.1) | "
        f"Crash-Sicherung N={tc.notfall_horizont_bars}"
    )
    txt.extend(_block_text("    TRAILING", agg_t))
    txt.append("")

    agg48: AggBlock = _agg_block(laeufe_b[48][0])
    agg96: AggBlock = _agg_block(laeufe_b[96][0])
    txt.append(linie)
    txt.append("A/B-DELTA (r_f4, Trailing minus Baseline):")
    txt.append(
        f"  vs N=48: {agg_t.sum_r_f4 - agg48.sum_r_f4:+9.2f}R   "
        f"(Trailing {agg_t.sum_r_f4:+8.2f}R | Baseline {agg48.sum_r_f4:+8.2f}R)"
    )
    txt.append(
        f"  vs N=96: {agg_t.sum_r_f4 - agg96.sum_r_f4:+9.2f}R   "
        f"(Trailing {agg_t.sum_r_f4:+8.2f}R | Baseline {agg96.sum_r_f4:+8.2f}R)"
    )
    txt.append(linie)

    # --- Export (A/B-Report + Trailing-Trades TSV, Baseline bleibt unberuehrt)
    cfg.report_dir.mkdir(parents=True, exist_ok=True)
    out_txt: Path = cfg.report_dir / f"setup_c_ab_trailing_{fenster}.txt"
    out_txt.write_text("\n".join(txt), encoding="utf-8")
    out_tsv: Path = cfg.report_dir / f"setup_c_ab_trailing_trades_{fenster}.tsv"
    out_tsv.write_text(
        _trade_block_tsv(trades_t, fenster, cfg), encoding="utf-8"
    )
    return "\n".join(txt)


def bericht_fenster(
    fenster: str,
    cfg: TrendConfig,
    gate_provider: Optional[IRegimeProvider] = None,
) -> str:
    """Baut den Phase-1-Report fuer ein Fenster (L1 + L2, Text + TSV).

    Args:
        fenster: Alias (AUG | S1 | S2) oder freie Bezeichnung eines
            beliebigen Zeitraums (dann ``cfg.start``/``cfg.ende`` gesetzt).
        cfg: TrendConfig.
        gate_provider: Optionaler Regime-Provider (nur bei
            ``cfg.mit_regime_gate``; Default = RegimeFilterProvider).

    Returns:
        Reporttext (wird zusaetzlich nach reports/setup_c/ geschrieben).
    """
    start, ende = fenster_spanne(fenster, cfg)
    seg_cfg: SegmentConfig = replace(
        cfg.segment,
        db_path=cfg.db_path,
        symbol=cfg.symbol,
        timeframe=cfg.timeframe,
        start=start,
        ende=ende,
    )
    df: pd.DataFrame = load_data(
        seg_cfg.db_path, seg_cfg.start, seg_cfg.ende, seg_cfg.symbol, seg_cfg.timeframe
    )
    sr: SegmentResult = segmentiere_markt(df, seg_cfg)
    signale: List[SetupCSignal] = _erfasse_signale(sr, cfg)

    # --- Gate-Modus: eigenstaendiger Report; Baseline-Pfad bleibt unberuehrt
    if cfg.mit_regime_gate:
        provider: IRegimeProvider = (
            gate_provider if gate_provider is not None else RegimeFilterProvider()
        )
        states: "List[RegimeState]" = provider.klassifiziere(df, sr)
        return _bericht_gate(fenster, cfg, df, sr, signale, states)

    # --- EMA-Slope-Trailing-Modus (A/B, §5.2/§5.4): eigener Report
    if cfg.ema_trailing.aktiviert:
        if cfg.ema_trailing.modus != "STOP_AUF_EXTREMUM":
            raise SystemExit(
                "EMA-Slope-Trailing: Modus "
                f"{cfg.ema_trailing.modus} (Variante A/SOFORT_EXIT) ist "
                "Backlog-Task §5.4 - nur STOP_AUF_EXTREMUM implementiert."
            )
        if cfg.ema_trailing.ema_periode <= 0:
            raise SystemExit("EMA-Slope-Trailing: ema_periode > 0 erforderlich.")
        if cfg.ema_trailing.notfall_horizont_bars <= 0:
            raise SystemExit(
                "EMA-Slope-Trailing: notfall_horizont_bars > 0 erforderlich."
            )
        return _bericht_ab_trailing(fenster, cfg, df, sr, signale)

    # --- L1: Pipeline-Anker (Populationen; A/B nur noch DIAGNOSE) -----------
    n_f3: int = sum(
        1 for p in sr.phases if p.break_dir is not None and p.brk_idx is not None
    )
    pop_conf: int = len(_population(signale, "CONFIRMED"))
    pop_raw: List[SetupCSignal] = _population(signale, "RAW")
    pop_a: int = sum(
        1
        for s in pop_raw
        if s.vorlauf_bars is not None and s.vorlauf_bars <= cfg.cluster_a_max_vorlauf
    )
    pop_b: int = sum(1 for s in pop_raw if s.vorlauf_bars is not None) - pop_a
    pop_offen: int = sum(1 for s in pop_raw if s.vorlauf_bars is None)
    pop_retest: int = len(_population(signale, "RETEST"))

    # --- L2: live-kausaler RAW-Kern je Horizont ------------------------------
    laeufe: Dict[int, Tuple[List[KernelTrade], int]] = {}
    for horizont in cfg.zeit_horizonte:
        laeufe[horizont] = _kern_lauefe(df, signale, cfg, horizont)

    linie = "=" * 120
    txt: List[str] = [
        linie,
        "SETUP C - PHASE-1-PRODUKTIONSKERN (setup_c_profil.py)",
        f"Fenster: {fenster} | Symbol: {cfg.symbol} {cfg.timeframe} | "
        f"Segmente: {len(sr.phases)} | F3-Brueche: {n_f3}",
        "HANDELSPFAD: LIVE-KAUSAL - jeder Volumen-Durchstoss an der kausalen",
        "  Kante (F5-Volumen, Einstieg Open der Folge-Bar). KEIN Vorlauf-Filter;",
        "  offene Phasen werden NICHT zensiert (kein Lookahead).",
        f"Kern: F4 intrabar (Puffer {cfg.stop_puffer}) + Zeit-Exit "
        f"{cfg.zeit_horizonte} + Suppression={cfg.suppression_phasenlokal} "
        f"| r_ref: 0.45%-SL",
        linie,
        "",
        "L1 PIPELINE-ANKER (Populationen, SIGNAL & sl_usd>0):",
        f"  F3-Brueche      : {n_f3}",
        f"  CONFIRMED       : {pop_conf}",
        f"  RAW gesamt      : {len(pop_raw)}",
        f"    davon offene Phase (brk_idx leer, live gehandelt): {pop_offen}",
        f"    Diagnose Vorlauf: A(<=1)={pop_a}, B(>1)={pop_b} "
        f"(NICHT Auswahl - der Handelspfad nutzt ALLE RAW)",
        f"  RETEST          : {pop_retest}",
        "",
    ]

    for horizont in cfg.zeit_horizonte:
        trades, n_supp = laeufe[horizont]
        agg = _agg_block(trades, n_supp)
        txt.append(linie)
        txt.append(
            f"L2 RAW (live-kausal, alle Trigger)  |  Horizont N = {horizont}  "
            f"(Close der Bar entry+{horizont})"
        )
        txt.extend(_block_text("    RAW (live)", agg))
        txt.append("")

    # Referenzzeile (Suppression aus): reine Schutzschicht-Diagnose
    if cfg.suppression_phasenlokal:
        cfg_ref: TrendConfig = replace(cfg, suppression_phasenlokal=False)
        txt.append(linie)
        txt.append("L2-REFERENZ (suppression_phasenlokal=False - Schutzschicht aus):")
        for horizont in cfg_ref.zeit_horizonte:
            trades_ref, n_supp_ref = _kern_lauefe(df, signale, cfg_ref, horizont)
            agg_ref = _agg_block(trades_ref, n_supp_ref)
            txt.extend(_block_text(f"    N={horizont}", agg_ref))
        txt.append("")

    txt.append(linie)
    txt.append(
        "HISTORISCHER ANKER (§2.14, Stand VOR der Kausalitaets-Bereinigung - "
        "NICHT mehr gueltig):"
    )
    txt.append(
        "  L1 damals: AUG 11/11/10(2/8)/3 | S1 138/138/105(38/67)/59 | "
        "S2 61/61/76(3/73)/18"
    )
    txt.append(
        f"  aktuelles Fenster {fenster}: {n_f3}/{pop_conf}/{len(pop_raw)}"
        f"(offen {pop_offen})/{pop_retest} - der RAW-Bestand ist seit der"
    )
    txt.append(
        "  Bereinigung groesser (offene Phasen zaehlen mit) und daher nicht"
        " vergleichbar."
    )
    txt.append(linie)

    # --- Export (Text + TSV) --------------------------------------------------
    cfg.report_dir.mkdir(parents=True, exist_ok=True)
    out_txt: Path = cfg.report_dir / f"setup_c_{fenster}.txt"
    out_txt.write_text("\n".join(txt), encoding="utf-8")
    alle_trades: List[KernelTrade] = []
    for horizont in cfg.zeit_horizonte:
        alle_trades.extend(laeufe[horizont][0])
    out_tsv: Path = cfg.report_dir / f"setup_c_trades_{fenster}.tsv"
    out_tsv.write_text(_trade_block_tsv(alle_trades, fenster, cfg), encoding="utf-8")
    return "\n".join(txt)


# =============================================================================
# 7) MAIN
# =============================================================================


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI-Einstieg: fuehrt den Phase-1-Report fuer Fenster aus.

    Optionen:
        --fenster=AUG|S1|S2|ALLE   (Default AUG)
        --start=YYYY-MM-DD         Freier Zeitraum-Start (inklusive);
                                   nur gemeinsam mit --ende.
        --ende=YYYY-MM-DD          Freies Zeitraum-Ende (exklusiv).
                                   --start/--ende ueberschreiben das
                                   Alias-Fenster (beliebiger Zeitraum).
        --bezeichnung=LABEL        Report-Namensraum des Laufs
                                   (Default bei freiem Zeitraum:
                                   YYYYMMDD_YYYYMMDD).
        --ohne-suppression         L2-Referenzmodus (F3-Suppression aus)
        --mit-regime-gate          Gated-Portfolio (§2.16-F.1)
        --ema-trailing             A/B: Baseline vs. EMA-Slope-Trailing
                                   (Variante B, §5.2/§5.4)
        --ema-trailing-modus=MODUS STOP_AUF_EXTREMUM (Primaer) | SOFORT_EXIT
                                   (Backlog, wird abgelehnt)
        --symbol=SYM               Instrument (Default SILVER). Jedes andere
                                   Symbol erhaelt ein Label-Suffix
                                   (z. B. Brent -> _BRENT), damit die
                                   Silber-Artefakte unberuehrt bleiben.
        --timeframe=TF             Timeframe (Default M15).

    Args:
        argv: Kommandozeilen-Argumente (Default: sys.argv[1:]).

    Returns:
        Exit-Code 0 bei Erfolg.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    fenster: str = "AUG"
    start: Optional[str] = None
    ende: Optional[str] = None
    bezeichnung: Optional[str] = None
    suppression: bool = True
    mit_gate: bool = False
    ema_trailing: bool = False
    ema_modus: str = "STOP_AUF_EXTREMUM"
    symbol: str = "SILVER"
    timeframe: str = "M15"
    for a in args:
        if a.startswith("--fenster="):
            fenster = a.split("=", 1)[1].strip().upper()
        elif a.startswith("--start="):
            start = a.split("=", 1)[1].strip()
        elif a.startswith("--ende="):
            ende = a.split("=", 1)[1].strip()
        elif a.startswith("--bezeichnung="):
            bezeichnung = a.split("=", 1)[1].strip()
        elif a.startswith("--symbol="):
            symbol = a.split("=", 1)[1].strip()
        elif a.startswith("--timeframe="):
            timeframe = a.split("=", 1)[1].strip()
        elif a == "--ohne-suppression":
            suppression = False
        elif a == "--mit-regime-gate":
            mit_gate = True
        elif a == "--ema-trailing":
            ema_trailing = True
        elif a.startswith("--ema-trailing-modus="):
            ema_modus = a.split("=", 1)[1].strip().upper()
    if mit_gate and ema_trailing:
        raise SystemExit(
            "--mit-regime-gate und --ema-trailing schliessen sich aus "
            "(getrennte A/B-Pfade)."
        )
    if not ema_trailing and "--ema-trailing-modus=" in " ".join(args):
        raise SystemExit(
            "--ema-trailing-modus= ist nur zusammen mit --ema-trailing sinnvoll."
        )
    if ema_trailing and ema_modus not in ("STOP_AUF_EXTREMUM", "SOFORT_EXIT"):
        raise SystemExit(
            f"Unbekannter Trailing-Modus: {ema_modus} "
            "(STOP_AUF_EXTREMUM|SOFORT_EXIT)"
        )

    # --- Zeitraum-Aufloesung: freier Zeitraum (--start/--ende) gewinnt -------
    fenster_list: List[str] = loese_zeitraeume(
        fenster, start, ende, bezeichnung, symbol
    )
    cfg = TrendConfig(
        fenster=fenster_list[0],
        start=start,
        ende=ende,
        symbol=symbol,
        timeframe=timeframe,
        suppression_phasenlokal=suppression,
        mit_regime_gate=mit_gate,
        ema_trailing=EMASlopeTrailingConfig(
            aktiviert=ema_trailing, modus=ema_modus  # type: ignore[arg-type]
        ),
    )
    for f in fenster_list:
        text = bericht_fenster(f, cfg)
        print(text)
        if cfg.mit_regime_gate:
            name: str = f"setup_c_gate_{f}.txt"
        elif cfg.ema_trailing.aktiviert:
            name = f"setup_c_ab_trailing_{f}.txt"
        else:
            name = f"setup_c_{f}.txt"
        print(f"\nReport geschrieben: {cfg.report_dir / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
