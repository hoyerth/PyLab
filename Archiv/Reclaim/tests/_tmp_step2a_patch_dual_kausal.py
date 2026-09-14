"""Schritt 2a: dualer kausaler Lauf + Fail-Loud-Asserts im Renderer.

Patched ``test/tmp_png_aug_sichttest.py`` mit exaktem String-Ersatz
(Count-Assert je Anker, fail-loud) und LF-Erhalt. Rein additive, auf V019
gated Aenderungen; V01..V018 bleiben verhaltensidentisch.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "test" / "tmp_png_aug_sichttest.py"
src = P.read_text(encoding="utf-8")

PAARE = []

# ------------------------------------------------------------------ (1) Import
PAARE.append((
    "IMPORT",
    "from backtest_lab.phasen_regime_adapter import (  # noqa: E402\n"
    "    ADAPTER_V014, ADAPTER_V015, ADAPTER_V019, BASELINE_V01_H2_R,\n",
    "from backtest_lab.phasen_regime_adapter import (  # noqa: E402\n"
    "    ADAPTER_V014, ADAPTER_V015, ADAPTER_V019, ADAPTER_V019_KAUSAL,\n"
    "    AUTO_VERSCHMELZUNG_SCHWELLE, BASELINE_V01_H2_R,\n",
))

# ------------------------------------------------------------- (2) Docstring
PAARE.append((
    "DOC",
    "        neu_basis_soll: Soll-Menge der Neuzugaenge ohne den G4-Zusatz.\n"
    "            ``(1002, 77)`` wird bei ``g4_aktiv`` automatisch ergaenzt.\n",
    "        neu_basis_soll: Soll-Menge der Neuzugaenge ohne den G4-Zusatz.\n"
    "            ``(1002, 77)`` wird bei ``g4_aktiv`` automatisch ergaenzt.\n"
    "        neu_basis_soll_hindsight: Soll-Menge der Neuzugaenge, die NUR im\n"
    "            Batch-/Hindsight-Lauf existieren (Hysterese-Artefakt der\n"
    "            rueckwirkenden Etikettierung). Im kausalen Lauf entfallen\n"
    "            sie. V019: ``((1211, 76),)`` (Bar 1211 SHORT K76).\n"
    "        ziel_trades_kausal: Soll-Trades des KAUSALEN Laufs (Stufe 2a).\n"
    "            0 = kein Kausal-Assert -> V01..V018 unveraendert.\n"
    "        ziel_r_kausal: Soll-R des kausalen Laufs (0.0 = inaktiv).\n"
    "        ziel_r_h2_kausal: Soll-R des kausalen H2-Bereichs (0.0 = inaktiv).\n",
))

# ---------------------------------------------------------------- (3) Felder
PAARE.append((
    "FELDER",
    "    niveauwechsel_gesamt: int = 205\n"
    "    niveauwechsel_baseline: int = 205\n"
    "    netto_preiswechsel_baseline: int = 54\n",
    "    niveauwechsel_gesamt: int = 205\n"
    "    niveauwechsel_baseline: int = 205\n"
    "    netto_preiswechsel_baseline: int = 54\n"
    "    # --- Stufe 2a: KAUSALER Parallel-Sollwert (E-34n/15 D6) -------------\n"
    "    # Defaults = inaktiv -> V01..V018 bleiben verhaltensidentisch.\n"
    "    neu_basis_soll_hindsight: Tuple[Tuple[int, int], ...] = ()\n"
    "    ziel_trades_kausal: int = 0\n"
    "    ziel_r_kausal: float = 0.0\n"
    "    ziel_r_h2_kausal: float = 0.0\n",
))

# ------------------------------------------------------ (4) KONFIGURATION_V019
PAARE.append((
    "V019_NEU_SOLL",
    "    neu_basis_soll=((903, 67), (980, 67), (981, 73), (1075, 62), (1122, 73),\n"
    "                    (1172, 82), (1211, 76), (1268, 76), (1272, 73),\n"
    "                    (1280, 76)),\n",
    "    neu_basis_soll=((903, 67), (980, 67), (981, 73), (1075, 62), (1122, 73),\n"
    "                    (1172, 82), (1268, 76), (1272, 73), (1280, 76)),\n"
    "    # Hysterese-Artefakt (Stufe 2b: gedampfter Marker, KEINE Loeschung).\n"
    "    neu_basis_soll_hindsight=((1211, 76),),\n"
    "    # --- KAUSALER Sollwert (PRIMAER fuer die Ausfuehrung) ---------------\n"
    "    ziel_trades_kausal=23,        # 24 - 1: K76@1211 faellt weg\n"
    "    ziel_r_kausal=85.577150,      # H2 46.657566 / H1 38.919584\n"
    "    ziel_r_h2_kausal=46.657566,\n",
))

# ------------------------------------ (5) Scan-Abgleich: BEIDE V019-Adapter
PAARE.append((
    "SCANCHECK",
    "if _V19:\n"
    "    _SK_KATALOG = list(scan[\"edges\"]) + list(scan[\"seeds\"])\n"
    "    for _sk_ref in sorted({int(_s.start_bar) for _s in adapter.segmente}):\n"
    "        try:\n"
    "            adapter.verifiziere_gegen_scan(\n"
    "                [(_e.kid, _e.seite, float(_e.basis_bei(_sk_ref)))\n"
    "                 for _e in _SK_KATALOG])\n"
    "        except ValueError as _sk_exc:\n"
    "            raise SystemExit(\n"
    "                \"Modus V019: verifiziere_gegen_scan @REF \"\n"
    "                f\"{_sk_ref} fehlgeschlagen -- {_sk_exc}\") from _sk_exc\n",
    "if _V19:\n"
    "    _SK_KATALOG = list(scan[\"edges\"]) + list(scan[\"seeds\"])\n"
    "    for _sk_ad in (adapter, ADAPTER_V019_KAUSAL):\n"
    "        for _sk_ref in sorted({int(_s.start_bar)\n"
    "                               for _s in _sk_ad.segmente}):\n"
    "            try:\n"
    "                _sk_ad.verifiziere_gegen_scan(\n"
    "                    [(_e.kid, _e.seite, float(_e.basis_bei(_sk_ref)))\n"
    "                     for _e in _SK_KATALOG])\n"
    "            except ValueError as _sk_exc:\n"
    "                raise SystemExit(\n"
    "                    \"Modus V019: verifiziere_gegen_scan @REF \"\n"
    "                    f\"{_sk_ref} ({_sk_ad.segmente[1].phasen_id}) \"\n"
    "                    f\"fehlgeschlagen -- {_sk_exc}\") from _sk_exc\n",
))

# --------------------------------------------------- (6) vierter Lauf kausal
PAARE.append((
    "KAUSAL_LAUF",
    "V1_aktiv, st_aktiv = _lauf(adapter, True)\n",
    "V1_aktiv, st_aktiv = _lauf(adapter, True)\n"
    "# Stufe 2a: KAUSALER Parallel-Lauf (nur V019). Fenster aus dem Adapter\n"
    "# (ADAPTER_V019_KAUSAL) -- der Renderer rechnet KEINE zweite Wahrheit.\n"
    "V1_kausal: list = []\n"
    "st_kausal: dict = {}\n"
    "if KONF.mode == \"V019\":\n"
    "    V1_kausal, st_kausal = _lauf(ADAPTER_V019_KAUSAL, True)\n",
))

# ----------------------------------------------- (7) V019-Assert-Verankerung
PAARE.append((
    "KAUSAL_ASSERT",
    "        assert len(V1) - len(V1_basis) == 10, len(V1) - len(V1_basis)\n",
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
))

# ------------------------------------------------- (8) NEU-Soll: Hindsight
PAARE.append((
    "NEU_SOLL",
    "    _neu_soll = sorted(KONF.neu_basis_soll)\n"
    "    if KONF.g4_aktiv:\n",
    "    _neu_soll = sorted(set(KONF.neu_basis_soll)\n"
    "                       | set(KONF.neu_basis_soll_hindsight))\n"
    "    if KONF.g4_aktiv:\n",
))

# ------------------------------------------------- (9) Protokoll dual
PAARE.append((
    "PROTOKOLL",
    "log(f\"  V1_aktiv ({KONF.mode}) : {len(V1):2d} Trades / {R1:+.6f} R  \"\n"
    "    f\"(H1 {len(h1_1)}/{sum(t.r for t in h1_1):+.6f} | \"\n"
    "    f\"H2 {len(h2_1)}/{sum(t.r for t in h2_1):+.6f})\")\n",
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
))

for _nm, _alt, _neu in PAARE:
    _n = src.count(_alt)
    assert _n == 1, f"Anker {_nm}: {_n} Treffer"
    src = src.replace(_alt, _neu)

P.write_text(src, encoding="utf-8", newline="\n")
print(f"OK  {P.name}: {len(PAARE)} Anker ersetzt")
print(f"SHA256 neu: {hashlib.sha256(P.read_bytes()).hexdigest()}")
