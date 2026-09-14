"""READ-ONLY Mentor-Schritt 1: Phasen-Alter der Serien-Verluste vs. Top-Winner (S1+S2).
Quellen: tmp_S{1,2}_monatslauf.log (Phasen-Tableau UTF-16) + Monatsberichte (Trade-Zeiten UTC).
Berechnet je Trade: Alter = Signal-Zeit - Phasenstart (h/Tage/Bars über M15-Position).
Report: test/tmp_phasen_alter_schritt1.txt
"""
import sys, re, glob
from datetime import datetime
sys.stdout.reconfigure(encoding="utf-8")
import duckdb
import pandas as pd
import numpy as np

# ---------- Phasen-Tableau aus Log ----------
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
        start = datetime(jahr, int(m.group(3)), int(m.group(2)), int(m.group(4)), int(m.group(5)))
        ende = datetime(jahr, int(m.group(7)), int(m.group(6)), int(m.group(8)), int(m.group(9)))
        out[pid] = dict(start=start, ende=ende, dauer_h=float(m.group(10)),
                        bars=int(m.group(11)), marker=m.group(12).strip())
    return out

# ---------- Trades aus Monatsberichten ----------
def parse_monatsdatei(path):
    out = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})\s+(LONG|SHORT)\s+([\d.]+)\s+([+-][\d.]+)", line)
        if m:
            out.append(dict(nr=int(m.group(1)), ph=int(m.group(2)),
                            dt=datetime(int(m.group(5)), int(m.group(4)), int(m.group(3)),
                                        int(m.group(6)), int(m.group(7))),
                            direction=m.group(8), entry=float(m.group(9)), r=float(m.group(10))))
    return out

def lade(fenster, jahr, logpfad):
    phasen = parse_phase_log(logpfad, jahr)
    tr = []
    for f in sorted(glob.glob(f"test/tmp_{fenster}_monatslauf_{jahr}-*.txt")):
        tr += parse_monatsdatei(f)
    tr.sort(key=lambda t: t["dt"])
    # Alter je Trade
    for t in tr:
        p = phasen.get(t["ph"])
        if p and p["start"] <= t["dt"] <= p["ende"] + __import__("datetime").timedelta(hours=2):
            t["ph_start"] = p["start"]
            t["ph_ende"] = p["ende"]
            t["age_h"] = (t["dt"] - p["start"]).total_seconds() / 3600
            t["ph_dauer_h"] = p["dauer_h"]
            t["ph_bars"] = p["bars"]
            t["ph_marker"] = p["marker"]
        else:
            t["ph_start"] = t["ph_ende"] = None
            t["age_h"] = t["ph_dauer_h"] = t["ph_bars"] = None
            t["ph_marker"] = f"?? Phase {t['ph']} nicht im Tableau"
    return phasen, tr

S1_LOG = "test/tmp_S1_monatslauf.log"
S2_LOG = "test/tmp_S2_monatslauf.log"
ph1, tr1 = lade("S1", 2026, S1_LOG)
ph2, tr2 = lade("S2", 2025, S2_LOG)

lines = []
def emit(s=""):
    lines.append(s)

def serie_tabelle(tr, lo, hi, title):
    emit(f"\n{'=' * 100}")
    emit(f"{title}")
    emit(f"{'=' * 100}")
    emit(f"{'Nr':>4} {'Ph':>4} {'Signal UTC':<16} {'Phasenstart':<16} {'Alter h':>8} "
         f"{'Alter d':>7} {'Dir':<5} {'Entry':>8} {'R':>7} | Phasen-Marker")
    seg = [t for t in tr if lo <= t["nr"] <= hi]
    for t in seg:
        alter_d = t["age_h"] / 24 if t["age_h"] is not None else float("nan")
        emit(f"{t['nr']:>4} {t['ph']:>4} {t['dt']:%d.%m.%Y %H:%M} "
             f"{(t['ph_start'].strftime('%d.%m %H:%M') if t['ph_start'] else '??'):<16} "
             f"{t['age_h']:>8.1f} {alter_d:>7.2f} {t['direction']:<5} {t['entry']:>8.3f} "
             f"{t['r']:>+7.2f} | {t['ph_marker']}")
    n = len(seg)
    sumr = sum(t["r"] for t in seg)
    emit(f"  -> {n} Trades | SumR {sumr:+.2f}R | Phasen: {sorted(set(t['ph'] for t in seg))}")
    # Phasenwechsel-Annotation
    prev = None
    for t in seg:
        if t["ph"] != prev:
            emit(f"     *** Wechsel zu Phase {t['ph']} (start {t['ph_start']:%d.%m %H:%M}, "
                 f"Alter zurueck auf 0)")
            prev = t["ph"]

emit("=" * 100)
emit("MENTOR-SCHRITT 1: PHASEN-ALTER (Trade-Alter = Signal-Zeit minus Phasenstart)")
emit("=" * 100)

# --- 1) Monsterserien im Detail ---
serien = [("S2", "17er-Serie Feb 2025 (T37-T53)", tr2, 37, 53),
          ("S2", "13er-Serie Jul 2025 (T99-T111)", tr2, 99, 111),
          ("S2", "10er-Serie Apr 2025 (T75-T84)", tr2, 75, 84),
          ("S2", "10er-Serie Okt/Nov 2025 (T187-T196)", tr2, 187, 196),
          ("S1", "S1-Jun Kaskade 1 (T120-T126)", tr1, 120, 126),
          ("S1", "S1-Jun Kaskade 2 / Ph102 (T137-T143)", tr1, 137, 143),
          ("S1", "S1-Aug 5er (T183-T187)", tr1, 183, 187)]
for fen, titel, tr, lo, hi in serien:
    serie_tabelle(tr, lo, hi, f"{titel}")

# --- 2) Top-Winner ---
def winner_tabelle(tr, k, title):
    emit(f"\n{'=' * 100}")
    emit(f"{title} (Top {k} nach R)")
    emit(f"{'=' * 100}")
    emit(f"{'Nr':>4} {'Ph':>4} {'Signal UTC':<16} {'Phasenstart':<16} {'Alter h':>8} "
         f"{'Alter d':>7} {'Dir':<5} {'Entry':>8} {'R':>7} | Phasen-Marker / Phasendauer")
    for t in sorted([t for t in tr if t["r"] > 0], key=lambda t: -t["r"])[:k]:
        alter_d = t["age_h"] / 24 if t["age_h"] is not None else float("nan")
        emit(f"{t['nr']:>4} {t['ph']:>4} {t['dt']:%d.%m.%Y %H:%M} "
             f"{(t['ph_start'].strftime('%d.%m %H:%M') if t['ph_start'] else '??'):<16} "
             f"{t['age_h']:>8.1f} {alter_d:>7.2f} {t['direction']:<5} {t['entry']:>8.3f} "
             f"{t['r']:>+7.2f} | {t['ph_marker']}")

winner_tabelle(tr1, 10, "S1 TOP-10-WINNER (Referenz T59/T154/T188/T35/T27)")
winner_tabelle(tr2, 10, "S2 TOP-10-WINNER")

# --- 3) Verteilungs-Kontrast (Alter) ---
emit("\n" + "=" * 100)
emit("VERTEILUNGS-KONTRAST: Phasen-Alter in Tagen (Serien-Verluste vs. Winner vs. Einzel-Verluste)")
emit("=" * 100)
for fen, tr, phasen in [("S1", tr1, ph1), ("S2", tr2, ph2)]:
    # Serien-ID-Menge (>=4er)
    serien_ids = set()
    i = 0
    while i < len(tr):
        if tr[i]["r"] < 0:
            j = i
            while j + 1 < len(tr) and tr[j + 1]["r"] < 0:
                j += 1
            if j - i + 1 >= 4:
                for t in tr[i:j + 1]:
                    serien_ids.add(t["nr"])
            i = j + 1
        else:
            i += 1
    g_w = [t for t in tr if t["r"] > 0 and t["age_h"] is not None]
    g_l_ser = [t for t in tr if t["r"] < 0 and t["nr"] in serien_ids and t["age_h"] is not None]
    g_l_ein = [t for t in tr if t["r"] < 0 and t["nr"] not in serien_ids and t["age_h"] is not None]
    emit(f"\n{fen}: Winner n={len(g_w)} | Serien-L n={len(g_l_ser)} | Einzel-L n={len(g_l_ein)}")
    def stats(g):
        a = np.array([t["age_h"] / 24 for t in g])
        a = a[~np.isnan(a)]
        if len(a) == 0:
            return "n/a"
        return (f"Median {np.median(a):5.2f}d | Q25 {np.percentile(a, 25):5.2f} "
                f"Q75 {np.percentile(a, 75):5.2f} | >2d: {100 * np.mean(a > 2):4.0f}% "
                f"| >5d: {100 * np.mean(a > 5):4.0f}% | >10d: {100 * np.mean(a > 10):4.0f}%")
    emit(f"  Winner     : {stats(g_w)}")
    emit(f"  Serien-L   : {stats(g_l_ser)}")
    emit(f"  Einzel-L   : {stats(g_l_ein)}")
    # Top-Winner Alter einzeln
    tw = sorted([t for t in g_w], key=lambda t: -t["r"])[:5]
    emit("  Top-Winner Alter: " + ", ".join(f"T{t['nr']} {t['age_h']/24:.2f}d" for t in tw))

# --- 4) Stale-Vorgriff: Phasendauer der Serien-Phasen ---
emit("\n" + "=" * 100)
emit("STALE-VORGRIFF: Phasendauer & Phasenalter der Monsterserien-Phasen (aus Log-Tableau)")
emit("=" * 100)
for fen, tr, phasen in [("S1", tr1, ph1), ("S2", tr2, ph2)]:
    emit(f"\n{fen} - Phasen der Monsterserien:")
    serie_phasen = {"S2": [4, 5, 11, 12, 13, 14, 7, 49], "S1": [86, 88, 89, 90, 91, 102, 132]}[fen]
    for pid in sorted(set(serie_phasen) & set(phasen)):
        p = phasen[pid]
        tr_in = [t for t in tr if t["ph"] == pid]
        n_w = sum(1 for t in tr_in if t["r"] > 0)
        n_l = sum(1 for t in tr_in if t["r"] < 0)
        emit(f"  Phase {pid:>3}: {p['start']:%d.%m %H:%M} -> {p['ende']:%d.%m %H:%M} | "
             f"Dauer {p['dauer_h']:>6.1f}h ({p['dauer_h']/24:>5.1f}d) | {p['bars']:>4}C | "
             f"Trades {len(tr_in):>2} (W {n_w}/L {n_l}) | {p['marker']}")

with open("test/tmp_phasen_alter_schritt1.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"OK -> test/tmp_phasen_alter_schritt1.txt ({len(lines)} Zeilen)")
print(f"S1: {len(ph1)} Phasen, {len(tr1)} Trades | S2: {len(ph2)} Phasen, {len(tr2)} Trades")
