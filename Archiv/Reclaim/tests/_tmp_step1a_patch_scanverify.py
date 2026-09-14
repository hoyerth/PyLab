"""Schritt 1a: verankert ``verifiziere_gegen_scan`` im Renderer-V019-Pfad.

Ersetzt genau EINE Ankerzeile in ``test/tmp_png_aug_sichttest.py`` und fuegt
dahinter den V019-gated Fail-Loud-Block ein. Count-Assert (fail-loud), LF-
Erhalt, danach separat ``py_compile``. Kein weiterer Eingriff.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "test" / "tmp_png_aug_sichttest.py"

ANCHOR = 'scan["box_end_bar"] = n                       # Voll-Lauf (arretierte Basis)'

BLOCK = '''scan["box_end_bar"] = n                       # Voll-Lauf (arretierte Basis)

# ---- Fail-Loud: Scan-Abgleich der Phasenkanten (Adapter-Vertrag v0.24) -----
# ``PhasenRegimeAdapter.verifiziere_gegen_scan`` ist im Adapter selbst als
# Renderer-Pflicht dokumentiert (phasen_regime_adapter.py Z. 686: "laeuft im
# Renderer/Test"), lief bis E-34n/15 aber ausschliesslich in test/-Pruefern ->
# kalter Vertrag. Hier fest im V019-Pfad verankert: jede Phasenkante muss im
# Scan-Katalog existieren, die Seite muss stimmen und die kausale Basis muss
# innerhalb der Provenienz-Toleranz liegen.
# Gated auf V019: V01..V018 bleiben byte-identisch (kein neuer Codepfad).
# Referenzbars sind datengetrieben aus den Segmentstaenden abgeleitet (848 /
# 1033 / 1174) -- kein Bar-Literal.
if _V19:
    _SK_KATALOG = list(scan["edges"]) + list(scan["seeds"])
    for _sk_ref in sorted({int(_s.start_bar) for _s in adapter.segmente}):
        try:
            adapter.verifiziere_gegen_scan(
                [(_e.kid, _e.seite, float(_e.basis_bei(_sk_ref)))
                 for _e in _SK_KATALOG])
        except ValueError as _sk_exc:
            raise SystemExit(
                "Modus V019: verifiziere_gegen_scan @REF "
                f"{_sk_ref} fehlgeschlagen -- {_sk_exc}") from _sk_exc'''

src = P.read_text(encoding="utf-8")
assert src.count(ANCHOR) == 1, f"Anker nicht eindeutig: {src.count(ANCHOR)}"
out = src.replace(ANCHOR, BLOCK)
assert out != src
P.write_text(out, encoding="utf-8", newline="\n")

print(f"OK  {P.name}: {len(src):,} -> {len(out):,} Zeichen")
print(f"SHA256 neu: {hashlib.sha256(P.read_bytes()).hexdigest()}")
