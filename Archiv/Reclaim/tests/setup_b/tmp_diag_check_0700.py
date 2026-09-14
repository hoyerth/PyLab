# test/tmp_diag_check_0700.py
"""Check: 04:15-SHORT vs. 07:00-Fakeout in B3 (P7+P8) - KORRIGIERT.

Die 07:00-Bar ist k=764 (M15). Pruefen:
1) 04:15-Signal (k=753, Entry 04:30 @ 66.953) -> SL 67.254 bei 07:00 (H 67.282)?
2) 07:00-Fakeout (k=764): waere Entry 07:15 @ Open 66.990 NICHT in den SL?
   -> Warum wurde kein Signal generiert? (POC-Filter? Cooldown? Bounce?)
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "tmp_phasen_volumen_profil.py"

src = SRC.read_text(encoding="utf-8")
cut = src.index("reclaim_signals = []")
ns = {"__file__": str(SRC), "__name__": "diag"}
exec(compile(src[:cut], str(SRC), "exec"), ns)

df = ns["df"]
phases = ns["phases"]
_laufende_zone = ns["_laufende_zone"]
_aufloesen = ns["_aufloesen"]
_bounce_nr = ns["_bounce_nr"]
pd = ns["pd"]
np = ns["np"]

P7, P8 = phases[6], phases[7]
box = {
    "i_start": P7["i_start"], "i_ende": min(phases[8]["i_start"] - 1, len(df) - 1),
    "h": list(P7["h_prices"]) + list(P8["h_prices"]),
    "h_ts": list(P7["h_ts"]) + list(P8["h_ts"]),
    "l": list(P7["l_prices"]) + list(P8["l_prices"]),
    "l_ts": list(P7["l_ts"]) + list(P8["l_ts"]),
}
p = {"i_start": box["i_start"], "i_ende": box["i_ende"],
     "h_prices": box["h"], "h_ts": box["h_ts"],
     "l_prices": box["l"], "l_ts": box["l_ts"]}

hi = df["high"].values; lo = df["low"].values
cl = df["close"].values; op = df["open"].values
ts = df["ts"].values
COOLDOWN = ns["MIN_SIGNAL_ABSTAND_BARS"]
MIN_BOUNCE = ns["MIN_RECLAIM_BOUNCE"]
MIN_CRV = ns["MIN_RECLAIM_CRV"]

# Index-Zuordnung der relevanten Bars (aus temporaerem Dump bekannt)
print("=== Index-Zuordnung ===")
for k in range(752, 767):
    print(f"  k={k} -> {pd.Timestamp(ts[k]):%d.%m %H:%M} H {hi[k]:.3f} C {cl[k]:.3f} O {op[k]:.3f}")

print(f"\n=== Laufende Zone + Signal-Bedingungen je Bar ===")
last_short_bar = -10**9
for k in range(752, 767):
    vz = _laufende_zone(df, p, k)
    if vz is None:
        continue
    U, L, POC = vz["U_zone"], vz["L_zone"], vz["POC"]
    nb_h, nb_l = _bounce_nr(p["h_prices"], p["h_ts"], p["l_prices"], p["l_ts"],
                            pd.Timestamp(ts[k]), U, L)
    cd = k - last_short_bar
    cd_ok = cd >= COOLDOWN
    # SHORT-Kandidaten-Bedingungen
    fake = hi[k] > U
    e_bar = e_preis = None
    if fake:
        if cl[k] <= U:
            e_bar, e_preis = k + 1, float(op[k + 1])
            rec = "in_bar"
        elif k + 2 <= p["i_ende"] and cl[k + 1] <= U:
            e_bar, e_preis = k + 2, float(op[k + 2])
            rec = "next_bar"
        else:
            rec = "kein Reclaim"
    e_ok = (e_preis is not None and e_preis > POC) if e_preis is not None else None
    bo_ok = nb_h >= MIN_BOUNCE if e_preis is not None else None
    flags = []
    if fake: flags.append("FAKEOUT")
    if rec and rec != "kein Reclaim":
        flags.append(rec)
    if e_ok is True:
        flags.append("e>POC OK")
    elif e_ok is False:
        flags.append(f"e<POC FILTER ({e_preis:.3f}<{POC:.3f})")
    if bo_ok is False:
        flags.append(f"Bo {nb_h}<{MIN_BOUNCE}")
    if not cd_ok:
        flags.append(f"CD-BLOCK (k-last={cd})")
    print(f"  {pd.Timestamp(ts[k]):%d.%m %H:%M} (k={k}) H {hi[k]:.3f} U {U:.3f} "
          f"POC {POC:.3f} | BoH {nb_h} | {' '.join(flags) or '-'}")
    if e_ok is True and bo_ok and cd_ok and rec and rec != "kein Reclaim":
        last_short_bar = k  # Signal wuerde gesetzt

# --- 1) Der tatsaechliche 04:15-Signal-Trade ---
print(f"\n=== 1) TATSÄCHLICHES SIGNAL k=753 (04:15), Entry 04:30 ===")
k = 753
vz = _laufende_zone(df, p, k)
U, L, POC = vz["U_zone"], vz["L_zone"], vz["POC"]
e_bar = k + 1
e_preis = float(op[e_bar])
sl = e_preis * (1 + ns["SL_PCT"] / 100.0)
tp1, tp2 = POC, L * (1 + ns["TP2_PUFFER_PCT"] / 100.0)
s = {"typ": "SHORT", "bar": k, "ts": pd.Timestamp(ts[k]), "einstieg_bar": e_bar,
     "einstieg_preis": e_preis, "U_laufend": U, "L_laufend": L, "POC": POC,
     "tp1": tp1, "tp2": tp2, "sl": sl, "bounce_nr": 3}
res = ns["_aufloesen"](df, s)
print(f"  U={U:.3f} | Entry {e_preis:.3f} | SL {sl:.3f} (Kante {U:.3f}, SL{' UNTER' if sl < U else ' UEBER'} Kante)")
print(f"  -> {res['resultat']} {res['r_mult']:+.2f}R (SL getroffen bei {res['exit1']:.3f})")

# --- 2) Hypothetischer 07:00-Signal-Trade (k=764, Entry 07:15) ---
print(f"\n=== 2) HYPOTHETISCHES SIGNAL k=764 (07:00), Entry 07:15 ===")
k = 764
vz = _laufende_zone(df, p, k)
U, L, POC = vz["U_zone"], vz["L_zone"], vz["POC"]
nb_h, nb_l = _bounce_nr(p["h_prices"], p["h_ts"], p["l_prices"], p["l_ts"],
                        pd.Timestamp(ts[k]), U, L)
e_bar = k + 1
e_preis = float(op[e_bar])
sl = e_preis * (1 + ns["SL_PCT"] / 100.0)
tp1, tp2 = POC, L * (1 + ns["TP2_PUFFER_PCT"] / 100.0)
s2 = {"typ": "SHORT", "bar": k, "ts": pd.Timestamp(ts[k]), "einstieg_bar": e_bar,
      "einstieg_preis": e_preis, "U_laufend": U, "L_laufend": L, "POC": POC,
      "tp1": tp1, "tp2": tp2, "sl": sl, "bounce_nr": nb_h}
res2 = ns["_aufloesen"](df, s2)
print(f"  U={U:.3f} POC={POC:.3f} L={L:.3f} BoH={nb_h}")
print(f"  Entry {e_preis:.3f} (Open {pd.Timestamp(ts[e_bar]):%d.%m %H:%M}) | SL {sl:.3f} (Kante {U:.3f}, SL{' UNTER' if sl < U else ' UEBER'} Kante)")
print(f"  e_preis > POC? {e_preis > POC} -> {'wuerde SIGNAL' if e_preis > POC else 'kein Signal (POC-Filter)'}")
print(f"  Wenn genommen: {res2['resultat']} {res2['r_mult']:+.2f}R "
      f"(H1 {res2['exit1']:.3f} {res2['grund1']} {res2['r1']:+.2f}R | "
      f"H2 {res2['exit2']:.3f} {res2['grund2']} {res2['r2']:+.2f}R)")
print(f"  SL getroffen? {res2['sl_hit1']}")

# --- Max-High nach Entry 07:15 bis zum Abwaertsbewegung ---
print(f"\n=== Max-High nach Entry (07:15) ===")
maxh = max(hi[e_bar + 1:])
print(f"  Max High nach Entry-Bar: {maxh:.3f} (SL {sl:.3f} -> {'UEBERLEBT' if maxh < sl else 'GETROFFEN'})")
