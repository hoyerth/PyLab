# -*- coding: utf-8 -*-
"""test/tmp_kanten_engine_k20_trace.py -- Lifecycle-Trace K20 (rein lesend).

Instrumentiert den ECHTEN Harness (test/tmp_kanten_engine_replay.py) per
Wrapper um _body_bruch / _verarbeite_pivot und protokolliert:

  1) Jeden AKTIV->SCHLAFEND-Uebergang (2-Body-Bruch) mit Kante, Bar k und den
     beteiligten Kerzen (open/close) - liefert die EXAKTE Bruch-Bar.
  2) Jedes UNTEN-Pivot im Band 62.8..64.8 (Region K1/K11/K19/K20/K21) mit
     SwingFilter-Klassifikation und Outcome (Geburt/Touch/verworfen).

Keine Engine-Aenderung, keine Feature-Logik - reines Audit.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(r"test").resolve()))
import tmp_kanten_engine_replay as eng

WANT_BODY = {1, 11, 19, 20, 21}
REGION = (62.8, 64.8)

_orig_body_bruch = eng._body_bruch
_orig_verarbeite_pivot = eng._verarbeite_pivot


def _body_trace(kanten, k, op, cl):
    """Loggt 2-Body-Bruch-Kandidaten VOR dem echten Uebergang."""
    for k2 in kanten.values():
        if k2.zustand != "AKTIV" or k2.kanten_id not in WANT_BODY:
            continue
        bal = k2.balance_preis
        if k2.seite == "OBEN":
            out = min(op[k - 1], cl[k - 1]) > bal and min(op[k], cl[k]) > bal
        else:
            out = max(op[k - 1], cl[k - 1]) < bal and max(op[k], cl[k]) < bal
        if out:
            print(
                f"  [2BODY->SCHLAFEND] k={k:4d} kid={k2.kanten_id:2d} "
                f"bal={bal:8.3f} | bar {k-1}: O {op[k-1]:8.3f} C {cl[k-1]:8.3f} "
                f"| bar {k}: O {op[k]:8.3f} C {cl[k]:8.3f}"
            )
    _orig_body_bruch(kanten, k, op, cl)


def _piv_trace(m, typ, hi, lo, vol, ts_vals, kanten, last_ref):
    seite = "OBEN" if typ == "H" else "UNTEN"
    preis = float(hi[m]) if typ == "H" else float(lo[m])
    ts = pd_timestamp(ts_vals[m])
    region = seite == "UNTEN" and REGION[0] <= preis <= REGION[1]
    if region:
        ref = last_ref["L" if typ == "H" else "H"]
        if ref["bar"] < 0:
            amp, herkunft = float("inf"), False
        else:
            amp = abs(preis - ref["preis"]) / ref["preis"] * 100.0
            herkunft = bool(ref["kanten_ereignis"])
        n_vorher = {k2.kanten_id: len(k2.touche) for k2 in kanten.values()}
        ids_vorher = set(kanten)
    _orig_verarbeite_pivot(m, typ, hi, lo, vol, ts_vals, kanten, last_ref)
    if region:
        neu = [k2 for k2 in kanten.values() if k2.kanten_id not in ids_vorher]
        getroffen = [
            k2 for k2 in kanten.values()
            if k2.kanten_id in n_vorher and len(k2.touche) > n_vorher[k2.kanten_id]
            and k2.letzter_touch_bar == m
        ]
        if neu:
            out = f"GEBURT K{neu[0].kanten_id} (basis {preis:.3f})"
        elif getroffen:
            k2 = getroffen[0]
            out = (f"TOUCH K{k2.kanten_id:2d} (bal {k2.balance_preis:8.3f}, "
                   f"jetzt {len(k2.touche)} Touches, zustand {k2.zustand})")
        else:
            out = "VERWORFEN (kein Touch/Geburt)"
        print(
            f"  [PIVOT] {ts:%m-%d %H:%M} bar {m:4d} L preis {preis:8.3f} "
            f"amp {amp:6.2f}% herkunft={herkunft} -> {out}"
        )


def pd_timestamp(x):
    import pandas as pd
    return pd.Timestamp(x)


eng._body_bruch = _body_trace
eng._verarbeite_pivot = _piv_trace

print("=== AUG/mt60: K20/K21-Lifecycle + UNTEN-Pivots 62.8..64.8 ===")
erg = eng._replay("AUG", eng.HarnessKonfiguration(max_tage=60))
print()
for kid in (20, 21):
    k2 = erg.kanten.get(kid)
    if k2 is None:
        print(f"K{kid}: nicht vorhanden")
        continue
    print(f"K{kid} {k2.seite} Geburt bar {k2.geburts_bar} "
          f"({k2.geburts_ts:%m-%d %H:%M}) basis {k2.basis_preis:.3f} "
          f"balance {k2.balance_preis:.3f} zustand {k2.zustand} "
          f"touches {k2.touch_anzahl}")
    for t in k2.touche:
        print(f"    Touch bar {t.pivot_bar:4d} ({t.ts:%m-%d %H:%M}) {t.preis:.3f}")
