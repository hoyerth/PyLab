# backtest_lab/phasen_regime_adapter.py
"""Phasen-Regime-Adapter (H2) - read-only Hook-Schicht fuer den SE-Harness.

Der arretierte V3-Straight-Edge-Harness (``test/tmp_kanten_engine_replay.py``,
Baseline SHA256 ``3ba15c723958161f...``) kennt nur die Box (bars < 640) und
bewertet im H2-Bereich weiter mit der Makro-Gegenkante. Dieses Modul liefert
die Regime-Logik fuer den H2-Bereich als reine Wertedomaene - ohne Import der
Engine und ohne Seiteneffekte auf den Harness.

Vier Hooks (Anbindung erfolgt per Namens-Injektion, weil ``_kandidat`` und
``_blockiert_durch_aussenkante`` Closures in ``_se_trades`` sind und nicht per
Monkeypatch ersetzt werden koennen):

* ``hook_1_freigabe_kid``  Freigabe der sweep-bildenden Wand. Wird an ZWEI
  Stellen konsumiert: Hook 1a (Pool-Filter in ``_kandidat``) und Hook 1b
  (``continue`` in ``_blockiert_durch_aussenkante``). Die Auswertung erfolgt
  genau EINMAL pro (Bar, Richtung), damit 1a und 1b nie desynchronisieren.
* ``hook_2_ziel``          TP2-Herkunft als Tri-State (MAKRO | PHASE |
  BLOCKIERT); ersetzt die binaere ``None``-Weiche.
* ``aktive_phase_bei``     Scope-Aufloesung Bar -> Segment, strikt fail-closed
  in den Phasen-Luecken.
* ``hook_3_boden_reclaim`` (v0.20) Autorisiert EINEN zusaetzlichen LONG, wenn
  der Markt den deklarierten Phasenboden durchsticht (``lo[k] < literal``) und
  per ``close`` zurueckholt (``cl[k] > literal``) und die Bodenkante kausal
  ``>= 3`` Touches bestaetigt. Rueckgabe ist ein ``BodenReclaimSpec`` mit
  LITERAL-Anker (Anker-Invariante §69.9) - niemals ``basis_bei(k)``.
  Inert ohne ``boden_deklariert_literal`` (Default ``None``).

Invarianten (nicht verhandelbar):

1. Die Engine-Datei ist bis v0.19 unveraendert geblieben. Ab v0.20 wird sie
   AUSSCHLIESSLICH um den guard-geschuetzten Konsum von ``hook_3_boden_reclaim``
   erweitert (duck-typisierter ``globals().get("_hook")``-Guard; inert ohne
   gebundenen Adapter). Jede weitere Aenderung an der Engine bleibt unzulaessig.
   Der historische SHA ``3ba15c72…5255cb006`` gilt fuer v0.13-v0.19; die
   Revision mit Hook-3-Konsum wird mit EIGENEM SHA neu arretiert.
2. Die Band-Pruefung nutzt IMMER die kausale Basis ``basis_bei(k)``; der
   statische ``provenienz_basis``-Wert ist reine Dokumentation/Audit.
3. Regime-Gueltigkeit wird am SIGNAL-Bar ``k`` geprueft, nicht am Entry-Bar
   ``k + 1`` (Bar 1020 ist der letzte P9-Bar und load-bearing).
4. Freigestellt wird hoechstens EINE Kante: ``min |sweep_px - basis_bei(k)|``
   innerhalb des Touch-Bandes, und nur wenn sie die Grenzkante der aktiven
   Seite ist (Entscheidung #6, Over-Trading-Schutz).
5. Die Freigabe greift ausschliesslich im Docht-Defizit (``dist < 0``) -
   regulaere Q1-Setups (``dist >= 0``) bleiben unangetastet.
6. Luecken zwischen Segmenten sind strikt fail-closed.

Segment-Bestaende (Dreiteilung, Addendum v0.6 Abschnitt 24.1):

* ``AKTIVE_DEFAULT_SEGMENTE`` - operativ freigegeben und ertragsbelegt
  (P9, +5.4212 R). Ausschliesslich diese Liste ist der Default.
* ``P12_RESERVE``             - strukturell geprueft, operativ inert
  (August-Fenster: 0 Trades). Wird vom Test ueber
  ``RESERVE_SEGMENTE`` auditiert, damit die Konstante kein totes Kapital ist.
* ``RESERVE_SEGMENTE``        - Bindungspfad der Reserve fuer
  ``verifiziere_gegen_scan``.

Die Transition-Zone (Bars 640-847) ist bewusst KEIN Segment: sie laeuft
kausal unter MAKRO (5 Park-Trades / +2.4809 R der arretierten Baseline) und
wird nicht angefasst.

Provenienz: ``reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md``
(Addenda v0.3-v0.6, Abschnitte 12-25).
"""
from dataclasses import dataclass, replace
from enum import Enum
import math
from typing import Optional, Sequence, Tuple


class Hook2ZielModus(Enum):
    """Tri-State der TP2-Herkunft (ersetzt die binaere ``None``-Weiche)."""

    MAKRO = "MAKRO"          # bar_idx < start_scope_bar -> Engine unveraendert
    PHASE = "PHASE"          # bar_idx im Segment      -> Segmentziel
    BLOCKIERT = "BLOCKIERT"  # Regime-Vakuum (Luecke)  -> kein Trade


@dataclass(frozen=True, slots=True)
class PhasenKanteInfo:
    """Stammdaten einer Phasen-Grenzkante.

    Args:
        kid: Kanten-ID des Harness (``_SEEdgeH.kid``, int).
        provenienz_basis: Niveau aus der v0.4-Baseline (``U_final`` /
            ``L_final``). NUR Dokumentation/Audit - die Hook-Pruefung nutzt
            ausschliesslich ``basis_bei(k)``.
        touch_bars: Bestaetigte Docht-Bars. Dokumentarisch; von keinem Hook
            konsumiert (die Engine haelt ``_SEEdgeH.wicks``).
        niveau_override: Phasen-lokaler Niveau-Override (v0.14, Anwender-
            Entscheidung 2026-09-10). Ist der Wert gesetzt, gilt fuer diese
            Kante INNERHALB ihres Segments genau dieser Preis statt der
            kausalen Engine-Basis. Ausserhalb des Segments und fuer alle
            anderen Kanten bleibt die Engine unveraendert (die Core-Engine
            wird NICHT gepatcht, Z. 600/`box_end_bar = 640` unberuehrt).
            ``None`` (Default) = keine Wirkung, Bestandsverhalten v0.1.
    """

    kid: int
    provenienz_basis: float
    touch_bars: Tuple[int, ...] = ()
    niveau_override: Optional[float] = None

    def hat_override(self) -> bool:
        """True gdw. fuer diese Kante ein Phasen-Override gesetzt ist."""
        return self.niveau_override is not None


@dataclass(frozen=True, slots=True)
class PhasenSegmentEintrag:
    """Ein v0.4-Phasenfenster als Regime-Einheit (Bar-Indizes = Engine).

    Args:
        phasen_id: Bezeichner der Phase (z. B. ``"P9"``).
        start_bar: Erstes Bar (inklusiv) - identisch zu ``start_scope_bar``.
        end_bar: Letztes Bar (inklusiv). LOAD-BEARING: muss den letzten
            Signal-Bar der Phase enthalten (P9: 1020).
        decke: Obere Grenzkante (SHORT-Wand).
        boden: Untere Grenzkante (LONG-Wand).
        ziel_preis_short: Operatives TP2-Ziel fuer SHORT (Execution-Wert).
        ziel_preis_long: Operatives TP2-Ziel fuer LONG (Spiegelwert).
        touch_band_pct: Band um die kausale Basis in Prozent (Mentor: 0.12).
        provenienz_toleranz_pct: Zulaessige Abweichung der kausalen Basis vom
            Provenienz-Niveau bei der Fail-Loud-Pruefung.
        boden_deklariert_literal: Deklarierter Phasenboden als LITERAL (v0.20,
            Regel G4). ``None`` (Default) = keine Wirkung - die Bestandssegmente
            (P9, P9_DIRECT_69_87, P12_RESERVE) bleiben unveraendert inert.
    """

    phasen_id: str
    start_bar: int
    end_bar: int
    decke: PhasenKanteInfo
    boden: PhasenKanteInfo
    ziel_preis_short: float
    ziel_preis_long: float
    touch_band_pct: float = 0.12
    provenienz_toleranz_pct: float = 1.0
    boden_deklariert_literal: Optional[float] = None

    def deckt_bar_ab(self, bar_idx: int) -> bool:
        """Prueft, ob ``bar_idx`` im Fenster [start_bar, end_bar] liegt.

        Args:
            bar_idx: Signal-Bar-Index der Engine.

        Returns:
            True gdw. beide Grenzen inklusiv abgedeckt sind.
        """
        return self.start_bar <= bar_idx <= self.end_bar


@dataclass(frozen=True, slots=True)
class Hook2Ergebnis:
    """Rueckgabe von ``hook_2_ziel`` (Modus + optionaler Zielpreis).

    Args:
        modus: Herkunft des TP2-Ziels.
        ziel_preis: Zielpreis, nur bei ``modus is PHASE`` gesetzt.
    """

    modus: Hook2ZielModus
    ziel_preis: Optional[float] = None


@dataclass(frozen=True, slots=True)
class BodenReclaimSpec:
    """Autorisierung eines Phasenboden-Reclaims (Hook 3, v0.20).

    Der Adapter autorisiert, die Engine exekutiert. Bewusst nur vier Felder -
    alles weitere (Entry, SL, POC, R) loest die Engine aus ``cfg`` und ``seg``
    auf; es gibt KEINE zweite Wahrheit.

    Args:
        phasen_id: Segment, das die Autorisierung erteilt (z. B. ``"P9"``).
        boden_kid: Kanten-ID des deklarierten Bodens (P9: 77).
        deklarierter_boden_literal: LITERALES Bodenniveau (P9: 68.4000) -
            NICHT ``basis_bei(k)`` (Anker-Invariante §69.9).
        tp2: Segment-Decke in der Kaskade
            ``niveau_override`` -> ``ziel_preis`` -> ``provenienz_basis``
            (P9: 69.8700 statt des Provenienz-Werts 69.9140).
    """

    phasen_id: str
    boden_kid: int
    deklarierter_boden_literal: float
    tp2: float


# --- P9 (v0.1, verifiziert: +5.4212 R) -------------------------------------
P9: PhasenSegmentEintrag = PhasenSegmentEintrag(
    phasen_id="P9",
    start_bar=848,
    end_bar=1020,                       # LOAD-BEARING: Signal-Bar 1020
    decke=PhasenKanteInfo(kid=67, provenienz_basis=69.9140),
    boden=PhasenKanteInfo(kid=77, provenienz_basis=68.3700),
    ziel_preis_short=68.3700,
    ziel_preis_long=69.9140,
)

# Aktive, empirisch verifizierte Standard-Segmente (einziger Default).
# ARRETIERT: v0.1-Baseline (K73-Umweg), H2 = +7.902085 R. NICHT veraendern.
AKTIVE_DEFAULT_SEGMENTE: Tuple[PhasenSegmentEintrag, ...] = (P9,)

# --- v0.14: P9 mit phasen-lokalem K67-Niveau-Override (Anwender-Freigabe) --
# Entscheidung des Anwenders (2026-09-10, Fragen 1-3):
#   * KEINE neue Kanten-ID - K67 bleibt die Decke; nur ihr Niveau wird fuer
#     P9 auf 69.87 ueberschrieben.
#   * FAIL-LOUD: der Override greift strikt nur bei phase == "P9" und wird
#     ueber ``verifiziere_niveau_overrides`` erzwungen.
#   * MITARRETIERT: das vollstaendige Quartett (903, 980, 981, 1020) gehoert
#     ins Verifikationsprotokoll - kein Cherry-Picking.
# H2-Benchmark v0.14 = +22.285802 R (Referenz v0.1 = +7.902085 R, Frage 4).
K67_OVERRIDE_69_87: float = 69.87
P9_DIRECT_69_87: PhasenSegmentEintrag = PhasenSegmentEintrag(
    phasen_id="P9",
    start_bar=848,
    end_bar=1020,                       # LOAD-BEARING: Signal-Bar 1020
    decke=PhasenKanteInfo(kid=67, provenienz_basis=69.9140,
                          niveau_override=K67_OVERRIDE_69_87),
    boden=PhasenKanteInfo(kid=77, provenienz_basis=68.3700),
    ziel_preis_short=68.3700,
    ziel_preis_long=69.9140,
)

# Selektionsliste der v0.14-Variante (explizit, NICHT Default).
AKTIVE_SEGMENTE_V014: Tuple[PhasenSegmentEintrag, ...] = (P9_DIRECT_69_87,)

# Benchmark-Register (Frage 4: beide Werte ausweisen, keiner verdraengt den
# anderen). Werte read-only aus der Engine reproduziert.
BASELINE_V01_H2_R: float = 7.902085          # Adapter v0.1 (K73-Umweg)
BENCHMARK_V014_H2_R: float = 22.285802       # v0.14 Phasen-Override
BENCHMARK_V014_GESAMT_R: float = 61.250064   # v0.14 gesamt (17 Trades)
BENCHMARK_V014_DELTA_R: float = 14.383717    # Zuwachs gegenueber v0.1
QUARTETT_V014_BARS: Tuple[int, ...] = (903, 980, 981, 1020)

# --- P12 (Reserve: strukturell geprueft, operativ inert) -------------------
# August-Fenster: 0 Trades. Freigabe der Decke K73 promoviert die Innenlinie
# K76, die M6-Aussenwand K67 (69.9458, +0.63 %) sperrt; Bar 1259 LONG
# scheitert an Q29. Entscheidung #6 verweigert die K67-Freigabe in P12.
# Ziel 67.6355 = v0.4 L_final (Provenienz-Norm, empirisch noch unbelegt).
P12_RESERVE: PhasenSegmentEintrag = PhasenSegmentEintrag(
    phasen_id="P12",
    start_bar=1171,
    end_bar=1272,
    decke=PhasenKanteInfo(kid=73, provenienz_basis=69.5550),
    boden=PhasenKanteInfo(kid=82, provenienz_basis=67.6355),
    ziel_preis_short=67.6355,
    ziel_preis_long=69.5550,
)

# Bindungsliste der Reserve - ausschliesslich fuer die Fail-Loud-Auditierung
# in Tests; NICHT Teil der aktiven Ausfuehrung.
RESERVE_SEGMENTE: Tuple[PhasenSegmentEintrag, ...] = (P12_RESERVE,)


@dataclass(frozen=True, slots=True)
class PhasenRegimeAdapter:
    """Read-only Regime-Logik fuer den H2-Bereich.

    Args:
        start_scope_bar: Erstes Bar, ab dem das Regime greift (Mentor: 848).
        segmente: Chronologische Segmentliste. Default =
            ``AKTIVE_DEFAULT_SEGMENTE`` (nur P9); die Reserve wird bewusst
            nicht automatisch aktiviert.
    """

    start_scope_bar: int = 848
    segmente: Tuple[PhasenSegmentEintrag, ...] = AKTIVE_DEFAULT_SEGMENTE

    def aktive_phase_bei(self, bar_idx: int) -> Optional[PhasenSegmentEintrag]:
        """Loest ein Bar auf das aktive Segment auf (strikt fail-closed).

        Args:
            bar_idx: Signal-Bar-Index der Engine.

        Returns:
            Aktives Segment oder None unterhalb des Scopes und in Luecken.
        """
        if bar_idx < self.start_scope_bar:
            return None
        for seg in self.segmente:
            if seg.deckt_bar_ab(bar_idx):
                return seg
        return None

    def niveau_override_bei(self, bar_idx: int, kid: int) -> Optional[float]:
        """Phasen-lokaler Niveau-Override fuer die Kante ``kid`` bei Bar ``k``.

        Strikt phasengebunden (Frage 1/2): Der Override wird **nur** geliefert,
        wenn ``bar_idx`` im Fenster des eigenen Segments liegt UND ``kid`` die
        Decke/Boden-Kante dieses Segments ist. Ausserhalb - sowie fuer alle
        Kanten ohne ``niveau_override`` - gilt die unveraenderte Engine-Basis.

        Args:
            bar_idx: Signal-Bar ``k`` der Engine.
            kid: Kanten-ID des Harness.

        Returns:
            Override-Preis als float oder None (kein Override / falsche Phase).
        """
        seg = self.aktive_phase_bei(bar_idx)
        if seg is None:
            return None
        for kante in (seg.decke, seg.boden):
            if kante.kid == int(kid) and kante.hat_override():
                return float(kante.niveau_override)  # type: ignore[arg-type]
        return None

    def verifiziere_niveau_overrides(self) -> None:
        """Fail-Loud-Pruefung aller Phasen-Niveau-Overrides (Frage 2).

        Erzwingt: Override gesetzt ⇒ endlich, positiv und innerhalb der
        Provenienz-Toleranz des Segments. Ein Override ohne Phasenbindung oder
        mit unplausiblem Niveau wird hart abgelehnt.

        Raises:
            ValueError: Override nicht endlich/positiv, Kante nicht Teil des
                Segments oder Abweichung vom Provenienz-Niveau zu gross.
        """
        for seg in self.segmente:
            for kante in (seg.decke, seg.boden):
                if not kante.hat_override():
                    continue
                ov = float(kante.niveau_override)  # type: ignore[arg-type]
                if not math.isfinite(ov) or ov <= 0.0:
                    raise ValueError(
                        f"Niveau-Override K{kante.kid} ({seg.phasen_id}): "
                        f"{ov} ist nicht endlich/positiv.")
                if kante.provenienz_basis <= 0.0:
                    raise ValueError(
                        f"Niveau-Override K{kante.kid} ({seg.phasen_id}): "
                        f"provenienz_basis muss > 0 sein.")
                abw = (abs(ov - kante.provenienz_basis)
                       / kante.provenienz_basis * 100.0)
                if abw > seg.provenienz_toleranz_pct:
                    raise ValueError(
                        f"Niveau-Override K{kante.kid} ({seg.phasen_id}): "
                        f"{ov:.4f} weicht {abw:.4f} % vom Provenienz-Niveau "
                        f"{kante.provenienz_basis:.4f} ab "
                        f"(Toleranz {seg.provenienz_toleranz_pct:.2f} %).")
                if seg.start_bar > seg.end_bar:
                    raise ValueError(
                        f"Niveau-Override K{kante.kid} ({seg.phasen_id}): "
                        f"Segmentfenster ist leer.")

    def verifiziere_boden_literale(self) -> None:
        """Fail-Loud-Pruefung aller deklarierten Phasenboden-Literale (v0.20).

        Analog zu :meth:`verifiziere_niveau_overrides`. Erzwingt: Literal
        gesetzt ⇒ endlich, positiv, STRIKT unter dem Provenienz-Niveau der
        Segmentdecke und das Segmentfenster nicht leer. Die Plausibilisierung
        erfolgt NICHT ueber ``basis_bei`` - der Nachweis "Literal stammt nie
        aus ``basis_bei``" ist strukturell (Code-Inspektion, §69.9).

        Raises:
            ValueError: Literal nicht endlich/positiv, nicht unter der
                Provenienz-Decke oder Segmentfenster leer.
        """
        for seg in self.segmente:
            lit = seg.boden_deklariert_literal
            if lit is None:
                continue
            lv = float(lit)
            if not math.isfinite(lv) or lv <= 0.0:
                raise ValueError(
                    f"Boden-Literal ({seg.phasen_id}): {lv} ist nicht "
                    f"endlich/positiv.")
            if not (lv < seg.decke.provenienz_basis):
                raise ValueError(
                    f"Boden-Literal ({seg.phasen_id}): {lv:.4f} liegt nicht "
                    f"unter der Provenienz-Decke "
                    f"{seg.decke.provenienz_basis:.4f}.")
            if seg.start_bar > seg.end_bar:
                raise ValueError(
                    f"Boden-Literal ({seg.phasen_id}): Segmentfenster ist "
                    f"leer.")

    def angewandte_basis(self, bar_idx: int, kid: int,
                         basis_engine: float) -> float:
        """Wirksame Basis einer Kante: Override (phasen-lokal) sonst Engine.

        Reine Wertedomaene ohne Engine-Import - fuer die Injektionsschicht
        gedacht, damit die Core-Engine unveraendert bleibt.

        Args:
            bar_idx: Signal-Bar ``k``.
            kid: Kanten-ID.
            basis_engine: ``basis_bei(k)`` der Engine.

        Returns:
            Override-Preis, falls fuer (Phase, kid) gesetzt, sonst
            ``basis_engine`` unveraendert.
        """
        ov = self.niveau_override_bei(bar_idx, kid)
        return float(ov) if ov is not None else float(basis_engine)

    def verifiziere_gegen_scan(
        self, kanten: Sequence[Tuple[int, str, float]]
    ) -> None:
        """Fail-Loud-Pruefung aller Segmentkanten gegen den Scan-Katalog.

        Args:
            kanten: Sequenz ``(kid, seite, basis_bei_ref_bar)`` aus
                ``scan["edges"] + scan["seeds"]``. Bewusst als flache Tupel
                (keine Engine-Typen) - der Adapter bleibt Engine-frei.

        Raises:
            ValueError: Kante fehlt, Seite falsch oder die kausale Basis
                weicht zu stark vom Provenienz-Niveau ab.
        """
        by_kid: dict[int, Tuple[str, float]] = {}
        for kid, seite, basis in kanten:
            by_kid[int(kid)] = (str(seite), float(basis))

        for seg in self.segmente:
            for kante, erwartete_seite in ((seg.decke, "OBEN"),
                                           (seg.boden, "UNTEN")):
                if kante.kid not in by_kid:
                    raise ValueError(
                        f"Phasen-Kante K{kante.kid} ({seg.phasen_id}) "
                        f"existiert nicht im Scan-Katalog.")
                seite, basis = by_kid[kante.kid]
                if seite != erwartete_seite:
                    raise ValueError(
                        f"Phasen-Kante K{kante.kid} ({seg.phasen_id}) hat "
                        f"falsche Seite: erwartet {erwartete_seite}, "
                        f"gefunden {seite}.")
                if kante.provenienz_basis <= 0.0:
                    raise ValueError(
                        f"Phasen-Kante K{kante.kid} ({seg.phasen_id}): "
                        f"provenienz_basis muss > 0 sein.")
                abweichung = (abs(basis - kante.provenienz_basis)
                              / kante.provenienz_basis * 100.0)
                if abweichung > seg.provenienz_toleranz_pct:
                    raise ValueError(
                        f"Phasen-Kante K{kante.kid} ({seg.phasen_id}): "
                        f"kausale Basis {basis:.4f} weicht "
                        f"{abweichung:.4f} % vom Provenienz-Niveau "
                        f"{kante.provenienz_basis:.4f} ab "
                        f"(Toleranz {seg.provenienz_toleranz_pct:.2f} %).")

    def hook_1_freigabe_kid(
        self,
        bar_idx: int,
        sweep_px: float,
        richtung: str,
        kanten: Sequence[Tuple[int, float]],
    ) -> Optional[int]:
        """Ermittelt die freizustellende sweep-bildende Wand (Hook 1).

        Das Vorzeichen des Docht-Defizits wird INTERN und einheitlich aus
        ``sweep_px`` und ``basis_k`` abgeleitet (kein externes Flag), damit
        Hook 1a (Pool) und Hook 1b (M6) nicht desynchronisieren koennen.

        Args:
            bar_idx: Signal-Bar ``k`` (nicht der Entry-Bar).
            sweep_px: ``hi[k]`` bei SHORT, ``lo[k]`` bei LONG.
            richtung: ``"SHORT"`` oder ``"LONG"``.
            kanten: Kanonische Kantenmenge ``(kid, basis_bei(k))`` derselben
                Seite - identisch fuer Hook 1a und Hook 1b.

        Returns:
            ``kid`` der einzigen freizustellenden Kante oder None.
        """
        seg = self.aktive_phase_bei(bar_idx)
        if seg is None:
            return None

        seite_kid = seg.decke.kid if richtung == "SHORT" else seg.boden.kid

        gueltige: list[Tuple[float, int]] = []
        for kid, basis_k in kanten:
            if kid != seite_kid:
                continue                    # Entscheidung #6: nur die Wand
            if basis_k <= 0.0:
                continue
            # Interne Vorzeichen-Pruefung: nur Docht-Defizit (dist < 0),
            # regulaere Durchstiche (dist >= 0) bleiben Q1-Setups.
            if richtung == "SHORT" and sweep_px >= basis_k:
                continue
            if richtung == "LONG" and sweep_px <= basis_k:
                continue
            toleranz = basis_k * (seg.touch_band_pct / 100.0)
            diff = abs(sweep_px - basis_k)
            if diff <= toleranz:
                gueltige.append((diff, kid))

        if not gueltige:
            return None
        gueltige.sort(key=lambda x: x[0])   # Tie-Break: min |diff|
        return gueltige[0][1]

    def hook_2_ziel(self, bar_idx: int, richtung: str) -> Hook2Ergebnis:
        """Bestimmt die TP2-Herkunft (Hook 2, Tri-State).

        Args:
            bar_idx: Signal-Bar ``k``.
            richtung: ``"SHORT"`` oder ``"LONG"``.

        Returns:
            ``MAKRO`` (Engine unveraendert), ``PHASE`` (Segmentziel) oder
            ``BLOCKIERT`` (Regime-Vakuum - Aufrufer muss den Trade ablehnen).
        """
        if bar_idx < self.start_scope_bar:
            return Hook2Ergebnis(Hook2ZielModus.MAKRO, None)
        seg = self.aktive_phase_bei(bar_idx)
        if seg is None:
            return Hook2Ergebnis(Hook2ZielModus.BLOCKIERT, None)
        ziel = (seg.ziel_preis_short if richtung == "SHORT"
                else seg.ziel_preis_long)
        return Hook2Ergebnis(Hook2ZielModus.PHASE, ziel)

    def hook_3_boden_reclaim(self, bar_idx: int
                             ) -> Optional[BodenReclaimSpec]:
        """Autorisiert den Phasenboden-Reclaim am Bar ``k`` (Hook 3, v0.20).

        Reine Wertedomaene: Der Adapter prueft AUSSCHLIESSLICH die
        Segment-/Literal-Zustaendigkeit. Die Marktbedingungen
        (``lo[k] < literal < cl[k]``, ``touch_conf(boden, k) >= 3``) und die
        Exekution liegen in der Engine.

        Args:
            bar_idx: Signal-Bar ``k`` der Engine.

        Returns:
            ``BodenReclaimSpec``, falls ``bar_idx`` in einem Segment mit
            deklariertem Boden liegt; sonst ``None`` (inert).
        """
        seg = self.aktive_phase_bei(bar_idx)
        if seg is None:
            return None
        literal = seg.boden_deklariert_literal
        if literal is None:
            return None
        # TP2 ueber den Override: 69.8700 (nicht hook_2_ziel = 69.9140).
        # Latenter Bestand: in P9 wurde nie ein LONG gehandelt, daher blieb
        # die Diskrepanz bis v0.20 unsichtbar.
        tp2 = self.angewandte_basis(bar_idx, seg.decke.kid,
                                    seg.ziel_preis_long)
        return BodenReclaimSpec(
            phasen_id=seg.phasen_id,
            boden_kid=seg.boden.kid,
            deklarierter_boden_literal=float(literal),
            tp2=float(tp2),
        )


DEFAULT_ADAPTER: PhasenRegimeAdapter = PhasenRegimeAdapter()

# v0.14-Variante: P9 mit K67-Niveau-Override 69.87 (phasen-lokal, fail-loud).
# Explizit zu waehlen - der Default (``DEFAULT_ADAPTER``) bleibt die
# arretierte v0.1-Baseline, damit beide Benchmarks nebeneinander bestehen
# (Frage 4). Fail-Loud wird beim Aufbau erzwungen.
ADAPTER_V014: PhasenRegimeAdapter = PhasenRegimeAdapter(
    segmente=AKTIVE_SEGMENTE_V014)
ADAPTER_V014.verifiziere_niveau_overrides()


# --- v0.20: P9_BODEN_RECLAIM (generische Phasenboden-Regel G4) -------------
# Anwender-Freigabe 2026-09-10 (F-1 .. F-6). Deklarierter Phasenboden ist das
# LITERAL 68.4000 (Anker-Invariante §69.9; NICHT basis_bei(1002) = 68.3427).
# Die Decke traegt den v0.14-Override 69.87, damit TP2 = 69.8700 lautet.
# Der Adapter AUTORISIERT nur; die Exekution liegt in der Engine (Route A).
# KEIN Default: P9 / P9_DIRECT_69_87 / DEFAULT_ADAPTER / ADAPTER_V014 bleiben
# unveraendert (Feld = None, null Wirkung - Baseline byte-identisch).
P9_BODEN_LITERAL: float = 68.4000
P9_BODEN_RECLAIM: PhasenSegmentEintrag = PhasenSegmentEintrag(
    phasen_id="P9",
    start_bar=848,
    end_bar=1020,                       # LOAD-BEARING: Signal-Bar 1020
    decke=PhasenKanteInfo(kid=67, provenienz_basis=69.9140,
                          niveau_override=K67_OVERRIDE_69_87),
    boden=PhasenKanteInfo(kid=77, provenienz_basis=68.3700),
    ziel_preis_short=68.3700,
    ziel_preis_long=69.9140,
    boden_deklariert_literal=P9_BODEN_LITERAL,
)

# Selektionsliste der v0.15-G4-Variante (explizit, NICHT Default).
AKTIVE_SEGMENTE_V015: Tuple[PhasenSegmentEintrag, ...] = (P9_BODEN_RECLAIM,)

# Fail-Loud beim Aufbau - analog ``ADAPTER_V014`` (v0.20, F-4).
ADAPTER_V015: PhasenRegimeAdapter = PhasenRegimeAdapter(
    segmente=AKTIVE_SEGMENTE_V015)
ADAPTER_V015.verifiziere_niveau_overrides()
ADAPTER_V015.verifiziere_boden_literale()


# --- v0.24/V019: endogene Segmentbildung (E-34 .. E-34f) -------------------
# Anwender-Ratifizierung 2026-09-11 (v): §S0 (Basis +82.614385 R, kein (a))
# und §S1 (Plateau [41, 114], Referenz 77). V019 loest V018 als
# Betriebsstandard ab.
#
# Die Zielfenster A1 (1033..1173) und A2 (1174..1287) sind ZIELFREI aus EINER
# Regel hergeleitet (E-34 §O1): eine Kante lebt, solange ihr letzter
# BESTAETIGTER Docht b+2 <= k juenger als cfg.wall_live_bars (96) ist; die
# Segmentgrenze ist der Wechsel des Paares (aeusserste lebende Linie je Seite).
#
# Die Fenster werden hier als ARRETIERTE KONSTANTEN gefuehrt, NICHT zur
# Laufzeit neu berechnet: der Adapter bleibt eine reine Wertedomaene ohne
# Engine-Import (Invariante 1, Modul-Docstring).
#
# Herkunft/Limit der Plateaugrenzen: Klippenkarte
# test/_tmp_e34b_klippenkarte_out.txt,
# SHA256 7bfa4ec9e122530080c7ec31c1b123f017e69b8a4ce9d680378d0ea870b58dce.
# Das Plateau ist AUG-SPEZIFISCH; eine Verallgemeinerung ist NICHT belegt.
PLATEAU_MIN_BARS: int = 41          # untere PnL-Klippe (§S1)
PLATEAU_MAX_BARS: int = 114         # obere PnL-Klippe (§S1, 115 = 1 Segment)
PLATEAU_REFERENZ_BARS: int = 77     # Plateaumitte, max. Klippenabstand


@dataclass(frozen=True, slots=True)
class PhasenReifeKonfiguration:
    """SSoT des PnL-invarianten Phasen-Plateaus (endogene Segmentbildung).

    WICHTIG (Semantik, E-34e §S1): gesteuert wird die VERSCHMELZUNGS-
    SCHWELLE, nicht die Segmentlaenge. Ein gueltiges Segment kann aus
    mehreren verschmolzenen Teilstuecken entstehen; die Pruefung
    ``ist_im_plateau`` ist daher eine Aussage ueber den PARAMETER, nicht
    ueber ein Ergebnis-Segment.

    Args:
        verschmelzungs_schwelle: Ersatzwert fuer ``cfg.wall_live_bars`` der
            endogenen Regel. Default = Plateaumitte (max. Klippenabstand).
    """

    verschmelzungs_schwelle: int = PLATEAU_REFERENZ_BARS

    def ist_im_plateau(self) -> bool:
        """True gdw. die gewaehlte Schwelle im invarianten Plateau liegt."""
        return (PLATEAU_MIN_BARS <= self.verschmelzungs_schwelle
                <= PLATEAU_MAX_BARS)


# --- Bindung der V019-Segmente an die Reife-SSoT (E-34n/15 §D4) ------------
# Die Fenster A1 (1033..1173) und A2 (1174..1287) sind aus EINER Regel mit
# der Verschmelzungsschwelle hergeleitet; ihre Namen ``..._AUTO_77`` und die
# Plateaumitte muessen deshalb uebereinstimmen. Ohne diese Bindung waere
# ``PhasenReifeKonfiguration`` ein Deklarations-Datenblatt ohne Laufzeit-
# Wirkung (genau der E-34n/15-Befund). Die Bindung wird beim Modulimport
# erzwungen.
#
# Bewusst ``raise`` statt ``assert``: ``python -O`` entfernt Asserts und
# liesse die Arretierung stumm ausfallen; die Meldung muss unueberhoerbar
# sein. Konvention identisch zu ``verifiziere_niveau_overrides``.
AUTO_VERSCHMELZUNG_SCHWELLE: int = (
    PhasenReifeKonfiguration().verschmelzungs_schwelle)


def _verifiziere_reife_bindung() -> None:
    """Fail-Loud beim Import: V019-Segmente stammen aus dem Plateau.

    Geprueft wird der GEBUNDENE Wert ``AUTO_VERSCHMELZUNG_SCHWELLE`` (der
    Zustand, den die Segmente konsumieren), NICHT der Klassen-Default: ein
    Aufruf ``PhasenReifeKonfiguration().ist_im_plateau()`` waere tautologisch,
    weil der Default stets ``PLATEAU_REFERENZ_BARS`` ist. Der Praedikat-
    Aufruf nutzt weiterhin die SSoT-Methode (keine zweite Plateau-Wahrheit).

    Raises:
        ValueError: Verschmelzungsschwelle ausserhalb ``[41, 114]`` oder
            ungleich der Plateaumitte (Referenz 77).
    """
    if not PhasenReifeKonfiguration(
            AUTO_VERSCHMELZUNG_SCHWELLE).ist_im_plateau():
        raise ValueError(
            "Verschmelzungsschwelle ausserhalb des Plateaus "
            f"[{PLATEAU_MIN_BARS}, {PLATEAU_MAX_BARS}] "
            f"(ist {AUTO_VERSCHMELZUNG_SCHWELLE}).")
    if AUTO_VERSCHMELZUNG_SCHWELLE != PLATEAU_REFERENZ_BARS:
        raise ValueError(
            "Konfigurations-Mismatch zur Plateaumitte: "
            f"PhasenReifeKonfiguration={AUTO_VERSCHMELZUNG_SCHWELLE}, "
            f"PLATEAU_REFERENZ_BARS={PLATEAU_REFERENZ_BARS}.")


_verifiziere_reife_bindung()


# --- v0.24/V019: Zielzone A1/A2 (endogen, MIN77) ---------------------------
# P9 wird NICHT neu deklariert, sondern aus ``P9_BODEN_RECLAIM`` uebernommen
# (E-34f §T1): eine Neudeklaration mit vertauschten Rollen (K77 als Decke)
# scheitert an ``verifiziere_gegen_scan``; ausserdem gingen der Niveau-Override
# 69.87 und das Boden-Literal 68.40 verloren (Trade @1020 entfaellt).
#
# A1/A2 tragen KEIN ``boden_deklariert_literal`` -> Hook 3 (Regel G4) bleibt
# dort inert; die G4-Regel handelt ausschliesslich im arretierten P9.
#
# Die Schwellenzahl 77 im Namen ist NICHT frei gewaehlt, sondern
# ``AUTO_VERSCHMELZUNG_SCHWELLE`` (= Plateaumitte, oben fail-loud gebunden).
# Der machineelle Nachweis ``zusammenfassen(roh, 77) == A1/A2`` folgt als
# separater Prueflauf (E-34n/15 §D4, Teilschritt 1b.2).

# A1 (1033..1173): Decke K67 (69.8990), Boden K82 (67.5350).
A1_AUTO_77: PhasenSegmentEintrag = PhasenSegmentEintrag(
    phasen_id="A1_AUTO_77",
    start_bar=1033,
    end_bar=1173,
    decke=PhasenKanteInfo(kid=67, provenienz_basis=69.8990),
    boden=PhasenKanteInfo(kid=82, provenienz_basis=67.5350),
    ziel_preis_short=67.5350,
    ziel_preis_long=69.8990,
    provenienz_toleranz_pct=1.0,        # == Feld-Default; explizit ausgewiesen
)

# A2 (1174..1287): Decke K73 (69.6380), Boden K82 (67.5530).
#
# K82-DOPPELROLLE (dokumentationspflichtig, E-34f §T8.4 / E-34g): K82 ist
# Boden in A1 UND A2, traegt aber ZWEI Provenienz-Werte (67.5350 / 67.5530,
# Differenz 1.80 Cent). Das ist KEIN Widerspruch, sondern der Preisschritt der
# Kante an der Segmentgrenze: basis_bei(1173) = 67.5350, basis_bei(1174) =
# 67.5530. Beide Provenienz-Werte sind exakt der kausale Basiswert am
# jeweiligen Segmentstart (Abweichung 0.0000 %; Nachweis E-34g
# test/_tmp_e34g_toleranz_out.txt). Fuer die Signalmechanik entscheidet dieser
# Cent ueber ``dist < 0`` vs. ``dist >= 0`` --- die Hook-Pruefung nutzt
# ohnehin ausschliesslich ``basis_bei(k)`` (Invariante 2).
A2_AUTO_77: PhasenSegmentEintrag = PhasenSegmentEintrag(
    phasen_id="A2_AUTO_77",
    start_bar=1174,
    end_bar=1287,
    decke=PhasenKanteInfo(kid=73, provenienz_basis=69.6380),
    boden=PhasenKanteInfo(kid=82, provenienz_basis=67.5530),
    ziel_preis_short=67.5530,
    ziel_preis_long=69.6380,
    provenienz_toleranz_pct=1.0,        # == Feld-Default; explizit ausgewiesen
)

# Selektionsliste der V019-Generation (explizit, NICHT Default).
# Reihenfolge = chronologisch. Die Luecke 1021..1032 bleibt offen ->
# fail-closed (eliminiert den E-33-Verlust-Trade @1028).
AKTIVE_SEGMENTE_V019: Tuple[PhasenSegmentEintrag, ...] = (
    P9_BODEN_RECLAIM, A1_AUTO_77, A2_AUTO_77)

# Fail-Loud beim Aufbau - analog ``ADAPTER_V014`` / ``ADAPTER_V015``.
# ``verifiziere_gegen_scan`` bewusst NICHT hier: sie braucht den Scan-Katalog
# und laeuft im Renderer/Test (engine-freie Wertedomaene, Invariante 1).
ADAPTER_V019: PhasenRegimeAdapter = PhasenRegimeAdapter(
    segmente=AKTIVE_SEGMENTE_V019)
ADAPTER_V019.verifiziere_niveau_overrides()
ADAPTER_V019.verifiziere_boden_literale()


# --- v0.24/V019-KAUSAL: kausale Fensterableitung (E-34n/15 D6/D7) ----------
# Der Batch-Lauf (ADAPTER_V019) etikettiert rueckwirkend: ``zusammenfassen``
# dehnt das Etikett eines Segmentes ueber die gemeinsamen Bars aus. Kausal
# verfuegbar ist ein Etikett jedoch erst ab ``start_bar + Schwelle - 1``
# (Mindestlaenge bestaetigt). MESSUNG (E-34n/15 §D6, Harness
# ``test/_chk_v019_kausal_vergleich.py``): das kostet genau einen Trade --
# Bar 1211 SHORT K76 (+2.539476 R) faellt weg -> 23 / +85.577150 (H2 15 /
# +46.657566), H1 unveraendert 8 / +38.919584.
#
# Die Ableitung ist eine REINE, zustandsfreie Funktion der arretierten
# Segmente -- der Renderer konsumiert nur, er rechnet NICHT (keine zweite
# Wahrheit). Semantik:
#   * Index 0 (P9) ist der ARRETIERTE Anker und bleibt unberuehrt.
#   * Die uebrigen (endogenen) Segmente behalten ihren ``start_bar``; das
#     Etikett des Vorgaengers reicht bis ``wirksam_ab - 1``.
#   * ``wirksam_ab`` des ersten endogenen Segments ist sein eigener Start
#     (kein Vorgaenger-Etikett zu verlaengern).
# Das Fenster wird in ``aktive_phase_bei`` per First-Match aufgeloest; fuer
# 1174..1249 gewinnt damit A1 -- exakt das Harness-Ergebnis.
def kausale_segmentfenster(
    segmente: Sequence[PhasenSegmentEintrag],
    verschmelzungs_schwelle: int,
) -> Tuple[PhasenSegmentEintrag, ...]:
    """Leitet die kausalen Segmentfenster aus den Batch-Fenstern ab.

    Args:
        segmente: Chronologische Batch-Segmente; Index 0 = arretierter Anker
            (P9), alle weiteren = endogen.
        verschmelzungs_schwelle: Bestaetigungslaenge in Bars (Plateaumitte,
            ``AUTO_VERSCHMELZUNG_SCHWELLE``).

    Returns:
        Segmenttupel mit unveraendertem Anker und verlaengerten endogenen
        Fenstern (``end_bar`` des Vorgaengers = ``wirksam_ab`` des
        Nachfolgers - 1).

    Raises:
        ValueError: Schwelle < 1 oder leerer Segmentverbund.
    """
    if verschmelzungs_schwelle < 1:
        raise ValueError(
            f"Verschmelzungsschwelle muss >= 1 sein "
            f"(ist {verschmelzungs_schwelle}).")
    if not segmente:
        raise ValueError("kein Segmentverbund uebergeben.")
    if len(segmente) == 1:
        return tuple(segmente)

    endogen = list(segmente[1:])
    wirksam_ab = [
        s.start_bar if i == 0 else s.start_bar + verschmelzungs_schwelle - 1
        for i, s in enumerate(endogen)
    ]
    neu: list[PhasenSegmentEintrag] = []
    for i, s in enumerate(endogen):
        if i == len(endogen) - 1:
            ende = s.end_bar
        else:
            ende = max(s.end_bar, wirksam_ab[i + 1] - 1)
        if ende < s.start_bar:
            raise ValueError(
                f"Kausales Fenster {s.phasen_id} waere leer "
                f"({s.start_bar}..{ende}).")
        neu.append(replace(s, end_bar=int(ende)))
    return (segmente[0], *neu)


# Kausalitaets-Variante (Stufe 2a): gleiche Kanten, gleiche Sollwerte,
# ausschliesslich verlaengerte Fenster. Explizit, NICHT Default.
ADAPTER_V019_KAUSAL: PhasenRegimeAdapter = PhasenRegimeAdapter(
    segmente=kausale_segmentfenster(AKTIVE_SEGMENTE_V019,
                                    AUTO_VERSCHMELZUNG_SCHWELLE))
ADAPTER_V019_KAUSAL.verifiziere_niveau_overrides()
ADAPTER_V019_KAUSAL.verifiziere_boden_literale()


# --- v0.25: Typisierter 4-Zustands-Marktregime-Datenvertrag (H20.27) ---------
# Reine Wertedomaene ohne Import der Replay-Engine. Implementiert die arretierte
# Zustandsmatrix H20.26/H20.27 (Z0..Z3) zur Makro-Regime-Filterung.
# APPEND-ONLY: die Zeilen 1-816 dieser Datei bleiben unveraendert.
from typing import Literal  # noqa: E402  (Bestandsimporte Z. 65-68 ohne Literal)

KantenSeiteLiteral = Literal["OBEN", "UNTEN"]


class MarktRegimeZustand(Enum):
    """Zustaende des 4-Zustands-Marktregime-Automaten (SSoT H20.26/H20.27)."""

    Z0_WARMUP = "Z0_WARMUP"
    Z1_PROVISIONAL = "Z1_PROVISIONAL"
    Z1_MATURE = "Z1_MATURE"
    Z2_BEDROHT = "Z2_BEDROHT"
    Z3_TRANSITION = "Z3_TRANSITION"

    @property
    def ist_freigabekandidat(self) -> bool:
        """Notwendige (nicht hinreichende) Vorbedingung fuer Neugeschaeft.

        Massgeblich fuer die Trade-Autorisierung ist strikt das Feld
        ``RegimeZustandSnapshot.handel_freigegeben``; ein Z2_BEDROHT aus
        Z1_PROVISIONAL bleibt Fail-Closed (H20.26 Zeile 4 vs. Zeile 7).
        """
        return self in (MarktRegimeZustand.Z1_MATURE,
                        MarktRegimeZustand.Z2_BEDROHT)


class TransitionReason(Enum):
    """Spezifische Ursache fuer den Uebergang nach Z3_TRANSITION."""

    KEIN_GRUND = "KEIN_GRUND"
    BREAKOUT_OBEN = "BREAKOUT_OBEN"
    BREAKOUT_UNTEN = "BREAKOUT_UNTEN"
    BOTH_SIDES = "BOTH_SIDES"                  # Vorrang: schliesst OBEN/UNTEN aus
    OUTER_PIVOT_EXPANSION = "OUTER_PIVOT_EXPANSION"
    DECAY_NO_SUCCESSOR = "DECAY_NO_SUCCESSOR"
    GRACE_ABLAUF = "GRACE_ABLAUF"              # Acceptance nach Kantenbruch


class RegimeEvent(Enum):
    """Kausale Marktereignisse am Bar k."""

    INITIALIZE = "INITIALIZE"
    PAAR_GEBILDET = "PAAR_GEBILDET"
    REIFE_ERREICHT = "REIFE_ERREICHT"
    DURCHSTICH_OBEN = "DURCHSTICH_OBEN"
    DURCHSTICH_UNTEN = "DURCHSTICH_UNTEN"
    RECLAIM_BESTAETIGT = "RECLAIM_BESTAETIGT"
    BREAKOUT_BESTAETIGT = "BREAKOUT_BESTAETIGT"
    RE_LABEL_ERFOLGT = "RE_LABEL_ERFOLGT"
    DECAY_KOLLAPS = "DECAY_KOLLAPS"
    GRACE_ABLAUF = "GRACE_ABLAUF"
    RUHE = "RUHE"


@dataclass(frozen=True, slots=True)
class RegimePaar:
    """Eingefrorener Zustand des aktiven Grenz-Kantenpaars M(k)."""

    decke_kid: int
    decke_basis: float
    boden_kid: int
    boden_basis: float

    @property
    def korridor_breite_pct(self) -> float:
        """Relative Breite des Korridors bezogen auf den Boden."""
        if self.boden_basis <= 0.0:
            return 0.0
        return (self.decke_basis - self.boden_basis) / self.boden_basis * 100.0


@dataclass(frozen=True, slots=True)
class RegimeKonfiguration:
    """SSoT-Bruecke fuer Schwellen: bindet an Bestandskonstanten ohne Duplikate.

    Drei Schwellen-Klassen (H20.28):
    1. Bindbar gegen Engine-cfg: ``wall_live_bars``, ``touch_conf_handelbar``,
       ``min_wall_alter_bars``.
    2. Bindbar gegen Adapter-SSoT: ``reife_gate_bars`` (Import-Zeit).
    3. Nicht-bindbar / Neue Invarianten: ``struktur_band_pct``,
       ``touch_conf_existenz``, ``breakout_move_pct`` -- letzteres SEMANTISCH
       GETRENNT von ``max_sweep_ueberdehnung_pct`` (Obergrenze Sweep; H20.22 K2,
       H20.28 Klasse 3). Kein Bindungs-Parameter, kein Kopplungs-Assert.
    """

    struktur_band_pct: float = 0.50
    breakout_move_pct: float = 0.60
    reife_gate_bars: int = PLATEAU_REFERENZ_BARS     # SSoT Z. 610
    wall_live_bars: int = 96                          # Engine-cfg Invariante
    min_wall_alter_bars: int = 24                     # Engine-cfg Invariante (Z1)
    touch_conf_existenz: int = 2                      # Literal im Replay (Klasse 3)
    touch_conf_handelbar: int = 3                     # == min_touches_handelbar
    # reclaim_grace_bars entfaellt: wird dynamisch aus Engine-cfg konsumiert (E4)

    def verifiziere_gegen_engine(
        self,
        *,
        wall_live_bars: int,
        min_touches_handelbar: int,
        min_wall_alter_bars: int,
    ) -> "ValidierteRegimeKonfiguration":
        """Fail-Loud-Abgleich der bindbaren Schwellen gegen die Engine-cfg.

        Engine-frei: konsumiert flache Primitive (Bestandsmuster wie
        ``verifiziere_gegen_scan``, Z. 404-406), importiert nichts aus dem
        Harness und mutiert weder sich selbst noch die Engine.

        Args:
            wall_live_bars: ``cfg.wall_live_bars`` der Engine (Liveness 96).
            min_touches_handelbar: ``cfg.min_touches_handelbar`` der Engine (3).
            min_wall_alter_bars: ``cfg.min_wall_alter_bars`` der Engine (24).

        Returns:
            Unveraenderliche ``ValidierteRegimeKonfiguration``-Huelle. Der
            Automat akzeptiert als ``cfg`` ausschliesslich diesen Typ.

        Raises:
            ValueError: Abweichung einer bindenden Schwelle.
        """
        if int(wall_live_bars) != self.wall_live_bars:
            raise ValueError(
                f"wall_live_bars Mismatch: Adapter={self.wall_live_bars}, "
                f"Engine={wall_live_bars}")
        if int(min_touches_handelbar) != self.touch_conf_handelbar:
            raise ValueError(
                f"min_touches_handelbar Mismatch: Adapter="
                f"{self.touch_conf_handelbar}, Engine={min_touches_handelbar}")
        if int(min_wall_alter_bars) != self.min_wall_alter_bars:
            raise ValueError(
                f"min_wall_alter_bars Mismatch: Adapter="
                f"{self.min_wall_alter_bars}, Engine={min_wall_alter_bars}")
        return ValidierteRegimeKonfiguration(konfiguration=self)


@dataclass(frozen=True, slots=True)
class ValidierteRegimeKonfiguration:
    """Typ-sichere Huelle einer erfolgreich gegen die Engine geprueften Konfiguration.

    Erzwingt den Aufruf von ``RegimeKonfiguration.verifiziere_gegen_engine``
    typseitig: die Uebergangsfunktion (Option b) konsumiert ausschliesslich
    diesen Typ, nicht die ungepruefte ``RegimeKonfiguration``.
    """

    konfiguration: RegimeKonfiguration

    @property
    def cfg(self) -> RegimeKonfiguration:
        """Kurzform fuer den Lesezugriff im Automaten."""
        return self.konfiguration


@dataclass(frozen=True, slots=True)
class RegimeZustandSnapshot:
    """Unveraenderlicher Zustands-Snapshot des Regime-Automaten am Bar k."""

    bar_idx: int
    zustand: MarktRegimeZustand
    aktives_paar: Optional[RegimePaar]
    k_start: Optional[int]
    letzter_event: RegimeEvent
    touch_conf: int = 0
    handel_freigegeben: bool = False                  # Einzige Gate-Wahrheit
    aus_mature: bool = False                          # Herkunft bei Z2_BEDROHT
    transition_reason: TransitionReason = TransitionReason.KEIN_GRUND
    durchstich_bar: Optional[int] = None
    durchstich_seite: Optional[KantenSeiteLiteral] = None

    def ist_reif(self, cfg: RegimeKonfiguration) -> bool:
        """Prueft den Zeitanteil des Gates (reife_bar = k_start + Gate - 1)."""
        if self.k_start is None:
            return False
        return (self.bar_idx - self.k_start + 1) >= cfg.reife_gate_bars
