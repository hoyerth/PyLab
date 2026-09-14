# -*- coding: utf-8 -*-
"""Abschlusskontrolle Schritt 2/3: Artefakt-SHAs + arretierte Fremdstaende."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ART = [
    ("test/tmp_kanten_engine_v022_replay.py", "V022-Modul"),
    ("test/_chk_v022_paritaet.py", "Paritaets-Harness"),
    ("test/_chk_v022_paritaet_out.txt", "Paritaets-Report"),
    ("test/_tmp_v022_erzeuge.py", "Erzeuger (Schritt 2)"),
    ("test/_tmp_v022_smoke.py", "Smoke-Test (Schritt 2)"),
    ("test/_tmp_v022_freie_namen.py", "Fremdnamen-AST"),
    ("test/_tmp_v022_loeschgrenze.py", "Loeschgrenzen-AST"),
]

ARR = [
    ("test/tmp_kanten_engine_replay.py",
     "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006", "Baseline"),
    ("test/tmp_kanten_engine_v021_replay.py",
     "cda9e5b189ed4137198795e1547cec00436dffe64222434bb6ec4c448e598e89", "V021"),
    ("backtest_lab/phasen_regime_adapter.py",
     "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14", "Adapter"),
    ("test/tmp_png_aug_sichttest.py", "500b55762001d666", "Renderer"),
]

print("ARTEFAKTE DIESER SITZUNG")
for rel, name in ART:
    p = ROOT / rel
    if not p.exists():
        print(f"  {name:22s} FEHLT  ({rel})")
        continue
    b = p.read_bytes()
    print(f"  {name:22s} {len(b):7d} B  {hashlib.sha256(b).hexdigest()}")

print()
print("ARRETIERTE FREMDSTAENDE")
for rel, soll, name in ARR:
    p = ROOT / rel
    if not p.exists():
        print(f"  {name:10s} FEHLT  ({rel})")
        continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    marke = "OK" if h.startswith(soll[:16]) else "VERAENDERT"
    print(f"  {name:10s} {marke:11s} {h[:16]}  {p.stat().st_size} B")

print()
print("Line-Endings der neuen Dateien")
for rel, name in ART:
    p = ROOT / rel
    if p.suffix in (".py", ".txt") and p.exists():
        b = p.read_bytes()
        print(f"  {name:22s} CRLF {b.count(bytes([13, 10])):5d}  "
              f"LF {b.count(bytes([10])):5d}")

print()
pyc = ROOT / "test" / "__pycache__"
if pyc.exists():
    treffer = sorted(x.name for x in pyc.iterdir() if "v022" in x.name)
    print(f"V022-Bytecode-Rueckstand: {treffer if treffer else 'keiner'}")
