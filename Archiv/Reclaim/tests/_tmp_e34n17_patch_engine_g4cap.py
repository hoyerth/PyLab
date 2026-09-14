# -*- coding: utf-8 -*-
"""Stufe 4b-Nachtrag: Concurrency-Guard auch im G4-Pfad (Bypass schliessen).

ASCII-only, UTF-8/CRLF-erhaltend, Vorab-SHA-Assert, Count-Checks.
"""
import hashlib

P = r"F:\Python\PyLab\test\tmp_kanten_engine_replay.py"
PRE_SHA = "da195c918dd7ae0178444ff05d67f94b86eb76c637ba270b75b3ca335a2dd713"
PRE_BYTES = 199654

OLD = (
    '                _tr_g4 = _c_loese_trade(\r\n'
    '                    hi, lo, cl, _eb_g4, _entry_g4, "LONG", _sl_g4,\r\n'
    '                    _poc_g4, float(_spec_g4.tp2), cfg.tp1_anteil_pct)\r\n'
    '                getradete_entry_bars.add(_eb_g4)\r\n'
)
NEW = (
    '                _tr_g4 = _c_loese_trade(\r\n'
    '                    hi, lo, cl, _eb_g4, _entry_g4, "LONG", _sl_g4,\r\n'
    '                    _poc_g4, float(_spec_g4.tp2), cfg.tp1_anteil_pct)\r\n'
    '                # --- Stufe 4b-Nachtrag (E-34n/17): KEIN Sonderweg ------\r\n'
    '                # Der G4-Reclaim hing bis hier direkt an ``setups`` und\r\n'
    '                # umging die Concurrency-Schranke. Auf AUG folgenlos\r\n'
    '                # (einzelner LONG in P9), aber ein Risikomodul kennt\r\n'
    '                # keine unkontrollierten Nebenwege -> Guard identisch\r\n'
    '                # zum Regel-Loop.\r\n'
    '                if cfg.max_gleichzeitig_je_richtung > 0:\r\n'
    '                    _offen_g4 = _konkurrenz_aktiv(\r\n'
    '                        setups, "LONG", _eb_g4,\r\n'
    '                        _tr_g4.exit1_bar, _tr_g4.exit2_bar)\r\n'
    '                    if _offen_g4 > cfg.max_gleichzeitig_je_richtung:\r\n'
    '                        stats["concurrency_blockiert"] += 1\r\n'
    '                        continue\r\n'
    '                getradete_entry_bars.add(_eb_g4)\r\n'
)


def main() -> None:
    raw = open(P, "rb").read()
    assert len(raw) == PRE_BYTES, ("Pre-Bytes", len(raw))
    h = hashlib.sha256(raw).hexdigest()
    assert h == PRE_SHA, ("Pre-SHA", h)

    txt = raw.decode("utf-8")
    assert txt.count(OLD) == 1, ("OLD", txt.count(OLD))
    txt = txt.replace(OLD, NEW, 1)
    assert txt.count("_konkurrenz_aktiv") == 3, txt.count("_konkurrenz_aktiv")
    assert txt.count("concurrency_blockiert") == 3, \
        txt.count("concurrency_blockiert")

    open(P, "wb").write(txt.encode("utf-8"))
    nb = open(P, "rb").read()
    print("pre  bytes", len(raw), "sha", h)
    print("post bytes", len(nb), "sha", hashlib.sha256(nb).hexdigest())
    print("delta", len(nb) - len(raw))


if __name__ == "__main__":
    main()
