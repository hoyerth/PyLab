# -*- coding: utf-8 -*-
"""Stufe 3 / Phase 1: Engine-Patch (box_end_datum).

ASCII-only, CRLF- und UTF-8-erhaltend, mit Vorab-SHA-Assert und Count-Checks.
"""
import hashlib

P = r"F:\Python\PyLab\test\tmp_kanten_engine_replay.py"
PRE_SHA = "4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a"
PRE_BYTES = 196649

A1_OLD = (
    "    erlaube_loeschung_fuer_prim_anker: bool = False\r\n"
)
A1_NEW = (
    "    erlaube_loeschung_fuer_prim_anker: bool = False\r\n"
    "    # --- Stufe 3 (E-34n/17): Kalenderkante parametrisiert --------------\r\n"
    "    # Die box_end-Kante war bis V019 ein Datums-Literal in ``_se_scan``\r\n"
    "    # und damit ein reines AUG-Artefakt. Sie ist jetzt ein Konfigurations-\r\n"
    "    # feld; der Default haelt jeden historischen Aufruf byte-identisch\r\n"
    "    # (AUG = 644). ISO-8601 (``YYYY-MM-DD``); ``np.datetime64`` parst den\r\n"
    "    # Wert in ``_se_scan``.\r\n"
    "    box_end_datum: str = \"2026-08-19\"\r\n"
)

A2_OLD = (
    "    box_end_bar = int(np.searchsorted(ts_arr, "
    "np.datetime64(\"2026-08-19\")))\r\n"
)
A2_NEW = (
    "    box_end_bar = int(np.searchsorted(ts_arr, "
    "np.datetime64(cfg.box_end_datum)))\r\n"
)


def main() -> None:
    raw = open(P, "rb").read()
    assert len(raw) == PRE_BYTES, ("Pre-Bytes", len(raw))
    h = hashlib.sha256(raw).hexdigest()
    assert h == PRE_SHA, ("Pre-SHA", h)

    txt = raw.decode("utf-8")
    assert txt.count("2026-08-19") == 1, txt.count("2026-08-19")
    assert txt.count(A1_OLD) == 1, ("A1", txt.count(A1_OLD))
    assert txt.count(A2_OLD) == 1, ("A2", txt.count(A2_OLD))

    txt = txt.replace(A1_OLD, A1_NEW, 1)
    txt = txt.replace(A2_OLD, A2_NEW, 1)

    assert "2026-08-19" not in txt.replace('"2026-08-19"', ""), "Restliteral"
    assert txt.count("box_end_datum") == 2, txt.count("box_end_datum")
    assert "np.datetime64(cfg.box_end_datum)" in txt

    open(P, "wb").write(txt.encode("utf-8"))
    nb = open(P, "rb").read()
    print("pre  bytes", len(raw), "sha", h)
    print("post bytes", len(nb), "sha", hashlib.sha256(nb).hexdigest())
    print("delta", len(nb) - len(raw))


if __name__ == "__main__":
    main()
