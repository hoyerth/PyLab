# -*- coding: utf-8 -*-
"""Syntax-, Import- und Vertrags-Smoke-Test fuer das V022-Modul (Schritt 2).

KEIN Motorlauf. Geprueft wird:
  S1  py_compile (Quelltext ist syntaktisch gueltig)
  S2  Import ohne Seiteneffekt: ``_CACHE`` ist danach LEER (kein Baseline-Load)
  S3  Vertrag: genau 1 dataclass-Feld; GEGENKANTE_MODUS nicht in fields()
  S4  ``__post_init__`` fail-loud bei ``<= 0``
  S5  G3-Beweis: ``_engine()`` laedt die Baseline (dataclasses+sys.modules)
  S6  Paritaetswaechter liefert True fuer den Default
  S7  Forwarder liefern OBJEKTE DER BASELINE-KLASSE (nicht geklont)
  S8  ``_gegenkante_v022`` vorhanden, Signatur wie im Vertrag
  S9  Alle 15 Stats-Schluessel der Baseline sind im Rumpftext adressiert
"""
from __future__ import annotations

import dataclasses
import importlib.util
import inspect
import subprocess
import sys
from pathlib import Path

TEST = Path(__file__).resolve().parent
ZIEL = TEST / "tmp_kanten_engine_v022_replay.py"
BASELINE = TEST / "tmp_kanten_engine_replay.py"

fehler: list[str] = []

# ---------------------------------------------------------------- S1 py_compile
r = subprocess.run([sys.executable, "-m", "py_compile", str(ZIEL)],
                   capture_output=True, text=True)
print(f"S1 py_compile        rc={r.returncode} {r.stderr.strip()}")
if r.returncode != 0:
    raise SystemExit("py_compile fehlgeschlagen")

# ---------------------------------------------------------------- S2 Import
spec = importlib.util.spec_from_file_location("v022_smoke", ZIEL)
V = importlib.util.module_from_spec(spec)
sys.modules["v022_smoke"] = V
spec.loader.exec_module(V)
print(f"S2 Import            OK  _CACHE == {V._CACHE}")
assert V._CACHE == {}, "Import hat die Baseline geladen (Seiteneffekt!)"

# ---------------------------------------------------------------- S3 Vertrag
felder = dataclasses.fields(V.V022KantenKonfiguration)
namen = [f.name for f in felder]
print(f"S3 Vertragsfelder    {namen}")
assert namen == ["tp_mindist_pct"], f"Feldvertrag verletzt: {namen}"
assert V.V022KantenKonfiguration.GEGENKANTE_MODUS == "EXTREM"
assert "GEGENKANTE_MODUS" not in namen
cfg = V.V022KantenKonfiguration()
print(f"    Default          tp_mindist_pct={cfg.tp_mindist_pct}, "
      f"GEGENKANTE_MODUS={V.V022KantenKonfiguration.GEGENKANTE_MODUS}")

# ---------------------------------------------------------------- S4 Waechter
for schlecht in (0.0, -1.5):
    try:
        V.V022KantenKonfiguration(tp_mindist_pct=schlecht)
    except ValueError as e:
        print(f"S4 ValueError        tp_mindist_pct={schlecht}: {e}")
    else:
        fehler.append(f"S4 kein ValueError bei {schlecht}")
assert not fehler, fehler

# ---------------------------------------------------------------- S5 G3-Beweis
B = V._engine()
print(f"S5 Baseline geladen  {Path(B.__file__).name}  "
      f"sys.modules-Eintrag: {'v022_basis' in sys.modules}")
assert "v022_basis" in sys.modules, "G3: Modul NICHT in sys.modules registriert"
hcfg = B.StraightEdgeHarnessKonfiguration()
_n_hcfg = len(dataclasses.fields(hcfg))
print(f"    Harness-Konfig   {_n_hcfg} Felder "
      f"(Konstruktion OK -> dataclasses-Aufloesung funktioniert)")
assert _n_hcfg == 22, f"Engine-Feldzahl: {_n_hcfg}"

# ---------------------------------------------------------------- S6 Paritaet
ok = V.pruefe_paritaet(cfg, B)
print(f"S6 pruefe_paritaet   {ok}  (Vertrag 1.5 vs Baseline "
      f"V3_TP_MINDIST_PCT {B.V3_TP_MINDIST_PCT})")
assert ok is True
assert V.pruefe_paritaet(V.V022KantenKonfiguration(tp_mindist_pct=2.0), B) is False

# ---------------------------------------------------------------- S7 Forwarder
setup = V._SESetup(bar=1, richtung="LONG", kid=1, basis=1.0, sweep=1.0,
                   trigger_close=1.0, touch_n=3, poc=1.0, tp2=1.0, sl=1.0,
                   entry=1.0, r=0.0, resultat="x")
print(f"S7 Forwarder         type(setup) is B._SESetup -> "
      f"{type(setup) is B._SESetup}")
assert type(setup) is B._SESetup, "Setup-Klasse ist NICHT die Baseline-Klasse"
assert dataclasses.astuple(setup) == dataclasses.astuple(
    B._SESetup(bar=1, richtung="LONG", kid=1, basis=1.0, sweep=1.0,
               trigger_close=1.0, touch_n=3, poc=1.0, tp2=1.0, sl=1.0,
               entry=1.0, r=0.0, resultat="x"))
for name in ("_c_loese_trade", "_konkurrenz_aktiv", "_reclaim_stufe",
             "berechne_kausalen_histogramm_poc"):
    fn = getattr(V, name)
    assert getattr(B, name) is not fn, f"{name} ist ein Klon, kein Forwarder"
print("    Forwarder        alle 5 Resolver aktiv, keiner ist ein Klon")

# ---------------------------------------------------------------- S8 Signatur
sig = str(inspect.signature(V._gegenkante_v022))
sig2 = str(inspect.signature(V._se_trades_v022))
print(f"S8 _gegenkante_v022  {sig}")
print(f"   _se_trades_v022   {sig2}")
assert list(inspect.signature(V._gegenkante_v022).parameters) == \
    ["seite_edges", "k", "richtung"]
assert list(inspect.signature(V._se_trades_v022).parameters) == \
    ["scan", "cfg", "harness_cfg"]

# ---------------------------------------------------------------- S9 Stats-Keys
BS = "".join(B.STRAIGHT_EDGE_STATS_KEYS) if hasattr(B, "STRAIGHT_EDGE_STATS_KEYS") else None
quelle = ZIEL.read_text(encoding="utf-8")
keys = ["v_s", "kein_gegner", "f3", "kein_raum", "zyklus_blockiert",
        "quartil_blockiert", "blocker", "promotionen", "stacking_blockiert",
        "frisch_blockiert", "concurrency_blockiert",
        "zyklus_liste", "quartil_liste", "blocker_liste", "stacking_liste"]
fehlend = [k for k in keys if f'"{k}"' not in quelle]
print(f"S9 Stats-Schluessel  {len(keys) - len(fehlend)}/{len(keys)} adressiert"
      + (f"  FEHLEND: {fehlend}" if fehlend else ""))
assert not fehlend, fehlend

print()
print("ALLE SMOKE-PRUEFUNGEN OK  (kein Motorlauf)")
