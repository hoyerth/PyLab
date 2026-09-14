# -*- coding: utf-8 -*-
"""Erzeugt test/tmp_S2_monatsauswertung.py als exakte Kopie des S1-Helpers
mit S2-spezifischen Anpassungen (Fenster 2025-01-01..2025-12-01, 210 Trades,
+99.88R, Dateipraefixe tmp_S2_). Rein lesend fuer die S1-Datei; schreibt nur
die neue S2-Helper-Datei in test/ (I4: keine Produktionsaenderung).
"""
import io
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

src = io.open("test/tmp_S1_monatsauswertung.py", encoding="utf-8").read()
orig_len = len(src)

# ---------------------------------------------------------------- Ersetzungen S1 -> S2
REPL = [
    # Docstring
    ("S1-Monatsauswertung: Baseline-Lauf 2026-02-05..2026-08-28", "S2-Monatsauswertung: Baseline-Lauf 2025-01-01..2025-12-01"),
    ("(201 Signale, +197.26R -> gegen test/tmp_S1_monatslauf_trades.txt verifiziert)",
     "(210 Signale, +99.88R -> gegen test/tmp_S2_monatslauf_trades.txt verifiziert)"),
    ("tmp_S1_monatslauf_YYYY-MM.txt", "tmp_S2_monatslauf_YYYY-MM.txt"),
    ("tmp_S1_monatslauf_YYYY-MM.png", "tmp_S2_monatslauf_YYYY-MM.png"),
    ("test/tmp_S1_monatslauf_trades.txt", "test/tmp_S2_monatslauf_trades.txt"),
    # Konstanten
    ("BASELINE_S1 = 197.26", "BASELINE_S2 = 99.88"),
    ("pvp_s1_monate", "pvp_s2_monate"),
    ("--start=2026-02-05", "--start=2025-01-01"),
    ("--ende=2026-08-28", "--ende=2025-12-01"),
    ("df S1:", "df S2:"),
    ("Mapping Log->Signal: {mm}/201", "Mapping Log->Signal: {mm}/210"),
    # Asserts / Zaehler
    ("assert len(trades) == 201 and abs(s_sum - BASELINE_S1) < 0.10",
     "assert len(trades) == 210 and abs(s_sum - BASELINE_S2) < 0.10"),
    # Monatsbericht-Header (txt) - Teilstrings (Quelltext bricht nach '| ' um)
    ("S1-MONATSBERICHT {m} | Baseline phasen_volumen_profil.py", "S2-MONATSBERICHT {m} | Baseline phasen_volumen_profil.py"),
    ("Fenster 2026-02-05..2026-08-28 | Gesamt +197.26R", "Fenster 2025-01-01..2025-12-01 | Gesamt +99.88R"),
    # Chart-Titel
    ("SILVER M15 | S1-Baseline | Monat {m}", "SILVER M15 | S2-Baseline | Monat {m}"),
    # Output-Dateinamen (f-Strings im Monats-Rendering)
    ('f"tmp_S1_monatslauf_{m}.txt"', 'f"tmp_S2_monatslauf_{m}.txt"'),
    ('f"tmp_S1_monatslauf_{m}.png"', 'f"tmp_S2_monatslauf_{m}.png"'),
]

cnt = 0
for a, b in REPL:
    n = src.count(a)
    assert n >= 1, f"Ersetzung nicht gefunden: {a!r}"
    src = src.replace(a, b)
    cnt += n

# Kontrollen (noqa: S102 ist eine Pyflakes-Kennung, KEIN S1-Label -> erlaubt)
assert "S2" in src and "2025-01-01" in src and "99.88" in src
assert "2026-02-05" not in src and "2026-08-28" not in src and "197.26" not in src
assert "tmp_S1_" not in src and "S1-Baseline" not in src and "S1-MONATSBERICHT" not in src
assert "Baseline-Lauf 2026" not in src and "df S1:" not in src and "pvp_s1" not in src
assert "tmp_S2_monatslauf_trades.txt" in src

out = Path("test/tmp_S2_monatsauswertung.py")
out.write_text(src, encoding="utf-8")
print(f"OK -> {out.name} ({len(src)} Zeichen, {orig_len} vorher, {cnt} Ersetzungen)")
