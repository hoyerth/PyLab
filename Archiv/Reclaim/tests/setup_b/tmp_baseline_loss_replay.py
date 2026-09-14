"""AUG Baseline-Loss-Obduktion Phase 1+2 (kausaler Replay, bitgenau).

exec-Import von scripts/phasen_volumen_profil.py mit Cut NACH dem
Baseline-Signal-Loop (reclaim_signals.sort im else-Zweig, Z. ~1389) ->
alle 27 original erzeugten ReclaimSignal-Objekte (mit .phase, .trade,
.U_laufend/.L_laufend/.POC/.crv/.bounce_nr) stehen im Namespace.

Dann: Abgleich gegen test/stats_trades_AUG.txt (Baseline-Block) und
Anreicherung jedes Signals mit kausalen Audit-Feldern (Profilalter,
Penetrationstiefe, Reclaim-Tiefe, Cooldown-Gap, POC-Distanz, Aufloesung).
Kein Schreiben von Produktivcode, DuckDB read_only.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path("test/tmp_baseline_loss_replay.txt")
_buf: list[str] = []


def out(*a: object) -> None:
    s = " ".join(str(x) for x in a)
    _buf.append(s)


# ---------------------------------------------------------------- exec-Import
src = io.open("scripts/phasen_volumen_profil.py", encoding="utf-8").read()
_marker = "reclaim_signals.sort(key=lambda s: s.ts)"
_cut = src.rindex(_marker) + len(_marker)
ns: dict = {"__file__": str(Path("scripts/phasen_volumen_profil.py").resolve())}
exec(compile(src[:_cut], "phasen_volumen_profil.py", "exec"), ns)  # noqa: S102

df = ns["df"]
phases = ns["phases"]
sigs: list = ns["reclaim_signals"]
hi = df["high"].values
lo = df["low"].values
cl = df["close"].values
op = df["open"].values

out("=" * 120)
out("BASELINE-REPLAY AUG | exec-Import Produktion (Cut nach Baseline-Signal-Loop)")
out("=" * 120)
out(f"df-Zeilen: {len(df)} | Phasen: {len(phases)} | reclaim_signals: {len(sigs)}")
out("Phasen (i_start/ts, i_ende/ts, n_candles):")
for pi, p in enumerate(phases, 1):
    out(f"  P{pi:2d} i_start {p.i_start:5d} ({df['ts'].iloc[p.i_start]}) -> "
        f"i_ende {p.i_ende:5d} ({df['ts'].iloc[p.i_ende]}) | n_candles {p.n_candles}")
out("")

# ---------------------------------------------------------------- Log-Parsing
log_txt = io.open("test/stats_trades_AUG.txt", encoding="utf-8").read()
log_txt = log_txt.split("Modus: --macro-live")[0]  # nur Baseline-Block
rows: list[dict] = []
_in_trade = False
for l in log_txt.splitlines():
    if l.startswith("TRADE-LOG"):
        _in_trade = True
        continue
    if not _in_trade:
        continue
    if "|" not in l:
        continue
    p = [x.strip() for x in l.split("|")]
    if len(p) < 9:
        continue
    try:
        rows.append({
            "nr": int(p[0]), "phase": int(p[1]), "bar_sig": int(p[2]),
            "bar_entry": int(p[3]), "typ": p[4], "dir": p[5],
            "entry": float(p[6]), "r": float(p[8]),
        })
    except ValueError:
        continue
out(f"Log-Trades (Baseline-Block): {len(rows)}")

# ---------------------------------------------------------------- Mapping
assert len(sigs) == len(rows) == 27, (len(sigs), len(rows))
mismatch = 0
for i, (s, r) in enumerate(zip(sigs, rows), 1):
    ok = (s.bar == r["bar_sig"] and s.einstieg_bar == r["bar_entry"]
          and s.typ == r["dir"] and abs(s.einstieg_preis - r["entry"]) < 1e-9
          and abs(float(s.trade.r_mult) - r["r"]) < 5e-3)
    if not ok:
        mismatch += 1
        out(f"  MISMATCH {i}: sig bar {s.bar}/{r['bar_sig']} entry "
            f"{s.einstieg_bar}/{r['bar_entry']} {s.typ}/{r['dir']} "
            f"{s.einstieg_preis:.3f}/{r['entry']:.3f} "
            f"{s.trade.r_mult:+.2f}/{r['r']:+.2f}")
out(f"Mapping bitgenau: {27 - mismatch}/27 | Phase-Zuordnung Log==Replay: "
    f"{sum(1 for s, r in zip(sigs, rows) if s.phase == r['phase'])}/27")
out("")

# ---------------------------------------------------------------- Audit-Anreicherung
last_bar: dict[tuple[int, str], int] = {}  # (phase, dir) -> letzte Signal-Bar


def cooldown_gap(s: object) -> int | None:
    key = (s.phase, s.typ)
    prev = last_bar.get(key)
    gap = None if prev is None else s.bar - prev
    last_bar[key] = s.bar
    return gap


recs = []
for s, r in zip(sigs, rows):
    k = s.bar
    p = phases[s.phase - 1]
    age = k - p.i_start + 1
    if s.typ == "SHORT":
        edge = s.U_laufend
        pen = hi[k] - edge
        rd = (edge - cl[k]) if s.reclaim == "in_bar" else (edge - cl[k + 1])
        zone_other = s.L_laufend
    else:
        edge = s.L_laufend
        pen = edge - lo[k]
        rd = (cl[k] - edge) if s.reclaim == "in_bar" else (cl[k + 1] - edge)
        zone_other = s.U_laufend
    risk = abs(s.sl - s.einstieg_preis)
    poc_dist_r = abs(s.einstieg_preis - s.POC) / risk if risk > 0 else float("nan")
    tr = s.trade
    recs.append({
        "nr": r["nr"], "phase": s.phase, "ts": s.ts, "dir": s.typ,
        "reclaim": s.reclaim, "entry": s.einstieg_preis, "sl": s.sl,
        "tp1": s.tp1, "tp2": s.tp2, "r": tr.r_mult,
        "age": age, "edge": edge, "poc": s.POC, "poc_dist_r": poc_dist_r,
        "crv": s.crv, "crv2": s.crv2, "pen": pen, "rd": rd,
        "bounce": s.bounce_nr, "cd_gap": cooldown_gap(s),
        "g1": tr.grund1, "g2": tr.grund2, "r1": tr.r1, "r2": tr.r2,
        "exit1": tr.exit1, "exit2": tr.exit2,
        "tp1_hit": tr.tp1_hit, "sl_hit1": tr.sl_hit1, "sl_hit2": tr.sl_hit2,
    })

# ---------------------------------------------------------------- Report
HDR = (f"{'#':>2} {'Ph':>2} {'Zeit (Signal)':<17} {'Dir':<5} {'Rc':<8} "
       f"{'Entry':>8} {'R':>6} | {'Alter':>4} {'Kante':>7} {'POC':>7} "
       f"{'POCdist':>7} {'Pen':>6} {'RcDepth':>7} {'Bo':>2} {'CD':>4} | "
       f"{'G1':<4} {'r1':>6} {'G2':<4} {'r2':>6}")
out(HDR)
out("-" * len(HDR))
for x in recs:
    out(f"{x['nr']:>2} {x['phase']:>2} {x['ts']:%d.%m %H:%M} {x['dir']:<5} "
        f"{x['reclaim']:<8} {x['entry']:>8.3f} {x['r']:>+6.2f} | "
        f"{x['age']:>4} {x['edge']:>7.3f} {x['poc']:>7.3f} {x['poc_dist_r']:>7.2f} "
        f"{x['pen']:>6.3f} {x['rd']:>7.3f} {x['bounce']:>2} "
        f"{str(x['cd_gap']):>4} | {x['g1']:<4} {x['r1']:>+6.2f} "
        f"{x['g2']:<4} {x['r2']:>+6.2f}")
out("")

# ---------------------------------------------------------------- Fokus 15 Loser
losers = [x for x in recs if x["r"] < 0]
winners = [x for x in recs if x["r"] > 0]
out(f"LOSER {len(losers)} | WINNER {len(winners)}")
out("")
out("--- 15 LOSER: Cluster-Merkmale ---")
for x in losers:
    flags = []
    if x["g1"] == "TP1":
        flags.append("TEILVERLUST(TP1-erreicht)")
    else:
        flags.append("VOLL-SL")
    if x["age"] < 40:
        flags.append(f"FRUEH-ALTER-{x['age']}")
    if x["cd_gap"] == 12:
        flags.append("CD-EXAKT-MIN")
    if x["pen"] < 0.05:
        flags.append("PEN-MIKRO")
    if x["rd"] is not None and x["rd"] < 0.02:
        flags.append("RD-MIKRO")
    out(f"  T{x['nr']:>2} P{x['phase']:>2} {x['ts']:%d.%m %H:%M} {x['dir']:<5} "
        f"{x['reclaim']:<8} E{x['entry']:.3f} R{x['r']:+.2f} "
        f"Alter {x['age']:>3} CD {str(x['cd_gap']):>4} "
        f"{' | '.join(flags)}")
out("")
out("--- 15 LOSER: Detail (r1/r2-Komponenten & Exit) ---")
for x in losers:
    out(f"  T{x['nr']:>2} P{x['phase']:>2} {x['ts']:%d.%m %H:%M} {x['dir']:<5} "
        f"{x['reclaim']:<8} E{x['entry']:.3f} SL{x['sl']:.3f} "
        f"TP1(POC){x['tp1']:.3f} TP2{x['tp2']:.3f} R{x['r']:+.2f} | "
        f"H1 {x['g1']} {x['exit1']:.3f} {x['r1']:+.2f}R | "
        f"H2 {x['g2']} {x['exit2']:.3f} {x['r2']:+.2f}R")
out("")

# ---------------------------------------------------------------- Winner-Kontrast
out("--- 12 WINNER (Kontrollgruppe) ---")
for x in winners:
    flags = []
    if x["age"] < 40:
        flags.append(f"FRUEH-ALTER-{x['age']}")
    if x["cd_gap"] == 12:
        flags.append("CD-EXAKT-MIN")
    out(f"  T{x['nr']:>2} P{x['phase']:>2} {x['ts']:%d.%m %H:%M} {x['dir']:<5} "
        f"{x['reclaim']:<8} E{x['entry']:.3f} R{x['r']:+.2f} "
        f"Alter {x['age']:>3} CD {str(x['cd_gap']):>4} Bo {x['bounce']} "
        f"Kante {x['edge']:.3f} POC {x['poc']:.3f} "
        f"{' | '.join(flags) if flags else ''}")
out("")
out("--- Aggregat: Alter-Verteilung ---")
for label, grp in (("LOSER", losers), ("WINNER", winners)):
    ages = sorted(x["age"] for x in grp)
    out(f"  {label}: n={len(grp)} Alter min/med/max = {ages[0]}/{ages[len(ages)//2]}/{ages[-1]} "
        f"| <40: {sum(1 for a in ages if a < 40)} | >=40: {sum(1 for a in ages if a >= 40)}")

OUT.write_text("\n".join(_buf) + "\n", encoding="utf-8")
print(f"OK -> {OUT} ({len(_buf)} Zeilen)")
