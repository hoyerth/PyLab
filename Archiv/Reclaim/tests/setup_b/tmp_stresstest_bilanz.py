# -*- coding: utf-8 -*-
"""AUG-Stresstest-Bilanz: Anker-Volumen-Ratio-Filter (spikege15/spikege20)
ueber alle 27 Baseline-Trades. Reine Analyse; Werte aus dem kanonischen
Audit-Log test/tmp_anchor_audit_AUG.txt (per-Trade R 2-dp, Summe +24.97R).
Erzeugt test/tmp_stresstest_bilanz.txt und haengt §8.11 an die Doku an.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

# --- 27 Trades: (id, Phase, R) aus Audit-Log-Tabelle (2-dp) ---
R = {1: 1.29, 2: 1.69, 3: -0.29, 4: -1.00, 5: -1.00, 6: 4.59, 7: -1.00,
     8: -1.00, 9: -1.00, 10: -1.00, 11: -1.00, 12: -1.00, 13: -1.00,
     14: 6.71, 15: 6.60, 16: -1.00, 17: -1.00, 18: -1.00, 19: 4.26,
     20: 3.06, 21: 2.67, 22: -0.36, 23: 2.10, 24: 2.96, 25: 1.83,
     26: -1.00, 27: 0.86}
WINNERS = {1, 2, 6, 14, 15, 19, 20, 21, 23, 24, 25, 27}
LOSERS = set(R) - WINNERS
assert len(WINNERS) == 12 and len(LOSERS) == 15
base = sum(R.values())
assert abs(base - 24.97) < 1e-9, base

# --- Membership (ohne Anker = wuerde geblockt) aus Audit-Log, Variante A/B ---
# A: irgendein Spike-Pivot im ±0.15-Fenster; B: naechster Pivot ≤0.15 UND Spike
VAR = {
    "A15": (1.5, {3, 5, 7, 12, 13, 22, 26}, {1, 2, 6, 19, 20, 21, 23, 24}),
    "A20": (2.0, {3, 5, 7, 9, 10, 12, 13, 16, 17, 22, 26},
            {1, 2, 6, 19, 20, 21, 23, 24, 25}),
    "B15": (1.5, {3, 5, 7, 9, 10, 11, 12, 13, 16, 18, 22, 26},
            {1, 2, 6, 19, 20, 21, 23, 24, 27}),
    "B20": (2.0, {3, 5, 7, 9, 10, 11, 12, 13, 16, 17, 18, 22, 26},
            {1, 2, 6, 19, 20, 21, 23, 24, 25, 27}),
}

def fmt_rs(ids):
    return ", ".join(f"T{i} {R[i]:+.2f}R" for i in sorted(ids))

out = []
out.append("AUG-Stresstest-Bilanz: Anker-Volumen-Ratio-Filter (spikege15/spikege20)")
out.append(f"Baseline AUG: 27 Trades (12W/15L), +{base:.2f}R")
for key, (thr, bl, bw) in VAR.items():
    prev = -sum(R[i] for i in bl)      # verhinderte Verluste (positiv)
    lost = sum(R[i] for i in bw)       # verlorene Gewinne (positiv)
    remain = set(R) - bl - bw
    rw = sum(R[i] for i in remain if R[i] > 0)
    rl = -sum(R[i] for i in remain if R[i] < 0)
    nw = sum(1 for i in remain if R[i] > 0)
    nl = len(remain) - nw
    filt = base + prev - lost
    out.append("")
    out.append(f"[{key}] Schwelle {thr:.1f}x | geblockte Verlierer {len(bl)}/15 "
               f"(+{prev:.2f}R verhindert) | geblockte Winner {len(bw)}/12 "
               f"(-{lost:.2f}R) | verbleibend {len(remain)} ({nw}W/{nl}L) "
               f"= {filt:+.2f}R | Delta {filt - base:+.2f}R")
    out.append(f"  geblockte Verlierer: {fmt_rs(bl)}")
    out.append(f"  geblockte Winner  : {fmt_rs(bw)}")
    out.append(f"  verbleibend       : {fmt_rs(remain)}")

# Gegencheck Winner-Gruppe, strikte Lesart B15
bw_b15 = VAR["B15"][2]
out.append("")
out.append("GEGENCHECK Winner (strikt spikege15, naechster Pivot): "
           f"{len(bw_b15)}/12 geblockt = {fmt_rs(bw_b15)} "
           f"(-{sum(R[i] for i in bw_b15):.2f}R)")

log_txt = "\n".join(out) + "\n"
with open("test/tmp_stresstest_bilanz.txt", "w", encoding="utf-8") as f:
    f.write(log_txt)
print(log_txt)
