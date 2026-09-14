# -*- coding: utf-8 -*-
"""V022-Kanten-Engine: Schlanker, autonomer Trade-Loop ohne Altlasten.

Arretierte Invarianten:
    * Kantenbasis: ausschliesslich ``basis_bei(k)``. Kein Basis-Modus.
    * Fensterrand-Exit: unbedingte Glattstellung zum ``close[-1]``, Grund
      ``ENDE``. NICHT hier implementiert, sondern durch das Zitat von
      ``B._c_loese_trade`` geerbt (Baseline Z1594/1630/1637).
    * Read-Only: ``scan = copy.deepcopy(scan)`` als erste Rumpfanweisung.
    * Kausalitaet: ``reclaim_bar = entry_bar - 1`` (Baseline Z2644, K6).
    * Trade-Aufloesung: ``B._c_loese_trade`` wird direkt zitiert (kein Klon,
      10 Positionalparameter).
    * Keine Modul-Globals als LAUFZUSTAND (``_CACHE`` ist reiner Lade-Cache).
    * Kein G4-Hook-Block (Baseline Z2753..2838 entfernt), kein V020-Erbgang,
      keine String-Patches, kein ``exec``.

Herkunft: Der Rumpf von ``_se_trades_v022`` ist ZEILEN-VERBATIM aus
``test/tmp_kanten_engine_replay.py`` Z2409..2845 uebernommen (Erzeuger:
``test/_tmp_v022_erzeuge.py``). Vier mechanische Eingriffe -- dokumentiert im
Funktions-Docstring (V022-Delta) und im Erzeuger.

Bewusste Auslassungen (Beschluss F32/F33/F40/F42):
    * keine Segmentgrenzen, kein ``segmentwand_modus``, kein ``exec``
      (die August-Segmentwand bleibt als V021/T2-Spezialfall arretiert);
    * kein ``replikationspfad_v020`` (V020 bleibt in seinem eigenen Modul);
    * kein ATR (``anreichere_atr_h1`` verbleibt als Diagnostik-Werkzeug der
      Sonde -- keine Scheinkonfiguration, kein toter Pfad).
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    ClassVar,
    Dict,
    Final,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
)

import numpy as np

# ============================================================ A) Typ-Aliase
# Wertform identisch zur Baseline (Z2845); Annotation ehrlich korrigiert (B1).
# Die Baseline deklariert ``Dict[str, int]``, schreibt aber in Z2841..2844 vier
# LISTEN hinein (jeweils ``# type: ignore``). Die Wertform bleibt unveraendert.
SeErgebnis = Tuple[List[Any], Dict[str, Any]]
Richtung = Literal["SHORT", "LONG"]

# Reine ANNOTATIONS-Aliase: unter PEP 563 werden alle Annotationen zu Strings
# und NIE zur Laufzeit aufgeloest. Sie stehen ausschliesslich fuer die
# Lesbarkeit des verbatim uebernommenen Textes. Der lokale Alias ist
# notwendig, weil die Baseline erst zur Laufzeit via ``_load`` existiert.
KantenSeite = Literal["OBEN", "UNTEN"]
_SEEdgeH = Any

# ============================================================ B) Baseline-Anker
# G1: der SHA ist GERECHNET, nicht zitiert.
BASELINE_PFAD: Final[Path] = (
    Path(__file__).resolve().parent / "tmp_kanten_engine_replay.py")
BASELINE_SHA_SOLL: Final[str] = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")


# ============================================================ C) Vertrag
@dataclass(frozen=True, slots=True)
class V022KantenKonfiguration:
    """Bereinigter V022-Vertrag: 1 Feld, 1 dokumentierende Klassenkonstante."""

    tp_mindist_pct: float = 1.5
    """Basis-zu-Basis Mindestabstand in Prozent.

    FALSIFIKATIONSVERMERK (Erratum K7b, H20.53 Paragraph 1b):
    Empirisch in 5/5 Fenstern INERT -- 0 Bindungen. ``_gegenkante`` mit
    ``GEGENKANTE_MODUS = "EXTREM"`` maximiert die Distanz, waehrend dieses
    Gate kleine Distanzen verwirft: Extremwahl und Mindestabstand stehen in
    direkter Opposition. Das Gate kann nur feuern, wenn der GESAMTE
    Gegenpool innerhalb der Schwelle liegt. KEIN STEUERUNGSHEBEL -- das Feld
    bleibt zur Baseline-Kompatibilitaet (Default 1.5).
    """

    GEGENKANTE_MODUS: ClassVar[Literal["EXTREM"]] = "EXTREM"

    def __post_init__(self) -> None:
        if self.tp_mindist_pct <= 0.0:
            raise ValueError(
                f"tp_mindist_pct muss > 0.0 sein (ist {self.tp_mindist_pct}).")


# ============================================================ D) Fremdnamen-Vertrag
# Diese Definitionen werden NICHT geklont, sondern zur Laufzeit aus der
# arretierten Baseline bezogen (Beschluss L2). Die fuenf Forwarder unten
# sind reine Resolver ohne eigene Logik: der Rumpftext kann deshalb verbatim
# bleiben und ruft weiterhin ``_SESetup(...)`` statt ``B._SESetup(...)``.
#
#   B.StraightEdgeHarnessKonfiguration   <- direkt in _se_trades_v022
#   B._SESetup                           <- Forwarder
#   B._c_loese_trade                     <- Forwarder (10 Positionalparameter)
#   B._konkurrenz_aktiv                  <- Forwarder
#   B._reclaim_stufe                     <- Forwarder (liest 4 Engine-Felder)
#   B.berechne_kausalen_histogramm_poc   <- Forwarder
#   B.V3_TP_MINDIST_PCT                  <- nur via pruefe_paritaet
#
# Rein annotativ (nie zur Laufzeit aufgeloest): _SEEdgeH, KantenSeite,
# SignalRichtung, Tuple/List/Dict/Optional.


# ============================================================ E) Loader
def _sha(pfad: Path) -> str:
    """SHA256 einer Datei, blockweise (identisch zur Sonde/SHA-Guard-Konvention)."""
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _pruefe_anker() -> None:
    """Fremdstand-Schutz der Baseline (fail-loud, G8: ``RuntimeError``).

    Raises:
        RuntimeError: Die Baseline weicht vom arretierten SHA ab.
    """
    ist = _sha(BASELINE_PFAD)
    if ist != BASELINE_SHA_SOLL:
        raise RuntimeError(
            f"Baseline-Fremdstand: {ist[:16]}..., "
            f"erwartet {BASELINE_SHA_SOLL[:16]}...")


_CACHE: Dict[str, Any] = {}


def _load(name: str, p: Path) -> Any:
    """Dynamischer Modul-Loader (verbatim V021, Beschluss F45/G3).

    Die Registrierung in ``sys.modules`` ist ZWINGEND: die Baseline setzt
    ``from __future__ import annotations`` (Z91), ihre Feldannotationen sind
    damit Strings. CPython 3.12 ``dataclasses._is_type`` loest dot-freie
    Annotationen ueber ``sys.modules.get(cls.__module__).__dict__`` auf
    (``dataclasses.py`` Z742..749). Fehlt der Eintrag, greift ``None.__dict__``
    -> ``AttributeError: 'NoneType' object has no attribute '__dict__'``.
    """
    spec = importlib.util.spec_from_file_location(name, p)
    if spec is None or spec.loader is None:
        raise ImportError(f"Kann {p} nicht laden")
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(p)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _engine() -> Any:
    """Baseline-Modul, read-only, lazy und gecached (kein Importseiteneffekt)."""
    if "basis" not in _CACHE:
        _pruefe_anker()
        _CACHE["basis"] = _load("v022_basis", BASELINE_PFAD)
    return _CACHE["basis"]


# ============================================================ F) Forwarder
def _reclaim_stufe(*args: Any, **kwargs: Any) -> Any:
    """Resolver auf ``B._reclaim_stufe`` (liest 4 Engine-Felder der Harness)."""
    return _engine()._reclaim_stufe(*args, **kwargs)


def _konkurrenz_aktiv(*args: Any, **kwargs: Any) -> Any:
    """Resolver auf ``B._konkurrenz_aktiv`` (Gleichzeitigkeit je Richtung)."""
    return _engine()._konkurrenz_aktiv(*args, **kwargs)


def _c_loese_trade(*args: Any, **kwargs: Any) -> Any:
    """Resolver auf ``B._c_loese_trade`` -- kein Klon (Beschluss L2).

    Traegt die Fensterrand-Invariante: offen am Fensterende -> ``close[-1]``
    mit Grund ``ENDE`` (Baseline Z1594/1630/1637).
    """
    return _engine()._c_loese_trade(*args, **kwargs)


def _SESetup(*args: Any, **kwargs: Any) -> Any:
    """Resolver auf ``B._SESetup`` -- dadurch EINE Setup-Klasse fuer alle Laeufe."""
    return _engine()._SESetup(*args, **kwargs)


def berechne_kausalen_histogramm_poc(*args: Any, **kwargs: Any) -> Any:
    """Resolver auf ``B.berechne_kausalen_histogramm_poc`` (Q-POC, kausal)."""
    return _engine().berechne_kausalen_histogramm_poc(*args, **kwargs)


# ============================================================ G) Paritaetswaechter
def pruefe_paritaet(cfg: V022KantenKonfiguration, B: Any) -> bool:
    """Vergleicht den Vertrags-Default mit der Baseline-Konstante (F39).

    Bewusst NICHT als Dauer-Assert im Trade-Loop: ein harter Waechter dort
    wuerde jede Parameter-Variation (F24, ``quartil_distanz_pct``) blockieren.
    """
    return bool(float(cfg.tp_mindist_pct) == float(B.V3_TP_MINDIST_PCT))


def _gegenkante_v022(seite_edges: Dict[Any, List[Any]], k: int,
                     richtung: Richtung) -> Optional[Any]:
    gegenseite: KantenSeite = "UNTEN" if richtung == "SHORT" else "OBEN"
    # Block2/Q30: identische Existenz-Semantik wie _kandidat (Pivot+2),
    # bewusst OHNE AKTIV-Gate (Q5/Q14: SCHLAFENDE Gegenkanten erlaubt).
    # Q18/Q30: promovierte Primaer-Anker ohne 2-Touch-Gate.
    pool = [e for e in seite_edges[gegenseite]
            if e.erster_pivot_bar + 2 <= k + 1
            and ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                 or e.touch_conf(k) >= 2)]
    if not pool:
        return None
    if gegenseite == "OBEN":
        return max(pool, key=lambda e: e.basis_bei(k))
    return min(pool, key=lambda e: e.basis_bei(k))



def _se_trades_v022(scan: Dict[str, Any], cfg: V022KantenKonfiguration,
                    harness_cfg: Optional[Any] = None) -> SeErgebnis:
    """Regel-2-Trades an der aeussersten AKTIVEN Kante (D4, 2026-09-08).

    Q1: Die aeusserste Linie handelt ohne V-S >= 3 — die Reclaim-Abweisung
    IST die operative Reife; V-S >= 3 bleibt Schutz innerer (stummer) Linien.
    Q9b/Q13: promovierte Primaer-Anker sind handelbar, Basis eingefroren.
    Q2/Q3/Q17: echter Durchstich + Stufen 1/2/3 (Non-Expansion mit Puffer).
    Q4: F3-Frische referenziert den Sweep-Bar.
    Q6/Q10: SL = Cluster-Extremum (kausal bis Reclaim-Bar) + Puffer.
    Q11/Q16: F2 — Einstieg nur ohne offene Position ODER nach De-Risking
    (Haelfte 1 = TP1). Q8: gleicher Schwung sperrt im Vollrisiko.
    Q5/Q14: TP2 = aeusserste Gegenkante (>= 2 Touches, >= 1.5 %, SCHLAFEND ok).
    Nur in der Box (bars < box_end_bar).

    --- V022-Delta gegenueber dem verbatim uebernommenen Rumpf -------
    (1) ``scan = copy.deepcopy(scan)`` als erste Rumpfanweisung (M1:
        der Motor mutiert Kantenobjekte; bisher musste der AUFRUFER
        kopieren).
    (2) Zielraum-Mindestabstand: die Baseline-Modulkonstante
        ``V3_TP_MINDIST_PCT`` (Z2681/Z2689) wird zum Vertragsfeld
        ``cfg.tp_mindist_pct``. Default identisch (1.5) -- der
        Paritaetswaechter ``pruefe_paritaet`` belegt das.
    (3) Der G4/Hook-3-Block (Baseline Z2753..2838) entfaellt restlos:
        kein ``globals().get("_hook")``, kein zweiter Append. Der
        Hauptappend (Z2750/Z2751) bleibt unberuehrt.
    (4) ``_gegenkante`` wird als ``_gegenkante_v022`` auf Modulebene
        gefuehrt; ``seite_edges`` ist Parameter statt Closure. Der
        Rumpf bleibt verbatim, die Reihenfolge unveraendert (B4).
    (5) Die Harness-Konfiguration wird INJIZIERT (``harness_cfg``).
        Alle Rumpfzugaenge lesen ``hcfg`` -- 14 Engine-Felder.
        Damit bleibt der 1-Feld-Vertrag gewahrt und ``Q29``
        (``quartil_distanz_pct``) fuer die Parameter-Sonde F24
        steuerbar.
    """
    # --- READ-ONLY-GARANTIE (nicht abschaltbar) ------------------------
    scan = copy.deepcopy(scan)
    hcfg = (harness_cfg if harness_cfg is not None
            else _engine().StraightEdgeHarnessKonfiguration())
    d = scan["d"]
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    op = d["open"].to_numpy(dtype=float)
    alle: List[_SEEdgeH] = list(scan["edges"]) + list(scan["seeds"])
    seite_edges: Dict[KantenSeite, List[_SEEdgeH]] = {
        "OBEN": [e for e in alle if e.seite == "OBEN"],
        "UNTEN": [e for e in alle if e.seite == "UNTEN"]}
    setups: List[_SESetup] = []
    box_end = scan["box_end_bar"]
    stats: Dict[str, int] = {"v_s": 0, "kein_gegner": 0, "f3": 0,
                             "kein_raum": 0, "zyklus_blockiert": 0,
                             "quartil_blockiert": 0, "blocker": 0,
                             "promotionen": 0,
                             "stacking_blockiert": 0,
                             "frisch_blockiert": 0,
                             "concurrency_blockiert": 0}
    poc_start = 0                       # Balance-Beginn (Box-Beginn)
    letzter_trade: Dict[int, _SESetup] = {}
    getradete_entry_bars: set[int] = set()   # B23-3: Dedup je Entry-Bar
    stacking_liste: List[str] = []        # §7.1 B (Teil 4)
    zyklus_liste: List[str] = []
    quartil_liste: List[str] = []
    blocker_liste: List[str] = []

    def _existiert(e: _SEEdgeH, k: int) -> bool:
        """Linie existiert, sobald ihr level-definierender Pivot bestaetigt ist.

        Bestaetigung = Pivot-Bar + 2 (P1). Fuer den fruehestmoeglichen Entry
        (k+1) bedeutet das: erster_pivot_bar + 2 <= k + 1. Die Keimung
        (>= 2 Touches) ist KEINE Existenzbedingung — sie bestimmt nur die
        ZWISCHEN_LEVEL-Rolle.
        """
        if not e.ist_aktiv_bei(k):
            return False
        return e.erster_pivot_bar + 2 <= k + 1

    def _lebt(e: _SEEdgeH, k: int) -> bool:
        """Q25: Linie ist am Markt praesent (letzter Kontakt <= wall_live_bars).

        Dormante Crash-Extreme (K3 62.967/Bar 14, K4 63.252/Bar 20) sind keine
        Begrenzung der aktuellen Balance und duerfen die Unterseite nicht
        lahmlegen; eine LEBENDE, nicht erreichte Aussenlinie sperrt dagegen
        jeden Einstieg weiter innen.
        """
        bars = [b for b, _ in e.wicks if b <= k]
        if not bars:
            return False
        return max(bars) >= k - hcfg.wall_live_bars

    def _im_aussenquartil(richtung: SignalRichtung, k: int,
                          sweep_px: float) -> bool:
        """Q29: Einstieg nur an der aeusseren lebenden Wand.

        Distanz des Sweep-Extremums zum laufenden Range-Extrem,
        normiert auf die kausale Spanne 0..k. Aeusseres Quartil =
        <= quartil_distanz_pct (Default 25 %).
        """
        ex_hi = float(np.max(hi[:k + 1]))
        ex_lo = float(np.min(lo[:k + 1]))
        spanne = ex_hi - ex_lo
        if spanne <= 0.0:
            return True
        distanz = ((ex_hi - sweep_px) if richtung == "SHORT"
                   else (sweep_px - ex_lo)) / spanne * 100.0
        return distanz <= hcfg.quartil_distanz_pct

    def _blockiert_durch_aussenkante(richtung: SignalRichtung, k: int,
                                     kd: _SEEdgeH,
                                     sweep_px: float) -> Optional[_SEEdgeH]:
        """M6: Innenlevel-Blocker (kein Fade unter einer Aussenwand).

        Blocker ist die AEUSSERSTE existierende Linie derselben Seite, die
        vom Sweep-Extremum NICHT erreicht wurde (jenseits des Sweeps liegt)
        und deren Abstand zur Kandidatenbasis <= max_seed_distanz_pct
        (0.75 %) ist. Nur _existiert-Linien (AKTIV) wirken als Blocker (F3).
        Die AEUSSERSTE Linie ist entscheidend: eine naehere Innenlinie darf
        die Sperre nicht ausloesen, wenn die Aussenwand selbst erreicht wurde.
        """
        seite: KantenSeite = "OBEN" if richtung == "SHORT" else "UNTEN"
        basis_k = kd.basis_bei(k)
        aussen: Optional[_SEEdgeH] = None
        for e in seite_edges[seite]:
            if e is kd or not _existiert(e, k):
                continue
            b = e.basis_bei(k)
            if seite == "OBEN":
                if b <= sweep_px:
                    continue                    # erreicht -> kein Blocker
                if aussen is None or b > aussen.basis_bei(k):
                    aussen = e
            else:
                if b >= sweep_px:
                    continue
                if aussen is None or b < aussen.basis_bei(k):
                    aussen = e
        if aussen is None:
            return None
        b = aussen.basis_bei(k)
        dist = ((b - basis_k) if seite == "OBEN"
                else (basis_k - b)) / basis_k * 100.0
        return aussen if 0.0 < dist <= hcfg.max_seed_distanz_pct else None

    def _etabliert(e: _SEEdgeH, k: int) -> bool:
        """Q24: Linie ist etabliert, wenn ihr level-definierender Pivot
        mindestens min_wall_alter_bars zurueckliegt (kein Fade des ersten
        Ausbruchsversuchs einer frischen Linie).
        """
        return k - e.erster_pivot_bar >= hcfg.min_wall_alter_bars

    def _kandidat(richtung: SignalRichtung, k: int,
                  sweep_px: float) -> Optional[_SEEdgeH]:
        """Kaskade von aussen nach innen ueber EXISTIERENDE Linien (Regel 2).

        - top = hoechste/tiefste existierende Linie.
        - dist(top) <= 0            -> kein Trade (kein Fading unter der Wand)
        - dist(top) > touch_band    -> top handelt (Q1: Reclaim = Reife)
        - dist(top) <= touch_band   -> in-band beruehrt (kein Sweep) ->
          naechste Linie nach innen; innere Linien brauchen V-S >= 3
        - dist > max_sweep          -> Ueberdehnung, kein Trade
        """
        seite: KantenSeite = "OBEN" if richtung == "SHORT" else "UNTEN"

        def _dist(e: _SEEdgeH) -> float:
            basis = e.basis_bei(k)
            if richtung == "SHORT":
                return (sweep_px - basis) / basis * 100.0
            return (basis - sweep_px) / basis * 100.0

        pool: List[_SEEdgeH] = []
        for e in seite_edges[seite]:
            if not _existiert(e, k):
                continue
            # B23-2: Anker wirkt erst ab seiner Promotions-Bar (kausal).
            if not ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                    or e.touch_conf(k) >= 2):
                continue                        # Seeds nur ereignisgetrieben
            if not _etabliert(e, k):
                if _dist(e) > hcfg.touch_band_pct:
                    stats["frisch_blockiert"] += 1
                continue                        # Q24: Linie noch zu jung
            pool.append(e)
        # Q9b: ein Seed zaehlt NUR, wenn dieser Bar ihn tatsaechlich
        # durchsticht (K3/K4 werden in der Box nie unterschritten).
        for e in seite_edges[seite]:
            if e in pool or not _existiert(e, k) or e.ist_prim_anker:
                continue
            if e.touch_conf(k) >= 2 or not _etabliert(e, k):
                continue
            d = _dist(e)
            if hcfg.sweep_mindestdurchstich_pct < d <= hcfg.max_sweep_ueberdehnung_pct:
                pool.append(e)
        if not pool:
            return None
        pool.sort(key=lambda e: e.basis_bei(k), reverse=(seite == "OBEN"))
        for pos, e in enumerate(pool):
            dist = _dist(e)
            if dist < 0.0:
                if _lebt(e, k):
                    return None                 # lebende Wand nicht erreicht
                continue                        # dormante Linie ignorieren
            if dist > hcfg.max_sweep_ueberdehnung_pct:
                return None                     # Ueberdehnung, kein Reclaim
            if dist <= hcfg.sweep_mindestdurchstich_pct:
                continue                        # nur Durchstich zaehlt (Teil 7)
            if pos == 0:
                return e                        # Q1: Wand handelt (Reclaim=Reife)
            if e.touch_conf(k) < hcfg.min_touches_handelbar:
                continue                        # innere Linie braucht V-S >= 3
            return e
        return None


    for k in range(2, box_end - 3):
        for richtung in ("SHORT", "LONG"):
            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])
            kd = _kandidat(richtung, k, sweep_px)
            if kd is None:
                continue
            # --- M6: Innenlevel-Blocker (unerreichte Aussenwand) ---------------
            blk = _blockiert_durch_aussenkante(richtung, k, kd, sweep_px)
            if blk is not None:
                stats["blocker"] += 1
                blocker_liste.append(
                    f"bar {k:4d} {richtung:5s} K{kd.kid:3d} "
                    f"basis={kd.basis_bei(k):.3f} sweep={sweep_px:.3f} "
                    f"-> BLOCKER-SPERRE (unerreichte Aussenwand K{blk.kid} "
                    f"{blk.basis_bei(k):.3f})")
                continue
            # --- Q29: Niemandsland-Sperre (aeusseres Quartil) ----------
            if not _im_aussenquartil(richtung, k, sweep_px):
                stats["quartil_blockiert"] += 1
                quartil_liste.append(
                    f"bar {k:4d} {richtung:5s} K{kd.kid:3d} "
                    f"basis={kd.basis_bei(k):.3f} sweep={sweep_px:.3f} "
                    f"-> QUARTIL-SPERRE (Mitte der Range)")
                continue
            seite: KantenSeite = "OBEN" if richtung == "SHORT" else "UNTEN"
            basis = kd.basis_bei(k)
            stufe_n, stufe_name = _reclaim_stufe(seite, k, basis, hi, lo, cl,
                                                 hcfg)
            if stufe_n == 0:
                continue
            entry_bar = k + stufe_n
            reclaim_bar = entry_bar - 1
            # --- Q4: F3-Frische (Sweep-Bar-Referenz) --------------------------
            if k <= kd.letzter_sweep_bar:
                stats["f3"] += 1
                continue
            # --- Q6/Q10: Cluster-Extremum kausal bis Reclaim-Bar --------------
            if richtung == "SHORT":
                cluster_ext = float(np.max(hi[k:reclaim_bar + 1]))
                sl = cluster_ext + hcfg.sl_buffer_usd
            else:
                cluster_ext = float(np.min(lo[k:reclaim_bar + 1]))
                sl = cluster_ext - hcfg.sl_buffer_usd
            # --- Q21/B23: Retest-Zyklus (ersetzt F2-Vollrisiko + Q8) ----------
            # B23-5: letzter_sweep_bar wird NUR bei tatsaechlich genommenem
            # Trade fortgeschrieben (siehe unten) -- ein abgewiesener Kontakt
            # setzt die Uhr nicht zurueck.
            _vor_zeit = letzter_trade.get(kd.kid)
            if (_vor_zeit is not None
                    and entry_bar - _vor_zeit.entry_bar
                    < hcfg.retest_zyklus_bars):
                stats["zyklus_blockiert"] += 1
                zyklus_liste.append(
                    f"bar {k:4d} {richtung:5s} K{kd.kid:3d} "
                    f"basis={kd.basis_bei(k):.3f} -> ZYKLUS-SPERRE "
                    f"(letzter Sweep Bar {kd.letzter_sweep_bar}, "
                    f"Abstand {k - kd.letzter_sweep_bar} "
                    f"< {hcfg.retest_zyklus_bars})")
                continue
            geg = _gegenkante_v022(seite_edges, k, richtung)
            if geg is None:
                stats["kein_gegner"] += 1
                continue
            gegen_basis = geg.basis_bei(k)
            # --- Halbraum-Tripwire (Erratum K7a) -----------------------
            # KONSERVIERUNGSVERMERK (H20.53 Paragraph 1a): 0 Bindungen in
            # 5/5 Fenstern -- NICHT inert, sondern KONSERVIERT. Die
            # Gegenkante mit GEGENKANTE_MODUS="EXTREM" garantiert die
            # zulaessige Seite strukturell. Der Halbraum ist die
            # Bindungs-NULLINIE dieser Invariante: faellt er auf 0 zu
            # bleiben aus, ist die Zielwahl gekippt (Beleg: Erratum K3,
            # 22/84 Zeilen unter NAECHSTE). Beide Zweige sind ECHTER Code
            # und bleiben echte Zweige -- kein Vorab-Filter (B4).
            if richtung == "SHORT":
                if not (gegen_basis < basis):
                    stats["kein_raum"] += 1
                    continue
                if abs(basis - gegen_basis) / basis * 100.0 < cfg.tp_mindist_pct:
                    stats["kein_raum"] += 1
                    continue
                unter, ober = gegen_basis, basis
            else:
                if not (gegen_basis > basis):
                    stats["kein_raum"] += 1
                    continue
                if abs(gegen_basis - basis) / basis * 100.0 < cfg.tp_mindist_pct:
                    stats["kein_raum"] += 1
                    continue
                unter, ober = basis, gegen_basis
            poc = berechne_kausalen_histogramm_poc(
                d, poc_start, k, unter, ober, hcfg.num_bins)
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
            # --- §7.1 B REVOZIERT (Teil 7): kein Stacking-Gate ----------
            # Der Schutz gegen Re-Entry-Spamming liegt beim 12-Bar-
            # Entry-Mindestabstand (B2, Zyklus-Check unten).
            trade = _c_loese_trade(
                hi, lo, cl, entry_bar, entry, richtung, sl, poc, tp2,
                hcfg.tp1_anteil_pct)
            # --- Stufe 4b (E-34n/17): Concurrency-Schranke (Klumpenrisiko) -
            # Schutz gegen ungedecktes paralleles Engagement in EINER
            # Richtung. Auf AUG hoechstens 3 gleichzeitig -> inert; die
            # Wirkung ist maschinell im Bindetest nachgewiesen.
            if hcfg.max_gleichzeitig_je_richtung > 0:
                _offen = _konkurrenz_aktiv(
                    setups, richtung, entry_bar,
                    trade.exit1_bar, trade.exit2_bar)
                if _offen > hcfg.max_gleichzeitig_je_richtung:
                    stats["concurrency_blockiert"] += 1
                    continue
            if entry_bar in getradete_entry_bars:   # B23-3: Dedup
                continue
            getradete_entry_bars.add(entry_bar)
            kd.letzter_signal_bar = k
            kd.letzter_sweep_bar = k
            # Strenge Regel: keine Seed-Promotion fuer Trades (V-S >= 3).
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

    stats["promotionen"] = sum(1 for e in alle if e.ist_prim_anker)
    stats["v_s"] = len(setups)
    stats["zyklus_liste"] = zyklus_liste  # type: ignore[assignment]
    stats["quartil_liste"] = quartil_liste  # type: ignore[assignment]
    stats["blocker_liste"] = blocker_liste  # type: ignore[assignment]
    stats["stacking_liste"] = stacking_liste  # type: ignore[assignment]
    return setups, stats
