# -*- coding: utf-8 -*-
"""E-29 (read-only) -- BINNING-AUDIT + H2-STOP-OUT-ANATOMIE.

Aufruf:  python test/_tmp_e29_audit.py <modus> <bins> [geg960poc]

Konfiguration: arretierter E-28-Kernstandard `geg960poc`
  Q29 lokal 960  +  Gegenkante lokal 960-Lebigkeit  +  POC-Anker lokal 960
  (Fenster _W(k) = max(0, k-960) auf allen drei Achsen).

`bins` ueberschreibt `cfg.num_bins` (Default 60) via dataclasses.replace --
nur fuer dieses Skript, die Engine bleibt unangetastet.

Ein Lauf = ein Prozess (E-27/F0). Ausgabe:
  T1  POC-Histogramm-Oekonomie je Trade (Fensterlaenge, Bin-Breite, Fuellung)
  T2  Kennzahlen der Variante (gesamt / H1 / H2)
  T3  Stop-Out-Anatomie (Exit-Rekonstruktion aus der gespeicherten Geometrie)
  T4  Hybrid-Schliessungs-Proxy (Strukturbruch der Einstiegskante)
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib.util
import pickle
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
SPLIT = 17692
W960 = 960
MODE = (sys.argv[1] if len(sys.argv) > 1 else "s2").lower()
BINS = int(sys.argv[2]) if len(sys.argv) > 2 else 60
OUT = ROOT / "test" / f"_tmp_e29_audit_{MODE}_b{BINS}_out.txt"
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

spec = importlib.util.spec_from_file_location("eng", ENGINE_P)
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)
cfg0 = eng.StraightEdgeHarnessKonfiguration()
cfg = dataclasses.replace(cfg0, num_bins=BINS)

t0 = time.time()
if MODE == "s2":
    scan = pickle.loads((ROOT / "test" / "_tmp_s2_scan_cache.pkl").read_bytes())
    box_orig = scan["box_end_bar"]
    scan["box_end_bar"] = scan["n"]
    TITEL = "S2"
else:
    scan = eng._se_scan("AUG", cfg0)
    box_orig = scan["box_end_bar"]
    TITEL = "AUG"
N = scan["n"]
d = scan["d"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
cl = d["close"].to_numpy(float)
ts = d["ts"].to_numpy()

# ------------------------------------------------------------ AST-Extraktion
quelle = ENGINE_P.read_text(encoding="utf-8")
baum = ast.parse(quelle)
knoten = next(n for n in ast.walk(baum)
              if isinstance(n, ast.FunctionDef) and n.name == "_se_trades")
zeilen = quelle.split("\n")
SRC = "\n".join(zeilen[knoten.lineno - 1:knoten.end_lineno])
_n_stat = len(re.findall(r'stats\["(\w+)"\] \+= 1', SRC))
SRC = re.sub(r'stats\["(\w+)"\] \+= 1', r'_hit(_CUR, "\1")', SRC)

ERS = [
    ("""        for richtung in ("SHORT", "LONG"):
            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])""",
     """        for richtung in ("SHORT", "LONG"):
            _CUR[0] = k
            _CUR[1] = richtung
            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])"""),
    # Q29 ratifiziert lokal (E-27)
    ("""        ex_hi = float(np.max(hi[:k + 1]))
        ex_lo = float(np.min(lo[:k + 1]))""",
     """        ex_hi = float(np.max(hi[_W(k):k + 1]))
        ex_lo = float(np.min(lo[_W(k):k + 1]))"""),
    # Gegenkante: E-28 ratifiziert (geg960 = Liveness 960)
    ("""        pool = [e for e in seite_edges[gegenseite]
                if e.erster_pivot_bar + 2 <= k + 1
                and ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                     or e.touch_conf(k) >= 2)]""",
     """        pool = [e for e in seite_edges[gegenseite]
                if e.erster_pivot_bar + 2 <= k + 1
                and _lebt960(e, k)
                and ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                     or e.touch_conf(k) >= 2)]"""),
    # POC-Anker lokal (E-28) -- Wrapper loggt
    ("""            poc = berechne_kausalen_histogramm_poc(
                d, poc_start, k, unter, ober, cfg.num_bins)""",
     """            poc = _poc_log(d, _W(k), k, unter, ober, cfg.num_bins)"""),
    ("""            kd = _kandidat(richtung, k, sweep_px)
            if kd is None:
                continue""",
     """            kd = _kandidat(richtung, k, sweep_px)
            if kd is None:
                _hit(_CUR, "kaskade_leer")
                continue
            _hit(_CUR, "kandidat")"""),
    ("""            if stufe_n == 0:
                continue""",
     """            if stufe_n == 0:
                _hit(_CUR, "stufe0")
                continue"""),
    ("""            letzter_trade[kd.kid] = setup
            setups.append(setup)""",
     """            letzter_trade[kd.kid] = setup
            setups.append(setup)
            _hit(_CUR, "SETUP")"""),
]
for alt, neu in ERS:
    assert alt in SRC, "Ankertext fehlt:\n" + alt[:120]
    SRC = SRC.replace(alt, neu, 1)

_POC_ROH = eng.berechne_kausalen_histogramm_poc
POC_LOG: List[Dict] = []


def _poc_log(df, start, sig, u, o, nb):
    """Wrapper um die Engine-POC (unveraendert) + reine Diagnose-Logging.

    Die Diagnose repliziert die Engine-Binnung exakt; die Uebereinstimmung
    des replizierten POC mit dem Engine-Rueckgabewert wird per assert geprueft.
    """
    poc = _POC_ROH(df, start, sig, u, o, nb)
    sub = df.iloc[start:sig + 1]
    spanne = float(o) - float(u)
    binw = spanne / nb if nb else 0.0
    zero = 0
    share = 0.0
    if not sub.empty and spanne > 0.0:
        edges = np.linspace(u, o, nb + 1)
        vol = np.zeros(nb, dtype=float)
        for l_, h_, v_ in zip(sub["low"].to_numpy(float),
                              sub["high"].to_numpy(float),
                              sub["tick_volume"].to_numpy(float)):
            if h_ <= l_ or v_ <= 0:
                continue
            lb = int(np.clip(np.searchsorted(edges, l_, side="right") - 1,
                             0, nb - 1))
            hb = int(np.clip(np.searchsorted(edges, h_, side="left") - 1,
                             0, nb - 1))
            if lb == hb:
                vol[lb] += v_
            else:
                ov = np.array([max(0.0, min(h_, edges[b + 1]) - max(l_, edges[b]))
                               for b in range(lb, hb + 1)])
                tot = float(ov.sum())
                if tot > 0:
                    vol[lb:hb + 1] += v_ * ov / tot
        zero = int((vol <= 0).sum())
        vs = np.convolve(vol, np.ones(3) / 3.0, mode="same") if nb >= 3 else vol
        s_ = float(vs.sum())
        share = float(vs.max() / s_) if s_ > 0 else 0.0
        idx = int(np.argmax(vs))
        assert abs((edges[idx] + edges[idx + 1]) / 2.0 - poc) < 1e-9, \
            "Diagnose-Replikation weicht vom Engine-POC ab"
    POC_LOG.append({"start": int(start), "sig": int(sig), "n_bars": int(len(sub)),
                    "spanne": spanne, "binw": binw, "zero": zero,
                    "share": share, "poc": float(poc), "u": float(u),
                    "o": float(o)})
    return poc


def _w(k: int) -> int:
    return max(0, k - W960)


def _lebt960(e, k: int) -> bool:
    bars = [b for b, _ in e.wicks if b <= k]
    if not bars:
        return False
    return max(bars) >= k - W960


HITS: List[Tuple[int, str, str]] = []
ns: Dict = dict(eng.__dict__)
ns["_CUR"] = [0, "?"]
ns["_W"] = _w
ns["_lebt960"] = _lebt960
ns["_poc_log"] = _poc_log


def _hit(cur: List, key: str) -> None:
    HITS.append((cur[0], cur[1], key))


ns["_hit"] = _hit
exec(compile(SRC, str(ENGINE_P) + "<e29>", "exec"), ns)  # noqa: S102
fn = ns["_se_trades"]

# --------------------------------------------------------------- Kennzahlen
_tr = np.maximum(hi[1:] - lo[1:],
                 np.maximum(np.abs(hi[1:] - cl[:-1]), np.abs(lo[1:] - cl[:-1])))
_tr = np.concatenate([[hi[1] - lo[1]], _tr])


def atr14(k: int) -> float:
    return float(_tr[max(0, k - 13):k + 1].mean())


def kz(ss: List) -> Dict[str, float]:
    if not ss:
        return {"n": 0, "R": 0.0, "USD": 0.0, "USDn": 0.0, "ATRn": 0.0,
                "Qstop": 0.0}
    r = [float(s.r) for s in ss]
    usd = [float(s.r) * abs(float(s.sl) - float(s.entry)) for s in ss]
    at = [u / atr14(int(s.bar)) for u, s in zip(usd, ss)]
    nstop = sum(1 for x in r if x <= -1.0 + 1e-9)
    return {"n": len(ss), "R": sum(r), "USD": sum(usd),
            "USDn": sum(usd) / len(ss), "ATRn": sum(at) / len(ss),
            "Qstop": nstop / len(ss)}


def exit_anatomie(s) -> Dict:
    """Rekonstruiert beide Halb-Exits aus der gespeicherten Geometrie.

    Identische Logik wie `_c_loese_trade` (Engine Z. 1596-1647); die
    Rekonstruktion wird gegen `s.r` und `s.exit1_bar` verifiziert.
    """
    e_bar = int(s.entry_bar)
    entry = float(s.entry)
    risk = abs(float(s.sl) - entry) or 1e-9
    tp1, tp2, sl = float(s.poc), float(s.tp2), float(s.sl)
    short = s.richtung == "SHORT"
    hh, ll, cc = hi[e_bar:], lo[e_bar:], cl[e_bar:]
    nb = len(hh)

    def first(mask: np.ndarray) -> int:
        return int(np.argmax(mask)) if mask.any() else nb

    if short:
        t1, t2, tsl = first(ll <= tp1), first(ll <= tp2), first(hh >= sl)
    else:
        t1, t2, tsl = first(hh >= tp1), first(hh >= tp2), first(ll <= sl)
    # Kein Stop im Datenfenster -> Sentinel -1 (nicht: nb, das waere Bar nb).
    t_sl_glob = (e_bar + tsl) if tsl < nb else -1
    end = max(1, min(tsl, nb))          # tsl == 0 (Stop am Entry-Bar) -> 1
    mfe = ((entry - float(ll[:end].min())) if short
           else (float(hh[:end].max()) - entry)) / risk
    mae_geg = (float(hh[:end].max()) - entry if short
               else entry - float(ll[:end].min())) / risk
    # Hybrid-Proxy: erster Close jenseits der Einstiegskante (Basis)
    basis = float(s.basis)
    brk = -1
    grenze = tsl if tsl < nb else nb
    for m in range(1, grenze):
        if (short and cc[m] > basis) or ((not short) and cc[m] < basis):
            brk = m
            break
    r_brk = (((entry - cc[brk]) if short else (cc[brk] - entry)) / risk
             if brk >= 0 else None)
    return {"t1": t1, "t2": t2, "tsl": tsl, "tsl_glob": t_sl_glob,
            "mfe": mfe, "mae_geg": mae_geg, "brk": brk,
            "brk_glob": (e_bar + brk) if brk >= 0 else -1,
            "r_brk": r_brk, "risk": risk,
            "d_poc": abs(tp1 - entry) / risk,
            "d_tp2": abs(tp2 - entry) / risk,
            "d_basis": abs(basis - entry) / risk}


t1w = time.time()
setups, stats = fn(scan, cfg)
t_lauf = time.time() - t1w
alle_s = list(setups)

# Setup-Geometrien sichern (fuer pfadgenaue Offline-Gegenproben, z. B.
# Break-Even/Trailing-Studien) -- read-only Spiegel, keine Engine-Aenderung.
import pickle as _pkl  # noqa: E402
_pkl.dump([{f: getattr(s, f) for f in
            ("bar", "richtung", "kid", "basis", "sweep", "trigger_close",
             "touch_n", "poc", "tp2", "sl", "entry", "r", "resultat",
             "entry_bar", "reclaim_bar", "grund1", "exit1_bar", "exit2_bar")}
           for s in alle_s],
          (ROOT / "test" / f"_tmp_e29_setups_{MODE}_b{BINS}.pkl").open("wb"))

h1 = [s for s in alle_s if int(s.bar) < SPLIT]
h2 = [s for s in alle_s if int(s.bar) >= SPLIT]

print("=" * 110)
print(f"E-29 AUDIT -- {TITEL}   Kernstandard geg960poc   num_bins = {BINS}")
print("=" * 110)
print(f"Engine : {ENGINE_P.name}  "
      f"SHA {hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()[:24]}...")
print(f"n {N}  box_end_bar {box_orig} -> Laufgrenze {scan['box_end_bar']}  |  "
      f"Fenster _W(k) = max(0, k-{W960})  |  Q29 + Gegenkante + POC lokal")
print(f"Laufzeit {t_lauf:.1f}s   Setups {len(alle_s)}   POC-Aufrufe {len(POC_LOG)}")

print("")
print("T2 -- KENNZAHLEN")
for name, sset in (("gesamt", alle_s), ("H1", h1), ("H2", h2)):
    k = kz(sset)
    print(f"   {name:<7}: n {k['n']:>4}  R {k['R']:+.6f}  USD {k['USD']:+.4f}  "
          f"USD/Tr {k['USDn']:+.4f}  ATR/Tr {k['ATRn']:+.4f}  "
          f"Q_stop {k['Qstop']:.3f}")

# --------------------------------------------------------------------- T1
print("")
print("T1 -- POC-HISTOGRAMM-OEKONOMIE (je Aufruf; Fenster = [_W(k), k])")
pl = np.array([[p["n_bars"], p["spanne"], p["binw"], p["zero"], p["share"]]
               for p in POC_LOG], dtype=float)
if len(pl):
    print(f"   Aufrufe {len(pl)}   Fenster-Bars  min {pl[:,0].min():.0f}  "
          f"median {np.median(pl[:,0]):.0f}  max {pl[:,0].max():.0f}  "
          f"(vorgesehen {W960})")
    print(f"   Preisspanne  min {pl[:,1].min():.4f}  median "
          f"{np.median(pl[:,1]):.4f}  max {pl[:,1].max():.4f}")
    print(f"   Bin-Breite   min {pl[:,2].min():.6f}  median "
          f"{np.median(pl[:,2]):.6f}  max {pl[:,2].max():.6f}")
    print(f"   leere Bins   mean {pl[:,3].mean():.1f}  median "
          f"{np.median(pl[:,3]):.1f}  max {pl[:,3].max():.0f}  von {BINS}"
          f"   ({pl[:,3].mean() / BINS * 100:.1f} % leer)")
    print(f"   POC-Gewicht mean {pl[:,4].mean() * 100:.2f} %  median "
          f"{np.median(pl[:,4]) * 100:.2f} %  (Anteil des Max-Bins am "
          f"Gewicht)")

# --------------------------------------------------------------------- T3/T4
print("")
print("T3/T4 -- STOP-OUT-ANATOMIE + HYBRID-PROXY  "
      "(Rekonstruktion aus gespeicherter Geometrie)")
print(f"   {'Bar':>6} {'Ri':<6}{'K':>5}{'risk':>8}{'d_POC':>7}{'d_TP2':>7}"
      f"{'d_Basis':>8}{'MFE':>8}{'MAE':>8}{'SL@':>7}{'Bruch@':>8}{'R_brk':>9}"
      f"  Verdikt")
verbesserung = 0
stopouts = 0
for s in sorted(alle_s, key=lambda x: int(x.bar)):
    a = exit_anatomie(s)
    kat = "STOP" if float(s.r) <= -1.0 + 1e-9 else (
        "Teil-SL" if a["tsl"] < min(a["t1"], a["t2"]) or
        float(s.r) < 0 else "ok")
    if kat == "STOP":
        stopouts += 1
    b_txt = f"{a['brk_glob']:>7}" if a["brk"] >= 0 else "      -"
    r_txt = f"{a['r_brk']:>+8.4f}" if a["r_brk"] is not None else "       -"
    if kat == "STOP" and a["r_brk"] is not None and a["r_brk"] > -1.0:
        verbesserung += 1
    print(f"   {int(s.bar):>6} {s.richtung:<6}K{int(s.kid):<4}"
          f"{a['risk']:>8.4f}{a['d_poc']:>7.2f}{a['d_tp2']:>7.2f}"
          f"{a['d_basis']:>8.2f}{a['mfe']:>8.2f}{a['mae_geg']:>8.2f}"
          f"{a['tsl_glob']:>7}{b_txt}{r_txt}  {kat}")

print("")
print("T4b -- AGGREGAT HYBRID-PROXY (nur Verlust-Trades; "
      "R_brk ersetzt r, falls Bruch vor dem Stop)")
_print_r = [float(s.r) for s in alle_s]
_prox_r = list(_print_r)
for i, s in enumerate(alle_s):
    a = exit_anatomie(s)
    if _print_r[i] <= -1.0 + 1e-9 and a["r_brk"] is not None and a["r_brk"] > -1.0:
        _prox_r[i] = a["r_brk"]
_risk = [abs(float(s.sl) - float(s.entry)) for s in alle_s]
_usd = [r * k_ for r, k_ in zip(_print_r, _risk)]
_usd_p = [r * k_ for r, k_ in zip(_prox_r, _risk)]
_q = sum(1 for x in _prox_r if x <= -1.0 + 1e-9) / len(_prox_r) if _prox_r else 0.0
print(f"   Stop-Outs (r <= -1)            : {stopouts} von {len(alle_s)}")
print(f"   mit Strukturbruch vor dem Stop : {verbesserung}")
print(f"   R gesamt   {sum(_print_r):+.6f}  ->  Proxy {sum(_prox_r):+.6f}")
print(f"   USD        {sum(_usd):+.4f}  ->  Proxy {sum(_usd_p):+.4f}")
print(f"   USD/Tr     {sum(_usd)/len(_usd):+.4f}  ->  Proxy "
      f"{sum(_usd_p)/len(_usd_p):+.4f}")
print(f"   Q_stop     {sum(1 for x in _print_r if x <= -1.0+1e-9)/len(_print_r):.3f}"
      f"  ->  Proxy {_q:.3f}")

# ---- T4c Gegenprobe: Bruch-Exit greift mechanisch auf ALLE Trades ---------
_all_r = list(_print_r)
_gekillt = 0
_verlust = 0.0
for i, s in enumerate(alle_s):
    a = exit_anatomie(s)
    if a["r_brk"] is not None and a["r_brk"] < _all_r[i]:
        if _print_r[i] > 0:
            _gekillt += 1
            _verlust += _print_r[i] - a["r_brk"]
        _all_r[i] = a["r_brk"]
_all_usd = [r * k_ for r, k_ in zip(_all_r, _risk)]
print("")
print("T4c -- GEGENPROBE: Bruch-Exit mechanisch auf ALLE Trades")
print(f"   Gewinner, die der Bruch-Exit toeten wuerde : {_gekillt} "
      f"von {sum(1 for x in _print_r if x > 0)} Gewinnern")
print(f"   R-Verlust durch getoetete Gewinner          : {-_verlust:+.6f} R")
print(f"   R gesamt   {sum(_print_r):+.6f}  ->  {sum(_all_r):+.6f}")
print(f"   USD/Tr     {sum(_usd)/len(_usd):+.4f}  ->  "
      f"{sum(_all_usd)/len(_all_usd):+.4f}")
print(f"   Q_stop     "
      f"{sum(1 for x in _print_r if x <= -1.0+1e-9)/len(_print_r):.3f}  ->  "
      f"{sum(1 for x in _all_r if x <= -1.0+1e-9)/len(_all_r):.3f}")
print("")
print("   LEHRE: 'Close jenseits der Einstiegskante' feuert auch auf")
print("   Gewinner (Whipsaw). Der Bruch-Alarm allein ist KEIN Exit-Kriterium")
print("   -- er braucht den Zustandsautomaten (Block A), der Rauschen von")
print("   echter Neu-Deklaration trennt. T4b-tauglich erst dann.")
print("")
print(f"ENDE {TITEL} b{BINS}   Gesamtlaufzeit {time.time() - t0:.1f}s")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
