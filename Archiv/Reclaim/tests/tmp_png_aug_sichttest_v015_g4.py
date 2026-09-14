# -*- coding: utf-8 -*-
"""ENTWURF (Staging) -- V015-Bildsatz: visueller Nachweis der Phasenboden-Regel G4.

STATUS: **laufbereit** -- Freigaben der Runde 4 eingearbeitet:
  (1) Null-LONG-Assert auf ``V1_aktiv`` VOR der Injektion (fail-loud),
  (5) H1-Byte-Invariante nach dem Schreibe-Lauf (Panel 02 == Baseline),
  (6) G4-Kennzeichnung: Ring + Text "G4 RECLAIM" am berechneten Trade-Kreis.
Die Fragment-Anker sind durch ``assert count == 1`` fail-loud abgesichert;
``--fragmente`` prueft die Anker, ohne zu rendern.

WAS DIESES SKRIPT TUT
---------------------
Es rendert den *kanonischen* Renderer ``test/tmp_png_aug_sichttest.py`` erneut,
jedoch mit **zwei** in-memory vorgenommenen Ergaenzungen:

  1. Der G4-Trade (Phasenboden-Regel, Spez v0.19 / Abschnitt 69.8) wird als
     ``_SESetup`` **berechnet** und in die Trade-Liste eingespeist.
  2. Der Zielkatalog (Fail-Loud-Asserts) wird auf den V015-Sollwert gehoben.

Die kanonische Datei, die Engine, der Adapter und alle arretierten Bildsaetze
(V01, V014) bleiben **byte-unveraendert**. Es wird **nichts** ueberschrieben:
der Satz schreibt unter eigenem Praefix und eigenem Protokoll.

REGEL G4 (generisch, kausal -- KEIN Hardcoding des Ergebnisses)
--------------------------------------------------------------
    Kandidat = Bar k im Phasenfenster des deklarierten Segments mit
        (1) lo[k] < deklarierter_boden
        (2) cl[k] > deklarierter_boden
        (3) touch_conf(bodenkante, k) >= min_touches_handelbar (= 3)
    Entry = open[k+1]; SL = min(lo[k:k+2]) - sl_buffer_usd;
    POC = regel-lokaler Anker (Phasenstart des Segments);
    TP2 = Segment-Decke (Override-Preis).
    Der Anker ``deklarierter_boden`` ist ein LITERAL (Abschnitt 69.9), NICHT
    ``basis_bei(k)``.

Die Erwartungswerte (Bar 1002, Entry 68.5070, SL 68.2580, R +3.629016) sind
**nicht** Eingabe, sondern **Assert-Ziel** -- hergeleitet in Spez Abschnitt 69.8.

SOLLWERTE DES V015-SATZES (gegenueber V014)
-------------------------------------------
| Kennzahl      | V014            | V015            | Delta          |
|---------------|-----------------|-----------------|----------------|
| Trades        | 17              | **18**          | +1             |
| R gesamt      | +61.250064      | **+64.879080**  | +3.629016      |
| H1            | 8 / +38.964262  | 8 / +38.964262  | **0 (bit-fest)** |
| H2            | 9 / +22.285802  | **10 / +25.914818** | +1 / +3.629016 |
| P9-Beitrag    | +19.804922      | **+23.433938**  | +3.629016      |
| H2-LONGS      | 0               | **1**           | +1             |

Der Beweis der Regressionsfreiheit ist Panel 02: es muss weiterhin
byte-identisch zum V01-Panel 02 bleiben (SHA256 ``d9f35876...``, 899.249 B).

Aufruf (nach Freigabe):
    $env:PYTHONIOENCODING="utf-8"; .venv\\Scripts\\python.exe test\\tmp_png_aug_sichttest_v015_g4.py
    ... --fragmente      # nur Patch-Anker zaehlen, KEIN Rendern
"""
from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path
from typing import Final, List, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
# Referenz HALTEN: der kanonische Renderer umhuellt denselben Puffer ein
# zweites Mal; ohne lebende Referenz schliesst der GC diesen Wrapper (und
# damit den gemeinsamen Puffer) -> "I/O operation on closed file".
_STDOUT_GUARD = sys.stdout
ROOT = Path(__file__).resolve().parent.parent
KANONISCH = ROOT / "test" / "tmp_png_aug_sichttest.py"

# ---------------------------------------------------------------------------
# Praefix-Familie. Die bestehenden Saetze heissen
#   ``aug_sichttest_``      (V01) und
#   ``aug_sichttest_v014_`` (V014).
# Fuer die Familien-Konsistenz wird ``aug_sichttest_v015_`` vorgeschlagen
# (Abweichung vom Auftrags-Vorschlag ``v015_``; siehe Rueckfrage 1).
# ---------------------------------------------------------------------------
PRAEFIX: Final[str] = "aug_sichttest_v015_"
PROTOKOLL: Final[str] = "test/tmp_png_aug_sichttest_v015_out.txt"

# ---------------------------------------------------------------------------
# Fail-Loud-Erwartungen (Spez Abschnitt 69.8). Diese Werte sind ASSERT-ZIELE.
# ---------------------------------------------------------------------------
G4_BAR: Final[int] = 1002
G4_ENTRY_BAR: Final[int] = 1003
G4_RICHTUNG: Final[str] = "LONG"
G4_KID: Final[int] = 77
G4_BODEN_LITERAL: Final[float] = 68.4000
G4_DECKE: Final[float] = 69.8700
G4_ENTRY: Final[float] = 68.5070
G4_SL: Final[float] = 68.2580
G4_R: Final[float] = 3.629016

ZIEL_TRADES: Final[int] = 18
ZIEL_R_GESAMT: Final[float] = 64.879080
ZIEL_R_H2: Final[float] = 25.914818
ZIEL_P9: Final[float] = 23.433938
ZIEL_DELTA: Final[float] = 18.012732        # V015 - V1_basis
ZIEL_H1: Final[float] = 38.964262           # unveraendert (Regressionsanker)


# ===========================================================================
# 1) Die Patch-Fragmente (Einfuegung des G4-Trades + Zielkatalog)
# ===========================================================================
# Einfuegepunkt: unmittelbar nach der Zuweisung der Aktiv-Trade-Liste und VOR
# der Berechnung von R1 / h1_1 / h2_1 / P9_BEITRAG (Kanonisch Zeile 347ff).
ANKER_V1: Final[str] = "V1, st1 = V1_aktiv, st_aktiv"

FRAGMENT_G4: Final[str] = '''V1, st1 = V1_aktiv, st_aktiv

# ===================== STAGING V015: G4-Phasenboden-Regel ==================
# Berechnung, nicht Setzung: die Regel laeuft generisch ueber das Phasenfenster
# des deklarierten Segments; die Erwartungswerte sind Assert-Ziele.
_dg = scan["d"]
_op_g = _dg["open"].to_numpy(dtype=float)
_lo_g = _dg["low"].to_numpy(dtype=float)
_cl_g = _dg["close"].to_numpy(dtype=float)
_hi_g = _dg["high"].to_numpy(dtype=float)
_by_kid_g = {e.kid: e for e in (list(scan["edges"]) + list(scan["seeds"]))}
_kante_g = _by_kid_g[77]

# --- Freigabe 1 (Runde 4): kein LONG im H2-REGIME VOR der Injektion --------
# Abgrenzung: der Renderer-Bucket ``entry_bar >= box_end`` (= 640) enthaelt den
# arretierten MAKRO-Transition-Park [640 .. P9.start_bar - 1]; dieser fuehrt
# selbst 3 LONG-Trades (K1@639 / K3@650 / K45@679) und ist unberuehrbar.
# Freigabe 1 meint das ADAPTER-GOVERNED H2 ab P9.start_bar (848): dort muss die
# Zahl der LONGs VOR G4 null sein, damit der G4-Trade der EINZIGE LONG-Beitrag
# des Regimes ist.
_park_longs_vor = [t for t in V1_aktiv
                   if box_end <= t.entry_bar < P9.start_bar
                   and t.richtung == "LONG"]
_h2_longs_vor = [t for t in V1_aktiv
                 if t.entry_bar >= P9.start_bar and t.richtung == "LONG"]
assert len(_park_longs_vor) == 3, ("Transition-Park-LONGs != 3",
                                   _park_longs_vor)
assert not _h2_longs_vor, ("H2-LONGS (>= P9.start_bar) vor G4 != 0",
                           _h2_longs_vor)

# Deklarierte Grenzen des P9-Segments (Spez 69.9): der Boden ist ein LITERAL
# (NICHT basis_bei(k)); die Decke ist der Override-Preis 69.8700. Die Namen
# leben im exec-Namensraum des gepatchten Renderers (nicht im Staging-Modul).
G4_BODEN_LITERAL = 68.4000
G4_DECKE = 69.8700

# (1)+(2)+(3): literaler Anker, Durchstich nach unten, Reclaim, Touch-Reife.
_kand_g = [k for k in range(848, 1021)
           if _lo_g[k] < G4_BODEN_LITERAL < _cl_g[k]
           and _kante_g.touch_conf(k) >= cfg.min_touches_handelbar]
assert _kand_g == [1002], ("G4-Kandidaten", _kand_g)

_k_g = _kand_g[0]
_eb_g = _k_g + 1
_entry_g = float(_op_g[_eb_g])
_sl_g = float(_lo_g[_k_g:_eb_g + 1].min()) - cfg.sl_buffer_usd
# Regel-lokaler POC: Anker = Phasenstart (848), NICHT poc_start = 0.
_poc_g = engine.berechne_kausalen_histogramm_poc(
    _dg, 848, _k_g, 68.4000, 69.8700, cfg.num_bins)
_tr_g = engine._c_loese_trade(_hi_g, _lo_g, _cl_g, _eb_g, _entry_g, "LONG",
                              _sl_g, _poc_g, 69.8700, cfg.tp1_anteil_pct)

assert _k_g == 1002, _k_g
assert abs(_entry_g - 68.5070) < 1e-9, _entry_g
assert abs(_sl_g - 68.2580) < 1e-9, _sl_g
assert _entry_g < _poc_g < 69.8700, (_poc_g, _entry_g)
assert abs(_tr_g.r_mult - 3.629016) < 1e-6, _tr_g.r_mult
assert _tr_g.resultat == "GEWONNEN", _tr_g.resultat

_G4 = engine._SESetup(
    bar=_k_g, richtung="LONG", kid=77,
    basis=float(_kante_g.basis_bei(_k_g)), sweep=float(_lo_g[_k_g]),
    trigger_close=float(_cl_g[_k_g]),
    touch_n=int(_kante_g.touch_conf(_k_g)), poc=float(_poc_g), tp2=69.8700,
    sl=_sl_g, entry=_entry_g, r=float(_tr_g.r_mult), resultat=_tr_g.resultat,
    stufe="STUFE_1_IN_BAR", reclaim_bar=_eb_g, entry_bar=_eb_g,
    ist_prim_anker=False, grund1=_tr_g.grund1,
    exit1_bar=int(_tr_g.exit1_bar), exit2_bar=int(_tr_g.exit2_bar))

V1 = list(V1_aktiv) + [_G4]      # Liste, keine Mutation von V1_aktiv
V1_aktiv = V1                    # Folgeauswertungen (R1/h2_1/P9) ziehen nach
P9_BEITRAG_G4 = float(_G4.r)

from dataclasses import replace as _replace      # noqa: E402
KONF = _replace(
    KONF, mode="V015", ausgabe_praefix="aug_sichttest_v015_",
    protokoll_datei="test/tmp_png_aug_sichttest_v015_out.txt",
    ziel_trades_gesamt=18, ziel_r_gesamt=64.879080, ziel_r_h2=25.914818,
    ziel_p9_beitrag=23.433938)
# =================== ENDE STAGING V015 =====================================
'''

# Fail-Loud-Assert des kanonischen Renderers, der V015 verletzen wuerde:
#   (a) Mengendifferenz V1_aktiv - V1_basis: V014 = 2, V015 = 3
#   (b) Delta gegen den V014-Benchmark: muss auf den V015-Wert gehoben werden.
ANKER_DIFF: Final[str] = (
    "    assert len(V1) - len(V1_basis) == 2, len(V1) - len(V1_basis)")
FRAGMENT_DIFF: Final[str] = (
    "    assert len(V1) - len(V1_basis) == 3, len(V1) - len(V1_basis)")

ANKER_DELTA: Final[str] = (
    "    assert abs((R1 - RB) - BENCHMARK_V014_DELTA_R) < 1e-4, R1 - RB")
FRAGMENT_DELTA: Final[str] = (
    "    assert abs((R1 - RB) - 18.012732) < 1e-4, R1 - RB")

# Der V014-spezifische Quartett-Assert bleibt gueltig (Quartett unveraendert).
# Der K67-Aggregat-Assert (+17.1107) bleibt ebenfalls gueltig.

# --- Textkennzeichnung (nur Beschriftung, keine Logik) ---------------------
ANKER_LIT: Final[str] = 'AdapterMode = Literal["V01", "V014"]'
FRAGMENT_LIT: Final[str] = 'AdapterMode = Literal["V01", "V014", "V015"]'

ANKER_LOGKOPF: Final[str] = (
    "    f\"Adapter {'v0.14' if KONF.k67_override_aktiv else 'v0.1'})\")")
FRAGMENT_LOGKOPF: Final[str] = (
    "    f\"Adapter {'v0.15 G4' if KONF.mode == 'V015' else "
    "('v0.14' if KONF.k67_override_aktiv else 'v0.1')})\")")

ANKER_P1: Final[str] = (
    '    _ad = ("Adapter v0.14: P9 mit K67-Override" if KONF.k67_override_aktiv\n'
    '           else "Adapter v0.1: P9 aktiv (848-1020)")')
FRAGMENT_P1: Final[str] = (
    '    _ad = ("Adapter v0.15 G4: P9-Override + Phasenboden-Regel"\n'
    '           if KONF.mode == "V015" else\n'
    '           ("Adapter v0.14: P9 mit K67-Override"\n'
    '            if KONF.k67_override_aktiv\n'
    '            else "Adapter v0.1: P9 aktiv (848-1020)"))')

ANKER_DELTALOG: Final[str] = (
    '    log(f"  Delta v0.14-v0.1: {R1 - RB:+.6f} R  (Soll "\n'
    '        f"{BENCHMARK_V014_DELTA_R:+.6f})")')
FRAGMENT_DELTALOG: Final[str] = (
    '    _dsoll = 18.012732 if KONF.mode == "V015" else BENCHMARK_V014_DELTA_R\n'
    '    log(f"  Delta {KONF.mode}-v0.1: {R1 - RB:+.6f} R  (Soll "\n'
    '        f"{_dsoll:+.6f})")')

# Zusatzzeile im Statistikblock: Quartett und P9-Regime-Beitrag werden getrennt
# ausgewiesen (in V015 ist P9_BEITRAG nicht mehr die Quartett-Summe). Die
# G4-Zeile wird aus dem berechneten Trade gebaut -- kein Ergebnis-Hardcoding.
ANKER_EXTRA: Final[str] = (
    '        f"Quartett {list(KONF.quartett_bars)} = {P9_BEITRAG:+.6f} R",')
FRAGMENT_EXTRA: Final[str] = (
    '        f"QUARTETT = {QUARTETT_R:+.6f} R   |   '
    'P9-REGIME-BEITRAG = {P9_BEITRAG:+.6f} R",\n'
    '        *G4_ZEILEN,')

ANKER_KONST: Final[str] = (
    "GEAENDERT: dict = {}                  # kid -> (v_start, v_ende, n_stufen)")

ANMERKUNG_KONSTANTEN: Final[str] = '''# --- V015-Anzeigekonstanten (nur Beschriftung; Quelle = berechneter Trade) --
QUARTETT_R = 19.804922          # mitarretiertes V014-Quartett (unveraendert)
G4_MARKE = ((int(_G4.bar), int(_G4.kid)) if KONF.mode == "V015" else None)
G4_ZEILEN = ([
    f"G4-PHASENBODEN (69.8): K{_G4.kid}@{_G4.bar} entry {_G4.entry:.4f} "
    f"sl {_G4.sl:.4f} tp2 {_G4.tp2:.4f} | R {_G4.r:+.6f} | "
    f"literaler Boden {G4_BODEN_LITERAL:.4f} | {_G4.richtung}",
    f"Freigabe 1: H2-LONGs vor G4 = 0 (ab P9 {P9.start_bar}) | "
    f"Transition-Park {box_end}-{P9.start_bar - 1}: "
    f"{len(_park_longs_vor)} LONGs (arretiert, MAKRO, unberuehrt)",
] if KONF.mode == "V015" else [])
'''

# --- G4-Kennzeichnung am Trade-Kreis (Freigabe 6, Runde 4) -----------------
# Ring + Text "G4 RECLAIM" ausschliesslich am berechneten G4-Trade. Der Anker
# ist der Trade-Kreis-Block in ``mark_trades``; die Bedingung greift nur fuer
# das Paar (bar, kid) der G4-Marke. Alle anderen Panels -- und insbesondere
# Panel 02 (H1) -- bleiben dadurch unveraendert (Byte-Invariante, Freigabe 5).
ANKER_RING: Final[str] = (
    '        ax.plot(t.bar, t.basis, "o", ms=9.0 if in_h1 else 10.5, color=col,\n'
    '                zorder=9, mec=col if ref else "#1a1a1a",\n'
    '                mew=0.9 if ref else (0.7 if in_h1 else 1.6),\n'
    '                mfc="none" if ref else col, alpha=0.45 if ref else None)')
FRAGMENT_RING: Final[str] = ANKER_RING + '''
        if not ref and G4_MARKE and (int(t.bar), int(t.kid)) == G4_MARKE:
            ax.plot(t.bar, t.basis, "o", ms=17.5, color=C_CHG, mfc="none",
                    mew=2.2, zorder=13)
            ax.annotate("G4 RECLAIM", (t.bar, t.basis),
                        textcoords="offset points", xytext=(0, 44),
                        ha="center", fontsize=fs + 0.5, color=C_CHG,
                        weight="bold", zorder=14,
                        bbox=dict(boxstyle="round,pad=0.22", fc="#fdf6e3",
                                  ec=C_CHG, lw=0.9))'''

PATCHES: Final[Tuple[Tuple[str, str, str], ...]] = (
    ("V1-Einfuegung",        ANKER_V1,       FRAGMENT_G4),
    ("Konfig-Literal",       ANKER_LIT,      FRAGMENT_LIT),
    ("Mengen-Assert",        ANKER_DIFF,     FRAGMENT_DIFF),
    ("Delta-Assert",         ANKER_DELTA,    FRAGMENT_DELTA),
    ("Logkopf",              ANKER_LOGKOPF,  FRAGMENT_LOGKOPF),
    ("Panel-01-Titel",       ANKER_P1,       FRAGMENT_P1),
    ("Delta-Logzeile",       ANKER_DELTALOG, FRAGMENT_DELTALOG),
    ("Anzeigekonstanten",    ANKER_KONST,    ANMERKUNG_KONSTANTEN + ANKER_KONST),
    ("Zusatzzeile",          ANKER_EXTRA,    FRAGMENT_EXTRA),
    ("G4-Ring",              ANKER_RING,     FRAGMENT_RING),
)


def patche(quelle: str) -> str:
    """Wendet alle Fragmente an; jeder Anker muss genau einmal vorkommen.

    Args:
        quelle: Quelltext des kanonischen Renderers.

    Returns:
        Gepatchter Quelltext.

    Raises:
        AssertionError: Anker fehlt oder ist mehrdeutig (Fail-Loud).
    """
    text = quelle
    for name, alt, neu in PATCHES:
        treffer = text.count(alt)
        assert treffer == 1, (name, treffer)
        text = text.replace(alt, neu)
    return text


def zeige_fragmente(quelle: str) -> None:
    """Zaehlt die Patch-Anker, ohne zu rendern (Trockenlauf der Vorpruefung)."""
    print(f"Fragment-Anker (Soll = 1), PRAEFIX = {PRAEFIX}:")
    fehler = 0
    for name, alt, _neu in PATCHES:
        c = quelle.count(alt)
        fehler += int(c != 1)
        print(f"  {'OK ' if c == 1 else '!! '} {name:20s} {c}")
    zusatz = ("  Konflikt-Kontrolle: der V014-Praefix darf im V015-Quelltext "
              "nur in der ersetzten Zuweisung stehen.")
    print(zusatz)
    assert fehler == 0, f"{fehler} Anker nicht eindeutig (Fail-Loud)"


def h1_byte_invariante(outdir: Path) -> Tuple[Path, int, str]:
    """Freigabe 5 (Runde 4): H1-Panel muss byte-identisch zur Baseline sein.

    Der G4-Trade hat ``entry_bar = 1003 >= box_end`` und darf H1 strukturell
    nicht beruehren. Der Beweis ist die Byte-Gleichheit von
    ``aug_sichttest_v015_02_h1_box.png`` mit der arretierten Baseline
    ``aug_sichttest_02_h1_box.png`` (SHA256 ``d9f35876...``, 899.249 B).

    Args:
        outdir: Ausgabeverzeichnis (``test/``).

    Returns:
        ``(pfad, groesse_in_bytes, sha256_hex)``.

    Raises:
        AssertionError: Datei fehlt, Groesse oder Hash weicht ab (Fail-Loud).
    """
    neu = outdir / f"{PRAEFIX}02_h1_box.png"
    ref = outdir / "aug_sichttest_02_h1_box.png"
    assert neu.exists() and ref.exists(), (neu.exists(), ref.exists())
    h_neu = hashlib.sha256(neu.read_bytes()).hexdigest()
    h_ref = hashlib.sha256(ref.read_bytes()).hexdigest()
    assert neu.stat().st_size == 899_249, neu.stat().st_size
    assert h_neu == h_ref, (h_neu, h_ref)
    assert h_neu.startswith("d9f35876"), h_neu
    return neu, neu.stat().st_size, h_neu


def main() -> int:
    """Rendert den V015-Satz mit berechnetem G4-Trade (oder prueft nur Anker)."""
    quelle = KANONISCH.read_text(encoding="utf-8")
    if "--fragmente" in sys.argv:
        zeige_fragmente(quelle)
        return 0

    gepatcht = patche(quelle)

    modul = {
        "__name__": "_v015_staging",
        "__file__": str(ROOT / "test" / "tmp_png_aug_sichttest_v015_g4.py"),
    }
    sys.argv = [str(KANONISCH), "--mode", "V014",
                "--protokoll-nach", PROTOKOLL]
    sys.modules[modul["__name__"]] = type(sys)("_v015_staging")
    exec(compile(gepatcht, str(KANONISCH), "exec"), modul)

    outdir: Path = modul["OUTDIR"]
    rollen = ((1, "gesamt"), (2, "h1_box"), (3, "h2_phasen"),
              (4, "p9_regime"), (5, "kantenkarte"))
    geschrieben: List[Path] = [outdir / f"{PRAEFIX}{i:02d}_{r}.png"
                               for i, r in rollen]
    print(f"\nV015-Satz (PRAEFIX = {PRAEFIX}):")
    for p in geschrieben:
        if p.exists():
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            print(f"  OK    {p.name:36s} {p.stat().st_size:>10,} B  {h}")
        else:
            print(f"  FEHLT {p.name}")

    print("\nFreigabe 5 -- H1-Byte-Invariante (Panel 02):")
    _p, _sz, _h = h1_byte_invariante(outdir)
    print(f"  OK    {_p.name:36s} {_sz:>10,} B  {_h}")
    print("        == aug_sichttest_02_h1_box.png (Baseline, arretiert)")
    print("\nFreigabe 1 -- Null-LONG in H2 vor Injektion: OK (Assert im Lauf).")
    print("Freigabe 6 -- G4-Ring + Text 'G4 RECLAIM' an Bar 1002: gezeichnet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
