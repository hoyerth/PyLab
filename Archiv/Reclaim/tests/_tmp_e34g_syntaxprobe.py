# -*- coding: utf-8 -*-
"""E-34g (read-only) -- Syntax-/Konstruktions-Probe des Gutachten-Diffs.

Extrahiert den §B-Codeblock aus ``test/_tmp_e34g_diff_gutachten.md``,
fuehrt ihn im NAMESPACE des echten Adapters aus (``exec``, kein Schreiben)
und laesst danach die Fail-Loud-Pruefer laufen.

Damit ist bewiesen: der vorgeschlagene Codeblock ist syntaktisch korrekt,
kollidiert mit keinem bestehenden Namen und erzeugt eine gueltige Generation.
Die Zieldatei ``backtest_lab/phasen_regime_adapter.py`` bleibt unberuehrt.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ADAPTER_P = ROOT / "backtest_lab" / "phasen_regime_adapter.py"
GUTACHTEN = ROOT / "test" / "_tmp_e34g_diff_gutachten.md"
OUT = ROOT / "test" / "_tmp_e34g_syntaxprobe_out.txt"
_FH = OUT.open("w", encoding="utf-8", newline="\n")


class _Tee:
    def write(self, s: str) -> int:
        _FH.write(s)
        _FH.flush()
        return sys.__stdout__.write(s)

    def flush(self) -> None:
        _FH.flush()
        sys.__stdout__.flush()


sys.stdout = _Tee()  # type: ignore[assignment]

print("=" * 96)
print("E-34g SYNTAX-/KONSTRUKTIONSPROBE DES GUTACHTEN-DIFFS (read-only)")
print("=" * 96)

sha_vorher = hashlib.sha256(ADAPTER_P.read_bytes()).hexdigest()
print(f"Adapter-SHA vorher : {sha_vorher}")

text = GUTACHTEN.read_text(encoding="utf-8")
start = text.index("## B · Der vollstaendige Diff")
block = text.index("```python", start)
ende = text.index("```", block + 10)
code = text[block + len("```python"):ende]
print(f"Codeblock: {len(code.splitlines())} Zeilen extrahiert.")

# Adapter als Namespace laden (ohne Seiteneffekt auf die Datei).
spec = importlib.util.spec_from_file_location("pra", ADAPTER_P)
pra = importlib.util.module_from_spec(spec)
sys.modules["pra"] = pra
spec.loader.exec_module(pra)
ns = dict(pra.__dict__)

namen_vorher = set(ns)
try:
    exec(compile(code, "<e34g_diff_block>", "exec"), ns)
    print("exec: OK (syntaktisch korrekt)")
except SyntaxError as exc:
    print(f"exec: SYNTAXFEHLER {exc}")
    _FH.close()
    sys.stdout = sys.__stdout__
    raise SystemExit(1)
ausserhalb = {"dataclass", "__builtins__", "__name__"}
neue = sorted(n for n in set(ns) - namen_vorher if not n.startswith("__")
              and n not in ausserhalb)
print(f"Neue Namen im Namespace: {neue}")

ADAPTER_V019 = ns["ADAPTER_V019"]
AKTIVE_SEGMENTE_V019 = ns["AKTIVE_SEGMENTE_V019"]
PhasenReifeKonfiguration = ns["PhasenReifeKonfiguration"]

print("\n--- Struktur ---")
print(f"  AKTIVE_SEGMENTE_V019 = "
      f"{[s.phasen_id for s in AKTIVE_SEGMENTE_V019]}")
print(f"  ADAPTER_V019.segmente = "
      f"{[s.phasen_id for s in ADAPTER_V019.segmente]}")
print(f"  P9-Boden-Literal (uebernommen): "
      f"{ADAPTER_V019.segmente[0].boden_deklariert_literal}")
print(f"  P9-Override (uebernommen)     : "
      f"{ADAPTER_V019.segmente[0].decke.niveau_override}")
for s in ADAPTER_V019.segmente[1:]:
    print(f"  {s.phasen_id}: {s.start_bar}..{s.end_bar} "
          f"K{s.decke.kid}/K{s.boden.kid} "
          f"tol={s.provenienz_toleranz_pct} "
          f"literal={s.boden_deklariert_literal}")

print("\n--- Plateau-SSoT ---")
for schwelle in (40, 41, 77, 114, 115):
    k = PhasenReifeKonfiguration(verschmelzungs_schwelle=schwelle)
    print(f"  d={schwelle:>4}: ist_im_plateau={k.ist_im_plateau()}")

print("\n--- Nahtstellen (fail-closed) ---")
for k in (1020, 1021, 1032, 1033, 1173, 1174, 1287, 1288):
    m = ADAPTER_V019.hook_2_ziel(k, "SHORT").modus.value
    s = ADAPTER_V019.aktive_phase_bei(k)
    print(f"  bar {k:>4}: {m:<10} phase={s.phasen_id if s else None}")
akt = sum(1 for k in range(1021, 1288)
          if ADAPTER_V019.aktive_phase_bei(k) is not None)
print(f"  aktive Phasen 1021..1287: {akt} / 267")

print("\n--- Fail-Loud-Pruefer gegen den echten Scan ---")
eng_spec = importlib.util.spec_from_file_location(
    "eng", ROOT / "test" / "tmp_kanten_engine_replay.py")
eng = importlib.util.module_from_spec(eng_spec)
sys.modules["eng"] = eng
eng_spec.loader.exec_module(eng)
scan = eng._se_scan("AUG", eng.StraightEdgeHarnessKonfiguration())
for ref in (848, 980, 1259):
    kanten = [(e.kid, e.seite, float(e.basis_bei(ref)))
              for e in list(scan["edges"]) + list(scan["seeds"])]
    try:
        ADAPTER_V019.verifiziere_gegen_scan(kanten)
        print(f"  REF {ref:>4}: verifiziere_gegen_scan OK")
    except ValueError as exc:
        print(f"  REF {ref:>4}: FEHLER {exc}")
for label, fn in (("verifiziere_niveau_overrides",
                   ADAPTER_V019.verifiziere_niveau_overrides),
                  ("verifiziere_boden_literale",
                   ADAPTER_V019.verifiziere_boden_literale)):
    try:
        fn()
        print(f"  {label:<30} OK")
    except ValueError as exc:
        print(f"  {label:<30} FEHLER {exc}")

print("\n--- Inertheit: Bestand unberuehrt ---")
print(f"  DEFAULT_ADAPTER.segmente: "
      f"{[s.phasen_id for s in pra.DEFAULT_ADAPTER.segmente]}")
print(f"  ADAPTER_V015.segmente   : "
      f"{[s.phasen_id for s in pra.ADAPTER_V015.segmente]}")
print(f"  P9.phasen_id            : {pra.P9.phasen_id}")
print(f"  P9_BODEN_RECLAIM is S0  : "
      f"{ADAPTER_V019.segmente[0] is pra.P9_BODEN_RECLAIM}")

sha_nachher = hashlib.sha256(ADAPTER_P.read_bytes()).hexdigest()
print(f"\nAdapter-SHA nachher: {sha_nachher}")
print(f"BIT-IDENTISCH: {sha_vorher == sha_nachher}")
print("\nENDE E-34g-Syntaxprobe")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
