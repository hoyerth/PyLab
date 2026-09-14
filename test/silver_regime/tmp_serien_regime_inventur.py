"""Read-only Serien- & Monats-Inventur S1/S2 (Teil A+B).
Quelle: test/tmp_S{1,2}_monatslauf_*.txt (Zeitstempel UTC). Erkennt alle max.
Verlustserien >= 4 und baut die Monats-Matrix. Report nach test/tmp_serien_regime_inventur.txt
"""
import sys, re, glob, os
from datetime import datetime
sys.stdout.reconfigure(encoding="utf-8")

def parse_monatsdatei(path):
    """Liefert Liste (nr, phase, dt, direction, entry, r) aus Monatsbericht."""
    out = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})\s+(LONG|SHORT)\s+([\d.]+)\s+([+-][\d.]+)", line)
        if m:
            nr, ph = int(m.group(1)), int(m.group(2))
            dt = datetime(int(m.group(5)), int(m.group(4)), int(m.group(3)), int(m.group(6)), int(m.group(7)))
            direction = m.group(8)
            entry = float(m.group(9))
            r = float(m.group(10))
            out.append((nr, ph, dt, direction, entry, r))
    return out

# --- Sammle Trade-Streams je Fenster ---
streams = {}
for fenster, jahr in [("S1", 2026), ("S2", 2025)]:
    files = sorted(glob.glob(f"test/tmp_{fenster}_monatslauf_{jahr}-*.txt"))
    trades = []
    for f in files:
        trades += parse_monatsdatei(f)
    trades.sort(key=lambda t: t[2])
    streams[fenster] = trades
    print(f"{fenster}: {len(trades)} Trades aus {len(files)} Monatsdateien "
          f"({trades[0][2].date()}..{trades[-1][2].date()})" if trades else f"{fenster}: leer")

lines = []
def emit(s=""):
    lines.append(s)

emit("=" * 100)
emit("SERIEN- & MONATS-INVENTUR S1/S2 (SILVER) | Quellen: Monatslauf-Berichte (UTC)")
emit("=" * 100)

for fenster in ["S1", "S2"]:
    tr = streams[fenster]
    emit(f"\n--- {fenster}: {len(tr)} Trades, kumuliert {sum(t[5] for t in tr):+.2f}R ---")

    # 1) Verlustserien >= 4
    emit("\nMAXIMALE VERLUSTSERIEN >= 4 (R < 0, aufeinanderfolgend):")
    emit("  von..bis Trade | Zeitraum (UTC)      | Tage | Phasen      | n  | SumR    | Dir-Zsm | Entry 1.->letzter | letzter Entry")
    i = 0
    while i < len(tr):
        if tr[i][5] < 0:
            j = i
            while j + 1 < len(tr) and tr[j + 1][5] < 0:
                j += 1
            n = j - i + 1
            if n >= 4:
                seg = tr[i:j + 1]
                phasen = sorted(set(t[1] for t in seg))
                tage = (seg[-1][2] - seg[0][2]).days
                dirs = {}
                for t in seg:
                    dirs[t[3]] = dirs.get(t[3], 0) + 1
                dirstr = " ".join(f"{k}{v}" for k, v in dirs.items())
                sumr = sum(t[5] for t in seg)
                e1, el = seg[0][4], seg[-1][4]
                emit(f"  T{seg[0][0]:>3}-T{seg[-1][0]:>3} | {seg[0][2]:%d.%m.%Y %H:%M}..{seg[-1][2]:%d.%m %H:%M} | {tage:>3}d | "
                     f"{phasen} | {n:>2} | {sumr:>+7.2f}R | {dirstr:<12} | {e1:.3f}->{el:.3f}")
            i = j + 1
        else:
            i += 1

    # 2) Monats-Matrix
    emit("\nMONATS-MATRIX:")
    emit("  Monat     | n   | WR     | SumR     | Long/Short | Voll-SL | maxSerie | Phasen")
    by_monat = {}
    for t in tr:
        by_monat.setdefault(t[2].strftime("%Y-%m"), []).append(t)
    for mon in sorted(by_monat):
        mt = by_monat[mon]
        n = len(mt)
        wins = [t for t in mt if t[5] > 0]
        wr = 100 * len(wins) / n
        sumr = sum(t[5] for t in mt)
        longs = sum(1 for t in mt if t[3] == "LONG")
        voll = sum(1 for t in mt if t[5] == -1.00)
        # max Serie in diesem Monat
        maxser = cur = 0
        for t in mt:
            if t[5] < 0:
                cur += 1
                maxser = max(maxser, cur)
            else:
                cur = 0
        phasen = sorted(set(t[1] for t in mt))
        emit(f"  {mon} | {n:>3} | {wr:>5.1f}% | {sumr:>+8.2f}R | {longs:>4}L/{n-longs:<3}S | {voll:>5}  | {maxser:>3}     | {phasen}")

    # 3) Top-3-Einzelmonate
    emit("\n  Beste 3 Monate: " + ", ".join(
        f"{m} {sum(t[5] for t in by_monat[m]):+.2f}R" for m in
        sorted(by_monat, key=lambda m: -sum(t[5] for t in by_monat[m]))[:3]))
    emit("  Schwaechste 3 Monate: " + ", ".join(
        f"{m} {sum(t[5] for t in by_monat[m]):+.2f}R" for m in
        sorted(by_monat, key=lambda m: sum(t[5] for t in by_monat[m]))[:3]))

with open("test/tmp_serien_regime_inventur.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("\n".join(lines[-60:]))
print(f"\n-> Report: test/tmp_serien_regime_inventur.txt ({len(lines)} Zeilen)")
