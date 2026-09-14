# -*- coding: utf-8 -*-
"""READ-ONLY Zulassungs-Funnel-Sonde (L6 + L7) -- Telemetrie der Gate-Kette.

Auftrag (Anwender, 14.09.2026, Beschluesse L6/L7 + N1-N7/O1-O7)
-------------------------------------------------------------
Zwei Fragen, EIN Durchlauf:

    L6  Wie oft und WARUM verwirft der Zielraum?
        ``stats["kein_raum"]`` aggregiert 8 Code-Stellen / 5 Ursachen
        (Halbraum, Mindestabstand, POC-Band, Ordnung, Risk) und ist als
        nackte Zahl eine Blackbox (Befund M6).

    L7  Warum feuert JUN 28/28 LONG in einem fallenden Monat (0 SHORT)?
        Die Zulassungskette hat 6 unbewachte Abbruch-Ursachen, die ``stats``
        nicht zaehlt (Befund M7).

VERFAHREN (N2/O2): Der Quelltext der ORIGINAL-``_se_trades`` wird per AST
extrahiert und VERBATIM ausgefuehrt; eingefuegt werden ausschliesslich
Zaehler ``_c("<site>", richtung)``. Eine freie Nachrechnung ist unzulaessig:
``letzter_sweep_bar`` (Z2733, nur bei genommenem Trade fortgeschrieben),
``getradete_entry_bars`` (Z2729) und die Concurrency-Sperre (Z2722-2728)
machen die Ablehnung eines Bares vom Ausgang der VORHERIGEN Bares abhaengig.
Nur die Ausfuehrung des echten Codes ist zustandstreu.

ZWEI INSTRUMENTIERUNGSZIELE (N6/O3)
-----------------------------------
    T1  ``_se_trades`` verbatim aus ``tmp_kanten_engine_replay.py``
        -> MAI, JUN, JUL, AUG_BASE
    T2  gepatchte Kette ``V._baue_ns -> V._regel_ersetzen -> Instrumentierung``
        -> AUG_WAND

T2 ist zwingend, weil ``segmentwand_modus="AN"`` NICHT durch die Baseline
laeuft: ``_se_trades_v021`` baut einen frischen Namespace, ersetzt vier
Regeln im Quelltext (A_UEB1/A_VC/A_M6L/A_SB) und fuehrt den gepatchten Text
aus. A_UEB1 ueberschreibt dabei Z2586 (``if dist > cfg.max_sweep_ueberdehnung
_pct:`` -> ``if dist > _ueb(k):``). Alle Anker sind deshalb INHALTS-Snippets
am unveraenderten Terminal, nie Zeilennummern (O2).

BUDGETIDENTITAET (N1/O4) -- fail-loud, kein Protokoll bei Verletzung
-------------------------------------------------------------------
    (I)   eintritt(richtung) == Summe aller Ausgaenge dieser Richtung
    (II)  eintritt(richtung) == box_end - 5      [range(2, box_end - 3)]
    (III) kand_none == pool_leer + lebende_wand + ueberdehnung + erschoepft
    (IV)  stats["kein_raum"] == Summe der 8 zerlegten Stellen (Fenster-Total,
          weil ``stats`` NICHT richtungsgetrennt zaehlt)
    (V)   die Summe der gebundenen Anker == ihr stats-Wert (+ ``v_s``)

Statisch nachgeprueft (AST, siehe ``test/_tmp_ausgang_probe.py``):
``_se_trades`` hat in der ``richtung``-Schleife **17 Ausgaenge + 1 Erfolg**
(``setups.append``) -- jeder Ausgang ist instrumentiert, und ``_kandidat``
liefert an **genau 4** Stellen ``None`` (Z2578/2584/2587/2595). Damit sind
(I) und (III) strukturell geschlossen, nicht nur empirisch. Die
G4-Doppelzaehlung ist in ``test/_tmp_stats_probe.py`` nachgewiesen.

G4-DOPPELZAEHLUNG (V): Der Hook-3-Block (Z2762-2838) laeuft NACH der
k-Schleife und schreibt in DIESELBEN ``stats``-Schluessel
(``concurrency_blockiert``) bzw. an ``setups`` (Z2824). Er wird deshalb
getrennt gezaehlt (``g4_concurrency``/``g4_accept``, NICHT im Budget) und in
(V) mit der Hauptloop zusammen gerechnet. Ohne diese Trennung waere (V)
falsch-positiv. Nebenbefund: die Baseline definiert kein Modul-globales
``_hook`` und ``V._baue_ns`` setzt keines -- G4 ist in der Sonde strukturell
inert (messbar als ``G4 == 0``).

Verschwindet ein Setup im Niemandsland, bricht die Sonde ab. (IV) und (V)
vergleichen gegen die EIGENE Zaehlung des Motors -- die Sonde ist damit
selbstpruefend.

CAVEAT (O5, verschaerft): ``stats["v_s"] = len(setups)`` (Z2840) schliesst
den G4-Anhang ein. Da beide Append-Stellen gezaehlt werden, wird jetzt die
GLEICHHEIT ``accept + g4_accept == v_s`` geprueft -- die alte Ungleichung
``accept <= v_s`` ist darin enthalten.

GRENZE: Die Sonde beantwortet "WO wird verworfen", NICHT "was soll anders
sein". Kein Wert darf ohne Freigabe in einen Motor wandern.

Aufruf:
    .venv\\Scripts\\python.exe test\\_chk_zulassung_funnel.py
    .venv\\Scripts\\python.exe test\\_chk_zulassung_funnel.py --nur-anker
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
V021_PFAD = ROOT / "test" / "tmp_kanten_engine_v021_replay.py"
ADAPTER_PFAD = ROOT / "backtest_lab" / "phasen_regime_adapter.py"

BASELINE_SHA = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
V021_SHA = (
    "cda9e5b189ed4137198795e1547cec00436dffe64222434bb6ec4c448e598e89")
ADAPTER_SHA = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")

OUT = ROOT / "test" / "_chk_zulassung_funnel_out.txt"

FensterId = Literal["MAI", "JUN", "JUL", "AUG_BASE", "AUG_WAND"]
Richtung = Literal["SHORT", "LONG"]
RICHTUNGEN: Tuple[Richtung, ...] = ("SHORT", "LONG")

# (Id, Ziel, start, ende, SOLL_Trades, SOLL_SumR)   -- "AUG" = Fenstername
FENSTER: Tuple[Tuple[str, str, str, str, int, float], ...] = (
    ("MAI", "T1", "2026-05-01", "2026-06-01", 35, 38.318126),
    ("JUN", "T1", "2026-06-01", "2026-07-01", 28, -11.421155),
    ("JUL", "T1", "2026-07-01", "2026-08-01", 21, -4.325355),
    ("AUG_BASE", "T1", "AUG", "AUG", 14, 42.450970),
    ("AUG_WAND", "T2", "AUG", "AUG", 18, 52.876174),
)
SOLL_H1 = (8, 38.919584)      # AUG_WAND, entry_bar <  KALENDERKANTE
SOLL_H2 = (10, 13.956589)     # AUG_WAND, entry_bar >= KALENDERKANTE
KALENDERKANTE = 644


# ======================================================= A) Die 29 Anker (O2)
# Jeder Anker MUSS genau 1x im Quelltext vorkommen (fail-loud). Die Ersetzung
# fuegt AUSSCHLIESSLICH eine Zaehlerzeile ein -- nichts wird umgeschrieben.
ANKER: Tuple[Tuple[str, str, str], ...] = (
    # --- 1) Budgetanker -----------------------------------------------------
    ("eintritt",
     '            sweep_px = float(hi[k]) if richtung == "SHORT" '
     'else float(lo[k])',
     '            sweep_px = float(hi[k]) if richtung == "SHORT" '
     'else float(lo[k])\n'
     '            _c("eintritt", richtung)'),
    # --- 2) _kandidat: per-Element-Filter (koennen n x feuern) --------------
    ("kand_frisch",
     '                    stats["frisch_blockiert"] += 1',
     '                    stats["frisch_blockiert"] += 1\n'
     '                    _c("kand_frisch", richtung)'),
    ("kand_dormant",
     '                continue                        # dormante Linie '
     'ignorieren',
     '                _c("kand_dormant", richtung)\n'
     '                continue                        # dormante Linie '
     'ignorieren'),
    ("kand_kein_durchstich",
     '                continue                        # nur Durchstich '
     'zaehlt (Teil 7)',
     '                _c("kand_kein_durchstich", richtung)\n'
     '                continue                        # nur Durchstich '
     'zaehlt (Teil 7)'),
    ("kand_vs_lt3",
     '                continue                        # innere Linie '
     'braucht V-S >= 3',
     '                _c("kand_vs_lt3", richtung)\n'
     '                continue                        # innere Linie '
     'braucht V-S >= 3'),
    # --- 3) _kandidat: Terminals (genau 1 x je k/Richtung) -----------------
    # ACHTUNG: ``if not pool:`` + ``return None`` steht 2x -- Z2577 in
    # ``_kandidat`` und Z2607 in ``_gegenkante``. Ein reiner 2-Zeilen-Anker
    # zaehlt deshalb 2x. Diskriminator ist die FOLGEZEILE: nur in
    # ``_kandidat`` schliesst das Sortieren nach ``basis_bei(k)`` an.
    ("kand_pool_leer",
     '        if not pool:\n'
     '            return None\n'
     '        pool.sort(key=lambda e: e.basis_bei(k), '
     'reverse=(seite == "OBEN"))',
     '        if not pool:\n'
     '            _c("kand_pool_leer", richtung)\n'
     '            return None\n'
     '        pool.sort(key=lambda e: e.basis_bei(k), '
     'reverse=(seite == "OBEN"))'),
    ("kand_lebende_wand",
     '                    return None                 # lebende Wand nicht '
     'erreicht',
     '                    _c("kand_lebende_wand", richtung)\n'
     '                    return None                 # lebende Wand nicht '
     'erreicht'),
    ("kand_ueberdehnung",
     '                return None                     # Ueberdehnung, kein '
     'Reclaim',
     '                _c("kand_ueberdehnung", richtung)\n'
     '                return None                     # Ueberdehnung, kein '
     'Reclaim'),
    ("kand_erschoepft",
     '            return e\n        return None\n',
     '            return e\n'
     '        _c("kand_erschoepft", richtung)\n'
     '        return None\n'),
    ("kand_none",
     '            if kd is None:\n                continue',
     '            if kd is None:\n'
     '                _c("kand_none", richtung)\n'
     '                continue'),
    # --- 4) Gate-Kette -----------------------------------------------------
    ("g_blocker",
     '                stats["blocker"] += 1',
     '                stats["blocker"] += 1\n'
     '                _c("g_blocker", richtung)'),
    ("g_quartil",
     '                stats["quartil_blockiert"] += 1',
     '                stats["quartil_blockiert"] += 1\n'
     '                _c("g_quartil", richtung)'),
    ("g_stufe0",
     '            if stufe_n == 0:\n                continue',
     '            if stufe_n == 0:\n'
     '                _c("g_stufe0", richtung)\n'
     '                continue'),
    ("g_f3",
     '                stats["f3"] += 1',
     '                stats["f3"] += 1\n'
     '                _c("g_f3", richtung)'),
    ("g_zyklus",
     '                stats["zyklus_blockiert"] += 1',
     '                stats["zyklus_blockiert"] += 1\n'
     '                _c("g_zyklus", richtung)'),
    ("g_kein_gegner",
     '                stats["kein_gegner"] += 1',
     '                stats["kein_gegner"] += 1\n'
     '                _c("g_kein_gegner", richtung)'),
    # ACHTUNG: ``stats["concurrency_blockiert"] += 1`` steht 2x -- Z2727
    # (Hauptloop, ``if _offen > ...``) und Z2818 (G4-Hook-3-Kopie,
    # ``if _offen_g4 > ...``). Ein reiner Zeilenanker zaehlt 2x (der
    # 20-Leerzeichen-Text ist Teilstring der 24-Leerzeichen-Zeile).
    # Diskriminator ist die VORZEILE mit der Variablen ``_offen`` (nicht
    # ``_offen_g4``).
    ("g_concurrency",
     '                if _offen > cfg.max_gleichzeitig_je_richtung:\n'
     '                    stats["concurrency_blockiert"] += 1',
     '                if _offen > cfg.max_gleichzeitig_je_richtung:\n'
     '                    stats["concurrency_blockiert"] += 1\n'
     '                    _c("g_concurrency", richtung)'),
    # --- 4b) G4-Hook-3-Block (Z2762-2838) -- AUSSERHALB der k-Schleife ------
    # Er zaehlt aber in DIESELBEN stats-Schluessel. Ohne eigene Zaehler waere
    # (V) fuer ``concurrency_blockiert``/``v_s`` falsch (Doppelzaehlung in
    # ``stats``). Diese beiden Zaehler gehoeren deshalb NICHT ins Budget (I).
    # Diskriminator zur Hauptloop: Variable ``_offen_g4``; ``richtung`` ist im
    # G4-Block nicht definiert -> Literal "LONG".
    ("g4_concurrency",
     '                    if _offen_g4 > cfg.max_gleichzeitig_je_richtung:\n'
     '                        stats["concurrency_blockiert"] += 1',
     '                    if _offen_g4 > cfg.max_gleichzeitig_je_richtung:\n'
     '                        stats["concurrency_blockiert"] += 1\n'
     '                        _c("g4_concurrency", "LONG")'),
    ("g4_accept",
     '                setups.append(_SESetup(',
     '                _c("g4_accept", "LONG")\n'
     '                setups.append(_SESetup('),
    # NEU (N3-Korrektur): der Dedup-Exit war unbewacht.
    ("g_dedup",
     '            if entry_bar in getradete_entry_bars:   # B23-3: Dedup\n'
     '                continue',
     '            if entry_bar in getradete_entry_bars:   # B23-3: Dedup\n'
     '                _c("g_dedup", richtung)\n'
     '                continue'),
    ("accept",
     '            setups.append(setup)',
     '            setups.append(setup)\n'
     '            _c("accept", richtung)'),
    # --- 5) kein_raum, 8-fach zerlegt (L6/O4) ------------------------------
    ("r_halb_short",
     '                if not (gegen_basis < basis):\n'
     '                    stats["kein_raum"] += 1',
     '                if not (gegen_basis < basis):\n'
     '                    _c("r_halb_short", richtung)\n'
     '                    stats["kein_raum"] += 1'),
    ("r_mindist_short",
     '                if abs(basis - gegen_basis) / basis * 100.0 '
     '< V3_TP_MINDIST_PCT:\n'
     '                    stats["kein_raum"] += 1',
     '                if abs(basis - gegen_basis) / basis * 100.0 '
     '< V3_TP_MINDIST_PCT:\n'
     '                    _c("r_mindist_short", richtung)\n'
     '                    stats["kein_raum"] += 1'),
    ("r_halb_long",
     '                if not (gegen_basis > basis):\n'
     '                    stats["kein_raum"] += 1',
     '                if not (gegen_basis > basis):\n'
     '                    _c("r_halb_long", richtung)\n'
     '                    stats["kein_raum"] += 1'),
    ("r_mindist_long",
     '                if abs(gegen_basis - basis) / basis * 100.0 '
     '< V3_TP_MINDIST_PCT:\n'
     '                    stats["kein_raum"] += 1',
     '                if abs(gegen_basis - basis) / basis * 100.0 '
     '< V3_TP_MINDIST_PCT:\n'
     '                    _c("r_mindist_long", richtung)\n'
     '                    stats["kein_raum"] += 1'),
    ("r_poc",
     '            if not (unter < poc < ober):\n'
     '                stats["kein_raum"] += 1',
     '            if not (unter < poc < ober):\n'
     '                _c("r_poc", richtung)\n'
     '                stats["kein_raum"] += 1'),
    ("r_ord_short",
     '                if not (sl > entry > poc > tp2):\n'
     '                    stats["kein_raum"] += 1',
     '                if not (sl > entry > poc > tp2):\n'
     '                    _c("r_ord_short", richtung)\n'
     '                    stats["kein_raum"] += 1'),
    ("r_ord_long",
     '                if not (sl < entry < poc < tp2):\n'
     '                    stats["kein_raum"] += 1',
     '                if not (sl < entry < poc < tp2):\n'
     '                    _c("r_ord_long", richtung)\n'
     '                    stats["kein_raum"] += 1'),
    ("r_risk",
     '            if risk <= 0:\n'
     '                stats["kein_raum"] += 1',
     '            if risk <= 0:\n'
     '                _c("r_risk", richtung)\n'
     '                stats["kein_raum"] += 1'),
)

# Flussrichtung des Codes fuer die Trichteranzeige
SITES_TERMINAL: Tuple[str, ...] = (
    "kand_none", "g_blocker", "g_quartil", "g_stufe0", "g_f3", "g_zyklus",
    "g_kein_gegner", "g_dedup", "g_concurrency", "accept")
SITES_KAND: Tuple[str, ...] = (
    "kand_pool_leer", "kand_lebende_wand", "kand_ueberdehnung",
    "kand_erschoepft")
SITES_KAND_FILTER: Tuple[str, ...] = (
    "kand_frisch", "kand_dormant", "kand_kein_durchstich", "kand_vs_lt3")
SITES_RAUM: Tuple[str, ...] = (
    "r_halb_short", "r_mindist_short", "r_halb_long", "r_mindist_long",
    "r_poc", "r_ord_short", "r_ord_long", "r_risk")
# G4-Hook-3-Nebenweg: NICHT Teil des Budgets (I) -- er laeuft NACH der
# k-Schleife. Er erscheint in den Zaehlern nur, damit (V) exakt bleibt.
SITES_G4: Tuple[str, ...] = ("g4_concurrency", "g4_accept")

# stats-Schluessel -> zaehlende Anker (Summe == stats-Wert). Mehrere Anker je
# Schluessel nur dort, wo der Motor ZWEI Stellen in denselben Schluessel
# zaehlt (concurrency_blockiert: Hauptloop + G4-Block).
STATS_BINDUNG: Dict[str, Tuple[str, ...]] = {
    "frisch_blockiert": ("kand_frisch",),
    "blocker": ("g_blocker",),
    "quartil_blockiert": ("g_quartil",),
    "f3": ("g_f3",),
    "zyklus_blockiert": ("g_zyklus",),
    "kein_gegner": ("g_kein_gegner",),
    "concurrency_blockiert": ("g_concurrency", "g4_concurrency"),
}

# Hypothesen A-F (N5/O6): gleichrangig, kein Vorab-Bias
HYPOTHESEN: Tuple[Tuple[str, str, str], ...] = (
    ("A", "g_quartil", "Quartil Q29 sperrt Mittelkanten (Z2490)"),
    ("B", "kand_lebende_wand", "lebende Aussenwand bricht die Suche ab (Z2584)"),
    ("C", "kand_ueberdehnung", "Ueberdehnungskorridor > 0.60 % (Z2587)"),
    ("D", "g_blocker", "M6 Innenlevel-Blocker (Z2526)"),
    ("E", "g_dedup", "Entry-Bar-Dedup (Z2730, NEU)"),
    ("F", "g_stufe0", "Reclaim-Stufe 0 (Z2641, NEU)"),
)

_KONTEXT: List[str] = ["?"]
ZAHL: Dict[Tuple[str, str, str], int] = {}


def _c(site: str, richtung: str) -> None:
    """Zaehler -- wird in den ausgefuehrten Quelltext injiziert."""
    schluessel = (_KONTEXT[0], site, str(richtung))
    ZAHL[schluessel] = ZAHL.get(schluessel, 0) + 1


def _n(fenster: str, site: str, richtung: str) -> int:
    return int(ZAHL.get((fenster, site, richtung), 0))


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _pruefe_anker(src: str) -> List[str]:
    """O2: jeder Anker genau 1x -- Rueckgabe der Fehlerliste (fail-loud)."""
    return [f"{name}: {src.count(alt)}x (erwartet 1x)"
            for name, alt, _neu in ANKER if src.count(alt) != 1]


def _instrumentiere(src: str) -> str:
    """Fuegt die Zaehler ein. Aendert NICHTS ausser Zaehlerzeilen."""
    for name, alt, neu in ANKER:
        assert src.count(alt) == 1, f"Anker '{name}' nicht eindeutig."
        src = src.replace(alt, neu)
    return src


def _quelle_se_trades() -> str:
    """T1: Quelltextsegment der ORIGINAL-``_se_trades`` (verbatim, AST)."""
    quell = BASELINE_PFAD.read_text(encoding="utf-8")
    for n in ast.parse(quell).body:
        if isinstance(n, ast.FunctionDef) and n.name == "_se_trades":
            seg = ast.get_source_segment(quell, n)
            assert seg, "_se_trades nicht segmentierbar."
            return seg
    raise RuntimeError("_se_trades nicht gefunden.")


# ============================================================ B) Datenvertrag
@dataclass(frozen=True, slots=True)
class TelemetrieBudget:
    """Soll-Ist-Budgetpruefung fuer eine (Fenster, Richtung)-Paarung (O4).

    Zwei Sentinels markieren "auf dieser Ebene nicht pruefbar":

    * ``kein_raum_summe < 0`` -- ``stats["kein_raum"]`` ist NICHT
      richtungsgetrennt; (IV) wird im Fenster-Aggregat geprueft.
    * ``summe_ausgaenge < 0`` (nur Zeile ``TOTAL``) -- (I)/(III) sind
      richtungsdefiniert und haben in der Aggregatzeile keine Bedeutung.
      Ohne diesen Sentinel verglich die Aggregatzeile ``-1`` gegen
      ``eintritt`` und meldete FALSCH-ALARM (Erstlauf 14.09.2026: 5 von 15
      Budgets "verletzt", ausschliesslich die TOTAL-Zeilen -- alle 10
      richtungsgetrennten Budgets waren OK).
    """

    fenster: str
    richtung: str
    box_end: int
    eintritt_ist: int
    eintritt_soll: int
    summe_ausgaenge: int
    kand_none_summe: int
    kand_none_details: int
    kein_raum_summe: int
    kein_raum_details: int
    stats_abweichungen: Tuple[str, ...] = field(default=())

    @property
    def ist_valide(self) -> bool:
        return (self.eintritt_ist == self.eintritt_soll
                and (self.summe_ausgaenge < 0
                     or self.eintritt_ist == self.summe_ausgaenge)
                and (self.kand_none_summe < 0
                     or self.kand_none_summe == self.kand_none_details)
                and (self.kein_raum_summe < 0
                     or self.kein_raum_summe == self.kein_raum_details)
                and not self.stats_abweichungen)

    @property
    def verletzungen(self) -> Tuple[str, ...]:
        v: List[str] = []
        if self.eintritt_ist != self.eintritt_soll:
            v.append(f"(II) eintritt {self.eintritt_ist} != Soll "
                     f"{self.eintritt_soll}")
        if (self.summe_ausgaenge >= 0
                and self.eintritt_ist != self.summe_ausgaenge):
            v.append(f"(I) Summe Ausgaenge {self.summe_ausgaenge} != eintritt "
                     f"{self.eintritt_ist}")
        if (self.kand_none_summe >= 0
                and self.kand_none_summe != self.kand_none_details):
            v.append(f"(III) kand_none {self.kand_none_summe} != Details "
                     f"{self.kand_none_details}")
        if (self.kein_raum_summe >= 0
                and self.kein_raum_summe != self.kein_raum_details):
            v.append(f"(IV) kein_raum {self.kein_raum_summe} != Details "
                     f"{self.kein_raum_details}")
        for a in self.stats_abweichungen:
            v.append(f"(V) {a}")
        return tuple(v)


# ============================================================== C) Lauf-Helfer
def _scan_monat(B: Any, start: str, ende: str) -> Tuple[Dict[str, Any], int]:
    """Kausaler SE-Scan eines Monatsfensters (BKZ, read-only)."""
    B.FENSTER["LAB"] = (start, ende)
    try:
        d = B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]
    n = int(len(d))
    original = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        scan = B._se_scan("LAB", B.StraightEdgeHarnessKonfiguration())
    finally:
        B._lade_fenster = original  # type: ignore
    scan = copy.deepcopy(scan)
    scan["box_end_bar"] = int(n)
    return scan, n


def _grenzen(AD: Any, V: Any) -> List[Any]:
    """Adapter-Segmente -> passive ``Segmentgrenze`` (G4, reine Daten)."""
    PhK = AD.PhasenKanteInfo
    return [V.Segmentgrenze(
        start_bar=int(s.start_bar), end_bar=int(s.end_bar),
        boden=PhK(kid=int(s.boden.kid),
                  provenienz_basis=float(s.boden.provenienz_basis)),
        decke=PhK(kid=int(s.decke.kid),
                  provenienz_basis=float(s.decke.provenienz_basis)),
        boden_deklariert_literal=s.boden_deklariert_literal)
        for s in AD.ADAPTER_V019_KAUSAL.segmente]


def _fuehre_aus(ns: Dict[str, Any], sc: Dict[str, Any], cfg: Any
                ) -> Tuple[List[Any], Dict[str, Any]]:
    """Ruft die instrumentierte ``_se_trades`` aus dem frischen Namespace."""
    ns["_c"] = _c
    exec(compile(ns["_queltext"], "<funnel_se_trades>", "exec"), ns)
    return ns["_se_trades"](sc, cfg)


def _lauf_t1(B: Any, V: Any, fenster: str, scan: Dict[str, Any], box_end: int
             ) -> Tuple[List[Any], Dict[str, Any]]:
    """T1 -- Baseline-``_se_trades`` verbatim, instrumentiert."""
    sc = copy.deepcopy(scan)
    sc["box_end_bar"] = int(box_end)
    cfg = V._wirksame_cfg(V.V021KantenKonfiguration())
    ns = dict(B.__dict__)
    ns["_queltext"] = _instrumentiere(_quelle_se_trades())
    _KONTEXT[0] = fenster
    return _fuehre_aus(ns, sc, cfg)


def _lauf_t2(B: Any, V: Any, fenster: str, scan: Dict[str, Any], box_end: int,
             grenzen: Sequence[Any]) -> Tuple[List[Any], Dict[str, Any]]:
    """T2 -- gepatchte Segmentwand-Kette (A_UEB1/A_VC/A_M6L/A_SB).

    Reihenfolge: Namespace -> Patch -> Instrumentierung -> ZP-5-Vorlauf ->
    Loop (identisch zu ``_se_trades_v021``, nur instrumentiert).
    """
    sc = copy.deepcopy(scan)
    sc["box_end_bar"] = int(box_end)
    cfg = V.V021KantenKonfiguration(segmentwand_modus="AN")
    wcfg = V._wirksame_cfg(cfg)
    V._SEGMENTGRENZEN = tuple(grenzen)
    try:
        ns = V._baue_ns(B, wcfg)
        ns["_SEG_SHIM"] = V._GrenzenShim(grenzen)
        gepatcht = V._regel_ersetzen(ns["_src_baseline"], cfg)
        ns["_queltext"] = _instrumentiere(gepatcht)
        ns["erweitere_segmentwand_dochte"](
            sc, ns["_SEG_SHIM"], wcfg,
            sc["d"]["high"].to_numpy(dtype=float),
            sc["d"]["low"].to_numpy(dtype=float),
            ns["_ueb"])
        _KONTEXT[0] = fenster
        return _fuehre_aus(ns, sc, wcfg)
    finally:
        V._SEGMENTGRENZEN = ()


# ============================================================== D) Auswertung
def _budget(fenster: str, box_end: int, richtung: str) -> TelemetrieBudget:
    """Baut das Budget EINER (Fenster, Richtung)-Paarung -- (I)(II)(III)."""
    eintritt = _n(fenster, "eintritt", richtung)
    kand_none = _n(fenster, "kand_none", richtung)
    kein_detail = sum(_n(fenster, s, richtung) for s in SITES_RAUM)
    ausgaenge = (kand_none
                 + _n(fenster, "g_blocker", richtung)
                 + _n(fenster, "g_quartil", richtung)
                 + _n(fenster, "g_stufe0", richtung)
                 + _n(fenster, "g_f3", richtung)
                 + _n(fenster, "g_zyklus", richtung)
                 + _n(fenster, "g_kein_gegner", richtung)
                 + _n(fenster, "g_dedup", richtung)
                 + _n(fenster, "g_concurrency", richtung)
                 + kein_detail
                 + _n(fenster, "accept", richtung))
    kand_detail = sum(_n(fenster, s, richtung) for s in SITES_KAND)
    return TelemetrieBudget(
        fenster=fenster, richtung=richtung, box_end=box_end,
        eintritt_ist=eintritt, eintritt_soll=box_end - 5,
        summe_ausgaenge=ausgaenge, kand_none_summe=kand_none,
        kand_none_details=kand_detail, kein_raum_summe=-1,
        kein_raum_details=kein_detail)


def _stats_abweichungen(fenster: str, stats: Dict[str, Any]) -> Tuple[str, ...]:
    """(V): die Summe der gebundenen Anker reproduziert den stats-Wert."""
    fehler: List[str] = []
    for schluessel, sites in STATS_BINDUNG.items():
        ist = sum(_n(fenster, s, r) for s in sites for r in RICHTUNGEN)
        soll = int(stats.get(schluessel, 0))
        if ist != soll:
            fehler.append(f"{'+'.join(sites)} {ist} != "
                          f"stats['{schluessel}'] {soll}")
    return tuple(fehler)


def _v_s_identitaet(fenster: str, stats: Dict[str, Any]) -> Tuple[str, ...]:
    """(V) fuer ``stats["v_s"]``: ``len(setups)`` == beide Append-Stellen.

    O5 verlangte urspruenglich nur ``accept <= v_s``. Da der G4-Anhang
    (Z2824) jetzt ebenfalls gezaehlt wird, ist die Gleichheit messbar -- sie
    ist strenger und ersetzt die Ungleichung nicht, sondern prueft sie aus.
    """
    accept = sum(_n(fenster, "accept", r) for r in RICHTUNGEN)
    g4 = sum(_n(fenster, "g4_accept", r) for r in RICHTUNGEN)
    v_s = int(stats.get("v_s", 0))
    if accept + g4 != v_s:
        return (f"accept {accept} + g4_accept {g4} != stats['v_s'] {v_s}",)
    return ()


def _kein_raum_aggregat(fenster: str, stats: Dict[str, Any]
                        ) -> Tuple[int, int]:
    """(IV) Fenster-Total: (stats["kein_raum"], Summe der 8 Stellen)."""
    soll = int(stats.get("kein_raum", 0))
    ist = sum(_n(fenster, s, r) for s in SITES_RAUM for r in RICHTUNGEN)
    return soll, ist


def _verteilung(setups: Sequence[Any]) -> Dict[str, int]:
    v = {"SHORT": 0, "LONG": 0}
    for t in setups:
        v[str(t.richtung)] = v.get(str(t.richtung), 0) + 1
    return v


def _trichter(fenster: str) -> List[str]:
    """Block 2: Trichter mit LONG/SHORT-Spalten und Durchlassquote."""
    z: List[str] = []
    e_l = _n(fenster, "eintritt", "LONG")
    e_s = _n(fenster, "eintritt", "SHORT")
    e_g = e_l + e_s
    z.append(f"  eintritt (k-Paare)        {e_l:>7d} {e_s:>7d} {e_l - e_s:>+8d}"
             f"   gesamt {e_g}")
    z.append("  " + "-" * 70)
    z.append(f"  {'Stufe':<22s} {'LONG':>7s} {'SHORT':>7s} {'Delta':>8s}"
             f"   {'Quote L/S':>14s}")
    z.append("  " + "-" * 70)
    for site in SITES_KAND:
        z.append(_zeile(fenster, site))
    z.append(f"  {'kand_none (Summe)':<22s} "
             f"{_n(fenster, 'kand_none', 'LONG'):>7d} "
             f"{_n(fenster, 'kand_none', 'SHORT'):>7d} "
             f"{_n(fenster, 'kand_none', 'LONG') - _n(fenster, 'kand_none', 'SHORT'):>+8d}")
    z.append("")
    for site in SITES_KAND_FILTER:
        z.append(f"  [{site:<20s}] {_n(fenster, site, 'LONG'):>7d} "
                 f"{_n(fenster, site, 'SHORT'):>7d} "
                 f"{_n(fenster, site, 'LONG') - _n(fenster, site, 'SHORT'):>+8d}"
                 f"  (per Element, nicht terminal)")
    z.append("")
    for site in SITES_TERMINAL:
        if site == "accept":
            a, b = _n(fenster, site, "LONG"), _n(fenster, site, "SHORT")
            z.append(f"  {site:<22s} {a:>7d} {b:>7d} {a - b:>+8d}"
                     f"   <== DURCHGELASSEN")
            continue
        z.append(_zeile(fenster, site))
    z.append("  " + "-" * 70)
    z.append(f"  {'kein_raum Zerlegung':<22s} {'LONG':>7s} {'SHORT':>7s}")
    for site in SITES_RAUM:
        z.append(f"    {site:<20s} {_n(fenster, site, 'LONG'):>7d} "
                 f"{_n(fenster, site, 'SHORT'):>7d}")
    z.append("  " + "-" * 70)
    z.append("  G4-Hook-3-Nebenweg (nach der k-Schleife, NICHT im Budget):")
    for site in SITES_G4:
        z.append(f"    {site:<20s} {_n(fenster, site, 'LONG'):>7d} "
                 f"{_n(fenster, site, 'SHORT'):>7d}")
    return z


def _zeile(fenster: str, site: str) -> str:
    a, b = _n(fenster, site, "LONG"), _n(fenster, site, "SHORT")
    return f"  {site:<22s} {a:>7d} {b:>7d} {a - b:>+8d}"


def _signaturen(fenster: str) -> List[str]:
    """Block 3: Verdikt je Hypothese A-F (gleichrangig, kein Vorab-Bias)."""
    z: List[str] = []
    for kenn, site, text in HYPOTHESEN:
        a, b = _n(fenster, site, "LONG"), _n(fenster, site, "SHORT")
        # Verdikt-Kriterium: ueberwiegt die SHORT-Seite deutlich, ist die
        # Asymmetrie durch dieses Gate (mit-)erklaert.
        ges = a + b
        ver = ("SHORT-DOMINANT (> Factor 3)" if b > 3 * max(a, 1)
               else "LONG-DOMINANT (> Factor 3)" if a > 3 * max(b, 1)
               else "symmetrisch/unauffaellig")
        z.append(f"  {kenn}  {site:<22s} L {a:>6d} / S {b:>6d} "
                 f"(n={ges:>6d})  {ver}")
        z.append(f"       {text}")
    return z


# ================================================================ E) Bericht
def main(nur_anker: bool = False) -> None:
    z: List[str] = []
    z.append("ZULASSUNGS-FUNNEL-SONDE (L6 + L7) -- read-only, keine "
             "Handelswirkung")
    z.append("=" * 96)
    for p, soll, nm in ((BASELINE_PFAD, BASELINE_SHA, "Baseline"),
                        (V021_PFAD, V021_SHA, "V021"),
                        (ADAPTER_PFAD, ADAPTER_SHA, "Adapter")):
        ist = _sha(p)
        if ist != soll:
            raise RuntimeError(f"Fremdstand {nm}: {ist[:16]}... != "
                               f"{soll[:16]}...")
    z.append(f"SHA Baseline {BASELINE_SHA[:16]}...  OK")
    z.append(f"SHA V021     {V021_SHA[:16]}...  OK")
    z.append(f"SHA Adapter  {ADAPTER_SHA[:16]}...  OK")
    z.append("")

    # ---------------------------------------------------- Ankerpruefung (O2)
    quell_t1 = _quelle_se_trades()
    fehler_t1 = _pruefe_anker(quell_t1)
    z.append(f"ANKERPRUEFUNG T1 (Baseline- Verbatim): {len(ANKER)} Anker")
    if fehler_t1:
        raise AssertionError("T1-Anker nicht eindeutig: "
                             + "; ".join(fehler_t1))
    z.append(f"  alle {len(ANKER)} Anker eindeutig (count == 1)  OK")

    if nur_anker:
        V = importlib.import_module("tmp_kanten_engine_v021_replay")
        cfg_an = V.V021KantenKonfiguration(segmentwand_modus="AN")
        gepatcht = V._regel_ersetzen(quell_t1, cfg_an)
        fehler_t2 = _pruefe_anker(gepatcht)
        z.append(f"ANKERPRUEFUNG T2 (gepatchte Segmentwand-Kette): "
                 f"{len(ANKER)} Anker")
        if fehler_t2:
            raise AssertionError("T2-Anker nicht eindeutig: "
                                 + "; ".join(fehler_t2))
        z.append(f"  alle {len(ANKER)} Anker ueberleben "
                 f"A_UEB1/A_VC/A_M6L/A_SB  OK")

        # Die blosse Eindeutigkeit genuegt nicht: die Injektion ist
        # MEHRZEILIG (Einrueckung!), der instrumentierte Text muss weiter
        # kompilierbar sein. Das ist die einzige Fehlerquelle der Sonde, die
        # OHNE Motorlauf pruefbar ist -- deshalb hier und nicht erst im Lauf.
        for lbl, txt in (("T1", quell_t1), ("T2", gepatcht)):
            inj = _instrumentiere(txt)
            n_c = inj.count('_c("')
            if n_c != len(ANKER):
                raise AssertionError(
                    f"{lbl}: {n_c} Zaehlerinjektionen, erwartet {len(ANKER)}.")
            compile(inj, f"<anker_{lbl}>", "exec")
            z.append(f"  {lbl}-Quelltext instrumentiert: {n_c} Zaehler, "
                     f"{len(inj.splitlines())} Zeilen, kompiliert  OK")
        z.append("")
        z.append("MODUS --nur-anker: keine Messung, kein Motorlauf, "
                 "kein Protokoll.")
        print("\n".join(z))
        return

    V = importlib.import_module("tmp_kanten_engine_v021_replay")
    AD = importlib.import_module("backtest_la" + "b.phasen_regime_adapter")
    B = V._engine()
    grenzen = _grenzen(AD, V)
    z.append(f"Adapter-Segmente (ADAPTER_V019_KAUSAL): {len(grenzen)} "
             f"-> {[(int(g.start_bar), int(g.end_bar)) for g in grenzen]}")
    z.append("")

    budgets: List[TelemetrieBudget] = []
    trichter: Dict[str, List[str]] = {}
    signaturen: Dict[str, List[str]] = {}
    kompakt: List[str] = []

    for fenster, ziel, start, ende, soll_n, soll_r in FENSTER:
        if start == "AUG":
            scan = B._se_scan("AUG", B.StraightEdgeHarnessKonfiguration())
            box_end = int(scan["n"])
        else:
            scan, box_end = _scan_monat(B, start, ende)

        if ziel == "T1":
            setups, stats = _lauf_t1(B, V, fenster, scan, box_end)
        else:
            setups, stats = _lauf_t2(B, V, fenster, scan, box_end, grenzen)
        setups = sorted(list(setups), key=lambda t: int(t.entry_bar))

        # --- Fail-Loud gegen den arretierten Bestand ----------------------
        ist_r = round(float(sum(float(t.r) for t in setups)), 6)
        assert (len(setups), ist_r) == (soll_n, round(soll_r, 6)), (
            f"{fenster}: Soll ({soll_n}, {soll_r}) != Ist "
            f"({len(setups)}, {ist_r})")
        if fenster == "AUG_WAND":
            h1 = [float(t.r) for t in setups if int(t.entry_bar) < KALENDERKANTE]
            h2 = [float(t.r) for t in setups if int(t.entry_bar) >= KALENDERKANTE]
            assert (len(h1), round(sum(h1), 6)) == SOLL_H1
            assert (len(h2), round(sum(h2), 6)) == SOLL_H2

        # --- Budget (I)(II)(III) je Richtung ------------------------------
        for r in RICHTUNGEN:
            budgets.append(_budget(fenster, box_end, r))
        # --- (IV)(V) Fenster-Total ----------------------------------------
        kr_soll, kr_ist = _kein_raum_aggregat(fenster, stats)
        abw = _stats_abweichungen(fenster, stats) + _v_s_identitaet(
            fenster, stats)
        budgets.append(TelemetrieBudget(
            fenster=fenster, richtung="TOTAL", box_end=box_end,
            eintritt_ist=(_n(fenster, "eintritt", "LONG")
                          + _n(fenster, "eintritt", "SHORT")),
            eintritt_soll=2 * (box_end - 5),
            summe_ausgaenge=-1, kand_none_summe=-1, kand_none_details=-1,
            kein_raum_summe=kr_soll, kein_raum_details=kr_ist,
            stats_abweichungen=abw))

        v = _verteilung(setups)
        acc = (_n(fenster, "accept", "LONG") + _n(fenster, "accept", "SHORT"))
        g4 = (_n(fenster, "g4_accept", "LONG")
              + _n(fenster, "g4_accept", "SHORT"))
        v_s = int(stats.get("v_s", 0))
        kompakt.append(
            f"{fenster:<9s} {ziel}  {len(setups):>3d}/{ist_r:>+11.6f}  "
            f"LONG {v.get('LONG', 0):>3d} / SHORT {v.get('SHORT', 0):>3d}  "
            f"kein_raum {kr_soll:>6d} (Zerlegung {kr_ist:>6d})  "
            f"accept {acc:>3d} + G4 {g4:>3d} = v_s {v_s:>3d}"
            f"{'' if acc + g4 == v_s else '  <== ABWEICHUNG'}")
        trichter[fenster] = _trichter(fenster)
        signaturen[fenster] = _signaturen(fenster)

    # --------------------------------------------------------- Budgetblock
    z.append("=" * 96)
    z.append("BLOCK 1 -- BUDGETIDENTITAET (I)-(V), fail-loud")
    z.append("=" * 96)
    verletzt = [b for b in budgets if not b.ist_valide]
    for b in budgets:
        if b.richtung == "TOTAL":
            z.append(f"  {b.fenster:<9s} TOTAL  eintritt {b.eintritt_ist:>6d}"
                     f" / Soll {b.eintritt_soll:>6d}   kein_raum stats "
                     f"{b.kein_raum_summe:>6d} / Zerlegung "
                     f"{b.kein_raum_details:>6d}   {'OK' if b.ist_valide else 'VERLETZT'}")
        else:
            z.append(f"  {b.fenster:<9s} {b.richtung:<5s}  eintritt "
                     f"{b.eintritt_ist:>6d} = Ausgaenge {b.summe_ausgaenge:>6d}"
                     f"  kand_none {b.kand_none_summe:>4d} = Details "
                     f"{b.kand_none_details:>4d}   "
                     f"{'OK' if b.ist_valide else 'VERLETZT'}")
    if verletzt:
        z.append("")
        detail: List[str] = []
        for b in verletzt:
            for x in b.verletzungen:
                z.append(f"  VERLETZUNG {b.fenster}/{b.richtung}: {x}")
                detail.append(f"{b.fenster}/{b.richtung}: {x}")
        # O4: kein Protokoll bei Verletzung. Die VERLETZUNGSZEILEN werden
        # aber in die Exception gehoben, damit sie ueber den Traceback
        # (der laut __main__ nach OUT geht) diagnostizierbar bleiben --
        # sonst ist die Ursache im Abbruchprotokoll unsichtbar.
        raise AssertionError("Budgetidentitaet verletzt -- kein Protokoll. "
                             + " | ".join(detail))
    z.append("")
    z.append("  (I)(II)(III)(IV)(V) fuer ALLE Fenster/Richtungen erfuellt.")

    # ---------------------------------------------------------- Kompaktlage
    z.append("")
    z.append("=" * 96)
    z.append("BLOCK 2 -- KOMPAKTLAGE")
    z.append("=" * 96)
    z.append(f"  {'Fenster':<9s} {'Ziel':<4s} {'Trades/SumR':>17s}  "
             f"{'Richtungen':<20s} {'kein_raum (stats/Zerlegung)':<28s} "
             f"accept/v_s")
    for k in kompakt:
        z.append("  " + k)

    # ----------------------------------------------------------- Trichter
    for fenster, *_ in FENSTER:
        z.append("")
        z.append("=" * 96)
        z.append(f"BLOCK 3 -- TRICHTER {fenster}")
        z.append("=" * 96)
        z.extend(trichter[fenster])

    # --------------------------------------------------------- Signaturen
    z.append("")
    z.append("=" * 96)
    z.append("BLOCK 4 -- SIGNATUREN DER HYPOTHESEN A-F (gleichrangig)")
    z.append("=" * 96)
    for fenster, *_ in FENSTER:
        z.append(f"  --- {fenster} ---")
        z.extend(signaturen[fenster])
        z.append("")

    # --------------------------------------------------- Nebenprotokoll O7
    z.append("=" * 96)
    z.append("BLOCK 5 -- NEBENPROTOKOLL (fuer H20.53, O7)")
    z.append("=" * 96)
    z.append("  N1  stats['stacking_blockiert'] wird an KEINER Stelle "
             "inkrementiert")
    z.append("      (Z2712-2714: 'kein Stacking-Gate') -- 9. toter Zaehler.")
    z.append("  N2  sweep_mindestdurchstich_pct = 0.0 macht Z2588-2589 "
             "faktisch inert:")
    z.append("      Z2582 faengt dist < 0.0 ab, es bleibt nur die exakte "
             "Null. Das Durchstich-Gate ist ausgeschaltet.")
    z.append("  N3  'kand_dormant/kein_durchstich/vs_lt3' sind "
             "per-Element-Zaehler und duerfen NICHT")
    z.append("      gegen das Terminalbudget gerechnet werden.")

    OUT.write_text("\n".join(z) + "\n", encoding="utf-8", newline="\n")
    for zeile in z:
        print(zeile)
    print(f"\nPROTOKOLL: {OUT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Zulassungs-Funnel-Sonde (L6/L7), read-only.")
    parser.add_argument("--nur-anker", action="store_true",
                        help=f"Nur die {len(ANKER)} Anker pruefen "
                             "(kein Motorlauf, kein Protokoll).")
    args = parser.parse_args()
    _fehler = False
    try:
        main(nur_anker=bool(args.nur_anker))
    except BaseException as exc:                        # noqa: BLE001
        _fehler = True
        import traceback
        tb = traceback.format_exc()
        sys.stderr.write(tb)
        if not args.nur_anker:
            OUT.write_text(f"ABBRUCH: {type(exc).__name__}: {exc}\n\n{tb}",
                           encoding="utf-8")
    print(f"\nFehler={_fehler}")
