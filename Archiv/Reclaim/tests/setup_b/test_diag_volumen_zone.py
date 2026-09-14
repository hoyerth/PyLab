# test/test_diag_volumen_zone.py
"""Diagnose Volumenbereich: laufende Zone (bis Bar k) vs. finale Zone der Phase.

Verdacht (User): Die Verschlechterung nach dem Lookahead-Fix haengt am
Volumenbereich. Die laufende Zone (nur Bars bis Signal-Bar) kann andere
Kanten liefern als die finale Zone der gesamten Phase -> Signale an
"Phantom-Kanten", die in der voll entwickelten Zone nicht existieren.

Vorgehen: Das Hauptskript wird bis VOR der Signal-Ausfuehrung geladen
(exec), dann werden je Phase die Setup-B-Signale berechnet und mit der
finalen Zone der Phase verglichen. Testzeitraum = Skript-Default (August 2026).

Aufruf: python test/test_diag_volumen_zone.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "tmp_phasen_volumen_profil.py"

# --- Hauptskript bis kurz vor der Signal-Ausfuehrung laden (Definitionen +
#     Konstanten + Daten + Phasen + Zonen + find_reclaim_signals) ---
src = SRC.read_text(encoding="utf-8")
cut = src.index("reclaim_signals = []")
ns = {"__file__": str(SRC), "__name__": "test_diag"}
exec(compile(src[:cut], str(SRC), "exec"), ns)

df = ns["df"]
phases = ns["phases"]
find_reclaim_signals = ns["find_reclaim_signals"]
compute_volume_zone = ns["compute_volume_zone"]
pd = ns["pd"]

SCHWELLE_PCT = 0.05  # Kanten-Abweichung laufende vs. finale Zone (%)

print(f"=== DIAGNOSE VOLUMENBEREICH | Testzeitraum {ns['START']}..{ns['ENDE']} ===")
print(f"Phasen: {len(phases)} | Candles: {len(df)}\n")

# --- 1) Signale je Phase + Abweichung der laufenden Kante zur finalen Zone ---
alle = []
for pi, p in enumerate(phases, 1):
    vz = p.get("vol_zone")
    if vz is None:
        continue
    Uf, Lf, Pf = vz["U_zone"], vz["L_zone"], vz["POC"]
    for s in find_reclaim_signals(df, p):
        s["phase"] = pi
        if s["typ"] == "SHORT":
            abw = abs(s["U_laufend"] - Uf) / Uf * 100.0
            # liegt die laufende Kante ueberhaupt auf der finalen Zone?
            im_bereich = s["U_laufend"] <= Uf + Uf * SCHWELLE_PCT / 100
        else:
            abw = abs(s["L_laufend"] - Lf) / Lf * 100.0
            im_bereich = s["L_laufend"] >= Lf - Lf * SCHWELLE_PCT / 100
        s["abw_pct"] = abw
        s["im_bereich"] = im_bereich
        alle.append(s)

alle.sort(key=lambda s: (s["phase"], s["ts"]))

# --- 2) Statistik: konsistente vs. abweichende Signale ---
kons = [s for s in alle if s["abw_pct"] <= SCHWELLE_PCT]
abw = [s for s in alle if s["abw_pct"] > SCHWELLE_PCT]


def stat(gruppe, label):
    n = len(gruppe)
    w = sum(1 for s in gruppe if s["resultat"] == "GEWONNEN")
    l = sum(1 for s in gruppe if s["resultat"] == "VERLOREN")
    r = sum(s["r_mult"] for s in gruppe)
    wr = 100.0 * w / (w + l) if (w + l) else 0.0
    print(f"  {label:28s} n={n:3d} | WR {wr:3.0f}% | Summe R {r:+8.2f} | avg {r/n if n else 0:+.2f}")
    return n, w, l, r


print("--- Signale nach Kanten-Abweichung (laufende vs. finale Zone) ---")
n_k, _, _, r_k = stat(kons, f"Kante konsistent (<= {SCHWELLE_PCT}%)")
n_a, _, _, r_a = stat(abw, f"Kante abweichend  (>  {SCHWELLE_PCT}%)")
print(f"  GESAMT: {len(alle)} Signale (konsistent {n_k} / abweichend {n_a})")
print(f"  Abweichende Signale tragen bei: {r_a:+.2f}R | Konsistente: {r_k:+.2f}R")

# --- 3) Liste der abweichenden Signale (Phantom-Kanten-Kandidaten) ---
print(f"\n--- Abweichende Signale im Detail (Kante laufend vs. final) ---")
for s in abw:
    vz = phases[s["phase"] - 1]["vol_zone"]
    Uf, Lf = vz["U_zone"], vz["L_zone"]
    kante = s["U_laufend"] if s["typ"] == "SHORT" else s["L_laufend"]
    final = Uf if s["typ"] == "SHORT" else Lf
    print(f"  P{s['phase']:2d} {s['ts']:%d.%m %H:%M} {s['typ']:5s} "
          f"Kante {kante:.3f} vs. final {final:.3f} ({s['abw_pct']:+.2f}%) "
          f"-> {s['resultat']} {s['r_mult']:+.2f}R")

# --- 4) Zonen-Drift: laufende Zone an 5%-Schritten der laengsten Phase ---
print(f"\n--- Zonen-Drift der laengsten Phase (laufende Zone im Zeitverlauf) ---")
lp = max(phases, key=lambda p: p["i_ende"] - p["i_start"])
print(f"  Phase {phases.index(lp) + 1}: {lp['start']:%d.%m %H:%M} -> {lp['ende']:%d.%m %H:%M} "
      f"({lp['n_candles']}C)")
vz = lp["vol_zone"]
print(f"  FINALE Zone: OBEN {vz['U_zone']:.3f} | POC {vz['POC']:.3f} | UNTEN {vz['L_zone']:.3f}")
print(f"  {'Anteil':>6s} | {'Bars':>4s} | {'OBEN':>8s} | {'POC':>8s} | {'UNTEN':>8s} | {'Breite':>7s}")
span = lp["i_ende"] - lp["i_start"]
for q in range(5, 101, 5):
    k = lp["i_start"] + int(span * q / 100)
    z = compute_volume_zone(df.iloc[lp["i_start"]:k + 1])
    if z is None:
        continue
    breite = z["U_zone"] - z["L_zone"]
    print(f"  {q:5d}% | {k-lp['i_start']:4d} | {z['U_zone']:8.3f} | {z['POC']:8.3f} "
          f"| {z['L_zone']:8.3f} | {breite:7.3f}")

# --- 5) Wie viele Bars braucht die laufende Zone, bis sie "stabil" ist? ---
print(f"\n--- Stabilitaet: Abweichung laufende vs. finale Zone ueber Phasendauer ---")
for pi, p in enumerate(phases, 1):
    vz = p.get("vol_zone")
    if vz is None or (p["i_ende"] - p["i_start"]) < 60:
        continue
    Uf, Lf = vz["U_zone"], vz["L_zone"]
    span = p["i_ende"] - p["i_start"]
    aus = []
    for q in range(10, 101, 10):
        k = p["i_start"] + int(span * q / 100)
        z = compute_volume_zone(df.iloc[p["i_start"]:k + 1])
        if z is None:
            continue
        du = abs(z["U_zone"] - Uf) / Uf * 100.0
        dl = abs(z["L_zone"] - Lf) / Lf * 100.0
        aus.append(f"{q:3d}%:{max(du, dl):.2f}")
    print(f"  P{pi}: " + " ".join(aus))
