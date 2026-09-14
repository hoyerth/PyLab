"""READ-ONLY Schritt 0: Folgephasen-Ausbeute der 5 TRUE-Phasen (S2 Ph3/4/13/19, S1 Ph102).
Fenster: 72h und 168h ab exaktem Phasenende. Erfasst ALLE Trades in Streak-Richtung
(LONG) in den Folgephasen innerhalb des Fensters -> realisierte R, Wins/Losses.
Report: test/tmp_post_phase_verification.txt
"""
import sys, re, glob
sys.stdout.reconfigure(encoding="utf-8")
import pandas as pd

# ---------- Phasen-Tableaus (Endzeitpunkte) ----------
def parse_phase_log(path, jahr):
    t = open(path, encoding="utf-16").read()
    pat = re.compile(r"^Phase (\d+): \w+ (\d{2})\.(\d{2}) (\d{2}):(\d{2}) -> \w+ (\d{2})\.(\d{2}) (\d{2}):(\d{2}) "
                     r"\(([\d.]+)h, (\d+)C\)(.*)$")
    out = {}
    for l in t.splitlines():
        m = pat.match(l.strip())
        if not m:
            continue
        pid = int(m.group(1))
        start = pd.Timestamp(datetime := __import__("datetime").datetime(
            jahr, int(m.group(3)), int(m.group(2)), int(m.group(4)), int(m.group(5))), tz="UTC")
        ende = pd.Timestamp(datetime := __import__("datetime").datetime(
            jahr, int(m.group(7)), int(m.group(6)), int(m.group(8)), int(m.group(9))), tz="UTC")
        out[pid] = dict(start=start, ende=ende)
    return out

phS1 = parse_phase_log("test/tmp_S1_monatslauf.log", 2026)
phS2 = parse_phase_log("test/tmp_S2_monatslauf.log", 2025)

# ---------- Trades aus Monatsberichten (Zeit, Phase, Richtung, R) ----------
def parse_monatsdatei(path):
    out = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})\s+(LONG|SHORT)\s+([\d.]+)\s+([+-][\d.]+)", line)
        if m:
            out.append(dict(nr=int(m.group(1)), ph=int(m.group(2)),
                            dt=pd.Timestamp(datetime := __import__("datetime").datetime(
                                int(m.group(5)), int(m.group(4)), int(m.group(3)),
                                int(m.group(6)), int(m.group(7))), tz="UTC"),
                            direction=m.group(8), entry=float(m.group(9)), r=float(m.group(10))))
    return out

trades = []
for fenster, jahr in [("S1", 2026), ("S2", 2025)]:
    for f in sorted(glob.glob(f"test/tmp_{fenster}_monatslauf_{jahr}-*.txt")):
        for t in parse_monatsdatei(f):
            t["fenster"] = fenster
            trades.append(t)

# ---------- Streak je Phase finden (Richtung) ----------
from collections import Counter
def finde_streak(fenster, phid):
    tr = sorted([t for t in trades if t["fenster"] == fenster and t["ph"] == phid],
                key=lambda t: t["dt"])
    i = 0
    while i < len(tr):
        if tr[i]["r"] < 0:
            j = i
            while j + 1 < len(tr) and tr[j + 1]["r"] < 0:
                j += 1
            if j - i + 1 >= 4:
                seg = tr[i:j + 1]
                dirs = Counter(t["direction"] for t in seg)
                return seg, dirs.most_common(1)[0][0]
            i = j + 1
        else:
            i += 1
    return None, None

# ---------- Fokus ----------
fokus = [("S2", 3, 72), ("S2", 3, 168), ("S2", 4, 72), ("S2", 4, 168),
         ("S2", 13, 72), ("S2", 13, 168), ("S2", 19, 72), ("S2", 19, 168),
         ("S1", 102, 72), ("S1", 102, 168)]

lines = []
def emit(s=""):
    lines.append(s)

emit("=" * 110)
emit("SCHRITT 0: FOLGEPHASEN-AUSBEUTE der 5 TRUE-Phasen (S2 Ph3/4/13/19, S1 Ph102)")
emit("Fenster: 72h / 168h ab Phasenende | Richtung = Streak-Richtung (LONG)")
emit("=" * 110)

# Erst Tabelle je Phase & Fenster
emit("\n")
emit(f"{'Fen':<3}{'Ph':>3} {'Ende (UTC)':<16}{'Strk-Dir':<7}{'Streak-R':>8} | {'Fenster':<8}"
     f"{'Tr':>3}{'W':>3}{'L':>3} | {'real. R':>8} | {'Netto(Strk+real)':>17}")
emit("-" * 110)

results = {}
for fenster, phid, h in fokus:
    phasen = phS1 if fenster == "S1" else phS2
    seg, richtung = finde_streak(fenster, phid)
    p = phasen.get(phid)
    if seg is None or p is None:
        continue
    streak_r = sum(t["r"] for t in seg)
    ende = p["ende"]
    fenster_end = ende + pd.Timedelta(hours=h)
    # Folge-Trades: gleiches Fenster, spaeter als Phasenende, in Streak-Richtung
    folge = [t for t in trades
             if t["fenster"] == fenster and t["dt"] > ende and t["dt"] <= fenster_end
             and t["direction"] == richtung]
    folge.sort(key=lambda t: t["dt"])
    n_tr = len(folge)
    n_w = sum(1 for t in folge if t["r"] > 0)
    n_l = sum(1 for t in folge if t["r"] < 0)
    real_r = sum(t["r"] for t in folge)
    netto = streak_r + real_r
    emit(f"{fenster:<3}{phid:>3} {ende:%d.%m.%Y %H:%M}  {richtung:<7}{streak_r:>+8.2f} | "
         f"{h:>3}h   {n_tr:>3}{n_w:>3}{n_l:>3} | {real_r:>+8.2f} | {netto:>+17.2f}")

# Detail-Liste der Folge-Trades (fuer die 5 Phasen, 168h)
emit("\n" + "=" * 110)
emit("DETAIL: Folge-Trades in Streak-Richtung (168h-Fenster)")
emit("=" * 110)
for fenster, phid in [("S2", 3), ("S2", 4), ("S2", 13), ("S2", 19), ("S1", 102)]:
    phasen = phS1 if fenster == "S1" else phS2
    seg, richtung = finde_streak(fenster, phid)
    p = phasen.get(phid)
    if seg is None or p is None:
        continue
    streak_r = sum(t["r"] for t in seg)
    ende = p["ende"]
    fenster_end = ende + pd.Timedelta(hours=168)
    folge = [t for t in trades
             if t["fenster"] == fenster and t["dt"] > ende and t["dt"] <= fenster_end
             and t["direction"] == richtung]
    folge.sort(key=lambda t: t["dt"])
    emit(f"\n  {fenster} Ph{phid} ({richtung}, Streak {streak_r:+.2f}R, Ende {ende:%d.%m %H:%M}):")
    if not folge:
        emit("    (keine Folge-Trades in Streak-Richtung im 168h-Fenster)")
    for t in folge:
        emit(f"    T{t['nr']:>3} Ph{t['ph']:>3} {t['dt']:%d.%m %H:%M} {t['direction']:<5} "
             f"Entry {t['entry']:>8.3f} {t['r']:>+7.2f}R")

# Aggregat uber die 5 TRUE-Phasen (168h)
emit("\n" + "=" * 110)
emit("AGGREGAT (5 TRUE-Phasen, 168h-Fenster in Streak-Richtung)")
emit("=" * 110)
sum_streak = 0
sum_real = 0
n_ges = n_w_ges = n_l_ges = 0
for fenster, phid in [("S2", 3), ("S2", 4), ("S2", 13), ("S2", 19), ("S1", 102)]:
    phasen = phS1 if fenster == "S1" else phS2
    seg, richtung = finde_streak(fenster, phid)
    p = phasen.get(phid)
    if seg is None or p is None:
        continue
    streak_r = sum(t["r"] for t in seg)
    ende = p["ende"]
    fenster_end = ende + pd.Timedelta(hours=168)
    folge = [t for t in trades
             if t["fenster"] == fenster and t["dt"] > ende and t["dt"] <= fenster_end
             and t["direction"] == richtung]
    sum_streak += streak_r
    sum_real += sum(t["r"] for t in folge)
    n_ges += len(folge)
    n_w_ges += sum(1 for t in folge if t["r"] > 0)
    n_l_ges += sum(1 for t in folge if t["r"] < 0)
emit(f"  Streak-Verlust der 5 TRUE-Phasen gesamt: {sum_streak:+.2f}R")
emit(f"  Realisierte R der Folgephasen (168h, Streak-Richtung): {sum_real:+.2f}R "
     f"({n_ges} Trades: {n_w_ges}W/{n_l_ges}L)")
emit(f"  Netto-Zyklus (Streak + 168h-Folge): {sum_streak + sum_real:+.2f}R")
emit(f"  WR der Folge-Trades: {100*n_w_ges/max(n_ges,1):.1f}%")
emit("\n  Interpretation:")
emit("  - Ist realisierte R deutlich positiv und deckt den Streak-Verlust -> KEIN")
emit("    Ausfuehrungs-Vakuum, sondern Fehlversuch-Kaskade vor dem Turn (der Turn")
emit("    wurde in den Folgephasen gehandelt).")
emit("  - Ist realisierte R klein/negativ -> tatsaechliche Sequenzer-Luecke.")

with open("test/tmp_post_phase_verification.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("\n".join(lines))
print(f"\n-> test/tmp_post_phase_verification.txt ({len(lines)} Zeilen)")
