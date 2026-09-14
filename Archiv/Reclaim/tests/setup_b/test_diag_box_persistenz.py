# test/test_diag_box_persistenz.py
"""Simulation BOX-PERSISTENZ: Die alte Box (66.45-63.76) lebt als EINE
Einheit weiter (10.08 - 19.08, bis der Kurs die Box nach oben verlaesst).

Vergleich zu P5-Signalen der aktuellen Segmentierung (14.-18.08):
  aktuell   : laufende Volume-Zone der frisch geoeffneten Phase P5
              (Zwischen-Kanten 64.7-65.9 -> 6 Verluste, dann 2 Gewinne an 66.28)
  BOX-SIM   : Kanten = alte Box 66.45 / 63.76 (konstant), POC = laufende
              Volume-Zone ab Box-Beginn 10.08

Aufruf: python test/test_diag_box_persistenz.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "tmp_phasen_volumen_profil.py"

src = SRC.read_text(encoding="utf-8")
cut = src.index("reclaim_signals = []")
ns = {"__file__": str(SRC), "__name__": "test_diag"}
exec(compile(src[:cut], str(SRC), "exec"), ns)

df = ns["df"]
phases = ns["phases"]
piv = ns["piv"]
_laufende_zone = ns["_laufende_zone"]
_aufloesen = ns["_aufloesen"]
pd = ns["pd"]
np = ns["np"]

MIN_BOUNCE = ns["MIN_RECLAIM_BOUNCE"]
MIN_CRV = ns["MIN_RECLAIM_CRV"]
COOLDOWN = ns["MIN_SIGNAL_ABSTAND_BARS"]
TP2_PUFFER = ns["TP2_PUFFER_PCT"] / 100.0
SL_P = ns["SL_PCT"] / 100.0
DENSITY_BAND = ns["DENSITY_BAND"]

U_BOX, L_BOX = 66.45, 63.76
T_START = pd.Timestamp("2026-08-10 00:00")
T_ENDE = pd.Timestamp("2026-08-19 17:45")  # bis zum echten Ausbruch nach oben

sub = df[(df["ts"] >= T_START) & (df["ts"] <= T_ENDE)].reset_index(drop=True)
i_start = int(df.loc[df["ts"] == T_START, "idx"].iloc[0])
i_ende = int(df.loc[df["ts"] == T_ENDE, "idx"].iloc[0])

# Pivots der Box-Phase (fuer Bounce-Zaehlung)
h_prices = piv.loc[(piv["typ"] == "H") & (piv["ts"] >= T_START) & (piv["ts"] <= T_ENDE), "price"].values
h_ts = piv.loc[(piv["typ"] == "H") & (piv["ts"] >= T_START) & (piv["ts"] <= T_ENDE), "ts"].values
l_prices = piv.loc[(piv["typ"] == "L") & (piv["ts"] >= T_START) & (piv["ts"] <= T_ENDE), "price"].values
l_ts = piv.loc[(piv["typ"] == "L") & (piv["ts"] >= T_START) & (piv["ts"] <= T_ENDE), "ts"].values


def bounce_nr_box(ts_k, U, L):
    n_h = 1 + sum(1 for pr, t in zip(h_prices, h_ts)
                  if t <= ts_k and abs(pr - U) <= DENSITY_BAND)
    n_l = 1 + sum(1 for pr, t in zip(l_prices, l_ts)
                  if t <= ts_k and abs(pr - L) <= DENSITY_BAND)
    return n_h, n_l


def sim_box():
    sigs = []
    hi, lo, cl, op = (df["high"].values, df["low"].values,
                      df["close"].values, df["open"].values)
    ts = df["ts"].values
    last_bar = {"SHORT": -10 ** 9, "LONG": -10 ** 9}
    for k in range(i_start, i_ende):
        vz = _laufende_zone(df, {"i_start": i_start, "i_ende": i_ende}, k)
        if vz is None:
            continue
        POC = vz["POC"]
        ts_k = ts[k]
        nb_h, nb_l = bounce_nr_box(ts_k, U_BOX, L_BOX)
        # OBERKANTE 66.45 -> SHORT
        if hi[k] > U_BOX:
            if cl[k] <= U_BOX:
                e_bar, e_preis, rec = k + 1, float(op[k + 1]), "in_bar"
            elif k + 2 <= i_ende and cl[k + 1] <= U_BOX:
                e_bar, e_preis, rec = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, rec = None, None
            if (rec is not None and e_bar <= i_ende and e_preis > POC
                    and nb_h >= MIN_BOUNCE and k - last_bar["SHORT"] >= COOLDOWN):
                sl = e_preis * (1 + SL_P)
                tp1 = POC
                tp2 = L_BOX * (1 + TP2_PUFFER)
                crv = abs(tp1 - e_preis) / abs(sl - e_preis) if sl != e_preis else 0
                if crv >= MIN_CRV:
                    last_bar["SHORT"] = k
                    s = {"typ": "SHORT", "bar": int(k), "ts": pd.Timestamp(ts[k]),
                         "reclaim": rec, "einstieg_bar": int(e_bar),
                         "einstieg_preis": e_preis, "U_laufend": U_BOX,
                         "L_laufend": L_BOX, "POC": POC, "tp1": tp1, "tp2": tp2,
                         "sl": sl, "crv": crv, "bounce_nr": nb_h}
                    s.update(_aufloesen(df, s))
                    sigs.append(s)
        # UNTERKANTE 63.76 -> LONG
        if lo[k] < L_BOX:
            if cl[k] >= L_BOX:
                e_bar, e_preis, rec = k + 1, float(op[k + 1]), "in_bar"
            elif k + 2 <= i_ende and cl[k + 1] >= L_BOX:
                e_bar, e_preis, rec = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, rec = None, None
            if (rec is not None and e_bar <= i_ende and e_preis < POC
                    and nb_l >= MIN_BOUNCE and k - last_bar["LONG"] >= COOLDOWN):
                sl = e_preis * (1 - SL_P)
                tp1 = POC
                tp2 = U_BOX * (1 - TP2_PUFFER)
                crv = abs(tp1 - e_preis) / abs(sl - e_preis) if sl != e_preis else 0
                if crv >= MIN_CRV:
                    last_bar["LONG"] = k
                    s = {"typ": "LONG", "bar": int(k), "ts": pd.Timestamp(ts[k]),
                         "reclaim": rec, "einstieg_bar": int(e_bar),
                         "einstieg_preis": e_preis, "U_laufend": U_BOX,
                         "L_laufend": L_BOX, "POC": POC, "tp1": tp1, "tp2": tp2,
                         "sl": sl, "crv": crv, "bounce_nr": nb_l}
                    s.update(_aufloesen(df, s))
                    sigs.append(s)
    return sigs


sigs = sim_box()
sigs.sort(key=lambda s: s["ts"])

w = sum(1 for s in sigs if s["resultat"] == "GEWONNEN")
l = sum(1 for s in sigs if s["resultat"] == "VERLOREN")
r = sum(s["r_mult"] for s in sigs)
n = len(sigs)
print(f"=== BOX-PERSISTENZ-SIMULATION | {T_START:%d.%m %H:%M} - {T_ENDE:%d.%m %H:%M} ===")
print(f"Box: OBEN {U_BOX:.3f} | UNTEN {L_BOX:.3f}\n")
print(f"BOX-SIM      : {n:2d} Signale | {w}W/{l}L | WR {100.0*w/(w+l) if w+l else 0:.0f}% | "
      f"{r:+8.2f}R | avg {r/n if n else 0:+.2f}")
print(f"Vergleich P5 (aktuell, 14.-18.08): 8 Signale | 2W/6L | WR 25% | +10.02R\n")

print("Einzelne Signale (Box-Persistenz):")
for s in sigs:
    print(f"  {s['ts']:%d.%m %H:%M} {s['typ']:5s} Entry {s['einstieg_preis']:.3f} "
          f"| POC {s['POC']:.3f} | Bo {s['bounce_nr']} | {s['resultat']} {s['r_mult']:+.2f}R")
