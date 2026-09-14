# -*- coding: utf-8 -*-
"""Ableitung der Durchlassquoten aus dem Zaehler-Rohstand (reine Rechnung).

Quelle: ``test/_tmp_funnel_budget_diag_out.txt`` (Zaehlerstand nach dem
vollstaendigen Durchlauf aller fuenf Fenster). Kein Motorlauf.
"""
from __future__ import annotations

import pathlib
import re
from typing import Dict, List, Tuple

QUELLE = pathlib.Path("test/_tmp_funnel_budget_diag_out.txt")
TXT = QUELLE.read_text(encoding="utf-8")
BLOCK = TXT[TXT.index("ZAEHLER-ROHSTAND"):TXT.index("TRICHTER MAI")]

FENSTER: List[str] = ["MAI", "JUN", "JUL", "AUG_BASE", "AUG_WAND"]
ZAHL: Dict[Tuple[str, str], Dict[str, int]] = {}

cur = ""
for zeile in BLOCK.splitlines():
    m = re.match(r"\s*--- (\w+) ---", zeile)
    if m:
        cur = m.group(1)
        ZAHL[(cur, "L")] = {}
        ZAHL[(cur, "S")] = {}
        continue
    m = re.match(r"\s*(\w+)\s+L\s+(\d+)\s+S\s+(\d+)\s*$", zeile)
    if m and cur:
        ZAHL[(cur, "L")][m.group(1)] = int(m.group(2))
        ZAHL[(cur, "S")][m.group(1)] = int(m.group(3))

assert all((f, r) in ZAHL for f in FENSTER for r in "LS"), "Parsefehler"

# ---------------------------------------------------------------- Pruefung
print("SELBSTPRUEFUNG DER PARSE-UND-ABLEITUNG")
print("-" * 96)
ok = True
for f in FENSTER:
    for r in "LS":
        d = ZAHL[(f, r)]
        auf = [k for k in d if k.startswith("g_")
               or k in ("accept",) or k.startswith("r_") or k == "kand_none"]
        s_auf = sum(d.get(k, 0) for k in auf)
        if f == "AUG_WAND" and r == "S":
            pass
        if s_auf != d["eintritt"]:
            ok = False
            print(f"  ABWEICHUNG {f}/{r}: {s_auf} != {d['eintritt']}")
print(f"  (I) eintritt == Summe Ausgaenge: "
      f"{'alle 10 Paarungen OK' if ok else 'FEHLER'}")
print()

# --------------------------------------------------------------- Quoten
print("DURCHLASSQUOTEN (Stufe -> Stufe)")
print("=" * 96)
kopf = (f"  {'Fenster':<9s} {'R':<2s} {'eintritt':>9s} {'kand_none':>10s} "
        f"{'Surv':>6s} {'Surv%':>7s} {'Q29':>5s} {'Q29/Surv':>9s} "
        f"{'Zyklus':>7s} {'accept':>7s} {'Acc/Surv':>9s} {'Acc/Ein':>8s}")
print(kopf)
print("-" * 96)
for f in FENSTER:
    for r in "LS":
        d = ZAHL[(f, r)]
        e = d["eintritt"]
        kn = d.get("kand_none", 0)
        surv = e - kn
        q29 = d.get("g_quartil", 0)
        zyk = d.get("g_zyklus", 0)
        acc = d.get("accept", 0)
        print(f"  {f:<9s} {r:<2s} {e:>9d} {kn:>10d} {surv:>6d} "
              f"{100.0 * surv / e:>6.2f}% {q29:>5d} "
              f"{100.0 * q29 / surv if surv else float('nan'):>8.2f}% "
              f"{zyk:>7d} {acc:>7d} "
              f"{100.0 * acc / surv if surv else float('nan'):>8.2f}% "
              f"{100.0 * acc / e:>7.3f}%")
    print()

# ------------------------------------------------- JUN-Spezifik vs. Rest
print("JUN-SPEZIFIK: ANTILIEN AM SHORT-KANDIDATENPOOL")
print("=" * 96)
print(f"  {'Fenster':<9s} {'pool_leer':>10s} {'leb_wand':>10s} "
      f"{'ueberd':>8s} {'erschoepft':>11s} {'kand_none':>10s} "
      f"{'in % eintritt':>14s}")
for f in FENSTER:
    d = ZAHL[(f, "S")]
    e = d["eintritt"]
    print(f"  {f:<9s} {d.get('kand_pool_leer', 0):>10d} "
          f"{d.get('kand_lebende_wand', 0):>10d} "
          f"{d.get('kand_ueberdehnung', 0):>8d} "
          f"{d.get('kand_erschoepft', 0):>11d} "
          f"{d.get('kand_none', 0):>10d} "
          f"{100.0 * d.get('kand_none', 0) / e:>13.2f}%")
print()
print("  Vergleich LONG:")
for f in FENSTER:
    d = ZAHL[(f, "L")]
    e = d["eintritt"]
    print(f"  {f:<9s} {d.get('kand_pool_leer', 0):>10d} "
          f"{d.get('kand_lebende_wand', 0):>10d} "
          f"{d.get('kand_ueberdehnung', 0):>8d} "
          f"{d.get('kand_erschoepft', 0):>11d} "
          f"{d.get('kand_none', 0):>10d} "
          f"{100.0 * d.get('kand_none', 0) / e:>13.2f}%")

# --------------------------------------------------- kein_raum-Bilanz
print()
print("KEIN_RAUM 8-FACH: WELCHE STELLE FEUERT UEBERHAUPT?")
print("=" * 96)
SITES = ["r_halb_short", "r_mindist_short", "r_halb_long", "r_mindist_long",
         "r_poc", "r_ord_short", "r_ord_long", "r_risk"]
for s in SITES:
    tot = sum(ZAHL[(f, r)].get(s, 0) for f in FENSTER for r in "LS")
    print(f"  {s:<18s} {tot:>5d}")
print()
print("  Tote Gates (0 in ALLEN 5 Fenstern und beiden Richtungen):")
TOTE = ["g_f3", "g_kein_gegner", "g_dedup", "g_concurrency",
        "kand_kein_durchstich", "r_halb_short", "r_mindist_short",
        "r_halb_long", "r_mindist_long", "r_poc", "r_risk"]
for s in TOTE:
    tot = sum(ZAHL[(f, r)].get(s, 0) for f in FENSTER for r in "LS")
    print(f"    {s:<18s} {tot:>5d}")
