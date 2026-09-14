# -*- coding: utf-8 -*-
"""Stufe 4 / Schritt 3: Renderer-Re-Pin + R_realisiert-Reporting.

ASCII-only, LF-erhaltend, Vorab-SHA-Assert, Count-Checks.
"""
import hashlib

P = r"F:\Python\PyLab\test\tmp_png_aug_sichttest.py"
PRE_SHA = "6844f3ab4e6ff9ea6152c8e6035727434b13fbd628609a6f01ca2f843a8eaaad"
PRE_BYTES = 119081
OLD_ENGINE = "df92aab57ccded613611b613b6890cc61d49852e123afbd2531c4ead36f60e3c"
NEW_ENGINE = "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"

# --- A) Engine-Pin --------------------------------------------------------
A_OLD = '    "' + OLD_ENGINE + '")\n'
A_NEW = '    "' + NEW_ENGINE + '")\n'

# --- B) Doku + Konfigurationsfelder --------------------------------------
B_OLD = (
    '        ziel_r_h2_hindsight: Soll-R des Hindsight-H2-Bereichs (0.0).\n'
)
B_NEW = (
    '        ziel_r_h2_hindsight: Soll-R des Hindsight-H2-Bereichs (0.0).\n'
    '        ziel_r_realisiert: Soll-R des operativen Realwerts (b): offene\n'
    '            ENDE-Schenkel werden genullt (Mark-to-Market am Fensterende\n'
    '            ist kein realisierter Exit). 0.0 = inaktiv (V01..V018).\n'
    '        ziel_r_untergrenze: Soll-R der Stresstest-Untergrenze (a):\n'
    '            Trades mit mindestens EINEM ENDE-Schenkel entfallen ganz.\n'
    '        ziel_trades_untergrenze: Soll-Trades der Untergrenze (a).\n'
)

B2_OLD = (
    '    ziel_r_h2_hindsight: float = 0.0\n'
)
B2_NEW = (
    '    ziel_r_h2_hindsight: float = 0.0\n'
    '    # --- Stufe 4a (E-34n/17): Realwert-Kennzahlen (0.0 = inaktiv) -------\n'
    '    ziel_r_realisiert: float = 0.0\n'
    '    ziel_r_untergrenze: float = 0.0\n'
    '    ziel_trades_untergrenze: int = 0\n'
)

# --- C) KONFIGURATION_V019 ------------------------------------------------
C_OLD = (
    '    ziel_r_h2_hindsight=49.197042,\n'
)
C_NEW = (
    '    ziel_r_h2_hindsight=49.197042,\n'
    '    # --- Stufe 4a (E-34n/17): Realwert (MESSUNG, kausaler 23er-Satz) ---\n'
    '    ziel_r_realisiert=75.677008,      # (b) ENDE-Schenkel genullt\n'
    '    ziel_r_untergrenze=75.588050,     # (a) 4 ENDE-Trades entfernt\n'
    '    ziel_trades_untergrenze=19,\n'
)

# --- D) Fail-Loud-Asserts ------------------------------------------------
D_OLD = (
    '        assert abs(sum(t.r for t in _h2b)\n'
    '                   - KONF.ziel_r_h2_hindsight) < 1e-6, sum(t.r for t in _h2b)\n'
)
D_NEW = (
    '        assert abs(sum(t.r for t in _h2b)\n'
    '                   - KONF.ziel_r_h2_hindsight) < 1e-6, sum(t.r for t in _h2b)\n'
    '        # --- Stufe 4a (E-34n/17): Realwert-Kennzahlen, strikt typisiert\n'
    '        # aus den durchgereichten _SESetup-Feldern (kein String-Filter).\n'
    '        # (b) R_realisiert: ENDE-Schenkel werden genullt.\n'
    '        # (a) R_untergrenze: Trades mit >= 1 ENDE-Schenkel entfallen.\n'
    '        _w1r = cfg.tp1_anteil_pct / 100.0\n'
    '        R_REAL = sum(\n'
    '            (0.0 if t.grund1 == "ENDE" else _w1r * t.r1)\n'
    '            + (0.0 if t.grund2 == "ENDE" else (1.0 - _w1r) * t.r2)\n'
    '            for t in V1)\n'
    '        _a_set = [t for t in V1\n'
    '                  if t.grund1 != "ENDE" and t.grund2 != "ENDE"]\n'
    '        R_UNT = sum(_w1r * t.r1 + (1.0 - _w1r) * t.r2 for t in _a_set)\n'
    '        assert len(_a_set) == KONF.ziel_trades_untergrenze, len(_a_set)\n'
    '        assert abs(R_REAL - KONF.ziel_r_realisiert) < 1e-6, R_REAL\n'
    '        assert abs(R_UNT - KONF.ziel_r_untergrenze) < 1e-6, R_UNT\n'
)

# --- E) Protokollzeile ---------------------------------------------------
E_OLD = (
    '        f"Hysterese {AUTO_VERSCHMELZUNG_SCHWELLE}, nicht handelbar")\n'
)
E_NEW = (
    '        f"Hysterese {AUTO_VERSCHMELZUNG_SCHWELLE}, nicht handelbar")\n'
    '    log(f"  R_realisiert   : brutto {R1:+.6f} R | "\n'
    '        f"(b) {R_REAL:+.6f} R (ENDE-Schenkel genullt) | "\n'
    '        f"(a) {R_UNT:+.6f} R ({len(_a_set)} Trades, ENDE entfernt)")'
    '\n'
)


def main() -> None:
    raw = open(P, "rb").read()
    assert len(raw) == PRE_BYTES, ("Pre-Bytes", len(raw))
    h = hashlib.sha256(raw).hexdigest()
    assert h == PRE_SHA, ("Pre-SHA", h)

    txt = raw.decode("utf-8")
    for _n, _o in (("A", A_OLD), ("B", B_OLD), ("B2", B2_OLD),
                   ("C", C_OLD), ("D", D_OLD), ("E", E_OLD)):
        assert txt.count(_o) == 1, (_n, txt.count(_o))

    txt = (txt.replace(A_OLD, A_NEW, 1)
              .replace(B_OLD, B_NEW, 1)
              .replace(B2_OLD, B2_NEW, 1)
              .replace(C_OLD, C_NEW, 1)
              .replace(D_OLD, D_NEW, 1)
              .replace(E_OLD, E_NEW, 1))

    assert NEW_ENGINE in txt and OLD_ENGINE not in txt
    # je 4x: Docstring + Feld-Definition + KONFIGURATION_V019 + Assert
    assert txt.count("ziel_r_realisiert") == 4, txt.count("ziel_r_realisiert")
    assert txt.count("ziel_r_untergrenze") == 4, txt.count("ziel_r_untergrenze")
    assert txt.count("ziel_trades_untergrenze") == 4, \
        txt.count("ziel_trades_untergrenze")
    assert txt.count("R_REAL") == 4, txt.count("R_REAL")

    open(P, "wb").write(txt.encode("utf-8"))
    nb = open(P, "rb").read()
    print("pre  bytes", len(raw), "sha", h)
    print("post bytes", len(nb), "sha", hashlib.sha256(nb).hexdigest())
    print("delta", len(nb) - len(raw))


if __name__ == "__main__":
    main()
