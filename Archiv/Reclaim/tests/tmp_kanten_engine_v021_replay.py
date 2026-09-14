# -*- coding: utf-8 -*-
"""V021-Kanten-Engine (additiv) -- 12-Punkte-Vertrag, Schritt 2.

ANLAGE (additiv). Die arretierten Motoren bleiben byte-identisch und werden
READ-ONLY geladen (SHA-Guard vor jedem Lauf):

* ``test/tmp_kanten_engine_replay.py``     Baseline ``53f28e1b...`` (SSoT Scan)
* ``test/tmp_kanten_engine_v020_replay.py`` V020 ``e79c5c29...``
* ``test/tmp_png_aug_sichttest.py``        Renderer ``500b5576...`` (ZP-5-Quelle)

DREI PFADE -- fail-loud statt stiller Falschabbildung:

1. ``TRIPEL`` -- (existenz NATIV, m6l DORMANT_PERMISSIV, rand ENDOGEN) wird an
   ``_se_trades_v020`` DELEGIERT. Grund: V020s S4 (``marktrand_bei`` aus
   lebenden Kanten) ist mechanisch NICHT der Renderer-Patch ``A_VC``
   (``hi[segment_start:k+1]``). Nur die Delegation ist bit-exakt.
   Teilbelegungen sind nicht definiert -> ``ValueError``.
2. ``SEGMENTWAND`` -- ``segmentwand_modus="AN"``: eigenes, ADAPTERFREIES
   ZP-4-Regelwerk (A_UEB1 / A_VC / A_M6L / A_SB) direkt auf dem Rohbaseline-
   Quelltext, plus ZP-5-Vorlauf ``erweitere_segmentwand_dochte`` (AST-verbatim,
   argument-pur) auf der laufeigenen ``deepcopy``.
3. ``BASELINE`` -- alle Schalter im Legacy-Stand: direkter Aufruf der
   Baseline ``_se_trades`` -- bit-identisch per Konstruktion.

Vertrag (12 Punkte, Defaults = Legacy/Baseline-Semantik):
    basis_modus              "MITTEL" | "URSPRUNG"
    gegenkante_modus         "EXTREM" | "NAECHSTE"
    fensterrand_exit         bool
    min_risk_usd             float
    atr_risiko_faktor        float
    atr_periode              int
    existenz_modus           "BASELINE" | "NATIV"
    m6l_modus                "BASELINE" | "DORMANT_PERMISSIV"
    rand_modus               "GLOBAL" | "ENDOGEN"
    segmentwand_modus        "AUS" | "AN"
    scan_readonly            "ERZWINGEN"    (nicht abschaltbar)
    ueberdehnung_segment_pct float          (12. Punkt, kein Hardcoding)

Read-only-Garantie (H20.50 Abschnitt 3): ``_se_trades_v021`` fuehrt als ERSTE
Anweisung ``copy.deepcopy(scan)`` aus. Der Aufrufer kann den Scan nicht mehr
teilen; die In-place-Mutationen (``letzter_sweep_bar``, ``cluster_*``) bleiben
in der Kapsel. Reihenfolge: deepcopy -> Segmentwand-Vorlauf -> Trade-Loop.

BEWUSST NICHT ENTHALTEN (Architekturgrenze, G4): die Hook-Schicht des
Adapters (Hook 1/2/3). Ein ``import`` des Renderers ist unmoeglich
(Modul-Level ``argparse`` -> ``SystemExit``); Adapter-Hooks sind nicht Teil
der Engine.

MESSSTAND AUG VOLL (n=1288, Split bei Kalenderkante 644; Beleg
``test/_chk_v021_verify_out.txt`` ``5f8e2b68...``):

    LEGACY (Defaults)              14 / +42.450970 | H1 8/+38.919584 | H2  6/ +3.531386
    TRIPEL (BOX 644)               14 / +27.327383 | -- bit-exakt V020-A
    SEGMENTWAND "AN" (adapterfrei) 18 / +52.876174 | H1 8/+38.919584 | H2 10/+13.956589

Der Hook-getragene Wert V1_kausal 23/+85.577150 ist mit dieser Engine NICHT
erreichbar -- die Differenz ist die Adapter-Schicht, nicht die Segmentwand.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np

ROOT: Path = Path(__file__).resolve().parent.parent
TEST: Path = ROOT / "test"
BASELINE_PFAD: Path = TEST / "tmp_kanten_engine_replay.py"
V020_PFAD: Path = TEST / "tmp_kanten_engine_v020_replay.py"
RENDERER_PFAD: Path = TEST / "tmp_png_aug_sichttest.py"
BASELINE_SHA: str = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
V020_SHA: str = (
    "e79c5c29482398d8237469a79a234c7200f8718e840252cc33d2bea37f3865af")
RENDERER_SHA: str = (
    "500b55762001d6667af3d977324c81eb4ecbceacc2fa0d8b62c36c7e383250e0")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backtest_lab.phasen_regime_adapter import PhasenKanteInfo  # noqa: E402

# --- Lauf-Kapsel: je Aufruf gesetzt, nie ueber Aufrufe hinweg geteilt -------
_SEGMENTGRENZEN: Tuple["Segmentgrenze", ...] = ()


# ============================================================ A) Der Vertrag
BasisModus = Literal["MITTEL", "URSPRUNG"]
GegenkanteModus = Literal["EXTREM", "NAECHSTE"]
ExistenzModus = Literal["BASELINE", "NATIV"]
M6LModus = Literal["BASELINE", "DORMANT_PERMISSIV"]
RandModus = Literal["GLOBAL", "ENDOGEN"]
SegmentwandModus = Literal["AUS", "AN"]
ScanReadOnlyModus = Literal["ERZWINGEN"]


@dataclass(frozen=True, slots=True)
class Segmentgrenze:
    """Passive Segmentgrenze -- Daten, nicht Konfiguration (Beschluss G4).

    Die Attributnamen spiegeln ``PhasenSegmentEintrag``, damit der per AST
    extrahierte Rumpf von ``erweitere_segmentwand_dochte`` verbatim laeuft.
    ``PhasenKanteInfo`` wird aus dem Adapter IMPORTIERT (Single Source of
    Truth) -- keine zweite Definition im Motor.

    Args:
        start_bar: Erstes Bar des Segments (inklusiv).
        end_bar: Letztes Bar des Segments (inklusiv).
        boden: Untere Grenzkante; gelesen wird ``.kid``.
        decke: Obere Grenzkante; gelesen wird ``.kid``.
        boden_deklariert_literal: Deklarierter Phasenboden als LITERAL.
            ``None`` (Default) = Regel G4 inaktiv.
    """

    start_bar: int
    end_bar: int
    boden: PhasenKanteInfo
    decke: PhasenKanteInfo
    boden_deklariert_literal: Optional[float] = None


@dataclass(frozen=True, slots=True)
class V021KantenKonfiguration:
    """Unveraenderlicher Konfigurationsvertrag der V021-Replay-Engine.

    Abgrenzung: ``V020KantenKonfiguration`` hat S2/S3/S4 unbedingt verdrahtet
    (keine Schalter). V021 fuehrt dieselbe Semantik schaltbar; alle Defaults
    = Legacy/Baseline-Verhalten.

    Beweislasten (arretiert):
        * Defaults => V0 (VOLL) 14/+42.450970, H1 8/+38.919584,
          H2 6/+3.531386 -- bit-identisch.
        * Tripel => V020 bit-exakt (AUG BOX 14/+27.327383;
          MAI/JUN/JUL 58/56/68).
        * ``scan_readonly``: derselbe Scan zweimal => identisches Ergebnis.

    Raises:
        ValueError: ``atr_periode < 1``, negative Risiko-Untergrenzen oder
            ``ueberdehnung_segment_pct <= 0``.
    """

    basis_modus: BasisModus = "MITTEL"
    gegenkante_modus: GegenkanteModus = "EXTREM"
    fensterrand_exit: bool = True
    min_risk_usd: float = 0.0
    atr_risiko_faktor: float = 0.0
    atr_periode: int = 14
    existenz_modus: ExistenzModus = "BASELINE"
    m6l_modus: M6LModus = "BASELINE"
    rand_modus: RandModus = "GLOBAL"
    segmentwand_modus: SegmentwandModus = "AUS"
    scan_readonly: ScanReadOnlyModus = "ERZWINGEN"
    ueberdehnung_segment_pct: float = 0.80

    def __post_init__(self) -> None:
        if self.atr_periode < 1:
            raise ValueError(
                f"atr_periode muss >= 1 sein (ist {self.atr_periode}).")
        if self.min_risk_usd < 0.0 or self.atr_risiko_faktor < 0.0:
            raise ValueError("Risiko-Untergrenzen muessen >= 0 sein.")
        if self.ueberdehnung_segment_pct <= 0.0:
            raise ValueError(
                "ueberdehnung_segment_pct muss > 0 sein "
                f"(ist {self.ueberdehnung_segment_pct}).")

    @property
    def ist_tripel(self) -> bool:
        """True gdw. alle drei Regression-Schalter V020-Semantik tragen."""
        return (self.existenz_modus == "NATIV"
                and self.m6l_modus == "DORMANT_PERMISSIV"
                and self.rand_modus == "ENDOGEN")

    @property
    def hat_tripel_teilbelegung(self) -> bool:
        """True gdw. genau eine oder zwei Tripel-Komponenten gesetzt sind."""
        n = sum((self.existenz_modus == "NATIV",
                 self.m6l_modus == "DORMANT_PERMISSIV",
                 self.rand_modus == "ENDOGEN"))
        return 0 < n < 3

    @property
    def ist_legacy(self) -> bool:
        """True gdw. alle Schalter im arretierten Legacy-Stand stehen."""
        return (not self.ist_tripel
                and self.existenz_modus == "BASELINE"
                and self.m6l_modus == "BASELINE"
                and self.rand_modus == "GLOBAL"
                and self.segmentwand_modus == "AUS")

    def risiko_floor(self, atr: float) -> float:
        """Untergrenze des Stop-Nenners (Beschluss H2: Maximum der Klammern).

        Args:
            atr: Kausaler ATR-Wert des Signal-Bars (USD).

        Returns:
            ``max(min_risk_usd, atr_risiko_faktor * atr)``.
        """
        return max(float(self.min_risk_usd),
                   float(self.atr_risiko_faktor) * float(atr))

    def risiko_effektiv(self, risk_roh: float, atr: float) -> float:
        """Ehrlicher Nenner: ``max(|sl-entry|, risiko_floor(atr))``."""
        return max(abs(float(risk_roh)), self.risiko_floor(atr))


# ======================================================= B) Lazy-Bindung
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _pruefe_anker() -> None:
    """Fremdstand-Schutz fuer alle drei Quellen (fail-loud, vor jedem Lauf)."""
    for _p, _soll, _nm in ((BASELINE_PFAD, BASELINE_SHA, "Baseline"),
                           (V020_PFAD, V020_SHA, "V020"),
                           (RENDERER_PFAD, RENDERER_SHA, "Renderer")):
        _ist = _sha(_p)
        if _ist != _soll:
            raise RuntimeError(
                f"{_nm}-Fremdstand: {_p.name} hat {_ist[:16]}..., "
                f"erwartet {_soll[:16]}...")


def _load(name: str, p: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(p)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_CACHE: Dict[str, Any] = {}


def _engine() -> Any:
    """Baseline-Modul (read-only, SHA-Guard, lazy -- kein Importseiteneffekt)."""
    if "basis" not in _CACHE:
        _pruefe_anker()
        _CACHE["basis"] = _load("v021_basis", BASELINE_PFAD)
    return _CACHE["basis"]


def _v020() -> Any:
    """V020-Modul -- Delegationsziel des Tripels."""
    if "v020" not in _CACHE:
        _pruefe_anker()
        _CACHE["v020"] = _load("v021_v020", V020_PFAD)
    return _CACHE["v020"]


def _wirksame_cfg(cfg: V021KantenKonfiguration) -> Any:
    """Frozen-Subklasse der Engine-Config, die die 12 Vertragsfelder traegt.

    Der Patchtext liest Engine-Felder (``cfg.touch_band_pct``,
    ``cfg.max_sweep_ueberdehnung_pct``, ...) UND Vertragsfelder
    (``cfg.ueberdehnung_segment_pct``, ``cfg.existenz_modus``, ...). Die
    Subklasse fuehrt beide Welten zusammen, ohne die oeffentliche
    Vertragsklasse zu verbreitern.

    Args:
        cfg: Der 12-Punkte-Vertrag.

    Returns:
        Instanz mit Engine-Defaults plus den 12 Vertragswerten.
    """
    if "_WCFG" not in _CACHE:
        B = _engine()

        @dataclasses.dataclass(frozen=True, slots=True)
        class WirksameCfg(B.StraightEdgeHarnessKonfiguration):  # type: ignore
            basis_modus: str = "MITTEL"
            gegenkante_modus: str = "EXTREM"
            fensterrand_exit: bool = True
            min_risk_usd: float = 0.0
            atr_risiko_faktor: float = 0.0
            atr_periode: int = 14
            existenz_modus: str = "BASELINE"
            m6l_modus: str = "BASELINE"
            rand_modus: str = "GLOBAL"
            segmentwand_modus: str = "AUS"
            scan_readonly: str = "ERZWINGEN"
            ueberdehnung_segment_pct: float = 0.80

        _CACHE["_WCFG"] = WirksameCfg
    felder = [f.name for f in dataclasses.fields(V021KantenKonfiguration)]
    return _CACHE["_WCFG"](**{f: getattr(cfg, f) for f in felder})


# ============================================ C) AST-Extraktion (ZP-Quelle)
def _extrahiere(quelle: str, funktionen: Sequence[str]) -> str:
    """Quelltexte der benannten Funktionen, verbatim, in Dateireihenfolge.

    Ein ``import`` des Renderers ist unmoeglich (Modul-Level ``argparse`` ->
    ``SystemExit``). Die AST-Extraktion ist der einzige quellentreue Weg;
    eine Funktionskopie waere eine zweite Wahrheit.

    Raises:
        RuntimeError: ein angefordertes Funktionsobjekt fehlt.
    """
    tree = ast.parse(quelle)
    treffer = {n.name: n for n in tree.body
               if isinstance(n, ast.FunctionDef) and n.name in funktionen}
    fehlend = set(funktionen) - set(treffer)
    if fehlend:
        raise RuntimeError(f"AST-Anker fehlt: {sorted(fehlend)}")
    return "\n\n".join(
        ast.get_source_segment(quelle, treffer[n]) or "" for n in funktionen)


def _ueberdehnung_binden(text: str) -> str:
    """12. Vertragspunkt: die beiden 0.80-CODE-Literale -> cfg.ueberdehnung_
    segment_pct.

    Nur CODE-Anker werden ersetzt; die Nennungen in Kommentaren und
    Docstrings bleiben unangetastet (dokumentarisch korrekt).

    Raises:
        RuntimeError: ein Code-Anker kommt nicht genau einmal vor.
    """
    anker = (
        ("_ueb-Rumpf",
         "return 0.80 if _zv(kk) else cfg.max_sweep_ueberdehnung_pct",
         "return cfg.ueberdehnung_segment_pct if _zv(kk) else "
         "cfg.max_sweep_ueberdehnung_pct"),
        ("_reclaim_stufe_lok-Rumpf",
         "max_sweep_ueberdehnung_pct=0.80)",
         "max_sweep_ueberdehnung_pct=cfg.ueberdehnung_segment_pct)"),
    )
    for _nm, _alt, _neu in anker:
        n = text.count(_alt)
        if n != 1:
            raise RuntimeError(
                f"0.80-Code-Anker '{_nm}' nicht eindeutig ({n}).")
        text = text.replace(_alt, _neu)
    return text


def _regel_ersetzen(src: str, cfg: V021KantenKonfiguration) -> str:
    """Weht die vier ZP-4-Regeln in den ROHBASELINE-Quelltext von ``_se_trades``.

    Die Regeln (verbatim aus dem Renderer uebernommen, nur Gate und
    ``_hook``-Bezug adapterfrei gefasst):

    1. A_UEB1  Ueberdehnungsschranke segment-lokal (``_ueb``).
    2. A_VC    Quartil-Extremum ab Segmentstart.
    3. A_M6L   M6-Blocker ueberspringt dormante Linien.
    4. A_SB    gesweepte Linie zaehlt in der Zone als aktiv.

    Das Gate ist je Regel ``_zv(k)`` (segment-lokal) ODER der globale
    Regressionsschalter; im Legacy-Stand ist es damit wirkungsgleich zu
    ``_zv(k)`` und ausserhalb der Zone vollstaendig inert.

    Raises:
        RuntimeError: ein Regelanker kommt nicht genau einmal vor.
    """
    g_sb = ("_zv(k) or cfg.existenz_modus == 'NATIV'"
            if cfg.existenz_modus == "NATIV" else "_zv(k)")
    g_m6 = ("_zv(k) or cfg.m6l_modus == 'DORMANT_PERMISSIV'"
            if cfg.m6l_modus == "DORMANT_PERMISSIV" else "_zv(k)")
    g_q = ("_zv(k) or cfg.rand_modus == 'ENDOGEN'"
           if cfg.rand_modus == "ENDOGEN" else "_zv(k)")
    paare = (
        ("A_UEB1",
         "            if dist > cfg.max_sweep_ueberdehnung_pct:",
         "            if dist > _ueb(k):"),
        ("A_VC",
         "        ex_hi = float(np.max(hi[:k + 1]))\n"
         "        ex_lo = float(np.min(lo[:k + 1]))",
         "        _q0 = 0\n"
         f"        if {g_q}:\n"
         "            _q0 = _segment_start(k)\n"
         "        ex_hi = float(np.max(hi[_q0:k + 1]))\n"
         "        ex_lo = float(np.min(lo[_q0:k + 1]))"),
        ("A_M6L",
         "            if e is kd or not _existiert(e, k):\n"
         "                continue",
         f"            if e is kd or not _existiert(e, k) or (\n"
         f"                    {g_m6} and not _lebt(e, k)):\n"
         "                continue"),
        ("A_SB",
         "        if not e.ist_aktiv_bei(k):\n"
         "            return False\n"
         "        return e.erster_pivot_bar + 2 <= k + 1",
         "        if not e.ist_aktiv_bei(k):\n"
         "            _ev = ((hi[k] > e.basis_bei(k)) if e.seite == \"OBEN\"\n"
         "                   else (lo[k] < e.basis_bei(k)))\n"
         f"            if not (({g_sb}) and _ev):\n"
         "                return False\n"
         "        return e.erster_pivot_bar + 2 <= k + 1"),
    )
    for _nm, _alt, _neu in paare:
        n = src.count(_alt)
        if n != 1:
            raise RuntimeError(f"ZP-4-Regelanker '{_nm}' nicht eindeutig ({n}).")
        src = src.replace(_alt, _neu)
    return src


def _zv_lokal(kk: int) -> bool:
    """Segment-lokales Gate.

    Args:
        kk: Bar-Index.

    Returns:
        True gdw. >1 Segmentgrenze vorliegt, ``kk`` in der Zone
        ``[seg1.start, segN.end]`` liegt und ``kk`` nicht im Ankersegment
        (Index 0, P9) liegt.
    """
    if len(_SEGMENTGRENZEN) <= 1:
        return False
    if not (_SEGMENTGRENZEN[1].start_bar <= kk <= _SEGMENTGRENZEN[-1].end_bar):
        return False
    s0 = _SEGMENTGRENZEN[0]
    return not (s0.start_bar <= kk <= s0.end_bar)


def _segment_start(kk: int) -> int:
    """Startbar des Segments, das ``kk`` enthaelt (sonst 0)."""
    for g in _SEGMENTGRENZEN:
        if g.start_bar <= kk <= g.end_bar:
            return int(g.start_bar)
    return 0


class _GrenzenShim:
    """Minimal-Adapter: macht ``Segmentgrenzen`` fuer den verbatim-Rumpf lesbar.

    ``erweitere_segmentwand_dochte`` liest ``hook.segmente``; der Rumpf wird
    NICHT angepasst, sondern die Daten werden passend dargereicht (G4).
    """

    def __init__(self, grenzen: Sequence[Segmentgrenze]) -> None:
        self.segmente: Tuple[Segmentgrenze, ...] = tuple(grenzen)


def _baue_ns(engine: Any, cfg: Any) -> Dict[str, Any]:
    """Frischer Ausfuehrungs-Namespace (kein geteilter Zustand zwischen Laeufen).

    Enthaelt die AST-extrahierten ZP-Helfer plus die in-modul definierten
    Ersatzstuecke (``_zv``, ``_segment_start``), die den ``_hook``-Bezug des
    Renderers adapterfrei ersetzen.
    """
    _pruefe_anker()
    quell_renderer = RENDERER_PFAD.read_text(encoding="utf-8")
    quell_basis = BASELINE_PFAD.read_text(encoding="utf-8")
    tree = ast.parse(quell_basis)
    node = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "_se_trades")
    enginesrc = ast.get_source_segment(quell_basis, node)
    if not enginesrc:
        raise RuntimeError("_se_trades nicht segmentierbar.")

    zp_src = _ueberdehnung_binden(_extrahiere(
        quell_renderer, ("_ueb", "_reclaim_stufe_lok",
                         "erweitere_segmentwand_dochte")))
    ns: Dict[str, Any] = dict(engine.__dict__)
    ns.update({
        "cfg": cfg,
        "engine": engine,
        "np": np,
        "copy": copy,
        "dataclasses": dataclasses,
        "Callable": __import__("typing").Callable,
        "Sequence": __import__("typing").Sequence,
        "_zv": _zv_lokal,
        "_segment_start": _segment_start,
        "_RS_ORIG": engine._reclaim_stufe,
        "_SEG_SHIM": _GrenzenShim(_SEGMENTGRENZEN),
    })
    exec(compile("from __future__ import annotations\n" + zp_src,
                 "<v021_zp_helper>", "exec"), ns)
    ns["_src_baseline"] = enginesrc
    return ns


# ================================================= D) Der Motor
def _se_trades_v021(scan: Dict[str, Any],
                    cfg: V021KantenKonfiguration,
                    segmentgrenzen: Sequence[Segmentgrenze] = ()
                    ) -> Tuple[List[Any], Dict[str, Any]]:
    """Regel-2-Trades der V021-Engine -- ein Aufruf = eine Einwegfunktion.

    Args:
        scan: Scan-Dict der Baseline (10 Schluessel). Wird NIE mutiert; es gilt
            ``copy.deepcopy(scan)`` als erste Anweisung.
        cfg: 12-Punkte-Vertrag.
        segmentgrenzen: Passive Segmentgrenzen (Beschluss G4). Pflicht bei
            ``segmentwand_modus="AN"`` (fail-loud), verboten bei ``"AUS"``.

    Returns:
        ``(setups, stats)`` -- gleiche Form wie die Baseline-Rueckgabe.

    Raises:
        ValueError: inkonsistente Paarung Modus/Segmentgrenzen oder
            Teilbelegung des Tripels.
        RuntimeError: Fremdstand einer der drei Quellen (SHA-Guard).
    """
    # --- Vertragspruefung VOR jeder Arbeit (kein stiller No-Op) ------------
    if cfg.segmentwand_modus == "AN" and len(segmentgrenzen) <= 1:
        raise ValueError(
            "segmentwand_modus='AN' verlangt >1 Segmentgrenze "
            f"(erhalten: {len(segmentgrenzen)}).")
    if cfg.segmentwand_modus == "AUS" and segmentgrenzen:
        raise ValueError(
            "segmentwand_modus='AUS' vertraegt keine Segmentgrenzen "
            f"(erhalten: {len(segmentgrenzen)}).")
    if cfg.hat_tripel_teilbelegung:
        raise ValueError(
            "Tripel-Teilbelegung nicht definiert: S2/S3/S4 sind in V020 "
            "unbedingt verdrahtet. Bitte alle drei setzen "
            "(NATIV + DORMANT_PERMISSIV + ENDOGEN) oder keinen.")

    global _SEGMENTGRENZEN
    _SEGMENTGRENZEN = tuple(segmentgrenzen)
    try:
        # --- READ-ONLY-GARANTIE (nicht abschaltbar): vollstaendige Kapsel ---
        sc: Dict[str, Any] = copy.deepcopy(scan)
        wcfg = _wirksame_cfg(cfg)

        # --- PFAD 1: Tripel -> bit-exakte V020-Delegation ------------------
        if cfg.ist_tripel:
            # Bit-Exaktheit per Konstruktion: der V020-Motor laeuft mit SEINER
            # eigenen Konfiguration (Vorgabe V020-A, hook=None, keine
            # Wertedomaene). Die V021-Vertragsfelder wirken in diesem Pfad
            # nicht -- das ist der Preis der exakten Replikation.
            # Wichtig: das zweite Argument ist die HARNESS-Config (der Motor
            # liest daraus u. a. ``doppeltop_puffer_usd``); die V020-Felder
            # liegen in ``self.cfg``.
            V = _v020()
            eng = V.V020KantenEngine(hook=None, wertedomaene=None,
                                     cfg=V.V020KantenKonfiguration())
            return eng._se_trades_v020(sc, wcfg)

        B = _engine()

        # --- PFAD 3: Legacy -> Baseline bit-identisch per Konstruktion -----
        if cfg.ist_legacy:
            return B._se_trades(sc, wcfg)

        # --- PFAD 2: Segmentwand -- eigenes, adapterfreies ZP-4/5 ----------
        ns = _baue_ns(B, wcfg)
        ns["_SEG_SHIM"] = _GrenzenShim(segmentgrenzen)
        patched = _regel_ersetzen(ns["_src_baseline"], cfg)
        exec(compile(patched, "<se_trades_v021>", "exec"), ns)
        if cfg.segmentwand_modus == "AN":
            # Reihenfolge INTERN (I5): deepcopy -> Vorlauf -> Handel.
            ns["erweitere_segmentwand_dochte"](
                sc, ns["_SEG_SHIM"], wcfg,
                sc["d"]["high"].to_numpy(dtype=float),
                sc["d"]["low"].to_numpy(dtype=float),
                ns["_ueb"])
        orig = B._se_trades
        B._se_trades = ns["_se_trades"]
        try:
            return B._se_trades(sc, wcfg)
        finally:
            B._se_trades = orig
    finally:
        _SEGMENTGRENZEN = ()


def _lauf(scan: Dict[str, Any], cfg: V021KantenKonfiguration,
          grenzen: Sequence[Segmentgrenze] = (),
          box_end: Optional[int] = None) -> List[Any]:
    """Bequemer Einzellauf: liefert nur die Setups (Kopf fuer Sonden/Renderer).

    Args:
        scan: Scan-Dict der Baseline. Wird kopiert (read-only).
        cfg: 12-Punkte-Vertrag.
        grenzen: Passive Segmentgrenzen.
        box_end: Optionaler ``box_end_bar``-Override (z. B. ``n`` fuer den
            Voll-Lauf; Renderer-Konvention).

    Returns:
        Liste der ``_SESetup``.
    """
    sc = copy.deepcopy(scan)
    if box_end is not None:
        sc["box_end_bar"] = int(box_end)
    setups, _ = _se_trades_v021(sc, cfg, grenzen)
    return list(setups)


__all__ = ["Segmentgrenze", "V021KantenKonfiguration", "_se_trades_v021",
           "_lauf", "BasisModus", "GegenkanteModus", "ExistenzModus",
           "M6LModus", "RandModus", "SegmentwandModus", "ScanReadOnlyModus"]
