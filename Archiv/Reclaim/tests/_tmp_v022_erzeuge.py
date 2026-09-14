# -*- coding: utf-8 -*-
"""Erzeuger fuer ``test/tmp_kanten_engine_v022_replay.py`` (Schritt 2).

Prinzip: Der Trade-Loop wird NICHT neu getippt, sondern ZEILEN-VERBATIM aus der
arretierten Baseline uebernommen. Jeder Eingriff ist einzeln gezaehlt und
assertiert -- ein einziger unerwarteter Treffer bricht den Lauf ab.

Vier (4) Eingriffe, alle mechanisch:

  E1  G4/Hook-3-Block entfernen          Baseline Z2753..2838 (86 Zeilen).
                                          Z2750/2751 (Hauptappend) BLEIBEN.
  E2  `_gegenkante` (verschachtelte Closure Z2597..2611) wird als
      Modul-Funktion `_gegenkante_v022` gefuehrt; `seite_edges` wird
      Parameter. Aufrufstelle Z2672 entsprechend.
  E3  Zielraum-Mindestabstand: Modulkonstante `V3_TP_MINDIST_PCT` (Z2681/2689)
      -> Vertragsfeld `cfg.tp_mindist_pct` (2 Treffer, Default identisch 1.5).
  E4  Harness-Config wird injiziert: alle Rumpfzugaenge `cfg.<engine_feld>`
      und das blanke `cfg` an `_reclaim_stufe` lesen `hcfg`;
      `scan = copy.deepcopy(scan)` als erste Rumpfanweisung (M1).

Kein Motorlauf, keine Baseline-Aenderung. Ausgabe: das V022-Modul + Kurzreport.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

TEST = Path(__file__).resolve().parent
BASELINE = TEST / "tmp_kanten_engine_replay.py"
ZIEL = TEST / "tmp_kanten_engine_v022_replay.py"

BASELINE_SHA_SOLL = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")

# --- Zeilengrenzen (1-basiert, inklusiv) -----------------------------------
FN_DEF, FN_END = 2409, 2845          # def _se_trades .. return setups, stats
G4_VON, G4_BIS = 2753, 2838          # E1
GK_DEF, GK_END = 2597, 2611          # E2 (def _gegenkante .. return min(...))
DOC_ENDE = 2423                      # """ (Abschluss des Funktions-Docstrings)
CALLSITE = 2672                      # geg = _gegenkante(richtung, k)

# ============================================================ 0) Anker
ist = hashlib.sha256(BASELINE.read_bytes()).hexdigest()
assert ist == BASELINE_SHA_SOLL, f"Baseline-Fremdstand: {ist}"
print(f"Baseline-Anker  OK  {ist[:16]}...  {BASELINE.stat().st_size} B")

roh = BASELINE.read_text(encoding="utf-8")
zeilen = roh.splitlines()
print(f"Baseline        {len(zeilen)} Zeilen")

# --- Grenzen belegen -------------------------------------------------------
assert zeilen[FN_DEF - 1].startswith("def _se_trades(scan: Dict, cfg:"), \
    zeilen[FN_DEF - 1]
assert zeilen[FN_END - 1].strip() == "return setups, stats", zeilen[FN_END - 1]
_g4kopf = zeilen[G4_VON - 1]
assert _g4kopf.lstrip().startswith("# --- v0.20: Phasenboden-Regel"), _g4kopf
assert zeilen[G4_BIS - 1].strip() == "r2=_tr_g4.r2))", zeilen[G4_BIS - 1]
assert zeilen[G4_VON - 1].startswith("    #"), "G4-Anfang nicht indent 4"
assert zeilen[G4_VON - 2].strip() == "", "Leerzeile vor G4 fehlt"
assert zeilen[G4_BIS].startswith('    stats["promotionen"]'), zeilen[G4_BIS]
assert zeilen[G4_BIS - 1].startswith("                    r2="), "G4-Ende falsch"
_gkkopf = zeilen[GK_DEF - 1]
assert _gkkopf.lstrip().startswith("def _gegenkante(richtung"), _gkkopf
assert zeilen[GK_END - 1].strip().startswith("return min(pool"), \
    zeilen[GK_END - 1]
assert zeilen[DOC_ENDE - 1].strip() == '"""', zeilen[DOC_ENDE - 1]
assert zeilen[DOC_ENDE].strip() == 'd = scan["d"]', zeilen[DOC_ENDE]
assert zeilen[CALLSITE - 1].strip() == "geg = _gegenkante(richtung, k)", \
    zeilen[CALLSITE - 1]
print("Alle 8 Grenzmarken belegt")

# ============================================================ 1) Extraktion
rumpf = zeilen[FN_DEF - 1:FN_END]
print(f"E0 Extraktion   Z{FN_DEF}..Z{FN_END}  = {len(rumpf)} Zeilen")

assert sum("globals().get(\"_hook\")" in z for z in rumpf) == 1
assert sum("V3_TP_MINDIST_PCT" in z for z in rumpf) == 2
assert sum("_gegenkante(richtung, k)" in z for z in rumpf) == 1
print("    Vorpruefung: globals().get=_hook 1x, V3_TP 2x, Aufruf 1x")

# --- E1: G4-Block entfernen (relativ zum Rumpf) ----------------------------
o = G4_VON - FN_DEF                     # 0-basierter Offset im Rumpf
n = G4_BIS - G4_VON + 1                 # 86
rumpf_e1 = rumpf[:o] + rumpf[o + n:]
assert len(rumpf) - len(rumpf_e1) == 86
assert "globals().get(\"_hook\")" not in "\n".join(rumpf_e1)
assert "_g4" not in "\n".join(rumpf_e1), "G4-Rest gefunden"
assert rumpf_e1[o - 2].strip() == "setups.append(setup)", rumpf_e1[o - 2]
assert rumpf_e1[o - 1].strip() == "", "Leerzeile Z2752 verloren"
assert rumpf_e1[o].startswith('    stats["promotionen"]'), rumpf_e1[o]
print(f"E1 G4-Loeschung 86 Zeilen entfernt; Hauptappend Z2751 gerettet")

# --- E2a: `_gegenkante`-Closure aus dem Rumpf entfernen --------------------
og = GK_DEF - FN_DEF
ng = GK_END - GK_DEF + 1                # 15
rumpf_e2 = (rumpf_e1[:og] + rumpf_e1[og + ng:])
assert len(rumpf_e1) - len(rumpf_e2) == 15
assert "def _gegenkante(richtung" not in "\n".join(rumpf_e2)
print("E2a Closure Z2597..2611 aus dem Rumpf entfernt (15 Zeilen)")

# --- E2c: Funktionkopf isolieren (sonst frisst der cfg-Swap sein `cfg:`) ---
alt_def = ('def _se_trades(scan: Dict, cfg: StraightEdgeHarnessKonfiguration\n'
           '               ) -> Tuple[List[_SESetup], Dict[str, int]]:')
neu_def = ('def _se_trades_v022(scan: Dict[str, Any], cfg: V022KantenKonfiguration,\n'
           '                    harness_cfg: Optional[Any] = None) -> SeErgebnis:')
assert "\n".join(rumpf_e2[:2]) == alt_def, "\n".join(rumpf_e2[:2])
text = "\n".join(rumpf_e2[2:])          # Rumpf OHNE Kopfzeilen
print("E2c Funktionkopf isoliert (2 Zeilen)")

# --- E2b: Aufrufstelle umschreiben (genau 1x) ------------------------------
alt_call = "geg = _gegenkante(richtung, k)"
neu_call = "geg = _gegenkante_v022(seite_edges, k, richtung)"
assert text.count(alt_call) == 1
text = text.replace(alt_call, neu_call)

# --- E3: Platzhalter-Tausch (vor dem cfg->hcfg-Swap!) ----------------------
PH = "___TP_MINDIST___"
assert text.count("V3_TP_MINDIST_PCT") == 2
text = text.replace("V3_TP_MINDIST_PCT", PH)

# --- E4: Harness-Config-Zugaenge auf hcfg ----------------------------------
anz_cfg = len(re.findall(r"\bcfg\b", text))
text = re.sub(r"\bcfg\b", "hcfg", text)
assert len(re.findall(r"\bhcfg\b", text)) == anz_cfg, "Swap nicht total"

# --- E3b: Platzhalter -> Vertragsfeld --------------------------------------
assert text.count(PH) == 2
text = text.replace(PH, "cfg.tp_mindist_pct")

_tok = re.findall(r"\bcfg\b", text)
assert len(_tok) == 2, f"erwartet 2 cfg-Token, gefunden {len(_tok)}"
assert text.count("cfg.tp_mindist_pct") == 2
assert "hcfg.tp_mindist_pct" not in text

# Der harte Nachweis: der Rumpf liest EXAKT diese 13 Engine-Felder.
# (Das 14. Feld ``doppeltop_puffer_usd`` wird INNERHALB von ``_reclaim_stufe``
#  aus demselben hcfg-Objekt gelesen -- ausserhalb dieser Textdatei.)
HCFG_FELDER = {
    "wall_live_bars", "quartil_distanz_pct", "max_seed_distanz_pct",
    "min_wall_alter_bars", "touch_band_pct", "sweep_mindestdurchstich_pct",
    "max_sweep_ueberdehnung_pct", "min_touches_handelbar", "sl_buffer_usd",
    "retest_zyklus_bars", "num_bins", "tp1_anteil_pct",
    "max_gleichzeitig_je_richtung",
}
_felder = set(re.findall(r"\bhcfg\.(\w+)", text))
assert _felder == HCFG_FELDER, f"Feldabweichung: {_felder ^ HCFG_FELDER}"
print(f"E3 Vertragsfeld  2x V3_TP_MINDIST_PCT -> cfg.tp_mindist_pct")
print(f"E4 Harness-Cfg   {anz_cfg}x cfg-Token -> hcfg, "
      f"{len(_felder)} Engine-Felder belegt")

text = neu_def + "\n" + text

# --- Docstring-Delta (ergaenzend, NICHT ueberschreibend) -------------------
alt_doc = ('    Nur in der Box (bars < box_end_bar).\n    """\n')
delta = (
    '    Nur in der Box (bars < box_end_bar).\n'
    '\n'
    '    --- V022-Delta gegenueber dem verbatim uebernommenen Rumpf -------\n'
    '    (1) ``scan = copy.deepcopy(scan)`` als erste Rumpfanweisung (M1:\n'
    '        der Motor mutiert Kantenobjekte; bisher musste der AUFRUFER\n'
    '        kopieren).\n'
    '    (2) Zielraum-Mindestabstand: die Baseline-Modulkonstante\n'
    '        ``V3_TP_MINDIST_PCT`` (Z2681/Z2689) wird zum Vertragsfeld\n'
    '        ``cfg.tp_mindist_pct``. Default identisch (1.5) -- der\n'
    '        Paritaetswaechter ``pruefe_paritaet`` belegt das.\n'
    '    (3) Der G4/Hook-3-Block (Baseline Z2753..2838) entfaellt restlos:\n'
    '        kein ``globals().get("_hook")``, kein zweiter Append. Der\n'
    '        Hauptappend (Z2750/Z2751) bleibt unberuehrt.\n'
    '    (4) ``_gegenkante`` wird als ``_gegenkante_v022`` auf Modulebene\n'
    '        gefuehrt; ``seite_edges`` ist Parameter statt Closure. Der\n'
    '        Rumpf bleibt verbatim, die Reihenfolge unveraendert (B4).\n'
    '    (5) Die Harness-Konfiguration wird INJIZIERT (``harness_cfg``).\n'
    '        Alle Rumpfzugaenge lesen ``hcfg`` -- 14 Engine-Felder.\n'
    '        Damit bleibt der 1-Feld-Vertrag gewahrt und ``Q29``\n'
    '        (``quartil_distanz_pct``) fuer die Parameter-Sonde F24\n'
    '        steuerbar.\n'
    '    """\n')
assert text.count(alt_doc) == 1
text = text.replace(alt_doc, delta)

# --- Deepcopy + hcfg-Aufloesung als erste Rumpfanweisung -------------------
alt_first = '    """\n    d = scan["d"]\n'
neu_first = (
    '    """\n'
    '    # --- READ-ONLY-GARANTIE (nicht abschaltbar) ------------------------\n'
    '    scan = copy.deepcopy(scan)\n'
    '    hcfg = (harness_cfg if harness_cfg is not None\n'
    '            else _engine().StraightEdgeHarnessKonfiguration())\n'
    '    d = scan["d"]\n')
assert text.count(alt_first) == 1
text = text.replace(alt_first, neu_first)
print("Rumpf-Kopf: deepcopy + hcfg-Injektion eingefuegt")

# --- E5: KONSERVIERUNGSVERMERK am Halbraum-Zweig (G7, Erratum K7a) ---------
alt_hb = ('            gegen_basis = geg.basis_bei(k)\n'
          '            if richtung == "SHORT":\n')
neu_hb = (
    '            gegen_basis = geg.basis_bei(k)\n'
    '            # --- Halbraum-Tripwire (Erratum K7a) -----------------------\n'
    '            # KONSERVIERUNGSVERMERK (H20.53 Paragraph 1a): 0 Bindungen in\n'
    '            # 5/5 Fenstern -- NICHT inert, sondern KONSERVIERT. Die\n'
    '            # Gegenkante mit GEGENKANTE_MODUS="EXTREM" garantiert die\n'
    '            # zulaessige Seite strukturell. Der Halbraum ist die\n'
    '            # Bindungs-NULLINIE dieser Invariante: faellt er auf 0 zu\n'
    '            # bleiben aus, ist die Zielwahl gekippt (Beleg: Erratum K3,\n'
    '            # 22/84 Zeilen unter NAECHSTE). Beide Zweige sind ECHTER Code\n'
    '            # und bleiben echte Zweige -- kein Vorab-Filter (B4).\n'
    '            if richtung == "SHORT":\n')
assert text.count(alt_hb) == 1, text.count(alt_hb)
text = text.replace(alt_hb, neu_hb)
print("E5 KONSERVIERUNGSVERMERK am Halbraum-Zweig eingefuegt")

# ============================================================ 2) _gegenkante_v022
gk_quelle = zeilen[GK_DEF:GK_END + 1]              # ohne die def-Zeile
gk_rumpf = []
for z in gk_quelle[1:]:                            # ab Docstring
    gk_rumpf.append(z[4:] if z.startswith("    ") else z)
gk_funktion = (
    'def _gegenkante_v022(seite_edges: Dict[Any, List[Any]], k: int,\n'
    '                     richtung: Richtung) -> Optional[Any]:\n'
    + "\n".join(gk_rumpf) + "\n")
assert "seite_edges[gegenseite]" in gk_funktion
assert "max(pool, key=lambda e: e.basis_bei(k))" in gk_funktion
assert "min(pool, key=lambda e: e.basis_bei(k))" in gk_funktion
assert "def _gegenkante_v022(seite_edges" in gk_funktion
print("E2b _gegenkante_v022 auf Modulebene erzeugt (Rumpf verbatim, dedent 4)")

# ============================================================ 3) Modul zusammensetzen
KOPF = '''# -*- coding: utf-8 -*-
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


'''

TEXT = KOPF + gk_funktion + "\n\n" + text + "\n"

# ============================================================ 4) Schlusskontrolle
# Die Prosa (Modul-Docstring, Delta-Vermerke) NENNT die entfernten Dinge
# absichtlich. Geprueft wird deshalb nicht der Text, sondern der CODE:
# alle Bezeichner (ast.Name/ast.Attribute) muessen frei von Altlasten sein.
import ast  # noqa: E402

baum = ast.parse(TEXT)
_namen = {n.id for n in ast.walk(baum) if isinstance(n, ast.Name)}
_attrs = {n.attr for n in ast.walk(baum) if isinstance(n, ast.Attribute)}
_ident = _namen | _attrs

_verboten_namen = {"_hook", "globals", "V3_TP_MINDIST_PCT", "_SEGMENTGRENZEN",
                   "segmentgrenzen", "segmentwand_modus", "atr_h1"}
_schlag = _namen & _verboten_namen
assert not _schlag, f"Altlast als freier Name: {sorted(_schlag)}"
_schlag_a = _attrs & {"_hook", "_SEGMENTGRENZEN", "segmentgrenzen",
                      "segmentwand_modus", "atr_h1"}
assert not _schlag_a, f"Altlast als Attribut: {sorted(_schlag_a)}"
# Einzige erlaubte Nennung im Code: der Paritaetswaechter (F39) vergleicht
# gegen die Baseline-Konstante -- genau EINMAL, ueber das uebergebene B.
assert TEXT.count("float(B.V3_TP_MINDIST_PCT)") == 1, \
    "Waechterzugriff nicht genau 1x im Code"
_g4 = sorted(x for x in _ident if x.endswith("_g4"))
assert not _g4, f"G4-Rest im CODE: {_g4}"
assert "exec" not in _namen, "exec im Code"
assert "globals" not in _namen, "globals() im Code"

assert TEXT.count("def _se_trades_v022(") == 1
assert TEXT.count("def _gegenkante_v022(") == 1
assert text.count("    scan = copy.deepcopy(scan)\n") == 1, \
    "deepcopy nicht genau 1x im Rumpf"
assert TEXT.count("return setups, stats") == 1
assert TEXT.count("stats[\"kein_raum\"] += 1") == 8
assert TEXT.count("stats[\"concurrency_blockiert\"] += 1") == 1, \
    "G4-Doppelzaehler ueberlebt"
print("Schlusskontrolle (AST): keine Altlast-Bezeichner, kein globals()/exec,")
print("                        8 kein_raum-Stellen, 1 concurrency-Stelle")
assert TEXT.count("KONSERVIERUNGSVERMERK") == 1, "G7-Vermerk fehlt"
assert TEXT.count("FALSIFIKATIONSVERMERK") == 1, "K7b-Vermerk fehlt"
print("Vermerke (K7a/K7b): KONSERVIERUNGSVERMERK 1x, FALSIFIKATIONSVERMERK 1x")

ZIEL.write_text(TEXT, encoding="utf-8", newline="\n")
neu = ZIEL.read_bytes()
print()
print(f"GESCHRIEBEN  {ZIEL.name}  {len(neu)} B  "
      f"SHA256 {hashlib.sha256(neu).hexdigest()}")
print(f"             {len(TEXT.splitlines())} Zeilen")
