"""Stufe 2b: Rollentausch (V1 = kausal), Hindsight-Stil, Q0-Asserts, Dual.

Exakter String-Ersatz in ``test/tmp_png_aug_sichttest.py`` mit Count-Assert
je Anker. Rein V019-wirksame Aenderungen; V01..V018 bleiben byte-identisch.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "test" / "tmp_png_aug_sichttest.py"
src = P.read_text(encoding="utf-8")

PAARE = []
MULTI = []

# ------------------------------------------------------------------ Docstring
PAARE.append((
    "DOC",
    "    ``..._v019_out.txt``.\n",
    "    ``..._v019_out.txt``.\n"
    "    Ab Stufe 2b (E-34n/15) ist der KAUSALE Satz der Primaersatz\n"
    "    (``V1_kausal`` = 23 / +85.577150 R); die Batch-Hysterese\n"
    "    (24 / +88.116626 R) bleibt als ``V1_batch`` ausgewiesen und wird\n"
    "    nur als gedämpftes Hindsight-Artefakt gezeichnet (Abschnitt 54.4).\n",
))

# --------------------------------------------------------- Dataclass-Docstring
PAARE.append((
    "DOC2",
    "        ziel_r_h2_kausal: Soll-R des kausalen H2-Bereichs (0.0 = inaktiv).\n",
    "        ziel_r_h2_kausal: Soll-R des kausalen H2-Bereichs (0.0 = inaktiv).\n"
    "        ziel_trades_hindsight: Soll-Trades des Batch-Hindsight-Laufs\n"
    "            (0 = inaktiv). Nicht handelbar -- nur Provenienz/Ausweis.\n"
    "        ziel_r_hindsight: Soll-R des Batch-Hindsight-Laufs (0.0 inaktiv).\n"
    "        ziel_r_h2_hindsight: Soll-R des Hindsight-H2-Bereichs (0.0).\n",
))

# ------------------------------------------------------------------ Felder
PAARE.append((
    "FELDER",
    "    ziel_trades_kausal: int = 0\n"
    "    ziel_r_kausal: float = 0.0\n"
    "    ziel_r_h2_kausal: float = 0.0\n",
    "    ziel_trades_kausal: int = 0\n"
    "    ziel_r_kausal: float = 0.0\n"
    "    ziel_r_h2_kausal: float = 0.0\n"
    "    ziel_trades_hindsight: int = 0\n"
    "    ziel_r_hindsight: float = 0.0\n"
    "    ziel_r_h2_hindsight: float = 0.0\n",
))

# --------------------------------------------------------- KONFIGURATION_V019
PAARE.append((
    "V019_KOPF",
    "    ziel_trades_gesamt=24,\n"
    "    ziel_r_gesamt=88.116626,\n",
    "    # Stufe 2b: Primaerwert = KAUSAL.\n"
    "    ziel_trades_gesamt=23,\n"
    "    ziel_r_gesamt=85.577150,\n",
))
PAARE.append((
    "V019_H2",
    "    ziel_r_h2=49.197042,          # ZP-5(D): +5.502241 (K82@1172, entry 1173)\n",
    "    ziel_r_h2=46.657566,          # kausal: 49.197042 - 2.539476 (K76@1211)\n",
))
PAARE.append((
    "V019_DELTA",
    "    ziel_delta_rb=40.300929,      # = 88.116626 - 47.815697 (ZP-5(D))\n",
    "    ziel_delta_rb=37.761453,      # = 85.577150 - 47.815697 (kausal)\n",
))
PAARE.append((
    "V019_KAUSALBLOCK",
    "    # --- KAUSALER Sollwert (PRIMAER fuer die Ausfuehrung) ---------------\n"
    "    ziel_trades_kausal=23,        # 24 - 1: K76@1211 faellt weg\n"
    "    ziel_r_kausal=85.577150,      # H2 46.657566 / H1 38.919584\n"
    "    ziel_r_h2_kausal=46.657566,\n",
    "    # --- KAUSALER Sollwert (PRIMAER; == ziel_*_gesamt oben) ------------\n"
    "    ziel_trades_kausal=23,        # 24 - 1: K76@1211 faellt weg\n"
    "    ziel_r_kausal=85.577150,      # H2 46.657566 / H1 38.919584\n"
    "    ziel_r_h2_kausal=46.657566,\n"
    "    # --- HINDSIGHT-/Batch-Referenz (nicht handelbar) -------------------\n"
    "    ziel_trades_hindsight=24,\n"
    "    ziel_r_hindsight=88.116626,\n"
    "    ziel_r_h2_hindsight=49.197042,\n",
))

# ------------------------------------------------------------------ Laeufe
PAARE.append((
    "LAUF",
    "V1_aktiv, st_aktiv = _lauf(adapter, True)\n"
    "# Stufe 2a: KAUSALER Parallel-Lauf (nur V019). Fenster aus dem Adapter\n"
    "# (ADAPTER_V019_KAUSAL) -- der Renderer rechnet KEINE zweite Wahrheit.\n"
    "V1_kausal: list = []\n"
    "st_kausal: dict = {}\n"
    "if KONF.mode == \"V019\":\n"
    "    V1_kausal, st_kausal = _lauf(ADAPTER_V019_KAUSAL, True)\n",
    "V1_aktiv, st_aktiv = _lauf(adapter, True)\n"
    "# Stufe 2b - ROLLENTAUSCH: Primaersatz ist der KAUSALE Lauf; der\n"
    "# Batch-Lauf bleibt als Hindsight-Referenz (V1_batch) erhalten.\n"
    "V1_batch, st_batch = V1_aktiv, st_aktiv\n"
    "# KAUSALER Lauf (nur V019). Fenster aus dem Adapter (ADAPTER_V019_KAUSAL)\n"
    "# -- der Renderer rechnet KEINE zweite Wahrheit.\n"
    "V1_kausal: list = list(V1_aktiv)\n"
    "st_kausal: dict = dict(st_aktiv)\n"
    "if KONF.mode == \"V019\":\n"
    "    V1_kausal, st_kausal = _lauf(ADAPTER_V019_KAUSAL, True)\n",
))

PAARE.append((
    "KEYS",
    "_AKTIV_KEYS = {_key(t) for t in V1_aktiv}\n"
    "_BASIS_KEYS = {_key(t) for t in V1_basis}\n"
    "REFERENZ = [t for t in V1_basis if _key(t) not in _AKTIV_KEYS]\n"
    "NEU = [t for t in V1_aktiv if _key(t) not in _BASIS_KEYS]\n"
    "\n"
    "V1, st1 = V1_aktiv, st_aktiv\n",
    "_AKTIV_KEYS = {_key(t) for t in V1_kausal}\n"
    "_BASIS_KEYS = {_key(t) for t in V1_basis}\n"
    "REFERENZ = [t for t in V1_basis if _key(t) not in _AKTIV_KEYS]\n"
    "NEU = [t for t in V1_kausal if _key(t) not in _BASIS_KEYS]\n"
    "\n"
    "# Primaersatz = KAUSAL (Stufe 2b).\n"
    "V1, st1 = V1_kausal, st_kausal\n"
    "# Hindsight-Artefakte: existieren NUR im Batch-Lauf (Hysterese). Sie\n"
    "# werden gezeichnet (transparent), zaehlen aber NICHT in V1/R1.\n"
    "_HINDSIGHT_KEYS = {(int(_b), int(_k))\n"
    "                   for (_b, _k) in KONF.neu_basis_soll_hindsight}\n"
    "HINDSIGHT_TRADES = [t for t in V1_batch if _key(t) in _HINDSIGHT_KEYS]\n",
))

# ------------------------------------------------------------------ Asserts
PAARE.append((
    "DELTA9",
    "        assert len(V1) - len(V1_basis) == 10, len(V1) - len(V1_basis)\n"
    "        # --- Stufe 2a: DUALES Fail-Loud (kausal primaer, Batch sekundaer)\n"
    "        # Kausal: strikt 1e-6 (Engine rechnet deterministisch).\n"
    "        _h1k = [t for t in V1_kausal if t.entry_bar < box_end]\n"
    "        _h2k = [t for t in V1_kausal if t.entry_bar >= box_end]\n"
    "        assert len(V1_kausal) == KONF.ziel_trades_kausal, (\n"
    "            len(V1_kausal), KONF.ziel_trades_kausal)\n"
    "        assert abs(sum(t.r for t in V1_kausal)\n"
    "                   - KONF.ziel_r_kausal) < 1e-6, sum(\n"
    "            t.r for t in V1_kausal)\n"
    "        assert abs(sum(t.r for t in _h2k)\n"
    "                   - KONF.ziel_r_h2_kausal) < 1e-6, sum(t.r for t in _h2k)\n"
    "        # H1-Invariante: kausal IDENTISCH zur Batch-Box (Box ist etikettfrei)\n"
    "        assert len(_h1k) == KONF.ziel_h1_trades, len(_h1k)\n"
    "        assert abs(sum(t.r for t in _h1k) - KONF.ziel_r_h1) < 1e-6, sum(\n"
    "            t.r for t in _h1k)\n"
    "        # Batch strikt nachgezogen (die geteilten 1e-4-Asserts fuer\n"
    "        # V01..V018 bleiben unangetastet -- arretierte Saetze).\n"
    "        assert abs(R1 - KONF.ziel_r_gesamt) < 1e-6, R1\n",
    "        # Stufe 2b: V1 ist KAUSAL -> 23 - 14 = 9.\n"
    "        assert len(V1) - len(V1_basis) == 9, len(V1) - len(V1_basis)\n"
    "        # --- Stufe 2b: DUALES Fail-Loud. V1 = KAUSAL (primaer, gezeichnet),\n"
    "        # V1_batch = Hindsight-Referenz. Beide strikt 1e-6.\n"
    "        _h1k = [t for t in V1 if t.entry_bar < box_end]\n"
    "        _h2k = [t for t in V1 if t.entry_bar >= box_end]\n"
    "        assert len(V1) == KONF.ziel_trades_kausal, (\n"
    "            len(V1), KONF.ziel_trades_kausal)\n"
    "        assert abs(R1 - KONF.ziel_r_kausal) < 1e-6, R1\n"
    "        assert abs(sum(t.r for t in _h2k)\n"
    "                   - KONF.ziel_r_h2_kausal) < 1e-6, sum(t.r for t in _h2k)\n"
    "        # H1-Invariante: Box ist etikettfrei -> kausal == Batch.\n"
    "        assert len(_h1k) == KONF.ziel_h1_trades, len(_h1k)\n"
    "        assert abs(sum(t.r for t in _h1k) - KONF.ziel_r_h1) < 1e-6, sum(\n"
    "            t.r for t in _h1k)\n"
    "        # Batch-/Hindsight-Referenz strikt nachgezogen.\n"
    "        _h2b = [t for t in V1_batch if t.entry_bar >= box_end]\n"
    "        assert len(V1_batch) == KONF.ziel_trades_hindsight, len(V1_batch)\n"
    "        assert abs(sum(t.r for t in V1_batch)\n"
    "                   - KONF.ziel_r_hindsight) < 1e-6, sum(\n"
    "            t.r for t in V1_batch)\n"
    "        assert abs(sum(t.r for t in _h2b)\n"
    "                   - KONF.ziel_r_h2_hindsight) < 1e-6, sum(t.r for t in _h2b)\n",
))

PAARE.append((
    "NEUSOLL",
    "    _neu_soll = sorted(set(KONF.neu_basis_soll)\n"
    "                       | set(KONF.neu_basis_soll_hindsight))\n",
    "    # Stufe 2b: der Primaersatz ist kausal -> Hindsight-Set NICHT mehr\n"
    "    # Teil des Mengen-Asserts (es steuert nur den Marker-Zweig).\n"
    "    _neu_soll = sorted(KONF.neu_basis_soll)\n",
))

# ------------------------------------------------------------------ Q0-Asserts
PAARE.append((
    "Q0",
    "                    f\"{_sk_ref} ({_sk_ad.segmente[1].phasen_id}) \"\n"
    "                    f\"fehlgeschlagen -- {_sk_exc}\") from _sk_exc\n",
    "                    f\"{_sk_ref} ({_sk_ad.segmente[1].phasen_id}) \"\n"
    "                    f\"fehlgeschlagen -- {_sk_exc}\") from _sk_exc\n"
    "\n"
    "# ---- _q0-Vorbedingung: kausales Etikett entscheidet das Quartilfenster --\n"
    "# ZP-4 (A_VC) setzt _q0 = aktive_phase_bei(k).start_bar. Solange A2 kausal\n"
    "# nicht bestaetigt ist (bis Bar 1249), liefert 1174..1249 A1 -> _q0 = 1033\n"
    "# (Stufe 2b, Abschnitt 54.4). Geprueft wird die EINGANGS-SSoT\n"
    "# ``aktive_phase_bei`` -- die Injektionskette bleibt unberuehrt.\n"
    "if _V19:\n"
    "    assert ADAPTER_V019.aktive_phase_bei(1174).phasen_id == \"A2_AUTO_77\"\n"
    "    assert (ADAPTER_V019_KAUSAL.aktive_phase_bei(1174).phasen_id\n"
    "            == \"A1_AUTO_77\")\n"
    "    assert (ADAPTER_V019_KAUSAL.aktive_phase_bei(1249).phasen_id\n"
    "            == \"A1_AUTO_77\")\n"
    "    assert (ADAPTER_V019_KAUSAL.aktive_phase_bei(1250).phasen_id\n"
    "            == \"A2_AUTO_77\")\n",
))

# ------------------------------------------------------------------ mark_trades
PAARE.append((
    "MARK_KOPF",
    "    ref = stil == \"referenz\"\n"
    "    for t in trades:\n"
    "        col = \"#7f7f7f\" if ref else (C_SHORT if t.richtung == \"SHORT\"\n"
    "                                     else C_LONG)\n"
    "        in_h1 = t.entry_bar < box_end\n"
    "        # Immer farbig gefuellt (Richtung = Farbe). H1/H2 werden NICHT mehr\n"
    "        # ueber die Fuellung, sondern ueber Groesse + Randstaerke getrennt.\n"
    "        # Ausnahme: entfallene V01-Referenz-Trades (Abschnitt 66.4).\n"
    "        ax.plot(t.bar, t.basis, \"o\", ms=9.0 if in_h1 else 10.5, color=col,\n"
    "                zorder=9, mec=col if ref else \"#1a1a1a\",\n"
    "                mew=0.9 if ref else (0.7 if in_h1 else 1.6),\n"
    "                mfc=\"none\" if ref else col, alpha=0.45 if ref else None)\n"
    "        # v0.20 (Route A): G4-Reclaim am ENGINE-berechneten Trade markieren.\n"
    "        # Wirkt nur im Modus V015; Panel 02 (H1) enthaelt keinen G4-Trade,\n"
    "        # die Byte-Invariante d9f35876... ist damit strukturell gesichert.\n"
    "        if not ref and (int(t.bar), int(t.kid)) in G4_MARKE:\n",
    "    ref = stil == \"referenz\"\n"
    "    hin = stil == \"hindsight\"\n"
    "    for t in trades:\n"
    "        col = (\"#7f7f7f\" if (ref or hin)\n"
    "               else (C_SHORT if t.richtung == \"SHORT\" else C_LONG))\n"
    "        in_h1 = t.entry_bar < box_end\n"
    "        # Immer farbig gefuellt (Richtung = Farbe). H1/H2 werden NICHT mehr\n"
    "        # ueber die Fuellung, sondern ueber Groesse + Randstaerke getrennt.\n"
    "        # Ausnahmen (54.2): (a) entfallene V01-Referenz-Trades (66.4);\n"
    "        # (b) Hindsight-Artefakte (54.4) -- ungefuellter grauer Kreis,\n"
    "        # damit ein real nicht existierender Einstieg nie als Position\n"
    "        # gelesen wird.\n"
    "        if hin:\n"
    "            ax.plot(t.bar, t.basis, \"o\", ms=9.0, color=\"#7f7f7f\",\n"
    "                    zorder=12, mec=\"#7f7f7f\", mew=1.4, mfc=\"none\")\n"
    "        else:\n"
    "            ax.plot(t.bar, t.basis, \"o\", ms=9.0 if in_h1 else 10.5,\n"
    "                    color=col, zorder=9, mec=col if ref else \"#1a1a1a\",\n"
    "                    mew=0.9 if ref else (0.7 if in_h1 else 1.6),\n"
    "                    mfc=\"none\" if ref else col,\n"
    "                    alpha=0.45 if ref else None)\n"
    "        # v0.20 (Route A): G4-Reclaim am ENGINE-berechneten Trade markieren.\n"
    "        # Wirkt nur im Modus V015; Panel 02 (H1) enthaelt keinen G4-Trade,\n"
    "        # die Byte-Invariante d9f35876... ist damit strukturell gesichert.\n"
    "        if not (ref or hin) and (int(t.bar), int(t.kid)) in G4_MARKE:\n",
))

PAARE.append((
    "MARK_SPANNE",
    "        ax.plot([t.bar, t.bar], [t.tp2, t.sl], color=col, lw=1.1,\n"
    "                alpha=0.25 if ref else 0.45, ls=\"--\" if ref else \":\",\n"
    "                zorder=6)\n"
    "        if ref:\n",
    "        ax.plot([t.bar, t.bar], [t.tp2, t.sl], color=col, lw=1.1,\n"
    "                alpha=0.25 if ref else (0.50 if hin else 0.45),\n"
    "                ls=\"--\" if (ref or hin) else \":\", zorder=6)\n"
    "        if ref:\n",
))

PAARE.append((
    "MARK_ANNOT",
    "        else:\n"
    "            # Auflage A-3: Kollisions-Offsets fuer das K67-Cluster;\n",
    "        elif hin:\n"
    "            # Stufe 2b / 54.4: Hindsight-Artefakt -- sichtbar, aber\n"
    "            # ausdruecklich als nicht handelbar gekennzeichnet.\n"
    "            ax.annotate(f\"K{t.kid}@{t.bar} HINDSIGHT ({t.r:+.2f} R)\",\n"
    "                        (t.bar, t.basis), textcoords=\"offset points\",\n"
    "                        xytext=(0, -30), ha=\"center\", fontsize=fs - 0.5,\n"
    "                        color=\"#7f7f7f\", zorder=11,\n"
    "                        bbox=dict(boxstyle=\"round,pad=0.18\", fc=\"white\",\n"
    "                                  alpha=0.55, ec=\"#7f7f7f\", lw=0.5,\n"
    "                                  ls=\"--\"))\n"
    "        else:\n"
    "            # Auflage A-3: Kollisions-Offsets fuer das K67-Cluster;\n",
))

# ------------------------------------------------------------------ Legende
PAARE.append((
    "LEG_DEF",
    "# Zusatz-Legende nur im Override-Modus; im Modus V01 bleibt die Legende\n",
    "# Stufe 2b / 54.4: Legenden-Handle des Hindsight-Artefakts. Leer, solange\n"
    "# kein Hindsight-Trade vorliegt -> V01..V018 unveraendert.\n"
    "LEG_HINDSIGHT: list = [] if not HINDSIGHT_TRADES else [\n"
    "    Line2D([0], [0], marker=\"o\", color=\"w\", mfc=\"none\", mec=\"#7f7f7f\",\n"
    "           mew=1.4, ms=9.0, ls=\"--\",\n"
    "           label=\"Hindsight-Artefakt \\u2014 K76@1211, +2.5395 R, \"\n"
    "                 \"Hysterese 77 (nicht handelbar)\"),\n"
    "]\n"
    "\n"
    "# Zusatz-Legende nur im Override-Modus; im Modus V01 bleibt die Legende\n",
))

# ------------------------------------------------------------------ Marker
PAARE.append((
    "P01",
    "        mark_trades(ax1, REFERENZ, fs=7.5, stil=\"referenz\")\n"
    "    mark_trades(ax1, V1, fs=7.5)\n",
    "        mark_trades(ax1, REFERENZ, fs=7.5, stil=\"referenz\")\n"
    "    mark_trades(ax1, V1, fs=7.5)\n"
    "    if HINDSIGHT_TRADES:\n"
    "        mark_trades(ax1, HINDSIGHT_TRADES, fs=7.5, stil=\"hindsight\")\n",
))

PAARE.append((
    "P03",
    "    mark_trades(ax1, h2_1, fs=7.5)\n",
    "    mark_trades(ax1, h2_1, fs=7.5)\n"
    "    if HINDSIGHT_TRADES:\n"
    "        mark_trades(ax1, [t for t in HINDSIGHT_TRADES\n"
    "                          if t.entry_bar >= box_end], fs=7.5,\n"
    "                    stil=\"hindsight\")\n",
))

PAARE.append((
    "P05",
    "        mark_trades(ax1, REFERENZ, fs=7.0, stil=\"referenz\")\n"
    "    mark_trades(ax1, V1, fs=7.0)\n",
    "        mark_trades(ax1, REFERENZ, fs=7.0, stil=\"referenz\")\n"
    "    mark_trades(ax1, V1, fs=7.0)\n"
    "    if HINDSIGHT_TRADES:\n"
    "        mark_trades(ax1, HINDSIGHT_TRADES, fs=7.0, stil=\"hindsight\")\n",
))

MULTI.append((
    "LEGEND_01_03",
    "    legend(ax1, _leg_basis_sweep() + [\n"
    "        Line2D([0], [0], color=\"gray\", ls=\":\", lw=1.0,\n"
    "               label=\"Tombstone-Band (R21)\"),\n"
    "    ] + LEG_MODUS)\n",
    "    legend(ax1, _leg_basis_sweep() + [\n"
    "        Line2D([0], [0], color=\"gray\", ls=\":\", lw=1.0,\n"
    "               label=\"Tombstone-Band (R21)\"),\n"
    "    ] + LEG_MODUS + LEG_HINDSIGHT)\n",
    2,
))

MULTI.append((
    "LEGEND_05",
    "    legend(ax1, _leg_basis_sweep() + [\n"
    "        Line2D([0], [0], color=\"gray\", ls=\":\", lw=1.0,\n"
    "               label=\"Tombstone-Band (R21)\"),\n"
    "        Line2D([0], [0], marker=\"x\", color=\"w\", mfc=\"gray\", ms=6,\n"
    "               label=\"Seed (< 2 Touches)\"),\n"
    "    ] + LEG_MODUS)\n",
    "    legend(ax1, _leg_basis_sweep() + [\n"
    "        Line2D([0], [0], color=\"gray\", ls=\":\", lw=1.0,\n"
    "               label=\"Tombstone-Band (R21)\"),\n"
    "        Line2D([0], [0], marker=\"x\", color=\"w\", mfc=\"gray\", ms=6,\n"
    "               label=\"Seed (< 2 Touches)\"),\n"
    "    ] + LEG_MODUS + LEG_HINDSIGHT)\n",
    1,
))

# ------------------------------------------------------------------ Protokoll
PAARE.append((
    "PROTO",
    "log(f\"  V1_aktiv ({KONF.mode}) : {len(V1):2d} Trades / {R1:+.6f} R  \"\n"
    "    f\"(H1 {len(h1_1)}/{sum(t.r for t in h1_1):+.6f} | \"\n"
    "    f\"H2 {len(h2_1)}/{sum(t.r for t in h2_1):+.6f})\")\n"
    "if KONF.mode == \"V019\":\n"
    "    _h1kc = [t for t in V1_kausal if t.entry_bar < box_end]\n"
    "    _h2kc = [t for t in V1_kausal if t.entry_bar >= box_end]\n"
    "    log(f\"  V1_kausal (LIVE): {len(V1_kausal):2d} Trades / \"\n"
    "        f\"{sum(t.r for t in V1_kausal):+.6f} R  \"\n"
    "        f\"(H1 {len(_h1kc)}/{sum(t.r for t in _h1kc):+.6f} | \"\n"
    "        f\"H2 {len(_h2kc)}/{sum(t.r for t in _h2kc):+.6f})  \"\n"
    "        f\"<- PRIMAER (live-faehig)\")\n"
    "    log(f\"    Batch-Delta : \"\n"
    "        f\"{R1 - sum(t.r for t in V1_kausal):+.6f} R aus \"\n"
    "        f\"{len(V1) - len(V1_kausal)} Hindsight-Trade(s) -- \"\n"
    "        f\"Hysterese {AUTO_VERSCHMELZUNG_SCHWELLE}, NICHT handelbar\")\n",
    "if _V19:\n"
    "    log(f\"  V1_kausal (LIVE, primaer): {len(V1):2d} Trades / \"\n"
    "        f\"{R1:+.6f} R  \"\n"
    "        f\"(H1 {len(h1_1)}/{sum(t.r for t in h1_1):+.6f} | \"\n"
    "        f\"H2 {len(h2_1)}/{sum(t.r for t in h2_1):+.6f})  \"\n"
    "        f\"<- PRIMAER (live-faehig)\")\n"
    "else:\n"
    "    log(f\"  V1_aktiv ({KONF.mode}) : {len(V1):2d} Trades / {R1:+.6f} R  \"\n"
    "        f\"(H1 {len(h1_1)}/{sum(t.r for t in h1_1):+.6f} | \"\n"
    "        f\"H2 {len(h2_1)}/{sum(t.r for t in h2_1):+.6f})\")\n"
    "if KONF.mode == \"V019\":\n"
    "    _h1b = [t for t in V1_batch if t.entry_bar < box_end]\n"
    "    _h2b = [t for t in V1_batch if t.entry_bar >= box_end]\n"
    "    log(f\"  V1_batch (HINDSIGHT)     : {len(V1_batch):2d} Trades / \"\n"
    "        f\"{sum(t.r for t in V1_batch):+.6f} R  \"\n"
    "        f\"(H1 {len(_h1b)}/{sum(t.r for t in _h1b):+.6f} | \"\n"
    "        f\"H2 {len(_h2b)}/{sum(t.r for t in _h2b):+.6f})  \"\n"
    "        f\"<- NICHT handelbar\")\n"
    "    log(f\"    Hindsight-Delta: \"\n"
    "        f\"{sum(t.r for t in V1_batch) - R1:+.6f} R aus \"\n"
    "        f\"{len(V1_batch) - len(V1)} Artefakt-Trade(s) -- \"\n"
    "        f\"Hysterese {AUTO_VERSCHMELZUNG_SCHWELLE}, nicht handelbar\")\n",
))

for _nm, _alt, _neu in PAARE:
    _n = src.count(_alt)
    assert _n == 1, f"Anker {_nm}: {_n} Treffer"
    src = src.replace(_alt, _neu)

for _nm, _alt, _neu, _erw in MULTI:
    _n = src.count(_alt)
    assert _n == _erw, f"Anker {_nm}: {_n} != {_erw}"
    src = src.replace(_alt, _neu)

P.write_text(src, encoding="utf-8", newline="\n")
print(f"OK  {P.name}: {len(PAARE)} Einzel- + {len(MULTI)} Mehrfachanker ersetzt")
print(f"SHA256 neu: {hashlib.sha256(P.read_bytes()).hexdigest()}")
