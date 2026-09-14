# -*- coding: utf-8 -*-
"""Stufe 3 / Phase 2: Renderer-Guard V019 harmonisieren.

ASCII-only, LF-erhaltend, Vorab-SHA-Assert, Count-Checks.
"""
import hashlib

P = r"F:\Python\PyLab\test\tmp_png_aug_sichttest.py"
PRE_SHA = "cb302fc7ea80bdf5b30a0de829265587bcceb157cc855c3c776ac2722d15b416"
PRE_BYTES = 118127
NEW_ENGINE_SHA = "df92aab57ccded613611b613b6890cc61d49852e123afbd2531c4ead36f60e3c"

OLD = (
    'if KONF.mode == "V019" and box_end != 644:\n'
    '    raise SystemExit(\n'
    '        f"Modus V019 erfordert die V018-Engine (BKZ/UTC, box_end 644), "\n'
    '        f"geladen wurde box_end={box_end} ({ENGINE_NAME} "\n'
    '        f"{ENGINE_SHA[:16]}...).")\n'
)

NEW = (
    '# Stufe 3 (E-34n/17): Zero-Trust-Harmonisierung des V019-Guards.\n'
    '# Die fruehere Bar-Pruefung (box_end != 644) war eine reine\n'
    '# Engine-Identitaetspruefung und ist nach der Parametrisierung von\n'
    '# ``box_end_datum`` nicht mehr selbsttragend (Befund B1: ein Abgleich\n'
    '# gegen dieselbe searchsorted-Formel waere tautologisch). Der Guard\n'
    '# prueft daher ZWEI unabhaengige Dinge: (1) den deterministischen\n'
    '# Soll-Bar des AUG-Fensters, (2) den urkundlichen Engine-SHA.\n'
    '# Gekapselt auf V019 -> V017/V018 unberuehrt (Befund B2).\n'
    '_V019_BOX_END_SOLL: Final[int] = 644\n'
    '_V019_ENGINE_SHA_SOLL: Final[str] = (\n'
    f'    "{NEW_ENGINE_SHA}")\n'
    'if KONF.mode == "V019":\n'
    '    if box_end != _V019_BOX_END_SOLL:\n'
    '        raise SystemExit(\n'
    '            f"Modus V019 erfordert den AUG-Soll-Bar "\n'
    '            f"{_V019_BOX_END_SOLL}, geladen wurde box_end={box_end} "\n'
    '            f"({ENGINE_NAME} {ENGINE_SHA[:16]}...).")\n'
    '    if ENGINE_SHA != _V019_ENGINE_SHA_SOLL:\n'
    '        raise SystemExit(\n'
    '            "Modus V019 erfordert die Stufe-3-Engine (E-34n/17) "\n'
    '            f"SHA {_V019_ENGINE_SHA_SOLL[:16]}..., geladen wurde "\n'
    '            f"{ENGINE_SHA[:16]}... ({ENGINE_NAME}).")\n'
)


def main() -> None:
    raw = open(P, "rb").read()
    assert len(raw) == PRE_BYTES, ("Pre-Bytes", len(raw))
    h = hashlib.sha256(raw).hexdigest()
    assert h == PRE_SHA, ("Pre-SHA", h)

    txt = raw.decode("utf-8")
    assert txt.count(OLD) == 1, ("OLD", txt.count(OLD))
    txt = txt.replace(OLD, NEW, 1)

    assert txt.count("_V019_ENGINE_SHA_SOLL") == 3, txt.count(
        "_V019_ENGINE_SHA_SOLL")
    assert txt.count("_V019_BOX_END_SOLL") == 3, txt.count(
        "_V019_BOX_END_SOLL")
    # V017/V018-Guards unberuehrt:
    assert 'if KONF.mode == "V017" and box_end != 640:' in txt
    assert 'if KONF.mode == "V018" and box_end != 644:' in txt

    open(P, "wb").write(txt.encode("utf-8"))
    nb = open(P, "rb").read()
    print("pre  bytes", len(raw), "sha", h)
    print("post bytes", len(nb), "sha", hashlib.sha256(nb).hexdigest())
    print("delta", len(nb) - len(raw))


if __name__ == "__main__":
    main()
