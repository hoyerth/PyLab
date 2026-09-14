# -*- coding: utf-8 -*-
"""Gegenueberstellung Definition 'erster nennenswerter Pullback':
(1) quantitativ: k - i_start < N Kerzen  (N = 20, 0-basiert = Mentor-Def.)
(2) strukturell: kein Gegenzug >= 0.15 USD vom laufenden Extrem VOR Signal (INIT)
Daten aus tmp_init_phase_audit_AUG.txt (Mapping 27/27 bitgenau).
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

# nr: (phase, R, alter1b, kls, n_pivots_vor_sig)
D = {
 1:(1,+1.29,9,"PB30",1), 2:(1,+1.69,15,"PB30",4), 3:(1,-0.29,36,"PB30",10),
 4:(2,-1.00,7,"PB30",2), 5:(2,-1.00,22,"PB30",7), 6:(2,+4.59,43,"PB30",13),
 7:(3,-1.00,2,"INIT",0), 8:(3,-1.00,21,"PB30",6), 9:(5,-1.00,24,"PB30",7),
 10:(5,-1.00,36,"PB30",10), 11:(5,-1.00,48,"PB30",13), 12:(5,-1.00,96,"PB30",24),
 13:(5,-1.00,111,"PB30",28), 14:(5,+6.71,156,"PB30",41), 15:(5,+6.60,182,"PB30",48),
 16:(6,-1.00,21,"PB30",8), 17:(6,-1.00,33,"PB30",11), 18:(7,-1.00,17,"PB30",4),
 19:(7,+4.26,31,"PB30",6), 20:(9,+3.06,35,"PB30",6), 21:(9,+2.67,56,"PB30",12),
 22:(9,-0.36,82,"PB30",18), 23:(9,+2.10,133,"PB30",37), 24:(9,+2.96,154,"PB30",43),
 25:(12,+1.83,2,"INIT",0), 26:(12,-1.00,39,"PB30",7), 27:(12,+0.86,97,"PB30",25)}
voll = {k:v for k,v in D.items() if v[1] <= -0.99}   # 13 Voll-SL
teil = {k:v for k,v in D.items() if -0.99 < v[1] < 0}  # 2 Teilverluste
win  = {k:v for k,v in D.items() if v[1] > 0}          # 12 Winner

for N in (10, 15, 20, 25, 30, 40):
    bl = {k:v for k,v in D.items() if v[2]-1 < N}   # alter1b-1 = 0b dist
    bvoll = {k:v for k,v in voll.items() if v[2]-1 < N}
    bwin  = {k:v for k,v in win.items()  if v[2]-1 < N}
    bteil = {k:v for k,v in teil.items() if v[2]-1 < N}
    r_save = -sum(v[1] for v in bvoll.values()) - sum(v[1] for v in bteil.values())
    r_kill = sum(v[1] for v in bwin.values())
    out = f"<{N:>2} Kerzen(0b): blockiert {len(bvoll)}VollSL+{len(bteil)}Teil+{len(bwin)}Win"
    out += f" | spart {r_save:+.2f}R | killt Winner {r_kill:+.2f}R | Netto {r_save-r_kill:+.2f}R"
    out += " | Kandidaten " + ",".join(f"T{k}" for k in sorted(bl))
    print(out)
print()
# Strukturell (INIT)
init = {k:v for k,v in D.items() if v[3] == "INIT"}
print("Strukturell INIT:", {k:(v[1],v[2]) for k,v in init.items()})
r_save = -sum(v[1] for k,v in init.items() if v[1]<0)
r_kill = sum(v[1] for k,v in init.items() if v[1]>0)
print(f"  -> spart {r_save:+.2f}R (T7) | killt {r_kill:+.2f}R (T25) | Netto {r_save-r_kill:+.2f}R")
print()
# Geister unter beiden Definitionen
print("Geister 0b-Distanz: T9", D[9][2]-1, "T10", D[10][2]-1, "T11", D[11][2]-1, "T26", D[26][2]-1)
print("Geister Pivots vor Signal:", D[9][4], D[10][4], D[11][4], D[26][4])
print()
print("Winner 0b-Distanzen:", {k: v[2]-1 for k, v in sorted(win.items())})
