# -*- coding: utf-8 -*-
"""Stufe 4 (Batch 4a+4b): Engine-Patch.

  * _SESetup: grund2/r1/r2 (Durchreichung)
  * _c_loese_trade-Werte an beiden Konstruktionsstellen
  * Concurrency-Schranke Cap = 3 je Richtung + Helfer _konkurrenz_aktiv
  * stats-Zaehler concurrency_blockiert

ASCII-only, UTF-8/CRLF-erhaltend, Vorab-SHA-Assert, Count-Checks.
"""
import hashlib

P = r"F:\Python\PyLab\test\tmp_kanten_engine_replay.py"
PRE_SHA = "df92aab57ccded613611b613b6890cc61d49852e123afbd2531c4ead36f60e3c"
PRE_BYTES = 197093

# --- 1) Konfigurationsfeld -----------------------------------------------
C1_OLD = (
    '    box_end_datum: str = "2026-08-19"\r\n'
)
C1_NEW = (
    '    box_end_datum: str = "2026-08-19"\r\n'
    '    # --- Stufe 4b (E-34n/17): Concurrency-Schranke ----------------------\r\n'
    '    # Hoechstzahl GLEICHZEITIG offener Positionen je Richtung. AUG\r\n'
    '    # erreicht hoechstens 3 gleichzeitige SHORTs (K67@903 / K67@980 /\r\n'
    '    # K73@981, alle Exit 991) -> Cap 3 ist auf dem arretierten Fenster\r\n'
    '    # inert; die bindende Wirkung ist erst im Zweitfenster belegbar\r\n'
    '    # (Bindetest: test/_chk_v019_cap_bindetest.py). 0 = Schranke aus.\r\n'
    '    max_gleichzeitig_je_richtung: int = 3\r\n'
)

# --- 2) _SESetup-Felder + Helfer -----------------------------------------
C2_OLD = (
    '    exit2_bar: int = -1\r\n'
    '\r\n'
    '\r\n'
    'def _se_trades(scan: Dict, cfg: StraightEdgeHarnessKonfiguration\r\n'
)
C2_NEW = (
    '    exit2_bar: int = -1\r\n'
    '    # --- Stufe 4a (E-34n/17): Schenkel-Durchreichung ---------------------\r\n'
    '    # ``_c_loese_trade`` berechnet r1/r2/grund1/grund2 bereits vollstaendig;\r\n'
    '    # bis Stufe 4a wurden grund2/r1/r2 bei der _SESetup-Instanziierung\r\n'
    '    # verworfen. Die Durchreichung ist rein additiv (Defaults = inert).\r\n'
    '    grund2: str = ""\r\n'
    '    r1: float = 0.0\r\n'
    '    r2: float = 0.0\r\n'
    '\r\n'
    '\r\n'
    'def _konkurrenz_aktiv(\r\n'
    '    setups: List["_SESetup"],\r\n'
    '    richtung: SignalRichtung,\r\n'
    '    entry_bar: int,\r\n'
    '    exit1_bar: int,\r\n'
    '    exit2_bar: int,\r\n'
    ') -> int:\r\n'
    '    """Gleichzeitig offene Positionen DERSELBEN Richtung (inkl. Kandidat).\r\n'
    '\r\n'
    '    Eine Position ist von ``entry_bar`` bis ``max(exit1_bar, exit2_bar)``\r\n'
    '    offen (Haltedauer inklusiv; ein Exit-Bar < Entry gilt als Entry-Bar).\r\n'
    '    Gemessen wird der Ueberlapp mit dem Kandidaten; dieser zaehlt selbst\r\n'
    '    mit (Rueckgabe >= 1).\r\n'
    '    """\r\n'
    '    neu_von = int(entry_bar)\r\n'
    '    neu_bis = max(int(exit1_bar), int(exit2_bar), neu_von)\r\n'
    '    anzahl = 1\r\n'
    '    for s in setups:\r\n'
    '        if s.richtung != richtung:\r\n'
    '            continue\r\n'
    '        von = int(s.entry_bar)\r\n'
    '        bis = max(int(s.exit1_bar), int(s.exit2_bar), von)\r\n'
    '        if von <= neu_bis and neu_von <= bis:\r\n'
    '            anzahl += 1\r\n'
    '    return anzahl\r\n'
    '\r\n'
    '\r\n'
    'def _se_trades(scan: Dict, cfg: StraightEdgeHarnessKonfiguration\r\n'
)

# --- 3) stats-Zaehler -----------------------------------------------------
C3_OLD = (
    '                             "frisch_blockiert": 0}\r\n'
)
C3_NEW = (
    '                             "frisch_blockiert": 0,\r\n'
    '                             "concurrency_blockiert": 0}\r\n'
)

# --- 4) Guard im Trade-Loop ----------------------------------------------
C4_OLD = (
    '            trade = _c_loese_trade(\r\n'
    '                hi, lo, cl, entry_bar, entry, richtung, sl, poc, tp2,\r\n'
    '                cfg.tp1_anteil_pct)\r\n'
    '            if entry_bar in getradete_entry_bars:   # B23-3: Dedup\r\n'
)
C4_NEW = (
    '            trade = _c_loese_trade(\r\n'
    '                hi, lo, cl, entry_bar, entry, richtung, sl, poc, tp2,\r\n'
    '                cfg.tp1_anteil_pct)\r\n'
    '            # --- Stufe 4b (E-34n/17): Concurrency-Schranke (Klumpenrisiko) -\r\n'
    '            # Schutz gegen ungedecktes paralleles Engagement in EINER\r\n'
    '            # Richtung. Auf AUG hoechstens 3 gleichzeitig -> inert; die\r\n'
    '            # Wirkung ist maschinell im Bindetest nachgewiesen.\r\n'
    '            if cfg.max_gleichzeitig_je_richtung > 0:\r\n'
    '                _offen = _konkurrenz_aktiv(\r\n'
    '                    setups, richtung, entry_bar,\r\n'
    '                    trade.exit1_bar, trade.exit2_bar)\r\n'
    '                if _offen > cfg.max_gleichzeitig_je_richtung:\r\n'
    '                    stats["concurrency_blockiert"] += 1\r\n'
    '                    continue\r\n'
    '            if entry_bar in getradete_entry_bars:   # B23-3: Dedup\r\n'
)

# --- 5) Konstruktionsstelle 1 --------------------------------------------
C5_OLD = (
    '                grund1=trade.grund1, exit1_bar=trade.exit1_bar,\r\n'
    '                exit2_bar=trade.exit2_bar)\r\n'
)
C5_NEW = (
    '                grund1=trade.grund1, exit1_bar=trade.exit1_bar,\r\n'
    '                exit2_bar=trade.exit2_bar,\r\n'
    '                grund2=trade.grund2, r1=trade.r1, r2=trade.r2)\r\n'
)

# --- 6) Konstruktionsstelle 2 (G4) ---------------------------------------
C6_OLD = (
    '                    ist_prim_anker=False, grund1=_tr_g4.grund1,\r\n'
    '                    exit1_bar=int(_tr_g4.exit1_bar),\r\n'
    '                    exit2_bar=int(_tr_g4.exit2_bar)))\r\n'
)
C6_NEW = (
    '                    ist_prim_anker=False, grund1=_tr_g4.grund1,\r\n'
    '                    exit1_bar=int(_tr_g4.exit1_bar),\r\n'
    '                    exit2_bar=int(_tr_g4.exit2_bar),\r\n'
    '                    grund2=_tr_g4.grund2, r1=_tr_g4.r1,\r\n'
    '                    r2=_tr_g4.r2)))\r\n'
)


def main() -> None:
    raw = open(P, "rb").read()
    assert len(raw) == PRE_BYTES, ("Pre-Bytes", len(raw))
    h = hashlib.sha256(raw).hexdigest()
    assert h == PRE_SHA, ("Pre-SHA", h)

    txt = raw.decode("utf-8")
    for _name, _old in (("C1", C1_OLD), ("C2", C2_OLD), ("C3", C3_OLD),
                        ("C4", C4_OLD), ("C5", C5_OLD), ("C6", C6_OLD)):
        assert txt.count(_old) == 1, (_name, txt.count(_old))

    txt = (txt.replace(C1_OLD, C1_NEW, 1)
              .replace(C2_OLD, C2_NEW, 1)
              .replace(C3_OLD, C3_NEW, 1)
              .replace(C4_OLD, C4_NEW, 1)
              .replace(C5_OLD, C5_NEW, 1)
              .replace(C6_OLD, C6_NEW, 1))

    assert txt.count("max_gleichzeitig_je_richtung") == 3, \
        txt.count("max_gleichzeitig_je_richtung")   # 1x Feld + 2x Vergleich
    assert txt.count("_konkurrenz_aktiv") == 2, txt.count("_konkurrenz_aktiv")
    assert txt.count("concurrency_blockiert") == 2, \
        txt.count("concurrency_blockiert")
    # je 2 Bestands-Returns (_loese_trade/_c_loese_trade) + 2 neue Stellen
    assert txt.count("grund2=") == 4, txt.count("grund2=")
    assert txt.count("r1=") == 4, txt.count("r1=")

    open(P, "wb").write(txt.encode("utf-8"))
    nb = open(P, "rb").read()
    print("pre  bytes", len(raw), "sha", h)
    print("post bytes", len(nb), "sha", hashlib.sha256(nb).hexdigest())
    print("delta", len(nb) - len(raw))


if __name__ == "__main__":
    main()
