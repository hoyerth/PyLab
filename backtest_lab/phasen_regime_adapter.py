# backtest_lab/phasen_regime_adapter.py
"""Phasen-Regime-Adapter (H2) - read-only Hook-Schicht fuer den SE-Harness.

Der arretierte V3-Straight-Edge-Harness (``test/tmp_kanten_engine_replay.py``,
Baseline SHA256 ``3ba15c723958161f...``) kennt nur die Box (bars < 640) und
bewertet im H2-Bereich weiter mit der Makro-Gegenkante. Dieses Modul liefert
die Regime-Logik fuer den H2-Bereich als reine Wertedomaene - ohne Import der
Engine und ohne Seiteneffekte auf den Harness.

Drei Hooks (Anbindung erfolgt per Namens-Injektion in den RAM-Patch, weil
``_kandidat`` und ``_blockiert_durch_aussenkante`` Closures in ``_se_trades``
sind und nicht per Monkeypatch ersetzt werden koennen):

* ``hook_1_freigabe_kid``  Freigabe der sweep-bildenden Wand. Wird an ZWEI
  Stellen konsumiert: Hook 1a (Pool-Filter in ``_kandidat``) und Hook 1b
  (``continue`` in ``_blockiert_durch_aussenkante``). Die Auswertung erfolgt
  genau EINMAL pro (Bar, Richtung), damit 1a und 1b nie desynchronisieren.
* ``hook_2_ziel``          TP2-Herkunft als Tri-State (MAKRO | PHASE |
  BLOCKIERT); ersetzt die binaere ``None``-Weiche.
* ``aktive_phase_bei``     Scope-Aufloesung Bar -> Segment, strikt fail-closed
  in den Phasen-Luecken.

Invarianten (nicht verhandelbar):

1. Die Engine-Datei wird NICHT veraendert.
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
from dataclasses import dataclass
from enum import Enum
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
    """

    kid: int
    provenienz_basis: float
    touch_bars: Tuple[int, ...] = ()


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
AKTIVE_DEFAULT_SEGMENTE: Tuple[PhasenSegmentEintrag, ...] = (P9,)

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


DEFAULT_ADAPTER: PhasenRegimeAdapter = PhasenRegimeAdapter()
