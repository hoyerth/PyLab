# -*- coding: utf-8 -*-
"""V020-Kanten-Engine -- Stufe B: typisierter Motor `_se_trades_v020`.

Neuanlage (additiv). Die arretierte Baseline
``test/tmp_kanten_engine_replay.py`` (SHA 53f28e1b...) bleibt die kanonische
SSoT fuer Scanning und Kanten-Geometrie und wird READ-ONLY geladen
(Lazy-Import mit SHA-Guard). Dieses Modul enthaelt KEINE AST-Patches, KEINE
``globals()``-Bindung und KEINE globalen Fensteranker in der Quartilpruefung
(kein ``hi[:k+1]`` / ``lo[:k+1]``, kein Bar-0-Range fuer Q29, kein ZP-Fenster,
kein ``erweitere_segmentwand_dochte``).

Enthaltene Substitutionen (H20.38, 7 Punkte):
  1. ``e.basis_bei(k)``        -> ``self._basis_wirksam(...)``
  2. ``_existiert(e, k)``      -> ``existiert_nativ(...)`` (A_SB nativ)
  3. M6-Blocker                -> ueberspringt dormante Linien (A_M6L generell)
  4. ``_im_aussenquartil``     -> ``self._quartil_pass`` + endogener Marktrand
  5. Hook-1-Freigabe           -> ``self._hook.hook_1_freigabe_kid(...)``
  6. TP2                       -> ``self._hook.hook_2_ziel(...)`` (Wertvergleich)
  7. G4-Boden-Reclaim          -> ``self._hook.hook_3_boden_reclaim(...)``

Pflicht-Errata (H20.38 Abschnitt 3/4) sind eingearbeitet:
  * K1: Segment-Rand ueber ``kanten_index`` (kid -> Engine-Kante); die
    statische ``provenienz_basis`` des Adapters ist KEINE Rechenbasis.
  * K2: Hook-2-Modus wird ueber ``.value`` verglichen, nicht per ``is``
    (Adapter-Enum ist nicht die V020-Klasse -> stiller Semantikverlust).
  * K3: ``_quartil_pass`` zaehlt nur ``quartil_undefiniert``;
    ``quartil_blockiert`` zaehlt der Motor (Baseline-Konvention, kein
    Doppelzaehlen).

Offen dokumentierte Punkte (bewusst NICHT "mitgeloest"):
  * D1 (Divergenz): ``_gegenkante`` nutzt die wirksame Basis. V019 liess
    diese Stelle roh (``basis_bei``) -- bewusste Vereinheitlichung.
  * R1 (Residualanker): ``poc_start = 0`` bleibt als Balance-Beginn erhalten
    und ist NICHT Teil der 7 Substitutionen (Entscheidung offen).
  * M1 (Mutation): Der Motor mutiert Kantenobjekte des uebergebenen ``scan``
    (``letzter_signal_bar``, ``letzter_sweep_bar``, ``cluster_*``). Der
    Aufrufer MUSS eine ``deepcopy`` uebergeben (Baseline-Konvention).

Verifikation: ausschliesslich statisch (``python -m py_compile``). Dieses
Modul fuehrt beim Import KEINE Laufzeitlogik aus (Lazy-Loader).

Kein R-Pin: V020 ist NICHT byte-identisch zu V0 (die Verallgemeinerung von
A_SB/A_M6L sowie der endogene Rand veraendern das Verhalten). Beobachtend zu
messen gegen V0 (14 / +42.450970 R) und V1_kausal (23 / +85.577150 R).
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import (Any, Dict, List, NamedTuple, Optional, Protocol, Sequence,
                    Tuple, runtime_checkable)

import numpy as np

# --------------------------------------------------------------- Baseline-Bindung
_HIER: Path = Path(__file__).resolve().parent
BASELINE_PFAD: Path = _HIER / "tmp_kanten_engine_replay.py"
BASELINE_SHA_SOLL: str = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")

_BASELINE_CACHE: Dict[str, Any] = {}


def baseline() -> Any:
    """Laedt die arretierte Baseline READ-ONLY (Lazy, SHA-guarded, gecacht).

    Returns:
        Modul-Namespace der Baseline-Engine (``_SEEdgeH``, ``_SESetup``,
        ``_se_scan``, ``_reclaim_stufe``, ``_c_loese_trade``,
        ``_konkurrenz_aktiv``, ``berechne_kausalen_histogramm_poc``,
        ``_lade_fenster``, ``StraightEdgeHarnessKonfiguration``, ...).

    Raises:
        RuntimeError: Baseline fehlt oder ihr SHA-256 weicht ab (Fremdstand).
    """
    if "mod" in _BASELINE_CACHE:
        return _BASELINE_CACHE["mod"]
    if not BASELINE_PFAD.is_file():
        raise RuntimeError(f"Baseline fehlt: {BASELINE_PFAD}")
    sha = hashlib.sha256(BASELINE_PFAD.read_bytes()).hexdigest()
    if sha != BASELINE_SHA_SOLL:
        raise RuntimeError(
            f"Fremde Baseline: {sha[:16]}... (Soll {BASELINE_SHA_SOLL[:16]}...)")
    spec = importlib.util.spec_from_loader("v020_baseline_ro", loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(BASELINE_PFAD)
    sys.modules["v020_baseline_ro"] = mod
    exec(compile(BASELINE_PFAD.read_text(encoding="utf-8"),
                 str(BASELINE_PFAD), "exec"), mod.__dict__)
    _BASELINE_CACHE["mod"] = mod
    return mod


# --------------------------------------------------------------------- Typen
class KantenSeite(str, Enum):
    """Seite einer Kante im Orderbuch-Bild."""
    OBEN = "OBEN"
    UNTEN = "UNTEN"


class SignalRichtung(str, Enum):
    """Signalrichtung (SHORT fadet die Decke, LONG den Boden)."""
    LONG = "LONG"
    SHORT = "SHORT"


class Hook2ZielModus(str, Enum):
    """TP2-Herkunft (Hook 2, Tri-State), Spiegel der Adapter-Werte.

    K2: Der Vergleich erfolgt ausschliesslich ueber ``.value`` -- die
    Adapter-Klasse ist NICHT diese Klasse.
    """
    MAKRO = "MAKRO"
    PHASE = "PHASE"
    BLOCKIERT = "BLOCKIERT"


@dataclass(frozen=True, slots=True)
class V020KantenKonfiguration:
    """Alle Hyperparameter extern; KEINE Bar-Literale, KEINE Fensteranker.

    Args:
        touch_band_pct: Bandbreite, innerhalb derer ein Touch kein Sweep ist.
        min_touches_handelbar: Mindest-Touchbestaetigung innerer Linien.
        max_sweep_ueberdehnung_pct: geschuetzte Baseline-Schranke (0.60 %).
        ueb_schranke_quelle: Herkunft einer segment-lokalen Schranke. Die Zahl
            0.80 aus ZP-4 ist bewusst NICHT als Konstante eingebrannt.
        wall_live_bars: Lebensdauer einer Wand ohne Kontakt.
        min_wall_alter_bars: Mindestalter des level-definierenden Pivots.
        quartil_distanz_pct: zulaessige Distanz zum Range-Extrem (Q29).
        sweep_mindestdurchstich_pct: Mindest-Durchstich jenseits der Basis.
        tp1_anteil_pct: Anteil der ersten Teilposition.
    """
    touch_band_pct: float = 0.12
    min_touches_handelbar: int = 3
    max_sweep_ueberdehnung_pct: float = 0.60
    ueb_schranke_quelle: str = "korridor_endogen"
    wall_live_bars: int = 96
    min_wall_alter_bars: int = 24
    quartil_distanz_pct: float = 25.0
    sweep_mindestdurchstich_pct: float = 0.0
    tp1_anteil_pct: float = 50.0


class KantenReferenz(NamedTuple):
    """Unveraenderliche Kantensicht zum Bar k (strikt kausal).

    Args:
        kid: Kanten-ID.
        seite: OBEN oder UNTEN.
        basis_bei_k: wirksame Basis zum Bar k (Override bereits angewandt).
        erster_pivot_bar: Bar des level-definierenden Pivots.
        letzter_sweep_bar: Bar des letzten tatsaechlichen Durchstichs.
        letzter_touch_bar: Bar des letzten Kontakts (fuer wall_live_bars);
            ``-1``, wenn kein Kontakt <= k.
        touch_n: Touch-Bestaetigungen bis k.
        ist_aktiv: Lifecycle-Zustand; wird NIE mutiert.
        ist_prim_anker: promovierter Primaer-Anker (Basis eingefroren).
    """
    kid: int
    seite: KantenSeite
    basis_bei_k: float
    erster_pivot_bar: int
    letzter_sweep_bar: int
    letzter_touch_bar: int
    touch_n: int
    ist_aktiv: bool
    ist_prim_anker: bool


class Marktrand(NamedTuple):
    """Endogene Randgroesse aus L_s(k), strikt <= k.

    Args:
        decke: oberer Rand (max Basis der lebenden OBEN-Kanten bzw. Segment).
        boden: unterer Rand (min Basis der lebenden UNTEN-Kanten bzw. Segment).
        quelle: "lebende_kanten" oder "segment_fallback".
    """
    decke: float
    boden: float
    quelle: str


class Hook2Ergebnis(NamedTuple):
    """Rueckgabe von Hook 2 (TP2-Herkunft), Spiegel der Adapter-Struktur."""
    modus: Hook2ZielModus
    ziel_preis: Optional[float]


class BodenReclaimSpec(NamedTuple):
    """Autorisation eines Phasenboden-Reclaims (Hook 3, G4)."""
    phasen_id: str
    boden_kid: int
    deklarierter_boden_literal: float
    tp2: float


# ----------------------------------------------------------------- Protocols
@runtime_checkable
class KantenWertedomaene(Protocol):
    """Reine Wertedomaene -- zustandslos, keine Trade-Entscheidung."""

    def angewandte_basis(self, bar_idx: int, kid: int,
                         basis_engine: float) -> float:
        """Wirksame Basis: Override (phasen-lokal) sonst Engine-Basis."""
        raise NotImplementedError

    def niveau_override_bei(self, bar_idx: int, kid: int) -> Optional[float]:
        """Override-Preis fuer (Bar, Kante) oder None."""
        raise NotImplementedError


@runtime_checkable
class KantenRegimeHook(Protocol):
    """Entscheidungs-/Kontextschicht -- ersetzt AST- und globals()-Hooks."""

    def aktive_phase_bei(self, bar_idx: int) -> Optional[Any]:
        """Aktives Segment am Bar oder None."""
        raise NotImplementedError

    def hook_1_freigabe_kid(self, bar_idx: int, sweep_px: float,
                            richtung: SignalRichtung,
                            seiten_kanten: Sequence[Tuple[int, float]]
                            ) -> Optional[int]:
        """Gibt eine Sperr-Kante frei (oder None)."""
        raise NotImplementedError

    def hook_2_ziel(self, bar_idx: int,
                    richtung: SignalRichtung) -> Hook2Ergebnis:
        """TP2-Herkunft (MAKRO / PHASE / BLOCKIERT)."""
        raise NotImplementedError

    def hook_3_boden_reclaim(
            self, bar_idx: int) -> Optional[BodenReclaimSpec]:
        """Autorisiert einen Phasenboden-Reclaim (oder None)."""
        raise NotImplementedError


# ------------------------------------------------------- reine Kernfunktionen
def kantenreferenz_aus(e: Any, k: int,
                       wertedomaene: Optional[KantenWertedomaene] = None
                       ) -> KantenReferenz:
    """Uebersetzt eine Baseline-Kante (``_SEEdgeH``) in eine KantenReferenz.

    Args:
        e: Baseline-Kante mit ``kid``, ``seite``, ``basis_bei``,
            ``erster_pivot_bar``, ``letzter_sweep_bar``, ``wicks``,
            ``ist_aktiv_bei``, ``ist_prim_anker``.
        k: Signal-Bar (strikt kausal).
        wertedomaene: optionale Wertedomaene fuer den Override.

    Returns:
        KantenReferenz mit wirksamer Basis und letztem Touch-Bar <= k.
    """
    basis = float(e.basis_bei(k))
    if wertedomaene is not None:
        basis = float(wertedomaene.angewandte_basis(k, int(e.kid), basis))
    _wick_bars = [int(b) for b, _ in e.wicks if int(b) <= k]
    letzter_touch = max(_wick_bars) if _wick_bars else -1
    return KantenReferenz(
        kid=int(e.kid),
        seite=KantenSeite(str(e.seite)),
        basis_bei_k=basis,
        erster_pivot_bar=int(e.erster_pivot_bar),
        letzter_sweep_bar=int(e.letzter_sweep_bar),
        letzter_touch_bar=letzter_touch,
        touch_n=int(e.touch_conf(k)),
        ist_aktiv=bool(e.ist_aktiv_bei(k)),
        ist_prim_anker=bool(e.ist_prim_anker))


def marktrand_bei(lebende: Sequence[KantenReferenz],
                  segment_rand: Optional[Marktrand] = None
                  ) -> Optional[Marktrand]:
    """Endogener Marktrand -- Fallback-Stufen 1 und 2 (H20.36 Abschnitt 3).

    Stufe 1: lebende Kanten ``L_s(k)`` -> decke = max(basis), boden = min(basis).
             Bei genau einer Kante ist die Spanne degeneriert (decke == boden).
    Stufe 2: ``segment_rand`` (Aufrufer liefert den Segmentrand).
    Stufe 3: KEINE -- rueckgabe ``None``; ``im_aeusseren_quartil`` behandelt
             diesen Fall permissiv und die Engine zaehlt ihn.

    Args:
        lebende: Kanten mit erster_pivot_bar + 2 <= k + 1 und Lifecycle aktiv.
        segment_rand: optionaler Segmentrand als Fallback-Quelle.

    Returns:
        Marktrand aus lebenden Kanten, sonst der Segmentrand, sonst None.
    """
    if lebende:
        basiswerte = [float(r.basis_bei_k) for r in lebende]
        return Marktrand(decke=max(basiswerte), boden=min(basiswerte),
                         quelle="lebende_kanten")
    if segment_rand is not None:
        return Marktrand(decke=float(segment_rand.decke),
                         boden=float(segment_rand.boden),
                         quelle="segment_fallback")
    return None


def im_aeusseren_quartil(preis: float, rand: Optional[Marktrand],
                         richtung: SignalRichtung, quartil_pct: float) -> bool:
    """Ersetzt ``_im_aussenquartil`` -- ohne ``hi[:k+1]`` / ``lo[:k+1]``.

    Mathematisch identische Perzentilpruefung, aber der Rand ist endogen
    (``Marktrand``) statt global ab Bar 0.

    Args:
        preis: Sweep-Extremum bei k (``hi[k]`` fuer SHORT, ``lo[k]`` fuer LONG).
        rand: endogener Marktrand; ``None`` = undefiniert.
        richtung: SHORT prueft Naehe zur Decke, LONG zur Boden.
        quartil_pct: zulaessige Distanz zum Extrem in Prozent der Spanne.

    Returns:
        True, wenn die normierte Distanz <= quartil_pct ist. Bei ``rand is None``
        oder degenerierter Spanne (``decke == boden``) ebenfalls True
        (Permissiv-Modus; die Engine inkrementiert ``quartil_undefiniert``).
    """
    if rand is None:
        return True
    spanne = float(rand.decke) - float(rand.boden)
    if spanne <= 0.0:
        return True
    if richtung == SignalRichtung.SHORT:
        distanz = (float(rand.decke) - float(preis)) / spanne * 100.0
    else:
        distanz = (float(preis) - float(rand.boden)) / spanne * 100.0
    return distanz <= float(quartil_pct)


def existiert_nativ(ref: KantenReferenz, k: int,
                    cfg: V020KantenKonfiguration, preis: float) -> bool:
    """A_SB nativ: ``pivot + 2`` UND (Lifecycle aktiv ODER realer Durchstich).

    Ersetzt das ZP-4-Patch ``A_SB`` ohne Fensteranker: Die Reaktivierung gilt
    generell und ausschliesslich bei einem ECHTEN Durchstich aus realem OHLC
    (``hi``/``lo``) -- keine Scan-Manipulation.

    Precondition (Aufrufer): ``preis`` ist das SEITENRICHTIGE Extrem --
    OBEN (SHORT) -> ``hi[k]``, UNTEN (LONG) -> ``lo[k]``.

    Args:
        ref: Kantensicht zum Bar k.
        k: Signal-Bar.
        cfg: Konfiguration (API-konform; Formel nutzt sie nicht).
        preis: Sweep-Extremum bei k.

    Returns:
        True, wenn die Kante nach Baseline-Semantik existiert.
    """
    if ref.erster_pivot_bar + 2 > k + 1:
        return False
    if ref.ist_aktiv:
        return True
    if ref.seite == KantenSeite.OBEN:
        return float(preis) > float(ref.basis_bei_k)
    return float(preis) < float(ref.basis_bei_k)


def lebt_kausal(ref: KantenReferenz, k: int,
                cfg: V020KantenKonfiguration) -> bool:
    """Wand-Liveness ``wall_live_bars`` -- ausschliesslich aus Touches <= k.

    Args:
        ref: Kantensicht zum Bar k (``letzter_touch_bar`` ist bereits <= k).
        k: Signal-Bar.
        cfg: Konfiguration.

    Returns:
        True, wenn der letzte Kontakt hoechstens ``wall_live_bars`` zurueckliegt.
    """
    if ref.letzter_touch_bar < 0:
        return False
    return ref.letzter_touch_bar >= k - int(cfg.wall_live_bars)


def etabliert_kausal(ref: KantenReferenz, k: int,
                     cfg: V020KantenKonfiguration) -> bool:
    """Q24: Linie ist reif, wenn ihr Pivot mindestens ``min_wall_alter_bars``
    zurueckliegt (kein Fade des ersten Ausbruchsversuchs).

    Args:
        ref: Kantensicht zum Bar k.
        k: Signal-Bar.
        cfg: Konfiguration.

    Returns:
        True, wenn ``k - erster_pivot_bar >= min_wall_alter_bars``.
    """
    return (k - int(ref.erster_pivot_bar)) >= int(cfg.min_wall_alter_bars)


# ---------------------------------------------------------------- Engine (DI)
V3_TP_MINDIST_PCT: float = 1.5      # Baseline-Invariante (Engine-Z. 2681/2689)


class V020KantenEngine:
    """Native Engine -- Dependency Injection statt ``globals()``/AST.

    Args:
        hook: Regime-Entscheidungsschicht; ``None`` = rein native Mechanik.
        wertedomaene: optionale Wertedomaene (Override-Basis).
        cfg: typisierte V020-Konfiguration ohne Fensteranker.
    """

    def __init__(self,
                 hook: Optional[KantenRegimeHook] = None,
                 wertedomaene: Optional[KantenWertedomaene] = None,
                 cfg: V020KantenKonfiguration = V020KantenKonfiguration()
                 ) -> None:
        self._hook = hook
        self._wertedomaene = wertedomaene
        self.cfg = cfg
        self.stats: Dict[str, Any] = {
            "quartil_undefiniert": 0,
            "quartil_blockiert": 0,
            "blocker": 0,
        }

    # --- Wertedomaene --------------------------------------------------------
    def _basis_wirksam(self, kid: int, k: int, basis_engine: float) -> float:
        """Override, falls Wertedomaene gebunden; sonst Engine-Basis.

        Args:
            kid: Kanten-ID.
            k: Signal-Bar.
            basis_engine: ``basis_bei(k)`` der Baseline.

        Returns:
            Wirksame Basis.
        """
        if self._wertedomaene is None:
            return float(basis_engine)
        return float(self._wertedomaene.angewandte_basis(k, kid, basis_engine))

    def _referenzen(self, kanten: Sequence[Any], k: int
                    ) -> Dict[int, KantenReferenz]:
        """Uebersetzt Kanten in kausale Referenzen (Override angewandt).

        Args:
            kanten: Baseline-Kanten (edges oder edges + seeds).
            k: Signal-Bar.

        Returns:
            ``kid -> KantenReferenz``.
        """
        return {int(e.kid): kantenreferenz_aus(e, k, self._wertedomaene)
                for e in kanten}

    # --- endogener Rand ------------------------------------------------------
    def _marktrand(self, referenzen: Sequence[KantenReferenz], k: int,
                   kanten_index: Dict[int, Any]) -> Optional[Marktrand]:
        """Endogener Marktrand (Erratum K1: kid -> Engine-Kante).

        Stufe 1 aus den lebenden Kanten. Stufe 2 aus dem aktiven Segment --
        aufgeloest ueber ``kanten_index`` (die ``PhasenKanteInfo`` des Adapters
        traegt KEIN ``basis_bei``; die statische ``provenienz_basis`` ist
        keine Rechenbasis). Ist eine Segmentkante nicht aufloesbar, gilt der
        Segment-Rand als NICHT bestimmbar (Stufe 3, permissiv + Zaehler).

        Args:
            referenzen: kausale Kantensicht (nur ``scan["edges"]``).
            k: Signal-Bar.
            kanten_index: ``{kid: _SEEdgeH}`` der etablierten Kanten.

        Returns:
            Marktrand oder None (doppelt degenerierter Fall).
        """
        lebende = [r for r in referenzen
                   if (r.erster_pivot_bar + 2 <= k + 1
                       and lebt_kausal(r, k, self.cfg))]
        if lebende:
            return marktrand_bei(lebende, None)
        segment_rand: Optional[Marktrand] = None
        if self._hook is not None:
            _seg = self._hook.aktive_phase_bei(k)
            if _seg is not None:
                _d = getattr(_seg, "decke", None)
                _b = getattr(_seg, "boden", None)
                if _d is not None and _b is not None:
                    _ek_d = kanten_index.get(int(getattr(_d, "kid", -1)))
                    _ek_b = kanten_index.get(int(getattr(_b, "kid", -1)))
                    if _ek_d is not None and _ek_b is not None:
                        segment_rand = Marktrand(
                            decke=self._basis_wirksam(
                                int(_ek_d.kid), k, float(_ek_d.basis_bei(k))),
                            boden=self._basis_wirksam(
                                int(_ek_b.kid), k, float(_ek_b.basis_bei(k))),
                            quelle="segment_fallback")
        return marktrand_bei([], segment_rand)

    def _quartil_pass(self, preis: float, rand: Optional[Marktrand],
                      richtung: SignalRichtung) -> bool:
        """Quartilpruefung (Erratum K3: zaehlt NUR ``quartil_undefiniert``).

        ``quartil_blockiert`` zaehlt der Motor (Baseline-Konvention), damit
        kein Doppelzaehlen entsteht.

        Args:
            preis: Sweep-Extremum bei k.
            rand: endogener Marktrand.
            richtung: Signalsicht.

        Returns:
            True, wenn der Rand undefiniert/degeneriert ist (permissiv) oder
            das Quartil erfuellt ist.
        """
        if rand is None or (rand.decke - rand.boden) <= 0.0:
            self.stats["quartil_undefiniert"] += 1
            return True
        return im_aeusseren_quartil(preis, rand, richtung,
                                    self.cfg.quartil_distanz_pct)

    # --- Motor (Stufe B) -----------------------------------------------------
    def _se_trades_v020(self, scan: Dict[str, Any],
                        cfg: Any = None) -> Tuple[List[Any], Dict[str, Any]]:
        """Regel-Trades an der aeussersten existierenden Kante (V020).

        Faithful-Refactor der Baseline ``_se_trades`` (Z. 2409-2845) mit den
        sieben Substitutionen aus H20.38. Die Engine-Interna (Reclaim-Stufen,
        Trade-Aufloesung, POC, Concurrency) bleiben unveraendert und werden
        read-only aus der Baseline gebunden.

        Args:
            scan: Scan-Dict der Baseline. MUSS eine laufeigene ``deepcopy``
                sein (der Motor mutiert Kantenobjekte).
            cfg: ``StraightEdgeHarnessKonfiguration`` der Baseline (Engine-
                Interna). ``None`` -> Default-Instanz. NICHT ``self.cfg``:
                die V020-Konfiguration traegt nur die V020-Gates.

        Returns:
            ``(setups, stats)`` -- identische Struktur wie ``_se_trades``.
        """
        B = baseline()
        _SESetup = B._SESetup
        _reclaim_stufe = B._reclaim_stufe
        _c_loese_trade = B._c_loese_trade
        _konkurrenz_aktiv = B._konkurrenz_aktiv
        _poc = B.berechne_kausalen_histogramm_poc
        if cfg is None:
            cfg = B.StraightEdgeHarnessKonfiguration()

        d = scan["d"]
        hi = d["high"].to_numpy(dtype=float)
        lo = d["low"].to_numpy(dtype=float)
        cl = d["close"].to_numpy(dtype=float)
        op = d["open"].to_numpy(dtype=float)
        edges: List[Any] = list(scan["edges"])
        seeds: List[Any] = list(scan["seeds"])
        alle: List[Any] = edges + seeds
        kanten_index: Dict[int, Any] = {int(e.kid): e for e in edges}
        seite_edges: Dict[str, List[Any]] = {
            "OBEN": [e for e in alle if e.seite == "OBEN"],
            "UNTEN": [e for e in alle if e.seite == "UNTEN"]}
        setups: List[Any] = []
        box_end = int(scan["box_end_bar"])
        stats: Dict[str, Any] = self.stats
        stats.update({
            "v_s": 0, "kein_gegner": 0, "f3": 0, "kein_raum": 0,
            "zyklus_blockiert": 0, "quartil_blockiert": 0, "blocker": 0,
            "promotionen": 0, "stacking_blockiert": 0, "frisch_blockiert": 0,
            "concurrency_blockiert": 0, "quartil_undefiniert": 0})
        poc_start = 0                       # R1: Balance-Beginn (Residualanker)
        letzter_trade: Dict[int, Any] = {}
        getradete_entry_bars: set = set()
        stacking_liste: List[str] = []
        zyklus_liste: List[str] = []
        quartil_liste: List[str] = []
        blocker_liste: List[str] = []

        # --- Substitution 1: wirksame Basis ---------------------------------
        def _basis(e: Any, kk: int) -> float:
            return self._basis_wirksam(int(e.kid), kk, float(e.basis_bei(kk)))

        # --- Substitution 2: A_SB nativ (realer Durchstich) -----------------
        def _existiert(e: Any, kk: int, refs: Dict[int, KantenReferenz],
                       preis: float) -> bool:
            _r = refs.get(int(e.kid))
            if _r is None:
                return False
            return existiert_nativ(_r, kk, self.cfg, preis)

        def _lebt_schlaf(e: Any, kk: int) -> bool:
            """Liveness aus realen Wicks (Baseline-Semantik, unveraendert)."""
            bars = [b for b, _ in e.wicks if b <= kk]
            if not bars:
                return False
            return max(bars) >= kk - cfg.wall_live_bars

        def _etabliert(e: Any, kk: int) -> bool:
            return kk - e.erster_pivot_bar >= cfg.min_wall_alter_bars

        # --- Substitution 3: A_M6L generell (dormante sperren nicht) --------
        def _blockiert_durch_aussenkante(richtung: str, kk: int, kd: Any,
                                         sweep_px: float,
                                         refs: Dict[int, KantenReferenz],
                                         freigabe_kid: Optional[int]
                                         ) -> Optional[Any]:
            seite = "OBEN" if richtung == "SHORT" else "UNTEN"
            basis_k = _basis(kd, kk)
            aussen: Optional[Any] = None
            for e in seite_edges[seite]:
                if e is kd or not _existiert(e, kk, refs, sweep_px):
                    continue
                if freigabe_kid is not None and int(e.kid) == freigabe_kid:
                    continue
                _r = refs.get(int(e.kid))
                if _r is not None and not lebt_kausal(_r, kk, self.cfg):
                    continue                # A_M6L: dormante Linie sperrt nicht
                b = _basis(e, kk)
                if seite == "OBEN":
                    if b <= sweep_px:
                        continue
                    if aussen is None or b > _basis(aussen, kk):
                        aussen = e
                else:
                    if b >= sweep_px:
                        continue
                    if aussen is None or b < _basis(aussen, kk):
                        aussen = e
            if aussen is None:
                return None
            b = _basis(aussen, kk)
            dist = ((b - basis_k) if seite == "OBEN"
                    else (basis_k - b)) / basis_k * 100.0
            return aussen if 0.0 < dist <= cfg.max_seed_distanz_pct else None

        # --- Kandidatenkaskade (Substitutionen 2 und 5) ---------------------
        def _kandidat(richtung: str, kk: int, sweep_px: float,
                      refs: Dict[int, KantenReferenz],
                      freigabe_kid: Optional[int]) -> Optional[Any]:
            seite = "OBEN" if richtung == "SHORT" else "UNTEN"

            def _dist(e: Any) -> float:
                basis = _basis(e, kk)
                if richtung == "SHORT":
                    return (sweep_px - basis) / basis * 100.0
                return (basis - sweep_px) / basis * 100.0

            pool: List[Any] = []
            for e in seite_edges[seite]:
                if not _existiert(e, kk, refs, sweep_px):
                    continue
                if not ((e.ist_prim_anker and kk >= e.promoviert_ab_bar)
                        or e.touch_conf(kk) >= 2):
                    continue
                if not _etabliert(e, kk):
                    if _dist(e) > cfg.touch_band_pct:
                        stats["frisch_blockiert"] += 1
                    continue
                pool.append(e)
            for e in seite_edges[seite]:
                if (e in pool or e.ist_prim_anker
                        or not _existiert(e, kk, refs, sweep_px)):
                    continue
                if e.touch_conf(kk) >= 2 or not _etabliert(e, kk):
                    continue
                dd = _dist(e)
                if (cfg.sweep_mindestdurchstich_pct
                        < dd <= cfg.max_sweep_ueberdehnung_pct):
                    pool.append(e)
            if not pool:
                return None
            pool.sort(key=lambda e: _basis(e, kk), reverse=(seite == "OBEN"))
            if freigabe_kid is not None:            # Substitution 5
                pool = [e for e in pool if int(e.kid) != freigabe_kid]
            for pos, e in enumerate(pool):
                dist = _dist(e)
                if dist < 0.0:
                    if _lebt_schlaf(e, kk):
                        return None
                    continue
                if dist > cfg.max_sweep_ueberdehnung_pct:
                    return None
                if dist <= cfg.sweep_mindestdurchstich_pct:
                    continue
                if pos == 0:
                    return e
                if e.touch_conf(kk) < cfg.min_touches_handelbar:
                    continue
                return e
            return None

        def _gegenkante(richtung: str, kk: int) -> Optional[Any]:
            """Aeusserste Gegenkante (>= 2 Touches, SCHLAFEND zulaessig)."""
            gegenseite = "UNTEN" if richtung == "SHORT" else "OBEN"
            pool = [e for e in seite_edges[gegenseite]
                    if e.erster_pivot_bar + 2 <= kk + 1
                    and ((e.ist_prim_anker and kk >= e.promoviert_ab_bar)
                         or e.touch_conf(kk) >= 2)]
            if not pool:
                return None
            if gegenseite == "OBEN":
                return max(pool, key=lambda e: _basis(e, kk))
            return min(pool, key=lambda e: _basis(e, kk))

        # ------------------------------------------------------------- Loop
        for k in range(2, box_end - 3):
            refs = self._referenzen(alle, k)
            rand_k = self._marktrand(
                [refs[int(e.kid)] for e in edges], k, kanten_index)
            for richtung in ("SHORT", "LONG"):
                sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])
                _seite = "OBEN" if richtung == "SHORT" else "UNTEN"
                freigabe_kid: Optional[int] = None
                if self._hook is not None:          # Substitution 5
                    _sk = [(int(e.kid), _basis(e, k))
                           for e in seite_edges[_seite]
                           if _existiert(e, k, refs, sweep_px)]
                    freigabe_kid = self._hook.hook_1_freigabe_kid(
                        k, sweep_px, richtung, _sk)
                kd = _kandidat(richtung, k, sweep_px, refs, freigabe_kid)
                if kd is None:
                    continue
                blk = _blockiert_durch_aussenkante(
                    richtung, k, kd, sweep_px, refs, freigabe_kid)
                if blk is not None:
                    stats["blocker"] += 1
                    blocker_liste.append(
                        f"bar {k:4d} {richtung:5s} K{kd.kid:3d} "
                        f"basis={_basis(kd, k):.3f} sweep={sweep_px:.3f} "
                        f"-> BLOCKER-SPERRE (unerreichte Aussenwand K{blk.kid} "
                        f"{_basis(blk, k):.3f})")
                    continue
                # --- Substitution 4: endogener Marktrand -------------------
                if not self._quartil_pass(sweep_px, rand_k, richtung):
                    stats["quartil_blockiert"] += 1
                    quartil_liste.append(
                        f"bar {k:4d} {richtung:5s} K{kd.kid:3d} "
                        f"basis={_basis(kd, k):.3f} sweep={sweep_px:.3f} "
                        f"-> QUARTIL-SPERRE (ausserhalb des aeusseren Quartils)")
                    continue
                seite = _seite
                basis = _basis(kd, k)
                stufe_n, stufe_name = _reclaim_stufe(
                    seite, k, basis, hi, lo, cl, cfg)
                if stufe_n == 0:
                    continue
                entry_bar = k + stufe_n
                reclaim_bar = entry_bar - 1
                if k <= kd.letzter_sweep_bar:
                    stats["f3"] += 1
                    continue
                if richtung == "SHORT":
                    cluster_ext = float(np.max(hi[k:reclaim_bar + 1]))
                    sl = cluster_ext + cfg.sl_buffer_usd
                else:
                    cluster_ext = float(np.min(lo[k:reclaim_bar + 1]))
                    sl = cluster_ext - cfg.sl_buffer_usd
                _vor_zeit = letzter_trade.get(kd.kid)
                if (_vor_zeit is not None
                        and entry_bar - _vor_zeit.entry_bar
                        < cfg.retest_zyklus_bars):
                    stats["zyklus_blockiert"] += 1
                    zyklus_liste.append(
                        f"bar {k:4d} {richtung:5s} K{kd.kid:3d} "
                        f"basis={_basis(kd, k):.3f} -> ZYKLUS-SPERRE "
                        f"(letzter Sweep Bar {kd.letzter_sweep_bar}, "
                        f"Abstand {k - kd.letzter_sweep_bar} "
                        f"< {cfg.retest_zyklus_bars})")
                    continue
                geg = _gegenkante(richtung, k)
                if geg is None:
                    stats["kein_gegner"] += 1
                    continue
                gegen_basis = _basis(geg, k)          # D1: wirksame Basis
                # --- Substitution 6: Hook 2 (TP2-Herkunft) ----------------
                if self._hook is not None:
                    _h2 = self._hook.hook_2_ziel(k, richtung)
                    _modus = getattr(getattr(_h2, "modus", None), "value", None)
                    if _modus == "BLOCKIERT":         # K2: Wertvergleich
                        stats["kein_raum"] += 1
                        continue
                    if _modus == "PHASE":
                        _zp = getattr(_h2, "ziel_preis", None)
                        if _zp is not None:
                            gegen_basis = float(_zp)
                if richtung == "SHORT":
                    if not (gegen_basis < basis):
                        stats["kein_raum"] += 1
                        continue
                    if (abs(basis - gegen_basis) / basis * 100.0
                            < V3_TP_MINDIST_PCT):
                        stats["kein_raum"] += 1
                        continue
                    unter, ober = gegen_basis, basis
                else:
                    if not (gegen_basis > basis):
                        stats["kein_raum"] += 1
                        continue
                    if (abs(gegen_basis - basis) / basis * 100.0
                            < V3_TP_MINDIST_PCT):
                        stats["kein_raum"] += 1
                        continue
                    unter, ober = basis, gegen_basis
                poc = _poc(d, poc_start, k, unter, ober, cfg.num_bins)
                if not (unter < poc < ober):
                    stats["kein_raum"] += 1
                    continue
                entry = float(op[entry_bar])
                tp2 = gegen_basis
                if richtung == "SHORT":
                    if not (sl > entry > poc > tp2):
                        stats["kein_raum"] += 1
                        continue
                else:
                    if not (sl < entry < poc < tp2):
                        stats["kein_raum"] += 1
                        continue
                risk = abs(sl - entry)
                if risk <= 0:
                    stats["kein_raum"] += 1
                    continue
                trade = _c_loese_trade(
                    hi, lo, cl, entry_bar, entry, richtung, sl, poc, tp2,
                    cfg.tp1_anteil_pct)
                if cfg.max_gleichzeitig_je_richtung > 0:
                    _offen = _konkurrenz_aktiv(
                        setups, richtung, entry_bar,
                        trade.exit1_bar, trade.exit2_bar)
                    if _offen > cfg.max_gleichzeitig_je_richtung:
                        stats["concurrency_blockiert"] += 1
                        continue
                if entry_bar in getradete_entry_bars:
                    continue
                getradete_entry_bars.add(entry_bar)
                kd.letzter_signal_bar = k
                kd.letzter_sweep_bar = k
                if richtung == "SHORT":
                    kd.cluster_hoch = max(kd.cluster_hoch, cluster_ext)
                else:
                    kd.cluster_tief = (cluster_ext if kd.cluster_tief <= 0.0
                                       else min(kd.cluster_tief, cluster_ext))
                setup = _SESetup(
                    bar=k, richtung=richtung, kid=kd.kid, basis=basis,
                    sweep=sweep_px, trigger_close=float(cl[k]),
                    touch_n=kd.touch_conf(k), poc=poc, tp2=tp2, sl=sl,
                    entry=entry, r=trade.r_mult, resultat=trade.resultat,
                    stufe=stufe_name or "STUFE_1_IN_BAR", reclaim_bar=reclaim_bar,
                    entry_bar=entry_bar, ist_prim_anker=kd.ist_prim_anker,
                    grund1=trade.grund1, exit1_bar=trade.exit1_bar,
                    exit2_bar=trade.exit2_bar,
                    grund2=trade.grund2, r1=trade.r1, r2=trade.r2)
                letzter_trade[kd.kid] = setup
                setups.append(setup)

        # --- Substitution 7: G4-Phasenboden (DI statt globals()) ----------
        if self._hook is not None:
            _kid_g4: Dict[int, Any] = {int(e.kid): e for e in alle}
            for _seg_g4 in getattr(self._hook, "segmente", ()):
                _lit_g4 = getattr(_seg_g4, "boden_deklariert_literal", None)
                if _lit_g4 is None:
                    continue
                for _k_g4 in range(int(_seg_g4.start_bar),
                                   int(_seg_g4.end_bar) + 1):
                    if not (lo[_k_g4] < _lit_g4 < cl[_k_g4]):
                        continue
                    _spec_g4 = self._hook.hook_3_boden_reclaim(_k_g4)
                    if _spec_g4 is None:
                        continue
                    assert abs(float(_spec_g4.deklarierter_boden_literal)
                               - float(_lit_g4)) < 1e-12, _spec_g4
                    _kante_g4 = _kid_g4.get(int(_spec_g4.boden_kid))
                    if _kante_g4 is None:
                        continue
                    if _kante_g4.touch_conf(_k_g4) < cfg.min_touches_handelbar:
                        continue
                    _eb_g4 = _k_g4 + 1
                    if _eb_g4 in getradete_entry_bars:
                        continue
                    _entry_g4 = float(op[_eb_g4])
                    _sl_g4 = (float(lo[_k_g4:_eb_g4 + 1].min())
                              - cfg.sl_buffer_usd)
                    _poc_g4 = _poc(
                        d, int(_seg_g4.start_bar), _k_g4, float(_lit_g4),
                        float(_spec_g4.tp2), cfg.num_bins)
                    if not (_sl_g4 < _entry_g4 < _poc_g4 < _spec_g4.tp2):
                        continue
                    _tr_g4 = _c_loese_trade(
                        hi, lo, cl, _eb_g4, _entry_g4, "LONG", _sl_g4,
                        _poc_g4, float(_spec_g4.tp2), cfg.tp1_anteil_pct)
                    if cfg.max_gleichzeitig_je_richtung > 0:
                        _offen_g4 = _konkurrenz_aktiv(
                            setups, "LONG", _eb_g4,
                            _tr_g4.exit1_bar, _tr_g4.exit2_bar)
                        if _offen_g4 > cfg.max_gleichzeitig_je_richtung:
                            stats["concurrency_blockiert"] += 1
                            continue
                    getradete_entry_bars.add(_eb_g4)
                    setups.append(_SESetup(
                        bar=_k_g4, richtung="LONG",
                        kid=int(_spec_g4.boden_kid),
                        basis=float(_basis(_kante_g4, _k_g4)),
                        sweep=float(lo[_k_g4]), trigger_close=float(cl[_k_g4]),
                        touch_n=int(_kante_g4.touch_conf(_k_g4)),
                        poc=float(_poc_g4), tp2=float(_spec_g4.tp2),
                        sl=_sl_g4, entry=_entry_g4, r=float(_tr_g4.r_mult),
                        resultat=_tr_g4.resultat, stufe="STUFE_1_IN_BAR",
                        reclaim_bar=_eb_g4, entry_bar=_eb_g4,
                        ist_prim_anker=False, grund1=_tr_g4.grund1,
                        exit1_bar=int(_tr_g4.exit1_bar),
                        exit2_bar=int(_tr_g4.exit2_bar),
                        grund2=_tr_g4.grund2, r1=_tr_g4.r1,
                        r2=_tr_g4.r2))

        stats["promotionen"] = sum(1 for e in alle if e.ist_prim_anker)
        stats["v_s"] = len(setups)
        stats["zyklus_liste"] = zyklus_liste
        stats["quartil_liste"] = quartil_liste
        stats["blocker_liste"] = blocker_liste
        stats["stacking_liste"] = stacking_liste
        return setups, stats


__all__ = [
    "baseline", "BASELINE_PFAD", "BASELINE_SHA_SOLL",
    "KantenSeite", "SignalRichtung", "Hook2ZielModus",
    "V020KantenKonfiguration", "KantenReferenz", "Marktrand",
    "Hook2Ergebnis", "BodenReclaimSpec",
    "KantenWertedomaene", "KantenRegimeHook",
    "kantenreferenz_aus", "marktrand_bei", "im_aeusseren_quartil",
    "existiert_nativ", "lebt_kausal", "etabliert_kausal",
    "V020KantenEngine", "V3_TP_MINDIST_PCT",
]
