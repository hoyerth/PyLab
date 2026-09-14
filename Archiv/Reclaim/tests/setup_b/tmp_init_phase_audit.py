# -*- coding: utf-8 -*-
"""AUG-Initialisierungsphasen-Audit (Pullback-Struktur vor dem ersten echten Swing).

Arbeitsauftrag: Relativ-Distanz (Phasenstart -> Signal) fuer alle 27 Baseline-
Trades; Fokus P5-Fehl-Shorts T9-T11 & T26 (27.08): Signale in der fruehen
Initialisierungsphase VOR dem ersten nennenswerten Pullback? Kontrast mit
Winnern (T14/T15 & restliche 10). Reine Analyse, kein Produktivcode.

Methodik (kausal, Fenster i_start..signal_bar k):
  - exec-Import wie tmp_baseline_loss_replay.py (Cut nach Baseline-Signal-Loop),
    27/27 Mapping gegen test/stats_trades_AUG.txt.
  - Fade-Richtung = Trade-Typ (SHORT -> Gegenzug = Retracement vom laufenden
    Hoch; LONG -> vom laufenden Tief).
  - retr_cl[j] = M[j] - cl[j]  (SHORT/up) bzw. cl[j] - m[j] (LONG/down);
    retr_lo[j]/retr_hi[j] analog intrabar. M[j]=max(hi[i0..j]), m[j]=min(lo[i0..j]).
  - Schwellen 0.15 / 0.30 USD (= etablierte Distanzgroesse §8.10; bei 64-69 USD
    ~0.22-0.46 %). 'Pullback vor Signal' = erste Bar j < k mit retr_cl >= Schwelle.
  - Pivot-Struktur: find_pivots (Produktions-Identik, Lookback 2) auf Gesamt-df;
    bestaetigt nur j <= k - LOOKBACK (kein Lookahead). 'Initialimpuls ohne
    bestaetigten Gegenseiten-Pivot' = kein L-Pivot (bei SHORT) / H-Pivot (LONG)
    bis k-2.
Ausgabe: test/tmp_init_phase_audit_AUG.txt (UTF-8).
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path("test/tmp_init_phase_audit_AUG.txt")
_buf: list[str] = []


def out(*a: object) -> None:
    _buf.append(" ".join(str(x) for x in a))


# ---------------------------------------------------------------- exec-Import
src = io.open("scripts/phasen_volumen_profil.py", encoding="utf-8").read()
_marker = "reclaim_signals.sort(key=lambda s: s.ts)"
_cut = src.rindex(_marker) + len(_marker)
ns: dict = {"__file__": str(Path("scripts/phasen_volumen_profil.py").resolve())}
exec(compile(src[:_cut], "phasen_volumen_profil.py", "exec"), ns)  # noqa: S102

df = ns["df"]
phases = ns["phases"]
sigs: list = ns["reclaim_signals"]
LOOKBACK: int = int(ns["PIVOT_LOOKBACK"])
hi = df["high"].values
lo = df["low"].values
cl = df["close"].values
tsa = df["ts"].values
assert len(sigs) == 27, len(sigs)

# Pivot-Tabelle (Produktions-Identik, Z. 361) + Bar-Index je Pivot
piv = ns["find_pivots"](df.reset_index(drop=True), n=LOOKBACK).sort_values("ts").reset_index(drop=True)
ts_to_bar = {t: i for i, t in enumerate(tsa)}
piv_rows = []
for _, r in piv.iterrows():
    b = ts_to_bar.get(r["ts"])
    if b is not None:
        piv_rows.append((b, r["typ"], float(r["price"])))
piv_rows.sort()
piv_bars = np.array([x[0] for x in piv_rows], dtype=int)
piv_typs = np.array([x[1] for x in piv_rows])
piv_prs = np.array([x[2] for x in piv_rows])

# ---------------------------------------------------------------- Log-Parsing (Mapping-Verifikation)
log_txt = io.open("test/stats_trades_AUG.txt", encoding="utf-8").read().split("Modus: --macro-live")[0]
rows: list[dict] = []
_in = False
for l in log_txt.splitlines():
    if l.startswith("TRADE-LOG"):
        _in = True
        continue
    if not _in or "|" not in l:
        continue
    p = [x.strip() for x in l.split("|")]
    if len(p) < 9:
        continue
    try:
        rows.append({"nr": int(p[0]), "phase": int(p[1]), "bar_sig": int(p[2]),
                     "bar_entry": int(p[3]), "typ": p[4], "dir": p[5],
                     "entry": float(p[6]), "r": float(p[8])})
    except ValueError:
        continue
assert len(rows) == 27, len(rows)
mm = sum(1 for s, r in zip(sigs, rows)
         if s.bar == r["bar_sig"] and s.typ == r["dir"]
         and abs(s.einstieg_preis - r["entry"]) < 1e-9
         and abs(float(s.trade.r_mult) - r["r"]) < 5e-3)
out("=" * 118)
out("AUG-INITIALISIERUNGSAUDIT | exec-Import (Cut nach Baseline-Signal-Loop)")
out("=" * 118)
out(f"df {len(df)} Bars | Phasen {len(phases)} | Signale {len(sigs)} | "
    f"Mapping bitgenau {mm}/27 | Pivots gesamt {len(piv_rows)} "
    f"(H {int((piv_typs == 'H').sum())}/L {int((piv_typs == 'L').sum())})")
out("")

# ---------------------------------------------------------------- Analyse je Trade
recs = []
for s, r in zip(sigs, rows):
    k = s.bar
    p = phases[s.phase - 1]
    i0 = p.i_start
    nr, typ, R = r["nr"], s.typ, float(s.trade.r_mult)
    alter1 = k - i0 + 1            # 1-basiert (konsistent §8.9.3)
    alter0 = k - i0                # 0-basiert
    ph_anteil = alter1 / p.n_candles
    up = typ == "SHORT"            # SHORT faded steigenden Markt
    # laufende Extrema seit Phasenstart
    M = np.maximum.accumulate(hi[i0:k + 1])
    m = np.minimum.accumulate(lo[i0:k + 1])
    if up:
        retr_cl = M - cl[i0:k + 1]
        retr_xtr = M - lo[i0:k + 1]
        ext_now = M[-1]
        ext_start = cl[i0]
    else:
        retr_cl = cl[i0:k + 1] - m
        retr_xtr = hi[i0:k + 1] - m
        ext_now = m[-1]
        ext_start = cl[i0]
    max_rc = float(retr_cl.max())
    max_rx = float(retr_xtr.max())
    # erste Pullback-Bar (close-basiert), strikt vor Signal (< k)
    def first_pb(thr: float) -> int | None:
        hit = np.where(retr_cl[:k - i0] >= thr)[0]  # nur j < k
        return int(hit[0] + i0) if len(hit) else None
    pb15 = first_pb(0.15)
    pb30 = first_pb(0.30)
    n_pb15 = int((retr_cl[:k - i0] >= 0.15).sum())
    n_pb30 = int((retr_cl[:k - i0] >= 0.30).sum())
    # bestaetigte Pivots im Fenster i0..k-LOOKBACK (kein Lookahead)
    sel = (piv_bars >= i0) & (piv_bars <= k - LOOKBACK)
    pbars, ptyps, pprs = piv_bars[sel], piv_typs[sel], piv_prs[sel]
    n_h = int((ptyps == "H").sum())
    n_l = int((ptyps == "L").sum())
    # Gegenseiten-Pivot (Pullback-Bestaetigung der fade-Richtung)
    geg = "L" if up else "H"
    n_geg = int((ptyps == geg).sum())
    # letzter bestaetigter Pivot vor Signal
    if len(pbars):
        lb, lt, lp = int(pbars[-1]), str(ptyps[-1]), float(pprs[-1])
        ldist = k - lb
    else:
        lb, lt, lp, ldist = None, "", float("nan"), k - i0
    # Klassifikation (close-basiert, Pullback strikt vor Signal)
    if pb15 is None:
        cls = "INIT"          # nie >= 0.15 USD Gegenzug vor Signal
    elif pb30 is None:
        cls = "PB15"          # Gegenzug 0.15..0.30 USD
    else:
        cls = "PB30"          # etablierter Gegenzug >= 0.30 USD
    recs.append({
        "nr": nr, "phase": s.phase, "bar": k, "ts": s.ts, "dir": typ, "R": R,
        "alter1": alter1, "alter0": alter0, "anteil": ph_anteil,
        "cl0": float(cl[i0]), "clk": float(cl[k]), "ext": ext_now,
        "netto_pct": (float(cl[k]) - float(cl[i0])) / float(cl[i0]) * 100.0,
        "edge": s.U_laufend if up else s.L_laufend,
        "max_rc": max_rc, "max_rx": max_rx, "pb15": pb15, "pb30": pb30,
        "n_pb15": n_pb15, "n_pb30": n_pb30, "n_h": n_h, "n_l": n_l,
        "n_geg": n_geg, "last_piv_bar": lb, "last_piv_typ": lt,
        "last_piv_pr": lp, "last_dist": ldist, "cls": cls,
    })

# ---------------------------------------------------------------- Report
HDR = (f"{'#':>2} {'Ph':>2} {'Zeit':<12} {'Dir':<5} {'R':>6} {'Rc':>4} "
       f"{'Alter':>3} {'Ant%':>5} | {'cl0':>7} {'clk':>7} {'Net%':>6} "
       f"{'Kante':>7} {'Ext':>7} | {'mRetrC':>6} {'mRetrX':>6} "
       f"{'PB15@':>5} {'PB30@':>5} {'#15':>3} | {'hP':>2} {'lP':>2} "
       f"{'letzterPiv':>16} {'Kls':>4}")
out(HDR)
out("-" * len(HDR))
for x in recs:
    lp = (f"B{x['last_piv_bar']}{x['last_piv_typ']}{x['last_piv_pr']:.3f}"
          if x["last_piv_bar"] is not None else "-")
    out(f"{x['nr']:>2} {x['phase']:>2} {x['ts']:%d.%m %H:%M} {x['dir']:<5} "
        f"{x['R']:>+6.2f} {x['alter1']:>3} {x['anteil']*100:>5.1f} | "
        f"{x['cl0']:>7.3f} {x['clk']:>7.3f} {x['netto_pct']:>+6.2f} "
        f"{x['edge']:>7.3f} {x['ext']:>7.3f} | {x['max_rc']:>6.3f} "
        f"{x['max_rx']:>6.3f} "
        f"{str(x['pb15']):>5} {str(x['pb30']):>5} {x['n_pb15']:>3} | "
        f"{x['n_h']:>2} {x['n_l']:>2} {lp:>16} {x['cls']:>4}")
out("")

# ---------------------------------------------------------------- Aggregat
los = [x for x in recs if x["R"] < 0]
win = [x for x in recs if x["R"] > 0]
voll = [x for x in los if x["R"] <= -0.99]   # R ~ -1.00 = Voll-SL
teil = [x for x in los if x["R"] > -0.99]     # Teilverlust (T3/T22)
out(f"AGGREGAT | Winner {len(win)} | Loser {len(los)} (davon Voll-SL {len(voll)}, "
    f"Teilverlust {len(teil)}: " + ", ".join(f"T{x['nr']} {x['R']:+.2f}R" for x in teil) + ")")
for label, grp in (("WINNER", win), ("LOSER", los), ("VOLL-SL", voll)):
    if not grp:
        continue
    a = sorted(x["alter1"] for x in grp)
    an = sorted(x["alter0"] for x in grp)
    pb = [x["cls"] for x in grp]
    out(f"  {label}: n={len(grp)} | Alter(1b) min/med/max "
        f"{a[0]}/{a[len(a)//2]}/{a[-1]} | Anteil<40: "
        f"{sum(1 for v in a if v < 40)} | INIT {pb.count('INIT')} | "
        f"PB15 {pb.count('PB15')} | PB30 {pb.count('PB30')}")
    out(f"      Einzel-Kls: " + ", ".join(f"T{x['nr']}:{x['cls']}" for x in grp))

# Kontrastfrage: INIT-Loser vs INIT-Winner R-Summen
for label, grp in (("WINNER", win), ("LOSER", los)):
    init = [x for x in grp if x["cls"] == "INIT"]
    out(f"  {label} INIT: {len(init)} Trades "
        f"(R {sum(x['R'] for x in init):+.2f}R) -> "
        + ", ".join(f"T{x['nr']} {x['R']:+.2f}R A{x['alter1']}" for x in init))
out("")

# ---------------------------------------------------------------- Fokus-Zeitlinien
out("-" * 118)
out("FOKUS-ZEITLINIEN (P5-Geister T9-T11, T26 P12, Kontrast-Winner T14/T15, T25/T27 P12)")
out("-" * 118)


def ts_str(b: int) -> str:
    return f"{pd.Timestamp(tsa[b]):%d.%m %H:%M}"


for x in recs:
    if x["nr"] not in (9, 10, 11, 26, 14, 15, 25, 27):
        continue
    s = next(z for z in sigs if z.bar == x["bar"])
    p = phases[s.phase - 1]
    i0, k = p.i_start, s.bar
    up = s.typ == "SHORT"
    sel = (piv_bars >= i0) & (piv_bars <= k - LOOKBACK)
    pbs, pts, pps = piv_bars[sel], piv_typs[sel], piv_prs[sel]
    out("")
    out(f"T{x['nr']} P{x['phase']} {s.typ} E{s.einstieg_preis:.3f} "
        f"R{x['R']:+.2f} | Signal {ts_str(k)} (B{k}), Phasenstart {ts_str(i0)} "
        f"(B{i0}) cl0 {x['cl0']:.3f} | Kante {x['edge']:.3f} "
        f"| Alter {x['alter1']} (0b {x['alter0']}) | mRetrC {x['max_rc']:.3f} "
        f"PB15@{x['pb15']} PB30@{x['pb30']} | Kls {x['cls']}")
    if len(pbs) == 0:
        out(f"   Pivots bis Signal: KEINE bestaetigten (i0..k-{LOOKBACK}) -> "
            f"Preis lief seit Phasenstart ohne 2-Bar-Bestaetigung eines Extrems")
    for j, (b, t, pr) in enumerate(zip(pbs, pts, pps)):
        mark = " <== Signal hier" if False else ""
        out(f"   Piv {j + 1}: B{b} {ts_str(b)} {t} {pr:.3f} "
            f"(Abstand zu Signal {k - b}){mark}")

OUT.write_text("\n".join(_buf) + "\n", encoding="utf-8")
print(f"OK -> {OUT} ({len(_buf)} Zeilen)")
