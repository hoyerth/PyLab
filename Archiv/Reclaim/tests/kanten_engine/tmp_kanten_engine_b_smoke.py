# -*- coding: utf-8 -*-
"""AUG-Smoke-Analyse Modus A vs. Modus B (Schritt 4 der V2-Arretierung).

Rein lesend: importiert tmp_kanten_engine_replay, spielt AUG (mt60) in beiden
Modi deterministisch durch und druckt die Evidenz fuer die 4 Verifikationsziele
(K9-Gravity, K14-Spiegel, K20-Touch-Zaehlung, K11-Body-Reclaim).

Zonen werden ueber Anker-Preis/Bar identifiziert (die K-IDs verschieben sich
in Modus B durch zusaetzliche Cluster-Geburten!).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tmp_kanten_engine_replay as m  # noqa: E402

CFG_A = m.HarnessKonfiguration(max_tage=60, modus="A")
CFG_B = m.HarnessKonfiguration(max_tage=60, modus="B")

erg_a = m._replay("AUG", CFG_A)
erg_b = m._replay("AUG", CFG_B)
print(f"AUG A: {erg_a.kanten_geboren} Kanten, {len(erg_a.signale)} Signale | "
      f"AUG B: {erg_b.kanten_geboren} Kanten, {len(erg_b.signale)} Signale")


def sig_zeile(s: m._Signal) -> str:
    t = s.trade
    r = f"{t.r_mult:+.2f}R/{t.resultat}" if t is not None else "keinTrade"
    return (f"    Sig K{s.kanten_id:2d}>{s.kanten_id_gegen:2d} "
            f"{s.richtung:5s} sweep={s.sweep_bar:4d} entry={s.entry_bar:4d} "
            f"E={s.entry_preis:8.3f}  {r}")


def kante_zeile(kid: int, k2: m._Kante) -> str:
    tb = ",".join(str(t.pivot_bar) for t in k2.touche)
    return (f"    K{kid:2d} {k2.seite:5s} geb={k2.geburts_bar:4d} "
            f"basis={k2.basis_preis:8.3f} anker={k2.anker_extremum:8.3f} "
            f"bal={k2.balance_preis:8.3f} {k2.zustand:9s} "
            f"nT={k2.touch_anzahl:2d} typB={int(k2.ist_typ_b)} "
            f"hand={int(k2.ist_handelbar)}  touche@[{tb}]")


def finde(erg, seite=None, preis=None, tol=0.02, geb_bar=None,
          touch_bars=None):
    out = []
    for kid, k2 in erg.kanten.items():
        if seite is not None and k2.seite != seite:
            continue
        if geb_bar is not None and k2.geburts_bar != geb_bar:
            continue
        if preis is not None:
            near = (abs(k2.basis_preis - preis) <= tol
                    or abs(k2.anker_extremum - preis) <= tol
                    or abs(k2.balance_preis - preis) <= tol)
            if not near:
                continue
        if touch_bars:
            tset = {t.pivot_bar for t in k2.touche}
            if not tset.issuperset(touch_bars):
                continue
        out.append((kid, k2))
    return out


def sig_zu(erg, kid: int):
    return [s for s in erg.signale if s.kanten_id == kid]


def diag_zeilen(erg, filter_f):
    return [z for z in erg.diagnose if filter_f(z)]


def block(titel: str):
    print("\n" + "=" * 100)
    print(titel)
    print("=" * 100)


# --- Ziel 1: K9-Zone OBEN 66.459 (V1: Balance-Gravity -> verfrühter Short) ---
block("ZIEL 1: OBEN-Zone anker/basis 66.459 (V1-K9 bar 107 / B-K13 bar 107)")
for name, erg in (("Modus A", erg_a), ("Modus B", erg_b)):
    print(f"[{name}] Kanten mit 66.459 (+/-0.02):")
    for kid, k2 in finde(erg, seite="OBEN", preis=66.459, geb_bar=107):
        print(kante_zeile(kid, k2))
        for s in sig_zu(erg, kid):
            print(sig_zeile(s))
# Verfrühter Short-Kandidat Bereich sweep 520..540
print("\nSignale mit sweep_bar in [515,545] (Modus A):")
for s in erg_a.signale:
    if 515 <= s.sweep_bar <= 545:
        print(sig_zeile(s))
print("Signale mit sweep_bar in [515,545] (Modus B):")
for s in erg_b.signale:
    if 515 <= s.sweep_bar <= 545:
        print(sig_zeile(s))
print("\nModus B: ABGELEHNT_RATCHET_INNEN OBEN, anker nahe 66.459, bars 200-530:")
for z in diag_zeilen(erg_b, lambda z: ("ABGELEHNT_RATCHET_INNEN" in z
                                       and " OBEN " in z and " anker= 66.45" in z
                                       and 200 <= int(z.split("bar ")[1].split()[0]) <= 530)):
    print("   ", z)

# --- Ziel 2: K14-Spiegel UNTEN (kein Anheben durch Higher Lows) ---
block("ZIEL 2: UNTEN-Zone 65.049 (V1-K14 bar 209) - Spiegel-Evidenz")
for name, erg in (("Modus A", erg_a), ("Modus B", erg_b)):
    print(f"[{name}] UNTEN-Kanten mit Preis 65.049 (+/-0.02):")
    for kid, k2 in finde(erg, seite="UNTEN", preis=65.049, tol=0.03):
        print(kante_zeile(kid, k2))
        for s in sig_zu(erg, kid):
            print(sig_zeile(s))
    # UNTEN-Kanten im Bereich geb 195..260 (nahe bar 209)
    print(f"  [-- {name}: UNTEN-Kanten geb_bar 190..260 --]")
    for kid, k2 in sorted(erg.kanten.items()):
        if k2.seite == "UNTEN" and 190 <= k2.geburts_bar <= 260:
            print(kante_zeile(kid, k2))
print("\nModus B: ABGELEHNT_RATCHET_INNEN UNTEN mit p > anker (hoechere Lows):")
rej = diag_zeilen(erg_b, lambda z: ("ABGELEHNT_RATCHET_INNEN" in z and " UNTEN " in z))
n = 0
for z in rej:
    teile = z.split()
    # Format: ... UNTEN p=63.918 anker=64.013
    p = float(z.split("p=")[1].split()[0])
    anker = float(z.split("anker=")[1])
    if p > anker:
        print("   ", z)
        n += 1
print(f"   (Summe UNTEN-Rejects mit p>anker: {n})")

# --- Ziel 3: K20-Zone 63.7x (Touches 627/632/635 zaehlen) ---
block("ZIEL 3: Zone mit Touch-Bars 627/632/635 (V1-K20)")
for name, erg in (("Modus A", erg_a), ("Modus B", erg_b)):
    print(f"[{name}] Kanten, die 627 UND 632 UND 635 getoucht haben:")
    for kid, k2 in finde(erg, touch_bars={627, 632, 635}):
        print(kante_zeile(kid, k2))
    print(f"[{name}] Kanten mit mind. einem Touch in {627,632,635}:")
    for kid, k2 in erg.kanten.items():
        tset = {t.pivot_bar for t in k2.touche}
        if tset & {627, 632, 635}:
            print(kante_zeile(kid, k2))
print("\nModus B Diagnose bars 600-700 (Ratchet/Touch/Cluster):")
for z in diag_zeilen(erg_b, lambda z: 600 <= int(z.split("bar ")[1].split()[0]) <= 700
                     if "bar " in z else False):
    print("   ", z)

# --- Ziel 4: Body-Reclaim (Close > anker) statt Docht-Zwang ---
block("ZIEL 4: OBEN-Zone 64.208 - Body-Reclaim nach Bruch")
print("Modus B body_reclaims gesamt:", erg_b.body_reclaims)
for name, erg in (("Modus A", erg_a), ("Modus B", erg_b)):
    print(f"[{name}] Kanten mit Preis 64.208 (+/-0.02):")
    for kid, k2 in finde(erg, preis=64.208, tol=0.02):
        print(kante_zeile(kid, k2))
        for s in sig_zu(erg, kid):
            print(sig_zeile(s))
print("\nModus A: Signale entry_bar 380..430 (Zone 64.2, V1-Verzoegerung):")
for s in erg_a.signale:
    if 380 <= s.entry_bar <= 430:
        print(sig_zeile(s))
print("Modus B: Signale entry_bar 380..430:")
for s in erg_b.signale:
    if 380 <= s.entry_bar <= 430:
        print(sig_zeile(s))
print("\nModus B Diagnose bars 390..410 (Bruch-/Reclaim-Umfeld):")
for z in diag_zeilen(erg_b, lambda z: 390 <= int(z.split("bar ")[1].split()[0]) <= 410
                     if "bar " in z else False):
    print("   ", z)
