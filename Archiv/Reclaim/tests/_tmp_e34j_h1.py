# -*- coding: utf-8 -*-
"""E-34j (read-only) -- H1-Trade-Menge ueber die Engine-Generationen.

Vergleicht die H1-Box (entry_bar < box_end) fuer:
  * V016-Motor  = test/_tmp_backup_engine_pre_v017.py   (box_end 640)
  * V017-Motor  = test/_tmp_backup_engine_pre_v018.py   (box_end 640)
  * V018-Motor  = test/tmp_kanten_engine_replay.py      (box_end 644, BKZ)

Zeitbasis: ``ts`` ist Broker-Kerzen-Zeit (BKZ, ``time AT TIME ZONE 'UTC'``),
tz-naiv. Ausgabe in BKZ (Tag.Monat Stunde:Minute).

Rein lesend; keine PNG, kein Schreiben in Engine/Adapter.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

OUT = ROOT / "test" / "_tmp_e34j_h1_out.txt"
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


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


ENGINES = (
    ("V016", ROOT / "test" / "_tmp_backup_engine_pre_v017.py"),
    ("V017", ROOT / "test" / "_tmp_backup_engine_pre_v018.py"),
    ("V018", ROOT / "test" / "tmp_kanten_engine_replay.py"),
)

ergebnis = {}
for tag, p in ENGINES:
    eng = load(f"ke_{tag}", p)
    cfg = eng.StraightEdgeHarnessKonfiguration()
    scan = eng._se_scan("AUG", cfg)
    box_end = int(scan["box_end_bar"])
    ts = scan["d"]["ts"]
    n = int(scan["n"])
    scan["box_end_bar"] = n
    setups, _st = eng._se_trades(scan, cfg)
    h1 = sorted([t for t in setups if t.entry_bar < box_end],
                key=lambda x: x.bar)
    h2 = [t for t in setups if t.entry_bar >= box_end]
    ergebnis[tag] = {"box_end": box_end, "ts": ts, "h1": h1, "h2": h2,
                     "n": n}

print("=" * 108)
print("E-34j H1-MENGE UEBER DIE ENGINE-GENERATIONEN (BKZ = Broker-Kerzen-Zeit)")
print("=" * 108)

for tag in ("V016", "V017", "V018"):
    e = ergebnis[tag]
    ts = e["ts"]
    print(f"\n--- {tag}  box_end={e['box_end']}  n={e['n']}  "
          f"H1={len(e['h1'])} Trades / {sum(t.r for t in e['h1']):+.6f} R  "
          f"| H2={len(e['h2'])} Trades / {sum(t.r for t in e['h2']):+.6f} R ---")
    print(f"  {'sig':>4} {'BKZ sig':>13} {'kid':>4} {'richt':5} "
          f"{'entry':>5} {'BKZ entry':>13} {'r':>11}")
    for t in e["h1"]:
        print(f"  {t.bar:>4} {ts.iloc[t.bar].strftime('%d.%m. %H:%M'):>13} "
              f"{t.kid:>4} {t.richtung:5} {t.entry_bar:>5} "
              f"{ts.iloc[t.entry_bar].strftime('%d.%m. %H:%M'):>13} "
              f"{t.r:>+11.6f}")

print("\n" + "=" * 108)
print("DELTA H1 (Schluessel = (bar, kid))")
print("=" * 108)


def keyset(tag):
    return {(int(t.bar), int(t.kid)) for t in ergebnis[tag]["h1"]}


def rmap(tag):
    return {(int(t.bar), int(t.kid)): t.r for t in ergebnis[tag]["h1"]}


for a, b in (("V016", "V017"), ("V017", "V018"), ("V016", "V018")):
    ka, kb = keyset(a), keyset(b)
    verloren = sorted(ka - kb)
    gewonnen = sorted(kb - ka)
    print(f"\n{a} -> {b}:")
    for k in verloren:
        t = next(t for t in ergebnis[a]["h1"] if (t.bar, t.kid) == k)
        ts = ergebnis[a]["ts"]
        print(f"  VERLOREN {k}  r={t.r:+.6f}  sig "
              f"{ts.iloc[t.bar].strftime('%d.%m. %H:%M')} BKZ  entry "
              f"{ts.iloc[t.entry_bar].strftime('%d.%m. %H:%M')} BKZ")
    for k in gewonnen:
        t = next(t for t in ergebnis[b]["h1"] if (t.bar, t.kid) == k)
        ts = ergebnis[b]["ts"]
        print(f"  GEWONNEN {k}  r={t.r:+.6f}  sig "
              f"{ts.iloc[t.bar].strftime('%d.%m. %H:%M')} BKZ  entry "
              f"{ts.iloc[t.entry_bar].strftime('%d.%m. %H:%M')} BKZ")
    if not verloren and not gewonnen:
        print("  (identische H1-Menge)")
    # R-Vergleich gemeinsamer Schluessel
    ra, rb = rmap(a), rmap(b)
    gemeinsam = sorted(ka & kb)
    diff = [(k, ra[k], rb[k]) for k in gemeinsam if abs(ra[k] - rb[k]) > 1e-9]
    if diff:
        print(f"  R-Abweichungen bei gemeinsamen Schluesseln ({len(diff)}):")
        for k, va, vb in diff:
            print(f"    {k}: {va:+.6f} -> {vb:+.6f} "
                  f"(delta {vb - va:+.6f})")

print("\n" + "=" * 108)
print("KONTEXT: Trades mit entry_bar an der Grenze (BKZ)")
print("=" * 108)
for tag in ("V018",):
    e = ergebnis[tag]
    ts = e["ts"]
    print(f"  {tag} box_end={e['box_end']}: box_end-Bar = "
          f"{ts.iloc[e['box_end']].strftime('%d.%m. %H:%M')} BKZ; "
          f"Bar {e['box_end'] - 1} = "
          f"{ts.iloc[e['box_end'] - 1].strftime('%d.%m. %H:%M')} BKZ; "
          f"Bar {e['box_end'] - 4} = "
          f"{ts.iloc[e['box_end'] - 4].strftime('%d.%m. %H:%M')} BKZ")
    for t in e["h1"][-3:]:
        print(f"    letzte H1-Trades: bar {t.bar} K{t.kid} entry {t.entry_bar}"
              f" = {ts.iloc[t.entry_bar].strftime('%d.%m. %H:%M')} BKZ "
              f"r={t.r:+.6f}")
    for t in sorted(e["h2"], key=lambda x: x.bar)[:3]:
        print(f"    erste H2-Trades : bar {t.bar} K{t.kid} entry {t.entry_bar}"
              f" = {ts.iloc[t.entry_bar].strftime('%d.%m. %H:%M')} BKZ "
              f"r={t.r:+.6f}")

print("\nENDE E-34j")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
