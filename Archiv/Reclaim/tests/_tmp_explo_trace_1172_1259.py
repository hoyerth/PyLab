# -*- coding: utf-8 -*-
"""READ-ONLY-DIAGNOSE: Filterkette LONG in den Fenstern Bar 1160-1180 / 1250-1270.

Zweck: Bars 1172 (K82 3. Touch) und 1259 (K82 4. Touch) sind weder Q29- noch
M6-gesperrt -- es muss ein Spaetfilter greifen (Stufe / F3-Frische / Zyklus /
Gegner / Mindestabstand / POC / TP2 / Dedup). Diese Datei instrumentiert die
QUELLE von ``_se_trades`` (reine Trace-Insertionen, KEINE Logikaenderung),
schreibt sie als Wegwerf-Engine nach ``test/_tmp_engine_v017trace.py`` und
laesst den Renderer-KOPF (alles vor dem Plot-Teil, also ohne PNG) genau EINMAL
darueber laufen.

Inertheitsnachweis: der Lauf mit der Trace-Engine muss exakt 17 Trades und
R1 = +65.835576 liefern (V017-Sollwerte §72.6). Erst dann ist der Trace gueltig.

Kein Schreiben in den Produktionssatz; die Wegwerf-Engine liegt in ``test/``
und ist gitignored.
"""
from __future__ import annotations

import pathlib
import sys
import types
from typing import Dict, List

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
ROOT = pathlib.Path(__file__).resolve().parent.parent
RENDERER = ROOT / "test" / "tmp_png_aug_sichttest.py"
ENGINE = ROOT / "test" / "tmp_kanten_engine_replay.py"
TRACED = ROOT / "test" / "_tmp_engine_v017trace.py"
TRACE = ROOT / "test" / "_tmp_explo_trace_out.txt"

ZIEL_TRADES = 17
ZIEL_R1 = 65.835576

# ------------------------------------------- 1) Quelle von _se_trades holen
src_lines = ENGINE.read_text(encoding="utf-8").split("\n")
start = None
for i, l in enumerate(src_lines):
    if l.startswith("def _se_trades("):
        start = i
        break
assert start is not None, "_se_trades nicht gefunden"
end = start + 1
while end < len(src_lines):
    l = src_lines[end]
    if l and not l[0].isspace():
        break
    end += 1
func_src = "\n".join(src_lines[start:end])
print(f"[setup] _se_trades Z.{start + 1}..{end} ({len(func_src)} Zeichen)")

# ------------------------------------------- 2) Trace-Insertionen (pur)
INS_HEAD = '''    blocker_liste: List[str] = []

    _TRACE_BARS = set(range(1160, 1181)) | set(range(1250, 1271))

    def _tw(*a: object) -> None:
        if richtung != "LONG" or k not in _TRACE_BARS:
            return
        with open(_TRACE_PATH, "a", encoding="utf-8") as _fh:
            _fh.write(" ".join(str(x) for x in a) + "\\n")
'''

REPL: List[tuple] = [
    # (0) Trace-Infrastruktur
    ("    blocker_liste: List[str] = []\n", INS_HEAD),

    # (A) Kandidat + Pool-Evidenz (jede UNTEN-Linie mit dist/exist/touch/lebt)
    ("            kd = _kandidat(richtung, k, sweep_px)\n",
     "            kd = _kandidat(richtung, k, sweep_px)\n"
     "            if richtung == \"LONG\" and k in _TRACE_BARS:\n"
     "                _seite_l = \"OBEN\" if richtung == \"SHORT\" else \"UNTEN\"\n"
     "                _tw(\"==\", k, richtung, \"sweep\", round(sweep_px, 4),\n"
     "                    \"kd\", (kd.kid if kd is not None else None))\n"
     "                for _e in seite_edges[_seite_l]:\n"
     "                    _b = _e.basis_bei(k)\n"
     "                    _d = ((sweep_px - _b) if richtung == \"SHORT\"\n"
     "                          else (_b - sweep_px)) / _b * 100.0\n"
     "                    if not (abs(_d) < 3.0 or _e is kd):\n"
     "                        continue\n"
     "                    _tw(\"   K\", _e.kid,\n"
     "                        \"basis\", round(_b, 4),\n"
     "                        \"dist%\", round(_d, 4),\n"
     "                        \"exist\", _existiert(_e, k),\n"
     "                        \"touch\", _e.touch_conf(k),\n"
     "                        \"etabliert\", _etabliert(_e, k),\n"
     "                        \"lebt\", _lebt(_e, k),\n"
     "                        \"ank\", _e.ist_prim_anker,\n"
     "                        \"sweepbar\", _e.letzter_sweep_bar)\n"),

    # (B) M6
    ("            blk = _blockiert_durch_aussenkante(richtung, k, kd, sweep_px)\n",
     "            blk = _blockiert_durch_aussenkante(richtung, k, kd, sweep_px)\n"
     "            if blk is not None:\n"
     "                _tw(\"   M6-BLOCK K\", blk.kid, round(blk.basis_bei(k), 4))\n"),

    # (C) Q29
    ("            if not _im_aussenquartil(richtung, k, sweep_px):\n",
     "            if richtung == \"LONG\" and k in _TRACE_BARS:\n"
     "                _ex_hi = float(np.max(hi[:k + 1]))\n"
     "                _ex_lo = float(np.min(lo[:k + 1]))\n"
     "                _sp = _ex_hi - _ex_lo\n"
     "                _dq = (0.0 if _sp <= 0 else\n"
     "                       ((_ex_hi - sweep_px) if richtung == \"SHORT\"\n"
     "                        else (sweep_px - _ex_lo)) / _sp * 100.0)\n"
     "                _tw(\"   Q29 dist%\", round(_dq, 4),\n"
     "                    \"grenze\", cfg.quartil_distanz_pct,\n"
     "                    \"ok\", _im_aussenquartil(richtung, k, sweep_px))\n"
     "            if not _im_aussenquartil(richtung, k, sweep_px):\n"),

    # (D) Stufe
    ("            if stufe_n == 0:\n",
     "            _tw(\"   STUFE\", stufe_n, stufe_name, \"basis\", round(basis, 4),\n"
     "                \"lo[k]\", round(float(lo[k]), 4))\n"
     "            if stufe_n == 0:\n"),

    # (E) F3-Frische
    ("            if k <= kd.letzter_sweep_bar:\n",
     "            _tw(\"   F3 k\", k, \"<= letzter_sweep_bar\",\n"
     "                kd.letzter_sweep_bar, \"->\", k <= kd.letzter_sweep_bar)\n"
     "            if k <= kd.letzter_sweep_bar:\n"),

    # (F) Zyklus
    ("            _vor_zeit = letzter_trade.get(kd.kid)\n",
     "            _vor_zeit = letzter_trade.get(kd.kid)\n"
     "            _tw(\"   ZYKLUS vor_zeit\",\n"
     "                (None if _vor_zeit is None else\n"
     "                 (_vor_zeit.entry_bar, round(_vor_zeit.r, 4))),\n"
     "                \"entry_bar\", entry_bar, \"abstand\",\n"
     "                (None if _vor_zeit is None\n"
     "                 else entry_bar - _vor_zeit.entry_bar),\n"
     "                \"grenze\", cfg.retest_zyklus_bars)\n"),

    # (G) Gegenkante + Mindestabstand
    ("            gegen_basis = geg.basis_bei(k)\n",
     "            gegen_basis = geg.basis_bei(k)\n"
     "            _tw(\"   GEGNER K\", geg.kid, \"basis\", round(gegen_basis, 4),\n"
     "                \"dist%\", round(abs(gegen_basis - basis) / basis * 100.0, 4),\n"
     "                \"mindist%\", V3_TP_MINDIST_PCT)\n"),

    # (H) POC-Bedingung
    ("            if not (unter < poc < ober):\n",
     "            _tw(\"   POC\", round(poc, 4), \"unter\", round(unter, 4),\n"
     "                \"ober\", round(ober, 4), \"ok\", (unter < poc < ober))\n"
     "            if not (unter < poc < ober):\n"),

    # (I) Dedup + TP2-Bedingung
    ("            if entry_bar in getradete_entry_bars:   # B23-3: Dedup\n",
     "            _tw(\"   DEDUP entry_bar\", entry_bar, \"bereits_getradet\",\n"
     "                entry_bar in getradete_entry_bars,\n"
     "                \"sl\", round(sl, 4), \"entry\", round(float(op[entry_bar]), 4),\n"
     "                \"poc\", round(poc, 4), \"tp2\", round(tp2, 4),\n"
     "                \"sl<e<poc<tp2\", (sl < float(op[entry_bar]) < poc < tp2))\n"
     "            if entry_bar in getradete_entry_bars:   # B23-3: Dedup\n"),

    # (J) Trade
    ("            setups.append(setup)\n",
     "            _tw(\"   >>> TRADE\", k, \"K\", kd.kid, \"entry_bar\", entry_bar,\n"
     "                \"r\", round(setup.r, 6))\n"
     "            setups.append(setup)\n"),
]

probe = func_src
for old, new in REPL:
    cnt = probe.count(old)
    if cnt != 1:
        raise SystemExit(f"TRACE-ANKER NICHT EINDEUTIG ({cnt}x): {old!r}")
    probe = probe.replace(old, new)

# ------------------------------------------- 3) Wegwerf-Engine schreiben
src_lines[start:end] = probe.split("\n")
traced_src = "\n".join(src_lines)
traced_src += (f"\n\n# --- TRACE (Wegwerf, READ-ONLY) ---\n"
               f"_TRACE_PATH = r\"{TRACE}\"\n")
TRACED.write_text(traced_src, encoding="utf-8", newline="\r\n")
print(f"[setup] Trace-Engine -> {TRACED.name} "
      f"({TRACED.stat().st_size} B, {len(traced_src.splitlines())} Zeilen)")
TRACE.write_text("", encoding="utf-8")

# ------------------------------------------- 4) Renderer-Kopf einmal laufen
HEAD = RENDERER.read_text(encoding="utf-8").split(
    "# ---------------------------------------------------------------- Plot")[0]
mod = types.ModuleType("explo_trace")
mod.__file__ = str(RENDERER)
sys.modules[mod.__name__] = mod
ns: Dict = mod.__dict__
_old_argv = sys.argv
sys.argv = ["t", "--mode", "V017", "--engine", "test/_tmp_engine_v017trace.py",
            "--probe-praefix", "_explo_",
            "--protokoll-nach", "test/_tmp_explo_out.txt"]
# WICHTIG: der Kopf ersetzt sys.stdout durch einen eigenen TextIOWrapper. Wird
# dieser wieder freigegeben, schliesst er den gemeinsamen Puffer -> spaetere
# print()-Aufrufe scheitern. Deshalb bleibt der Kopf-Wrapper aktiv (UTF-8).
exec(compile(HEAD, "<head_trace>", "exec"), ns)
sys.argv = _old_argv

V1 = list(ns["V1"])
n = ns["n"]
r1 = sum(t.r for t in V1)
print(f"[check] Trace-Lauf: {len(V1)} Trades | R1 = {r1:+.6f}")
print(f"[check] Soll (V017): {ZIEL_TRADES} Trades | R1 = {ZIEL_R1:+.6f} "
      f"-> inert: {len(V1) == ZIEL_TRADES and abs(r1 - ZIEL_R1) < 1e-5}")

# ------------------------------------------- 5) Trace lesen + aufbereiten
lines = TRACE.read_text(encoding="utf-8").splitlines()
print(f"\n[out] {TRACE.name}: {len(lines)} Zeilen")

import pandas as pd  # noqa: E402

ts = pd.to_datetime(ns["scan"]["d"]["ts"])


def _dump(lo_bar: int, hi_bar: int) -> None:
    print("\n" + "=" * 104)
    print(f"TRACE LONG | Bars {lo_bar}..{hi_bar}")
    print("=" * 104)
    cur: List[str] = []
    for line in lines:
        if line.startswith("=="):
            b = int(line.split()[1])
            if cur:
                if lo_bar <= cur_b <= hi_bar:
                    print("\n".join(cur))
                    print("-" * 104)
            cur, cur_b = [line], b
        else:
            cur.append(line)
    if cur and lo_bar <= cur_b <= hi_bar:
        print("\n".join(cur))
    print("=" * 104)


_dump(1160, 1181)
_dump(1250, 1271)
