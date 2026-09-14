# -*- coding: utf-8 -*-
"""Erzeugt tmp_S2_economic_backtest.py + tmp_S2_leverage_backtest.py als
S2-Kopien der S1-Wirtschafts-Helper (Fenster 2025-01-01..2025-12-01, 210
Trades, +99.88R exakt / +99.90R gerundet, 10 Monatsberichte, letzter Trade
28.11.2025, erster Voll-SL T2 02.01.2025). Schreiben nur nach test/ (I4).
"""
import io
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ================================================================ economic
src = io.open("test/tmp_S1_economic_backtest.py", encoding="utf-8").read()
REPL_ECO = [
    # Docstring
    ("Wirtschaftliches Backtesting S1 (Baseline): Equity-Kurve in USD.",
     "Wirtschaftliches Backtesting S2 (Baseline): Equity-Kurve in USD."),
    ("letzten 2026-Trade (S1-Fenster-Ende 27.08.2026)",
     "letzten 2025-Trade (S2-Fenster-Ende 28.11.2025)"),
    ("test/tmp_S1_monatslauf_2026-*.txt (7 Monatsberichte, verifiziert:\n201 Trades, Summe +197.26R exakt = Baseline S1)",
     "test/tmp_S2_monatslauf_2025-*.txt (10 Monatsberichte, verifiziert:\n210 Trades, Summe +99.90R gerundet; exakt +99.88R = Baseline S2)"),
    ("Ausgabe: test/tmp_S1_economic_backtest.txt", "Ausgabe: test/tmp_S2_economic_backtest.txt"),
    # Pfade / Logik
    ('OUT = Path("test/tmp_S1_economic_backtest.txt")', 'OUT = Path("test/tmp_S2_economic_backtest.txt")'),
    ('glob.glob("test/tmp_S1_monatslauf_2026-*.txt")', 'glob.glob("test/tmp_S2_monatslauf_2025-*.txt")'),
    ("assert len(trades) == 201, len(trades)", "assert len(trades) == 210, len(trades)"),
    ("- 197.26) < 0.02", "- 99.88) < 0.10  # gerundete Monats-R (+99.90); exakt +99.88R"),
    # Report-Texte
    ("WIRTSCHAFTLICHES BACKTESTING S1 (Baseline phasen_volumen_profil.py)",
     "WIRTSCHAFTLICHES BACKTESTING S2 (Baseline phasen_volumen_profil.py)"),
    ("2026-02-05 .. 2026-08-28 (letzter Trade 27.08.2026)",
     "2025-01-01 .. 2025-12-01 (letzter Trade 28.11.2025)"),
    ("(z. B. T27 +17.79R, danach -461 USD bis T34)",
     "(wiederkehrendes Muster, siehe Episoden oben)"),
]
for a, b in REPL_ECO:
    n = src.count(a)
    assert n >= 1, f"[eco] nicht gefunden: {a!r}"
    src = src.replace(a, b)
out_eco = Path("test/tmp_S2_economic_backtest.py")
out_eco.write_text(src, encoding="utf-8")
print(f"OK {out_eco.name} ({len(src)} Zeichen, {len(REPL_ECO)} Ersetzungen)")

# ================================================================ leverage
src = io.open("test/tmp_S1_leverage_backtest.py", encoding="utf-8").read()
REPL_LEV = [
    # Docstring
    ("S1-Zinseszins-Hochrechnung mit Hebel-500-Einordnung (Baseline phasen_volumen_profil.py).",
     "S2-Zinseszins-Hochrechnung mit Hebel-500-Einordnung (Baseline phasen_volumen_profil.py)."),
    ("Datenbasis: test/tmp_S1_monatslauf_2026-*.txt (201 Trades, +197.26R, verifiziert).",
     "Datenbasis: test/tmp_S2_monatslauf_2025-*.txt (10 Monatsberichte, 210 Trades,\n+99.90R gerundet; exakt +99.88R = Baseline S2, verifiziert)."),
    ("Ausgabe: test/tmp_S1_leverage_backtest.txt", "Ausgabe: test/tmp_S2_leverage_backtest.txt"),
    # Pfade / Logik
    ('OUT = Path("test/tmp_S1_leverage_backtest.txt")', 'OUT = Path("test/tmp_S2_leverage_backtest.txt")'),
    ('glob.glob("test/tmp_S1_monatslauf_2026-*.txt")', 'glob.glob("test/tmp_S2_monatslauf_2025-*.txt")'),
    ("assert len(trades) == 201, len(trades)", "assert len(trades) == 210, len(trades)"),
    ("- 197.26) < 0.02", "- 99.88) < 0.10  # gerundete Monats-R (+99.90); exakt +99.88R"),
    # Report-Texte
    ("S1 ZINSESZINS-HOCHRECHNUNG MIT HEBEL-500-EINORDNUNG (Baseline)",
     "S2 ZINSESZINS-HOCHRECHNUNG MIT HEBEL-500-EINORDNUNG (Baseline)"),
    ("Fenster            : 2026-02-05 .. 2026-08-28 (201 Trades, Summe",
     "Fenster            : 2025-01-01 .. 2025-12-01 (210 Trades, Summe"),
    # Vergleich linear: hartkodierte S1-Werte -> dynamisch aus gerundeten R
    ('o(f"  Vergleich linear (fix)  : +19,726.00 USD (+197.26R x 100 USD, ohne Zinseszins)")',
     '_lin_usd = sum(t["r"] for t in trades) * 100.0\n'
     'o(f"  Vergleich linear (fix)  : {_lin_usd:+,.2f} USD '
     '({sum(t["r"] for t in trades):+.2f}R x 100 USD, ohne Zinseszins)")'),
    # Zinseszins-Vorteil dynamisch
    ("{profit - 19726.0:+,.2f} USD gegenueber fix 100 USD/Trade",
     "{profit - _lin_usd:+,.2f} USD gegenueber fix 100 USD/Trade"),
    # Lesart: erster Voll-SL in S2 ist T2 (02.01.2025), nicht T1
    ("(T1, 09.02.2026)", "(T2, 02.01.2025)"),
]
for a, b in REPL_LEV:
    n = src.count(a)
    assert n >= 1, f"[lev] nicht gefunden: {a!r}"
    src = src.replace(a, b)
out_lev = Path("test/tmp_S2_leverage_backtest.py")
out_lev.write_text(src, encoding="utf-8")
print(f"OK {out_lev.name} ({len(src)} Zeichen, {len(REPL_LEV)} Ersetzungen)")
