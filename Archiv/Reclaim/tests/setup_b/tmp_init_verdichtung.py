# -*- coding: utf-8 -*-
"""Verdichtung Initialisierungsaudit -> Berichtszahlen (kein neuer Lauf)."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

# (nr, phase, R, alter1, anteil_pct) aus tmp_init_phase_audit_AUG.txt
D = {
 1:(1,1.29,9,14.1),2:(1,1.69,15,23.4),3:(1,-0.29,36,56.2),4:(2,-1.00,7,14.3),
 5:(2,-1.00,22,44.9),6:(2,4.59,43,87.8),7:(3,-1.00,2,3.5),8:(3,-1.00,21,36.8),
 9:(5,-1.00,24,12.9),10:(5,-1.00,36,19.4),11:(5,-1.00,48,25.8),12:(5,-1.00,96,51.6),
 13:(5,-1.00,111,59.7),14:(5,6.71,156,83.9),15:(5,6.60,182,97.8),16:(6,-1.00,21,38.9),
 17:(6,-1.00,33,61.1),18:(7,-1.00,17,21.8),19:(7,4.26,31,39.7),20:(9,3.06,35,20.2),
 21:(9,2.67,56,32.4),22:(9,-0.36,82,47.4),23:(9,2.10,133,76.9),24:(9,2.96,154,89.0),
 25:(12,1.83,2,2.0),26:(12,-1.00,39,38.2),27:(12,0.86,97,95.1)}
los = {k:v for k,v in D.items() if v[1]<0}
win = {k:v for k,v in D.items() if v[1]>0}
print("LOSER 15: Alter(1b) sortiert:", sorted(v[2] for v in los.values()))
print("  <40:", sum(1 for v in los.values() if v[2]<40), "| >=40:", sum(1 for v in los.values() if v[2]>=40))
print("WINNER 12: Alter(1b) sortiert:", sorted(v[2] for v in win.values()))
print("  <40:", sum(1 for v in win.values() if v[2]<40), "| >=40:", sum(1 for v in win.values() if v[2]>=40))
wj = sum(v[1] for v in win.values() if v[2]<40)
wr = sum(v[1] for v in win.values() if v[2]>=40)
print(f"Winner-R jung(<40): {wj:+.2f}R | reif(>=40): {wr:+.2f}R | gesamt {wj+wr:+.2f}R")
lj = sum(v[1] for v in los.values() if v[2]<40)
lr = sum(v[1] for v in los.values() if v[2]>=40)
print(f"Loser-R  jung(<40): {lj:+.2f}R | reif(>=40): {lr:+.2f}R | gesamt {lj+lr:+.2f}R")
# Voll-SL (R<=-0.99) Alters-Split
voll = {k:v for k,v in los.items() if v[1]<=-0.99}
print("VOLL-SL 13: <40:", sum(1 for v in voll.values() if v[2]<40), "| >=40:", sum(1 for v in voll.values() if v[2]>=40))
print("  Alter sortiert:", sorted(v[2] for v in voll.values()))
# Teilverluste
print("Teilverluste:", [(k,v[1],v[2]) for k,v in los.items() if v[1]>-0.99])
# Phasenanteil der Geister + Kontrast P5-Gesamt
print("Geister Phasenanteil %: T9", D[9][3], "T10", D[10][3], "T11", D[11][3], "T26", D[26][3])
print("P5-Gesamtlaenge Bars: P5-Signale bis 182 (T15) -> Phase > 186 Bars")
# Winner INIT/PB aus Log
print("INIT-Trades (keine bestaetigten Pivots, kein PB>=0.15): T7(L,-1.00R,A2), T25(L,+1.83R,A2)")
# Winner 12: Einzel-R
print("Winner-R je Trade:", {k:round(v[1],2) for k,v in sorted(win.items())})
